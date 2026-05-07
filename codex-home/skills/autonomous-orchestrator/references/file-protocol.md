# File Protocol

Use this reference before materializing any autonomous task or result artifact.

This protocol is authoritative for parent/child artifacts in this skill.
Do not fall back to the universal orchestrator markdown handoff shape for these artifacts.

## Task Folder Layout

Each dispatched task lives in its own folder:

```text
.orchestrator/tasks/<TASK_CODE>/
  <TASK_CODE>.task.txt
  RESULT.txt
  FOLLOWUP-01.task.txt
  RESULT-01.txt
  FOLLOWUP-02.task.txt
  RESULT-02.txt
```

Rules:

- the first task file must be named exactly after the task code with `.task.txt`;
- a same-agent follow-up stays in the same task folder;
- a replacement-agent retry gets a new task code and a new folder;
- all paths written into task files must be absolute paths;
- the parent message to the child is only the absolute path of the active task file;
- live task and result artifacts in this skill are text files only; active `.md` artifacts are forbidden.

## ASCII Task Codes

Live task codes must be ASCII-only.

Use `TASK-<PHASE>-<AREA>-<NN>` or another uppercase ASCII scheme using only:

- `A-Z`
- `0-9`
- `-`

Do not use Cyrillic or other non-ASCII characters in live task codes, task folders, or result paths.

## Legacy Artifact Rule

Do not create or reuse these as active task-family artifacts:

- `<TASK_CODE>.md`
- `FOLLOWUP-01.md`
- `RESULT.md`
- `RESULT-01.md`

If you inherit them from an older run, migrate or quarantine them before the next live spawn, wait, or acceptance step.

## Parent-To-Child Message

Parent message format:

```text
C:\absolute\path\to\.orchestrator\tasks\TASK-R2-LANDING-01\TASK-R2-LANDING-01.task.txt
```

No extra prose.
No pasted task body.
No summary outside the file.

The task file itself must be self-contained.

The parent must bind the child role separately through the spawn call:

- `agent_type: default`
- one `skill` item with the chosen installed skill path
- one text item whose entire content is the absolute task-file path above

Do not use a generic platform role label as a replacement for the child skill.

## Reply Gate For Parent

The child reply is valid only when it is the exact expected `result_file` absolute path and nothing else.

The parent must not open sibling artifacts, follow-up drafts, or changed product files until this gate passes.

If the returned path is missing, mismatched, nonexistent, or ends in `.md`, treat it as `protocol_breach`.

## Machine-Oriented Task File

Use a flat key-value and list format.

Keep it compact:

- prefer pointers to tracked docs over pasted content;
- list only the minimum read context needed for this task;
- do not repeat roadmap or brief text that already lives in canonical docs;
- if a tiny embedded excerpt is unavoidable, keep it short and isolated.

Example:

```text
protocol_version: autonomous-orchestrator/v2
role_skill: $universal-subtask-worker
task_kind: implementation
task_code: TASK-R2-BILLING-03
task_fingerprint: billing-export|csv-proof|app/exporters/billing.py
attempt: 1
result_file: C:\repo\.orchestrator\tasks\TASK-R2-BILLING-03\RESULT.txt
return_message: Reply with the absolute result_file path only.

product_target:
- Which product outcome, user scenario, or proof target this task moves.

why_now:
- Why this task is in the current dispatch wave.

read_context_files:
- C:\repo\docs\project\PRODUCT_BRIEF.md
- C:\repo\docs\roadmap.md

write_scope:
- C:\repo\path\allowed\to\edit.py
- C:\repo\another\allowed\file.ts

do_not_touch:
- C:\repo\docs\...
- C:\repo\shared\serial\surface.py

do_work:
- Exact bounded deliverables.
- Exact issue to fix or question to close.

checks_to_run:
- Exact cheap-first checks.
- Prefer headless and non-disruptive checks.

acceptance_for_parent:
- Exact conditions that let the parent accept.

delegation_inside_task:
- No. NO_VALID_SUBAGENT_SPLIT.
```

### Child Skill Selection

Typical `role_skill` values:

- `$universal-subtask-worker`
- `$universal-deep-research`
- a project-specific worker, validator, or runner skill

Do not put `$universal-project-orchestrator` in a child task file.
Do not replace `role_skill` with a generic platform role such as `worker`.

### Follow-Up Files

Same-agent follow-up files stay in the same folder and use the same flat format:

```text
protocol_version: autonomous-orchestrator/v2
role_skill: $universal-subtask-worker
followup_mode: delta_only
base_task_file: C:\repo\.orchestrator\tasks\TASK-R2-BILLING-03\TASK-R2-BILLING-03.task.txt
followup_to: TASK-R2-BILLING-03
task_kind: implementation-followup
task_code: TASK-R2-BILLING-03
task_fingerprint: billing-export|csv-proof|app/exporters/billing.py
attempt: 2
previous_result_file: C:\repo\.orchestrator\tasks\TASK-R2-BILLING-03\RESULT.txt
result_file: C:\repo\.orchestrator\tasks\TASK-R2-BILLING-03\RESULT-01.txt
return_message: Reply with the absolute result_file path only.
changed_fields:
- why_rejected
- do_work
- checks_to_run
- acceptance_for_parent

why_rejected:
- Exact rejection reason.

do_work:
- Exact missing correction or missing proof.

checks_to_run:
- Updated targeted checks only.

acceptance_for_parent:
- What must now be true for acceptance.

delegation_inside_task:
- No. NO_VALID_SUBAGENT_SPLIT.
```

Delta-only rules:

- unchanged `product_target`, `read_context_files`, `write_scope`, `do_not_touch`, and `delegation_inside_task` are inherited from `base_task_file`;
- do not restate unchanged fields just because they existed in the original task;
- if more than half of the task would need to be repeated or the write scope broadens materially, stop using same-agent follow-ups and create a replacement task instead.

If the same child is no longer useful, close it and create a new task folder with a new task code instead of stacking more follow-ups.

## Result File Contract

Every child must write the result file before replying.

Do not paste the full report into chat.
Reply with the absolute result-file path only.

Use a flat machine-oriented format:

```text
protocol_version: autonomous-orchestrator/v2
task_code: TASK-R2-BILLING-03
attempt: 1
role_skill: $universal-subtask-worker
result_status: completed
parent_action_hint: accept
source_task_file: C:\repo\.orchestrator\tasks\TASK-R2-BILLING-03\TASK-R2-BILLING-03.task.txt

summary:
- What was done.

files_changed:
- C:\repo\path\file1.py
- C:\repo\path\file2.ts

checks_run:
- python -m pytest tests/test_export.py -q => passed

check_results:
- Export contract proved by targeted test.

residual_risks:
- Anything still not proven.

handoff_notes:
- Useful facts for the parent or next child.
```

Result economy rules:

- keep each list operational and short;
- list only files actually changed;
- list only checks actually run;
- do not paste long reasoning into the result file;
- the parent accepts or rejects from this schema, not from prose in chat.

For research tasks, use the same envelope but replace the lower blocks with:

```text
findings:
- ...

options_considered:
- ...

recommendation:
- ...

remaining_unknowns:
- ...

needs_user_input: no
```

If user input is still required after research:

```text
needs_user_input: yes
bounded_user_question: <short question>
recommended_option: A
options:
- A: ...
- B: ...
```

## Protocol Breach Handling

If attempt `1` fails the reply gate:

- reject the attempt as `protocol_breach`;
- spend retry budget normally;
- write the next live task as `FOLLOWUP-01.task.txt` or replace the child with a new task code;
- do not claim product success from source-file inspection alone;
- do not accept a legacy markdown result path as the final artifact.

## Runtime Ledger Expectations

`task-ledger.json` should preserve at least these fields per task:

```text
task_code
task_fingerprint
task_kind
role_skill
origin
status
attempt_count
same_agent_followups
task_dir
active_task_file
latest_result_file
write_scope
```

`agent-ledger.json` should preserve at least these fields per child:

```text
agent_id
task_code
role_skill
status
task_file
latest_result_file
integrated
closed
```

Update the ledger before spawn, after result arrival, after integration, and after close.
