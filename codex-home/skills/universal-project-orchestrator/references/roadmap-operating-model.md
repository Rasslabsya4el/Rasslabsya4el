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

## Parallel Planning Rules

- Пользователь может ставить сколько угодно first-level threads параллельно.
- Ограничение идёт не от числа threads, а от dependency readiness, disjoint ownership и runtime safety.
- Планируй parallel dispatch по полному task inventory проекта, а не только по текущей фазе.
- Если в роудмепе видны только `1-2` задачи из-за неполной декомпозиции остальных фаз, это broken planning state; сначала исправь роудмеп.
- Как только phase graph и ownership позволяют safe parallel dispatch, отдавай полный ближайший parallel batch по проекту, а не одну задачу из страха перед параллельностью.
