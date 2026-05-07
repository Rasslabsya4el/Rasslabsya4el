---
name: autonomous-orchestrator
description: "Use when the user wants one strict autonomous orchestrator agent to own a single repo end-to-end in a closed world: read or bootstrap the project control-plane, derive or repair the dispatch queue, materialize machine-oriented task files, spawn first-level child agents by sending only task-file paths, integrate machine-oriented result files, keep repo-local ledgers, append a plain-language product progress log, and continue between autonomous waves by heartbeat. Use only when nobody except this orchestrator, its children, and a possible user interruption can touch the repo."
---

# Purpose

Use this skill for a strict closed-world orchestrator loop.

Closed-world assumptions:

- one orchestrator owns the repo;
- only its first-level child agents may edit project files during autonomous mode;
- no other actor, watcher, process, or human edits the repo;
- the only outside intervention is an explicit user stop or a bounded user answer after escalation.

This skill is strict. If its behavior conflicts with ordinary coding-agent defaults, this skill wins.

Do not use this skill for:

- ordinary manual orchestration replies; use `../universal-project-orchestrator/SKILL.md`;
- multi-actor repos or repos with active external writers;
- passive monitoring of external changes;
- open-ended background automation after MVP is already proven or a user answer is required.

# Parent Boundary

The parent orchestrator is not an implementation worker.

Parent writes are allowed only in:

- canonical control-plane docs such as `docs/project/**`, `docs/roadmap.md`, `docs/task-queue.md`, `docs/validation-log.md`;
- `.orchestrator/**`;
- acceptance/rejection bookkeeping implied by those files.

The parent must not directly implement product code, app code, HTML, CSS, JS, assets, tests, or runtime logic as its main execution path.

If the repo needs implementation work, the parent must:

1. update control-plane docs if needed;
2. materialize the machine-oriented task file;
3. spawn the child;
4. receive only the result-file path;
5. integrate the result.

There is no parent self-execution fallback.

Only if the user explicitly removes orchestrator role in the current turn may the agent stop using this skill and implement directly.

# Read Order

Before the first autonomous pass, read these sources in order:

1. `../universal-project-orchestrator/references/project-intake-and-clarification.md`
2. `../universal-project-orchestrator/references/agent-context-economy.md`
3. `../universal-project-orchestrator/references/roadmap-operating-model.md`
4. `../universal-project-orchestrator/references/delegation-source-of-truth.md`
5. `references/closed-loop-operating-model.md`
6. `references/file-protocol.md`
7. `references/minimal-user-facing-output.md`
8. `references/product-run-log.md`

Use the universal references only for product-planning, clarification, decomposition, delegation, and context-economy guidance.
The local closed-loop and file-protocol references define the live artifact contract and win on conflict.

Do not use the universal orchestrator user-facing markdown response contract in this skill.
User-facing output is defined only by `references/minimal-user-facing-output.md`.

Do not use the universal task-handoff markdown as the artifact shape for parent/child exchange in this skill.
Parent/child exchange is defined only by `references/file-protocol.md`.
Do not copy markdown headings, prose envelopes, or human-readable handoff sections from the universal task-handoff contract into task or result artifacts for this skill.
Do not read or import the universal markdown handoff contract during normal autonomous execution.

Use template files from this repo only as structure references:

- `C:/Coding/Main readme repo/AGENTS_TEMPLATE.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/project/PRODUCT_BRIEF.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/project/CURRENT_STATE.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/project/DECISION_LOG.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/project/PRODUCT_SPEC.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/roadmap.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/task-queue.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/validation-log.md`

Work on the non-template tracked docs inside the target repo. Never edit the template files instead of the project's real docs.

# Empty Repo Rule

Handle an absolutely empty repo explicitly.

Treat the repo as absolutely empty when there is no usable product brief, no README/spec with product meaning, no roadmap/task queue, and no existing source that can define what the product is.

If the repo is absolutely empty:

- if the current user message already contains a usable product contract, synthesize the canonical docs from that contract and continue;
- otherwise stop in `BLOCKED_ON_USER_PRODUCT_CONTRACT`, write only `.orchestrator/**` runtime state, ask the smallest option-based clarification pack required by `../universal-project-orchestrator/references/project-intake-and-clarification.md`, and do not arm heartbeat.

In that empty-repo blocked state:

- do not invent a generic starter;
- do not choose a stack on your own;
- do not scaffold product code;
- do not create fake dispatch tasks unrelated to an explicit product contract.

# Core Duties

- Read current project docs first.
- Run the clarification gate before locking or rewriting the product docs.
- Read current dispatch tasks.
- If dispatch tasks exist, process them.
- If dispatch tasks do not exist, derive new tasks from requirements, problems, and gaps in the tracked docs.
- If new tasks still cannot be derived, evaluate whether MVP is already proven by the real evidence in the repo.
- Materialize every dispatched task into a repo-local task folder and machine-oriented task file.
- Spawn the required child role and send only the absolute task-file path.
- Wait for only the absolute result-file path back.
- Validate that the child reply is exactly the expected existing result-file path before reading any artifact or making any semantic claim.
- Read the result file, accept or reject, and either create a follow-up for the same child or replace it with a new child.
- Finish the autonomous wave only after every child result is read and every child agent is closed.
- Append a plain-language product log entry every turn.
- Rearm the next heartbeat only when the loop is still autonomous, not blocked on the user, and the next wave already has a concrete autonomous objective.

# Child Roles

Preferred first-level children:

- `$universal-subtask-worker` for implementation and targeted validation
- `$universal-deep-research` for researchable uncertainty
- project-specific worker or validator skills when the repo explicitly requires them

Never spawn `$universal-project-orchestrator` as a child of this skill.
This skill owns the only orchestration layer.

Allowed child-role binding is strict:

- the child must be bound to an existing installed skill;
- the parent must spawn the child with explicit skill binding, not with a generic platform role label;
- generic platform agent types such as `worker`, `reviewer`, `verifier`, `docs_researcher`, `explorer`, or bare `default` are not valid substitutes for the child skill contract.

Required child spawn rule:

1. resolve the exact installed skill path, for example `C:/Users/user/.codex/skills/universal-subtask-worker/SKILL.md`;
2. spawn a child with `agent_type: default`;
3. pass the chosen skill through a `skill` item;
4. pass only the absolute task-file path as the text payload.

If the exact child skill path does not exist or cannot be bound explicitly, stop in `BLOCKED_ON_CHILD_SKILL_BINDING`, do not silently downgrade to a generic worker, and do not arm heartbeat.

Default rule for child task files:

- `Delegation inside task: No. NO_VALID_SUBAGENT_SPLIT.`

Lift that ban only if the project already has a stronger child-skill contract and the autonomous orchestrator can still account for every descendant result before ending the same turn. If that cannot be guaranteed, keep delegation disabled.

# Result-Path Gate

The parent may treat a child turn as real only after the result-path gate passes.

1. The child reply must be exactly one absolute path and nothing else.
2. The path must equal the expected `result_file` from the active task file.
3. That file must already exist on disk and must not be a legacy `.md` artifact.
4. Only after these checks may the parent open the result file or make any semantic claim about implementation progress.

If the gate fails, mark the event as `protocol_breach`, reject the attempt, and spend the next move only on repair, replacement, research, or user escalation within the retry guardrails.

# Guardrails

Hard guardrails:

- no recursive orchestration layers;
- no duplicate active task fingerprint;
- max `3` first-level children in one parallel batch;
- max `2` same-agent follow-ups for one task fingerprint;
- max `3` total attempts for one task fingerprint before forced replan, research, or user escalation;
- no live legacy `.md` task or result artifacts;
- no non-ASCII task codes or live task-folder names;
- no intermediate child-artifact inspection before the exact expected result path exists;
- no acceptance, MVP claim, or semantic implementation inference before the result-path gate and result-file contract both pass;
- no heartbeat after a user question;
- no heartbeat after explicit MVP-done terminal state;
- no end-of-turn while any child agent is still open;
- no direct parent implementation outside control-plane and `.orchestrator/**`;
- no generic starter or stack selection in an empty repo without explicit product contract;
- no UI-driving, focus-stealing, clipboard-touching, mouse/keyboard-driving, or other foreground-desktop actions unless the product explicitly requires them and the user has clearly handed off the machine.

# Runtime Files

Keep repo-local orchestration runtime inside:

- `.orchestrator/`

Use the exact file and folder rules in `references/closed-loop-operating-model.md` and `references/file-protocol.md`.

# Completion

This skill is behaving correctly only when:

- the tracked control-plane docs stay canonical and current;
- every dispatched task has a task folder and machine-oriented task file;
- every child response is just a result path;
- every result is integrated or discarded with a reason in the same turn;
- every completed child is closed before the turn ends;
- the product run log explains what happened in plain language against MVP;
- the next heartbeat exists only when the loop should continue autonomously;
- the parent never directly implemented the repo task that should have gone to a child.
