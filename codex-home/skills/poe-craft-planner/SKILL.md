---
name: poe-craft-planner
description: Self-contained Poe Junkroan craft planner skill. Use to estimate craft feasibility, expected cost, and buy-vs-craft evidence for one concrete item spec.
---

# Purpose

Estimate craft paths for a concrete item spec in a build context. Craft evidence
informs build decisions; it does not replace PoB comparison or final build
choice.

# Runtime Boundary

Use only this skill bundle, sibling installed Poe Junkroan skills, and explicit
external dependencies. Do not depend on the development repo as runtime context.

Read:

1. `references/poe-skill-runtime-boundary.md`
2. `references/agentic-build-system-first-principles.md`

# Hard Rules

- State item base, required mods, optional mods, league/economy, and freshness.
- Separate deterministic steps from expected-cost or variance estimates.
- Return craft evidence and blockers, not final build decisions.
- If Craft of Exile or required data is unavailable, fail closed with the
  smallest missing dependency.

# Packaged Assets

- `scripts/python/src/poe_build_research/craft`
- `scripts/python/src/poe_build_research/market` for shared realm/source
  contracts used by craft evidence
- `scripts/python/schemas/craft`
