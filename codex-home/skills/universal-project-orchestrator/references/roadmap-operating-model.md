# Roadmap Operating Model

Read this before planning, acceptance, rejection, or dispatch. Follow it verbatim.

## Canonical Control-Plane Set

Проект должен иметь один tracked control-plane set:

- `docs/project/PRODUCT_BRIEF.md` — canonical product source of truth;
- `docs/project/CURRENT_STATE.md` — conservative snapshot того, что tracked source реально умеет сейчас;
- `docs/project/DECISION_LOG.md` — durable product/architecture decisions;
- `docs/roadmap.md` — фазы и полный currently knowable task inventory до MVP;
- `docs/task-queue.md` — current dispatchable batch, in-flight items и blocked queue;
- `docs/validation-log.md` — batch-level validation ledger / wave summaries;
- `docs/project/PRODUCT_SPEC.md` — optional detailed contract, если brief слишком coarse.

Canonical templates and root policy template live here:

- `C:\Coding\Main readme repo\AGENTS_TEMPLATE.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\project\PRODUCT_BRIEF.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\project\CURRENT_STATE.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\project\DECISION_LOG.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\project\PRODUCT_SPEC.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\roadmap.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\task-queue.md`
- `C:\Coding\Main readme repo\project-doc-templates\docs\validation-log.md`
- `C:\Users\user\.codex\skills\universal-project-orchestrator\references\progress-loop-guard.md`

Bootstrap и migration правила:

- Не считай имя файла достаточным описанием структуры.
- Если canonical docs отсутствуют, stale или legacy-shaped, сначала открой `AGENTS_TEMPLATE.md` и нужные project-doc templates по absolute paths выше.
- Создавай canonical docs по structure template, а потом уже мигрируй в них факты из tracked repo context.
- Если canonical files отсутствуют, синтезируй их из existing tracked sources: `AGENTS.md`, `README`, specs, legacy roadmap/state docs, architecture notes и nearby source.
- Если repo живёт на legacy именах, не используй это как excuse для бесконечной ad hoc памяти. Собери canonical files и трактуй старые документы как migration inputs или detail appendices.
- Если tracked context реально не даёт восстановить product-defining facts, только тогда поднимай bounded user question с вариантами ответа и рекомендуемым вариантом первым.
- Если shell output даёт mojibake на UTF-8 rich docs, сначала почини encoding и перечитай файл; mojibake не считается valid source of truth.

## Roadmap Must Contain

- summary проекта;
- MVP outcome;
- ссылку или явную привязку к отдельному product brief/spec, который описывает что продукт должен делать и зачем;
- phases с кодами `R1`, `R2`, `R3` и далее, с целью, exit criteria, dependencies и status;
- детальные задачи внутри каждой фазы;
- полный task inventory по всем нетерминальным или planned фазам до MVP;
- все currently knowable задачи, которые уже можно назвать из текущего контекста, а не только ближайшие `1-2` next tasks;
- текущий dispatchable queue;
- roadmap как canonical storage для phase tasks: task queue, thread notes или user-facing reply не могут быть единственным местом, где эти задачи живут;
- риски и deferred items.

## Product Source Of Truth

- У проекта должен быть отдельный durable product brief/spec, который не совпадает с roadmap.
- Предпочитай `docs/project/PRODUCT_BRIEF.md`, `docs/project/PRODUCT_SPEC.md`, `docs/product.md`, `docs/mvp.md`, `docs/spec.md`, `PRODUCT_BRIEF.md`, `PROJECT_BRIEF.md`, legacy `PROJECT_SCOPE.md` или другой tracked doc с явной фиксацией product goal, target user, key user scenarios, in-scope/out-of-scope, MVP outcome и critical proof scenarios.
- Если product brief отсутствует, stale или не покрывает user-visible behavior, сначала почини именно этот слой. Не продолжай orchestration по памяти и не пытайся выводить продуктовую цель из roadmap.
- Перед созданием или крупной переписью product brief/spec сначала прогоняй intake gate по `project-intake-and-clarification.md`. Repo context помогает строить варианты, но не отменяет необходимость закрыть decision-changing product gaps.
- Empty task queue, exhausted roadmap или отсутствие ready tasks не равны `MVP done`. MVP считается доказанным только если product brief говорит, что должно быть готово, и roadmap/evidence показывают, что эти user-visible outcomes реально закрыты.
- Каждая dispatchable задача должна быть привязана хотя бы к одному product outcome, user scenario или proof target из product brief. Если такой привязки нет, это не roadmap gap, а product-alignment gap; сначала чини product brief или задавай вопрос пользователю.
- Перед любой новой задачей читай `progress-loop-guard.md`: оркестратор должен посмотреть последние релевантные tasks/results, понять был ли material progress, и оценить expected value vs cost. Это относится ко всем задачам, не только к e2e и дорогим run-ам.
- Если следующий task не меняет решение, повторяет тот же результат или стоит дороже ожидаемой пользы, останови dispatch и объясни это пользователю простым языком.
- Если implementation uncertainty относится к technical path, integration tactic, library choice, validation method или architecture decision, сначала закрывай её через bounded research. Пользователь нужен только там, где после research остаётся business/product ambiguity или private knowledge gap.

## Intake And Clarification Gate

Детальный контракт живёт в `project-intake-and-clarification.md`.

Короткие правила:

- перед roadmap bootstrap или major replan сначала проверь, decision-stable ли product contract;
- если missing answers ещё меняют scope, MVP proof, phases или acceptance, сначала спроси пользователя;
- вопросы должны быть только option-based и grounded in repo context;
- спрашивай минимальный question pack, а не свободное интервью;
- после ответов сначала обнови `PRODUCT_BRIEF` или `PRODUCT_SPEC`, и только потом roadmap и task queue.

## Phase Rules

- фаза должна быть достаточно узкой, чтобы её прогресс был виден пользователю;
- размечай весь уже понятный путь до MVP сразу, а не только ближайшую фазу;
- на каждом planning pass сначала добивайся полного currently knowable breakdown по всему пути до MVP; missing tasks допустимы только там, где работа реально не может быть определена до нового evidence;
- у каждой нетерминальной или planned фазы задачи обязаны быть прописаны прямо в роудмепе, а не только жить в thread context;
- если breakdown по всем нетерминальным или planned фазам ещё не собран, первым делом останови новый dispatch и исправь роудмеп;
- проектируй phase task lists так, чтобы по ним было видно serial work, parallel work и блокирующие зависимости;
- если после декомпозиции у фазы больше `6` явно понятных задач, не скрывай лишние задачи; либо оставь полный список, либо переразбей фазу, но все known tasks всё равно должны остаться явно записанными в roadmap;
- если фаза прошла `6` task cycles без явного milestone movement, остановись и переразметь роудмеп перед следующей постановкой;
- после materially relevant acceptance или rejection обновляй breakdown не только текущей фазы, но и всех затронутых downstream/upstream фаз;
- roadmap должен отражать phase/task state, а не служить журналом каждого validation micro-step;
- если phase/task state не поменялся, не делай отдельную roadmap rewrite и отдельный doc-only commit на каждый validation run; своди serial validation churn в один wave summary или validation ledger на batch;
- если MVP outcome фазы уже доказан, закрой фазу и вынеси residuals в backlog или в следующую фазу;
- не держи nice-to-have и MVP-critical work в одной фазе без явного разделения.

## Where To Keep The Roadmap

- `docs/roadmap.md`, если есть `docs/`;
- иначе `roadmap.md` в root;
- если tracked repo пока нет, отдай роудмеп в thread и явно скажи, что tracked roadmap file пока отсутствует.

## Where To Keep Related Planning Files

- `docs/task-queue.md` — для current ready/in-flight/blocked queue и thread routing, но не как единственное место хранения phase tasks;
- `docs/validation-log.md` — для batch-level validation churn, а не для phase/task memory;
- `docs/project/CURRENT_STATE.md` — для conservative snapshot подтверждённого tracked behavior;
- `docs/project/DECISION_LOG.md` — для durable решений, reversals и boundaries;
- legacy planning docs вроде `MVP_ROADMAP.md`, `ENGINEERING_BREAKDOWN.md`, `status.md` или `tasking guide` используй как migration inputs или detail appendices, а не как excuse держать split-brain planning surface навсегда.

## Operating Loop

1. Проверь `git status` и ближайший repo policy doc перед planning edits или acceptance decisions.
2. Сначала проверь canonical control-plane set. Если `PRODUCT_BRIEF`, `CURRENT_STATE`, `DECISION_LOG`, roadmap, task queue или validation log отсутствуют, stale или живут только в legacy aliases, сначала открой `C:\Coding\Main readme repo\AGENTS_TEMPLATE.md` и нужные template files из `C:\Coding\Main readme repo\project-doc-templates\...`.
3. Создай или мигрируй canonical docs по structure templates, а затем наполни их фактами из tracked repo context.
4. Прогони intake/clarification gate. Если product contract ещё не decision-stable, сначала задай минимальный option-based question pack и обнови product brief/spec по ответам.
5. Затем перечитай tracked product brief/spec вместе с roadmap и task queue. Не считай roadmap достаточным источником сам по себе.
6. Если product brief отсутствует, stale, противоречит явному user intent или не описывает critical user scenarios, сначала исправь его или задай пользователю вопрос.
7. Если roadmap или task queue отсутствуют, stale, хранят только локальный short queue или не покрывают задачами все нетерминальные/planned фазы, сначала обнови их до полного currently knowable inventory и честного current batch.
8. Выполни delegation check и parallelism check по всему актуальному phase graph, затем собери полный safe dispatchable batch из всех ready tasks, а не локальную пару next tasks.
9. Перед любой новой задачей выполни progress review / expected value gate: сравни recent task results, repeated pattern, last material progress, current bottleneck, expected decision change и estimated cost по `docs/validation-log.md`, task results, task queue и current state.
10. Прими explicit decision: `accepted`, `rejected`, `blocked` или `needs_followup_task`.
11. Если progress review показывает no-progress loop или poor expected value, не dispatch-и задачу; запиши review и выбери materially different diagnostic/research/user decision/pause.
12. Если проблема выглядит researchable через repo/docs/primary sources, сначала проведи bounded research-pass или выдай отдельную research-task. Не эскалируй это сразу пользователю.
13. Если после research product-visible behavior, success criteria, scope boundary, priority или private business knowledge всё ещё не определены в tracked docs, только тогда подними bounded option-based user question pack.
14. После acceptance или rejection пересчитай immediate next dispatch из freshest context, product brief, current state, decision log и полного роудмепа, а не копируй старый локальный план.
15. Если в этой фазе были запущены orchestrator-owned subagents, не завершай user-facing ответ, пока их output не интегрирован или явно не discarded.
16. После materially accepted задачи обновляй roadmap, phase status, phase task lists и текущий `docs/task-queue.md` только когда реально изменился tracked planning state. Validation-only evidence и micro-acceptance churn своди в `docs/validation-log.md` или другой wave summary. Product brief обновляй только когда меняется именно продуктовый контракт, а не статус инженерной работы.

## Skill Update Resync

Если пользователь пишет, что skill обновлён, формат обновлён, правила обновлены, надо перечитать skill, или ты сам понимаешь, что активный orchestrator contract изменился:

1. Считай это top-priority control-plane instruction, которая важнее текущего content question.
2. Немедленно останови старую линию рассуждения, старый dispatch plan и старую локальную трактовку формата.
3. Перечитай активный orchestrator skill и все reference-файлы, на которые он сейчас опирается для roadmap, response format, task handoff и progress-loop guard.
4. Сразу после этого открой `C:\Coding\Main readme repo\AGENTS_TEMPLATE.md` и нужные files из `C:\Coding\Main readme repo\project-doc-templates\...`, чтобы resync идти по canonical structure, а не по памяти.
5. Сразу после этого проведи contract audit tracked planning surface:
   - tracked product brief/spec;
   - tracked roadmap file;
   - tracked task queue и validation log, если они есть;
   - ближайшие tracked planning docs, которые управляют queue/schedule/dispatch, если они есть;
   - текущий user-facing output shape против нового контракта.
6. Если planning docs stale или противоречат новому skill contract, сначала исправь их по structure templates, а уже потом отвечай по существу или ставь новые задачи.
7. Не отвечай на вопросы про next task, definition of done, progress, numbering, "что ты уже делал с роудмепом" или другие planning implications из pre-resync state, пока этот audit не завершён.
8. Если skill-update signal пришёл в одном сообщении вместе с другим вопросом, сначала сделай resync и repair, и только потом отвечай на остальную часть сообщения уже из post-resync state.
9. После audit пересчитай immediate dispatch batch заново из обновлённого tracked plan, даже если до обновления skill уже был старый "следующий шаг".
10. Если repair требовался, не ограничивайся диагностической строкой в ответе. Сначала меняй tracked docs, потом показывай уже исправленное состояние.

## Parallel Planning Rules

- Пользователь может ставить сколько угодно first-level threads параллельно.
- Ограничение идёт не от числа threads, а от dependency readiness, disjoint ownership и runtime safety.
- Планируй parallel dispatch по полному task inventory проекта, а не только по текущей фазе.
- Если в роудмепе видны только `1-2` задачи из-за неполной декомпозиции остальных фаз, это broken planning state; сначала исправь роудмеп.
- Не жди отдельной просьбы пользователя на ещё одну-две задачи: если safe-ready задачи уже видны, они должны быть занесены в roadmap и включены в текущий dispatch batch сразу.
- Как только phase graph и ownership позволяют safe parallel dispatch, отдавай полный ближайший parallel batch по проекту, а не одну задачу из страха перед параллельностью.
