# Action Cost/Value Report

- Ledger ID: `cv1.tree-pathing.template`
- Status: `accepted`
- Decision family: `direct_build.tree_pathing`
- Action scope: `tree`
- Product-agent behavioral proof required: `false`

## Selected Action

- Action: Resolute Technique pathing package (`tree_pathing.rt_package`)
  - Cost: 4 passive points, including 2 travel points.
  - Expected surfaces: tree_state:normal_passive_count, constraint:hit_chance_or_requirement_pressure
  - Evidence refs: evidence.tree_pathing.rt_package.static-cost
  - Verdict reason: Selected because it repairs the accuracy surface for fewer total passives than the damage wheel and has clearer proof needs than the long travel package.

## Rejected Alternatives

- Action: Nearby fire damage wheel (`tree_pathing.damage_wheel`)
  - Cost: 3 passive points, including 1 travel points.
  - Expected surfaces: tree_state:normal_passive_count, pob_metric:FullDPS
  - Evidence refs: evidence.tree_pathing.damage_wheel.static-cost
  - Verdict reason: Rejected because the package spends fewer points but does not repair the active accuracy constraint.

- Action: Long travel to life wheel (`tree_pathing.long_life_route`)
  - Cost: 6 passive points, including 4 travel points.
  - Expected surfaces: tree_state:normal_passive_count, pob_metric:Life
  - Evidence refs: evidence.tree_pathing.long_life_route.static-cost
  - Verdict reason: Rejected for the MVP comparison because four travel points make the opportunity cost too high before the build has solved hit reliability.

## Comparison Rows

| Verdict | Action | Cost | Expected surfaces | Evidence refs | Reason |
| --- | --- | --- | --- | --- | --- |
| selected | Resolute Technique pathing package | 4 passive points, including 2 travel points. | tree_state:normal_passive_count, constraint:hit_chance_or_requirement_pressure | evidence.tree_pathing.rt_package.static-cost | Selected because it repairs the accuracy surface for fewer total passives than the damage wheel and has clearer proof needs than the long travel package. |
| rejected | Nearby fire damage wheel | 3 passive points, including 1 travel points. | tree_state:normal_passive_count, pob_metric:FullDPS | evidence.tree_pathing.damage_wheel.static-cost | Rejected because the package spends fewer points but does not repair the active accuracy constraint. |
| rejected | Long travel to life wheel | 6 passive points, including 4 travel points. | tree_state:normal_passive_count, pob_metric:Life | evidence.tree_pathing.long_life_route.static-cost | Rejected for the MVP comparison because four travel points make the opportunity cost too high before the build has solved hit reliability. |
