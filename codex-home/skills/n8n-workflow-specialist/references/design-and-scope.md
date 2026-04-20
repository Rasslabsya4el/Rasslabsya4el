# Design And Scope

## Preferred Style

Use n8n as a thin orchestration layer.

Prefer:

- clean intake and validation
- explicit routing
- readable node names
- small, understandable branches
- Code nodes or helper scripts for concentrated logic when that is cleaner
- clear logging or result storage

Avoid:

- giant low-code tangles just to keep everything on canvas
- decorative AI nodes with no effect on routing
- fake complexity that makes import, testing, and review harder

## What Good Looks Like

A strong n8n project usually demonstrates several of:

- webhook or form intake
- validation
- routing by business result
- helper script or Code node transformation
- storage or audit trail
- explicit error handling
- reproducible local testing

## Host Vs Canvas Boundary

Keep this mental split:

- n8n: orchestration, branching, storage, responses, scheduling
- helper script or external logic: deterministic heavy lifting that would be brittle on canvas

If a task really belongs on the host, do not force it into twenty tiny nodes.
