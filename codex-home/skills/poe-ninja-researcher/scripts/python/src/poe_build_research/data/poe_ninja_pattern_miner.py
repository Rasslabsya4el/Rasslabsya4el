"""Bounded public-build pattern mining over accepted poe.ninja retrieval surfaces."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from .poe_ninja import (
    POE_NINJA_BUILD_LISTING_RECORD_KIND,
    POE_NINJA_BUILD_PAGE_RECORD_KIND,
    POE_NINJA_BUILD_PAGE_PARTITIONED_RECORD_KIND,
    POE_NINJA_CHARACTER_PROFILE_RECORD_KIND,
    POE_NINJA_SOURCE_ID,
    POE_NINJA_UPSTREAM_SYSTEM,
    PoENinjaClient,
)

POE_NINJA_PATTERN_MINER_SCHEMA_VERSION = "1.0.0"
POE_NINJA_PATTERN_MINER_RECORD_KIND = "poe_ninja_public_build_pattern_research"
POE_NINJA_PATTERN_MINER_GENERATOR = "poe_build_research.data.poe_ninja_pattern_miner"
NINJA_RESEARCHER_ROLE = "ninja_researcher"
WEAPON_SLOT_IDS = {"Weapon", "Weapon2"}
QUIVER_SLOT_IDS = {"Offhand", "Offhand2"}
GENERIC_LOADOUT_SLOT_IDS = {
    "Amulet",
    "Belt",
    "BodyArmour",
    "Boots",
    "Gloves",
    "Helmet",
    "Ring",
    "Ring2",
    "Weapon",
    "Weapon2",
    "Offhand",
    "Offhand2",
}
MECHANIC_FACET_PATTERNS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("damage_engine", "damage engine", ("damage", "critical", "crit", "impale", "overwhelm")),
    ("ailment_engine", "ailment engine", ("ignite", "shock", "chill", "freeze", "poison", "bleed", "bleeding", "brittle", "scorch", "sap")),
    ("charge_engine", "charge engine", ("charge", "frenzy", "power charge", "endurance charge", "inspiration")),
    ("resource_stacking", "resource stacking", ("mana", "life", "energy shield", "attribute", "strength", "dexterity", "intelligence", "rage", "accuracy")),
    ("projectile_behavior", "projectile behavior", ("projectile", "arrow", "bow", "quiver", "chain", "fork", "pierce", "return", "sniper's mark")),
    ("trigger_proc_behavior", "trigger/proc behavior", ("trigger", "triggered", "cast when", "when you", "on hit", "on kill")),
    ("conversion", "conversion", ("converted", "conversion", "convert", "gain as extra", "as extra")),
    ("reservation_aura", "reservation/aura", ("reservation", "aura", "herald", "banner", "grace", "determination", "hatred", "purity")),
    ("minion_totem", "minion/totem", ("minion", "zombie", "spectre", "golem", "totem", "ballista")),
    ("defensive_engine", "defensive engine", ("armour", "evasion", "block", "suppression", "ward", "maximum resistance", "resistances")),
)
MECHANIC_FACET_CATEGORIES = {category for category, _, _ in MECHANIC_FACET_PATTERNS}


class PoENinjaPatternMinerContractError(RuntimeError):
    """Raised when pattern-miner inputs violate the accepted bounded contract."""


@dataclass(frozen=True, slots=True)
class PackageComponent:
    component_kind: str
    label: str
    normalized_key: str
    slot: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_kind": self.component_kind,
            "label": self.label,
            "normalized_key": self.normalized_key,
            "slot": self.slot,
        }


@dataclass(frozen=True, slots=True)
class MechanicTag:
    tag_id: str
    label: str
    category: str
    source_component_refs: tuple[dict[str, Any], ...]
    source_refs: tuple[str, ...]
    source_profile_key: tuple[str, str]
    extractor_name: str
    can_participate_in_interaction_evidence: bool
    confidence: float | None = None
    strength: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag_id": self.tag_id,
            "label": self.label,
            "category": self.category,
            "source_component_refs": list(self.source_component_refs),
            "source_refs": list(self.source_refs),
            "source_profile_key": list(self.source_profile_key),
            "extractor_name": self.extractor_name,
            "confidence": self.confidence,
            "strength": self.strength,
            "can_participate_in_interaction_evidence": self.can_participate_in_interaction_evidence,
        }


@dataclass(frozen=True, slots=True)
class PackageObservation:
    family: str
    label: str
    components: tuple[PackageComponent, ...]
    taxonomy_kind: str
    default_adjacent_search_seed: bool
    interaction_evidence: tuple[str, ...]
    mechanic_tag_ids: tuple[str, ...]
    interaction_mechanic_tag_ids: tuple[str, ...]
    applicability_notes: tuple[str, ...]
    profile_key: tuple[str, str]
    artifact_surface: str = "package_candidate"
    rejection_reason: str | None = None

    @property
    def group_key(self) -> tuple[str, tuple[str, ...]]:
        return (self.family, tuple(component.normalized_key for component in self.components))


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PoENinjaPatternMinerContractError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PoENinjaPatternMinerContractError(f"{field_name} must be an object.")
    return value


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoENinjaPatternMinerContractError(f"{field_name} must be an array.")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PoENinjaPatternMinerContractError("Expected a string when a value is provided.")
    normalized = value.strip()
    return normalized or None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _component_key(component_kind: str, label: str, *, slot: str | None = None) -> str:
    parts = [component_kind]
    if slot is not None:
        parts.append(slot.lower())
    parts.append(_slug(label))
    return ":".join(parts)


def _stable_digest(parts: Sequence[str]) -> str:
    payload = "|".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _item_label(item: Mapping[str, Any]) -> str:
    rarity = _require_non_empty_string(item.get("rarity"), "item.rarity")
    name = _optional_string(item.get("name"))
    type_line = _optional_string(item.get("type_line"))
    base_type = _optional_string(item.get("base_type"))
    if rarity == "unique" and name is not None:
        return name
    if type_line is not None:
        return type_line
    if base_type is not None:
        return base_type
    if name is not None:
        return name
    raise PoENinjaPatternMinerContractError("Item must define a usable name, type_line, or base_type.")


def _item_text_values(item: Mapping[str, Any]) -> list[str]:
    values = [_item_label(item)]
    for field_name in ("explicit_mods", "crafted_mods", "enchant_mods"):
        raw_values = item.get(field_name, [])
        if raw_values is None:
            continue
        for index, value in enumerate(_require_list(raw_values, f"item.{field_name}")):
            values.append(_require_non_empty_string(value, f"item.{field_name}[{index}]"))
    return values


def _component_ref(component: PackageComponent) -> dict[str, Any]:
    return {
        "component_kind": component.component_kind,
        "normalized_key": component.normalized_key,
        "label": component.label,
        "slot": component.slot,
    }


def _mechanic_facets_from_text(text: str) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    normalized_text = text.lower()
    matched: list[tuple[str, str, tuple[str, ...]]] = []
    for category, label, terms in MECHANIC_FACET_PATTERNS:
        matched_terms = tuple(term for term in terms if term in normalized_text)
        if matched_terms:
            matched.append((category, label, matched_terms))
    return tuple(matched)


def _mechanic_facet_tag(
    *,
    profile_key: str,
    profile_key_tuple: tuple[str, str],
    component: PackageComponent,
    category: str,
    label: str,
    matched_terms: Sequence[str],
    source_ref: str,
    source_text: str,
    extractor_name: str,
) -> MechanicTag:
    matched_term_label = ", ".join(sorted(set(matched_terms)))
    return MechanicTag(
        tag_id=f"tag.ninja.{_stable_digest([profile_key, component.normalized_key, category, source_ref, source_text])}",
        label=f"{label}: {matched_term_label}",
        category=category,
        source_component_refs=(_component_ref(component),),
        source_refs=(source_ref,),
        source_profile_key=profile_key_tuple,
        extractor_name=extractor_name,
        confidence=0.75,
        strength="source_text_mechanic_facet",
        can_participate_in_interaction_evidence=True,
    )


def _profile_mechanic_tag_manifest(profile: Mapping[str, Any]) -> tuple[MechanicTag, ...]:
    tags: list[MechanicTag] = []
    profile_key_tuple = _profile_key(profile)
    profile_key = "/".join(profile_key_tuple)
    for item_index, raw_item in enumerate(_require_list(profile.get("equipment"), "character_profile.equipment")):
        item = _require_mapping(raw_item, f"character_profile.equipment[{item_index}]")
        slot = _require_non_empty_string(item.get("inventory_id"), f"character_profile.equipment[{item_index}].inventory_id")
        if slot not in GENERIC_LOADOUT_SLOT_IDS:
            continue
        label = _item_label(item)
        component = PackageComponent("equipment", label, _component_key("equipment", label, slot=slot.lower()), slot=slot.lower())
        tags.append(
            MechanicTag(
                tag_id=f"tag.ninja.{_stable_digest([profile_key, slot, label, 'generic-loadout-slot'])}",
                label=f"{slot} loadout component",
                category="generic_loadout_cooccurrence",
                source_component_refs=(_component_ref(component),),
                source_refs=(f"character_profile.equipment[{item_index}]",),
                source_profile_key=profile_key_tuple,
                extractor_name="generic_loadout_component_tagger",
                confidence=1.0,
                strength="observed_component",
                can_participate_in_interaction_evidence=False,
            )
        )
        for mod_index, raw_mod in enumerate(_require_list(item.get("explicit_mods", []), f"character_profile.equipment[{item_index}].explicit_mods")):
            mod = _require_non_empty_string(raw_mod, f"character_profile.equipment[{item_index}].explicit_mods[{mod_index}]")
            normalized_mod = mod.lower()
            for category, facet_label, matched_terms in _mechanic_facets_from_text(mod):
                tags.append(
                    _mechanic_facet_tag(
                        profile_key=profile_key,
                        profile_key_tuple=profile_key_tuple,
                        component=component,
                        category=category,
                        label=facet_label,
                        matched_terms=matched_terms,
                        source_ref=f"character_profile.equipment[{item_index}].explicit_mods[{mod_index}]",
                        source_text=mod,
                        extractor_name="item_mod_mechanic_facet_tagger",
                    )
                )
            if "quiver" not in normalized_mod:
                continue
            tags.append(
                MechanicTag(
                    tag_id=f"tag.ninja.{_stable_digest([profile_key, slot, label, mod, 'explicit-quiver-interaction'])}",
                    label="explicit quiver scaling text",
                    category="explicit_mechanic_interaction",
                    source_component_refs=(_component_ref(component),),
                    source_refs=(f"character_profile.equipment[{item_index}].explicit_mods[{mod_index}]",),
                    source_profile_key=profile_key_tuple,
                    extractor_name="item_mod_interaction_tagger",
                    confidence=0.9,
                    strength="explicit_mod_text",
                    can_participate_in_interaction_evidence=True,
                )
            )
        item_text = " ".join(_item_text_values(item))
        for category, facet_label, matched_terms in _mechanic_facets_from_text(item_text):
            tags.append(
                _mechanic_facet_tag(
                    profile_key=profile_key,
                    profile_key_tuple=profile_key_tuple,
                    component=component,
                    category=category,
                    label=facet_label,
                    matched_terms=matched_terms,
                    source_ref=f"character_profile.equipment[{item_index}]",
                    source_text=item_text,
                    extractor_name="item_text_mechanic_facet_tagger",
                )
            )
    for skill_index, skill_name in enumerate(_main_skill_names(profile)):
        component = PackageComponent("skill", skill_name, _component_key("skill", skill_name))
        tags.append(
            MechanicTag(
                tag_id=f"tag.ninja.{_stable_digest([profile_key, skill_name, 'primary-skill'])}",
                label=f"primary skill: {skill_name}",
                category="archetype_shell",
                source_component_refs=(_component_ref(component),),
                source_refs=(f"character_profile.skill_groups[].primary_skill_names[{skill_index}]",),
                source_profile_key=profile_key_tuple,
                extractor_name="skill_shell_tagger",
                confidence=1.0,
                strength="observed_primary_skill",
                can_participate_in_interaction_evidence=False,
            )
        )
        for category, facet_label, matched_terms in _mechanic_facets_from_text(skill_name):
            tags.append(
                _mechanic_facet_tag(
                    profile_key=profile_key,
                    profile_key_tuple=profile_key_tuple,
                    component=component,
                    category=category,
                    label=facet_label,
                    matched_terms=matched_terms,
                    source_ref=f"character_profile.skill_groups[].primary_skill_names[{skill_index}]",
                    source_text=skill_name,
                    extractor_name="skill_name_mechanic_facet_tagger",
                )
            )
    for keystone_index, keystone_name in enumerate(_keystone_names(profile)):
        component = PackageComponent("keystone", keystone_name, _component_key("keystone", keystone_name))
        for category, facet_label, matched_terms in _mechanic_facets_from_text(keystone_name):
            tags.append(
                _mechanic_facet_tag(
                    profile_key=profile_key,
                    profile_key_tuple=profile_key_tuple,
                    component=component,
                    category=category,
                    label=facet_label,
                    matched_terms=matched_terms,
                    source_ref=f"character_profile.passives.keystone_names[{keystone_index}]",
                    source_text=keystone_name,
                    extractor_name="keystone_name_mechanic_facet_tagger",
                )
            )
    return tuple(tags)


def _interaction_tags_for_components(tags: Sequence[MechanicTag], components: Sequence[PackageComponent]) -> tuple[MechanicTag, ...]:
    component_keys = {component.normalized_key for component in components}
    return tuple(
        tag
        for tag in tags
        if tag.can_participate_in_interaction_evidence
        and any(ref.get("normalized_key") in component_keys for ref in tag.source_component_refs)
    )


def _mechanic_tag_ids_for_components(tags: Sequence[MechanicTag], components: Sequence[PackageComponent]) -> tuple[str, ...]:
    component_keys = {component.normalized_key for component in components}
    return tuple(
        tag.tag_id
        for tag in tags
        if any(ref.get("normalized_key") in component_keys for ref in tag.source_component_refs)
    )


def _linked_interaction_tags_for_components(tags: Sequence[MechanicTag], components: Sequence[PackageComponent]) -> tuple[MechanicTag, ...]:
    component_keys = {component.normalized_key for component in components}
    matched_tags = tuple(
        tag
        for tag in tags
        if tag.can_participate_in_interaction_evidence
        and tag.source_refs
        and any(ref.get("normalized_key") in component_keys for ref in tag.source_component_refs)
    )
    explicit_tags = tuple(tag for tag in matched_tags if tag.category == "explicit_mechanic_interaction")
    facet_tags_by_category: dict[str, list[MechanicTag]] = {}
    for tag in matched_tags:
        if tag.category not in MECHANIC_FACET_CATEGORIES:
            continue
        facet_tags_by_category.setdefault(tag.category, []).append(tag)
    linked_facet_tags = tuple(
        tag
        for category in sorted(facet_tags_by_category)
        for tag in facet_tags_by_category[category]
        if len({ref.get("normalized_key") for facet_tag in facet_tags_by_category[category] for ref in facet_tag.source_component_refs}) >= 2
    )
    deduped_tags: list[MechanicTag] = []
    seen_tag_ids: set[str] = set()
    for tag in (*explicit_tags, *linked_facet_tags):
        if tag.tag_id in seen_tag_ids:
            continue
        seen_tag_ids.add(tag.tag_id)
        deduped_tags.append(tag)
    return tuple(deduped_tags)


def _component_from_ref(ref: Mapping[str, Any]) -> PackageComponent | None:
    component_kind = _optional_string(ref.get("component_kind"))
    label = _optional_string(ref.get("label"))
    normalized_key = _optional_string(ref.get("normalized_key"))
    if component_kind is None or label is None or normalized_key is None:
        return None
    return PackageComponent(
        component_kind,
        label,
        normalized_key,
        slot=_optional_string(ref.get("slot")),
    )


def _build_mechanic_linked_package_observations(
    profile: Mapping[str, Any],
    tags: Sequence[MechanicTag],
) -> tuple[PackageObservation, ...]:
    tags_by_category: dict[str, list[MechanicTag]] = {}
    for tag in tags:
        if tag.category not in MECHANIC_FACET_CATEGORIES:
            continue
        if not tag.can_participate_in_interaction_evidence or not tag.source_refs:
            continue
        tags_by_category.setdefault(tag.category, []).append(tag)

    observations: list[PackageObservation] = []
    for category in sorted(tags_by_category):
        category_tags = tags_by_category[category]
        components_by_key: dict[str, PackageComponent] = {}
        for tag in category_tags:
            for raw_ref in tag.source_component_refs:
                component = _component_from_ref(raw_ref)
                if component is not None:
                    components_by_key.setdefault(component.normalized_key, component)
        components = tuple(sorted(components_by_key.values(), key=lambda component: (component.component_kind, component.slot or "", component.label)))
        component_kinds = {component.component_kind for component in components}
        if len(components) < 2 or len(component_kinds) < 2:
            continue

        interaction_tags = tuple(
            tag
            for tag in category_tags
            if any(ref.get("normalized_key") in components_by_key for ref in tag.source_component_refs)
        )
        if len({ref.get("normalized_key") for tag in interaction_tags for ref in tag.source_component_refs}) < 2:
            continue

        category_label = next(label for matched_category, label, _ in MECHANIC_FACET_PATTERNS if matched_category == category)
        component_labels = " + ".join(component.label for component in components[:4])
        notes = (
            f"Observed source-backed {category_label} mechanic facets across multiple component kinds on public profiles.",
            "This is a taxonomy-gated research lead only; public-build support is not final winner evidence without later PoB compare proof.",
        )
        observations.append(
            PackageObservation(
                family=f"mechanic_linked_package:{category}",
                label=f"{category_label}: {component_labels}",
                components=components,
                taxonomy_kind="mechanic_linked_package",
                default_adjacent_search_seed=True,
                interaction_evidence=(
                    f"Shared source-backed mechanic facet category `{category}` links "
                    f"{len(components)} components across {len(component_kinds)} component kinds.",
                ),
                mechanic_tag_ids=_mechanic_tag_ids_for_components(tags, components),
                interaction_mechanic_tag_ids=tuple(tag.tag_id for tag in interaction_tags),
                applicability_notes=notes,
                profile_key=_profile_key(profile),
            )
        )
    return tuple(observations)


def _weapon_quiver_interaction_evidence(
    weapon: Mapping[str, Any],
    quiver: Mapping[str, Any],
    interaction_tags: Sequence[MechanicTag],
) -> tuple[str, ...]:
    weapon_label = _item_label(weapon)
    quiver_label = _item_label(quiver)
    combined_text = " ".join([*_item_text_values(weapon), *_item_text_values(quiver)]).lower()
    if interaction_tags and weapon_label == "Widowhail" and "quiver" in combined_text:
        return (
            f"{weapon_label} explicitly scales bonuses from the equipped quiver; {quiver_label} is not treated as mere slot compatibility.",
        )
    interaction_terms = (
        "quiver stat",
        "quiver bonus",
        "projectile damage per",
        "damage conversion",
        "gain a charge",
        "trigger",
        "attribute stacking",
    )
    matching_terms = [term for term in interaction_terms if term in combined_text]
    if interaction_tags and matching_terms:
        return (
            "Observed weapon/quiver package carries explicit mechanic text: "
            + ", ".join(matching_terms)
            + ".",
        )
    linked_categories = sorted({tag.category for tag in interaction_tags if tag.category in MECHANIC_FACET_CATEGORIES})
    if linked_categories:
        return (
            "Observed linked mechanic facet evidence with explicit source refs: "
            + ", ".join(linked_categories)
            + ".",
        )
    return ()


def _profile_key(profile: Mapping[str, Any]) -> tuple[str, str]:
    identity = _require_mapping(profile.get("identity"), "character_profile.identity")
    return (
        _require_non_empty_string(identity.get("account"), "character_profile.identity.account"),
        _require_non_empty_string(identity.get("name"), "character_profile.identity.name"),
    )


def _main_skill_names(profile: Mapping[str, Any]) -> list[str]:
    skill_groups = _require_list(profile.get("skill_groups"), "character_profile.skill_groups")
    names: list[str] = []
    for group_index, raw_group in enumerate(skill_groups):
        group = _require_mapping(raw_group, f"character_profile.skill_groups[{group_index}]")
        for skill_index, value in enumerate(
            _require_list(group.get("primary_skill_names"), f"character_profile.skill_groups[{group_index}].primary_skill_names")
        ):
            skill_name = _require_non_empty_string(value, f"character_profile.skill_groups[{group_index}].primary_skill_names[{skill_index}]")
            if skill_name not in names:
                names.append(skill_name)
    return names


def _keystone_names(profile: Mapping[str, Any]) -> list[str]:
    passives = _require_mapping(profile.get("passives"), "character_profile.passives")
    return [
        _require_non_empty_string(value, f"character_profile.passives.keystone_names[{index}]")
        for index, value in enumerate(_require_list(passives.get("keystone_names"), "character_profile.passives.keystone_names"))
    ]


def _equipment_by_slot(profile: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    equipment: dict[str, Mapping[str, Any]] = {}
    for index, raw_item in enumerate(_require_list(profile.get("equipment"), "character_profile.equipment")):
        item = _require_mapping(raw_item, f"character_profile.equipment[{index}]")
        inventory_id = _require_non_empty_string(item.get("inventory_id"), f"character_profile.equipment[{index}].inventory_id")
        equipment[inventory_id] = item
    return equipment


def _flask_labels(profile: Mapping[str, Any]) -> list[str]:
    labels: list[str] = []
    for index, raw_item in enumerate(_require_list(profile.get("flasks"), "character_profile.flasks")):
        label = _item_label(_require_mapping(raw_item, f"character_profile.flasks[{index}]"))
        if label not in labels:
            labels.append(label)
    return sorted(labels)


def _profile_row_lookup(build_page_payload: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    lookup: dict[tuple[str, str], Mapping[str, Any]] = {}
    for index, raw_row in enumerate(_require_list(build_page_payload.get("results"), "poe_ninja_build_page.results")):
        row = _require_mapping(raw_row, f"poe_ninja_build_page.results[{index}]")
        summary = _require_mapping(row.get("summary"), f"poe_ninja_build_page.results[{index}].summary")
        key = (
            _require_non_empty_string(summary.get("account"), f"poe_ninja_build_page.results[{index}].summary.account"),
            _require_non_empty_string(summary.get("name"), f"poe_ninja_build_page.results[{index}].summary.name"),
        )
        lookup[key] = row
    return lookup


def _row_main_skill_label(row: Mapping[str, Any], profile: Mapping[str, Any]) -> str:
    summary = _require_mapping(row.get("summary"), "poe_ninja_build_page.results[].summary")
    summary_skill = _optional_string(summary.get("main_skill"))
    if summary_skill is not None:
        return summary_skill
    profile_skills = _main_skill_names(profile)
    if profile_skills:
        return profile_skills[0]
    return "unknown"


def _profile_page_url(profile: Mapping[str, Any]) -> str:
    page = _require_mapping(profile.get("page"), "character_profile.page")
    return _require_non_empty_string(page.get("requested_url"), "character_profile.page.requested_url")


def _profile_api_url(profile: Mapping[str, Any]) -> str:
    page = _require_mapping(profile.get("page"), "character_profile.page")
    return _require_non_empty_string(page.get("api_url"), "character_profile.page.api_url")


def _resource_urls(payload: Mapping[str, Any]) -> list[str]:
    freshness = _require_mapping(payload.get("freshness"), "payload.freshness")
    return [
        _require_non_empty_string(
            _require_mapping(resource, f"payload.freshness.resources[{index}]").get("url"),
            f"payload.freshness.resources[{index}].url",
        )
        for index, resource in enumerate(_require_list(freshness.get("resources"), "payload.freshness.resources"))
    ]


def _trace_attachment_id(kind: str, *parts: str) -> str:
    slug = ".".join(_slug(part) for part in parts if part)
    return f"evidence.ninja.{kind}.{slug}"


def _build_trace_attachment(
    payload: Mapping[str, Any],
    *,
    attachment_id: str,
    title: str,
    summary: str,
    locator: str,
    captured_at: str,
    linked_record_ids: Sequence[str],
) -> dict[str, Any]:
    freshness = _require_mapping(payload.get("freshness"), "payload.freshness")
    provenance = _require_mapping(payload.get("provenance"), "payload.provenance")
    resource_urls = _resource_urls(payload)
    input_urls = [
        _require_non_empty_string(
            _require_mapping(item, f"payload.provenance.inputs[{index}]").get("url"),
            f"payload.provenance.inputs[{index}].url",
        )
        for index, item in enumerate(_require_list(provenance.get("inputs"), "payload.provenance.inputs"))
    ]
    freshness_note_parts = [
        f"retrieved_at={_require_non_empty_string(freshness.get('retrieved_at'), 'payload.freshness.retrieved_at')}",
        f"resources={len(resource_urls)}",
    ]
    observed_timestamps = _require_list(freshness.get("observed_data_timestamps"), "payload.freshness.observed_data_timestamps")
    if observed_timestamps:
        freshness_note_parts.append(
            "observed_data_timestamps=" + ",".join(_require_non_empty_string(value, "payload.freshness.observed_data_timestamps[]") for value in observed_timestamps)
        )
    return {
        "attachment_id": attachment_id,
        "attachment_kind": "ninja_snapshot",
        "title": title,
        "summary": summary,
        "locator": locator,
        "provenance_note": f"{len(input_urls)} upstream inputs preserved: " + "; ".join(input_urls),
        "captured_at": captured_at,
        "freshness_note": "; ".join(freshness_note_parts),
        "linked_record_ids": list(linked_record_ids),
        "source_role": NINJA_RESEARCHER_ROLE,
    }


def _validate_payload_record_kind(payload: Mapping[str, Any], expected_record_kind: str | set[str], field_name: str) -> None:
    observed = _require_non_empty_string(payload.get("record_kind"), f"{field_name}.record_kind")
    expected_record_kinds = {expected_record_kind} if isinstance(expected_record_kind, str) else expected_record_kind
    if observed not in expected_record_kinds:
        raise PoENinjaPatternMinerContractError(
            f"{field_name}.record_kind must be one of {sorted(expected_record_kinds)!r}, got {observed!r}."
        )
    source = _require_mapping(payload.get("source"), f"{field_name}.source")
    source_id = _require_non_empty_string(source.get("source_id"), f"{field_name}.source.source_id")
    upstream_system = _require_non_empty_string(source.get("upstream_system"), f"{field_name}.source.upstream_system")
    if source_id != POE_NINJA_SOURCE_ID or upstream_system != POE_NINJA_UPSTREAM_SYSTEM:
        raise PoENinjaPatternMinerContractError(f"{field_name}.source must stay on accepted poe.ninja surfaces.")
    _require_mapping(payload.get("freshness"), f"{field_name}.freshness")
    _require_mapping(payload.get("provenance"), f"{field_name}.provenance")


def _find_league_entry(listing_payload: Mapping[str, Any], league_url: str) -> Mapping[str, Any]:
    for index, raw_league in enumerate(_require_list(listing_payload.get("leagues"), "poe_ninja_build_listing.leagues")):
        league = _require_mapping(raw_league, f"poe_ninja_build_listing.leagues[{index}]")
        if _require_non_empty_string(league.get("league_url"), f"poe_ninja_build_listing.leagues[{index}].league_url") == league_url:
            return league
    raise PoENinjaPatternMinerContractError(f"build_listing does not contain league_url {league_url!r}.")


def _build_skill_shell_observation(profile: Mapping[str, Any], tags: Sequence[MechanicTag]) -> PackageObservation | None:
    identity = _require_mapping(profile.get("identity"), "character_profile.identity")
    ascendancy = _optional_string(identity.get("ascendancy_class_name")) or _optional_string(identity.get("base_class"))
    skill_names = _main_skill_names(profile)
    keystones = sorted(set(_keystone_names(profile)))
    if ascendancy is None or not skill_names or not keystones:
        return None
    primary_skill = skill_names[0]
    components = (
        PackageComponent("ascendancy", ascendancy, _component_key("ascendancy", ascendancy)),
        PackageComponent("skill", primary_skill, _component_key("skill", primary_skill)),
        *(
            PackageComponent("keystone", keystone, _component_key("keystone", keystone))
            for keystone in keystones
        ),
    )
    notes = (
        f"Observed on public {ascendancy} {primary_skill} profiles with explicit keystone support.",
        "Classify this as an archetype shell, not a combo or synergy claim; later PoB compare must confirm actual upside.",
    )
    return PackageObservation(
        family="skill_shell",
        label=f"{ascendancy} {primary_skill} shell",
        components=components,
        taxonomy_kind="archetype_shell",
        default_adjacent_search_seed=True,
        interaction_evidence=(
            "Shell evidence is structural only: repeated ascendancy, primary skill, and keystone alignment.",
        ),
        mechanic_tag_ids=_mechanic_tag_ids_for_components(tags, components),
        interaction_mechanic_tag_ids=(),
        applicability_notes=notes,
        profile_key=_profile_key(profile),
    )


def _build_weapon_quiver_observation(profile: Mapping[str, Any], tags: Sequence[MechanicTag]) -> PackageObservation | None:
    equipment = _equipment_by_slot(profile)
    weapon = next((equipment[slot] for slot in WEAPON_SLOT_IDS if slot in equipment), None)
    quiver = next(
        (
            equipment[slot]
            for slot in QUIVER_SLOT_IDS
            if slot in equipment
            and (
                "quiver" in (_optional_string(equipment[slot].get("type_line")) or "").lower()
                or "quiver" in (_optional_string(equipment[slot].get("base_type")) or "").lower()
            )
        ),
        None,
    )
    skill_names = _main_skill_names(profile)
    if weapon is None or quiver is None or not skill_names:
        return None
    primary_skill = skill_names[0]
    weapon_label = _item_label(weapon)
    quiver_label = _item_label(quiver)
    components = (
        PackageComponent("equipment", weapon_label, _component_key("equipment", weapon_label, slot="weapon"), slot="weapon"),
        PackageComponent("equipment", quiver_label, _component_key("equipment", quiver_label, slot="quiver"), slot="quiver"),
        PackageComponent("skill", primary_skill, _component_key("skill", primary_skill)),
    )
    interaction_tags = _linked_interaction_tags_for_components(tags, components)
    interaction_evidence = _weapon_quiver_interaction_evidence(weapon, quiver, interaction_tags)
    has_interaction_evidence = bool(interaction_tags) and bool(interaction_evidence)
    notes = (
        f"Observed as a repeated {primary_skill} weapon/quiver loadout package on public build profiles.",
        "Mandatory bow/quiver slot compatibility is not combo evidence; keep this as a seed only when explicit mechanic evidence is present.",
    )
    return PackageObservation(
        family="weapon_quiver_pair",
        label=f"{weapon_label} + {quiver_label}",
        components=components,
        taxonomy_kind="loadout_package" if has_interaction_evidence else "rejected_low_information",
        default_adjacent_search_seed=has_interaction_evidence,
        interaction_evidence=interaction_evidence,
        mechanic_tag_ids=_mechanic_tag_ids_for_components(tags, components),
        interaction_mechanic_tag_ids=tuple(tag.tag_id for tag in interaction_tags),
        applicability_notes=notes,
        profile_key=_profile_key(profile),
        artifact_surface="package_candidate" if has_interaction_evidence else "rejected_pattern",
        rejection_reason=None if has_interaction_evidence else "no_shared_mechanic_tags",
    )


def _build_flask_engine_observation(profile: Mapping[str, Any]) -> PackageObservation | None:
    flasks = _flask_labels(profile)
    skill_names = _main_skill_names(profile)
    if len(flasks) < 3 or not skill_names:
        return None
    primary_skill = skill_names[0]
    notes = (
        f"Observed as a repeated multi-flask co-occurrence around {primary_skill}.",
        "Generic flask bundles are utility baselines, not combo evidence; require explicit charge sustain, flask effect, or unique interaction evidence before seeding search.",
    )
    components = [PackageComponent("skill", primary_skill, _component_key("skill", primary_skill))]
    components.extend(
        PackageComponent("flask", label, _component_key("flask", label), slot="flask")
        for label in flasks
    )
    return PackageObservation(
        family="flask_engine",
        label=" / ".join(flasks),
        components=tuple(components),
        taxonomy_kind="utility_baseline",
        default_adjacent_search_seed=False,
        interaction_evidence=(),
        mechanic_tag_ids=(),
        interaction_mechanic_tag_ids=(),
        applicability_notes=notes,
        profile_key=_profile_key(profile),
        artifact_surface="rejected_pattern",
        rejection_reason="utility_baseline_noise",
    )


def _build_generic_loadout_noise_observation(profile: Mapping[str, Any], tags: Sequence[MechanicTag]) -> PackageObservation | None:
    equipment = _equipment_by_slot(profile)
    generic_items = [item for slot, item in sorted(equipment.items()) if slot in GENERIC_LOADOUT_SLOT_IDS]
    skill_names = _main_skill_names(profile)
    if len(generic_items) < 2 or not skill_names:
        return None
    primary_skill = skill_names[0]
    item_labels = tuple(_item_label(item) for item in generic_items)
    components = tuple(
        PackageComponent(
            "equipment",
            label,
            _component_key("equipment", label, slot=_require_non_empty_string(item.get("inventory_id"), "item.inventory_id").lower()),
            slot=_require_non_empty_string(item.get("inventory_id"), "item.inventory_id").lower(),
        )
        for item, label in zip(generic_items, item_labels, strict=True)
    ) + (PackageComponent("skill", primary_skill, _component_key("skill", primary_skill)),)
    observed_tag_ids = _mechanic_tag_ids_for_components(tags, components)
    notes = (
        f"Observed repeated generic loadout co-occurrence around {primary_skill}.",
        "Generic equipment slot coexistence is not interaction evidence; only explicit mechanic tags can promote a package to a seedable combo/loadout interaction.",
    )
    return PackageObservation(
        family="generic_loadout_cooccurrence",
        label=" + ".join(item_labels[:4]),
        components=components,
        taxonomy_kind="generic_cooccurrence",
        default_adjacent_search_seed=False,
        interaction_evidence=(),
        mechanic_tag_ids=observed_tag_ids,
        interaction_mechanic_tag_ids=(),
        applicability_notes=notes,
        profile_key=_profile_key(profile),
        artifact_surface="rejected_pattern",
        rejection_reason="no_shared_mechanic_tags",
    )


def _profile_observations(profile: Mapping[str, Any], tags: Sequence[MechanicTag]) -> list[PackageObservation]:
    observations = [
        observation
        for observation in (
            _build_skill_shell_observation(profile, tags),
            _build_weapon_quiver_observation(profile, tags),
            _build_flask_engine_observation(profile),
            _build_generic_loadout_noise_observation(profile, tags),
        )
        if observation is not None
    ]
    observations.extend(_build_mechanic_linked_package_observations(profile, tags))
    return observations


def _dedupe_inputs(payloads: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for payload in payloads:
        record_kind = _require_non_empty_string(payload.get("record_kind"), "payload.record_kind")
        provenance = _require_mapping(payload.get("provenance"), "payload.provenance")
        for index, raw_input in enumerate(_require_list(provenance.get("inputs"), "payload.provenance.inputs")):
            item = _require_mapping(raw_input, f"payload.provenance.inputs[{index}]")
            url = _require_non_empty_string(item.get("url"), f"payload.provenance.inputs[{index}].url")
            body_sha256 = _require_non_empty_string(
                item.get("body_sha256"),
                f"payload.provenance.inputs[{index}].body_sha256",
            )
            key = (url, body_sha256)
            deduped.setdefault(
                key,
                {
                    "record_kind": record_kind,
                    "url": url,
                    "method": _require_non_empty_string(item.get("method"), f"payload.provenance.inputs[{index}].method"),
                    "status": item.get("status"),
                    "content_type": _optional_string(item.get("content_type")),
                    "body_sha256": body_sha256,
                    "fetched_at": _require_non_empty_string(
                        item.get("fetched_at"),
                        f"payload.provenance.inputs[{index}].fetched_at",
                    ),
                },
            )
    return sorted(deduped.values(), key=lambda value: (value["record_kind"], value["url"]))


def _aggregate_freshness(payloads: Sequence[Mapping[str, Any]], *, captured_at: str) -> dict[str, Any]:
    retrieved_at: list[str] = []
    observed_timestamps: list[str] = []
    resource_urls: list[str] = []
    for payload in payloads:
        freshness = _require_mapping(payload.get("freshness"), "payload.freshness")
        retrieved_value = _require_non_empty_string(freshness.get("retrieved_at"), "payload.freshness.retrieved_at")
        if retrieved_value not in retrieved_at:
            retrieved_at.append(retrieved_value)
        for index, raw_value in enumerate(_require_list(freshness.get("observed_data_timestamps"), "payload.freshness.observed_data_timestamps")):
            timestamp = _require_non_empty_string(raw_value, f"payload.freshness.observed_data_timestamps[{index}]")
            if timestamp not in observed_timestamps:
                observed_timestamps.append(timestamp)
        for url in _resource_urls(payload):
            if url not in resource_urls:
                resource_urls.append(url)
    return {
        "captured_at": captured_at,
        "supporting_retrieved_at": retrieved_at,
        "observed_data_timestamps": observed_timestamps,
        "resource_urls": resource_urls,
    }


class PoENinjaPatternMiner:
    """Mine repeated public-build packages into explicit research leads."""

    def __init__(self, client: PoENinjaClient | None = None) -> None:
        self.client = client or PoENinjaClient()

    def mine_from_client(
        self,
        league_url: str,
        *,
        snapshot_type: str = "exp",
        filters: Mapping[str, str | Sequence[str]] | None = None,
        time_machine: str | None = None,
        result_limit: int = 10,
        profile_limit: int | None = None,
        minimum_support: int = 2,
        captured_at: str | None = None,
    ) -> dict[str, Any]:
        listing_payload = self.client.fetch_build_listing()
        build_page_payload = self.client.fetch_build_page(
            league_url,
            snapshot_type=snapshot_type,
            filters=filters,
            time_machine=time_machine,
            result_limit=result_limit,
        )
        rows = _require_list(build_page_payload.get("results"), "poe_ninja_build_page.results")
        profile_rows = rows[: profile_limit or len(rows)]
        character_profiles = [
            self.client.fetch_character_profile(
                league_url,
                account=_require_non_empty_string(
                    _require_mapping(row.get("summary"), f"poe_ninja_build_page.results[{index}].summary").get("account"),
                    f"poe_ninja_build_page.results[{index}].summary.account",
                ),
                name=_require_non_empty_string(
                    _require_mapping(row.get("summary"), f"poe_ninja_build_page.results[{index}].summary").get("name"),
                    f"poe_ninja_build_page.results[{index}].summary.name",
                ),
                snapshot_type=snapshot_type,
                time_machine=time_machine,
            )
            for index, row in enumerate(profile_rows)
        ]
        return self.mine_from_payloads(
            listing_payload,
            build_page_payload,
            character_profiles,
            minimum_support=minimum_support,
            captured_at=captured_at,
        )

    def mine_from_payloads(
        self,
        listing_payload: Mapping[str, Any],
        build_page_payload: Mapping[str, Any],
        character_profiles: Sequence[Mapping[str, Any]],
        *,
        minimum_support: int = 2,
        captured_at: str | None = None,
    ) -> dict[str, Any]:
        if minimum_support < 2:
            raise PoENinjaPatternMinerContractError("minimum_support must be at least 2 to stay above raw popularity tables.")
        if not character_profiles:
            raise PoENinjaPatternMinerContractError("character_profiles must contain at least one profile.")

        _validate_payload_record_kind(listing_payload, POE_NINJA_BUILD_LISTING_RECORD_KIND, "poe_ninja_build_listing")
        _validate_payload_record_kind(
            build_page_payload,
            {POE_NINJA_BUILD_PAGE_RECORD_KIND, POE_NINJA_BUILD_PAGE_PARTITIONED_RECORD_KIND},
            "poe_ninja_build_page",
        )
        for index, profile in enumerate(character_profiles):
            _validate_payload_record_kind(profile, POE_NINJA_CHARACTER_PROFILE_RECORD_KIND, f"character_profiles[{index}]")

        query = _require_mapping(build_page_payload.get("query"), "poe_ninja_build_page.query")
        league_url = _require_non_empty_string(query.get("league_url"), "poe_ninja_build_page.query.league_url")
        league_entry = _find_league_entry(listing_payload, league_url)
        row_lookup = _profile_row_lookup(build_page_payload)

        profile_map: dict[tuple[str, str], Mapping[str, Any]] = {}
        for index, profile in enumerate(character_profiles):
            key = _profile_key(profile)
            if key not in row_lookup:
                raise PoENinjaPatternMinerContractError(
                    f"character_profiles[{index}] ({key[0]}/{key[1]}) is not present in the bounded build_page row set."
                )
            profile_map[key] = profile
            _profile_api_url(profile)

        captured_at_value = captured_at or _utc_now_iso()
        grouped: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
        mechanic_tags_by_profile: dict[tuple[str, str], tuple[MechanicTag, ...]] = {}
        for key, profile in profile_map.items():
            row = row_lookup[key]
            tags = _profile_mechanic_tag_manifest(profile)
            mechanic_tags_by_profile[key] = tags
            for observation in _profile_observations(profile, tags):
                bucket = grouped.setdefault(
                    observation.group_key,
                    {
                        "observation": observation,
                        "profiles": [],
                        "rows": [],
                    },
                )
                bucket["profiles"].append(profile)
                bucket["rows"].append(row)

        candidate_ids_by_group: dict[tuple[str, tuple[str, ...]], str] = {}
        accepted_groups: list[dict[str, Any]] = []
        for group_key, bucket in grouped.items():
            support_count = len(bucket["profiles"])
            if support_count < minimum_support:
                continue
            observation = bucket["observation"]
            record_prefix = "candidate" if observation.artifact_surface == "package_candidate" else "rejected"
            candidate_id = (
                f"{record_prefix}.ninja.{_slug(observation.family)}."
                f"{_stable_digest([observation.family, *(component.normalized_key for component in observation.components)])}"
            )
            candidate_ids_by_group[group_key] = candidate_id
            accepted_groups.append(bucket)

        listing_attachment_id = _trace_attachment_id("listing", league_url)
        page_attachment_id = _trace_attachment_id("page", league_url, _optional_string(query.get("requested_time_machine")) or "current")
        profile_attachment_ids = {
            key: _trace_attachment_id("profile", key[0], key[1])
            for key in sorted(profile_map)
        }

        attachment_links: dict[str, list[str]] = {
            listing_attachment_id: [],
            page_attachment_id: [],
            **{attachment_id: [] for attachment_id in profile_attachment_ids.values()},
        }
        package_candidates: list[dict[str, Any]] = []
        rejected_patterns: list[dict[str, Any]] = []
        mechanic_tag_manifest = [
            tag.to_dict()
            for key in sorted(mechanic_tags_by_profile)
            for tag in mechanic_tags_by_profile[key]
        ]
        for bucket in sorted(
            accepted_groups,
            key=lambda value: (
                -len(value["profiles"]),
                value["observation"].family,
                value["observation"].label,
            ),
        ):
            observation: PackageObservation = bucket["observation"]
            supporting_keys = sorted(_profile_key(profile) for profile in bucket["profiles"])
            candidate_id = candidate_ids_by_group[observation.group_key]
            supporting_ids = [listing_attachment_id, page_attachment_id, *(profile_attachment_ids[key] for key in supporting_keys)]
            for attachment_id in supporting_ids:
                attachment_links[attachment_id].append(candidate_id)

            supporting_payloads = [listing_payload, build_page_payload, *(profile_map[key] for key in supporting_keys)]
            rows = [(key, row_lookup[key]) for key in supporting_keys]
            observed_support = {
                "matching_profile_count": len(supporting_keys),
                "profile_sample_size": len(profile_map),
                "page_row_count": len(rows),
                "matching_characters": [
                    {
                        "account": _require_non_empty_string(
                            _require_mapping(row.get("summary"), "poe_ninja_build_page.results[].summary").get("account"),
                            "poe_ninja_build_page.results[].summary.account",
                        ),
                        "name": _require_non_empty_string(
                            _require_mapping(row.get("summary"), "poe_ninja_build_page.results[].summary").get("name"),
                            "poe_ninja_build_page.results[].summary.name",
                        ),
                        "rank": row.get("rank"),
                        "class_name": _require_non_empty_string(
                            _require_mapping(row.get("summary"), "poe_ninja_build_page.results[].summary").get("class_name"),
                            "poe_ninja_build_page.results[].summary.class_name",
                        ),
                        "main_skill": _row_main_skill_label(row, profile_map[key]),
                        "page_url": _require_non_empty_string(
                            _require_mapping(row.get("character"), "poe_ninja_build_page.results[].character").get("page_url"),
                            "poe_ninja_build_page.results[].character.page_url",
                        ),
                    }
                    for key, row in rows
                ],
            }
            source_refs = [
                {
                    "attachment_id": listing_attachment_id,
                    "record_kind": POE_NINJA_BUILD_LISTING_RECORD_KIND,
                    "url": _require_non_empty_string(league_entry.get("search_page_url"), "poe_ninja_build_listing.leagues[].search_page_url"),
                },
                {
                    "attachment_id": page_attachment_id,
                    "record_kind": POE_NINJA_BUILD_PAGE_RECORD_KIND,
                    "url": _require_non_empty_string(
                        _require_mapping(build_page_payload.get("page"), "poe_ninja_build_page.page").get("requested_url"),
                        "poe_ninja_build_page.page.requested_url",
                    ),
                },
                *(
                    {
                        "attachment_id": profile_attachment_ids[key],
                        "record_kind": POE_NINJA_CHARACTER_PROFILE_RECORD_KIND,
                        "url": _profile_api_url(profile_map[key]),
                    }
                    for key in supporting_keys
                ),
            ]
            record = {
                "candidate_id": candidate_id,
                "candidate_label": observation.label,
                "candidate_kind": "research_lead" if observation.artifact_surface == "package_candidate" else "rejected_pattern",
                "status": "active" if observation.artifact_surface == "package_candidate" else "rejected",
                    "summary": (
                        f"Repeated {observation.family} package observed in "
                        f"{len(supporting_keys)}/{len(profile_map)} bounded public profiles."
                    ),
                    "why_it_exists": (
                        "Bounded public-build co-occurrence kept as taxonomy-gated research evidence instead of hidden memory."
                    ),
                    "supporting_evidence_ids": supporting_ids,
                    "related_variant_ids": [],
                    "budget_entry_ids": [],
                    "decision_note": (
                        "Soft public-build acceleration hint only. Do not treat prevalence as correctness or a final recommendation before PoB compare proof."
                    ),
                    "last_touched_by_role": NINJA_RESEARCHER_ROLE,
                    "last_touched_at": captured_at_value,
                    "family": observation.family,
                    "taxonomy_kind": observation.taxonomy_kind,
                    "default_adjacent_search_seed": observation.default_adjacent_search_seed,
                    "interaction_evidence": list(observation.interaction_evidence),
                    "mechanic_tag_ids": list(observation.mechanic_tag_ids),
                    "interaction_mechanic_tag_ids": list(observation.interaction_mechanic_tag_ids),
                    "rejection_reason": observation.rejection_reason,
                    "taxonomy_gate": {
                        "requires_explicit_interaction_evidence_for_combo": True,
                        "must_not_use_prevalence_as_final_winner_evidence": True,
                        "low_information_kinds_blocked_from_default_adjacent_search": [
                            "utility_baseline",
                            "generic_cooccurrence",
                            "rejected_low_information",
                        ],
                    },
                    "components": [component.to_dict() for component in observation.components],
                    "observed_support": observed_support,
                    "league_scope": {
                        "league_name": _require_non_empty_string(league_entry.get("league_name"), "poe_ninja_build_listing.leagues[].league_name"),
                        "league_url": league_url,
                        "snapshot_type": _require_non_empty_string(query.get("snapshot_type"), "poe_ninja_build_page.query.snapshot_type"),
                        "requested_time_machine": _optional_string(query.get("requested_time_machine")),
                        "filters": list(_require_list(query.get("filters"), "poe_ninja_build_page.query.filters")),
                    },
                    "applicability_notes": list(observation.applicability_notes),
                    "source_refs": source_refs,
                    "freshness": _aggregate_freshness(supporting_payloads, captured_at=captured_at_value),
                    "provenance": {
                        "generator": POE_NINJA_PATTERN_MINER_GENERATOR,
                        "source_id": POE_NINJA_SOURCE_ID,
                        "upstream_system": POE_NINJA_UPSTREAM_SYSTEM,
                        "derived_from_record_kinds": [
                            POE_NINJA_BUILD_LISTING_RECORD_KIND,
                            POE_NINJA_BUILD_PAGE_RECORD_KIND,
                            POE_NINJA_CHARACTER_PROFILE_RECORD_KIND,
                        ],
                        "inputs": _dedupe_inputs(supporting_payloads),
                        "notes": [
                            "Derived only from accepted bounded poe.ninja listing, build-page, and character-profile surfaces.",
                            "Public-build prevalence stays taxonomy-gated and cannot become final winner evidence without authoritative PoB compare.",
                        ],
                    },
            }
            if observation.artifact_surface == "package_candidate":
                package_candidates.append(record)
            else:
                rejected_patterns.append(record)

        trace_attachments = [
            _build_trace_attachment(
                listing_payload,
                attachment_id=listing_attachment_id,
                title=f"poe.ninja build listing trace for {league_url}",
                summary="Bounded league-listing trace preserved for freshness, routing, and search-page scope.",
                locator=_require_non_empty_string(league_entry.get("search_page_url"), "poe_ninja_build_listing.leagues[].search_page_url"),
                captured_at=captured_at_value,
                linked_record_ids=attachment_links[listing_attachment_id],
            ),
            _build_trace_attachment(
                build_page_payload,
                attachment_id=page_attachment_id,
                title=f"poe.ninja bounded build page trace for {league_url}",
                summary="Bounded search-page trace preserved for result rows, filters, and page/protobuf provenance.",
                locator=_require_non_empty_string(
                    _require_mapping(build_page_payload.get("page"), "poe_ninja_build_page.page").get("requested_url"),
                    "poe_ninja_build_page.page.requested_url",
                ),
                captured_at=captured_at_value,
                linked_record_ids=attachment_links[page_attachment_id],
            ),
            *(
                _build_trace_attachment(
                    profile_map[key],
                    attachment_id=profile_attachment_ids[key],
                    title=f"poe.ninja character profile trace for {key[1]}",
                    summary="Bounded public character-profile trace preserved for item, flask, jewel, and passive co-occurrence mining.",
                    locator=_profile_api_url(profile_map[key]),
                    captured_at=captured_at_value,
                    linked_record_ids=attachment_links[profile_attachment_ids[key]],
                )
                for key in sorted(profile_map)
            ),
        ]

        return {
            "schema_version": POE_NINJA_PATTERN_MINER_SCHEMA_VERSION,
            "record_kind": POE_NINJA_PATTERN_MINER_RECORD_KIND,
            "source": {
                "source_id": POE_NINJA_SOURCE_ID,
                "upstream_system": POE_NINJA_UPSTREAM_SYSTEM,
                "generator": POE_NINJA_PATTERN_MINER_GENERATOR,
                "source_role": NINJA_RESEARCHER_ROLE,
            },
            "query_scope": {
                "league_url": league_url,
                "snapshot_type": _require_non_empty_string(query.get("snapshot_type"), "poe_ninja_build_page.query.snapshot_type"),
                "requested_time_machine": _optional_string(query.get("requested_time_machine")),
                "filters": list(_require_list(query.get("filters"), "poe_ninja_build_page.query.filters")),
                "profile_sample_size": len(profile_map),
                "minimum_support": minimum_support,
            },
            "trace_attachments": trace_attachments,
            "mechanic_tag_manifest": mechanic_tag_manifest,
            "package_candidates": package_candidates,
            "rejected_patterns": rejected_patterns,
            "notes": [
                "Package candidates are explicit soft public-build priors only and do not replace authoritative PoB compare proof.",
                "The miner emits only compound co-occurrence packages; it does not publish raw popularity sections or standalone recommendations.",
            ],
        }


__all__ = [
    "POE_NINJA_PATTERN_MINER_GENERATOR",
    "POE_NINJA_PATTERN_MINER_RECORD_KIND",
    "POE_NINJA_PATTERN_MINER_SCHEMA_VERSION",
    "PoENinjaPatternMiner",
    "PoENinjaPatternMinerContractError",
]
