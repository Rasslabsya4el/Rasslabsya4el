# Manual File Handoff Contract

Read this before creating worker tasks, reading worker results, or writing a user-facing orchestration reply.

This is the default dispatch contract for `$universal-project-orchestrator`.
Do not ask the user to opt into this mode.
Use the old markdown task handoff only when the user explicitly asks for legacy inline task specs or when the filesystem cannot be written.

## Intent

Keep chat cheap and human-readable.
Keep task precision in files.
The user should only copy one ready fenced block into a worker thread.

## Runtime Layout

Create the task workspace if missing:

```text
.orchestrator/
  tasks/
    <TASK_ID>/
      <TASK_ID>.task.txt
      RESULT.txt
      FOLLOWUP-01.task.txt
      RESULT-01.txt
```

Rules:

- Use one folder per task family.
- Use ASCII task ids such as `TASK-MVP-UI-01` unless the project already has a stable id scheme.
- Do not create new live markdown task specs in chat or in task folders.
- Keep canonical planning state in `docs/project/**`, `docs/roadmap.md`, `docs/task-queue.md`, and `docs/validation-log.md`.
- Use `.orchestrator/tasks/**` only for executable handoff artifacts and result artifacts.

## Task File Contract

Write compact, machine-oriented plain text.
Prefer stable `key:` fields and short lists.
Avoid markdown prose, tables, headings, links, and fenced blocks inside task files.

Required shape:

```text
task_id: TASK-MVP-UI-01
mode: manual_file_handoff
role_skill: $universal-subtask-worker
required_skills:
- $poe-build-architect
- $poe-report-surface-guardrails
status: ready

thread_routing:
- decision: new | continue
- target_thread: New | Continue <TASK_ID>
- reason: short product/context reason
- evidence_checked: previous task file/result/task queue, or none for new task family

goal:
- Build the smallest product-visible change that closes this task.

why_now:
- Explain one short MVP reason.

recent_work_review:
- looked_at: last relevant task results/docs checked before dispatch
- last_material_progress: what actually changed recently, or `none`
- repeated_pattern: yes | no
- same_problem_count: number or `unknown`
- current_bottleneck: current limiting issue in plain terms
- why_next_step_is_not_blind_repeat: short reason

expected_value:
- expected_result: what this task should produce
- decision_it_will_change: what the orchestrator will decide differently if it succeeds/fails
- estimated_cost: low | medium | high plus time/quota/risk if known
- worth_it: yes | no
- cheaper_alternative: cheaper meaningful step, or `none`
- stop_condition: when to stop this line instead of repeating

repo_root:
C:\absolute\path\to\repo

context_files:
- docs/project/PRODUCT_BRIEF.md
- docs/roadmap.md
- path/to/relevant/source

write_scope:
- path/to/file-or-dir

do_not_touch:
- path/to/file-or-dir

acceptance:
- Observable condition the orchestrator can accept or reject.

validation:
- command or manual check that proves the acceptance.

progress_guard:
- attempt_fingerprint: required for repeated/costly work; otherwise `not_repeated_or_costly`
- previous_attempts_checked: validation log/task queue/result paths checked, or `none`
- expected_delta: what should change; required for repeated/costly work
- max_cost: runtime/quota/batch cap, or `small`
- stop_if: condition that blocks another same-class task
- cheaper_alternative_considered: yes/no plus short reason

delegation_inside_task:
No. NO_VALID_SUBAGENT_SPLIT.

result_file:
C:\absolute\path\to\repo\.orchestrator\tasks\TASK-MVP-UI-01\RESULT.txt

result_contract:
- task_id
- status: completed | partial | blocked | failed
- changed_files
- validation
- progress_evidence
- completed_acceptance
- limitations
- follow_up_needed
- follow_up

chat_response_contract:
- Write the result artifact to the exact result_file path.
- Final chat response must be exactly the absolute result_file path.
- No prose.
- No markdown.
- No summary.
- No questions to user.
- If blocked, still write result_file with status: blocked, then return only the path.
```

Task-file economy rules:

- Put paths, not copied source text, in `context_files`.
- Keep `goal`, `why_now`, and `acceptance` product-precise and short.
- Use `write_scope` as a hard ownership boundary.
- If parallel tasks would share write scope, do not dispatch them in the same batch.
- Put worker role in `role_skill`; it may vary by task.
- Put domain or report skills that must also be active in `required_skills`. This field is inside the task file only and does not change the three-line copy block.
- For research tasks, use the relevant research skill in `role_skill` and keep the same path/result discipline.
- `chat_response_contract` is mandatory for every task file, regardless of `role_skill`.
- Do not rely on a child skill already knowing the path-only protocol. Put the chat response rules directly in the task file every time.
- `thread_routing` is mandatory for every task file. It records why this task should start a new worker thread or continue an existing one.
- `recent_work_review` and `expected_value` are mandatory for every task file. They prove the orchestrator looked at recent work and decided the task is worth doing.
- `progress_guard` is mandatory for repeated/costly work. If it is not relevant, write `not_repeated_or_costly` instead of omitting the field.
- Do not create any task when `expected_value.worth_it` would honestly be `no`. Stop dispatch and explain the cost/value problem to the user.
- Do not create a repeated/costly task unless `progress_guard` states a new hypothesis, expected delta, max cost, and stop condition.

## Poe Skill Routing Gate

For Poe Junkroan product-authoring work, fail closed before dispatch when the task can author, compare, repair, or publish a PoE build artifact but does not name the matching installed `poe-*` skill.

Required routing:

- Ordinary PoE build creation, Direct Build, PoB generation, build option synthesis, and CandidateShortlist tasks require `poe-build-architect`.
- Output/report-bound product tasks require `poe-report-surface-guardrails` in addition to the domain skill.
- BuildReview tasks require `poe-build-review`.
- LoadoutPlan and gear progression tasks require `poe-loadout-planner`.
- Craft planning tasks require `poe-craft-planner`.
- Trade or market evaluation tasks require `poe-trade-evaluator`.
- poe.ninja public-build research tasks require `poe-ninja-researcher`.

Exceptions:

- `$universal-subtask-worker` remains valid by itself for bounded repo implementation tasks such as runtime, schema, test, validation, or docs repair work.
- A product-looking task may omit Poe skills only when it is explicitly marked `implementation_only: true` and the goal is implementation or validation, not authoring a user-facing PoE build artifact.

Handoff representation:

- Keep the second line of the copy block as the primary worker role line, usually `$universal-subtask-worker` for bounded implementation or harness tasks.
- Put additional required Poe skills in `required_skills` inside the task file. Do not add a fourth line to the three-line copy block.
- For product-authoring dogfood where a generic worker owns orchestration, mark the task as worker-as-harness and require Poe builder subagents in acceptance.

Worker-as-harness rule:

- The worker thread owns orchestration and verification, not silent generic build authoring.
- It launches first-level Poe builder subagents with explicit `poe-*` skill prompts, collects their outputs, verifies PoB evidence, asks for repair when evidence is insufficient, or stops with a precise blocker.
- Product-authoring dogfood has no artificial fixed subagent cap such as 2-3. The worker may launch as many first-level Poe builder subagents as useful for distinct hypotheses or branches, while recording cost, stop rules, and no recursive subagents.
- Future authoring dogfood is not accepted as skill-driven unless the result contains transcript-backed proof that a Poe builder subagent was launched with the intended `poe-*` skill.

## User-Facing Dispatch Blocks

For every task path the user must copy, emit a separate fenced block.
The fenced block must contain exactly three physical lines, with no blank lines:

1. task id;
2. worker role line;
3. absolute task-file path.

Example:

```text
TASK-MVP-UI-01
$universal-subtask-worker
C:\project\.orchestrator\tasks\TASK-MVP-UI-01\TASK-MVP-UI-01.task.txt
```

Rules:

- Do not put task specs in chat.
- Do not ask the user to type a mode name.
- Do not make the user assemble task id + role + path manually.
- If there are two tasks, emit two fenced blocks.
- If a task uses another role skill, put that exact role line in that task's fenced block.
- The first line must exactly match the task id inside the task file and task folder.
- The third line must be the only absolute path in the fenced block.
- Outside fenced blocks, explain only the product/runtime context, important failure or blocker if any, and what the user should copy next.

## Thread Routing Decision

Before creating or emitting any dispatch block, decide whether the task belongs in a new worker thread or an existing worker thread.

Required inputs to check:

- current user-provided result path, if any;
- task file that produced that result;
- result file content and `follow_up_needed`;
- existing `.orchestrator/tasks/<TASK_ID>/` family files;
- `docs/task-queue.md` in-flight/ready/blocked state;
- relevant validation log or current-state note when it names an active worker/e2e thread.

Prefer `Треды: Continue <TASK_ID>` when:

- the new work is a correction, rejection repair, narrowing, expansion, or validation retry for the same task family;
- the same worker thread has useful local context from the previous attempt;
- the follow-up reuses the same product scenario, subsystem, source data, validation window, or failure class;
- the task file lives as `FOLLOWUP-*.task.txt` inside the original task folder;
- the previous worker result is partial/blocked/failed but context is still useful;
- the user just returned a result path for this task and the next step directly depends on that result.

Prefer `Треды: New` when:

- this is a new task family or a materially different product scenario;
- role skill changes in a way that needs a fresh thread, for example implementation worker to research or e2e runner;
- the previous thread has stale assumptions, bad protocol compliance, or misleading context;
- the new task changes subsystem/write ownership enough that old context is more harmful than useful;
- the old thread is unknown to the orchestrator and no task/result path links it to this task family.

Do not default to `New` just because creating a fresh thread is simpler.
If a task bounces between orchestrator and worker multiple times, default to `Continue <TASK_ID>` unless there is a clear stale-context reason.

When choosing `Continue`, create a follow-up task file in the original task folder and put the follow-up path in the copy block.
When choosing `New`, create a new task folder.

## Result Intake

When the user returns a worker result path:

1. Read only the result file first.
2. Verify it matches the expected task family and declared `result_file` or follow-up result file.
3. Read the task file if needed for acceptance criteria.
4. Accept, reject, or create a follow-up task.
5. Apply `progress-loop-guard.md` before creating any next task; review recent work, material progress, expected value, and cost.
6. Update `docs/task-queue.md`, `docs/validation-log.md`, and roadmap/current-state docs only when state actually changed.

## Follow-Up And Correction Protocol

When a worker task must be corrected, narrowed, expanded, or interrupted, do not write the corrected task/spec/instructions directly in chat.

Required behavior:

1. Create or update a task file on disk:
   - use `FOLLOWUP-01.task.txt`, `FOLLOWUP-02.task.txt`, etc. inside the original task folder when continuing the same worker thread;
   - or create a new task folder and `<TASK_ID>.task.txt` when it is a new task family.
2. The follow-up task file must include the same mandatory fields as a normal task file, including `role_skill`, `result_file`, `result_contract`, and `chat_response_contract`.
3. In chat, give only a brief human explanation plus the standard copy block.
4. If continuing a running worker thread, use `Треды: Continue <TASK_ID>`.
5. The copy block still contains exactly task id, role line, absolute follow-up task-file path.

Forbidden:

- writing a mini task spec in chat;
- writing a one-line patch instruction for the user to paste into the worker;
- saying `give the worker this follow-up message` followed by task content;
- relying on chat-only corrections instead of updating `.task.txt` on disk.

If the user asks `what do I give the worker?`, answer with the copy block pointing to the task file, not with inline task instructions.

Reject or request reformat when:

- no result file exists;
- task id is missing or mismatched;
- `changed_files` is missing for implementation tasks;
- validation is missing without a clear policy reason;
- limitations are omitted;
- worker touched files outside `write_scope` without a justified blocker;
- the result is only a chat summary and not a file artifact.

## Human Update Style

The orchestrator is a product-facing technical lead, not a task-spec printer and not a file narrator.

The user-facing explanation must describe product logic:

- what product or feature area we are talking about;
- what user/operator is trying to accomplish;
- what user/business outcome is being moved;
- what became clearer or more proven;
- what product risk or bottleneck is blocking progress;
- why the next worker tasks exist from the product's point of view;
- what changed in the plan or confidence level.

Do not explain the current state primarily through files, modules, write scopes, test names, function names, classes, package names, or implementation details.
The only file paths normally visible to the user are the copy-paste task paths inside fenced blocks.

Default reply shape is flexible, not mandatory.
The default should be a short but fully understandable human explanation, not a cryptic status line.
Use only the sections that carry real information, but do not compress away the context the user needs to understand what is happening.
If there is no failure, blame, risk, or meaningful context change, omit that block entirely.
Never write filler such as `Ничего критичного`, `Никто`, or `нормальная зависимость` just to fill a template.

Maximum useful shape:

````text
<1-2 plain-language context lines: which product/feature/user journey this is about>

<2-6 plain-language lines explaining the product/runtime situation and why the next step exists>

<1-5 plain-language lines explaining what changed, what is proven, what is still unproven, or what was rejected>

<1-4 plain-language lines about real blocker/risk/blame, only if important>

Параллельность: Нет
Треды: New

```text
<TASK_ID>
$role-skill
C:\absolute\path\to\task.task.txt
```
````

Rules:

- Keep replies readable; usually 6-14 product-facing lines plus copy blocks. Shorter is fine only when the state is genuinely obvious.
- Prefer a clear mini-explanation over a cryptic compressed status. The user should not need to ask `what does this mean?` after a normal dispatch or acceptance.
- Always include a context lead after acceptance/resync/dispatch unless the immediately previous user message already states the full product context. The context lead should answer: `о каком продукте/фиче речь?`, `для кого это важно?`, and `какой пользовательский результат двигаем?`.
- Do not assume the user remembers internal project shorthand from previous turns. Re-anchor the answer in plain words before mentioning task-specific facts.
- For project-specific or domain-specific terms, add a plain-language apposition on first use. Example: `proof refs — ссылки/доказательства, по которым система понимает, что выбранный результат действительно относится к нужному источнику`.
- Handoffs are mandatory when tasks are ready. Explanatory sections are optional.
- Always include a micro instruction for parallelism and thread routing when giving tasks: `Параллельность: Да` or `Параллельность: Нет` on its own line, and `Треды: New` or `Треды: Continue <TASK_ID>` on its own line.
- `Параллельность` is a boolean field. Do not add reasons, punctuation clauses, or commentary on the same line.
- If the reason matters, put it as a separate short product-facing sentence before the boolean line.
- Do not include a blame/risk/blocker section unless something actually failed, is blocked, or can mislead the project.
- Do not include empty-positive status lines like `Ничего критичного`, `Никто`, `всё нормально`, or `без проблем`.
- Do not replace explanation with internal labels, row numbers, cluster ids, queue names, or bare task codes. If such ids matter, explain the human meaning first, then mention the id only as supporting detail.
- Do not use domain nouns like `import payload`, `matching report`, `proof refs`, `PoB session`, `workspace`, `package anchors`, `selected result`, or similar without explaining what they mean for the product flow.
- Do not list updated files in the user-facing reply after normal acceptance/resync/dispatch. File update lists belong in result files, validation logs, git diff, or an explicit audit reply.
- Do not start the human explanation with a task id. Start with the plain result or product/runtime meaning; task id belongs in the copy block or as a secondary detail only when necessary.
- Mention only active phase/current work, not every known phase.
- Do not include `## Роудмеп`, inline task specs, or old task-handoff markdown by default.
- Do not dump full roadmap unless the user asks for roadmap/state audit.
- Do not say things like `общий файл`, `write scope`, `модуль`, `компонент`, `класс`, `функция`, `тест`, `билд`, or `линтер` in the human explanation unless that technical detail is the actual product/ops bottleneck the user needs to understand.
- Avoid untranslated engineering phrases like `code/test hardening`, `larger-surface proof`, `downstream pool reshape`, `runtime contour`, `observed class`, or `targeted checks` in the human explanation. Translate them into plain user impact first.
- If a technical bottleneck matters, translate it into impact first. Example: say `заявки пока нельзя безопасно сохранять для нескольких менеджеров` before mentioning `database choice`.
- Explain non-parallel dispatch by product dependency, not file ownership. Example: `сначала надо доказать, что заявка проходит весь путь от формы до сохранения; дизайн и отчёты зависят от этого решения`.
- Explain acceptance by user-visible outcome, not changed files.
- Explain rejection by missing proof or broken product promise, not by code diff shape.
- For result acceptance, explain three things in plain language when relevant: what was fixed/proven, what remains unproven, and why the next task follows.
- Be plain-spoken. It is allowed to say plainly that a worker, previous task, context, tool, or orchestrator step was bad, but do not insult the user.
- If nothing is ready to dispatch, say exactly what blocks the next task and ask the smallest bounded question if needed.

Preferred style example:

````text
Речь про таблицу услуг: пользователь должен получить чистую итоговую таблицу, где мусорные строки не выглядят как реальные услуги.
Кодовую починку приняли: плохая строка больше не должна попадать в итоговую таблицу как нормальная услуга.
Но это пока доказано только локально — мы ещё не проверили, что после живого прогона workflow реально обновит публичную таблицу правильно.

Смысл следующего шага: один реальный прогон должен показать, что мусорная строка исчезла, а нужная услуга появилась или осталась валидно объяснённой.
Если это подтвердится, текущую линию можно закрывать. Если нет — возвращаемся к точечной починке.

Параллельность: Нет
Треды: New

```text
TASK-MVP-LIVE-PROOF-01
$universal-subtask-worker
C:\project\.orchestrator\tasks\TASK-MVP-LIVE-PROOF-01\TASK-MVP-LIVE-PROOF-01.task.txt
```
````

Bad style example:

```text
Принял TASK-123 как code/test hardening, но не как live acceptance.

Обновил:
- docs/project/CURRENT_STATE.md
- docs/roadmap.md
- docs/task-queue.md
- docs/validation-log.md

Текущий next step: повторить larger-surface acceptance после runtime hardening.
```

Why bad:

- starts with task id instead of meaning;
- dumps internal files;
- uses engineering labels instead of explaining what changed for the product/runtime;
- forces the user to decode why the next task matters.
````

Another good style example for dense domain work:

````text
Речь про публикацию результата в агентском workflow: агент должен выбрать правильный результат, собрать для него доказательства и безопасно передать это дальше в отчёт.
Публикацию приняли по смыслу: выбранный результат теперь закрывается не фразой вроде `где-то там`, а понятной цепочкой — что импортировали, как сопоставили, и на какие доказательства опираемся.

Что ещё не доказано: разные агентские прогоны пока нельзя уверенно пускать параллельно. Нужно проверить, что они не будут делить одну и ту же рабочую сессию или якоря данных и случайно портить друг другу результат.

Следующая задача нужна не для новой фичи, а для безопасности параллельной работы: если проверка зелёная, такие прогоны можно будет запускать одновременно; если нет — придётся оставить их последовательными.

Параллельность: Нет
Треды: New

```text
TASK-PUBLISH-PARALLEL-SAFETY-01
$universal-subtask-worker
C:\project\.orchestrator\tasks\TASK-PUBLISH-PARALLEL-SAFETY-01\TASK-PUBLISH-PARALLEL-SAFETY-01.task.txt
```
````

Bad human update:

```text
Что происходит сейчас
- Следующая работа упирается в один общий файл и один общий сценарий.
- Параллелить нельзя: задачи будут драться за один write scope.
```

Good human update:

````text
Сейчас доказываем главный путь MVP: человек оставляет заявку, а продукт не теряет её и показывает понятный следующий шаг.
Пока этот путь не доказан, отчёты и полировку не стартуем: они могут красиво лечь поверх неправильной логики.

Сначала нужно доказать один сквозной сценарий заявки.
Параллельность: Нет
Треды: New

```text
TASK-MVP-REQUEST-FLOW-01
$universal-subtask-worker
C:\project\.orchestrator\tasks\TASK-MVP-REQUEST-FLOW-01\TASK-MVP-REQUEST-FLOW-01.task.txt
```
````

## Legacy Isolation

The old `task-handoff-contract.md` and `user-facing-response-contract.md` are legacy fallback surfaces.
Do not read or apply them during normal manual file handoff.
Only use them when the user explicitly asks for old inline markdown task specs or when file handoff is impossible.
