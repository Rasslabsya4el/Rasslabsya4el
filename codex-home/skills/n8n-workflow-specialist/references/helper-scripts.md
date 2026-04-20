# Helper Scripts

## When A Helper Script Is Appropriate

Use an external Python or JS helper when one of these is true:

- the logic is awkward or brittle to express as many tiny n8n nodes
- a library is needed that does not exist as a native node
- the workflow must call an existing script or CLI
- the task is really orchestration plus a deterministic helper

Prefer n8n as the orchestration layer, not as the place where every detail is forced into the canvas.

## Contract For Scripts Called From n8n

Write helper scripts so that n8n can run them reliably:

- no interactive prompts
- deterministic inputs and outputs
- clear exit codes
- environment-variable driven secrets
- paths resolved from explicit arguments or documented defaults
- machine-readable stdout when the next step needs structured data

## Output Shape

If the next n8n step parses stdout, prefer stable JSON output rather than prose.

Good:

```json
{"status":"ok","items_processed":12}
```

Bad:

```text
Looks good, I processed twelve rows successfully.
```

## Environment Discipline

- never hardcode secrets
- document required env vars explicitly
- if the script depends on files, pass the path or define a clear default
- make sure the runtime where n8n runs can actually see that path

## Path Discipline

The current project can live anywhere. Keep helper scripts inside the current project by default.

Good examples:

- `<project>/scripts/fetch_data.py`
- `<project>/n8n/scripts/fetch_data.py`

Avoid storing project-specific helper logic in the shared runtime folder at `C:\Coding\n8n\self_hosted_n8n`.

## Validation

After editing a helper script:

- run a direct script-level check first
- then run the narrowest workflow-level smoke test that proves the integration contract

If a workflow node shells out to the script, the handoff notes should include:

- exact script path
- exact command used
- env vars required
- observed stdout or artifact shape
