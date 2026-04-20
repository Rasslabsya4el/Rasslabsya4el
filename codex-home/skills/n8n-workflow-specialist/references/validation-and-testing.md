# Validation And Testing

## Workflow JSON Validator

This skill bundles:

- `scripts/validate_workflow_json.py`

Run it after every workflow JSON edit:

```powershell
python "C:\Users\user\.codex\skills\n8n-workflow-specialist\scripts\validate_workflow_json.py" "<path-to-workflow-json>"
```

It checks:

- top-level structure
- node names and IDs
- connection references
- basic webhook/respond-to-webhook consistency
- isolated nodes warnings

## Standard Loop

Use this loop unless the task needs a different one:

1. edit the exported workflow JSON
2. run the validator
3. import the JSON into n8n
4. test the smallest relevant path
5. inspect execution details or returned payload
6. fix and repeat only on the failing path

## What To Test

Pick the narrowest proof that closes the contract:

- webhook request and response path
- form submission path
- manual trigger path
- helper-script invocation path
- Data Table or Sheets write path

Do not default to broad end-to-end retests if a focused repro is enough.

## Common Failure Modes

- duplicate node names
- `connections` source or target names that no longer exist
- missing `Respond to Webhook` on a `responseNode` flow
- wrong Code node output shape
- script path not visible to the n8n runtime
- missing env vars or credentials

## n8n-Specific Handoff Notes

When returning work under a generic worker contract, add these n8n-specific notes when relevant:

- workflow JSON path
- edited node names
- validation command
- import steps
- test payload or test steps
- credentials or env assumptions
- runtime path assumptions
