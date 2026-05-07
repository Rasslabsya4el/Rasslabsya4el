# Universal Sync Invariants For Nikita Orchestrator

Read this during Nikita hard resync and before editing `nikita-project-orchestrator/SKILL.md`.

Nikita Project orchestrator is a thin project-specific overlay on `$universal-project-orchestrator`.
Generic behavior must stay identical unless a project-specific section explicitly narrows it without changing the user-facing protocol.

## Must Match Universal

These rules are inherited from universal and must not be locally redefined in a conflicting way:

- manual file handoff is default;
- control-plane bootstrap runs before roadmap/task queue/dispatch/acceptance/resync;
- missing canonical docs are created from main readme templates by the orchestrator, not delegated to workers;
- chat contains no inline task specs;
- each dispatch copy block has exactly three physical lines with no blank line: task id, role line, absolute task-file path;
- `Параллельность` is boolean-only: `Параллельность: Да` or `Параллельность: Нет`;
- `Треды` is mandatory for dispatch: `New` or `Continue <TASK_ID>`;
- every task file includes `chat_response_contract`;
- every task file includes `thread_routing`;
- routing decision checks prior task/result files, task queue, validation log, and whether old thread context is useful or stale;
- every dispatch uses the universal progress review / expected value gate before task creation;
- every task file includes `recent_work_review` and `expected_value`;
- costly/repeated validation additionally uses `progress_guard`;
- any same-class work is blocked after repeated no-progress evidence unless the next task has a new hypothesis and expected decision change;
- repeated repair/retry/follow-up for the same task family defaults to `Continue <TASK_ID>` unless stale context is a real risk;
- child final chat response is only the absolute result path when the task file says so;
- follow-up/correction/interruption instructions are also task files on disk, never inline mini task specs in chat;
- if continuing a worker thread, create/update `FOLLOWUP-*.task.txt` and route with `Треды: Continue <TASK_ID>` plus the standard copy block;
- user-facing reply contains a short but self-contained product/runtime explanation plus copy blocks;
- acceptance/resync/dispatch replies include a plain context lead unless the immediately previous user message already contains full product context;
- context lead answers what product/runtime area this is, who/what it matters to, and what user/operator result is moving;
- normal dispatch/acceptance should explain what was fixed or proven, what remains unproven, and why the next task follows when those facts changed;
- do not over-compress into cryptic labels, ids, or one-line status if the user would lose the project context;
- do not start human explanation with task ids; start with the plain product/runtime result;
- do not list updated files in normal user-facing replies unless the user explicitly asks for audit/diff/file inventory;
- translate engineering labels into user impact; avoid phrases like `code/test hardening`, `larger-surface proof`, `runtime contour`, or `targeted checks` unless explained in plain language first;
- no filler blocks: no mandatory `Никто`, `Ничего критичного`, `всё нормально`, `без проблем`;
- no legacy user-facing headings: `ACCEPTED`, `REJECTED`, `BLOCKED`, `Human touch`, `Human touch: No`;
- no mandatory `## Роудмеп`, `## Порядок постановки`, or `## Простыми словами`;
- old `user-facing-response-contract.md` and `task-handoff-contract.md` are legacy fallback only.

## Nikita May Add Only These Overlays

Project-specific additions may define:

- Nikita canonical docs and templates;
- Nikita cluster codes and task id conventions;
- Nikita role bindings: `$nikita-project-subtask-worker`, `$nikita-project-e2e-runner`, `$universal-deep-research`;
- Nikita single-writer/hot-serial contours;
- Nikita validation and STOPPER/CENSUS rules;
- Nikita source-of-truth references.

Project-specific additions must not reintroduce old markdown response layout or inline task specs.

## Sync Check Before Completion

Before ending a Nikita resync/update turn, verify:

- Nikita `SKILL.md` points to `manual-file-handoff-contract.md` as the default user-facing and task handoff contract;
- no normal-flow instruction requires `user-facing-response-contract.md` or `task-handoff-contract.md`;
- no completion criterion requires `## Роудмеп`, `## Порядок постановки`, `## Простыми словами`, or `ACCEPTED`;
- dispatch wording says task id + role line + absolute task path;
- hard resync explicitly bans old layout;
- quick validation passes.
