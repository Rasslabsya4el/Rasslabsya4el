# Local Runtime

## Shared Runtime Root

The shared local self-hosted n8n runtime on this machine lives at:

`C:\Coding\n8n\self_hosted_n8n`

Use it as shared infrastructure. Do not treat it as the default project workspace.

## Launcher

Current launcher:

- `C:\Coding\n8n\self_hosted_n8n\start_n8n_local.ps1`

After startup, the UI is available at:

- `http://localhost:5678`

## What The Current Launcher Sets

Current shared launcher config:

- `N8N_USER_FOLDER=C:\Coding\n8n\self_hosted_n8n\data`
- `N8N_HOST=localhost`
- `N8N_PORT=5678`
- `N8N_PROTOCOL=http`
- `NODES_EXCLUDE=["n8n-nodes-base.localFileTrigger"]`

It also enables `Execute Command`.

## Existing Shared Extras

The current launcher also sets:

- `N8N_VENDOR_PAYLOAD_DIR` for an existing local demo flow
- Telegram env vars from `C:\Coding\n8n\self_hosted_n8n\credentials\telegram\tg_env.local` if that file exists

Treat those as shared runtime conveniences for existing local examples, not as requirements for every new project.

## Important Boundary

- keep workflow exports, helper scripts, payload fixtures, and project docs inside the current project
- keep runtime state, database, logs, and shared credentials inside `C:\Coding\n8n\self_hosted_n8n`

Do not casually rewrite shared runtime state or credentials while working on a project task.
