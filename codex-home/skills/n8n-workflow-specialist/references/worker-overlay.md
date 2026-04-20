# Worker Overlay

## Purpose

This file augments the active worker role. Keep the role's normal report format and handoff contract; add n8n-specific discipline on top of it.

## If Editing Workflow JSON

- preserve importability
- keep node names stable unless there is a concrete reason to rename
- keep existing IDs for existing nodes
- do not invent credential IDs or secrets
- do not speculate on unsupported parameter shapes
- run the bundled validator after the edit

## If Editing Helper Scripts For n8n

- make them deterministic and non-interactive
- document env vars and path assumptions
- validate the script directly first
- then run the narrowest workflow-level proof that the integration works

## What To Return In Handoff Notes

Add these n8n-specific notes whenever relevant:

- workflow path
- edited node names
- validator command and result
- import steps
- test payload or exact test steps
- credentials or env assumptions
- runtime path assumptions

## Common n8n Traps

- broken `connections` after a rename
- wrong Code node return shape
- missing `Respond to Webhook`
- helper script not visible from the runtime process
- credentials expected in JSON instead of configured in UI
