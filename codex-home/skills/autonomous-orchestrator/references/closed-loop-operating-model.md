# Closed-Loop Operating Model

Read this before each autonomous pass. This overlay does not replace the universal orchestrator references. It narrows them to one parent orchestrator, one repo, first-level children only, no external edits, machine-oriented artifacts, and minimal user-facing output.

## Closed-World Contract

- Only the parent orchestrator owns planning state.
- Only the parent and its spawned first-level children may edit the repo.
- No outside writer, watcher, background service, or human mutates project files during autonomous mode.
- The minute heartbeat is not external polling. It is the next scheduled autonomous wave.
- Every autonomous wave must end with zero open child agents, zero unread child result files, and a reconciled runtime ledger.

## Parent Write Boundary

The parent orchestrator may edit only:

- canonical project docs;
- `.orchestrator/**`;
- task materialization files;
- acceptance/rejection bookkeeping.

The parent must not directly create or edit product implementation files as the main execution path. That includes source code, landing-page files, assets, tests, or runtime behavior.

If the user provides a new concrete product ask, the parent must:

1. update or create the canonical docs;
2. derive or repair the ready task;
3. materialize the task file;
4. spawn a child;
5. integrate the child result.

Do not let the parent collapse into normal coding mode unless the user explicitly removes orchestrator role.

## Canonical Project Docs

Follow `../universal-project-orchestrator/references/roadmap-operating-model.md` as the product and planning source of truth.

Always work against the tracked docs in the target repo:

- `docs/project/PRODUCT_BRIEF.md`
- `docs/project/CURRENT_STATE.md`
- `docs/project/DECISION_LOG.md`
- `docs/project/PRODUCT_SPEC.md` when present
- `docs/roadmap.md`
- `docs/task-queue.md`
- `docs/validation-log.md`

If those files are missing, stale, or legacy-shaped, bootstrap or migrate them from these template files in this repo:

- `C:/Coding/Main readme repo/AGENTS_TEMPLATE.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/project/PRODUCT_BRIEF.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/project/CURRENT_STATE.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/project/DECISION_LOG.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/project/PRODUCT_SPEC.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/roadmap.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/task-queue.md`
- `C:/Coding/Main readme repo/project-doc-templates/docs/validation-log.md`

Never use the template files as the project's live docs.

## Clarification Gate

Before bootstrapping or rewriting the product docs, run the clarification gate from `../universal-project-orchestrator/references/project-intake-and-clarification.md`.

Rules:

- if the repo and current user context already yield a decision-stable product contract, continue without asking the user;
- if missing answers would still change the MVP proof, target user, first surface, roadmap shape, or next-task acceptance, stop and ask the smallest option-based question pack;
- build options from tracked repo context and the user's wording;
- after answers arrive, update canonical docs first and only then derive dispatch tasks;
- while waiting for the user, write blocked state and do not arm heartbeat.

## Absolutely Empty Repo

A repo is absolutely empty for this skill when all of the following are true:

- no usable product brief/spec/README with product meaning exists;
- no roadmap or task queue exists;
- no existing source or assets define what the product is supposed to do;
- the current tracked context does not let the parent derive a concrete MVP contract honestly.

If the repo is absolutely empty:

- if the current user message already contains a usable product contract, synthesize the canonical docs from it and continue;
- otherwise create only `.orchestrator/state.json`, `.orchestrator/task-ledger.json`, `.orchestrator/agent-ledger.json`, and `.orchestrator/PRODUCT_RUN_LOG.md`, mark the state as blocked on product contract, ask the smallest option-based question pack by `references/minimal-user-facing-output.md`, and stop.

In that blocked-empty-repo case:

- do not invent generic starter work;
- do not guess a stack;
- do not write source files;
- do not arm heartbeat.

## Repo-Local Runtime Surface

Create and maintain this runtime folder inside the target repo:

- `.orchestrator/state.json`
- `.orchestrator/task-ledger.json`
- `.orchestrator/agent-ledger.json`
- `.orchestrator/PRODUCT_RUN_LOG.md`
- `.orchestrator/tasks/`

Minimum semantics:

- `state.json`: current autonomous mode, turn counter, last autonomous verdict, heartbeat intent, blocked reason if any, next wave goal, and last issued task sequence.
- `task-ledger.json`: one entry per dispatched task fingerprint with code, origin, role skill, scope, attempt counters, current status, and artifact paths.
- `agent-ledger.json`: one entry per spawned child with agent id, linked task code, role skill, current status, task file path, latest result path, integrated flag, and closed flag.
- `PRODUCT_RUN_LOG.md`: append-only plain-language turn log for the human reader.

Persist every mutation before the next spawn, wait, or acceptance decision.

## Live Artifact Format

Live task families for this skill use the v2 text protocol only.

Rules:

- active task codes and task-folder names must be ASCII-only, for example `TASK-R2-LANDING-01`;
- use only uppercase letters, digits, and hyphen in live task codes;
- live task files must end in `.task.txt`;
- live result files must end in `.txt`;
- do not keep `active_task_file` or `latest_result_file` pointed at legacy `.md` artifacts.

If the repo already contains legacy live artifacts such as `<TASK_CODE>.md`, `FOLLOWUP-01.md`, `RESULT.md`, `RESULT-01.md`, or non-ASCII task codes:

- do not continue the live task family on those paths;
- migrate or quarantine the legacy files before the next spawn, wait, or acceptance step;
- do not mix legacy and v2 artifacts inside the same live task family.

## Turn Algorithm

Run each autonomous wave in this order:

1. Check `git status` and the nearest repo policy doc.
2. Check whether the repo is in the absolutely-empty state.
3. If it is absolutely empty and there is no usable product contract yet, enter blocked-empty-repo state and stop by the local minimal user-facing contract.
4. Ensure the canonical project docs exist and are up to date per the roadmap operating model.
5. Run the clarification gate before creating or rewriting `PRODUCT_BRIEF`, `PRODUCT_SPEC`, roadmap, or the first dispatch wave.
6. Read the product brief/spec, current state, decision log, roadmap, task queue, and validation log as needed.
7. Determine the next dispatch wave:
   - if `docs/task-queue.md` already has ready tasks, use them;
   - otherwise derive new ready tasks from roadmap gaps, current-state defects, validation gaps, or explicit product requirements already present in tracked context;
   - if no new task can honestly be derived, run an MVP evaluation against the product brief and available evidence.
8. Reconcile `.orchestrator/` runtime before any new spawn or acceptance:
   - if the live ledgers point to legacy `.md` artifacts or non-ASCII task codes, migrate or quarantine them first;
   - if an earlier child reply is still unresolved, resolve or discard it before creating replacement work.
9. For every ready task in the wave:
   - preserve its existing task code only if it already follows the ASCII live-code rule;
   - otherwise generate a stable code such as `TASK-<PHASE>-<AREA>-<NN>`;
   - create the task folder and machine-oriented task file per `references/file-protocol.md`;
   - register the task in `task-ledger.json` before spawning the child.
10. Spawn the required first-level child and send only the absolute task-file path.
11. Wait for only the absolute result-file path and do not inspect intermediate child artifacts while waiting.
12. Run the result-path gate first:
   - the reply is exactly one absolute path;
   - the path matches the expected `result_file`;
   - the file exists on disk;
   - the path is a live v2 `.txt` artifact, not a legacy `.md` file.
13. Only after the gate passes, read the result file, update the ledgers, and make an explicit decision:
   - `accepted`
   - `rejected`
   - `blocked`
   - `needs_followup_task`
14. If rejected:
   - reuse the same child only when the same role is still useful and the same-agent follow-up budget is not exhausted;
   - otherwise close the child, create a replacement task with a new task code or suffix, and spawn a fresh child.
15. After the whole wave is closed, reconcile runtime state, update the control-plane docs, append the product run log, compute the exact next autonomous objective, write it into `state.json`, emit only the local minimal user-facing status, and only then rearm the next heartbeat.

## Parallel Batches

Parallelism is allowed only under `../universal-project-orchestrator/references/delegation-source-of-truth.md`.

Additional hard limits for this skill:

- max `3` first-level children in one parallel batch;
- one writer per file per wave;
- no overlap in write scope;
- no shared control-plane docs inside a parallel batch;
- wait for the whole batch, then integrate the results, then recompute the next wave.

If disjoint ownership cannot be proven directly in the task files, do not parallelize.

## Task Fingerprints And Retries

Each task needs a stable fingerprint built from:

- product outcome or proof target;
- write scope;
- task kind;
- critical boundary or subsystem.

Rules:

- never spawn a new active task with a fingerprint that is already `running`, `awaiting_result`, `integrating`, or `accepted`;
- max `2` same-agent follow-ups for one fingerprint;
- max `3` total attempts for one fingerprint;
- any rejected delivery or `protocol_breach` still consumes attempt budget;
- after the budget is exhausted, the next move must be one of:
  - replan the roadmap/task queue,
  - create a research task,
  - ask the user a bounded option-based question pack.

## Child Lifecycle

The parent orchestrator must babysit every child it spawns.

Required lifecycle:

1. register child in `agent-ledger.json`;
2. wait for the result path and run the result-path gate immediately;
3. read and integrate the result file only if the gate passed; otherwise mark `protocol_breach` and reject or discard without semantic implementation claims;
4. mark the child as integrated or discarded with reason;
5. close the child immediately after integration or discard;
6. verify that `closed = true` before ending the wave.

If a previous autonomous wave was interrupted, the next wave must reconcile the ledgers first. Do not spawn replacement work until all pre-existing result files and child statuses are resolved.

## Result-Path Gate And Acceptance Gate

The parent must gate the child reply before reading anything else.

Path gate:

- the reply is one absolute path and nothing else;
- the path equals the expected `result_file`;
- the file exists;
- the file is a live `.txt` v2 artifact, not a legacy `.md` file.

Until the path gate passes, the parent must not inspect sibling artifacts, follow-up drafts, or changed product files to infer success.

Acceptance gate:

- `protocol_version` is `autonomous-orchestrator/v2`;
- `task_code`, `attempt`, `role_skill`, and `source_task_file` match the active task and ledger;
- claimed `files_changed` stay inside the declared `write_scope`;
- the required check or research sections are present.

If either gate fails:

- mark the attempt as `protocol_breach` or `rejected`;
- spend follow-up budget intentionally;
- do not make MVP or product-acceptance claims from that attempt.

## Child Skill Binding

Child skill binding is mandatory.

Allowed child execution model:

- resolve an existing installed skill path under `C:/Users/user/.codex/skills/<skill-name>/SKILL.md`;
- spawn the child with `agent_type: default`;
- pass one `skill` item pointing to that path;
- pass one text item containing only the absolute task-file path.

Forbidden:

- spawning `worker`, `reviewer`, `verifier`, `docs_researcher`, `explorer`, or bare `default` and treating that as the child role;
- replacing a missing named skill with a generic agent type;
- adding extra prose instead of the path-only handoff;
- continuing autonomously if explicit skill binding failed.

If the child skill path is missing or cannot be bound explicitly:

- write blocked reason `missing_child_skill_binding` to `state.json`;
- append it to `PRODUCT_RUN_LOG.md`;
- do not spawn a fallback child;
- do not arm heartbeat.

## MVP Evaluation

Run MVP evaluation only after:

- the current task queue is empty;
- the roadmap does not yield another honest ready task;
- the available repo evidence has been reread against the product brief/spec.

Possible outputs:

- `MVP done`: product outcomes are proven; mark terminal state and do not rearm heartbeat.
- `More work exists`: create the missing roadmap/task-queue tasks immediately and continue.
- `Research needed`: create a research task and continue.
- `User decision needed`: ask one bounded option-based question pack and do not rearm heartbeat.

## Heartbeat Policy

Default behavior:

- after a completed autonomous wave, rearm the next thread heartbeat for `+1 minute` only if `state.json` already contains a concrete `next_wave_goal`;
- treat that minute as the next autonomous wave, not as a search for external changes.
- the next wakeup is valid only when the parent already knows why it is waking up.

Because this repo is closed-world, do not schedule a wakeup that depends on outside changes.
If no next autonomous objective exists after the current wave, resolve that immediately in the same turn by doing one of these:

- derive the missing tasks now;
- create the needed research task now;
- ask the user now;
- or declare MVP done now.

Do not rearm heartbeat when:

- the user must answer a bounded option-based question pack;
- MVP is already proven;
- the user explicitly stopped the loop;
- a safety guardrail requires manual review.

If the runtime only supports a recurring minute heartbeat instead of a one-shot wakeup, keep it active only while autonomous mode is still running and remove or pause it immediately on any terminal or user-blocked state.

## User Escalation

User escalation is the last resort.

Before asking the user:

1. search the tracked docs and nearby source;
2. if still unresolved, create or run a bounded research task;
3. ask the user only if the gap is now clearly a business choice, private knowledge gap, approval, or hard product ambiguity.

Once a user question is asked:

- do not set heartbeat;
- do not continue dispatch;
- write the blocked state to `state.json`;
- append the blocked explanation to `PRODUCT_RUN_LOG.md`;
- use only the local minimal user-facing output shape.

## Desktop Safety

This orchestrator has full machine permissions but must not disturb the active user session.

Avoid:

- foreground browser driving;
- stealing focus;
- global keyboard or mouse control;
- clipboard mutation;
- loud notifications or persistent popups;
- long destructive jobs without an explicit task reason.

Prefer:

- headless checks;
- targeted file or CLI validation;
- read-only exploration;
- short-lived background work with clear scope.
