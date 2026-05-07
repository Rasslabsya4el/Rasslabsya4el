"""Comparison Protocol utilities for bounded PoB material decisions.

This module is an orchestration contract, not an optimizer. It validates that
an already-authored material decision compared alternatives through cost,
expected surfaces, required evidence refs, and explicit verdict reasons.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .artifacts import write_json
from .release_manager import utc_now_iso

COMPARISON_PROTOCOL_RECORD_KIND = "comparison_protocol"
COMPARISON_PROTOCOL_SCHEMA_VERSION = "0.1.0"
COMPARISON_PROTOCOL_VALIDATION_RECORD_KIND = "comparison_protocol_validation"

_MODES = frozenset({"normal", "debug", "trace_sampling"})
_HARD_FINDINGS = frozenset(
    {
        "candidate_count_below_minimum",
        "selected_candidate_id_missing",
        "selected_candidate_id_unknown",
        "rejected_candidate_count_below_minimum",
        "selected_candidate_verdict_reason_missing",
        "candidate_resource_cost_missing",
        "candidate_expected_surfaces_missing",
        "action_cost_value_ledger_ref_missing",
        "tree_pathing_opportunity_cost_ref_missing",
        "measured_claim_without_calc_snapshot_diff_ref",
    }
)


class ComparisonProtocolError(RuntimeError):
    """Raised when a Comparison Protocol input cannot be loaded."""


def build_comparison_protocol(
    *,
    comparison_id: str,
    decision_family: str,
    candidates: Sequence[Mapping[str, Any]],
    selected_candidate_id: str | None = None,
    mode: str = "normal",
    required_artifact_refs: Mapping[str, Any] | None = None,
    verdict_reason: str | None = None,
    stop_or_retry: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build and validate one material-decision comparison protocol record."""

    normalized_candidates = [_normalize_candidate(candidate) for candidate in candidates]
    selected_id = _string(selected_candidate_id) or _selected_from_candidates(normalized_candidates)
    rejected_ids = [
        _string(candidate.get("candidate_id"))
        for candidate in normalized_candidates
        if _string(candidate.get("candidate_id")) != selected_id
    ]
    refs = _normalize_required_refs(required_artifact_refs)
    selected = _candidate_by_id(normalized_candidates, selected_id)
    basis = _comparison_basis(selected, normalized_candidates, refs)
    record = {
        "schema_version": COMPARISON_PROTOCOL_SCHEMA_VERSION,
        "record_kind": COMPARISON_PROTOCOL_RECORD_KIND,
        "comparison_id": _required_string(comparison_id, "comparison_id"),
        "generated_at": generated_at or utc_now_iso(),
        "decision_family": _required_string(decision_family, "decision_family"),
        "mode": _normalize_mode(mode),
        "status": "blocked",
        "candidate_count": len(normalized_candidates),
        "candidates": normalized_candidates,
        "selected_candidate_id": selected_id,
        "rejected_candidate_ids": rejected_ids,
        "required_artifact_refs": refs,
        "comparison_basis": basis,
        "verdict_reason": _string(verdict_reason) or _string(selected.get("verdict_reason")),
        "stop_or_retry": _normalize_stop_or_retry(stop_or_retry),
        "validation": {
            "finding_count": 0,
            "findings": [],
        },
        "product_agent_behavioral_proof_required": False,
    }
    validation = build_comparison_protocol_validation(record, generated_at=record["generated_at"])
    record["status"] = validation["status"]
    record["validation"] = {
        "finding_count": validation["finding_count"],
        "findings": list(validation["findings"]),
    }
    return record


def build_comparison_protocol_validation(
    record: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic validation record for one Comparison Protocol."""

    payload = _mapping(record)
    findings = _record_findings(payload)
    hard = [finding for finding in findings if _string(finding.get("severity")) == "blocking"]
    partial = [finding for finding in findings if _string(finding.get("severity")) == "partial"]
    if hard:
        status = "blocked"
    elif partial:
        status = "partial"
    else:
        status = "accepted"
    return {
        "schema_version": COMPARISON_PROTOCOL_SCHEMA_VERSION,
        "record_kind": COMPARISON_PROTOCOL_VALIDATION_RECORD_KIND,
        "comparison_id": _string(payload.get("comparison_id")) or "missing-comparison-id",
        "generated_at": generated_at or utc_now_iso(),
        "status": status,
        "finding_count": len(findings),
        "findings": findings,
        "product_agent_behavioral_proof_required": False,
        "scope_note": "CV4 validates a material-decision comparison artifact only; it is not a Direct Build proof.",
    }


def build_comparison_protocol_mvp_example(*, generated_at: str | None = None) -> dict[str, Any]:
    """Return a fixture tying CV1, CV2, and CV3 refs into one comparison."""

    return build_comparison_protocol(
        comparison_id="cv4.comparison-protocol.tree-pathing.mvp",
        decision_family="direct_build.tree_pathing",
        mode="normal",
        candidates=_mvp_candidates(),
        selected_candidate_id="tree_pathing.nearby_dex_life_package",
        required_artifact_refs={
            "action_cost_value_ledger_ref": {
                "ref_id": "cv1.action-cost-value-ledger",
                "evidence_kind": "action_cost_value_ledger",
                "locator": "action_cost_value_tree_pathing_mvp.json",
                "json_pointer": "/rows",
                "summary": "CV1 ledger supplies candidate cost and alternatives.",
            },
            "calc_snapshot_diff_refs": [
                {
                    "ref_id": "cv2.calc-snapshot-diff",
                    "evidence_kind": "calc_delta",
                    "locator": "calc_snapshot_diff_example.json",
                    "json_pointer": "/changed_surfaces",
                    "summary": "CV2 diff supplies measured delta evidence where available.",
                }
            ],
            "pathing_opportunity_cost_ref": {
                "ref_id": "cv3.pathing-opportunity-cost",
                "evidence_kind": "pathing_opportunity_cost",
                "locator": "pathing-opportunity-cost.json",
                "json_pointer": "/candidate_paths",
                "summary": "CV3 pathing opportunity record prices travel tax and value per passive.",
            },
        },
        verdict_reason=(
            "Selected nearby Dex/life package because it compares three alternatives, keeps travel tax low, "
            "cites CV1/CV2/CV3 evidence, and repairs a constraint while the distant high-value route loses on "
            "value per total passive."
        ),
        stop_or_retry={
            "recommendation": "stop_with_selected",
            "reason": "Comparison is accepted for this bounded decision; continue with the selected action if the caller owns the build decision.",
            "next_action": "Use the selected candidate as the authored material action input.",
        },
        generated_at=generated_at or "2026-05-06T00:00:00Z",
    )


def produce_comparison_protocol_artifacts(
    *,
    record: Mapping[str, Any],
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Write Comparison Protocol record and validation artifacts."""

    target_dir = Path(output_dir).resolve(strict=False)
    target_dir.mkdir(parents=True, exist_ok=True)
    generated = generated_at or utc_now_iso()
    payload = dict(record)
    validation = build_comparison_protocol_validation(payload, generated_at=generated)
    payload["status"] = validation["status"]
    payload["validation"] = {
        "finding_count": validation["finding_count"],
        "findings": list(validation["findings"]),
    }
    record_path = write_json(target_dir / "comparison-protocol.json", payload)
    validation_path = write_json(target_dir / "comparison-protocol-validation.json", validation)
    return {
        "schema_version": COMPARISON_PROTOCOL_SCHEMA_VERSION,
        "record_kind": "comparison_protocol_production_result",
        "status": validation["status"],
        "comparison_id": _string(payload.get("comparison_id")) or "missing-comparison-id",
        "artifact_locators": {
            "record": _path_string(record_path),
            "validation": _path_string(validation_path),
        },
        "blockers": _validation_findings_as_blockers(validation),
        "product_agent_behavioral_proof_required": False,
    }


def produce_comparison_protocol_example_artifacts(
    *,
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Write the CV4 comparison protocol example artifacts."""

    return produce_comparison_protocol_artifacts(
        record=build_comparison_protocol_mvp_example(generated_at=generated_at),
        output_dir=output_dir,
        generated_at=generated_at or "2026-05-06T00:00:00Z",
    )


def produce_comparison_protocol_artifacts_from_file(
    *,
    input_path: Path,
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Load one Comparison Protocol record/input and produce validation artifacts."""

    payload = _load_json_mapping(Path(input_path), label="Comparison Protocol input")
    if _string(payload.get("record_kind")) == COMPARISON_PROTOCOL_RECORD_KIND:
        record = payload
    else:
        record = build_comparison_protocol(
            comparison_id=_string(payload.get("comparison_id")) or "comparison-protocol",
            decision_family=_string(payload.get("decision_family")),
            mode=_string(payload.get("mode")) or "normal",
            candidates=_sequence(payload.get("candidates")),
            selected_candidate_id=_string(payload.get("selected_candidate_id")) or None,
            required_artifact_refs=_mapping(payload.get("required_artifact_refs")),
            verdict_reason=_string(payload.get("verdict_reason")) or None,
            stop_or_retry=_mapping(payload.get("stop_or_retry")),
            generated_at=generated_at,
        )
    return produce_comparison_protocol_artifacts(
        record=record,
        output_dir=output_dir,
        generated_at=generated_at,
    )


def _mvp_candidates() -> list[dict[str, Any]]:
    return [
        _candidate(
            candidate_id="tree_pathing.distant_big_fire_cluster",
            label="Distant high-value fire cluster",
            total_passive_points=8,
            travel_points=5,
            payoff_points=3,
            measured=True,
            opportunity=True,
            verdict="rejected",
            verdict_reason="Rejected because CV3 shows weaker value per total passive after travel tax.",
            missing_evidence=(),
        ),
        _candidate(
            candidate_id="tree_pathing.nearby_dex_life_package",
            label="Nearby dexterity and life package",
            total_passive_points=4,
            travel_points=1,
            payoff_points=3,
            measured=True,
            opportunity=True,
            verdict="selected",
            verdict_reason="Selected because it has better value per passive and repairs Dexterity pressure.",
            missing_evidence=(),
        ),
        _candidate(
            candidate_id="tree_pathing.nearby_fire_cast_package",
            label="Nearby fire and cast speed package",
            total_passive_points=3,
            travel_points=1,
            payoff_points=2,
            measured=True,
            opportunity=True,
            verdict="rejected",
            verdict_reason="Rejected because CV3 shows lower total opportunity value than the selected constraint-relief package.",
            missing_evidence=(),
        ),
    ]


def _candidate(
    *,
    candidate_id: str,
    label: str,
    total_passive_points: int,
    travel_points: int,
    payoff_points: int,
    measured: bool,
    opportunity: bool,
    verdict: str,
    verdict_reason: str,
    missing_evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    evidence_refs = [
        {
            "ref_id": f"evidence.cv4.{candidate_id}.ledger",
            "evidence_kind": "action_cost_value_ledger",
            "locator": "action_cost_value_tree_pathing_mvp.json",
            "json_pointer": "/rows",
            "summary": "Action Cost/Value Ledger ref for resource cost and alternatives.",
        }
    ]
    if measured:
        evidence_refs.append(
            {
                "ref_id": f"evidence.cv4.{candidate_id}.calc-diff",
                "evidence_kind": "calc_delta",
                "locator": "calc_snapshot_diff_example.json",
                "json_pointer": "/changed_surfaces",
                "summary": "Calc Snapshot Diff ref for measured before/after evidence.",
            }
        )
    if opportunity:
        evidence_refs.append(
            {
                "ref_id": f"evidence.cv4.{candidate_id}.pathing",
                "evidence_kind": "pathing_opportunity_cost",
                "locator": "pathing-opportunity-cost.json",
                "json_pointer": "/candidate_paths",
                "summary": "Pathing Opportunity Cost ref for travel tax and value per point.",
            }
        )
    return {
        "candidate_id": candidate_id,
        "label": label,
        "resource_cost": {
            "total_passive_points": total_passive_points,
            "travel_points": travel_points,
            "payoff_points": payoff_points,
            "summary": f"{total_passive_points} passives, {travel_points} travel, {payoff_points} payoff.",
        },
        "expected_surfaces": [
            {
                "surface_kind": "tree_state",
                "metric_key": "normal_passive_count",
                "expected_direction": "increase",
                "note": "Candidate consumes passive budget.",
            },
            {
                "surface_kind": "calc_surface",
                "metric_key": "FullDPS_or_constraint_relief",
                "expected_direction": "increase",
                "note": "Candidate expects DPS, constraint relief, or both.",
            },
        ],
        "evidence_refs": evidence_refs,
        "claims_measured_evidence": measured,
        "claims_opportunity_cost": opportunity,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "uncertainty": {
            "level": "medium",
            "notes": [
                "CV4 validates comparison completeness only and does not optimize the build.",
            ],
        },
        "missing_evidence": [dict(item) for item in missing_evidence],
    }


def _normalize_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    payload = _mapping(candidate)
    candidate_id = _required_string(payload.get("candidate_id"), "candidates[].candidate_id")
    return {
        "candidate_id": candidate_id,
        "label": _required_string(payload.get("label"), f"{candidate_id}.label"),
        "resource_cost": dict(_mapping(payload.get("resource_cost"))),
        "expected_surfaces": [dict(_mapping(value)) for value in _sequence(payload.get("expected_surfaces"))],
        "evidence_refs": [dict(_mapping(value)) for value in _sequence(payload.get("evidence_refs"))],
        "claims_measured_evidence": bool(payload.get("claims_measured_evidence")),
        "claims_opportunity_cost": bool(payload.get("claims_opportunity_cost")),
        "verdict": _string(payload.get("verdict")) or "pending",
        "verdict_reason": _string(payload.get("verdict_reason")),
        "uncertainty": dict(_mapping(payload.get("uncertainty"))) or {
            "level": "unknown",
            "notes": ["No uncertainty note supplied."],
        },
        "missing_evidence": [dict(_mapping(value)) for value in _sequence(payload.get("missing_evidence"))],
    }


def _normalize_required_refs(value: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _mapping(value)
    return {
        "action_cost_value_ledger_ref": _nullable_mapping(payload.get("action_cost_value_ledger_ref")),
        "calc_snapshot_diff_refs": [dict(_mapping(value)) for value in _sequence(payload.get("calc_snapshot_diff_refs"))],
        "pathing_opportunity_cost_ref": _nullable_mapping(payload.get("pathing_opportunity_cost_ref")),
    }


def _comparison_basis(
    selected: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    refs: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "resource_cost": dict(_mapping(selected.get("resource_cost"))),
        "expected_surfaces": list(_sequence(selected.get("expected_surfaces"))),
        "measured_evidence": {
            "claimed": bool(selected.get("claims_measured_evidence")),
            "calc_snapshot_diff_refs": list(_sequence(refs.get("calc_snapshot_diff_refs"))),
        },
        "opportunity_cost": {
            "claimed": bool(selected.get("claims_opportunity_cost")),
            "pathing_opportunity_cost_ref": _nullable_mapping(refs.get("pathing_opportunity_cost_ref")),
        },
        "uncertainty": dict(_mapping(selected.get("uncertainty"))),
        "missing_evidence": list(_sequence(selected.get("missing_evidence"))),
        "candidate_ids": [_string(candidate.get("candidate_id")) for candidate in candidates],
    }


def _record_findings(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if _string(record.get("record_kind")) != COMPARISON_PROTOCOL_RECORD_KIND:
        findings.append(_finding("record_kind_invalid", "record_kind must be comparison_protocol."))
    if _string(record.get("mode")) not in _MODES:
        findings.append(_finding("mode_invalid", "mode must be normal, debug, or trace_sampling."))
    candidates = [_mapping(candidate) for candidate in _sequence(record.get("candidates"))]
    if len(candidates) < 2:
        findings.append(_finding("candidate_count_below_minimum", "Comparison requires at least two candidates."))
    if len(candidates) == 2:
        findings.append(_finding("candidate_count_prefer_three", "Comparison has two candidates; three are preferred when available.", severity="partial"))
    selected_id = _string(record.get("selected_candidate_id"))
    if not selected_id:
        findings.append(_finding("selected_candidate_id_missing", "selected_candidate_id is required."))
    elif selected_id not in {_string(candidate.get("candidate_id")) for candidate in candidates}:
        findings.append(_finding("selected_candidate_id_unknown", "selected_candidate_id must match a candidate."))
    if len(_sequence(record.get("rejected_candidate_ids"))) < 1:
        findings.append(_finding("rejected_candidate_count_below_minimum", "At least one rejected candidate is required."))

    refs = _mapping(record.get("required_artifact_refs"))
    if not _mapping(refs.get("action_cost_value_ledger_ref")):
        findings.append(_finding("action_cost_value_ledger_ref_missing", "action_cost_value_ledger_ref is required."))
    calc_refs = _sequence(refs.get("calc_snapshot_diff_refs"))
    pathing_ref = _mapping(refs.get("pathing_opportunity_cost_ref"))
    if _string(record.get("decision_family")) == "direct_build.tree_pathing" and not pathing_ref:
        findings.append(_finding("tree_pathing_opportunity_cost_ref_missing", "tree_pathing requires pathing_opportunity_cost_ref."))

    for candidate in candidates:
        findings.extend(_candidate_findings(candidate, calc_refs=calc_refs))

    selected = _candidate_by_id(candidates, selected_id)
    if selected and not _string(selected.get("verdict_reason")):
        findings.append(_finding("selected_candidate_verdict_reason_missing", "Selected candidate requires verdict_reason.", candidate_id=selected_id))
    if selected and _has_blocking_missing_evidence(_sequence(selected.get("missing_evidence"))):
        findings.append(_finding("selected_candidate_has_blocking_missing_evidence", "Selected candidate has blocking missing evidence.", candidate_id=selected_id))
    if _has_nonblocking_missing_evidence(candidates):
        findings.append(_finding("comparison_has_nonblocking_missing_evidence", "Comparison contains non-blocking missing evidence and is partial.", severity="partial"))
    return findings


def _candidate_findings(candidate: Mapping[str, Any], *, calc_refs: Sequence[Any]) -> list[dict[str, Any]]:
    candidate_id = _string(candidate.get("candidate_id")) or "missing-candidate-id"
    findings: list[dict[str, Any]] = []
    resource_cost = _mapping(candidate.get("resource_cost"))
    if not resource_cost:
        findings.append(_finding("candidate_resource_cost_missing", "Each candidate requires resource_cost.", candidate_id=candidate_id))
    if not _sequence(candidate.get("expected_surfaces")):
        findings.append(_finding("candidate_expected_surfaces_missing", "Each candidate requires expected_surfaces.", candidate_id=candidate_id))
    candidate_calc_refs = [
        ref for ref in _sequence(candidate.get("evidence_refs"))
        if isinstance(ref, Mapping) and _string(ref.get("evidence_kind")) == "calc_delta"
    ]
    if candidate.get("claims_measured_evidence") and not calc_refs and not candidate_calc_refs:
        findings.append(
            _finding(
                "measured_claim_without_calc_snapshot_diff_ref",
                "Measured evidence claims require calc_snapshot_diff_refs or candidate calc_delta evidence refs.",
                candidate_id=candidate_id,
            )
        )
    return findings


def _validation_findings_as_blockers(validation: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "blocker_id": _string(finding.get("code")) or "comparison_protocol_finding",
            "severity": _string(finding.get("severity")) or "blocking",
            "summary": _string(finding.get("summary")) or "Comparison Protocol finding.",
            "unblock_condition": "Repair candidate count, resource cost, expected surfaces, required refs, or verdict reason.",
        }
        for finding in _sequence(validation.get("findings"))
        if isinstance(finding, Mapping)
    ]


def _selected_from_candidates(candidates: Sequence[Mapping[str, Any]]) -> str:
    selected = [
        _string(candidate.get("candidate_id"))
        for candidate in candidates
        if _string(candidate.get("verdict")) == "selected"
    ]
    return selected[0] if selected else ""


def _candidate_by_id(candidates: Sequence[Mapping[str, Any]], candidate_id: str) -> Mapping[str, Any]:
    for candidate in candidates:
        if _string(candidate.get("candidate_id")) == candidate_id:
            return candidate
    return {}


def _normalize_mode(value: str) -> str:
    mode = _string(value) or "normal"
    if mode not in _MODES:
        raise ComparisonProtocolError("mode must be normal, debug, or trace_sampling.")
    return mode


def _normalize_stop_or_retry(value: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _mapping(value)
    recommendation = _string(payload.get("recommendation")) or "retry_with_more_evidence"
    if recommendation not in {"stop_with_selected", "retry_with_more_evidence", "block"}:
        raise ComparisonProtocolError("stop_or_retry.recommendation is invalid.")
    return {
        "recommendation": recommendation,
        "reason": _string(payload.get("reason")) or "No stop/retry reason supplied.",
        "next_action": _string(payload.get("next_action")) or "Collect missing comparison evidence.",
    }


def _has_blocking_missing_evidence(missing_evidence: Sequence[Any]) -> bool:
    return any(isinstance(item, Mapping) and item.get("blocking") is True for item in missing_evidence)


def _has_nonblocking_missing_evidence(candidates: Sequence[Mapping[str, Any]]) -> bool:
    for candidate in candidates:
        for item in _sequence(candidate.get("missing_evidence")):
            if isinstance(item, Mapping) and item.get("blocking") is not True:
                return True
    return False


def _nullable_mapping(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _load_json_mapping(path: Path, *, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComparisonProtocolError(f"{label} at {path} must be readable JSON.") from exc
    if not isinstance(payload, Mapping):
        raise ComparisonProtocolError(f"{label} at {path} must be a JSON object.")
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
        raise ComparisonProtocolError(f"{field_name} must be a non-empty string.")
    return text


def _path_string(path: Path) -> str:
    return Path(path).resolve(strict=False).as_posix()


def _finding(code: str, summary: str, *, candidate_id: str | None = None, severity: str | None = None) -> dict[str, Any]:
    finding = {
        "code": code,
        "severity": severity or ("blocking" if code in _HARD_FINDINGS else "partial"),
        "summary": summary,
    }
    if candidate_id:
        finding["candidate_id"] = candidate_id
    return finding


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    produce = subparsers.add_parser("produce", help="Produce CV4 validation artifacts from a comparison protocol input.")
    produce.add_argument("--input", type=Path, required=True)
    produce.add_argument("--output-dir", type=Path, required=True)

    example = subparsers.add_parser("example", help="Produce the CV4 comparison protocol MVP example artifacts.")
    example.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "produce":
        result = produce_comparison_protocol_artifacts_from_file(
            input_path=args.input,
            output_dir=args.output_dir,
        )
    else:
        result = produce_comparison_protocol_example_artifacts(output_dir=args.output_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] in {"accepted", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "COMPARISON_PROTOCOL_RECORD_KIND",
    "COMPARISON_PROTOCOL_SCHEMA_VERSION",
    "COMPARISON_PROTOCOL_VALIDATION_RECORD_KIND",
    "ComparisonProtocolError",
    "build_comparison_protocol",
    "build_comparison_protocol_mvp_example",
    "build_comparison_protocol_validation",
    "produce_comparison_protocol_artifacts",
    "produce_comparison_protocol_artifacts_from_file",
    "produce_comparison_protocol_example_artifacts",
]
