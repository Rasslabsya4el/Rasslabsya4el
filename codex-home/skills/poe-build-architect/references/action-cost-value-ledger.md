# Action Cost/Value Ledger

Status: skill-owned runtime contract.

The Action Cost/Value Ledger is the first runtime surface for pricing PoB
actions. It does not optimize a build and it does not choose hidden build
changes. It records already-authored candidate actions so the product agent can
compare them by cost, alternatives, expected affected surfaces, evidence, and
verdict reason.

## Record Contract

Every material comparison row must include:

- `action_id`;
- `decision_family`;
- `action_scope`: `tree`, `skill`, `item`, `config`, or `mixed`;
- `candidate_action`;
- `resource_cost`;
- `alternatives_considered`;
- `expected_surfaces`;
- `evidence_refs`;
- `value_summary`;
- `verdict`: `selected`, `rejected`, or `blocked`;
- `verdict_reason`;
- `uncertainty`;
- `missing_evidence`.

The MVP ledger is accepted only when it has exactly one selected action and at
least two rejected alternatives. Each row must either cite evidence refs or
explicitly account for missing evidence. A selected row cannot have blocking
missing evidence.

## CV1 Scope

CV1 covers one bounded decision family first: Direct Build tree/pathing package
comparison. Tree choices are priced as packages:

```text
target + connector nodes + travel nodes + side benefits
```

The ledger can record static cost estimates and expected affected surfaces
before a later Calc Snapshot Diff Evidence Layer exists. It must not claim a
measured PoB improvement unless a PoB/Calc evidence ref is attached.

## Utility

Use the skill-owned Python utility:

```text
python -m poe_build_research.pob.action_cost_value_ledger example-tree-pathing --output-dir <dir>
python -m poe_build_research.pob.action_cost_value_ledger produce --ledger <ledger.json> --output-dir <dir>
```

Produced artifacts:

- `action-cost-value-ledger.json`;
- `action-cost-value-validation.json`;
- `action-cost-value-report.json`;
- `action-cost-value-report.md`.

This utility is a comparison artifact producer. It is not product-agent
behavioral proof, does not spawn agents, and does not run a Direct Build proof.

## Observability Modes

Action Cost/Value Ledger rows are always-on for material decisions in Normal
Mode. Full process packets are conditional/internal and are governed by
`references/pob-agent-observability-modes.md`.

## Measured Calc Evidence

Rows may cite `calc_delta` refs produced by
`references/calc-snapshot-diff-evidence.md`. The ledger remains responsible for
action price, alternatives, and verdict reason; the Calc diff record is only
the measured before/after evidence for changed surfaces, regressions, and
missing metrics.

## Tree Pathing Opportunity Cost

Tree/pathing rows may be further analyzed by
`references/pathing-opportunity-cost.md`. That layer compares authored path
packages by total passive cost, travel tax, payoff points, constraint relief,
and value per point. It does not search routes or replace agent-authored tree
decisions.

## Comparison Protocol

Material decisions should be wrapped by
`references/comparison-protocol.md` before action. That protocol ties selected
and rejected candidates to Action Cost/Value Ledger refs, Calc Snapshot Diff
refs when measured evidence is claimed, and Pathing Opportunity Cost refs for
tree/pathing decisions.
