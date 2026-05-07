# Pathing Opportunity Cost

Status: skill-owned runtime comparison contract.

Pathing Opportunity Cost records how expensive authored passive-tree pathing
choices are relative to their payoff. It compares candidate path packages that
the agent already authored. It does not search the tree graph, solve routes,
choose new passives, run PoB, or create Direct Build proof.

## Record Contract

Each record includes:

- `opportunity_cost_id`;
- `decision_family`: `direct_build.tree_pathing`;
- `baseline_tree_ref`;
- `tree_state_ref`;
- `candidate_paths`;
- `selected_path_id`;
- `rejected_path_ids`;
- selected-path `resource_cost`;
- selected-path `expected_surfaces`;
- selected-path `evidence_refs`;
- selected-path `value_per_point`;
- selected-path `travel_tax`;
- selected-path `constraint_relief`;
- `verdict_reason`;
- `uncertainty`;
- `missing_evidence`.

Each candidate path must include:

- `total_passive_points`;
- `travel_points`;
- `payoff_points`;
- optional `refund_or_respec_cost`;
- expected surfaces;
- Action Cost/Value Ledger refs and/or Calc Snapshot Diff refs;
- measured or authored value units;
- value per total passive and payoff point;
- travel tax ratio;
- constraint relief when the path fixes attribute, reservation, resistance,
  accuracy, mana, or another pressure surface.

## Utility

Use the skill-owned Python utility:

```text
python -m poe_build_research.pob.pathing_opportunity_cost example --output-dir <dir>
python -m poe_build_research.pob.pathing_opportunity_cost produce --input <candidate-paths.json> --output-dir <dir>
```

The `produce` command accepts either a complete `pathing_opportunity_cost`
record or an input object containing `baseline_tree_ref`, `tree_state_ref`,
optional `selected_path_id`, and `candidate_paths`.

## What It Computes

The MVP utility computes:

- `travel_tax_ratio = travel_points / total_passive_points`;
- `travel_to_payoff_ratio = travel_points / payoff_points`;
- `per_total_passive = value_units / total_passive_points`;
- `per_payoff_point = value_units / payoff_points`;
- `per_travel_point = value_units / travel_points` when travel exists.

The default fixture demonstrates an important rule: a far high-value target can
lose to a closer medium-value package when its travel tax makes value per total
passive worse. A path with constraint relief can win when it repairs a real
attribute or resource pressure surface while keeping travel low.

## Evidence Links

Pathing opportunity rows may cite:

- `action_cost_value_ledger` refs from the CV1 ledger surface;
- `calc_delta` refs from Calc Snapshot Diff Evidence;
- `missing_evidence` when a measured diff is not available.

This record does not replace the Action Cost/Value Ledger. It is the
tree-specific opportunity-cost layer that explains whether the measured payoff
earned the passive and travel cost.
