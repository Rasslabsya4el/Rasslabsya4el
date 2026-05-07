# Nikita Project Tasking Source Of Truth

Этот reference фиксирует project-specific source of truth для orchestration, roadmap discipline и safe parallelism.

Используй его вместо повторных походов в проектные docs, если вопрос уже покрыт этим summary.

## Главные Источники

- `AGENTS.md` — delegation policy, first-level spawn rules, lifecycle и write ownership.
- `docs/project/PRODUCT_BRIEF.md` — основной durable источник того, что продукт должен делать, для кого он и какие user-visible outcomes составляют MVP.
- `docs/project/PRODUCT_SPEC.md` — более детальный продуктовый контракт, если в репо он точнее brief.
- `docs/project/CURRENT_STATE.md` — conservative tracked snapshot текущего подтверждённого состояния.
- `docs/project/DECISION_LOG.md` — durable принятые решения и boundaries.
- `docs/roadmap.md` — canonical MVP phases, full known task inventory и current planning graph.
- `docs/task-queue.md` — canonical ready/in-flight/blocked queue surface.
- `docs/validation-log.md` — batch-level validation ledger, если validation churn уже вынесен из roadmap.
- `GIT_WORKFLOW.md` — multi-agent write ownership и worktree discipline.

Canonical templates for bootstrap:

- `C:\Coding\Main readme repo\AGENTS_TEMPLATE.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\project\PRODUCT_BRIEF.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\project\CURRENT_STATE.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\project\DECISION_LOG.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\project\PRODUCT_SPEC.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\roadmap.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\task-queue.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\validation-log.md`

Legacy migration inputs:

- `docs/project/PROJECT_SCOPE.md`
- `docs/project/MVP_ROADMAP.md`
- `docs/project/ENGINEERING_BREAKDOWN.md`
- `docs/project/TASKING_GUIDE.md`

## Delegation Defaults

- В начале каждой major phase делай delegation check.
- На phase допустимы только два исхода:
  - smallest useful first-level batch;
  - `NO_VALID_SUBAGENT_SPLIT`.
- Recursive delegation запрещена.
- Child agent не должен спавнить sub-subagents.
- Completed subagents надо wait/integrate/close до перехода дальше.
- Один writer на файл на фазу.

## Runtime Parallelism Reality

- Safe project parallelism строится вокруг single-writer contour.
- Stage queues, private outbox и writer-owned materialization важнее красивого fanout.
- Несколько воркеров не должны одновременно писать в общий flat output или shared writer-owned file.
- Shared orchestration surfaces и shared runtime contracts по умолчанию serial.
- Hot serial contour этого repo по умолчанию: `run_company_enrichment_pipeline.py`, `app/runtime/progress.py`, `app/runtime/state.py`, `app/runtime/work_units.py`, `company_enrichment_core.py`. Если задача трогает этот contour, по умолчанию это один исполнитель и часто `NO_VALID_SUBAGENT_SPLIT`, пока split не изолирован новым модулем или явно disjoint ownership.
- Пользователь здесь не участвует в разделении lane-ов: если parallel batch выдан, он должен быть уже безопасен для слепого copy-paste без ручной проверки scope или ownership.

## Current Narrow Safe Contour

- Current multithread contour узкий.
- Multithread rollout не считать уже глобально открытым.
- Project-specific guardrails и source-aware routing надо уважать до новых accepted proofs.
- Не планируй task batch так, будто любой source set уже safe для parallel rollout.

## Planning Discipline

- Product brief/spec обязателен перед tasking и acceptance. Roadmap не должен быть единственным местом, где оркестратор "помнит", что строится.
- Если canonical control-plane set отсутствует или repo живёт только на legacy names, сначала открой `AGENTS_TEMPLATE.md` и нужные files из `project-doc-templates`, затем мигрируй `PRODUCT_BRIEF`, `CURRENT_STATE`, `DECISION_LOG`, `roadmap`, `task-queue` и `validation-log` по structure templates, а потом уже заполняй их фактами из существующих tracked docs.
- Primary roadmap source of truth — `docs/roadmap.md`, а не runtime outputs.
- `docs/task-queue.md` хранит current ready/in-flight/blocked queue и thread routing, но не заменяет full roadmap inventory.
- `docs/validation-log.md` хранит validation waves и acceptance churn, но не заменяет roadmap memory.
- `docs/task-queue.md` and `docs/validation-log.md` store recent-work review: what was tried, what materially changed, what repeated, expected decision change, cost/value decision, and loop-guard decisions.
- Runtime outputs считаются evidence, но не roadmap memory.
- Empty roadmap или отсутствие ready tasks не означают `MVP done`, пока product brief не подтверждает, что целевые user-visible outcomes реально закрыты.
- Каждая задача должна быть связана с конкретным product outcome, user scenario или proof target. Если задача описывается только как внутренний cleanup без связи с продуктовым контрактом, её нельзя ставить автоматически.
- Если implementation uncertainty можно сначала закрыть через bounded research по repo/docs/official sources, не задавай пользователю вопрос сразу. Сначала research-task, потом либо решение, либо уже evidence-backed вопрос.
- `docs/roadmap.md` должен менять phase/task state, а не выступать журналом каждого validation micro-step. Если state не изменился, собирай validation churn в `docs/validation-log.md` или другой wave summary.
- Legacy `MVP_ROADMAP` и `ENGINEERING_BREAKDOWN` трактуй как detail appendices или migration inputs, а не как excuse жить на split-brain control-plane бесконечно.
- Старые routing notes могут быть stale. Если они конфликтуют со свежим tracked roadmap и breakdown, выбирай свежий tracked roadmap.
- Ближайший следующий шаг должен быть honest next step из свежего roadmap state, а не blind continuation старого wave pattern.
- Перед любой новой Nikita task сначала применяй `progress-loop-guard.md`: посмотри последние релевантные task results, task queue, validation log и current state; только потом решай next task.
- Любая task, не только e2e, должна иметь expected decision change. Если результат задачи не поменяет решение орка, задачу не ставь.
- Если expected result стоит дорого по времени, лимитам, риску shared outputs или opportunity cost, не ставь задачу; объясни пользователю простым языком и предложи cheaper diagnostic/research/pause/decision.
- Перед любым 100-row, census, multi-hour или repeated speed validation дополнительно применяй speed-run guard.
- Если два clean/complete runs одного source/window/runner класса снова дают тот же rows/hour класс и не меняют R6 decision, ещё один такой run запрещён.
- Для speed work следующий шаг должен быть materially different: telemetry/profiling, bottleneck isolation, source/window reduction, algorithmic change, or explicit pause/decision.
- Task file для любой Nikita task обязан фиксировать `recent_work_review` и `expected_value`; для e2e/speed/repeated/costly work дополнительно `progress_guard`: prior attempts checked, expected rows/hour delta or other primary metric, max runtime/quota, stop_if, and cheaper alternative considered.
- Если expected delta нельзя честно назвать, task queue должна ставить speed line в blocked/paused, а не выдавать очередной long run.

## Ambiguity Escalation

- Если product-visible behavior, приоритет, scope boundary или definition of done не определены в tracked docs, не домысливай их.
- Если ambiguity техническая и researchable, сначала ставь bounded research-task.
- Поднимай вопрос пользователю как bounded decision с вариантами ответа и рекомендуемым вариантом первым.
- Не задавай open-ended вопросы вроде `как лучше` или `что ты хочешь`, если можно подготовить конкретные варианты.

## Git And Multi-Agent Safety

- Parallel writes допустимы только при non-overlapping write-scope.
- Если write-scope пересекается, это не parallel batch.
- Если безопасный split нельзя жёстко зафиксировать в самих task specs, parallel batch не выдавай.
- При интенсивной multi-agent работе prefer отдельные worktrees, если repo policy это требует.
