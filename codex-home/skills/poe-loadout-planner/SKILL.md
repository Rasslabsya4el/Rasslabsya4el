---
name: poe-loadout-planner
description: Self-contained Poe Junkroan loadout planner skill. Use to plan progression between accepted PoB-backed loadouts with transition friction and evidence.
---

# Purpose

Plan progression between accepted build states. A loadout ladder optimizes not
only each loadout, but also transition cost, respec friction, item churn,
socket/link churn, market/craft burden, and power gain.

# Runtime Boundary

Use only this skill bundle, sibling installed Poe Junkroan skills, and explicit
external dependencies. Do not depend on the development repo as runtime context.

Read:

1. `references/poe-skill-runtime-boundary.md`
2. `references/agentic-build-system-first-principles.md`

# Hard Rules

- Start from accepted PoB-backed states or explicit blockers.
- Do not bypass required BuildReview or accepted candidate anchors.
- Score transitions explicitly; do not rank by DPS alone.
- Keep budget tier, required changes, optional changes, and evidence separate.

# Packaged Assets

- `templates/loadout_plan.md`
- `scripts/python/schemas/plan/loadout_plan.schema.json`
