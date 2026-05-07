# Agent Context Economy

Read this before writing any orchestrator-to-worker or worker-to-orchestrator contract.

This reference exists to reduce token waste, repeated context, and noisy handoffs.

## Core Principle

Context is finite.
Every repeated paragraph competes with the real task.

Default order of preference:

1. pointer to tracked file
2. stable identifier or fingerprint
3. short structured field
4. tiny excerpt only if the file cannot be trusted or the exact slice is critical
5. full prose restatement only as last resort

## Parent-To-Child Economy

The parent should send the child the smallest self-sufficient package.

That package must contain only:

- stable task identity;
- exact role skill;
- product target;
- why now;
- minimal read context pointers;
- exact write scope;
- exact do-not-touch scope;
- bounded work items;
- targeted checks;
- parent acceptance conditions;
- exact result target.

Do not include:

- long product recap already stored in `PRODUCT_BRIEF`;
- roadmap prose already stored in `roadmap.md`;
- repeated rejection history copied again and again;
- pasted source files unless a tiny excerpt is truly required.

## Schema First

Prefer fixed fields over prose.

Why:

- cheaper to parse;
- easier to diff;
- easier to validate;
- lower chance of drifting instructions.

If a handoff is repeated more than once, convert it to a stable field instead of re-explaining it in prose.

## Pointer Over Paste

Prefer:

- absolute file paths;
- exact task codes;
- exact result paths;
- explicit write scopes;
- exact proof targets.

Avoid:

- pasting doc bodies into chat;
- retelling the same brief in every task;
- asking a child to infer its scope from a large blob of context.

## Delta-Only Follow-Ups

Same-agent follow-ups must be delta-only.

Rules:

- inherit unchanged contract from the previous task file;
- restate only what changed;
- keep the same task fingerprint when the underlying product target and write scope are the same;
- if more than half of the original task fields would need to be rewritten, stop doing follow-ups and create a replacement task instead;
- if write scope broadens materially, use a replacement task instead of a same-agent follow-up.

## Result Economy

The child reply in chat should be as small as the parent can safely validate.

Preferred pattern:

- chat reply: exact result path only;
- result file: fixed machine-oriented schema;
- parent acceptance: based on the result file plus targeted checks, not on chat prose.

The result file should report only:

- what changed;
- what was checked;
- what was observed;
- what remains risky;
- what the parent should do next.

Do not write essay-style completion notes.

## Context Loading Rules For Children

Children should load context in this order:

1. task file;
2. base task file if the current file is a delta follow-up;
3. listed context files only;
4. minimal nearby code or docs needed to execute the bounded work.

Do not start with a repo-wide scan when the task already names the relevant context.

## Separation Of Responsibilities

Keep canonical product and planning context in tracked docs.
Keep runtime ownership and attempt history in ledgers.
Keep task execution context in the task file.
Keep acceptance evidence in the result file.

Do not force one artifact to do all four jobs.

## Stable Identity Beats Re-Description

Use stable codes and fingerprints for:

- tasks;
- task families;
- follow-ups;
- proof targets;
- child ownership.

It is cheaper to say `same fingerprint, attempt 2, changed checks only` than to restate the whole task.

## Parallel Batch Economy

Parallel children should not carry overlapping task context by default.

Rules:

- one child owns one write scope;
- shared docs stay serial unless ownership is explicit;
- do not give two children the same broad "read the project" instruction;
- every child should receive only the slice it needs.

## Compression Triggers

Stop and compress when:

- the same product recap appears in more than one active task file;
- a rejection note mostly repeats the prior task;
- the parent is tempted to paste prior child reports into the next task;
- a task file is growing because history is being appended instead of replaced with stable fields.

Compression actions:

- move durable facts into tracked docs;
- move execution history into ledgers;
- convert the next task into a delta-only follow-up;
- create a replacement task when the old family became too noisy.

## User-Facing Economy

Do not ask the user for information that can be recovered from:

- tracked docs;
- nearby source;
- bounded research.

When user input is required, ask only the smallest option-based pack that would change the product contract.

See `project-intake-and-clarification.md`.
