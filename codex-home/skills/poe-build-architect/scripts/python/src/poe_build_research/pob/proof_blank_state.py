"""Canonical blank-build proof surfaces for the minimal headless PoB slice."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping

from .artifacts import sha256_bytes, write_json
from .host_runtime import HEADLESS_PROOF_SLICE, PoBHeadlessHostContractError, PoBHeadlessProofRun, PoBHeadlessSessionHandle
from .release_manager import utc_now_iso

HEADLESS_PROOF_BLANK_STATE_SUPPORTED_PATH = "pob_headless_proof_blank_state_v1"
BLANK_BASELINE_PROOF_KIND = "pob_headless_blank_baseline"
BLANK_BASELINE_FILENAME = "blank-baseline-observation.json"
BLANK_ALLOWED_NEXT_ACTION = "prepare_boots_item"
BLANK_RECOMPUTE_EVENT_KIND = "blank_baseline_recompute"
EXPECTED_GEAR_SLOT_ORDER: tuple[str, ...] = (
    "Weapon 1",
    "Weapon 2",
    "Helmet",
    "Body Armour",
    "Gloves",
    "Boots",
    "Amulet",
    "Ring 1",
    "Ring 2",
    "Ring 3",
    "Belt",
    "Graft 1",
    "Graft 2",
    "Flask 1",
    "Flask 2",
    "Flask 3",
    "Flask 4",
    "Flask 5",
)
_CONFIG_DEFAULT_FIELDS: tuple[str, ...] = ("bandit", "pantheon_major", "pantheon_minor")
_BLANK_IDENTITY_LEVEL = 1
_BLANK_IDENTITY_CHARACTER_LEVEL_AUTO_MODE = True
_BLANK_IDENTITY_ACTIVE_SPEC_ID = "spec.main"
_BLANK_IDENTITY_CLASS_ID = "Witch"

BlankBuildCreator = Callable[[PoBHeadlessSessionHandle], None]
BlankStateReader = Callable[[PoBHeadlessSessionHandle], Mapping[str, Any]]


def _path_string(path: Path) -> str:
    return path.resolve(strict=False).as_posix()


def _require_mapping(value: Any, field_name: str, failure_state: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PoBHeadlessHostContractError(failure_state, f"{field_name} must be an object.")
    return dict(value)


def _require_list(value: Any, field_name: str, failure_state: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoBHeadlessHostContractError(failure_state, f"{field_name} must be an array.")
    return list(value)


def _require_bool(value: Any, field_name: str, failure_state: str) -> bool:
    if not isinstance(value, bool):
        raise PoBHeadlessHostContractError(failure_state, f"{field_name} must be a boolean.")
    return value


def _require_int(value: Any, field_name: str, failure_state: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PoBHeadlessHostContractError(failure_state, f"{field_name} must be an integer.")
    return value


def _require_non_empty_string(value: Any, field_name: str, failure_state: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PoBHeadlessHostContractError(failure_state, f"{field_name} must be a non-empty string.")
    return value.strip()


def _require_optional_string(value: Any, field_name: str, failure_state: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, field_name, failure_state)


def _require_string_list(value: Any, field_name: str, failure_state: str) -> list[str]:
    items = _require_list(value, field_name, failure_state)
    return [_require_non_empty_string(item, f"{field_name}[{index}]", failure_state) for index, item in enumerate(items)]


def _require_identifier_list(value: Any, field_name: str, failure_state: str) -> list[int | str]:
    items = _require_list(value, field_name, failure_state)
    normalized: list[int | str] = []
    for index, item in enumerate(items):
        if isinstance(item, bool) or not isinstance(item, (int, str)):
            raise PoBHeadlessHostContractError(
                failure_state,
                f"{field_name}[{index}] must be an integer or non-empty string identifier.",
            )
        if isinstance(item, str):
            normalized.append(_require_non_empty_string(item, f"{field_name}[{index}]", failure_state))
            continue
        normalized.append(item)
    return normalized


def _ensure_exact_keys(
    payload: Mapping[str, Any],
    *,
    allowed_keys: set[str],
    field_name: str,
    failure_state: str,
) -> None:
    observed_keys = set(payload)
    missing = sorted(allowed_keys - observed_keys)
    extra = sorted(observed_keys - allowed_keys)
    if missing:
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name} is missing required keys: {', '.join(missing)}.",
        )
    if extra:
        raise PoBHeadlessHostContractError(
            "blank_state_ambiguous",
            f"{field_name} includes unsupported keys: {', '.join(extra)}.",
        )


def _canonical_state_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return sha256_bytes(encoded)


def blank_baseline_observation_path(run: PoBHeadlessProofRun) -> Path:
    """Return the durable path for the structured blank-baseline proof."""

    return run.layout.manifest_paths.primary_proof_path.parent / BLANK_BASELINE_FILENAME


def _canonicalize_gear_slots(raw: Mapping[str, Any]) -> dict[str, Any]:
    payload = _require_mapping(raw, "gear_slots", "blank_state_missing_surface")
    payload.setdefault("state_kind", "empty")
    _ensure_exact_keys(
        payload,
        allowed_keys={
            "state_kind",
            "active_item_set_id",
            "use_second_weapon_set",
            "slot_order",
            "extra_slots",
            "slots",
            "nonempty_slot_count",
        },
        field_name="gear_slots",
        failure_state="blank_state_missing_surface",
    )
    state_kind = payload.get("state_kind")
    if state_kind is not None and _require_non_empty_string(state_kind, "gear_slots.state_kind", "blank_state_missing_surface") != "empty":
        raise PoBHeadlessHostContractError(
            "unexpected_nonempty_gear_state",
            "Blank baseline requires gear_slots.state_kind to remain empty.",
        )

    slot_order = _require_string_list(payload["slot_order"], "gear_slots.slot_order", "blank_state_missing_surface")
    if tuple(slot_order) != EXPECTED_GEAR_SLOT_ORDER:
        raise PoBHeadlessHostContractError(
            "blank_state_missing_surface",
            "gear_slots.slot_order must match the accepted deterministic main-slot order.",
        )

    extra_slots = _require_string_list(payload["extra_slots"], "gear_slots.extra_slots", "blank_state_missing_surface")
    if len(extra_slots) != len(set(extra_slots)) or set(extra_slots) & set(EXPECTED_GEAR_SLOT_ORDER):
        raise PoBHeadlessHostContractError(
            "blank_state_ambiguous",
            "gear_slots.extra_slots must be unique and must not overlap the canonical slot order.",
        )

    slots = _require_mapping(payload["slots"], "gear_slots.slots", "blank_state_missing_surface")
    expected_slot_keys = [*slot_order, *extra_slots]
    missing_slots = [slot for slot in expected_slot_keys if slot not in slots]
    unexpected_slots = sorted(set(slots) - set(expected_slot_keys))
    if missing_slots:
        raise PoBHeadlessHostContractError(
            "blank_state_missing_surface",
            f"gear_slots.slots is missing explicit blank-slot observations: {', '.join(missing_slots)}.",
        )
    if unexpected_slots:
        raise PoBHeadlessHostContractError(
            "blank_state_ambiguous",
            f"gear_slots.slots includes unsupported slot observations: {', '.join(unexpected_slots)}.",
        )

    normalized_slots: dict[str, dict[str, Any]] = {}
    for slot_name in expected_slot_keys:
        slot_payload = _require_mapping(slots[slot_name], f"gear_slots.slots.{slot_name}", "blank_state_missing_surface")
        _ensure_exact_keys(
            slot_payload,
            allowed_keys={"occupied", "item"},
            field_name=f"gear_slots.slots.{slot_name}",
            failure_state="blank_state_missing_surface",
        )
        occupied = _require_bool(slot_payload["occupied"], f"gear_slots.slots.{slot_name}.occupied", "blank_state_missing_surface")
        item = slot_payload["item"]
        if occupied or item is not None:
            raise PoBHeadlessHostContractError(
                "unexpected_nonempty_gear_state",
                f"Blank baseline requires slot {slot_name} to remain empty.",
            )
        normalized_slots[slot_name] = {"occupied": False, "item": None}

    nonempty_slot_count = _require_int(payload["nonempty_slot_count"], "gear_slots.nonempty_slot_count", "blank_state_missing_surface")
    if nonempty_slot_count != 0:
        raise PoBHeadlessHostContractError(
            "unexpected_nonempty_gear_state",
            "Blank baseline requires gear_slots.nonempty_slot_count to be 0.",
        )

    return {
        "state_kind": "empty",
        "active_item_set_id": _require_non_empty_string(
            payload["active_item_set_id"],
            "gear_slots.active_item_set_id",
            "blank_state_missing_surface",
        ),
        "use_second_weapon_set": _require_bool(
            payload["use_second_weapon_set"],
            "gear_slots.use_second_weapon_set",
            "blank_state_missing_surface",
        ),
        "slot_order": slot_order,
        "extra_slots": extra_slots,
        "slots": normalized_slots,
        "nonempty_slot_count": 0,
    }


def _canonicalize_tree_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    payload = _require_mapping(raw, "tree_state", "blank_state_missing_surface")
    payload.setdefault("state_kind", "default")
    payload.setdefault("override_carrier_node_ids", [])
    allowed_keys = {
        "state_kind",
        "active_spec_id",
        "class_id",
        "ascendancy_id",
        "secondary_ascendancy_id",
        "default_root_state_present",
        "engine_default_node_ids",
        "user_allocated_node_ids",
        "keystone_node_ids",
        "mastery_effect_ids",
        "cluster_jewel_socket_ids",
        "socketed_jewel_node_ids",
        "override_carrier_node_ids",
        "anoint_allocations",
    }
    observed_keys = set(payload)
    extra_keys = sorted(observed_keys - allowed_keys)
    missing_keys = allowed_keys - observed_keys
    if extra_keys:
        raise PoBHeadlessHostContractError(
            "blank_state_ambiguous",
            f"tree_state includes unsupported keys: {', '.join(extra_keys)}.",
        )
    missing_non_default_keys = sorted(missing_keys - {"engine_default_node_ids", "state_kind", "override_carrier_node_ids"})
    if missing_non_default_keys:
        raise PoBHeadlessHostContractError(
            "blank_state_missing_surface",
            f"tree_state is missing required keys: {', '.join(missing_non_default_keys)}.",
        )
    if "engine_default_node_ids" not in payload:
        raise PoBHeadlessHostContractError(
            "blank_state_ambiguous",
            "Blank baseline must record explicit engine_default_node_ids for the tree root state.",
        )
    state_kind = payload.get("state_kind")
    if state_kind is not None and _require_non_empty_string(state_kind, "tree_state.state_kind", "blank_state_missing_surface") != "default":
        raise PoBHeadlessHostContractError(
            "unexpected_nondefault_tree_state",
            "Blank baseline requires tree_state.state_kind to remain default.",
        )

    if not _require_bool(payload["default_root_state_present"], "tree_state.default_root_state_present", "blank_state_missing_surface"):
        raise PoBHeadlessHostContractError(
            "unexpected_nondefault_tree_state",
            "Blank baseline must explicitly prove that default_root_state_present is true.",
        )

    engine_default_node_ids = _require_identifier_list(
        payload["engine_default_node_ids"],
        "tree_state.engine_default_node_ids",
        "blank_state_ambiguous",
    )
    if not engine_default_node_ids:
        raise PoBHeadlessHostContractError(
            "blank_state_ambiguous",
            "Blank baseline must record explicit engine_default_node_ids for the tree root state.",
        )

    for field_name in (
        "user_allocated_node_ids",
        "keystone_node_ids",
        "mastery_effect_ids",
        "cluster_jewel_socket_ids",
        "socketed_jewel_node_ids",
        "anoint_allocations",
        ):
        values = _require_identifier_list(payload[field_name], f"tree_state.{field_name}", "blank_state_missing_surface")
        if values:
            raise PoBHeadlessHostContractError(
                "unexpected_nondefault_tree_state",
                f"Blank baseline requires tree_state.{field_name} to be empty.",
            )
    if "override_carrier_node_ids" in payload:
        override_carrier_node_ids = _require_identifier_list(
            payload["override_carrier_node_ids"],
            "tree_state.override_carrier_node_ids",
            "blank_state_missing_surface",
        )
        if override_carrier_node_ids:
            raise PoBHeadlessHostContractError(
                "unexpected_nondefault_tree_state",
                "Blank baseline requires tree_state.override_carrier_node_ids to be empty.",
            )

    return {
        "state_kind": "default",
        "active_spec_id": _require_non_empty_string(
            payload["active_spec_id"],
            "tree_state.active_spec_id",
            "blank_state_missing_surface",
        ),
        "class_id": _require_optional_string(payload["class_id"], "tree_state.class_id", "blank_state_missing_surface"),
        "ascendancy_id": _require_optional_string(
            payload["ascendancy_id"],
            "tree_state.ascendancy_id",
            "blank_state_missing_surface",
        ),
        "secondary_ascendancy_id": _require_optional_string(
            payload["secondary_ascendancy_id"],
            "tree_state.secondary_ascendancy_id",
            "blank_state_missing_surface",
        ),
        "default_root_state_present": True,
        "engine_default_node_ids": engine_default_node_ids,
        "user_allocated_node_ids": [],
        "keystone_node_ids": [],
        "mastery_effect_ids": [],
        "cluster_jewel_socket_ids": [],
        "socketed_jewel_node_ids": [],
        "anoint_allocations": [],
    }


def _canonicalize_skills_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    payload = _require_mapping(raw, "skills_state", "blank_state_missing_surface")
    payload.setdefault("state_kind", "empty")
    _ensure_exact_keys(
        payload,
        allowed_keys={
            "state_kind",
            "active_skill_set_id",
            "socket_group_count",
            "socket_groups",
            "main_socket_group_id",
            "main_active_skill_id",
        },
        field_name="skills_state",
        failure_state="blank_state_missing_surface",
    )
    state_kind = payload.get("state_kind")
    if state_kind is not None and _require_non_empty_string(state_kind, "skills_state.state_kind", "blank_state_missing_surface") != "empty":
        raise PoBHeadlessHostContractError(
            "unexpected_nonempty_skills_state",
            "Blank baseline requires skills_state.state_kind to remain empty.",
        )

    socket_groups = _require_list(payload["socket_groups"], "skills_state.socket_groups", "blank_state_missing_surface")
    if socket_groups:
        raise PoBHeadlessHostContractError(
            "unexpected_nonempty_skills_state",
            "Blank baseline requires skills_state.socket_groups to be empty.",
        )

    socket_group_count = _require_int(
        payload["socket_group_count"],
        "skills_state.socket_group_count",
        "blank_state_missing_surface",
    )
    if socket_group_count != 0:
        raise PoBHeadlessHostContractError(
            "unexpected_nonempty_skills_state",
            "Blank baseline requires skills_state.socket_group_count to be 0.",
        )
    if payload["main_socket_group_id"] is not None or payload["main_active_skill_id"] is not None:
        raise PoBHeadlessHostContractError(
            "unexpected_nonempty_skills_state",
            "Blank baseline requires main skill selectors to remain null.",
        )

    return {
        "state_kind": "empty",
        "active_skill_set_id": _require_non_empty_string(
            payload["active_skill_set_id"],
            "skills_state.active_skill_set_id",
            "blank_state_missing_surface",
        ),
        "socket_group_count": 0,
        "socket_groups": [],
        "main_socket_group_id": None,
        "main_active_skill_id": None,
    }


def _canonicalize_config_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    payload = _require_mapping(raw, "config_state", "blank_state_missing_surface")
    payload.setdefault("state_kind", "default")
    allowed_keys = {
        "state_kind",
        "active_config_set_id",
        "enabled_conditions",
        "custom_values",
        "notes",
        "bandit",
        "pantheon_major",
        "pantheon_minor",
        "engine_default_fields",
    }
    observed_keys = set(payload)
    extra_keys = sorted(observed_keys - allowed_keys)
    missing_keys = allowed_keys - observed_keys
    if extra_keys:
        raise PoBHeadlessHostContractError(
            "blank_state_ambiguous",
            f"config_state includes unsupported keys: {', '.join(extra_keys)}.",
        )
    missing_non_default_keys = sorted(missing_keys - {"engine_default_fields", "state_kind"})
    if missing_non_default_keys:
        raise PoBHeadlessHostContractError(
            "blank_state_missing_surface",
            f"config_state is missing required keys: {', '.join(missing_non_default_keys)}.",
        )
    if "engine_default_fields" not in payload:
        raise PoBHeadlessHostContractError(
            "blank_state_ambiguous",
            "Blank baseline must record config_state.engine_default_fields explicitly.",
        )
    state_kind = payload.get("state_kind")
    if state_kind is not None and _require_non_empty_string(state_kind, "config_state.state_kind", "blank_state_missing_surface") != "default":
        raise PoBHeadlessHostContractError(
            "unexpected_nondefault_config_state",
            "Blank baseline requires config_state.state_kind to remain default.",
        )

    enabled_conditions = _require_string_list(
        payload["enabled_conditions"],
        "config_state.enabled_conditions",
        "blank_state_missing_surface",
    )
    if enabled_conditions:
        raise PoBHeadlessHostContractError(
            "unexpected_nondefault_config_state",
            "Blank baseline requires config_state.enabled_conditions to be empty.",
        )

    custom_values = _require_mapping(payload["custom_values"], "config_state.custom_values", "blank_state_missing_surface")
    if custom_values:
        raise PoBHeadlessHostContractError(
            "unexpected_nondefault_config_state",
            "Blank baseline requires config_state.custom_values to be empty.",
        )
    if payload["notes"] is not None:
        raise PoBHeadlessHostContractError(
            "unexpected_nondefault_config_state",
            "Blank baseline requires config_state.notes to remain null.",
        )

    actual_defaults = {
        "bandit": _require_optional_string(payload["bandit"], "config_state.bandit", "blank_state_missing_surface"),
        "pantheon_major": _require_optional_string(
            payload["pantheon_major"],
            "config_state.pantheon_major",
            "blank_state_missing_surface",
        ),
        "pantheon_minor": _require_optional_string(
            payload["pantheon_minor"],
            "config_state.pantheon_minor",
            "blank_state_missing_surface",
        ),
    }
    engine_default_fields = _require_mapping(
        payload["engine_default_fields"],
        "config_state.engine_default_fields",
        "blank_state_ambiguous",
    )
    unknown_engine_defaults = sorted(set(engine_default_fields) - set(_CONFIG_DEFAULT_FIELDS))
    if unknown_engine_defaults:
        raise PoBHeadlessHostContractError(
            "blank_state_ambiguous",
            "config_state.engine_default_fields includes unsupported keys: "
            + ", ".join(unknown_engine_defaults),
        )
    for field_name, observed_value in actual_defaults.items():
        if field_name in engine_default_fields and engine_default_fields[field_name] != observed_value:
            raise PoBHeadlessHostContractError(
                "blank_state_ambiguous",
                f"config_state.engine_default_fields.{field_name} must match the observed config value.",
            )
        if observed_value is not None and field_name not in engine_default_fields:
            raise PoBHeadlessHostContractError(
                "blank_state_ambiguous",
                f"config_state.{field_name} is non-null and must be recorded explicitly in engine_default_fields.",
            )

    return {
        "state_kind": "default",
        "active_config_set_id": _require_non_empty_string(
            payload["active_config_set_id"],
            "config_state.active_config_set_id",
            "blank_state_missing_surface",
        ),
        "enabled_conditions": [],
        "custom_values": {},
        "notes": None,
        "bandit": actual_defaults["bandit"],
        "pantheon_major": actual_defaults["pantheon_major"],
        "pantheon_minor": actual_defaults["pantheon_minor"],
        "engine_default_fields": {key: engine_default_fields[key] for key in _CONFIG_DEFAULT_FIELDS if key in engine_default_fields},
    }


def _canonicalize_identity_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    payload = _require_mapping(raw, "identity_state", "blank_state_missing_surface")
    payload.setdefault("state_kind", "default")
    _ensure_exact_keys(
        payload,
        allowed_keys={
            "state_kind",
            "level",
            "character_level_auto_mode",
            "active_spec_id",
            "class_id",
            "ascendancy_id",
            "secondary_ascendancy_id",
        },
        field_name="identity_state",
        failure_state="blank_state_missing_surface",
    )
    state_kind = payload.get("state_kind")
    if (
        state_kind is not None
        and _require_non_empty_string(
            state_kind,
            "identity_state.state_kind",
            "blank_state_missing_surface",
        )
        != "default"
    ):
        raise PoBHeadlessHostContractError(
            "unexpected_nondefault_identity_state",
            "Blank baseline requires identity_state.state_kind to remain default.",
        )

    level = _require_int(payload["level"], "identity_state.level", "blank_state_missing_surface")
    if level != _BLANK_IDENTITY_LEVEL:
        raise PoBHeadlessHostContractError(
            "unexpected_nondefault_identity_state",
            f"Blank baseline requires identity_state.level to remain {_BLANK_IDENTITY_LEVEL}.",
        )
    character_level_auto_mode = _require_bool(
        payload["character_level_auto_mode"],
        "identity_state.character_level_auto_mode",
        "blank_state_missing_surface",
    )
    if character_level_auto_mode != _BLANK_IDENTITY_CHARACTER_LEVEL_AUTO_MODE:
        raise PoBHeadlessHostContractError(
            "unexpected_nondefault_identity_state",
            "Blank baseline requires identity_state.character_level_auto_mode to remain true.",
        )

    active_spec_id = _require_non_empty_string(
        payload["active_spec_id"],
        "identity_state.active_spec_id",
        "blank_state_missing_surface",
    )
    if active_spec_id != _BLANK_IDENTITY_ACTIVE_SPEC_ID:
        raise PoBHeadlessHostContractError(
            "unexpected_nondefault_identity_state",
            f"Blank baseline requires identity_state.active_spec_id to remain {_BLANK_IDENTITY_ACTIVE_SPEC_ID}.",
        )
    class_id = _require_optional_string(
        payload["class_id"],
        "identity_state.class_id",
        "blank_state_missing_surface",
    )
    if class_id != _BLANK_IDENTITY_CLASS_ID:
        raise PoBHeadlessHostContractError(
            "unexpected_nondefault_identity_state",
            f"Blank baseline requires identity_state.class_id to remain {_BLANK_IDENTITY_CLASS_ID}.",
        )
    ascendancy_id = _require_optional_string(
        payload["ascendancy_id"],
        "identity_state.ascendancy_id",
        "blank_state_missing_surface",
    )
    secondary_ascendancy_id = _require_optional_string(
        payload["secondary_ascendancy_id"],
        "identity_state.secondary_ascendancy_id",
        "blank_state_missing_surface",
    )
    if ascendancy_id is not None or secondary_ascendancy_id is not None:
        raise PoBHeadlessHostContractError(
            "unexpected_nondefault_identity_state",
            "Blank baseline requires identity_state ascendancies to remain null.",
        )

    return {
        "state_kind": "default",
        "level": _BLANK_IDENTITY_LEVEL,
        "character_level_auto_mode": _BLANK_IDENTITY_CHARACTER_LEVEL_AUTO_MODE,
        "active_spec_id": _BLANK_IDENTITY_ACTIVE_SPEC_ID,
        "class_id": _BLANK_IDENTITY_CLASS_ID,
        "ascendancy_id": None,
        "secondary_ascendancy_id": None,
    }


def _canonicalize_blank_readback(
    raw: Mapping[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any] | None,
]:
    payload = _require_mapping(raw, "blank_readback", "blank_state_missing_surface")
    required_keys = {"gear_slots", "tree_state", "skills_state", "config_state"}
    allowed_keys = {*required_keys, "identity_state"}
    observed_keys = set(payload)
    missing = sorted(required_keys - observed_keys)
    extra = sorted(observed_keys - allowed_keys)
    if missing:
        raise PoBHeadlessHostContractError(
            "blank_state_missing_surface",
            f"blank_readback is missing required keys: {', '.join(missing)}.",
        )
    if extra:
        raise PoBHeadlessHostContractError(
            "blank_state_ambiguous",
            f"blank_readback includes unsupported keys: {', '.join(extra)}.",
        )
    return (
        _canonicalize_gear_slots(payload["gear_slots"]),
        _canonicalize_tree_state(payload["tree_state"]),
        _canonicalize_skills_state(payload["skills_state"]),
        _canonicalize_config_state(payload["config_state"]),
        _canonicalize_identity_state(payload["identity_state"]) if "identity_state" in payload else None,
    )


@dataclass(frozen=True, slots=True)
class PoBBlankBaselineObservation:
    """Structured machine-readable blank-baseline observation for the proof slice."""

    pob_run_id: str
    session_role: str
    process_instance_id: str
    session_receipt_locator: Path
    observation_id: str
    observed_at: str
    gear_slots: dict[str, Any]
    tree_state: dict[str, Any]
    skills_state: dict[str, Any]
    config_state: dict[str, Any]
    identity_state: dict[str, Any] | None
    surface_classification: dict[str, Any]
    state_hash: str
    proof_scope: str = HEADLESS_PROOF_SLICE
    blank_build_created: bool = True
    blank_state_valid: bool = True
    allowed_next_action: str = BLANK_ALLOWED_NEXT_ACTION

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "supported_path": HEADLESS_PROOF_BLANK_STATE_SUPPORTED_PATH,
            "proof_kind": BLANK_BASELINE_PROOF_KIND,
            "proof_scope": self.proof_scope,
            "pob_run_id": self.pob_run_id,
            "session_role": self.session_role,
            "process_instance_id": self.process_instance_id,
            "session_receipt_locator": _path_string(self.session_receipt_locator),
            "observation_id": self.observation_id,
            "observed_at": self.observed_at,
            "blank_build_created": self.blank_build_created,
            "gear_slots": self.gear_slots,
            "tree_state": self.tree_state,
            "skills_state": self.skills_state,
            "config_state": self.config_state,
            "surface_classification": self.surface_classification,
            "state_hash": self.state_hash,
            "blank_state_valid": self.blank_state_valid,
            "allowed_next_action": self.allowed_next_action,
        }
        if self.identity_state is not None:
            payload["identity_state"] = self.identity_state
        return payload


@dataclass(frozen=True, slots=True)
class PoBBlankBaselineVerificationResult:
    """Durable wrapper-owned blank-baseline verification result."""

    observation: PoBBlankBaselineObservation
    observation_path: Path
    recompute_event: dict[str, Any]
    recompute_event_index: int
    recorded_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = self.observation.to_dict()
        payload["observation_locator"] = _path_string(self.observation_path)
        payload["wrapper_owned_verification"] = {
            "verified": True,
            "recorded_at": self.recorded_at,
            "recorded_in_session_receipt": True,
            "session_receipt_locator": _path_string(self.observation.session_receipt_locator),
            "recompute_event_index": self.recompute_event_index,
            "recompute_event": dict(self.recompute_event),
        }
        return payload


def verify_blank_baseline(
    run: PoBHeadlessProofRun,
    handle: PoBHeadlessSessionHandle,
    *,
    create_blank_build: BlankBuildCreator,
    read_blank_state: BlankStateReader,
    observed_at: str | None = None,
    recomputed_at: str | None = None,
) -> PoBBlankBaselineVerificationResult:
    """Create a blank build, read it back, and persist structured blank-state proof."""

    if not isinstance(handle, PoBHeadlessSessionHandle):
        raise PoBHeadlessHostContractError("invalid_request", "handle must be a PoBHeadlessSessionHandle.")
    tracked_handle = run.sessions.get(handle.session_role)
    if tracked_handle is None or tracked_handle.process_instance_id != handle.process_instance_id:
        raise PoBHeadlessHostContractError("unknown_session", f"Session is not tracked by run {run.request.pob_run_id}.")
    if tracked_handle.session_role != "normal":
        raise PoBHeadlessHostContractError(
            "blank_session_role_forbidden",
            "Blank baseline can only be recorded for the normal session.",
        )
    if tracked_handle.receipt.receipt_state != "launch_recorded" or tracked_handle.receipt.os_pid is None:
        raise PoBHeadlessHostContractError(
            "session_not_live",
            "Blank baseline requires a launched normal session.",
        )
    if tracked_handle.receipt.blank_state_verified:
        raise PoBHeadlessHostContractError(
            "blank_state_already_recorded",
            "Blank baseline is already recorded for this session.",
        )

    observation_path = blank_baseline_observation_path(run)
    if observation_path.exists():
        raise PoBHeadlessHostContractError(
            "blank_state_already_recorded",
            f"Blank baseline artifact already exists: {observation_path}",
        )

    try:
        create_blank_build(tracked_handle)
    except PoBHeadlessHostContractError:
        raise
    except Exception as exc:  # pragma: no cover - direct wrapper failures stay narrow
        raise PoBHeadlessHostContractError(
            "blank_build_creation_failed",
            f"Wrapper-owned blank build creation failed: {exc}",
        ) from exc

    try:
        raw_observation = read_blank_state(tracked_handle)
    except PoBHeadlessHostContractError:
        raise
    except Exception as exc:  # pragma: no cover - direct wrapper failures stay narrow
        raise PoBHeadlessHostContractError(
            "blank_state_readback_failed",
            f"Wrapper-owned blank read-back failed: {exc}",
        ) from exc

    gear_slots, tree_state, skills_state, config_state, identity_state = _canonicalize_blank_readback(raw_observation)
    state_payload = {
        "gear_slots": gear_slots,
        "tree_state": tree_state,
        "skills_state": skills_state,
        "config_state": config_state,
    }
    if identity_state is not None:
        state_payload["identity_state"] = identity_state
    state_hash = _canonical_state_hash(state_payload)
    observation_id = f"blank.{tracked_handle.process_instance_id}.{state_hash[:12]}"
    observed_timestamp = observed_at or utc_now_iso()
    recorded_timestamp = recomputed_at or observed_timestamp
    recompute_event_index = len(tracked_handle.receipt.recompute_events)
    surface_classification = {
        "gear_slots": gear_slots["state_kind"],
        "tree_state": tree_state["state_kind"],
        "skills_state": skills_state["state_kind"],
        "config_state": config_state["state_kind"],
        "non_boots_slots_empty": True,
        "boots_slot_empty": True,
        "engine_defaults_explicit": True,
    }
    if identity_state is not None:
        surface_classification["identity_state"] = identity_state["state_kind"]
    observation = PoBBlankBaselineObservation(
        pob_run_id=tracked_handle.pob_run_id,
        session_role=tracked_handle.session_role,
        process_instance_id=tracked_handle.process_instance_id,
        session_receipt_locator=tracked_handle.session_receipt_path,
        observation_id=observation_id,
        observed_at=observed_timestamp,
        gear_slots=gear_slots,
        tree_state=tree_state,
        skills_state=skills_state,
        config_state=config_state,
        identity_state=identity_state,
        surface_classification=surface_classification,
        state_hash=state_hash,
    )
    recompute_event = {
        "event_kind": BLANK_RECOMPUTE_EVENT_KIND,
        "proof_scope": HEADLESS_PROOF_SLICE,
        "recorded_at": recorded_timestamp,
        "observation_id": observation_id,
        "observation_locator": _path_string(observation_path),
        "state_hash": state_hash,
        "authoritative_read_back_present": True,
        "surface_classification": surface_classification,
    }
    result = PoBBlankBaselineVerificationResult(
        observation=observation,
        observation_path=observation_path,
        recompute_event=recompute_event,
        recompute_event_index=recompute_event_index,
        recorded_at=recorded_timestamp,
    )
    write_json(observation_path, result.to_dict())

    tracked_handle.receipt = replace(
        tracked_handle.receipt,
        blank_state_verified=True,
        recompute_events=(*tracked_handle.receipt.recompute_events, recompute_event),
    )
    run._write_session_receipt(tracked_handle)
    run._write_run_surfaces()
    return result


__all__ = [
    "BLANK_ALLOWED_NEXT_ACTION",
    "BLANK_BASELINE_FILENAME",
    "BLANK_BASELINE_PROOF_KIND",
    "BLANK_RECOMPUTE_EVENT_KIND",
    "BlankBuildCreator",
    "BlankStateReader",
    "EXPECTED_GEAR_SLOT_ORDER",
    "HEADLESS_PROOF_BLANK_STATE_SUPPORTED_PATH",
    "PoBBlankBaselineObservation",
    "PoBBlankBaselineVerificationResult",
    "blank_baseline_observation_path",
    "verify_blank_baseline",
]
