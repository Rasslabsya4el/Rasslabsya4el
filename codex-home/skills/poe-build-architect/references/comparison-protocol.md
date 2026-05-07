# Comparison Protocol

Status: skill-owned runtime orchestration contract.

Comparison Protocol is the required pre-action comparison surface for material
PoB decisions. It is not an optimizer, scorer, passive tree solver, route
generator, PoB run, or Direct Build proof. It records whether an already
authored decision compared alternatives with enough cost and evidence to move
forward.

## Required Protocol

Before a material action is accepted, the agent must compare candidates through:

- Action Cost/Value Ledger refs for resource cost and alternatives;
- Calc Snapshot Diff refs when measured evidence is claimed;
- Pathing Opportunity Cost refs for `direct_build.tree_pathing`;
- expected affected surfaces;
- uncertainty and missing evidence;
- selected and rejected verdict reasons.

## Record Contract

Each record includes:

- `comparison_id`;
- `decision_family`;
- `mode`: `normal`, `debug`, or `trace_sampling`;
- `status`: `accepted`, `partial`, or `blocked`;
- `candidate_count`;
- `candidates`;
- `selected_candidate_id`;
- `rejected_candidate_ids`;
- `required_artifact_refs`;
- `comparison_basis`;
- `verdict_reason`;
- `stop_or_retry`.

## MVP Rules

- A comparison with fewer than two candidates is blocked.
- Three candidates are preferred when available; two candidates may be partial.
- Every candidate must have `resource_cost`.
- Every candidate must have `expected_surfaces`.
- The selected candidate must have `verdict_reason`.
- `direct_build.tree_pathing` requires `pathing_opportunity_cost_ref`.
- A measured evidence claim requires `calc_snapshot_diff_refs` or candidate
  `calc_delta` evidence refs.
- Missing evidence must be recorded. Non-blocking missing evidence makes the
  comparison partial. Blocking missing evidence blocks the comparison.

## Utility

Use the skill-owned Python utility:

```text
python -m poe_build_research.pob.comparison_protocol example --output-dir <dir>
python -m poe_build_research.pob.comparison_protocol produce --input <comparison.json> --output-dir <dir>
```

The utility writes:

- `comparison-protocol.json`;
- `comparison-protocol-validation.json`.

It validates the comparison surface only. It does not mutate PoB, author build
decisions, or spawn product agents.

## Evidence Layer Relationship

CV1 Action Cost/Value Ledger records action price and alternatives.
CV2 Calc Snapshot Diff records measured before/after deltas.
CV3 Pathing Opportunity Cost records tree-specific travel tax and value per
passive.

CV4 Comparison Protocol ties those evidence surfaces into one auditable
champion/challenger decision record.
