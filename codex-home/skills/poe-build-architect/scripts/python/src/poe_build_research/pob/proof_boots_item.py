"""Minimal headless PoB proof helpers for the boots-only item mutation slice."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

from .artifacts import sha256_bytes, write_json
from .host_runtime import HEADLESS_PROOF_SLICE, PoBHeadlessHostContractError, PoBHeadlessProofRun, PoBHeadlessSessionHandle
from .proof_blank_state import (
    BLANK_ALLOWED_NEXT_ACTION,
    EXPECTED_GEAR_SLOT_ORDER,
    PoBBlankBaselineObservation,
    PoBBlankBaselineVerificationResult,
    _canonicalize_config_state,
    _canonicalize_skills_state,
    _canonicalize_tree_state,
)
from .release_manager import utc_now_iso

PREPARED_BOOTS_ITEM_SUPPORTED_PATH = "pob_headless_proof_prepared_boots_item_v1"
PREPARED_BOOTS_ITEM_PROOF_KIND = "pob_headless_prepared_boots_item"
PREPARED_BOOTS_ITEM_FILENAME = "prepared-boots-item-observation.json"
PREPARED_BOOTS_ITEM_EVENT_KIND = "prepare_boots_item_recorded"
PREPARED_BOOTS_ALLOWED_NEXT_ACTION = "equip_boots_item"

EQUIPPED_BOOTS_STATE_SUPPORTED_PATH = "pob_headless_proof_equipped_boots_state_v1"
EQUIPPED_BOOTS_STATE_PROOF_KIND = "pob_headless_equipped_boots_state"
EQUIPPED_BOOTS_STATE_FILENAME = "equipped-boots-state-observation.json"
EQUIPPED_BOOTS_RECOMPUTE_EVENT_KIND = "equip_boots_item_recompute"
EQUIPPED_BOOTS_ALLOWED_NEXT_ACTION = "export_build_artifact"

EXPECTED_BOOTS_SLOT = "Boots"
EXPECTED_RARITY = "Rare"
EXPECTED_TYPE_LABEL = "Boots"
EXPECTED_EXPLICIT_AFFIX = "30% increased Movement Speed"
_ITEM_ALLOWED_KEYS = {
    "rarity",
    "slot",
    "type_label",
    "base_type",
    "explicit_affixes",
    "implicit_affixes",
    "crafted",
    "enchanted",
    "fractured",
    "veiled",
    "influences",
    "corrupted",
    "sockets",
    "links",
}

PreparedItemSourceKind = Literal["raw_item_text", "normalized_item_payload"]
BootsItemEquipper = Callable[[PoBHeadlessSessionHandle, str, Mapping[str, Any]], None]
BuildStateReader = Callable[[PoBHeadlessSessionHandle], Mapping[str, Any]]


def _path_string(path: Path) -> str:
    return path.resolve(strict=False).as_posix()


def _stable_json_bytes(payload: Any, *, field_name: str, failure_state: str) -> bytes:
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PoBHeadlessHostContractError(failure_state, f"{field_name} must be JSON-serializable.") from exc


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


def _require_string_list(value: Any, field_name: str, failure_state: str) -> list[str]:
    items = _require_list(value, field_name, failure_state)
    return [_require_non_empty_string(item, f"{field_name}[{index}]", failure_state) for index, item in enumerate(items)]


def _ensure_exact_keys(
    payload: Mapping[str, Any],
    *,
    allowed_keys: set[str],
    field_name: str,
    missing_failure_state: str,
    extra_failure_state: str,
) -> None:
    observed_keys = set(payload)
    missing = sorted(allowed_keys - observed_keys)
    extra = sorted(observed_keys - allowed_keys)
    if missing:
        raise PoBHeadlessHostContractError(
            missing_failure_state,
            f"{field_name} is missing required keys: {', '.join(missing)}.",
        )
    if extra:
        raise PoBHeadlessHostContractError(
            extra_failure_state,
            f"{field_name} includes unsupported keys: {', '.join(extra)}.",
        )


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def _canonical_slot(value: Any, *, field_name: str, failure_state: str) -> str:
    normalized = _normalize_whitespace(_require_non_empty_string(value, field_name, failure_state))
    if normalized.casefold() != EXPECTED_BOOTS_SLOT.casefold():
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name} must normalize to {EXPECTED_BOOTS_SLOT}.",
        )
    return EXPECTED_BOOTS_SLOT


def _canonical_rarity(value: Any, *, field_name: str, failure_state: str) -> str:
    normalized = _normalize_whitespace(_require_non_empty_string(value, field_name, failure_state))
    if normalized.casefold() != EXPECTED_RARITY.casefold():
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name} must normalize to {EXPECTED_RARITY}.",
        )
    return EXPECTED_RARITY


def _canonical_affix(value: Any, *, field_name: str, failure_state: str) -> str:
    normalized = _normalize_whitespace(_require_non_empty_string(value, field_name, failure_state))
    if normalized != EXPECTED_EXPLICIT_AFFIX:
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name} must be exactly {EXPECTED_EXPLICIT_AFFIX}.",
        )
    return EXPECTED_EXPLICIT_AFFIX


def _canonical_boots_base_type(value: Any, *, field_name: str, failure_state: str) -> str:
    normalized = _normalize_whitespace(_require_non_empty_string(value, field_name, failure_state))
    if EXPECTED_BOOTS_SLOT.casefold() not in normalized.casefold():
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name} must stay within the Boots base-type family.",
        )
    return normalized


def _canonicalize_proof_item_payload(
    payload: Mapping[str, Any],
    *,
    field_name: str,
    failure_state: str,
    allow_runtime_base_details: bool = False,
) -> dict[str, Any]:
    item = _require_mapping(payload, field_name, failure_state)
    extra_keys = sorted(set(item) - _ITEM_ALLOWED_KEYS)
    if extra_keys:
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name} includes unsupported logical state: {', '.join(extra_keys)}.",
        )

    required_keys = {
        "rarity",
        "slot",
        "explicit_affixes",
        "implicit_affixes",
        "crafted",
        "enchanted",
        "fractured",
        "veiled",
        "influences",
        "corrupted",
        "sockets",
        "links",
    }
    missing_keys = sorted(required_keys - set(item))
    if missing_keys:
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name} is missing required keys: {', '.join(missing_keys)}.",
        )
    if "type_label" not in item and "base_type" not in item:
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name} must include type_label or base_type.",
        )

    type_values: list[str] = []
    if "type_label" in item:
        type_values.append(_canonical_slot(item["type_label"], field_name=f"{field_name}.type_label", failure_state=failure_state))
    if "base_type" in item:
        _canonical_boots_base_type(item["base_type"], field_name=f"{field_name}.base_type", failure_state=failure_state)
        type_values.append(EXPECTED_TYPE_LABEL)
    if len(set(type_values)) > 1:
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name}.type_label and {field_name}.base_type must match when both are provided.",
        )

    explicit_affixes = _require_string_list(item["explicit_affixes"], f"{field_name}.explicit_affixes", failure_state)
    if len(explicit_affixes) != 1:
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name}.explicit_affixes must contain exactly one affix.",
        )
    explicit_affixes = [
        _canonical_affix(explicit_affixes[0], field_name=f"{field_name}.explicit_affixes[0]", failure_state=failure_state)
    ]

    implicit_affixes = _require_string_list(item["implicit_affixes"], f"{field_name}.implicit_affixes", failure_state)
    if implicit_affixes:
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name}.implicit_affixes must stay empty for the proof item.",
        )

    influences = _require_string_list(item["influences"], f"{field_name}.influences", failure_state)
    if influences:
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name}.influences must stay empty for the proof item.",
        )

    sockets = _require_list(item["sockets"], f"{field_name}.sockets", failure_state)
    if sockets and not allow_runtime_base_details:
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name}.sockets must stay empty for the proof item.",
        )

    links = _require_int(item["links"], f"{field_name}.links", failure_state)
    if links != 0 and not allow_runtime_base_details:
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name}.links must stay 0 for the proof item.",
        )

    for flag_name in ("crafted", "enchanted", "fractured", "veiled", "corrupted"):
        if _require_bool(item[flag_name], f"{field_name}.{flag_name}", failure_state):
            raise PoBHeadlessHostContractError(
                failure_state,
                f"{field_name}.{flag_name} must stay false for the proof item.",
            )

    return {
        "rarity": _canonical_rarity(item["rarity"], field_name=f"{field_name}.rarity", failure_state=failure_state),
        "slot": _canonical_slot(item["slot"], field_name=f"{field_name}.slot", failure_state=failure_state),
        "type_label": EXPECTED_TYPE_LABEL,
        "explicit_affixes": explicit_affixes,
        "implicit_affixes": [],
        "crafted": False,
        "enchanted": False,
        "fractured": False,
        "veiled": False,
        "influences": [],
        "corrupted": False,
        "sockets": [],
        "links": 0,
    }


def _canonicalize_raw_item_text(raw_item_text: Any) -> tuple[dict[str, Any], str]:
    failure_state = "invalid_boots_item"
    raw_text = _require_non_empty_string(raw_item_text, "raw_item_text", failure_state)
    lines = [_normalize_whitespace(line.strip()) for line in raw_text.splitlines() if line.strip()]
    if not lines or lines[0] != "Rarity: Rare":
        raise PoBHeadlessHostContractError(
            failure_state,
            "raw_item_text must start with the exact rarity line Rarity: Rare.",
        )

    remaining = lines[1:]
    if not remaining:
        raise PoBHeadlessHostContractError(failure_state, "raw_item_text must include a Boots type line and affix line.")

    type_index: int | None = None
    if remaining[0] == EXPECTED_TYPE_LABEL:
        type_index = 0
    elif len(remaining) >= 2 and remaining[1] == EXPECTED_TYPE_LABEL:
        type_index = 1
    if type_index is None:
        raise PoBHeadlessHostContractError(
            failure_state,
            "raw_item_text must include Boots as the only accepted type label.",
        )

    logical_tail = remaining[type_index + 1 :]
    if logical_tail and logical_tail[0] == "--------":
        logical_tail = logical_tail[1:]
    if logical_tail != [EXPECTED_EXPLICIT_AFFIX]:
        raise PoBHeadlessHostContractError(
            failure_state,
            "raw_item_text must normalize to exactly one explicit affix and no extra logical state.",
        )

    if type_index == 1:
        _require_non_empty_string(remaining[0], "raw_item_text.name_line", failure_state)

    return (
        {
            "rarity": EXPECTED_RARITY,
            "slot": EXPECTED_BOOTS_SLOT,
            "type_label": EXPECTED_TYPE_LABEL,
            "explicit_affixes": [EXPECTED_EXPLICIT_AFFIX],
            "implicit_affixes": [],
            "crafted": False,
            "enchanted": False,
            "fractured": False,
            "veiled": False,
            "influences": [],
            "corrupted": False,
            "sockets": [],
            "links": 0,
        },
        raw_text,
    )


def _load_json_object(path: Path, *, failure_state: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PoBHeadlessHostContractError(failure_state, f"JSON surface is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PoBHeadlessHostContractError(failure_state, f"JSON surface is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise PoBHeadlessHostContractError(failure_state, f"JSON surface must decode to an object: {path}")
    return payload


def prepared_boots_item_observation_path(run: PoBHeadlessProofRun) -> Path:
    """Return the durable path for the prepared-item observation."""

    return run.layout.manifest_paths.primary_proof_path.parent / PREPARED_BOOTS_ITEM_FILENAME


def equipped_boots_state_observation_path(run: PoBHeadlessProofRun) -> Path:
    """Return the durable path for the equipped boots-only state observation."""

    return run.layout.manifest_paths.primary_proof_path.parent / EQUIPPED_BOOTS_STATE_FILENAME


@dataclass(frozen=True, slots=True)
class PoBPreparedBootsItemObservation:
    """Durable prepared-item observation for the boots-only proof slice."""

    pob_run_id: str
    session_role: str
    process_instance_id: str
    session_receipt_locator: Path
    observation_id: str
    observed_at: str
    source_kind: PreparedItemSourceKind
    source_digest: str
    prepared_item_ref: str
    normalized_item: dict[str, Any]
    item_hash: str
    proof_scope: str = HEADLESS_PROOF_SLICE
    build_state_mutated: bool = False
    allowed_next_action: str = PREPARED_BOOTS_ALLOWED_NEXT_ACTION

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported_path": PREPARED_BOOTS_ITEM_SUPPORTED_PATH,
            "proof_kind": PREPARED_BOOTS_ITEM_PROOF_KIND,
            "proof_scope": self.proof_scope,
            "pob_run_id": self.pob_run_id,
            "session_role": self.session_role,
            "process_instance_id": self.process_instance_id,
            "session_receipt_locator": _path_string(self.session_receipt_locator),
            "observation_id": self.observation_id,
            "observed_at": self.observed_at,
            "source_kind": self.source_kind,
            "source_digest": self.source_digest,
            "prepared_item_ref": self.prepared_item_ref,
            "normalized_item": self.normalized_item,
            "item_hash": self.item_hash,
            "build_state_mutated": self.build_state_mutated,
            "allowed_next_action": self.allowed_next_action,
        }


@dataclass(frozen=True, slots=True)
class PoBPreparedBootsItemVerificationResult:
    """Structured durable result for one prepared boots item observation."""

    observation: PoBPreparedBootsItemObservation
    observation_path: Path
    receipt_event: dict[str, Any]
    receipt_event_index: int
    recorded_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = self.observation.to_dict()
        payload["observation_locator"] = _path_string(self.observation_path)
        payload["wrapper_owned_verification"] = {
            "verified": True,
            "recorded_at": self.recorded_at,
            "recorded_in_session_receipt": True,
            "session_receipt_locator": _path_string(self.observation.session_receipt_locator),
            "receipt_event_index": self.receipt_event_index,
            "receipt_event": dict(self.receipt_event),
        }
        return payload


@dataclass(frozen=True, slots=True)
class PoBEquippedBootsStateObservation:
    """Durable equipped-state observation for the boots-only proof slice."""

    pob_run_id: str
    session_role: str
    process_instance_id: str
    session_receipt_locator: Path
    observation_id: str
    observed_at: str
    prepared_item_ref: str
    prepared_item_observation_id: str
    gear_slots: dict[str, Any]
    tree_state: dict[str, Any]
    skills_state: dict[str, Any]
    config_state: dict[str, Any]
    surface_classification: dict[str, Any]
    state_hash: str
    proof_scope: str = HEADLESS_PROOF_SLICE
    nonempty_slot_count: int = 1
    allowed_next_action: str = EQUIPPED_BOOTS_ALLOWED_NEXT_ACTION

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported_path": EQUIPPED_BOOTS_STATE_SUPPORTED_PATH,
            "proof_kind": EQUIPPED_BOOTS_STATE_PROOF_KIND,
            "proof_scope": self.proof_scope,
            "pob_run_id": self.pob_run_id,
            "session_role": self.session_role,
            "process_instance_id": self.process_instance_id,
            "session_receipt_locator": _path_string(self.session_receipt_locator),
            "observation_id": self.observation_id,
            "observed_at": self.observed_at,
            "prepared_item_ref": self.prepared_item_ref,
            "prepared_item_observation_id": self.prepared_item_observation_id,
            "gear_slots": self.gear_slots,
            "tree_state": self.tree_state,
            "skills_state": self.skills_state,
            "config_state": self.config_state,
            "surface_classification": self.surface_classification,
            "state_hash": self.state_hash,
            "nonempty_slot_count": self.nonempty_slot_count,
            "allowed_next_action": self.allowed_next_action,
        }


@dataclass(frozen=True, slots=True)
class PoBEquippedBootsItemVerificationResult:
    """Structured durable result for one equipped boots-only state observation."""

    observation: PoBEquippedBootsStateObservation
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


def _require_live_normal_handle(run: PoBHeadlessProofRun, handle: PoBHeadlessSessionHandle) -> PoBHeadlessSessionHandle:
    if not isinstance(handle, PoBHeadlessSessionHandle):
        raise PoBHeadlessHostContractError("invalid_request", "handle must be a PoBHeadlessSessionHandle.")
    tracked_handle = run.sessions.get(handle.session_role)
    if tracked_handle is None or tracked_handle.process_instance_id != handle.process_instance_id:
        raise PoBHeadlessHostContractError("unknown_session", f"Session is not tracked by run {run.request.pob_run_id}.")
    if tracked_handle.session_role != "normal":
        raise PoBHeadlessHostContractError(
            "invalid_request",
            "The boots-only mutation slice can only run in the normal session.",
        )
    if tracked_handle.receipt.receipt_state != "launch_recorded" or tracked_handle.receipt.os_pid is None:
        raise PoBHeadlessHostContractError(
            "session_not_live",
            "Boots-only mutation requires a launched normal session.",
        )
    return tracked_handle


def _extract_blank_baseline_observation(
    blank_baseline: PoBBlankBaselineObservation | PoBBlankBaselineVerificationResult,
) -> PoBBlankBaselineObservation:
    if isinstance(blank_baseline, PoBBlankBaselineVerificationResult):
        observation = blank_baseline.observation
    elif isinstance(blank_baseline, PoBBlankBaselineObservation):
        observation = blank_baseline
    else:
        raise PoBHeadlessHostContractError(
            "invalid_request",
            "blank_baseline must be a PoBBlankBaselineObservation or PoBBlankBaselineVerificationResult.",
        )
    if not observation.blank_state_valid:
        raise PoBHeadlessHostContractError("blank_baseline_missing", "Blank baseline observation must be valid.")
    if observation.allowed_next_action != BLANK_ALLOWED_NEXT_ACTION:
        raise PoBHeadlessHostContractError(
            "blank_baseline_missing",
            "Blank baseline observation does not allow prepare_boots_item as the next action.",
        )
    return observation


def _extract_prepared_item_observation(
    prepared_item: PoBPreparedBootsItemObservation | PoBPreparedBootsItemVerificationResult,
) -> PoBPreparedBootsItemObservation:
    if isinstance(prepared_item, PoBPreparedBootsItemVerificationResult):
        observation = prepared_item.observation
    elif isinstance(prepared_item, PoBPreparedBootsItemObservation):
        observation = prepared_item
    else:
        raise PoBHeadlessHostContractError(
            "invalid_request",
            "prepared_item must be a PoBPreparedBootsItemObservation or PoBPreparedBootsItemVerificationResult.",
        )
    if observation.allowed_next_action != PREPARED_BOOTS_ALLOWED_NEXT_ACTION:
        raise PoBHeadlessHostContractError(
            "invalid_boots_item",
            "Prepared item observation does not allow equip_boots_item as the next action.",
        )
    return observation


def _canonicalize_blank_sensitive_state(
    raw_value: Any,
    *,
    field_name: str,
    blank_value: dict[str, Any],
) -> dict[str, Any]:
    try:
        if field_name == "tree_state":
            canonical = _canonicalize_tree_state(raw_value)
        elif field_name == "skills_state":
            canonical = _canonicalize_skills_state(raw_value)
        elif field_name == "config_state":
            canonical = _canonicalize_config_state(raw_value)
        else:  # pragma: no cover - closed set guarded by caller
            raise AssertionError(field_name)
    except PoBHeadlessHostContractError as exc:
        failure_state = "authoritative_readback_missing" if exc.failure_state == "blank_state_missing_surface" else "bulk_mutation_forbidden"
        raise PoBHeadlessHostContractError(
            failure_state,
            f"{field_name} is not acceptable for the boots-only proof slice: {exc}",
        ) from exc

    if canonical != blank_value:
        raise PoBHeadlessHostContractError(
            "bulk_mutation_forbidden",
            f"{field_name} changed relative to the blank baseline.",
        )
    return canonical


def _canonicalize_equipped_gear_slots(
    raw_value: Any,
    *,
    prepared_item: PoBPreparedBootsItemObservation,
    blank_gear_slots: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _require_mapping(raw_value, "gear_slots", "authoritative_readback_missing")
    payload.setdefault("state_kind", "boots_only")
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
        missing_failure_state="authoritative_readback_missing",
        extra_failure_state="bulk_mutation_forbidden",
    )
    state_kind = payload.get("state_kind")
    if state_kind is not None and _require_non_empty_string(state_kind, "gear_slots.state_kind", "authoritative_readback_missing") != "boots_only":
        raise PoBHeadlessHostContractError(
            "bulk_mutation_forbidden",
            "gear_slots.state_kind must remain boots_only after equipping the proof item.",
        )

    slot_order = _require_string_list(payload["slot_order"], "gear_slots.slot_order", "authoritative_readback_missing")
    if tuple(slot_order) != EXPECTED_GEAR_SLOT_ORDER:
        raise PoBHeadlessHostContractError(
            "bulk_mutation_forbidden",
            "gear_slots.slot_order must match the accepted deterministic slot order.",
        )

    extra_slots = _require_string_list(payload["extra_slots"], "gear_slots.extra_slots", "authoritative_readback_missing")
    expected_extra_slots = list(blank_gear_slots["extra_slots"])
    if extra_slots != expected_extra_slots:
        raise PoBHeadlessHostContractError(
            "bulk_mutation_forbidden",
            "gear_slots.extra_slots changed relative to the blank baseline.",
        )

    active_item_set_id = _require_non_empty_string(
        payload["active_item_set_id"],
        "gear_slots.active_item_set_id",
        "authoritative_readback_missing",
    )
    if active_item_set_id != blank_gear_slots["active_item_set_id"]:
        raise PoBHeadlessHostContractError(
            "bulk_mutation_forbidden",
            "gear_slots.active_item_set_id changed relative to the blank baseline.",
        )

    use_second_weapon_set = _require_bool(
        payload["use_second_weapon_set"],
        "gear_slots.use_second_weapon_set",
        "authoritative_readback_missing",
    )
    if use_second_weapon_set != blank_gear_slots["use_second_weapon_set"]:
        raise PoBHeadlessHostContractError(
            "bulk_mutation_forbidden",
            "gear_slots.use_second_weapon_set changed relative to the blank baseline.",
        )

    slots = _require_mapping(payload["slots"], "gear_slots.slots", "authoritative_readback_missing")
    expected_slot_names = [*slot_order, *extra_slots]
    missing_slots = [slot for slot in expected_slot_names if slot not in slots]
    unexpected_slots = sorted(set(slots) - set(expected_slot_names))
    if missing_slots:
        raise PoBHeadlessHostContractError(
            "authoritative_readback_missing",
            f"gear_slots.slots is missing required slots: {', '.join(missing_slots)}.",
        )
    if unexpected_slots:
        raise PoBHeadlessHostContractError(
            "bulk_mutation_forbidden",
            f"gear_slots.slots includes unsupported slots: {', '.join(unexpected_slots)}.",
        )

    normalized_slots: dict[str, dict[str, Any]] = {}
    for slot_name in expected_slot_names:
        slot_payload = _require_mapping(slots[slot_name], f"gear_slots.slots.{slot_name}", "authoritative_readback_missing")
        _ensure_exact_keys(
            slot_payload,
            allowed_keys={"occupied", "item"},
            field_name=f"gear_slots.slots.{slot_name}",
            missing_failure_state="authoritative_readback_missing",
            extra_failure_state="bulk_mutation_forbidden",
        )
        occupied = _require_bool(
            slot_payload["occupied"],
            f"gear_slots.slots.{slot_name}.occupied",
            "authoritative_readback_missing",
        )
        item = slot_payload["item"]
        if slot_name == EXPECTED_BOOTS_SLOT:
            if not occupied or item is None:
                raise PoBHeadlessHostContractError(
                    "invalid_target_slot",
                    "The prepared item must end up equipped in the Boots slot.",
                )
            normalized_item = _canonicalize_proof_item_payload(
                _require_mapping(item, f"gear_slots.slots.{slot_name}.item", "invalid_boots_item"),
                field_name=f"gear_slots.slots.{slot_name}.item",
                failure_state="invalid_boots_item",
                allow_runtime_base_details=True,
            )
            if normalized_item != prepared_item.normalized_item:
                raise PoBHeadlessHostContractError(
                    "invalid_boots_item",
                    "The equipped Boots item does not match the prepared item contract.",
                )
            normalized_slots[slot_name] = {"occupied": True, "item": normalized_item}
            continue
        if occupied or item is not None:
            raise PoBHeadlessHostContractError(
                "bulk_mutation_forbidden",
                f"Non-Boots slot {slot_name} must remain empty in the boots-only proof slice.",
            )
        normalized_slots[slot_name] = {"occupied": False, "item": None}

    nonempty_slot_count = _require_int(
        payload["nonempty_slot_count"],
        "gear_slots.nonempty_slot_count",
        "authoritative_readback_missing",
    )
    if nonempty_slot_count != 1:
        raise PoBHeadlessHostContractError(
            "bulk_mutation_forbidden",
            "gear_slots.nonempty_slot_count must be exactly 1 after equipping the proof item.",
        )

    return {
        "state_kind": "boots_only",
        "active_item_set_id": active_item_set_id,
        "use_second_weapon_set": use_second_weapon_set,
        "slot_order": slot_order,
        "extra_slots": extra_slots,
        "slots": normalized_slots,
        "nonempty_slot_count": 1,
    }


def _canonicalize_equipped_readback(
    raw_observation: Mapping[str, Any],
    *,
    blank_observation: PoBBlankBaselineObservation,
    prepared_item: PoBPreparedBootsItemObservation,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    payload = _require_mapping(raw_observation, "equip_readback", "authoritative_readback_missing")
    _ensure_exact_keys(
        payload,
        allowed_keys={"gear_slots", "tree_state", "skills_state", "config_state"},
        field_name="equip_readback",
        missing_failure_state="authoritative_readback_missing",
        extra_failure_state="bulk_mutation_forbidden",
    )

    return (
        _canonicalize_equipped_gear_slots(
            payload["gear_slots"],
            prepared_item=prepared_item,
            blank_gear_slots=blank_observation.gear_slots,
        ),
        _canonicalize_blank_sensitive_state(
            payload["tree_state"],
            field_name="tree_state",
            blank_value=blank_observation.tree_state,
        ),
        _canonicalize_blank_sensitive_state(
            payload["skills_state"],
            field_name="skills_state",
            blank_value=blank_observation.skills_state,
        ),
        _canonicalize_blank_sensitive_state(
            payload["config_state"],
            field_name="config_state",
            blank_value=blank_observation.config_state,
        ),
    )


def _update_primary_proof_prepare(
    run: PoBHeadlessProofRun,
    *,
    result: PoBPreparedBootsItemVerificationResult,
) -> None:
    primary_proof = _load_json_object(
        run.layout.manifest_paths.primary_proof_path,
        failure_state="missing_durable_surface",
    )
    primary_proof["prepared_boots_item_assertion"] = {
        "status": "verified",
        "observation_id": result.observation.observation_id,
        "prepared_item_ref": result.observation.prepared_item_ref,
        "item_hash": result.observation.item_hash,
        "observation_locator": _path_string(result.observation_path),
        "session_receipt_locator": _path_string(result.observation.session_receipt_locator),
    }
    write_json(run.layout.manifest_paths.primary_proof_path, primary_proof)


def _update_primary_proof_equip(
    run: PoBHeadlessProofRun,
    *,
    result: PoBEquippedBootsItemVerificationResult,
) -> None:
    primary_proof = _load_json_object(
        run.layout.manifest_paths.primary_proof_path,
        failure_state="missing_durable_surface",
    )
    primary_proof["equipped_boots_state_assertion"] = {
        "status": "verified",
        "observation_id": result.observation.observation_id,
        "prepared_item_ref": result.observation.prepared_item_ref,
        "prepared_item_observation_id": result.observation.prepared_item_observation_id,
        "state_hash": result.observation.state_hash,
        "observation_locator": _path_string(result.observation_path),
        "session_receipt_locator": _path_string(result.observation.session_receipt_locator),
    }
    write_json(run.layout.manifest_paths.primary_proof_path, primary_proof)


def _update_live_control_prepare(
    run: PoBHeadlessProofRun,
    *,
    result: PoBPreparedBootsItemVerificationResult,
) -> None:
    live_control = _load_json_object(
        run.layout.manifest_paths.live_control_result_path,
        failure_state="missing_durable_surface",
    )
    live_control["prepared_item_summary"] = result.to_dict()
    write_json(run.layout.manifest_paths.live_control_result_path, live_control)


def _update_live_control_equip(
    run: PoBHeadlessProofRun,
    *,
    result: PoBEquippedBootsItemVerificationResult,
) -> None:
    live_control = _load_json_object(
        run.layout.manifest_paths.live_control_result_path,
        failure_state="missing_durable_surface",
    )
    live_control["equipped_boots_readback_summary"] = result.to_dict()
    write_json(run.layout.manifest_paths.live_control_result_path, live_control)


def _restore_prepared_item_surfaces(run: PoBHeadlessProofRun) -> None:
    observation_path = prepared_boots_item_observation_path(run)
    if not observation_path.is_file():
        return
    prepared_payload = _load_json_object(observation_path, failure_state="missing_durable_surface")

    primary_proof = _load_json_object(
        run.layout.manifest_paths.primary_proof_path,
        failure_state="missing_durable_surface",
    )
    primary_proof["prepared_boots_item_assertion"] = {
        "status": "verified",
        "observation_id": prepared_payload["observation_id"],
        "prepared_item_ref": prepared_payload["prepared_item_ref"],
        "item_hash": prepared_payload["item_hash"],
        "observation_locator": prepared_payload["observation_locator"],
        "session_receipt_locator": prepared_payload["session_receipt_locator"],
    }
    write_json(run.layout.manifest_paths.primary_proof_path, primary_proof)

    live_control = _load_json_object(
        run.layout.manifest_paths.live_control_result_path,
        failure_state="missing_durable_surface",
    )
    live_control["prepared_item_summary"] = prepared_payload
    write_json(run.layout.manifest_paths.live_control_result_path, live_control)


def prepare_boots_item(
    run: PoBHeadlessProofRun,
    handle: PoBHeadlessSessionHandle,
    *,
    raw_item_text: str | None = None,
    normalized_item_payload: Mapping[str, Any] | None = None,
    observed_at: str | None = None,
    recorded_at: str | None = None,
) -> PoBPreparedBootsItemVerificationResult:
    """Normalize one accepted proof boots item and persist durable prepared-item evidence."""

    tracked_handle = _require_live_normal_handle(run, handle)
    if not tracked_handle.receipt.blank_state_verified:
        raise PoBHeadlessHostContractError(
            "blank_baseline_missing",
            "prepare_boots_item requires an accepted blank baseline first.",
        )
    blank_observation_locator = tracked_handle.run_layout.manifest_paths.primary_proof_path.parent / "blank-baseline-observation.json"
    if not blank_observation_locator.exists():
        raise PoBHeadlessHostContractError(
            "blank_baseline_missing",
            "prepare_boots_item requires the durable blank baseline observation artifact.",
        )
    if (raw_item_text is None) == (normalized_item_payload is None):
        raise PoBHeadlessHostContractError(
            "invalid_request",
            "prepare_boots_item requires exactly one of raw_item_text or normalized_item_payload.",
        )

    observation_path = prepared_boots_item_observation_path(run)
    if observation_path.exists():
        raise PoBHeadlessHostContractError(
            "prepared_item_already_recorded",
            f"Prepared boots item artifact already exists: {observation_path}",
        )

    if raw_item_text is not None:
        normalized_item, raw_text = _canonicalize_raw_item_text(raw_item_text)
        source_kind: PreparedItemSourceKind = "raw_item_text"
        source_digest = sha256_bytes(raw_text.encode("utf-8"))
    else:
        normalized_item = _canonicalize_proof_item_payload(
            normalized_item_payload or {},
            field_name="normalized_item_payload",
            failure_state="invalid_boots_item",
        )
        source_kind = "normalized_item_payload"
        source_digest = sha256_bytes(
            _stable_json_bytes(
                normalized_item_payload,
                field_name="normalized_item_payload",
                failure_state="invalid_boots_item",
            )
        )

    item_hash = sha256_bytes(
        _stable_json_bytes(normalized_item, field_name="normalized_item", failure_state="invalid_boots_item")
    )
    observation_id = f"boots.prepare.{tracked_handle.process_instance_id}.{item_hash[:12]}"
    prepared_item_ref = f"prepared-item.{tracked_handle.process_instance_id}.{item_hash[:12]}"
    observed_timestamp = observed_at or utc_now_iso()
    recorded_timestamp = recorded_at or observed_timestamp
    receipt_event_index = len(tracked_handle.receipt.recompute_events)
    observation = PoBPreparedBootsItemObservation(
        pob_run_id=tracked_handle.pob_run_id,
        session_role=tracked_handle.session_role,
        process_instance_id=tracked_handle.process_instance_id,
        session_receipt_locator=tracked_handle.session_receipt_path,
        observation_id=observation_id,
        observed_at=observed_timestamp,
        source_kind=source_kind,
        source_digest=source_digest,
        prepared_item_ref=prepared_item_ref,
        normalized_item=normalized_item,
        item_hash=item_hash,
    )
    receipt_event = {
        "event_kind": PREPARED_BOOTS_ITEM_EVENT_KIND,
        "proof_scope": HEADLESS_PROOF_SLICE,
        "recorded_at": recorded_timestamp,
        "observation_id": observation_id,
        "observation_locator": _path_string(observation_path),
        "prepared_item_ref": prepared_item_ref,
        "item_hash": item_hash,
        "build_state_mutated": False,
    }
    result = PoBPreparedBootsItemVerificationResult(
        observation=observation,
        observation_path=observation_path,
        receipt_event=receipt_event,
        receipt_event_index=receipt_event_index,
        recorded_at=recorded_timestamp,
    )
    write_json(observation_path, result.to_dict())

    tracked_handle.receipt = replace(
        tracked_handle.receipt,
        recompute_events=(*tracked_handle.receipt.recompute_events, receipt_event),
    )
    run._write_session_receipt(tracked_handle)
    run._write_run_surfaces()
    _update_primary_proof_prepare(run, result=result)
    _update_live_control_prepare(run, result=result)
    return result


def equip_boots_item(
    run: PoBHeadlessProofRun,
    handle: PoBHeadlessSessionHandle,
    *,
    prepared_item: PoBPreparedBootsItemObservation | PoBPreparedBootsItemVerificationResult,
    blank_baseline: PoBBlankBaselineObservation | PoBBlankBaselineVerificationResult,
    equip_item: BootsItemEquipper,
    read_build_state: BuildStateReader,
    observed_at: str | None = None,
    recomputed_at: str | None = None,
) -> PoBEquippedBootsItemVerificationResult:
    """Equip the accepted prepared boots item and persist authoritative boots-only state evidence."""

    tracked_handle = _require_live_normal_handle(run, handle)
    if not tracked_handle.receipt.blank_state_verified:
        raise PoBHeadlessHostContractError(
            "blank_baseline_missing",
            "equip_boots_item requires an accepted blank baseline first.",
        )
    blank_observation = _extract_blank_baseline_observation(blank_baseline)
    prepared_observation = _extract_prepared_item_observation(prepared_item)

    if blank_observation.pob_run_id != tracked_handle.pob_run_id or blank_observation.process_instance_id != tracked_handle.process_instance_id:
        raise PoBHeadlessHostContractError(
            "blank_baseline_missing",
            "Blank baseline observation must come from the same normal session.",
        )
    if prepared_observation.pob_run_id != tracked_handle.pob_run_id or prepared_observation.process_instance_id != tracked_handle.process_instance_id:
        raise PoBHeadlessHostContractError(
            "invalid_boots_item",
            "Prepared item observation must come from the same normal session.",
        )

    observation_path = equipped_boots_state_observation_path(run)
    if observation_path.exists():
        raise PoBHeadlessHostContractError(
            "equipped_boots_state_already_recorded",
            f"Equipped boots state artifact already exists: {observation_path}",
        )

    try:
        equip_item(tracked_handle, prepared_observation.prepared_item_ref, prepared_observation.normalized_item)
    except PoBHeadlessHostContractError:
        raise
    except Exception as exc:  # pragma: no cover - direct wrapper failures stay narrow
        raise PoBHeadlessHostContractError(
            "boots_item_equip_failed",
            f"Wrapper-owned equip callback failed: {exc}",
        ) from exc

    try:
        raw_observation = read_build_state(tracked_handle)
    except PoBHeadlessHostContractError:
        raise
    except Exception as exc:  # pragma: no cover - direct wrapper failures stay narrow
        raise PoBHeadlessHostContractError(
            "authoritative_readback_missing",
            f"Authoritative equip read-back failed: {exc}",
        ) from exc

    gear_slots, tree_state, skills_state, config_state = _canonicalize_equipped_readback(
        raw_observation,
        blank_observation=blank_observation,
        prepared_item=prepared_observation,
    )
    state_payload = {
        "gear_slots": gear_slots,
        "tree_state": tree_state,
        "skills_state": skills_state,
        "config_state": config_state,
    }
    state_hash = sha256_bytes(
        _stable_json_bytes(state_payload, field_name="equipped_boots_state", failure_state="invalid_state_observation")
    )
    observation_id = f"boots.equip.{tracked_handle.process_instance_id}.{state_hash[:12]}"
    observed_timestamp = observed_at or utc_now_iso()
    recorded_timestamp = recomputed_at or observed_timestamp
    recompute_event_index = len(tracked_handle.receipt.recompute_events)
    surface_classification = {
        "gear_slots": "boots_only",
        "tree_state": "default",
        "skills_state": "empty",
        "config_state": "default",
        "non_boots_slots_empty": True,
        "boots_slot_matches_prepared_item": True,
        "blank_baseline_parity": True,
    }
    observation = PoBEquippedBootsStateObservation(
        pob_run_id=tracked_handle.pob_run_id,
        session_role=tracked_handle.session_role,
        process_instance_id=tracked_handle.process_instance_id,
        session_receipt_locator=tracked_handle.session_receipt_path,
        observation_id=observation_id,
        observed_at=observed_timestamp,
        prepared_item_ref=prepared_observation.prepared_item_ref,
        prepared_item_observation_id=prepared_observation.observation_id,
        gear_slots=gear_slots,
        tree_state=tree_state,
        skills_state=skills_state,
        config_state=config_state,
        surface_classification=surface_classification,
        state_hash=state_hash,
    )
    recompute_event = {
        "event_kind": EQUIPPED_BOOTS_RECOMPUTE_EVENT_KIND,
        "proof_scope": HEADLESS_PROOF_SLICE,
        "recorded_at": recorded_timestamp,
        "observation_id": observation_id,
        "observation_locator": _path_string(observation_path),
        "prepared_item_ref": prepared_observation.prepared_item_ref,
        "state_hash": state_hash,
        "authoritative_read_back_present": True,
        "surface_classification": surface_classification,
        "nonempty_slot_count": 1,
    }
    result = PoBEquippedBootsItemVerificationResult(
        observation=observation,
        observation_path=observation_path,
        recompute_event=recompute_event,
        recompute_event_index=recompute_event_index,
        recorded_at=recorded_timestamp,
    )
    write_json(observation_path, result.to_dict())

    tracked_handle.receipt = replace(
        tracked_handle.receipt,
        recompute_events=(*tracked_handle.receipt.recompute_events, recompute_event),
    )
    run._write_session_receipt(tracked_handle)
    run._write_run_surfaces()
    _restore_prepared_item_surfaces(run)
    _update_primary_proof_equip(run, result=result)
    _update_live_control_equip(run, result=result)
    return result


__all__ = [
    "BootsItemEquipper",
    "BuildStateReader",
    "EQUIPPED_BOOTS_ALLOWED_NEXT_ACTION",
    "EQUIPPED_BOOTS_RECOMPUTE_EVENT_KIND",
    "EQUIPPED_BOOTS_STATE_FILENAME",
    "EQUIPPED_BOOTS_STATE_PROOF_KIND",
    "EQUIPPED_BOOTS_STATE_SUPPORTED_PATH",
    "EXPECTED_BOOTS_SLOT",
    "EXPECTED_EXPLICIT_AFFIX",
    "EXPECTED_RARITY",
    "EXPECTED_TYPE_LABEL",
    "PREPARED_BOOTS_ALLOWED_NEXT_ACTION",
    "PREPARED_BOOTS_ITEM_EVENT_KIND",
    "PREPARED_BOOTS_ITEM_FILENAME",
    "PREPARED_BOOTS_ITEM_PROOF_KIND",
    "PREPARED_BOOTS_ITEM_SUPPORTED_PATH",
    "PoBEquippedBootsItemVerificationResult",
    "PoBEquippedBootsStateObservation",
    "PoBPreparedBootsItemVerificationResult",
    "PoBPreparedBootsItemObservation",
    "PreparedItemSourceKind",
    "equip_boots_item",
    "equipped_boots_state_observation_path",
    "prepare_boots_item",
    "prepared_boots_item_observation_path",
]
