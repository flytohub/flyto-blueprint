# Robotics and vision Blueprint adoption gate

Date: 2026-08-10
Owner: claude
Branch: main

## Finished

- Recorded the current, evidence-gated adoption boundary for robotics/vision
  work in `STATE.md` and `DECISIONS.md`. Documentation only: no runtime, test,
  blueprint, config, or dependency change.
- Confirmed that a Blueprint search for `robotics vision exhibition` returns no
  candidates. This is an honest not-applicable result, not a failure and not a
  success. Flyto2 AI may continue through Core discovery and validation.

## Evidence actually held

An independent read-only lower check ran current sibling sources against the
real `core.mcp_handler.validate_params`.

Accepted:

- `robotics.move(distance_m=0.05, speed=0.05)`
- `robotics.turn(degrees=15, angular_speed=0.4)`
- `robotics.stop(seconds=0)`
- `vision.observe(zone='arena')`

Rejected:

- missing `distance_m`
- `distance_m=999`
- missing `degrees`
- non-text `zone`
- unknown module `robotics.fly`

## Honest current limit

This proves module registration and parameter validation only. There was no
`execute` call, no gateway request, no pixels, no physical camera identity, no
robot or motor action, no authenticated Cloud route, and no commit, push, or
deploy.

Gazebo results and gateway reports produced in lower repositories are evidence
about those repositories, not Blueprint outcome evidence. Physical acceptance
remains pending the OpenCR/device-side issue.

## Verification

The authoritative host run passed all four repository-configured checks from
`.flyto/coding.yaml`: `compile`, Ruff `lint`, `generated_reference`, and the
full `pytest` suite. This change is Markdown-only, so no source declaration,
catalog entry, or MCP schema moved.

This is separate from the independent cross-repository check described above,
which exercised `core.mcp_handler.validate_params` only and is not evidence
about this repository.

## Next evidence step

Do not ship an official robotics/vision Blueprint yet. Promotion requires
repeated trusted real-workload outcomes plus a completed physical loop, and the
recorded promotion checklist in `DECISIONS.md` (2026-08-10).
