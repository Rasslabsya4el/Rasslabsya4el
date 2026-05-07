"""Thin replay-safe intake surface for external mechanic gap follow-up."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..pob.mechanic_coverage import load_mechanic_coverage_bundle

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_COMMITTED_MISSING_LIST_PATH = (
    PROJECT_ROOT / "src" / "poe_build_research" / "pob" / "mechanic_coverage_data" / "missing_list.json"
)
DEFAULT_SOURCE_PACK_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "data" / "mechanic_gap_source_pack.schema.json"
DEFAULT_SOURCE_PACK_FIXTURE_PATH = (
    PROJECT_ROOT / "tests" / "data" / "fixtures" / "mechanic_gap_intake" / "current_source_pack.json"
)

SCHEMA_VERSION = "1.0.0"
PACK_ID = "mechanic_gap_source_pack"
MISSING_LIST_CORPUS_ID = "pob_mechanic_coverage"
MISSING_LIST_FAMILY = "missing_list"
COMMITTED_MISSING_LIST_RELATIVE_PATH = "src/poe_build_research/pob/mechanic_coverage_data/missing_list.json"
EXPECTED_GAP_FAMILY_KEYS = ("nova", "quiver", "slam", "warstaff", "exposure", "orb")
EXPECTED_NEXT_STEP_SOURCES = ("wiki", "curated_notes")
LAYER_NAMES = ("delivery", "scaling", "enablement")
ALLOWED_SOURCE_FAMILIES = ("wiki", "secondary")
ALLOWED_SOURCE_KINDS = ("wiki_page", "patch_notes", "announcement", "forum_post")
ALLOWED_SURFACE_ROLES = ("default_wiki", "secondary_clarifier")


class MechanicGapIntakeContractError(RuntimeError):
    """Raised when the mechanic-gap source-pack contract is violated."""


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _coerce_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MechanicGapIntakeContractError(f"{field_name} must be an object.")
    return value


def _coerce_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise MechanicGapIntakeContractError(f"{field_name} must be an array.")
    return value


def _coerce_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MechanicGapIntakeContractError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _coerce_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise MechanicGapIntakeContractError(f"{field_name} must be a boolean.")
    return value


def _coerce_string_list(value: Any, field_name: str) -> list[str]:
    values = _coerce_list(value, field_name)
    return [_coerce_non_empty_string(item, f"{field_name}[{index}]") for index, item in enumerate(values)]


def _project_relative_path(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False)).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _load_missing_list_payload(path: Path) -> dict[str, Any]:
    if path.resolve(strict=False) == DEFAULT_COMMITTED_MISSING_LIST_PATH.resolve(strict=False):
        return load_mechanic_coverage_bundle("missing_list")
    return _load_json(path)


def _validate_gap_family_keys(group_keys: list[str], *, field_name: str) -> None:
    if tuple(group_keys) != EXPECTED_GAP_FAMILY_KEYS:
        raise MechanicGapIntakeContractError(
            f"{field_name} drifted from the current accepted gap families: {EXPECTED_GAP_FAMILY_KEYS!r}"
        )


def _validate_missing_list_bundle(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise MechanicGapIntakeContractError(
            f"Accepted missing-list schema_version must be {SCHEMA_VERSION!r}."
        )
    if payload.get("corpus_id") != MISSING_LIST_CORPUS_ID:
        raise MechanicGapIntakeContractError(
            f"Accepted missing-list corpus_id must be {MISSING_LIST_CORPUS_ID!r}."
        )
    if payload.get("family") != MISSING_LIST_FAMILY:
        raise MechanicGapIntakeContractError(
            f"Accepted missing-list family must be {MISSING_LIST_FAMILY!r}."
        )

    metadata = _coerce_mapping(payload.get("metadata"), "metadata")
    follow_up_sources = _coerce_string_list(metadata.get("follow_up_sources"), "metadata.follow_up_sources")
    if tuple(follow_up_sources) != EXPECTED_NEXT_STEP_SOURCES:
        raise MechanicGapIntakeContractError(
            f"Accepted missing-list follow_up_sources must be {EXPECTED_NEXT_STEP_SOURCES!r}."
        )

    raw_records = _coerce_list(payload.get("records"), "records")
    if payload.get("record_count") != len(raw_records):
        raise MechanicGapIntakeContractError("Accepted missing-list record_count must match records length.")

    records_by_key: dict[str, dict[str, Any]] = {}
    ordered_keys: list[str] = []
    for index, raw_record in enumerate(raw_records):
        record = dict(_coerce_mapping(raw_record, f"records[{index}]"))
        group_key = _coerce_non_empty_string(record.get("group_key"), f"records[{index}].group_key")
        if group_key in records_by_key:
            raise MechanicGapIntakeContractError(f"Accepted missing-list contains duplicate group_key {group_key!r}.")
        coverage_status = _coerce_non_empty_string(record.get("coverage_status"), f"records[{index}].coverage_status")
        if coverage_status == "covered":
            raise MechanicGapIntakeContractError("Accepted missing-list must not contain covered families.")
        if coverage_status not in {"partial", "gap"}:
            raise MechanicGapIntakeContractError(
                f"Accepted missing-list coverage_status must be 'partial' or 'gap', got {coverage_status!r}."
            )
        next_step_sources = _coerce_string_list(record.get("next_step_sources"), f"records[{index}].next_step_sources")
        if tuple(next_step_sources) != EXPECTED_NEXT_STEP_SOURCES:
            raise MechanicGapIntakeContractError(
                f"{group_key!r} must keep next_step_sources {EXPECTED_NEXT_STEP_SOURCES!r}."
            )
        ordered_keys.append(group_key)
        records_by_key[group_key] = record

    _validate_gap_family_keys(ordered_keys, field_name="Accepted missing-list group_key order")
    return records_by_key


def load_accepted_mechanic_gap_missing_list(
    missing_list_path: Path = DEFAULT_COMMITTED_MISSING_LIST_PATH,
) -> dict[str, Any]:
    """Load the accepted PoB-side missing-list surface for mechanic follow-up."""

    payload = _load_missing_list_payload(missing_list_path)
    _validate_missing_list_bundle(_coerce_mapping(payload, "missing_list"))
    return payload


def load_mechanic_gap_source_pack_schema(
    schema_path: Path = DEFAULT_SOURCE_PACK_SCHEMA_PATH,
) -> dict[str, Any]:
    """Load the schema that backs the mechanic-gap source pack fixture."""

    return _load_json(schema_path)


def _validate_source_entry(entry: Mapping[str, Any], *, field_name: str) -> str:
    entry_id = _coerce_non_empty_string(entry.get("entry_id"), f"{field_name}.entry_id")
    source_family = _coerce_non_empty_string(entry.get("source_family"), f"{field_name}.source_family")
    if source_family not in ALLOWED_SOURCE_FAMILIES:
        raise MechanicGapIntakeContractError(
            f"{field_name}.source_family must be one of {ALLOWED_SOURCE_FAMILIES!r}."
        )
    source_kind = _coerce_non_empty_string(entry.get("source_kind"), f"{field_name}.source_kind")
    if source_kind not in ALLOWED_SOURCE_KINDS:
        raise MechanicGapIntakeContractError(
            f"{field_name}.source_kind must be one of {ALLOWED_SOURCE_KINDS!r}."
        )
    _coerce_non_empty_string(entry.get("url"), f"{field_name}.url")
    _coerce_non_empty_string(entry.get("title"), f"{field_name}.title")
    _coerce_non_empty_string(entry.get("locator"), f"{field_name}.locator")

    raw_claims = _coerce_list(entry.get("normalized_claim_candidates"), f"{field_name}.normalized_claim_candidates")
    if not raw_claims:
        raise MechanicGapIntakeContractError(f"{field_name} must contain at least one normalized claim candidate.")
    for claim_index, raw_claim in enumerate(raw_claims):
        claim = _coerce_mapping(raw_claim, f"{field_name}.normalized_claim_candidates[{claim_index}]")
        _coerce_non_empty_string(claim.get("claim_id"), f"{field_name}.normalized_claim_candidates[{claim_index}].claim_id")
        _coerce_non_empty_string(claim.get("summary"), f"{field_name}.normalized_claim_candidates[{claim_index}].summary")
        _coerce_non_empty_string(
            claim.get("normalized_statement"),
            f"{field_name}.normalized_claim_candidates[{claim_index}].normalized_statement",
        )
        target_layers = _coerce_string_list(
            claim.get("target_layers"),
            f"{field_name}.normalized_claim_candidates[{claim_index}].target_layers",
        )
        if not target_layers:
            raise MechanicGapIntakeContractError(
                f"{field_name}.normalized_claim_candidates[{claim_index}].target_layers must not be empty."
            )
        unknown_layers = sorted(set(target_layers) - set(LAYER_NAMES))
        if unknown_layers:
            raise MechanicGapIntakeContractError(
                f"{field_name}.normalized_claim_candidates[{claim_index}] uses unknown layers: {unknown_layers!r}."
            )

    provenance = _coerce_mapping(entry.get("provenance"), f"{field_name}.provenance")
    _coerce_non_empty_string(provenance.get("captured_at"), f"{field_name}.provenance.captured_at")
    capture_mode = _coerce_non_empty_string(provenance.get("capture_mode"), f"{field_name}.provenance.capture_mode")
    if capture_mode != "manual_repo_tracked_review":
        raise MechanicGapIntakeContractError(
            f"{field_name}.provenance.capture_mode must be 'manual_repo_tracked_review'."
        )
    surface_role = _coerce_non_empty_string(provenance.get("surface_role"), f"{field_name}.provenance.surface_role")
    if surface_role not in ALLOWED_SURFACE_ROLES:
        raise MechanicGapIntakeContractError(
            f"{field_name}.provenance.surface_role must be one of {ALLOWED_SURFACE_ROLES!r}."
        )
    _coerce_non_empty_string(
        provenance.get("selection_reason"),
        f"{field_name}.provenance.selection_reason",
    )
    return source_family


def _validate_source_pack(
    source_pack: Mapping[str, Any],
    *,
    missing_list: Mapping[str, Any],
    missing_list_path: Path,
) -> None:
    if source_pack.get("schema_version") != SCHEMA_VERSION:
        raise MechanicGapIntakeContractError(f"Source pack schema_version must be {SCHEMA_VERSION!r}.")
    if source_pack.get("pack_id") != PACK_ID:
        raise MechanicGapIntakeContractError(f"Source pack pack_id must be {PACK_ID!r}.")
    pack_version = source_pack.get("pack_version")
    if isinstance(pack_version, bool) or not isinstance(pack_version, int) or pack_version < 1:
        raise MechanicGapIntakeContractError("Source pack pack_version must be an integer >= 1.")
    _coerce_non_empty_string(source_pack.get("description"), "description")

    input_missing_list = _coerce_mapping(source_pack.get("input_missing_list"), "input_missing_list")
    if input_missing_list.get("bundle_path") != COMMITTED_MISSING_LIST_RELATIVE_PATH:
        raise MechanicGapIntakeContractError(
            "input_missing_list.bundle_path must point at the accepted committed missing-list surface."
        )
    if input_missing_list.get("corpus_id") != MISSING_LIST_CORPUS_ID:
        raise MechanicGapIntakeContractError(
            f"input_missing_list.corpus_id must be {MISSING_LIST_CORPUS_ID!r}."
        )
    if input_missing_list.get("family") != MISSING_LIST_FAMILY:
        raise MechanicGapIntakeContractError(
            f"input_missing_list.family must be {MISSING_LIST_FAMILY!r}."
        )

    actual_missing_list_records = _validate_missing_list_bundle(missing_list)
    actual_group_keys = list(actual_missing_list_records)
    if input_missing_list.get("record_count") != len(actual_group_keys):
        raise MechanicGapIntakeContractError(
            "input_missing_list.record_count must match the accepted missing-list record count."
        )
    if input_missing_list.get("bundle_sha256") != _sha256_file(missing_list_path):
        raise MechanicGapIntakeContractError(
            f"input_missing_list.bundle_sha256 drifted from {_project_relative_path(missing_list_path)}."
        )
    gap_family_keys = _coerce_string_list(input_missing_list.get("gap_family_keys"), "input_missing_list.gap_family_keys")
    if gap_family_keys != actual_group_keys:
        raise MechanicGapIntakeContractError(
            "input_missing_list.gap_family_keys must match the accepted missing-list order."
        )

    source_policy = _coerce_mapping(source_pack.get("source_policy"), "source_policy")
    if source_policy.get("default_source_family") != "wiki":
        raise MechanicGapIntakeContractError("source_policy.default_source_family must be 'wiki'.")
    _coerce_non_empty_string(source_policy.get("secondary_source_rule"), "source_policy.secondary_source_rule")
    _coerce_non_empty_string(source_policy.get("promotion_boundary"), "source_policy.promotion_boundary")

    raw_records = _coerce_list(source_pack.get("records"), "records")
    if len(raw_records) != len(actual_group_keys):
        raise MechanicGapIntakeContractError("Source pack record count must match the accepted missing-list.")

    seen_group_keys: list[str] = []
    for index, raw_record in enumerate(raw_records):
        record = _coerce_mapping(raw_record, f"records[{index}]")
        group_key = _coerce_non_empty_string(record.get("group_key"), f"records[{index}].group_key")
        seen_group_keys.append(group_key)
        if group_key not in actual_missing_list_records:
            raise MechanicGapIntakeContractError(f"Unknown gap family {group_key!r} in source pack.")

        accepted_record = actual_missing_list_records[group_key]
        if record.get("coverage_status") != accepted_record.get("coverage_status"):
            raise MechanicGapIntakeContractError(f"{group_key!r} coverage_status drifted from the accepted missing-list.")
        if _coerce_string_list(record.get("missing_layers"), f"records[{index}].missing_layers") != list(
            accepted_record.get("missing_layers", [])
        ):
            raise MechanicGapIntakeContractError(f"{group_key!r} missing_layers drifted from the accepted missing-list.")
        if _coerce_string_list(record.get("partial_layers"), f"records[{index}].partial_layers") != list(
            accepted_record.get("partial_layers", [])
        ):
            raise MechanicGapIntakeContractError(f"{group_key!r} partial_layers drifted from the accepted missing-list.")
        if _coerce_non_empty_string(record.get("status_reason"), f"records[{index}].status_reason") != _coerce_non_empty_string(
            accepted_record.get("status_reason"),
            f"accepted_missing_list[{group_key}].status_reason",
        ):
            raise MechanicGapIntakeContractError(f"{group_key!r} status_reason drifted from the accepted missing-list.")

        _coerce_string_list(record.get("terminology_notes"), f"records[{index}].terminology_notes")
        _coerce_string_list(record.get("ambiguity_notes"), f"records[{index}].ambiguity_notes")
        wiki_only_sufficient = _coerce_bool(record.get("wiki_only_sufficient"), f"records[{index}].wiki_only_sufficient")

        raw_entries = _coerce_list(record.get("source_entries"), f"records[{index}].source_entries")
        if not raw_entries:
            raise MechanicGapIntakeContractError(f"{group_key!r} must contain at least one source entry.")
        seen_entry_ids: set[str] = set()
        source_families: list[str] = []
        for entry_index, raw_entry in enumerate(raw_entries):
            entry = _coerce_mapping(raw_entry, f"records[{index}].source_entries[{entry_index}]")
            entry_id = _coerce_non_empty_string(entry.get("entry_id"), f"records[{index}].source_entries[{entry_index}].entry_id")
            if entry_id in seen_entry_ids:
                raise MechanicGapIntakeContractError(f"{group_key!r} contains duplicate source entry id {entry_id!r}.")
            seen_entry_ids.add(entry_id)
            source_families.append(
                _validate_source_entry(entry, field_name=f"records[{index}].source_entries[{entry_index}]")
            )

        has_secondary = "secondary" in source_families
        if wiki_only_sufficient and has_secondary:
            raise MechanicGapIntakeContractError(
                f"{group_key!r} marks wiki_only_sufficient but still carries secondary sources."
            )
        if not wiki_only_sufficient and not has_secondary:
            raise MechanicGapIntakeContractError(
                f"{group_key!r} requires at least one secondary source when wiki_only_sufficient is false."
            )

    if seen_group_keys != actual_group_keys:
        raise MechanicGapIntakeContractError("Source pack record order must match the accepted missing-list order.")


def load_mechanic_gap_source_pack(
    source_pack_path: Path = DEFAULT_SOURCE_PACK_FIXTURE_PATH,
    *,
    missing_list_path: Path = DEFAULT_COMMITTED_MISSING_LIST_PATH,
) -> dict[str, Any]:
    """Load the replay-safe mechanic gap source pack aligned to the accepted missing-list."""

    missing_list = _load_missing_list_payload(missing_list_path)
    source_pack = _load_json(source_pack_path)
    _validate_source_pack(
        _coerce_mapping(source_pack, "source_pack"),
        missing_list=_coerce_mapping(missing_list, "missing_list"),
        missing_list_path=missing_list_path,
    )
    return source_pack
