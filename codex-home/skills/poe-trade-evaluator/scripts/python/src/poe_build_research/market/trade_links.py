"""Trade query and trade-link bundle helpers for market review flows."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from poe_build_research.market.source_contracts import (
    CANONICAL_SOURCE_CONTRACTS,
    Realm,
    SourceId,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRADE_LINK_BUNDLE_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "market" / "trade_link_bundle.schema.json"
TRADE_LINK_BUNDLE_VERSION = "1.0.0"
TRADE_LINK_RECORD_KIND = "trade_link_bundle"
TRADE_LINK_GENERATOR = "poe_build_research.market.trade_links"
TRADE_LINK_SOURCE = CANONICAL_SOURCE_CONTRACTS[SourceId.UNDOCUMENTED_TRADE_API]
TRADE_SEARCH_REQUEST_URL = "https://www.pathofexile.com/api/trade/search/{league}"
TRADE_RESULTS_URL = "https://www.pathofexile.com/trade/search/{league}/{search_id}"
SEARCH_ID_PATTERN = re.compile(r"^[A-Za-z0-9]+$")


class TradeLinkContractError(RuntimeError):
    """Raised when a trade-link query or bundle violates the contract."""


def _stable_json(payload: Any) -> str:
    try:
        return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    except ValueError as exc:
        raise TradeLinkContractError("Trade-link payload contains non-finite numeric values.") from exc


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _require_non_empty_string(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TradeLinkContractError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _require_iso8601(value: str, field_name: str) -> str:
    text = _require_non_empty_string(value, field_name)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TradeLinkContractError(f"{field_name} must be an ISO 8601 timestamp.") from exc
    return text


def _require_search_id(value: str) -> str:
    token = _require_non_empty_string(value, "search_id")
    if not SEARCH_ID_PATTERN.fullmatch(token):
        raise TradeLinkContractError("search_id must be alphanumeric.")
    return token


def _require_realm(value: Realm | str) -> Realm:
    if isinstance(value, Realm):
        return value
    try:
        return Realm(_require_non_empty_string(value, "realm"))
    except ValueError as exc:
        raise TradeLinkContractError("realm must be one of: pc, xbox, sony.") from exc


def _require_finite_number(value: int | float, field_name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise TradeLinkContractError(f"{field_name} must be a finite number when provided.")
    return value


def _league_token(league: str) -> str:
    return quote(_require_non_empty_string(league, "league"), safe="")


def trade_search_request_url(league: str) -> str:
    """Return the official trade search submission endpoint for a league."""

    return TRADE_SEARCH_REQUEST_URL.format(league=_league_token(league))


def trade_results_url_template(league: str) -> str:
    """Return the human-facing result URL template for a resolved trade search."""

    return TRADE_RESULTS_URL.format(league=_league_token(league), search_id="{search_id}")


def trade_results_url(league: str, search_id: str) -> str:
    """Return the human-facing result URL for a resolved trade search."""

    return TRADE_RESULTS_URL.format(league=_league_token(league), search_id=quote(_require_search_id(search_id), safe=""))


@dataclass(frozen=True, slots=True)
class InputProvenanceRef:
    """One upstream record whose provenance should survive bundle generation."""

    record_kind: str
    record_id: str
    source_uri: str
    observed_at: str
    collector: str
    collected_at: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_kind", _require_non_empty_string(self.record_kind, "record_kind"))
        object.__setattr__(self, "record_id", _require_non_empty_string(self.record_id, "record_id"))
        object.__setattr__(self, "source_uri", _require_non_empty_string(self.source_uri, "source_uri"))
        object.__setattr__(self, "observed_at", _require_iso8601(self.observed_at, "observed_at"))
        object.__setattr__(self, "collector", _require_non_empty_string(self.collector, "collector"))
        if self.collected_at is not None:
            object.__setattr__(self, "collected_at", _require_iso8601(self.collected_at, "collected_at"))
        if self.note is not None:
            object.__setattr__(self, "note", _require_non_empty_string(self.note, "note"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_kind": self.record_kind,
            "record_id": self.record_id,
            "source_uri": self.source_uri,
            "observed_at": self.observed_at,
            "collector": self.collector,
            "collected_at": self.collected_at,
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class UniqueItemTradeQuery:
    """Minimal structured query model for reproducible unique-item searches."""

    league: str
    name: str
    type_line: str | None = None
    realm: Realm | str = Realm.PC
    online_only: bool = True
    search_id: str | None = None
    provenance_refs: tuple[InputProvenanceRef, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "realm", _require_realm(self.realm))
        object.__setattr__(self, "league", _require_non_empty_string(self.league, "league"))
        object.__setattr__(self, "name", _require_non_empty_string(self.name, "name"))
        if self.type_line is not None:
            object.__setattr__(self, "type_line", _require_non_empty_string(self.type_line, "type_line"))
        if self.search_id is not None:
            object.__setattr__(self, "search_id", _require_search_id(self.search_id))
        object.__setattr__(self, "provenance_refs", _normalize_provenance_refs(self.provenance_refs))

    @property
    def label(self) -> str:
        if self.type_line:
            return f"{self.name} ({self.type_line})"
        return self.name

    def query_model(self) -> dict[str, Any]:
        return {
            "kind": "unique_item",
            "name": self.name,
            "type_line": self.type_line,
            "online_only": self.online_only,
        }

    def trade_query(self) -> dict[str, Any]:
        query: dict[str, Any] = {
            "status": {"option": "online" if self.online_only else "any"},
            "name": self.name,
            "stats": [],
        }
        if self.type_line is not None:
            query["type"] = self.type_line
        return {
            "query": query,
            "sort": {"price": "asc"},
        }


@dataclass(frozen=True, slots=True)
class RareItemCoreStat:
    """One required trade stat for a rare-item core template."""

    trade_stat_id: str
    label: str
    minimum: int | float | None = None
    maximum: int | float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "trade_stat_id", _require_non_empty_string(self.trade_stat_id, "trade_stat_id"))
        object.__setattr__(self, "label", _require_non_empty_string(self.label, "label"))
        if self.minimum is None and self.maximum is None:
            raise TradeLinkContractError("Rare-item core stats must define minimum, maximum, or both.")
        if self.minimum is not None:
            _require_finite_number(self.minimum, "minimum")
        if self.maximum is not None:
            _require_finite_number(self.maximum, "maximum")
        if self.minimum is not None and self.maximum is not None and self.maximum < self.minimum:
            raise TradeLinkContractError("Rare-item core stat maximum must be >= minimum.")

    def to_model_dict(self) -> dict[str, Any]:
        return {
            "trade_stat_id": self.trade_stat_id,
            "label": self.label,
            "minimum": self.minimum,
            "maximum": self.maximum,
        }

    def to_trade_filter(self) -> dict[str, Any]:
        value: dict[str, Any] = {}
        if self.minimum is not None:
            value["min"] = self.minimum
        if self.maximum is not None:
            value["max"] = self.maximum
        return {
            "id": self.trade_stat_id,
            "disabled": False,
            "value": value,
        }


@dataclass(frozen=True, slots=True)
class RareItemCoreTemplate:
    """Core search template for a rare item without full realism claims."""

    league: str
    base_type: str
    core_stats: tuple[RareItemCoreStat, ...]
    realm: Realm | str = Realm.PC
    online_only: bool = True
    search_id: str | None = None
    provenance_refs: tuple[InputProvenanceRef, ...] = ()
    label: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "realm", _require_realm(self.realm))
        object.__setattr__(self, "league", _require_non_empty_string(self.league, "league"))
        object.__setattr__(self, "base_type", _require_non_empty_string(self.base_type, "base_type"))
        if self.label is not None:
            object.__setattr__(self, "label", _require_non_empty_string(self.label, "label"))
        if self.search_id is not None:
            object.__setattr__(self, "search_id", _require_search_id(self.search_id))
        object.__setattr__(self, "core_stats", _normalize_core_stats(self.core_stats))
        object.__setattr__(self, "provenance_refs", _normalize_provenance_refs(self.provenance_refs))
        if not self.core_stats:
            raise TradeLinkContractError("Rare-item core templates must include at least one core stat.")

    @property
    def resolved_label(self) -> str:
        if self.label is not None:
            return self.label
        return f"{self.base_type} rare core"

    def query_model(self) -> dict[str, Any]:
        return {
            "kind": "rare_item_core",
            "label": self.resolved_label,
            "base_type": self.base_type,
            "rarity": "rare",
            "realism_scope": "core_requirements_only",
            "core_stats": [stat.to_model_dict() for stat in self.core_stats],
        }

    def trade_query(self) -> dict[str, Any]:
        return {
            "query": {
                "status": {"option": "online" if self.online_only else "any"},
                "type": self.base_type,
                "filters": {
                    "type_filters": {
                        "disabled": False,
                        "filters": {
                            "rarity": {"option": "rare"},
                        },
                    }
                },
                "stats": [
                    {
                        "type": "and",
                        "filters": [stat.to_trade_filter() for stat in self.core_stats],
                    }
                ],
            },
            "sort": {"price": "asc"},
        }


def _normalize_provenance_refs(value: tuple[InputProvenanceRef, ...] | list[InputProvenanceRef]) -> tuple[InputProvenanceRef, ...]:
    refs = tuple(value)
    for index, ref in enumerate(refs):
        if not isinstance(ref, InputProvenanceRef):
            raise TradeLinkContractError(f"provenance_refs[{index}] must be an InputProvenanceRef.")
    return refs


def _normalize_core_stats(value: tuple[RareItemCoreStat, ...] | list[RareItemCoreStat]) -> tuple[RareItemCoreStat, ...]:
    stats = tuple(value)
    for index, stat in enumerate(stats):
        if not isinstance(stat, RareItemCoreStat):
            raise TradeLinkContractError(f"core_stats[{index}] must be a RareItemCoreStat.")
    return stats


@dataclass(frozen=True, slots=True)
class TradeLinkBundle:
    """Structured, reproducible trade-link output."""

    bundle_id: str
    bundle_kind: str
    label: str
    realm: Realm
    league: str
    query_model: dict[str, Any]
    trade_query: dict[str, Any]
    links: dict[str, Any]
    provenance: dict[str, Any]
    freshness: dict[str, Any]
    liquidity: dict[str, Any]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TRADE_LINK_BUNDLE_VERSION,
            "record_kind": TRADE_LINK_RECORD_KIND,
            "bundle_id": self.bundle_id,
            "bundle_kind": self.bundle_kind,
            "label": self.label,
            "realm": self.realm.value,
            "league": self.league,
            "query_model": self.query_model,
            "trade_query": self.trade_query,
            "links": self.links,
            "provenance": self.provenance,
            "freshness": self.freshness,
            "liquidity": self.liquidity,
            "limitations": list(self.limitations),
        }

    def to_json(self) -> str:
        return _stable_json(self.to_dict())


def _build_bundle(
    *,
    bundle_kind: str,
    label: str,
    realm: Realm,
    league: str,
    query_model: dict[str, Any],
    trade_query: dict[str, Any],
    search_id: str | None,
    provenance_refs: tuple[InputProvenanceRef, ...],
    limitations: tuple[str, ...],
    generated_at: str,
) -> TradeLinkBundle:
    generated_at = _require_iso8601(generated_at, "generated_at")
    latest_input_observed_at = max((ref.observed_at for ref in provenance_refs), default=None)

    input_provenance = [ref.to_dict() for ref in provenance_refs]
    input_payload = {
        "bundle_kind": bundle_kind,
        "realm": realm.value,
        "league": league,
        "query_model": query_model,
        "input_provenance": input_provenance,
    }
    input_sha256 = _sha256_json(input_payload)
    query_sha256 = _sha256_json(trade_query)
    bundle_hash = _sha256_json(
        {
            "bundle_kind": bundle_kind,
            "realm": realm.value,
            "league": league,
            "query_model": query_model,
            "trade_query": trade_query,
            "input_provenance": input_provenance,
        }
    )

    links = {
        "search_submission_method": "POST",
        "search_submission_url": trade_search_request_url(league),
        "results_url_template": trade_results_url_template(league),
        "resolved_search_id": search_id,
        "resolved_search_url": trade_results_url(league, search_id) if search_id is not None else None,
    }
    provenance = {
        "generated_at": generated_at,
        "generator": TRADE_LINK_GENERATOR,
        "generator_version": TRADE_LINK_BUNDLE_VERSION,
        "source_id": TRADE_LINK_SOURCE.source_id.value,
        "support_level": TRADE_LINK_SOURCE.support_level.value,
        "authority_rank": TRADE_LINK_SOURCE.authority_rank,
        "hard_requirement": TRADE_LINK_SOURCE.hard_requirement,
        "input_sha256": input_sha256,
        "query_sha256": query_sha256,
        "input_provenance": input_provenance,
    }
    freshness = {
        "status": "query_only",
        "generated_at": generated_at,
        "latest_input_observed_at": latest_input_observed_at,
        "note": "This bundle carries search templates only; live market freshness must come from snapshots or submitted searches.",
    }
    liquidity = {
        "status": "unknown",
        "listing_count": None,
        "note": "No snapshot aggregation is attached to this trade-link bundle.",
    }

    return TradeLinkBundle(
        bundle_id=f"trade_link_bundle.{bundle_kind}.{bundle_hash[:16]}",
        bundle_kind=bundle_kind,
        label=label,
        realm=realm,
        league=league,
        query_model=query_model,
        trade_query=trade_query,
        links=links,
        provenance=provenance,
        freshness=freshness,
        liquidity=liquidity,
        limitations=tuple(limitations),
    )


def build_unique_item_trade_link_bundle(query: UniqueItemTradeQuery, *, generated_at: str) -> TradeLinkBundle:
    """Build a reproducible trade-link bundle for a unique item."""

    limitations = [
        "Trade-link bundles do not submit searches or attach live prices by themselves.",
    ]
    if query.search_id is None:
        limitations.append("Search ids stay unresolved until the query is submitted to the official trade search endpoint.")
    return _build_bundle(
        bundle_kind="unique_item",
        label=query.label,
        realm=query.realm,
        league=query.league,
        query_model=query.query_model(),
        trade_query=query.trade_query(),
        search_id=query.search_id,
        provenance_refs=query.provenance_refs,
        limitations=tuple(limitations),
        generated_at=generated_at,
    )


def build_rare_item_core_trade_link_bundle(template: RareItemCoreTemplate, *, generated_at: str) -> TradeLinkBundle:
    """Build a rare-item core template bundle without claiming full realism."""

    limitations = [
        "Rare-item core bundles encode only required core mods and do not claim full rare-item realism.",
        "Trade-link bundles do not submit searches or attach live prices by themselves.",
    ]
    if template.search_id is None:
        limitations.append("Search ids stay unresolved until the query is submitted to the official trade search endpoint.")
    return _build_bundle(
        bundle_kind="rare_item_core",
        label=template.resolved_label,
        realm=template.realm,
        league=template.league,
        query_model=template.query_model(),
        trade_query=template.trade_query(),
        search_id=template.search_id,
        provenance_refs=template.provenance_refs,
        limitations=tuple(limitations),
        generated_at=generated_at,
    )


def load_trade_link_bundle_schema(path: Path = DEFAULT_TRADE_LINK_BUNDLE_SCHEMA_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


__all__ = [
    "DEFAULT_TRADE_LINK_BUNDLE_SCHEMA_PATH",
    "InputProvenanceRef",
    "RareItemCoreStat",
    "RareItemCoreTemplate",
    "TradeLinkBundle",
    "TradeLinkContractError",
    "UniqueItemTradeQuery",
    "build_rare_item_core_trade_link_bundle",
    "build_unique_item_trade_link_bundle",
    "load_trade_link_bundle_schema",
    "trade_results_url",
    "trade_results_url_template",
    "trade_search_request_url",
]
