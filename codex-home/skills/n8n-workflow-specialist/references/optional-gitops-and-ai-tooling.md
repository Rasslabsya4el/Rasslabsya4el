# Optional GitOps And AI Tooling

## Default

The default workflow for this skill is still:

- export
- patch
- validate
- import
- smoke-test

This keeps the skill usable without extra tools.

## Optional Upgrade: n8n-as-code

If a project becomes large enough that raw JSON exports are painful, consider adding `n8n-as-code`.

High-value features:

- explicit pull and push workflow sync
- local workflow files designed for review and diffs
- validation before push
- agent-oriented node schema and docs dataset

This is optional. Do not require it for normal n8n work in this environment.

## Optional Upgrade: Source Control And Environments

n8n has source control and environments features, but they are plan-gated and not a full replacement for normal Git review workflows.

Use them only if:

- the target instance supports the feature
- the user explicitly wants instance-level Git integration

## Optional Upgrade: External Secrets

For multi-environment or more mature setups, external secrets may be cleaner than embedding credential assumptions in local docs. Treat this as an advanced integration, not a default requirement.
