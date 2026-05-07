"""Contracts for supported pricing sources and raw market ingestion."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MARKET_SOURCES_PATH = PROJECT_ROOT / "config" / "market_sources.toml"
DEFAULT_RAW_LISTING_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "market" / "raw_listing.schema.json"


class MarketSourceContractError(RuntimeError):
    """Raised when source config or checkpoint state violates the contract."""


class SourceId(StrEnum):
    OFFICIAL_PUBLIC_STASHES = "official_public_stashes"
    SELF_RECORDED_SNAPSHOTS = "self_recorded_snapshots"
    MANUAL_BOOTSTRAP_SNAPSHOTS = "manual_bootstrap_snapshots"
    UNDOCUMENTED_TRADE_API = "undocumented_trade_api"


class SupportLevel(StrEnum):
    SUPPORTED = "supported"
    BOOTSTRAP_ONLY = "bootstrap_only"
    UNSUPPORTED_OPT_IN = "unsupported_opt_in"


class SourceRole(StrEnum):
    LIVE_INGEST = "live_ingest"
    HISTORICAL_READ = "historical_read"
    BOOTSTRAP_READ = "bootstrap_read"
    EXPERIMENTAL = "experimental"


class Realm(StrEnum):
    PC = "pc"
    XBOX = "xbox"
    SONY = "sony"


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    DELAYED = "delayed"
    STALE = "stale"
    BOOTSTRAP = "bootstrap"


class CheckpointCursorKind(StrEnum):
    NEXT_CHANGE_ID = "next_change_id"
    MANIFEST_ENTRY = "manifest_entry"


class OAuthClientType(StrEnum):
    CONFIDENTIAL = "confidential"
    PUBLIC = "public"


class OAuthGrantType(StrEnum):
    CLIENT_CREDENTIALS = "client_credentials"
    AUTHORIZATION_CODE_PKCE = "authorization_code_pkce"


def _parse_iso8601(value: str, field_name: str) -> None:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MarketSourceContractError(f"{field_name} must be an ISO 8601 timestamp.") from exc


def _as_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MarketSourceContractError(f"{field_name} must be a table/object.")
    return value


def _as_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise MarketSourceContractError(f"{field_name} must be a boolean.")
    return value


def _as_int(value: Any, field_name: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int):
        raise MarketSourceContractError(f"{field_name} must be an integer.")
    if minimum is not None and value < minimum:
        raise MarketSourceContractError(f"{field_name} must be >= {minimum}.")
    return value


def _as_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MarketSourceContractError(f"{field_name} must be a non-empty string.")
    return value


def _as_string_or_none(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise MarketSourceContractError(f"{field_name} must be a string when provided.")
    return value


def _as_string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise MarketSourceContractError(f"{field_name} must be an array of non-empty strings.")
    return tuple(value)


def _resolve_project_path(value: Any, field_name: str) -> Path:
    raw_path = Path(_as_non_empty_string(value, field_name))
    return raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path


def _normalize_partition_token(value: str, field_name: str) -> str:
    token = _as_non_empty_string(value, field_name).strip()
    windows_token = PureWindowsPath(token)
    posix_token = PurePosixPath(token)

    if windows_token.anchor or posix_token.is_absolute():
        raise MarketSourceContractError(f"{field_name} must not be an absolute or rooted path.")
    if "/" in token or "\\" in token:
        raise MarketSourceContractError(f"{field_name} must not contain path separators.")
    if token in {".", ".."}:
        raise MarketSourceContractError(f"{field_name} must not use relative path segments.")

    windows_normalized = token.rstrip(" .")
    if windows_normalized in {"", ".", ".."}:
        raise MarketSourceContractError(f"{field_name} must not normalize to relative path segments on Windows.")
    if windows_normalized != token:
        raise MarketSourceContractError(f"{field_name} must stay stable under Windows path normalization.")

    return token


def _ensure_path_within_root(path: Path, root: Path, field_name: str) -> Path:
    resolved_root = root.resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    if not resolved_path.is_relative_to(resolved_root):
        raise MarketSourceContractError(f"{field_name} must stay within {resolved_root}.")
    return path


@dataclass(frozen=True)
class OAuthRequirement:
    required: bool
    client_type: OAuthClientType | None = None
    grant_type: OAuthGrantType | None = None
    scopes: tuple[str, ...] = ()

    def validate(self, source_id: SourceId) -> None:
        if self.required:
            if self.client_type is None or self.grant_type is None or not self.scopes:
                raise MarketSourceContractError(f"{source_id} requires a complete OAuth definition.")
            if any(scope.startswith("service:") for scope in self.scopes):
                if self.client_type is not OAuthClientType.CONFIDENTIAL:
                    raise MarketSourceContractError(f"{source_id} service scopes require a confidential client.")
                if self.grant_type is not OAuthGrantType.CLIENT_CREDENTIALS:
                    raise MarketSourceContractError(f"{source_id} service scopes require client_credentials.")
        else:
            if self.client_type is not None or self.grant_type is not None or self.scopes:
                raise MarketSourceContractError(f"{source_id} must not define OAuth client details when OAuth is disabled.")


@dataclass(frozen=True)
class SourceContract:
    source_id: SourceId
    support_level: SupportLevel
    authority_rank: int
    allowed_roles: tuple[SourceRole, ...]
    hard_requirement: bool
    oauth: OAuthRequirement
    required_rate_limit_headers: tuple[str, ...] = ()
    requires_endpoint: bool = False


CANONICAL_SOURCE_CONTRACTS: dict[SourceId, SourceContract] = {
    SourceId.SELF_RECORDED_SNAPSHOTS: SourceContract(
        source_id=SourceId.SELF_RECORDED_SNAPSHOTS,
        support_level=SupportLevel.SUPPORTED,
        authority_rank=1,
        allowed_roles=(SourceRole.HISTORICAL_READ,),
        hard_requirement=False,
        oauth=OAuthRequirement(required=False),
    ),
    SourceId.OFFICIAL_PUBLIC_STASHES: SourceContract(
        source_id=SourceId.OFFICIAL_PUBLIC_STASHES,
        support_level=SupportLevel.SUPPORTED,
        authority_rank=2,
        allowed_roles=(SourceRole.LIVE_INGEST,),
        hard_requirement=True,
        oauth=OAuthRequirement(
            required=True,
            client_type=OAuthClientType.CONFIDENTIAL,
            grant_type=OAuthGrantType.CLIENT_CREDENTIALS,
            scopes=("service:psapi",),
        ),
        required_rate_limit_headers=(
            "X-Rate-Limit-Policy",
            "X-Rate-Limit-Rules",
            "X-Rate-Limit-Client",
            "X-Rate-Limit-Client-State",
            "Retry-After",
        ),
        requires_endpoint=True,
    ),
    SourceId.MANUAL_BOOTSTRAP_SNAPSHOTS: SourceContract(
        source_id=SourceId.MANUAL_BOOTSTRAP_SNAPSHOTS,
        support_level=SupportLevel.BOOTSTRAP_ONLY,
        authority_rank=3,
        allowed_roles=(SourceRole.BOOTSTRAP_READ,),
        hard_requirement=False,
        oauth=OAuthRequirement(required=False),
    ),
    SourceId.UNDOCUMENTED_TRADE_API: SourceContract(
        source_id=SourceId.UNDOCUMENTED_TRADE_API,
        support_level=SupportLevel.UNSUPPORTED_OPT_IN,
        authority_rank=99,
        allowed_roles=(SourceRole.EXPERIMENTAL,),
        hard_requirement=False,
        oauth=OAuthRequirement(required=False),
    ),
}

SUPPORTED_PRICE_SOURCE_HIERARCHY: tuple[SourceContract, ...] = tuple(
    sorted(CANONICAL_SOURCE_CONTRACTS.values(), key=lambda contract: contract.authority_rank)
)


@dataclass(frozen=True)
class ConfiguredSource:
    contract: SourceContract
    enabled: bool
    role: SourceRole
    checkpoint_namespace: str
    expected_delay_seconds: int
    rate_limit_headers: tuple[str, ...]
    endpoint: str | None = None
    derived_from: str | None = None
    feature_flag: str | None = None

    @property
    def source_id(self) -> SourceId:
        return self.contract.source_id

    def validate(self) -> None:
        if self.role not in self.contract.allowed_roles:
            raise MarketSourceContractError(
                f"{self.source_id} role must be one of {[role.value for role in self.contract.allowed_roles]}."
            )
        if self.contract.requires_endpoint and not self.endpoint:
            raise MarketSourceContractError(f"{self.source_id} must declare an endpoint.")
        if self.expected_delay_seconds < 0:
            raise MarketSourceContractError(f"{self.source_id} expected_delay_seconds must be >= 0.")
        if self.contract.required_rate_limit_headers:
            missing = sorted(set(self.contract.required_rate_limit_headers) - set(self.rate_limit_headers))
            if missing:
                raise MarketSourceContractError(
                    f"{self.source_id} is missing required rate-limit headers: {', '.join(missing)}"
                )
        if self.contract.support_level is SupportLevel.UNSUPPORTED_OPT_IN and not self.feature_flag:
            raise MarketSourceContractError(f"{self.source_id} must declare a feature_flag.")
        self.contract.oauth.validate(self.source_id)


@dataclass(frozen=True)
class StorageRoots:
    checkpoint_root: Path
    raw_root: Path
    normalized_root: Path
    snapshot_root: Path

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StorageRoots":
        return cls(
            checkpoint_root=_resolve_project_path(data.get("checkpoint_root"), "storage.checkpoint_root"),
            raw_root=_resolve_project_path(data.get("raw_root"), "storage.raw_root"),
            normalized_root=_resolve_project_path(data.get("normalized_root"), "storage.normalized_root"),
            snapshot_root=_resolve_project_path(data.get("snapshot_root"), "storage.snapshot_root"),
        )


@dataclass(frozen=True)
class FreshnessPolicy:
    fresh_within_seconds: int
    stale_after_seconds: int
    clock_skew_tolerance_seconds: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FreshnessPolicy":
        fresh_within_seconds = _as_int(data.get("fresh_within_seconds"), "freshness.defaults.fresh_within_seconds", minimum=1)
        stale_after_seconds = _as_int(data.get("stale_after_seconds"), "freshness.defaults.stale_after_seconds", minimum=1)
        clock_skew_tolerance_seconds = _as_int(
            data.get("clock_skew_tolerance_seconds"),
            "freshness.defaults.clock_skew_tolerance_seconds",
            minimum=0,
        )
        if stale_after_seconds <= fresh_within_seconds:
            raise MarketSourceContractError("freshness.defaults.stale_after_seconds must be greater than fresh_within_seconds.")
        return cls(
            fresh_within_seconds=fresh_within_seconds,
            stale_after_seconds=stale_after_seconds,
            clock_skew_tolerance_seconds=clock_skew_tolerance_seconds,
        )


@dataclass(frozen=True)
class LeagueWindow:
    label: str
    start_offset_hours: int
    end_offset_hours: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], field_name: str) -> "LeagueWindow":
        label = _as_non_empty_string(data.get("label"), f"{field_name}.label")
        start_offset_hours = _as_int(data.get("start_offset_hours"), f"{field_name}.start_offset_hours", minimum=0)
        end_offset_hours = _as_int(data.get("end_offset_hours"), f"{field_name}.end_offset_hours", minimum=1)
        if end_offset_hours <= start_offset_hours:
            raise MarketSourceContractError(f"{field_name} must end after it starts.")
        return cls(label=label, start_offset_hours=start_offset_hours, end_offset_hours=end_offset_hours)


@dataclass(frozen=True)
class SourceSelection:
    default_strategy: str
    default_realm: Realm
    live_ingest: SourceId
    historical_read: SourceId
    bootstrap_read: SourceId
    fallback_order: tuple[SourceId, ...]
    deny_as_hard_requirement: tuple[SourceId, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceSelection":
        default_strategy = _as_non_empty_string(data.get("default_strategy"), "selection.default_strategy")
        if default_strategy != "supported_only":
            raise MarketSourceContractError("selection.default_strategy must be 'supported_only' for v1.")
        default_realm = Realm(_as_non_empty_string(data.get("default_realm"), "selection.default_realm"))
        live_ingest = SourceId(_as_non_empty_string(data.get("live_ingest"), "selection.live_ingest"))
        historical_read = SourceId(_as_non_empty_string(data.get("historical_read"), "selection.historical_read"))
        bootstrap_read = SourceId(_as_non_empty_string(data.get("bootstrap_read"), "selection.bootstrap_read"))
        fallback_order = tuple(SourceId(item) for item in _as_string_tuple(data.get("fallback_order"), "selection.fallback_order"))
        deny_as_hard_requirement = tuple(
            SourceId(item) for item in _as_string_tuple(data.get("deny_as_hard_requirement"), "selection.deny_as_hard_requirement")
        )
        return cls(
            default_strategy=default_strategy,
            default_realm=default_realm,
            live_ingest=live_ingest,
            historical_read=historical_read,
            bootstrap_read=bootstrap_read,
            fallback_order=fallback_order,
            deny_as_hard_requirement=deny_as_hard_requirement,
        )

    def validate(self, configured_sources: Mapping[SourceId, ConfiguredSource]) -> None:
        for source_id in (self.live_ingest, self.historical_read, self.bootstrap_read):
            if source_id not in configured_sources:
                raise MarketSourceContractError(f"selection references unknown source {source_id}.")

        if SourceId.UNDOCUMENTED_TRADE_API not in self.deny_as_hard_requirement:
            raise MarketSourceContractError("selection.deny_as_hard_requirement must include undocumented_trade_api.")
        if SourceId.UNDOCUMENTED_TRADE_API in self.fallback_order:
            raise MarketSourceContractError("selection.fallback_order must not include undocumented_trade_api.")

        if configured_sources[self.live_ingest].role is not SourceRole.LIVE_INGEST:
            raise MarketSourceContractError("selection.live_ingest must point to a live_ingest source.")
        if configured_sources[self.historical_read].role is not SourceRole.HISTORICAL_READ:
            raise MarketSourceContractError("selection.historical_read must point to a historical_read source.")
        if configured_sources[self.bootstrap_read].role is not SourceRole.BOOTSTRAP_READ:
            raise MarketSourceContractError("selection.bootstrap_read must point to a bootstrap_read source.")

        missing = sorted(set(self.fallback_order) - set(configured_sources))
        if missing:
            raise MarketSourceContractError(f"selection.fallback_order references unknown sources: {', '.join(item.value for item in missing)}")

        positions = {source_id: index for index, source_id in enumerate(self.fallback_order)}
        required_order = (self.historical_read, self.live_ingest, self.bootstrap_read)
        if len(set(required_order)) != len(required_order):
            raise MarketSourceContractError("selection source hierarchy must reference distinct sources.")
        if any(source_id not in positions for source_id in required_order):
            raise MarketSourceContractError("selection.fallback_order must include historical, live, and bootstrap sources.")
        if not (positions[self.historical_read] < positions[self.live_ingest] < positions[self.bootstrap_read]):
            raise MarketSourceContractError(
                "selection.fallback_order must rank historical_read ahead of live_ingest ahead of bootstrap_read."
            )


@dataclass(frozen=True)
class CheckpointState:
    source_id: SourceId
    realm: Realm
    checkpoint_key: str
    cursor_kind: CheckpointCursorKind
    cursor_in: str | None
    cursor_out: str
    page_sequence: int
    persisted_at: str
    last_observed_at: str
    last_success_at: str
    empty_poll_count: int = 0
    resume_safe: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CheckpointState":
        source_id = SourceId(_as_non_empty_string(data.get("source_id"), "checkpoint.source_id"))
        realm = Realm(_as_non_empty_string(data.get("realm"), "checkpoint.realm"))
        checkpoint_key = _as_non_empty_string(data.get("checkpoint_key"), "checkpoint.checkpoint_key")
        cursor_kind = CheckpointCursorKind(_as_non_empty_string(data.get("cursor_kind"), "checkpoint.cursor_kind"))
        cursor_in = _as_string_or_none(data.get("cursor_in"), "checkpoint.cursor_in")
        cursor_out = _as_non_empty_string(data.get("cursor_out"), "checkpoint.cursor_out")
        resume_from = _as_string_or_none(data.get("resume_from"), "checkpoint.resume_from")
        page_sequence = _as_int(data.get("page_sequence"), "checkpoint.page_sequence", minimum=0)
        persisted_at = _as_non_empty_string(data.get("persisted_at"), "checkpoint.persisted_at")
        last_observed_at = _as_non_empty_string(data.get("last_observed_at"), "checkpoint.last_observed_at")
        last_success_at = _as_non_empty_string(data.get("last_success_at"), "checkpoint.last_success_at")
        empty_poll_count = _as_int(data.get("empty_poll_count", 0), "checkpoint.empty_poll_count", minimum=0)
        resume_safe = _as_bool(data.get("resume_safe", True), "checkpoint.resume_safe")
        if resume_from is not None and resume_from != cursor_out:
            raise MarketSourceContractError("checkpoint.resume_from must match checkpoint.cursor_out.")
        for field_name, value in (
            ("checkpoint.persisted_at", persisted_at),
            ("checkpoint.last_observed_at", last_observed_at),
            ("checkpoint.last_success_at", last_success_at),
        ):
            _parse_iso8601(value, field_name)
        return cls(
            source_id=source_id,
            realm=realm,
            checkpoint_key=checkpoint_key,
            cursor_kind=cursor_kind,
            cursor_in=cursor_in,
            cursor_out=cursor_out,
            page_sequence=page_sequence,
            persisted_at=persisted_at,
            last_observed_at=last_observed_at,
            last_success_at=last_success_at,
            empty_poll_count=empty_poll_count,
            resume_safe=resume_safe,
        )

    @property
    def resume_from(self) -> str:
        return self.cursor_out

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id.value,
            "realm": self.realm.value,
            "checkpoint_key": self.checkpoint_key,
            "cursor_kind": self.cursor_kind.value,
            "cursor_in": self.cursor_in,
            "cursor_out": self.cursor_out,
            "page_sequence": self.page_sequence,
            "persisted_at": self.persisted_at,
            "last_observed_at": self.last_observed_at,
            "last_success_at": self.last_success_at,
            "empty_poll_count": self.empty_poll_count,
            "resume_from": self.resume_from,
            "resume_safe": self.resume_safe,
        }


@dataclass(frozen=True)
class MarketSourceConfig:
    version: int
    selection: SourceSelection
    storage: StorageRoots
    freshness: FreshnessPolicy
    sources: dict[SourceId, ConfiguredSource]
    league_windows: dict[str, LeagueWindow]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MarketSourceConfig":
        version = _as_int(data.get("version"), "version", minimum=1)
        if version != 1:
            raise MarketSourceContractError("Only market source config version 1 is supported.")

        selection = SourceSelection.from_dict(_as_mapping(data.get("selection"), "selection"))
        storage = StorageRoots.from_dict(_as_mapping(data.get("storage"), "storage"))
        freshness_root = _as_mapping(data.get("freshness"), "freshness")
        freshness = FreshnessPolicy.from_dict(_as_mapping(freshness_root.get("defaults"), "freshness.defaults"))
        sources = _parse_sources(_as_mapping(data.get("sources"), "sources"))
        league_windows = {
            name: LeagueWindow.from_dict(_as_mapping(window_data, f"league_windows.{name}"), f"league_windows.{name}")
            for name, window_data in _as_mapping(data.get("league_windows"), "league_windows").items()
        }
        config = cls(
            version=version,
            selection=selection,
            storage=storage,
            freshness=freshness,
            sources=sources,
            league_windows=league_windows,
        )
        config.validate()
        return config

    def validate(self) -> None:
        self.selection.validate(self.sources)
        required_windows = {"day_1", "day_3", "day_7", "week_1_avg"}
        missing_windows = sorted(required_windows - self.league_windows.keys())
        if missing_windows:
            raise MarketSourceContractError(f"league_windows is missing required windows: {', '.join(missing_windows)}")
        for source in self.sources.values():
            source.validate()

    def checkpoint_path(self, source_id: SourceId, realm: Realm | None = None) -> Path:
        partition_realm = realm or self.selection.default_realm
        return self.storage.checkpoint_root / source_id.value / f"{partition_realm.value}.json"

    def raw_partition_root(self, source_id: SourceId, realm: Realm | None, league: str) -> Path:
        partition_realm = realm or self.selection.default_realm
        league_token = _normalize_partition_token(league, "league")
        partition_root = self.storage.raw_root / source_id.value / partition_realm.value / league_token
        return _ensure_path_within_root(partition_root, self.storage.raw_root, "league")


def _parse_sources(data: Mapping[str, Any]) -> dict[SourceId, ConfiguredSource]:
    unknown_source_ids = sorted(set(data) - {source_id.value for source_id in CANONICAL_SOURCE_CONTRACTS})
    if unknown_source_ids:
        raise MarketSourceContractError(f"Unknown source ids in config: {', '.join(unknown_source_ids)}")

    configured_sources: dict[SourceId, ConfiguredSource] = {}
    for source_id, contract in CANONICAL_SOURCE_CONTRACTS.items():
        source_data = _as_mapping(data.get(source_id.value), f"sources.{source_id.value}")
        support_level = SupportLevel(_as_non_empty_string(source_data.get("support_level"), f"sources.{source_id.value}.support_level"))
        authority_rank = _as_int(source_data.get("authority_rank"), f"sources.{source_id.value}.authority_rank", minimum=1)
        if support_level is not contract.support_level:
            raise MarketSourceContractError(
                f"sources.{source_id.value}.support_level must stay {contract.support_level.value}."
            )
        if authority_rank != contract.authority_rank:
            raise MarketSourceContractError(
                f"sources.{source_id.value}.authority_rank must stay {contract.authority_rank}."
            )
        hard_requirement = _as_bool(source_data.get("hard_requirement"), f"sources.{source_id.value}.hard_requirement")
        if hard_requirement is not contract.hard_requirement:
            raise MarketSourceContractError(
                f"sources.{source_id.value}.hard_requirement must stay {contract.hard_requirement}."
            )

        oauth_required = _as_bool(source_data.get("oauth_required"), f"sources.{source_id.value}.oauth_required")
        oauth_client_type_value = _as_string_or_none(source_data.get("oauth_client_type"), f"sources.{source_id.value}.oauth_client_type")
        oauth_grant_type_value = _as_string_or_none(source_data.get("oauth_grant_type"), f"sources.{source_id.value}.oauth_grant_type")
        oauth_scopes = _as_string_tuple(source_data.get("oauth_scopes", []), f"sources.{source_id.value}.oauth_scopes")
        configured_oauth = OAuthRequirement(
            required=oauth_required,
            client_type=OAuthClientType(oauth_client_type_value) if oauth_client_type_value is not None else None,
            grant_type=OAuthGrantType(oauth_grant_type_value) if oauth_grant_type_value is not None else None,
            scopes=oauth_scopes,
        )
        if configured_oauth != contract.oauth:
            raise MarketSourceContractError(
                f"sources.{source_id.value} OAuth contract must stay {contract.oauth}."
            )

        configured_source = ConfiguredSource(
            contract=contract,
            enabled=_as_bool(source_data.get("enabled"), f"sources.{source_id.value}.enabled"),
            role=SourceRole(_as_non_empty_string(source_data.get("role"), f"sources.{source_id.value}.role")),
            endpoint=_as_string_or_none(source_data.get("endpoint"), f"sources.{source_id.value}.endpoint"),
            derived_from=_as_string_or_none(source_data.get("derived_from"), f"sources.{source_id.value}.derived_from"),
            checkpoint_namespace=_as_non_empty_string(
                source_data.get("checkpoint_namespace"),
                f"sources.{source_id.value}.checkpoint_namespace",
            ),
            expected_delay_seconds=_as_int(
                source_data.get("expected_delay_seconds"),
                f"sources.{source_id.value}.expected_delay_seconds",
                minimum=0,
            ),
            rate_limit_headers=_as_string_tuple(
                source_data.get("rate_limit_headers", []),
                f"sources.{source_id.value}.rate_limit_headers",
            ),
            feature_flag=_as_string_or_none(source_data.get("feature_flag"), f"sources.{source_id.value}.feature_flag"),
        )
        configured_sources[source_id] = configured_source
    return configured_sources


def load_market_source_config(path: Path = DEFAULT_MARKET_SOURCES_PATH) -> MarketSourceConfig:
    with path.open("rb") as handle:
        return MarketSourceConfig.from_dict(tomllib.load(handle))


def load_raw_listing_schema(path: Path = DEFAULT_RAW_LISTING_SCHEMA_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
