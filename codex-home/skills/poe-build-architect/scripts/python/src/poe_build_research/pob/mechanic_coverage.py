"""Repo-owned PoB-side mechanic coverage surface derived from accepted corpora."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .game_corpus import DEFAULT_MANIFEST_PATH as DEFAULT_GAME_MANIFEST_PATH
from .game_corpus import load_game_corpus_manifest
from .mod_corpus import DEFAULT_MANIFEST_PATH as DEFAULT_MOD_MANIFEST_PATH
from .mod_corpus import FAMILY_FILE_NAMES as MOD_FAMILY_FILE_NAMES
from .mod_corpus import load_mod_corpus_bundle, load_mod_corpus_manifest
from .tag_corpus import DEFAULT_MANIFEST_PATH as DEFAULT_TAG_MANIFEST_PATH
from .tag_corpus import FAMILY_FILE_NAMES as TAG_FAMILY_FILE_NAMES
from .tag_corpus import load_tag_corpus_bundle, load_tag_corpus_manifest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = Path(__file__).with_name("mechanic_coverage_data")
DEFAULT_MANIFEST_PATH = DEFAULT_OUTPUT_ROOT / "manifest.json"

SCHEMA_VERSION = "1.0.0"
CORPUS_ID = "pob_mechanic_coverage"
SOURCE_GAME_CORPUS_ID = "pob_game_corpus"
SOURCE_TAG_CORPUS_ID = "pob_tag_corpus"
SOURCE_MOD_CORPUS_ID = "pob_mod_corpus"

FAMILY_FILE_NAMES = {
    "coverage_map": "coverage_map.json",
    "missing_list": "missing_list.json",
}

EXPECTED_TAG_FAMILIES = tuple(TAG_FAMILY_FILE_NAMES)
EXPECTED_MOD_FAMILIES = tuple(MOD_FAMILY_FILE_NAMES)
CANDIDATE_FACETS = (
    "mechanic",
    "damage_type",
    "resource",
    "defence",
    "ailment",
    "weapon",
    "charge",
    "attribute",
)
DELIVERY_REQUIRED_DOMAINS = ("mechanic", "damage_type", "ailment")
DELIVERY_TAG_FAMILIES = ("active_gems", "support_gems", "items")
SCALING_TAG_FAMILIES = ("support_gems", "items", "passives", "masteries", "ascendancies", "keystones")
ENABLEMENT_TAG_FAMILIES = ("config_surfaces", "items", "ascendancies", "keystones")
STRUCTURAL_ENABLEMENT_FACETS = (
    "config_section",
    "config_control_type",
    "config_scope",
    "config_predicate",
    "item_slot",
    "item_class",
    "item_kind",
    "influence",
    "class",
    "node_kind",
)
LAYER_ORDER = ("delivery", "scaling", "enablement")
STATUS_ORDER = ("covered", "partial", "gap")
PARTIAL_LAYER_STATUSES = ("tag_only", "mod_only")
EVIDENCE_SAMPLE_LIMIT = 2
FIELD_ORDER = {
    "manifest": [
        "schema_version",
        "corpus_id",
        "source_game_corpus",
        "source_tag_corpus",
        "source_mod_corpus",
        "families",
        "downstream_policy",
        "field_order",
    ],
    "bundle": [
        "schema_version",
        "corpus_id",
        "family",
        "record_count",
        "provenance",
        "metadata",
        "records",
    ],
    "coverage_record": [
        "group_id",
        "group_key",
        "domains",
        "matched_terms",
        "coverage_status",
        "delivery_required",
        "layer_coverage",
        "missing_layers",
        "partial_layers",
        "status_reason",
    ],
    "missing_record": [
        "group_id",
        "group_key",
        "domains",
        "coverage_status",
        "missing_layers",
        "partial_layers",
        "present_layers",
        "status_reason",
        "next_step_sources",
        "evidence_samples",
    ],
    "layer": [
        "layer",
        "required",
        "status",
        "tag_record_count",
        "tag_source_families",
        "mod_record_count",
        "mod_source_families",
        "evidence_samples",
    ],
    "evidence": [
        "corpus_id",
        "family",
        "record_id",
        "display_name",
        "matched_terms",
        "source_families",
        "supporting_text",
    ],
}


class MechanicCoverageContractError(RuntimeError):
    """Raised when the committed mechanic coverage contract cannot be satisfied."""


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload), encoding="utf-8", newline="\n")
    return path


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sorted_strings(values: Iterable[str]) -> list[str]:
    return sorted({str(value) for value in values if str(value)})


def _facet_map(record: dict[str, Any]) -> dict[str, set[str]]:
    return {
        facet["facet"]: {str(value) for value in facet["values"]}
        for facet in record.get("scaling_facets", [])
        if isinstance(facet, dict)
    }


def _require_file(path: Path, *, label: str) -> None:
    if not path.is_file():
        raise MechanicCoverageContractError(f"{label} is missing: {_relative_path(path)}")


def _validate_source_lane(source_lane: dict[str, Any], *, label: str) -> None:
    required_keys = {
        "lane_id",
        "canonical_path",
        "lock_path",
        "repo",
        "repo_url",
        "pinned_ref",
        "pinned_commit",
        "observed_commit",
        "tree_version",
    }
    missing = sorted(required_keys - set(source_lane))
    if missing:
        raise MechanicCoverageContractError(f"{label} is missing source-lane keys: {', '.join(missing)}")
    if source_lane["observed_commit"] != source_lane["pinned_commit"]:
        raise MechanicCoverageContractError(f"{label} must reflect a pinned, matching PoB source lane.")


def _bundle_input(family: str, bundle_path: Path, record_count: int) -> dict[str, Any]:
    return {
        "family": family,
        "relative_path": _relative_path(bundle_path),
        "record_count": record_count,
        "sha256": _sha256_file(bundle_path),
    }


def _load_source_game_corpus(manifest_path: Path) -> dict[str, Any]:
    _require_file(manifest_path, label="Committed game corpus manifest")
    manifest = load_game_corpus_manifest(manifest_path)
    if manifest.get("corpus_id") != SOURCE_GAME_CORPUS_ID:
        raise MechanicCoverageContractError(
            f"Unsupported committed game corpus id: {manifest.get('corpus_id')!r}"
        )
    source_lane = manifest.get("source_lane")
    if not isinstance(source_lane, dict):
        raise MechanicCoverageContractError("Committed game corpus manifest is missing source_lane provenance.")
    _validate_source_lane(source_lane, label="Committed game corpus manifest")
    return {
        "corpus_id": manifest["corpus_id"],
        "manifest_path": _relative_path(manifest_path),
        "manifest_sha256": _sha256_file(manifest_path),
        "schema_version": manifest["schema_version"],
        "source_lane": source_lane,
    }


def _load_source_tag_corpus(manifest_path: Path, *, expected_game_manifest_sha256: str) -> tuple[dict[str, Any], dict[str, Any]]:
    _require_file(manifest_path, label="Committed tag corpus manifest")
    manifest = load_tag_corpus_manifest(manifest_path)
    if manifest.get("corpus_id") != SOURCE_TAG_CORPUS_ID:
        raise MechanicCoverageContractError(f"Unsupported committed tag corpus id: {manifest.get('corpus_id')!r}")
    source_corpus = manifest.get("source_corpus")
    if not isinstance(source_corpus, dict):
        raise MechanicCoverageContractError("Committed tag corpus manifest is missing source_corpus provenance.")
    if source_corpus.get("corpus_id") != SOURCE_GAME_CORPUS_ID:
        raise MechanicCoverageContractError(
            f"Committed tag corpus must derive from {SOURCE_GAME_CORPUS_ID}, got {source_corpus.get('corpus_id')!r}"
        )
    if source_corpus.get("manifest_sha256") != expected_game_manifest_sha256:
        raise MechanicCoverageContractError("Committed tag corpus provenance does not match the accepted game corpus.")
    source_lane = source_corpus.get("source_lane")
    if not isinstance(source_lane, dict):
        raise MechanicCoverageContractError("Committed tag corpus is missing inherited game-corpus source_lane provenance.")
    _validate_source_lane(source_lane, label="Committed tag corpus manifest")

    manifest_families = {entry["family"]: entry for entry in manifest.get("families", []) if isinstance(entry, dict)}
    if set(manifest_families) != set(EXPECTED_TAG_FAMILIES):
        raise MechanicCoverageContractError("Committed tag corpus family coverage drifted from the accepted contract.")

    bundle_inputs: list[dict[str, Any]] = []
    bundles: dict[str, Any] = {}
    for family in EXPECTED_TAG_FAMILIES:
        bundle_path = manifest_path.parent / TAG_FAMILY_FILE_NAMES[family]
        _require_file(bundle_path, label=f"Committed tag corpus bundle for family {family}")
        bundle = load_tag_corpus_bundle(family, manifest_path=manifest_path)
        if bundle.get("family") != family:
            raise MechanicCoverageContractError(
                f"Committed tag corpus bundle {bundle_path} reports family {bundle.get('family')!r}, expected {family!r}"
            )
        records = bundle.get("records")
        if not isinstance(records, list):
            raise MechanicCoverageContractError(f"Committed tag corpus bundle {bundle_path} is missing a records list.")
        if bundle.get("record_count") != len(records):
            raise MechanicCoverageContractError(f"Committed tag corpus bundle {bundle_path} has a record_count mismatch.")
        provenance = bundle.get("provenance")
        if not isinstance(provenance, dict):
            raise MechanicCoverageContractError(f"Committed tag corpus bundle {bundle_path} is missing provenance.")
        if provenance.get("derived_from_manifest_sha256") != expected_game_manifest_sha256:
            raise MechanicCoverageContractError(
                f"Committed tag corpus bundle {bundle_path} does not match the accepted game corpus provenance."
            )
        bundle_inputs.append(_bundle_input(family, bundle_path, len(records)))
        bundles[family] = bundle

    source_ref = {
        "corpus_id": manifest["corpus_id"],
        "manifest_path": _relative_path(manifest_path),
        "manifest_sha256": _sha256_file(manifest_path),
        "schema_version": manifest["schema_version"],
        "derived_from_game_manifest_sha256": expected_game_manifest_sha256,
        "bundle_inputs": bundle_inputs,
    }
    return source_ref, bundles


def _load_source_mod_corpus(manifest_path: Path, *, expected_game_manifest_sha256: str) -> tuple[dict[str, Any], dict[str, Any]]:
    _require_file(manifest_path, label="Committed mod corpus manifest")
    manifest = load_mod_corpus_manifest(manifest_path)
    if manifest.get("corpus_id") != SOURCE_MOD_CORPUS_ID:
        raise MechanicCoverageContractError(f"Unsupported committed mod corpus id: {manifest.get('corpus_id')!r}")
    source_game_corpus = manifest.get("source_game_corpus")
    if not isinstance(source_game_corpus, dict):
        raise MechanicCoverageContractError("Committed mod corpus manifest is missing source_game_corpus provenance.")
    if source_game_corpus.get("corpus_id") != SOURCE_GAME_CORPUS_ID:
        raise MechanicCoverageContractError(
            f"Committed mod corpus must derive from {SOURCE_GAME_CORPUS_ID}, got {source_game_corpus.get('corpus_id')!r}"
        )
    if source_game_corpus.get("manifest_sha256") != expected_game_manifest_sha256:
        raise MechanicCoverageContractError("Committed mod corpus provenance does not match the accepted game corpus.")
    source_lane = source_game_corpus.get("source_lane")
    if not isinstance(source_lane, dict):
        raise MechanicCoverageContractError("Committed mod corpus is missing inherited game-corpus source_lane provenance.")
    _validate_source_lane(source_lane, label="Committed mod corpus manifest")

    manifest_families = {entry["family"]: entry for entry in manifest.get("families", []) if isinstance(entry, dict)}
    if set(manifest_families) != set(EXPECTED_MOD_FAMILIES):
        raise MechanicCoverageContractError("Committed mod corpus family coverage drifted from the accepted contract.")

    bundle_inputs: list[dict[str, Any]] = []
    bundles: dict[str, Any] = {}
    for family in EXPECTED_MOD_FAMILIES:
        bundle_path = manifest_path.parent / MOD_FAMILY_FILE_NAMES[family]
        _require_file(bundle_path, label=f"Committed mod corpus bundle for family {family}")
        bundle = load_mod_corpus_bundle(family, manifest_path=manifest_path)
        if bundle.get("family") != family:
            raise MechanicCoverageContractError(
                f"Committed mod corpus bundle {bundle_path} reports family {bundle.get('family')!r}, expected {family!r}"
            )
        records = bundle.get("records")
        if not isinstance(records, list):
            raise MechanicCoverageContractError(f"Committed mod corpus bundle {bundle_path} is missing a records list.")
        if bundle.get("record_count") != len(records):
            raise MechanicCoverageContractError(f"Committed mod corpus bundle {bundle_path} has a record_count mismatch.")
        provenance = bundle.get("provenance")
        if not isinstance(provenance, dict):
            raise MechanicCoverageContractError(f"Committed mod corpus bundle {bundle_path} is missing provenance.")
        if provenance.get("manifest_sha256") != expected_game_manifest_sha256:
            raise MechanicCoverageContractError(
                f"Committed mod corpus bundle {bundle_path} does not match the accepted game corpus provenance."
            )
        bundle_inputs.append(_bundle_input(family, bundle_path, len(records)))
        bundles[family] = bundle

    source_ref = {
        "corpus_id": manifest["corpus_id"],
        "manifest_path": _relative_path(manifest_path),
        "manifest_sha256": _sha256_file(manifest_path),
        "schema_version": manifest["schema_version"],
        "derived_from_game_manifest_sha256": expected_game_manifest_sha256,
        "bundle_inputs": bundle_inputs,
    }
    return source_ref, bundles


def _prepare_tag_sources(tag_bundles: dict[str, Any]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for family in EXPECTED_TAG_FAMILIES:
        bundle = tag_bundles[family]
        for record in bundle["records"]:
            facet_map = _facet_map(record)
            prepared.append(
                {
                    "family": family,
                    "record": record,
                    "facet_map": facet_map,
                    "facet_values": {value for values in facet_map.values() for value in values},
                    "search_tags": set(record.get("search_tags", [])),
                    "structural_facets": sorted(set(facet_map) & set(STRUCTURAL_ENABLEMENT_FACETS)),
                }
            )
    return prepared


def _prepare_mod_sources(mod_bundles: dict[str, Any]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for family in EXPECTED_MOD_FAMILIES:
        bundle = mod_bundles[family]
        for record in bundle["records"]:
            normalized_blob = " ".join(
                record.get("normalized_surface_texts", []) or [record.get("normalized_text", "")]
            ).lower()
            normalized_blob = f"{normalized_blob} {' '.join(record.get('query_tokens', []))}".strip()
            prepared.append(
                {
                    "family": family,
                    "record": record,
                    "query_tokens": set(record.get("query_tokens", [])),
                    "normalized_blob": normalized_blob,
                    "source_families": list(record.get("source_families", [])),
                }
            )
    return prepared


def _candidate_domains(tag_sources: list[dict[str, Any]]) -> dict[str, set[str]]:
    candidates: dict[str, set[str]] = {}
    for source in tag_sources:
        for domain in CANDIDATE_FACETS:
            for value in source["facet_map"].get(domain, set()):
                candidates.setdefault(value, set()).add(domain)
    return candidates


def _match_terms(group_key: str) -> list[str]:
    parts = [part for part in group_key.split("_") if part]
    terms = {group_key, " ".join(parts), "-".join(parts), "".join(parts)}
    terms.update(parts)
    return _sorted_strings(terms)


def _tag_source_matches_group(source: dict[str, Any], group_key: str) -> bool:
    return group_key in source["facet_values"] or group_key in source["search_tags"]


def _mod_source_match_terms(source: dict[str, Any], *, group_key: str, match_terms: list[str]) -> list[str]:
    matched: set[str] = set()
    if group_key in source["query_tokens"]:
        matched.add(group_key)
    for term in match_terms:
        if term in source["query_tokens"] or term in source["normalized_blob"]:
            matched.add(term)
    if matched:
        return sorted(matched)
    parts = [part for part in group_key.split("_") if part]
    if parts and all(part in source["normalized_blob"] or part in source["query_tokens"] for part in parts):
        return sorted(parts)
    return []


def _tag_evidence_sample(source: dict[str, Any], *, group_key: str) -> dict[str, Any]:
    matched_terms = [group_key]
    matched_terms.extend(facet for facet, values in source["facet_map"].items() if group_key in values)
    return {
        "corpus_id": SOURCE_TAG_CORPUS_ID,
        "family": source["family"],
        "record_id": source["record"]["source_id"],
        "display_name": source["record"]["source_name"],
        "matched_terms": _sorted_strings(matched_terms),
        "source_families": [source["family"]],
        "supporting_text": list(source["record"].get("supporting_text", [])[:2]),
    }


def _mod_evidence_sample(source: dict[str, Any], matched_terms: list[str]) -> dict[str, Any]:
    record = source["record"]
    display_name = record.get("normalized_text") or " / ".join(record.get("normalized_surface_texts", []))
    supporting_text = record.get("original_texts") or record.get("original_surface_examples") or []
    return {
        "corpus_id": SOURCE_MOD_CORPUS_ID,
        "family": source["family"],
        "record_id": record["family_id"],
        "display_name": display_name,
        "matched_terms": matched_terms,
        "source_families": list(record.get("source_families", [])),
        "supporting_text": list(supporting_text[:2]),
    }


def _sample_evidence(
    tag_sources: list[dict[str, Any]],
    mod_sources: list[tuple[dict[str, Any], list[str]]],
    *,
    group_key: str,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for source in tag_sources[:EVIDENCE_SAMPLE_LIMIT]:
        samples.append(_tag_evidence_sample(source, group_key=group_key))
    remaining = max(0, EVIDENCE_SAMPLE_LIMIT - len(samples))
    for source, matched_terms in mod_sources[:remaining]:
        samples.append(_mod_evidence_sample(source, matched_terms))
    return samples


def _delivery_required(domains: list[str], delivery_matches: list[dict[str, Any]]) -> bool:
    return bool(set(domains) & set(DELIVERY_REQUIRED_DOMAINS)) or ("weapon" in domains and bool(delivery_matches))


def _layer_status(*, layer: str, required: bool, tag_count: int, mod_count: int = 0) -> str:
    if layer == "scaling":
        if tag_count and mod_count:
            return "covered"
        if tag_count:
            return "tag_only"
        if mod_count:
            return "mod_only"
        return "missing"
    if tag_count:
        return "covered"
    if required:
        return "missing"
    return "not_required"


def _status_reason(layer_coverage: list[dict[str, Any]]) -> str:
    missing_layers = [layer["layer"] for layer in layer_coverage if layer["required"] and layer["status"] == "missing"]
    partial_layers = [layer["layer"] for layer in layer_coverage if layer["status"] in PARTIAL_LAYER_STATUSES]
    if missing_layers and partial_layers:
        return (
            f"Required layer(s) {', '.join(missing_layers)} are missing and layer(s) "
            f"{', '.join(partial_layers)} rely on single-surface evidence."
        )
    if missing_layers:
        return f"Required layer(s) {', '.join(missing_layers)} have no committed PoB-side evidence."
    if partial_layers:
        return f"Layer(s) {', '.join(partial_layers)} rely on single-surface evidence and need follow-up."
    return "Required delivery, scaling, and enablement layers are covered by committed PoB-side surfaces."


def _coverage_status(layer_coverage: list[dict[str, Any]]) -> str:
    if any(layer["required"] and layer["status"] == "missing" for layer in layer_coverage):
        return "gap"
    if any(layer["status"] in PARTIAL_LAYER_STATUSES for layer in layer_coverage):
        return "partial"
    return "covered"


def _layer_record(
    *,
    layer: str,
    required: bool,
    group_key: str,
    tag_matches: list[dict[str, Any]],
    mod_matches: list[tuple[dict[str, Any], list[str]]] | None = None,
) -> dict[str, Any]:
    mod_matches = mod_matches or []
    tag_source_families = _sorted_strings(source["family"] for source in tag_matches)
    mod_source_families = _sorted_strings(
        family_name
        for source, _matched_terms in mod_matches
        for family_name in source["source_families"]
    )
    return {
        "layer": layer,
        "required": required,
        "status": _layer_status(layer=layer, required=required, tag_count=len(tag_matches), mod_count=len(mod_matches)),
        "tag_record_count": len(tag_matches),
        "tag_source_families": tag_source_families,
        "mod_record_count": len(mod_matches),
        "mod_source_families": mod_source_families,
        "evidence_samples": _sample_evidence(tag_matches, mod_matches, group_key=group_key),
    }


def _build_coverage_records(tag_sources: list[dict[str, Any]], mod_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coverage_records: list[dict[str, Any]] = []
    for group_key, domains in sorted(_candidate_domains(tag_sources).items()):
        match_terms = _match_terms(group_key)
        ordered_domains = _sorted_strings(domains)
        delivery_matches = [
            source
            for source in tag_sources
            if source["family"] in DELIVERY_TAG_FAMILIES
            and _tag_source_matches_group(source, group_key)
            and (
                set(ordered_domains) & set(DELIVERY_REQUIRED_DOMAINS)
                or "weapon" in ordered_domains
            )
        ]
        scaling_tag_matches = [
            source
            for source in tag_sources
            if source["family"] in SCALING_TAG_FAMILIES and _tag_source_matches_group(source, group_key)
        ]
        enablement_matches = [
            source
            for source in tag_sources
            if source["family"] in ENABLEMENT_TAG_FAMILIES
            and _tag_source_matches_group(source, group_key)
            and (source["family"] == "config_surfaces" or source["structural_facets"])
        ]
        scaling_mod_matches = [
            (source, matched_terms)
            for source in mod_sources
            if (matched_terms := _mod_source_match_terms(source, group_key=group_key, match_terms=match_terms))
        ]
        delivery_required = _delivery_required(ordered_domains, delivery_matches)
        layer_coverage = [
            _layer_record(
                layer="delivery",
                required=delivery_required,
                group_key=group_key,
                tag_matches=delivery_matches,
            ),
            _layer_record(
                layer="scaling",
                required=True,
                group_key=group_key,
                tag_matches=scaling_tag_matches,
                mod_matches=scaling_mod_matches,
            ),
            _layer_record(
                layer="enablement",
                required=True,
                group_key=group_key,
                tag_matches=enablement_matches,
            ),
        ]
        coverage_records.append(
            {
                "group_id": f"mechanic_group:{group_key}",
                "group_key": group_key,
                "domains": ordered_domains,
                "matched_terms": match_terms,
                "coverage_status": _coverage_status(layer_coverage),
                "delivery_required": delivery_required,
                "layer_coverage": layer_coverage,
                "missing_layers": [
                    layer["layer"] for layer in layer_coverage if layer["required"] and layer["status"] == "missing"
                ],
                "partial_layers": [
                    layer["layer"] for layer in layer_coverage if layer["status"] in PARTIAL_LAYER_STATUSES
                ],
                "status_reason": _status_reason(layer_coverage),
            }
        )
    return coverage_records


def _status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in STATUS_ORDER}
    for record in records:
        counts[record["coverage_status"]] += 1
    return counts


def _coverage_bundle(
    coverage_records: list[dict[str, Any]],
    *,
    source_game_corpus: dict[str, Any],
    source_tag_corpus: dict[str, Any],
    source_mod_corpus: dict[str, Any],
) -> dict[str, Any]:
    status_counts = _status_counts(coverage_records)
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_id": CORPUS_ID,
        "family": "coverage_map",
        "record_count": len(coverage_records),
        "provenance": {
            "source_game_corpus": source_game_corpus,
            "source_tag_corpus": source_tag_corpus,
            "source_mod_corpus": source_mod_corpus,
        },
        "metadata": {
            "candidate_facets": list(CANDIDATE_FACETS),
            "layer_order": list(LAYER_ORDER),
            "status_order": list(STATUS_ORDER),
            "coverage_status_counts": status_counts,
            "coverage_rule": (
                "covered requires every required layer plus both tag and mod evidence for scaling; "
                "partial means no required layer is missing but at least one layer is tag-only or mod-only; "
                "gap means at least one required layer is missing."
            ),
            "follow_up_sources": ["wiki", "curated_notes"],
        },
        "records": coverage_records,
    }


def _missing_bundle(
    coverage_records: list[dict[str, Any]],
    *,
    source_game_corpus: dict[str, Any],
    source_tag_corpus: dict[str, Any],
    source_mod_corpus: dict[str, Any],
) -> dict[str, Any]:
    missing_records: list[dict[str, Any]] = []
    for record in coverage_records:
        if record["coverage_status"] == "covered":
            continue
        present_layers = [
            layer["layer"]
            for layer in record["layer_coverage"]
            if layer["status"] in ("covered",) + PARTIAL_LAYER_STATUSES
        ]
        evidence_samples: list[dict[str, Any]] = []
        for layer in record["layer_coverage"]:
            evidence_samples.extend(layer["evidence_samples"])
        missing_records.append(
            {
                "group_id": record["group_id"],
                "group_key": record["group_key"],
                "domains": list(record["domains"]),
                "coverage_status": record["coverage_status"],
                "missing_layers": list(record["missing_layers"]),
                "partial_layers": list(record["partial_layers"]),
                "present_layers": present_layers,
                "status_reason": record["status_reason"],
                "next_step_sources": ["wiki", "curated_notes"],
                "evidence_samples": evidence_samples[:EVIDENCE_SAMPLE_LIMIT + 1],
            }
        )

    missing_records.sort(key=lambda entry: (STATUS_ORDER.index(entry["coverage_status"]), entry["group_key"]))
    status_counts = _status_counts(missing_records)
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_id": CORPUS_ID,
        "family": "missing_list",
        "record_count": len(missing_records),
        "provenance": {
            "source_game_corpus": source_game_corpus,
            "source_tag_corpus": source_tag_corpus,
            "source_mod_corpus": source_mod_corpus,
        },
        "metadata": {
            "generated_from_family": "coverage_map",
            "status_order": list(STATUS_ORDER),
            "coverage_status_counts": status_counts,
            "follow_up_sources": ["wiki", "curated_notes"],
            "consumer_rule": (
                "External wiki and curated notes work must start from this committed missing list instead of "
                "inventing ad hoc gap areas."
            ),
        },
        "records": missing_records,
    }


def _manifest_family_summary(family: str, bundle: dict[str, Any], *, output_root: Path) -> dict[str, Any]:
    return {
        "family": family,
        "relative_path": _relative_path(output_root / FAMILY_FILE_NAMES[family]),
        "record_count": bundle["record_count"],
        "coverage_status_counts": dict(bundle["metadata"]["coverage_status_counts"]),
    }


def _build_manifest(
    bundles: dict[str, Any],
    *,
    output_root: Path,
    source_game_corpus: dict[str, Any],
    source_tag_corpus: dict[str, Any],
    source_mod_corpus: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_id": CORPUS_ID,
        "source_game_corpus": source_game_corpus,
        "source_tag_corpus": source_tag_corpus,
        "source_mod_corpus": source_mod_corpus,
        "families": [
            _manifest_family_summary("coverage_map", bundles["coverage_map"], output_root=output_root),
            _manifest_family_summary("missing_list", bundles["missing_list"], output_root=output_root),
        ],
        "downstream_policy": {
            "read_root": "src/poe_build_research/pob/mechanic_coverage_data",
            "derivation_source_roots": [
                "src/poe_build_research/pob/corpus_data",
                "src/poe_build_research/pob/tag_data",
                "src/poe_build_research/pob/mod_data",
            ],
            "consumer_rule": (
                "Downstream agents must read the committed mechanic coverage map and missing list instead of "
                "rebuilding PoB-side archetype coverage ad hoc."
            ),
            "loader_boundary": "poe_build_research.pob.mechanic_coverage",
            "authority_rule": (
                "Use accepted committed game, tag, and mod corpora for ordinary mechanic coverage reads; "
                "wiki and curated notes are follow-up sources only for missing_list entries."
            ),
            "missing_list_rule": (
                "Treat partial and gap records as the only normal input surface for external wiki and curated-notes follow-up."
            ),
        },
        "field_order": FIELD_ORDER,
    }


def build_mechanic_coverage(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    game_corpus_manifest_path: Path = DEFAULT_GAME_MANIFEST_PATH,
    tag_corpus_manifest_path: Path = DEFAULT_TAG_MANIFEST_PATH,
    mod_corpus_manifest_path: Path = DEFAULT_MOD_MANIFEST_PATH,
) -> Path:
    source_game_corpus = _load_source_game_corpus(game_corpus_manifest_path)
    source_tag_corpus, tag_bundles = _load_source_tag_corpus(
        tag_corpus_manifest_path,
        expected_game_manifest_sha256=source_game_corpus["manifest_sha256"],
    )
    source_mod_corpus, mod_bundles = _load_source_mod_corpus(
        mod_corpus_manifest_path,
        expected_game_manifest_sha256=source_game_corpus["manifest_sha256"],
    )

    tag_sources = _prepare_tag_sources(tag_bundles)
    mod_sources = _prepare_mod_sources(mod_bundles)
    coverage_records = _build_coverage_records(tag_sources, mod_sources)
    bundles = {
        "coverage_map": _coverage_bundle(
            coverage_records,
            source_game_corpus=source_game_corpus,
            source_tag_corpus=source_tag_corpus,
            source_mod_corpus=source_mod_corpus,
        ),
        "missing_list": _missing_bundle(
            coverage_records,
            source_game_corpus=source_game_corpus,
            source_tag_corpus=source_tag_corpus,
            source_mod_corpus=source_mod_corpus,
        ),
    }

    output_root.mkdir(parents=True, exist_ok=True)
    for family, bundle in bundles.items():
        _write_json(output_root / FAMILY_FILE_NAMES[family], bundle)
    manifest = _build_manifest(
        bundles,
        output_root=output_root,
        source_game_corpus=source_game_corpus,
        source_tag_corpus=source_tag_corpus,
        source_mod_corpus=source_mod_corpus,
    )
    return _write_json(output_root / "manifest.json", manifest)


def load_mechanic_coverage_manifest(manifest_path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    return _load_json(manifest_path)


def load_mechanic_coverage_bundle(family: str, manifest_path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    if family not in FAMILY_FILE_NAMES:
        raise MechanicCoverageContractError(f"Unknown mechanic coverage family: {family}")
    return _load_json(manifest_path.parent / FAMILY_FILE_NAMES[family])
