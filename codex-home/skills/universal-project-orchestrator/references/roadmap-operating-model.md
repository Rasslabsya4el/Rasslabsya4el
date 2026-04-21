# Roadmap Operating Model

Read this before planning, acceptance, rejection, or dispatch. Follow it verbatim.

## Roadmap Must Contain

- summary проекта;
- MVP outcome;
- phases с кодами `R1`, `R2`, `R3` и далее, с целью, exit criteria, dependencies и status;
- детальные задачи внутри каждой фазы;
- полный task inventory по всем нетерминальным или planned фазам до MVP;
- текущий dispatchable queue;
- риски и deferred items.

## Phase Rules

- фаза должна быть достаточно узкой, чтобы её прогресс был виден пользователю;
- размечай весь уже понятный путь до MVP сразу, а не только ближайшую фазу;
- у каждой нетерминальной или planned фазы задачи обязаны быть прописаны прямо в роудмепе, а не только жить в thread context;
- если breakdown по всем нетерминальным или planned фазам ещё не собран, первым делом останови новый dispatch и исправь роудмеп;
- проектируй phase task lists так, чтобы по ним было видно serial work, parallel work и блокирующие зависимости;
- по умолчанию фаза должна содержать примерно `2-6` подзадач, а не бесконечный хвост микротасок;
- если фаза прошла `6` task cycles без явного milestone movement, остановись и переразметь роудмеп перед следующей постановкой;
- после materially relevant acceptance или rejection обновляй breakdown не только текущей фазы, но и всех затронутых downstream/upstream фаз;
- если MVP outcome фазы уже доказан, закрой фазу и вынеси residuals в backlog или в следующую фазу;
- не держи nice-to-have и MVP-critical work в одной фазе без явного разделения.

## Where To Keep The Roadmap

- `docs/roadmap.md`, если есть `docs/`;
- иначе `roadmap.md` в root;
- если tracked repo пока нет, отдай роудмеп в thread и явно скажи, что tracked roadmap file пока отсутствует.

## Operating Loop

1. Проверь `git status` и ближайший repo policy doc перед planning edits или acceptance decisions.
2. Читай только directly relevant files, ближайший planning doc и минимально нужные policy docs.
3. Если роудмеп отсутствует, stale или не покрывает задачами все нетерминальные/planned фазы, сначала обнови его.
4. Выполни delegation check и parallelism check по всему актуальному phase graph, а не только по одной текущей фазе.
5. Прими explicit decision: `accepted`, `rejected`, `blocked` или `needs_followup_task`.
6. После acceptance или rejection пересчитай immediate next dispatch из freshest context и полного роудмепа, а не копируй старый локальный план.
7. Если в этой фазе были запущены orchestrator-owned subagents, не завершай user-facing ответ, пока их output не интегрирован или явно не discarded.
8. После каждой materially accepted задачи обнови роудмеп, phase status, phase task lists и ближайший dispatch batch.

## Skill Update Resync

Если пользователь пишет, что skill обновлён, формат обновлён, правила обновлены, надо перечитать skill, или ты сам понимаешь, что активный orchestrator contract изменился:

1. Считай это top-priority control-plane instruction, которая важнее текущего content question.
2. Немедленно останови старую линию рассуждения, старый dispatch plan и старую локальную трактовку формата.
3. Перечитай активный orchestrator skill и все reference-файлы, на которые он сейчас опирается для roadmap, response format и task handoff.
4. Сразу после этого проведи contract audit tracked planning surface:
   - tracked roadmap file;
   - ближайшие tracked planning docs, которые управляют queue/schedule/dispatch, если они есть;
   - текущий user-facing output shape против нового контракта.
5. Если planning docs stale или противоречат новому skill contract, сначала исправь их, а уже потом отвечай по существу или ставь новые задачи.
6. Не отвечай на вопросы про next task, definition of done, progress, numbering, "что ты уже делал с роудмепом" или другие planning implications из pre-resync state, пока этот audit не завершён.
7. Если skill-update signal пришёл в одном сообщении вместе с другим вопросом, сначала сделай resync и repair, и только потом отвечай на остальную часть сообщения уже из post-resync state.
8. После audit пересчитай immediate dispatch batch заново из обновлённого tracked plan, даже если до обновления skill уже был старый "следующий шаг".
9. Если repair требовался, не ограничивайся диагностической строкой в ответе. Сначала меняй tracked docs, потом показывай уже исправленное состояние.

## Parallel Planning Rules

- Пользователь может ставить сколько угодно first-level threads параллельно.
- Ограничение идёт не от числа threads, а от dependency readiness, disjoint ownership и runtime safety.
- Планируй parallel dispatch по полному task inventory проекта, а не только по текущей фазе.
- Если в роудмепе видны только `1-2` задачи из-за неполной декомпозиции остальных фаз, это broken planning state; сначала исправь роудмеп.
- Как только phase graph и ownership позволяют safe parallel dispatch, отдавай полный ближайший parallel batch по проекту, а не одну задачу из страха перед параллельностью.
