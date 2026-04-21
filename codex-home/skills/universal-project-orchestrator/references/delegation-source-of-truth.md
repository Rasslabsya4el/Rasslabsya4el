# Delegation And Parallelism Source Of Truth

Этот reference — durable default source of truth для orchestration task batching и worker-side subagent planning.

Он собран из tracked project policies и нужен для того, чтобы не отправлять каждый следующий агент обратно в проектные policy docs за одними и теми же правилами.

## Core Defaults

- Пользовательский бюджет first-level threads считай практически неограниченным.
- Ограничение идёт не от числа threads, а от dependency readiness, disjoint ownership и runtime safety.
- По умолчанию допускай один полезный first-level слой делегации.
- Recursive delegation не использовать, если более близкая repo policy явно не разрешает его.
- В начале каждой major phase делай ровно одно:
  - спавни smallest useful first-level batch с реально disjoint scopes;
  - или явно пиши `NO_VALID_SUBAGENT_SPLIT`.

## Safe Parallelism

- Параллельность допустима только при disjoint scopes.
- Один writer на файл на фазу.
- Shared orchestration files, shared schema/contracts, roadmap docs и общий runtime config по умолчанию считай serial contour, пока ownership не доказан иначе.
- New-file или isolated-module work можно dispatch-ить параллельно, только если write-scope реально не пересекается.
- Не используй vague labels вроде `можно потом распараллелить`.
- Либо выдавай exact parallel batch, либо честно говори, что параллельности сейчас нет.

## Phase Sizing

- Размер оценивай по текущей фазе, а не по всей задаче.
- Small phase обычно держи локально.
- Medium phase обычно распадается на `1-3` first-level tracks.
- Large read-only phase можно fanout-ить шире, если scopes естественно disjoint и runtime cap это выдерживает.
- Large write phase сначала режь по non-overlapping ownership, потом уже валидируй.

## Worker-Side Spawn Plans

Если orchestrator просит worker-а спавнить subagents, task spec обязана заранее фиксировать:

- сколько first-level subagents надо спавнить;
- какого типа каждый subagent;
- какой у него narrow objective;
- какой file/module ownership или read scope;
- какой expected output;
- какой stop condition;
- какой validation target;
- что completed subagents надо закрыть сразу после integration.

Если такой план заранее не получается сформулировать безопасно, пиши `Делегация внутри задачи: Нет` и `NO_VALID_SUBAGENT_SPLIT`.

## Lifecycle

- Parent обязан дождаться output каждого spawned subagent.
- Parent обязан output интегрировать или явно discard-нуть с причиной.
- Completed subagents надо закрывать promptly после integration.
- Не переходи к следующей фазе, пока outputs текущей фазы не обработаны и completed agents не закрыты.
- Оставить completed subagent открытым — policy violation, а не harmless artifact.

## Reassessment

- После каждой integration step reassess delegation заново.
- Не держи старый spawn plan только потому, что он уже был once chosen.
- Если phase graph поменялся, пересобери batch.
