# Surface Impact Classification

Status: skill-owned runtime classification contract.

Surface Impact Classification maps expected and measured PoB surfaces into
bounded impact categories. It is not an optimizer, universal scorer, passive
tree solver, PoB run, or Direct Build proof.

## Categories

CV6 supports these MVP categories:

- `offense`;
- `defense`;
- `quality_of_life`;
- `sustain`;
- `requirement_relief`;
- `reservation`;
- `usability`;
- `progression_friction`;
- `regression`;
- `unknown`;
- `missing_evidence`.

Unknown surfaces must remain `unknown` or `missing_evidence`. Do not invent a
value category for a metric that does not match a bounded rule.

## Rule Examples

- `FullDPS`, `CombinedDPS`, `AverageHit`, `CastRate`, and damage/DPS metrics:
  `offense`.
- Radius, area, AoE, speed, and cast-rate comfort: `quality_of_life`.
- Life, ES, EHP, max hit, resists, suppression, block, and defensive warnings:
  `defense`.
- Recovery, regen, leech, recoup, and mana-cost pressure: `sustain`.
- Attribute or requirement shortfall repair: `requirement_relief`.
- Reserved or unreserved life/mana surfaces: `reservation` and `usability`.
- Travel, passive cost, respec, budget, craft, trade, and churn signals:
  `progression_friction`.
- Worsened known surfaces, warning additions, losses, pressure, or regressions:
  add `regression`.

## Relationship To CV1-CV5

CV6 classifies surfaces already exposed by the earlier runtime layers:

- CV1 Action Cost/Value Ledger can use classifications in `value_summary`.
- CV2 Calc Snapshot Diff supplies measured changed surfaces.
- CV3 Pathing Opportunity Cost can cite classifications when explaining travel
  tax versus payoff surfaces.
- CV4 Comparison Protocol can use classifications in `comparison_basis`.
- CV5 Pre-PoB Hypothesis Triage can use classifications in
  `expected_value_summary`.

CV6 does not select a build action. It only makes the value type auditable.

## Utility

Use the skill-owned Python utility:

```text
python -m poe_build_research.pob.surface_impact_classification example --output-dir <dir>
python -m poe_build_research.pob.surface_impact_classification produce --input <classification-input.json> --output-dir <dir>
```

The utility writes:

- `surface-impact-classification.json`;
- `surface-impact-classification-validation.json`.

The utility consumes existing fixture/records or caller-provided JSON. It does
not mutate PoB, run materializer/verifier, author build choices, or spawn
product agents.
