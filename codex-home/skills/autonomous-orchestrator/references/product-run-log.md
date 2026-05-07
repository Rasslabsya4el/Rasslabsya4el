# Product Run Log

Use this reference before appending to `.orchestrator/PRODUCT_RUN_LOG.md`.

## Purpose

This file is for the human owner of the project.
It must explain the autonomous wave in simple product language, as if the reader were a smart fifteen-year-old.

This file is not:

- a raw child-agent transcript;
- a command log;
- a file-diff inventory;
- a place for module names, function names, branches, env vars, or agent ids.

## Path

Append to:

- `.orchestrator/PRODUCT_RUN_LOG.md`

Create the file if it does not exist.

## One Entry Per Autonomous Wave

Append one entry after each completed autonomous wave.

Use this shape:

```text
## Turn 007 | 2026-04-23 19:05 Europe/Budapest

What we tried
- Short plain-language goal for this wave.

What happened
- Short plain-language result.

How it happened
- The orchestrator created or reused specific work items.
- A worker, researcher, validator, or other child role completed the work.
- The orchestrator accepted, rejected, retried, or blocked the result.

Why this matters for MVP
- Connect the wave directly to the product outcome or proof scenario.

What is next
- The next planned autonomous step or the exact reason the loop is blocked.
```

## Style Rules

- Keep the language plain and product-facing.
- Do not include file paths.
- Do not include module names, function names, test names, commands, or git details.
- If there was a parallel batch, describe it in plain language as multiple work items done side by side.
- If a result was rejected, say so plainly and explain what was still missing.
- If the user must answer a question, make that explicit in `What is next`.
- If MVP is proven, say that plainly and stop the log entry there.

## Required Link To Product

Every entry must explain how the wave relates to the product brief:

- which promised behavior moved forward;
- what proof was gained;
- what still blocks the promised MVP.

If the wave did not move MVP at all, say that plainly instead of inventing progress.
