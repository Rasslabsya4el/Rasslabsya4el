# Project Layout

## Goal

New n8n projects should be able to live in any repo or folder. They should not need to live under `C:\Coding\n8n`.

## Default Layout

If the current project has no better convention, use a project-local layout like:

```text
<project>/
  n8n/
    workflows/
    payloads/
    evidence/
  scripts/
  docs/
```

Reasonable variations:

- keep exported workflow JSON directly in `<project>/n8n/`
- keep helper scripts in `<project>/scripts/`
- keep workflow-specific helpers in `<project>/n8n/scripts/`

## Shared Runtime Boundary

Keep these out of the shared runtime folder:

- project workflow exports
- project payload fixtures
- project helper scripts
- project README or demo docs

The shared runtime folder is for:

- launcher scripts
- runtime database and logs
- shared local credentials

## Respect Existing Repo Shape

If the current repo already has a clear structure, preserve it. Do not force a new `n8n/` subtree just because this skill exists.
