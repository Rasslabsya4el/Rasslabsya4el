"""Bounded tree visual inspection contract for Direct Build publication gates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

TREE_VISUAL_INSPECTION_RECORD_KIND = "tree_visual_inspection"
TREE_VISUAL_INSPECTION_SCHEMA_VERSION = "0.1.0"
TREE_VISUAL_INSPECTION_ACCEPTED_STATUSES = {"accepted", "passed", "operator_review_ready"}


def validate_tree_visual_inspection_artifact(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Return fail-closed blockers for a compact tree visual inspection artifact.

    The artifact may come from a browser screenshot workflow or from a
    deterministic tree-layout summary. This validator deliberately does not
    choose passives; it only requires that route-shape inspection happened and
    did not report dead travel or irrelevant clusters.
    """

    if not isinstance(payload, Mapping) or not payload:
        return [
            _blocker(
                "tree_visual_inspection_missing",
                "Tree visual inspection artifact is missing.",
                "Attach a tree visual inspection artifact before publication.",
            )
        ]

    blockers: list[dict[str, Any]] = []
    record_kind = _string(payload.get("record_kind"))
    if record_kind and record_kind != TREE_VISUAL_INSPECTION_RECORD_KIND:
        blockers.append(
            _blocker(
                "tree_visual_inspection_record_kind_invalid",
                f"Tree visual inspection record_kind is {record_kind}.",
                TREE_VISUAL_INSPECTION_RECORD_KIND,
            )
        )

    status = _string(payload.get("status")).lower()
    if status not in TREE_VISUAL_INSPECTION_ACCEPTED_STATUSES:
        blockers.append(
            _blocker(
                "tree_visual_inspection_not_accepted",
                f"Tree visual inspection status is {status or '<missing>'}.",
                sorted(TREE_VISUAL_INSPECTION_ACCEPTED_STATUSES),
            )
        )

    if not _has_visual_or_layout_ref(payload):
        blockers.append(
            _blocker(
                "tree_visual_inspection_evidence_missing",
                "Tree visual inspection must cite a screenshot/ref or deterministic layout summary.",
                "screenshot_ref, artifact_ref, route_shape_summary, or deterministic_tree_layout_summary",
            )
        )
    if not _has_deterministic_route_shape_evidence(payload):
        blockers.append(
            _blocker(
                "tree_visual_route_shape_evidence_missing",
                "Tree visual inspection self-report is insufficient without deterministic/readback route-shape evidence.",
                "deterministic_route_shape_evidence, readback_route_shape_evidence, or route_shape_metrics",
            )
        )
    if not _has_route_alternative_evidence(payload):
        blockers.append(
            _blocker(
                "tree_visual_route_alternatives_missing",
                "Tree visual inspection must compare the selected route against local connector/cleanup alternatives.",
                "local_alternative_refs, rejected_route_alternatives, or connector_alternative_refs",
            )
        )

    checklist = _mapping(payload.get("checklist")) or payload
    for key, code, summary in (
        (
            "dead_travel_detected",
            "tree_visual_dead_travel_detected",
            "Tree visual inspection reports dead travel.",
        ),
        (
            "irrelevant_cluster_detected",
            "tree_visual_irrelevant_cluster_detected",
            "Tree visual inspection reports an irrelevant cluster.",
        ),
        (
            "poor_route_shape_detected",
            "tree_visual_poor_route_shape_detected",
            "Tree visual inspection reports poor route shape.",
        ),
    ):
        if _truthy(checklist.get(key)):
            blockers.append(_blocker(code, summary, False))

    return blockers


def _has_visual_or_layout_ref(payload: Mapping[str, Any]) -> bool:
    for key in (
        "screenshot_ref",
        "artifact_ref",
        "visual_artifact_ref",
        "route_shape_summary",
        "deterministic_tree_layout_summary",
    ):
        value = payload.get(key)
        if isinstance(value, Mapping) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def _has_deterministic_route_shape_evidence(payload: Mapping[str, Any]) -> bool:
    for key in (
        "deterministic_route_shape_evidence",
        "readback_route_shape_evidence",
        "route_shape_metrics",
        "selected_route_node_ids",
    ):
        value = payload.get(key)
        if isinstance(value, Mapping) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) and value:
            return True
    return False


def _has_route_alternative_evidence(payload: Mapping[str, Any]) -> bool:
    for key in (
        "local_alternative_refs",
        "rejected_route_alternatives",
        "connector_alternative_refs",
        "pathing_cleanup_alternatives",
    ):
        value = payload.get(key)
        if isinstance(value, Mapping) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) and value:
            return True
    return False


def _blocker(code: str, observed: Any, expected: Any) -> dict[str, Any]:
    return {"code": code, "observed": observed, "expected": expected}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "on", "enabled", "active"}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    return bool(value)
