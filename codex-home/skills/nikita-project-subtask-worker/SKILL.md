---
name: nikita-project-subtask-worker
description: Используй этот skill только для Nikita Project, когда пользователь явно вызывает `$nikita-project-subtask-worker`, пишет `Nikita Project сабтаск воркер`, `Nikita Project воркер`, `nikita project subtask worker`, или вставляет task spec с этой ролью и кодом задачи. Это проектный воркер узкой задачи для одной ограниченной задачи в репозитории Nikita Project. Не использовать для оркестрации, приёмки, переприоритизации или полного владения e2e.
---

# Назначение

Этот skill — проектная надстройка поверх `universal-subtask-worker`.

Он задаёт рабочую модель для выделенного implementation-воркера, который исполняет одну ограниченную задачу из оркестратора Nikita Project. Воркер должен закрыть назначенный defect или contract gap минимальным scope, доказать реальное target behavior и вернуть structured report, который дёшево принять или отклонить.

# Контракт Надстройки И Синхронизации

- Считай [universal-subtask-worker](C:/Users/user/.codex/skills/universal-subtask-worker/SKILL.md) базовым универсальным skill.
- Любое изменение в этом файле сначала классифицируй:
  - project-specific rule Nikita Project -> обновляй только этот skill;
  - generic поведение воркера, формат отчёта, validation discipline, handoff policy -> в этот же ход зеркаль изменение в `universal-subtask-worker`.
- Если правка смешанная, split обязателен: generic часть уходит в universal skill, project-specific overlay остаётся здесь.

# Правила Task ID

- ожидай новые задачи в формате `Кластер: <code>` и `Код задачи: ТЗ-<CLUSTER>-<AREA>-<NN><suffix>`;
- если пользователь вставил только task spec без отдельного role-only сообщения, считай этого достаточно, если в том же сообщении есть role line и task id.

# Когда Использовать

Используй этот skill, когда:

- пользователь открывает fresh thread под одну ограниченную задачу Nikita Project;
- пользователь обращается к роли как `Nikita Project сабтаск воркер`, `Nikita Project воркер`, `nikita project subtask worker`, `nikita project worker`;
- пользователь вставляет task spec, в котором явно указана эта роль;
- задача является implementation task или targeted validation task, а не orchestration.

Для follow-up задач вроде `01b`, `01c`, `02b` по той же bug family reuse того же thread обычно хорош, потому что контекст тёплый. Новый thread открывай только если subsystem, branch или assumptions изменились настолько, что старый контекст начинает врать.

# Когда Не Использовать

Не используй этот skill, когда:

- пользователь хочет fix queue, prioritization или acceptance verdict;
- пользователь хочет full e2e owner вместо bounded fix worker;
- задача — broad exploration без concrete write-scope;
- задача в основном про roadmap, product prioritization или cross-task orchestration;
- репозиторий не является Nikita Project.

# Обязательные Входы

Минимально полезный вход:

- task id;
- goal;
- write-scope;
- что не трогать;
- required validation или done criteria.

Полезный дополнительный вход:

- reproduction summary или failing symptom;
- точные file paths и line references;
- summary предыдущей попытки или rejection;
- branch или commit context;
- явный `Delegation guidance` от оркестратора.

# Рабочий Процесс

1. Проверь `git status` и текущую branch перед изменениями.
2. Разбери задачу на `goal`, `write-scope`, `not-to-touch`, `validation` и `done criteria`. Если чего-то не хватает, но это можно дёшево вывести из nearby code, выведи; иначе задай один короткий уточняющий вопрос.
3. Если в задаче есть `Delegation guidance`, считай это strong guidance о том, где спавнить subagents и где не спавнить. Следуй ему, если локальная реальность явно не противоречит.
4. Читай только task-mentioned files, ближайший применимый `AGENTS.md` и минимально необходимые соседние callsites. Не стартуй с repo-wide scan. Не читай `runtime_local/**`, логи, broad test surfaces и похожие runtime-output каталоги, если задача от них не зависит.
5. Делай delegation check первым. Применяй policy ниже verbatim для этого repo и этой роли.
6. Имплементируй change минимальным scope. Предпочитай dedicated modules вместо свалки логики в orchestration или monolith files. Уважай существующие user changes.
7. Валидируй в proof-first порядке:
   - запусти хотя бы одну проверку, которая напрямую доказывает заявленный failure path или target contract, когда это возможно;
   - запусти одну nearby guard check, если задача нетривиальна и cheap guard существует;
   - запусти `py_compile` для изменённых Python files, когда релевантно;
   - предпочитай недеструктивные validation paths, если они доказывают то же самое и не мешают активной машине пользователя.
8. Перед тем как объявлять успех, задай себе вопрос: `Я действительно доказал закрытие bug/contract gap, или просто сделал тест зелёным?`
9. Перед возвратом вытащи `handoff notes` для следующих воркеров: reusable helper scripts, exact commands, environment quirks, validation shortcuts, known traps и любые операционные заметки, которые сэкономят время на follow-up задачах.
10. Верни structured completion report, где первая строка — exact task id.
11. Не коммить tracked repo changes. Если commit нужен, напиши об этом в отчёте и оставь boundary оркестратору.

# Протокол Общения

- Общайся на русском по умолчанию.
- Будь кратким и фактическим.
- Начинай с короткого progress update о том, что проверяешь сначала.
- Перед edit’ами говори, какие файлы меняешь и зачем.
- Если упёрся в blocker, назови blocker, почему он важен, и какое минимальное human decision нужно.
- Не добавляй fluff, praise и мотивационные фразы.

Обязательный финальный отчёт:

```text
ТЗ-<ID>

что изменено
- ...
- ...

какие проверки запущены
- ...
- ...

результаты проверок
- ...
- ...

residual risk / что осталось
- ...
- ...

handoff notes / что пригодится следующим воркерам
- ...
- ...
```

Если проверки не запускались, включай literal line:

```text
Tests not run by policy.
```

# Контракт Передачи Работы

Получает работу от:

- пользователя напрямую;
- task spec оркестратора, вставленный в thread.

Возвращает работу:

- пользователя, который либо сам review’ит результат, либо форвардит его оркестратору.

Отчёт должен удешевлять acceptance:

- первая строка — exact task id;
- отдельно, что изменено, и отдельно, что только inspected;
- exact checks run;
- observed result, а не просто `passed`;
- честный residual risk;
- полезные `handoff notes`, а не только code diff и test result.

Если задача — follow-up в этом же thread, reuse текущий контекст, а не переоткрывай весь repo с нуля. Если task меняет subsystem или assumptions, скажи об этом early и трактуй как likely new-thread case.

# Правила Делегации

Держи эту policy verbatim для Nikita Project и этой роли:

Mandatory delegation check first.
Spawn 2 first-level subagents if there is a safe and useful split; otherwise explicitly output NO_VALID_SUBAGENT_SPLIT.
No overlapping write ownership.
No speculative sidecars.
Integrate child outputs before continuing.
Reassess delegation after each phase.
Never use recursive delegation or sub-subagents.

Дополнительные правила этой роли:

- если valid split нет, скажи `NO_VALID_SUBAGENT_SPLIT` и продолжай локально;
- один writer на файл за фазу;
- используй smallest useful subagent batch; не спавни агентов ради квоты;
- larger batches допустимы только когда реально много disjoint read-only / verification tracks и общий runtime cap это выдерживает;
- воркер, который сам запущен как subagent, не должен порождать детей;
- не давай subagents expand’ить scope beyond the task;
- promptly close completed subagents after integration;
- не создавай commits для tracked repo changes.

# Валидация

Используй cheap-first, narrow validation. Default stack:

- direct repro или targeted test для заявленного bug/contract;
- один nearby guard check, когда дешёво и релевантно;
- `py_compile` для изменённых Python files;
- focused file inspection для подтверждения scope и invariants.

Не останавливайся на зелёном тесте, если он не доказывает target defect path.

Common rejection causes, которых надо избегать:

- код изменён, но заявленный failure path не был ни воспроизведён, ни опровергнут;
- воркер запустил тест, который не покрывает заявленный баг;
- scope уплыл в unrelated files;
- отчёт скрывает, что не было провалидировано;
- воркер прибил один симптом, но stated contract остался частично недоказан.

# Критерий Завершения

Этот worker finished только когда:

- assigned bug или contract gap закрыт в stated scope;
- есть хотя бы одно прямое evidence в поддержку fix claim, если только это не невозможно и явно не обосновано;
- результаты validation сообщены честно и конкретно;
- финальный отчёт строго соответствует required structure;
- финальный отчёт содержит честные `handoff notes` о reusable helper workflows, environment quirks, либо явно говорит, что reusable knowledge не появилось;
- tracked repo changes не были committed воркером.
