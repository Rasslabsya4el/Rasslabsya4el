---
name: n8n-workflow-specialist
description: Design, patch, validate, and test importable n8n workflow projects, including workflow JSON exports, node wiring, webhooks, Code nodes, helper scripts invoked from n8n, and local self-hosted n8n testing. Use when the project is being implemented in n8n, the user mentions n8n workflows, nodes, canvas, Data Tables, self-hosted n8n, or a task directly supports an n8n workflow. Do not use for generic coding tasks that are not part of an n8n workflow.
---

# n8n Workflow Specialist

## Overview

Use this skill as a domain overlay for n8n projects. It is not a role replacement: keep the active orchestrator or worker skill as the source of truth for dispatch, reporting, and acceptance contracts, and use this skill only for n8n-specific workflow design, helper-script constraints, validation, and local runtime knowledge.

## Working Mode

1. Confirm that the task is actually n8n-related. If the work is generic backend or frontend coding with no direct n8n workflow integration, stop using this skill.
2. Keep project files inside the current project, not inside the shared runtime folder. By default, store workflow exports under the current project's own `n8n/` subtree unless the user asks for another layout.
3. Treat the shared local runtime at `C:\Coding\n8n\self_hosted_n8n` as infrastructure, not as the project workspace.
4. Prefer editing an existing exported workflow JSON over generating one from scratch. If there is no export yet, start from the templates in `assets/templates/`.
5. Load only the reference files needed for the current task.

## Which Reference To Read

- For workflow JSON edits, node wiring, webhook behavior, connections, IDs, templates, and importability, read `references/workflow-json.md`.
- For Python or JS helpers that n8n will invoke through `Execute Command` or similar orchestration, read `references/helper-scripts.md`.
- For validator usage, import-test loops, evidence collection, and common failure modes, read `references/validation-and-testing.md`.
- For the shared local self-hosted runtime and launcher location, read `references/local-runtime.md`.
- For host-vs-container path behavior, Execute Command, and file access rules, read `references/runtime-and-files.md`.
- For Code node language choice, task-runner assumptions, built-in methods, and item-linking traps, read `references/code-node-runtime.md`.
- For choosing between Data Tables, workflow static data, variables, and external stores, read `references/storage-and-state.md`.
- For credential rebinding, export sanitization, and multi-environment promotion rules, read `references/credentials-and-promotion.md`.
- For development-time mocking, pinning, and lightweight execution evidence, read `references/development-loop.md`.
- For optional workflow-as-code and GitOps tooling beyond plain JSON export/import, read `references/optional-gitops-and-ai-tooling.md`.
- For recommended per-project layout outside the shared runtime repo, read `references/project-layout.md`.
- If the active role is orchestrator, also read `references/orchestrator-overlay.md`.
- If the active role is worker, also read `references/worker-overlay.md`.
- For project-shaping decisions such as thin orchestration vs external helpers, read `references/design-and-scope.md`.
- For official documentation links and optional live-instance tooling notes, read `references/official-links.md`.

## Ground Truth Order

Resolve uncertainty in this order:

1. The user's current requirements and the current project's actual files.
2. The exported workflow JSON or helper script you are editing.
3. The reusable templates and validator bundled in this skill.
4. Official n8n documentation when local evidence is not enough.

## Bundled Resources

- `scripts/validate_workflow_json.py`: structural validator for exported workflow JSON files.
- `assets/templates/webhook_validate_route_response.json`: baseline webhook template.
- `assets/templates/webhook_validate_single_action_response.json`: baseline single-action template.
- `assets/templates/workflow_patch_request.md`: useful patch-request scaffold.
- `assets/templates/code/normalize_and_chunk_text.js`: reusable Code node snippet.
- `assets/templates/code/simple_keyword_eval.js`: reusable Code node snippet.

## Shared Examples

If you need local examples of finished projects, inspect these optional example repos on this machine:

- `C:\Coding\improvado_vendor_onboarding`
- `C:\Coding\telegram_public_history_to_google_sheets`
- `C:\Coding\telegram_service_directory_to_google_sheets`

Do not treat those example folders as the default place for new projects. They are references only.

## Result Standard

A good n8n result is:

- importable into n8n
- structurally valid
- explicit about credentials and environment assumptions
- easy to smoke-test in the local self-hosted instance
- kept inside the current project rather than mixed into shared runtime state
