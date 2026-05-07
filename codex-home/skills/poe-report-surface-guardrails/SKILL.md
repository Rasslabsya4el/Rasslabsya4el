---
name: poe-report-surface-guardrails
description: Self-contained Poe Junkroan report-surface guardrail skill. Use to enforce accepted product output surfaces and block prose-only substitutes.
---

# Purpose

Guard accepted user-facing and operator-facing report/output surfaces. This
skill does not choose builds. It checks whether the requested publication surface
is allowed and evidence-backed.

# Runtime Boundary

Use only this skill bundle, sibling installed Poe Junkroan skills, and explicit
external dependencies. Do not depend on the development repo as runtime context.

Read:

1. `references/poe-skill-runtime-boundary.md`
2. `references/agentic-build-system-first-principles.md`

# Hard Rules

- A requested PoB artifact cannot be replaced by a mini guide.
- A final PoB import requires accepted verification and delivery surface.
- Report claims cite evidence refs.
- Baseline and conditional states remain separate.
- Block unsupported output surfaces with the smallest missing proof.

# Packaged Assets

- `templates/reports`
