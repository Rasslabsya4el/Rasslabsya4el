"""Repo-owned live PoB workspace boundary built on accepted live-control results."""

from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import PROJECT_ROOT, sha256_file, validate_token, write_json, write_text
from .live_control import DEFAULT_LAUNCHER_RELATIVE_PATH, LIVE_CONTROL_SUPPORTED_PATH
from .release_manager import utc_now_iso

WORKSPACE_SUPPORTED_PATH = "accepted_live_control_variant_workspace_v1"
VARIANT_HANDOFF_KIND = "next_pob_run_variant_workspace_v1"
DEFAULT_WORKSPACES_ROOT = PROJECT_ROOT / "artifacts" / "pob_workspaces"


class WorkspaceContractError(RuntimeError):
    """Raised when the repo-owned PoB workspace boundary cannot satisfy its contract."""

    def __init__(self, failure_state: str, message: str) -> None:
        super().__init__(message)
        self.failure_state = failure_state


def _require_non_empty_string(value: str, field_name: str, failure_state: str = "invalid_request") -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceContractError(failure_state, f"{field_name} must be a non-empty string.")
    return value.strip()


def _path_string(path: Path) -> str:
    return path.resolve().as_posix()


def _require_file(path: Path, failure_state: str, message: str) -> Path:
    resolved_path = path.resolve()
    if not resolved_path.is_file():
        raise WorkspaceContractError(failure_state, message)
    return resolved_path


def _require_dir(path: Path, failure_state: str, message: str) -> Path:
    resolved_path = path.resolve()
    if not resolved_path.is_dir():
        raise WorkspaceContractError(failure_state, message)
    return resolved_path


def _read_json_object(path: Path, *, missing_state: str, invalid_state: str, label: str) -> dict[str, Any]:
    file_path = _require_file(path, missing_state, f"{label} is missing: {path}")
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkspaceContractError(invalid_state, f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkspaceContractError(invalid_state, f"{label} must decode to a JSON object.")
    return payload


def _expect_string(payload: dict[str, Any], field_name: str, failure_state: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceContractError(failure_state, f"{field_name} must be a non-empty string.")
    return value.strip()


def _expect_optional_string(payload: dict[str, Any], field_name: str, failure_state: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceContractError(failure_state, f"{field_name} must be null or a non-empty string.")
    return value.strip()


def _expect_dict(payload: dict[str, Any], field_name: str, failure_state: str) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise WorkspaceContractError(failure_state, f"{field_name} must be a JSON object.")
    return value


def _expect_list(payload: dict[str, Any], field_name: str, failure_state: str) -> list[Any]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise WorkspaceContractError(failure_state, f"{field_name} must be a JSON array.")
    return value


def _expect_absolute_path(payload: dict[str, Any], field_name: str, failure_state: str) -> Path:
    value = Path(_expect_string(payload, field_name, failure_state))
    if not value.is_absolute():
        raise WorkspaceContractError(failure_state, f"{field_name} must be an absolute path.")
    return value


def _resolve_run_relative_path(run_root: Path, relative_value: str, field_name: str) -> Path:
    relative_path = Path(_require_non_empty_string(relative_value, field_name, "live_control_result_invalid"))
    candidate = (run_root / relative_path).resolve()
    try:
        candidate.relative_to(run_root.resolve())
    except ValueError as exc:
        raise WorkspaceContractError(
            "live_control_result_invalid",
            f"{field_name} must stay within the live-control run root.",
        ) from exc
    return candidate


def _same_path(left: Path, right: Path) -> bool:
    return left.resolve(strict=False) == right.resolve(strict=False)


def _stable_xml_text(root: ET.Element) -> str:
    return ET.tostring(root, encoding="unicode", short_empty_elements=True) + "\n"


@dataclass(frozen=True, slots=True)
class _SettingsSurface:
    build_file_path: Path
    build_name: str
    build_dir: Path


def _read_settings_surface(settings_path: Path, *, failure_state: str) -> _SettingsSurface:
    xml_path = _require_file(
        settings_path,
        failure_state,
        f"Settings.xml is missing: {settings_path}",
    )
    try:
        root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
    except (OSError, ET.ParseError) as exc:
        raise WorkspaceContractError(failure_state, f"Settings.xml is not valid XML: {exc}") from exc

    if root.tag != "PathOfBuilding":
        raise WorkspaceContractError(failure_state, "Settings.xml must use PathOfBuilding as the root element.")

    mode = root.find("Mode")
    if mode is None or mode.attrib.get("mode") != "BUILD":
        raise WorkspaceContractError(failure_state, "Settings.xml must contain one BUILD mode surface.")

    args = mode.findall("Arg")
    if len(args) < 2:
        raise WorkspaceContractError(
            failure_state,
            "Settings.xml BUILD mode must contain build path and build name arguments.",
        )

    build_file_value = args[0].attrib.get("string", "")
    build_name = args[1].attrib.get("string", "")
    misc = root.find("Misc")
    build_dir_value = "" if misc is None else misc.attrib.get("buildPath", "")

    if not build_file_value.strip():
        raise WorkspaceContractError(failure_state, "Settings.xml is missing the staged build file path.")
    if not build_dir_value.strip():
        raise WorkspaceContractError(failure_state, "Settings.xml is missing the staged build directory path.")

    return _SettingsSurface(
        build_file_path=Path(build_file_value),
        build_name=_require_non_empty_string(build_name, "build_name", failure_state),
        build_dir=Path(build_dir_value),
    )


def _retarget_settings_surface(
    settings_path: Path,
    *,
    build_file_path: Path,
    build_name: str,
    build_dir: Path,
) -> None:
    surface = _read_settings_surface(settings_path, failure_state="settings_surface_invalid")
    root = ET.fromstring(settings_path.read_text(encoding="utf-8"))
    mode = root.find("Mode")
    assert mode is not None  # validated by _read_settings_surface()
    mode.clear()
    mode.attrib["mode"] = "BUILD"
    ET.SubElement(mode, "Arg", {"string": build_file_path.as_posix()})
    ET.SubElement(mode, "Arg", {"string": build_name})

    misc = root.find("Misc")
    if misc is None:
        misc = ET.SubElement(root, "Misc")
    misc.attrib.clear()
    misc.attrib["buildPath"] = build_dir.as_posix().rstrip("/") + "/"

    # Preserve any extra settings elements copied from the source workspace.
    write_text(settings_path, _stable_xml_text(root))

    updated = _read_settings_surface(settings_path, failure_state="settings_surface_invalid")
    if surface.build_name != updated.build_name and surface.build_name != build_name:
        raise WorkspaceContractError(
            "settings_surface_invalid",
            "Retargeted Settings.xml did not preserve the expected build name surface.",
        )


def _build_file_records(build_dir: Path) -> list[dict[str, Any]]:
    resolved_build_dir = _require_dir(
        build_dir,
        "variant_manifest_invalid",
        f"Variant build directory is missing: {build_dir}",
    )
    records: list[dict[str, Any]] = []
    for path in sorted(resolved_build_dir.rglob("*")):
        if not path.is_file():
            continue
        records.append(
            {
                "path": _path_string(path),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
        )
    if not records:
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            f"Variant build directory contains no staged build files: {resolved_build_dir}",
        )
    return records


@dataclass(frozen=True, slots=True)
class _VariantLayout:
    variant_id: str
    variant_root: Path
    workspace_path: Path
    settings_path: Path
    runtime_manifest_path: Path
    runtime_launcher_path: Path
    workspace_build_dir: Path
    variant_manifest_path: Path
    next_run_handoff_path: Path


@dataclass(frozen=True, slots=True)
class _WorkspaceLayout:
    workspace_id: str
    workspace_root: Path
    variants_root: Path
    workspace_manifest_path: Path

    def variant(self, variant_id: str) -> _VariantLayout:
        variant_root = self.variants_root / variant_id
        workspace_path = variant_root / "workspace"
        return _VariantLayout(
            variant_id=variant_id,
            variant_root=variant_root,
            workspace_path=workspace_path,
            settings_path=workspace_path / "Settings.xml",
            runtime_manifest_path=workspace_path / "manifest.xml",
            runtime_launcher_path=workspace_path / DEFAULT_LAUNCHER_RELATIVE_PATH,
            workspace_build_dir=workspace_path / "Builds",
            variant_manifest_path=variant_root / "variant_manifest.json",
            next_run_handoff_path=variant_root / "next_run_handoff.json",
        )


def _prepare_workspace_layout(workspace_id: str, workspaces_root: Path) -> _WorkspaceLayout:
    workspace_root = Path(workspaces_root) / workspace_id
    if workspace_root.exists():
        raise WorkspaceContractError(
            "workspace_exists",
            f"Workspace root already exists and will not be overwritten: {workspace_root}",
        )
    variants_root = workspace_root / "variants"
    variants_root.mkdir(parents=True, exist_ok=False)
    return _WorkspaceLayout(
        workspace_id=workspace_id,
        workspace_root=workspace_root.resolve(),
        variants_root=variants_root.resolve(),
        workspace_manifest_path=(workspace_root / "workspace_manifest.json").resolve(),
    )


def _existing_workspace_layout(workspace_manifest_path: Path) -> _WorkspaceLayout:
    manifest_path = _require_file(
        workspace_manifest_path,
        "workspace_manifest_missing",
        f"Workspace manifest is missing: {workspace_manifest_path}",
    )
    workspace_root = manifest_path.parent.resolve()
    variants_root = workspace_root / "variants"
    _require_dir(
        variants_root,
        "workspace_manifest_invalid",
        f"Workspace variants root is missing: {variants_root}",
    )
    return _WorkspaceLayout(
        workspace_id=workspace_root.name,
        workspace_root=workspace_root,
        variants_root=variants_root,
        workspace_manifest_path=manifest_path,
    )


@dataclass(frozen=True, slots=True)
class _AcceptedLiveControl:
    run_id: str
    build_id: str
    build_name: str
    control_result_path: Path
    input_request_path: Path
    runtime_snapshot_path: Path
    run_manifest_path: Path
    source_workspace_path: Path
    source_settings_path: Path
    source_runtime_manifest_path: Path
    source_runtime_launcher_path: Path
    source_workspace_build_path: Path
    source_bundle: dict[str, Any]


def _load_accepted_live_control(control_result_path: Path) -> _AcceptedLiveControl:
    control_result = _read_json_object(
        Path(control_result_path),
        missing_state="live_control_result_missing",
        invalid_state="live_control_result_invalid",
        label="control_result.json",
    )
    if control_result.get("supported_path") != LIVE_CONTROL_SUPPORTED_PATH:
        raise WorkspaceContractError(
            "live_control_supported_path_mismatch",
            "control_result.json does not reference the accepted live-control boundary.",
        )
    if control_result.get("control_state") != "launch_probe_succeeded" or control_result.get("failure_state") is not None:
        raise WorkspaceContractError(
            "live_control_not_success",
            "Base workspace creation requires an accepted live-control result with launch_probe_succeeded.",
        )

    run_root = control_result_path.resolve().parent
    run_id = _expect_string(control_result, "run_id", "live_control_result_invalid")
    build_id = _expect_string(control_result, "build_id", "live_control_result_invalid")

    workspace_build_path = _resolve_run_relative_path(
        run_root,
        _expect_string(control_result, "workspace_build_path", "live_control_result_invalid"),
        "workspace_build_path",
    )
    settings_path = _resolve_run_relative_path(
        run_root,
        _expect_string(control_result, "settings_path", "live_control_result_invalid"),
        "settings_path",
    )
    _require_file(
        workspace_build_path,
        "live_control_artifact_missing",
        f"Accepted live-control workspace build file is missing: {workspace_build_path}",
    )
    _require_file(
        settings_path,
        "live_control_artifact_missing",
        f"Accepted live-control Settings.xml is missing: {settings_path}",
    )

    input_request_path = run_root / "input_request.json"
    input_request = _read_json_object(
        input_request_path,
        missing_state="live_control_artifact_missing",
        invalid_state="live_control_result_invalid",
        label="input_request.json",
    )
    if input_request.get("supported_path") != LIVE_CONTROL_SUPPORTED_PATH:
        raise WorkspaceContractError(
            "live_control_supported_path_mismatch",
            "input_request.json does not match the accepted live-control boundary.",
        )
    if _expect_string(input_request, "run_id", "live_control_result_invalid") != run_id:
        raise WorkspaceContractError("live_control_result_invalid", "input_request.json run_id does not match control_result.json.")
    if _expect_string(input_request, "build_id", "live_control_result_invalid") != build_id:
        raise WorkspaceContractError(
            "live_control_result_invalid",
            "input_request.json build_id does not match control_result.json.",
        )
    if _expect_string(input_request, "workspace_build_path", "live_control_result_invalid") != _expect_string(
        control_result,
        "workspace_build_path",
        "live_control_result_invalid",
    ):
        raise WorkspaceContractError(
            "live_control_result_invalid",
            "input_request.json workspace_build_path does not match control_result.json.",
        )
    if _expect_string(input_request, "settings_path", "live_control_result_invalid") != _expect_string(
        control_result,
        "settings_path",
        "live_control_result_invalid",
    ):
        raise WorkspaceContractError(
            "live_control_result_invalid",
            "input_request.json settings_path does not match control_result.json.",
        )
    build_name = _expect_string(input_request, "build_name", "live_control_result_invalid")

    runtime_snapshot_path = run_root / "pob_runtime.json"
    runtime_snapshot = _read_json_object(
        runtime_snapshot_path,
        missing_state="live_control_artifact_missing",
        invalid_state="live_control_result_invalid",
        label="pob_runtime.json",
    )
    if runtime_snapshot.get("supported_path") != LIVE_CONTROL_SUPPORTED_PATH:
        raise WorkspaceContractError(
            "live_control_supported_path_mismatch",
            "pob_runtime.json does not match the accepted live-control boundary.",
        )
    control_surface = _expect_dict(runtime_snapshot, "control_surface", "live_control_result_invalid")
    if control_surface.get("surface_ready") is not True:
        raise WorkspaceContractError(
            "live_control_not_success",
            "pob_runtime.json does not mark the live-control surface as ready.",
        )

    source_workspace_path = _resolve_run_relative_path(
        run_root,
        _expect_string(control_surface, "workspace_root", "live_control_result_invalid"),
        "workspace_root",
    )
    source_runtime_manifest_path = _resolve_run_relative_path(
        run_root,
        _expect_string(control_surface, "workspace_manifest_path", "live_control_result_invalid"),
        "workspace_manifest_path",
    )
    source_runtime_launcher_path = _resolve_run_relative_path(
        run_root,
        _expect_string(control_surface, "workspace_launcher_path", "live_control_result_invalid"),
        "workspace_launcher_path",
    )

    if _expect_string(control_surface, "workspace_build_path", "live_control_result_invalid") != _expect_string(
        control_result,
        "workspace_build_path",
        "live_control_result_invalid",
    ):
        raise WorkspaceContractError(
            "live_control_result_invalid",
            "pob_runtime.json workspace_build_path does not match control_result.json.",
        )

    _require_dir(
        source_workspace_path,
        "live_control_artifact_missing",
        f"Accepted live-control workspace directory is missing: {source_workspace_path}",
    )
    _require_file(
        source_runtime_manifest_path,
        "live_control_artifact_missing",
        f"Accepted live-control runtime manifest is missing: {source_runtime_manifest_path}",
    )
    _require_file(
        source_runtime_launcher_path,
        "live_control_artifact_missing",
        f"Accepted live-control launcher is missing: {source_runtime_launcher_path}",
    )

    run_manifest_path = run_root / "run_manifest.json"
    run_manifest = _read_json_object(
        run_manifest_path,
        missing_state="live_control_artifact_missing",
        invalid_state="live_control_result_invalid",
        label="run_manifest.json",
    )
    if _expect_string(run_manifest, "run_id", "live_control_result_invalid") != run_id:
        raise WorkspaceContractError("live_control_result_invalid", "run_manifest.json run_id does not match control_result.json.")
    if _expect_string(run_manifest, "build_id", "live_control_result_invalid") != build_id:
        raise WorkspaceContractError("live_control_result_invalid", "run_manifest.json build_id does not match control_result.json.")
    if run_manifest.get("supported_path") != LIVE_CONTROL_SUPPORTED_PATH:
        raise WorkspaceContractError(
            "live_control_supported_path_mismatch",
            "run_manifest.json does not match the accepted live-control boundary.",
        )

    settings_surface = _read_settings_surface(settings_path, failure_state="settings_surface_invalid")
    expected_build_dir = source_workspace_path / "Builds"
    if not _same_path(settings_surface.build_file_path, workspace_build_path):
        raise WorkspaceContractError(
            "settings_surface_invalid",
            "Settings.xml does not point at the accepted live-control staged build file.",
        )
    if not _same_path(settings_surface.build_dir, expected_build_dir):
        raise WorkspaceContractError(
            "settings_surface_invalid",
            "Settings.xml does not point at the accepted live-control Build directory.",
        )
    if settings_surface.build_name != build_name:
        raise WorkspaceContractError(
            "settings_surface_invalid",
            "Settings.xml build name does not match input_request.json.",
        )

    source_bundle = {
        "supported_path": LIVE_CONTROL_SUPPORTED_PATH,
        "run_id": run_id,
        "build_id": build_id,
        "input_request_path": _path_string(input_request_path),
        "input_request_sha256": sha256_file(input_request_path),
        "control_result_path": _path_string(control_result_path),
        "control_result_sha256": sha256_file(control_result_path),
        "runtime_snapshot_path": _path_string(runtime_snapshot_path),
        "runtime_snapshot_sha256": sha256_file(runtime_snapshot_path),
        "run_manifest_path": _path_string(run_manifest_path),
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "source_workspace_path": _path_string(source_workspace_path),
        "source_settings_path": _path_string(settings_path),
        "source_runtime_manifest_path": _path_string(source_runtime_manifest_path),
        "source_runtime_launcher_path": _path_string(source_runtime_launcher_path),
        "source_workspace_build_path": _path_string(workspace_build_path),
        "source_workspace_build_sha256": sha256_file(workspace_build_path),
    }

    return _AcceptedLiveControl(
        run_id=run_id,
        build_id=build_id,
        build_name=build_name,
        control_result_path=control_result_path.resolve(),
        input_request_path=input_request_path.resolve(),
        runtime_snapshot_path=runtime_snapshot_path.resolve(),
        run_manifest_path=run_manifest_path.resolve(),
        source_workspace_path=source_workspace_path.resolve(),
        source_settings_path=settings_path.resolve(),
        source_runtime_manifest_path=source_runtime_manifest_path.resolve(),
        source_runtime_launcher_path=source_runtime_launcher_path.resolve(),
        source_workspace_build_path=workspace_build_path.resolve(),
        source_bundle=source_bundle,
    )


def _materialize_variant_workspace(
    *,
    source_workspace_path: Path,
    source_settings_path: Path,
    source_primary_build_path: Path,
    build_name: str,
    target_layout: _VariantLayout,
) -> tuple[list[dict[str, Any]], Path]:
    source_workspace = _require_dir(
        source_workspace_path,
        "live_control_artifact_missing",
        f"Source workspace directory is missing: {source_workspace_path}",
    )
    _require_file(
        source_settings_path,
        "settings_surface_invalid",
        f"Source Settings.xml is missing: {source_settings_path}",
    )
    _require_file(
        source_primary_build_path,
        "live_control_artifact_missing",
        f"Source primary build file is missing: {source_primary_build_path}",
    )
    _require_file(
        source_workspace / "manifest.xml",
        "live_control_artifact_missing",
        f"Source runtime manifest is missing: {source_workspace / 'manifest.xml'}",
    )
    _require_file(
        source_workspace / DEFAULT_LAUNCHER_RELATIVE_PATH,
        "live_control_artifact_missing",
        f"Source launcher is missing: {source_workspace / DEFAULT_LAUNCHER_RELATIVE_PATH}",
    )

    source_surface = _read_settings_surface(source_settings_path, failure_state="settings_surface_invalid")
    if not _same_path(source_surface.build_file_path, source_primary_build_path):
        raise WorkspaceContractError(
            "settings_surface_invalid",
            "Source Settings.xml does not point at the declared primary build file.",
        )
    if not _same_path(source_surface.build_dir, source_workspace / "Builds"):
        raise WorkspaceContractError(
            "settings_surface_invalid",
            "Source Settings.xml does not point at the source Build directory.",
        )
    if source_surface.build_name != build_name:
        raise WorkspaceContractError(
            "settings_surface_invalid",
            "Source Settings.xml build name does not match the declared build name.",
        )

    if target_layout.variant_root.exists():
        raise WorkspaceContractError(
            "variant_exists",
            f"Variant root already exists and will not be overwritten: {target_layout.variant_root}",
        )
    target_layout.variant_root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(source_workspace, target_layout.workspace_path)

    _require_file(
        target_layout.runtime_manifest_path,
        "variant_manifest_invalid",
        f"Copied runtime manifest is missing: {target_layout.runtime_manifest_path}",
    )
    _require_file(
        target_layout.runtime_launcher_path,
        "variant_manifest_invalid",
        f"Copied launcher is missing: {target_layout.runtime_launcher_path}",
    )

    target_primary_build_path = target_layout.workspace_build_dir / source_primary_build_path.name
    _require_file(
        target_primary_build_path,
        "variant_manifest_invalid",
        f"Copied primary build file is missing: {target_primary_build_path}",
    )
    _retarget_settings_surface(
        target_layout.settings_path,
        build_file_path=target_primary_build_path,
        build_name=build_name,
        build_dir=target_layout.workspace_build_dir,
    )

    copied_surface = _read_settings_surface(target_layout.settings_path, failure_state="variant_manifest_invalid")
    if not _same_path(copied_surface.build_file_path, target_primary_build_path):
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "Copied Settings.xml does not point at the copied primary build file.",
        )
    if not _same_path(copied_surface.build_dir, target_layout.workspace_build_dir):
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "Copied Settings.xml does not point at the copied Build directory.",
        )
    if copied_surface.build_name != build_name:
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "Copied Settings.xml build name does not match the expected build name.",
        )

    return _build_file_records(target_layout.workspace_build_dir), target_primary_build_path.resolve()


def _variant_record_payload(
    *,
    variant_id: str,
    variant_role: str,
    parent_variant_id: str | None,
    target_layout: _VariantLayout,
    primary_build_path: Path,
    created_at: str,
) -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "variant_role": variant_role,
        "parent_variant_id": parent_variant_id,
        "variant_manifest_path": _path_string(target_layout.variant_manifest_path),
        "next_run_handoff_path": _path_string(target_layout.next_run_handoff_path),
        "variant_root": _path_string(target_layout.variant_root),
        "workspace_path": _path_string(target_layout.workspace_path),
        "settings_path": _path_string(target_layout.settings_path),
        "runtime_manifest_path": _path_string(target_layout.runtime_manifest_path),
        "runtime_launcher_path": _path_string(target_layout.runtime_launcher_path),
        "primary_build_path": _path_string(primary_build_path),
        "created_at": created_at,
    }


def _variant_manifest_payload(
    *,
    workspace_id: str,
    workspace_manifest_path: Path,
    variant_id: str,
    variant_role: str,
    parent_variant_id: str | None,
    target_layout: _VariantLayout,
    primary_build_path: Path,
    build_name: str,
    staged_build_files: list[dict[str, Any]],
    control_dependencies: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "supported_path": WORKSPACE_SUPPORTED_PATH,
        "variant_id": variant_id,
        "variant_role": variant_role,
        "parent_variant_id": parent_variant_id,
        "workspace_manifest_path": _path_string(workspace_manifest_path),
        "variant_root": _path_string(target_layout.variant_root),
        "workspace_path": _path_string(target_layout.workspace_path),
        "settings_path": _path_string(target_layout.settings_path),
        "runtime_manifest_path": _path_string(target_layout.runtime_manifest_path),
        "runtime_launcher_path": _path_string(target_layout.runtime_launcher_path),
        "primary_build_path": _path_string(primary_build_path),
        "build_name": build_name,
        "staged_build_files": staged_build_files,
        "control_dependencies": control_dependencies,
        "next_run_handoff_path": _path_string(target_layout.next_run_handoff_path),
        "created_at": created_at,
    }


def _next_run_handoff_payload(
    *,
    workspace_id: str,
    workspace_manifest_path: Path,
    variant_manifest_path: Path,
    variant_id: str,
    variant_role: str,
    parent_variant_id: str | None,
    target_layout: _VariantLayout,
    primary_build_path: Path,
    build_name: str,
    staged_build_files: list[dict[str, Any]],
    control_dependencies: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    return {
        "handoff_kind": VARIANT_HANDOFF_KIND,
        "workspace_id": workspace_id,
        "supported_path": WORKSPACE_SUPPORTED_PATH,
        "variant_id": variant_id,
        "variant_role": variant_role,
        "parent_variant_id": parent_variant_id,
        "workspace_manifest_path": _path_string(workspace_manifest_path),
        "variant_manifest_path": _path_string(variant_manifest_path),
        "workspace_path": _path_string(target_layout.workspace_path),
        "settings_path": _path_string(target_layout.settings_path),
        "runtime_manifest_path": _path_string(target_layout.runtime_manifest_path),
        "runtime_launcher_path": _path_string(target_layout.runtime_launcher_path),
        "primary_build_path": _path_string(primary_build_path),
        "build_name": build_name,
        "staged_build_files": staged_build_files,
        "control_dependencies": control_dependencies,
        "created_at": created_at,
    }


def _write_variant_surfaces(
    *,
    workspace_id: str,
    workspace_manifest_path: Path,
    variant_id: str,
    variant_role: str,
    parent_variant_id: str | None,
    target_layout: _VariantLayout,
    primary_build_path: Path,
    build_name: str,
    staged_build_files: list[dict[str, Any]],
    control_dependencies: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    variant_manifest = _variant_manifest_payload(
        workspace_id=workspace_id,
        workspace_manifest_path=workspace_manifest_path,
        variant_id=variant_id,
        variant_role=variant_role,
        parent_variant_id=parent_variant_id,
        target_layout=target_layout,
        primary_build_path=primary_build_path,
        build_name=build_name,
        staged_build_files=staged_build_files,
        control_dependencies=control_dependencies,
        created_at=created_at,
    )
    write_json(target_layout.variant_manifest_path, variant_manifest)
    write_json(
        target_layout.next_run_handoff_path,
        _next_run_handoff_payload(
            workspace_id=workspace_id,
            workspace_manifest_path=workspace_manifest_path,
            variant_manifest_path=target_layout.variant_manifest_path,
            variant_id=variant_id,
            variant_role=variant_role,
            parent_variant_id=parent_variant_id,
            target_layout=target_layout,
            primary_build_path=primary_build_path,
            build_name=build_name,
            staged_build_files=staged_build_files,
            control_dependencies=control_dependencies,
            created_at=created_at,
        ),
    )
    return _variant_record_payload(
        variant_id=variant_id,
        variant_role=variant_role,
        parent_variant_id=parent_variant_id,
        target_layout=target_layout,
        primary_build_path=primary_build_path,
        created_at=created_at,
    )


def _find_variant_record(
    workspace_manifest: dict[str, Any],
    *,
    variant_id: str,
    failure_state: str,
) -> dict[str, Any]:
    variants = _expect_list(workspace_manifest, "variants", failure_state)
    for record in variants:
        if not isinstance(record, dict):
            raise WorkspaceContractError(failure_state, "variants must contain JSON objects.")
        if record.get("variant_id") == variant_id:
            return record
    raise WorkspaceContractError(failure_state, f"Variant is missing from workspace_manifest.json: {variant_id}")


def _load_workspace_manifest(workspace_manifest_path: Path) -> dict[str, Any]:
    payload = _read_json_object(
        workspace_manifest_path,
        missing_state="workspace_manifest_missing",
        invalid_state="workspace_manifest_invalid",
        label="workspace_manifest.json",
    )
    if payload.get("supported_path") != WORKSPACE_SUPPORTED_PATH:
        raise WorkspaceContractError(
            "workspace_manifest_invalid",
            "workspace_manifest.json does not reference the accepted workspace boundary.",
        )
    workspace_id = _expect_string(payload, "workspace_id", "workspace_manifest_invalid")
    workspace_root = _expect_absolute_path(payload, "workspace_root", "workspace_manifest_invalid")
    declared_manifest_path = _expect_absolute_path(payload, "workspace_manifest_path", "workspace_manifest_invalid")
    base_variant_id = _expect_string(payload, "base_variant_id", "workspace_manifest_invalid")
    active_variant_id = _expect_string(payload, "active_variant_id", "workspace_manifest_invalid")
    _expect_string(payload, "created_at", "workspace_manifest_invalid")
    _expect_string(payload, "updated_at", "workspace_manifest_invalid")
    source_live_control = _expect_dict(payload, "source_live_control", "workspace_manifest_invalid")
    if source_live_control.get("supported_path") != LIVE_CONTROL_SUPPORTED_PATH:
        raise WorkspaceContractError(
            "workspace_manifest_invalid",
            "workspace_manifest.json source_live_control does not point at the accepted live-control boundary.",
        )
    _find_variant_record(payload, variant_id=base_variant_id, failure_state="workspace_manifest_invalid")
    _find_variant_record(payload, variant_id=active_variant_id, failure_state="workspace_manifest_invalid")
    if workspace_root != workspace_manifest_path.resolve().parent:
        raise WorkspaceContractError(
            "workspace_manifest_invalid",
            "workspace_manifest.json workspace_root does not match the manifest location.",
        )
    if declared_manifest_path != workspace_manifest_path.resolve():
        raise WorkspaceContractError(
            "workspace_manifest_invalid",
            "workspace_manifest.json workspace_manifest_path does not match the manifest location.",
        )
    if workspace_id != workspace_root.name:
        raise WorkspaceContractError(
            "workspace_manifest_invalid",
            "workspace_manifest.json workspace_id does not match the workspace root directory name.",
        )
    return payload


def _load_variant_manifest(
    variant_manifest_path: Path,
    *,
    workspace_id: str,
    variant_id: str,
) -> dict[str, Any]:
    payload = _read_json_object(
        variant_manifest_path,
        missing_state="variant_manifest_missing",
        invalid_state="variant_manifest_invalid",
        label="variant_manifest.json",
    )
    if payload.get("supported_path") != WORKSPACE_SUPPORTED_PATH:
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "variant_manifest.json does not reference the accepted workspace boundary.",
        )
    if _expect_string(payload, "workspace_id", "variant_manifest_invalid") != workspace_id:
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "variant_manifest.json workspace_id does not match workspace_manifest.json.",
        )
    if _expect_string(payload, "variant_id", "variant_manifest_invalid") != variant_id:
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "variant_manifest.json variant_id does not match workspace_manifest.json.",
        )
    return payload


def _validate_variant_record(record: dict[str, Any], *, failure_state: str) -> None:
    variant_role = _expect_string(record, "variant_role", failure_state)
    if variant_role not in {"base", "fork"}:
        raise WorkspaceContractError(failure_state, "variant_role must be either 'base' or 'fork'.")
    _expect_optional_string(record, "parent_variant_id", failure_state)
    for field_name in (
        "variant_manifest_path",
        "next_run_handoff_path",
        "variant_root",
        "workspace_path",
        "settings_path",
        "runtime_manifest_path",
        "runtime_launcher_path",
        "primary_build_path",
        "created_at",
    ):
        if field_name == "created_at":
            _expect_string(record, field_name, failure_state)
            continue
        _expect_absolute_path(record, field_name, failure_state)


@dataclass(frozen=True, slots=True)
class PoBBaseWorkspaceRequest:
    """Request to create a base PoB workspace from one accepted live-control result."""

    workspace_id: str
    base_variant_id: str
    control_result_path: Path
    created_at: str | None = None

    def __post_init__(self) -> None:
        try:
            validate_token(self.workspace_id, "workspace_id")
            validate_token(self.base_variant_id, "base_variant_id")
        except RuntimeError as exc:
            raise WorkspaceContractError("invalid_request", str(exc)) from exc
        if not isinstance(self.control_result_path, Path):
            raise WorkspaceContractError("invalid_request", "control_result_path must be a Path.")
        if self.created_at is not None:
            _require_non_empty_string(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class PoBVariantForkRequest:
    """Request to fork one repo-owned PoB workspace variant."""

    workspace_manifest_path: Path
    parent_variant_id: str
    variant_id: str
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.workspace_manifest_path, Path):
            raise WorkspaceContractError("invalid_request", "workspace_manifest_path must be a Path.")
        try:
            validate_token(self.parent_variant_id, "parent_variant_id")
            validate_token(self.variant_id, "variant_id")
        except RuntimeError as exc:
            raise WorkspaceContractError("invalid_request", str(exc)) from exc
        if self.created_at is not None:
            _require_non_empty_string(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class PoBWorkspaceVariantResult:
    """Materialized repo-owned workspace surface for one PoB variant."""

    workspace_id: str
    variant_id: str
    variant_role: str
    parent_variant_id: str | None
    supported_path: str
    workspace_root: Path
    workspace_manifest_path: Path
    variant_root: Path
    variant_manifest_path: Path
    next_run_handoff_path: Path
    workspace_path: Path
    settings_path: Path
    runtime_manifest_path: Path
    runtime_launcher_path: Path
    primary_build_path: Path


def create_base_workspace(
    request: PoBBaseWorkspaceRequest,
    *,
    workspaces_root: Path = DEFAULT_WORKSPACES_ROOT,
) -> PoBWorkspaceVariantResult:
    """Create one repo-owned base workspace from an accepted live-control result."""

    accepted = _load_accepted_live_control(request.control_result_path)
    created_at = request.created_at or utc_now_iso()
    layout = _prepare_workspace_layout(request.workspace_id, workspaces_root=Path(workspaces_root))
    variant_layout = layout.variant(request.base_variant_id)

    staged_build_files, primary_build_path = _materialize_variant_workspace(
        source_workspace_path=accepted.source_workspace_path,
        source_settings_path=accepted.source_settings_path,
        source_primary_build_path=accepted.source_workspace_build_path,
        build_name=accepted.build_name,
        target_layout=variant_layout,
    )

    workspace_manifest = {
        "workspace_id": request.workspace_id,
        "supported_path": WORKSPACE_SUPPORTED_PATH,
        "workspace_root": _path_string(layout.workspace_root),
        "workspace_manifest_path": _path_string(layout.workspace_manifest_path),
        "base_variant_id": request.base_variant_id,
        "active_variant_id": request.base_variant_id,
        "created_at": created_at,
        "updated_at": created_at,
        "source_live_control": accepted.source_bundle,
        "variants": [
            _write_variant_surfaces(
                workspace_id=request.workspace_id,
                workspace_manifest_path=layout.workspace_manifest_path,
                variant_id=request.base_variant_id,
                variant_role="base",
                parent_variant_id=None,
                target_layout=variant_layout,
                primary_build_path=primary_build_path,
                build_name=accepted.build_name,
                staged_build_files=staged_build_files,
                control_dependencies=accepted.source_bundle,
                created_at=created_at,
            )
        ],
    }
    write_json(layout.workspace_manifest_path, workspace_manifest)

    return PoBWorkspaceVariantResult(
        workspace_id=request.workspace_id,
        variant_id=request.base_variant_id,
        variant_role="base",
        parent_variant_id=None,
        supported_path=WORKSPACE_SUPPORTED_PATH,
        workspace_root=layout.workspace_root,
        workspace_manifest_path=layout.workspace_manifest_path,
        variant_root=variant_layout.variant_root.resolve(),
        variant_manifest_path=variant_layout.variant_manifest_path.resolve(),
        next_run_handoff_path=variant_layout.next_run_handoff_path.resolve(),
        workspace_path=variant_layout.workspace_path.resolve(),
        settings_path=variant_layout.settings_path.resolve(),
        runtime_manifest_path=variant_layout.runtime_manifest_path.resolve(),
        runtime_launcher_path=variant_layout.runtime_launcher_path.resolve(),
        primary_build_path=primary_build_path,
    )


def fork_variant_workspace(request: PoBVariantForkRequest) -> PoBWorkspaceVariantResult:
    """Fork one repo-owned PoB workspace variant without manual operator copying."""

    created_at = request.created_at or utc_now_iso()
    layout = _existing_workspace_layout(request.workspace_manifest_path)
    workspace_manifest = _load_workspace_manifest(layout.workspace_manifest_path)
    workspace_id = _expect_string(workspace_manifest, "workspace_id", "workspace_manifest_invalid")
    if request.variant_id == request.parent_variant_id:
        raise WorkspaceContractError(
            "invalid_request",
            "variant_id must differ from parent_variant_id when forking a variant.",
        )

    for existing_record in _expect_list(workspace_manifest, "variants", "workspace_manifest_invalid"):
        if not isinstance(existing_record, dict):
            raise WorkspaceContractError("workspace_manifest_invalid", "variants must contain JSON objects.")
        if existing_record.get("variant_id") == request.variant_id:
            raise WorkspaceContractError(
                "variant_exists",
                f"Variant is already present in workspace_manifest.json: {request.variant_id}",
            )

    parent_record = _find_variant_record(
        workspace_manifest,
        variant_id=request.parent_variant_id,
        failure_state="variant_not_found",
    )
    _validate_variant_record(parent_record, failure_state="workspace_manifest_invalid")

    parent_variant_manifest_path = _expect_absolute_path(
        parent_record,
        "variant_manifest_path",
        "workspace_manifest_invalid",
    )
    parent_variant_manifest = _load_variant_manifest(
        parent_variant_manifest_path,
        workspace_id=workspace_id,
        variant_id=request.parent_variant_id,
    )
    parent_build_name = _expect_string(parent_variant_manifest, "build_name", "variant_manifest_invalid")
    parent_primary_build_path = _expect_absolute_path(
        parent_variant_manifest,
        "primary_build_path",
        "variant_manifest_invalid",
    )
    parent_workspace_path = _expect_absolute_path(
        parent_variant_manifest,
        "workspace_path",
        "variant_manifest_invalid",
    )
    parent_settings_path = _expect_absolute_path(
        parent_variant_manifest,
        "settings_path",
        "variant_manifest_invalid",
    )
    parent_runtime_manifest_path = _expect_absolute_path(
        parent_variant_manifest,
        "runtime_manifest_path",
        "variant_manifest_invalid",
    )
    parent_runtime_launcher_path = _expect_absolute_path(
        parent_variant_manifest,
        "runtime_launcher_path",
        "variant_manifest_invalid",
    )

    if parent_workspace_path != _expect_absolute_path(parent_record, "workspace_path", "workspace_manifest_invalid"):
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "variant_manifest.json workspace_path does not match workspace_manifest.json.",
        )
    if parent_settings_path != _expect_absolute_path(parent_record, "settings_path", "workspace_manifest_invalid"):
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "variant_manifest.json settings_path does not match workspace_manifest.json.",
        )
    if parent_primary_build_path != _expect_absolute_path(parent_record, "primary_build_path", "workspace_manifest_invalid"):
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "variant_manifest.json primary_build_path does not match workspace_manifest.json.",
        )
    if parent_runtime_manifest_path != _expect_absolute_path(
        parent_record,
        "runtime_manifest_path",
        "workspace_manifest_invalid",
    ):
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "variant_manifest.json runtime_manifest_path does not match workspace_manifest.json.",
        )
    if parent_runtime_launcher_path != _expect_absolute_path(
        parent_record,
        "runtime_launcher_path",
        "workspace_manifest_invalid",
    ):
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "variant_manifest.json runtime_launcher_path does not match workspace_manifest.json.",
        )

    _require_dir(
        parent_workspace_path,
        "variant_manifest_invalid",
        f"Parent workspace path is missing: {parent_workspace_path}",
    )
    _require_file(
        parent_settings_path,
        "variant_manifest_invalid",
        f"Parent Settings.xml is missing: {parent_settings_path}",
    )
    _require_file(
        parent_primary_build_path,
        "variant_manifest_invalid",
        f"Parent primary build file is missing: {parent_primary_build_path}",
    )
    _require_file(
        parent_runtime_manifest_path,
        "variant_manifest_invalid",
        f"Parent runtime manifest is missing: {parent_runtime_manifest_path}",
    )
    _require_file(
        parent_runtime_launcher_path,
        "variant_manifest_invalid",
        f"Parent launcher is missing: {parent_runtime_launcher_path}",
    )

    parent_settings_surface = _read_settings_surface(parent_settings_path, failure_state="variant_manifest_invalid")
    if not _same_path(parent_settings_surface.build_file_path, parent_primary_build_path):
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "Parent Settings.xml does not point at the parent primary build file.",
        )
    if not _same_path(parent_settings_surface.build_dir, parent_workspace_path / "Builds"):
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "Parent Settings.xml does not point at the parent Build directory.",
        )
    if parent_settings_surface.build_name != parent_build_name:
        raise WorkspaceContractError(
            "variant_manifest_invalid",
            "Parent Settings.xml build name does not match variant_manifest.json.",
        )

    source_live_control = _expect_dict(workspace_manifest, "source_live_control", "workspace_manifest_invalid")
    variant_layout = layout.variant(request.variant_id)
    staged_build_files, primary_build_path = _materialize_variant_workspace(
        source_workspace_path=parent_workspace_path,
        source_settings_path=parent_settings_path,
        source_primary_build_path=parent_primary_build_path,
        build_name=parent_build_name,
        target_layout=variant_layout,
    )

    variant_record = _write_variant_surfaces(
        workspace_id=workspace_id,
        workspace_manifest_path=layout.workspace_manifest_path,
        variant_id=request.variant_id,
        variant_role="fork",
        parent_variant_id=request.parent_variant_id,
        target_layout=variant_layout,
        primary_build_path=primary_build_path,
        build_name=parent_build_name,
        staged_build_files=staged_build_files,
        control_dependencies=source_live_control,
        created_at=created_at,
    )
    _expect_list(workspace_manifest, "variants", "workspace_manifest_invalid").append(variant_record)
    workspace_manifest["active_variant_id"] = request.variant_id
    workspace_manifest["updated_at"] = created_at
    write_json(layout.workspace_manifest_path, workspace_manifest)

    return PoBWorkspaceVariantResult(
        workspace_id=workspace_id,
        variant_id=request.variant_id,
        variant_role="fork",
        parent_variant_id=request.parent_variant_id,
        supported_path=WORKSPACE_SUPPORTED_PATH,
        workspace_root=layout.workspace_root,
        workspace_manifest_path=layout.workspace_manifest_path,
        variant_root=variant_layout.variant_root.resolve(),
        variant_manifest_path=variant_layout.variant_manifest_path.resolve(),
        next_run_handoff_path=variant_layout.next_run_handoff_path.resolve(),
        workspace_path=variant_layout.workspace_path.resolve(),
        settings_path=variant_layout.settings_path.resolve(),
        runtime_manifest_path=variant_layout.runtime_manifest_path.resolve(),
        runtime_launcher_path=variant_layout.runtime_launcher_path.resolve(),
        primary_build_path=primary_build_path,
    )


__all__ = [
    "DEFAULT_WORKSPACES_ROOT",
    "PoBBaseWorkspaceRequest",
    "PoBVariantForkRequest",
    "PoBWorkspaceVariantResult",
    "VARIANT_HANDOFF_KIND",
    "WORKSPACE_SUPPORTED_PATH",
    "WorkspaceContractError",
    "create_base_workspace",
    "fork_variant_workspace",
]
