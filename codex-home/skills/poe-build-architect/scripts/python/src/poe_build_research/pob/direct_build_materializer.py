"""Direct Build producer/materializer for agent-authored PoB packages.

This module is deliberately not a build generator. It accepts agent-authored
decision artifacts, checks the proof boundary, applies explicit source
surfaces to PoB, and publishes only after the import publication verifier.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import zlib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .artifacts import sha256_bytes, write_json
from .direct_build_early_game_rails import build_direct_build_early_game_rails_report
from .headless_runtime_adapter import PinnedPoBHeadlessRuntimeAdapter
from .host_runtime import PoBHeadlessHostRequest, create_headless_proof_run
from .import_code_verifier import ImportCodeVerifier, verify_direct_build_import_publication_inputs
from .item_mod_lookup import (
    EARLY_GAME_MAX_BASE_REQUIRED_LEVEL,
    affix_allowed_on_item_class,
    affix_exists_anywhere,
    base_identity_matches,
    base_implicit_matches,
    base_required_level,
    item_class_for_base,
    lookup_affix_tier,
    proof_affix_numeric_values,
    resolve_item_base,
    tier_number,
    tier_value_range,
)
from .proof_export_reopen import PoBProofStateObservation, publish_ready_pob_import
from .release_manager import PoBReleaseManager, utc_now_iso
from .tree_visual_inspection import validate_tree_visual_inspection_artifact

DIRECT_BUILD_DECISION_LEDGER_RECORD_KIND = "direct_build_decision_ledger"
DIRECT_BUILD_SEMANTIC_VALIDATION_RECORD_KIND = "direct_build_semantic_validation"
DIRECT_BUILD_MATERIALIZATION_SOURCE_PACKET_RECORD_KIND = "direct_build_materialization_source_packet"
DIRECT_BUILD_PRE_MATERIALIZATION_CHECKPOINT_RECORD_KIND = "direct_build_pre_materialization_checkpoint"
DIRECT_BUILD_PRODUCTION_RESULT_RECORD_KIND = "direct_build_materialization_production_result"
DIRECT_BUILD_MATERIALIZATION_RESULT_RECORD_KIND = "direct_build_materialization_result"
DIRECT_BUILD_OUTPUT_RECORD_KIND = "direct_build_output"
DIRECT_BUILD_OUTPUT_SCHEMA_VERSION = "1.0.0"
PRODUCT_ARTIFACT_MODE = "product"
EARLY_GAME_DIRECT_BUILD_LANE = "early_game"
EARLY_GAME_ALLOWED_BANDIT_VALUES = {"kill_all", "kill all", "none"}
EARLY_GAME_ALLOWED_BOSS_MARKERS = ("guardian", "pinnacle")
EARLY_GAME_MAX_TRAVEL_TAX_RATIO = 0.35
EARLY_GAME_ALLOWED_LOADOUT_LANES = {"early_game", "starter", "starter_rare", "campaign_to_early_maps"}
EARLY_GAME_MAX_EXPLICIT_AFFIXES_PER_RARE = 3
EARLY_GAME_BEST_ALLOWED_AFFIX_TIER = 3
EARLY_GAME_ELEMENTAL_RESIST_TARGET = 75.0
EARLY_GAME_CHAOS_RESIST_TARGET = 25.0
UNIVERSAL_CONFIG_STATE_KEYS = {
    "is_ignited",
    "enemy_ignited",
    "enemy_is_ignited",
    "conditionenemyignited",
    "condition_enemy_ignited",
    "ignited",
    "is_burning",
    "enemy_burning",
    "is_shocked",
    "enemy_shocked",
    "conditionenemyshocked",
    "condition_enemy_shocked",
    "shock",
    "shock_effect",
    "exposure",
    "fire_exposure",
    "cold_exposure",
    "lightning_exposure",
    "curse",
    "curses",
    "enemy_cursed",
    "onslaught",
    "has_onslaught",
    "buffonslaught",
    "using_flask",
    "conditionusingflask",
    "flask_active",
    "flasks_active",
    "fortification",
    "bufffortification",
    "fortify",
    "leeching",
    "life_leeching",
    "mana_leeching",
    "power_charges",
    "frenzy_charges",
    "endurance_charges",
    "charges",
}
UNIVERSAL_SKILL_COUNT_KEYS = {
    "hit_count",
    "skill_hit_count",
    "full_dps_hit_count",
    "hit_count_override",
    "projectile_count",
    "overlap_count",
    "repeat_count",
    "full_dps_count",
    "count",
    "hits",
}
REQUIRED_MUTATION_KINDS = ("identity", "skill", "tree", "item", "config")
REQUIRED_MATERIALIZATION_SURFACES = (
    "identity_state",
    "skill_state",
    "tree_state",
    "item_state",
    "config_state",
)
COST_AWARE_REF_FIELDS = (
    "pre_pob_hypothesis_triage_refs",
    "comparison_protocol_refs",
    "action_cost_value_ledger_refs",
    "calc_snapshot_diff_refs",
    "pathing_opportunity_cost_refs",
    "surface_impact_classification_refs",
)
REQUIRED_COST_AWARE_DECISION_REFS = (
    "action_cost_value_ledger_refs",
    "comparison_protocol_refs",
)
TREE_PATHING_COST_AWARE_REFS = ("pathing_opportunity_cost_refs",)
MEASURED_EVIDENCE_COST_AWARE_REFS = ("calc_snapshot_diff_refs",)
SURFACE_TO_APPLY_METHOD = {
    "identity_state": "apply_identity_state",
    "skill_state": "apply_skill_state",
    "tree_state": "apply_tree_state",
    "item_state": "apply_item_state",
    "config_state": "apply_config_state",
}
SUPPORTED_TREE_APPLY_FIELDS = frozenset(
    {
        "active_spec_id",
        "class_id",
        "ascendancy_id",
        "secondary_ascendancy_id",
        "ascendancy_node_ids",
        "ascendancy_notable_node_ids",
        "user_allocated_node_ids",
        "keystone_node_ids",
        "mastery_effect_ids",
        "cluster_jewel_socket_ids",
        "socketed_jewel_node_ids",
        "anoint_allocations",
        "override_carrier_node_ids",
        "override_carriers",
        "cluster_jewel_items",
        "socketed_jewel_items",
    }
)
TREE_STATE_SOURCE_QUALITY_METADATA_FIELDS = frozenset(
    {
        "accepted_agent_payload",
        "allocated_masteries",
        "constraint_repair_evidence_refs",
        "irrelevant_stat_evidence_refs",
        "irrelevant_stat_justification",
        "masteries",
        "masteries_considered",
        "mastery_allocations",
        "no_masteries_justification",
        "pathing_cleanup_notes",
        "pathing_cleanup_steps",
        "quality_rails",
        "relevance_tags",
        "semantic_relevance_justification",
        "semantic_relevance_tags",
        "travel_tax_ratio",
        "tree_semantic_evidence_refs",
        "tree_visual_inspection",
        "visual_inspection",
        "visual_tree_inspection",
    }
)
ITEM_STATE_APPLY_FIELDS = frozenset({"active_item_set_id", "item_sets"})
ITEM_STATE_SOURCE_QUALITY_METADATA_FIELDS = frozenset(
    {
        "accepted_agent_payload",
        "early_game_loadout_rails",
        "equipped_items",
        "gear_slots",
        "item_loadout_rails",
        "item_shell",
        "item_proofs",
        "items",
        "loadout_rails",
        "proof_items",
        "raw_items",
        "structured_items",
    }
)
CONFIG_STATE_APPLY_FIELDS = frozenset({"active_config_set_id", "config_sets"})
CONFIG_STATE_SOURCE_QUALITY_METADATA_FIELDS = frozenset(
    {
        "accepted_agent_payload",
        "pob_authoring_evidence_refs",
        "config_state_evidence_refs",
        "enabled_config_evidence_refs",
        "conditional_state_evidence_refs",
        "ignite_chance_evidence_refs",
        "ignite_sustain_evidence_refs",
        "enemy_ignited_evidence_refs",
        "enemy_burning_evidence_refs",
        "ignite_config_evidence_refs",
        "shock_threshold_evidence_refs",
        "pinnacle_shock_threshold_evidence_refs",
        "guardian_shock_threshold_evidence_refs",
        "shock_hit_damage_evidence_refs",
        "shock_effect_evidence_refs",
        "expected_shock_effect_evidence_refs",
        "shock_sustain_evidence_refs",
        "shock_uptime_evidence_refs",
        "shock_proof",
        "shock_threshold_proof",
        "pinnacle_shock_proof",
        "ignite_proof",
        "ignite_sustain_proof",
        "enemy_ignited_proof",
    }
)
WRAPPER_ENTRYPOINT_REF = "src/poe_build_research/pob/headless_wrapper.lua"


class DirectBuildMaterializerError(RuntimeError):
    """Raised when a Direct Build materialization contract cannot proceed."""


RuntimeAdapterFactory = Callable[[], Any]


def encode_pob_import_code(xml_text: str) -> str:
    """Encode PoB XML into the operator-pasteable PoB import string envelope."""

    if not isinstance(xml_text, str) or not xml_text.strip():
        raise DirectBuildMaterializerError("PoB XML must be non-empty text.")
    return base64.b64encode(zlib.compress(xml_text.encode("utf-8"), level=9)).decode("ascii").replace(
        "+",
        "-",
    ).replace("/", "_")


def produce_direct_build_materialization_package(
    *,
    decision_ledger_path: Path,
    output_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Produce semantic/source/checkpoint artifacts from one agent-authored ledger."""

    ledger_input_path = Path(decision_ledger_path).resolve(strict=True)
    target_dir = Path(output_dir).resolve(strict=False)
    target_dir.mkdir(parents=True, exist_ok=True)
    ledger = _load_json_mapping(ledger_input_path, label="decision ledger")
    generated = _string(ledger.get("generated_at")) or generated_at or utc_now_iso()

    semantic = build_direct_build_semantic_validation(ledger, generated_at=generated)
    source_packet = build_direct_build_materialization_source_packet(
        ledger,
        semantic_validation=semantic,
        generated_at=generated,
    )
    checkpoint = build_direct_build_pre_materialization_checkpoint(
        source_packet,
        semantic_validation=semantic,
        generated_at=generated,
    )

    ledger_path = target_dir / "direct-build-decision-ledger.json"
    semantic_path = target_dir / "direct-build-semantic-validation.json"
    source_packet_path = target_dir / "materialization-source-packet.json"
    checkpoint_path = target_dir / "pob-pre-materialization-checkpoint.json"
    write_json(ledger_path, dict(ledger))
    write_json(semantic_path, semantic)
    write_json(source_packet_path, source_packet)
    write_json(checkpoint_path, checkpoint)

    blockers = [
        *_semantic_findings_as_blockers(semantic),
        *_source_packet_blockers_as_publication_blockers(source_packet),
        *_checkpoint_blockers_as_publication_blockers(checkpoint),
    ]
    accepted = not blockers
    result = {
        "schema_version": "1.0.0",
        "record_kind": DIRECT_BUILD_PRODUCTION_RESULT_RECORD_KIND,
        "status": "accepted" if accepted else "blocked",
        "ledger_id": _string(semantic.get("ledger_id")),
        "generated_at": generated,
        "artifact_mode": _string(semantic.get("artifact_mode")),
        "artifact_locators": {
            "decision_ledger": _path_string(ledger_path),
            "semantic_validation": _path_string(semantic_path),
            "materialization_source_packet": _path_string(source_packet_path),
            "pre_materialization_checkpoint": _path_string(checkpoint_path),
        },
        "publication_guard": {
            "materialization_allowed": accepted,
            "direct_build_output_allowed": accepted,
        },
        "blockers": blockers,
    }
    write_json(target_dir / "direct-build-materialization-production-result.json", result)
    return result


def build_direct_build_semantic_validation(
    decision_ledger: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Validate the ledger identity and mandatory agent-decision discipline."""

    ledger = _mapping(decision_ledger)
    findings = _decision_ledger_findings(ledger)
    return {
        "record_kind": DIRECT_BUILD_SEMANTIC_VALIDATION_RECORD_KIND,
        "ledger_id": _string(ledger.get("ledger_id")) or "missing-ledger-id",
        "generated_at": generated_at or _string(ledger.get("generated_at")) or utc_now_iso(),
        "artifact_mode": _string(ledger.get("artifact_mode")) or PRODUCT_ARTIFACT_MODE,
        "status": "passed" if not findings else "needs_revision",
        "finding_count": len(findings),
        "findings": findings,
    }


def build_direct_build_materialization_source_packet(
    decision_ledger: Mapping[str, Any],
    *,
    semantic_validation: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the source packet consumed by the PoB materializer."""

    ledger = _mapping(decision_ledger)
    semantic = _mapping(semantic_validation)
    blockers = []
    if _string(semantic.get("status")) != "passed":
        blockers.append(
            _blocker(
                "semantic_validation_not_passed",
                "Decision ledger semantic validation did not pass.",
                "Repair the agent-authored decision ledger before materialization.",
            )
        )
    blockers.extend(_source_packet_blockers(ledger))
    materialization_payload = ledger.get("materialization_payload")
    source_ready = not blockers
    return {
        "record_kind": DIRECT_BUILD_MATERIALIZATION_SOURCE_PACKET_RECORD_KIND,
        "ledger_id": _string(semantic.get("ledger_id")) or _string(ledger.get("ledger_id")),
        "generated_at": generated_at or _string(semantic.get("generated_at")) or utc_now_iso(),
        "artifact_mode": _string(semantic.get("artifact_mode")) or PRODUCT_ARTIFACT_MODE,
        "status": "source_ready" if source_ready else "blocked",
        "source_policy": "accepted_agent_authored_decision_rows_only",
        "build_identity": dict(_mapping(ledger.get("build_identity"))),
        "direct_build_lane": _direct_build_lane(ledger),
        "direct_build_decision_trace": dict(_mapping(ledger.get("direct_build_decision_trace"))),
        "repair_context": dict(_mapping(ledger.get("repair_context"))),
        "cost_value_contract": _cost_value_contract_summary(ledger),
        "cost_aware_artifact_refs": _collect_cost_aware_artifact_refs(ledger),
        "cost_aware_decision_rows": _cost_aware_decision_rows(ledger),
        "materialization_payload": dict(materialization_payload) if isinstance(materialization_payload, Mapping) else {},
        "decision_row_count": len(_accepted_decision_rows(ledger)),
        "required_mutation_kinds": list(REQUIRED_MUTATION_KINDS),
        "publication_guard": {
            "source_packet_ready": source_ready,
            "pre_materialization_checkpoint_allowed": source_ready,
        },
        "blockers": blockers,
    }


def build_direct_build_pre_materialization_checkpoint(
    materialization_source_packet: Mapping[str, Any],
    *,
    semantic_validation: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the final fail-closed checkpoint before PoB materialization."""

    source_packet = _mapping(materialization_source_packet)
    semantic = _mapping(semantic_validation)
    blockers = []
    if _string(source_packet.get("status")) != "source_ready":
        blockers.append(
            _blocker(
                "materialization_source_packet_not_ready",
                "Materialization source packet is not source_ready.",
                "Repair source packet blockers before starting PoB materialization.",
            )
        )
    blockers.extend(_source_packet_blockers_as_publication_blockers(source_packet))
    passed = not blockers
    return {
        "record_kind": DIRECT_BUILD_PRE_MATERIALIZATION_CHECKPOINT_RECORD_KIND,
        "ledger_id": _string(semantic.get("ledger_id")) or _string(source_packet.get("ledger_id")),
        "generated_at": generated_at or _string(semantic.get("generated_at")) or utc_now_iso(),
        "artifact_mode": _string(semantic.get("artifact_mode")) or _string(source_packet.get("artifact_mode")),
        "status": "passed" if passed else "blocked",
        "source_policy": "accepted_decision_ledger_rows_only",
        "blockers": blockers,
        "publication_guard": {
            "direct_build_output_allowed": passed,
            "ready_pob_import_allowed": passed,
        },
        "materialization_source_packet": {
            "status": _string(source_packet.get("status")),
            "ledger_id": _string(source_packet.get("ledger_id")),
        },
    }


def materialize_direct_build_publication(
    *,
    semantic_validation_path: Path,
    materialization_source_packet_path: Path,
    pre_materialization_checkpoint_path: Path,
    output_dir: Path,
    artifacts_root: Path,
    pob_run_id: str | None = None,
    release_manager: PoBReleaseManager | None = None,
    runtime_adapter_factory: RuntimeAdapterFactory | None = None,
    verifier: ImportCodeVerifier | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Apply explicit source surfaces to PoB and publish DirectBuildOutput if verified."""

    semantic_path = Path(semantic_validation_path).resolve(strict=True)
    source_path = Path(materialization_source_packet_path).resolve(strict=True)
    checkpoint_path = Path(pre_materialization_checkpoint_path).resolve(strict=True)
    target_dir = Path(output_dir).resolve(strict=False)
    target_dir.mkdir(parents=True, exist_ok=True)
    artifacts = Path(artifacts_root).resolve(strict=False)
    semantic = _load_json_mapping(semantic_path, label="semantic validation")
    source_packet = _load_json_mapping(source_path, label="materialization source packet")
    checkpoint = _load_json_mapping(checkpoint_path, label="pre-materialization checkpoint")
    generated = generated_at or utc_now_iso()
    run_id = pob_run_id or _default_pob_run_id(source_packet)

    preflight_blockers = [
        *_source_packet_blockers_as_publication_blockers(source_packet),
        *_checkpoint_blockers_as_publication_blockers(checkpoint),
    ]
    if _string(semantic.get("status")) != "passed":
        preflight_blockers.append(
            _blocker(
                "semantic_validation_not_passed",
                "Semantic validation did not pass.",
                "Repair semantic validation before materialization.",
            )
        )
    if _string(source_packet.get("status")) != "source_ready":
        preflight_blockers.append(
            _blocker(
                "materialization_source_packet_not_ready",
                "Materialization source packet is not source_ready.",
                "Repair source packet blockers before materialization.",
            )
        )
    if _string(checkpoint.get("status")) != "passed":
        preflight_blockers.append(
            _blocker(
                "pre_materialization_checkpoint_not_passed",
                "Pre-materialization checkpoint did not pass.",
                "Pass the checkpoint before materialization.",
            )
        )

    xml_path = target_dir / "ready-pob-import.xml"
    import_code_path = target_dir / "ready-pob-import.pobcode.txt"
    direct_build_output_path = target_dir / "direct-build-output.json"
    calc_snapshot_path = target_dir / "normalized-calc-snapshot.json"
    early_game_rails_report_path = target_dir / "early-game-rails-report.json"
    verification_result: dict[str, Any] | None = None
    run = None
    readback_state: dict[str, Any] | None = None
    calc_snapshot: dict[str, Any] | None = None
    runtime_blockers: list[dict[str, Any]] = []

    if not preflight_blockers:
        manager = release_manager or PoBReleaseManager()
        adapter = (runtime_adapter_factory or (lambda: PinnedPoBHeadlessRuntimeAdapter(release_manager=manager)))()
        run = create_headless_proof_run(
            PoBHeadlessHostRequest(
                pob_run_id=run_id,
                export_surface_kind="pob_xml",
                wrapper_entrypoint_ref=WRAPPER_ENTRYPOINT_REF,
            ),
            release_manager=manager,
            artifacts_root=artifacts,
        )
        normal_live = False
        try:
            normal = run.bootstrap_session("normal")
            normal = run.launch_session(normal, launcher=adapter.launch_session)
            normal_live = True
            adapter.create_blank_build(normal)
            _apply_materialization_payload(adapter, normal, _mapping(source_packet.get("materialization_payload")))
            readback_state = adapter.read_state(normal)
            calc_snapshot = adapter.read_calc_snapshot(normal)
            xml_text = adapter.export_build_artifact(normal)
            shutdown = adapter.shutdown_session(normal)
            normal_live = False
            normal = run.seal_session(
                normal,
                exit_code=shutdown.exit_code,
                termination=shutdown.termination,
                process_exit_observed=shutdown.process_exit_observed,
            )
            pre_export_observation = PoBProofStateObservation(
                observation_id=f"pre-export.{_safe_ref(run_id)}",
                gear_slots=readback_state.get("gear_slots") or readback_state.get("items_state") or {},
                tree_state=dict(_mapping(readback_state.get("tree_state"))),
                skills_state=dict(_mapping(readback_state.get("skills_state"))),
                config_state=dict(_mapping(readback_state.get("config_state"))),
            )
            publish_ready_pob_import(
                run,
                normal,
                pre_export_observation=pre_export_observation,
                export_observation_id=f"export.{_safe_ref(run_id)}",
                export_payload=xml_text,
            )
            xml_path.write_text(xml_text, encoding="utf-8", newline="\n")
            import_code_path.write_text(encode_pob_import_code(xml_text), encoding="utf-8", newline="\n")
            normalized_calc_snapshot = _normalized_calc_snapshot_for_rails(calc_snapshot)
            write_json(calc_snapshot_path, normalized_calc_snapshot)
            runtime_blockers.extend(
                _early_game_rails_blockers(
                    source_packet,
                    pob_xml_text=xml_text,
                    normalized_calc_snapshot=normalized_calc_snapshot,
                    report_path=early_game_rails_report_path,
                )
            )
        except Exception as exc:  # pragma: no cover - exact runtime errors are environment dependent
            runtime_blockers.append(
                _blocker(
                    "pob_materialization_failed",
                    f"PoB materialization failed before a verified import could be published: {type(exc).__name__}: {exc}",
                    "Repair the source payload or pinned PoB runtime and rerun materialization.",
                )
            )
            if normal_live:
                try:
                    adapter.shutdown_session(normal)
                except Exception:
                    pass
        finally:
            adapter.close()

    if import_code_path.is_file():
        verification_result = verify_direct_build_import_publication_inputs(
            semantic_validation_path=semantic_path,
            materialization_source_packet_path=source_path,
            pre_materialization_checkpoint_path=checkpoint_path,
            ready_pob_import_code_path=import_code_path,
            artifacts_root=artifacts / "icv",
            pob_run_id=_import_verifier_pob_run_id(run_id),
            verifier=verifier,
            additional_blockers=runtime_blockers,
        )
    elif not preflight_blockers:
        preflight_blockers.append(
            _blocker(
                "ready_pob_import_missing",
                "Materialization did not produce ready-pob-import.pobcode.txt.",
                "Produce an exact PoB import payload before publication verification.",
            )
        )

    verification_blockers = list(verification_result.get("blockers", [])) if verification_result else []
    blockers = _dedupe_publication_blockers([*preflight_blockers, *runtime_blockers, *verification_blockers])
    accepted = not blockers and verification_result is not None and verification_result.get("status") == "accepted"
    direct_build_output_ref = None
    if accepted and run is not None and readback_state is not None and calc_snapshot is not None:
        direct_build_output = build_direct_build_output(
            decision_ledger=_sibling_decision_ledger(semantic_path),
            semantic_validation=semantic,
            materialization_source_packet=source_packet,
            pre_materialization_checkpoint=checkpoint,
            verification_result=verification_result,
            pob_run_id=run_id,
            run=run,
            ready_xml_path=xml_path,
            ready_import_code_path=import_code_path,
            readback_state=readback_state,
            calc_snapshot=calc_snapshot,
            generated_at=generated,
        )
        write_json(direct_build_output_path, direct_build_output)
        direct_build_output_ref = {
            "ref_id": f"direct-build-output.{_string(source_packet.get('ledger_id'))}",
            "locator": _path_string(direct_build_output_path),
            "json_pointer": "/composition_summary/ready_pob_import/payload",
        }

    result = {
        "schema_version": "1.0.0",
        "record_kind": DIRECT_BUILD_MATERIALIZATION_RESULT_RECORD_KIND,
        "status": "accepted" if accepted else "blocked",
        "ledger_id": _string(source_packet.get("ledger_id")),
        "generated_at": generated,
        "pob_run_id": run_id,
        "ready_pob_import": {
            "xml_locator": _path_string(xml_path) if xml_path.is_file() else None,
            "import_code_locator": _path_string(import_code_path) if import_code_path.is_file() else None,
            "payload_sha256": sha256_bytes(import_code_path.read_text(encoding="utf-8").encode("utf-8"))
            if import_code_path.is_file()
            else None,
        },
        "early_game_rails": {
            "required": _string(source_packet.get("direct_build_lane")) == EARLY_GAME_DIRECT_BUILD_LANE,
            "report_locator": _path_string(early_game_rails_report_path) if early_game_rails_report_path.is_file() else None,
            "normalized_calc_snapshot_locator": _path_string(calc_snapshot_path) if calc_snapshot_path.is_file() else None,
        },
        "direct_build_output_ref": direct_build_output_ref,
        "verification_result": verification_result,
        "publication_guard": {
            "direct_build_output_allowed": accepted,
            "ready_pob_import_allowed": accepted,
            "successful_chat_payload_allowed": accepted,
        },
        "blockers": blockers,
    }
    write_json(target_dir / "direct-build-materialization-result.json", result)
    return result


def build_direct_build_output(
    *,
    decision_ledger: Mapping[str, Any],
    semantic_validation: Mapping[str, Any],
    materialization_source_packet: Mapping[str, Any],
    pre_materialization_checkpoint: Mapping[str, Any],
    verification_result: Mapping[str, Any],
    pob_run_id: str,
    run: Any,
    ready_xml_path: Path,
    ready_import_code_path: Path,
    readback_state: Mapping[str, Any],
    calc_snapshot: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    """Build the accepted DirectBuildOutput surface from verified artifacts."""

    ledger = _mapping(decision_ledger)
    identity = _mapping(ledger.get("build_identity") or materialization_source_packet.get("build_identity"))
    composition = _composition_summary(ledger, identity, ready_import_code_path)
    import_verifier = _mapping(verification_result.get("import_code_verifier"))
    proof_result = _mapping(import_verifier.get("result"))
    semantic_ref = _mapping(verification_result.get("semantic_validation"))
    source_ref = _mapping(verification_result.get("materialization_source_packet"))
    checkpoint_ref = _mapping(verification_result.get("pre_materialization_checkpoint"))
    artifact_id = f"artifact.direct-build-output.{_safe_ref(_string(semantic_validation.get('ledger_id')))}"
    return {
        "schema_version": DIRECT_BUILD_OUTPUT_SCHEMA_VERSION,
        "record_kind": DIRECT_BUILD_OUTPUT_RECORD_KIND,
        "assembly_id": f"assembly.{_safe_ref(_string(semantic_validation.get('ledger_id')))}",
        "generated_at": generated_at,
        "source_context": _source_context(ledger),
        "artifact_locator": {
            "artifact_id": artifact_id,
            "artifact_kind": "pob_xml",
            "locator": _path_string(ready_xml_path),
            "workspace_locator": _path_string(run.layout.manifest_paths.workspace_manifest_path),
            "handoff_locator": _path_string(run.layout.manifest_paths.next_run_handoff_path),
        },
        "proof_refs": {
            "pob_run_id": pob_run_id,
            "primary_proof_kind": "pob_run",
            "primary_proof_locator": _path_string(run.layout.manifest_paths.primary_proof_path),
            "live_control_result_locator": _path_string(run.layout.manifest_paths.live_control_result_path),
            "workspace_manifest_locator": _path_string(run.layout.manifest_paths.workspace_manifest_path),
            "next_run_handoff_locator": _path_string(run.layout.manifest_paths.next_run_handoff_path),
            "import_code_verifier_status": _string(import_verifier.get("status")) or None,
            "import_code_verifier_locator": _string(import_verifier.get("locator")) or None,
            "import_code_verifier_payload_sha256": _string(import_verifier.get("payload_sha256")) or None,
            "semantic_validation_status": _string(semantic_validation.get("status")) or None,
            "semantic_validation_locator": _string(semantic_ref.get("locator")) or None,
            "semantic_validation_mode": _string(semantic_validation.get("artifact_mode")) or None,
            "materialization_source_packet_status": _string(materialization_source_packet.get("status")) or None,
            "materialization_source_packet_locator": _string(source_ref.get("locator")) or None,
            "pre_materialization_checkpoint_status": _string(pre_materialization_checkpoint.get("status")) or None,
            "pre_materialization_checkpoint_locator": _string(checkpoint_ref.get("locator")) or None,
        },
        "composition_summary": composition,
        "budget_shell": dict(_mapping(ledger.get("budget_shell"))),
        "cost_value_summary": _cost_value_summary(ledger, materialization_source_packet),
        "baseline_state": _state_section(ledger, calc_snapshot, readback_state, field_name="baseline_state"),
        "conditional_state": _state_section(ledger, calc_snapshot, readback_state, field_name="conditional_state"),
        "assumptions": list(_sequence_or_default(ledger.get("assumptions"), default=[])),
        "blockers": [],
        "freshness_notes": [
            {
                "surface_kind": "proof_run",
                "status": "fresh",
                "note": "DirectBuildOutput was generated from the accepted materialization package and exact import verifier result.",
                "captured_at": generated_at,
            },
            {
                "surface_kind": "artifact_handoff",
                "status": "fresh",
                "note": f"Verifier payload hash: {_string(proof_result.get('validated_import_code_payload_sha256')) or _string(import_verifier.get('payload_sha256'))}.",
                "captured_at": generated_at,
            },
        ],
    }


def _apply_materialization_payload(adapter: Any, handle: Any, payload: Mapping[str, Any]) -> None:
    for surface_name in REQUIRED_MATERIALIZATION_SURFACES:
        surface_payload = payload.get(surface_name)
        if not isinstance(surface_payload, Mapping):
            raise DirectBuildMaterializerError(f"materialization_payload.{surface_name} must be an object.")
        getattr(adapter, SURFACE_TO_APPLY_METHOD[surface_name])(handle, _runtime_apply_payload(surface_name, surface_payload))


def _runtime_apply_payload(surface_name: str, surface_payload: Mapping[str, Any]) -> dict[str, Any]:
    if surface_name == "tree_state":
        return _tree_runtime_apply_payload(surface_payload)
    if surface_name == "item_state":
        return _item_runtime_apply_payload(surface_payload)
    if surface_name == "config_state":
        return _config_runtime_apply_payload(surface_payload)
    return dict(surface_payload)


def _tree_runtime_apply_payload(tree_state: Mapping[str, Any]) -> dict[str, Any]:
    unsupported_fields = sorted(
        set(tree_state) - SUPPORTED_TREE_APPLY_FIELDS - TREE_STATE_SOURCE_QUALITY_METADATA_FIELDS
    )
    if unsupported_fields:
        raise DirectBuildMaterializerError(
            "materialization_payload.tree_state contains unsupported runtime tree payload fields: "
            + ", ".join(unsupported_fields)
        )
    return {field_name: value for field_name, value in tree_state.items() if field_name in SUPPORTED_TREE_APPLY_FIELDS}


def _item_runtime_apply_payload(item_state: Mapping[str, Any]) -> dict[str, Any]:
    unsupported_fields = sorted(
        set(item_state) - ITEM_STATE_APPLY_FIELDS - ITEM_STATE_SOURCE_QUALITY_METADATA_FIELDS
    )
    if unsupported_fields:
        raise DirectBuildMaterializerError(
            "materialization_payload.item_state contains unsupported runtime item payload fields: "
            + ", ".join(unsupported_fields)
        )
    runtime_payload = {field_name: value for field_name, value in item_state.items() if field_name in ITEM_STATE_APPLY_FIELDS}
    missing_runtime_fields = sorted(ITEM_STATE_APPLY_FIELDS - set(runtime_payload))
    if missing_runtime_fields:
        raise DirectBuildMaterializerError(
            "materialization_payload.item_state is missing supported runtime item payload fields: "
            + ", ".join(missing_runtime_fields)
        )
    return runtime_payload


def _config_runtime_apply_payload(config_state: Mapping[str, Any]) -> dict[str, Any]:
    unsupported_fields = sorted(
        set(config_state) - CONFIG_STATE_APPLY_FIELDS - CONFIG_STATE_SOURCE_QUALITY_METADATA_FIELDS
    )
    if unsupported_fields:
        raise DirectBuildMaterializerError(
            "materialization_payload.config_state contains unsupported runtime config payload fields: "
            + ", ".join(unsupported_fields)
        )
    runtime_payload = {field_name: value for field_name, value in config_state.items() if field_name in CONFIG_STATE_APPLY_FIELDS}
    if "config_sets" not in runtime_payload:
        runtime_payload["active_config_set_id"] = "config.main"
        runtime_payload["config_sets"] = [{"config_set_id": "config.main"}]
    return runtime_payload


def _early_game_rails_blockers(
    source_packet: Mapping[str, Any],
    *,
    pob_xml_text: str,
    normalized_calc_snapshot: Mapping[str, Any],
    report_path: Path,
) -> list[dict[str, Any]]:
    if _string(source_packet.get("direct_build_lane")) != EARLY_GAME_DIRECT_BUILD_LANE:
        return []
    trace = _mapping(source_packet.get("direct_build_decision_trace"))
    if _string(trace.get("record_kind")) != "direct_build_decision_trace":
        return [
            _blocker(
                "early_game_direct_build_decision_trace_missing",
                "Early Game Direct Build cannot run rails validation without direct_build_decision_trace.",
                "Provide the agent-authored direct_build_decision_trace in the decision ledger and rerun materialization.",
            )
        ]
    try:
        report = build_direct_build_early_game_rails_report(
            candidate_payload=trace,
            pob_xml_text=pob_xml_text,
            normalized_calc_snapshot=normalized_calc_snapshot,
        )
    except Exception as exc:
        return [
            _blocker(
                "early_game_rails_report_failed",
                f"Early Game rails report failed before acceptance: {type(exc).__name__}: {exc}",
                "Repair PoB XML, direct_build_decision_trace, or normalized calc snapshot and rerun rails validation.",
            )
        ]
    write_json(report_path, report)
    if _string(report.get("status")) == "passed":
        return []
    blockers = []
    for row in _sequence(report.get("blockers")):
        if not isinstance(row, Mapping):
            continue
        code = _string(row.get("code")) or "early_game_rails_blocker"
        blockers.append(
            _blocker(
                code,
                f"Early Game rails blocker: {code}.",
                "Produce a rails-passing level 90 Early Game Direct Build before DirectBuildOutput publication.",
            )
        )
    return blockers or [
        _blocker(
            "early_game_rails_not_passed",
            "Early Game rails report did not pass.",
            "Produce a rails-passing level 90 Early Game Direct Build before publication.",
        )
    ]


def _normalized_calc_snapshot_for_rails(calc_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(calc_snapshot)
    if isinstance(payload.get("baseline"), Mapping):
        normalized = dict(payload)
        normalized["baseline"] = _rails_calc_snapshot_section(_mapping(payload.get("baseline")))
        if isinstance(payload.get("conditional"), Mapping):
            normalized["conditional"] = _rails_calc_snapshot_section(_mapping(payload.get("conditional")))
        return normalized
    return {
        "baseline": {
            "calc_snapshot": _rails_calc_snapshot_payload(payload),
        }
    }


def _rails_calc_snapshot_section(section: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(section)
    calc_snapshot = payload.get("calc_snapshot")
    if isinstance(calc_snapshot, Mapping):
        payload["calc_snapshot"] = _rails_calc_snapshot_payload(calc_snapshot)
    else:
        payload["calc_snapshot"] = _rails_calc_snapshot_payload(payload)
    return payload


def _rails_calc_snapshot_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = dict(payload)
    if "main_output" not in snapshot and isinstance(snapshot.get("calcs_output"), Mapping):
        snapshot["main_output"] = dict(_mapping(snapshot.get("calcs_output")))
    if "main_output" not in snapshot:
        snapshot["main_output"] = {}
    return snapshot


def _decision_ledger_findings(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if _string(ledger.get("record_kind")) != DIRECT_BUILD_DECISION_LEDGER_RECORD_KIND:
        findings.append(_finding("decision_ledger_record_kind_invalid", "Decision ledger record_kind is invalid."))
    if _string(ledger.get("artifact_mode")) != PRODUCT_ARTIFACT_MODE:
        findings.append(_finding("decision_ledger_not_product", "Decision ledger artifact_mode must be product."))
    if not _string(ledger.get("ledger_id")):
        findings.append(_finding("decision_ledger_id_missing", "Decision ledger must expose ledger_id."))
    if not _string(ledger.get("generated_at")):
        findings.append(_finding("decision_ledger_generated_at_missing", "Decision ledger must expose generated_at."))
    identity = _mapping(ledger.get("build_identity"))
    for field_name in ("class_name", "main_skill", "level"):
        if _identity_value(identity.get(field_name)) is None:
            findings.append(_finding(f"build_identity_{field_name}_missing", f"build_identity.{field_name} is required."))
    level = _int_value(identity.get("level"))
    if level is not None and (level < 1 or level > 100):
        findings.append(_finding("build_identity_level_out_of_range", "build_identity.level must be between 1 and 100."))
    missing_kinds = sorted(set(REQUIRED_MUTATION_KINDS) - _accepted_mutation_kinds(ledger))
    if missing_kinds:
        findings.append(
            _finding(
                "decision_rows_missing_required_mutation_kinds",
                "Accepted agent-authored decision rows must cover identity, skill, tree, item, and config.",
                details={"missing": missing_kinds},
            )
        )
    findings.extend(_repair_context_findings(ledger))
    for row in _accepted_decision_rows(ledger):
        row_id = _string(row.get("row_id") or row.get("decision_id")) or "<unknown>"
        if row.get("agent_authored") is not True:
            findings.append(_finding("decision_row_not_agent_authored", f"Decision row {row_id} must set agent_authored=true."))
        if not isinstance(row.get("resource_cost"), (Mapping, list)):
            findings.append(_finding("decision_row_resource_cost_missing", f"Decision row {row_id} must expose resource_cost."))
        if not _sequence(row.get("alternatives_considered")):
            findings.append(
                _finding(
                    "decision_row_alternatives_missing",
                    f"Decision row {row_id} must expose alternatives_considered.",
                )
            )
        if not _sequence(row.get("evidence_refs")):
            findings.append(_finding("decision_row_evidence_refs_missing", f"Decision row {row_id} must expose evidence_refs."))
    findings.extend(_cost_aware_contract_findings(ledger))
    return findings


def _repair_context_findings(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    repair_context = ledger.get("repair_context")
    if repair_context is None:
        return []
    if not isinstance(repair_context, Mapping):
        return [_finding("repair_context_invalid", "repair_context must be an object when present.")]

    findings: list[dict[str, Any]] = []
    if _string(repair_context.get("record_kind")) != "direct_build_repair_context":
        findings.append(_finding("repair_context_record_kind_invalid", "repair_context.record_kind is invalid."))

    repair_packet_ref = repair_context.get("repair_packet_ref")
    if not isinstance(repair_packet_ref, Mapping):
        findings.append(_finding("repair_packet_ref_missing", "repair_context.repair_packet_ref is required."))
    else:
        for field_name in ("ref_id", "locator"):
            if not _string(repair_packet_ref.get(field_name)):
                findings.append(
                    _finding(
                        f"repair_packet_ref_{field_name}_missing",
                        f"repair_context.repair_packet_ref.{field_name} is required.",
                    )
                )

    repair_packet_summary = repair_context.get("repair_packet_summary")
    if not isinstance(repair_packet_summary, Mapping):
        findings.append(_finding("repair_packet_summary_missing", "repair_context.repair_packet_summary is required."))
        expected_repair_ids: set[str] = set()
    else:
        if _string(repair_packet_summary.get("record_kind")) != "direct_build_repair_packet":
            findings.append(
                _finding(
                    "repair_packet_summary_record_kind_invalid",
                    "repair_context.repair_packet_summary.record_kind must be direct_build_repair_packet.",
                )
            )
        if repair_packet_summary.get("next_attempt_required") is not True:
            findings.append(
                _finding(
                    "repair_packet_summary_next_attempt_required_missing",
                    "repair_context.repair_packet_summary.next_attempt_required must be true.",
                )
            )
        if repair_packet_summary.get("stop_allowed") is not False:
            findings.append(
                _finding(
                    "repair_packet_summary_stop_allowed_invalid",
                    "repair_context.repair_packet_summary.stop_allowed must be false for a repair attempt.",
                )
            )
        expected_repair_ids = _repair_ids_from_summary(repair_packet_summary)
        if not expected_repair_ids:
            findings.append(
                _finding(
                    "repair_packet_summary_repair_ids_missing",
                    "repair_context.repair_packet_summary.repair_ids must name at least one repair requirement.",
                )
            )

    covered_repair_ids = _string_set(repair_context.get("covered_repair_ids"))
    row_repair_ids = _accepted_row_repair_ids(ledger)
    missing_context_ids = sorted(expected_repair_ids - covered_repair_ids)
    missing_row_ids = sorted(expected_repair_ids - row_repair_ids)
    if missing_context_ids:
        findings.append(
            _finding(
                "repair_context_missing_covered_repair_ids",
                "repair_context.covered_repair_ids does not cover every repair packet requirement.",
                details={"missing": missing_context_ids},
            )
        )
    if missing_row_ids:
        findings.append(
            _finding(
                "repair_decision_rows_missing_repair_ids",
                "Accepted decision rows must cite the repair_ids they are repairing.",
                details={"missing": missing_row_ids},
            )
        )
    return findings


def _cost_aware_contract_findings(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not _is_cost_aware_direct_build(ledger):
        return []

    findings: list[dict[str, Any]] = []
    for row in _accepted_decision_rows(ledger):
        if not _is_material_decision_row(row):
            continue
        row_id = _string(row.get("row_id") or row.get("decision_id")) or "<unknown>"
        for field_name in REQUIRED_COST_AWARE_DECISION_REFS:
            if not _has_row_cost_aware_refs(row, field_name):
                findings.append(
                    _finding(
                        f"cost_aware_{field_name}_missing",
                        f"Cost-aware decision row {row_id} must cite {field_name}.",
                    )
                )
        if _is_tree_pathing_decision_row(row):
            for field_name in TREE_PATHING_COST_AWARE_REFS:
                if not _has_row_cost_aware_refs(row, field_name):
                    findings.append(
                        _finding(
                            f"cost_aware_{field_name}_missing",
                            f"Cost-aware tree/pathing row {row_id} must cite {field_name}.",
                        )
                    )
        if _row_claims_measured_evidence(row):
            for field_name in MEASURED_EVIDENCE_COST_AWARE_REFS:
                if not _has_row_cost_aware_refs(row, field_name):
                    findings.append(
                        _finding(
                            f"cost_aware_{field_name}_missing_for_measured_claim",
                            f"Cost-aware measured claim row {row_id} must cite {field_name}.",
                        )
                    )
    return findings


def _is_cost_aware_direct_build(ledger: Mapping[str, Any]) -> bool:
    contract = _mapping(ledger.get("cost_value_contract"))
    return (
        ledger.get("cost_aware_direct_build") is True
        or _string(ledger.get("cost_value_mode")) == "cost_aware"
        or _string(contract.get("mode")) == "cost_aware"
        or _string(contract.get("status")) == "cost_aware_required"
    )


def _cost_value_contract_summary(ledger: Mapping[str, Any]) -> dict[str, Any]:
    cost_aware = _is_cost_aware_direct_build(ledger)
    findings = _cost_aware_contract_findings(ledger) if cost_aware else []
    return {
        "mode": "cost_aware" if cost_aware else "legacy",
        "status": "blocked" if findings else ("accepted" if cost_aware else "not_applicable"),
        "required_ref_fields": {
            "material_decision_rows": list(REQUIRED_COST_AWARE_DECISION_REFS),
            "tree_pathing_decision_rows": list(TREE_PATHING_COST_AWARE_REFS),
            "measured_claim_rows": list(MEASURED_EVIDENCE_COST_AWARE_REFS),
        },
        "blocker_codes": [_string(finding.get("code")) for finding in findings],
    }


def _collect_cost_aware_artifact_refs(ledger: Mapping[str, Any]) -> dict[str, list[Any]]:
    refs: dict[str, list[Any]] = {}
    nested = _mapping(ledger.get("cost_aware_artifact_refs"))
    for field_name in COST_AWARE_REF_FIELDS:
        refs[field_name] = _dedupe_cost_aware_refs(
            [
                *_cost_aware_ref_values(ledger, field_name),
                *_cost_aware_ref_values(nested, field_name),
                *[
                    ref
                    for row in _accepted_decision_rows(ledger)
                    for ref in _cost_aware_ref_values(row, field_name)
                ],
                *[
                    ref
                    for row in _accepted_decision_rows(ledger)
                    for ref in _cost_aware_ref_values(_mapping(row.get("cost_aware_artifact_refs")), field_name)
                ],
            ]
        )
    return refs


def _cost_aware_decision_rows(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in _accepted_decision_rows(ledger):
        if not _is_material_decision_row(row):
            continue
        artifact_refs = {
            field_name: _dedupe_cost_aware_refs(
                [
                    *_cost_aware_ref_values(row, field_name),
                    *_cost_aware_ref_values(_mapping(row.get("cost_aware_artifact_refs")), field_name),
                ]
            )
            for field_name in COST_AWARE_REF_FIELDS
        }
        rows.append(
            {
                "row_id": _string(row.get("row_id") or row.get("decision_id")) or "unknown-row",
                "mutation_kind": _row_mutation_kind(row),
                "decision_family": _string(row.get("decision_family")) or None,
                "action_scope": _string(row.get("action_scope")) or None,
                "selected_decision": _selected_decision_label(row),
                "rejected_alternatives_short": _alternatives_short(row),
                "resource_cost": _json_safe_value(row.get("resource_cost")),
                "expected_surfaces": list(_sequence(row.get("expected_surfaces"))),
                "measured_or_expected_value": _json_safe_value(row.get("value_summary") or row.get("expected_value_summary")),
                "impact_categories": _impact_categories(row),
                "uncertainty": _json_safe_value(row.get("uncertainty")),
                "missing_evidence": list(_sequence(row.get("missing_evidence"))),
                "artifact_refs": artifact_refs,
            }
        )
    return rows


def _cost_value_summary(ledger: Mapping[str, Any], materialization_source_packet: Mapping[str, Any]) -> dict[str, Any]:
    source_packet = _mapping(materialization_source_packet)
    contract = _mapping(source_packet.get("cost_value_contract")) or _cost_value_contract_summary(ledger)
    rows = list(_sequence(source_packet.get("cost_aware_decision_rows"))) or _cost_aware_decision_rows(ledger)
    artifact_refs = _mapping(source_packet.get("cost_aware_artifact_refs")) or _collect_cost_aware_artifact_refs(ledger)
    missing_evidence = []
    for row in rows:
        if isinstance(row, Mapping):
            missing_evidence.extend(list(_sequence(row.get("missing_evidence"))))
    mode = _string(contract.get("mode")) or "legacy"
    return {
        "mode": mode,
        "status": _string(contract.get("status")) or ("not_applicable" if mode == "legacy" else "partial"),
        "selected_decisions": [dict(row) for row in rows if isinstance(row, Mapping)],
        "artifact_refs": {field_name: list(_sequence(artifact_refs.get(field_name))) for field_name in COST_AWARE_REF_FIELDS},
        "missing_evidence": missing_evidence,
        "notes": [
            "Compact cost/value summary only; full debug packets are internal artifacts and are not inlined.",
        ],
    }


def _is_material_decision_row(row: Mapping[str, Any]) -> bool:
    return _row_mutation_kind(row) in REQUIRED_MUTATION_KINDS


def _is_tree_pathing_decision_row(row: Mapping[str, Any]) -> bool:
    decision_family = _string(row.get("decision_family"))
    action_scope = _string(row.get("action_scope"))
    return _row_mutation_kind(row) == "tree" or action_scope == "tree" or "tree_pathing" in decision_family


def _row_claims_measured_evidence(row: Mapping[str, Any]) -> bool:
    value_summary = _mapping(row.get("value_summary"))
    return (
        row.get("claims_measured_evidence") is True
        or row.get("measured_evidence_claimed") is True
        or _string(row.get("measured_or_expected")) in {"measured", "mixed"}
        or value_summary.get("claims_measured_evidence") is True
        or _string(value_summary.get("measured_or_expected")) in {"measured", "mixed"}
    )


def _has_row_cost_aware_refs(row: Mapping[str, Any], field_name: str) -> bool:
    return bool(
        _cost_aware_ref_values(row, field_name)
        or _cost_aware_ref_values(_mapping(row.get("cost_aware_artifact_refs")), field_name)
    )


def _cost_aware_ref_values(container: Mapping[str, Any], field_name: str) -> list[Any]:
    return _valid_cost_aware_refs(container.get(field_name))


def _valid_cost_aware_refs(value: Any) -> list[Any]:
    refs = []
    for entry in _sequence(value):
        if isinstance(entry, Mapping):
            refs.append(dict(entry))
        elif isinstance(entry, str) and entry.strip():
            refs.append(entry.strip())
    return refs


def _dedupe_cost_aware_refs(refs: Sequence[Any]) -> list[Any]:
    result = []
    seen: set[str] = set()
    for ref in refs:
        key = json.dumps(ref, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return result


def _row_mutation_kind(row: Mapping[str, Any]) -> str:
    return _string(row.get("mutation_kind") or row.get("target_mutation_kind") or row.get("surface"))


def _selected_decision_label(row: Mapping[str, Any]) -> str:
    candidate = _mapping(row.get("candidate_action"))
    return (
        _string(candidate.get("label"))
        or _string(candidate.get("summary"))
        or _string(row.get("selected_decision"))
        or _string(row.get("summary"))
        or _string(row.get("row_id") or row.get("decision_id"))
        or "accepted decision"
    )


def _alternatives_short(row: Mapping[str, Any]) -> list[str]:
    alternatives = []
    for entry in _sequence(row.get("alternatives_considered")):
        if isinstance(entry, Mapping):
            alternatives.append(
                _string(entry.get("label") or entry.get("action_id") or entry.get("summary")) or "alternative"
            )
        elif isinstance(entry, str) and entry.strip():
            alternatives.append(entry.strip())
    return alternatives[:3]


def _impact_categories(row: Mapping[str, Any]) -> list[str]:
    value_summary = _mapping(row.get("value_summary"))
    for value in (
        row.get("impact_categories"),
        value_summary.get("impact_categories"),
        row.get("primary_impact"),
    ):
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        categories = [entry.strip() for entry in _sequence(value) if isinstance(entry, str) and entry.strip()]
        if categories:
            return categories
    return []


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe_value(entry) for key, entry in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe_value(entry) for entry in value]
    return value


def _repair_ids_from_summary(repair_packet_summary: Mapping[str, Any]) -> set[str]:
    repair_ids = _string_set(repair_packet_summary.get("repair_ids"))
    if repair_ids:
        return repair_ids
    repair_items = repair_packet_summary.get("repair_items")
    if not isinstance(repair_items, Sequence) or isinstance(repair_items, (str, bytes, bytearray)):
        return set()
    return {_string(item.get("repair_id")) for item in repair_items if isinstance(item, Mapping) and _string(item.get("repair_id"))}


def _accepted_row_repair_ids(ledger: Mapping[str, Any]) -> set[str]:
    repair_ids: set[str] = set()
    for row in _accepted_decision_rows(ledger):
        repair_ids.update(_string_set(row.get("repair_ids")))
    return repair_ids


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return set()
    return {entry.strip() for entry in value if isinstance(entry, str) and entry.strip()}


def _source_packet_blockers(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    materialization_payload = ledger.get("materialization_payload")
    if not isinstance(materialization_payload, Mapping):
        return [
            _blocker(
                "materialization_payload_missing",
                "Decision ledger does not contain materialization_payload.",
                "Provide exact agent-authored identity/tree/item/skill/config state payloads.",
            )
        ]
    blockers.extend(_universal_pob_authoring_evidence_blockers(ledger, _mapping(materialization_payload)))
    if _direct_build_lane(ledger) == EARLY_GAME_DIRECT_BUILD_LANE:
        trace = ledger.get("direct_build_decision_trace")
        if not isinstance(trace, Mapping) or _string(trace.get("record_kind")) != "direct_build_decision_trace":
            blockers.append(
                _blocker(
                    "early_game_direct_build_decision_trace_missing",
                    "Early Game Direct Build requires an agent-authored direct_build_decision_trace.",
                    "Provide direct_build_decision_trace with identity, skill, tree, item, config, and observe actions before materialization.",
                )
            )
        blockers.extend(_early_game_quality_source_blockers(ledger, _mapping(materialization_payload)))
    for surface_name in REQUIRED_MATERIALIZATION_SURFACES:
        if not isinstance(materialization_payload.get(surface_name), Mapping):
            blockers.append(
                _blocker(
                    f"materialization_payload_{surface_name}_missing",
                    f"materialization_payload.{surface_name} must be an object.",
                    "Provide the exact source surface payload authored by the product agent.",
                )
            )
    if not isinstance(ledger.get("composition_summary"), Mapping):
        blockers.append(
            _blocker(
                "composition_summary_missing",
                "Decision ledger must carry composition_summary for DirectBuildOutput.",
                "Add the agent-authored composition summary that matches the materialization payload.",
            )
        )
    if not isinstance(ledger.get("budget_shell"), Mapping):
        blockers.append(
            _blocker(
                "budget_shell_missing",
                "Decision ledger must carry budget_shell for DirectBuildOutput.",
                "Add the budget shell evidence or starter-baseline assumption rows.",
            )
        )
    return blockers


def _universal_pob_authoring_evidence_blockers(
    ledger: Mapping[str, Any],
    materialization_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    skill_state = _mapping(materialization_payload.get("skill_state"))
    config_state = _mapping(materialization_payload.get("config_state"))

    unsupported_counts = _unsupported_skill_count_overrides(ledger, skill_state)
    if unsupported_counts:
        blockers.append(
            _blocker(
                "pob_authoring_skill_count_evidence_missing",
                f"Skill count/overlap overrides lack mechanics evidence: {', '.join(unsupported_counts)}.",
                "Add skill_count_evidence_refs, overlap_evidence_refs, or full_dps_count_evidence_refs before using counts above 1.",
            )
        )

    route_claims_ignite_value = _skill_uses_ignite_or_burning(skill_state, ledger)
    baseline_config = _baseline_config(config_state)
    baseline_enemy_ignited = _baseline_enemy_ignited(baseline_config)
    if route_claims_ignite_value and not baseline_enemy_ignited:
        blockers.append(
            _blocker(
                "pob_authoring_ignite_config_consistency_missing",
                "Ignite/burning value is claimed but the evaluated enemy ignited/burning state is not configured.",
                "Either prove and enable enemy ignited/burning state for the evaluated scenario, or remove the ignite/burning value claim.",
            )
        )
    if baseline_enemy_ignited and not route_claims_ignite_value:
        blockers.append(
            _blocker(
                "pob_authoring_unclaimed_ignite_state_enabled",
                "Enemy ignited state is enabled without an ignite/burning value claim.",
                "Remove enemy ignited state or add route evidence that the build uses and sustains it.",
            )
        )
    if baseline_enemy_ignited and not _has_ignite_sustain_evidence(ledger, skill_state, config_state):
        blockers.append(
            _blocker(
                "pob_authoring_ignite_sustain_evidence_missing",
                "Enemy ignited/burning state is enabled without ignite chance/sustain evidence.",
                "Add ignite_chance_evidence_refs and ignite_sustain_evidence_refs, or disable the state.",
            )
        )

    active_states = _active_config_authoring_states(config_state)
    shock_states = [state for state in active_states if _is_shock_state_key(state["key"])]
    if shock_states and not _has_shock_threshold_evidence(ledger, config_state):
        blockers.append(
            _blocker(
                "pob_authoring_shock_threshold_evidence_missing",
                "Shock state/effect is enabled without Pinnacle/Guardian ailment threshold and sustain evidence.",
                "Add hit-damage-vs-boss threshold proof, expected shock effect, and sustain evidence before enabling shock.",
            )
        )
    for state in active_states:
        key = state["key"]
        if _is_shock_state_key(key) or _is_ignite_state_key(key):
            continue
        if not _has_config_state_evidence(ledger, config_state, key):
            blockers.append(
                _blocker(
                    "pob_authoring_config_state_evidence_missing",
                    f"Config state {state['path']}={state['value']!r} lacks build capability/sustain evidence.",
                    "Add config_state_evidence_refs or field-specific evidence refs before enabling DPS/defense-affecting states.",
                )
            )
    return blockers


def _early_game_quality_source_blockers(
    ledger: Mapping[str, Any],
    materialization_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    identity = _mapping(ledger.get("build_identity"))
    composition = _mapping(ledger.get("composition_summary"))
    budget_shell = _mapping(ledger.get("budget_shell"))
    identity_state = _mapping(materialization_payload.get("identity_state"))
    skill_state = _mapping(materialization_payload.get("skill_state"))
    tree_state = _mapping(materialization_payload.get("tree_state"))
    item_state = _mapping(materialization_payload.get("item_state"))
    config_state = _mapping(materialization_payload.get("config_state"))

    if not _tested_hypothesis_label(ledger, composition, identity):
        blockers.append(
            _blocker(
                "early_game_build_hypothesis_missing",
                "Early Game Direct Build must name the tested hypothesis/archetype.",
                "Add build_hypothesis, archetype, or composition_summary.tested_hypothesis before publication.",
            )
        )

    budget_status = _string(budget_shell.get("budget_status")).lower()
    if not budget_shell or budget_status in {"", "unknown"}:
        blockers.append(
            _blocker(
                "early_game_budget_shell_unknown",
                "Early Game budget shell is missing or unknown.",
                "Provide a bounded early-game loadout shell with budget_status other than unknown.",
            )
        )
    unknown_line_items = [
        _string(item.get("label") or item.get("slot")) or "<unknown>"
        for item in _sequence(budget_shell.get("line_items"))
        if isinstance(item, Mapping) and _string(item.get("source_kind")).lower() in {"", "unknown"}
    ]
    if unknown_line_items:
        blockers.append(
            _blocker(
                "early_game_budget_shell_line_item_unknown_source",
                "Early Game budget line items cannot use unknown source_kind.",
                "Use starter_baseline_assumption, manual_estimate, trade_snapshot, carry_over, or craft_placeholder with refs.",
            )
        )
    blockers.extend(_budget_arithmetic_blockers(budget_shell))
    blockers.extend(_early_game_loadout_blockers(ledger, item_state, budget_shell, composition))
    if _rare_gem_level_item_count(item_state) > 0 and not _has_power_gear_allowance(ledger):
        blockers.append(
            _blocker(
                "early_game_unrealistic_gem_level_rare_gear",
                "Early Game item shell contains rare +gem-level gear without lane evidence.",
                "Provide early_game_power_gear_evidence_refs or lower the item shell to the accepted starter rail.",
            )
        )
    high_power_items = _high_power_rare_item_labels(item_state)
    if high_power_items and not _has_power_gear_allowance(ledger):
        blockers.append(
            _blocker(
                "early_game_overpowered_rare_gear",
                f"Early Game item shell contains high-power rare gear markers: {', '.join(high_power_items)}.",
                "Provide early_game_power_gear_evidence_refs or use a lower-power starter rare shell.",
            )
        )

    bandit = _normalized_bandit(
        identity_state.get("bandit")
        or identity_state.get("bandit_choice")
        or identity.get("bandit")
        or identity.get("bandit_choice")
    )
    if bandit not in EARLY_GAME_ALLOWED_BANDIT_VALUES:
        blockers.append(
            _blocker(
                "early_game_bandit_not_kill_all",
                "Early Game baseline must use Kill All bandits.",
                "Set identity_state.bandit or build_identity.bandit to Kill All/None unless an explicit operator override changes the lane.",
            )
        )

    baseline_config = _baseline_config(config_state)
    boss_label = _baseline_boss_label(baseline_config)
    if not any(marker in boss_label for marker in EARLY_GAME_ALLOWED_BOSS_MARKERS):
        blockers.append(
            _blocker(
                "early_game_baseline_enemy_not_guardian_or_pinnacle",
                "Early Game baseline enemy must be Guardian/Pinnacle boss.",
                "Set baseline enemy_state.boss or equivalent config field to Guardian/Pinnacle.",
            )
        )

    if not _has_mastery_consideration(tree_state, composition):
        blockers.append(
            _blocker(
                "early_game_mastery_consideration_missing",
                "Level 90 Early Game tree must allocate relevant masteries or justify taking none.",
                "Add actual allocated masteries, or no_masteries_justification plus rejected mastery alternatives.",
            )
        )
    blockers.extend(_tree_semantic_blockers(ledger, tree_state, composition, skill_state, identity))
    blockers.extend(_ascendancy_semantic_blockers(ledger, tree_state, composition, skill_state, identity))
    blockers.extend(_tree_pathing_quality_blockers(ledger, tree_state, composition))
    blockers.extend(_tree_visual_inspection_blockers(tree_state))
    return blockers


def _budget_arithmetic_blockers(budget_shell: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    cap = _float_value(budget_shell.get("budget_cap_chaos"))
    total = _float_value(budget_shell.get("estimated_total_chaos"))
    mandatory = _float_value(budget_shell.get("mandatory_total_chaos"))
    optional = _float_value(budget_shell.get("optional_total_chaos"))
    headroom = _float_value(budget_shell.get("headroom_chaos"))
    if cap is not None and total is not None and total > cap:
        blockers.append(
            _blocker(
                "early_game_budget_cap_exceeded",
                f"Estimated budget {total}c exceeds cap {cap}c.",
                "Keep estimated_total_chaos within budget_cap_chaos or change the lane with operator approval.",
            )
        )
    if total is not None and mandatory is not None and optional is not None and abs((mandatory + optional) - total) > 0.01:
        blockers.append(
            _blocker(
                "early_game_budget_shell_arithmetic_invalid",
                "mandatory_total_chaos + optional_total_chaos does not equal estimated_total_chaos.",
                "Repair budget_shell totals before publication.",
            )
        )
    if cap is not None and total is not None and headroom is not None and abs((cap - total) - headroom) > 0.01:
        blockers.append(
            _blocker(
                "early_game_budget_shell_arithmetic_invalid",
                "budget_cap_chaos - estimated_total_chaos does not equal headroom_chaos.",
                "Repair budget_shell headroom before publication.",
            )
        )
    manual_without_evidence = [
        _string(item.get("label") or item.get("slot")) or "<unknown>"
        for item in _sequence(budget_shell.get("line_items"))
        if isinstance(item, Mapping)
        and _string(item.get("source_kind")).lower() == "manual_estimate"
        and not (_string(item.get("source_ref")) or _string(item.get("evidence_note")))
    ]
    if manual_without_evidence:
        blockers.append(
            _blocker(
                "early_game_budget_manual_estimate_evidence_missing",
                f"Manual budget estimates lack evidence refs/notes: {', '.join(manual_without_evidence)}.",
                "Attach source_ref, evidence_note, or note for each manual_estimate line item.",
            )
        )
    return blockers


def _unsupported_skill_count_overrides(ledger: Mapping[str, Any], skill_state: Mapping[str, Any]) -> list[str]:
    if _has_skill_count_evidence(ledger, skill_state):
        return []
    unsupported: list[str] = []
    for container in (skill_state, *[row for row in _accepted_decision_rows(ledger) if _row_mutation_kind(row) == "skill"]):
        unsupported.extend(_count_override_labels(container))
    return sorted(set(unsupported))


def _count_override_labels(value: Any, *, path: str = "skill_state") -> list[str]:
    labels: list[str] = []
    if isinstance(value, Mapping):
        for key, entry in value.items():
            normalized_key = _normalized_key(key)
            numeric = _int_value(entry)
            if normalized_key in UNIVERSAL_SKILL_COUNT_KEYS and numeric is not None and numeric > 1:
                labels.append(f"{path}.{normalized_key}={numeric}")
            labels.extend(_count_override_labels(entry, path=f"{path}.{normalized_key}"))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, entry in enumerate(value, start=1):
            labels.extend(_count_override_labels(entry, path=f"{path}[{index}]"))
    return labels


def _active_config_authoring_states(config_state: Mapping[str, Any]) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []

    def visit(value: Any, *, path: str) -> None:
        if isinstance(value, Mapping):
            for key, entry in value.items():
                normalized_key = _normalized_key(key)
                if normalized_key in UNIVERSAL_CONFIG_STATE_KEYS and _truthy(entry):
                    states.append({"key": normalized_key, "path": f"{path}.{normalized_key}", "value": _json_safe_value(entry)})
                visit(entry, path=f"{path}.{normalized_key}")
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for index, entry in enumerate(value, start=1):
                visit(entry, path=f"{path}[{index}]")

    visit(config_state, path="config_state")
    return states


def _has_skill_count_evidence(ledger: Mapping[str, Any], skill_state: Mapping[str, Any]) -> bool:
    return _has_evidence_refs(
        _authoring_evidence_containers(ledger, skill_state),
        {
            "skill_count_evidence_refs",
            "skill_mechanics_evidence_refs",
            "overlap_evidence_refs",
            "multi_hit_evidence_refs",
            "full_dps_count_evidence_refs",
            "projectile_count_evidence_refs",
            "repeat_count_evidence_refs",
            "hit_count_evidence_refs",
        },
    )


def _has_config_state_evidence(ledger: Mapping[str, Any], config_state: Mapping[str, Any], state_key: str) -> bool:
    keys = {
        "pob_authoring_evidence_refs",
        "config_state_evidence_refs",
        "enabled_config_evidence_refs",
        "conditional_state_evidence_refs",
        f"{state_key}_evidence_refs",
    }
    keys.update(f"{variant}_evidence_refs" for variant in _evidence_key_variants(state_key))
    return _has_evidence_refs(_authoring_evidence_containers(ledger, config_state), keys)


def _has_ignite_sustain_evidence(
    ledger: Mapping[str, Any],
    skill_state: Mapping[str, Any],
    config_state: Mapping[str, Any],
) -> bool:
    containers = _authoring_evidence_containers(ledger, skill_state, config_state)
    return _has_evidence_refs(
        containers,
        {
            "ignite_chance_evidence_refs",
            "ignite_sustain_evidence_refs",
            "enemy_ignited_evidence_refs",
            "enemy_burning_evidence_refs",
            "condition_enemy_ignited_evidence_refs",
            "conditionenemyignited_evidence_refs",
            "ignite_config_evidence_refs",
        },
    ) or _has_accepted_proof_object(containers, {"ignite_proof", "ignite_sustain_proof", "enemy_ignited_proof"})


def _has_shock_threshold_evidence(ledger: Mapping[str, Any], config_state: Mapping[str, Any]) -> bool:
    containers = _authoring_evidence_containers(ledger, config_state)
    has_threshold = _has_evidence_refs(
        containers,
        {
            "shock_threshold_evidence_refs",
            "pinnacle_shock_threshold_evidence_refs",
            "guardian_shock_threshold_evidence_refs",
            "shock_hit_damage_evidence_refs",
        },
    )
    has_effect = _has_evidence_refs(containers, {"shock_effect_evidence_refs", "expected_shock_effect_evidence_refs"})
    has_sustain = _has_evidence_refs(containers, {"shock_sustain_evidence_refs", "shock_uptime_evidence_refs"})
    return (has_threshold and has_effect and has_sustain) or _has_accepted_proof_object(
        containers,
        {"shock_proof", "shock_threshold_proof", "pinnacle_shock_proof"},
    )


def _authoring_evidence_containers(ledger: Mapping[str, Any], *payloads: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    containers: list[Mapping[str, Any]] = [ledger, _mapping(ledger.get("composition_summary")), _mapping(ledger.get("direct_build_decision_trace"))]
    containers.extend(payload for payload in payloads if isinstance(payload, Mapping))
    containers.extend(_accepted_decision_rows(ledger))
    return containers


def _has_evidence_refs(containers: Sequence[Mapping[str, Any]], keys: set[str]) -> bool:
    normalized_keys = {_normalized_key(key) for key in keys}
    return any(_has_evidence_refs_in_value(container, normalized_keys) for container in containers)


def _has_evidence_refs_in_value(value: Any, normalized_keys: set[str]) -> bool:
    if isinstance(value, Mapping):
        for key, entry in value.items():
            normalized_key = _normalized_key(key)
            if normalized_key in normalized_keys and (_sequence(entry) or _string(entry) or _mapping(entry)):
                return True
            if _has_evidence_refs_in_value(entry, normalized_keys):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_has_evidence_refs_in_value(entry, normalized_keys) for entry in value)
    return False


def _has_accepted_proof_object(containers: Sequence[Mapping[str, Any]], keys: set[str]) -> bool:
    normalized_keys = {_normalized_key(key) for key in keys}
    return any(_has_accepted_proof_object_in_value(container, normalized_keys) for container in containers)


def _has_accepted_proof_object_in_value(value: Any, normalized_keys: set[str]) -> bool:
    if isinstance(value, Mapping):
        for key, entry in value.items():
            if _normalized_key(key) in normalized_keys:
                proof = _mapping(entry)
                if _string(proof.get("status")).lower() in {"accepted", "passed", "supported"}:
                    return True
            if _has_accepted_proof_object_in_value(entry, normalized_keys):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_has_accepted_proof_object_in_value(entry, normalized_keys) for entry in value)
    return False


def _evidence_key_variants(state_key: str) -> set[str]:
    variants = {state_key}
    if state_key.startswith("conditionenemy"):
        variants.add("condition_enemy_" + state_key.removeprefix("conditionenemy"))
    if state_key.startswith("enemy_"):
        variants.add(state_key.removeprefix("enemy_"))
    return variants


def _is_ignite_state_key(key: str) -> bool:
    return "ignite" in key or "ignited" in key or "burning" in key


def _is_shock_state_key(key: str) -> bool:
    return "shock" in key or "shocked" in key


def _early_game_loadout_blockers(
    ledger: Mapping[str, Any],
    item_state: Mapping[str, Any],
    budget_shell: Mapping[str, Any],
    composition: Mapping[str, Any],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    rails = _early_game_loadout_rails(item_state, budget_shell, composition, ledger)
    if not rails:
        return [
            _blocker(
                "early_game_loadout_rails_missing",
                "Early Game item shell lacks accepted loadout rail metadata.",
                "Add early_game_loadout_rails with accepted lane and operator-declared mod tier limits.",
            )
        ]
    if _string(rails.get("status")).lower() not in {"accepted", "passed"}:
        blockers.append(
            _blocker(
                "early_game_loadout_rails_not_accepted",
                _string(rails.get("status")) or "<missing>",
                "accepted",
            )
        )
    lane = _string(rails.get("loadout_lane") or rails.get("lane") or rails.get("gear_lane")).lower()
    if lane not in EARLY_GAME_ALLOWED_LOADOUT_LANES:
        blockers.append(
            _blocker(
                "early_game_loadout_lane_invalid",
                lane or "<missing>",
                sorted(EARLY_GAME_ALLOWED_LOADOUT_LANES),
            )
        )
    if not (
        _string(rails.get("affix_tier_policy"))
        or _string(rails.get("operator_declared_mod_tier_limits"))
        or _string(rails.get("max_affix_tier"))
    ):
        blockers.append(
            _blocker(
                "early_game_affix_tier_limits_missing",
                "Early Game loadout rails do not declare affix/mod tier limits.",
                "Add affix_tier_policy, max_affix_tier, or operator_declared_mod_tier_limits.",
            )
        )
    if not _has_loadout_policy_evidence(rails, budget_shell, ledger):
        blockers.append(
            _blocker(
                "early_game_loadout_policy_evidence_missing",
                "Early Game loadout lane lacks policy/base-catalog evidence.",
                "Attach loadout_policy_ref, policy_evidence_refs, base_catalog_ref, or evidence-backed budget line items.",
            )
        )
    blockers.extend(_proof_item_contract_blockers(item_state))
    parsed_items = [_parse_item_entry(item, index=index) for index, item in enumerate(_item_entries(item_state), start=1)]
    if not parsed_items:
        blockers.append(
            _blocker(
                "early_game_loadout_items_missing",
                "Early Game item shell has no parsed gear items.",
                "Provide raw_items, items, equipped_items, or item_shell entries with rarity/base/explicit affixes.",
            )
        )
    flat_accuracy_item_count = 0
    for parsed in parsed_items:
        rarity = parsed["rarity"].lower()
        label = parsed["label"]
        if rarity == "unique":
            blockers.append(
                _blocker(
                    "early_game_unique_item_not_allowed",
                    label,
                    "Early Game loadout lane allows rare gear only.",
                )
            )
            continue
        if rarity != "rare":
            blockers.append(
                _blocker(
                    "early_game_non_rare_item_not_allowed",
                    f"{label}: {parsed['rarity'] or '<missing>'}",
                    "Rare",
                )
            )
            continue
        base_record = resolve_item_base(parsed["base_name"], parsed["base_name"])
        if not base_record:
            blockers.append(
                _blocker(
                    "early_game_item_base_not_in_catalog",
                    f"{label}: {parsed['base_name'] or '<missing>'}",
                    "Use a base from the packaged item base corpus.",
                )
            )
        else:
            required_level = base_required_level(base_record)
            if required_level > EARLY_GAME_MAX_BASE_REQUIRED_LEVEL:
                blockers.append(
                    _blocker(
                        "early_game_item_base_tier_too_high",
                        f"{label}: {parsed['base_name']} requires level {required_level}",
                        f"Early Game base required level must be <= {EARLY_GAME_MAX_BASE_REQUIRED_LEVEL}.",
                    )
                )
            if parsed["implicit_mods"] and not base_implicit_matches(base_record, parsed["implicit_mods"]):
                blockers.append(
                    _blocker(
                        "early_game_item_implicit_not_from_base",
                        f"{label}: {', '.join(parsed['implicit_mods']) or '<missing>'}",
                        _string(base_record.get("implicit_text")) or "no implicit",
                    )
                )
        explicit_affixes = list(parsed["explicit_affixes"])
        if len(explicit_affixes) > EARLY_GAME_MAX_EXPLICIT_AFFIXES_PER_RARE:
            blockers.append(
                _blocker(
                    "early_game_rare_item_too_many_explicit_affixes",
                    f"{label}: {len(explicit_affixes)} explicit affixes",
                    f"At most {EARLY_GAME_MAX_EXPLICIT_AFFIXES_PER_RARE} explicit affixes per rare item.",
                )
            )
        high_tier_affixes = [
            affix
            for affix in explicit_affixes
            if (tier := _explicit_affix_tier(affix)) is not None and tier < EARLY_GAME_BEST_ALLOWED_AFFIX_TIER
        ]
        if high_tier_affixes:
            blockers.append(
                _blocker(
                    "early_game_affix_tier_too_high",
                    f"{label}: {', '.join(high_tier_affixes)}",
                    f"Affix tiers must be T{EARLY_GAME_BEST_ALLOWED_AFFIX_TIER} or lower-power for Early Game.",
                )
            )
        if any(_is_flat_accuracy_affix(affix) for affix in explicit_affixes):
            flat_accuracy_item_count += 1
    if flat_accuracy_item_count > 1:
        blockers.append(
            _blocker(
                "early_game_flat_accuracy_roll_excess",
                flat_accuracy_item_count,
                "Flat accuracy may appear on at most one Early Game rare item.",
            )
        )
    return blockers


def _early_game_loadout_rails(
    item_state: Mapping[str, Any],
    budget_shell: Mapping[str, Any],
    composition: Mapping[str, Any],
    ledger: Mapping[str, Any],
) -> Mapping[str, Any]:
    for container in (item_state, budget_shell, composition, ledger):
        for key in ("early_game_loadout_rails", "loadout_rails", "item_loadout_rails"):
            value = _mapping(container.get(key))
            if value:
                return value
    return {}


def _has_loadout_policy_evidence(
    rails: Mapping[str, Any],
    budget_shell: Mapping[str, Any],
    ledger: Mapping[str, Any],
) -> bool:
    containers = [rails, budget_shell]
    containers.extend(_accepted_decision_rows(ledger))
    if _has_evidence_refs(
        containers,
        {
            "policy_evidence_refs",
            "loadout_policy_refs",
            "loadout_policy_ref",
            "base_catalog_refs",
            "base_catalog_ref",
            "early_game_loadout_evidence_refs",
        },
    ):
        return True
    return any(
        isinstance(item, Mapping)
        and _string(item.get("source_kind")).lower()
        in {"starter_baseline_assumption", "trade_snapshot", "carry_over", "craft_placeholder"}
        and (_string(item.get("source_ref")) or _string(item.get("evidence_note")) or _string(item.get("note")))
        for item in _sequence(budget_shell.get("line_items"))
    )


def _proof_item_contract_blockers(item_state: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    proof_items = _proof_item_entries(item_state)
    if not proof_items:
        if _item_entries(item_state):
            blockers.append(
                _blocker(
                    "early_game_proof_items_missing",
                    "Early Game item shell relies on raw/self-authored item text without structured proof items.",
                    "Add proof_items with base_id/base_name, catalog refs, structured affix ids/tier/value, and source refs.",
                )
            )
        return blockers

    raw_entries = _item_entries(item_state)
    if raw_entries and len(raw_entries) != len(proof_items):
        blockers.append(
            _blocker(
                "early_game_proof_item_count_mismatch",
                f"raw/source item count {len(raw_entries)} != proof item count {len(proof_items)}",
                "Every published Early Game source item needs a matching proof_items entry.",
            )
        )

    for index, item in enumerate(proof_items, start=1):
        label = _proof_item_label(item, index=index)
        rarity = _string(item.get("rarity")).lower()
        if rarity != "rare":
            blockers.append(_blocker("early_game_proof_item_not_rare", f"{label}: {rarity or '<missing>'}", "rare"))
        base_id = _string(item.get("base_id"))
        base_name = _string(item.get("base_name") or item.get("base") or item.get("base_type"))
        if not base_name or not base_id:
            blockers.append(
                _blocker(
                    "early_game_proof_item_base_identity_missing",
                    label,
                    "proof item base_id and base_name",
                )
            )
            base_record = None
        else:
            base_record = resolve_item_base(base_id, base_name)
        if not base_record:
            blockers.append(
                _blocker(
                    "early_game_proof_item_base_not_in_catalog",
                    f"{label}: {item.get('base_name') or item.get('base') or '<missing>'}",
                    "base_id/base_name must resolve to the packaged item base corpus",
                )
            )
        else:
            if not base_identity_matches(base_record, base_id, base_name):
                blockers.append(
                    _blocker(
                        "early_game_proof_item_base_identity_mismatch",
                        f"{label}: base_id={base_id}, base_name={base_name}",
                        f"base_id/base_name must both match {base_record.get('name')}",
                    )
                )
            required_level = base_required_level(base_record)
            if required_level > EARLY_GAME_MAX_BASE_REQUIRED_LEVEL:
                blockers.append(
                    _blocker(
                        "early_game_proof_item_base_tier_too_high",
                        f"{label}: {base_name} requires level {required_level}",
                        f"Early Game base required level must be <= {EARLY_GAME_MAX_BASE_REQUIRED_LEVEL}.",
                    )
                )
            if not base_implicit_matches(base_record, _string_entries(item.get("implicit_mods") or item.get("implicits"))):
                blockers.append(
                    _blocker(
                        "early_game_proof_item_implicit_not_from_base",
                        label,
                        _string(base_record.get("implicit_text")) or "no implicit",
                    )
                )
        if not _has_proof_item_catalog_ref(item):
            blockers.append(
                _blocker(
                    "early_game_proof_item_catalog_ref_missing",
                    label,
                    "base_catalog_ref, catalog_ref, source_ref, or evidence_ref",
                )
            )
        affixes = _proof_item_affixes(item)
        if len(affixes) > EARLY_GAME_MAX_EXPLICIT_AFFIXES_PER_RARE:
            blockers.append(
                _blocker(
                    "early_game_proof_item_too_many_affixes",
                    f"{label}: {len(affixes)} affixes",
                    f"At most {EARLY_GAME_MAX_EXPLICIT_AFFIXES_PER_RARE} structured affixes per rare item.",
                )
            )
        for affix_index, affix in enumerate(affixes, start=1):
            blockers.extend(
                _proof_affix_blockers(affix, label=label, affix_index=affix_index, base_record=base_record)
            )
        if _is_resistance_fixing_ring(item) and not _has_ring_base_justification(item):
            blockers.append(
                _blocker(
                    "early_game_ring_base_requires_two_stone_or_justification",
                    f"{label}: {item.get('base_name') or item.get('base')}",
                    "Use Two-Stone Ring for Early Game resistance fixing, or add base_choice_justification.",
                )
            )
    return blockers


def _proof_item_entries(item_state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in ("proof_items", "item_proofs", "structured_items"):
        entries = [entry for entry in _sequence(item_state.get(key)) if isinstance(entry, Mapping)]
        if entries:
            return entries
    return []


def _proof_item_label(item: Mapping[str, Any], *, index: int) -> str:
    return _string(item.get("label") or item.get("name") or item.get("slot")) or f"proof-item-{index}"


def _has_proof_item_catalog_ref(item: Mapping[str, Any]) -> bool:
    return bool(
        _string(item.get("base_catalog_ref"))
        or _string(item.get("catalog_ref"))
        or _string(item.get("source_ref"))
        or _sequence(item.get("evidence_refs"))
    )


def _proof_item_affixes(item: Mapping[str, Any]) -> list[Any]:
    for key in ("affixes", "explicit_affixes", "explicit_mods", "structured_affixes"):
        entries = list(_sequence(item.get(key)))
        if entries:
            return entries
    return []


def _proof_affix_blockers(
    affix: Any,
    *,
    label: str,
    affix_index: int,
    base_record: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(affix, Mapping):
        return [
            _blocker(
                "early_game_proof_item_affix_not_structured",
                f"{label} affix {affix_index}: {_string(affix) or type(affix).__name__}",
                "Affix must be an object with affix_id, tier, value, and source/catalog ref.",
            )
        ]
    blockers: list[dict[str, Any]] = []
    affix_label = f"{label} affix {affix_index}"
    affix_id = _string(affix.get("affix_id") or affix.get("id"))
    if not affix_id:
        blockers.append(_blocker("early_game_proof_item_affix_id_missing", affix_label, "affix_id"))
    tier = tier_number(affix.get("tier"))
    if tier is None:
        blockers.append(_blocker("early_game_proof_item_affix_tier_missing", affix_label, "T3 or lower-power tier"))
    elif tier < EARLY_GAME_BEST_ALLOWED_AFFIX_TIER:
        blockers.append(
            _blocker(
                "early_game_proof_item_affix_tier_too_high",
                f"{affix_label}: T{tier}",
                f"T{EARLY_GAME_BEST_ALLOWED_AFFIX_TIER} or lower-power",
            )
        )
    values = proof_affix_numeric_values(affix)
    if not values:
        blockers.append(
            _blocker(
                "early_game_proof_item_affix_value_missing",
                affix_label,
                "Structured affix value, value_range, or values",
            )
        )
    if not (_string(affix.get("source_ref") or affix.get("catalog_ref")) or _sequence(affix.get("evidence_refs"))):
        blockers.append(
            _blocker(
                "early_game_proof_item_affix_source_ref_missing",
                affix_label,
                "source_ref, catalog_ref, or evidence_refs",
            )
        )
    if affix_id and base_record:
        item_class = item_class_for_base(base_record)
        if not affix_exists_anywhere(affix_id):
            blockers.append(
                _blocker(
                    "early_game_proof_item_affix_unknown",
                    f"{affix_label}: {affix_id}",
                    "affix_id must resolve to the skill-owned Early Game mod catalog",
                )
            )
        elif not affix_allowed_on_item_class(affix_id, item_class):
            blockers.append(
                _blocker(
                    "early_game_proof_item_affix_wrong_item_class",
                    f"{affix_label}: {affix_id} on {item_class}",
                    "affix_id must be valid for the item base class",
                )
            )
        elif tier is not None:
            tier_record = lookup_affix_tier(affix_id, item_class, affix.get("tier"))
            if not tier_record:
                blockers.append(
                    _blocker(
                        "early_game_proof_item_affix_tier_unknown",
                        f"{affix_label}: {affix_id} {affix.get('tier')}",
                        "tier must exist for this affix_id and item class in the skill-owned mod catalog",
                    )
                )
            elif values:
                low, high = tier_value_range(tier_record)
                if high is not None and max(values) > high:
                    blockers.append(
                        _blocker(
                            "early_game_proof_item_affix_value_too_high",
                            f"{affix_label}: max value {max(values)} > {high} for {affix_id} {affix.get('tier')}",
                            tier_record.get("text"),
                        )
                    )
                if low is not None and min(values) < low:
                    blockers.append(
                        _blocker(
                            "early_game_proof_item_affix_value_out_of_range",
                            f"{affix_label}: min value {min(values)} < {low} for {affix_id} {affix.get('tier')}",
                            tier_record.get("text"),
                        )
                    )
    elif affix_id and base_record is None:
        blockers.append(
            _blocker(
                "early_game_proof_item_affix_base_unresolved",
                f"{affix_label}: {affix_id}",
                "Resolve proof item base before validating affix catalog applicability.",
            )
        )
    return blockers


def _is_resistance_fixing_ring(item: Mapping[str, Any]) -> bool:
    base_name = _normalized_search_text(item.get("base_name") or item.get("base") or item.get("base_type"))
    if "ring" not in base_name or "two stone" in base_name:
        return False
    affix_text = _normalized_search_text(_proof_item_affixes(item))
    return "resist" in affix_text or "resistance" in affix_text


def _has_ring_base_justification(item: Mapping[str, Any]) -> bool:
    for key in ("base_choice_justification", "ring_base_justification", "resistance_fixing_justification"):
        if _string(item.get(key)):
            return True
    return bool(_sequence(item.get("base_choice_evidence_refs")))


def _parse_item_entry(item: Any, *, index: int) -> dict[str, Any]:
    if isinstance(item, Mapping):
        raw_text = _string(item.get("raw_item_text") or item.get("raw_text") or item.get("text"))
        parsed = _parse_raw_item_text(raw_text, index=index) if raw_text else {}
        explicit_affixes = _string_entries(
            item.get("explicit_affixes")
            or item.get("explicit_mods")
            or item.get("affixes")
            or parsed.get("explicit_affixes")
        )
        implicit_mods = _string_entries(item.get("implicit_mods") or item.get("implicits") or parsed.get("implicit_mods"))
        return {
            "label": _string(item.get("label") or item.get("name") or item.get("slot")) or parsed.get("label") or f"item-{index}",
            "rarity": _string(item.get("rarity")) or parsed.get("rarity") or "",
            "base_name": _string(item.get("base") or item.get("base_type") or item.get("item_base")) or parsed.get("base_name") or "",
            "explicit_affixes": explicit_affixes,
            "implicit_mods": implicit_mods,
        }
    if isinstance(item, str):
        return _parse_raw_item_text(item, index=index)
    return {"label": f"item-{index}", "rarity": "", "base_name": "", "explicit_affixes": [], "implicit_mods": []}


def _parse_raw_item_text(raw_text: str, *, index: int) -> dict[str, Any]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    content_lines = [line for line in lines if set(line) != {"-"}]
    rarity = ""
    if content_lines and content_lines[0].lower().startswith("rarity:"):
        rarity = content_lines[0].split(":", 1)[1].strip()
        content_lines = content_lines[1:]
    label = content_lines[0] if content_lines else f"item-{index}"
    base_name = content_lines[1] if len(content_lines) > 1 else ""
    affix_lines = [
        line
        for line in content_lines[2:]
        if not _raw_item_non_affix_line(line) and not line.lower().startswith("implicit:")
    ]
    implicit_mods = [line.split(":", 1)[1].strip() for line in content_lines[2:] if line.lower().startswith("implicit:")]
    return {
        "label": label,
        "rarity": rarity,
        "base_name": base_name,
        "explicit_affixes": affix_lines,
        "implicit_mods": implicit_mods,
    }


def _string_entries(value: Any) -> list[str]:
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return [entry.strip() for entry in _sequence(value) if isinstance(entry, str) and entry.strip()]


def _raw_item_non_affix_line(line: str) -> bool:
    normalized = line.strip().lower()
    return (
        normalized.startswith("item level:")
        or normalized.startswith("requirements:")
        or normalized.startswith("sockets:")
        or normalized.startswith("quality:")
        or normalized.startswith("level:")
        or normalized.startswith("str:")
        or normalized.startswith("dex:")
        or normalized.startswith("int:")
    )


def _explicit_affix_tier(affix: str) -> int | None:
    text = affix.lower()
    match = re.search(r"\b(?:tier|t)\s*[:#-]?\s*([1-9])\b", text)
    if not match:
        return None
    return int(match.group(1))


def _is_flat_accuracy_affix(affix: str) -> bool:
    text = affix.lower()
    return bool(re.search(r"(?:\+|adds\s+)?\d+\s+to\s+accuracy(?:\s+rating)?", text) or "accuracy rating" in text)


def _fabricated_implicit_markers(implicit_mods: Sequence[str], base_info: Mapping[str, Any] | None) -> list[str]:
    if not implicit_mods:
        return []
    allowed_markers = {str(marker).lower() for marker in _sequence(_mapping(base_info).get("implicit_markers"))}
    fabricated = []
    for implicit in implicit_mods:
        text = implicit.lower()
        if not allowed_markers or not any(marker and marker in text for marker in allowed_markers):
            fabricated.append(implicit)
    return fabricated


def _tested_hypothesis_label(
    ledger: Mapping[str, Any],
    composition: Mapping[str, Any] | None = None,
    identity: Mapping[str, Any] | None = None,
) -> str:
    composition = _mapping(composition)
    identity = _mapping(identity)
    for container in (ledger, composition, identity, _mapping(ledger.get("source_context"))):
        for key in ("tested_hypothesis", "build_hypothesis", "hypothesis", "build_archetype", "archetype"):
            value = _string(container.get(key))
            if value:
                return value
    accepted_candidate = _mapping(_mapping(ledger.get("source_context")).get("accepted_candidate_ref"))
    candidate_label = _string(accepted_candidate.get("candidate_label"))
    if candidate_label:
        return candidate_label
    trace = _mapping(ledger.get("direct_build_decision_trace"))
    for key in ("tested_hypothesis", "build_hypothesis", "candidate_label"):
        value = _string(trace.get(key))
        if value:
            return value
    final_candidate = _mapping(trace.get("final_candidate"))
    return _string(final_candidate.get("candidate_label") or final_candidate.get("label"))


def _build_archetype_label(
    ledger: Mapping[str, Any],
    composition: Mapping[str, Any] | None = None,
    identity: Mapping[str, Any] | None = None,
) -> str:
    composition = _mapping(composition)
    identity = _mapping(identity)
    for container in (ledger, composition, identity):
        value = _string(container.get("build_archetype") or container.get("archetype"))
        if value:
            return value
    return _tested_hypothesis_label(ledger, composition, identity)


def _rare_gem_level_item_count(item_state: Mapping[str, Any]) -> int:
    count = 0
    for item in _item_entries(item_state):
        text = _normalized_search_text(item)
        if "rare" in text and _mentions_gem_level_power(text):
            count += 1
    return count


def _high_power_rare_item_labels(item_state: Mapping[str, Any]) -> list[str]:
    labels: list[str] = []
    for index, item in enumerate(_item_entries(item_state), start=1):
        text = _normalized_search_text(item)
        if "rare" not in text:
            continue
        if any(marker in text for marker in ("tier 1", "t1 ", "elevated", "fractured", "synthesised", "synthesized")):
            if isinstance(item, Mapping):
                labels.append(_string(item.get("label") or item.get("name") or item.get("slot")) or f"item-{index}")
            else:
                labels.append(f"item-{index}")
    return labels


def _item_entries(item_state: Mapping[str, Any]) -> list[Any]:
    for key in ("raw_items", "items", "equipped_items", "item_shell"):
        value = item_state.get(key)
        if isinstance(value, Mapping):
            return list(value.values())
        entries = list(_sequence(value))
        if entries:
            return entries
    gear_slots = item_state.get("gear_slots")
    if isinstance(gear_slots, Mapping):
        return list(gear_slots.values())
    return []


def _mentions_gem_level_power(text: str) -> bool:
    return (
        "level of all" in text
        or "level of socketed" in text
        or "+1 to level" in text
        or "+2 to level" in text
        or "+3 to level" in text
    )


def _has_power_gear_allowance(ledger: Mapping[str, Any]) -> bool:
    containers = [ledger, _mapping(ledger.get("budget_shell"))]
    containers.extend(_accepted_decision_rows(ledger))
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        for key in ("early_game_power_gear_evidence_refs", "power_gear_evidence_refs", "item_power_evidence_refs"):
            if _sequence(container.get(key)):
                return True
    return False


def _normalized_bandit(value: Any) -> str:
    text = _string(value).lower().replace("_", " ").replace("-", " ")
    if text in {"kill all", "kill_all"}:
        return "kill_all"
    if text == "none":
        return "none"
    return text


def _baseline_config(config_state: Mapping[str, Any]) -> Mapping[str, Any]:
    config_sets = config_state.get("config_sets")
    if isinstance(config_sets, Sequence) and not isinstance(config_sets, (str, bytes, bytearray)):
        fallback: Mapping[str, Any] = {}
        for entry in config_sets:
            if not isinstance(entry, Mapping):
                continue
            if not fallback:
                fallback = entry
            marker = _normalized_search_text(
                {
                    "state_role": entry.get("state_role"),
                    "config_set_id": entry.get("config_set_id"),
                    "id": entry.get("id"),
                    "label": entry.get("label"),
                    "name": entry.get("name"),
                }
            )
            if "baseline" in marker:
                return entry
        return fallback
    baseline = config_state.get("baseline")
    if isinstance(baseline, Mapping):
        return baseline
    return config_state


def _baseline_boss_label(config: Mapping[str, Any]) -> str:
    labels: list[str] = []
    for container in (config, _mapping(config.get("enemy_state")), _mapping(config.get("enemy"))):
        for key, value in container.items():
            key_text = str(key).lower()
            if "boss" in key_text or "enemy" in key_text or "pinnacle" in key_text or "guardian" in key_text:
                labels.append(_string(value))
    return _normalized_search_text(labels)


def _skill_uses_ignite_or_burning(skill_state: Mapping[str, Any], ledger: Mapping[str, Any]) -> bool:
    text = _normalized_search_text([skill_state, [row for row in _accepted_decision_rows(ledger) if _row_mutation_kind(row) == "skill"]])
    return any(marker in text for marker in ("ignite", "ignited", "burning damage", "combustion", "swift affliction"))


def _baseline_enemy_ignited(config: Mapping[str, Any]) -> bool:
    return _recursive_truthy_key(
        config,
        {
            "is_ignited",
            "enemy_ignited",
            "enemy_is_ignited",
            "ignited",
            "conditionenemyignited",
            "condition_enemy_ignited",
        },
    )


def _has_mastery_consideration(tree_state: Mapping[str, Any], composition: Mapping[str, Any]) -> bool:
    for key in ("allocated_masteries", "masteries", "mastery_allocations", "mastery_effect_ids", "allocated_mastery_effect_ids"):
        if _sequence(tree_state.get(key)):
            return True
    if _string(tree_state.get("no_masteries_justification")) and _has_rejected_mastery_alternatives(tree_state):
        return True
    return False


def _has_rejected_mastery_alternatives(tree_state: Mapping[str, Any]) -> bool:
    for key in ("rejected_mastery_alternatives", "mastery_alternatives_rejected", "no_mastery_alternative_refs"):
        if _sequence(tree_state.get(key)):
            return True
    return False


def _tree_semantic_blockers(
    ledger: Mapping[str, Any],
    tree_state: Mapping[str, Any],
    composition: Mapping[str, Any],
    skill_state: Mapping[str, Any],
    identity: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not _is_fireball_spell_route(ledger, skill_state, identity, composition):
        return []
    blockers: list[dict[str, Any]] = []
    tags = _tree_relevance_tags(ledger, tree_state, composition)
    if not tags & _fireball_relevant_tree_tags():
        blockers.append(
            _blocker(
                "early_game_fireball_tree_relevance_missing",
                sorted(tags),
                "Fireball spell route needs fire/spell/cast/life/defense/resource/requirement relevance tags.",
            )
        )
    irrelevant = sorted(tags & _fireball_irrelevant_tree_tags())
    if irrelevant and not _has_tree_irrelevance_justification(ledger, tree_state):
        blockers.append(
            _blocker(
                "early_game_fireball_tree_irrelevant_accuracy_pathing",
                irrelevant,
                "Remove accuracy/attack route pressure from a spell Fireball tree or cite measured constraint evidence.",
            )
        )
    mastery_text = _normalized_search_text(
        [
            tree_state.get("allocated_masteries"),
            tree_state.get("masteries"),
            _mapping(composition.get("tree_summary")).get("mastery_focus"),
        ]
    )
    if "accuracy" in mastery_text and not _has_tree_irrelevance_justification(ledger, tree_state):
        blockers.append(
            _blocker(
                "early_game_mastery_relevance_missing",
                mastery_text,
                "Fireball spell route masteries must be relevant or explicitly justified by measured constraint evidence.",
            )
        )
    return blockers


def _ascendancy_semantic_blockers(
    ledger: Mapping[str, Any],
    tree_state: Mapping[str, Any],
    composition: Mapping[str, Any],
    skill_state: Mapping[str, Any],
    identity: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not _is_fireball_spell_route(ledger, skill_state, identity, composition):
        return []
    text = _normalized_search_text(
        [
            tree_state.get("ascendancy_notables"),
            tree_state.get("allocated_ascendancy_notables"),
            tree_state.get("ascendancy_node_names"),
            tree_state.get("ascendancy_relevance"),
            _mapping(composition.get("tree_summary")).get("ascendancy_notables"),
            [
                row
                for row in _accepted_decision_rows(ledger)
                if _string(row.get("mutation_kind") or row.get("target_mutation_kind")) in {"tree", "identity"}
            ],
        ]
    )
    if not any(marker in text for marker in ("impale", "attack", "melee", "bleed", "master of metal")):
        return []
    if _has_ascendancy_attack_or_impale_evidence(ledger, tree_state, skill_state):
        return []
    return [
        _blocker(
            "early_game_ascendancy_irrelevant_impale_for_fireball",
            "Champion ascendancy package contains impale/attack/melee value on a Fireball spell route.",
            "Every ascendancy notable must have build-relevant value evidence; remove impale/attack notables or prove the build uses them.",
        )
    ]


def _has_ascendancy_attack_or_impale_evidence(
    ledger: Mapping[str, Any],
    tree_state: Mapping[str, Any],
    skill_state: Mapping[str, Any],
) -> bool:
    containers = [ledger, tree_state, skill_state, _mapping(tree_state.get("quality_rails"))]
    containers.extend(_accepted_decision_rows(ledger))
    if _has_evidence_refs(
        containers,
        {
            "ascendancy_relevance_evidence_refs",
            "impale_evidence_refs",
            "attack_scaling_evidence_refs",
            "ascendancy_value_evidence_refs",
        },
    ):
        return True
    return any(
        _string(container.get("ascendancy_relevance_justification") or container.get("impale_justification"))
        for container in containers
        if isinstance(container, Mapping)
    )


def _tree_pathing_quality_blockers(
    ledger: Mapping[str, Any],
    tree_state: Mapping[str, Any],
    composition: Mapping[str, Any],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if not _has_tree_pathing_quality_evidence(ledger, tree_state, composition):
        blockers.append(
            _blocker(
                "early_game_pathing_cleanup_missing",
                "Early Game tree needs pathing cleanup/travel-tax accounting before publication.",
                "Add pathing cleanup notes, bounded travel_tax_ratio, and Pathing Opportunity Cost evidence.",
            )
        )
        return blockers
    if not _has_explicit_pathing_cleanup_text(ledger, tree_state, composition):
        blockers.append(
            _blocker(
                "early_game_pathing_cleanup_missing",
                "Pathing Opportunity Cost refs or travel ratios alone are not enough.",
                "Add explicit pathing cleanup steps/notes for the selected route.",
            )
        )
    travel_tax_ratio = _tree_travel_tax_ratio(ledger, tree_state)
    if travel_tax_ratio is None:
        blockers.append(
            _blocker(
                "early_game_pathing_travel_tax_missing",
                None,
                f"travel_tax_ratio <= {EARLY_GAME_MAX_TRAVEL_TAX_RATIO}",
            )
        )
    elif travel_tax_ratio > EARLY_GAME_MAX_TRAVEL_TAX_RATIO and not _has_tree_irrelevance_justification(ledger, tree_state):
        blockers.append(
            _blocker(
                "early_game_pathing_travel_tax_too_high",
                travel_tax_ratio,
                f"travel_tax_ratio <= {EARLY_GAME_MAX_TRAVEL_TAX_RATIO} or explicit measured waiver",
            )
        )
    return blockers


def _tree_visual_inspection_blockers(tree_state: Mapping[str, Any]) -> list[dict[str, Any]]:
    visual = _tree_visual_inspection_payload(tree_state)
    blockers = []
    for blocker in validate_tree_visual_inspection_artifact(visual):
        code = _string(blocker.get("code")) or "tree_visual_inspection_blocker"
        blockers.append(
            _blocker(
                f"early_game_{code}",
                _json_safe_value(blocker.get("observed")),
                _json_safe_value(blocker.get("expected")),
            )
        )
    return blockers


def _tree_visual_inspection_payload(tree_state: Mapping[str, Any]) -> Mapping[str, Any]:
    quality = _mapping(tree_state.get("quality_rails"))
    for container in (tree_state, quality):
        for key in ("tree_visual_inspection", "visual_inspection", "visual_tree_inspection"):
            value = _mapping(container.get(key))
            if value:
                return value
    return {}


def _has_tree_pathing_quality_evidence(
    ledger: Mapping[str, Any],
    tree_state: Mapping[str, Any],
    composition: Mapping[str, Any],
) -> bool:
    quality = _mapping(tree_state.get("quality_rails"))
    if _sequence(quality.get("pathing_cleanup_steps")) or _string(quality.get("pathing_cleanup_notes")):
        return True
    if _float_value(quality.get("travel_tax_ratio")) is not None or _float_value(tree_state.get("travel_tax_ratio")) is not None:
        return True
    tree_summary = _mapping(composition.get("tree_summary"))
    if _string(tree_summary.get("pathing_cleanup_notes")):
        return True
    for row in _accepted_decision_rows(ledger):
        if not _is_tree_pathing_decision_row(row):
            continue
        if _has_row_cost_aware_refs(row, "pathing_opportunity_cost_refs"):
            return True
        if _float_value(row.get("travel_tax_ratio")) is not None or _string(row.get("pathing_cleanup_notes")):
            return True
    return False


def _has_explicit_pathing_cleanup_text(
    ledger: Mapping[str, Any],
    tree_state: Mapping[str, Any],
    composition: Mapping[str, Any],
) -> bool:
    quality = _mapping(tree_state.get("quality_rails"))
    if _sequence(quality.get("pathing_cleanup_steps")) or _string(quality.get("pathing_cleanup_notes")):
        return True
    tree_summary = _mapping(composition.get("tree_summary"))
    if _string(tree_summary.get("pathing_cleanup_notes")):
        return True
    return any(
        _is_tree_pathing_decision_row(row) and _string(row.get("pathing_cleanup_notes"))
        for row in _accepted_decision_rows(ledger)
    )


def _tree_travel_tax_ratio(ledger: Mapping[str, Any], tree_state: Mapping[str, Any]) -> float | None:
    quality = _mapping(tree_state.get("quality_rails"))
    for value in (quality.get("travel_tax_ratio"), tree_state.get("travel_tax_ratio")):
        numeric = _float_value(value)
        if numeric is not None:
            return numeric
    for row in _accepted_decision_rows(ledger):
        if not _is_tree_pathing_decision_row(row):
            continue
        numeric = _float_value(row.get("travel_tax_ratio"))
        if numeric is not None:
            return numeric
    return None


def _is_fireball_spell_route(
    ledger: Mapping[str, Any],
    skill_state: Mapping[str, Any],
    identity: Mapping[str, Any],
    composition: Mapping[str, Any],
) -> bool:
    text = _normalized_search_text([ledger.get("request_summary"), ledger.get("build_identity"), skill_state, identity, composition])
    return "fireball" in text


def _tree_relevance_tags(
    ledger: Mapping[str, Any],
    tree_state: Mapping[str, Any],
    composition: Mapping[str, Any],
) -> set[str]:
    values: list[Any] = [
        tree_state.get("relevance_tags"),
        tree_state.get("semantic_relevance_tags"),
        _mapping(tree_state.get("quality_rails")).get("relevance_tags"),
        _mapping(tree_state.get("quality_rails")).get("semantic_relevance_tags"),
        _mapping(composition.get("tree_summary")).get("relevance_tags"),
    ]
    for row in _accepted_decision_rows(ledger):
        if not _is_tree_pathing_decision_row(row):
            continue
        values.extend(
            [
                row.get("relevance_tags"),
                row.get("semantic_relevance_tags"),
                row.get("impact_categories"),
                _mapping(row.get("value_summary")).get("impact_categories"),
            ]
        )
    tags: set[str] = set()
    for value in values:
        for entry in _sequence(value):
            if isinstance(entry, str) and entry.strip():
                tags.add(entry.strip().lower().replace(" ", "_").replace("-", "_"))
    return tags


def _fireball_relevant_tree_tags() -> set[str]:
    return {
        "fire",
        "fire_damage",
        "fire_spell_damage",
        "spell",
        "spell_damage",
        "elemental",
        "elemental_damage",
        "cast_speed",
        "projectile_spell",
        "aoe",
        "life",
        "armour",
        "defense",
        "defence",
        "resistance",
        "elemental_resistance",
        "mana",
        "reservation",
        "attribute_requirement_repair",
        "requirement_relief",
    }


def _fireball_irrelevant_tree_tags() -> set[str]:
    return {
        "accuracy",
        "accuracy_rating",
        "attack",
        "attack_damage",
        "attack_speed",
        "bow",
        "melee",
        "weapon_projectile",
        "attack_projectile",
    }


def _has_tree_irrelevance_justification(ledger: Mapping[str, Any], tree_state: Mapping[str, Any]) -> bool:
    containers = [ledger, tree_state, _mapping(tree_state.get("quality_rails"))]
    containers.extend(row for row in _accepted_decision_rows(ledger) if _is_tree_pathing_decision_row(row))
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        if _string(container.get("semantic_relevance_justification")) or _string(container.get("irrelevant_stat_justification")):
            return True
        for key in ("tree_semantic_evidence_refs", "irrelevant_stat_evidence_refs", "constraint_repair_evidence_refs"):
            if _sequence(container.get(key)):
                return True
    return False


def _recursive_truthy_key(value: Any, keys: set[str]) -> bool:
    if isinstance(value, Mapping):
        for key, entry in value.items():
            normalized_key = str(key).strip().lower().replace(" ", "_").replace("-", "_")
            if normalized_key in keys and _truthy(entry):
                return True
            if _recursive_truthy_key(entry, keys):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_recursive_truthy_key(entry, keys) for entry in value)
    return False


def _normalized_search_text(value: Any) -> str:
    return " ".join(_flatten_strings(value)).lower().replace("_", " ").replace("-", " ")


def _normalized_key(value: Any) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        result: list[str] = []
        for key, entry in value.items():
            result.append(str(key))
            result.extend(_flatten_strings(entry))
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        result = []
        for entry in value:
            result.extend(_flatten_strings(entry))
        return result
    if value is None:
        return []
    return [str(value)]


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "on", "enabled", "active"}
    return bool(value)


def _direct_build_lane(ledger: Mapping[str, Any]) -> str:
    return _string(ledger.get("direct_build_lane") or ledger.get("loadout_id") or ledger.get("lane"))


def _accepted_decision_rows(ledger: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = ledger.get("accepted_decision_rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        rows = ledger.get("decision_rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return []
    accepted = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if _string(row.get("status")) in {"accepted", "publication_ready"}:
            accepted.append(row)
    return accepted


def _accepted_mutation_kinds(ledger: Mapping[str, Any]) -> set[str]:
    kinds = set()
    for row in _accepted_decision_rows(ledger):
        kind = _string(row.get("mutation_kind") or row.get("target_mutation_kind") or row.get("surface"))
        if kind:
            kinds.add(kind)
    return kinds


def _semantic_findings_as_blockers(semantic_validation: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings = semantic_validation.get("findings")
    if not isinstance(findings, Sequence) or isinstance(findings, (str, bytes, bytearray)):
        return []
    return [
        _blocker(
            _string(finding.get("code")) if isinstance(finding, Mapping) else "semantic_validation_finding",
            _string(finding.get("summary")) if isinstance(finding, Mapping) else "Semantic validation finding.",
            "Repair the decision ledger and rerun production.",
        )
        for finding in findings
    ]


def _source_packet_blockers_as_publication_blockers(source_packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers = source_packet.get("blockers")
    if not isinstance(blockers, Sequence) or isinstance(blockers, (str, bytes, bytearray)):
        return []
    return [_normalize_blocker(blocker, prefix="source_packet") for blocker in blockers]


def _checkpoint_blockers_as_publication_blockers(checkpoint: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers = checkpoint.get("blockers")
    if not isinstance(blockers, Sequence) or isinstance(blockers, (str, bytes, bytearray)):
        return []
    return [_normalize_blocker(blocker, prefix="checkpoint") for blocker in blockers]


def _normalize_blocker(blocker: Any, *, prefix: str) -> dict[str, Any]:
    if not isinstance(blocker, Mapping):
        return _blocker(f"{prefix}_blocker_invalid", "A blocker was not a JSON object.", "Repair machine-readable blockers.")
    return _blocker(
        _string(blocker.get("blocker_id") or blocker.get("code")) or f"{prefix}_blocker",
        _string(blocker.get("summary")) or "Direct Build materialization blocker.",
        _string(blocker.get("unblock_condition")) or "Repair this blocker and rerun.",
    )


def _composition_summary(
    ledger: Mapping[str, Any],
    identity: Mapping[str, Any],
    ready_import_code_path: Path,
) -> dict[str, Any]:
    composition = dict(_mapping(ledger.get("composition_summary")))
    ready_payload = ready_import_code_path.read_text(encoding="utf-8")
    composition["class_name"] = _string(composition.get("class_name")) or _string(identity.get("class_name"))
    composition["ascendancy"] = _string(composition.get("ascendancy")) or _string(identity.get("ascendancy")) or "None"
    composition["main_skill"] = _string(composition.get("main_skill")) or _string(identity.get("main_skill"))
    composition["tested_hypothesis"] = _tested_hypothesis_label(ledger, composition, identity) or "Legacy Direct Build route"
    composition["build_archetype"] = _build_archetype_label(ledger, composition, identity) or composition["tested_hypothesis"]
    composition["build_label"] = _string(composition.get("build_label")) or (
        f"{composition['main_skill']} {composition['ascendancy']}".strip()
    )
    composition["ready_pob_import"] = {
        "surface_kind": "pob_string",
        "locator": None,
        "import_code_locator": _path_string(ready_import_code_path),
        "payload": ready_payload,
    }
    return composition


def _source_context(ledger: Mapping[str, Any]) -> dict[str, Any]:
    source_context = ledger.get("source_context")
    if isinstance(source_context, Mapping):
        return dict(source_context)
    ledger_id = _string(ledger.get("ledger_id")) or "direct-build-decision-ledger"
    return {
        "entry_kind": "brief_only",
        "request_summary": _string(ledger.get("request_summary")) or "Agent-authored Direct Build request.",
        "brief_ref": {
            "brief_id": f"brief.{_safe_ref(ledger_id)}",
            "label": "Agent-authored Direct Build decision ledger",
            "locator": "direct-build-decision-ledger.json",
        },
        "accepted_candidate_ref": None,
    }


def _state_section(
    ledger: Mapping[str, Any],
    calc_snapshot: Mapping[str, Any],
    readback_state: Mapping[str, Any],
    *,
    field_name: str,
) -> dict[str, Any]:
    existing = ledger.get(field_name)
    if isinstance(existing, Mapping):
        return dict(existing)
    rows = _metric_rows_from_calc(calc_snapshot)
    if not rows:
        rows = [
            {
                "metric_key": "readback_surface_count",
                "label": "Readback surface count",
                "value": float(len([key for key in ("items_state", "tree_state", "skills_state", "config_state") if key in readback_state])),
                "unit": None,
                "note": "Fallback proof metric from materialized read-back surfaces.",
            }
        ]
    return {
        "summary": "Materialized PoB read-back metrics.",
        "metric_rows": rows,
        "scope_notes": ["Generated from the materializer calc/read-back snapshot."],
    }


def _metric_rows_from_calc(calc_snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    metrics = _find_metric_mapping(calc_snapshot)
    rows = []
    for key, label, unit in (
        ("FullDPS", "Full DPS", "dps"),
        ("CombinedDPS", "Combined DPS", "dps"),
        ("Life", "Life", None),
        ("EnergyShield", "Energy Shield", None),
        ("HitChance", "Hit Chance", "%"),
        ("TotalEHP", "Total EHP", None),
    ):
        value = _float_value(metrics.get(key))
        if value is None:
            continue
        rows.append({"metric_key": key, "label": label, "value": value, "unit": unit, "note": None})
    return rows


def _find_metric_mapping(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    for key in ("main_output", "calcs_output", "output", "metrics"):
        candidate = payload.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    baseline = payload.get("baseline")
    if isinstance(baseline, Mapping):
        candidate = _find_metric_mapping(baseline)
        if candidate:
            return candidate
    calc_snapshot = payload.get("calc_snapshot")
    if isinstance(calc_snapshot, Mapping):
        candidate = _find_metric_mapping(calc_snapshot)
        if candidate:
            return candidate
    return {}


def _sibling_decision_ledger(semantic_path: Path) -> Mapping[str, Any]:
    ledger_path = semantic_path.with_name("direct-build-decision-ledger.json")
    if not ledger_path.is_file():
        return {}
    return _load_json_mapping(ledger_path, label="decision ledger")


def _default_pob_run_id(source_packet: Mapping[str, Any]) -> str:
    return f"direct-build-materialize.{_safe_ref(_string(source_packet.get('ledger_id')) or 'run')}"


def _import_verifier_pob_run_id(run_id: str) -> str:
    return f"icv.{sha256_bytes(run_id.encode('utf-8'))[:16]}"


def _dedupe_publication_blockers(blockers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for blocker in blockers:
        if not isinstance(blocker, Mapping):
            continue
        blocker_id = _string(blocker.get("blocker_id")) or _string(blocker.get("code")) or "publication_blocker"
        summary = _string(blocker.get("summary"))
        dedupe_key = (blocker_id, summary)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        result.append(dict(blocker))
    return result


def _safe_ref(value: str) -> str:
    normalized = "".join(character if character.isalnum() or character in "._-" else "-" for character in value.strip())
    return normalized or "unknown"


def _blocker(blocker_id: str, summary: str, unblock_condition: str) -> dict[str, Any]:
    return {
        "blocker_id": blocker_id,
        "severity": "blocking",
        "summary": summary,
        "unblock_condition": unblock_condition,
    }


def _finding(code: str, summary: str, *, details: Mapping[str, Any] | None = None) -> dict[str, Any]:
    finding = {"code": code, "summary": summary}
    if details:
        finding["details"] = dict(details)
    return finding


def _load_json_mapping(path: Path, *, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DirectBuildMaterializerError(f"{label} at {path} must be readable JSON.") from exc
    if not isinstance(payload, Mapping):
        raise DirectBuildMaterializerError(f"{label} at {path} must be a JSON object.")
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return []


def _sequence_or_default(value: Any, *, default: Sequence[Any]) -> Sequence[Any]:
    sequence = _sequence(value)
    return sequence if sequence else default


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _identity_value(value: Any) -> str | int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _float_value(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _path_string(path: Path) -> str:
    return Path(path).resolve(strict=False).as_posix()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    produce = subparsers.add_parser("produce", help="Produce semantic/source/checkpoint artifacts from a decision ledger.")
    produce.add_argument("--decision-ledger", type=Path, required=True)
    produce.add_argument("--output-dir", type=Path, required=True)

    materialize = subparsers.add_parser("materialize", help="Materialize a Direct Build source packet through PoB.")
    materialize.add_argument("--semantic-validation", type=Path, required=True)
    materialize.add_argument("--source-packet", type=Path, required=True)
    materialize.add_argument("--checkpoint", type=Path, required=True)
    materialize.add_argument("--output-dir", type=Path, required=True)
    materialize.add_argument("--artifacts-root", type=Path, required=True)
    materialize.add_argument("--pob-run-id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "produce":
        result = produce_direct_build_materialization_package(
            decision_ledger_path=args.decision_ledger,
            output_dir=args.output_dir,
        )
    else:
        result = materialize_direct_build_publication(
            semantic_validation_path=args.semantic_validation,
            materialization_source_packet_path=args.source_packet,
            pre_materialization_checkpoint_path=args.checkpoint,
            output_dir=args.output_dir,
            artifacts_root=args.artifacts_root,
            pob_run_id=args.pob_run_id,
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
