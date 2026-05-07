# Agentic Build System First Principles

Status: binding product and architecture direction.

This skill-owned reference records the operator course correction for the PoE
build agent. It is packaged into the skill bundle so the product agent does not
need the development repository as its runtime instruction source.

## Core Thesis

The product is not a hidden script that generates PoE builds. The product is an
agentic PoB laboratory where the LLM reasons about build value and skill-owned
tools force proof, comparison, memory, and safe publication.

The operating formula is:

```text
Agent proposes -> Tools execute -> PoB measures -> Ledger remembers -> Scorer judges -> Reporter explains
```

Code must hardcode the scientific method, not PoE build choices. It may enforce
schemas, budgets, evidence, route costs, trial counts, freshness, and output
gates. It must not secretly choose the final class, ascendancy, tree, item plan,
support setup, config state, loadout ladder, final build, or publication payload.

## Non-Negotiable Boundaries

- Pinned Path of Building is the authoritative calculator.
- The LLM owns build hypotheses, branch choices, rejected reasons, repair
  choices, tradeoff interpretation, and publication requests.
- Tools own bounded execution: inspect, mutate, import, export, evaluate, diff,
  validate, cache, write ledgers, and submit only after proof.
- A wrapper, helper, materializer, fixture, public profile, guide, or script may
  provide evidence, serialization, benchmark state, or read-back. It must not be
  final build authority for a created build.
- A successful product answer cannot be a mini guide, plausible shell, status
  string, screenshot, locator list, raw package row, or first valid import. It
  must be the accepted artifact surface backed by PoB evidence.
- A failed edit, failed tool call, rejected branch, or bad first tree is not a
  stopping condition. Stop only when the trial budget is exhausted, every safe
  next action is accounted for, or a precise blocker is proven.
- Every reusable lesson must be external memory with evidence and scope. Chat
  memory is not project memory.

## Required System Components

The durable architecture is a set of small, proof-oriented components:

- PoB wrapper:
  import/export, inspect, mutate, evaluate, diff, calc snapshot, native import
  verifier, and final submit guard.
- Trial runner:
  applies one explicit hypothesis/action to a copy of state, runs PoB, records
  before/after, verdict, blockers, and safe next actions.
- Experiment ledger:
  append-only record of hypotheses, actions, observations, before/after metrics,
  rejected branches, champion/challenger decisions, blockers, and lessons.
- Choice Valuation Engine:
  prices every material decision by scarce resources, measured value, rejected
  alternatives, opportunity cost, and transition friction.
- Scorer/comparator:
  enforces hard constraints, Pareto comparisons, objective profiles, and
  dominated-option rejection. It does not replace PoB or select a hidden build.
- Frontier manager:
  keeps multiple live branches instead of one greedy `current_best`.
- Evidence providers:
  trade, craft, public-build, research, wiki, and mechanics sources provide
  provenance-backed priors or cost evidence, never final created-build proof.
- Memory promotion:
  turns raw trials into compact experience, warnings, Pattern Cards, negative
  findings, Build Layer candidates, skill updates, and evals only through review.
- Reporter/output gate:
  emits only accepted surfaces and only after required proof refs exist.

## Required Artifact Shape

Future schemas may refine names, but each real build run must preserve these
conceptual records:

- `BuildState`: PoB ref, state hash/version, class, ascendancy, level, tree,
  items, skills, config, tags, and separated baseline/conditional metrics.
- `Metrics`: DPS, skill DPS, EHP, max hit, Life/ES/Mana, recovery, hit chance,
  resistances, suppression/block, reservation, mana cost, speed, AoE, ailment
  status, cost posture, warnings, and blockers.
- `Hypothesis`: goal, rationale, expected mechanism, actions, expected upside,
  risks, alternatives considered, stop condition, and applicability boundary.
- `Action`: mutation type, target surface, payload, resource cost, expected
  affected surfaces, input observation refs, and output/read-back expectation.
- `Trial`: before state, action/hypothesis refs, after state, calc/metrics diff,
  verdict, rejected alternatives, blocker or safe next action, and evidence refs.
- `Candidate`: build state ref, objective profile, score summary, constraint
  status, frontier role, provenance, and publication readiness state.
- `Evidence`: source type, authority role, freshness, version/league/patch scope,
  confidence, applies-to boundary, refs, and invalidation rules.

Prose may summarize these records. Prose must not replace them.

## Mandatory Build Loop

Every Direct Build, BuildReview, optimization, or loadout-ladder run follows the
same loop, with scope and budgets adjusted to the mode:

1. Intake:
   record user goal, league/economy model, build constraints, budget/loadout,
   missing expert decisions, forbidden sources, and output boundary.
2. Retrieve:
   load relevant accepted memory, compact experiment experience, warnings, and
   known negatives. If relevant experience exists but is missing or stale, block
   or refresh before repeating the same work.
3. Inspect:
   read current PoB state before mutating, comparing, exporting, or submitting.
4. Arithmetic map:
   identify damage/defense/resource buckets, missing constraints, saturated
   buckets, likely marginal stats, and PoB evidence surfaces to read.
5. Hypothesize:
   generate competing hypotheses with alternatives considered and expected
   numeric movement.
6. Estimate and filter:
   compute resource cost, obvious dominance, path/package cost, and shortlist
   only plausible or intentionally exploratory actions.
7. Experiment:
   run bounded PoB mutations or batch trials on copies of state.
8. Observe:
   read back state, metrics, warnings, and Calc deltas from pinned PoB.
9. Compare:
   compare champion/challenger or branch frontier rows with separated baseline
   and conditional lanes.
10. Record:
    write all accepted, rejected, repaired, parked, blocked, and exhausted
    results into the ledger.
11. Decide:
    accept, reject, repair, park, or branch from the measured result and budget.
12. Verify and submit:
    run the required final checks and emit only the accepted output surface, or
    stop with the smallest proven blocker.

## Choice Valuation

The agent's key failure mode is not seeing the price of each action. Every
material action must therefore be turned into a comparable value record:

```text
action -> resource cost -> expected affected surfaces -> pre-PoB estimate
       -> measured PoB/Calc diff -> normalized value -> verdict vs alternatives
```

Resource cost includes, when relevant:

- passive points;
- travel points;
- useful travel credit, such as attribute repair from a connector;
- prefix/suffix pressure;
- item slot and unique slot pressure;
- gem socket and support slot pressure;
- reservation and mana-cost pressure;
- attribute, resistance, accuracy, ailment, and recovery pressure;
- budget, craft difficulty, trade availability, and market freshness;
- transition friction between loadouts;
- config dependency and uptime assumptions;
- opportunity cost of nearby rejected choices.

Passive tree decisions must be priced as packages, not isolated nodes:

```text
target notable/mastery/cluster + connector nodes + travel nodes + side benefits
```

A high raw-value target behind five weak travel nodes can lose to two medium
nearby targets that cost fewer points or repair attributes. A tree choice must
record the selected package, package cost, rejected local alternatives, and the
PoB read-back check.

## Evaluation Ladder

The project should not waste PoB trials on obvious dominated choices, but it
must measure uncertain choices:

1. Dominance filter:
   reject same-stat same-cost choices where one option plainly dominates.
2. Static estimate:
   parse known stats, expected affected surfaces, route cost, and constraints.
3. Cheap probe:
   batch apply many candidate actions and read key metrics.
4. Full Calc diff:
   snapshot before/after Calc surfaces and classify normalized deltas.
5. Contextual validation:
   attach market, craft, research, transition, freshness, and operator evidence.

This ladder is generic. It does not encode "take this passive for this skill";
it encodes how to decide whether any proposed action earned its cost.

## Calc Evidence

Calc snapshots are telemetry for all build surfaces, not just DPS.

Every material trial should preserve before/after metric rows or a precise
unavailable reason. Deltas should be classified into effects such as:

- `constraint_repair`;
- `dps_gain`;
- `defense_gain`;
- `mana_pressure`;
- `reservation_pressure`;
- `attribute_pressure`;
- `resistance_pressure`;
- `accuracy_repair`;
- `aoe_qol_gain`;
- `speed_qol_gain`;
- `suspicious_tradeoff`;
- `config_dependency`;
- `invalid_state`.

Calc telemetry is not the whole truth. Trade price, craftability, public-source
evidence, real uptime, shotgun behavior, and league freshness remain separate
evidence providers.

## Search Model

The search model is frontier/beam/local search plus LLM hypothesis generation,
not one greedy current build.

Useful frontier roles include:

- best valid DPS;
- best valid defense;
- best budget branch;
- best transition candidate;
- weird high-ceiling candidate;
- high-ceiling but unfinished branch;
- repair-focused branch for the weakest hard constraint.

The system keeps branch diversity while the budget allows it. It accepts a
branch when it improves the objective without breaking hard constraints, keeps
it when it improves one important axis or opens a plausible new route, rejects
it when dominated or invalid, and blocks only with precise missing proof.

Novelty comes from allowing unusual hypotheses while forcing measurement. It
does not come from removing all rails.

## Subagent Model

The intended product work shape is:

```text
PoE Architect = strategy
Worker harness/controller = discipline and integration
Workers = laboratory
PoB = calculator
Ledger = memory
```

Workers must return artifacts, not loose prose:

- PoB Trial Worker:
  trial batch, observations, best/worst trial refs, blockers, and safe next
  actions.
- Trade Evaluator:
  market evidence, availability, price range, freshness, and applicability.
- Craft Evaluator:
  craft path evidence, expected cost, variance, blockers, and league scope.
- Researcher:
  provenance-backed fact pack with confidence and open contradictions.
- Reviewer/Verifier:
  missing proof, regression, import/read-back validation, and output checks.

Parallelize independent batches such as support swaps, item replacements,
config variants, market checks, craft paths, and research packs. Do not claim
parallel speedup for dependent decisions where the next action depends on the
previous PoB observation.

## Performance Requirements

The architecture must be designed for many trials:

- persistent PoB process where feasible;
- batch trial API;
- build-hash and action-hash cache;
- bounded action spaces per pass;
- frontier state instead of one mutable best build;
- compact context packets for new threads;
- evidence packets instead of whole-ledger rereads;
- explicit wall-clock, tool-call, and trial budgets.

A new thread should start from a compact packet: build brief, constraints,
current frontier, latest metrics, accepted memory, known negatives, open
questions, next recommended pass, and submit boundary.

## Product Roadmap Shape

The product should scale by reusing the same proof loop, not by inventing a new
agent for every mode.

Suggested product phases:

1. Contract stabilization:
   product brief, first-principles, artifact schemas, no-prose/no-hidden-engine
   gates.
2. PoB execution substrate:
   inspect/evaluate/apply/diff/calc snapshot/native verifier/submit guard,
   persistent runtime, batch evaluation, cache, and read-back verification.
3. Trial ledger:
   real before/after trials, all rejected branches, blockers, and evidence refs.
4. Choice valuation:
   resource-cost records, tree package costing, static estimate, dominance
   filter, Calc delta classifier, and multi-objective comparator.
5. First vertical proof:
   BuildReview is the simplest proof slice because it starts from an existing
   PoB and can run 20-50 bounded improvements. In this repo's current accepted
   MVP, the active proof target is Early Game Direct Build; BuildReview work is
   useful only if it advances the same measured hypothesis/action/PoB/ledger
   loop and does not replace the accepted Early Game goal.
6. Frontier optimization:
   multiple live candidates, Pareto/frontier roles, pass scheduler, champion
   versus challenger, and branch diversity.
7. Early Game Direct Build:
   one level 90 PoB-backed loadout from a simple ask, with tree/gem/gear/config
   passes, no external sourcing in the MVP path, and final wrapper read-back.
8. Evidence providers:
   trade, craft, poe.ninja, public-build, and research wrappers as evidence
   providers with freshness and provenance.
9. Loadout ladder:
   Early/Mid/End/Giga stages with transition edges, cost, respec, item churn,
   socket/link churn, and power gain.
10. Learning system:
    raw ledger to run summary to compact experience cards to reviewed Pattern
    Cards, negative memory, Build Layer candidates, warnings, skill updates, and
    evals.
11. Product hardening:
    e2e scenarios, readiness evals, failure traps, stale-market tests,
    impossible-item/craft blockers, and reviewer/verifier passes.

## Memory And Learning

The system learns through external memory and distillation:

- Raw Ledger:
  full trial/audit history, not read wholesale by future agents.
- Run Summary:
  compact 1-3 page explanation of what was tried and what changed.
- Experiment Experience:
  compact, tagged PoB experiment cards loaded before similar future decisions.
- Pattern Cards:
  reusable positive findings with required conditions, good/bad contexts,
  budget/loadout scope, evidence refs, confidence, patch, and reverify rules.
- Negative Memory:
  expensive dead ends and failed routes with changed-condition requirements for
  retry.
- Market/Craft Memory:
  short-lived evidence with freshness and league scope.

Memory freshness rules:

- mechanic interactions reverify each patch;
- trade price reverify quickly;
- craft estimates reverify per league/economy;
- tree/gem scaling reverify after balance or PoB data changes;
- public-build patterns remain priors until PoB comparison proves them.

After a serious run, the architect or harness must ask what became reusable,
what confirmed or invalidated old memory, what should become a warning/eval, and
what was build-specific noise that should not be promoted.

## Acceptance Gates

An MVP or product-ready claim is invalid if it relies on contracts alone,
helper slices, prose, screenshots, or a single happy fixture.

A BuildReview proof slice is not accepted until:

- at least 20 real trials are run, unless a smaller explicit trial budget is
  operator-approved for a narrow test;
- each accepted fix has PoB before/after metrics;
- each accepted fix has resource cost and alternatives considered;
- each tree recommendation has package cost;
- rejected fixes are recorded with reasons;
- the final report cites trial/evidence ids;
- the ledger is reusable by a new thread.

The current Early Game Direct Build MVP is not accepted until:

- a simple ordinary ask is converted into one level 90 Early Game PoB;
- the agent authors the class/skill/tree/gear/config decisions through the
  accepted action-observation loop;
- meaningful alternatives are compared instead of publishing the first plausible
  import;
- the final PoB import is verified, delivered through the accepted surface, and
  approved by the operator after real import into Path of Building;
- the run leaves reusable ledger, choice-cost, arithmetic-map, and memory
  candidates behind.

Broader product readiness also requires:

- BuildReview without full rebuild;
- frontier optimization over multiple hours/trials;
- trade, craft, public-build, and research evidence providers;
- loadout ladders with transition friction;
- pattern/negative memory promotion and retrieval;
- stale knowledge reverification;
- readiness evals that catch lazy, prose-only, first-plausible, and
  source-copy behavior.

## Development Priority

Roadmap priority must follow user-visible product proof:

1. Make the agent inspect, mutate, observe, compare, record, repair, and submit
   through PoB.
2. Make the agent understand action cost through choice valuation.
3. Make the agent remember prior trials through compact external memory.
4. Then widen into trade/craft/research, Build Layers, loadout ladders, and
   novelty search.

Convenience work, wording hardening, helper proliferation, and guard-only waves
are not progress when the measured PoB loop still fails the ordinary user ask.
