# Hard Resync Payload

Use this file when an existing orchestrator thread appears stale after skill updates.

The user may paste this payload into the stale thread. Treat it as higher priority than prior thread habits.

```text
HARD RESYNC REQUIRED.

Stop using the previous response style and previous handoff style.

First, reread the current skill files from disk:
- C:/Users/user/.codex/skills/universal-project-orchestrator/SKILL.md
- C:/Users/user/.codex/skills/universal-project-orchestrator/references/control-plane-bootstrap.md
- C:/Users/user/.codex/skills/universal-project-orchestrator/references/manual-file-handoff-contract.md
- C:/Users/user/.codex/skills/universal-project-orchestrator/references/project-intake-and-clarification.md
- C:/Users/user/.codex/skills/universal-project-orchestrator/references/roadmap-operating-model.md
- C:/Users/user/.codex/skills/universal-project-orchestrator/references/delegation-source-of-truth.md
- C:/Users/user/.codex/skills/universal-project-orchestrator/references/progress-loop-guard.md

If this is Nikita Project, also reread:
- C:/Users/user/.codex/skills/nikita-project-orchestrator/SKILL.md
- C:/Users/user/.codex/skills/nikita-project-orchestrator/references/universal-sync-invariants.md
- C:/Users/user/.codex/skills/nikita-project-orchestrator/references/project-tasking-source-of-truth.md

After rereading, normal replies must follow these rules:
- Start with a plain context lead: what product/runtime area this is, who/what it matters to, and what result is moving.
- Explain what was fixed/proven, what remains unproven, and why the next task follows when state changed.
- Do not start with task ids or internal labels.
- Do not list updated files unless I explicitly ask for file audit/diff.
- Do not use legacy headings or mandatory sections.
- Do not print inline task specs in chat.
- Before any dispatch or follow-up, review recent work/results and expected value. Do not dispatch a task whose expected result repeats no-progress work or is not worth its cost.
- If the expected result is too expensive for the likely value, stop and explain that plainly instead of creating a task.
- If dispatching, create task files on disk and give only copy blocks.
- Each copy block must contain exactly three physical lines with no blank line: task id, role line, absolute task-file path.
- `Параллельность` must be exactly `Параллельность: Да` or `Параллельность: Нет`.
- Include `Треды: New` or `Треды: Continue <TASK_ID>`.

Now redo your last answer according to the reread contract. Do not answer from memory.
```
