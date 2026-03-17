# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Google Firestore storage backend for blueprints (flyto-cloud adapter)."""
import logging
from typing import Callable, List, Optional

from flyto_blueprint.storage.base import StorageBackend

logger = logging.getLogger(__name__)

_DEFAULT_COLLECTION = "learned_blueprints"


class FirestoreBackend(StorageBackend):
    """Persists blueprints in Google Firestore.

    Requires ``google-cloud-firestore`` and a Firestore client instance.
    """

    def __init__(self, db, collection: str = _DEFAULT_COLLECTION) -> None:
        """Initialize with a Firestore client and optional collection name."""
        self._db = db
        self._collection = collection

    def _col(self):
        """Return the Firestore collection reference."""
        return self._db.collection(self._collection)

    def load_all(self) -> List[dict]:
        """Stream all documents from the collection as dicts."""
        results = []
        for doc in self._col().stream():
            data = doc.to_dict()
            if data and isinstance(data, dict):
                results.append(data)
        return results

    def save(self, blueprint_id: str, data: dict) -> None:
        """Set (create or overwrite) a Firestore document."""
        self._col().document(blueprint_id).set(data)

    def update(self, blueprint_id: str, fields: dict) -> None:
        """Partially update fields on an existing Firestore document."""
        self._col().document(blueprint_id).update(fields)

    def load_one(self, blueprint_id: str) -> Optional[dict]:
        """Fetch a single document by ID, or return None."""
        doc = self._col().document(blueprint_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def delete(self, blueprint_id: str) -> None:
        """Delete a Firestore document by ID."""
        self._col().document(blueprint_id).delete()

    def atomic_update(
        self,
        blueprint_id: str,
        update_fn: Callable[[dict], Optional[dict]],
    ) -> Optional[dict]:
        """Run update_fn inside a Firestore transaction."""
        from google.cloud import firestore as firestore_lib

        doc_ref = self._col().document(blueprint_id)
        transaction = self._db.transaction()

        @firestore_lib.transactional
        def _txn(txn, ref):
            snapshot = ref.get(transaction=txn)
            if not snapshot.exists:
                return None
            data = snapshot.to_dict()
            result = update_fn(data)
            if result is not None:
                txn.set(ref, result)
            return result

        return _txn(transaction, doc_ref)
