"""Surface Impact Classification utilities for bounded PoB action evidence.

This module classifies already-authored expected surfaces and already-measured
Calc Snapshot Diff surfaces into impact categories. It is not a scorer,
optimizer, passive tree solver, or PoB runner.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .artifacts import write_json
from .calc_snapshot_diff import build_calc_snapshot_diff_mvp_example
from .release_manager import utc_now_iso

SURFACE_IMPACT_CLASSIFICATION_RECORD_KIND = "surface_impact_classification"
SURFACE_IMPACT_CLASSIFICATION_SCHEMA_VERSION = "0.1.0"
SURFACE_IMPACT_CLASSIFICATION_VALIDATION_RECORD_KIND = "surface_impact_classification_validation"

_IMPACT_CATEGORIES = frozenset(
    {
        "offense",
        "defense",
        "quality_of_life",
        "sustain",
        "requirement_relief",
        "reservation",
        "usability",
        "progression_friction",
        "regression",
        "unknown",
        "missing_evidence",
    }
)
_MEASUREMENT_MODES = frozenset({"measured", "expected", "mixed"})
_PRIMARY_PRIORITY = (
    "requirement_relief",
    "offense",
    "defense",
    "reservation",
    "sustain",
    "quality_of_life",
    "usability",
    "progression_friction",
    "regression",
    "unknown",
    "missing_evidence",
)


class SurfaceImpactClassificationError(RuntimeError):
    """Raised when a Surface Impact Classification input cannot be loaded."""


def build_surface_impact_classification(
    *,
    classification_id: str,
    calc_diff: Mapping[str, Any] | None = None,
    action_ledger: Mapping[str, Any] | None = None,
    expected_surfaces: Sequence[Mapping[str, Any]] | None = None,
    action_refs: Sequence[str] | None = None,
    comparison_refs: Sequence[str] | None = None,
    calc_diff_refs: Sequence[str] | None = None,
    evidence_refs: Sequence[Mapping[str, Any]] | None = None,
    classification_reason: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Classify expected and measured surfaces into bounded impact categories."""

    calc_payload = _mapping(calc_diff)
    ledger_payload = _mapping(action_ledger)
    calc_surfaces = _calc_diff_surfaces(calc_payload)
    ledger_surfaces = _ledger_expected_surfaces(ledger_payload)
    explicit_surfaces = _explicit_expected_surfaces(expected_surfaces)
    missing_surfaces = _missing_metric_surfaces(calc_payload)
    impacted = [
        _classify_surface(surface)
        for surface in [*calc_surfaces, *ledger_surfaces, *explicit_surfaces, *missing_surfaces]
    ]
    categories = _category_list(impacted)
    primary = _primary_impact(categories, impacted)
    generated = generated_at or utc_now_iso()
    record = {
        "schema_version": SURFACE_IMPACT_CLASSIFICATION_SCHEMA_VERSION,
        "record_kind": SURFACE_IMPACT_CLASSIFICATION_RECORD_KIND,
        "classification_id": _required_string(classification_id, "classification_id"),
        "generated_at": generated,
        "status": "blocked",
        "action_refs": _merge_strings(action_refs, _sequence(calc_payload.get("action_refs")), _ledger_action_refs(ledger_payload)),
        "comparison_refs": [_required_string(value, "comparison_refs[]") for value in _sequence(comparison_refs)],
        "calc_diff_refs": _merge_strings(
            calc_diff_refs,
            [_string(calc_payload.get("diff_id"))] if _string(calc_payload.get("diff_id")) else [],
        ),
        "impacted_surfaces": impacted,
        "impact_categories": categories,
        "primary_impact": primary,
        "secondary_impacts": [category for category in categories if category != primary],
        "measured_or_expected": _measured_or_expected(impacted),
        "evidence_refs": _normalize_evidence_refs(
            evidence_refs,
            calc_diff=calc_payload,
            action_ledger=ledger_payload,
        ),
        "classification_reason": _string(classification_reason) or _default_reason(primary, categories, impacted),
        "uncertainty": _uncertainty(impacted),
        "missing_evidence": _missing_evidence(impacted),
        "validation": {
            "finding_count": 0,
            "findings": [],
        },
        "product_agent_behavioral_proof_required": False,
    }
    validation = build_surface_impact_classification_validation(record, generated_at=generated)
    record["status"] = validation["status"]
    record["validation"] = {
        "finding_count": validation["finding_count"],
        "findings": list(validation["findings"]),
    }
    return record


def build_surface_impact_classification_validation(
    record: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic validation record for one classification artifact."""

    payload = _mapping(record)
    findings = _record_findings(payload)
    return {
        "schema_version": SURFACE_IMPACT_CLASSIFICATION_SCHEMA_VERSION,
        "record_kind": SURFACE_IMPACT_CLASSIFICATION_VALIDATION_RECORD_KIND,
        "classification_id": _string(payload.get("classification_id")) or "missing-classification-id",
        "generated_at": generated_at or utc_now_iso(),
        "status": "accepted" if not findings else "not_accepted",
        "finding_count": len(findings),
        "findings": findings,
        "product_agent_behavioral_proof_required": False,
        "scope_note": "CV6 validates surface impact classification only; it is not a Direct Build proof or scoring engine.",
    }


def build_surface_impact_classification_mvp_example(*, generated_at: str | None = None) -> dict[str, Any]:
    """Return a fixture covering offense, QoL, requirement relief, regression, and unknown."""

    return build_surface_impact_classification(
        classification_id="cv6.surface-impact-classification.mvp",
        calc_diff=build_calc_snapshot_diff_mvp_example(generated_at=generated_at or "2026-05-06T00:00:00Z"),
        expected_surfaces=[
            {
                "surface_kind": "constraint",
                "metric_key": "dexterity_requirement_shortfall",
                "expected_direction": "repair",
                "note": "Expected Dex requirement relief before measurement.",
                "source_ref_id": "cv5.hypothesis.nearby_dex_life_package",
            },
            {
                "surface_kind": "calc_surface",
                "metric_key": "UnmappedMysteryValue",
                "expected_direction": "unknown",
                "note": "Fixture unknown metric must remain unknown, not invented value.",
                "source_ref_id": "cv6.fixture.unknown",
            },
        ],
        action_refs=("tree_pathing.rt_package",),
        comparison_refs=("cv4.comparison-protocol.tree-pathing.mvp",),
        calc_diff_refs=("cv2.calc-snapshot-diff.mvp",),
        evidence_refs=[
            {
                "ref_id": "cv6.evidence.pre-pob-triage",
                "evidence_kind": "pre_pob_triage",
                "locator": "pre-pob-hypothesis-triage.json",
                "json_pointer": "/candidate_hypotheses",
                "summary": "CV5 fixture supplies expected requirement relief and blocked unknown evidence context.",
            }
        ],
        classification_reason=(
            "Classified measured DPS and radius gains plus expected requirement relief while keeping "
            "defensive/resource losses as regressions and unmapped metrics as unknown."
        ),
        generated_at=generated_at or "2026-05-06T00:00:00Z",
    )


def produce_surface_impact_classification_artifacts(
    *,
    record: Mapping[str, Any],
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Write Surface Impact Classification record and validation artifacts."""

    target_dir = Path(output_dir).resolve(strict=False)
    target_dir.mkdir(parents=True, exist_ok=True)
    generated = generated_at or utc_now_iso()
    payload = dict(record)
    validation = build_surface_impact_classification_validation(payload, generated_at=generated)
    payload["status"] = validation["status"]
    payload["validation"] = {
        "finding_count": validation["finding_count"],
        "findings": list(validation["findings"]),
    }
    record_path = write_json(target_dir / "surface-impact-classification.json", payload)
    validation_path = write_json(target_dir / "surface-impact-classification-validation.json", validation)
    return {
        "schema_version": SURFACE_IMPACT_CLASSIFICATION_SCHEMA_VERSION,
        "record_kind": "surface_impact_classification_production_result",
        "status": validation["status"],
        "classification_id": _string(payload.get("classification_id")) or "missing-classification-id",
        "artifact_locators": {
            "record": _path_string(record_path),
            "validation": _path_string(validation_path),
        },
        "blockers": _validation_findings_as_blockers(validation),
        "product_agent_behavioral_proof_required": False,
    }


def produce_surface_impact_classification_example_artifacts(
    *,
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Write the CV6 surface impact classification example artifacts."""

    return produce_surface_impact_classification_artifacts(
        record=build_surface_impact_classification_mvp_example(generated_at=generated_at),
        output_dir=output_dir,
        generated_at=generated_at or "2026-05-06T00:00:00Z",
    )


def produce_surface_impact_classification_artifacts_from_file(
    *,
    input_path: Path,
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Load a classification record/input and produce CV6 artifacts."""

    payload = _load_json_mapping(Path(input_path), label="Surface Impact Classification input")
    if _string(payload.get("record_kind")) == SURFACE_IMPACT_CLASSIFICATION_RECORD_KIND:
        record = payload
    else:
        record = build_surface_impact_classification(
            classification_id=_string(payload.get("classification_id")) or "surface-impact-classification",
            calc_diff=_mapping(payload.get("calc_diff")),
            action_ledger=_mapping(payload.get("action_ledger")),
            expected_surfaces=_sequence(payload.get("expected_surfaces")),
            action_refs=[_string(value) for value in _sequence(payload.get("action_refs"))],
            comparison_refs=[_string(value) for value in _sequence(payload.get("comparison_refs"))],
            calc_diff_refs=[_string(value) for value in _sequence(payload.get("calc_diff_refs"))],
            evidence_refs=[_mapping(value) for value in _sequence(payload.get("evidence_refs"))],
            classification_reason=_string(payload.get("classification_reason")) or None,
            generated_at=generated_at,
        )
    return produce_surface_impact_classification_artifacts(
        record=record,
        output_dir=output_dir,
        generated_at=generated_at,
    )


def _calc_diff_surfaces(calc_diff: Mapping[str, Any]) -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    diff_id = _string(calc_diff.get("diff_id"))
    for row in _sequence(calc_diff.get("changed_surfaces")):
        payload = dict(_mapping(row))
        payload["source_kind"] = "calc_snapshot_diff"
        payload["source_ref_id"] = diff_id or _string(payload.get("evidence_ref_id")) or "calc_diff"
        payload["measured_or_expected"] = "measured"
        surfaces.append(payload)
    return surfaces


def _missing_metric_surfaces(calc_diff: Mapping[str, Any]) -> list[dict[str, Any]]:
    diff_id = _string(calc_diff.get("diff_id"))
    surfaces: list[dict[str, Any]] = []
    for row in _sequence(calc_diff.get("missing_metrics")):
        payload = dict(_mapping(row))
        payload["surface_id"] = _string(payload.get("metric_key")) or "missing_metric"
        payload["direction"] = "unknown"
        payload["classification"] = "missing_metric"
        payload["source_kind"] = "calc_snapshot_diff_missing_metric"
        payload["source_ref_id"] = diff_id or "calc_diff_missing_metric"
        payload["measured_or_expected"] = "measured"
        surfaces.append(payload)
    return surfaces


def _ledger_expected_surfaces(action_ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    for row in _sequence(action_ledger.get("rows")):
        if not isinstance(row, Mapping):
            continue
        action_id = _string(row.get("action_id"))
        for surface in _sequence(row.get("expected_surfaces")):
            payload = dict(_mapping(surface))
            payload["source_kind"] = "action_cost_value_ledger"
            payload["source_ref_id"] = action_id or _string(action_ledger.get("ledger_id")) or "action_ledger"
            payload["measured_or_expected"] = "expected"
            surfaces.append(payload)
    return surfaces


def _explicit_expected_surfaces(expected_surfaces: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    for index, surface in enumerate(_sequence(expected_surfaces)):
        payload = dict(_mapping(surface))
        payload["source_kind"] = _string(payload.get("source_kind")) or "expected_surface_input"
        payload["source_ref_id"] = _string(payload.get("source_ref_id")) or f"expected_surface.{index}"
        payload["measured_or_expected"] = "expected"
        surfaces.append(payload)
    return surfaces


def _classify_surface(surface: Mapping[str, Any]) -> dict[str, Any]:
    payload = _mapping(surface)
    metric_key = _string(payload.get("metric_key")) or _string(payload.get("surface_id")) or "unknown_metric"
    categories = _categories_for_surface(payload)
    if not categories:
        categories = ["unknown"]
    reason = _surface_reason(metric_key, categories, payload)
    return {
        "surface_ref_id": _string(payload.get("evidence_ref_id")) or _string(payload.get("source_ref_id")) or metric_key,
        "source_kind": _string(payload.get("source_kind")) or "unknown",
        "source_ref_id": _string(payload.get("source_ref_id")) or None,
        "surface_id": _string(payload.get("surface_id")) or metric_key,
        "surface_kind": _string(payload.get("surface_kind")) or "unknown",
        "metric_key": metric_key,
        "direction": _string(payload.get("direction")) or _string(payload.get("expected_direction")) or "unknown",
        "measured_or_expected": _normalize_measurement_mode(_string(payload.get("measured_or_expected"))),
        "impact_categories": categories,
        "is_regression": "regression" in categories,
        "baseline_value": payload.get("baseline_value"),
        "after_value": payload.get("after_value"),
        "absolute_delta": payload.get("absolute_delta"),
        "percent_delta": payload.get("percent_delta"),
        "classification_source": {
            "calc_classification": _string(payload.get("classification")) or None,
            "expected_direction": _string(payload.get("expected_direction")) or None,
        },
        "classification_reason": reason,
    }


def _categories_for_surface(surface: Mapping[str, Any]) -> list[str]:
    metric = _surface_text(surface)
    direction = _string(surface.get("direction")) or _string(surface.get("expected_direction"))
    calc_classification = _string(surface.get("classification")).lower()
    categories: list[str] = []

    if "missing_metric" in calc_classification or _string(surface.get("source_kind")) == "calc_snapshot_diff_missing_metric":
        return ["missing_evidence", "unknown"]
    if _has_any(metric, ("fulldps", "combineddps", "averagedps", "averagedhit", "averagehit", "dps", "damage", "castrate", "cast_rate")):
        categories.append("offense")
    if _has_any(metric, ("radius", "areaofeffect", "area_of_effect", "area", "aoe", "speed", "castrate", "cast_rate")):
        categories.append("quality_of_life")
    if _has_any(metric, ("life", "energyshield", "energy_shield", "total_ehp", "totalehp", "ehp", "resist", "resistance", "maxhit", "armour", "armor", "evasion", "suppression", "block", "warning")):
        categories.append("defense")
    if _has_any(metric, ("recovery", "regen", "leech", "recoup", "life_on_hit", "mana_cost", "cost")):
        categories.append("sustain")
    if _has_any(metric, ("reserved", "unreserved", "reservation")):
        categories.extend(["reservation", "usability"])
    if _has_any(metric, ("requirement", "shortfall", "reqstr", "reqdex", "reqint", "strength", "dexterity", "intelligence", "omniscience")):
        if direction in {"repair", "decrease"} or "requirement_repair" in calc_classification:
            categories.append("requirement_relief")
        else:
            categories.extend(["usability", "progression_friction"])
    if _has_any(metric, ("travel", "passive", "respec", "regret", "budget", "craft", "trade", "item_churn")):
        categories.append("progression_friction")
    if _is_regression(surface):
        categories.append("regression")
    return _dedupe_categories(categories)


def _is_regression(surface: Mapping[str, Any]) -> bool:
    calc_classification = _string(surface.get("classification")).lower()
    direction = _string(surface.get("direction"))
    expected_direction = _string(surface.get("expected_direction"))
    if "requirement_repair" in calc_classification:
        return False
    if any(token in calc_classification for token in ("loss", "regression", "pressure", "warning_added")):
        return True
    if expected_direction in {"decrease"} and _categories_without_regression(surface):
        return True
    if direction in {"decrease", "added"} and _known_surface_without_regression(surface):
        return True
    return False


def _categories_without_regression(surface: Mapping[str, Any]) -> list[str]:
    copy = dict(surface)
    copy["classification"] = ""
    return [category for category in _categories_for_surface_no_regression(copy) if category != "regression"]


def _known_surface_without_regression(surface: Mapping[str, Any]) -> bool:
    return bool(_categories_without_regression(surface))


def _categories_for_surface_no_regression(surface: Mapping[str, Any]) -> list[str]:
    metric = _surface_text(surface)
    categories: list[str] = []
    if _has_any(metric, ("fulldps", "combineddps", "averagedps", "averagedhit", "averagehit", "dps", "damage", "castrate", "cast_rate")):
        categories.append("offense")
    if _has_any(metric, ("radius", "areaofeffect", "area_of_effect", "area", "aoe", "speed", "castrate", "cast_rate")):
        categories.append("quality_of_life")
    if _has_any(metric, ("life", "energyshield", "energy_shield", "total_ehp", "totalehp", "ehp", "resist", "resistance", "maxhit", "armour", "armor", "evasion", "suppression", "block", "warning")):
        categories.append("defense")
    if _has_any(metric, ("recovery", "regen", "leech", "recoup", "life_on_hit", "mana_cost", "cost")):
        categories.append("sustain")
    if _has_any(metric, ("reserved", "unreserved", "reservation")):
        categories.extend(["reservation", "usability"])
    if _has_any(metric, ("requirement", "shortfall", "reqstr", "reqdex", "reqint", "strength", "dexterity", "intelligence", "omniscience")):
        categories.extend(["requirement_relief", "usability"])
    if _has_any(metric, ("travel", "passive", "respec", "regret", "budget", "craft", "trade", "item_churn")):
        categories.append("progression_friction")
    return _dedupe_categories(categories)


def _surface_text(surface: Mapping[str, Any]) -> str:
    parts = (
        _string(surface.get("metric_key")),
        _string(surface.get("surface_id")),
        _string(surface.get("surface_kind")),
        _string(surface.get("classification")),
        _string(surface.get("note")),
    )
    return " ".join(parts).replace("-", "_").lower()


def _has_any(text: str, needles: Sequence[str]) -> bool:
    return any(needle.lower() in text for needle in needles)


def _dedupe_categories(categories: Sequence[str]) -> list[str]:
    result: list[str] = []
    for category in categories:
        if category in _IMPACT_CATEGORIES and category not in result:
            result.append(category)
    return result


def _category_list(impacted_surfaces: Sequence[Mapping[str, Any]]) -> list[str]:
    categories: list[str] = []
    for surface in impacted_surfaces:
        categories.extend(_string(category) for category in _sequence(surface.get("impact_categories")))
    return _dedupe_categories(categories)


def _primary_impact(categories: Sequence[str], impacted_surfaces: Sequence[Mapping[str, Any]]) -> str:
    if not categories:
        return "unknown"
    counts = Counter(
        category
        for surface in impacted_surfaces
        for category in _sequence(surface.get("impact_categories"))
        if _string(category) not in {"regression", "unknown", "missing_evidence"}
    )
    if counts:
        return sorted(counts.items(), key=lambda item: (-item[1], _PRIMARY_PRIORITY.index(item[0]) if item[0] in _PRIMARY_PRIORITY else 99))[0][0]
    for category in _PRIMARY_PRIORITY:
        if category in categories:
            return category
    return categories[0]


def _measured_or_expected(impacted_surfaces: Sequence[Mapping[str, Any]]) -> str:
    modes = {_string(surface.get("measured_or_expected")) for surface in impacted_surfaces}
    modes.discard("")
    if modes == {"measured"}:
        return "measured"
    if modes == {"expected"}:
        return "expected"
    if modes:
        return "mixed"
    return "expected"


def _normalize_measurement_mode(value: str) -> str:
    return value if value in _MEASUREMENT_MODES else "expected"


def _normalize_evidence_refs(
    explicit_refs: Sequence[Mapping[str, Any]] | None,
    *,
    calc_diff: Mapping[str, Any],
    action_ledger: Mapping[str, Any],
) -> list[dict[str, Any]]:
    refs = [dict(_mapping(ref)) for ref in _sequence(explicit_refs)]
    diff_id = _string(calc_diff.get("diff_id"))
    if diff_id:
        refs.append(
            {
                "ref_id": f"evidence.cv6.{diff_id}",
                "evidence_kind": "calc_delta",
                "locator": "calc_snapshot_diff_example.json",
                "json_pointer": "/changed_surfaces",
                "summary": "Calc Snapshot Diff evidence supplied measured surfaces for classification.",
            }
        )
    ledger_id = _string(action_ledger.get("ledger_id"))
    if ledger_id:
        refs.append(
            {
                "ref_id": f"evidence.cv6.{ledger_id}",
                "evidence_kind": "action_cost_value_ledger",
                "locator": "action_cost_value_tree_pathing_mvp.json",
                "json_pointer": "/rows",
                "summary": "Action Cost/Value Ledger supplied expected surfaces for classification.",
            }
        )
    return refs


def _ledger_action_refs(action_ledger: Mapping[str, Any]) -> list[str]:
    return [
        _string(row.get("action_id"))
        for row in _sequence(action_ledger.get("rows"))
        if isinstance(row, Mapping) and _string(row.get("action_id"))
    ]


def _missing_evidence(impacted_surfaces: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for surface in impacted_surfaces:
        categories = {_string(category) for category in _sequence(surface.get("impact_categories"))}
        if "missing_evidence" in categories or "unknown" in categories:
            missing.append(
                {
                    "evidence_kind": "surface_classification_rule",
                    "reason": f"No reliable impact rule or source metric evidence for {_string(surface.get('metric_key'))}.",
                    "blocking": False,
                    "surface_ref_id": _string(surface.get("surface_ref_id")),
                }
            )
    return missing


def _uncertainty(impacted_surfaces: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    categories = _category_list(impacted_surfaces)
    if "unknown" in categories or "missing_evidence" in categories:
        level = "medium"
        notes = ["At least one surface is unknown or missing evidence; no value is invented for it."]
    else:
        level = "low"
        notes = ["All fixture surfaces matched bounded CV6 category rules."]
    return {"level": level, "notes": notes}


def _surface_reason(metric_key: str, categories: Sequence[str], surface: Mapping[str, Any]) -> str:
    if "missing_evidence" in categories:
        return f"{metric_key} is recorded as missing evidence and is not assigned invented value."
    if "unknown" in categories:
        return f"{metric_key} did not match a bounded CV6 rule and remains unknown."
    return (
        f"{metric_key} classified as {', '.join(categories)} from "
        f"{_string(surface.get('source_kind')) or 'surface'}."
    )


def _default_reason(primary: str, categories: Sequence[str], impacted_surfaces: Sequence[Mapping[str, Any]]) -> str:
    return (
        f"Classified {len(impacted_surfaces)} expected/measured surfaces. "
        f"Primary impact is {primary}; categories present: {', '.join(categories) or 'none'}."
    )


def _record_findings(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if _string(record.get("record_kind")) != SURFACE_IMPACT_CLASSIFICATION_RECORD_KIND:
        findings.append(_finding("record_kind_invalid", "record_kind must be surface_impact_classification."))
    impacted = [_mapping(surface) for surface in _sequence(record.get("impacted_surfaces"))]
    if not impacted:
        findings.append(_finding("impacted_surfaces_missing", "At least one impacted surface is required."))
    categories = [_string(category) for category in _sequence(record.get("impact_categories"))]
    if not categories:
        findings.append(_finding("impact_categories_missing", "impact_categories must name at least one category."))
    invalid = [category for category in categories if category not in _IMPACT_CATEGORIES]
    if invalid:
        findings.append(_finding("impact_category_invalid", f"Invalid impact categories: {', '.join(invalid)}."))
    if _string(record.get("primary_impact")) not in _IMPACT_CATEGORIES:
        findings.append(_finding("primary_impact_invalid", "primary_impact must be a known impact category."))
    if _string(record.get("measured_or_expected")) not in _MEASUREMENT_MODES:
        findings.append(_finding("measured_or_expected_invalid", "measured_or_expected must be measured, expected, or mixed."))
    if not _sequence(record.get("evidence_refs")) and not _sequence(record.get("missing_evidence")):
        findings.append(_finding("evidence_accounting_missing", "Classification must cite evidence_refs or account for missing_evidence."))
    for surface in impacted:
        findings.extend(_surface_findings(surface))
    return findings


def _surface_findings(surface: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    surface_ref_id = _string(surface.get("surface_ref_id")) or "missing-surface-ref"
    categories = [_string(category) for category in _sequence(surface.get("impact_categories"))]
    if not categories:
        findings.append(_finding("surface_impact_categories_missing", "Each impacted surface needs impact_categories.", surface_ref_id=surface_ref_id))
    invalid = [category for category in categories if category not in _IMPACT_CATEGORIES]
    if invalid:
        findings.append(_finding("surface_impact_category_invalid", f"Invalid surface categories: {', '.join(invalid)}.", surface_ref_id=surface_ref_id))
    if not _string(surface.get("metric_key")):
        findings.append(_finding("surface_metric_key_missing", "Each impacted surface needs metric_key.", surface_ref_id=surface_ref_id))
    if not _string(surface.get("classification_reason")):
        findings.append(_finding("surface_classification_reason_missing", "Each impacted surface needs classification_reason.", surface_ref_id=surface_ref_id))
    return findings


def _validation_findings_as_blockers(validation: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "blocker_id": _string(finding.get("code")) or "surface_impact_finding",
            "severity": "blocking",
            "summary": _string(finding.get("summary")) or "Surface Impact Classification finding.",
            "unblock_condition": "Repair impacted surfaces, categories, evidence accounting, or classification reason.",
        }
        for finding in _sequence(validation.get("findings"))
        if isinstance(finding, Mapping)
    ]


def _merge_strings(*groups: Sequence[str] | None) -> list[str]:
    result: list[str] = []
    for group in groups:
        for value in _sequence(group):
            text = _string(value)
            if text and text not in result:
                result.append(text)
    return result


def _load_json_mapping(path: Path, *, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SurfaceImpactClassificationError(f"{label} at {path} must be readable JSON.") from exc
    if not isinstance(payload, Mapping):
        raise SurfaceImpactClassificationError(f"{label} at {path} must be a JSON object.")
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
        raise SurfaceImpactClassificationError(f"{field_name} must be a non-empty string.")
    return text


def _path_string(path: Path) -> str:
    return Path(path).resolve(strict=False).as_posix()


def _finding(code: str, summary: str, *, surface_ref_id: str | None = None) -> dict[str, Any]:
    finding = {"code": code, "summary": summary}
    if surface_ref_id:
        finding["surface_ref_id"] = surface_ref_id
    return finding


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    produce = subparsers.add_parser("produce", help="Produce CV6 validation artifacts from a classification input.")
    produce.add_argument("--input", type=Path, required=True)
    produce.add_argument("--output-dir", type=Path, required=True)

    example = subparsers.add_parser("example", help="Produce the CV6 surface impact classification MVP example artifacts.")
    example.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "produce":
        result = produce_surface_impact_classification_artifacts_from_file(
            input_path=args.input,
            output_dir=args.output_dir,
        )
    else:
        result = produce_surface_impact_classification_example_artifacts(output_dir=args.output_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SURFACE_IMPACT_CLASSIFICATION_RECORD_KIND",
    "SURFACE_IMPACT_CLASSIFICATION_SCHEMA_VERSION",
    "SURFACE_IMPACT_CLASSIFICATION_VALIDATION_RECORD_KIND",
    "SurfaceImpactClassificationError",
    "build_surface_impact_classification",
    "build_surface_impact_classification_mvp_example",
    "build_surface_impact_classification_validation",
    "produce_surface_impact_classification_artifacts",
    "produce_surface_impact_classification_artifacts_from_file",
    "produce_surface_impact_classification_example_artifacts",
]
