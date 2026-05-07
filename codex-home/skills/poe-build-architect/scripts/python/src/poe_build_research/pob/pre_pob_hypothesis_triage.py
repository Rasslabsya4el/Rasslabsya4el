"""Pre-PoB Hypothesis Triage utilities for bounded authored hypotheses.

This module is not an optimizer and does not run PoB. It validates that an
agent compared authored hypotheses before spending materializer or PoB
evaluation budget, and that unsupported or under-evidenced hypotheses are
rejected or blocked instead of silently selected.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .artifacts import write_json
from .release_manager import utc_now_iso

PRE_POB_HYPOTHESIS_TRIAGE_RECORD_KIND = "pre_pob_hypothesis_triage"
PRE_POB_HYPOTHESIS_TRIAGE_SCHEMA_VERSION = "0.1.0"
PRE_POB_HYPOTHESIS_TRIAGE_VALIDATION_RECORD_KIND = "pre_pob_hypothesis_triage_validation"

_VERDICTS = frozenset({"selected_for_measurement", "rejected_before_pob", "blocked", "pending"})
_TRIAGE_VERDICTS = frozenset({"measure", "reject", "blocked", "partial"})
_HARD_FINDINGS = frozenset(
    {
        "candidate_count_below_minimum",
        "hypothesis_id_duplicate",
        "selected_hypothesis_id_unknown",
        "rejected_hypothesis_id_unknown",
        "blocked_hypothesis_id_unknown",
        "hypothesis_expected_surfaces_missing",
        "hypothesis_estimated_resource_cost_missing",
        "selected_hypothesis_worth_pob_cost_reason_missing",
        "selected_hypothesis_has_unsupported_claim",
        "unsupported_claim_not_rejected_or_blocked",
        "selected_hypothesis_has_blocking_missing_evidence",
        "all_hypotheses_missing_critical_evidence",
    }
)


class PrePoBHypothesisTriageError(RuntimeError):
    """Raised when a Pre-PoB Hypothesis Triage input cannot be loaded."""


def build_pre_pob_hypothesis_triage(
    *,
    triage_id: str,
    decision_family: str,
    candidate_hypotheses: Sequence[Mapping[str, Any]],
    baseline_refs: Sequence[Mapping[str, Any]] | None = None,
    constraints: Mapping[str, Any] | None = None,
    selected_for_measurement: Sequence[str] | None = None,
    rejected_before_pob: Sequence[str] | None = None,
    blocked_hypotheses: Sequence[str] | None = None,
    reason: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build and validate one pre-PoB hypothesis triage record."""

    normalized = [_normalize_hypothesis(hypothesis) for hypothesis in candidate_hypotheses]
    selected_ids = _ids_or_verdict(selected_for_measurement, normalized, "selected_for_measurement")
    rejected_ids = _ids_or_verdict(rejected_before_pob, normalized, "rejected_before_pob")
    blocked_ids = _ids_or_verdict(blocked_hypotheses, normalized, "blocked")
    selected_rows = [_hypothesis_by_id(normalized, hypothesis_id) for hypothesis_id in selected_ids]
    record = {
        "schema_version": PRE_POB_HYPOTHESIS_TRIAGE_SCHEMA_VERSION,
        "record_kind": PRE_POB_HYPOTHESIS_TRIAGE_RECORD_KIND,
        "triage_id": _required_string(triage_id, "triage_id"),
        "generated_at": generated_at or utc_now_iso(),
        "decision_family": _required_string(decision_family, "decision_family"),
        "baseline_refs": [dict(_mapping(ref)) for ref in _sequence(baseline_refs)],
        "constraints": dict(_mapping(constraints)),
        "candidate_count": len(normalized),
        "candidate_hypotheses": normalized,
        "selected_for_measurement": selected_ids,
        "rejected_before_pob": rejected_ids,
        "blocked_hypotheses": blocked_ids,
        "expected_surfaces": _aggregate_expected_surfaces(selected_rows or normalized),
        "estimated_resource_cost": _aggregate_resource_cost(selected_rows),
        "expected_value_summary": _aggregate_expected_value(selected_rows),
        "risk_flags": _aggregate_risk_flags(normalized),
        "missing_evidence": _aggregate_missing_evidence(normalized),
        "triage_verdict": "blocked",
        "reason": _string(reason) or _default_reason(selected_ids, rejected_ids, blocked_ids),
        "validation": {
            "finding_count": 0,
            "findings": [],
        },
        "product_agent_behavioral_proof_required": False,
    }
    validation = build_pre_pob_hypothesis_triage_validation(record, generated_at=record["generated_at"])
    record["triage_verdict"] = validation["triage_verdict"]
    record["validation"] = {
        "finding_count": validation["finding_count"],
        "findings": list(validation["findings"]),
    }
    return record


def build_pre_pob_hypothesis_triage_validation(
    record: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic validation record for one triage artifact."""

    payload = _mapping(record)
    findings = _record_findings(payload)
    blocking = [finding for finding in findings if _string(finding.get("severity")) == "blocking"]
    partial = [finding for finding in findings if _string(finding.get("severity")) == "partial"]
    if blocking:
        status = "blocked"
    elif partial:
        status = "partial"
    else:
        status = "accepted"
    return {
        "schema_version": PRE_POB_HYPOTHESIS_TRIAGE_SCHEMA_VERSION,
        "record_kind": PRE_POB_HYPOTHESIS_TRIAGE_VALIDATION_RECORD_KIND,
        "triage_id": _string(payload.get("triage_id")) or "missing-triage-id",
        "generated_at": generated_at or utc_now_iso(),
        "status": status,
        "triage_verdict": _triage_verdict(payload, status=status, findings=findings),
        "finding_count": len(findings),
        "findings": findings,
        "product_agent_behavioral_proof_required": False,
        "scope_note": "CV5 validates pre-PoB authored hypothesis triage only; it is not a Direct Build proof or optimizer.",
    }


def build_pre_pob_hypothesis_triage_mvp_example(*, generated_at: str | None = None) -> dict[str, Any]:
    """Return the CV5 fixture with selected, rejected, and blocked hypotheses."""

    return build_pre_pob_hypothesis_triage(
        triage_id="cv5.pre-pob-hypothesis-triage.mvp",
        decision_family="direct_build.tree_pathing",
        baseline_refs=[
            {
                "ref_id": "fixture.cv5.baseline-tree",
                "evidence_kind": "source_ledger",
                "locator": "comparison-protocol.json",
                "json_pointer": "/comparison_basis",
                "summary": "Fixture baseline context from CV4 comparison protocol.",
            }
        ],
        constraints={
            "normal_passive_budget": 113,
            "full_dps_floor": 200000,
            "must_preserve": ["life_floor", "reservation_works", "attribute_requirements"],
        },
        candidate_hypotheses=_mvp_hypotheses(),
        selected_for_measurement=["hypothesis.nearby_dex_life_package"],
        rejected_before_pob=["hypothesis.distant_fire_cluster"],
        blocked_hypotheses=["hypothesis.unverified_keystone_swap"],
        reason=(
            "Measure the nearby Dex/life package first because it has bounded passive cost, expected "
            "constraint relief, and no unsupported claim; reject the distant package on static travel tax, "
            "and block the keystone swap until evidence exists."
        ),
        generated_at=generated_at or "2026-05-06T00:00:00Z",
    )


def produce_pre_pob_hypothesis_triage_artifacts(
    *,
    record: Mapping[str, Any],
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Write Pre-PoB Hypothesis Triage record and validation artifacts."""

    target_dir = Path(output_dir).resolve(strict=False)
    target_dir.mkdir(parents=True, exist_ok=True)
    generated = generated_at or utc_now_iso()
    payload = dict(record)
    validation = build_pre_pob_hypothesis_triage_validation(payload, generated_at=generated)
    payload["triage_verdict"] = validation["triage_verdict"]
    payload["validation"] = {
        "finding_count": validation["finding_count"],
        "findings": list(validation["findings"]),
    }
    record_path = write_json(target_dir / "pre-pob-hypothesis-triage.json", payload)
    validation_path = write_json(target_dir / "pre-pob-hypothesis-triage-validation.json", validation)
    return {
        "schema_version": PRE_POB_HYPOTHESIS_TRIAGE_SCHEMA_VERSION,
        "record_kind": "pre_pob_hypothesis_triage_production_result",
        "status": validation["status"],
        "triage_verdict": validation["triage_verdict"],
        "triage_id": _string(payload.get("triage_id")) or "missing-triage-id",
        "artifact_locators": {
            "record": _path_string(record_path),
            "validation": _path_string(validation_path),
        },
        "blockers": _validation_findings_as_blockers(validation),
        "product_agent_behavioral_proof_required": False,
    }


def produce_pre_pob_hypothesis_triage_example_artifacts(
    *,
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Write the CV5 pre-PoB triage example artifacts."""

    return produce_pre_pob_hypothesis_triage_artifacts(
        record=build_pre_pob_hypothesis_triage_mvp_example(generated_at=generated_at),
        output_dir=output_dir,
        generated_at=generated_at or "2026-05-06T00:00:00Z",
    )


def produce_pre_pob_hypothesis_triage_artifacts_from_file(
    *,
    input_path: Path,
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Load one triage record/input and produce validation artifacts."""

    payload = _load_json_mapping(Path(input_path), label="Pre-PoB Hypothesis Triage input")
    if _string(payload.get("record_kind")) == PRE_POB_HYPOTHESIS_TRIAGE_RECORD_KIND:
        record = payload
    else:
        record = build_pre_pob_hypothesis_triage(
            triage_id=_string(payload.get("triage_id")) or "pre-pob-hypothesis-triage",
            decision_family=_string(payload.get("decision_family")),
            baseline_refs=_sequence(payload.get("baseline_refs")),
            constraints=_mapping(payload.get("constraints")),
            candidate_hypotheses=_sequence(payload.get("candidate_hypotheses")),
            selected_for_measurement=[_string(value) for value in _sequence(payload.get("selected_for_measurement"))],
            rejected_before_pob=[_string(value) for value in _sequence(payload.get("rejected_before_pob"))],
            blocked_hypotheses=[_string(value) for value in _sequence(payload.get("blocked_hypotheses"))],
            reason=_string(payload.get("reason")) or None,
            generated_at=generated_at,
        )
    return produce_pre_pob_hypothesis_triage_artifacts(
        record=record,
        output_dir=output_dir,
        generated_at=generated_at,
    )


def _mvp_hypotheses() -> list[dict[str, Any]]:
    return [
        _hypothesis(
            hypothesis_id="hypothesis.nearby_dex_life_package",
            label="Nearby Dex/life pathing package",
            verdict="selected_for_measurement",
            reason="Bounded route with likely constraint relief and acceptable passive cost.",
            worth_pob_cost_reason="Worth measuring because the expected Dex repair can unlock support and item choices while spending only four passives.",
            total_passive_points=4,
            expected_metric="LifeAndDexRequirement",
            expected_direction="repair",
            expected_value="Medium DPS-adjacent value plus attribute constraint relief.",
            risk_flags=(
                {
                    "risk_id": "risk.cv5.nearby-dex.low-raw-dps",
                    "severity": "medium",
                    "summary": "May look worse than a pure DPS package if constraint relief is undervalued.",
                },
            ),
            missing_evidence=(),
            unsupported_claims=(),
        ),
        _hypothesis(
            hypothesis_id="hypothesis.distant_fire_cluster",
            label="Distant fire cluster route",
            verdict="rejected_before_pob",
            reason="Rejected before PoB because CV3-style travel tax is too high for the expected payoff.",
            worth_pob_cost_reason="Not worth PoB cost in this pass; measure later only if closer packages fail.",
            total_passive_points=8,
            expected_metric="FullDPS",
            expected_direction="increase",
            expected_value="Higher raw DPS upside, but poor value per passive after travel.",
            risk_flags=(
                {
                    "risk_id": "risk.cv5.distant-fire.travel-tax",
                    "severity": "high",
                    "summary": "Five travel points may crowd out life and requirement repairs.",
                },
            ),
            missing_evidence=(),
            unsupported_claims=(),
        ),
        _hypothesis(
            hypothesis_id="hypothesis.unverified_keystone_swap",
            label="Unverified keystone swap",
            verdict="blocked",
            reason="Blocked because the claimed synergy is unsupported and could invert defenses.",
            worth_pob_cost_reason="Not worth PoB cost until mechanic evidence or a prior measured diff supports the claim.",
            total_passive_points=3,
            expected_metric="FullDPSAndDefenseTradeoff",
            expected_direction="unknown",
            expected_value="Potential high upside, but no supported mechanic evidence is attached.",
            risk_flags=(
                {
                    "risk_id": "risk.cv5.keystone.defense-inversion",
                    "severity": "high",
                    "summary": "Could break an implicit defensive assumption.",
                },
            ),
            missing_evidence=(
                {
                    "evidence_kind": "mechanic_evidence",
                    "reason": "No supported reference proves the keystone interaction applies to this build.",
                    "blocking": True,
                },
            ),
            unsupported_claims=(
                {
                    "claim_id": "claim.cv5.keystone-double-dips-fireball",
                    "summary": "Claims an unverified double-dip interaction.",
                    "required_evidence": "mechanic_evidence or measured calc diff before selection.",
                },
            ),
        ),
    ]


def _hypothesis(
    *,
    hypothesis_id: str,
    label: str,
    verdict: str,
    reason: str,
    worth_pob_cost_reason: str,
    total_passive_points: int,
    expected_metric: str,
    expected_direction: str,
    expected_value: str,
    risk_flags: Sequence[Mapping[str, Any]],
    missing_evidence: Sequence[Mapping[str, Any]],
    unsupported_claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "hypothesis_id": hypothesis_id,
        "label": label,
        "candidate_action": {
            "action_scope": "tree",
            "action_type": "pathing_package",
            "summary": label,
        },
        "expected_surfaces": [
            {
                "surface_kind": "tree_state",
                "metric_key": "normal_passive_count",
                "expected_direction": "increase",
                "note": "Hypothesis consumes passive budget before any PoB measurement.",
            },
            {
                "surface_kind": "calc_surface",
                "metric_key": expected_metric,
                "expected_direction": expected_direction,
                "note": "Authored expected surface for pre-PoB triage.",
            },
        ],
        "estimated_resource_cost": {
            "total_passive_points": total_passive_points,
            "travel_points": max(0, total_passive_points - 3),
            "payoff_points": min(3, total_passive_points),
            "summary": f"{total_passive_points} passive points before PoB measurement.",
        },
        "expected_value_summary": {
            "value_level": "medium" if verdict != "blocked" else "unknown",
            "summary": expected_value,
        },
        "risk_flags": [dict(item) for item in risk_flags],
        "missing_evidence": [dict(item) for item in missing_evidence],
        "unsupported_claims": [dict(item) for item in unsupported_claims],
        "evidence_refs": [
            {
                "ref_id": f"evidence.cv5.{hypothesis_id}.comparison",
                "evidence_kind": "comparison_protocol",
                "locator": "comparison-protocol.json",
                "json_pointer": "/candidates",
                "summary": "CV4 fixture comparison context for authored alternatives.",
            }
        ],
        "triage_verdict": verdict,
        "reason": reason,
        "worth_pob_cost_reason": worth_pob_cost_reason,
        "uncertainty": {
            "level": "medium" if verdict != "blocked" else "high",
            "notes": [
                "CV5 triage is static pre-PoB selection pressure and does not claim measured improvement.",
            ],
        },
    }


def _normalize_hypothesis(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = _mapping(value)
    hypothesis_id = _required_string(payload.get("hypothesis_id"), "candidate_hypotheses[].hypothesis_id")
    verdict = _string(payload.get("triage_verdict")) or _string(payload.get("verdict")) or "pending"
    if verdict not in _VERDICTS:
        raise PrePoBHypothesisTriageError(f"{hypothesis_id}.triage_verdict is invalid.")
    return {
        "hypothesis_id": hypothesis_id,
        "label": _required_string(payload.get("label"), f"{hypothesis_id}.label"),
        "candidate_action": dict(_mapping(payload.get("candidate_action"))),
        "expected_surfaces": [dict(_mapping(item)) for item in _sequence(payload.get("expected_surfaces"))],
        "estimated_resource_cost": dict(_mapping(payload.get("estimated_resource_cost"))),
        "expected_value_summary": dict(_mapping(payload.get("expected_value_summary"))),
        "risk_flags": [dict(_mapping(item)) for item in _sequence(payload.get("risk_flags"))],
        "missing_evidence": [dict(_mapping(item)) for item in _sequence(payload.get("missing_evidence"))],
        "unsupported_claims": [dict(_mapping(item)) for item in _sequence(payload.get("unsupported_claims"))],
        "evidence_refs": [dict(_mapping(item)) for item in _sequence(payload.get("evidence_refs"))],
        "triage_verdict": verdict,
        "reason": _string(payload.get("reason")),
        "worth_pob_cost_reason": _string(payload.get("worth_pob_cost_reason")),
        "uncertainty": dict(_mapping(payload.get("uncertainty"))) or {
            "level": "unknown",
            "notes": ["No uncertainty note supplied."],
        },
    }


def _record_findings(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if _string(record.get("record_kind")) != PRE_POB_HYPOTHESIS_TRIAGE_RECORD_KIND:
        findings.append(_finding("record_kind_invalid", "record_kind must be pre_pob_hypothesis_triage."))
    hypotheses = [_mapping(hypothesis) for hypothesis in _sequence(record.get("candidate_hypotheses"))]
    if len(hypotheses) < 2:
        findings.append(_finding("candidate_count_below_minimum", "Pre-PoB triage requires at least two candidate hypotheses."))
    hypothesis_ids = [_string(hypothesis.get("hypothesis_id")) for hypothesis in hypotheses]
    if len([hypothesis_id for hypothesis_id in hypothesis_ids if hypothesis_id]) != len(set(hypothesis_id for hypothesis_id in hypothesis_ids if hypothesis_id)):
        findings.append(_finding("hypothesis_id_duplicate", "candidate_hypotheses[].hypothesis_id values must be unique."))
    selected_ids = [_string(value) for value in _sequence(record.get("selected_for_measurement")) if _string(value)]
    rejected_ids = [_string(value) for value in _sequence(record.get("rejected_before_pob")) if _string(value)]
    blocked_ids = [_string(value) for value in _sequence(record.get("blocked_hypotheses")) if _string(value)]
    id_set = set(hypothesis_ids)
    findings.extend(_unknown_id_findings(selected_ids, id_set, code="selected_hypothesis_id_unknown"))
    findings.extend(_unknown_id_findings(rejected_ids, id_set, code="rejected_hypothesis_id_unknown"))
    findings.extend(_unknown_id_findings(blocked_ids, id_set, code="blocked_hypothesis_id_unknown"))
    if not selected_ids and not rejected_ids and not blocked_ids:
        findings.append(_finding("triage_bucket_missing", "Triage must select, reject, or block at least one hypothesis.", severity="partial"))
    for hypothesis in hypotheses:
        findings.extend(_hypothesis_findings(hypothesis, selected_ids=selected_ids))
    if hypotheses and all(_has_blocking_missing_evidence(_sequence(hypothesis.get("missing_evidence"))) for hypothesis in hypotheses):
        findings.append(
            _finding(
                "all_hypotheses_missing_critical_evidence",
                "All hypotheses are missing critical evidence, so triage cannot measure.",
            )
        )
    return findings


def _hypothesis_findings(hypothesis: Mapping[str, Any], *, selected_ids: Sequence[str]) -> list[dict[str, Any]]:
    hypothesis_id = _string(hypothesis.get("hypothesis_id")) or "missing-hypothesis-id"
    verdict = _string(hypothesis.get("triage_verdict")) or "pending"
    selected = hypothesis_id in selected_ids or verdict == "selected_for_measurement"
    findings: list[dict[str, Any]] = []
    if not _sequence(hypothesis.get("expected_surfaces")):
        findings.append(_finding("hypothesis_expected_surfaces_missing", "Each hypothesis requires expected_surfaces.", hypothesis_id=hypothesis_id))
    if not _mapping(hypothesis.get("estimated_resource_cost")):
        findings.append(_finding("hypothesis_estimated_resource_cost_missing", "Each hypothesis requires estimated_resource_cost.", hypothesis_id=hypothesis_id))
    unsupported_claims = _sequence(hypothesis.get("unsupported_claims"))
    if unsupported_claims and selected:
        findings.append(_finding("selected_hypothesis_has_unsupported_claim", "Unsupported claims cannot be selected for measurement.", hypothesis_id=hypothesis_id))
    if unsupported_claims and verdict not in {"rejected_before_pob", "blocked"}:
        findings.append(_finding("unsupported_claim_not_rejected_or_blocked", "Unsupported claims must be rejected before PoB or blocked.", hypothesis_id=hypothesis_id))
    if selected and not _string(hypothesis.get("worth_pob_cost_reason")):
        findings.append(_finding("selected_hypothesis_worth_pob_cost_reason_missing", "Selected hypotheses must explain why they are worth PoB cost.", hypothesis_id=hypothesis_id))
    if selected and _has_blocking_missing_evidence(_sequence(hypothesis.get("missing_evidence"))):
        findings.append(_finding("selected_hypothesis_has_blocking_missing_evidence", "Selected hypotheses cannot have blocking missing evidence.", hypothesis_id=hypothesis_id))
    if _has_nonblocking_missing_evidence(_sequence(hypothesis.get("missing_evidence"))):
        findings.append(_finding("hypothesis_has_nonblocking_missing_evidence", "Non-blocking missing evidence makes the triage partial.", hypothesis_id=hypothesis_id, severity="partial"))
    if not _string(hypothesis.get("reason")):
        findings.append(_finding("hypothesis_reason_missing", "Hypothesis triage reason is missing.", hypothesis_id=hypothesis_id, severity="partial"))
    return findings


def _triage_verdict(record: Mapping[str, Any], *, status: str, findings: Sequence[Mapping[str, Any]]) -> str:
    if status == "blocked":
        return "blocked"
    if status == "partial":
        return "partial"
    selected = _sequence(record.get("selected_for_measurement"))
    blocked = _sequence(record.get("blocked_hypotheses"))
    if selected:
        return "measure"
    if blocked and len(blocked) == _number_or_zero(record.get("candidate_count")):
        return "blocked"
    if _sequence(record.get("rejected_before_pob")):
        return "reject"
    existing = _string(record.get("triage_verdict"))
    if existing in _TRIAGE_VERDICTS:
        return existing
    if findings:
        return "partial"
    return "blocked"


def _ids_or_verdict(
    explicit_ids: Sequence[str] | None,
    hypotheses: Sequence[Mapping[str, Any]],
    verdict: str,
) -> list[str]:
    ids = [_string(value) for value in _sequence(explicit_ids) if _string(value)]
    if ids:
        return ids
    return [
        _string(hypothesis.get("hypothesis_id"))
        for hypothesis in hypotheses
        if _string(hypothesis.get("triage_verdict")) == verdict
    ]


def _aggregate_expected_surfaces(hypotheses: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for hypothesis in hypotheses:
        hypothesis_id = _string(hypothesis.get("hypothesis_id"))
        for surface in _sequence(hypothesis.get("expected_surfaces")):
            payload = dict(_mapping(surface))
            key = (
                _string(payload.get("surface_kind")),
                _string(payload.get("metric_key")),
                _string(payload.get("expected_direction")),
                _string(payload.get("note")),
            )
            if key in seen:
                continue
            seen.add(key)
            payload["hypothesis_id"] = hypothesis_id
            surfaces.append(payload)
    return surfaces


def _aggregate_resource_cost(hypotheses: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "selected_hypotheses": [
            {
                "hypothesis_id": _string(hypothesis.get("hypothesis_id")),
                "estimated_resource_cost": dict(_mapping(hypothesis.get("estimated_resource_cost"))),
            }
            for hypothesis in hypotheses
        ],
        "summary": f"{len(hypotheses)} hypotheses selected for measurement.",
    }


def _aggregate_expected_value(hypotheses: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "selected_hypotheses": [
            {
                "hypothesis_id": _string(hypothesis.get("hypothesis_id")),
                "expected_value_summary": dict(_mapping(hypothesis.get("expected_value_summary"))),
            }
            for hypothesis in hypotheses
        ],
        "summary": "Selected hypotheses have static expected value only; measured value belongs in Calc Snapshot Diff after PoB.",
    }


def _aggregate_risk_flags(hypotheses: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        hypothesis_id = _string(hypothesis.get("hypothesis_id"))
        for flag in _sequence(hypothesis.get("risk_flags")):
            payload = dict(_mapping(flag))
            payload["hypothesis_id"] = hypothesis_id
            flags.append(payload)
    return flags


def _aggregate_missing_evidence(hypotheses: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        hypothesis_id = _string(hypothesis.get("hypothesis_id"))
        for item in _sequence(hypothesis.get("missing_evidence")):
            payload = dict(_mapping(item))
            payload["hypothesis_id"] = hypothesis_id
            missing.append(payload)
    return missing


def _unknown_id_findings(ids: Sequence[str], known_ids: set[str], *, code: str) -> list[dict[str, Any]]:
    return [
        _finding(code, f"{hypothesis_id} does not match a candidate hypothesis.", hypothesis_id=hypothesis_id)
        for hypothesis_id in ids
        if hypothesis_id not in known_ids
    ]


def _validation_findings_as_blockers(validation: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "blocker_id": _string(finding.get("code")) or "pre_pob_triage_finding",
            "severity": _string(finding.get("severity")) or "blocking",
            "summary": _string(finding.get("summary")) or "Pre-PoB Hypothesis Triage finding.",
            "unblock_condition": "Repair candidate count, expected surfaces, resource cost, evidence accounting, or selected hypothesis reason.",
        }
        for finding in _sequence(validation.get("findings"))
        if isinstance(finding, Mapping)
    ]


def _default_reason(selected_ids: Sequence[str], rejected_ids: Sequence[str], blocked_ids: Sequence[str]) -> str:
    return (
        f"Pre-PoB triage selected {len(selected_ids)}, rejected {len(rejected_ids)}, "
        f"and blocked {len(blocked_ids)} authored hypotheses."
    )


def _hypothesis_by_id(hypotheses: Sequence[Mapping[str, Any]], hypothesis_id: str) -> Mapping[str, Any]:
    for hypothesis in hypotheses:
        if _string(hypothesis.get("hypothesis_id")) == hypothesis_id:
            return hypothesis
    return {}


def _has_blocking_missing_evidence(missing_evidence: Sequence[Any]) -> bool:
    return any(isinstance(item, Mapping) and item.get("blocking") is True for item in missing_evidence)


def _has_nonblocking_missing_evidence(missing_evidence: Sequence[Any]) -> bool:
    return any(isinstance(item, Mapping) and item.get("blocking") is not True for item in missing_evidence)


def _load_json_mapping(path: Path, *, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PrePoBHypothesisTriageError(f"{label} at {path} must be readable JSON.") from exc
    if not isinstance(payload, Mapping):
        raise PrePoBHypothesisTriageError(f"{label} at {path} must be a JSON object.")
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
        raise PrePoBHypothesisTriageError(f"{field_name} must be a non-empty string.")
    return text


def _number_or_zero(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _path_string(path: Path) -> str:
    return Path(path).resolve(strict=False).as_posix()


def _finding(
    code: str,
    summary: str,
    *,
    hypothesis_id: str | None = None,
    severity: str | None = None,
) -> dict[str, Any]:
    finding = {
        "code": code,
        "severity": severity or ("blocking" if code in _HARD_FINDINGS else "partial"),
        "summary": summary,
    }
    if hypothesis_id:
        finding["hypothesis_id"] = hypothesis_id
    return finding


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    produce = subparsers.add_parser("produce", help="Produce CV5 validation artifacts from triage input.")
    produce.add_argument("--input", type=Path, required=True)
    produce.add_argument("--output-dir", type=Path, required=True)

    example = subparsers.add_parser("example", help="Produce the CV5 pre-PoB triage MVP example artifacts.")
    example.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "produce":
        result = produce_pre_pob_hypothesis_triage_artifacts_from_file(
            input_path=args.input,
            output_dir=args.output_dir,
        )
    else:
        result = produce_pre_pob_hypothesis_triage_example_artifacts(output_dir=args.output_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] in {"accepted", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PRE_POB_HYPOTHESIS_TRIAGE_RECORD_KIND",
    "PRE_POB_HYPOTHESIS_TRIAGE_SCHEMA_VERSION",
    "PRE_POB_HYPOTHESIS_TRIAGE_VALIDATION_RECORD_KIND",
    "PrePoBHypothesisTriageError",
    "build_pre_pob_hypothesis_triage",
    "build_pre_pob_hypothesis_triage_mvp_example",
    "build_pre_pob_hypothesis_triage_validation",
    "produce_pre_pob_hypothesis_triage_artifacts",
    "produce_pre_pob_hypothesis_triage_artifacts_from_file",
    "produce_pre_pob_hypothesis_triage_example_artifacts",
]
