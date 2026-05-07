---
name: poe-ninja-researcher
description: Self-contained Poe Junkroan public-build researcher skill. Use to collect poe.ninja/public-build priors, benchmarks, and provenance-backed pattern leads.
---

# Purpose

Collect public-build evidence, package priors, and research leads. Public builds
are priors or benchmarks only. They are not created-build output and must not be
source-copied into final Direct Build publication.

# Runtime Boundary

Use only this skill bundle, sibling installed Poe Junkroan skills, and explicit
external dependencies. Do not depend on the development repo as runtime context.

Read:

1. `references/poe-skill-runtime-boundary.md`
2. `references/agentic-build-system-first-principles.md`

# Hard Rules

- Preserve source, league, timestamp, URL/profile/listing refs, and freshness.
- Distinguish repeated pattern leads from final proof.
- Never treat absence of poe.ninja examples as a build impossibility proof.
- Never publish a public PoB/profile as an agent-authored created build.

# Packaged Assets

- `scripts/python/src/poe_build_research/data`
- `scripts/python/schemas/data`
