"""Calc Snapshot Diff Evidence utilities for bounded PoB action measurement.

This module does not choose actions and does not run an optimizer. It compares
two already-produced normalized Calc snapshots and emits a compact evidence
record that Action Cost/Value Ledger rows can cite.
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .artifacts import sha256_bytes, write_json
from .release_manager import utc_now_iso

CALC_SNAPSHOT_DIFF_RECORD_KIND = "calc_snapshot_diff_evidence"
CALC_SNAPSHOT_DIFF_SCHEMA_VERSION = "0.1.0"
CALC_SNAPSHOT_DIFF_SUPPORTED_PATH = "pob_calc_snapshot_diff_evidence_v1"

_REGRESSION_CLASSIFICATIONS = frozenset(
    {
        "dps_loss",
        "defense_regression",
        "resource_regression",
        "qol_regression",
        "requirement_pressure",
        "warning_added",
    }
)

_SURFACE_DEFS: tuple[dict[str, Any], ...] = (
    {
        "surface_id": "FullDPS",
        "aliases": ("FullDPS", "full_dps", "damage_per_second"),
        "surface_kind": "pob_metric",
        "higher_is_better": True,
        "gain": "dps_gain",
        "loss": "dps_loss",
    },
    {
        "surface_id": "CombinedDPS",
        "aliases": ("CombinedDPS", "combined_dps"),
        "surface_kind": "pob_metric",
        "higher_is_better": True,
        "gain": "dps_gain",
        "loss": "dps_loss",
    },
    {
        "surface_id": "AverageHit",
        "aliases": ("AverageHit", "average_hit"),
        "surface_kind": "pob_metric",
        "higher_is_better": True,
        "gain": "dps_gain",
        "loss": "dps_loss",
    },
    {
        "surface_id": "CastRate",
        "aliases": ("CastRate", "cast_rate"),
        "surface_kind": "pob_metric",
        "higher_is_better": True,
        "gain": "speed_qol_gain",
        "loss": "qol_regression",
    },
    {
        "surface_id": "TotalEHP",
        "aliases": ("TotalEHP", "effective_hit_pool"),
        "surface_kind": "pob_metric",
        "higher_is_better": True,
        "gain": "defense_gain",
        "loss": "defense_regression",
    },
    {
        "surface_id": "Life",
        "aliases": ("Life", "life_total"),
        "surface_kind": "pob_metric",
        "higher_is_better": True,
        "gain": "defense_gain",
        "loss": "defense_regression",
    },
    {
        "surface_id": "Mana",
        "aliases": ("Mana", "mana_total"),
        "surface_kind": "pob_metric",
        "higher_is_better": True,
        "gain": "resource_gain",
        "loss": "resource_regression",
    },
    {
        "surface_id": "EnergyShield",
        "aliases": ("EnergyShield", "ES", "energy_shield"),
        "surface_kind": "pob_metric",
        "higher_is_better": True,
        "gain": "defense_gain",
        "loss": "defense_regression",
    },
    {
        "surface_id": "LifeUnreserved",
        "aliases": ("LifeUnreserved", "life_unreserved"),
        "surface_kind": "calc_surface",
        "higher_is_better": True,
        "gain": "resource_gain",
        "loss": "resource_regression",
    },
    {
        "surface_id": "ManaUnreserved",
        "aliases": ("ManaUnreserved", "mana_unreserved"),
        "surface_kind": "calc_surface",
        "higher_is_better": True,
        "gain": "resource_gain",
        "loss": "resource_regression",
    },
    {
        "surface_id": "LifeReserved",
        "aliases": ("LifeReserved", "life_reserved"),
        "surface_kind": "calc_surface",
        "higher_is_better": False,
        "gain": "resource_gain",
        "loss": "resource_regression",
    },
    {
        "surface_id": "ManaReserved",
        "aliases": ("ManaReserved", "mana_reserved"),
        "surface_kind": "calc_surface",
        "higher_is_better": False,
        "gain": "resource_gain",
        "loss": "resource_regression",
    },
    {
        "surface_id": "Radius",
        "aliases": ("Radius", "radius"),
        "surface_kind": "qol",
        "higher_is_better": True,
        "gain": "aoe_qol_gain",
        "loss": "qol_regression",
    },
    {
        "surface_id": "AreaOfEffect",
        "aliases": ("AreaOfEffect", "Area", "area_of_effect"),
        "surface_kind": "qol",
        "higher_is_better": True,
        "gain": "aoe_qol_gain",
        "loss": "qol_regression",
    },
)

_REQUIREMENT_KEYS: tuple[tuple[str, str, str], ...] = (
    ("Str", "ReqStr", "strength"),
    ("Dex", "ReqDex", "dexterity"),
    ("Int", "ReqInt", "intelligence"),
    ("Omni", "ReqOmni", "omniscience"),
)


class CalcSnapshotDiffError(RuntimeError):
    """Raised when a Calc Snapshot Diff Evidence record cannot be produced."""


def build_calc_snapshot_diff(
    baseline_snapshot: Mapping[str, Any],
    after_snapshot: Mapping[str, Any],
    *,
    baseline_snapshot_ref: str,
    after_snapshot_ref: str,
    action_refs: Sequence[str] | None = None,
    ledger_refs: Sequence[str] | None = None,
    selected_skill: str | None = None,
    generated_at: str | None = None,
    diff_id: str | None = None,
) -> dict[str, Any]:
    """Build a compact before/after Calc delta evidence record."""

    baseline_ref = _required_string(baseline_snapshot_ref, "baseline_snapshot_ref")
    after_ref = _required_string(after_snapshot_ref, "after_snapshot_ref")
    baseline = _extract_snapshot_surfaces(_mapping(baseline_snapshot), snapshot_label="baseline")
    after = _extract_snapshot_surfaces(_mapping(after_snapshot), snapshot_label="after")

    changed_surfaces: list[dict[str, Any]] = []
    unchanged_surfaces: list[dict[str, Any]] = []
    missing_metrics: list[dict[str, Any]] = []
    unsupported_claims: list[dict[str, Any]] = []

    for surface in _SURFACE_DEFS:
        baseline_value, baseline_key, baseline_bad = _lookup_numeric(baseline["main_output"], surface["aliases"])
        after_value, after_key, after_bad = _lookup_numeric(after["main_output"], surface["aliases"])
        if baseline_bad is not None:
            unsupported_claims.append(_unsupported_claim(surface["surface_id"], "baseline", baseline_bad))
        if after_bad is not None:
            unsupported_claims.append(_unsupported_claim(surface["surface_id"], "after", after_bad))
        if baseline_value is None and after_value is None:
            continue
        metric_key = baseline_key or after_key or surface["surface_id"]
        if baseline_value is None or after_value is None:
            missing_metrics.append(
                {
                    "metric_key": metric_key,
                    "surface_kind": surface["surface_kind"],
                    "missing_from": "baseline" if baseline_value is None else "after",
                    "reason": "Metric exists on only one side of the before/after Calc snapshot pair.",
                }
            )
            continue
        row = _numeric_delta_row(
            surface_id=surface["surface_id"],
            surface_kind=surface["surface_kind"],
            metric_key=metric_key,
            baseline_value=baseline_value,
            after_value=after_value,
            higher_is_better=bool(surface["higher_is_better"]),
            gain_classification=str(surface["gain"]),
            loss_classification=str(surface["loss"]),
        )
        if row["direction"] == "unchanged":
            unchanged_surfaces.append(row)
        else:
            changed_surfaces.append(row)

    for row in _requirement_delta_rows(baseline, after):
        if row["direction"] == "unchanged":
            unchanged_surfaces.append(row)
        else:
            changed_surfaces.append(row)

    changed_surfaces.extend(_warning_delta_rows(baseline["warning_codes"], after["warning_codes"]))
    regressions = [
        row
        for row in changed_surfaces
        if _string(row.get("classification")) in _REGRESSION_CLASSIFICATIONS
    ]

    evidence_quality = _evidence_quality(
        changed_surfaces=changed_surfaces,
        unchanged_surfaces=unchanged_surfaces,
        missing_metrics=missing_metrics,
        unsupported_claims=unsupported_claims,
    )
    generated = generated_at or utc_now_iso()
    normalized_action_refs = [_required_string(value, "action_refs[]") for value in _sequence(action_refs)]
    normalized_ledger_refs = [_required_string(value, "ledger_refs[]") for value in _sequence(ledger_refs)]
    record_id = diff_id or _default_diff_id(
        baseline_snapshot_ref=baseline_ref,
        after_snapshot_ref=after_ref,
        action_refs=normalized_action_refs,
        ledger_refs=normalized_ledger_refs,
    )
    return {
        "schema_version": CALC_SNAPSHOT_DIFF_SCHEMA_VERSION,
        "record_kind": CALC_SNAPSHOT_DIFF_RECORD_KIND,
        "supported_path": CALC_SNAPSHOT_DIFF_SUPPORTED_PATH,
        "diff_id": record_id,
        "generated_at": generated,
        "baseline_snapshot_ref": baseline_ref,
        "after_snapshot_ref": after_ref,
        "action_refs": normalized_action_refs,
        "ledger_refs": normalized_ledger_refs,
        "selected_skill": _string(selected_skill) or None,
        "changed_surfaces": changed_surfaces,
        "unchanged_surfaces": unchanged_surfaces,
        "regressions": regressions,
        "missing_metrics": missing_metrics,
        "unsupported_claims": unsupported_claims,
        "evidence_quality": evidence_quality,
        "summary": {
            "text": _summary_text(evidence_quality, changed_surfaces, regressions, missing_metrics, unsupported_claims),
            "changed_surface_count": len(changed_surfaces),
            "unchanged_surface_count": len(unchanged_surfaces),
            "regression_count": len(regressions),
            "missing_metric_count": len(missing_metrics),
            "unsupported_claim_count": len(unsupported_claims),
            "product_agent_behavioral_proof_required": False,
        },
        "product_agent_behavioral_proof_required": False,
    }


def build_calc_snapshot_diff_from_files(
    *,
    baseline_snapshot_path: Path,
    after_snapshot_path: Path,
    baseline_snapshot_ref: str | None = None,
    after_snapshot_ref: str | None = None,
    action_refs: Sequence[str] | None = None,
    ledger_refs: Sequence[str] | None = None,
    selected_skill: str | None = None,
    generated_at: str | None = None,
    diff_id: str | None = None,
) -> dict[str, Any]:
    """Load two JSON snapshots and build a Calc Snapshot Diff Evidence record."""

    baseline_path = Path(baseline_snapshot_path)
    after_path = Path(after_snapshot_path)
    return build_calc_snapshot_diff(
        _load_json_mapping(baseline_path, label="baseline Calc snapshot"),
        _load_json_mapping(after_path, label="after Calc snapshot"),
        baseline_snapshot_ref=baseline_snapshot_ref or _path_string(baseline_path),
        after_snapshot_ref=after_snapshot_ref or _path_string(after_path),
        action_refs=action_refs,
        ledger_refs=ledger_refs,
        selected_skill=selected_skill,
        generated_at=generated_at,
        diff_id=diff_id,
    )


def produce_calc_snapshot_diff_artifact(
    *,
    baseline_snapshot_path: Path,
    after_snapshot_path: Path,
    output_path: Path,
    baseline_snapshot_ref: str | None = None,
    after_snapshot_ref: str | None = None,
    action_refs: Sequence[str] | None = None,
    ledger_refs: Sequence[str] | None = None,
    selected_skill: str | None = None,
    generated_at: str | None = None,
    diff_id: str | None = None,
) -> dict[str, Any]:
    """Build and write one Calc Snapshot Diff Evidence artifact."""

    diff = build_calc_snapshot_diff_from_files(
        baseline_snapshot_path=baseline_snapshot_path,
        after_snapshot_path=after_snapshot_path,
        baseline_snapshot_ref=baseline_snapshot_ref,
        after_snapshot_ref=after_snapshot_ref,
        action_refs=action_refs,
        ledger_refs=ledger_refs,
        selected_skill=selected_skill,
        generated_at=generated_at,
        diff_id=diff_id,
    )
    path = write_json(Path(output_path), diff)
    return {
        "schema_version": CALC_SNAPSHOT_DIFF_SCHEMA_VERSION,
        "record_kind": "calc_snapshot_diff_production_result",
        "status": diff["evidence_quality"],
        "diff_id": diff["diff_id"],
        "artifact_locator": _path_string(path),
        "product_agent_behavioral_proof_required": False,
    }


def build_calc_snapshot_diff_mvp_example(*, generated_at: str | None = None) -> dict[str, Any]:
    """Return a small fixture diff with gains, regressions, and missing evidence."""

    return build_calc_snapshot_diff(
        build_calc_snapshot_diff_baseline_example(),
        build_calc_snapshot_diff_after_example(),
        baseline_snapshot_ref="fixture://cv2/baseline-calc-snapshot",
        after_snapshot_ref="fixture://cv2/after-calc-snapshot",
        action_refs=("tree_pathing.rt_package",),
        ledger_refs=("cv1.tree-pathing.mvp#/rows/0",),
        selected_skill="Fireball",
        generated_at=generated_at or "2026-05-06T00:00:00Z",
        diff_id="cv2.calc-snapshot-diff.mvp",
    )


def build_calc_snapshot_diff_baseline_example() -> dict[str, Any]:
    """Return the baseline fixture snapshot used by the CV2 example."""

    return {
        "calc_snapshot": {
            "main_output": {
                "FullDPS": 180000.0,
                "CombinedDPS": 175000.0,
                "AverageHit": 1000.0,
                "CastRate": 3.0,
                "TotalEHP": 22000.0,
                "Life": 4500.0,
                "Mana": 780.0,
                "EnergyShield": 0.0,
                "ManaUnreserved": 120.0,
                "Radius": 22.0,
                "Str": 120.0,
                "ReqStr": 100.0,
            },
            "warning_codes": [],
            "triage": {
                "requirement_pressure": {
                    "strength": {
                        "available": 120.0,
                        "required": 100.0,
                        "shortfall": 0.0,
                        "satisfied": True,
                    }
                }
            },
        }
    }


def build_calc_snapshot_diff_after_example() -> dict[str, Any]:
    """Return the after fixture snapshot used by the CV2 example."""

    return {
        "calc_snapshot": {
            "main_output": {
                "FullDPS": 210000.0,
                "CombinedDPS": 205000.0,
                "CastRate": 3.2,
                "TotalEHP": 21400.0,
                "Life": 4350.0,
                "Mana": 780.0,
                "EnergyShield": 0.0,
                "ManaUnreserved": 95.0,
                "Radius": 24.0,
                "Str": 90.0,
                "ReqStr": 100.0,
            },
            "warning_codes": ["unmet_strength_requirement"],
            "triage": {
                "requirement_pressure": {
                    "strength": {
                        "available": 90.0,
                        "required": 100.0,
                        "shortfall": 10.0,
                        "satisfied": False,
                    }
                }
            },
        }
    }


def produce_calc_snapshot_diff_example_artifacts(
    *,
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Write the CV2 baseline, after, and diff example artifacts."""

    target_dir = Path(output_dir).resolve(strict=False)
    target_dir.mkdir(parents=True, exist_ok=True)
    baseline = build_calc_snapshot_diff_baseline_example()
    after = build_calc_snapshot_diff_after_example()
    diff = build_calc_snapshot_diff_mvp_example(generated_at=generated_at)
    baseline_path = write_json(target_dir / "calc_snapshot_diff_baseline_example.json", baseline)
    after_path = write_json(target_dir / "calc_snapshot_diff_after_example.json", after)
    diff_path = write_json(target_dir / "calc_snapshot_diff_example.json", diff)
    return {
        "schema_version": CALC_SNAPSHOT_DIFF_SCHEMA_VERSION,
        "record_kind": "calc_snapshot_diff_example_production_result",
        "status": diff["evidence_quality"],
        "artifact_locators": {
            "baseline_snapshot": _path_string(baseline_path),
            "after_snapshot": _path_string(after_path),
            "diff": _path_string(diff_path),
        },
        "product_agent_behavioral_proof_required": False,
    }


def _extract_snapshot_surfaces(snapshot: Mapping[str, Any], *, snapshot_label: str) -> dict[str, Any]:
    for candidate in (
        _mapping(snapshot.get("calc_snapshot")),
        _mapping(_mapping(snapshot.get("baseline")).get("calc_snapshot")),
        _mapping(_mapping(snapshot.get("conditional")).get("calc_snapshot")),
        snapshot,
        _mapping(snapshot.get("baseline")),
        _mapping(snapshot.get("conditional")),
    ):
        main_output = _mapping(candidate.get("main_output"))
        if not main_output:
            main_output = _mapping(candidate.get("metrics"))
        if main_output:
            return {
                "main_output": main_output,
                "warning_codes": _warning_codes(candidate, snapshot),
                "requirements": _requirements(candidate, main_output),
            }
    raise CalcSnapshotDiffError(f"{snapshot_label} Calc snapshot has no main_output or metrics object.")


def _numeric_delta_row(
    *,
    surface_id: str,
    surface_kind: str,
    metric_key: str,
    baseline_value: float,
    after_value: float,
    higher_is_better: bool,
    gain_classification: str,
    loss_classification: str,
) -> dict[str, Any]:
    delta = after_value - baseline_value
    if math.isclose(delta, 0.0, rel_tol=1e-12, abs_tol=1e-12):
        direction = "unchanged"
        classification = "no_change"
    elif delta > 0:
        direction = "increase"
        classification = gain_classification if higher_is_better else loss_classification
    else:
        direction = "decrease"
        classification = loss_classification if higher_is_better else gain_classification
    percent_delta = None if math.isclose(baseline_value, 0.0, abs_tol=1e-12) else (delta / baseline_value) * 100.0
    return {
        "surface_id": surface_id,
        "surface_kind": surface_kind,
        "metric_key": metric_key,
        "baseline_value": baseline_value,
        "after_value": after_value,
        "absolute_delta": delta,
        "percent_delta": percent_delta,
        "direction": direction,
        "classification": classification,
        "evidence_ref_id": f"calc_delta.{surface_id}",
    }


def _requirement_delta_rows(baseline: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    baseline_requirements = _mapping(baseline.get("requirements"))
    after_requirements = _mapping(after.get("requirements"))
    for key in sorted(set(baseline_requirements) | set(after_requirements)):
        baseline_shortfall = _number(_mapping(baseline_requirements.get(key)).get("shortfall"))
        after_shortfall = _number(_mapping(after_requirements.get(key)).get("shortfall"))
        if baseline_shortfall is None or after_shortfall is None:
            continue
        row = _numeric_delta_row(
            surface_id=f"requirement.{key}",
            surface_kind="constraint",
            metric_key=f"{key}.shortfall",
            baseline_value=baseline_shortfall,
            after_value=after_shortfall,
            higher_is_better=False,
            gain_classification="requirement_repair",
            loss_classification="requirement_pressure",
        )
        rows.append(row)
    return rows


def _warning_delta_rows(baseline_codes: Sequence[str], after_codes: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    baseline = set(baseline_codes)
    after = set(after_codes)
    for code in sorted(after - baseline):
        rows.append(
            {
                "surface_id": f"warning_code.{code}",
                "surface_kind": "warning_codes",
                "metric_key": code,
                "baseline_value": False,
                "after_value": True,
                "absolute_delta": None,
                "percent_delta": None,
                "direction": "added",
                "classification": "warning_added",
                "evidence_ref_id": f"calc_delta.warning_code.{code}",
            }
        )
    for code in sorted(baseline - after):
        rows.append(
            {
                "surface_id": f"warning_code.{code}",
                "surface_kind": "warning_codes",
                "metric_key": code,
                "baseline_value": True,
                "after_value": False,
                "absolute_delta": None,
                "percent_delta": None,
                "direction": "removed",
                "classification": "warning_removed",
                "evidence_ref_id": f"calc_delta.warning_code.{code}",
            }
        )
    return rows


def _requirements(candidate: Mapping[str, Any], main_output: Mapping[str, Any]) -> dict[str, Any]:
    triage = _mapping(candidate.get("triage"))
    pressure = _mapping(triage.get("requirement_pressure"))
    requirements: dict[str, Any] = {
        key: dict(value)
        for key, value in pressure.items()
        if isinstance(key, str) and isinstance(value, Mapping) and _number(value.get("shortfall")) is not None
    }
    for available_key, required_key, label in _REQUIREMENT_KEYS:
        available = _number(main_output.get(available_key))
        required = _number(main_output.get(required_key))
        if available is None or required is None:
            continue
        shortfall = max(0.0, required - available)
        requirements[label] = {
            "available": available,
            "required": required,
            "shortfall": shortfall,
            "satisfied": shortfall <= 0.0,
        }
    return requirements


def _warning_codes(*surfaces: Mapping[str, Any]) -> list[str]:
    codes: set[str] = set()
    for surface in surfaces:
        for key in ("warning_codes", "warnings"):
            for value in _sequence(surface.get(key)):
                text = _string(value)
                if text:
                    codes.add(text.split(":", 1)[-1])
    return sorted(codes)


def _lookup_numeric(output: Mapping[str, Any], aliases: Sequence[str]) -> tuple[float | None, str | None, str | None]:
    for alias in aliases:
        if alias not in output:
            continue
        value = output.get(alias)
        numeric = _number(value)
        if numeric is None:
            return None, alias, f"{alias} exists but is not a finite number."
        return numeric, alias, None
    return None, None, None


def _evidence_quality(
    *,
    changed_surfaces: Sequence[Mapping[str, Any]],
    unchanged_surfaces: Sequence[Mapping[str, Any]],
    missing_metrics: Sequence[Mapping[str, Any]],
    unsupported_claims: Sequence[Mapping[str, Any]],
) -> str:
    if not changed_surfaces and not unchanged_surfaces and not missing_metrics:
        return "blocked"
    if missing_metrics or unsupported_claims:
        return "partial"
    return "accepted"


def _summary_text(
    evidence_quality: str,
    changed_surfaces: Sequence[Mapping[str, Any]],
    regressions: Sequence[Mapping[str, Any]],
    missing_metrics: Sequence[Mapping[str, Any]],
    unsupported_claims: Sequence[Mapping[str, Any]],
) -> str:
    return (
        f"Calc snapshot diff evidence is {evidence_quality}: "
        f"{len(changed_surfaces)} changed surfaces, {len(regressions)} regressions, "
        f"{len(missing_metrics)} missing metrics, {len(unsupported_claims)} unsupported claims."
    )


def _unsupported_claim(surface_id: str, lane: str, reason: str) -> dict[str, Any]:
    return {
        "claim_id": f"unsupported.{lane}.{surface_id}",
        "summary": f"{lane} {surface_id} could not be compared.",
        "reason": reason,
    }


def _default_diff_id(
    *,
    baseline_snapshot_ref: str,
    after_snapshot_ref: str,
    action_refs: Sequence[str],
    ledger_refs: Sequence[str],
) -> str:
    fingerprint = sha256_bytes(
        json.dumps(
            {
                "baseline_snapshot_ref": baseline_snapshot_ref,
                "after_snapshot_ref": after_snapshot_ref,
                "action_refs": list(action_refs),
                "ledger_refs": list(ledger_refs),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )[:16]
    return f"calcdiff.{fingerprint}"


def _load_json_mapping(path: Path, *, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CalcSnapshotDiffError(f"{label} at {path} must be readable JSON.") from exc
    if not isinstance(payload, Mapping):
        raise CalcSnapshotDiffError(f"{label} at {path} must be a JSON object.")
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
        raise CalcSnapshotDiffError(f"{field_name} must be a non-empty string.")
    return text


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _path_string(path: Path) -> str:
    return Path(path).resolve(strict=False).as_posix()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    diff = subparsers.add_parser("diff", help="Produce one Calc Snapshot Diff Evidence artifact.")
    diff.add_argument("--baseline", type=Path, required=True)
    diff.add_argument("--after", type=Path, required=True)
    diff.add_argument("--output", type=Path, required=True)
    diff.add_argument("--baseline-ref")
    diff.add_argument("--after-ref")
    diff.add_argument("--action-ref", action="append", default=[])
    diff.add_argument("--ledger-ref", action="append", default=[])
    diff.add_argument("--selected-skill")

    example = subparsers.add_parser("example", help="Produce the CV2 example artifacts.")
    example.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "diff":
        result = produce_calc_snapshot_diff_artifact(
            baseline_snapshot_path=args.baseline,
            after_snapshot_path=args.after,
            output_path=args.output,
            baseline_snapshot_ref=args.baseline_ref,
            after_snapshot_ref=args.after_ref,
            action_refs=args.action_ref,
            ledger_refs=args.ledger_ref,
            selected_skill=args.selected_skill,
        )
    else:
        result = produce_calc_snapshot_diff_example_artifacts(output_dir=args.output_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] in {"accepted", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CALC_SNAPSHOT_DIFF_RECORD_KIND",
    "CALC_SNAPSHOT_DIFF_SCHEMA_VERSION",
    "CALC_SNAPSHOT_DIFF_SUPPORTED_PATH",
    "CalcSnapshotDiffError",
    "build_calc_snapshot_diff",
    "build_calc_snapshot_diff_after_example",
    "build_calc_snapshot_diff_baseline_example",
    "build_calc_snapshot_diff_from_files",
    "build_calc_snapshot_diff_mvp_example",
    "produce_calc_snapshot_diff_artifact",
    "produce_calc_snapshot_diff_example_artifacts",
]
