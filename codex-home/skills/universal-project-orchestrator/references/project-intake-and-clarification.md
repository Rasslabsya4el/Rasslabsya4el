# Project Intake And Clarification

Read this before creating or rewriting `PRODUCT_BRIEF`, `PRODUCT_SPEC`, roadmap, or the first dispatch batch.

This reference exists to stop drift.
Use repo context aggressively, but do not pretend repo context answers product questions that are still ambiguous.

## Goal

Lock a decision-stable product contract before planning or dispatch.

`Decision-stable` means the remaining unknowns would no longer change one of these:

- `PRODUCT_BRIEF` scope;
- `PRODUCT_SPEC` user-visible behavior;
- roadmap phases or task inventory;
- acceptance criteria for the next batch;
- MVP proof scenario.

If those things would still change, the intake is not done yet.

## Product Contract Fitness Gate

Before any roadmap, task queue, dispatch, or acceptance work, classify the tracked product contract.

Good product docs exist only when `PRODUCT_BRIEF` or `PRODUCT_SPEC` clearly answers all decision-changing fields below:

- product type: what is being built, not just a vibe or asset request;
- primary user: who must succeed first;
- core job: the one before/after outcome the product must create;
- first surface: web UI, API, CLI, automation, data pipeline, content artifact, or another explicit surface;
- critical inputs: what the user/system provides in the MVP path;
- critical outputs: what the product must produce or change;
- MVP proof: the demo, behavior, artifact, or measurable result that proves v1 works;
- non-goals: what must not be built or changed in v1;
- constraints: stack, deployment, budget, privacy, auth, data, performance, style, deadline, or operational limits that would change planning;
- acceptance boundary: what would let the orchestrator reject a worker result as off-target.

If any missing field would change roadmap shape, task inventory, acceptance, or MVP proof, the docs are not good enough.
Stop dispatch and ask a bounded question pack.

Do not treat a short creative request as a product contract.
For example, `make an HTML landing page with horses` is not enough unless the existing repo docs already define audience, goal, conversion action, content constraints, style boundaries, and done proof.
The orchestrator must clarify before creating the roadmap or task files.

## Contract Quality Classification

Use this classification every time before planning or dispatch:

- `READY`: docs answer the fitness gate, and current user request does not change product direction. Proceed without questions.
- `PATCHABLE_FROM_REPO`: docs have small gaps that repo code, existing docs, or primary-source research can fill without guessing product intent. Patch docs first, then proceed.
- `BLOCKED_ON_PRODUCT_CONTRACT`: docs miss product-visible decisions. Ask the user bounded questions before roadmap or dispatch.
- `BLOCKED_ON_IMPLEMENTATION_DECISION`: product is clear, but an implementation choice changes cost, durability, security, hosting, data ownership, or future migration enough that guessing would be risky. Ask a bounded implementation decision pack.

Do not proceed to worker task files while status is `BLOCKED_ON_PRODUCT_CONTRACT` or `BLOCKED_ON_IMPLEMENTATION_DECISION`.

## When Clarification Is Mandatory

Run a clarification pass when any of these are true:

- the repo is empty or nearly empty from a product-definition standpoint;
- `PRODUCT_BRIEF` or `PRODUCT_SPEC` is missing, stale, contradictory, or too vague to drive acceptance;
- the user request introduces a new MVP, a new feature family, a redesign, a major bugfix contract, or a scope change;
- the request is metaphorical, compressed, or slogan-like;
- more than one materially different product interpretation still fits the current context;
- the roadmap would branch differently depending on the missing answer;
- acceptance for the next task cannot be written without guessing user-visible behavior.
- the current request gives only an artifact label, aesthetic direction, or implementation noun without target user, job, success proof, and non-goals;
- the docs cannot explain why the next task matters for the final product in one plain-language sentence.

Do not skip this pass just because some code already exists.

## When Clarification Is Not Needed

Do not ask the user if all missing information is only about:

- implementation technique;
- library or tool choice;
- validation method;
- internal architecture;
- file layout;
- researchable ecosystem facts.

Close those gaps via repo inspection or research first.

Exception: if an implementation choice would materially change product operations, data durability, cost, privacy, compliance, deployment, scale assumptions, or migration risk, treat it as `BLOCKED_ON_IMPLEMENTATION_DECISION` unless the repo/docs already choose it.

Examples that may require a bounded implementation decision pack:

- database: Postgres vs SQLite vs no database;
- auth: no auth, password login, OAuth, magic links;
- hosting: static local app, single VPS, managed platform, serverless;
- data storage: browser local storage, server DB, files, third-party API;
- payment provider, email provider, analytics provider, or queue system;
- destructive migrations or stack changes in an existing repo.

## Question-Pack Rules

Ask the smallest useful pack, not a giant interview.

Rules:

- ask only questions whose answers would change the product contract, roadmap, or acceptance;
- every question must have explicit answer options;
- put the recommended option first;
- ground the options in the current repo context and the user's wording;
- keep one round usually between `1` and `7` questions;
- do not mix unrelated decisions into one question;
- avoid free-form prompts like `how should it work?`;
- if the user answer reveals a new ambiguity, ask one more bounded pack instead of inventing;
- stop once the contract is decision-stable.
- include short examples inside answer options when the user request is vague, creative, or domain-light;
- make the recommended option concrete enough that the user can answer by letter only;
- never ask `what do you want?` when you can ask `which of these product shapes is correct?`.

If the user picks `Other`, restate it back into the canonical docs in structured form. Ask a follow-up pack only if that new answer still leaves decision-changing ambiguity.

Every question pack must explicitly say why the questions block planning in one short sentence.
Example: `Без этого орк не сможет отличить красивую страницу от страницы, которая реально продаёт нужный продукт.`

## Order By Information Gain

Prefer this order. Stop early when the contract becomes stable.

1. Request class
2. Primary user or operator
3. Core job to be done
4. MVP proof scenario
5. Surface and I/O shape
6. Constraints and non-goals
7. Priority or severity
8. Integrations, data, auth, or compliance only if they change the first delivery
9. Implementation decisions that create long-lived product or infrastructure commitments

## Question Types

### 1. Request Class

Use this first when the ask can mean different work modes.

Ask:

- is this a new MVP;
- a new feature in an existing product;
- a bugfix to expected behavior;
- a redesign without behavior change;
- a research-only decision before build.

### 2. Primary User

Ask who must succeed first in MVP terms, not every possible stakeholder.

Bad:

- who are all stakeholders.

Good:

- who must be able to complete the critical flow first.

### 3. Core Job To Be Done

Ask for the single most important before/after outcome.

Bad:

- what features should it have.

Good:

- which concrete user action must work end to end.

### 4. MVP Proof Scenario

Ask how the project will be judged as "good enough for MVP".

Typical proof options:

- one successful demo flow;
- one production-safe flow for internal users;
- one externally usable flow for first real users;
- one bug no longer reproducible with proof;
- one measurable artifact or output contract.

### 5. Surface And I/O

Ask only the surface that changes the first roadmap:

- web UI;
- API/backend only;
- CLI/tooling;
- automation/internal ops;
- data pipeline;
- mixed surface.

Then ask only the minimal input/output questions that define the critical path.

### 6. Constraints And Non-Goals

Force the first boundaries early.

Examples:

- desktop only vs mobile-first;
- manual auth later vs auth now;
- no payments in MVP;
- no multi-user permissions in MVP;
- speed first vs pixel polish first;
- use existing stack vs stack may change.

### 7. Priority Or Severity

When the ask is a change to an existing repo, ask what matters most:

- must-ship now;
- must stop a broken path;
- important but not release-blocking;
- exploration before commitment.

### 8. Long-Lived Implementation Decisions

Ask only when the decision is hard to reverse or changes roadmap/acceptance.

Bad:

- какую базу использовать?

Good:

- где должны жить данные MVP?
  - A: Postgres, because we need server-side durable multi-user data from day one.
  - B: SQLite/file storage, because this is local or single-user first.
  - C: Browser/local-only storage, because MVP only needs a demo without backend data durability.

Common decision packs:

- data durability: no persistence, browser storage, files, SQLite, Postgres, managed DB;
- users/auth: no auth, single admin secret, password login, OAuth/magic link;
- deployment: local-only, static hosting, single server, managed app platform, serverless;
- external services: none in MVP, mocked adapter, real provider now;
- scale: demo-only, internal team, first real users, public launch.

When asking implementation questions, phrase them through product consequences, not technology preference.
Do not ask the user to choose Postgres because of taste; ask whether MVP needs durable server-side multi-user data.

## Repo-Grounded Option Construction

Before asking, inspect the repo and existing docs. Then build options that reflect real nearby context.

Rules:

- if the repo already implies a likely stack or surface, include that as the recommended option instead of asking abstractly;
- if the user language implies one likely interpretation, make that option first;
- if there are only two serious interpretations, give only two or three options, not five;
- never fabricate exotic options just to look comprehensive.

## Mapping Answers Back Into Docs

Once the pack is answered:

- update `PRODUCT_BRIEF` with the chosen target user, outcome, scope, and MVP proof;
- update `PRODUCT_SPEC` only for user-visible behavior that needs extra precision;
- update roadmap phases and task inventory to match the chosen contract;
- update task queue only after the contract changes are written down.

Do not keep critical answers only in chat memory.

## Recommended Packs

### New MVP Or Empty Repo

Ask only the smallest pack that defines the first product contract:

1. Which kind of first product are we building?
2. Who must use it first?
3. What single flow must work in MVP?
4. What proves MVP is real?
5. What is explicitly out of scope for v1?

Use options with examples. For a vague landing-page request, ask things like:

1. What is the page trying to do?
2. Who should the page convince?
3. What action should the visitor take?
4. What content/style is required vs forbidden?
5. What proves the page is done?

### New Feature In Existing Product

Ask:

1. Which existing user or operator is this for?
2. What new action becomes possible?
3. What current surface should own it?
4. What is the smallest acceptable proof?
5. What must not be changed by this feature?

Also ask a long-lived implementation decision pack if the feature adds data storage, auth, payments, background jobs, external APIs, or irreversible schema changes and the docs do not already choose the approach.

### Bugfix

Ask:

1. Which current behavior is wrong?
2. What behavior is expected instead?
3. How severe is it for release or users?
4. What proof would convince us the bug is actually fixed?

### Redesign Or Refactor

Ask:

1. Is user-visible behavior allowed to change?
2. What pain is the redesign solving?
3. What contract must stay stable?
4. What proof would show success?

## Output Shape For User Questions

Ask in option-pack form, not open prose.

Use this shape:

```text
Нужно уточнить продуктовый контракт перед роудмепом.
Почему стопор: <one sentence about what would drift if we guess>.

1. <question>
- A (Recommended): ...
- B: ...
- C: ...

2. <question>
- A (Recommended): ...
- B: ...
```

If a later round is needed, ask only the unresolved questions.

For implementation-decision blocks, use this shape:

```text
Нужно уточнить техническое решение, потому что оно меняет роудмеп и цену ошибки.
Почему стопор: <one sentence about durability/cost/security/migration risk>.

1. <question through product consequence>
- A (Recommended): ...
- B: ...
- C: ...
```

Do not create task files in the same reply as a blocking question pack.

## Stop Rule

Do not keep interviewing for completeness theater.

Stop and proceed when:

- the next roadmap can be written without guessing;
- the next task batch can be tied to explicit product outcomes;
- the MVP proof scenario is concrete enough to reject drift;
- remaining unknowns are implementation or research questions rather than product-definition questions.
