---
name: poe-trade-evaluator
description: Self-contained Poe Junkroan trade evaluator skill. Use to price or compare trade items for one concrete PoE build route with explicit market provenance and freshness.
---

# Purpose

Evaluate market price, availability, and trade risk for item specs or concrete
items in a build context. Trade evidence informs build decisions; it does not
replace PoB as calculator or make a public item/build final authority.

# Runtime Boundary

Use only this skill bundle, sibling installed Poe Junkroan skills, and explicit
external dependencies. Do not depend on the development repo as runtime context.

Read:

1. `references/poe-skill-runtime-boundary.md`
2. `references/agentic-build-system-first-principles.md`

# Hard Rules

- Always record league/economy, query shape, timestamp/freshness, and source.
- Distinguish exact item pricing from rough affix/spec availability.
- Do not price Early Game baseline rare gear unless the output promises an
  exact shopping list or non-baseline cost driver.
- Return evidence artifacts, not standalone build decisions.

# Packaged Assets

- `scripts/python/src/poe_build_research/market`
- `scripts/python/schemas/market`
