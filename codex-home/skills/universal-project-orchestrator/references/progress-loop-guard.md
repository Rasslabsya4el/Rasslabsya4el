# Progress Review And Expected Value Gate

Use this before every dispatch, every follow-up task, every acceptance/rejection follow-up, and every "next task" decision.

This is not only for e2e and not only for expensive runs. The orchestrator must always look back at recent work, decide whether progress is real, and decide whether the next task is worth doing.

## Always Review Recent Work

Before creating any task file, review the freshest relevant history:

- current user-provided result path, if any;
- current task family folder in `.orchestrator/tasks/**`;
- last 3-7 completed or blocked task results relevant to the same product area;
- `docs/task-queue.md`;
- `docs/validation-log.md`;
- `docs/project/CURRENT_STATE.md`;
- `docs/roadmap.md`.

If a project has fewer than 3 prior tasks, review all available prior work.

The review must answer:

```text
recent_work_review:
- looked_at:
- last_material_progress:
- repeated_pattern: yes | no
- same_problem_count:
- current_bottleneck:
- why_next_step_is_not_blind_repeat:
```

## Material Progress

Material progress means the project learned or changed something that affects the next decision:

- a product-visible promise moved from unproven to proven;
- a blocker was isolated to a narrower cause;
- a metric improved enough to change the plan;
- a hypothesis was falsified and the next task is materially different;
- a user/business decision became clearer;
- a risky assumption was removed.

Not material progress:

- another task with the same result class;
- another clean run with the same speed, error, output, or blocker;
- another refactor/test/validation that does not change product confidence;
- changing task ids while proving the same thing;
- "try again" with no new mechanism or hypothesis;
- a long run whose expected result would not change the next decision.

## Expected Value Gate

Before dispatch, compare expected decision value against cost.

Cost includes:

- wall-clock time;
- paid API/quota/rate limits;
- user attention;
- risk of corrupting shared outputs;
- opportunity cost of blocking other work;
- complexity added to the project;
- model/context churn.

The next task is allowed only if it has a clear expected decision change:

```text
expected_value:
- expected_result:
- decision_it_will_change:
- estimated_cost:
- worth_it: yes | no
- cheaper_alternative:
- stop_condition:
```

If `worth_it: no`, do not dispatch the task. Explain in plain language why the expected result is not worth the cost, and either pause the line, ask a bounded user decision, or dispatch a cheaper diagnostic.

## Repeat Stop Rule

Stop dispatching same-class work when any condition is true:

- two relevant attempts in a row produced no material progress;
- the same bottleneck appeared 3+ times in recent work;
- the proposed task has no new hypothesis, mechanism, input slice, or acceptance boundary;
- the expected result would be "we will probably see the same class of result again";
- the task cost is high and the expected decision change is low.

Same-class work means the same product proof target, same bottleneck, same validation class, same metric, same failure class, or same implementation loop — even if the role, task id, or exact command changed.

## Zoom-Out Stop Behavior

When the gate blocks a task, the orchestrator must:

1. stop normal dispatch;
2. write a short review into `docs/validation-log.md`, `docs/task-queue.md`, or the relevant task result surface;
3. tell the user plainly what happened;
4. choose one of:
   - materially different diagnostic task;
   - bounded research task;
   - bounded user decision;
   - pause/blocked state.

Review shape:

```text
progress_review:
- product_area:
- recent_attempts:
- repeated_result:
- material_progress:
- cost_spent_or_expected:
- why_more_of_the_same_is_blocked:
- cheapest_meaningful_next_step:
```

## Task File Fields

Every task file must include `recent_work_review` and `expected_value`.

```text
recent_work_review:
- looked_at:
- last_material_progress:
- repeated_pattern:
- same_problem_count:
- current_bottleneck:
- why_next_step_is_not_blind_repeat:

expected_value:
- expected_result:
- decision_it_will_change:
- estimated_cost:
- worth_it:
- cheaper_alternative:
- stop_condition:
```

For repeated or costly work, also include `progress_guard`:

```text
progress_guard:
- attempt_fingerprint:
- previous_attempts_checked:
- expected_delta:
- max_cost:
- stop_if:
- cheaper_alternative_considered:
```

If the task is not repeated or costly, write:

```text
progress_guard:
- not_repeated_or_costly
```

## User-Facing Behavior

If the gate blocks a task, explain it simply:

```text
Мы сейчас не ставим следующую задачу, потому что последние попытки не меняли решение: они снова показывали тот же результат.
Ещё одна такая задача потратит время/лимиты, но почти наверняка не даст нового понимания.
Следующий осмысленный шаг — сначала найти причину дешевле или поставить эту линию на паузу.
```

Do not hide this behind queue/file/task terminology.
