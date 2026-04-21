# Task Handoff Contract

Read this before emitting any worker or validation handoff. Follow it verbatim.

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

## Unified Worker Task Spec

```text
Роль: сабтаск воркер. Используй $universal-subtask-worker.
ТЗ-<ID>

Что нужно сделать
- ...
- ...

Зачем это нужно
- ...

Scope
- ...
- ...

Не трогать
- ...
- ...

Делегация внутри задачи
- Да. Спавн ...
- Нет. NO_VALID_SUBAGENT_SPLIT.

Какие проверки запустить
- ...
- ...

Что считать acceptance
- ...
- ...

Формат отчёта
- Первая строка: ТЗ-<ID>
- Секции: что изменено / какие проверки запущены / результаты проверок / residual risk / handoff notes
- Если checks не запускались: Tests not run by policy.
```

Если проект использует dedicated validation runner, сохраняй ту же форму task spec. Меняется только role line. Всё остальное, включая thread routing вне fenced block и отсутствие backticks внутри task spec, остаётся тем же.

Если validation target уже привязан к prior artifacts, handoff-и targeted window или targeted slice вместо blind top-N rerun.

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
