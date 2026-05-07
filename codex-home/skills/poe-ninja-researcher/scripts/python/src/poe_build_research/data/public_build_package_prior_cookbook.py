"""Materialize explicit public-build package priors from accepted pattern research."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from .poe_ninja import POE_NINJA_SOURCE_ID, POE_NINJA_UPSTREAM_SYSTEM
from .poe_ninja_pattern_miner import POE_NINJA_PATTERN_MINER_RECORD_KIND

PUBLIC_BUILD_PACKAGE_PRIOR_COOKBOOK_SCHEMA_VERSION = "1.0.0"
PUBLIC_BUILD_PACKAGE_PRIOR_COOKBOOK_RECORD_KIND = "public_build_package_prior_cookbook"
PUBLIC_BUILD_PACKAGE_PRIOR_COOKBOOK_GENERATOR = (
    "poe_build_research.data.public_build_package_prior_cookbook"
)
PUBLIC_BUILD_PACKAGE_PRIOR_ENTRY_KIND = "public_build_package_prior"
PUBLIC_BUILD_PACKAGE_PRIOR_ENFORCEMENT_LEVEL = "soft_search_input"
PUBLIC_BUILD_PACKAGE_PRIOR_MAX_REUSE_WINDOW_HOURS = 168
BLOCKED_DEFAULT_SEED_TAXONOMY_KINDS = frozenset(
    {"utility_baseline", "generic_cooccurrence", "rejected_low_information"}
)


class PublicBuildPackagePriorCookbookContractError(RuntimeError):
    """Raised when cookbook materialization inputs violate the accepted contract."""


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicBuildPackagePriorCookbookContractError(
            f"{field_name} must be a non-empty string."
        )
    return value.strip()


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicBuildPackagePriorCookbookContractError(f"{field_name} must be an object.")
    return value


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PublicBuildPackagePriorCookbookContractError(f"{field_name} must be an array.")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PublicBuildPackagePriorCookbookContractError(
            "Expected a string when a value is provided."
        )
    normalized = value.strip()
    return normalized or None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _entry_id(candidate_id: str, family: str) -> str:
    suffix = candidate_id.rsplit(".", 1)[-1]
    return f"cookbook.package-prior.{_slug(family)}.{suffix}"


def _validate_pattern_research_payload(pattern_research_payload: Mapping[str, Any]) -> None:
    record_kind = _require_non_empty_string(
        pattern_research_payload.get("record_kind"),
        "pattern_research.record_kind",
    )
    if record_kind != POE_NINJA_PATTERN_MINER_RECORD_KIND:
        raise PublicBuildPackagePriorCookbookContractError(
            "pattern_research.record_kind must stay on accepted "
            f"{POE_NINJA_PATTERN_MINER_RECORD_KIND!r} inputs."
        )
    source = _require_mapping(pattern_research_payload.get("source"), "pattern_research.source")
    source_id = _require_non_empty_string(source.get("source_id"), "pattern_research.source.source_id")
    upstream_system = _require_non_empty_string(
        source.get("upstream_system"),
        "pattern_research.source.upstream_system",
    )
    if source_id != POE_NINJA_SOURCE_ID or upstream_system != POE_NINJA_UPSTREAM_SYSTEM:
        raise PublicBuildPackagePriorCookbookContractError(
            "pattern_research.source must stay on accepted poe.ninja public-build surfaces."
        )
    _require_non_empty_string(source.get("generator"), "pattern_research.source.generator")
    _require_mapping(pattern_research_payload.get("query_scope"), "pattern_research.query_scope")
    _require_list(pattern_research_payload.get("trace_attachments"), "pattern_research.trace_attachments")
    _require_list(pattern_research_payload.get("package_candidates"), "pattern_research.package_candidates")


def _attachment_lookup(pattern_research_payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    lookup: dict[str, Mapping[str, Any]] = {}
    for index, raw_attachment in enumerate(
        _require_list(pattern_research_payload.get("trace_attachments"), "pattern_research.trace_attachments")
    ):
        attachment = _require_mapping(raw_attachment, f"pattern_research.trace_attachments[{index}]")
        attachment_id = _require_non_empty_string(
            attachment.get("attachment_id"),
            f"pattern_research.trace_attachments[{index}].attachment_id",
        )
        lookup[attachment_id] = attachment
    return lookup


def _candidate_components(candidate: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    components: list[Mapping[str, Any]] = []
    for index, raw_component in enumerate(
        _require_list(candidate.get("components"), "package_candidate.components")
    ):
        component = _require_mapping(raw_component, f"package_candidate.components[{index}]")
        components.append(
            {
                "component_kind": _require_non_empty_string(
                    component.get("component_kind"),
                    f"package_candidate.components[{index}].component_kind",
                ),
                "label": _require_non_empty_string(
                    component.get("label"),
                    f"package_candidate.components[{index}].label",
                ),
                "normalized_key": _require_non_empty_string(
                    component.get("normalized_key"),
                    f"package_candidate.components[{index}].normalized_key",
                ),
                "slot": _optional_string(component.get("slot")),
            }
        )
    return components


def _validate_supporting_evidence_ids(
    candidate: Mapping[str, Any],
    *,
    attachment_lookup: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    evidence_ids = [
        _require_non_empty_string(
            value,
            f"package_candidate.supporting_evidence_ids[{index}]",
        )
        for index, value in enumerate(
            _require_list(candidate.get("supporting_evidence_ids"), "package_candidate.supporting_evidence_ids")
        )
    ]
    if not evidence_ids:
        raise PublicBuildPackagePriorCookbookContractError(
            "package_candidate.supporting_evidence_ids must not be empty."
        )
    missing = [attachment_id for attachment_id in evidence_ids if attachment_id not in attachment_lookup]
    if missing:
        raise PublicBuildPackagePriorCookbookContractError(
            "package_candidate.supporting_evidence_ids must resolve to trace attachments: "
            + ", ".join(sorted(missing))
        )
    non_ninja_snapshot = [
        attachment_id
        for attachment_id in evidence_ids
        if _require_non_empty_string(
            attachment_lookup[attachment_id].get("attachment_kind"),
            f"trace_attachment[{attachment_id}].attachment_kind",
        )
        != "ninja_snapshot"
    ]
    if non_ninja_snapshot:
        raise PublicBuildPackagePriorCookbookContractError(
            "package_candidate.supporting_evidence_ids must stay linked to "
            "attachment_kind = ninja_snapshot traces."
        )
    return evidence_ids


def _component_constraint(component: Mapping[str, Any]) -> dict[str, Any]:
    component_kind = _require_non_empty_string(
        component.get("component_kind"),
        "package_component.component_kind",
    )
    label = _require_non_empty_string(component.get("label"), "package_component.label")
    normalized_key = _require_non_empty_string(
        component.get("normalized_key"),
        "package_component.normalized_key",
    )
    slot = _optional_string(component.get("slot"))
    mapping = {
        "ascendancy": (
            "ascendancy_match",
            "Only seed search when the active shell still targets this ascendancy.",
        ),
        "skill": (
            "primary_skill_overlap",
            "Only seed search when the build brief or active variant still centers on this skill.",
        ),
        "keystone": (
            "keystone_feasibility",
            "Only keep the prior active while this keystone remains reachable and policy-legal.",
        ),
        "equipment": (
            "slot_compatibility",
            "Only seed search when the named equipment slot can absorb this package cost.",
        ),
        "flask": (
            "flask_slot_compatibility",
            "Only seed search when flask slots, suffixes, and uptime intent remain compatible.",
        ),
    }
    constraint_kind, note = mapping.get(
        component_kind,
        (
            "component_compatibility",
            "Only seed search while this public-build component remains compatible with the active shell.",
        ),
    )
    constraint: dict[str, Any] = {
        "constraint_kind": constraint_kind,
        "component_key": normalized_key,
        "component_label": label,
        "note": note,
    }
    if slot is not None:
        constraint["slot"] = slot
    return constraint


def _family_constraints(family: str, components: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if family == "weapon_quiver_pair":
        return [
            {
                "constraint_kind": "paired_slot_availability",
                "component_keys": [
                    component["normalized_key"]
                    for component in components
                    if component["component_kind"] == "equipment"
                ],
                "note": "Only seed search when both paired weapon and quiver slots can move together without breaking the active shell.",
            }
        ]
    if family == "flask_engine":
        return [
            {
                "constraint_kind": "full_flask_package_room",
                "component_keys": [
                    component["normalized_key"]
                    for component in components
                    if component["component_kind"] == "flask"
                ],
                "note": "Only seed search when the flask plan still has room for the repeated package and its suffix obligations.",
            }
        ]
    if family == "skill_shell":
        return [
            {
                "constraint_kind": "shell_alignment",
                "component_keys": [component["normalized_key"] for component in components],
                "note": "Only seed search when the combined ascendancy, skill, and keystone shell still matches the active build direction.",
            }
        ]
    return [
        {
            "constraint_kind": "family_alignment",
            "component_keys": [component["normalized_key"] for component in components],
            "note": f"Only seed search while the {family} package still fits the active build shell.",
        }
    ]


def _invalidation_signals(family: str) -> list[dict[str, str]]:
    signals = [
        {
            "signal_kind": "stale_supporting_public_build_traces",
            "note": "Refresh the bounded public-build lane before reusing the prior after the 7d window or when fresher traces disagree.",
        },
        {
            "signal_kind": "league_scope_changed",
            "note": "Invalidate the prior for this ask when the target league or requested time-machine window changes.",
        },
        {
            "signal_kind": "brief_conflicts_with_package_components",
            "note": "Invalidate the prior when the build brief or accepted shell explicitly conflicts with the package components.",
        },
        {
            "signal_kind": "support_drops_below_minimum_after_refresh",
            "note": "Invalidate the prior when refreshed accepted pattern evidence no longer clears the miner support threshold.",
        },
        {
            "signal_kind": "authoritative_pob_compare_disagrees",
            "note": "Invalidate the prior for the active shell if authoritative PoB compare does not confirm the expected package value.",
        },
    ]
    if family == "weapon_quiver_pair":
        signals.append(
            {
                "signal_kind": "paired_slot_pressure_conflict",
                "note": "Invalidate the prior if weapon or quiver slot pressure blocks the pair in the active shell.",
            }
        )
    if family == "flask_engine":
        signals.append(
            {
                "signal_kind": "flask_plan_conflict",
                "note": "Invalidate the prior if flask uptime, suffix, or empty-slot conditions no longer hold.",
            }
        )
    return signals


def _required_downstream_checks(family: str) -> list[dict[str, str]]:
    checks = [
        {
            "check_kind": "authoritative_pob_compare",
            "note": "Required before selection, publication, or rejection because the cookbook is only a public-build acceleration hint.",
        },
        {
            "check_kind": "budget_and_constraint_cross_check",
            "note": "Required before escalation because public-build prevalence does not guarantee budget fit or policy fit.",
        },
    ]
    if family in {"weapon_quiver_pair", "flask_engine"}:
        checks.append(
            {
                "check_kind": "slot_plan_review",
                "note": "Required to confirm the active slot plan can absorb this package before investing full compare budget.",
            }
        )
    return checks


def _seed_policy(taxonomy_kind: str, default_adjacent_search_seed: bool) -> dict[str, Any]:
    is_blocked_low_information = taxonomy_kind in BLOCKED_DEFAULT_SEED_TAXONOMY_KINDS
    return {
        "default_adjacent_search_seed": bool(default_adjacent_search_seed)
        and not is_blocked_low_information,
        "taxonomy_seed_gate": "allowed_soft_seed"
        if bool(default_adjacent_search_seed) and not is_blocked_low_information
        else "blocked_low_information",
        "blocked_low_information_kinds": sorted(BLOCKED_DEFAULT_SEED_TAXONOMY_KINDS),
        "requires_explicit_interaction_evidence_for_combo": True,
    }


class PublicBuildPackagePriorCookbookMaterializer:
    """Materialize explicit package-prior cookbook entries from accepted pattern research."""

    def materialize_from_pattern_research(
        self,
        pattern_research_payload: Mapping[str, Any],
        *,
        materialized_at: str | None = None,
    ) -> dict[str, Any]:
        _validate_pattern_research_payload(pattern_research_payload)
        source = _require_mapping(pattern_research_payload.get("source"), "pattern_research.source")
        query_scope = _require_mapping(pattern_research_payload.get("query_scope"), "pattern_research.query_scope")
        attachment_lookup = _attachment_lookup(pattern_research_payload)
        materialized_at_value = materialized_at or _utc_now_iso()

        cookbook_entries: list[dict[str, Any]] = []
        for index, raw_candidate in enumerate(
            _require_list(pattern_research_payload.get("package_candidates"), "pattern_research.package_candidates")
        ):
            candidate = _require_mapping(raw_candidate, f"pattern_research.package_candidates[{index}]")
            candidate_kind = _require_non_empty_string(
                candidate.get("candidate_kind"),
                f"pattern_research.package_candidates[{index}].candidate_kind",
            )
            if candidate_kind != "research_lead":
                raise PublicBuildPackagePriorCookbookContractError(
                    "Cookbook materialization accepts only candidate_kind = research_lead entries."
                )
            status = _require_non_empty_string(
                candidate.get("status"),
                f"pattern_research.package_candidates[{index}].status",
            )
            if status != "active":
                raise PublicBuildPackagePriorCookbookContractError(
                    "Cookbook materialization accepts only active research leads."
                )

            candidate_id = _require_non_empty_string(
                candidate.get("candidate_id"),
                f"pattern_research.package_candidates[{index}].candidate_id",
            )
            family = _require_non_empty_string(
                candidate.get("family"),
                f"pattern_research.package_candidates[{index}].family",
            )
            taxonomy_kind = _require_non_empty_string(
                candidate.get("taxonomy_kind"),
                f"pattern_research.package_candidates[{index}].taxonomy_kind",
            )
            default_adjacent_search_seed = candidate.get("default_adjacent_search_seed")
            if not isinstance(default_adjacent_search_seed, bool):
                raise PublicBuildPackagePriorCookbookContractError(
                    f"pattern_research.package_candidates[{index}].default_adjacent_search_seed must be a boolean."
                )
            interaction_evidence = [
                _require_non_empty_string(
                    value,
                    f"pattern_research.package_candidates[{index}].interaction_evidence[{evidence_index}]",
                )
                for evidence_index, value in enumerate(
                    _require_list(
                        candidate.get("interaction_evidence"),
                        f"pattern_research.package_candidates[{index}].interaction_evidence",
                    )
                )
            ]
            if taxonomy_kind == "mechanic_combo" and not interaction_evidence:
                raise PublicBuildPackagePriorCookbookContractError(
                    "mechanic_combo candidates must include explicit interaction_evidence."
                )
            seed_policy = _seed_policy(taxonomy_kind, default_adjacent_search_seed)
            components = _candidate_components(candidate)
            supporting_evidence_ids = _validate_supporting_evidence_ids(
                candidate,
                attachment_lookup=attachment_lookup,
            )
            candidate_freshness = _require_mapping(
                candidate.get("freshness"),
                f"pattern_research.package_candidates[{index}].freshness",
            )
            candidate_provenance = _require_mapping(
                candidate.get("provenance"),
                f"pattern_research.package_candidates[{index}].provenance",
            )
            source_refs = [
                _require_mapping(
                    value,
                    f"pattern_research.package_candidates[{index}].source_refs[{ref_index}]",
                )
                for ref_index, value in enumerate(
                    _require_list(
                        candidate.get("source_refs"),
                        f"pattern_research.package_candidates[{index}].source_refs",
                    )
                )
            ]
            cookbook_entries.append(
                {
                    "entry_id": _entry_id(candidate_id, family),
                    "entry_kind": PUBLIC_BUILD_PACKAGE_PRIOR_ENTRY_KIND,
                    "entry_label": _require_non_empty_string(
                        candidate.get("candidate_label"),
                        f"pattern_research.package_candidates[{index}].candidate_label",
                    ),
                    "search_input_kind": PUBLIC_BUILD_PACKAGE_PRIOR_ENFORCEMENT_LEVEL,
                    "package_family": family,
                    "taxonomy_kind": taxonomy_kind,
                    "interaction_evidence": interaction_evidence,
                    "seed_policy": seed_policy,
                    "source_candidate_id": candidate_id,
                    "package_components": components,
                    "search_seed": {
                        "seed_component_keys": [component["normalized_key"] for component in components],
                        "seed_labels": [component["label"] for component in components],
                        "default_adjacent_search_seed": seed_policy["default_adjacent_search_seed"],
                        "taxonomy_seed_gate": seed_policy["taxonomy_seed_gate"],
                        "why_it_can_seed_search": _require_non_empty_string(
                            candidate.get("summary"),
                            f"pattern_research.package_candidates[{index}].summary",
                        ),
                    },
                    "supporting_evidence_ids": supporting_evidence_ids,
                    "observed_support": _require_mapping(
                        candidate.get("observed_support"),
                        f"pattern_research.package_candidates[{index}].observed_support",
                    ),
                    "league_scope": _require_mapping(
                        candidate.get("league_scope"),
                        f"pattern_research.package_candidates[{index}].league_scope",
                    ),
                    "freshness": {
                        "materialized_at": materialized_at_value,
                        "source_captured_at": _require_non_empty_string(
                            candidate_freshness.get("captured_at"),
                            f"pattern_research.package_candidates[{index}].freshness.captured_at",
                        ),
                        "supporting_retrieved_at": list(
                            _require_list(
                                candidate_freshness.get("supporting_retrieved_at"),
                                f"pattern_research.package_candidates[{index}].freshness.supporting_retrieved_at",
                            )
                        ),
                        "observed_data_timestamps": list(
                            _require_list(
                                candidate_freshness.get("observed_data_timestamps"),
                                f"pattern_research.package_candidates[{index}].freshness.observed_data_timestamps",
                            )
                        ),
                        "max_reuse_window_hours": PUBLIC_BUILD_PACKAGE_PRIOR_MAX_REUSE_WINDOW_HOURS,
                        "freshness_note": (
                            "Refresh the bounded public-build lane before reuse after the 7d comparison window, "
                            "or earlier if a fresher league scope or PoB compare contradicts the package."
                        ),
                    },
                    "provenance": {
                        "source_record_kind": POE_NINJA_PATTERN_MINER_RECORD_KIND,
                        "source_generator": _require_non_empty_string(
                            source.get("generator"),
                            "pattern_research.source.generator",
                        ),
                        "source_candidate_id": candidate_id,
                        "source_refs": source_refs,
                        "derived_from_record_kinds": list(
                            _require_list(
                                candidate_provenance.get("derived_from_record_kinds"),
                                f"pattern_research.package_candidates[{index}].provenance.derived_from_record_kinds",
                            )
                        ),
                        "notes": [
                            "Materialized only from accepted bounded public-build pattern evidence.",
                            "Cookbook entries stay soft search inputs and reuse explicit ninja_snapshot trace links instead of hidden memory.",
                        ],
                    },
                    "applicability_constraints": [
                        *(_component_constraint(component) for component in components),
                        *_family_constraints(family, components),
                    ],
                    "invalidation_signals": _invalidation_signals(family),
                    "required_downstream_checks": _required_downstream_checks(family),
                    "soft_input_rules": {
                        "enforcement_level": PUBLIC_BUILD_PACKAGE_PRIOR_ENFORCEMENT_LEVEL,
                        "requires_authoritative_pob_cross_check": True,
                        "forbidden_final_winner_evidence": True,
                        "forbidden_actions": [
                            "hard_accept",
                            "hard_reject",
                            "publish_without_pob_compare",
                            "treat_public_build_prevalence_as_mechanics_authority",
                        ],
                    },
                }
            )

        return {
            "schema_version": PUBLIC_BUILD_PACKAGE_PRIOR_COOKBOOK_SCHEMA_VERSION,
            "record_kind": PUBLIC_BUILD_PACKAGE_PRIOR_COOKBOOK_RECORD_KIND,
            "source": {
                "generator": PUBLIC_BUILD_PACKAGE_PRIOR_COOKBOOK_GENERATOR,
                "source_record_kind": POE_NINJA_PATTERN_MINER_RECORD_KIND,
                "source_generator": _require_non_empty_string(
                    source.get("generator"),
                    "pattern_research.source.generator",
                ),
                "source_id": _require_non_empty_string(source.get("source_id"), "pattern_research.source.source_id"),
                "upstream_system": _require_non_empty_string(
                    source.get("upstream_system"),
                    "pattern_research.source.upstream_system",
                ),
                "source_role": _require_non_empty_string(
                    source.get("source_role"),
                    "pattern_research.source.source_role",
                ),
            },
            "materialized_at": materialized_at_value,
            "query_scope": {
                "league_url": _require_non_empty_string(
                    query_scope.get("league_url"),
                    "pattern_research.query_scope.league_url",
                ),
                "snapshot_type": _require_non_empty_string(
                    query_scope.get("snapshot_type"),
                    "pattern_research.query_scope.snapshot_type",
                ),
                "requested_time_machine": _optional_string(query_scope.get("requested_time_machine")),
                "filters": list(_require_list(query_scope.get("filters"), "pattern_research.query_scope.filters")),
                "profile_sample_size": query_scope.get("profile_sample_size"),
                "minimum_support": query_scope.get("minimum_support"),
            },
            "cookbook_entries": cookbook_entries,
            "notes": [
                "Cookbook entries are dynamic soft search inputs derived from accepted public-build pattern evidence.",
                "Do not commit live cookbook snapshots, treat prevalence as final truth, or skip authoritative PoB compare.",
            ],
        }


__all__ = [
    "PUBLIC_BUILD_PACKAGE_PRIOR_COOKBOOK_GENERATOR",
    "PUBLIC_BUILD_PACKAGE_PRIOR_COOKBOOK_RECORD_KIND",
    "PUBLIC_BUILD_PACKAGE_PRIOR_COOKBOOK_SCHEMA_VERSION",
    "PUBLIC_BUILD_PACKAGE_PRIOR_ENFORCEMENT_LEVEL",
    "PUBLIC_BUILD_PACKAGE_PRIOR_ENTRY_KIND",
    "PUBLIC_BUILD_PACKAGE_PRIOR_MAX_REUSE_WINDOW_HOURS",
    "PublicBuildPackagePriorCookbookContractError",
    "PublicBuildPackagePriorCookbookMaterializer",
]
