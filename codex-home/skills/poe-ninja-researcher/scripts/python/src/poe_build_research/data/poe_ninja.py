"""Bounded poe.ninja public-build intake surfaces for listing, page, and profile retrieval."""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POE_NINJA_BUILD_LISTING_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "data" / "poe_ninja_build_listing.schema.json"
DEFAULT_POE_NINJA_BUILD_PAGE_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "data" / "poe_ninja_build_page.schema.json"
DEFAULT_POE_NINJA_CHARACTER_PROFILE_SCHEMA_PATH = (
    PROJECT_ROOT / "schemas" / "data" / "poe_ninja_character_profile.schema.json"
)
POE_NINJA_SCHEMA_VERSION = "1.0.0"
POE_NINJA_BUILD_LISTING_RECORD_KIND = "poe_ninja_build_listing"
POE_NINJA_BUILD_PAGE_RECORD_KIND = "poe_ninja_build_page"
POE_NINJA_BUILD_PAGE_PARTITIONED_RECORD_KIND = "poe_ninja_build_page_partitioned"
POE_NINJA_CHARACTER_PROFILE_RECORD_KIND = "poe_ninja_character_profile"
POE_NINJA_GENERATOR = "poe_build_research.data.poe_ninja"
POE_NINJA_UPSTREAM_SYSTEM = "poe_ninja_public_builds"
POE_NINJA_SOURCE_ID = "poe_ninja_public_builds"
POE_NINJA_BASE_URL = "https://poe.ninja"
POE_NINJA_INDEX_STATE_URL = f"{POE_NINJA_BASE_URL}/poe1/api/data/index-state"
POE_NINJA_BUILD_INDEX_STATE_URL = f"{POE_NINJA_BASE_URL}/poe1/api/data/build-index-state"
POE_NINJA_BUILD_PAGE_URL_TEMPLATE = f"{POE_NINJA_BASE_URL}/poe1/builds/{{league_url}}"
POE_NINJA_CHARACTER_PAGE_URL_TEMPLATE = f"{POE_NINJA_BASE_URL}/poe1/builds/{{league_url}}/character/{{account}}/{{name}}"
POE_NINJA_SEARCH_ENDPOINT_TEMPLATE = f"{POE_NINJA_BASE_URL}/poe1/api/builds/{{version}}/search"
POE_NINJA_DICTIONARY_ENDPOINT_TEMPLATE = f"{POE_NINJA_BASE_URL}/poe1/api/builds/dictionary/{{hash_value}}"
POE_NINJA_CHARACTER_ENDPOINT_TEMPLATE = f"{POE_NINJA_BASE_URL}/poe1/api/builds/{{version}}/character"
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; poe-build-research-poe-ninja/0.1)"
DEFAULT_TIMEOUT_SECONDS = 30
MAX_BUILD_PAGE_RESULTS = 25
MAX_SECTION_ITEMS = 10
TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
LINK_CANONICAL_PATTERN = re.compile(r"<link\b[^>]*\brel=\"canonical\"[^>]*\bhref=\"([^\"]+)\"", re.IGNORECASE)
META_TAG_PATTERN = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
ATTRIBUTE_PATTERN = re.compile(r"([A-Za-z:_-]+)=\"([^\"]*)\"")
FRAME_TYPE_TO_RARITY = {
    0: "normal",
    1: "magic",
    2: "rare",
    3: "unique",
    4: "gem",
}


class PoENinjaContractError(RuntimeError):
    """Raised when a bounded poe.ninja intake surface violates its contract."""


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PoENinjaContractError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PoENinjaContractError("Expected a string when a value is provided.")
    normalized = value.strip()
    return normalized or None


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PoENinjaContractError(f"{field_name} must be an object.")
    return value


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoENinjaContractError(f"{field_name} must be an array.")
    return value


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise PoENinjaContractError("Expected a boolean when a value is provided.")
    return value


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise PoENinjaContractError("Expected an integer when a value is provided.")
    return value


def _optional_number(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PoENinjaContractError("Expected a number when a value is provided.")
    return value


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _parse_cache_control(headers: Mapping[str, str]) -> dict[str, int | None]:
    raw_value = headers.get("cache-control")
    parsed: dict[str, int | None] = {
        "max_age_seconds": None,
        "stale_while_revalidate_seconds": None,
        "stale_if_error_seconds": None,
    }
    if raw_value is None:
        return parsed

    for token in (part.strip() for part in raw_value.split(",")):
        if "=" not in token:
            continue
        key, raw_number = token.split("=", maxsplit=1)
        key = key.strip().lower()
        raw_number = raw_number.strip()
        if not raw_number.isdigit():
            continue
        number = int(raw_number)
        if key == "max-age":
            parsed["max_age_seconds"] = number
        elif key == "stale-while-revalidate":
            parsed["stale_while_revalidate_seconds"] = number
        elif key == "stale-if-error":
            parsed["stale_if_error_seconds"] = number
    return parsed


def _project_relative_path(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False)).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _source_surface(public_surface: str) -> dict[str, Any]:
    return {
        "source_id": POE_NINJA_SOURCE_ID,
        "upstream_system": POE_NINJA_UPSTREAM_SYSTEM,
        "public_surface": public_surface,
        "site_base_url": POE_NINJA_BASE_URL,
    }


@dataclass(frozen=True, slots=True)
class UpstreamResponse:
    """Observed upstream payload plus stable provenance metadata."""

    url: str
    method: str
    status: int
    headers: dict[str, str]
    body: bytes
    fetched_at: str

    @property
    def body_sha256(self) -> str:
        return _sha256_bytes(self.body)

    @property
    def content_type(self) -> str | None:
        return self.headers.get("content-type")

    @property
    def content_length(self) -> int:
        header_value = self.headers.get("content-length")
        if header_value is not None and header_value.isdigit():
            return int(header_value)
        return len(self.body)

    def text(self) -> str:
        return self.body.decode("utf-8")

    def json(self) -> Any:
        return json.loads(self.text())


@dataclass(frozen=True, slots=True)
class SnapshotVersion:
    """Minimal routing metadata for one poe.ninja build snapshot."""

    league_url: str
    snapshot_type: str
    league_name: str
    time_machine_labels: tuple[str, ...]
    version: str
    snapshot_name: str
    overview_type: int
    passive_tree: str
    atlas_tree: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], field_name: str) -> "SnapshotVersion":
        return cls(
            league_url=_require_non_empty_string(payload.get("url"), f"{field_name}.url"),
            snapshot_type=_require_non_empty_string(payload.get("type"), f"{field_name}.type"),
            league_name=_require_non_empty_string(payload.get("name"), f"{field_name}.name"),
            time_machine_labels=tuple(
                _require_non_empty_string(item, f"{field_name}.timeMachineLabels[]")
                for item in _require_list(payload.get("timeMachineLabels"), f"{field_name}.timeMachineLabels")
            ),
            version=_require_non_empty_string(payload.get("version"), f"{field_name}.version"),
            snapshot_name=_require_non_empty_string(payload.get("snapshotName"), f"{field_name}.snapshotName"),
            overview_type=_optional_int(payload.get("overviewType")) or 0,
            passive_tree=_require_non_empty_string(payload.get("passiveTree"), f"{field_name}.passiveTree"),
            atlas_tree=_require_non_empty_string(payload.get("atlasTree"), f"{field_name}.atlasTree"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "league_url": self.league_url,
            "snapshot_type": self.snapshot_type,
            "league_name": self.league_name,
            "time_machine_labels": list(self.time_machine_labels),
            "version": self.version,
            "snapshot_name": self.snapshot_name,
            "overview_type": self.overview_type,
            "passive_tree": self.passive_tree,
            "atlas_tree": self.atlas_tree,
        }


def _normalize_filter_values(filters: Mapping[str, str | Sequence[str]] | None) -> list[tuple[str, tuple[str, ...]]]:
    if filters is None:
        return []
    if not isinstance(filters, Mapping):
        raise PoENinjaContractError("filters must be a mapping when provided.")

    normalized: list[tuple[str, tuple[str, ...]]] = []
    for raw_key, raw_value in filters.items():
        key = _require_non_empty_string(raw_key, "filters key")
        if key in {"overview", "type", "timemachine", "timeMachine", "i"}:
            raise PoENinjaContractError(f"filters must not override reserved key '{key}'.")
        if isinstance(raw_value, str):
            values = (_require_non_empty_string(raw_value, f"filters.{key}"),)
        elif isinstance(raw_value, Sequence):
            values = tuple(_require_non_empty_string(item, f"filters.{key}[]") for item in raw_value)
            if not values:
                raise PoENinjaContractError(f"filters.{key} must not be an empty sequence.")
        else:
            raise PoENinjaContractError(f"filters.{key} must be a string or a sequence of strings.")
        normalized.append((key, values))
    return normalized


def _query_pairs_from_filters(filters: list[tuple[str, tuple[str, ...]]]) -> list[tuple[str, str]]:
    return [(key, ",".join(values)) for key, values in filters]


def _build_query_string(pairs: list[tuple[str, str]]) -> str:
    if not pairs:
        return ""
    return urlencode(pairs)


def _build_search_page_url(
    league_url: str,
    *,
    snapshot_type: str,
    filters: list[tuple[str, tuple[str, ...]]],
    time_machine: str | None,
) -> str:
    base_url = POE_NINJA_BUILD_PAGE_URL_TEMPLATE.format(league_url=quote(league_url, safe=""))
    pairs = _query_pairs_from_filters(filters)
    if snapshot_type != "exp":
        pairs.append(("type", snapshot_type))
    if time_machine is not None:
        pairs.append(("timemachine", time_machine))
    query_string = _build_query_string(pairs)
    return base_url if not query_string else f"{base_url}?{query_string}"


def _build_character_page_url(
    league_url: str,
    *,
    account: str,
    name: str,
    snapshot_type: str,
    filters: list[tuple[str, tuple[str, ...]]],
    time_machine: str | None,
    page_index: int | None,
) -> str:
    base_url = POE_NINJA_CHARACTER_PAGE_URL_TEMPLATE.format(
        league_url=quote(league_url, safe=""),
        account=quote(account, safe=""),
        name=quote(name, safe=""),
    )
    pairs: list[tuple[str, str]] = []
    if snapshot_type != "exp":
        pairs.append(("type", snapshot_type))
    if time_machine is not None:
        pairs.append(("timemachine", time_machine))
    if page_index is not None:
        pairs.append(("i", str(page_index)))
    pairs.extend(_query_pairs_from_filters(filters))
    query_string = _build_query_string(pairs)
    return base_url if not query_string else f"{base_url}?{query_string}"


def _build_search_api_url(
    snapshot: SnapshotVersion,
    *,
    filters: list[tuple[str, tuple[str, ...]]],
    time_machine: str | None,
) -> str:
    pairs = _query_pairs_from_filters(filters)
    pairs.append(("overview", snapshot.snapshot_name))
    pairs.append(("type", snapshot.snapshot_type))
    if time_machine is not None:
        pairs.append(("timemachine", time_machine))
    return f"{POE_NINJA_SEARCH_ENDPOINT_TEMPLATE.format(version=quote(snapshot.version, safe=''))}?{_build_query_string(pairs)}"


def _build_character_api_url(
    snapshot: SnapshotVersion,
    *,
    account: str,
    name: str,
    time_machine: str | None,
) -> str:
    pairs = [
        ("account", account),
        ("name", name),
        ("overview", snapshot.snapshot_name),
        ("type", snapshot.snapshot_type),
    ]
    if time_machine is not None:
        pairs.append(("timeMachine", time_machine))
    return f"{POE_NINJA_CHARACTER_ENDPOINT_TEMPLATE.format(version=quote(snapshot.version, safe=''))}?{_build_query_string(pairs)}"


def _attribute_map(raw_tag: str) -> dict[str, str]:
    return {
        key.lower(): html.unescape(value)
        for key, value in ATTRIBUTE_PATTERN.findall(raw_tag)
    }


def _extract_page_metadata(html_text: str, requested_url: str) -> dict[str, Any]:
    title_match = TITLE_PATTERN.search(html_text)
    title = html.unescape(title_match.group(1).strip()) if title_match else None
    description = None
    og_url = None
    for match in META_TAG_PATTERN.finditer(html_text):
        attributes = _attribute_map(match.group(0))
        content = attributes.get("content")
        if content is None:
            continue
        if attributes.get("name") == "description":
            description = content
        elif attributes.get("property") == "og:url":
            og_url = content
    canonical_match = LINK_CANONICAL_PATTERN.search(html_text)
    canonical_url = html.unescape(canonical_match.group(1)) if canonical_match else None
    return {
        "requested_url": requested_url,
        "title": title,
        "description": description,
        "canonical_url": canonical_url,
        "og_url": og_url,
    }


def _read_varint(buffer: bytes, position: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if position >= len(buffer):
            raise PoENinjaContractError("Unexpected end of protobuf payload while reading a varint.")
        current_byte = buffer[position]
        position += 1
        value |= (current_byte & 0x7F) << shift
        if not current_byte & 0x80:
            return value, position
        shift += 7
        if shift > 63:
            raise PoENinjaContractError("Unsupported varint length in protobuf payload.")


def _decode_packed_varints(buffer: bytes) -> list[int]:
    values: list[int] = []
    position = 0
    while position < len(buffer):
        value, position = _read_varint(buffer, position)
        values.append(value)
    return values


def _iter_protobuf_fields(buffer: bytes) -> list[tuple[int, int, Any]]:
    position = 0
    fields: list[tuple[int, int, Any]] = []
    while position < len(buffer):
        key, position = _read_varint(buffer, position)
        field_number = key >> 3
        wire_type = key & 0x07
        if wire_type == 0:
            value, position = _read_varint(buffer, position)
        elif wire_type == 1:
            if position + 8 > len(buffer):
                raise PoENinjaContractError("Unexpected end of protobuf payload while reading a 64-bit field.")
            value = buffer[position : position + 8]
            position += 8
        elif wire_type == 2:
            length, position = _read_varint(buffer, position)
            if position + length > len(buffer):
                raise PoENinjaContractError("Unexpected end of protobuf payload while reading a bytes field.")
            value = buffer[position : position + length]
            position += length
        elif wire_type == 5:
            if position + 4 > len(buffer):
                raise PoENinjaContractError("Unexpected end of protobuf payload while reading a 32-bit field.")
            value = buffer[position : position + 4]
            position += 4
        else:
            raise PoENinjaContractError(f"Unsupported protobuf wire type: {wire_type}.")
        fields.append((field_number, wire_type, value))
    return fields


def _decode_proto_string(value: Any, field_name: str) -> str:
    if not isinstance(value, (bytes, bytearray)):
        raise PoENinjaContractError(f"{field_name} must be bytes in the protobuf payload.")
    return value.decode("utf-8")


def _decode_proto_string_map(blob: bytes) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for field_number, wire_type, value in _iter_protobuf_fields(blob):
        if field_number != 7 or wire_type != 2:
            continue
        key = None
        mapped_value = None
        for nested_field_number, nested_wire_type, nested_value in _iter_protobuf_fields(value):
            if nested_field_number == 1 and nested_wire_type == 2:
                key = _decode_proto_string(nested_value, "protobuf map key")
            elif nested_field_number == 2 and nested_wire_type == 2:
                mapped_value = _decode_proto_string(nested_value, "protobuf map value")
        if key is not None and mapped_value is not None:
            parsed[key] = mapped_value
    return parsed


def _parse_search_value(blob: bytes) -> dict[str, Any]:
    payload = {
        "str": None,
        "number": None,
        "numbers": [],
        "strs": [],
        "boolean": None,
    }
    for field_number, wire_type, value in _iter_protobuf_fields(blob):
        if field_number == 1 and wire_type == 2:
            payload["str"] = _decode_proto_string(value, "search_value.str")
        elif field_number == 2 and wire_type == 0:
            payload["number"] = value
        elif field_number == 3 and wire_type == 0:
            payload["numbers"].append(value)
        elif field_number == 3 and wire_type == 2:
            payload["numbers"].extend(_decode_packed_varints(value))
        elif field_number == 4 and wire_type == 2:
            payload["strs"].append(_decode_proto_string(value, "search_value.strs[]"))
        elif field_number == 5 and wire_type == 0:
            payload["boolean"] = bool(value)
    return payload


def _parse_search_value_list(blob: bytes) -> tuple[str, list[dict[str, Any]]]:
    value_list_id = None
    values: list[dict[str, Any]] = []
    for field_number, wire_type, value in _iter_protobuf_fields(blob):
        if field_number == 1 and wire_type == 2:
            value_list_id = _decode_proto_string(value, "value_list.id")
        elif field_number == 2 and wire_type == 2:
            values.append(_parse_search_value(value))
    if value_list_id is None:
        raise PoENinjaContractError("SearchResultValueList is missing its id.")
    return value_list_id, values


def _parse_search_dictionary_reference(blob: bytes) -> dict[str, str]:
    payload: dict[str, str] = {}
    for field_number, wire_type, value in _iter_protobuf_fields(blob):
        if wire_type != 2:
            continue
        if field_number == 1:
            payload["id"] = _decode_proto_string(value, "dictionary_ref.id")
        elif field_number == 2:
            payload["hash"] = _decode_proto_string(value, "dictionary_ref.hash")
    if "id" not in payload or "hash" not in payload:
        raise PoENinjaContractError("SearchResultDictionaryReference is incomplete.")
    return payload


def _parse_search_dictionary_property(blob: bytes) -> tuple[str, list[str]]:
    property_id = None
    values: list[str] = []
    for field_number, wire_type, value in _iter_protobuf_fields(blob):
        if field_number == 1 and wire_type == 2:
            property_id = _decode_proto_string(value, "dictionary_property.id")
        elif field_number == 2 and wire_type == 2:
            values.append(_decode_proto_string(value, "dictionary_property.values[]"))
    if property_id is None:
        raise PoENinjaContractError("SearchResultDictionaryProperty is missing its id.")
    return property_id, values


def _parse_search_dictionary(blob: bytes) -> dict[str, Any]:
    dictionary_id = None
    values: list[str] = []
    properties: dict[str, list[str]] = {}
    for field_number, wire_type, value in _iter_protobuf_fields(blob):
        if field_number == 1 and wire_type == 2:
            dictionary_id = _decode_proto_string(value, "dictionary.id")
        elif field_number == 2 and wire_type == 2:
            values.append(_decode_proto_string(value, "dictionary.values[]"))
        elif field_number == 3 and wire_type == 2:
            property_id, property_values = _parse_search_dictionary_property(value)
            properties[property_id] = property_values
    if dictionary_id is None:
        raise PoENinjaContractError("SearchResultDictionary is missing its id.")
    return {
        "id": dictionary_id,
        "values": values,
        "properties": properties,
    }


def _parse_search_dimension_count(blob: bytes, *, implicit_key: int | None = None) -> dict[str, int] | None:
    payload = {"key": None, "count": None}
    for field_number, wire_type, value in _iter_protobuf_fields(blob):
        if wire_type != 0:
            continue
        if field_number == 1:
            payload["key"] = value
        elif field_number == 2:
            payload["count"] = value
    if payload["key"] is None and implicit_key is not None:
        payload["key"] = implicit_key
    if payload["key"] is not None and payload["count"] is None:
        return None
    if payload["key"] is None or payload["count"] is None:
        raise PoENinjaContractError("SearchResultDimensionCount is incomplete.")
    return {"key": payload["key"], "count": payload["count"]}


def _parse_search_dimension(blob: bytes) -> dict[str, Any]:
    payload = {"id": None, "dictionary_id": None, "counts": []}
    for field_number, wire_type, value in _iter_protobuf_fields(blob):
        if field_number == 1 and wire_type == 2:
            payload["id"] = _decode_proto_string(value, "dimension.id")
        elif field_number == 2 and wire_type == 2:
            payload["dictionary_id"] = _decode_proto_string(value, "dimension.dictionary_id")
        elif field_number == 3 and wire_type == 2:
            if not value:
                continue
            count = _parse_search_dimension_count(value, implicit_key=len(payload["counts"]))
            if count is not None:
                payload["counts"].append(count)
    if payload["id"] is None or payload["dictionary_id"] is None:
        raise PoENinjaContractError("SearchResultDimension is incomplete.")
    return payload


def _parse_search_integer_dimension(blob: bytes) -> dict[str, Any]:
    payload = {"id": None, "min_value": None, "max_value": None}
    for field_number, wire_type, value in _iter_protobuf_fields(blob):
        if field_number == 1 and wire_type == 2:
            payload["id"] = _decode_proto_string(value, "integer_dimension.id")
        elif field_number == 2 and wire_type == 0:
            payload["min_value"] = value
        elif field_number == 3 and wire_type == 0:
            payload["max_value"] = value
    if payload["id"] is None:
        raise PoENinjaContractError("SearchResultIntegerDimension is missing its id.")
    return payload


def _parse_search_performance_point(blob: bytes) -> dict[str, Any]:
    payload = {"name": None, "ms": None}
    for field_number, wire_type, value in _iter_protobuf_fields(blob):
        if field_number == 1 and wire_type == 2:
            payload["name"] = _decode_proto_string(value, "performance_point.name")
        elif field_number == 2 and wire_type == 1:
            payload["ms"] = int.from_bytes(value, byteorder="little", signed=False)
    if payload["name"] is None:
        raise PoENinjaContractError("SearchResultPerformance is missing its name.")
    return payload


def _parse_search_field(blob: bytes) -> dict[str, Any]:
    payload = {
        "id": None,
        "type": None,
        "name": None,
        "value_list_ids": [],
        "sort_id": None,
        "integer_dimension_id": None,
        "properties": {},
        "main_field_id": None,
        "description": None,
        "group": None,
        "pinned": False,
    }
    for field_number, wire_type, value in _iter_protobuf_fields(blob):
        if field_number == 1 and wire_type == 2:
            payload["id"] = _decode_proto_string(value, "field.id")
        elif field_number == 2 and wire_type == 2:
            payload["type"] = _decode_proto_string(value, "field.type")
        elif field_number == 3 and wire_type == 2:
            payload["name"] = _decode_proto_string(value, "field.name")
        elif field_number == 4 and wire_type == 2:
            payload["value_list_ids"].append(_decode_proto_string(value, "field.value_list_ids[]"))
        elif field_number == 5 and wire_type == 2:
            payload["sort_id"] = _decode_proto_string(value, "field.sort_id")
        elif field_number == 6 and wire_type == 2:
            payload["integer_dimension_id"] = _decode_proto_string(value, "field.integer_dimension_id")
        elif field_number == 7 and wire_type == 2:
            map_fields = _iter_protobuf_fields(value)
            key = None
            mapped_value = None
            for nested_field_number, nested_wire_type, nested_value in map_fields:
                if nested_field_number == 1 and nested_wire_type == 2:
                    key = _decode_proto_string(nested_value, "field.properties.key")
                elif nested_field_number == 2 and nested_wire_type == 2:
                    mapped_value = _decode_proto_string(nested_value, "field.properties.value")
            if key is not None and mapped_value is not None:
                payload["properties"][key] = mapped_value
        elif field_number == 8 and wire_type == 2:
            payload["main_field_id"] = _decode_proto_string(value, "field.main_field_id")
        elif field_number == 9 and wire_type == 2:
            payload["description"] = _decode_proto_string(value, "field.description")
        elif field_number == 10 and wire_type == 2:
            payload["group"] = _decode_proto_string(value, "field.group")
        elif field_number == 11 and wire_type == 0:
            payload["pinned"] = bool(value)
    if payload["id"] is None or payload["type"] is None or payload["name"] is None:
        raise PoENinjaContractError("SearchResultField is incomplete.")
    return payload


def _parse_search_section(blob: bytes) -> dict[str, Any]:
    payload = {"id": None, "type": None, "name": None, "dimension_id": None, "properties": {}}
    for field_number, wire_type, value in _iter_protobuf_fields(blob):
        if field_number == 1 and wire_type == 2:
            payload["id"] = _decode_proto_string(value, "section.id")
        elif field_number == 2 and wire_type == 2:
            payload["type"] = _decode_proto_string(value, "section.type")
        elif field_number == 3 and wire_type == 2:
            payload["name"] = _decode_proto_string(value, "section.name")
        elif field_number == 4 and wire_type == 2:
            payload["dimension_id"] = _decode_proto_string(value, "section.dimension_id")
        elif field_number == 5 and wire_type == 2:
            key = None
            mapped_value = None
            for nested_field_number, nested_wire_type, nested_value in _iter_protobuf_fields(value):
                if nested_field_number == 1 and nested_wire_type == 2:
                    key = _decode_proto_string(nested_value, "section.properties.key")
                elif nested_field_number == 2 and nested_wire_type == 2:
                    mapped_value = _decode_proto_string(nested_value, "section.properties.value")
            if key is not None and mapped_value is not None:
                payload["properties"][key] = mapped_value
    if payload["id"] is None or payload["name"] is None or payload["dimension_id"] is None:
        raise PoENinjaContractError("SearchResultSection is incomplete.")
    return payload


def _parse_search_field_descriptor(blob: bytes) -> dict[str, Any]:
    payload = {
        "id": None,
        "name": None,
        "optional": False,
        "description": None,
        "group": None,
        "pinned": False,
    }
    for field_number, wire_type, value in _iter_protobuf_fields(blob):
        if field_number == 1 and wire_type == 2:
            payload["id"] = _decode_proto_string(value, "field_descriptor.id")
        elif field_number == 2 and wire_type == 2:
            payload["name"] = _decode_proto_string(value, "field_descriptor.name")
        elif field_number == 3 and wire_type == 0:
            payload["optional"] = bool(value)
        elif field_number == 4 and wire_type == 2:
            payload["description"] = _decode_proto_string(value, "field_descriptor.description")
        elif field_number == 5 and wire_type == 2:
            payload["group"] = _decode_proto_string(value, "field_descriptor.group")
        elif field_number == 6 and wire_type == 0:
            payload["pinned"] = bool(value)
    if payload["id"] is None or payload["name"] is None:
        raise PoENinjaContractError("SearchResultFieldDescriptor is incomplete.")
    return payload


def _decode_search_result(payload: bytes) -> dict[str, Any]:
    root_fields = _iter_protobuf_fields(payload)
    result_messages = [value for field_number, wire_type, value in root_fields if field_number == 1 and wire_type == 2]
    if len(result_messages) != 1:
        raise PoENinjaContractError("Expected exactly one NinjaSearchResult.result payload.")

    parsed = {
        "total": 0,
        "dimensions": [],
        "integer_dimensions": [],
        "performance_points": [],
        "value_lists": {},
        "dictionaries": [],
        "fields": [],
        "sections": [],
        "field_descriptors": [],
        "default_field_ids": [],
    }
    for field_number, wire_type, value in _iter_protobuf_fields(result_messages[0]):
        if field_number == 1 and wire_type == 0:
            parsed["total"] = value
        elif field_number == 2 and wire_type == 2:
            parsed["dimensions"].append(_parse_search_dimension(value))
        elif field_number == 3 and wire_type == 2:
            parsed["integer_dimensions"].append(_parse_search_integer_dimension(value))
        elif field_number == 4 and wire_type == 2:
            parsed["performance_points"].append(_parse_search_performance_point(value))
        elif field_number == 5 and wire_type == 2:
            value_list_id, values = _parse_search_value_list(value)
            parsed["value_lists"][value_list_id] = values
        elif field_number == 6 and wire_type == 2:
            parsed["dictionaries"].append(_parse_search_dictionary_reference(value))
        elif field_number == 7 and wire_type == 2:
            parsed["fields"].append(_parse_search_field(value))
        elif field_number == 8 and wire_type == 2:
            parsed["sections"].append(_parse_search_section(value))
        elif field_number == 9 and wire_type == 2:
            parsed["field_descriptors"].append(_parse_search_field_descriptor(value))
        elif field_number == 10 and wire_type == 2:
            parsed["default_field_ids"].append(_decode_proto_string(value, "default_field_ids[]"))
    return parsed


def _dictionary_entry_properties(dictionary: Mapping[str, Any], index: int) -> dict[str, str]:
    properties: dict[str, str] = {}
    for property_id, values in dictionary.get("properties", {}).items():
        if index < len(values):
            properties[property_id] = values[index]
    return properties


def _resolve_search_value(value_id: str, payload: Mapping[str, Any], dictionaries: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    dictionary = dictionaries.get(value_id)
    if payload["str"] is not None:
        return {
            "value_id": value_id,
            "kind": "string",
            "string_value": payload["str"],
        }
    if payload["number"] is not None:
        if dictionary is not None:
            key = payload["number"]
            label = dictionary["values"][key] if key < len(dictionary["values"]) else None
            return {
                "value_id": value_id,
                "kind": "dictionary",
                "dictionary_id": dictionary["id"],
                "dictionary_key": key,
                "label": label,
                "entry_properties": _dictionary_entry_properties(dictionary, key),
            }
        return {
            "value_id": value_id,
            "kind": "number",
            "number_value": payload["number"],
        }
    if payload["numbers"]:
        if dictionary is not None:
            labels = [dictionary["values"][key] if key < len(dictionary["values"]) else None for key in payload["numbers"]]
            return {
                "value_id": value_id,
                "kind": "dictionary_list",
                "dictionary_id": dictionary["id"],
                "dictionary_keys": list(payload["numbers"]),
                "labels": labels,
            }
        return {
            "value_id": value_id,
            "kind": "number_list",
            "number_values": list(payload["numbers"]),
        }
    if payload["strs"]:
        return {
            "value_id": value_id,
            "kind": "string_list",
            "string_values": list(payload["strs"]),
        }
    if payload["boolean"] is not None:
        return {
            "value_id": value_id,
            "kind": "boolean",
            "boolean_value": payload["boolean"],
        }
    return {
        "value_id": value_id,
        "kind": "empty",
    }


def _display_resolved_value(resolved_value: Mapping[str, Any]) -> Any:
    kind = resolved_value["kind"]
    if kind == "string":
        return resolved_value.get("string_value")
    if kind == "number":
        return resolved_value.get("number_value")
    if kind == "dictionary":
        return resolved_value.get("label")
    if kind == "boolean":
        return resolved_value.get("boolean_value")
    if kind == "string_list":
        return resolved_value.get("string_values")
    if kind == "number_list":
        return resolved_value.get("number_values")
    if kind == "dictionary_list":
        return resolved_value.get("labels")
    return None


def _build_search_sections(
    search_result: Mapping[str, Any],
    dictionaries: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    dimensions_by_id = {dimension["id"]: dimension for dimension in search_result["dimensions"]}
    sections: list[dict[str, Any]] = []
    total = search_result["total"] or 0
    for section in search_result["sections"]:
        dimension = dimensions_by_id.get(section["dimension_id"])
        if dimension is None:
            continue
        dictionary = dictionaries.get(dimension["dictionary_id"])
        top_items: list[dict[str, Any]] = []
        for row in sorted(dimension["counts"], key=lambda item: (-item["count"], item["key"]))[:MAX_SECTION_ITEMS]:
            key = row["key"]
            label = dictionary["values"][key] if dictionary is not None and key < len(dictionary["values"]) else str(key)
            top_items.append(
                {
                    "dictionary_id": dimension["dictionary_id"],
                    "dictionary_key": key,
                    "label": label,
                    "count": row["count"],
                    "percentage": (row["count"] * 100 / total) if total else 0.0,
                    "entry_properties": _dictionary_entry_properties(dictionary, key) if dictionary is not None else {},
                }
            )
        sections.append(
            {
                "id": section["id"],
                "type": section["type"],
                "name": section["name"],
                "dimension_id": section["dimension_id"],
                "properties": section["properties"],
                "top_items": top_items,
            }
        )
    return sections


def _build_search_rows(
    *,
    search_result: Mapping[str, Any],
    dictionaries: Mapping[str, Mapping[str, Any]],
    league_url: str,
    snapshot: SnapshotVersion,
    filters: list[tuple[str, tuple[str, ...]]],
    time_machine: str | None,
    result_limit: int,
) -> list[dict[str, Any]]:
    row_count = 0
    if search_result["value_lists"]:
        row_count = max(len(values) for values in search_result["value_lists"].values())
    limited_count = min(row_count, result_limit)
    rows: list[dict[str, Any]] = []
    for row_index in range(limited_count):
        field_values: list[dict[str, Any]] = []
        summary: dict[str, Any] = {}
        character_name = None
        character_account = None
        for field in search_result["fields"]:
            resolved_values: list[dict[str, Any]] = []
            for value_list_id in field["value_list_ids"]:
                values = search_result["value_lists"].get(value_list_id, [])
                if row_index >= len(values):
                    continue
                resolved_values.append(_resolve_search_value(value_list_id, values[row_index], dictionaries))
            field_payload = {
                "field_id": field["id"],
                "field_type": field["type"],
                "field_name": field["name"],
                "group": field["group"],
                "pinned": field["pinned"],
                "value_list_ids": list(field["value_list_ids"]),
                "resolved_values": resolved_values,
            }
            field_values.append(field_payload)
            if field["id"] == "character" and len(resolved_values) >= 2:
                character_name = resolved_values[0].get("string_value")
                character_account = resolved_values[1].get("string_value")
                summary["name"] = character_name
                summary["account"] = character_account
            elif field["id"] == "level" and resolved_values:
                if resolved_values[0]["kind"] == "number":
                    summary["level"] = resolved_values[0]["number_value"]
                if len(resolved_values) > 1 and resolved_values[1]["kind"] == "dictionary":
                    summary["class_name"] = resolved_values[1].get("label")
            elif field["id"] in {"skill", "skills"} and resolved_values:
                summary["main_skill"] = _display_resolved_value(resolved_values[0])
            elif field["id"] in {"dps", "ehp", "life"} and resolved_values:
                summary[field["id"]] = _display_resolved_value(resolved_values[0])

        if character_name is None or character_account is None:
            raise PoENinjaContractError("Search results are missing the required character identity field.")

        rows.append(
            {
                "rank": row_index + 1,
                "page_index": row_index,
                "character": {
                    "name": character_name,
                    "account": character_account,
                    "page_url": _build_character_page_url(
                        league_url,
                        account=character_account,
                        name=character_name,
                        snapshot_type=snapshot.snapshot_type,
                        filters=filters,
                        time_machine=time_machine,
                        page_index=row_index,
                    ),
                },
                "summary": summary,
                "field_values": field_values,
            }
        )
    return rows


def _normalize_item_summary(container: Mapping[str, Any]) -> dict[str, Any]:
    item = _require_mapping(container.get("itemData"), "itemData")
    frame_type = _optional_int(item.get("frameType"))
    return {
        "item_slot": _optional_int(container.get("itemSlot")),
        "inventory_id": _optional_string(item.get("inventoryId")),
        "name": _optional_string(item.get("name")) or _optional_string(item.get("typeLine")),
        "type_line": _optional_string(item.get("typeLine")),
        "base_type": _optional_string(item.get("baseType")),
        "rarity": FRAME_TYPE_TO_RARITY.get(frame_type, "unknown"),
        "frame_type": frame_type,
        "icon": _optional_string(item.get("icon")),
        "identified": _optional_bool(item.get("identified")),
        "corrupted": _optional_bool(item.get("corrupted")),
        "explicit_mods": [
            _require_non_empty_string(value, "item.explicitMods[]")
            for value in _require_list(item.get("explicitMods", []), "item.explicitMods")
        ],
        "crafted_mods": [
            _require_non_empty_string(value, "item.craftedMods[]")
            for value in _require_list(item.get("craftedMods", []), "item.craftedMods")
        ],
        "enchant_mods": [
            _require_non_empty_string(value, "item.enchantMods[]")
            for value in _require_list(item.get("enchantMods", []), "item.enchantMods")
        ],
    }


def _normalize_skill_groups(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for index, raw_group in enumerate(_require_list(payload.get("skills", []), "profile.skills")):
        group = _require_mapping(raw_group, f"profile.skills[{index}]")
        gems: list[dict[str, Any]] = []
        for gem_index, raw_gem in enumerate(_require_list(group.get("allGems", []), f"profile.skills[{index}].allGems")):
            gem = _require_mapping(raw_gem, f"profile.skills[{index}].allGems[{gem_index}]")
            raw_item_data = gem.get("itemData")
            item_data = raw_item_data if isinstance(raw_item_data, Mapping) else {}
            gems.append(
                {
                    "name": _require_non_empty_string(gem.get("name"), f"profile.skills[{index}].allGems[{gem_index}].name"),
                    "level": _optional_int(gem.get("level")),
                    "quality": _optional_int(gem.get("quality")),
                    "support": bool(item_data.get("support", False)),
                    "built_in_support": bool(gem.get("isBuiltInSupport", False)),
                }
            )
        dps_entries = []
        for dps_index, raw_dps in enumerate(_require_list(group.get("dps", []), f"profile.skills[{index}].dps")):
            dps = _require_mapping(raw_dps, f"profile.skills[{index}].dps[{dps_index}]")
            dps_entries.append(
                {
                    "name": _require_non_empty_string(dps.get("name"), f"profile.skills[{index}].dps[{dps_index}].name"),
                    "dps": _optional_int(dps.get("dps")) or 0,
                    "dot_dps": _optional_int(dps.get("dotDps")) or 0,
                }
            )
        groups.append(
            {
                "item_slot": _optional_int(group.get("itemSlot")),
                "primary_skill_names": [entry["name"] for entry in dps_entries] or [gem["name"] for gem in gems if not gem["support"]],
                "gems": gems,
                "dps_entries": dps_entries,
            }
        )
    return groups


def _normalize_mastery_name(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, Mapping):
        return _optional_string(value.get("name")) or _optional_string(value.get("group"))
    raise PoENinjaContractError(f"{field_name} must be a string or object.")


def _normalize_hash_ex_value(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, int) and not isinstance(value, bool):
        if value < 0:
            raise PoENinjaContractError(f"{field_name} must not be negative.")
        return str(value)
    raise PoENinjaContractError(f"{field_name} must be a string or integer.")


def _build_freshness_payload(
    responses: Sequence[UpstreamResponse],
    *,
    observed_data_timestamps: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "retrieved_at": max(response.fetched_at for response in responses),
        "resources": [
            {
                "url": response.url,
                "method": response.method,
                "content_type": response.content_type,
                "age_seconds": int(response.headers["age"]) if response.headers.get("age", "").isdigit() else None,
                "last_modified": response.headers.get("last-modified"),
                "cf_cache_status": response.headers.get("cf-cache-status"),
                **_parse_cache_control(response.headers),
            }
            for response in responses
        ],
        "observed_data_timestamps": list(observed_data_timestamps),
    }


def _build_provenance_payload(
    responses: Sequence[UpstreamResponse],
    *,
    notes: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "generator": POE_NINJA_GENERATOR,
        "upstream_system": POE_NINJA_UPSTREAM_SYSTEM,
        "inputs": [
            {
                "url": response.url,
                "method": response.method,
                "status": response.status,
                "content_type": response.content_type,
                "etag": response.headers.get("etag"),
                "body_sha256": response.body_sha256,
                "body_bytes": response.content_length,
                "fetched_at": response.fetched_at,
            }
            for response in responses
        ],
        "notes": list(notes),
    }


class PoENinjaClient:
    """Thin bounded intake wrapper for public poe.ninja build surfaces."""

    def __init__(
        self,
        *,
        urlopen_fn: Callable[..., Any] = urlopen,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._urlopen = urlopen_fn
        self.user_agent = _require_non_empty_string(user_agent, "user_agent")
        if timeout_seconds < 1:
            raise PoENinjaContractError("timeout_seconds must be >= 1.")
        self.timeout_seconds = timeout_seconds

    def fetch_build_listing(self) -> dict[str, Any]:
        index_state_response = self._fetch_response(POE_NINJA_INDEX_STATE_URL, accept="application/json")
        build_index_response = self._fetch_response(POE_NINJA_BUILD_INDEX_STATE_URL, accept="application/json")
        index_state = _require_mapping(index_state_response.json(), "index_state")
        build_index_state = _require_mapping(build_index_response.json(), "build_index_state")

        build_leagues = {
            _require_non_empty_string(item.get("url"), "buildLeagues[].url"): {
                "display_name": _require_non_empty_string(item.get("displayName"), "buildLeagues[].displayName"),
                "source_bucket": "current",
            }
            for item in _require_list(index_state.get("buildLeagues", []), "buildLeagues")
        }
        old_build_leagues = {
            _require_non_empty_string(item.get("url"), "oldBuildLeagues[].url"): {
                "display_name": _require_non_empty_string(item.get("displayName"), "oldBuildLeagues[].displayName"),
                "source_bucket": "archived",
            }
            for item in _require_list(index_state.get("oldBuildLeagues", []), "oldBuildLeagues")
        }
        snapshot_versions: dict[str, list[SnapshotVersion]] = {}
        for index, raw_snapshot in enumerate(_require_list(index_state.get("snapshotVersions", []), "snapshotVersions")):
            snapshot = SnapshotVersion.from_dict(_require_mapping(raw_snapshot, f"snapshotVersions[{index}]"), f"snapshotVersions[{index}]")
            snapshot_versions.setdefault(snapshot.league_url, []).append(snapshot)

        leagues_payload: list[dict[str, Any]] = []
        seen_league_urls: set[str] = set()
        for index, raw_league in enumerate(_require_list(build_index_state.get("leagueBuilds", []), "leagueBuilds")):
            league = _require_mapping(raw_league, f"leagueBuilds[{index}]")
            league_url = _require_non_empty_string(league.get("leagueUrl"), f"leagueBuilds[{index}].leagueUrl")
            seen_league_urls.add(league_url)
            listing_meta = build_leagues.get(league_url) or old_build_leagues.get(league_url) or {
                "display_name": _optional_string(league.get("leagueName")) or league_url,
                "source_bucket": "unresolved",
            }
            top_archetypes = []
            for stat_index, raw_stat in enumerate(_require_list(league.get("statistics", []), f"leagueBuilds[{index}].statistics")):
                stat = _require_mapping(raw_stat, f"leagueBuilds[{index}].statistics[{stat_index}]")
                top_archetypes.append(
                    {
                        "class_name": _require_non_empty_string(stat.get("class"), f"leagueBuilds[{index}].statistics[{stat_index}].class"),
                        "skill_name": _optional_string(stat.get("skill")),
                        "usage_percent": float(_optional_number(stat.get("percentage")) or 0),
                        "trend": _optional_int(stat.get("trend")) or 0,
                    }
                )
            leagues_payload.append(
                {
                    "league_name": _require_non_empty_string(league.get("leagueName"), f"leagueBuilds[{index}].leagueName"),
                    "league_url": league_url,
                    "display_name": listing_meta["display_name"],
                    "source_bucket": listing_meta["source_bucket"],
                    "status_code": _optional_int(league.get("status")) or 0,
                    "total_characters": _optional_int(league.get("total")) or 0,
                    "top_archetypes": top_archetypes,
                    "search_page_url": _build_search_page_url(
                        league_url,
                        snapshot_type="exp",
                        filters=[],
                        time_machine=None,
                    ),
                    "snapshot_candidates": [snapshot.to_dict() for snapshot in snapshot_versions.get(league_url, [])],
                }
            )

        for league_url, listing_meta in {**build_leagues, **old_build_leagues}.items():
            if league_url in seen_league_urls:
                continue
            leagues_payload.append(
                {
                    "league_name": listing_meta["display_name"],
                    "league_url": league_url,
                    "display_name": listing_meta["display_name"],
                    "source_bucket": listing_meta["source_bucket"],
                    "status_code": 0,
                    "total_characters": 0,
                    "top_archetypes": [],
                    "search_page_url": _build_search_page_url(
                        league_url,
                        snapshot_type="exp",
                        filters=[],
                        time_machine=None,
                    ),
                    "snapshot_candidates": [snapshot.to_dict() for snapshot in snapshot_versions.get(league_url, [])],
                }
            )

        return {
            "schema_version": POE_NINJA_SCHEMA_VERSION,
            "record_kind": POE_NINJA_BUILD_LISTING_RECORD_KIND,
            "source": _source_surface("build_listing"),
            "leagues": leagues_payload,
            "freshness": _build_freshness_payload((index_state_response, build_index_response)),
            "provenance": _build_provenance_payload(
                (index_state_response, build_index_response),
                notes=(
                    "Listing surface merges routing metadata from index-state with league totals and top archetypes from build-index-state.",
                ),
            ),
        }

    def fetch_build_page(
        self,
        league_url: str,
        *,
        snapshot_type: str = "exp",
        filters: Mapping[str, str | Sequence[str]] | None = None,
        time_machine: str | None = None,
        result_limit: int = MAX_BUILD_PAGE_RESULTS,
    ) -> dict[str, Any]:
        league_url = _require_non_empty_string(league_url, "league_url")
        snapshot_type = _require_non_empty_string(snapshot_type, "snapshot_type")
        if result_limit < 1 or result_limit > MAX_BUILD_PAGE_RESULTS:
            raise PoENinjaContractError(f"result_limit must stay within 1..{MAX_BUILD_PAGE_RESULTS}.")

        normalized_filters = _normalize_filter_values(filters)
        index_state_response = self._fetch_response(POE_NINJA_INDEX_STATE_URL, accept="application/json")
        index_state = _require_mapping(index_state_response.json(), "index_state")
        snapshot = self._resolve_snapshot(index_state, league_url, snapshot_type)
        if time_machine is not None and time_machine not in snapshot.time_machine_labels:
            raise PoENinjaContractError(
                f"time_machine {time_machine!r} is not available for snapshot {snapshot.snapshot_name}."
            )

        requested_page_url = _build_search_page_url(
            league_url,
            snapshot_type=snapshot.snapshot_type,
            filters=normalized_filters,
            time_machine=time_machine,
        )
        page_response = self._fetch_response(requested_page_url, accept="text/html")
        search_response = self._fetch_response(
            _build_search_api_url(snapshot, filters=normalized_filters, time_machine=time_machine),
            accept="application/x-protobuf",
        )
        search_result = _decode_search_result(search_response.body)

        dictionary_responses: list[UpstreamResponse] = []
        dictionaries_by_id: dict[str, dict[str, Any]] = {}
        fetched_dictionaries: dict[str, tuple[dict[str, Any], UpstreamResponse]] = {}
        for dictionary_ref in search_result["dictionaries"]:
            cached_dictionary = fetched_dictionaries.get(dictionary_ref["hash"])
            if cached_dictionary is None:
                dictionary, dictionary_response = self._fetch_dictionary(dictionary_ref)
                fetched_dictionaries[dictionary_ref["hash"]] = (dictionary, dictionary_response)
                dictionary_responses.append(dictionary_response)
            else:
                dictionary, dictionary_response = cached_dictionary
            dictionaries_by_id[dictionary["id"]] = dictionary

        rows = _build_search_rows(
            search_result=search_result,
            dictionaries=dictionaries_by_id,
            league_url=league_url,
            snapshot=snapshot,
            filters=normalized_filters,
            time_machine=time_machine,
            result_limit=result_limit,
        )

        responses: tuple[UpstreamResponse, ...] = (
            index_state_response,
            page_response,
            search_response,
            *dictionary_responses,
        )

        return {
            "schema_version": POE_NINJA_SCHEMA_VERSION,
            "record_kind": POE_NINJA_BUILD_PAGE_RECORD_KIND,
            "source": _source_surface("build_page"),
            "page": _extract_page_metadata(page_response.text(), requested_page_url),
            "snapshot": snapshot.to_dict(),
            "query": {
                "league_url": league_url,
                "snapshot_type": snapshot.snapshot_type,
                "requested_time_machine": time_machine,
                "result_limit": result_limit,
                "filters": [{"key": key, "values": list(values)} for key, values in normalized_filters],
            },
            "fields": search_result["fields"],
            "field_descriptors": search_result["field_descriptors"],
            "default_field_ids": search_result["default_field_ids"],
            "sections": _build_search_sections(search_result, dictionaries_by_id),
            "results": rows,
            "freshness": _build_freshness_payload(responses),
            "provenance": _build_provenance_payload(
                responses,
                notes=(
                    "Search rows are decoded from the public poe.ninja protobuf search surface and resolved against public dictionary endpoints.",
                ),
            ),
        }

    def fetch_build_page_partitions(
        self,
        league_url: str,
        *,
        query_partitions: Sequence[Mapping[str, str | Sequence[str]]],
        base_filters: Mapping[str, str | Sequence[str]] | None = None,
        snapshot_type: str = "exp",
        time_machine: str | None = None,
        result_limit_per_partition: int = MAX_BUILD_PAGE_RESULTS,
        target_result_limit: int = 100,
    ) -> dict[str, Any]:
        league_url = _require_non_empty_string(league_url, "league_url")
        snapshot_type = _require_non_empty_string(snapshot_type, "snapshot_type")
        if result_limit_per_partition < 1 or result_limit_per_partition > MAX_BUILD_PAGE_RESULTS:
            raise PoENinjaContractError(f"result_limit_per_partition must stay within 1..{MAX_BUILD_PAGE_RESULTS}.")
        if target_result_limit < 1 or target_result_limit > 100:
            raise PoENinjaContractError("target_result_limit must stay within 1..100.")
        if not isinstance(query_partitions, Sequence) or isinstance(query_partitions, (str, bytes)):
            raise PoENinjaContractError("query_partitions must be a non-empty sequence of filter mappings.")
        if not query_partitions:
            raise PoENinjaContractError("query_partitions must not be empty.")

        normalized_base_filters = _normalize_filter_values(base_filters)
        base_filter_keys = {key for key, _values in normalized_base_filters}
        rows: list[dict[str, Any]] = []
        partition_results: list[dict[str, Any]] = []
        partition_pages: list[dict[str, Any]] = []
        seen_characters: set[tuple[str, str]] = set()
        duplicate_rows_skipped = 0

        for partition_index, partition_filters in enumerate(query_partitions):
            normalized_partition_filters = _normalize_filter_values(partition_filters)
            for key, _values in normalized_partition_filters:
                if key in base_filter_keys:
                    raise PoENinjaContractError(f"query_partitions[{partition_index}] must not override base filter '{key}'.")
            merged_filters = [*normalized_base_filters, *normalized_partition_filters]
            page = self.fetch_build_page(
                league_url,
                snapshot_type=snapshot_type,
                filters={key: list(values) if len(values) > 1 else values[0] for key, values in merged_filters},
                time_machine=time_machine,
                result_limit=result_limit_per_partition,
            )
            partition_pages.append(page)

            accepted_rows = 0
            partition_duplicates = 0
            for row in page["results"]:
                character = _require_mapping(row.get("character"), "build_page.results[].character")
                identity = (
                    _require_non_empty_string(character.get("account"), "build_page.results[].character.account"),
                    _require_non_empty_string(character.get("name"), "build_page.results[].character.name"),
                )
                if identity in seen_characters:
                    duplicate_rows_skipped += 1
                    partition_duplicates += 1
                    continue
                seen_characters.add(identity)
                rows.append(row)
                accepted_rows += 1
                if len(rows) >= target_result_limit:
                    break

            partition_results.append(
                {
                    "partition_index": partition_index,
                    "filters": page["query"]["filters"],
                    "decoded_rows": len(page["results"]),
                    "accepted_rows": accepted_rows,
                    "duplicate_rows_skipped": partition_duplicates,
                    "search_api_url": next(
                        item["url"]
                        for item in page["provenance"]["inputs"]
                        if "/api/builds/" in item["url"] and item["url"].endswith("/search") is False
                    ),
                }
            )
            if len(rows) >= target_result_limit:
                break

        return {
            "schema_version": POE_NINJA_SCHEMA_VERSION,
            "record_kind": POE_NINJA_BUILD_PAGE_PARTITIONED_RECORD_KIND,
            "source": _source_surface("build_page"),
            "page": {
                "requested_url": _require_non_empty_string(
                    _require_mapping(partition_pages[0].get("page"), "partition_pages[0].page").get("requested_url"),
                    "partition_pages[0].page.requested_url",
                ),
                "partitioned_requested_urls": [
                    _require_non_empty_string(
                        _require_mapping(page.get("page"), f"partition_pages[{index}].page").get("requested_url"),
                        f"partition_pages[{index}].page.requested_url",
                    )
                    for index, page in enumerate(partition_pages)
                ],
            },
            "query": {
                "league_url": league_url,
                "snapshot_type": snapshot_type,
                "requested_time_machine": time_machine,
                "result_limit_per_partition": result_limit_per_partition,
                "target_result_limit": target_result_limit,
                "filters": [{"key": key, "values": list(values)} for key, values in normalized_base_filters],
                "base_filters": [{"key": key, "values": list(values)} for key, values in normalized_base_filters],
                "partition_count_attempted": len(partition_results),
            },
            "partition_results": partition_results,
            "results": rows,
            "counts": {
                "accepted_rows": len(rows),
                "duplicate_rows_skipped": duplicate_rows_skipped,
            },
            "freshness": {
                "retrieved_at": max(
                    _require_non_empty_string(
                        _require_mapping(page.get("freshness"), f"partition_pages[{index}].freshness").get("retrieved_at"),
                        f"partition_pages[{index}].freshness.retrieved_at",
                    )
                    for index, page in enumerate(partition_pages)
                ),
                "resources": [
                    resource
                    for page in partition_pages
                    for resource in _require_list(
                        _require_mapping(page.get("freshness"), "partition_page.freshness").get("resources"),
                        "partition_page.freshness.resources",
                    )
                ],
                "observed_data_timestamps": sorted(
                    {
                        _require_non_empty_string(timestamp, "partition_page.freshness.observed_data_timestamps[]")
                        for page in partition_pages
                        for timestamp in _require_list(
                            _require_mapping(page.get("freshness"), "partition_page.freshness").get("observed_data_timestamps"),
                            "partition_page.freshness.observed_data_timestamps",
                        )
                    }
                ),
            },
            "provenance": {
                "generator": POE_NINJA_GENERATOR,
                "upstream_system": POE_NINJA_UPSTREAM_SYSTEM,
                "inputs": [
                    source_input
                    for page in partition_pages
                    for source_input in _require_list(
                        _require_mapping(page.get("provenance"), "partition_page.provenance").get("inputs"),
                        "partition_page.provenance.inputs",
                    )
                ],
                "notes": [
                    "Partitioned build rows come from repeated accepted fetch_build_page calls with explicit filter partitions and character de-duplication."
                ],
            },
        }

    def fetch_character_profile(
        self,
        league_url: str,
        *,
        account: str,
        name: str,
        snapshot_type: str = "exp",
        time_machine: str | None = None,
    ) -> dict[str, Any]:
        league_url = _require_non_empty_string(league_url, "league_url")
        account = _require_non_empty_string(account, "account")
        name = _require_non_empty_string(name, "name")
        snapshot_type = _require_non_empty_string(snapshot_type, "snapshot_type")

        index_state_response = self._fetch_response(POE_NINJA_INDEX_STATE_URL, accept="application/json")
        index_state = _require_mapping(index_state_response.json(), "index_state")
        snapshot = self._resolve_snapshot(index_state, league_url, snapshot_type)
        if time_machine is not None and time_machine not in snapshot.time_machine_labels:
            raise PoENinjaContractError(
                f"time_machine {time_machine!r} is not available for snapshot {snapshot.snapshot_name}."
            )

        character_api_url = _build_character_api_url(snapshot, account=account, name=name, time_machine=time_machine)
        character_response = self._fetch_response(character_api_url, accept="application/json")
        profile = _require_mapping(character_response.json(), "character_profile")

        defensive_stats = _require_mapping(profile.get("defensiveStats", {}), "character_profile.defensiveStats")
        observed_timestamps = [
            timestamp
            for timestamp in (
                _optional_string(profile.get("lastSeenUtc")),
                _optional_string(profile.get("updatedUtc")),
                _optional_string(profile.get("lastCheckedUtc")),
            )
            if timestamp is not None
        ]

        return {
            "schema_version": POE_NINJA_SCHEMA_VERSION,
            "record_kind": POE_NINJA_CHARACTER_PROFILE_RECORD_KIND,
            "source": _source_surface("character_profile"),
            "identity": {
                "account": _require_non_empty_string(profile.get("account"), "character_profile.account"),
                "name": _require_non_empty_string(profile.get("name"), "character_profile.name"),
                "league": _require_non_empty_string(profile.get("league"), "character_profile.league"),
                "base_class": _optional_string(profile.get("baseClass")),
                "ascendancy_class_name": _optional_string(profile.get("ascendancyClassName")),
                "secondary_ascendancy_class_name": _optional_string(profile.get("secondaryAscendancyClassName")),
            },
            "page": {
                "requested_url": _build_character_page_url(
                    league_url,
                    account=account,
                    name=name,
                    snapshot_type=snapshot.snapshot_type,
                    filters=[],
                    time_machine=time_machine,
                    page_index=None,
                ),
                "api_url": character_api_url,
                "league_url": league_url,
                "snapshot_type": snapshot.snapshot_type,
                "requested_time_machine": time_machine,
            },
            "timestamps": {
                "last_seen_utc": _optional_string(profile.get("lastSeenUtc")),
                "updated_utc": _optional_string(profile.get("updatedUtc")),
                "last_checked_utc": _optional_string(profile.get("lastCheckedUtc")),
                "status_code": _optional_int(profile.get("status")) or 0,
                "time_machine_labels": [
                    _require_non_empty_string(item, "tmz[]")
                    for item in (character_response.headers.get("tmz", "").split(",") if character_response.headers.get("tmz") else [])
                    if item
                ],
                "profile_visible": character_response.headers.get("profile-visible") == "true",
            },
            "snapshot": snapshot.to_dict(),
            "defensive_summary": {
                "life": _optional_int(defensive_stats.get("life")) or 0,
                "energy_shield": _optional_int(defensive_stats.get("energyShield")) or 0,
                "mana": _optional_int(defensive_stats.get("mana")) or 0,
                "ward": _optional_int(defensive_stats.get("ward")) or 0,
                "movement_speed": _optional_int(defensive_stats.get("movementSpeed")) or 0,
                "effective_health_pool": _optional_int(defensive_stats.get("effectiveHealthPool")) or 0,
                "lowest_maximum_hit_taken": _optional_int(defensive_stats.get("lowestMaximumHitTaken")) or 0,
                "resistances": {
                    "fire": _optional_int(defensive_stats.get("fireResistance")) or 0,
                    "cold": _optional_int(defensive_stats.get("coldResistance")) or 0,
                    "lightning": _optional_int(defensive_stats.get("lightningResistance")) or 0,
                    "chaos": _optional_int(defensive_stats.get("chaosResistance")) or 0,
                },
                "block": {
                    "attack": _optional_int(defensive_stats.get("blockChance")) or 0,
                    "spell": _optional_int(defensive_stats.get("spellBlockChance")) or 0,
                },
                "charges": {
                    "endurance": _optional_int(defensive_stats.get("enduranceCharges")) or 0,
                    "frenzy": _optional_int(defensive_stats.get("frenzyCharges")) or 0,
                    "power": _optional_int(defensive_stats.get("powerCharges")) or 0,
                },
            },
            "skill_groups": _normalize_skill_groups(profile),
            "equipment": [
                _normalize_item_summary(_require_mapping(item, f"character_profile.items[{index}]"))
                for index, item in enumerate(_require_list(profile.get("items", []), "character_profile.items"))
            ],
            "flasks": [
                _normalize_item_summary(_require_mapping(item, f"character_profile.flasks[{index}]"))
                for index, item in enumerate(_require_list(profile.get("flasks", []), "character_profile.flasks"))
            ],
            "jewels": [
                _normalize_item_summary(_require_mapping(item, f"character_profile.jewels[{index}]"))
                for index, item in enumerate(_require_list(profile.get("jewels", []), "character_profile.jewels"))
            ],
            "passives": {
                "passive_tree_name": _optional_string(profile.get("passiveTreeName")),
                "atlas_tree_name": _optional_string(profile.get("atlasTreeName")),
                "passive_selection_ids": [
                    _optional_int(value) or 0
                    for value in _require_list(profile.get("passiveSelection", []), "character_profile.passiveSelection")
                ],
                "keystone_names": [
                    _require_non_empty_string(
                        _require_mapping(item, f"character_profile.keyStones[{index}]").get("name"),
                        f"character_profile.keyStones[{index}].name",
                    )
                    for index, item in enumerate(_require_list(profile.get("keyStones", []), "character_profile.keyStones"))
                ],
                "mastery_names": [
                    mastery_name
                    for index, value in enumerate(_require_list(profile.get("masteries", []), "character_profile.masteries"))
                    if (mastery_name := _normalize_mastery_name(value, f"character_profile.masteries[{index}]")) is not None
                ],
                "hashes_ex": [
                    hash_value
                    for index, value in enumerate(_require_list(profile.get("hashesEx", []), "character_profile.hashesEx"))
                    if (hash_value := _normalize_hash_ex_value(value, f"character_profile.hashesEx[{index}]")) is not None
                ],
            },
            "loadout_features": {
                "bandit_choice": _optional_string(profile.get("banditChoice")),
                "pantheon_major": _optional_string(profile.get("pantheonMajor")),
                "pantheon_minor": _optional_string(profile.get("pantheonMinor")),
                "use_second_weapon_set": bool(profile.get("useSecondWeaponSet", False)),
            },
            "freshness": _build_freshness_payload(
                (index_state_response, character_response),
                observed_data_timestamps=observed_timestamps,
            ),
            "provenance": _build_provenance_payload(
                (index_state_response, character_response),
                notes=(
                    "Character profile data is taken from the public poe.ninja JSON character endpoint without build quality or ranking logic.",
                ),
            ),
        }

    def _fetch_response(self, url: str, *, accept: str) -> UpstreamResponse:
        request = Request(
            url,
            headers={
                "Accept": accept,
                "User-Agent": self.user_agent,
            },
            method="GET",
        )
        with self._urlopen(request, timeout=self.timeout_seconds) as response:
            status = getattr(response, "status", response.getcode())
            headers = {key.lower(): value for key, value in response.headers.items()}
            body = response.read()
        return UpstreamResponse(
            url=url,
            method="GET",
            status=status,
            headers=headers,
            body=body,
            fetched_at=_utc_now_iso(),
        )

    def _resolve_snapshot(self, index_state: Mapping[str, Any], league_url: str, snapshot_type: str) -> SnapshotVersion:
        for index, raw_snapshot in enumerate(_require_list(index_state.get("snapshotVersions", []), "snapshotVersions")):
            snapshot = SnapshotVersion.from_dict(_require_mapping(raw_snapshot, f"snapshotVersions[{index}]"), f"snapshotVersions[{index}]")
            if snapshot.league_url == league_url and snapshot.snapshot_type == snapshot_type:
                return snapshot
        raise PoENinjaContractError(f"No poe.ninja snapshot version found for league {league_url!r} and type {snapshot_type!r}.")

    def _fetch_dictionary(self, dictionary_ref: Mapping[str, str]) -> tuple[dict[str, Any], UpstreamResponse]:
        dictionary_url = POE_NINJA_DICTIONARY_ENDPOINT_TEMPLATE.format(hash_value=quote(dictionary_ref["hash"], safe=""))
        dictionary_response = self._fetch_response(dictionary_url, accept="application/x-protobuf")
        dictionary = _parse_search_dictionary(dictionary_response.body)
        return dictionary, dictionary_response


def load_poe_ninja_build_listing_schema(path: Path = DEFAULT_POE_NINJA_BUILD_LISTING_SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_poe_ninja_build_page_schema(path: Path = DEFAULT_POE_NINJA_BUILD_PAGE_SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_poe_ninja_character_profile_schema(
    path: Path = DEFAULT_POE_NINJA_CHARACTER_PROFILE_SCHEMA_PATH,
) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = [
    "DEFAULT_POE_NINJA_BUILD_LISTING_SCHEMA_PATH",
    "DEFAULT_POE_NINJA_BUILD_PAGE_SCHEMA_PATH",
    "DEFAULT_POE_NINJA_CHARACTER_PROFILE_SCHEMA_PATH",
    "MAX_BUILD_PAGE_RESULTS",
    "POE_NINJA_BUILD_LISTING_RECORD_KIND",
    "POE_NINJA_BUILD_PAGE_RECORD_KIND",
    "POE_NINJA_BUILD_PAGE_PARTITIONED_RECORD_KIND",
    "POE_NINJA_CHARACTER_PROFILE_RECORD_KIND",
    "POE_NINJA_SCHEMA_VERSION",
    "PoENinjaClient",
    "PoENinjaContractError",
    "load_poe_ninja_build_listing_schema",
    "load_poe_ninja_build_page_schema",
    "load_poe_ninja_character_profile_schema",
]
