# Minimal User-Facing Output

This skill does not use the heavy universal orchestrator markdown reply shape.

User-facing output must be short, mechanical, and cheap.

## General Rules

- No `# ACCEPTED`, `# BLOCKED`, `Human touch`, roadmap block, or long PM summary.
- No task specs in chat.
- No universal orchestrator markdown layout.
- Prefer 4-8 short lines, except when a compact question pack is required.
- Mention only the minimum state needed by the user.

## Normal Autonomous Wave Reply

Use this shape:

```text
AUTONOMOUS_ORCHESTRATOR
status: wave_complete
repo_state: running | blocked | done
tasks_created: <number>
children_spawned: <number>
accepted: <number>
rejected: <number>
heartbeat: armed +1m | not_armed
run_log: C:\repo\.orchestrator\PRODUCT_RUN_LOG.md
```

If one of the counts is zero, still include it.

## Blocked On User Reply

Use this shape:

```text
AUTONOMOUS_ORCHESTRATOR
status: blocked_on_user
reason: missing product contract | clarification_needed
heartbeat: not_armed
```

If clarification is needed, append a minimal option-based pack:

```text
questions:
1. <question>
   - A: ...
   - B: ...
   recommended: A
2. <question>
   - A: ...
   - B: ...
   - C: ...
   recommended: B
```

Do not add roadmap, long explanation, or prose below that.

## Child Skill Binding Failure Reply

Use this shape:

```text
AUTONOMOUS_ORCHESTRATOR
status: blocked_on_child_skill_binding
missing_skill: <skill-name>
heartbeat: not_armed
```

## MVP Done Reply

Use this shape:

```text
AUTONOMOUS_ORCHESTRATOR
status: mvp_done
heartbeat: not_armed
run_log: C:\repo\.orchestrator\PRODUCT_RUN_LOG.md
```
