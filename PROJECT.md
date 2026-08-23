# Project

`flyto-blueprint` is Flyto2's independently usable procedure-memory package.
It stores, learns from, expands, scores, and persists reusable procedures, but
never executes them.

Flyto2 has three independently usable packages: `flyto-ai` owns intent,
provider governance, and routing; `flyto-blueprint` owns procedure memory;
`flyto-core` owns deterministic validation, execution, replay, and evidence.

Product lines:

- cloud_apps_automation
- data
- zero_person_agent

Status: active open-source library

Owned surfaces: reusable procedure learning and scoring; procedure expansion
and compatibility; procedure outcome history.

Non-goals: intent and provider governance; workflow execution; hosted product
and account logic; general-purpose mathematics, physics, chemistry, robotics,
or other domain solvers.

Evidence contract: Flyto2 AI owns the trusted real-workload host. This
repository owns strict run schemas, deterministic scorecards, cross-model /
cross-hardware / history gates, and real SQLite learning-lifecycle evidence.

Current published benchmark: v3, 4,000 raw records across three model families,
two hardware families, and one independent GitHub runner.

Health target: A
