# Calc Snapshot Diff Evidence

Status: skill-owned runtime evidence contract.

Calc Snapshot Diff Evidence records what changed between two already-produced
normalized PoB Calc snapshots. It is evidence for a proposed action. It is not
an optimizer, not a scorer, and not authority to choose tree, gem, item, or
config changes.

## Record Contract

Each diff record includes:

- `diff_id`;
- `baseline_snapshot_ref`;
- `after_snapshot_ref`;
- `action_refs`;
- `ledger_refs`;
- `selected_skill`;
- `changed_surfaces`;
- `unchanged_surfaces`;
- `regressions`;
- `missing_metrics`;
- `unsupported_claims`;
- `evidence_quality`: `accepted`, `partial`, or `blocked`;
- `summary`.

The MVP utility compares an allowlist of important surfaces only:

- `FullDPS`, `CombinedDPS`, `AverageHit`, `CastRate`;
- `TotalEHP`, `Life`, `Mana`, `EnergyShield`;
- unreserved/reserved Life or Mana when present;
- AoE surfaces such as `Radius` and `AreaOfEffect`;
- attribute requirement shortfalls from `triage.requirement_pressure` or
  `Str/ReqStr`, `Dex/ReqDex`, `Int/ReqInt`, `Omni/ReqOmni`;
- `warning_codes`.

Missing metrics are recorded as missing evidence. The utility must not invent
values for a side that lacks the metric.

## Utility

Use the skill-owned Python utility:

```text
python -m poe_build_research.pob.calc_snapshot_diff diff --baseline <baseline.json> --after <after.json> --output <diff.json> --action-ref <action_id> --ledger-ref <ledger_ref>
python -m poe_build_research.pob.calc_snapshot_diff example --output-dir <dir>
```

The utility reads fixtures or already-produced normalized Calc snapshots. It
does not run PoB, create a Direct Build proof, spawn an agent, or mutate build
decisions.

## Action Cost/Value Ledger Link

Action Cost/Value Ledger rows cite this evidence with `evidence_kind:
calc_delta`.

Minimal row evidence ref shape:

```json
{
  "ref_id": "evidence.tree_pathing.rt_package.calc-diff",
  "evidence_kind": "calc_delta",
  "locator": "calc_snapshot_diff_example.json",
  "json_pointer": "/changed_surfaces/0",
  "summary": "Measured FullDPS increased after the authored action."
}
```

The ledger still owns action price, alternatives, and verdict reason. The Calc
diff owns measured before/after deltas and regression/missing-metric evidence.

## Evidence Quality

- `accepted`: comparable snapshots exist and no allowlisted present-on-one-side
  metric is missing.
- `partial`: at least one useful delta exists, but some metrics are missing or
  unsupported.
- `blocked`: the snapshot pair cannot produce any comparable evidence, or a
  required reference/input is absent.

Partial evidence can support a rejected or blocked row. A selected row may cite
partial evidence only when missing evidence is explicitly accounted for and is
not blocking for the decision.
