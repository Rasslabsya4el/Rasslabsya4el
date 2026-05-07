# Control-Plane Bootstrap

Use this before roadmap, task queue, dispatch, acceptance, resync, or first project work in any repo.

The orchestrator owns control-plane bootstrap. Do not delegate missing project docs to a worker.

## Required Files

Every orchestrated repo should have this tracked control-plane set:

```text
AGENTS.md
docs/project/PRODUCT_BRIEF.md
docs/project/CURRENT_STATE.md
docs/project/DECISION_LOG.md
docs/project/PRODUCT_SPEC.md
docs/roadmap.md
docs/task-queue.md
docs/validation-log.md
```

`PRODUCT_SPEC.md` may stay brief if `PRODUCT_BRIEF.md` is enough, but the file should exist so future behavior detail has a canonical home.

## Template Sources

Use these templates from the main readme repo:

```text
C:\Coding\Main readme repo\AGENTS_TEMPLATE.md
C:\Coding\Main readme repo\project-doc-templates\docs\project\PRODUCT_BRIEF.md
C:\Coding\Main readme repo\project-doc-templates\docs\project\CURRENT_STATE.md
C:\Coding\Main readme repo\project-doc-templates\docs\project\DECISION_LOG.md
C:\Coding\Main readme repo\project-doc-templates\docs\project\PRODUCT_SPEC.md
C:\Coding\Main readme repo\project-doc-templates\docs\roadmap.md
C:\Coding\Main readme repo\project-doc-templates\docs\task-queue.md
C:\Coding\Main readme repo\project-doc-templates\docs\validation-log.md
```

## Bootstrap Algorithm

1. Check whether each required file exists.
2. If a file is missing, copy the matching template structure into the target repo.
3. Adapt placeholders from known repo/user context only:
   - project name;
   - current user request;
   - existing README/spec/package/app clues;
   - already tracked decisions.
4. If the product contract is still unknown, write `UNKNOWN` / `BLOCKED_ON_USER_PRODUCT_CONTRACT` in the relevant fields instead of inventing.
5. Run the Product Contract Fitness Gate after the files exist.
6. If decision-changing fields are still unknown, ask bounded option questions before creating implementation task files.

## Do Not

- Do not create a worker task whose purpose is only “bootstrap product docs”.
- Do not let a worker invent product source of truth.
- Do not dispatch implementation before required files exist or are honestly marked blocked.
- Do not leave template placeholders like `...` or empty headings when the answer is known from repo/user context.
- Do not pretend placeholders are real product decisions.

## User-Facing Summary

When bootstrap creates or repairs docs, explain it in human terms without listing every file unless the user asks for file audit.

Good:

```text
Я сначала создал проектную память: что строим, для кого, какой MVP считаем доказанным и какие вопросы ещё открыты.
Контракт продукта пока неполный, поэтому перед задачами нужно выбрать первый рабочий сценарий.
```

Bad:

```text
Updated:
- docs/project/PRODUCT_BRIEF.md
- docs/project/CURRENT_STATE.md
- docs/roadmap.md
```

