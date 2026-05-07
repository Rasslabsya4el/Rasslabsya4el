# Task Handoff Contract

Read this before emitting any worker or validation handoff. Follow it verbatim.

Before writing the handoff, also read `agent-context-economy.md`.
This file defines the markdown wrapper and fixed semantic fields.
`agent-context-economy.md` defines what should stay out of the handoff because it already belongs in tracked docs or ledgers.

## Outer Markdown Form

Для каждого task handoff:

- вне fenced block сначала пиши heading level 3, а сам код задачи внутри heading оборачивай в inline code;
- следующей строкой пиши только строку `**Thread:** ...`; если это continuation, код предыдущей задачи тоже оборачивай в inline code;
- между heading с task code, строкой `**Thread:** ...` и fenced task spec не вставляй дополнительный prose;
- только сам task spec заворачивай в fenced block с info string `text`;
- thread-routing instructions никогда не тащи внутрь task spec;
- если task идёт в старый thread, явно называй код предыдущей задачи или треда, который надо продолжить;
- если нужен новый thread, пиши `**Thread:** New`;
- не пиши `Задача 1`, `Задача 2` и аналогичные заголовки;
- дублируй exact task id и вне fenced block, и в начале самой task spec;
- рутинный thread routing пользователя относится к обычному dispatch и не должен влиять на `Human touch`.
- task handoff должен быть безопасен для слепого copy-paste пользователем без дополнительной интерпретации scope, conflict rules или safe parallelism.

## Inside Task Spec

- не используй backticks;
- не используй вложенные fenced blocks;
- не используй markdown links;
- не используй markdown tables;
- не пиши low-signal boilerplate вроде `Project:` или `Repo path:`, если без этого задача остаётся понятной;
- любые упоминания skills пиши только через `$`, а не через текст `если доступен skill`.
- если задача участвует в parallel batch, orchestrator обязан сам заранее сузить её так, чтобы worker не пересекался с соседними задачами по write-scope;
- если такую безопасную границу нельзя сформулировать прямо в `Scope`, `Не трогать` и thread routing, не ставь задачу параллельно.

## Research-First Escalation

- Если ork не знает implementation answer, не задавай пользователю вопрос сразу.
- Сначала определи, можно ли закрыть gap через repo/docs/primary sources или bounded external research.
- Если можно, ставь отдельную research-task или проводи bounded research-pass сам.
- Пользователю эскалируй только то, что после research всё ещё требует business choice, private knowledge, approval или explicit product decision.

## Unified Worker Task Spec

```text
Роль: сабтаск воркер. Используй $universal-subtask-worker.
ТЗ-<ID>

Продуктовый target
- ...

Почему сейчас
- ...

Прочитать
- ...
- ...

Scope записи
- ...

Не трогать
- ...

Сделать
- ...
- ...

Проверки
- ...
- ...

Acceptance для орка
- ...
- ...

Делегация внутри задачи
- Да. Спавн ...
- Нет. NO_VALID_SUBAGENT_SPLIT.

Формат отчёта
- Первая строка: ТЗ-<ID>
- Секции: что изменено / какие проверки запущены / результаты проверок / residual risk / handoff notes
- Если checks не запускались: Tests not run by policy.
```

Контекстно-экономные правила для этого spec:

- в `Прочитать` перечисляй paths, а не пересказывай содержимое файлов;
- не дублируй весь product brief или roadmap внутри задачи;
- в `Сделать` держи только bounded deliverables текущего task;
- если follow-up повторяет большую часть старой задачи, не раздувай новый markdown block, а создавай новый compact spec или переводи семью в file-driven protocol;
- rejection reason держи короткой и операционной, а не essay-style.

Если проект использует dedicated validation runner, сохраняй ту же форму task spec. Меняется только role line. Всё остальное, включая thread routing вне fenced block и отсутствие backticks внутри task spec, остаётся тем же.

Если orchestrator не может привязать задачу к конкретному product outcome, user-visible scenario или proof target из product brief/spec, такую задачу нельзя dispatch-ить до прояснения продуктового контракта.

Если validation target уже привязан к prior artifacts, handoff-и targeted window или targeted slice вместо blind top-N rerun.

Если repo известен нестандартным bootstrap или launcher quirk, orchestrator обязан явно зафиксировать это в `Проверки`: например root `cwd`, `python -m pytest` вместо bare `pytest`, UTF-8 shell output для кириллицы и другие критичные bootstrap assumptions.

## Unified Research Task Spec

```text
Роль: исследователь. Используй $universal-deep-research.
ИСС-<ID>

Вопрос исследования
- ...
- ...

Почему сейчас
- ...

Что уже известно
- ...

Прочитать
- ...

Какие варианты сравнить
- ...
- ...

Какие источники использовать
- tracked docs и nearby source;
- official docs и primary sources;
- вторичные источники только если первичные не закрывают вопрос.

Что считать достаточным ответом
- ...
- ...

Формат отчёта
- Первая строка: ИСС-<ID>
- Секции: findings / options considered / recommendation / remaining unknowns / нужны ли ещё вопросы пользователю
- Если после research всё ещё нужен input пользователя: подготовь bounded questions с вариантами ответа и рекомендуемым вариантом первым
```

Research-task нужна, когда ork упёрся в implementation uncertainty, но это ещё не user-facing product decision.

## `Делегация внутри задачи`

- это поле обязательно в каждой task spec;
- значение только `Да` или `Нет`;
- решение о safe parallelism полностью на orchestrator; пользователь не должен проверять, разделять или интерпретировать batch вручную;
- если `Да`, оркестратор обязан заранее прописать:
  - сколько first-level subagents спавнить;
  - какого типа каждый subagent;
  - какой у него scope;
  - какой output ожидать;
  - какой stop condition;
  - что completed subagents надо закрыть сразу после интеграции результата;
- формулировка `сабтаск воркер` описывает роль воркера, а не глубину делегации;
- worker thread, который пользователь открыл напрямую или которому оркестратор напрямую выдал task spec, может спавнить first-level subagents, если split безопасен и полезен;
- только агент, который уже сам запущен как spawned child subagent, не должен порождать детей;
- если `Нет`, пиши `NO_VALID_SUBAGENT_SPLIT` и короткую причину;
- не оставляй worker-у расплывчатое `подумай, может быть стоит распараллелить`.
- не оставляй и пользователю расплывчатое `не смешивай эти задачи`, `держи lane отдельно` или аналогичные ручные safety instructions; безопасный split обязан быть уже зашит в самих task specs.

## Worker Report Format

Worker report обязан начинаться exact task id из heading над task spec в первой строке и содержать секции:

- `что изменено`
- `какие проверки запущены`
- `результаты проверок`
- `residual risk / что осталось`
- `handoff notes / что пригодится следующим воркерам`

Если checks не запускались, worker report обязан содержать literal line `Tests not run by policy.`
