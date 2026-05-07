---
name: poe-build-review
description: Self-contained Poe Junkroan BuildReview skill. Use to review one existing PoB-backed build, identify bottlenecks, compare bounded fixes, and publish only proof-backed review output.
---

# Purpose

Review one existing PoB-backed build. Do not rebuild the archetype unless the
user explicitly asks for a full rebuild.

# Runtime Boundary

Use only this skill bundle, sibling installed Poe Junkroan skills, and explicit
external dependencies. Do not depend on the development repo as runtime context.

Read:

1. `references/poe-skill-runtime-boundary.md`
2. `references/agentic-build-system-first-principles.md`
3. `references/runtime-operation-contract.md`

# Review Loop

Inspect the build, form bounded hypotheses, test or request PoB trials, compare
before/after metrics, record resource cost and invasiveness, then report ranked
fixes. A review claim without PoB evidence is not accepted.

# Hard Rules

- No accepted fix without before/after PoB metrics.
- No material recommendation without resource cost and alternatives considered.
- No full rebuild when the task is bounded review.
- No prose-only "looks better" verdict.
- Keep baseline and conditional lanes separate.

# Packaged Assets

- `templates/build_review.md`
- `scripts/python/schemas/plan/build_review.schema.json`
