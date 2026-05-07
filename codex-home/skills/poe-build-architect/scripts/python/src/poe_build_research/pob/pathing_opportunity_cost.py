"""Pathing opportunity cost utilities for authored passive-tree path candidates.

This module is not a passive tree solver. It compares already-authored pathing
candidate records by package cost, travel tax, payoff value, constraint relief,
and evidence refs.
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .artifacts import write_json
from .release_manager import utc_now_iso

PATHING_OPPORTUNITY_COST_RECORD_KIND = "pathing_opportunity_cost"
PATHING_OPPORTUNITY_COST_SCHEMA_VERSION = "0.1.0"
PATHING_OPPORTUNITY_COST_VALIDATION_RECORD_KIND = "pathing_opportunity_cost_validation"


class PathingOpportunityCostError(RuntimeError):
    """Raised when a pathing opportunity cost input cannot be loaded."""


def build_pathing_opportunity_cost(
    *,
    candidate_paths: Sequence[Mapping[str, Any]],
    baseline_tree_ref: str,
    tree_state_ref: str,
    opportunity_cost_id: str = "cv3.pathing-opportunity-cost.mvp",
    generated_at: str | None = None,
    selected_path_id: str | None = None,
) -> dict[str, Any]:
    """Build a pathing opportunity cost record from provided candidates."""

    generated = generated_at or utc_now_iso()
    rows = [_normalize_candidate_path(row) for row in candidate_paths]
    selected_id = _string(selected_path_id) or _select_path_id(rows)
    rejected_ids = [_string(row.get("path_id")) for row in rows if _string(row.get("path_id")) != selected_id]
    for row in rows:
        path_id = _string(row.get("path_id"))
        row["verdict"] = "selected" if path_id == selected_id else "rejected"
        row["verdict_reason"] = _verdict_reason(row, selected_path_id=selected_id, rows=rows)

    selected = _path_by_id(rows, selected_id)
    return {
        "schema_version": PATHING_OPPORTUNITY_COST_SCHEMA_VERSION,
        "record_kind": PATHING_OPPORTUNITY_COST_RECORD_KIND,
        "opportunity_cost_id": _required_string(opportunity_cost_id, "opportunity_cost_id"),
        "generated_at": generated,
        "decision_family": "direct_build.tree_pathing",
        "baseline_tree_ref": _required_string(baseline_tree_ref, "baseline_tree_ref"),
        "tree_state_ref": _required_string(tree_state_ref, "tree_state_ref"),
        "candidate_paths": rows,
        "selected_path_id": selected_id,
        "rejected_path_ids": rejected_ids,
        "resource_cost": dict(selected.get("resource_cost", {})),
        "expected_surfaces": list(_sequence(selected.get("expected_surfaces"))),
        "evidence_refs": list(_sequence(selected.get("evidence_refs"))),
        "value_per_point": dict(selected.get("value_per_point", {})),
        "travel_tax": dict(selected.get("travel_tax", {})),
        "constraint_relief": list(_sequence(selected.get("constraint_relief"))),
        "verdict_reason": _string(selected.get("verdict_reason")),
        "uncertainty": dict(_mapping(selected.get("uncertainty"))),
        "missing_evidence": list(_sequence(selected.get("missing_evidence"))),
        "summary": {
            "text": _summary_text(selected, rows),
            "candidate_count": len(rows),
            "rejected_path_count": len(rejected_ids),
            "selected_value_per_total_passive": selected.get("value_per_point", {}).get("per_total_passive"),
            "selected_travel_tax_ratio": selected.get("travel_tax", {}).get("travel_tax_ratio"),
            "product_agent_behavioral_proof_required": False,
        },
        "product_agent_behavioral_proof_required": False,
    }


def build_pathing_opportunity_cost_validation(
    record: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic validation record for one pathing opportunity record."""

    payload = _mapping(record)
    findings = _record_findings(payload)
    return {
        "schema_version": PATHING_OPPORTUNITY_COST_SCHEMA_VERSION,
        "record_kind": PATHING_OPPORTUNITY_COST_VALIDATION_RECORD_KIND,
        "opportunity_cost_id": _string(payload.get("opportunity_cost_id")) or "missing-opportunity-cost-id",
        "generated_at": generated_at or utc_now_iso(),
        "status": "accepted" if not findings else "not_accepted",
        "finding_count": len(findings),
        "findings": findings,
        "product_agent_behavioral_proof_required": False,
        "scope_note": "CV3 validates authored path candidates only; it is not a Direct Build proof or passive tree solver.",
    }


def build_pathing_opportunity_cost_mvp_example(*, generated_at: str | None = None) -> dict[str, Any]:
    """Return a fixture where a distant high-value target loses on value per point."""

    return build_pathing_opportunity_cost(
        candidate_paths=_mvp_candidate_paths(),
        baseline_tree_ref="fixture://cv3/baseline-tree-state",
        tree_state_ref="fixture://cv3/current-tree-state",
        opportunity_cost_id="cv3.pathing-opportunity-cost.mvp",
        generated_at=generated_at or "2026-05-06T00:00:00Z",
    )


def produce_pathing_opportunity_cost_artifacts(
    *,
    record: Mapping[str, Any],
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Write pathing opportunity cost record and validation artifacts."""

    target_dir = Path(output_dir).resolve(strict=False)
    target_dir.mkdir(parents=True, exist_ok=True)
    generated = generated_at or utc_now_iso()
    payload = dict(record)
    validation = build_pathing_opportunity_cost_validation(payload, generated_at=generated)
    record_path = write_json(target_dir / "pathing-opportunity-cost.json", payload)
    validation_path = write_json(target_dir / "pathing-opportunity-cost-validation.json", validation)
    return {
        "schema_version": PATHING_OPPORTUNITY_COST_SCHEMA_VERSION,
        "record_kind": "pathing_opportunity_cost_production_result",
        "status": "accepted" if validation["status"] == "accepted" else "not_accepted",
        "opportunity_cost_id": _string(payload.get("opportunity_cost_id")) or "missing-opportunity-cost-id",
        "artifact_locators": {
            "record": _path_string(record_path),
            "validation": _path_string(validation_path),
        },
        "blockers": _validation_findings_as_blockers(validation),
        "product_agent_behavioral_proof_required": False,
    }


def produce_pathing_opportunity_cost_example_artifacts(
    *,
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Write the CV3 fixture opportunity cost example artifacts."""

    return produce_pathing_opportunity_cost_artifacts(
        record=build_pathing_opportunity_cost_mvp_example(generated_at=generated_at),
        output_dir=output_dir,
        generated_at=generated_at or "2026-05-06T00:00:00Z",
    )


def produce_pathing_opportunity_cost_artifacts_from_file(
    *,
    input_path: Path,
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Load candidate path input or a complete record and produce CV3 artifacts."""

    payload = _load_json_mapping(Path(input_path), label="Pathing opportunity cost input")
    if _string(payload.get("record_kind")) == PATHING_OPPORTUNITY_COST_RECORD_KIND:
        record = payload
    else:
        record = build_pathing_opportunity_cost(
            candidate_paths=_sequence(payload.get("candidate_paths")),
            baseline_tree_ref=_string(payload.get("baseline_tree_ref")),
            tree_state_ref=_string(payload.get("tree_state_ref")),
            opportunity_cost_id=_string(payload.get("opportunity_cost_id")) or "pathing-opportunity-cost",
            selected_path_id=_string(payload.get("selected_path_id")) or None,
            generated_at=generated_at,
        )
    return produce_pathing_opportunity_cost_artifacts(
        record=record,
        output_dir=output_dir,
        generated_at=generated_at,
    )


def _mvp_candidate_paths() -> list[dict[str, Any]]:
    return [
        _candidate_path(
            path_id="tree_pathing.distant_big_fire_cluster",
            label="Distant high-value fire cluster",
            route_summary="Travel across five connector nodes to reach a strong fire cluster.",
            total_passive_points=8,
            travel_points=5,
            payoff_points=3,
            value_units=30.0,
            value_unit_label="weighted_delta_percent",
            expected_metric="FullDPS",
            evidence_suffix="distant-fire",
            constraint_relief=(),
            missing_evidence=(),
        ),
        _candidate_path(
            path_id="tree_pathing.nearby_dex_life_package",
            label="Nearby dexterity and life package",
            route_summary="Spend one connector point and three payoff nodes to repair Dex while gaining life.",
            total_passive_points=4,
            travel_points=1,
            payoff_points=3,
            value_units=21.0,
            value_unit_label="weighted_delta_percent",
            expected_metric="LifeAndDexRequirement",
            evidence_suffix="nearby-dex-life",
            constraint_relief=(
                {
                    "constraint_kind": "attribute",
                    "metric_key": "dexterity_requirement_shortfall",
                    "before_shortfall": 18.0,
                    "after_shortfall": 0.0,
                    "relief_amount": 18.0,
                    "evidence_refs": [
                        {
                            "ref_id": "evidence.cv3.nearby-dex-life.calc-diff.dex",
                            "evidence_kind": "calc_delta",
                            "locator": "calc_snapshot_diff_example.json",
                            "json_pointer": "/changed_surfaces/7",
                            "summary": "Fixture-style Calc diff ref for an attribute shortfall repair surface.",
                        }
                    ],
                    "summary": "Repairs an 18 Dexterity shortfall while keeping travel tax low.",
                },
            ),
            missing_evidence=(),
        ),
        _candidate_path(
            path_id="tree_pathing.nearby_fire_cast_package",
            label="Nearby fire and cast speed package",
            route_summary="Take a compact nearby offensive package with one connector point.",
            total_passive_points=3,
            travel_points=1,
            payoff_points=2,
            value_units=14.0,
            value_unit_label="weighted_delta_percent",
            expected_metric="FullDPSAndCastRate",
            evidence_suffix="nearby-fire-cast",
            constraint_relief=(),
            missing_evidence=(
                {
                    "evidence_kind": "calc_delta",
                    "reason": "No measured Calc diff fixture is attached to this rejected offensive package yet.",
                    "blocking": False,
                },
            ),
        ),
    ]


def _candidate_path(
    *,
    path_id: str,
    label: str,
    route_summary: str,
    total_passive_points: int,
    travel_points: int,
    payoff_points: int,
    value_units: float,
    value_unit_label: str,
    expected_metric: str,
    evidence_suffix: str,
    constraint_relief: Sequence[Mapping[str, Any]],
    missing_evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "path_id": path_id,
        "label": label,
        "route_summary": route_summary,
        "path_node_refs": [
            f"{path_id}.node.{index}" for index in range(1, total_passive_points + 1)
        ],
        "resource_cost": {
            "total_passive_points": total_passive_points,
            "travel_points": travel_points,
            "payoff_points": payoff_points,
            "refund_or_respec_cost": None,
        },
        "expected_surfaces": [
            {
                "surface_kind": "tree_state",
                "metric_key": "normal_passive_count",
                "expected_direction": "increase",
                "note": "Path package consumes passive budget.",
            },
            {
                "surface_kind": "calc_surface",
                "metric_key": expected_metric,
                "expected_direction": "increase",
                "note": "Authored candidate expects value on this surface before measurement refs are compared.",
            },
        ],
        "evidence_refs": [
            {
                "ref_id": f"evidence.cv3.{evidence_suffix}.ledger",
                "evidence_kind": "action_cost_value_ledger",
                "locator": "action_cost_value_tree_pathing_mvp.json",
                "json_pointer": "/rows",
                "summary": "CV1 Action Cost/Value Ledger fixture provides path package cost context.",
            },
            {
                "ref_id": f"evidence.cv3.{evidence_suffix}.calc-diff",
                "evidence_kind": "calc_delta",
                "locator": "calc_snapshot_diff_example.json",
                "json_pointer": "/changed_surfaces/0",
                "summary": "CV2 Calc Snapshot Diff fixture provides measured delta evidence when available.",
            },
        ],
        "measured_value": {
            "value_units": float(value_units),
            "value_unit_label": value_unit_label,
            "source_surface_refs": [f"calc_delta.{expected_metric}"],
            "summary": "Fixture value used only to demonstrate pathing opportunity cost arithmetic.",
        },
        "constraint_relief": [dict(item) for item in constraint_relief],
        "uncertainty": {
            "level": "medium",
            "notes": [
                "CV3 compares authored path candidates only and does not solve the passive tree graph.",
            ],
        },
        "missing_evidence": [dict(item) for item in missing_evidence],
    }


def _normalize_candidate_path(candidate: Mapping[str, Any]) -> dict[str, Any]:
    payload = _mapping(candidate)
    path_id = _required_string(payload.get("path_id"), "candidate_paths[].path_id")
    resource_cost = _resource_cost(_mapping(payload.get("resource_cost")), path_id=path_id)
    measured_value = _measured_value(_mapping(payload.get("measured_value")), path_id=path_id)
    value_units = measured_value["value_units"]
    total = resource_cost["total_passive_points"]
    travel = resource_cost["travel_points"]
    payoff = resource_cost["payoff_points"]
    return {
        "path_id": path_id,
        "label": _required_string(payload.get("label"), f"{path_id}.label"),
        "route_summary": _required_string(payload.get("route_summary"), f"{path_id}.route_summary"),
        "path_node_refs": [_required_string(value, f"{path_id}.path_node_refs[]") for value in _sequence(payload.get("path_node_refs"))],
        "resource_cost": resource_cost,
        "expected_surfaces": [dict(_mapping(value)) for value in _sequence(payload.get("expected_surfaces"))],
        "evidence_refs": [dict(_mapping(value)) for value in _sequence(payload.get("evidence_refs"))],
        "measured_value": measured_value,
        "value_per_point": {
            "value_unit_label": measured_value["value_unit_label"],
            "total_value_units": value_units,
            "per_total_passive": value_units / total,
            "per_payoff_point": value_units / payoff if payoff > 0 else None,
            "per_travel_point": value_units / travel if travel > 0 else None,
            "summary": f"{value_units:g} {measured_value['value_unit_label']} over {total:g} passives.",
        },
        "travel_tax": {
            "travel_points": travel,
            "total_passive_points": total,
            "payoff_points": payoff,
            "travel_tax_ratio": travel / total,
            "travel_to_payoff_ratio": travel / payoff if payoff > 0 else None,
            "summary": f"{travel:g}/{total:g} passives are travel ({(travel / total) * 100.0:.1f}%).",
        },
        "constraint_relief": [dict(_mapping(value)) for value in _sequence(payload.get("constraint_relief"))],
        "verdict": "pending",
        "verdict_reason": "",
        "uncertainty": dict(_mapping(payload.get("uncertainty"))) or {
            "level": "unknown",
            "notes": ["No uncertainty note supplied."],
        },
        "missing_evidence": [dict(_mapping(value)) for value in _sequence(payload.get("missing_evidence"))],
    }


def _resource_cost(resource_cost: Mapping[str, Any], *, path_id: str) -> dict[str, Any]:
    total = _required_positive_number(resource_cost.get("total_passive_points"), f"{path_id}.resource_cost.total_passive_points")
    travel = _required_nonnegative_number(resource_cost.get("travel_points"), f"{path_id}.resource_cost.travel_points")
    payoff = _required_positive_number(resource_cost.get("payoff_points"), f"{path_id}.resource_cost.payoff_points")
    refund = resource_cost.get("refund_or_respec_cost")
    refund_value = None if refund is None else _mapping(refund)
    return {
        "total_passive_points": total,
        "travel_points": travel,
        "payoff_points": payoff,
        "refund_or_respec_cost": refund_value,
    }


def _measured_value(measured_value: Mapping[str, Any], *, path_id: str) -> dict[str, Any]:
    value_units = _required_number(measured_value.get("value_units"), f"{path_id}.measured_value.value_units")
    return {
        "value_units": value_units,
        "value_unit_label": _required_string(measured_value.get("value_unit_label"), f"{path_id}.measured_value.value_unit_label"),
        "source_surface_refs": [
            _required_string(value, f"{path_id}.measured_value.source_surface_refs[]")
            for value in _sequence(measured_value.get("source_surface_refs"))
        ],
        "summary": _required_string(measured_value.get("summary"), f"{path_id}.measured_value.summary"),
    }


def _select_path_id(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return ""

    def sort_key(row: Mapping[str, Any]) -> tuple[float, int, float]:
        value_per_point = _number(_mapping(row.get("value_per_point")).get("per_total_passive")) or 0.0
        relief_count = len(_sequence(row.get("constraint_relief")))
        travel_tax = _number(_mapping(row.get("travel_tax")).get("travel_tax_ratio")) or 1.0
        return (value_per_point, relief_count, -travel_tax)

    best = max(rows, key=sort_key)
    return _string(best.get("path_id"))


def _verdict_reason(row: Mapping[str, Any], *, selected_path_id: str, rows: Sequence[Mapping[str, Any]]) -> str:
    path_id = _string(row.get("path_id"))
    value_per_point = _number(_mapping(row.get("value_per_point")).get("per_total_passive")) or 0.0
    travel_tax = _number(_mapping(row.get("travel_tax")).get("travel_tax_ratio")) or 0.0
    if path_id == selected_path_id:
        return (
            f"Selected because it has the strongest value per total passive ({value_per_point:.3f}) "
            f"with travel tax {travel_tax:.3f} among the authored candidates."
        )
    selected = _path_by_id(rows, selected_path_id)
    selected_value = _number(_mapping(selected.get("value_per_point")).get("per_total_passive")) or 0.0
    selected_tax = _number(_mapping(selected.get("travel_tax")).get("travel_tax_ratio")) or 0.0
    return (
        f"Rejected because its value per total passive ({value_per_point:.3f}) and travel tax ({travel_tax:.3f}) "
        f"lose to {selected_path_id} ({selected_value:.3f}, travel tax {selected_tax:.3f})."
    )


def _summary_text(selected: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    return (
        f"Compared {len(rows)} authored tree/pathing candidates. "
        f"Selected {_string(selected.get('path_id'))} on value per passive and travel tax."
    )


def _path_by_id(rows: Sequence[Mapping[str, Any]], path_id: str) -> Mapping[str, Any]:
    for row in rows:
        if _string(row.get("path_id")) == path_id:
            return row
    return {}


def _record_findings(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if _string(record.get("record_kind")) != PATHING_OPPORTUNITY_COST_RECORD_KIND:
        findings.append(_finding("record_kind_invalid", "record_kind must be pathing_opportunity_cost."))
    if _string(record.get("decision_family")) != "direct_build.tree_pathing":
        findings.append(_finding("decision_family_invalid", "decision_family must be direct_build.tree_pathing."))
    candidates = [_mapping(row) for row in _sequence(record.get("candidate_paths"))]
    if len(candidates) < 3:
        findings.append(
            _finding(
                "candidate_path_count_below_minimum",
                "Pathing Opportunity Cost requires one selected path and at least two alternatives.",
            )
        )
    if len(_sequence(record.get("rejected_path_ids"))) < 2:
        findings.append(_finding("rejected_path_count_below_minimum", "At least two rejected_path_ids are required."))
    selected_path_id = _string(record.get("selected_path_id"))
    if not selected_path_id:
        findings.append(_finding("selected_path_id_missing", "selected_path_id is required."))
    elif selected_path_id not in {_string(row.get("path_id")) for row in candidates}:
        findings.append(_finding("selected_path_id_unknown", "selected_path_id must match a candidate path."))
    for candidate in candidates:
        findings.extend(_candidate_findings(candidate))
    return findings


def _candidate_findings(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    path_id = _string(candidate.get("path_id")) or "missing-path-id"
    findings: list[dict[str, Any]] = []
    resource_cost = _mapping(candidate.get("resource_cost"))
    for key in ("total_passive_points", "travel_points", "payoff_points"):
        if _number(resource_cost.get(key)) is None:
            findings.append(_finding(f"{key}_missing", f"resource_cost.{key} is required.", path_id=path_id))
    if not _sequence(candidate.get("expected_surfaces")):
        findings.append(_finding("expected_surfaces_missing", "expected_surfaces are required.", path_id=path_id))
    if not _sequence(candidate.get("evidence_refs")) and not _sequence(candidate.get("missing_evidence")):
        findings.append(
            _finding(
                "evidence_accounting_missing",
                "Each candidate path must cite evidence_refs or account for missing_evidence.",
                path_id=path_id,
            )
        )
    if _string(candidate.get("verdict")) == "selected" and _has_blocking_missing_evidence(_sequence(candidate.get("missing_evidence"))):
        findings.append(_finding("selected_path_has_blocking_missing_evidence", "Selected path cannot have blocking missing evidence.", path_id=path_id))
    value = _number(_mapping(candidate.get("value_per_point")).get("per_total_passive"))
    if value is None:
        findings.append(_finding("value_per_total_passive_missing", "value_per_point.per_total_passive is required.", path_id=path_id))
    tax = _number(_mapping(candidate.get("travel_tax")).get("travel_tax_ratio"))
    if tax is None:
        findings.append(_finding("travel_tax_ratio_missing", "travel_tax.travel_tax_ratio is required.", path_id=path_id))
    return findings


def _validation_findings_as_blockers(validation: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "blocker_id": _string(finding.get("code")) or "pathing_opportunity_finding",
            "severity": "blocking",
            "summary": _string(finding.get("summary")) or "Pathing opportunity cost finding.",
            "unblock_condition": "Repair candidate path count, resource cost, evidence accounting, or selected path.",
        }
        for finding in _sequence(validation.get("findings"))
        if isinstance(finding, Mapping)
    ]


def _has_blocking_missing_evidence(missing_evidence: Sequence[Any]) -> bool:
    return any(isinstance(item, Mapping) and item.get("blocking") is True for item in missing_evidence)


def _load_json_mapping(path: Path, *, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PathingOpportunityCostError(f"{label} at {path} must be readable JSON.") from exc
    if not isinstance(payload, Mapping):
        raise PathingOpportunityCostError(f"{label} at {path} must be a JSON object.")
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return []


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _required_string(value: Any, field_name: str) -> str:
    text = _string(value)
    if not text:
        raise PathingOpportunityCostError(f"{field_name} must be a non-empty string.")
    return text


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _required_number(value: Any, field_name: str) -> float:
    numeric = _number(value)
    if numeric is None:
        raise PathingOpportunityCostError(f"{field_name} must be a finite number.")
    return numeric


def _required_positive_number(value: Any, field_name: str) -> float:
    numeric = _required_number(value, field_name)
    if numeric <= 0:
        raise PathingOpportunityCostError(f"{field_name} must be greater than zero.")
    return numeric


def _required_nonnegative_number(value: Any, field_name: str) -> float:
    numeric = _required_number(value, field_name)
    if numeric < 0:
        raise PathingOpportunityCostError(f"{field_name} must be greater than or equal to zero.")
    return numeric


def _path_string(path: Path) -> str:
    return Path(path).resolve(strict=False).as_posix()


def _finding(code: str, summary: str, *, path_id: str | None = None) -> dict[str, Any]:
    finding = {"code": code, "summary": summary}
    if path_id:
        finding["path_id"] = path_id
    return finding


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    produce = subparsers.add_parser("produce", help="Produce CV3 validation artifacts from candidate path input.")
    produce.add_argument("--input", type=Path, required=True)
    produce.add_argument("--output-dir", type=Path, required=True)

    example = subparsers.add_parser("example", help="Produce the CV3 pathing opportunity MVP example artifacts.")
    example.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "produce":
        result = produce_pathing_opportunity_cost_artifacts_from_file(
            input_path=args.input,
            output_dir=args.output_dir,
        )
    else:
        result = produce_pathing_opportunity_cost_example_artifacts(output_dir=args.output_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PATHING_OPPORTUNITY_COST_RECORD_KIND",
    "PATHING_OPPORTUNITY_COST_SCHEMA_VERSION",
    "PATHING_OPPORTUNITY_COST_VALIDATION_RECORD_KIND",
    "PathingOpportunityCostError",
    "build_pathing_opportunity_cost",
    "build_pathing_opportunity_cost_mvp_example",
    "build_pathing_opportunity_cost_validation",
    "produce_pathing_opportunity_cost_artifacts",
    "produce_pathing_opportunity_cost_artifacts_from_file",
    "produce_pathing_opportunity_cost_example_artifacts",
]
