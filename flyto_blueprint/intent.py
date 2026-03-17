# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Intent-based blueprint matcher — system-level routing that replaces prompt reliance.

Three matching layers (cascading fallback):
1. Embedding similarity (semantic, highest quality)
2. Keyword BM25 (fast, no API call)
3. Tag word-match (existing, baseline)

Usage:
    matcher = IntentMatcher(blueprints)
    await matcher.build_index(api_key="sk-...")      # one-time, cached
    results = await matcher.match("scrape prices from amazon")
    # → [{"id": "browser_scrape", "score": 0.92, "method": "embedding"}, ...]
"""
import hashlib
import json
import logging
import math
import os
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Cache dir for embedding vectors
_CACHE_DIR = Path(os.environ.get("FLYTO_CACHE_DIR", Path.home() / ".flyto")) / "bp_embeddings"

# Synonym expansion for keyword matching
SYNONYMS: Dict[str, List[str]] = {
    "scrape": ["extract", "crawl", "fetch", "get", "pull"],
    "screenshot": ["capture", "snap", "photo", "image"],
    "download": ["fetch", "get", "save", "retrieve"],
    "fill": ["type", "input", "enter", "write", "submit"],
    "send": ["post", "notify", "dispatch", "push", "deliver"],
    "login": ["auth", "signin", "sign-in", "authenticate", "log-in", "signon"],
    "convert": ["transform", "parse", "export", "change"],
    "compress": ["optimize", "reduce", "shrink", "minify"],
    "resize": ["scale", "dimension", "crop"],
    "search": ["find", "query", "lookup", "google"],
    "monitor": ["check", "health", "ping", "uptime", "status"],
    "pdf": ["document", "print", "export"],
    "email": ["mail", "smtp", "inbox"],
    "slack": ["notification", "webhook", "alert", "message"],
    "csv": ["spreadsheet", "excel", "table", "data"],
    "json": ["api", "data", "parse", "response"],
    "ocr": ["text", "recognize", "read", "scan"],
    "performance": ["speed", "vitals", "audit", "lighthouse"],
    "responsive": ["mobile", "tablet", "desktop", "breakpoint"],
}

# Reverse synonym map: "crawl" → ["scrape"]
_REVERSE_SYNONYMS: Dict[str, List[str]] = {}
for _canonical, _aliases in SYNONYMS.items():
    for _alias in _aliases:
        _REVERSE_SYNONYMS.setdefault(_alias, []).append(_canonical)
    _REVERSE_SYNONYMS.setdefault(_canonical, []).extend(_aliases)


def expand_query(query: str) -> List[str]:
    """Expand query words with synonyms. Returns unique expanded word list."""
    words = query.lower().split()
    expanded = set(words)
    for word in words:
        if word in _REVERSE_SYNONYMS:
            expanded.update(_REVERSE_SYNONYMS[word])
        if word in SYNONYMS:
            expanded.update(SYNONYMS[word])
    return list(expanded)


def _pack_vector(vec: List[float]) -> bytes:
    return struct.pack("{}f".format(len(vec)), *vec)


def _unpack_vector(data: bytes) -> List[float]:
    n = len(data) // 4
    return list(struct.unpack("{}f".format(n), data))


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _bp_text(bp: dict) -> str:
    """Build searchable text from blueprint metadata."""
    parts = [
        bp.get("name", ""),
        bp.get("description", ""),
        " ".join(bp.get("tags", [])),
        bp.get("id", "").replace("_", " "),
    ]
    return " ".join(parts)


class IntentMatcher:
    """System-level blueprint matcher with embedding + keyword + tag fallback."""

    def __init__(self, blueprints: Dict[str, dict]) -> None:
        self._blueprints = blueprints
        self._embeddings: Dict[str, List[float]] = {}  # bp_id → vector
        self._index_built = False

    async def build_index(self, api_key: Optional[str] = None) -> bool:
        """Build embedding index for all blueprints. Cached to disk."""
        api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            logger.info("No API key — embedding index skipped, using keyword-only")
            return False

        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Check cache freshness: hash of blueprint IDs
        bp_ids = sorted(self._blueprints.keys())
        cache_hash = hashlib.md5(json.dumps(bp_ids).encode()).hexdigest()[:12]
        cache_file = _CACHE_DIR / "index_{}.json".format(cache_hash)

        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cached = json.load(f)
                self._embeddings = {k: v for k, v in cached.items() if k in self._blueprints}
                self._index_built = True
                logger.info("Loaded cached embedding index (%d vectors)", len(self._embeddings))
                return True
            except Exception as e:
                logger.debug("Cache load failed: %s", e)

        # Build embeddings via OpenAI API
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)

            texts = []
            ids = []
            for bp_id, bp in self._blueprints.items():
                if bp.get("retired"):
                    continue
                texts.append(_bp_text(bp))
                ids.append(bp_id)

            # Batch embed (max 2048 per call)
            all_embeddings = []
            for i in range(0, len(texts), 100):
                batch = texts[i:i + 100]
                resp = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=batch,
                )
                for item in resp.data:
                    all_embeddings.append(item.embedding)

            for bp_id, vec in zip(ids, all_embeddings):
                self._embeddings[bp_id] = vec

            # Cache to disk
            with open(cache_file, "w") as f:
                json.dump(self._embeddings, f)

            self._index_built = True
            logger.info("Built embedding index (%d vectors)", len(self._embeddings))
            return True

        except Exception as e:
            logger.warning("Embedding index build failed: %s", e)
            return False

    async def match(
        self,
        query: str,
        api_key: Optional[str] = None,
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Match user intent to blueprints. Returns ranked results.

        Cascading strategy:
        1. If embedding index exists → semantic similarity
        2. Always → keyword BM25 with synonym expansion
        3. Merge and deduplicate
        """
        results: Dict[str, Dict[str, Any]] = {}

        # Layer 1: Embedding similarity
        if self._index_built and self._embeddings:
            try:
                emb_results = await self._match_embedding(query, api_key, top_k, threshold)
                for r in emb_results:
                    results[r["id"]] = r
            except Exception as e:
                logger.debug("Embedding match failed: %s", e)

        # Layer 2: Keyword matching with synonym expansion
        kw_results = self._match_keywords(query, top_k)
        for r in kw_results:
            if r["id"] in results:
                # Boost score if both methods agree
                results[r["id"]]["score"] = max(results[r["id"]]["score"], r["score"])
                results[r["id"]]["method"] = "both"
            else:
                results[r["id"]] = r

        # Sort by score descending
        ranked = sorted(results.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]

    async def _match_embedding(
        self, query: str, api_key: Optional[str], top_k: int, threshold: float,
    ) -> List[Dict[str, Any]]:
        """Semantic matching via embedding cosine similarity."""
        api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return []

        import openai
        client = openai.OpenAI(api_key=api_key)
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=[query],
        )
        query_vec = resp.data[0].embedding

        scored = []
        for bp_id, bp_vec in self._embeddings.items():
            sim = _cosine_similarity(query_vec, bp_vec)
            if sim >= threshold:
                scored.append({"id": bp_id, "score": sim, "method": "embedding"})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def _match_keywords(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Keyword matching with synonym expansion and BM25-like scoring."""
        expanded = expand_query(query)
        scored = []

        for bp_id, bp in self._blueprints.items():
            if bp.get("retired"):
                continue

            score = 0.0
            tags = [t.lower() for t in bp.get("tags", [])]
            name_words = bp.get("name", "").lower().split()
            desc = bp.get("description", "").lower()
            id_words = bp_id.lower().replace("_", " ").split()
            all_bp_words = set(tags + name_words + id_words)

            # Count how many expanded query words hit blueprint words
            hits = 0
            for word in expanded:
                if word in all_bp_words:
                    # Exact tag match is strongest signal
                    if word in tags:
                        score += 3.0
                    elif word in id_words:
                        score += 2.0
                    elif word in name_words:
                        score += 1.5
                    hits += 1
                elif any(word in t for t in tags):
                    score += 1.0
                    hits += 1
                elif word in desc:
                    score += 0.5
                    hits += 1

            # Coverage bonus: what % of original query words matched?
            original_words = query.lower().split()
            original_hits = sum(1 for w in original_words if w in all_bp_words
                                or any(w in t for t in all_bp_words))
            if len(original_words) > 0:
                coverage = original_hits / len(original_words)
                score *= (0.5 + coverage * 0.5)

            # Quality bonus for learned blueprints
            if bp.get("_source") == "learned":
                score += bp.get("score", 50) / 200.0

            if score > 0:
                # Normalize to 0-1 range (approximate)
                normalized = min(1.0, score / 15.0)
                scored.append({"id": bp_id, "score": normalized, "method": "keyword"})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


# ---------------------------------------------------------------------------
# Query → Blueprint mapping tracker (for evolution learning)
# ---------------------------------------------------------------------------

class QueryTracker:
    """Track query → blueprint mappings for learning which blueprints users prefer.

    Stores in SQLite for persistence. Used to:
    1. Boost frequently-used blueprints in search results
    2. Train better intent classifiers over time
    3. Detect gaps (queries with no blueprint match)
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or str(
            Path(os.environ.get("FLYTO_CACHE_DIR", Path.home() / ".flyto")) / "query_tracker.db"
        )
        self._initialized = False

    async def init(self) -> None:
        if self._initialized:
            return
        import aiosqlite
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS query_map (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    blueprint_id TEXT NOT NULL,
                    success INTEGER DEFAULT 0,
                    timestamp REAL NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS query_gaps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_qm_query ON query_map(query)"
            )
            await db.commit()
        self._initialized = True

    async def record_match(self, query: str, blueprint_id: str, success: bool) -> None:
        """Record that a query was matched to a blueprint."""
        await self.init()
        import time
        import aiosqlite
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO query_map (query, blueprint_id, success, timestamp) VALUES (?, ?, ?, ?)",
                (query.lower().strip(), blueprint_id, int(success), time.time()),
            )
            await db.commit()

    async def record_gap(self, query: str) -> None:
        """Record a query that had no blueprint match — identifies coverage gaps."""
        await self.init()
        import time
        import aiosqlite
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO query_gaps (query, timestamp) VALUES (?, ?)",
                (query.lower().strip(), time.time()),
            )
            await db.commit()

    async def get_popular_mappings(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get most popular query→blueprint mappings for training data."""
        await self.init()
        import aiosqlite
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("""
                SELECT query, blueprint_id, COUNT(*) as count,
                       SUM(success) as successes
                FROM query_map
                GROUP BY query, blueprint_id
                ORDER BY count DESC
                LIMIT ?
            """, (limit,))
            rows = await cursor.fetchall()
            return [
                {"query": r[0], "blueprint_id": r[1], "count": r[2], "successes": r[3]}
                for r in rows
            ]

    async def get_gaps(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get queries with no blueprint match — candidates for new blueprints."""
        await self.init()
        import aiosqlite
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("""
                SELECT query, COUNT(*) as count
                FROM query_gaps
                GROUP BY query
                ORDER BY count DESC
                LIMIT ?
            """, (limit,))
            rows = await cursor.fetchall()
            return [{"query": r[0], "count": r[1]} for r in rows]
