# Direct Build Producer/Materializer

Status: skill-owned runtime rule.

The producer/materializer is a packaged runtime gate, not a hidden build
author. It exists so the product agent can turn its own accepted decisions into
proof-backed PoB artifacts without depending on the development repository.

## Boundary

- The product agent chooses the build: identity, skill, tree, gear, gems, config,
  budget shell, assumptions, and summaries.
- `direct_build_materializer.py produce` checks the agent-authored decision
  ledger and emits:
  - `direct-build-semantic-validation.json`
  - `materialization-source-packet.json`
  - `pob-pre-materialization-checkpoint.json`
- `direct_build_materializer.py materialize` applies only the explicit source
  payloads from `materialization-source-packet.json`, exports PoB XML/import
  code, runs the import publication verifier, and writes `direct-build-output`
  only when the verifier accepts the exact payload.
- The scripts may reject, block, apply, read back, encode, verify, and report.
  They must not pick passives, gems, affixes, uniques, configs, or the final
  archetype on the agent's behalf.

If materialization blocks, run the repair packet builder before deciding whether
to stop. The repair packet turns proof blockers into next-attempt requirements.
It does not choose the repaired tree, gear, gems, or config. If
`next_attempt_required` is true, a failed materialization is not a stop
condition: author a new decision ledger from the repair requirements, then rerun
producer and materializer until the trial budget is exhausted or publication
passes.

A repaired decision ledger must include `repair_context`:

- `record_kind: direct_build_repair_context`;
- `repair_packet_ref.ref_id` and `repair_packet_ref.locator`;
- `repair_packet_summary.record_kind: direct_build_repair_packet`;
- `repair_packet_summary.next_attempt_required: true`;
- `repair_packet_summary.stop_allowed: false`;
- `repair_packet_summary.repair_ids` or `repair_items`;
- `covered_repair_ids` covering every repair packet requirement;
- accepted decision rows with `repair_ids` showing which repair requirement
  each new decision addresses.

The producer blocks a repaired attempt if the ledger does not cover every
repair id from the packet.

## Required Decision Ledger Shape

The source ledger must be a JSON object with:

- `record_kind: direct_build_decision_ledger`
- `artifact_mode: product`
- `ledger_id`
- `generated_at`
- `build_identity.class_name`
- `build_identity.ascendancy` when applicable
- `build_identity.main_skill`
- `build_identity.level`
- accepted agent-authored rows for `identity`, `skill`, `tree`, `item`, and
  `config`
- each accepted row must include resource cost, alternatives considered, and
  evidence refs
- for cost-aware Direct Build ledgers, material decision rows must preserve
  compact CV artifact refs:
  - `pre_pob_hypothesis_triage_refs`;
  - `comparison_protocol_refs`;
  - `action_cost_value_ledger_refs`;
  - `calc_snapshot_diff_refs` when measured evidence is claimed;
  - `pathing_opportunity_cost_refs` for tree/pathing decisions;
  - `surface_impact_classification_refs`;
- `materialization_payload.identity_state`
- `materialization_payload.skill_state`
- `materialization_payload.tree_state`
- `materialization_payload.item_state`
- `materialization_payload.config_state`
- `composition_summary`
- `budget_shell`

If any part is missing, the producer must return the smallest blocker instead
of filling it from a heuristic.

## Early Game Loadout Rails And Universal Authoring Evidence

The Direct Build source gate separates lane-specific loadout constraints from
universal PoB authoring evidence.

For `direct_build_lane: early_game`, the loadout rails fail-close before a
DirectBuildOutput can be published:

- the ledger must name the tested hypothesis/archetype through
  `build_hypothesis`, `build_archetype`, or
  `composition_summary.tested_hypothesis`;
- `budget_shell.budget_status` and budget line item `source_kind` cannot be
  `unknown`;
- budget arithmetic must be internally consistent when numeric cap, total,
  mandatory, optional, and headroom fields are present;
- manual estimate budget rows need evidence refs or notes; they are not treated
  as live market proof by prose alone;
- the item payload must carry accepted `early_game_loadout_rails` metadata with
  Early Game lane, policy evidence, a prepared base catalog ref, and
  operator-declared affix/mod tier limits;
- Early Game item shells are rare-only; uniques and non-rare gear are blocked;
- each rare item may have at most three explicit affixes;
- T1/T2 affixes and T1/T2 bases are blocked unless the operator changes the
  lane;
- item bases must resolve to the packaged item base corpus
  (`corpus_data/items.json`) and cannot invent raw item base names;
- explicit implicit mods must match the selected base's cataloged implicits;
- flat accuracy may appear on at most one item total in the Early Game shell;
- bandits must be Kill All (`None` is accepted as PoB's Kill All encoding);
- baseline enemy must be Guardian/Pinnacle;
- the level 90 tree must allocate relevant masteries or justify none;
- Fireball spell trees must declare relevant tree/package tags. Accuracy,
  attack, bow, melee, or weapon-projectile route pressure blocks unless tied to
  measured constraint evidence;
- the tree must carry explicit pathing cleanup notes, bounded travel-tax
  accounting, and Pathing Opportunity Cost evidence. A CV3 ref or travel ratio
  alone is not enough;
- the tree payload must carry an accepted tree visual inspection artifact with
  screenshot/ref or deterministic layout summary and no reported dead travel,
  irrelevant cluster, or poor route shape;
- tree visual inspection and related source-quality evidence remain in the
  ledger/source packet for publication gates, but are stripped before the PoB
  tree apply call; only supported runtime tree fields are sent to PoB;
- item source-quality/loadout metadata such as `item_shell`,
  `early_game_loadout_rails`, `loadout_rails`, raw/equipped item evidence, and
  `proof_items` remain in the ledger/source packet for producer rails and
  reports, but are stripped before the PoB item apply call. PoB item apply
  receives only supported runtime item surfaces such as `active_item_set_id`
  and `item_sets`; unknown runtime item fields still fail closed;
- Early Game source items require structured proof-item evidence. Raw
  self-authored item text is not trusted by itself. Each proof item must expose
  rare item identity, `base_id`/`base_name` resolving to the packaged base
  corpus, catalog-backed implicits, at most three structured affixes, affix id,
  tier, value, and source/catalog refs;
- explicit rare affix ids, tiers, and roll ranges must resolve through the
  skill-owned Early Game proof-item mod catalog
  (`mod_data/early_game_proof_item_mods.json`). The MVP catalog is a versioned
  PoEDB `ModsView` snapshot for the selected item classes and stores source
  URLs, fetch timestamps, source hashes, and parser version. Agents must select
  catalog-backed proof items; prose/raw item text is not a substitute;
- affixes must be valid for the selected item class/base, tiers must be real
  catalog tiers, and values must sit inside the selected tier range. T1/T2
  tiers or T1/T2-like values disguised under a weaker label block publication;
- self-declared T3 items still block when their structured affix values exceed
  the Early Game power ceiling;
- Early Game resistance-fixing ring shells should use a Two-Stone Ring base or
  provide an explicit base-choice justification;
- readback rails block elemental resistances below 75, chaos resistance below
  25, low TotalEHP, and tight unreserved-mana-to-mana-cost usability before
  `direct-build-output` is published.
- tree visual inspection self-report is insufficient. Publication gates require
  deterministic/readback route-shape evidence plus local connector/cleanup
  alternative evidence, and still block reported dead travel, irrelevant
  clusters, poor route shape, or unexplained long corridors;
- mastery proof must come from actual allocated mastery fields in the tree
  payload/export, or from explicit no-mastery justification plus rejected
  mastery alternatives. `composition_summary.tree_summary.mastery_focus` text
  alone is not proof;
- ascendancy notables are subject to the same semantic relevance rules as the
  passive tree. Impale/attack Champion ascendancy choices block for a Fireball
  spell route unless the build proves relevant attack/impale value.

Universal PoB authoring evidence applies to every Direct Build lane, not only
Early Game or Fireball:

- every config checkbox, state, or count that affects DPS or defense must be
  backed by evidence that the build can create and sustain that state in the
  evaluated scenario;
- enabled states such as enemy ignited, enemy shocked, exposure, curses,
  charges, onslaught, flasks, leech, fortify, and conditional buffs need
  field-specific or config-state evidence refs;
- shock is not simply forbidden, but it requires Pinnacle/Guardian ailment
  threshold, expected shock effect, and sustain evidence before baseline shock
  can be enabled;
- ignite/burning value claims must prove ignite chance/sustain and configure the
  enemy ignited/burning state consistently; otherwise the route/config blocks;
- any skill hit count, projectile count, overlap count, repeat count, or
  FullDPS count override above 1 needs skill-mechanics/count evidence. Fireball
  multi-hit is only one example of the generic rule.

The DirectBuildOutput composition summary must expose the tested hypothesis,
build archetype, and the PoB import code file locator so the operator can
inspect the exact build artifact.

## Cost-Aware Direct Build Contract

Legacy DB1-style Direct Build ledgers remain valid legacy artifacts. They are
not retroactively cost-aware proof.

A new Cost-Aware Direct Build ledger opts in with either
`cost_aware_direct_build: true`, `cost_value_mode: cost_aware`, or
`cost_value_contract.mode: cost_aware`. Once opted in, the producer must
fail-close instead of silently accepting missing CV refs:

- every accepted material decision row needs `action_cost_value_ledger_refs`;
- every accepted material decision row needs `comparison_protocol_refs`;
- tree/pathing decision rows need `pathing_opportunity_cost_refs`;
- rows that claim measured evidence need `calc_snapshot_diff_refs`;
- missing optional CV refs remain visible through `cost_value_summary` and
  `missing_evidence`, not hidden in prose.

The producer preserves compact cost-aware refs into
`materialization-source-packet.json`:

- `cost_value_contract`;
- `cost_aware_artifact_refs`;
- `cost_aware_decision_rows`.

The materializer preserves the same compact information into
`direct-build-output.json.cost_value_summary`. The report surface shows selected
decisions, rejected alternatives, resource cost, measured/expected value,
impact categories, uncertainty, missing evidence, and artifact refs. It must
not inline full debug packets such as intake, hypothesis, measurement, or
failure packets.

## Commands

Run from the installed skill bundle, not from the development repo:

```powershell
python -m poe_build_research.pob.direct_build_materializer produce `
  --decision-ledger path\to\direct-build-decision-ledger.json `
  --output-dir path\to\publication-package
```

Then, only if the production result is accepted:

```powershell
python -m poe_build_research.pob.direct_build_materializer materialize `
  --semantic-validation path\to\direct-build-semantic-validation.json `
  --source-packet path\to\materialization-source-packet.json `
  --checkpoint path\to\pob-pre-materialization-checkpoint.json `
  --output-dir path\to\publication-package `
  --artifacts-root path\to\artifacts
```

After a blocked materialization:

```powershell
python -m poe_build_research.pob.direct_build_repair `
  --materialization-result path\to\direct-build-materialization-result.json `
  --output path\to\direct-build-repair-packet.json
```

The next attempt must cite this repair packet in its new decision trace.

## PoB Version Policy

PoB runtime is resolved through the packaged `pob.lock.json` and versioned cache.
If the operator asks for the latest PoB, first run the release manager pin step
to resolve the latest stable upstream release into a concrete tag, asset URL,
SHA-256, size, and release notes URL. Then fetch and verify that exact pinned
asset before materialization.

Do not treat "latest" as an implicit floating dependency during a build run.
Every DirectBuildOutput must be tied to the concrete pinned PoB lock that was
used for proof.
