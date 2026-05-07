"""Headless PoB proof surfaces for export, reopen, and unified state parity."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal
from xml.etree import ElementTree

from .artifacts import sha256_bytes, sha256_file, validate_token, write_json
from .host_runtime import (
    HEADLESS_PROOF_SLICE,
    ExportSurfaceKind,
    PoBHeadlessHostContractError,
    PoBHeadlessProofRun,
    PoBHeadlessReopenSource,
    PoBHeadlessSessionHandle,
)

_RECEIPT_STATE_TEARDOWN_SEALED = "teardown_sealed"
_ALLOWED_NEXT_REOPEN = "reopen_exported_artifact"
_ALLOWED_NEXT_VERIFY = "verify_same_state"
_SUPPORTED_EXPORT_SURFACE_KINDS: tuple[ExportSurfaceKind, ...] = ("pob_xml", "pob_string", "pob_import_bundle")
_SESSION_ROLES: tuple[Literal["normal", "reopen"], ...] = ("normal", "reopen")
_UNIFIED_STATE_CONTRACT_VERSION = "pob_unified_state_snapshot.v1"
_UNIFIED_STATE_DIFF_VERSION = "pob_unified_state_diff.v1"
_STATE_HASH_ALGORITHM = "sha256:canonical-json:pob-unified-state-snapshot.v1"
_PRE_R15_LEGACY_STATE_HASH_ALGORITHM = "sha256:canonical-json:pob-pre-r15-gear-slots-state.v1"
_STATE_SLICE_KEYS = ("items_state", "tree_state", "skills_state", "config_state")
_STATE_KIND_BY_SLICE = {
    "items_state": frozenset({"empty", "boots_only", "nondefault"}),
    "tree_state": frozenset({"default", "nondefault"}),
    "skills_state": frozenset({"empty", "nondefault"}),
    "config_state": frozenset({"default", "nondefault"}),
}
_UNSUPPORTED_STATE_MARKER_KEYS = frozenset(
    {
        "placeholder",
        "placeholder_heavy",
        "placeholder_only",
        "unsupported",
        "unsupported_surface",
        "upstream_visible_only",
    }
)
_UNSUPPORTED_STATE_MARKER_VALUES = frozenset(
    {
        "placeholder",
        "placeholder_heavy",
        "placeholder_only",
        "unsupported",
        "unsupported_surface",
        "upstream_visible_only",
    }
)


class PoBHeadlessProofExportContractError(PoBHeadlessHostContractError):
    """Raised when the export/reopen proof contract fails closed."""


def _fail(failure_state: str, message: str) -> None:
    raise PoBHeadlessProofExportContractError(failure_state, message)


def _require_non_empty_string(value: str, field_name: str, failure_state: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(failure_state, f"{field_name} must be a non-empty string.")
    return value.strip()


def _path_string(path: Path) -> str:
    return path.resolve(strict=False).as_posix()


def _load_json_object(path: Path, *, failure_state: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        _fail(failure_state, f"JSON surface is missing: {path}")
        raise AssertionError from exc
    except json.JSONDecodeError as exc:
        _fail(failure_state, f"JSON surface is not valid JSON: {path}")
        raise AssertionError from exc
    if not isinstance(payload, dict):
        _fail(failure_state, f"JSON surface must decode to an object: {path}")
    return payload


def _stable_json_bytes(payload: Any, *, field_name: str) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        _fail("invalid_state_observation", f"{field_name} must be JSON-serializable and finite.")
        raise AssertionError from exc


def _json_clone(payload: Any, *, field_name: str) -> Any:
    return json.loads(_stable_json_bytes(payload, field_name=field_name).decode("utf-8"))


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _validate_observation_id(observation_id: str) -> str:
    try:
        return validate_token(observation_id, "observation_id")
    except RuntimeError as exc:
        _fail("invalid_state_observation", str(exc))
        raise AssertionError from exc


def _validate_surface_kind(surface_kind: str) -> ExportSurfaceKind:
    normalized = _require_non_empty_string(surface_kind, "surface_kind", "invalid_ready_pob_import")
    if normalized not in _SUPPORTED_EXPORT_SURFACE_KINDS:
        _fail(
            "invalid_ready_pob_import",
            f"surface_kind must be one of {', '.join(sorted(_SUPPORTED_EXPORT_SURFACE_KINDS))}.",
        )
    return normalized  # type: ignore[return-value]


def _require_tracked_handle(
    run: PoBHeadlessProofRun,
    handle: PoBHeadlessSessionHandle,
    *,
    expected_role: Literal["normal", "reopen"],
) -> PoBHeadlessSessionHandle:
    if not isinstance(handle, PoBHeadlessSessionHandle):
        _fail("invalid_request", "handle must be a PoBHeadlessSessionHandle.")
    tracked_handle = run.sessions.get(expected_role)
    if tracked_handle is None or tracked_handle.process_instance_id != handle.process_instance_id:
        _fail("unknown_session", f"{expected_role} session is not tracked by run {run.request.pob_run_id}.")
    if tracked_handle.session_role != expected_role:
        _fail("unknown_session", f"Expected {expected_role} session handle.")
    return tracked_handle


def _require_sealed_session(handle: PoBHeadlessSessionHandle, *, failure_state: str) -> None:
    if handle.receipt.receipt_state != _RECEIPT_STATE_TEARDOWN_SEALED:
        _fail(failure_state, f"{handle.session_role} session must be sealed before durable proof publication.")
    if handle.receipt.os_pid is None:
        _fail(failure_state, f"{handle.session_role} session must record a launched PID before proof publication.")


def _validate_exact_export_locator(
    run: PoBHeadlessProofRun,
    locator: Path | None,
) -> Path:
    candidate = run.layout.export_locator if locator is None else Path(locator)
    exact_export_locator = run.layout.export_locator.resolve(strict=False)
    candidate_locator = candidate.resolve(strict=False)
    if candidate_locator != exact_export_locator:
        if any(_is_within(candidate_locator, run.layout.session(role).temp_root) for role in _SESSION_ROLES):
            _fail(
                "hidden_temp_export_routing_forbidden",
                "Export and reopen must not route through sessions/*/temp instead of exports/.",
            )
        _fail(
            "non_exact_durable_path_routing_forbidden",
            "Export and reopen must use the exact canonical export locator under run_root/exports/.",
        )
    return run.layout.export_locator


def _normalize_export_payload(
    surface_kind: ExportSurfaceKind,
    export_payload: str | bytes | None,
) -> tuple[bytes, str | None]:
    if export_payload is None:
        if surface_kind == "pob_string":
            _fail(
                "missing_ready_pob_import_payload",
                "pob_string export requires the exact literal payload, not locator-only closure.",
            )
        _fail("missing_export_payload", "Export publication requires the exact artifact payload.")
    if isinstance(export_payload, bytes):
        if not export_payload:
            _fail("missing_export_payload", "Export payload bytes must not be empty.")
        if surface_kind == "pob_string":
            try:
                inline_payload = export_payload.decode("utf-8")
            except UnicodeDecodeError as exc:
                _fail(
                    "invalid_ready_pob_import_payload",
                    "pob_string payload must be valid UTF-8 text.",
                )
                raise AssertionError from exc
            if not inline_payload.strip():
                _fail("missing_ready_pob_import_payload", "pob_string payload must not be blank.")
            return export_payload, inline_payload
        return export_payload, None
    if not isinstance(export_payload, str):
        _fail("missing_export_payload", "Export payload must be text or bytes.")
    if not export_payload.strip():
        if surface_kind == "pob_string":
            _fail("missing_ready_pob_import_payload", "pob_string payload must not be blank.")
        _fail("missing_export_payload", "Export payload text must not be blank.")
    payload_bytes = export_payload.encode("utf-8")
    return payload_bytes, export_payload if surface_kind == "pob_string" else None


def _normalize_xml_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    return normalized or None


def _xml_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", maxsplit=1)[-1]
    return tag


def _xml_child_sort_key(element: ElementTree.Element) -> tuple[str, ...]:
    attributes = element.attrib
    return (
        _xml_local_name(element.tag),
        attributes.get("id", ""),
        attributes.get("name", ""),
        attributes.get("stat", ""),
        attributes.get("slot", ""),
        attributes.get("subsection", ""),
        attributes.get("classId", ""),
        attributes.get("itemId", ""),
        attributes.get("number", ""),
        attributes.get("string", ""),
        _normalize_xml_text(element.text) or "",
    )


def _normalized_xml_payload(element: ElementTree.Element) -> dict[str, Any]:
    children = sorted(list(element), key=_xml_child_sort_key)
    return {
        "tag": _xml_local_name(element.tag),
        "attrs": [[key, value] for key, value in sorted(element.attrib.items())],
        "text": _normalize_xml_text(element.text),
        "children": [_normalized_xml_payload(child) for child in children],
    }


def _export_payload_digest(surface_kind: ExportSurfaceKind, payload_bytes: bytes) -> str:
    if surface_kind != "pob_xml":
        return sha256_bytes(payload_bytes)
    try:
        root = ElementTree.fromstring(payload_bytes)
    except ElementTree.ParseError:
        return sha256_bytes(payload_bytes)
    normalized = _normalized_xml_payload(root)
    return sha256_bytes(_stable_json_bytes(normalized, field_name="canonical_export_payload"))


def _write_export_payload(locator: Path, payload_bytes: bytes) -> None:
    locator.parent.mkdir(parents=True, exist_ok=True)
    locator.write_bytes(payload_bytes)


def _merge_and_write_json(path: Path, updates: dict[str, Any]) -> dict[str, Any]:
    payload = _load_json_object(path, failure_state="missing_durable_surface")
    payload.update(updates)
    write_json(path, payload)
    return payload


def _json_path_join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _state_hash(value: Any, *, field_name: str) -> str:
    return sha256_bytes(_stable_json_bytes(value, field_name=field_name))


def _detect_unsupported_state_markers(
    value: Any,
    *,
    path: str,
    hits: list[str],
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered_key = key.lower()
            if lowered_key in _UNSUPPORTED_STATE_MARKER_KEYS:
                if isinstance(item, bool) and item:
                    hits.append(path or key)
                elif isinstance(item, str) and item.strip().lower() in _UNSUPPORTED_STATE_MARKER_VALUES:
                    hits.append(path or key)
            _detect_unsupported_state_markers(item, path=_json_path_join(path, key), hits=hits)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _detect_unsupported_state_markers(item, path=f"{path}[{index}]", hits=hits)
        return
    if isinstance(value, str) and value.strip().lower() in _UNSUPPORTED_STATE_MARKER_VALUES:
        hits.append(path)


def _flatten_state_paths(value: Any, *, path: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        flattened: dict[str, Any] = {}
        for key in sorted(value):
            child_path = _json_path_join(path, key)
            flattened.update(_flatten_state_paths(value[key], path=child_path))
        if not flattened:
            flattened[path] = {}
        return flattened
    if isinstance(value, list):
        flattened = {}
        for index, item in enumerate(value):
            flattened.update(_flatten_state_paths(item, path=f"{path}[{index}]"))
        if not flattened:
            flattened[path] = []
        return flattened
    return {path: value}


def _compare_json_values(left: Any, right: Any, *, path: str = "") -> list[str]:
    if type(left) is not type(right):  # noqa: E721
        return [path or "$"]
    if isinstance(left, dict):
        changed: list[str] = []
        left_keys = set(left)
        right_keys = set(right)
        for key in sorted(left_keys | right_keys):
            child_path = _json_path_join(path, key)
            if key not in left or key not in right:
                changed.append(child_path)
                continue
            changed.extend(_compare_json_values(left[key], right[key], path=child_path))
        return changed
    if isinstance(left, list):
        changed = []
        max_len = max(len(left), len(right))
        for index in range(max_len):
            child_path = f"{path}[{index}]"
            if index >= len(left) or index >= len(right):
                changed.append(child_path)
                continue
            changed.extend(_compare_json_values(left[index], right[index], path=child_path))
        return changed
    return [] if left == right else [path or "$"]


@dataclass(frozen=True, slots=True)
class PoBProofStateObservation:
    """Canonical machine-readable unified state observation used for export/reopen parity."""

    observation_id: str
    gear_slots: list[dict[str, Any]] | dict[str, Any]
    tree_state: dict[str, Any]
    skills_state: dict[str, Any]
    config_state: dict[str, Any]

    def __post_init__(self) -> None:
        _validate_observation_id(self.observation_id)
        if not isinstance(self.gear_slots, (list, dict)):
            _fail("invalid_state_observation", "gear_slots must be an object or a single-entry list.")
        if not isinstance(self.tree_state, dict):
            _fail("invalid_state_observation", "tree_state must be an object.")
        if not isinstance(self.skills_state, dict):
            _fail("invalid_state_observation", "skills_state must be an object.")
        if not isinstance(self.config_state, dict):
            _fail("invalid_state_observation", "config_state must be an object.")

        cloned_gear = _json_clone(self.gear_slots, field_name="gear_slots")
        if isinstance(cloned_gear, list):
            if len(cloned_gear) != 1 or not isinstance(cloned_gear[0], dict):
                _fail(
                    "invalid_state_observation",
                    "gear_slots list input must carry exactly one repo-owned item-state object.",
                )
        elif not isinstance(cloned_gear, dict):
            _fail("invalid_state_observation", "gear_slots must canonicalize to an object.")
        object.__setattr__(self, "gear_slots", cloned_gear)
        object.__setattr__(self, "tree_state", _json_clone(self.tree_state, field_name="tree_state"))
        object.__setattr__(self, "skills_state", _json_clone(self.skills_state, field_name="skills_state"))
        object.__setattr__(self, "config_state", _json_clone(self.config_state, field_name="config_state"))
        self._validate_unified_state()

    def _validate_unified_state(self) -> None:
        for slice_name, state_kind in (
            ("items_state", self.items_state.get("state_kind")),
            ("tree_state", self.tree_state.get("state_kind")),
            ("skills_state", self.skills_state.get("state_kind")),
            ("config_state", self.config_state.get("state_kind")),
        ):
            if state_kind is None:
                continue
            if not isinstance(state_kind, str):
                _fail("invalid_state_observation", f"{slice_name}.state_kind must be a string when present.")
            allowed_kinds = _STATE_KIND_BY_SLICE[slice_name]
            if state_kind not in allowed_kinds:
                _fail(
                    "invalid_state_observation",
                    f"{slice_name}.state_kind must stay within the accepted repo-owned slice kinds: "
                    + ", ".join(sorted(allowed_kinds))
                    + ".",
                )

        unsupported_hits: list[str] = []
        _detect_unsupported_state_markers(self.to_unified_state(), path="", hits=unsupported_hits)
        if unsupported_hits:
            _fail(
                "invalid_state_observation",
                "Unified state snapshot must fail closed on unsupported or placeholder-heavy surfaces: "
                + ", ".join(sorted(filter(None, unsupported_hits))),
            )

    @property
    def contract_version(self) -> str:
        return _UNIFIED_STATE_CONTRACT_VERSION

    @property
    def hash_algorithm(self) -> str:
        return _STATE_HASH_ALGORITHM

    @property
    def items_state(self) -> dict[str, Any]:
        gear_slots = self.gear_slots
        if isinstance(gear_slots, list):
            return _json_clone(gear_slots[0], field_name="items_state")
        return _json_clone(gear_slots, field_name="items_state")

    @property
    def legacy_gear_slots(self) -> list[dict[str, Any]]:
        return [_json_clone(self.items_state, field_name="legacy_gear_slots")]

    def to_unified_state(self) -> dict[str, Any]:
        return {
            "items_state": self.items_state,
            "tree_state": _json_clone(self.tree_state, field_name="tree_state"),
            "skills_state": _json_clone(self.skills_state, field_name="skills_state"),
            "config_state": _json_clone(self.config_state, field_name="config_state"),
        }

    @property
    def slice_hashes(self) -> dict[str, str]:
        unified_state = self.to_unified_state()
        return {
            slice_name: _state_hash(unified_state[slice_name], field_name=slice_name)
            for slice_name in _STATE_SLICE_KEYS
        }

    @property
    def state_hash(self) -> str:
        return _state_hash(self._canonical_payload(), field_name="state_observation")

    @property
    def pre_r15_legacy_state_hash_algorithm(self) -> str:
        return _PRE_R15_LEGACY_STATE_HASH_ALGORITHM

    @property
    def pre_r15_legacy_state_hash(self) -> str:
        """Compatibility hash for packages materialized before the unified item slice existed."""
        return _state_hash(
            {
                "gear_slots": self.legacy_gear_slots,
                "tree_state": _json_clone(self.tree_state, field_name="tree_state"),
                "skills_state": _json_clone(self.skills_state, field_name="skills_state"),
                "config_state": _json_clone(self.config_state, field_name="config_state"),
            },
            field_name="pre_r15_legacy_state_observation",
        )

    def _canonical_payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "items_state": self.items_state,
            "tree_state": _json_clone(self.tree_state, field_name="tree_state"),
            "skills_state": _json_clone(self.skills_state, field_name="skills_state"),
            "config_state": _json_clone(self.config_state, field_name="config_state"),
        }

    def diff_against(self, other: "PoBProofStateObservation") -> "PoBUnifiedStateDiff":
        if not isinstance(other, PoBProofStateObservation):
            _fail("invalid_parity_observation", "diff target must be a PoBProofStateObservation.")
        return PoBUnifiedStateDiff.from_observations(left=self, right=other)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "contract_version": self.contract_version,
            "hash_algorithm": self.hash_algorithm,
            "gear_slots": self.legacy_gear_slots,
            "items_state": self.items_state,
            "tree_state": _json_clone(self.tree_state, field_name="tree_state"),
            "skills_state": _json_clone(self.skills_state, field_name="skills_state"),
            "config_state": _json_clone(self.config_state, field_name="config_state"),
            "slice_hashes": self.slice_hashes,
            "state_hash": self.state_hash,
        }


@dataclass(frozen=True, slots=True)
class PoBUnifiedStateDiff:
    """Machine-usable unified state diff with stable slice/hash semantics."""

    contract_version: str
    left_observation_id: str
    right_observation_id: str
    left_state_hash: str
    right_state_hash: str
    left_slice_hashes: dict[str, str]
    right_slice_hashes: dict[str, str]
    changed_slices: tuple[str, ...]
    changed_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty_string(self.contract_version, "contract_version", "invalid_parity_observation")
        _validate_observation_id(self.left_observation_id)
        _validate_observation_id(self.right_observation_id)
        _require_non_empty_string(self.left_state_hash, "left_state_hash", "invalid_parity_observation")
        _require_non_empty_string(self.right_state_hash, "right_state_hash", "invalid_parity_observation")
        for field_name, payload in (
            ("left_slice_hashes", self.left_slice_hashes),
            ("right_slice_hashes", self.right_slice_hashes),
        ):
            if not isinstance(payload, dict):
                _fail("invalid_parity_observation", f"{field_name} must be an object.")
            if set(payload) != set(_STATE_SLICE_KEYS):
                _fail(
                    "invalid_parity_observation",
                    f"{field_name} must cover exactly {', '.join(_STATE_SLICE_KEYS)}.",
                )
            for slice_name, digest in payload.items():
                _require_non_empty_string(digest, f"{field_name}.{slice_name}", "invalid_parity_observation")

    @classmethod
    def from_observations(
        cls,
        *,
        left: PoBProofStateObservation,
        right: PoBProofStateObservation,
    ) -> "PoBUnifiedStateDiff":
        left_state = left.to_unified_state()
        right_state = right.to_unified_state()
        changed_slices = tuple(
            slice_name for slice_name in _STATE_SLICE_KEYS if left_state[slice_name] != right_state[slice_name]
        )
        changed_paths: list[str] = []
        for slice_name in changed_slices:
            changed_paths.extend(
                _compare_json_values(
                    left_state[slice_name],
                    right_state[slice_name],
                    path=slice_name,
                )
            )
        if left.state_hash != right.state_hash and "state_hash" not in changed_paths:
            changed_paths.append("state_hash")
        return cls(
            contract_version=_UNIFIED_STATE_DIFF_VERSION,
            left_observation_id=left.observation_id,
            right_observation_id=right.observation_id,
            left_state_hash=left.state_hash,
            right_state_hash=right.state_hash,
            left_slice_hashes=left.slice_hashes,
            right_slice_hashes=right.slice_hashes,
            changed_slices=changed_slices,
            changed_paths=tuple(sorted(dict.fromkeys(changed_paths))),
        )

    @property
    def same_state(self) -> bool:
        return not self.changed_slices and not self.changed_paths and self.left_state_hash == self.right_state_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "left_observation_id": self.left_observation_id,
            "right_observation_id": self.right_observation_id,
            "left_state_hash": self.left_state_hash,
            "right_state_hash": self.right_state_hash,
            "left_slice_hashes": dict(self.left_slice_hashes),
            "right_slice_hashes": dict(self.right_slice_hashes),
            "changed_slices": list(self.changed_slices),
            "changed_paths": list(self.changed_paths),
            "same_state": self.same_state,
        }


@dataclass(frozen=True, slots=True)
class PoBPublishedReadyPoBImport:
    """Exact ready_pob_import surface published from the canonical export locator."""

    surface_kind: ExportSurfaceKind
    locator: str
    payload: str | None
    payload_hash: str
    pre_export_observation_id: str
    pre_export_state_hash: str

    def __post_init__(self) -> None:
        _validate_surface_kind(self.surface_kind)
        _require_non_empty_string(self.locator, "locator", "invalid_ready_pob_import")
        _require_non_empty_string(self.payload_hash, "payload_hash", "invalid_ready_pob_import")
        _validate_observation_id(self.pre_export_observation_id)
        _require_non_empty_string(
            self.pre_export_state_hash,
            "pre_export_state_hash",
            "invalid_ready_pob_import",
        )
        if self.surface_kind == "pob_string":
            _require_non_empty_string(
                "" if self.payload is None else self.payload,
                "payload",
                "missing_ready_pob_import_payload",
            )
        elif self.payload is not None:
            _fail(
                "invalid_ready_pob_import_payload",
                "Only pob_string may publish an inline ready_pob_import payload.",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_kind": self.surface_kind,
            "locator": self.locator,
            "payload": self.payload,
            "payload_hash": self.payload_hash,
            "pre_export_observation_id": self.pre_export_observation_id,
            "pre_export_state_hash": self.pre_export_state_hash,
        }


@dataclass(frozen=True, slots=True)
class PoBPublishedExportObservation:
    """Durable export observation linked to the pre-export canonical state."""

    observation_id: str
    ready_pob_import: PoBPublishedReadyPoBImport
    content_digest: str
    pre_export_observation: PoBProofStateObservation

    def __post_init__(self) -> None:
        _validate_observation_id(self.observation_id)
        _require_non_empty_string(self.content_digest, "content_digest", "invalid_ready_pob_import")

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "state_contract_version": self.pre_export_observation.contract_version,
            "ready_pob_import": self.ready_pob_import.to_dict(),
            "content_digest": self.content_digest,
            "pre_export_observation_id": self.pre_export_observation.observation_id,
            "pre_export_gear_slots": self.pre_export_observation.legacy_gear_slots,
            "pre_export_items_state": self.pre_export_observation.items_state,
            "pre_export_tree_state": _json_clone(self.pre_export_observation.tree_state, field_name="tree_state"),
            "pre_export_skills_state": _json_clone(
                self.pre_export_observation.skills_state,
                field_name="skills_state",
            ),
            "pre_export_config_state": _json_clone(
                self.pre_export_observation.config_state,
                field_name="config_state",
            ),
            "pre_export_unified_state": self.pre_export_observation.to_unified_state(),
            "slice_hashes": self.pre_export_observation.slice_hashes,
            "state_hash": self.pre_export_observation.state_hash,
            "allowed_next_action": _ALLOWED_NEXT_REOPEN,
        }


@dataclass(frozen=True, slots=True)
class PoBReopenReadbackObservation:
    """Durable clean-reopen read-back tied to the exact published export."""

    observation_id: str
    reopen_session_id: str
    reopen_source_locator: str
    reopen_source_hash: str
    artifact_digest_verified: bool
    clean_reopen_verified: bool
    post_reopen_observation: PoBProofStateObservation

    def __post_init__(self) -> None:
        _validate_observation_id(self.observation_id)
        _require_non_empty_string(self.reopen_session_id, "reopen_session_id", "invalid_reopen_observation")
        _require_non_empty_string(
            self.reopen_source_locator,
            "reopen_source_locator",
            "invalid_reopen_observation",
        )
        _require_non_empty_string(self.reopen_source_hash, "reopen_source_hash", "invalid_reopen_observation")
        if not self.artifact_digest_verified:
            _fail("invalid_reopen_observation", "artifact_digest_verified must be true for successful reopen proof.")
        if not self.clean_reopen_verified:
            _fail("invalid_reopen_observation", "clean_reopen_verified must be true for successful reopen proof.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "post_reopen_observation_id": self.post_reopen_observation.observation_id,
            "state_contract_version": self.post_reopen_observation.contract_version,
            "reopen_session_id": self.reopen_session_id,
            "reopen_source_locator": self.reopen_source_locator,
            "reopen_source_hash": self.reopen_source_hash,
            "artifact_digest_verified": self.artifact_digest_verified,
            "clean_reopen_verified": self.clean_reopen_verified,
            "gear_slots": self.post_reopen_observation.legacy_gear_slots,
            "items_state": self.post_reopen_observation.items_state,
            "tree_state": _json_clone(self.post_reopen_observation.tree_state, field_name="tree_state"),
            "skills_state": _json_clone(self.post_reopen_observation.skills_state, field_name="skills_state"),
            "config_state": _json_clone(self.post_reopen_observation.config_state, field_name="config_state"),
            "unified_state": self.post_reopen_observation.to_unified_state(),
            "slice_hashes": self.post_reopen_observation.slice_hashes,
            "state_hash": self.post_reopen_observation.state_hash,
            "allowed_next_action": _ALLOWED_NEXT_VERIFY,
        }


@dataclass(frozen=True, slots=True)
class PoBSameStateVerificationObservation:
    """Machine-readable parity result for pre-export vs post-reopen state."""

    observation_id: str
    pre_export_observation_id: str
    post_reopen_observation_id: str
    pre_export_state_hash: str
    post_reopen_state_hash: str
    unified_state_diff: PoBUnifiedStateDiff
    mismatch_fields: tuple[str, ...]
    gear_slots_match: bool
    items_state_match: bool
    tree_state_match: bool
    skills_state_match: bool
    config_state_match: bool
    artifact_surface_match: bool

    def __post_init__(self) -> None:
        _validate_observation_id(self.observation_id)
        _validate_observation_id(self.pre_export_observation_id)
        _validate_observation_id(self.post_reopen_observation_id)
        if not isinstance(self.unified_state_diff, PoBUnifiedStateDiff):
            _fail("invalid_parity_observation", "unified_state_diff must be a PoBUnifiedStateDiff.")
        _require_non_empty_string(
            self.pre_export_state_hash,
            "pre_export_state_hash",
            "invalid_parity_observation",
        )
        _require_non_empty_string(
            self.post_reopen_state_hash,
            "post_reopen_state_hash",
            "invalid_parity_observation",
        )

    @property
    def parity_match(self) -> bool:
        return (
            not self.mismatch_fields
            and self.unified_state_diff.same_state
            and self.gear_slots_match
            and self.items_state_match
            and self.tree_state_match
            and self.skills_state_match
            and self.config_state_match
            and self.artifact_surface_match
            and self.pre_export_state_hash == self.post_reopen_state_hash
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "pre_export_observation_id": self.pre_export_observation_id,
            "post_reopen_observation_id": self.post_reopen_observation_id,
            "pre_export_state_hash": self.pre_export_state_hash,
            "post_reopen_state_hash": self.post_reopen_state_hash,
            "state_diff": self.unified_state_diff.to_dict(),
            "parity_match": self.parity_match,
            "mismatch_fields": list(self.mismatch_fields),
            "gear_slots_match": self.gear_slots_match,
            "items_state_match": self.items_state_match,
            "tree_state_match": self.tree_state_match,
            "skills_state_match": self.skills_state_match,
            "config_state_match": self.config_state_match,
            "artifact_surface_match": self.artifact_surface_match,
            "allowed_next_action": None,
        }


def _write_normal_receipt(
    normal_handle: PoBHeadlessSessionHandle,
    *,
    export_observation: PoBPublishedExportObservation,
) -> None:
    payload = normal_handle.receipt.to_dict()
    payload.update(
        {
            "export_observation_id": export_observation.observation_id,
            "pre_export_observation_id": export_observation.pre_export_observation.observation_id,
            "state_contract_version": export_observation.pre_export_observation.contract_version,
            "pre_export_slice_hashes": export_observation.pre_export_observation.slice_hashes,
            "pre_export_state_hash": export_observation.pre_export_observation.state_hash,
        }
    )
    write_json(normal_handle.session_receipt_path, payload)


def _write_reopen_receipt(
    reopen_handle: PoBHeadlessSessionHandle,
    *,
    reopen_observation: PoBReopenReadbackObservation,
    parity_observation: PoBSameStateVerificationObservation | None = None,
) -> None:
    payload = reopen_handle.receipt.to_dict()
    payload.update(
        {
            "reopen_observation_id": reopen_observation.observation_id,
            "post_reopen_observation_id": reopen_observation.post_reopen_observation.observation_id,
            "state_contract_version": reopen_observation.post_reopen_observation.contract_version,
            "post_reopen_slice_hashes": reopen_observation.post_reopen_observation.slice_hashes,
            "post_reopen_state_hash": reopen_observation.post_reopen_observation.state_hash,
            "artifact_digest_verified": reopen_observation.artifact_digest_verified,
            "clean_reopen_verified": reopen_observation.clean_reopen_verified,
        }
    )
    if parity_observation is not None:
        payload.update(
            {
                "parity_observation_id": parity_observation.observation_id,
                "pre_export_observation_id": parity_observation.pre_export_observation_id,
                "pre_export_state_hash": parity_observation.pre_export_state_hash,
                "post_reopen_state_hash": parity_observation.post_reopen_state_hash,
                "state_diff": parity_observation.unified_state_diff.to_dict(),
                "mismatch_fields": list(parity_observation.mismatch_fields),
            }
        )
    write_json(reopen_handle.session_receipt_path, payload)


def _update_run_manifest(
    run: PoBHeadlessProofRun,
    *,
    ready_pob_import: PoBPublishedReadyPoBImport,
) -> None:
    run_manifest = _load_json_object(
        run.layout.manifest_paths.run_manifest_path,
        failure_state="missing_durable_surface",
    )
    artifact_locator = run_manifest.setdefault("artifact_locator", {})
    artifact_locator["artifact_kind"] = ready_pob_import.surface_kind
    artifact_locator["locator"] = ready_pob_import.locator
    artifact_locator["payload_hash"] = ready_pob_import.payload_hash
    artifact_locator["pre_export_observation_id"] = ready_pob_import.pre_export_observation_id
    artifact_locator["pre_export_state_hash"] = ready_pob_import.pre_export_state_hash
    artifact_locator["state_contract_version"] = _UNIFIED_STATE_CONTRACT_VERSION
    if ready_pob_import.payload is not None:
        artifact_locator["payload"] = ready_pob_import.payload
    else:
        artifact_locator.pop("payload", None)
    write_json(run.layout.manifest_paths.run_manifest_path, run_manifest)


def _update_primary_proof_export(
    run: PoBHeadlessProofRun,
    *,
    export_observation: PoBPublishedExportObservation,
) -> None:
    primary_proof = _load_json_object(
        run.layout.manifest_paths.primary_proof_path,
        failure_state="missing_durable_surface",
    )
    primary_proof["final_export_assertion"] = {
        "status": "recorded",
        "state_contract_version": export_observation.pre_export_observation.contract_version,
        "export_locator": export_observation.ready_pob_import.locator,
        "export_payload_hash": export_observation.content_digest,
        "observation_id": export_observation.observation_id,
        "pre_export_observation_id": export_observation.pre_export_observation.observation_id,
        "pre_export_state_hash": export_observation.pre_export_observation.state_hash,
        "pre_export_slice_hashes": export_observation.pre_export_observation.slice_hashes,
        "ready_pob_import": export_observation.ready_pob_import.to_dict(),
    }
    primary_proof["export_locator"] = export_observation.ready_pob_import.locator
    primary_proof["export_payload_hash"] = export_observation.content_digest
    write_json(run.layout.manifest_paths.primary_proof_path, primary_proof)


def _update_primary_proof_parity(
    run: PoBHeadlessProofRun,
    *,
    reopen_handle: PoBHeadlessSessionHandle,
    parity_observation: PoBSameStateVerificationObservation,
) -> None:
    primary_proof = _load_json_object(
        run.layout.manifest_paths.primary_proof_path,
        failure_state="missing_durable_surface",
    )
    primary_proof["reopen_parity_assertion"] = {
        "status": "verified",
        "session_receipt_locator": _path_string(reopen_handle.session_receipt_path),
        **parity_observation.to_dict(),
    }
    write_json(run.layout.manifest_paths.primary_proof_path, primary_proof)


def _update_live_control_export(
    run: PoBHeadlessProofRun,
    *,
    export_observation: PoBPublishedExportObservation,
) -> None:
    live_control = _load_json_object(
        run.layout.manifest_paths.live_control_result_path,
        failure_state="missing_durable_surface",
    )
    live_control["normal_readback_summary"] = export_observation.to_dict()
    live_control["authoritative_output_boundary"] = {
        "surface_kind": export_observation.ready_pob_import.surface_kind,
        "locator": export_observation.ready_pob_import.locator,
        "payload_hash": export_observation.content_digest,
        "reopen_required": True,
        "state_contract_version": export_observation.pre_export_observation.contract_version,
        "pre_export_observation_id": export_observation.pre_export_observation.observation_id,
    }
    write_json(run.layout.manifest_paths.live_control_result_path, live_control)


def _update_live_control_reopen(
    run: PoBHeadlessProofRun,
    *,
    reopen_observation: PoBReopenReadbackObservation,
    parity_observation: PoBSameStateVerificationObservation | None = None,
) -> None:
    live_control = _load_json_object(
        run.layout.manifest_paths.live_control_result_path,
        failure_state="missing_durable_surface",
    )
    reopen_summary = reopen_observation.to_dict()
    if parity_observation is not None:
        reopen_summary["same_state_verification"] = parity_observation.to_dict()
    live_control["reopen_readback_summary"] = reopen_summary
    write_json(run.layout.manifest_paths.live_control_result_path, live_control)


def _update_handoff(
    run: PoBHeadlessProofRun,
    *,
    ready_pob_import: PoBPublishedReadyPoBImport,
    reopen_requirement_satisfied: bool,
) -> None:
    handoff = _load_json_object(
        run.layout.manifest_paths.next_run_handoff_path,
        failure_state="missing_durable_surface",
    )
    handoff["ready_pob_import"] = ready_pob_import.to_dict()
    handoff["state_contract_version"] = _UNIFIED_STATE_CONTRACT_VERSION
    handoff["reopen_requirement_satisfied"] = reopen_requirement_satisfied
    write_json(run.layout.manifest_paths.next_run_handoff_path, handoff)


def publish_ready_pob_import(
    run: PoBHeadlessProofRun,
    normal_handle: PoBHeadlessSessionHandle,
    *,
    pre_export_observation: PoBProofStateObservation | None,
    export_observation_id: str,
    export_payload: str | bytes | None,
    published_locator: Path | None = None,
) -> PoBPublishedExportObservation:
    """Save and publish one exact ready_pob_import surface from the pre-export state."""

    if pre_export_observation is None:
        _fail(
            "locator_only_closure_forbidden",
            "Export closure requires the exact pre-export canonical observation, not only a locator.",
        )
    tracked_normal = _require_tracked_handle(run, normal_handle, expected_role="normal")
    _require_sealed_session(tracked_normal, failure_state="session_not_sealed")
    export_locator = _validate_exact_export_locator(run, published_locator)
    payload_bytes, inline_payload = _normalize_export_payload(run.request.export_surface_kind, export_payload)
    _write_export_payload(export_locator, payload_bytes)
    content_digest = _export_payload_digest(run.request.export_surface_kind, payload_bytes)
    export_observation = PoBPublishedExportObservation(
        observation_id=export_observation_id,
        ready_pob_import=PoBPublishedReadyPoBImport(
            surface_kind=run.request.export_surface_kind,
            locator=_path_string(export_locator),
            payload=inline_payload,
            payload_hash=content_digest,
            pre_export_observation_id=pre_export_observation.observation_id,
            pre_export_state_hash=pre_export_observation.state_hash,
        ),
        content_digest=content_digest,
        pre_export_observation=pre_export_observation,
    )
    tracked_normal.receipt = replace(tracked_normal.receipt, export_payload_hash=content_digest)
    _write_normal_receipt(tracked_normal, export_observation=export_observation)
    _update_run_manifest(run, ready_pob_import=export_observation.ready_pob_import)
    _update_primary_proof_export(run, export_observation=export_observation)
    _update_live_control_export(run, export_observation=export_observation)
    _update_handoff(
        run,
        ready_pob_import=export_observation.ready_pob_import,
        reopen_requirement_satisfied=False,
    )
    return export_observation


def _validate_clean_reopen_boundary(
    run: PoBHeadlessProofRun,
    *,
    normal_handle: PoBHeadlessSessionHandle,
    reopen_handle: PoBHeadlessSessionHandle,
    export_observation: PoBPublishedExportObservation,
) -> None:
    if reopen_handle.process_instance_id == normal_handle.process_instance_id:
        _fail(
            "non_clean_reopen_forbidden",
            "Reopen must happen in a distinct session/process boundary, not in the normal session.",
        )
    if normal_handle.os_pid is not None and reopen_handle.os_pid is not None and normal_handle.os_pid == reopen_handle.os_pid:
        _fail(
            "non_clean_reopen_forbidden",
            "Reopen must not reuse the same OS process as the normal session.",
        )
    if not reopen_handle.receipt.fresh_process or not reopen_handle.receipt.fresh_workspace:
        _fail(
            "non_clean_reopen_forbidden",
            "Reopen proof requires a fresh process and fresh workspace boundary.",
        )
    if reopen_handle.reopen_source is None:
        _fail(
            "non_clean_reopen_forbidden",
            "Reopen proof requires an exact durable reopen source.",
        )
    expected_locator = Path(export_observation.ready_pob_import.locator).resolve(strict=False)
    candidate_locator = reopen_handle.reopen_source.export_locator.resolve(strict=False)
    if candidate_locator != expected_locator:
        if any(_is_within(candidate_locator, run.layout.session(role).temp_root) for role in _SESSION_ROLES):
            _fail(
                "hidden_temp_export_routing_forbidden",
                "Reopen must not route through sessions/*/temp instead of the published export.",
            )
        _fail(
            "non_exact_durable_path_routing_forbidden",
            "Reopen must use the exact canonical export locator that was published for ready_pob_import.",
        )


def record_reopen_readback(
    run: PoBHeadlessProofRun,
    normal_handle: PoBHeadlessSessionHandle,
    reopen_handle: PoBHeadlessSessionHandle,
    *,
    export_observation: PoBPublishedExportObservation,
    post_reopen_observation: PoBProofStateObservation | None,
    reopen_observation_id: str,
) -> PoBReopenReadbackObservation:
    """Record one clean reopen read-back from the exact published export surface."""

    if post_reopen_observation is None:
        _fail(
            "locator_only_closure_forbidden",
            "Reopen closure requires canonical post-reopen read-back, not only a locator or prose note.",
        )
    if reopen_handle.session_role != "reopen":
        _fail(
            "non_clean_reopen_forbidden",
            "Reopen proof requires the explicit reopen session, not reuse of the normal-session handle.",
        )
    tracked_normal = _require_tracked_handle(run, normal_handle, expected_role="normal")
    tracked_reopen = _require_tracked_handle(run, reopen_handle, expected_role="reopen")
    _require_sealed_session(tracked_normal, failure_state="session_not_sealed")
    _require_sealed_session(tracked_reopen, failure_state="session_not_sealed")
    _validate_clean_reopen_boundary(
        run,
        normal_handle=tracked_normal,
        reopen_handle=tracked_reopen,
        export_observation=export_observation,
    )
    export_locator = _validate_exact_export_locator(run, Path(export_observation.ready_pob_import.locator))
    actual_digest = _export_payload_digest(run.request.export_surface_kind, export_locator.read_bytes())
    if actual_digest != export_observation.content_digest:
        _fail(
            "artifact_digest_mismatch",
            "Reopen source digest does not match the published export payload hash.",
        )
    tracked_reopen.reopen_source = PoBHeadlessReopenSource(
        export_locator=export_locator,
        export_payload_hash=actual_digest,
    )
    tracked_reopen.receipt = replace(
        tracked_reopen.receipt,
        reopen_source_hash=actual_digest,
        parity_verified=False,
    )
    _update_run_manifest(run, ready_pob_import=export_observation.ready_pob_import)
    _update_primary_proof_export(run, export_observation=export_observation)
    _update_live_control_export(run, export_observation=export_observation)
    _update_handoff(
        run,
        ready_pob_import=export_observation.ready_pob_import,
        reopen_requirement_satisfied=False,
    )
    reopen_observation = PoBReopenReadbackObservation(
        observation_id=reopen_observation_id,
        reopen_session_id=tracked_reopen.process_instance_id,
        reopen_source_locator=_path_string(export_locator),
        reopen_source_hash=actual_digest,
        artifact_digest_verified=True,
        clean_reopen_verified=True,
        post_reopen_observation=post_reopen_observation,
    )
    _write_reopen_receipt(tracked_reopen, reopen_observation=reopen_observation)
    _update_live_control_reopen(run, reopen_observation=reopen_observation)
    return reopen_observation


def verify_same_state(
    run: PoBHeadlessProofRun,
    reopen_handle: PoBHeadlessSessionHandle,
    *,
    export_observation: PoBPublishedExportObservation,
    reopen_observation: PoBReopenReadbackObservation,
    parity_observation_id: str,
    comparison_scope: str = HEADLESS_PROOF_SLICE,
) -> PoBSameStateVerificationObservation:
    """Verify machine-readable parity between pre-export and post-reopen state."""

    if comparison_scope != HEADLESS_PROOF_SLICE:
        _fail(
            "invalid_comparison_scope",
            f"comparison_scope must stay {HEADLESS_PROOF_SLICE} for the accepted headless proof slice.",
        )
    tracked_reopen = _require_tracked_handle(run, reopen_handle, expected_role="reopen")
    _require_sealed_session(tracked_reopen, failure_state="session_not_sealed")

    pre_export = export_observation.pre_export_observation
    post_reopen = reopen_observation.post_reopen_observation
    unified_state_diff = pre_export.diff_against(post_reopen)

    gear_slots_match = pre_export.legacy_gear_slots == post_reopen.legacy_gear_slots
    items_state_match = pre_export.items_state == post_reopen.items_state
    tree_state_match = pre_export.tree_state == post_reopen.tree_state
    skills_state_match = pre_export.skills_state == post_reopen.skills_state
    config_state_match = pre_export.config_state == post_reopen.config_state
    artifact_surface_match = (
        reopen_observation.artifact_digest_verified
        and reopen_observation.clean_reopen_verified
        and reopen_observation.reopen_source_locator == export_observation.ready_pob_import.locator
        and reopen_observation.reopen_source_hash == export_observation.content_digest
    )
    mismatch_fields: list[str] = []
    if not items_state_match:
        mismatch_fields.append("items_state")
    if not tree_state_match:
        mismatch_fields.append("tree_state")
    if not skills_state_match:
        mismatch_fields.append("skills_state")
    if not config_state_match:
        mismatch_fields.append("config_state")
    if not unified_state_diff.same_state:
        mismatch_fields.append("state_hash")
    if not artifact_surface_match:
        mismatch_fields.append("artifact_surface")
    if mismatch_fields:
        _fail(
            "broken_parity_evidence",
            "Same-state verification requires exact machine-readable parity, mismatches: "
            + ", ".join(mismatch_fields)
            + ". Changed paths: "
            + ", ".join(unified_state_diff.changed_paths or ("<none>",)),
        )

    parity_observation = PoBSameStateVerificationObservation(
        observation_id=parity_observation_id,
        pre_export_observation_id=pre_export.observation_id,
        post_reopen_observation_id=post_reopen.observation_id,
        pre_export_state_hash=pre_export.state_hash,
        post_reopen_state_hash=post_reopen.state_hash,
        unified_state_diff=unified_state_diff,
        mismatch_fields=(),
        gear_slots_match=True,
        items_state_match=True,
        tree_state_match=True,
        skills_state_match=True,
        config_state_match=True,
        artifact_surface_match=True,
    )
    tracked_reopen.receipt = replace(
        tracked_reopen.receipt,
        reopen_source_hash=export_observation.content_digest,
        parity_verified=True,
    )
    _write_reopen_receipt(
        tracked_reopen,
        reopen_observation=reopen_observation,
        parity_observation=parity_observation,
    )
    _update_primary_proof_parity(
        run,
        reopen_handle=tracked_reopen,
        parity_observation=parity_observation,
    )
    _update_live_control_reopen(
        run,
        reopen_observation=reopen_observation,
        parity_observation=parity_observation,
    )
    _update_handoff(
        run,
        ready_pob_import=export_observation.ready_pob_import,
        reopen_requirement_satisfied=True,
    )
    return parity_observation


__all__ = [
    "PoBHeadlessProofExportContractError",
    "PoBProofStateObservation",
    "PoBUnifiedStateDiff",
    "PoBPublishedReadyPoBImport",
    "PoBPublishedExportObservation",
    "PoBReopenReadbackObservation",
    "PoBSameStateVerificationObservation",
    "publish_ready_pob_import",
    "record_reopen_readback",
    "verify_same_state",
]
