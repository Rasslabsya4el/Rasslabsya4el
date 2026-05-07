"""Snapshot aggregation for windowed market budget outputs."""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from poe_build_research.market.normalize import (
    MarketNormalizationError,
    build_window_currency_context,
    describe_listing_item,
    normalized_partition_root,
    normalize_listing_price,
)
from poe_build_research.market.source_contracts import MarketSourceConfig, Realm

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_SCHEMA_VERSION = "1.0.0"
SNAPSHOT_RECORD_KIND = "market_snapshot"


class SnapshotContractError(RuntimeError):
    """Raised when listings cannot be aggregated into the snapshot contract."""


def _parse_iso8601(value: str, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SnapshotContractError(f"{field_name} must be an ISO 8601 timestamp.") from exc


def _coerce_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SnapshotContractError(f"{field_name} must be an object.")
    return value


def _coerce_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SnapshotContractError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _coerce_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise SnapshotContractError(f"{field_name} must be a boolean.")
    return value


def _coerce_int(value: Any, field_name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SnapshotContractError(f"{field_name} must be an integer.")
    if minimum is not None and value < minimum:
        raise SnapshotContractError(f"{field_name} must be >= {minimum}.")
    return value


def _status_rank(status: str) -> int:
    ranking = {"fresh": 0, "delayed": 1, "stale": 2, "bootstrap": 3}
    if status not in ranking:
        raise SnapshotContractError(f"Unsupported freshness status '{status}'.")
    return ranking[status]


def snapshot_partition_root(config: MarketSourceConfig, realm: Realm | str | None, league: str) -> Path:
    """Return the safe snapshot-output partition for one realm and league."""

    normalized_root = normalized_partition_root(config, realm, league)
    relative_partition = normalized_root.relative_to(config.storage.normalized_root)
    partition_root = config.storage.snapshot_root / relative_partition
    resolved_root = config.storage.snapshot_root.resolve(strict=False)
    resolved_partition = partition_root.resolve(strict=False)
    if not resolved_partition.is_relative_to(resolved_root):
        raise SnapshotContractError(f"league must stay within {resolved_root}.")
    return partition_root


def snapshot_artifact_path(
    config: MarketSourceConfig,
    realm: Realm | str | None,
    league: str,
    snapshot_id: str,
) -> Path:
    """Return the stable artifact path for a persisted snapshot window bundle."""

    filename = _coerce_non_empty_string(snapshot_id, "snapshot_id")
    if "/" in filename or "\\" in filename:
        raise SnapshotContractError("snapshot_id must not contain path separators.")
    if not filename.replace(".", "").replace("_", "").replace("-", "").isalnum():
        raise SnapshotContractError("snapshot_id must be filename-safe.")
    return snapshot_partition_root(config, realm, league) / f"{filename}.json"


def build_snapshot_artifact(
    listings: Iterable[Mapping[str, Any]],
    *,
    config: MarketSourceConfig,
    league_start_at: str,
    generated_at: str,
) -> dict[str, Any]:
    """Aggregate supported raw listings into the windowed market snapshot contract."""

    generated_at_dt = _parse_iso8601(generated_at, "generated_at")
    league_start_dt = _parse_iso8601(league_start_at, "league_start_at")

    materialized_listings = tuple(listings)
    if not materialized_listings:
        raise SnapshotContractError("At least one listing is required to build a snapshot artifact.")

    first_realm = _coerce_non_empty_string(materialized_listings[0].get("realm"), "listing.realm")
    first_league = _coerce_non_empty_string(materialized_listings[0].get("league"), "listing.league")

    for listing in materialized_listings:
        realm = _coerce_non_empty_string(listing.get("realm"), "listing.realm")
        league = _coerce_non_empty_string(listing.get("league"), "listing.league")
        if realm != first_realm:
            raise SnapshotContractError("All listings in one snapshot artifact must share the same realm.")
        if league != first_league:
            raise SnapshotContractError("All listings in one snapshot artifact must share the same league.")

    windows_payload: dict[str, Any] = {}
    for window_key, window in config.league_windows.items():
        window_listings = tuple(
            listing
            for listing in materialized_listings
            if _listing_is_inside_window(listing, window.start_offset_hours, window.end_offset_hours, league_start_dt)
        )
        windows_payload[window_key] = _build_window_payload(
            window_listings,
            window_key=window_key,
            window_label=window.label,
            start_offset_hours=window.start_offset_hours,
            end_offset_hours=window.end_offset_hours,
        )

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "record_kind": SNAPSHOT_RECORD_KIND,
        "realm": first_realm,
        "league": first_league,
        "league_start_at": league_start_at,
        "generated_at": generated_at_dt.isoformat().replace("+00:00", "Z"),
        "storage": {
            "tier": "dynamic_knowledge",
            "root": _project_relative_path(config.storage.snapshot_root),
            "git_tracked": False,
        },
        "windows": windows_payload,
    }


def write_snapshot_artifact(path: Path, payload: dict[str, Any]) -> Path:
    """Persist one snapshot artifact as stable JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return path


def _project_relative_path(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False)).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _listing_is_inside_window(
    listing: Mapping[str, Any],
    start_offset_hours: int,
    end_offset_hours: int,
    league_start_dt: datetime,
) -> bool:
    observed_at = _parse_iso8601(_coerce_non_empty_string(listing.get("observed_at"), "listing.observed_at"), "listing.observed_at")
    offset_hours = (observed_at - league_start_dt).total_seconds() / 3600
    return start_offset_hours <= offset_hours < end_offset_hours


def _build_window_payload(
    listings: tuple[Mapping[str, Any], ...],
    *,
    window_key: str,
    window_label: str,
    start_offset_hours: int,
    end_offset_hours: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "window_key": window_key,
        "label": window_label,
        "start_offset_hours": start_offset_hours,
        "end_offset_hours": end_offset_hours,
        "listing_count": len(listings),
        "aggregate_count": 0,
        "normalization": None,
        "aggregates": [],
    }
    if not listings:
        return payload

    try:
        currency_context = build_window_currency_context(listings)
    except MarketNormalizationError as exc:
        raise SnapshotContractError(f"{window_key} normalization failed: {exc}") from exc

    grouped: dict[str, list[tuple[Mapping[str, Any], Any, Any]]] = defaultdict(list)
    for listing in listings:
        descriptor = describe_listing_item(listing)
        normalized_price = normalize_listing_price(listing, currency_context, descriptor)
        grouped[descriptor.item_key].append((listing, descriptor, normalized_price))

    aggregates = [
        _build_item_aggregate(window_key=window_key, grouped_rows=grouped_rows)
        for _, grouped_rows in sorted(grouped.items())
    ]
    payload["aggregate_count"] = len(aggregates)
    payload["normalization"] = {
        "chaos_per_divine": currency_context.chaos_per_divine,
        "divine_per_chaos": currency_context.divine_per_chaos,
        "evidence_listing_ids": list(currency_context.evidence_listing_ids),
        "evidence_item_keys": list(currency_context.evidence_item_keys),
    }
    payload["aggregates"] = aggregates
    return payload


def _build_item_aggregate(*, window_key: str, grouped_rows: list[tuple[Mapping[str, Any], Any, Any]]) -> dict[str, Any]:
    first_listing, descriptor, _ = grouped_rows[0]
    unit_chaos_values = [row[2].unit_chaos_value for row in grouped_rows]
    unit_divine_values = [row[2].unit_divine_value for row in grouped_rows]
    listing_ids = sorted(_coerce_non_empty_string(row[0].get("listing_id"), "listing.listing_id") for row in grouped_rows)
    seller_keys = sorted(
        {
            _coerce_non_empty_string(_coerce_mapping(row[0].get("seller"), "listing.seller").get("seller_key"), "listing.seller.seller_key")
            for row in grouped_rows
        }
    )
    observed_at_values = [
        _parse_iso8601(_coerce_non_empty_string(row[0].get("observed_at"), "listing.observed_at"), "listing.observed_at")
        for row in grouped_rows
    ]
    return {
        "item_key": descriptor.item_key,
        "item_name": descriptor.item_name,
        "item_kind": descriptor.item_kind,
        "window_key": window_key,
        "listing_ids": listing_ids,
        "observed_at_range": {
            "first_observed_at": min(observed_at_values).isoformat().replace("+00:00", "Z"),
            "last_observed_at": max(observed_at_values).isoformat().replace("+00:00", "Z"),
        },
        "price": {
            "currency": {
                "quoted": sorted({row[2].quote_currency for row in grouped_rows}),
                "quote_notes": [row[2].listed_note for row in grouped_rows],
            },
            "chaos": _build_numeric_rollup(unit_chaos_values),
            "divine": _build_numeric_rollup(unit_divine_values),
        },
        "budget": {
            "reference_price_chaos": statistics.median(unit_chaos_values),
            "reference_price_divine": statistics.median(unit_divine_values),
            "price_floor_chaos": min(unit_chaos_values),
            "price_ceiling_chaos": max(unit_chaos_values),
        },
        "liquidity": _build_liquidity_payload(len(grouped_rows), len(seller_keys)),
        "freshness": _build_freshness_payload(grouped_rows),
        "provenance": _build_provenance_payload(grouped_rows),
        "sample": {
            "listing_count": len(grouped_rows),
            "seller_count": len(seller_keys),
            "stack_size_max": max(row[2].stack_size for row in grouped_rows),
            "example_listing_id": _coerce_non_empty_string(first_listing.get("listing_id"), "listing.listing_id"),
        },
    }


def _build_numeric_rollup(values: list[float]) -> dict[str, float]:
    return {
        "min": min(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "max": max(values),
    }


def _build_liquidity_payload(listing_count: int, seller_count: int) -> dict[str, Any]:
    sample_size = min(listing_count, seller_count)
    if sample_size >= 5:
        status = "liquid"
    elif sample_size >= 2:
        status = "thin"
    else:
        status = "illiquid"
    return {
        "listing_count": listing_count,
        "seller_count": seller_count,
        "sample_size": sample_size,
        "status": status,
    }


def _build_freshness_payload(grouped_rows: list[tuple[Mapping[str, Any], Any, Any]]) -> dict[str, Any]:
    status_counter: Counter[str] = Counter()
    max_source_lag_seconds = 0
    max_stale_after_seconds = 0
    all_within_sla = True

    for listing, _, _ in grouped_rows:
        freshness = _coerce_mapping(listing.get("freshness"), "listing.freshness")
        status = _coerce_non_empty_string(freshness.get("status"), "listing.freshness.status")
        status_counter[status] += 1
        max_source_lag_seconds = max(
            max_source_lag_seconds,
            _coerce_int(freshness.get("source_lag_seconds"), "listing.freshness.source_lag_seconds", minimum=0),
        )
        max_stale_after_seconds = max(
            max_stale_after_seconds,
            _coerce_int(freshness.get("stale_after_seconds"), "listing.freshness.stale_after_seconds", minimum=1),
        )
        all_within_sla = all_within_sla and _coerce_bool(
            freshness.get("ingested_within_sla"),
            "listing.freshness.ingested_within_sla",
        )

    worst_status = max(status_counter, key=_status_rank)
    return {
        "worst_status": worst_status,
        "status_counts": {key: status_counter.get(key, 0) for key in ("fresh", "delayed", "stale", "bootstrap")},
        "max_source_lag_seconds": max_source_lag_seconds,
        "max_stale_after_seconds": max_stale_after_seconds,
        "all_within_sla": all_within_sla,
    }


def _build_provenance_payload(grouped_rows: list[tuple[Mapping[str, Any], Any, Any]]) -> dict[str, Any]:
    source_ids: set[str] = set()
    origin_types: set[str] = set()
    raw_trace_paths: set[str] = set()
    change_ids: set[str] = set()
    ingestion_run_ids: set[str] = set()
    authority_ranks: set[int] = set()

    for listing, _, _ in grouped_rows:
        source = _coerce_mapping(listing.get("source"), "listing.source")
        provenance = _coerce_mapping(listing.get("provenance"), "listing.provenance")
        source_ids.add(_coerce_non_empty_string(source.get("source_id"), "listing.source.source_id"))
        authority_ranks.add(_coerce_int(source.get("authority_rank"), "listing.source.authority_rank", minimum=1))
        origin_types.add(_coerce_non_empty_string(provenance.get("origin"), "listing.provenance.origin"))
        raw_trace_paths.add(_coerce_non_empty_string(provenance.get("raw_page_path"), "listing.provenance.raw_page_path"))
        change_ids.add(_coerce_non_empty_string(provenance.get("public_stash_change_id"), "listing.provenance.public_stash_change_id"))
        ingestion_run_ids.add(_coerce_non_empty_string(provenance.get("ingestion_run_id"), "listing.provenance.ingestion_run_id"))

    return {
        "source_ids": sorted(source_ids),
        "origin_types": sorted(origin_types),
        "raw_trace_paths": sorted(raw_trace_paths),
        "change_ids": sorted(change_ids),
        "ingestion_run_ids": sorted(ingestion_run_ids),
        "authority_ranks": sorted(authority_ranks),
        "listing_count": len(grouped_rows),
    }
