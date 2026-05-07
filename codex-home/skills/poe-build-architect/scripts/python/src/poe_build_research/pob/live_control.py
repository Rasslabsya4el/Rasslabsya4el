"""Repo-owned live control boundary for the pinned Path of Building runtime."""

from __future__ import annotations

import math
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import (
    DEFAULT_RUNS_ROOT,
    PoBControlLayout,
    build_control_manifest,
    prepare_control_layout,
    sha256_file,
    validate_token,
    write_json,
    write_text,
)
from .release_manager import PoBReleaseManager, utc_now_iso

LIVE_CONTROL_SUPPORTED_PATH = "pinned_portable_build_xml_settings_v1"
DEFAULT_LAUNCHER_RELATIVE_PATH = Path("Path of Building.exe")
DEFAULT_STARTUP_WINDOW_SECONDS = 1.0
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 5.0


class LiveControlContractError(RuntimeError):
    """Raised when the live PoB control boundary cannot satisfy its contract."""

    def __init__(self, failure_state: str, message: str) -> None:
        super().__init__(message)
        self.failure_state = failure_state


def _validate_positive_seconds(value: float, field_name: str) -> float:
    if not math.isfinite(value) or value <= 0:
        raise LiveControlContractError(
            "invalid_control_window",
            f"{field_name} must be a finite value > 0 seconds.",
        )
    return value


def _require_non_empty_string(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LiveControlContractError("invalid_request", f"{field_name} must be a non-empty string.")
    return value.strip()


def _validate_build_xml(xml_text: str) -> None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise LiveControlContractError("invalid_build_xml", f"build_xml is not valid XML: {exc}") from exc

    if root.tag != "PathOfBuilding":
        raise LiveControlContractError(
            "invalid_build_xml",
            "build_xml must use PathOfBuilding as the root element.",
        )


def _stable_xml_text(root: ET.Element) -> str:
    return ET.tostring(root, encoding="unicode", short_empty_elements=True) + "\n"


@dataclass(frozen=True, slots=True)
class PoBBuildFileInput:
    """Deterministic build file input for the live control boundary."""

    build_xml: str
    filename: str = "build.xml"
    build_name: str | None = None

    def __post_init__(self) -> None:
        try:
            validate_token(self.filename, "filename")
        except RuntimeError as exc:
            raise LiveControlContractError("invalid_request", str(exc)) from exc
        if not self.filename.lower().endswith(".xml"):
            raise LiveControlContractError("invalid_build_xml", "filename must end with .xml.")
        _validate_build_xml(self.build_xml)
        if self.build_name is not None:
            _require_non_empty_string(self.build_name, "build_name")

    @property
    def resolved_build_name(self) -> str:
        if self.build_name is not None:
            return self.build_name.strip()
        return Path(self.filename).stem


@dataclass(frozen=True, slots=True)
class PoBLiveControlRequest:
    """Inputs required to stage and probe the pinned PoB runtime."""

    run_id: str
    build_id: str
    build_input: PoBBuildFileInput
    build_source: str = "user_intent"
    startup_window_seconds: float = DEFAULT_STARTUP_WINDOW_SECONDS
    shutdown_timeout_seconds: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        try:
            validate_token(self.run_id, "run_id")
        except RuntimeError as exc:
            raise LiveControlContractError("invalid_request", str(exc)) from exc
        _require_non_empty_string(self.build_id, "build_id")
        _require_non_empty_string(self.build_source, "build_source")
        if not isinstance(self.build_input, PoBBuildFileInput):
            raise LiveControlContractError("invalid_request", "build_input must be a PoBBuildFileInput.")
        try:
            startup_window_seconds = float(self.startup_window_seconds)
            shutdown_timeout_seconds = float(self.shutdown_timeout_seconds)
        except (TypeError, ValueError) as exc:
            raise LiveControlContractError(
                "invalid_control_window",
                "startup_window_seconds and shutdown_timeout_seconds must be numeric.",
            ) from exc
        object.__setattr__(
            self,
            "startup_window_seconds",
            _validate_positive_seconds(startup_window_seconds, "startup_window_seconds"),
        )
        object.__setattr__(
            self,
            "shutdown_timeout_seconds",
            _validate_positive_seconds(shutdown_timeout_seconds, "shutdown_timeout_seconds"),
        )


@dataclass(frozen=True, slots=True)
class PoBLiveControlResult:
    """Observed artifact bundle for one live-control probe."""

    run_id: str
    build_id: str
    supported_path: str
    run_root: Path
    manifest_path: Path
    control_result_path: Path
    runtime_snapshot_path: Path
    workspace_dir: Path
    settings_path: Path
    workspace_build_path: Path
    stdout_log_path: Path
    stderr_log_path: Path
    control_result: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _LaunchObservation:
    command: tuple[str, ...]
    startup_observed: bool
    exit_code: int
    termination: str
    stdout: str
    stderr: str


def _write_settings_xml(
    settings_path: Path,
    *,
    build_file_path: Path,
    build_name: str,
    build_path: Path,
) -> Path:
    root = ET.Element("PathOfBuilding")
    mode = ET.SubElement(root, "Mode", {"mode": "BUILD"})
    ET.SubElement(mode, "Arg", {"string": build_file_path.as_posix()})
    ET.SubElement(mode, "Arg", {"string": build_name})
    ET.SubElement(root, "Misc", {"buildPath": build_path.as_posix().rstrip("/") + "/"})
    return write_text(settings_path, _stable_xml_text(root))


def _runtime_snapshot(
    *,
    request: PoBLiveControlRequest,
    layout: PoBControlLayout,
    release_manager: PoBReleaseManager,
    fetch_report: Any,
    verify_report: Any,
    release_payload: dict[str, Any],
    lock_fingerprint: str,
    input_fingerprint: str,
    surface_ready: bool,
    workspace_build_path: Path,
) -> dict[str, Any]:
    return {
        "repo": release_payload["repo"],
        "tag": release_payload["tag"],
        "asset_name": release_payload["asset_name"],
        "asset_sha256": release_payload["asset_sha256"],
        "lock_path": str(release_manager.lock_path),
        "lock_fingerprint": lock_fingerprint,
        "archive_path": str(fetch_report.archive_path),
        "extract_dir": str(fetch_report.extract_dir),
        "verified_asset_sha256": verify_report.asset_sha256,
        "verified_asset_size": verify_report.asset_size,
        "runtime_present": verify_report.extracted_runtime_present,
        "supported_path": LIVE_CONTROL_SUPPORTED_PATH,
        "control_surface": {
            "build_source": request.build_source,
            "control_kind": "settings_build_file_launch_probe",
            "launcher_relative_path": DEFAULT_LAUNCHER_RELATIVE_PATH.as_posix(),
            "workspace_root": layout.relative_path(layout.workspace_dir),
            "workspace_manifest_path": layout.relative_path(layout.workspace_dir / "manifest.xml"),
            "workspace_launcher_path": layout.relative_path(layout.workspace_dir / DEFAULT_LAUNCHER_RELATIVE_PATH),
            "workspace_settings_path": layout.relative_path(layout.settings_path),
            "workspace_build_path": layout.relative_path(workspace_build_path),
            "input_fingerprint": input_fingerprint,
            "surface_ready": surface_ready,
        },
    }


def _write_control_result(
    layout: PoBControlLayout,
    *,
    request: PoBLiveControlRequest,
    launched_at: str,
    control_state: str,
    failure_state: str | None,
    failure_message: str | None,
    startup_observed: bool,
    launch_command: tuple[str, ...],
    exit_code: int,
    termination: str,
    workspace_build_path: Path,
) -> dict[str, Any]:
    payload = {
        "run_id": request.run_id,
        "build_id": request.build_id,
        "supported_path": LIVE_CONTROL_SUPPORTED_PATH,
        "control_state": control_state,
        "failure_state": failure_state,
        "failure_message": failure_message,
        "launched_at": launched_at,
        "startup_window_seconds": request.startup_window_seconds,
        "shutdown_timeout_seconds": request.shutdown_timeout_seconds,
        "startup_observed": startup_observed,
        "launch_command": list(launch_command),
        "launch_cwd": layout.relative_path(layout.workspace_dir),
        "workspace_build_path": layout.relative_path(workspace_build_path),
        "settings_path": layout.relative_path(layout.settings_path),
        "stdout_log_path": layout.relative_path(layout.stdout_log_path),
        "stderr_log_path": layout.relative_path(layout.stderr_log_path),
        "exit_code": exit_code,
        "termination": termination,
    }
    write_json(layout.control_result_path, payload)
    return payload


def _write_control_manifest(
    layout: PoBControlLayout,
    *,
    request: PoBLiveControlRequest,
    launched_at: str,
) -> Path:
    write_json(
        layout.run_manifest_path,
        build_control_manifest(
            layout,
            run_id=request.run_id,
            build_id=request.build_id,
            supported_path=LIVE_CONTROL_SUPPORTED_PATH,
            launched_at=launched_at,
        ),
    )
    return layout.run_manifest_path


def _fail_closed(
    layout: PoBControlLayout,
    *,
    request: PoBLiveControlRequest,
    launched_at: str,
    failure_state: str,
    failure_message: str,
    launch_command: tuple[str, ...],
    exit_code: int,
    termination: str,
    startup_observed: bool,
    workspace_build_path: Path,
) -> None:
    _write_control_result(
        layout,
        request=request,
        launched_at=launched_at,
        control_state="failed",
        failure_state=failure_state,
        failure_message=failure_message,
        startup_observed=startup_observed,
        launch_command=launch_command,
        exit_code=exit_code,
        termination=termination,
        workspace_build_path=workspace_build_path,
    )
    _write_control_manifest(layout, request=request, launched_at=launched_at)
    raise LiveControlContractError(failure_state, failure_message)


def _launch_runtime_probe(
    layout: PoBControlLayout,
    *,
    request: PoBLiveControlRequest,
) -> _LaunchObservation:
    workspace_launcher_path = layout.workspace_dir / DEFAULT_LAUNCHER_RELATIVE_PATH
    launch_command = (str(workspace_launcher_path),)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        process = subprocess.Popen(
            launch_command,
            cwd=layout.workspace_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
    except OSError as exc:
        raise LiveControlContractError(
            "runtime_launch_failed",
            f"Failed to launch {DEFAULT_LAUNCHER_RELATIVE_PATH.as_posix()}: {exc}",
        ) from exc

    startup_observed = False
    termination = "not_needed"

    try:
        exit_code = process.wait(timeout=request.startup_window_seconds)
    except subprocess.TimeoutExpired:
        startup_observed = True
        termination = "terminate"
        process.terminate()
        try:
            exit_code = process.wait(timeout=request.shutdown_timeout_seconds)
        except subprocess.TimeoutExpired:
            termination = "kill"
            process.kill()
            try:
                exit_code = process.wait(timeout=request.shutdown_timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                raise LiveControlContractError(
                    "runtime_shutdown_timeout",
                    "Pinned PoB runtime did not terminate within the shutdown timeout window.",
                ) from exc

    stdout, stderr = process.communicate()
    return _LaunchObservation(
        command=launch_command,
        startup_observed=startup_observed,
        exit_code=exit_code,
        termination=termination,
        stdout=stdout,
        stderr=stderr,
    )


def run_live_control(
    request: PoBLiveControlRequest,
    *,
    release_manager: PoBReleaseManager | None = None,
    artifacts_root: Path = DEFAULT_RUNS_ROOT,
    launched_at: str | None = None,
) -> PoBLiveControlResult:
    """Stage one deterministic build-file workspace and probe the pinned PoB runtime."""

    manager = release_manager or PoBReleaseManager()
    layout = prepare_control_layout(request.run_id, artifacts_root=artifacts_root)
    launched_at_value = launched_at or utc_now_iso()
    build_input_path = layout.build_input_path(request.build_input.filename)
    workspace_build_path = layout.workspace_build_path(request.build_input.filename)
    launch_command = (str(DEFAULT_LAUNCHER_RELATIVE_PATH),)

    write_text(build_input_path, request.build_input.build_xml)
    write_text(layout.stdout_log_path, "")
    write_text(layout.stderr_log_path, "")
    write_json(
        layout.input_request_path,
        {
            "run_id": request.run_id,
            "build_id": request.build_id,
            "build_source": request.build_source,
            "supported_path": LIVE_CONTROL_SUPPORTED_PATH,
            "build_input_path": layout.relative_path(build_input_path),
            "workspace_build_path": layout.relative_path(workspace_build_path),
            "settings_path": layout.relative_path(layout.settings_path),
            "build_name": request.build_input.resolved_build_name,
            "launched_at": launched_at_value,
        },
    )

    fetch_report = manager.fetch()
    verify_report = manager.verify()
    release_payload = manager.show_lock()
    lock_fingerprint = sha256_file(manager.lock_path)
    input_fingerprint = sha256_file(build_input_path)

    source_manifest_path = fetch_report.extract_dir / "manifest.xml"
    source_launcher_path = fetch_report.extract_dir / DEFAULT_LAUNCHER_RELATIVE_PATH
    surface_ready = source_manifest_path.is_file() and source_launcher_path.is_file()

    write_json(
        layout.pob_runtime_path,
        _runtime_snapshot(
            request=request,
            layout=layout,
            release_manager=manager,
            fetch_report=fetch_report,
            verify_report=verify_report,
            release_payload=release_payload,
            lock_fingerprint=lock_fingerprint,
            input_fingerprint=input_fingerprint,
            surface_ready=surface_ready,
            workspace_build_path=workspace_build_path,
        ),
    )

    if not source_manifest_path.is_file():
        _fail_closed(
            layout,
            request=request,
            launched_at=launched_at_value,
            failure_state="runtime_manifest_missing",
            failure_message="Pinned runtime is missing manifest.xml; live control cannot load the committed build surface.",
            launch_command=launch_command,
            exit_code=-1,
            termination="not_needed",
            startup_observed=False,
            workspace_build_path=workspace_build_path,
        )
    if not source_launcher_path.is_file():
        _fail_closed(
            layout,
            request=request,
            launched_at=launched_at_value,
            failure_state="runtime_launcher_missing",
            failure_message=(
                "Pinned runtime is missing "
                f"{DEFAULT_LAUNCHER_RELATIVE_PATH.as_posix()}; live control cannot launch fail-closed."
            ),
            launch_command=launch_command,
            exit_code=-1,
            termination="not_needed",
            startup_observed=False,
            workspace_build_path=workspace_build_path,
        )

    shutil.copytree(fetch_report.extract_dir, layout.workspace_dir, dirs_exist_ok=True)
    layout.workspace_build_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(build_input_path, workspace_build_path)
    _write_settings_xml(
        layout.settings_path,
        build_file_path=workspace_build_path,
        build_name=request.build_input.resolved_build_name,
        build_path=layout.workspace_build_dir,
    )

    if not workspace_build_path.is_file():
        _fail_closed(
            layout,
            request=request,
            launched_at=launched_at_value,
            failure_state="workspace_build_missing",
            failure_message="Live control did not materialize the deterministic workspace build file.",
            launch_command=launch_command,
            exit_code=-1,
            termination="not_needed",
            startup_observed=False,
            workspace_build_path=workspace_build_path,
        )
    if not layout.settings_path.is_file():
        _fail_closed(
            layout,
            request=request,
            launched_at=launched_at_value,
            failure_state="settings_surface_missing",
            failure_message="Live control did not materialize Settings.xml for the pinned runtime workspace.",
            launch_command=launch_command,
            exit_code=-1,
            termination="not_needed",
            startup_observed=False,
            workspace_build_path=workspace_build_path,
        )

    try:
        observation = _launch_runtime_probe(layout, request=request)
    except LiveControlContractError as exc:
        _fail_closed(
            layout,
            request=request,
            launched_at=launched_at_value,
            failure_state=exc.failure_state,
            failure_message=str(exc),
            launch_command=launch_command,
            exit_code=-1,
            termination="kill" if exc.failure_state == "runtime_shutdown_timeout" else "not_needed",
            startup_observed=False,
            workspace_build_path=workspace_build_path,
        )

    write_text(layout.stdout_log_path, observation.stdout)
    write_text(layout.stderr_log_path, observation.stderr)

    if not observation.startup_observed:
        _fail_closed(
            layout,
            request=request,
            launched_at=launched_at_value,
            failure_state="runtime_exited_early",
            failure_message=(
                "Pinned PoB runtime exited before the startup probe window elapsed; "
                "live control refuses to treat this as a ready workspace."
            ),
            launch_command=observation.command,
            exit_code=observation.exit_code,
            termination=observation.termination,
            startup_observed=False,
            workspace_build_path=workspace_build_path,
        )

    control_payload = _write_control_result(
        layout,
        request=request,
        launched_at=launched_at_value,
        control_state="launch_probe_succeeded",
        failure_state=None,
        failure_message=None,
        startup_observed=True,
        launch_command=observation.command,
        exit_code=observation.exit_code,
        termination=observation.termination,
        workspace_build_path=workspace_build_path,
    )
    _write_control_manifest(layout, request=request, launched_at=launched_at_value)

    return PoBLiveControlResult(
        run_id=request.run_id,
        build_id=request.build_id,
        supported_path=LIVE_CONTROL_SUPPORTED_PATH,
        run_root=layout.run_root,
        manifest_path=layout.run_manifest_path,
        control_result_path=layout.control_result_path,
        runtime_snapshot_path=layout.pob_runtime_path,
        workspace_dir=layout.workspace_dir,
        settings_path=layout.settings_path,
        workspace_build_path=workspace_build_path,
        stdout_log_path=layout.stdout_log_path,
        stderr_log_path=layout.stderr_log_path,
        control_result=control_payload,
    )


__all__ = [
    "DEFAULT_LAUNCHER_RELATIVE_PATH",
    "DEFAULT_SHUTDOWN_TIMEOUT_SECONDS",
    "DEFAULT_STARTUP_WINDOW_SECONDS",
    "LIVE_CONTROL_SUPPORTED_PATH",
    "LiveControlContractError",
    "PoBBuildFileInput",
    "PoBLiveControlRequest",
    "PoBLiveControlResult",
    "run_live_control",
]
