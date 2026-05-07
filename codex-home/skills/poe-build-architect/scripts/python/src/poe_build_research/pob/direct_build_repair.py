"""Repair packet builder for blocked Direct Build materialization runs.

This module does not choose PoE build changes. It converts proof blockers into
machine-readable next-attempt requirements so the product agent must repair and
rerun instead of stopping after a failed materialization.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .artifacts import write_json

RECORD_KIND = "direct_build_repair_packet"
SCHEMA_VERSION = "0.1.0"


class DirectBuildRepairPacketError(RuntimeError):
    """Raised when repair packet inputs are invalid."""


def build_direct_build_repair_packet(
    *,
    materialization_result: Mapping[str, Any],
    rails_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result_blockers = _blockers_from_materialization_result(materialization_result)
    rails_blockers = _blockers_from_rails_report(rails_report or {})
    blockers = _dedupe_blockers([*rails_blockers, *result_blockers])
    publication_guard = _mapping(materialization_result.get("publication_guard"))
    publishable = (
        materialization_result.get("status") == "accepted"
        and publication_guard.get("direct_build_output_allowed") is True
        and publication_guard.get("successful_chat_payload_allowed") is True
    )
    repair_items = _repair_items(blockers)
    return {
        "schema_version": SCHEMA_VERSION,
        "record_kind": RECORD_KIND,
        "status": "no_repair_required" if publishable and not repair_items else "repair_required",
        "publishable": publishable,
        "next_attempt_required": bool(repair_items),
        "stop_allowed": publishable and not repair_items,
        "ledger_id": _string(materialization_result.get("ledger_id")) or None,
        "pob_run_id": _string(materialization_result.get("pob_run_id")) or None,
        "source_materialization_result": {
            "record_kind": _string(materialization_result.get("record_kind")) or None,
            "status": _string(materialization_result.get("status")) or None,
        },
        "observed_blocker_codes": [blocker["code"] for blocker in blockers],
        "repair_items": repair_items,
        "minimum_next_hypotheses": _minimum_next_hypotheses(repair_items),
        "required_next_artifacts": [
            "repaired direct_build_decision_trace",
            "repaired direct-build-decision-ledger.json",
            "new materialization-source-packet.json",
            "new early-game-rails-report.json",
            "new normalized-calc-snapshot.json",
            "new native import-code verifier result",
        ]
        if repair_items
        else [],
        "safe_next_actions": _safe_next_actions(repair_items),
        "product_rule": "A failed materialization is not a stop condition while repair_items are present.",
    }


def _repair_items(blockers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    passive_budget = _first_blocker(blockers, "passive_budget_not_113") or _first_blocker(
        blockers, "candidate_passives_not_113"
    )
    if passive_budget:
        observed = _optional_number(passive_budget.get("observed"))
        expected = _optional_number(passive_budget.get("expected"))
        items.append(
            {
                "repair_id": "repair.tree.passive_budget",
                "blocker_codes": [
                    code
                    for code in ("passive_budget_not_113", "candidate_passives_not_113")
                    if _first_blocker(blockers, code)
                ],
                "priority": 10,
                "target_surfaces": ["tree"],
                "observed": {"normal_passives": observed},
                "expected": {"normal_passives": expected},
                "agent_must_author": (
                    "Author a revised tree_state package with exactly the expected normal passive budget. "
                    "Do not satisfy this by deleting ascendancy nodes or changing the requested identity."
                ),
                "required_evidence": [
                    "tree package cost for the revised path",
                    "removed/added node ids or equivalent PoB tree diff",
                    "alternatives_considered for at least one different repair route",
                    "post-materialization rails observed.normal_passive_count",
                ],
                "next_attempt_gate": "early-game rails must report normal_passive_count == expected.",
            }
        )

    dps_floor = _first_blocker(blockers, "baseline_full_dps_below_floor")
    if dps_floor:
        observed = _optional_number(dps_floor.get("observed"))
        expected = _optional_number(dps_floor.get("expected_minimum"))
        multiplier = None if observed is None or observed <= 0 or expected is None else expected / observed
        items.append(
            {
                "repair_id": "repair.baseline.full_dps_floor",
                "blocker_codes": ["baseline_full_dps_below_floor"],
                "priority": 9,
                "target_surfaces": ["skill", "tree", "item", "config"],
                "observed": {"baseline_full_dps": observed},
                "expected": {"minimum_baseline_full_dps": expected},
                "required_multiplier": multiplier,
                "agent_must_author": (
                    "Author competing DPS repair hypotheses and select a revised skill/tree/item/config package "
                    "from PoB evidence. The repair packet does not choose the scaling route."
                ),
                "required_evidence": [
                    "at least three competing DPS hypotheses unless budget is explicitly lower",
                    "resource cost for each accepted material change",
                    "alternatives_considered for rejected DPS routes",
                    "baseline calc snapshot FullDPS after materialization",
                ],
                "next_attempt_gate": "early-game rails must report baseline_full_dps >= expected minimum.",
            }
        )

    for blocker in blockers:
        code = _string(blocker.get("code"))
        if code in {
            "passive_budget_not_113",
            "candidate_passives_not_113",
            "baseline_full_dps_below_floor",
        }:
            continue
        items.append(
            {
                "repair_id": f"repair.generic.{code or 'blocker'}",
                "blocker_codes": [code or "unknown_blocker"],
                "priority": 5,
                "target_surfaces": ["identity", "skill", "tree", "item", "config", "observe"],
                "observed": _mapping_without_empty({"observed": blocker.get("observed")}),
                "expected": _mapping_without_empty(
                    {
                        "expected": blocker.get("expected"),
                        "expected_minimum": blocker.get("expected_minimum"),
                    }
                ),
                "agent_must_author": "Repair the blocked surface explicitly and rerun materialization.",
                "required_evidence": [
                    "source decision row for the repaired surface",
                    "resource cost",
                    "alternatives_considered",
                    "post-materialization read-back",
                ],
                "next_attempt_gate": f"materialization result must not contain blocker {code or 'unknown_blocker'}.",
            }
        )
    return sorted(items, key=lambda item: item["priority"], reverse=True)


def _safe_next_actions(repair_items: Sequence[Mapping[str, Any]]) -> list[str]:
    if not repair_items:
        return []
    return [
        "author repair hypotheses from repair_items",
        "write a new agent-authored decision ledger",
        "run direct_build_materializer produce",
        "run direct_build_materializer materialize",
        "run native import verification",
        "block again with the new repair packet if rails still fail",
    ]


def _minimum_next_hypotheses(repair_items: Sequence[Mapping[str, Any]]) -> int:
    if any(item.get("repair_id") == "repair.baseline.full_dps_floor" for item in repair_items):
        return 3
    if repair_items:
        return 1
    return 0


def _blockers_from_materialization_result(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        _normalized_blocker(blocker)
        for blocker in _sequence(payload.get("blockers"))
        if isinstance(blocker, Mapping)
    ]


def _blockers_from_rails_report(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        _normalized_blocker(blocker)
        for blocker in _sequence(payload.get("blockers"))
        if isinstance(blocker, Mapping)
    ]


def _normalized_blocker(blocker: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "code": _string(blocker.get("code")) or _string(blocker.get("blocker_id")) or "unknown_blocker",
        "summary": _string(blocker.get("summary")) or None,
        "observed": blocker.get("observed"),
        "expected": blocker.get("expected"),
        "expected_minimum": blocker.get("expected_minimum"),
    }


def _dedupe_blockers(blockers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for blocker in blockers:
        normalized = _normalized_blocker(blocker)
        if normalized["code"] in seen_codes:
            continue
        seen_codes.add(normalized["code"])
        result.append(normalized)
    return result


def _first_blocker(blockers: Sequence[Mapping[str, Any]], code: str) -> Mapping[str, Any] | None:
    for blocker in blockers:
        if _string(blocker.get("code")) == code:
            return blocker
    return None


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DirectBuildRepairPacketError(f"JSON file must contain an object: {path}")
    return payload


def _load_rails_report(materialization_result: Mapping[str, Any], explicit_path: Path | None) -> Mapping[str, Any]:
    if explicit_path is not None:
        return _load_json(explicit_path)
    locator = _mapping(materialization_result.get("early_game_rails")).get("report_locator")
    if isinstance(locator, str) and locator:
        path = Path(locator)
        if path.is_file():
            return _load_json(path)
    return {}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return []


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_number(value: Any) -> float | int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mapping_without_empty(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Direct Build repair packet from blocked proof artifacts.")
    parser.add_argument("--materialization-result", type=Path, required=True)
    parser.add_argument("--rails-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    materialization_result = _load_json(args.materialization_result)
    packet = build_direct_build_repair_packet(
        materialization_result=materialization_result,
        rails_report=_load_rails_report(materialization_result, args.rails_report),
    )
    write_json(args.output, packet)
    print(args.output)
    return 0 if packet["status"] == "no_repair_required" else 1


if __name__ == "__main__":
    raise SystemExit(main())
