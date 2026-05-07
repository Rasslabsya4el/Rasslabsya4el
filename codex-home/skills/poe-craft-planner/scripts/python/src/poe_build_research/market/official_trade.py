"""Official trade query and bounded snapshot helpers for agent-first workflows."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import quote
from urllib.request import Request, urlopen

from poe_build_research.market.source_contracts import (
    CANONICAL_SOURCE_CONTRACTS,
    MarketSourceConfig,
    Realm,
    SourceId,
    load_market_source_config,
)
from poe_build_research.market.trade_links import InputProvenanceRef, trade_results_url, trade_search_request_url

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OFFICIAL_TRADE_QUERY_REQUEST_SCHEMA_PATH = (
    PROJECT_ROOT / "schemas" / "market" / "official_trade_query_request.schema.json"
)
DEFAULT_OFFICIAL_TRADE_SNAPSHOT_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "market" / "official_trade_snapshot.schema.json"
OFFICIAL_TRADE_QUERY_REQUEST_VERSION = "1.0.0"
OFFICIAL_TRADE_SNAPSHOT_VERSION = "1.0.0"
OFFICIAL_TRADE_QUERY_RECORD_KIND = "official_trade_query_request"
OFFICIAL_TRADE_SNAPSHOT_RECORD_KIND = "official_trade_snapshot"
OFFICIAL_TRADE_GENERATOR = "poe_build_research.market.official_trade"
OFFICIAL_TRADE_SNAPSHOT_NAMESPACE = "official_trade"
OFFICIAL_TRADE_UPSTREAM_SYSTEM = "official_trade_website"
OFFICIAL_TRADE_FETCH_URL = "https://www.pathofexile.com/api/trade/fetch/{result_ids}?query={search_id}"
MAX_BOUNDED_RESULT_LIMIT = 10
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
TRADE_SOURCE = CANONICAL_SOURCE_CONTRACTS[SourceId.UNDOCUMENTED_TRADE_API]


class OfficialTradeContractError(RuntimeError):
    """Raised when the official-trade request or snapshot contract is violated."""


def _stable_json(payload: Any) -> str:
    try:
        return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise OfficialTradeContractError("Payload contains values that are not stable JSON.") from exc


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso8601(value: str, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OfficialTradeContractError(f"{field_name} must be an ISO 8601 timestamp.") from exc


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OfficialTradeContractError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _optional_non_empty_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, field_name)


def _require_iso8601(value: Any, field_name: str) -> str:
    text = _require_non_empty_string(value, field_name)
    _parse_iso8601(text, field_name)
    return text


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OfficialTradeContractError(f"{field_name} must be an object.")
    return value


def _optional_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    return _require_mapping(value, field_name)


def _require_int(value: Any, field_name: str, *, minimum: int | None = None, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise OfficialTradeContractError(f"{field_name} must be an integer.")
    if minimum is not None and value < minimum:
        raise OfficialTradeContractError(f"{field_name} must be >= {minimum}.")
    if maximum is not None and value > maximum:
        raise OfficialTradeContractError(f"{field_name} must be <= {maximum}.")
    return value


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    return _require_int(value, field_name)


def _optional_bool(value: Any, field_name: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise OfficialTradeContractError(f"{field_name} must be a boolean when provided.")
    return value


def _optional_number(value: Any, field_name: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OfficialTradeContractError(f"{field_name} must be numeric when provided.")
    return value


def _require_identifier(value: Any, field_name: str) -> str:
    token = _require_non_empty_string(value, field_name)
    if not REQUEST_ID_PATTERN.fullmatch(token):
        raise OfficialTradeContractError(f"{field_name} must use only letters, numbers, '.', '_' or '-'.")
    return token


def _require_trade_token(value: Any, field_name: str) -> str:
    token = _require_non_empty_string(value, field_name)
    if any(char in token for char in ("/", "\\", ",", "?", "&", "#")):
        raise OfficialTradeContractError(f"{field_name} must be one trade token without URL separators.")
    return token


def _require_realm(value: Realm | str) -> Realm:
    if isinstance(value, Realm):
        return value
    try:
        return Realm(_require_non_empty_string(value, "realm"))
    except ValueError as exc:
        raise OfficialTradeContractError("realm must be one of: pc, xbox, sony.") from exc


def _normalize_trade_query(value: Mapping[str, Any]) -> dict[str, Any]:
    query = _require_mapping(value, "trade_query")
    _require_mapping(query.get("query"), "trade_query.query")
    _require_mapping(query.get("sort"), "trade_query.sort")
    return json.loads(_stable_json(query))


def _normalize_provenance_refs(
    value: tuple[InputProvenanceRef, ...] | list[InputProvenanceRef],
) -> tuple[InputProvenanceRef, ...]:
    refs = tuple(value)
    for index, item in enumerate(refs):
        if not isinstance(item, InputProvenanceRef):
            raise OfficialTradeContractError(f"provenance_refs[{index}] must be an InputProvenanceRef.")
    return refs


def _source_surface() -> dict[str, Any]:
    return {
        "source_id": TRADE_SOURCE.source_id.value,
        "support_level": TRADE_SOURCE.support_level.value,
        "authority_rank": TRADE_SOURCE.authority_rank,
        "role": TRADE_SOURCE.allowed_roles[0].value,
        "hard_requirement": TRADE_SOURCE.hard_requirement,
        "oauth_required": TRADE_SOURCE.oauth.required,
    }


def _timestamp_token(value: str) -> str:
    return _parse_iso8601(value, "captured_at").astimezone(timezone.utc).strftime("%Y%m%dt%H%M%Sz").lower()


def _project_relative_path(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False)).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def official_trade_fetch_url(search_id: str, result_ids: tuple[str, ...]) -> str:
    safe_search_id = quote(_require_trade_token(search_id, "search_id"), safe="")
    safe_result_ids = ",".join(quote(_require_trade_token(result_id, "result_ids[]"), safe="") for result_id in result_ids)
    return OFFICIAL_TRADE_FETCH_URL.format(result_ids=safe_result_ids, search_id=safe_search_id)


def official_trade_snapshot_partition_root(
    config: MarketSourceConfig,
    realm: Realm | str | None,
    league: str,
) -> Path:
    validated_realm = realm or config.selection.default_realm
    raw_partition = config.raw_partition_root(SourceId.OFFICIAL_PUBLIC_STASHES, validated_realm, league)
    relative_partition = raw_partition.relative_to(config.storage.raw_root / SourceId.OFFICIAL_PUBLIC_STASHES.value)
    storage_root = config.storage.snapshot_root / OFFICIAL_TRADE_SNAPSHOT_NAMESPACE
    partition_root = storage_root / relative_partition
    resolved_root = storage_root.resolve(strict=False)
    resolved_partition = partition_root.resolve(strict=False)
    if not resolved_partition.is_relative_to(resolved_root):
        raise OfficialTradeContractError(f"league must stay within {resolved_root}.")
    return partition_root


def official_trade_snapshot_artifact_path(
    config: MarketSourceConfig,
    realm: Realm | str | None,
    league: str,
    snapshot_id: str,
) -> Path:
    filename = _require_identifier(snapshot_id, "snapshot_id")
    return official_trade_snapshot_partition_root(config, realm, league) / f"{filename}.json"


def write_official_trade_snapshot(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload), encoding="utf-8", newline="\n")
    return path


def _normalize_online_status(value: Any, field_name: str) -> bool | None:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, Mapping):
        return True
    raise OfficialTradeContractError(f"{field_name} must be null, a boolean, or an object.")


def _build_snapshot_id(request_id: str, captured_at: str, search_id: str) -> str:
    digest = hashlib.sha256(f"{request_id}\n{captured_at}\n{search_id}".encode("utf-8")).hexdigest()[:12]
    return f"{request_id}.{_timestamp_token(captured_at)}.{digest}"


def _normalize_search_response(payload: Mapping[str, Any], result_limit: int) -> tuple[str, int, tuple[str, ...]]:
    search_id = _require_trade_token(payload.get("id"), "search_response.id")
    raw_result_ids = payload.get("result")
    if not isinstance(raw_result_ids, list):
        raise OfficialTradeContractError("search_response.result must be an array.")
    result_ids = tuple(_require_trade_token(item, f"search_response.result[{index}]") for index, item in enumerate(raw_result_ids))
    total_result_count = payload.get("total", len(result_ids))
    if total_result_count is None:
        total_result_count = len(result_ids)
    total = _require_int(total_result_count, "search_response.total", minimum=0)
    return search_id, total, result_ids[:result_limit]


def _normalize_listing(result_id: str, position: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    listing = _optional_mapping(payload.get("listing"), f"fetch_response.result[{result_id}].listing")
    account = _optional_mapping(listing.get("account"), f"fetch_response.result[{result_id}].listing.account")
    price = _optional_mapping(listing.get("price"), f"fetch_response.result[{result_id}].listing.price")
    item = _require_mapping(payload.get("item"), f"fetch_response.result[{result_id}].item")

    indexed_at = _optional_non_empty_string(listing.get("indexed"), f"fetch_response.result[{result_id}].listing.indexed")
    if indexed_at is not None:
        _parse_iso8601(indexed_at, f"fetch_response.result[{result_id}].listing.indexed")

    return {
        "result_id": result_id,
        "position": position,
        "indexed_at": indexed_at,
        "seller": {
            "account_name": _optional_non_empty_string(
                account.get("name"),
                f"fetch_response.result[{result_id}].listing.account.name",
            ),
            "last_character_name": _optional_non_empty_string(
                account.get("lastCharacterName"),
                f"fetch_response.result[{result_id}].listing.account.lastCharacterName",
            ),
            "is_online": _normalize_online_status(
                account.get("online"),
                f"fetch_response.result[{result_id}].listing.account.online",
            ),
        },
        "price": {
            "amount": _optional_number(price.get("amount"), f"fetch_response.result[{result_id}].listing.price.amount"),
            "currency": _optional_non_empty_string(
                price.get("currency"),
                f"fetch_response.result[{result_id}].listing.price.currency",
            ),
            "type": _optional_non_empty_string(price.get("type"), f"fetch_response.result[{result_id}].listing.price.type"),
            "listed_note": _optional_non_empty_string(item.get("note"), f"fetch_response.result[{result_id}].item.note"),
        },
        "item": {
            "item_id": _optional_non_empty_string(item.get("id"), f"fetch_response.result[{result_id}].item.id"),
            "name": _optional_non_empty_string(item.get("name"), f"fetch_response.result[{result_id}].item.name"),
            "type_line": _optional_non_empty_string(item.get("typeLine"), f"fetch_response.result[{result_id}].item.typeLine"),
            "base_type": _optional_non_empty_string(item.get("baseType"), f"fetch_response.result[{result_id}].item.baseType"),
            "item_level": _optional_int(item.get("ilvl"), f"fetch_response.result[{result_id}].item.ilvl"),
            "identified": _optional_bool(item.get("identified"), f"fetch_response.result[{result_id}].item.identified"),
            "corrupted": _optional_bool(item.get("corrupted"), f"fetch_response.result[{result_id}].item.corrupted"),
            "stack_size": _optional_int(item.get("stackSize"), f"fetch_response.result[{result_id}].item.stackSize"),
            "icon": _optional_non_empty_string(item.get("icon"), f"fetch_response.result[{result_id}].item.icon"),
        },
    }


def _normalize_fetch_results(selected_result_ids: tuple[str, ...], payload: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    rows = payload.get("result")
    if not isinstance(rows, list):
        raise OfficialTradeContractError("fetch_response.result must be an array.")

    fetched_by_id: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(rows):
        row_mapping = _require_mapping(row, f"fetch_response.result[{index}]")
        result_id = _require_trade_token(row_mapping.get("id"), f"fetch_response.result[{index}].id")
        fetched_by_id[result_id] = row_mapping

    normalized_rows: list[dict[str, Any]] = []
    missing_result_ids: list[str] = []
    for position, result_id in enumerate(selected_result_ids, start=1):
        row = fetched_by_id.get(result_id)
        if row is None:
            missing_result_ids.append(result_id)
            continue
        normalized_rows.append(_normalize_listing(result_id, position, row))
    return normalized_rows, missing_result_ids


def _build_freshness_payload(
    *,
    config: MarketSourceConfig,
    captured_at: str,
    listings: list[dict[str, Any]],
) -> dict[str, Any]:
    captured_at_dt = _parse_iso8601(captured_at, "captured_at")
    indexed_rows: list[tuple[str, int]] = []
    for listing in listings:
        indexed_at = listing["indexed_at"]
        if indexed_at is None:
            continue
        indexed_dt = _parse_iso8601(indexed_at, "listing.indexed_at")
        age_seconds = int((captured_at_dt - indexed_dt).total_seconds())
        if age_seconds < -config.freshness.clock_skew_tolerance_seconds:
            raise OfficialTradeContractError("listing.indexed_at must not be materially in the future.")
        indexed_rows.append((indexed_at, max(age_seconds, 0)))

    if not indexed_rows:
        return {
            "captured_at": captured_at,
            "status": "unknown",
            "fresh_within_seconds": config.freshness.fresh_within_seconds,
            "stale_after_seconds": config.freshness.stale_after_seconds,
            "clock_skew_tolerance_seconds": config.freshness.clock_skew_tolerance_seconds,
            "oldest_listing_indexed_at": None,
            "newest_listing_indexed_at": None,
            "max_listing_age_seconds": None,
            "min_listing_age_seconds": None,
            "note": "No indexed listing timestamps were returned by the official trade snapshot.",
        }

    max_listing_age_seconds = max(age_seconds for _, age_seconds in indexed_rows)
    min_listing_age_seconds = min(age_seconds for _, age_seconds in indexed_rows)
    if max_listing_age_seconds <= config.freshness.fresh_within_seconds:
        status = "fresh"
    elif max_listing_age_seconds <= config.freshness.stale_after_seconds:
        status = "aging"
    else:
        status = "stale"

    ordered_timestamps = [timestamp for timestamp, _ in indexed_rows]
    return {
        "captured_at": captured_at,
        "status": status,
        "fresh_within_seconds": config.freshness.fresh_within_seconds,
        "stale_after_seconds": config.freshness.stale_after_seconds,
        "clock_skew_tolerance_seconds": config.freshness.clock_skew_tolerance_seconds,
        "oldest_listing_indexed_at": min(ordered_timestamps),
        "newest_listing_indexed_at": max(ordered_timestamps),
        "max_listing_age_seconds": max_listing_age_seconds,
        "min_listing_age_seconds": min_listing_age_seconds,
        "note": "Freshness is derived from official trade listing indexed timestamps relative to snapshot capture time.",
    }


@dataclass(frozen=True, slots=True)
class OfficialTradeQueryRequest:
    """Structured request surface for one bounded official-trade query."""

    request_id: str
    label: str
    league: str
    trade_query: Mapping[str, Any]
    requested_at: str
    realm: Realm | str = Realm.PC
    result_limit: int = 10
    provenance_refs: tuple[InputProvenanceRef, ...] = ()
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _require_identifier(self.request_id, "request_id"))
        object.__setattr__(self, "label", _require_non_empty_string(self.label, "label"))
        object.__setattr__(self, "realm", _require_realm(self.realm))
        object.__setattr__(self, "league", _require_non_empty_string(self.league, "league"))
        object.__setattr__(self, "requested_at", _require_iso8601(self.requested_at, "requested_at"))
        object.__setattr__(
            self,
            "result_limit",
            _require_int(self.result_limit, "result_limit", minimum=1, maximum=MAX_BOUNDED_RESULT_LIMIT),
        )
        object.__setattr__(self, "trade_query", _normalize_trade_query(self.trade_query))
        object.__setattr__(self, "provenance_refs", _normalize_provenance_refs(self.provenance_refs))
        if self.note is not None:
            object.__setattr__(self, "note", _require_non_empty_string(self.note, "note"))

    @property
    def query_sha256(self) -> str:
        return _sha256_json(self.trade_query)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OFFICIAL_TRADE_QUERY_REQUEST_VERSION,
            "record_kind": OFFICIAL_TRADE_QUERY_RECORD_KIND,
            "request_id": self.request_id,
            "label": self.label,
            "realm": self.realm.value,
            "league": self.league,
            "requested_at": self.requested_at,
            "result_limit": self.result_limit,
            "source": _source_surface(),
            "trade_query": self.trade_query,
            "provenance": {
                "generator": OFFICIAL_TRADE_GENERATOR,
                "submission_url": trade_search_request_url(self.league),
                "query_sha256": self.query_sha256,
                "input_provenance": [ref.to_dict() for ref in self.provenance_refs],
            },
            "note": self.note,
        }

    def to_json(self) -> str:
        return _stable_json(self.to_dict())


@dataclass(frozen=True, slots=True)
class OfficialTradeSnapshot:
    """Persisted bounded snapshot of one official-trade query."""

    artifact_path: Path
    payload: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(_stable_json(self.payload))

    def to_json(self) -> str:
        return _stable_json(self.payload)


class OfficialTradeSnapshotClient:
    """Thin wrapper for official-trade query capture without build-decision logic."""

    def __init__(
        self,
        *,
        config: MarketSourceConfig | None = None,
        urlopen_fn: Callable[..., Any] = urlopen,
        user_agent: str = "poe-build-research-official-trade",
    ) -> None:
        self.config = config or load_market_source_config()
        self._urlopen = urlopen_fn
        self.user_agent = _require_non_empty_string(user_agent, "user_agent")

    def capture(
        self,
        request: OfficialTradeQueryRequest,
        *,
        captured_at: str | None = None,
    ) -> OfficialTradeSnapshot:
        snapshot_captured_at = _require_iso8601(captured_at or _utc_now_iso(), "captured_at")
        search_payload = self._submit_search(request)
        search_id, total_result_count, selected_result_ids = _normalize_search_response(search_payload, request.result_limit)

        fetch_payload: Mapping[str, Any] | None = None
        fetch_url: str | None = None
        listings: list[dict[str, Any]] = []
        missing_result_ids: list[str] = []
        if selected_result_ids:
            fetch_url = official_trade_fetch_url(search_id, selected_result_ids)
            fetch_payload = self._fetch_results(fetch_url)
            listings, missing_result_ids = _normalize_fetch_results(selected_result_ids, fetch_payload)

        snapshot_id = _build_snapshot_id(request.request_id, snapshot_captured_at, search_id)
        artifact_path = official_trade_snapshot_artifact_path(self.config, request.realm, request.league, snapshot_id)
        storage_root = self.config.storage.snapshot_root / OFFICIAL_TRADE_SNAPSHOT_NAMESPACE
        payload = {
            "schema_version": OFFICIAL_TRADE_SNAPSHOT_VERSION,
            "record_kind": OFFICIAL_TRADE_SNAPSHOT_RECORD_KIND,
            "snapshot_id": snapshot_id,
            "request_id": request.request_id,
            "label": request.label,
            "realm": request.realm.value,
            "league": request.league,
            "requested_at": request.requested_at,
            "captured_at": snapshot_captured_at,
            "result_limit": request.result_limit,
            "storage": {
                "tier": "dynamic_knowledge",
                "root": _project_relative_path(storage_root),
                "path": _project_relative_path(artifact_path),
                "git_tracked": False,
            },
            "source": _source_surface(),
            "trade_query": request.trade_query,
            "search": {
                "search_id": search_id,
                "total_result_count": total_result_count,
                "requested_result_limit": request.result_limit,
                "selected_result_ids": list(selected_result_ids),
                "missing_result_ids": missing_result_ids,
                "returned_result_count": len(listings),
                "bounded": True,
                "selection_strategy": "first_n_by_official_sort",
            },
            "listings": listings,
            "links": {
                "search_submission_url": trade_search_request_url(request.league),
                "results_url": trade_results_url(request.league, search_id),
                "fetch_url": fetch_url,
            },
            "freshness": _build_freshness_payload(
                config=self.config,
                captured_at=snapshot_captured_at,
                listings=listings,
            ),
            "provenance": {
                "generator": OFFICIAL_TRADE_GENERATOR,
                "upstream_system": OFFICIAL_TRADE_UPSTREAM_SYSTEM,
                "query_sha256": request.query_sha256,
                "search_response_sha256": _sha256_json(search_payload),
                "fetch_response_sha256": _sha256_json(fetch_payload) if fetch_payload is not None else None,
                "input_provenance": [ref.to_dict() for ref in request.provenance_refs],
            },
            "limitations": [
                f"Bounded to the first {request.result_limit} official trade results returned by the search sort order.",
                "This surface captures listings only and does not make pricing, upgrade, or craft decisions.",
            ],
        }
        write_official_trade_snapshot(artifact_path, payload)
        return OfficialTradeSnapshot(artifact_path=artifact_path, payload=payload)

    def _submit_search(self, request: OfficialTradeQueryRequest) -> Mapping[str, Any]:
        search_request = Request(
            trade_search_request_url(request.league),
            data=_stable_json(request.trade_query).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
            },
            method="POST",
        )
        with self._urlopen(search_request, timeout=30) as response:
            payload = json.load(response)
        return _require_mapping(payload, "search_response")

    def _fetch_results(self, fetch_url: str) -> Mapping[str, Any]:
        fetch_request = Request(
            fetch_url,
            headers={
                "Accept": "application/json",
                "User-Agent": self.user_agent,
            },
            method="GET",
        )
        with self._urlopen(fetch_request, timeout=30) as response:
            payload = json.load(response)
        return _require_mapping(payload, "fetch_response")


def load_official_trade_query_request_schema(
    path: Path = DEFAULT_OFFICIAL_TRADE_QUERY_REQUEST_SCHEMA_PATH,
) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_official_trade_snapshot_schema(path: Path = DEFAULT_OFFICIAL_TRADE_SNAPSHOT_SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = [
    "DEFAULT_OFFICIAL_TRADE_QUERY_REQUEST_SCHEMA_PATH",
    "DEFAULT_OFFICIAL_TRADE_SNAPSHOT_SCHEMA_PATH",
    "MAX_BOUNDED_RESULT_LIMIT",
    "OFFICIAL_TRADE_QUERY_RECORD_KIND",
    "OFFICIAL_TRADE_QUERY_REQUEST_VERSION",
    "OFFICIAL_TRADE_SNAPSHOT_RECORD_KIND",
    "OFFICIAL_TRADE_SNAPSHOT_VERSION",
    "OfficialTradeContractError",
    "OfficialTradeQueryRequest",
    "OfficialTradeSnapshot",
    "OfficialTradeSnapshotClient",
    "load_official_trade_query_request_schema",
    "load_official_trade_snapshot_schema",
    "official_trade_fetch_url",
    "official_trade_snapshot_artifact_path",
    "official_trade_snapshot_partition_root",
    "write_official_trade_snapshot",
]
