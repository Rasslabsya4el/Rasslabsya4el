# Nikita Project Tasking Source Of Truth

Этот reference фиксирует project-specific source of truth для orchestration, roadmap discipline и safe parallelism.

Используй его вместо повторных походов в проектные docs, если вопрос уже покрыт этим summary.

## Главные Источники

- `AGENTS.md` — delegation policy, first-level spawn rules, lifecycle и write ownership.
- `docs/project/MVP_ROADMAP.md` — текущий MVP, phases, accepted slices и ближайший honest next step.
- `docs/project/ENGINEERING_BREAKDOWN.md` — инженерные границы runtime, writer contour и current safe execution path.
- `GIT_WORKFLOW.md` — multi-agent write ownership и worktree discipline.

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

## Current Narrow Safe Contour

- Current multithread contour узкий.
- Multithread rollout не считать уже глобально открытым.
- Project-specific guardrails и source-aware routing надо уважать до новых accepted proofs.
- Не планируй task batch так, будто любой source set уже safe для parallel rollout.

## Planning Discipline

- Primary roadmap source of truth — tracked roadmap, а не runtime outputs.
- Runtime outputs считаются evidence, но не roadmap memory.
- Старые routing notes могут быть stale. Если они конфликтуют со свежим tracked roadmap и breakdown, выбирай свежий tracked roadmap.
- Ближайший следующий шаг должен быть honest next step из свежего roadmap state, а не blind continuation старого wave pattern.

## Git And Multi-Agent Safety

- Parallel writes допустимы только при non-overlapping write-scope.
- Если write-scope пересекается, это не parallel batch.
- При интенсивной multi-agent работе prefer отдельные worktrees, если repo policy это требует.
