# Project

`flyto-blueprint` is the Python pattern engine for discovering, composing,
expanding, learning, scoring, and persisting reusable Flyto2 workflows.

Product lines:

- cloud_apps_automation
- data
- zero_person_agent

Status: active open-source library

Core relationship: produces and validates workflow step dictionaries that a
Flyto2 Core host can execute. It does not execute workflows itself.

Evidence contract: Flyto2 AI owns the trusted real-workload host. This
repository owns strict run schemas, deterministic scorecards, cross-model /
cross-hardware / history gates, and real SQLite learning-lifecycle evidence.

Current published benchmark: v3, 4,000 raw records across three model families,
two hardware families, and one independent GitHub runner.

Health target: A
