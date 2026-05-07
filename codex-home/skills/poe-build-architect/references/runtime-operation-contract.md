# Build Architect Runtime Operation Contract

Status: skill-owned runtime rule.

This file turns the first-principles architecture into the concrete operating
protocol for product PoE Build Architect work. It is runtime content and must
stay packaged inside the installed skill.

## Runtime Source Boundary

Use this skill bundle, sibling installed PoE skills, and explicit versioned
external dependencies. Do not read the development repo as product memory. If a
needed script, schema, template, memory packet, or PoB dependency is missing
from the installed skill/runtime, stop with the smallest missing dependency.

The in-app browser can be used for manual inspection or accepted web evidence
tasks. It is not the primary PoB runtime lane. The primary PoB lane is
skill-owned headless/live-control/native import verification.

## Required Run Shape

Every Direct Build, branch comparison, or review-coordination run must produce
or request artifacts in this order:

1. Intake packet:
   user goal, league/economy, budget/loadout, output surface, hard constraints,
   missing decisions, and forbidden sources.
2. Baseline observation:
   imported or blank PoB state, separated baseline/conditional metrics, current
   blockers, and the exact PoB/runtime version.
3. Arithmetic map:
   damage buckets, defense/resource buckets, constraint pressure, saturated
   stats, and expected affected Calc surfaces.
4. Hypothesis set:
   competing hypotheses with rationale, expected upside, risks, alternatives
   considered, resource-cost estimate, and stop condition.
5. Trial batch:
   bounded mutations applied to copies of state, before/after metrics, Calc
   deltas, rejected alternatives, blockers, and safe next actions.
6. Choice valuation:
   normalized value against scarce resources such as passive points, travel
   points, affix slots, gem slots, reservation, mana, attributes, accuracy,
   resistances, budget, craft difficulty, trade availability, and transition
   friction.
7. Ledger entry:
   accepted, rejected, repaired, parked, blocked, and exhausted outcomes with
   evidence refs.
8. Publication gate:
   final read-back, native import verification when a PoB import is delivered,
   no unsupported claims, and accepted report surface only.

Direct Build artifact publication must pass through the packaged
producer/materializer contract in `references/direct-build-producer-materializer.md`.
The producer validates the agent-authored decision ledger and source payloads;
the materializer applies those payloads to PoB and verifies the exact import
payload. Neither stage may invent build choices to fill missing agent decisions.
When materialization blocks, run the packaged Direct Build repair packet builder
and use its `repair_items` as mandatory next-attempt requirements. A blocked
materialization with `next_attempt_required=true` is not a valid stop condition.

When this skill is used for product-agent behavioral validation, the spawned PoE
Build Architect must author the requested decision ledger or precise blocker
itself. A ledger authored by the engineering/orchestrator thread, a script
fixture, or a main-thread repair is only development/regression evidence. Do not
return a behavioral-proof claim when the task only asks you to verify an
existing engineering-authored ledger.

Prose may explain these artifacts. Prose must not replace them.

## Action Cost/Value Ledger

Before claiming that a material tree, skill, item, or config action is better
than its alternatives, create or update the skill-owned Action Cost/Value Ledger
described in `references/action-cost-value-ledger.md`.

The ledger is the first comparison surface. It must preserve the selected
action, rejected alternatives, resource cost, expected affected surfaces,
evidence refs, missing evidence, and verdict reason. The CV1 utility can produce
the MVP tree/pathing report without running a new Direct Build proof:

```text
python -m poe_build_research.pob.action_cost_value_ledger produce --ledger <ledger.json> --output-dir <dir>
```

This utility does not choose final build changes, does not run a PoB optimizer,
and does not replace measured PoB evidence. It fail-closes comparison records
that lack cost, alternatives, or evidence accounting.

## Cost-Aware Direct Build Integration

For Cost-Aware Direct Build MVP, the product agent must author Direct Build
decision rows with compact refs to the CV1-CV6 artifacts that justified the
choice. The Direct Build producer/materializer preserves these refs; it does
not generate the missing decisions for the agent.

Cost-aware ledgers must carry, where applicable:

- `pre_pob_hypothesis_triage_refs` from Pre-PoB Hypothesis Triage;
- `comparison_protocol_refs` from Comparison Protocol;
- `action_cost_value_ledger_refs` from Action Cost/Value Ledger;
- `calc_snapshot_diff_refs` for measured claims;
- `pathing_opportunity_cost_refs` for tree/pathing decisions;
- `surface_impact_classification_refs` for compact impact categories.

An accepted cost-aware material decision row cannot omit the Action Cost/Value
Ledger or Comparison Protocol refs. A cost-aware tree/pathing row cannot omit
Pathing Opportunity Cost refs. A measured claim cannot omit Calc Snapshot Diff
evidence. Missing refs block or make the output partial; they are never treated
as accepted cost-aware proof by prose.

The operator-facing DirectBuildOutput includes only a compact cost/value
summary. Full debug packets stay internal unless Debug Mode or Trace Sampling
Mode is explicitly requested.

## Direct Build Minimum Bar

The Direct Build source gate splits Early Game loadout/stage rails from
universal PoB authoring evidence. Old exact Early Game loadout rails were not
fully recovered from migration; this runtime reconstructs the missing policy
inside the installed skill rather than relying on repo docs.

For Early Game Direct Build MVP loadout/stage rails:

- level 90 target;
- rare-only baseline gear shell with accepted Early Game loadout rail metadata,
  policy/base-catalog evidence, and operator-declared mod tier limits;
- no uniques;
- at most three explicit affixes per rare item;
- affix and base tiers must be no better than T3 unless the operator changes
  the lane;
- flat accuracy may appear on at most one item total;
- item bases must resolve to the packaged item base corpus
  (`corpus_data/items.json`) and cannot fabricate implicits;
- item publication needs structured proof items with `base_id`/`base_name`,
  catalog-backed implicits, affix id, tier, value, and source/catalog refs. Raw
  self-authored item text alone is not accepted as Early Game item evidence;
- explicit rare affix ids, tiers, and value ranges must resolve to the
  skill-owned Early Game proof-item mod catalog
  (`mod_data/early_game_proof_item_mods.json`). The MVP catalog is a versioned
  PoEDB `ModsView` snapshot with source URLs, fetch timestamps, source hashes,
  and parser version for the selected Early Game item classes;
- affixes must be valid for the selected item class/base, tiers must be real
  catalog tiers, and values must sit inside the selected tier range. A T1/T2
  value labelled as weaker tier blocks publication;
- self-declared T3/early-game items still fail if structured affix values behave
  like T1/high-power rolls;
- Early Game resistance-fixing rings should use Two-Stone Ring bases, or carry
  explicit base-choice justification;
- item source-quality/loadout metadata must remain available to producer rails
  and reports, but must not be sent into the PoB item apply call as unsupported
  runtime item fields;
- budget arithmetic must be bounded and internally consistent; manual estimates
  require evidence notes/refs and are not live-market proof by prose;
- 5L main skill unless the user explicitly changes the lane;
- explicit tested hypothesis/archetype in the ledger and DirectBuildOutput;
- Kill All bandits and Guardian/Pinnacle baseline enemy unless the user
  explicitly changes the lane;
- level 90 trees must allocate relevant masteries or justify none with rejected
  mastery alternatives. Mastery proof must be read from actual allocated
  mastery fields, not accepted from `mastery_focus` prose alone. Irrelevant
  mastery pressure such as accuracy on a spell Fireball route must be justified
  by measured constraint evidence;
- every ascendancy notable must have build-relevant value evidence. Champion
  impale/attack ascendancy choices block for a Fireball spell route unless the
  build proves attack/impale relevance;
- Fireball spell tree/pathing packages must declare semantic relevance tags
  such as fire/spell/cast/life/defense/resource/requirement relief. Accuracy or
  attack route pressure is not accepted by CV refs alone;
- tree routes must include explicit pathing cleanup, bounded travel-tax
  accounting, deterministic/readback route-shape evidence, local route
  alternative evidence, and an accepted visual/tree-layout inspection artifact
  before publication. Self-report text alone is not visual inspection proof;
- readback rails must block elemental resistances below 75, chaos resistance
  below 25, fragile TotalEHP, and unreserved mana that is too close to
  main-skill mana cost unless explicit sustain/waiver evidence changes the
  lane;
- no trade, Craft of Exile, poe.ninja, public-guide, or source-copy dependency
  for MVP closure;
- at least one tree pass, one gem/support pass, one gear/config pass, and one
  final read-back pass;
- meaningful alternatives must be compared before publication;
- first valid import is not sufficient proof;
- final PoB import must be verified through the packaged native import verifier
  or blocked with the smallest missing runtime dependency.

For universal PoB authoring evidence, every Direct Build lane must prove any
DPS/defense-affecting config checkbox, enemy/player state, buff, charge,
conditional, or count that it enables. Shock needs Pinnacle/Guardian threshold,
expected effect, and sustain proof. Ignite/burning claims need ignite
chance/sustain proof and config consistency. Any skill hit/projectile/overlap/
repeat/FullDPS count above 1 needs skill-mechanics evidence; this is not a
Fireball-specific rule.

## Review Coordination Minimum Bar

When coordinating a BuildReview from this skill:

- hand off or follow the `poe-build-review` bounded-review contract;
- do not silently rebuild the archetype;
- every accepted fix needs before/after PoB metrics, resource cost, alternatives
  considered, and invasiveness level;
- if fewer than 20 trials are run, record the explicit operator-approved trial
  budget or a precise runtime blocker.

## Stop Conditions

Valid stop conditions:

- trial budget exhausted and all safe next actions are accounted for;
- required runtime dependency is missing;
- user goal is underspecified and the missing decision cannot be inferred
  safely;
- all remaining actions are dominated, invalid, or blocked by explicit evidence;
- final artifact passed the publication gate.

Invalid stop conditions:

- first edit failed;
- one branch was invalid;
- a plausible import exists but was not compared;
- a prose guide can be written;
- PoB/browser interaction was inconvenient;
- market/craft/research evidence is missing for a mode that does not require
  it.
