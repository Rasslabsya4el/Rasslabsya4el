"""Craft of Exile intake and bounded route contract surface."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from poe_build_research.market.source_contracts import Realm

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_COE_ROUTE_BUNDLE_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "craft" / "coe_route_bundle.schema.json"
COE_ROUTE_BUNDLE_SCHEMA_VERSION = "1.0.0"
COE_ROUTE_BUNDLE_RECORD_KIND = "coe_route_bundle"
COE_ROUTE_BUNDLE_GENERATOR = "poe_build_research.craft.coe_contract"
COE_INTEGRATION_NAME = "craft_of_exile"

SUPPORTED_OUTPUTS = (
    "coe_intake",
    "coe_data_points",
    "bounded_route_surface",
    "cost_estimate_context",
    "assumption_context",
)
UNSUPPORTED_CAPABILITIES = (
    "buy_vs_craft_reasoning",
    "market_arbitrage",
    "build_choice_ranking",
    "live_browser_automation",
    "site_scrape",
    "full_route_search",
)
DEFAULT_WRAPPER_NOTE = (
    "This Craft of Exile wrapper preserves intake, data points, and bounded "
    "route hypotheses only; market comparison and buy-vs-craft reasoning stay "
    "downstream."
)
DEFAULT_LIMITATIONS = (
    "This surface preserves Craft of Exile data captures and bounded route hypotheses only.",
    "Consumers must compare route costs against market evidence separately.",
    "The wrapper does not perform buy-vs-craft reasoning, market arbitrage, or build-choice ranking.",
    "No repo-supported Craft of Exile live runtime is proven yet.",
)
DEFAULT_BUNDLE_FRESHNESS_NOTE = (
    "Bundle freshness tracks the newest captured Craft of Exile evidence only; "
    "downstream market freshness lives in separate market surfaces."
)


class CraftContractError(RuntimeError):
    """Raised when the craft contract surface is malformed or ambiguous."""


class WrapperStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    SIMULATED_ONLY = "simulated_only"
    MANUAL_EVIDENCE = "manual_evidence"


class SimulationTrustLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CostBasis(StrEnum):
    SIMULATION = "simulation"
    MANUAL_EVIDENCE = "manual_evidence"
    OPERATOR_ESTIMATE = "operator_estimate"


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    MANUAL_CAPTURE = "manual_capture"


class TargetRarity(StrEnum):
    NORMAL = "normal"
    MAGIC = "magic"
    RARE = "rare"


class ModSource(StrEnum):
    EXPLICIT = "explicit"
    FRACTURED = "fractured"
    INFLUENCED = "influenced"
    BENCH = "bench"
    IMPLICIT = "implicit"


class DataPointKind(StrEnum):
    BASE_REQUIREMENT = "base_requirement"
    CURRENCY_COST_HINT = "currency_cost_hint"
    ROUTE_GATE = "route_gate"
    SIMULATION_OBSERVATION = "simulation_observation"


def _stable_json(payload: Any) -> str:
    try:
        return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    except ValueError as exc:
        raise CraftContractError("Craft payload contains non-finite numeric values.") from exc


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _as_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CraftContractError(f"{field_name} must be an object.")
    return value


def _as_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CraftContractError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _as_iso8601(value: Any, field_name: str) -> str:
    text = _as_non_empty_string(value, field_name)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CraftContractError(f"{field_name} must be an ISO 8601 timestamp.") from exc
    return text


def _as_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise CraftContractError(f"{field_name} must be a boolean.")
    return value


def _as_int(value: Any, field_name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CraftContractError(f"{field_name} must be an integer.")
    if minimum is not None and value < minimum:
        raise CraftContractError(f"{field_name} must be >= {minimum}.")
    return value


def _as_float(value: Any, field_name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CraftContractError(f"{field_name} must be numeric.")
    normalized = float(value)
    if minimum is not None and normalized < minimum:
        raise CraftContractError(f"{field_name} must be >= {minimum}.")
    return normalized


def _as_optional_float(value: Any, field_name: str, *, minimum: float | None = None) -> float | None:
    if value is None:
        return None
    return _as_float(value, field_name, minimum=minimum)


def _as_str_enum(value: Any, enum_type: type[StrEnum], field_name: str) -> StrEnum:
    try:
        return enum_type(_as_non_empty_string(value, field_name))
    except ValueError as exc:
        allowed = ", ".join(member.value for member in enum_type)
        raise CraftContractError(f"{field_name} must be one of: {allowed}.") from exc


def _as_unique_string_tuple(value: Any, field_name: str, *, minimum_items: int = 0) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise CraftContractError(f"{field_name} must be an array.")
    items = tuple(_as_non_empty_string(item, f"{field_name}[]") for item in value)
    if len(set(items)) != len(items):
        raise CraftContractError(f"{field_name} must not contain duplicates.")
    if len(items) < minimum_items:
        raise CraftContractError(f"{field_name} must contain at least {minimum_items} entries.")
    return items


def _coerce_assumptions(value: Any, field_name: str, *, minimum_items: int = 0) -> tuple["Assumption", ...]:
    if not isinstance(value, list):
        raise CraftContractError(f"{field_name} must be an array.")
    assumptions = tuple(
        item if isinstance(item, Assumption) else Assumption.from_dict(_as_mapping(item, f"{field_name}[{index}]"))
        for index, item in enumerate(value)
    )
    if len(assumptions) < minimum_items:
        raise CraftContractError(f"{field_name} must contain at least {minimum_items} entries.")
    return assumptions


def _coerce_provenance_refs(value: Any, field_name: str, *, minimum_items: int = 1) -> tuple["ProvenanceRef", ...]:
    if not isinstance(value, list):
        raise CraftContractError(f"{field_name} must be an array.")
    refs = tuple(
        item if isinstance(item, ProvenanceRef) else ProvenanceRef.from_dict(_as_mapping(item, f"{field_name}[{index}]"))
        for index, item in enumerate(value)
    )
    if len(refs) < minimum_items:
        raise CraftContractError(f"{field_name} must contain at least {minimum_items} entries.")
    return refs


def _coerce_steps(value: Any, field_name: str) -> tuple["CraftStep", ...]:
    if not isinstance(value, list):
        raise CraftContractError(f"{field_name} must be an array.")
    steps = tuple(
        item if isinstance(item, CraftStep) else CraftStep.from_dict(_as_mapping(item, f"{field_name}[{index}]"))
        for index, item in enumerate(value)
    )
    if not steps:
        raise CraftContractError(f"{field_name} must contain at least one entry.")
    expected_steps = tuple(range(1, len(steps) + 1))
    actual_steps = tuple(step.step for step in steps)
    if actual_steps != expected_steps:
        raise CraftContractError(f"{field_name} step numbers must be contiguous from 1.")
    return steps


def _coerce_freshness(value: Any, field_name: str) -> "FreshnessEnvelope":
    if isinstance(value, FreshnessEnvelope):
        return value
    return FreshnessEnvelope.from_dict(_as_mapping(value, field_name))


def _parse_iso8601(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _max_observed_at(timestamps: list[str]) -> str:
    return max(timestamps, key=_parse_iso8601)


def _derive_bundle_freshness_status(statuses: list[FreshnessStatus]) -> FreshnessStatus:
    if any(status is FreshnessStatus.STALE for status in statuses):
        return FreshnessStatus.STALE
    if any(status is FreshnessStatus.MANUAL_CAPTURE for status in statuses):
        return FreshnessStatus.MANUAL_CAPTURE
    return FreshnessStatus.FRESH


@dataclass(frozen=True, slots=True)
class ProvenanceRef:
    record_kind: str
    record_id: str
    source_uri: str
    observed_at: str
    collector: str
    collected_at: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_kind", _as_non_empty_string(self.record_kind, "record_kind"))
        object.__setattr__(self, "record_id", _as_non_empty_string(self.record_id, "record_id"))
        object.__setattr__(self, "source_uri", _as_non_empty_string(self.source_uri, "source_uri"))
        object.__setattr__(self, "observed_at", _as_iso8601(self.observed_at, "observed_at"))
        object.__setattr__(self, "collector", _as_non_empty_string(self.collector, "collector"))
        if self.collected_at is not None:
            object.__setattr__(self, "collected_at", _as_iso8601(self.collected_at, "collected_at"))
        if self.note is not None:
            object.__setattr__(self, "note", _as_non_empty_string(self.note, "note"))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ProvenanceRef":
        return cls(
            record_kind=payload.get("record_kind"),
            record_id=payload.get("record_id"),
            source_uri=payload.get("source_uri"),
            observed_at=payload.get("observed_at"),
            collector=payload.get("collector"),
            collected_at=payload.get("collected_at"),
            note=payload.get("note"),
        )

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
class FreshnessEnvelope:
    status: FreshnessStatus | str
    observed_at: str
    captured_at: str
    note: str
    expires_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _as_str_enum(self.status, FreshnessStatus, "status"))
        object.__setattr__(self, "observed_at", _as_iso8601(self.observed_at, "observed_at"))
        object.__setattr__(self, "captured_at", _as_iso8601(self.captured_at, "captured_at"))
        object.__setattr__(self, "note", _as_non_empty_string(self.note, "note"))
        if self.expires_at is not None:
            object.__setattr__(self, "expires_at", _as_iso8601(self.expires_at, "expires_at"))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FreshnessEnvelope":
        return cls(
            status=payload.get("status"),
            observed_at=payload.get("observed_at"),
            captured_at=payload.get("captured_at"),
            note=payload.get("note"),
            expires_at=payload.get("expires_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "observed_at": self.observed_at,
            "captured_at": self.captured_at,
            "note": self.note,
            "expires_at": self.expires_at,
        }


@dataclass(frozen=True, slots=True)
class CostBand:
    currency: str = "chaos"
    low: float = 0.0
    expected: float = 0.0
    high: float = 0.0
    basis: CostBasis | str = CostBasis.SIMULATION
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "currency", _as_non_empty_string(self.currency, "currency"))
        if self.currency != "chaos":
            raise CraftContractError("currency must stay 'chaos'.")
        object.__setattr__(self, "low", _as_float(self.low, "low", minimum=0.0))
        object.__setattr__(self, "expected", _as_float(self.expected, "expected", minimum=0.0))
        object.__setattr__(self, "high", _as_float(self.high, "high", minimum=0.0))
        if self.low > self.expected or self.expected > self.high:
            raise CraftContractError("cost band must satisfy low <= expected <= high.")
        object.__setattr__(self, "basis", _as_str_enum(self.basis, CostBasis, "basis"))
        if self.note is not None:
            object.__setattr__(self, "note", _as_non_empty_string(self.note, "note"))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CostBand":
        return cls(
            currency=payload.get("currency"),
            low=payload.get("low"),
            expected=payload.get("expected"),
            high=payload.get("high"),
            basis=payload.get("basis"),
            note=payload.get("note"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "currency": self.currency,
            "low": self.low,
            "expected": self.expected,
            "high": self.high,
            "basis": self.basis.value,
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class Assumption:
    key: str
    statement: str
    source: str
    impact: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _as_non_empty_string(self.key, "key"))
        object.__setattr__(self, "statement", _as_non_empty_string(self.statement, "statement"))
        object.__setattr__(self, "source", _as_non_empty_string(self.source, "source"))
        object.__setattr__(self, "impact", _as_non_empty_string(self.impact, "impact"))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Assumption":
        return cls(
            key=payload.get("key"),
            statement=payload.get("statement"),
            source=payload.get("source"),
            impact=payload.get("impact"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "statement": self.statement,
            "source": self.source,
            "impact": self.impact,
        }


@dataclass(frozen=True, slots=True)
class CraftTargetItem:
    slot: str
    base_type: str
    item_class: str | None = None
    rarity: TargetRarity | str = TargetRarity.RARE
    item_level: int | None = None
    influence_tags: tuple[str, ...] = ()
    fractured: bool = False
    corrupted: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot", _as_non_empty_string(self.slot, "slot"))
        object.__setattr__(self, "base_type", _as_non_empty_string(self.base_type, "base_type"))
        if self.item_class is not None:
            object.__setattr__(self, "item_class", _as_non_empty_string(self.item_class, "item_class"))
        object.__setattr__(self, "rarity", _as_str_enum(self.rarity, TargetRarity, "rarity"))
        if self.item_level is not None:
            object.__setattr__(self, "item_level", _as_int(self.item_level, "item_level", minimum=1))
        object.__setattr__(
            self,
            "influence_tags",
            tuple(_as_non_empty_string(tag, "influence_tags[]") for tag in self.influence_tags),
        )
        object.__setattr__(self, "fractured", _as_bool(self.fractured, "fractured"))
        object.__setattr__(self, "corrupted", _as_bool(self.corrupted, "corrupted"))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CraftTargetItem":
        return cls(
            slot=payload.get("slot"),
            base_type=payload.get("base_type"),
            item_class=payload.get("item_class"),
            rarity=payload.get("rarity"),
            item_level=payload.get("item_level"),
            influence_tags=tuple(payload.get("influence_tags", [])),
            fractured=payload.get("fractured"),
            corrupted=payload.get("corrupted"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot": self.slot,
            "base_type": self.base_type,
            "item_class": self.item_class,
            "rarity": self.rarity.value,
            "item_level": self.item_level,
            "influence_tags": list(self.influence_tags),
            "fractured": self.fractured,
            "corrupted": self.corrupted,
        }


@dataclass(frozen=True, slots=True)
class DesiredCoreMod:
    stat_key: str
    label: str
    minimum_value: float | None = None
    preferred_tier: str | None = None
    priority: int = 100
    source: ModSource | str = ModSource.EXPLICIT

    def __post_init__(self) -> None:
        object.__setattr__(self, "stat_key", _as_non_empty_string(self.stat_key, "stat_key"))
        object.__setattr__(self, "label", _as_non_empty_string(self.label, "label"))
        if self.minimum_value is not None:
            object.__setattr__(self, "minimum_value", _as_float(self.minimum_value, "minimum_value"))
        if self.preferred_tier is not None:
            object.__setattr__(self, "preferred_tier", _as_non_empty_string(self.preferred_tier, "preferred_tier"))
        object.__setattr__(self, "priority", _as_int(self.priority, "priority", minimum=1))
        object.__setattr__(self, "source", _as_str_enum(self.source, ModSource, "source"))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DesiredCoreMod":
        return cls(
            stat_key=payload.get("stat_key"),
            label=payload.get("label"),
            minimum_value=payload.get("minimum_value"),
            preferred_tier=payload.get("preferred_tier"),
            priority=payload.get("priority"),
            source=payload.get("source"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "stat_key": self.stat_key,
            "label": self.label,
            "minimum_value": self.minimum_value,
            "preferred_tier": self.preferred_tier,
            "priority": self.priority,
            "source": self.source.value,
        }


def _coerce_desired_core(value: Any, field_name: str) -> tuple[DesiredCoreMod, ...]:
    if not isinstance(value, list):
        raise CraftContractError(f"{field_name} must be an array.")
    desired_core = tuple(
        item if isinstance(item, DesiredCoreMod) else DesiredCoreMod.from_dict(_as_mapping(item, f"{field_name}[{index}]"))
        for index, item in enumerate(value)
    )
    if not desired_core:
        raise CraftContractError(f"{field_name} must contain at least one core mod.")
    return desired_core


@dataclass(frozen=True, slots=True)
class CraftConstraints:
    league: str
    realm: Realm | str = Realm.PC
    max_budget_chaos: float | None = None
    max_steps: int | None = None
    allow_fractured_bases: bool = True
    allow_influence: bool = False
    ssf_mode: bool = False
    banned_methods: tuple[str, ...] = ()
    required_methods: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "league", _as_non_empty_string(self.league, "league"))
        object.__setattr__(self, "realm", _as_str_enum(self.realm, Realm, "realm"))
        if self.max_budget_chaos is not None:
            object.__setattr__(
                self,
                "max_budget_chaos",
                _as_float(self.max_budget_chaos, "max_budget_chaos", minimum=0.0),
            )
        if self.max_steps is not None:
            object.__setattr__(self, "max_steps", _as_int(self.max_steps, "max_steps", minimum=1))
        object.__setattr__(self, "allow_fractured_bases", _as_bool(self.allow_fractured_bases, "allow_fractured_bases"))
        object.__setattr__(self, "allow_influence", _as_bool(self.allow_influence, "allow_influence"))
        object.__setattr__(self, "ssf_mode", _as_bool(self.ssf_mode, "ssf_mode"))
        object.__setattr__(
            self,
            "banned_methods",
            tuple(_as_non_empty_string(item, "banned_methods[]") for item in self.banned_methods),
        )
        object.__setattr__(
            self,
            "required_methods",
            tuple(_as_non_empty_string(item, "required_methods[]") for item in self.required_methods),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CraftConstraints":
        return cls(
            league=payload.get("league"),
            realm=payload.get("realm"),
            max_budget_chaos=payload.get("max_budget_chaos"),
            max_steps=payload.get("max_steps"),
            allow_fractured_bases=payload.get("allow_fractured_bases"),
            allow_influence=payload.get("allow_influence"),
            ssf_mode=payload.get("ssf_mode"),
            banned_methods=tuple(payload.get("banned_methods", [])),
            required_methods=tuple(payload.get("required_methods", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "league": self.league,
            "realm": self.realm.value,
            "max_budget_chaos": self.max_budget_chaos,
            "max_steps": self.max_steps,
            "allow_fractured_bases": self.allow_fractured_bases,
            "allow_influence": self.allow_influence,
            "ssf_mode": self.ssf_mode,
            "banned_methods": list(self.banned_methods),
            "required_methods": list(self.required_methods),
        }


@dataclass(frozen=True, slots=True)
class CoEIntake:
    intake_id: str
    goal: str
    target_item: CraftTargetItem
    desired_core: tuple[DesiredCoreMod, ...]
    constraints: CraftConstraints
    provenance: tuple[ProvenanceRef, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "intake_id", _as_non_empty_string(self.intake_id, "intake_id"))
        object.__setattr__(self, "goal", _as_non_empty_string(self.goal, "goal"))
        if not isinstance(self.target_item, CraftTargetItem):
            raise CraftContractError("target_item must be a CraftTargetItem.")
        object.__setattr__(self, "desired_core", tuple(self.desired_core))
        if not self.desired_core:
            raise CraftContractError("desired_core must contain at least one core mod.")
        for index, mod in enumerate(self.desired_core):
            if not isinstance(mod, DesiredCoreMod):
                raise CraftContractError(f"desired_core[{index}] must be a DesiredCoreMod.")
        if not isinstance(self.constraints, CraftConstraints):
            raise CraftContractError("constraints must be a CraftConstraints.")
        object.__setattr__(self, "provenance", tuple(self.provenance))
        if not self.provenance:
            raise CraftContractError("provenance must contain at least one ref.")
        for index, ref in enumerate(self.provenance):
            if not isinstance(ref, ProvenanceRef):
                raise CraftContractError(f"provenance[{index}] must be a ProvenanceRef.")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CoEIntake":
        return cls(
            intake_id=payload.get("intake_id"),
            goal=payload.get("goal"),
            target_item=CraftTargetItem.from_dict(_as_mapping(payload.get("target_item"), "intake.target_item")),
            desired_core=_coerce_desired_core(payload.get("desired_core"), "intake.desired_core"),
            constraints=CraftConstraints.from_dict(_as_mapping(payload.get("constraints"), "intake.constraints")),
            provenance=_coerce_provenance_refs(payload.get("provenance"), "intake.provenance"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "intake_id": self.intake_id,
            "goal": self.goal,
            "target_item": self.target_item.to_dict(),
            "desired_core": [mod.to_dict() for mod in self.desired_core],
            "constraints": self.constraints.to_dict(),
            "provenance": [ref.to_dict() for ref in self.provenance],
        }


@dataclass(frozen=True, slots=True)
class CoEWrapperSurface:
    integration_name: str = COE_INTEGRATION_NAME
    surface_version: str = COE_ROUTE_BUNDLE_SCHEMA_VERSION
    runtime_status: WrapperStatus | str = WrapperStatus.UNSUPPORTED
    supported_outputs: tuple[str, ...] = SUPPORTED_OUTPUTS
    unsupported_capabilities: tuple[str, ...] = UNSUPPORTED_CAPABILITIES
    note: str = DEFAULT_WRAPPER_NOTE

    def __post_init__(self) -> None:
        object.__setattr__(self, "integration_name", _as_non_empty_string(self.integration_name, "integration_name"))
        object.__setattr__(self, "surface_version", _as_non_empty_string(self.surface_version, "surface_version"))
        if self.integration_name != COE_INTEGRATION_NAME:
            raise CraftContractError(f"integration_name must stay {COE_INTEGRATION_NAME}.")
        if self.surface_version != COE_ROUTE_BUNDLE_SCHEMA_VERSION:
            raise CraftContractError(f"surface_version must stay {COE_ROUTE_BUNDLE_SCHEMA_VERSION}.")
        object.__setattr__(self, "runtime_status", _as_str_enum(self.runtime_status, WrapperStatus, "runtime_status"))
        object.__setattr__(
            self,
            "supported_outputs",
            tuple(_as_non_empty_string(item, "supported_outputs[]") for item in self.supported_outputs),
        )
        object.__setattr__(
            self,
            "unsupported_capabilities",
            tuple(_as_non_empty_string(item, "unsupported_capabilities[]") for item in self.unsupported_capabilities),
        )
        object.__setattr__(self, "note", _as_non_empty_string(self.note, "note"))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CoEWrapperSurface":
        return cls(
            integration_name=payload.get("integration_name"),
            surface_version=payload.get("surface_version"),
            runtime_status=payload.get("runtime_status"),
            supported_outputs=tuple(payload.get("supported_outputs", [])),
            unsupported_capabilities=tuple(payload.get("unsupported_capabilities", [])),
            note=payload.get("note"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "integration_name": self.integration_name,
            "surface_version": self.surface_version,
            "runtime_status": self.runtime_status.value,
            "supported_outputs": list(self.supported_outputs),
            "unsupported_capabilities": list(self.unsupported_capabilities),
            "note": self.note,
        }


def default_wrapper_surface() -> CoEWrapperSurface:
    """Return the current contract-first CoE wrapper boundary."""

    return CoEWrapperSurface()


@dataclass(frozen=True, slots=True)
class CoEDataPoint:
    data_id: str
    kind: DataPointKind | str
    label: str
    value_summary: str
    numeric_value: float | None
    unit: str | None
    cost_hint: CostBand | None
    assumptions: tuple[Assumption, ...]
    freshness: FreshnessEnvelope
    provenance: tuple[ProvenanceRef, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_id", _as_non_empty_string(self.data_id, "data_id"))
        object.__setattr__(self, "kind", _as_str_enum(self.kind, DataPointKind, "kind"))
        object.__setattr__(self, "label", _as_non_empty_string(self.label, "label"))
        object.__setattr__(self, "value_summary", _as_non_empty_string(self.value_summary, "value_summary"))
        if self.numeric_value is not None:
            object.__setattr__(self, "numeric_value", _as_float(self.numeric_value, "numeric_value"))
        if self.unit is not None:
            object.__setattr__(self, "unit", _as_non_empty_string(self.unit, "unit"))
        if self.cost_hint is not None and not isinstance(self.cost_hint, CostBand):
            raise CraftContractError("cost_hint must be a CostBand when provided.")
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        for index, assumption in enumerate(self.assumptions):
            if not isinstance(assumption, Assumption):
                raise CraftContractError(f"assumptions[{index}] must be an Assumption.")
        if not isinstance(self.freshness, FreshnessEnvelope):
            raise CraftContractError("freshness must be a FreshnessEnvelope.")
        object.__setattr__(self, "provenance", tuple(self.provenance))
        if not self.provenance:
            raise CraftContractError("provenance must contain at least one ref.")
        for index, ref in enumerate(self.provenance):
            if not isinstance(ref, ProvenanceRef):
                raise CraftContractError(f"provenance[{index}] must be a ProvenanceRef.")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CoEDataPoint":
        cost_hint = payload.get("cost_hint")
        return cls(
            data_id=payload.get("data_id"),
            kind=payload.get("kind"),
            label=payload.get("label"),
            value_summary=payload.get("value_summary"),
            numeric_value=payload.get("numeric_value"),
            unit=payload.get("unit"),
            cost_hint=None if cost_hint is None else CostBand.from_dict(_as_mapping(cost_hint, "data_point.cost_hint")),
            assumptions=_coerce_assumptions(payload.get("assumptions", []), "data_point.assumptions"),
            freshness=_coerce_freshness(payload.get("freshness"), "data_point.freshness"),
            provenance=_coerce_provenance_refs(payload.get("provenance"), "data_point.provenance"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_id": self.data_id,
            "kind": self.kind.value,
            "label": self.label,
            "value_summary": self.value_summary,
            "numeric_value": self.numeric_value,
            "unit": self.unit,
            "cost_hint": None if self.cost_hint is None else self.cost_hint.to_dict(),
            "assumptions": [assumption.to_dict() for assumption in self.assumptions],
            "freshness": self.freshness.to_dict(),
            "provenance": [ref.to_dict() for ref in self.provenance],
        }


def _coerce_data_points(value: Any, field_name: str) -> tuple[CoEDataPoint, ...]:
    if not isinstance(value, list):
        raise CraftContractError(f"{field_name} must be an array.")
    data_points = tuple(
        item if isinstance(item, CoEDataPoint) else CoEDataPoint.from_dict(_as_mapping(item, f"{field_name}[{index}]"))
        for index, item in enumerate(value)
    )
    if not data_points:
        raise CraftContractError(f"{field_name} must contain at least one entry.")
    return data_points


@dataclass(frozen=True, slots=True)
class CraftStep:
    step: int
    action: str
    goal: str
    currency_item: str | None = None
    notes: str | None = None
    cost_hint_chaos: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "step", _as_int(self.step, "step", minimum=1))
        object.__setattr__(self, "action", _as_non_empty_string(self.action, "action"))
        object.__setattr__(self, "goal", _as_non_empty_string(self.goal, "goal"))
        if self.currency_item is not None:
            object.__setattr__(self, "currency_item", _as_non_empty_string(self.currency_item, "currency_item"))
        if self.notes is not None:
            object.__setattr__(self, "notes", _as_non_empty_string(self.notes, "notes"))
        if self.cost_hint_chaos is not None:
            object.__setattr__(
                self,
                "cost_hint_chaos",
                _as_float(self.cost_hint_chaos, "cost_hint_chaos", minimum=0.0),
            )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CraftStep":
        return cls(
            step=payload.get("step"),
            action=payload.get("action"),
            goal=payload.get("goal"),
            currency_item=payload.get("currency_item"),
            notes=payload.get("notes"),
            cost_hint_chaos=payload.get("cost_hint_chaos"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "action": self.action,
            "goal": self.goal,
            "currency_item": self.currency_item,
            "notes": self.notes,
            "cost_hint_chaos": self.cost_hint_chaos,
        }


@dataclass(frozen=True, slots=True)
class CoERoute:
    route_id: str
    label: str
    status: WrapperStatus | str
    route_kind: str
    simulation_trust_level: SimulationTrustLevel | str
    summary: str
    supporting_data_ids: tuple[str, ...]
    steps: tuple[CraftStep, ...]
    estimated_cost: CostBand | None
    assumptions: tuple[Assumption, ...]
    freshness: FreshnessEnvelope
    provenance: tuple[ProvenanceRef, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_id", _as_non_empty_string(self.route_id, "route_id"))
        object.__setattr__(self, "label", _as_non_empty_string(self.label, "label"))
        object.__setattr__(self, "status", _as_str_enum(self.status, WrapperStatus, "status"))
        object.__setattr__(self, "route_kind", _as_non_empty_string(self.route_kind, "route_kind"))
        object.__setattr__(
            self,
            "simulation_trust_level",
            _as_str_enum(self.simulation_trust_level, SimulationTrustLevel, "simulation_trust_level"),
        )
        object.__setattr__(self, "summary", _as_non_empty_string(self.summary, "summary"))
        object.__setattr__(
            self,
            "supporting_data_ids",
            tuple(_as_non_empty_string(item, "supporting_data_ids[]") for item in self.supporting_data_ids),
        )
        if not self.supporting_data_ids:
            raise CraftContractError("supporting_data_ids must contain at least one entry.")
        if len(set(self.supporting_data_ids)) != len(self.supporting_data_ids):
            raise CraftContractError("supporting_data_ids must not contain duplicates.")
        object.__setattr__(self, "steps", tuple(self.steps))
        if not self.steps:
            raise CraftContractError("steps must contain at least one entry.")
        for index, step in enumerate(self.steps):
            if not isinstance(step, CraftStep):
                raise CraftContractError(f"steps[{index}] must be a CraftStep.")
        if self.estimated_cost is not None and not isinstance(self.estimated_cost, CostBand):
            raise CraftContractError("estimated_cost must be a CostBand when provided.")
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        if not self.assumptions:
            raise CraftContractError("assumptions must contain at least one entry.")
        for index, assumption in enumerate(self.assumptions):
            if not isinstance(assumption, Assumption):
                raise CraftContractError(f"assumptions[{index}] must be an Assumption.")
        if not isinstance(self.freshness, FreshnessEnvelope):
            raise CraftContractError("freshness must be a FreshnessEnvelope.")
        object.__setattr__(self, "provenance", tuple(self.provenance))
        if not self.provenance:
            raise CraftContractError("provenance must contain at least one ref.")
        for index, ref in enumerate(self.provenance):
            if not isinstance(ref, ProvenanceRef):
                raise CraftContractError(f"provenance[{index}] must be a ProvenanceRef.")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CoERoute":
        estimated_cost = payload.get("estimated_cost")
        return cls(
            route_id=payload.get("route_id"),
            label=payload.get("label"),
            status=payload.get("status"),
            route_kind=payload.get("route_kind"),
            simulation_trust_level=payload.get("simulation_trust_level"),
            summary=payload.get("summary"),
            supporting_data_ids=tuple(payload.get("supporting_data_ids", [])),
            steps=_coerce_steps(payload.get("steps"), "route.steps"),
            estimated_cost=None if estimated_cost is None else CostBand.from_dict(_as_mapping(estimated_cost, "route.estimated_cost")),
            assumptions=_coerce_assumptions(payload.get("assumptions"), "route.assumptions", minimum_items=1),
            freshness=_coerce_freshness(payload.get("freshness"), "route.freshness"),
            provenance=_coerce_provenance_refs(payload.get("provenance"), "route.provenance"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "label": self.label,
            "status": self.status.value,
            "route_kind": self.route_kind,
            "simulation_trust_level": self.simulation_trust_level.value,
            "summary": self.summary,
            "supporting_data_ids": list(self.supporting_data_ids),
            "steps": [step.to_dict() for step in self.steps],
            "estimated_cost": None if self.estimated_cost is None else self.estimated_cost.to_dict(),
            "assumptions": [assumption.to_dict() for assumption in self.assumptions],
            "freshness": self.freshness.to_dict(),
            "provenance": [ref.to_dict() for ref in self.provenance],
        }


def _coerce_routes(value: Any, field_name: str) -> tuple[CoERoute, ...]:
    if not isinstance(value, list):
        raise CraftContractError(f"{field_name} must be an array.")
    routes = tuple(
        item if isinstance(item, CoERoute) else CoERoute.from_dict(_as_mapping(item, f"{field_name}[{index}]"))
        for index, item in enumerate(value)
    )
    if not routes:
        raise CraftContractError(f"{field_name} must contain at least one entry.")
    return routes


@dataclass(frozen=True, slots=True)
class CoEBundleProvenance:
    generated_at: str
    generator: str = COE_ROUTE_BUNDLE_GENERATOR
    generator_version: str = COE_ROUTE_BUNDLE_SCHEMA_VERSION
    source_name: str = COE_INTEGRATION_NAME
    runtime_status: WrapperStatus | str = WrapperStatus.UNSUPPORTED
    input_sha256: str = ""
    bundle_sha256: str = ""
    input_provenance: tuple[ProvenanceRef, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", _as_iso8601(self.generated_at, "generated_at"))
        object.__setattr__(self, "generator", _as_non_empty_string(self.generator, "generator"))
        object.__setattr__(self, "generator_version", _as_non_empty_string(self.generator_version, "generator_version"))
        object.__setattr__(self, "source_name", _as_non_empty_string(self.source_name, "source_name"))
        if self.generator != COE_ROUTE_BUNDLE_GENERATOR:
            raise CraftContractError(f"generator must stay {COE_ROUTE_BUNDLE_GENERATOR}.")
        if self.generator_version != COE_ROUTE_BUNDLE_SCHEMA_VERSION:
            raise CraftContractError(f"generator_version must stay {COE_ROUTE_BUNDLE_SCHEMA_VERSION}.")
        if self.source_name != COE_INTEGRATION_NAME:
            raise CraftContractError(f"source_name must stay {COE_INTEGRATION_NAME}.")
        object.__setattr__(self, "runtime_status", _as_str_enum(self.runtime_status, WrapperStatus, "runtime_status"))
        object.__setattr__(self, "input_sha256", _as_non_empty_string(self.input_sha256, "input_sha256"))
        object.__setattr__(self, "bundle_sha256", _as_non_empty_string(self.bundle_sha256, "bundle_sha256"))
        if len(self.input_sha256) != 64 or any(char not in "0123456789abcdef" for char in self.input_sha256):
            raise CraftContractError("input_sha256 must be a lowercase SHA-256 digest.")
        if len(self.bundle_sha256) != 64 or any(char not in "0123456789abcdef" for char in self.bundle_sha256):
            raise CraftContractError("bundle_sha256 must be a lowercase SHA-256 digest.")
        object.__setattr__(self, "input_provenance", tuple(self.input_provenance))
        if not self.input_provenance:
            raise CraftContractError("input_provenance must contain at least one ref.")
        for index, ref in enumerate(self.input_provenance):
            if not isinstance(ref, ProvenanceRef):
                raise CraftContractError(f"input_provenance[{index}] must be a ProvenanceRef.")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CoEBundleProvenance":
        return cls(
            generated_at=payload.get("generated_at"),
            generator=payload.get("generator"),
            generator_version=payload.get("generator_version"),
            source_name=payload.get("source_name"),
            runtime_status=payload.get("runtime_status"),
            input_sha256=payload.get("input_sha256"),
            bundle_sha256=payload.get("bundle_sha256"),
            input_provenance=_coerce_provenance_refs(payload.get("input_provenance"), "bundle_provenance.input_provenance"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "generator": self.generator,
            "generator_version": self.generator_version,
            "source_name": self.source_name,
            "runtime_status": self.runtime_status.value,
            "input_sha256": self.input_sha256,
            "bundle_sha256": self.bundle_sha256,
            "input_provenance": [ref.to_dict() for ref in self.input_provenance],
        }


@dataclass(frozen=True, slots=True)
class CoERouteBundle:
    bundle_id: str
    intake: CoEIntake
    wrapper_surface: CoEWrapperSurface
    data_points: tuple[CoEDataPoint, ...]
    routes: tuple[CoERoute, ...]
    provenance: CoEBundleProvenance
    freshness: FreshnessEnvelope
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "bundle_id", _as_non_empty_string(self.bundle_id, "bundle_id"))
        if not isinstance(self.intake, CoEIntake):
            raise CraftContractError("intake must be a CoEIntake.")
        if not isinstance(self.wrapper_surface, CoEWrapperSurface):
            raise CraftContractError("wrapper_surface must be a CoEWrapperSurface.")
        object.__setattr__(self, "data_points", tuple(self.data_points))
        if not self.data_points:
            raise CraftContractError("data_points must contain at least one entry.")
        data_ids: list[str] = []
        for index, data_point in enumerate(self.data_points):
            if not isinstance(data_point, CoEDataPoint):
                raise CraftContractError(f"data_points[{index}] must be a CoEDataPoint.")
            data_ids.append(data_point.data_id)
        if len(set(data_ids)) != len(data_ids):
            raise CraftContractError("data_points data_id values must be unique.")
        object.__setattr__(self, "routes", tuple(self.routes))
        if not self.routes:
            raise CraftContractError("routes must contain at least one entry.")
        route_ids: list[str] = []
        for index, route in enumerate(self.routes):
            if not isinstance(route, CoERoute):
                raise CraftContractError(f"routes[{index}] must be a CoERoute.")
            route_ids.append(route.route_id)
        if len(set(route_ids)) != len(route_ids):
            raise CraftContractError("routes route_id values must be unique.")
        if not isinstance(self.provenance, CoEBundleProvenance):
            raise CraftContractError("provenance must be a CoEBundleProvenance.")
        if not isinstance(self.freshness, FreshnessEnvelope):
            raise CraftContractError("freshness must be a FreshnessEnvelope.")
        object.__setattr__(self, "limitations", tuple(_as_non_empty_string(item, "limitations[]") for item in self.limitations))
        if not self.limitations:
            raise CraftContractError("limitations must contain at least one entry.")
        self._validate_links()

    def _validate_links(self) -> None:
        known_data_ids = {data_point.data_id for data_point in self.data_points}
        latest_observed_at = _max_observed_at(
            [data_point.freshness.observed_at for data_point in self.data_points]
            + [route.freshness.observed_at for route in self.routes]
        )
        if self.freshness.observed_at != latest_observed_at:
            raise CraftContractError("freshness.observed_at must match the newest supporting evidence timestamp.")
        if self.provenance.runtime_status != self.wrapper_surface.runtime_status:
            raise CraftContractError("provenance.runtime_status must match wrapper_surface.runtime_status.")
        if self.provenance.input_provenance != self.intake.provenance:
            raise CraftContractError("provenance.input_provenance must match intake.provenance.")
        for route in self.routes:
            if not set(route.supporting_data_ids).issubset(known_data_ids):
                raise CraftContractError("routes[].supporting_data_ids must reference known data_points[].data_id values.")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CoERouteBundle":
        schema_version = payload.get("schema_version")
        if schema_version is not None and schema_version != COE_ROUTE_BUNDLE_SCHEMA_VERSION:
            raise CraftContractError(f"schema_version must stay {COE_ROUTE_BUNDLE_SCHEMA_VERSION}.")
        record_kind = payload.get("record_kind")
        if record_kind is not None and record_kind != COE_ROUTE_BUNDLE_RECORD_KIND:
            raise CraftContractError(f"record_kind must stay {COE_ROUTE_BUNDLE_RECORD_KIND}.")
        return cls(
            bundle_id=payload.get("bundle_id"),
            intake=CoEIntake.from_dict(_as_mapping(payload.get("intake"), "coe_route_bundle.intake")),
            wrapper_surface=CoEWrapperSurface.from_dict(_as_mapping(payload.get("wrapper_surface"), "coe_route_bundle.wrapper_surface")),
            data_points=_coerce_data_points(payload.get("data_points"), "coe_route_bundle.data_points"),
            routes=_coerce_routes(payload.get("routes"), "coe_route_bundle.routes"),
            provenance=CoEBundleProvenance.from_dict(_as_mapping(payload.get("provenance"), "coe_route_bundle.provenance")),
            freshness=_coerce_freshness(payload.get("freshness"), "coe_route_bundle.freshness"),
            limitations=tuple(payload.get("limitations", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": COE_ROUTE_BUNDLE_SCHEMA_VERSION,
            "record_kind": COE_ROUTE_BUNDLE_RECORD_KIND,
            "bundle_id": self.bundle_id,
            "intake": self.intake.to_dict(),
            "wrapper_surface": self.wrapper_surface.to_dict(),
            "data_points": [data_point.to_dict() for data_point in self.data_points],
            "routes": [route.to_dict() for route in self.routes],
            "provenance": self.provenance.to_dict(),
            "freshness": self.freshness.to_dict(),
            "limitations": list(self.limitations),
        }

    def to_json(self) -> str:
        return _stable_json(self.to_dict())


def build_coe_route_bundle(
    intake: CoEIntake,
    *,
    data_points: tuple[CoEDataPoint, ...] | list[CoEDataPoint],
    routes: tuple[CoERoute, ...] | list[CoERoute],
    generated_at: str,
    wrapper_surface: CoEWrapperSurface | None = None,
    limitations: tuple[str, ...] | list[str] = DEFAULT_LIMITATIONS,
) -> CoERouteBundle:
    """Build a deterministic Craft of Exile route bundle without decision logic."""

    if not isinstance(intake, CoEIntake):
        raise CraftContractError("intake must be a CoEIntake.")
    wrapper_surface = default_wrapper_surface() if wrapper_surface is None else wrapper_surface
    if not isinstance(wrapper_surface, CoEWrapperSurface):
        raise CraftContractError("wrapper_surface must be a CoEWrapperSurface when provided.")

    normalized_generated_at = _as_iso8601(generated_at, "generated_at")
    normalized_data_points = tuple(data_points)
    normalized_routes = tuple(routes)
    if not normalized_data_points:
        raise CraftContractError("data_points must contain at least one entry.")
    if not normalized_routes:
        raise CraftContractError("routes must contain at least one entry.")
    for index, data_point in enumerate(normalized_data_points):
        if not isinstance(data_point, CoEDataPoint):
            raise CraftContractError(f"data_points[{index}] must be a CoEDataPoint.")
    for index, route in enumerate(normalized_routes):
        if not isinstance(route, CoERoute):
            raise CraftContractError(f"routes[{index}] must be a CoERoute.")

    input_payload = intake.to_dict()
    bundle_surface_payload = {
        "intake": input_payload,
        "wrapper_surface": wrapper_surface.to_dict(),
        "data_points": [data_point.to_dict() for data_point in normalized_data_points],
        "routes": [route.to_dict() for route in normalized_routes],
    }
    input_sha256 = _sha256_json(input_payload)
    bundle_sha256 = _sha256_json(bundle_surface_payload)
    latest_observed_at = _max_observed_at(
        [data_point.freshness.observed_at for data_point in normalized_data_points]
        + [route.freshness.observed_at for route in normalized_routes]
    )
    bundle_freshness_status = _derive_bundle_freshness_status(
        [data_point.freshness.status for data_point in normalized_data_points]
        + [route.freshness.status for route in normalized_routes]
    )
    provenance = CoEBundleProvenance(
        generated_at=normalized_generated_at,
        runtime_status=wrapper_surface.runtime_status,
        input_sha256=input_sha256,
        bundle_sha256=bundle_sha256,
        input_provenance=intake.provenance,
    )
    freshness = FreshnessEnvelope(
        status=bundle_freshness_status,
        observed_at=latest_observed_at,
        captured_at=normalized_generated_at,
        note=DEFAULT_BUNDLE_FRESHNESS_NOTE,
    )
    normalized_limitations = tuple(_as_non_empty_string(item, "limitations[]") for item in limitations)

    return CoERouteBundle(
        bundle_id=f"{COE_ROUTE_BUNDLE_RECORD_KIND}.{bundle_sha256[:16]}",
        intake=intake,
        wrapper_surface=wrapper_surface,
        data_points=normalized_data_points,
        routes=normalized_routes,
        provenance=provenance,
        freshness=freshness,
        limitations=normalized_limitations,
    )


def load_coe_route_bundle_schema(path: Path = DEFAULT_COE_ROUTE_BUNDLE_SCHEMA_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


__all__ = [
    "Assumption",
    "COE_INTEGRATION_NAME",
    "COE_ROUTE_BUNDLE_GENERATOR",
    "COE_ROUTE_BUNDLE_RECORD_KIND",
    "COE_ROUTE_BUNDLE_SCHEMA_VERSION",
    "CoEBundleProvenance",
    "CoEDataPoint",
    "CoEIntake",
    "CoERoute",
    "CoERouteBundle",
    "CoEWrapperSurface",
    "CostBand",
    "CostBasis",
    "CraftConstraints",
    "CraftContractError",
    "CraftStep",
    "CraftTargetItem",
    "DEFAULT_COE_ROUTE_BUNDLE_SCHEMA_PATH",
    "DataPointKind",
    "DesiredCoreMod",
    "FreshnessEnvelope",
    "FreshnessStatus",
    "ModSource",
    "ProvenanceRef",
    "SimulationTrustLevel",
    "TargetRarity",
    "WrapperStatus",
    "build_coe_route_bundle",
    "default_wrapper_surface",
    "load_coe_route_bundle_schema",
]
