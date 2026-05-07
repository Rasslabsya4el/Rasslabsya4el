"""Price parsing and window-specific normalization for market listings."""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping

from poe_build_research.market.source_contracts import MarketSourceConfig, Realm

PRICE_NOTE_PATTERN = re.compile(
    r"^\s*~(?:price|b/o)\s+"
    r"(?P<amount>[0-9]+(?:\.[0-9]+)?)"
    r"(?:/(?P<count>[0-9]+(?:\.[0-9]+)?))?\s+"
    r"(?P<currency>[A-Za-z][A-Za-z .'-]*)\s*$",
    re.IGNORECASE,
)
SAFE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

CURRENCY_ALIASES = {
    "c": "chaos",
    "chaos": "chaos",
    "chaos orb": "chaos",
    "chaos orbs": "chaos",
    "div": "divine",
    "divine": "divine",
    "divine orb": "divine",
    "divine orbs": "divine",
}
COMMODITY_CATEGORY_TOKENS = frozenset(
    {
        "currency",
        "fragment",
        "fragments",
        "scarab",
        "scarabs",
        "map",
        "maps",
        "divination_card",
        "divination cards",
        "fossil",
        "fossils",
        "resonator",
        "resonators",
        "essence",
        "essences",
        "oil",
        "oils",
    }
)
BASE_CURRENCY_NAMES = frozenset({"chaos orb", "divine orb"})


class MarketNormalizationError(RuntimeError):
    """Raised when a listing cannot be normalized into chaos/divine values."""


@dataclass(frozen=True, slots=True)
class ItemDescriptor:
    """Stable item identity used for window grouping and normalization."""

    item_key: str
    item_name: str
    item_kind: str
    stack_size: int


@dataclass(frozen=True, slots=True)
class ParsedListingPrice:
    """Parsed listing note price with explicit per-unit math."""

    note: str
    quote_currency: str
    quote_amount: float
    quoted_item_count: float
    total_currency_amount: float
    unit_currency_amount: float


@dataclass(frozen=True, slots=True)
class WindowCurrencyContext:
    """FX bridge evidence for one configured market window."""

    chaos_per_divine: float
    divine_per_chaos: float
    evidence_listing_ids: tuple[str, ...]
    evidence_item_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NormalizedListingPrice:
    """A listing price normalized into chaos and divine equivalents."""

    listing_id: str
    item_key: str
    item_name: str
    item_kind: str
    stack_size: int
    listed_note: str
    quote_currency: str
    quote_amount: float
    quoted_item_count: float
    total_chaos_value: float
    total_divine_value: float
    unit_chaos_value: float
    unit_divine_value: float


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug:
        raise MarketNormalizationError("Item key cannot be empty after normalization.")
    return slug


def _coerce_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MarketNormalizationError(f"{field_name} must be an object.")
    return value


def _coerce_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MarketNormalizationError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _coerce_positive_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MarketNormalizationError(f"{field_name} must be numeric.")
    normalized = float(value)
    if normalized <= 0:
        raise MarketNormalizationError(f"{field_name} must be > 0.")
    return normalized


def _extract_category_tokens(raw_payload: Mapping[str, Any]) -> set[str]:
    category = raw_payload.get("category")
    if category is None:
        return set()
    if isinstance(category, str):
        return {category.strip().lower()} if category.strip() else set()
    if isinstance(category, list):
        return {str(item).strip().lower() for item in category if str(item).strip()}
    if isinstance(category, Mapping):
        tokens: set[str] = set()
        for key, value in category.items():
            key_token = str(key).strip().lower()
            if key_token:
                tokens.add(key_token)
            if isinstance(value, list):
                tokens.update(str(item).strip().lower() for item in value if str(item).strip())
            elif value:
                value_token = str(value).strip().lower()
                if value_token:
                    tokens.add(value_token)
        return tokens
    return set()


def _extract_stack_size(raw_payload: Mapping[str, Any]) -> int:
    for key in ("stack_size", "stackSize", "stacksize", "stack"):
        value = raw_payload.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise MarketNormalizationError(f"item.raw_payload.{key} must be an integer when present.")
        if value < 1:
            raise MarketNormalizationError(f"item.raw_payload.{key} must be >= 1 when present.")
        return value
    return 1


def _canonical_currency(value: str) -> str:
    token = " ".join(value.strip().lower().split())
    canonical = CURRENCY_ALIASES.get(token)
    if canonical is None:
        raise MarketNormalizationError(f"Unsupported price currency '{value}'.")
    return canonical


def describe_listing_item(listing: Mapping[str, Any]) -> ItemDescriptor:
    """Return the stable item identity for one raw listing record."""

    item = _coerce_mapping(listing.get("item"), "listing.item")
    raw_payload = item.get("raw_payload")
    normalized_payload = _coerce_mapping(raw_payload, "listing.item.raw_payload") if raw_payload is not None else {}

    item_name = str(item.get("name") or "").strip()
    type_line = str(item.get("type_line") or "").strip()
    display_name = item_name or type_line
    if not display_name:
        raise MarketNormalizationError("listing.item.name or listing.item.type_line must be populated.")

    stack_size = _extract_stack_size(normalized_payload)
    category_tokens = _extract_category_tokens(normalized_payload)
    market_type = str(normalized_payload.get("market_type") or normalized_payload.get("marketType") or "").strip().lower()
    explicit_commodity = market_type == "commodity"
    commodity_like = (
        explicit_commodity
        or stack_size > 1
        or bool(category_tokens & COMMODITY_CATEGORY_TOKENS)
        or display_name.lower() in BASE_CURRENCY_NAMES
    )
    item_kind = "commodity" if commodity_like else "unique"
    key_basis = display_name
    return ItemDescriptor(
        item_key=f"{item_kind}:{_slugify(key_basis)}",
        item_name=display_name,
        item_kind=item_kind,
        stack_size=stack_size,
    )


def extract_listing_note(listing: Mapping[str, Any]) -> str:
    """Read the canonical listing note from the raw listing shape."""

    item = _coerce_mapping(listing.get("item"), "listing.item")
    direct_note = item.get("listed_note")
    if isinstance(direct_note, str) and direct_note.strip():
        return direct_note.strip()

    raw_payload = item.get("raw_payload")
    if raw_payload is None:
        raise MarketNormalizationError("listing.item.listed_note is required when raw_payload.note is missing.")

    payload = _coerce_mapping(raw_payload, "listing.item.raw_payload")
    payload_note = payload.get("note")
    if isinstance(payload_note, str) and payload_note.strip():
        return payload_note.strip()

    raise MarketNormalizationError("Listing is missing a supported price note.")


def parse_price_note(note: str) -> tuple[float, float, str]:
    """Parse a PoE stash note like '~price 150 chaos' or '~b/o 2/10 divine'."""

    match = PRICE_NOTE_PATTERN.match(note)
    if match is None:
        raise MarketNormalizationError(f"Unsupported listing note format: {note!r}")

    quote_amount = _coerce_positive_number(float(match.group("amount")), "price note amount")
    quoted_item_count = _coerce_positive_number(float(match.group("count") or 1), "price note item count")
    quote_currency = _canonical_currency(match.group("currency"))
    return quote_amount, quoted_item_count, quote_currency


def extract_listing_price(listing: Mapping[str, Any], descriptor: ItemDescriptor | None = None) -> ParsedListingPrice:
    """Parse the listing note and derive per-unit pricing for the listing."""

    resolved_descriptor = descriptor or describe_listing_item(listing)
    note = extract_listing_note(listing)
    quote_amount, quoted_item_count, quote_currency = parse_price_note(note)

    if quoted_item_count == 1 and resolved_descriptor.item_kind == "commodity" and resolved_descriptor.stack_size > 1:
        quoted_item_count = float(resolved_descriptor.stack_size)

    return ParsedListingPrice(
        note=note,
        quote_currency=quote_currency,
        quote_amount=quote_amount,
        quoted_item_count=quoted_item_count,
        total_currency_amount=quote_amount,
        unit_currency_amount=quote_amount / quoted_item_count,
    )


def build_window_currency_context(listings: Iterable[Mapping[str, Any]]) -> WindowCurrencyContext:
    """Derive the chaos-per-divine rate for one window from bridge listings."""

    candidate_rates: list[float] = []
    evidence_listing_ids: set[str] = set()
    evidence_item_keys: set[str] = set()

    for listing in listings:
        descriptor = describe_listing_item(listing)
        parsed_price = extract_listing_price(listing, descriptor)

        if descriptor.item_key == "commodity:divine-orb" and parsed_price.quote_currency == "chaos":
            candidate_rates.append(parsed_price.unit_currency_amount)
        elif descriptor.item_key == "commodity:chaos-orb" and parsed_price.quote_currency == "divine":
            candidate_rates.append(1 / parsed_price.unit_currency_amount)
        else:
            continue

        evidence_listing_ids.add(_coerce_non_empty_string(listing.get("listing_id"), "listing.listing_id"))
        evidence_item_keys.add(descriptor.item_key)

    if not candidate_rates:
        raise MarketNormalizationError("Window is missing chaos/divine bridge listings for normalization.")

    chaos_per_divine = statistics.median(candidate_rates)
    return WindowCurrencyContext(
        chaos_per_divine=chaos_per_divine,
        divine_per_chaos=1 / chaos_per_divine,
        evidence_listing_ids=tuple(sorted(evidence_listing_ids)),
        evidence_item_keys=tuple(sorted(evidence_item_keys)),
    )


def normalize_listing_price(
    listing: Mapping[str, Any],
    currency_context: WindowCurrencyContext,
    descriptor: ItemDescriptor | None = None,
) -> NormalizedListingPrice:
    """Normalize one listing into both chaos and divine equivalents."""

    if currency_context.chaos_per_divine <= 0:
        raise MarketNormalizationError("currency_context.chaos_per_divine must be > 0.")

    resolved_descriptor = descriptor or describe_listing_item(listing)
    parsed_price = extract_listing_price(listing, resolved_descriptor)
    listing_id = _coerce_non_empty_string(listing.get("listing_id"), "listing.listing_id")

    if parsed_price.quote_currency == "chaos":
        total_chaos_value = parsed_price.total_currency_amount
        unit_chaos_value = parsed_price.unit_currency_amount
        total_divine_value = total_chaos_value / currency_context.chaos_per_divine
        unit_divine_value = unit_chaos_value / currency_context.chaos_per_divine
    elif parsed_price.quote_currency == "divine":
        total_divine_value = parsed_price.total_currency_amount
        unit_divine_value = parsed_price.unit_currency_amount
        total_chaos_value = total_divine_value * currency_context.chaos_per_divine
        unit_chaos_value = unit_divine_value * currency_context.chaos_per_divine
    else:
        raise MarketNormalizationError(f"Unsupported normalized currency '{parsed_price.quote_currency}'.")

    return NormalizedListingPrice(
        listing_id=listing_id,
        item_key=resolved_descriptor.item_key,
        item_name=resolved_descriptor.item_name,
        item_kind=resolved_descriptor.item_kind,
        stack_size=resolved_descriptor.stack_size,
        listed_note=parsed_price.note,
        quote_currency=parsed_price.quote_currency,
        quote_amount=parsed_price.quote_amount,
        quoted_item_count=parsed_price.quoted_item_count,
        total_chaos_value=total_chaos_value,
        total_divine_value=total_divine_value,
        unit_chaos_value=unit_chaos_value,
        unit_divine_value=unit_divine_value,
    )


def _normalize_partition_token(value: str, field_name: str) -> str:
    token = _coerce_non_empty_string(value, field_name)
    windows_token = PureWindowsPath(token)
    posix_token = PurePosixPath(token)

    if windows_token.anchor or posix_token.is_absolute():
        raise MarketNormalizationError(f"{field_name} must not be an absolute or rooted path.")
    if "/" in token or "\\" in token:
        raise MarketNormalizationError(f"{field_name} must not contain path separators.")
    if token in {".", ".."}:
        raise MarketNormalizationError(f"{field_name} must not use relative path segments.")

    return token


def _ensure_path_within_root(path: Path, root: Path, field_name: str) -> Path:
    resolved_root = root.resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    if not resolved_path.is_relative_to(resolved_root):
        raise MarketNormalizationError(f"{field_name} must stay within {resolved_root}.")
    return path


def normalized_partition_root(config: MarketSourceConfig, realm: Realm | str | None, league: str) -> Path:
    """Return the safe normalized-output partition for one realm and league."""

    partition_realm = realm.value if isinstance(realm, Realm) else str(realm or config.selection.default_realm.value)
    league_token = _normalize_partition_token(league, "league")
    partition_root = config.storage.normalized_root / partition_realm / league_token
    return _ensure_path_within_root(partition_root, config.storage.normalized_root, "league")


def normalized_listing_path(
    config: MarketSourceConfig,
    realm: Realm | str | None,
    league: str,
    listing_id: str,
) -> Path:
    """Return the safe normalized listing artifact path."""

    filename = _coerce_non_empty_string(listing_id, "listing_id")
    if not SAFE_FILENAME_PATTERN.fullmatch(filename):
        raise MarketNormalizationError("listing_id must be filename-safe for normalized artifacts.")
    return normalized_partition_root(config, realm, league) / f"{filename}.json"
