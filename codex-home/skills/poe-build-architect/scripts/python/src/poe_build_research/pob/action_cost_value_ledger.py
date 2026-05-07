"""Action Cost/Value Ledger utilities for bounded PoB action comparison.

This module is not an optimizer and does not choose build mutations. It accepts
already-authored candidate actions, checks whether their cost/evidence accounting
is comparable, and publishes a compact report surface.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .artifacts import write_json, write_text
from .release_manager import utc_now_iso

ACTION_COST_VALUE_LEDGER_RECORD_KIND = "action_cost_value_ledger"
ACTION_COST_VALUE_LEDGER_SCHEMA_VERSION = "0.1.0"
ACTION_COST_VALUE_VALIDATION_RECORD_KIND = "action_cost_value_validation"
ACTION_COST_VALUE_REPORT_RECORD_KIND = "action_cost_value_report"


class ActionCostValueLedgerError(RuntimeError):
    """Raised when an Action Cost/Value Ledger input cannot be loaded."""


def build_tree_pathing_mvp_example(*, generated_at: str | None = None) -> dict[str, Any]:
    """Return a small tree/pathing comparison fixture for the CV1 surface."""

    generated = generated_at or utc_now_iso()
    rows = [
        _tree_row(
            action_id="tree_pathing.rt_package",
            label="Resolute Technique pathing package",
            summary="Spend a compact package to solve hit chance and avoid accuracy pressure.",
            passive_points=4,
            travel_points=2,
            expected_gain="Repairs hit chance reliability while keeping pathing compact.",
            normalized_value="constraint repair + low travel cost",
            verdict="selected",
            verdict_reason=(
                "Selected because it repairs the accuracy surface for fewer total passives than the damage wheel "
                "and has clearer proof needs than the long travel package."
            ),
            alternatives=("tree_pathing.damage_wheel", "tree_pathing.long_life_route"),
            tags=("accuracy_repair", "tree_package", "low_travel"),
        ),
        _tree_row(
            action_id="tree_pathing.damage_wheel",
            label="Nearby fire damage wheel",
            summary="Take a short damage-only wheel near current pathing.",
            passive_points=3,
            travel_points=1,
            expected_gain="Expected DPS increase without repairing hit chance or requirements.",
            normalized_value="moderate DPS per passive, no constraint repair",
            verdict="rejected",
            verdict_reason=(
                "Rejected because the package spends fewer points but does not repair the active accuracy constraint."
            ),
            alternatives=("tree_pathing.rt_package", "tree_pathing.long_life_route"),
            tags=("dps_gain", "tree_package"),
        ),
        _tree_row(
            action_id="tree_pathing.long_life_route",
            label="Long travel to life wheel",
            summary="Travel farther to reach a larger life wheel and incidental attributes.",
            passive_points=6,
            travel_points=4,
            expected_gain="Expected life and attribute comfort, but delayed payoff.",
            normalized_value="defense gain with high travel cost",
            verdict="rejected",
            verdict_reason=(
                "Rejected for the MVP comparison because four travel points make the opportunity cost too high "
                "before the build has solved hit reliability."
            ),
            alternatives=("tree_pathing.rt_package", "tree_pathing.damage_wheel"),
            tags=("defense_gain", "attribute_pressure", "high_travel"),
        ),
    ]
    return {
        "schema_version": ACTION_COST_VALUE_LEDGER_SCHEMA_VERSION,
        "record_kind": ACTION_COST_VALUE_LEDGER_RECORD_KIND,
        "ledger_id": "cv1.tree-pathing.mvp",
        "generated_at": generated,
        "decision_family": "direct_build.tree_pathing",
        "action_scope": "tree",
        "comparison_context": {
            "context_id": "cv1.tree-pathing.fireball-champion-example",
            "label": "Direct Build tree/pathing package comparison",
            "request_summary": "Compare three authored tree/pathing packages before a Direct Build publication choice.",
            "objective_profile": [
                "repair hard constraints before pure DPS",
                "prefer lower passive and travel cost when expected value is close",
                "record proof needs without running a new PoB optimization loop",
            ],
            "baseline_refs": [
                {
                    "ref_id": "cv1.baseline.static-tree-context",
                    "evidence_kind": "static_cost_estimate",
                    "locator": None,
                    "json_pointer": None,
                    "summary": "CV1 fixture uses static tree package costing only; no new DB1 artifact is mutated.",
                }
            ],
        },
        "status": "accepted",
        "selected_action_id": "tree_pathing.rt_package",
        "rows": rows,
        "blockers": [],
    }


def build_action_cost_value_validation(
    ledger: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic validation record for one action value ledger."""

    payload = _mapping(ledger)
    findings = _ledger_findings(payload)
    return {
        "schema_version": ACTION_COST_VALUE_LEDGER_SCHEMA_VERSION,
        "record_kind": ACTION_COST_VALUE_VALIDATION_RECORD_KIND,
        "ledger_id": _string(payload.get("ledger_id")) or "missing-ledger-id",
        "generated_at": generated_at or utc_now_iso(),
        "status": "accepted" if not findings else "not_accepted",
        "finding_count": len(findings),
        "findings": findings,
        "product_agent_behavioral_proof_required": False,
        "scope_note": "CV1 validates a comparison artifact only; it is not a Direct Build behavioral proof.",
    }


def build_action_cost_value_report(
    ledger: Mapping[str, Any],
    *,
    validation: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the compact report consumed by future product agents."""

    payload = _mapping(ledger)
    rows = [dict(row) for row in _row_mappings(payload)]
    validation_record = _mapping(validation) or build_action_cost_value_validation(payload, generated_at=generated_at)
    selected = [row for row in rows if _string(row.get("verdict")) == "selected"]
    rejected = [row for row in rows if _string(row.get("verdict")) == "rejected"]
    blocked = [row for row in rows if _string(row.get("verdict")) == "blocked"]
    selected_row = selected[0] if selected else None
    return {
        "schema_version": ACTION_COST_VALUE_LEDGER_SCHEMA_VERSION,
        "record_kind": ACTION_COST_VALUE_REPORT_RECORD_KIND,
        "ledger_id": _string(payload.get("ledger_id")) or "missing-ledger-id",
        "generated_at": generated_at or utc_now_iso(),
        "status": _string(validation_record.get("status")) or "not_accepted",
        "decision_family": _string(payload.get("decision_family")),
        "action_scope": _string(payload.get("action_scope")),
        "selected_action": _report_row(selected_row) if selected_row else None,
        "rejected_alternatives": [_report_row(row) for row in rejected],
        "blocked_alternatives": [_report_row(row) for row in blocked],
        "comparison_rows": [_report_row(row) for row in rows],
        "validation_ref": {
            "record_kind": _string(validation_record.get("record_kind")),
            "status": _string(validation_record.get("status")),
            "finding_count": validation_record.get("finding_count"),
        },
        "product_agent_behavioral_proof_required": False,
    }


def render_action_cost_value_report_markdown(report: Mapping[str, Any]) -> str:
    """Render the deterministic report surface as Markdown."""

    payload = _mapping(report)
    selected = _mapping(payload.get("selected_action"))
    rejected = [_mapping(row) for row in _sequence(payload.get("rejected_alternatives"))]
    blocked = [_mapping(row) for row in _sequence(payload.get("blocked_alternatives"))]
    lines = [
        "# Action Cost/Value Report",
        "",
        f"- Ledger ID: {_string(payload.get('ledger_id'))}",
        f"- Status: {_string(payload.get('status'))}",
        f"- Decision family: {_string(payload.get('decision_family'))}",
        f"- Action scope: {_string(payload.get('action_scope'))}",
        f"- Product-agent behavioral proof required: {str(payload.get('product_agent_behavioral_proof_required')).lower()}",
        "",
        "## Selected Action",
        "",
    ]
    if selected:
        lines.extend(_markdown_action_block(selected))
    else:
        lines.append("- None")
    lines.extend(["", "## Rejected Alternatives", ""])
    if rejected:
        for row in rejected:
            lines.extend(_markdown_action_block(row))
            lines.append("")
    else:
        lines.append("- None")
    lines.extend(["## Blocked Alternatives", ""])
    if blocked:
        for row in blocked:
            lines.extend(_markdown_action_block(row))
            lines.append("")
    else:
        lines.append("- None")
    lines.extend(["", "## Comparison Rows", ""])
    lines.append("| Verdict | Action | Cost | Expected surfaces | Evidence refs | Reason |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for row in _sequence(payload.get("comparison_rows")):
        item = _mapping(row)
        lines.append(
            "| "
            + " | ".join(
                _escape_table_cell(value)
                for value in (
                    _string(item.get("verdict")),
                    _string(item.get("label")),
                    _string(item.get("resource_cost_summary")),
                    ", ".join(_string(value) for value in _sequence(item.get("expected_surfaces"))),
                    ", ".join(_string(value) for value in _sequence(item.get("evidence_refs"))),
                    _string(item.get("verdict_reason")),
                )
            )
            + " |"
        )
    return "\n".join(lines).rstrip() + "\n"


def produce_action_cost_value_artifacts(
    *,
    ledger: Mapping[str, Any],
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Write ledger, validation, report JSON, and report Markdown artifacts."""

    target_dir = Path(output_dir).resolve(strict=False)
    target_dir.mkdir(parents=True, exist_ok=True)
    generated = generated_at or utc_now_iso()
    ledger_payload = dict(ledger)
    validation = build_action_cost_value_validation(ledger_payload, generated_at=generated)
    report = build_action_cost_value_report(ledger_payload, validation=validation, generated_at=generated)
    ledger_path = write_json(target_dir / "action-cost-value-ledger.json", ledger_payload)
    validation_path = write_json(target_dir / "action-cost-value-validation.json", validation)
    report_path = write_json(target_dir / "action-cost-value-report.json", report)
    markdown_path = write_text(target_dir / "action-cost-value-report.md", render_action_cost_value_report_markdown(report))
    accepted = _string(validation.get("status")) == "accepted"
    return {
        "schema_version": ACTION_COST_VALUE_LEDGER_SCHEMA_VERSION,
        "record_kind": "action_cost_value_production_result",
        "status": "accepted" if accepted else "not_accepted",
        "ledger_id": _string(ledger_payload.get("ledger_id")) or "missing-ledger-id",
        "generated_at": generated,
        "artifact_locators": {
            "ledger": _path_string(ledger_path),
            "validation": _path_string(validation_path),
            "report": _path_string(report_path),
            "markdown_report": _path_string(markdown_path),
        },
        "blockers": _validation_findings_as_blockers(validation),
        "product_agent_behavioral_proof_required": False,
    }


def produce_action_cost_value_artifacts_from_file(
    *,
    ledger_path: Path,
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Load a ledger JSON file and produce CV1 artifacts."""

    return produce_action_cost_value_artifacts(
        ledger=_load_json_mapping(Path(ledger_path), label="Action Cost/Value Ledger"),
        output_dir=output_dir,
        generated_at=generated_at,
    )


def _tree_row(
    *,
    action_id: str,
    label: str,
    summary: str,
    passive_points: int,
    travel_points: int,
    expected_gain: str,
    normalized_value: str,
    verdict: str,
    verdict_reason: str,
    alternatives: Sequence[str],
    tags: Sequence[str],
) -> dict[str, Any]:
    relationship = "selected_over" if verdict == "selected" else "rejected_for"
    return {
        "action_id": action_id,
        "decision_family": "direct_build.tree_pathing",
        "action_scope": "tree",
        "candidate_action": {
            "label": label,
            "summary": summary,
            "action_kind": "allocate_tree_package",
            "payload_ref": None,
            "tags": list(tags),
        },
        "resource_cost": {
            "scarce_resource_summary": f"{passive_points} passive points, including {travel_points} travel points.",
            "cost_components": [
                {
                    "resource": "passive_points",
                    "amount": passive_points,
                    "unit": "points",
                    "direction": "spent",
                    "note": "Total package cost.",
                },
                {
                    "resource": "travel_points",
                    "amount": travel_points,
                    "unit": "points",
                    "direction": "spent",
                    "note": "Connector nodes before payoff nodes.",
                },
            ],
            "opportunity_cost_notes": [
                "Spending this package delays at least one other nearby tree package.",
            ],
        },
        "alternatives_considered": [
            {
                "action_id": alternative,
                "label": alternative.rsplit(".", 1)[-1].replace("_", " "),
                "relationship": relationship,
            }
            for alternative in alternatives
        ],
        "expected_surfaces": [
            {
                "surface_kind": "tree_state",
                "metric_key": "normal_passive_count",
                "expected_direction": "increase",
                "note": "Tree package consumes passive budget.",
            },
            {
                "surface_kind": "constraint",
                "metric_key": "hit_chance_or_requirement_pressure",
                "expected_direction": "repair" if "accuracy_repair" in tags else "unknown",
                "note": "CV1 records expected affected surface before a later PoB/Calc diff layer attaches measured deltas.",
            },
        ],
        "evidence_refs": [
            {
                "ref_id": f"evidence.{action_id}.static-cost",
                "evidence_kind": "static_cost_estimate",
                "locator": None,
                "json_pointer": None,
                "summary": "Static package cost authored from the compared tree pathing package.",
            }
        ],
        "value_summary": {
            "value_label": label,
            "expected_gain_summary": expected_gain,
            "cost_summary": f"{passive_points} passive / {travel_points} travel.",
            "normalized_value": normalized_value,
            "tradeoff_notes": [
                "CV1 does not claim measured PoB improvement; it records comparable expected value and proof refs.",
            ],
        },
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "uncertainty": {
            "level": "medium",
            "notes": [
                "No new PoB optimization run is part of CV1.",
            ],
        },
        "missing_evidence": [],
    }


def _ledger_findings(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if _string(ledger.get("record_kind")) != ACTION_COST_VALUE_LEDGER_RECORD_KIND:
        findings.append(_finding("record_kind_invalid", "record_kind must be action_cost_value_ledger."))
    rows = _row_mappings(ledger)
    if len(rows) < 3:
        findings.append(_finding("row_count_below_minimum", "Action Cost/Value Ledger must contain at least three rows."))

    selected = [row for row in rows if _string(row.get("verdict")) == "selected"]
    rejected = [row for row in rows if _string(row.get("verdict")) == "rejected"]
    if len(selected) != 1:
        findings.append(_finding("selected_row_count_invalid", "Ledger must contain exactly one selected action row."))
    if len(rejected) < 2:
        findings.append(_finding("rejected_alternative_count_below_minimum", "Ledger must contain at least two rejected alternatives."))

    selected_action_id = _string(ledger.get("selected_action_id"))
    if selected and selected_action_id != _string(selected[0].get("action_id")):
        findings.append(_finding("selected_action_id_mismatch", "selected_action_id must match the selected row action_id."))

    for row in rows:
        findings.extend(_row_findings(row))
    return findings


def _row_findings(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    action_id = _string(row.get("action_id")) or "missing-action-id"
    findings: list[dict[str, Any]] = []
    if not isinstance(row.get("candidate_action"), Mapping):
        findings.append(_finding("candidate_action_missing", "candidate_action must be an object.", action_id=action_id))
    resource_cost = row.get("resource_cost")
    if not isinstance(resource_cost, Mapping) or not _sequence(resource_cost.get("cost_components")):
        findings.append(_finding("resource_cost_missing", "resource_cost.cost_components must contain at least one cost.", action_id=action_id))
    if len(_sequence(row.get("alternatives_considered"))) < 2:
        findings.append(_finding("alternatives_considered_below_minimum", "Each row must consider at least two alternatives.", action_id=action_id))
    if not _sequence(row.get("expected_surfaces")):
        findings.append(_finding("expected_surfaces_missing", "Each row must name expected affected surfaces.", action_id=action_id))
    has_evidence_refs_field = "evidence_refs" in row
    has_missing_evidence_field = "missing_evidence" in row
    evidence_refs = _sequence(row.get("evidence_refs"))
    missing_evidence = _sequence(row.get("missing_evidence"))
    if not has_evidence_refs_field and not has_missing_evidence_field:
        findings.append(
            _finding(
                "evidence_accounting_missing",
                "Each row must contain evidence_refs or missing_evidence accounting.",
                action_id=action_id,
            )
        )
    if not evidence_refs and not missing_evidence:
        findings.append(
            _finding(
                "evidence_or_missing_evidence_required",
                "Each row must either cite evidence_refs or explicitly name missing_evidence.",
                action_id=action_id,
            )
        )
    if _string(row.get("verdict")) == "selected":
        if not evidence_refs:
            findings.append(_finding("selected_row_evidence_refs_missing", "Selected action must cite evidence_refs.", action_id=action_id))
        if _has_blocking_missing_evidence(missing_evidence):
            findings.append(
                _finding(
                    "selected_row_has_blocking_missing_evidence",
                    "Selected action cannot have blocking missing evidence.",
                    action_id=action_id,
                )
            )
    if not isinstance(row.get("value_summary"), Mapping):
        findings.append(_finding("value_summary_missing", "value_summary must be an object.", action_id=action_id))
    if not _string(row.get("verdict_reason")):
        findings.append(_finding("verdict_reason_missing", "verdict_reason is required.", action_id=action_id))
    return findings


def _report_row(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    candidate = _mapping(row.get("candidate_action"))
    resource_cost = _mapping(row.get("resource_cost"))
    value_summary = _mapping(row.get("value_summary"))
    return {
        "action_id": _string(row.get("action_id")),
        "label": _string(candidate.get("label")),
        "summary": _string(candidate.get("summary")),
        "verdict": _string(row.get("verdict")),
        "verdict_reason": _string(row.get("verdict_reason")),
        "resource_cost_summary": _string(resource_cost.get("scarce_resource_summary")),
        "cost_components": [
            _string(component.get("resource"))
            for component in _sequence(resource_cost.get("cost_components"))
            if isinstance(component, Mapping)
        ],
        "alternatives_considered": [
            _string(alternative.get("action_id"))
            for alternative in _sequence(row.get("alternatives_considered"))
            if isinstance(alternative, Mapping)
        ],
        "expected_surfaces": [
            _string(surface.get("surface_kind")) + ":" + (_string(surface.get("metric_key")) or "unspecified")
            for surface in _sequence(row.get("expected_surfaces"))
            if isinstance(surface, Mapping)
        ],
        "evidence_refs": [
            _string(evidence.get("ref_id"))
            for evidence in _sequence(row.get("evidence_refs"))
            if isinstance(evidence, Mapping)
        ],
        "missing_evidence": [
            _string(evidence.get("evidence_kind"))
            for evidence in _sequence(row.get("missing_evidence"))
            if isinstance(evidence, Mapping)
        ],
        "value_summary": {
            "expected_gain_summary": _string(value_summary.get("expected_gain_summary")),
            "normalized_value": _string(value_summary.get("normalized_value")),
        },
    }


def _markdown_action_block(row: Mapping[str, Any]) -> list[str]:
    return [
        f"- Action: {_string(row.get('label'))} (`{_string(row.get('action_id'))}`)",
        f"  - Cost: {_string(row.get('resource_cost_summary'))}",
        f"  - Expected surfaces: {', '.join(_string(value) for value in _sequence(row.get('expected_surfaces')))}",
        f"  - Evidence refs: {', '.join(_string(value) for value in _sequence(row.get('evidence_refs')))}",
        f"  - Verdict reason: {_string(row.get('verdict_reason'))}",
    ]


def _validation_findings_as_blockers(validation: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "blocker_id": _string(finding.get("code")) or "action_value_finding",
            "severity": "blocking",
            "summary": _string(finding.get("summary")) or "Action Cost/Value Ledger finding.",
            "unblock_condition": "Repair the ledger row cost, alternatives, evidence accounting, or verdict.",
        }
        for finding in _sequence(validation.get("findings"))
        if isinstance(finding, Mapping)
    ]


def _has_blocking_missing_evidence(missing_evidence: Sequence[Any]) -> bool:
    return any(isinstance(item, Mapping) and item.get("blocking") is True for item in missing_evidence)


def _row_mappings(ledger: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [row for row in _sequence(ledger.get("rows")) if isinstance(row, Mapping)]


def _load_json_mapping(path: Path, *, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActionCostValueLedgerError(f"{label} at {path} must be readable JSON.") from exc
    if not isinstance(payload, Mapping):
        raise ActionCostValueLedgerError(f"{label} at {path} must be a JSON object.")
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return []


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _path_string(path: Path) -> str:
    return Path(path).resolve(strict=False).as_posix()


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _finding(code: str, summary: str, *, action_id: str | None = None) -> dict[str, Any]:
    finding = {"code": code, "summary": summary}
    if action_id:
        finding["action_id"] = action_id
    return finding


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    produce = subparsers.add_parser("produce", help="Produce CV1 validation and report artifacts from a ledger.")
    produce.add_argument("--ledger", type=Path, required=True)
    produce.add_argument("--output-dir", type=Path, required=True)

    example = subparsers.add_parser("example-tree-pathing", help="Produce the CV1 tree/pathing MVP example artifacts.")
    example.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "produce":
        result = produce_action_cost_value_artifacts_from_file(
            ledger_path=args.ledger,
            output_dir=args.output_dir,
        )
    else:
        result = produce_action_cost_value_artifacts(
            ledger=build_tree_pathing_mvp_example(),
            output_dir=args.output_dir,
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
