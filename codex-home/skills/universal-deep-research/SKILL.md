---
name: universal-deep-research
description: Universal deep research workflow for Codex. Use when the user explicitly invokes `$universal-deep-research`, `universal deep research`, `deep research`, or asks for a thorough investigation of a topic, method, product area, API, standard, competitor, or implementation direction. Use to turn a broad topic into evidence-backed findings, options, tradeoffs, and actionable implementation guidance for any project. Do not use for simple factual lookups, light brainstorming, or narrow code edits that do not require substantial external research.
---

# Purpose

Run a serious research process that ends in a decision-ready implementation memo, not a pile of links.

# Autonomous File Mode

If the input is a single absolute path to `*.task.txt`, treat it as a path-only research task from `autonomous-orchestrator`.

In that mode:

- read the task file first;
- if it is a delta follow-up, read `base_task_file` next and inherit unchanged fields;
- verify that `role_skill` points to `$universal-deep-research`;
- use listed context files plus primary external sources;
- write the answer into the exact `result_file`;
- reply in chat with the exact absolute `result_file` path only when the task contract says so.

Do not paste the research memo into chat in autonomous file mode.
Do not ask the user direct clarification questions from the child thread.
If user input is still required after research, encode that in the result file for the parent to escalate.

This skill is for questions like:

- "What is the right architecture for X in this project?"
- "How should we implement Y given the current ecosystem?"
- "What are the best approaches, tradeoffs, and risks here?"
- "What changed recently in this area and what should we adopt?"

The output should help the user decide what to build, what to avoid, and how to phase the work.

# Research Posture

1. Start from the decision, not from the search engine.
2. Prefer primary sources when technical correctness matters.
3. Separate evidence from inference.
4. Track uncertainty explicitly.
5. Synthesize aggressively. Do not dump raw search results.
6. End with implementation implications, not just summary.

# When To Use

Use this skill for:

- technical architecture research;
- library, framework, or API evaluation;
- standards, policy, or compliance research that affects implementation;
- product and competitor research tied to build decisions;
- method comparison before a major refactor or new feature;
- greenfield exploration when the user needs a strong recommendation.

Do not use this skill for:

- a one-line factual question;
- shallow recommendation lists;
- code-only tasks that can be solved from local context;
- rewriting or editorial cleanup.

# The Deep Research Workflow

## Phase 1. Frame The Decision

Before searching, define:

- the research question;
- the decision to be made;
- the project context;
- hard constraints;
- success criteria;
- what would count as a bad recommendation.

If the user already gave enough context, proceed. If not, ask only the smallest set of questions needed to avoid shallow or risky research.
In autonomous file mode, do not ask the user directly; record the missing decision in the result file instead.

Turn the request into:

- `Decision`
- `Context`
- `Constraints`
- `Evaluation criteria`
- `Open unknowns`

## Phase 2. Build The Research Map

Break the question into subquestions such as:

- what exists now;
- what changed recently;
- which options are credible;
- what the failure modes are;
- what implementation burden each option creates;
- what dependencies, cost, performance, safety, or maintenance tradeoffs exist.

Create a small research plan before diving in. Prefer breadth-first mapping first, then depth where the decision hinges.

## Phase 3. Gather Evidence

For each important claim:

- find the strongest available source;
- note whether it is a primary source, secondary summary, or community report;
- compare conflicting claims instead of averaging them;
- record exact dates when recency matters;
- extract only the details that move the decision.

Use local repository context when available:

- inspect the current stack;
- identify integration points;
- note constraints already visible in the codebase;
- use that context to reject irrelevant options early.

## Phase 4. Use Research Lenses

When the topic is broad or under-defined, push it through these lenses:

### Problem-First vs Solution-First

- What concrete problem is hurting users or developers now?
- Are we chasing a real need or trying to justify a shiny tool?

### Abstraction Ladder

- Move up: what general principle or pattern does this belong to?
- Move down: what is the most constrained real implementation case?
- Move sideways: what adjacent domain already solved a similar problem?

### Tension Hunting

Look for valuable contradictions:

- speed vs correctness;
- control vs convenience;
- local simplicity vs long-term maintainability;
- flexibility vs operational risk.

Good research often comes from making those tensions explicit instead of pretending one option wins on every axis.

### Gap And Novelty Check

Ask:

- what is still missing in the current ecosystem?
- what do teams repeatedly hand-roll?
- what changed recently that invalidates old advice?

## Phase 5. Synthesize

Turn raw evidence into a structure the user can act on:

- key findings;
- option set;
- tradeoff matrix;
- recommendation;
- rejected alternatives;
- implementation implications;
- remaining unknowns.

Do not present five options as if they are equally good when the evidence clearly narrows the field.

## Phase 6. Convert Research Into Implementation Guidance

The final output must answer:

- what should we do now;
- why this path beats the alternatives;
- what to build first;
- what to defer;
- what risks to validate early;
- what experiments or spikes would reduce uncertainty fastest.

When a repo is available, tie the recommendation to the actual project:

- likely modules or boundaries affected;
- migration shape;
- testing implications;
- rollout order;
- operational or maintenance impact.

# Required Output Shape

Default final structure:

```text
Research question
- ...

Decision to make
- ...

Context and constraints
- ...

What I investigated
- ...

Key findings
- ...

Options considered
- ...

Recommendation
- ...

Why
- ...

Implementation implications
- ...

Risks and unknowns
- ...

Next steps
- ...
```

If the user explicitly wants more detail, add:

- source map;
- chronology;
- deeper comparison tables;
- open questions for follow-up research.

In autonomous file mode, place the findings into the machine-oriented result envelope expected by `autonomous-orchestrator`, for example:

```text
protocol_version: autonomous-orchestrator/v2
task_code: TASK-...
attempt: 1
role_skill: $universal-deep-research
result_status: completed
parent_action_hint: accept
source_task_file: C:\repo\.orchestrator\tasks\...\TASK-....task.txt

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

If user input is still required, keep the chat reply path-only and put the blocker into the result file:

```text
needs_user_input: yes
bounded_user_question: ...
recommended_option: A
options:
- A: ...
- B: ...
```

# Response Style

- Be evidence-first.
- Prefer primary sources for technical questions.
- Distinguish clearly between facts and your inference.
- Name dates when "latest" matters.
- Keep the top-level answer readable, then add the deeper supporting detail.
- Avoid bloated "comprehensive" summaries that never commit to a recommendation.

# Quality Bar

Before finishing, check:

- Did I define the decision before researching?
- Did I use the freshest relevant sources?
- Did I separate facts from inference?
- Did I identify real tradeoffs instead of generic pros and cons?
- Did I end with implementation guidance, not only a literature review?
- If a repo exists, did I connect the research back to the actual project?
