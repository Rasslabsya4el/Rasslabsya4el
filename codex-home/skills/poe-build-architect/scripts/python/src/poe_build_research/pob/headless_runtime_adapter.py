"""Real pinned headless PoB adapter for the minimal proof loop."""

from __future__ import annotations

import hashlib
import json
import math
import queue
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import PROJECT_ROOT, sha256_file
from .host_runtime import (
    PoBHeadlessHostContractError,
    PoBHeadlessLaunchRequest,
    PoBHeadlessLaunchResult,
    PoBHeadlessSessionHandle,
)
from .release_manager import PoBReleaseManager

_WORKER_READY_TIMEOUT_SECONDS = 30.0
_WORKER_COMMAND_TIMEOUT_SECONDS = 30.0
_WORKER_NODE_POWER_TIMEOUT_SECONDS = 60.0
_WORKER_SHUTDOWN_TIMEOUT_SECONDS = 10.0
_WORKER_MODULE = "poe_build_research.pob.headless_runtime_worker"
_NATIVE_POB_IMPORT_STRING_PROOF_KIND = "pinned_pob_import_tab_import_string"
_NATIVE_POB_IMPORT_STRING_SURFACE_KIND = "pob_import_ui_import_code"
POB_HEADLESS_NODE_POWER_REPORT_SCHEMA_VERSION = "1.0.0"
POB_HEADLESS_NODE_POWER_REPORT_RECORD_KIND = "pob_headless_node_power_report"
POB_NATIVE_NODE_POWER_REPORT_SOURCE_KIND = "pob_native_node_power_report"
POB_NATIVE_NODE_POWER_REPORT_SUPPORTED_PATH = "pob_native_node_power_report_hint_v1"
_NODE_POWER_REPORT_STATUSES = {"accepted", "unavailable"}
_FORBIDDEN_NODE_POWER_PAYLOAD_FIELDS = {
    "Direct" "BuildOutput",
    "direct_build_output",
    "ready_import",
    "ready_" "pob_import",
    "pob_code",
    "pob" "code",
    "pob" "code_txt",
    "xml",
    "path_of_building_xml",
    "public_url",
}


@dataclass(frozen=True, slots=True)
class PoBHeadlessSessionShutdown:
    """Observed session shutdown boundary for one headless worker."""

    exit_code: int
    termination: str
    process_exit_observed: bool = True


@dataclass(slots=True)
class _WorkerProcess:
    process: subprocess.Popen[str]
    request: PoBHeadlessLaunchRequest


def _fail(failure_state: str, message: str) -> None:
    raise PoBHeadlessHostContractError(failure_state, message)


def _normalize_unified_state_payload(raw_state: Any, *, failure_state: str) -> dict[str, Any]:
    if not isinstance(raw_state, dict):
        _fail(failure_state, "Headless PoB worker returned a non-object unified state payload.")
    state = dict(raw_state)
    identity_state = state.get("identity_state")
    items_state = state.get("items_state")
    gear_slots = state.get("gear_slots")
    if items_state is None:
        items_state = gear_slots
    if gear_slots is None:
        gear_slots = items_state
    tree_state = state.get("tree_state")
    skills_state = state.get("skills_state")
    config_state = state.get("config_state")
    if identity_state is not None and not isinstance(identity_state, dict):
        _fail(failure_state, "Headless PoB worker returned an invalid identity_state payload.")
    if not isinstance(items_state, dict) or not isinstance(gear_slots, dict):
        _fail(failure_state, "Headless PoB worker must expose repo-owned items_state and gear_slots objects.")
    if not isinstance(tree_state, dict) or not isinstance(skills_state, dict) or not isinstance(config_state, dict):
        _fail(failure_state, "Headless PoB worker returned an invalid unified state payload.")
    if isinstance(identity_state, dict):
        state["identity_state"] = dict(identity_state)
    state["items_state"] = dict(items_state)
    state["gear_slots"] = dict(gear_slots)
    return state


def _legacy_minimal_state_payload(raw_state: Any, *, failure_state: str) -> dict[str, Any]:
    state = _normalize_unified_state_payload(raw_state, failure_state=failure_state)
    state.pop("items_state", None)
    state.pop("state_contract_version", None)
    return state


def _readline_with_timeout(handle: Any, timeout_seconds: float) -> str:
    output: queue.Queue[str] = queue.Queue(maxsize=1)

    def _reader() -> None:
        try:
            line = handle.readline()
        except Exception:
            line = ""
        output.put(line)

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()
    try:
        return output.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        raise PoBHeadlessHostContractError(
            "runtime_protocol_timeout",
            "Timed out waiting for the headless PoB worker protocol.",
        ) from exc


def _parse_worker_message(raw_line: str, *, failure_state: str) -> dict[str, Any]:
    stripped = raw_line.strip()
    if not stripped:
        _fail(failure_state, "Headless PoB worker returned an empty protocol message.")
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        _fail(failure_state, f"Headless PoB worker returned invalid JSON: {stripped}")
        raise AssertionError from exc
    if not isinstance(payload, dict):
        _fail(failure_state, "Headless PoB worker returned a non-object protocol message.")
    return payload


class PinnedPoBHeadlessRuntimeAdapter:
    """Proof-loop adapter backed by a real pinned PoB worker process."""

    def __init__(
        self,
        *,
        release_manager: PoBReleaseManager | None = None,
        python_executable: str | None = None,
    ) -> None:
        self._release_manager = release_manager or PoBReleaseManager()
        self._python_executable = python_executable or sys.executable
        self._workers: dict[str, _WorkerProcess] = {}

    def launch_session(self, request: PoBHeadlessLaunchRequest) -> PoBHeadlessLaunchResult:
        runtime_root = self._resolve_runtime_root(request)
        wrapper_path = self._resolve_wrapper_path(request.wrapper_entrypoint_ref)
        self._validate_wrapper_path(wrapper_path)

        command = (
            self._python_executable,
            "-m",
            _WORKER_MODULE,
            "--runtime-root",
            str(runtime_root),
            "--session-root",
            str(request.session_root),
            "--wrapper-path",
            str(wrapper_path),
            "--session-role",
            request.session_role,
        )
        if request.reopen_source_locator is not None:
            command = command + ("--reopen-source", str(request.reopen_source_locator))

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = subprocess.Popen(
                command,
                cwd=request.session_root,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
        except OSError as exc:
            _fail("runtime_launch_failed", f"Could not start the headless PoB worker: {exc}")
            raise AssertionError from exc

        try:
            raw_ready = _readline_with_timeout(process.stdout, _WORKER_READY_TIMEOUT_SECONDS)
            ready_payload = _parse_worker_message(raw_ready, failure_state="runtime_protocol_failed")
            if ready_payload.get("status") != "ready":
                failure_state = str(ready_payload.get("failure_state") or "runtime_launch_failed")
                message = str(ready_payload.get("message") or "Headless PoB worker failed to start.")
                _fail(failure_state, message)
        except Exception:
            self._terminate_process(process)
            raise

        self._workers[request.process_instance_id] = _WorkerProcess(process=process, request=request)
        dependency_fingerprints = {
            "lua51_dll_sha256": sha256_file(runtime_root / "lua51.dll"),
            "headless_wrapper_sha256": sha256_file(wrapper_path),
            "runtime_manifest_sha256": sha256_file(runtime_root / "manifest.xml"),
        }
        return PoBHeadlessLaunchResult(
            os_pid=process.pid,
            command=command,
            cwd=request.session_root,
            dependency_fingerprints=dependency_fingerprints,
        )

    def create_blank_build(self, handle: PoBHeadlessSessionHandle) -> None:
        self._call_worker(handle, {"action": "create_blank_build"})

    def apply_identity_state(self, handle: PoBHeadlessSessionHandle, identity_payload: dict[str, Any]) -> None:
        self._call_worker(handle, {"action": "apply_identity_state", "identity_payload": dict(identity_payload)})

    def apply_tree_state(self, handle: PoBHeadlessSessionHandle, tree_payload: dict[str, Any]) -> None:
        self._call_worker(handle, {"action": "apply_tree_state", "tree_payload": dict(tree_payload)})

    def apply_item_state(self, handle: PoBHeadlessSessionHandle, item_payload: dict[str, Any]) -> None:
        self._call_worker(handle, {"action": "apply_item_state", "item_payload": dict(item_payload)})

    def apply_skill_state(self, handle: PoBHeadlessSessionHandle, skill_payload: dict[str, Any]) -> None:
        self._call_worker(handle, {"action": "apply_skill_state", "skill_payload": dict(skill_payload)})

    def apply_config_state(self, handle: PoBHeadlessSessionHandle, config_payload: dict[str, Any]) -> None:
        self._call_worker(handle, {"action": "apply_config_state", "config_payload": dict(config_payload)})

    def read_state(self, handle: PoBHeadlessSessionHandle) -> dict[str, Any]:
        return _normalize_unified_state_payload(
            self._worker_result(self._call_worker(handle, {"action": "read_state"})),
            failure_state="runtime_protocol_failed",
        )

    def read_blank_state(self, handle: PoBHeadlessSessionHandle) -> dict[str, Any]:
        return _legacy_minimal_state_payload(
            self._worker_result(self._call_worker(handle, {"action": "read_state"})),
            failure_state="runtime_protocol_failed",
        )

    def read_calc_snapshot(self, handle: PoBHeadlessSessionHandle) -> dict[str, Any]:
        return self._worker_result(
            self._call_worker(handle, {"action": "read_calc_snapshot"})
        )

    def read_node_power_report(
        self,
        handle: PoBHeadlessSessionHandle,
        node_power_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request = dict(node_power_request or {})
        return _native_node_power_report_result(
            self._worker_result(
                self._call_worker(
                    handle,
                    {"action": "read_node_power_report", "node_power_request": request},
                    timeout_seconds=_WORKER_NODE_POWER_TIMEOUT_SECONDS,
                )
            )
        )

    def read_ascendancy_node_report(self, handle: PoBHeadlessSessionHandle) -> dict[str, Any]:
        return self._worker_result(self._call_worker(handle, {"action": "read_ascendancy_node_report"}))

    def equip_item(
        self,
        handle: PoBHeadlessSessionHandle,
        prepared_item_ref: str,
        normalized_item: dict[str, Any],
    ) -> None:
        # The accepted proof slice has exactly one item contract. The worker
        # materializes the pinned PoB-valid raw item text that normalizes back
        # to the prepared proof payload.
        if normalized_item.get("slot") != "Boots":
            _fail("invalid_boots_item", "The real headless adapter only supports the accepted Boots proof item.")
        self._call_worker(handle, {"action": "equip_boots_item", "prepared_item_ref": prepared_item_ref})

    def read_equipped_state(self, handle: PoBHeadlessSessionHandle) -> dict[str, Any]:
        return _legacy_minimal_state_payload(
            self._worker_result(self._call_worker(handle, {"action": "read_state"})),
            failure_state="runtime_protocol_failed",
        )

    def export_build_artifact(self, handle: PoBHeadlessSessionHandle) -> str:
        payload = self._call_worker(handle, {"action": "export_build_xml"})
        result = payload.get("result")
        if not isinstance(result, str) or not result.strip():
            _fail("missing_export_payload", "Headless PoB worker did not return a non-empty XML export.")
        return result

    def verify_pob_import_code_string(self, handle: PoBHeadlessSessionHandle, import_code: str) -> dict[str, Any]:
        if not isinstance(import_code, str):
            _fail("runtime_protocol_failed", "import_code must be a string.")
        return _native_import_code_string_result(
            self._worker_result(
                self._call_worker(
                    handle,
                    {"action": "verify_pob_import_code_string", "import_code": import_code},
                )
            ),
            import_code=import_code,
        )

    def read_reopened_state(self, handle: PoBHeadlessSessionHandle) -> dict[str, Any]:
        return _normalize_unified_state_payload(self.read_state(handle), failure_state="runtime_protocol_failed")

    def shutdown_session(self, handle: PoBHeadlessSessionHandle) -> PoBHeadlessSessionShutdown:
        worker = self._require_worker(handle)
        if worker.process.poll() is None:
            try:
                payload = self._call_worker(handle, {"action": "shutdown"}, timeout_seconds=_WORKER_SHUTDOWN_TIMEOUT_SECONDS)
                termination = str(payload.get("termination") or "process_exit_observed")
                worker.process.wait(timeout=_WORKER_SHUTDOWN_TIMEOUT_SECONDS)
                exit_code = worker.process.returncode if worker.process.returncode is not None else 0
                return PoBHeadlessSessionShutdown(exit_code=exit_code, termination=termination)
            except Exception:
                self._terminate_process(worker.process)
                raise
            finally:
                self._workers.pop(handle.process_instance_id, None)

        exit_code = worker.process.returncode if worker.process.returncode is not None else 0
        self._workers.pop(handle.process_instance_id, None)
        return PoBHeadlessSessionShutdown(exit_code=exit_code, termination="process_exit_observed")

    def close(self) -> None:
        for process_instance_id in list(self._workers):
            worker = self._workers.pop(process_instance_id)
            self._terminate_process(worker.process)

    def _resolve_runtime_root(self, request: PoBHeadlessLaunchRequest) -> Path:
        fetch_report = self._release_manager.fetch()
        verify_report = self._release_manager.verify()
        lock_fingerprint = sha256_file(self._release_manager.lock_path)

        if request.pinned_pob_release_ref.lock_fingerprint != lock_fingerprint:
            _fail(
                "runtime_dependency_mismatch",
                "Pinned PoB lock fingerprint drifted away from the launch request receipt.",
            )
        if request.pinned_pob_release_ref.tag != verify_report.tag:
            _fail(
                "runtime_dependency_mismatch",
                "Pinned PoB tag drifted away from the launch request receipt.",
            )

        runtime_root = fetch_report.extract_dir.resolve(strict=False)
        required_paths = (
            runtime_root / "lua51.dll",
            runtime_root / "Launch.lua",
            runtime_root / "manifest.xml",
        )
        missing = [str(path) for path in required_paths if not path.is_file()]
        if missing or not verify_report.extracted_runtime_present:
            _fail(
                "runtime_dependency_missing",
                "Pinned PoB runtime is not fully materialized for headless launch: " + ", ".join(missing),
            )
        return runtime_root

    def _resolve_wrapper_path(self, wrapper_entrypoint_ref: str) -> Path:
        candidate = Path(wrapper_entrypoint_ref)
        if candidate.is_absolute():
            return candidate.resolve(strict=False)
        return (PROJECT_ROOT / candidate).resolve(strict=False)

    def _validate_wrapper_path(self, wrapper_path: Path) -> None:
        if not wrapper_path.is_file():
            _fail("runtime_entrypoint_missing", f"Headless wrapper entrypoint is missing: {wrapper_path}")

    def _require_worker(self, handle: PoBHeadlessSessionHandle) -> _WorkerProcess:
        worker = self._workers.get(handle.process_instance_id)
        if worker is None:
            _fail("unknown_session", f"No live headless PoB worker exists for {handle.process_instance_id}.")
        return worker

    def _call_worker(
        self,
        handle: PoBHeadlessSessionHandle,
        payload: dict[str, Any],
        *,
        timeout_seconds: float = _WORKER_COMMAND_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        worker = self._require_worker(handle)
        if worker.process.poll() is not None:
            _fail(
                "runtime_exited_early",
                f"Headless PoB worker exited before action {payload.get('action')!r} could complete.",
            )
        if worker.process.stdin is None or worker.process.stdout is None:
            _fail("runtime_protocol_failed", "Headless PoB worker pipes are not available.")

        worker.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        worker.process.stdin.flush()
        raw_response = _readline_with_timeout(worker.process.stdout, timeout_seconds)
        response = _parse_worker_message(raw_response, failure_state="runtime_protocol_failed")
        if response.get("ok") is not True:
            failure_state = str(response.get("failure_state") or "runtime_protocol_failed")
            message = str(response.get("message") or "Headless PoB worker returned an error.")
            _fail(failure_state, message)
        return response

    def _worker_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = payload.get("result")
        if not isinstance(result, dict):
            _fail("runtime_protocol_failed", "Headless PoB worker did not return an object state payload.")
        return result

    def _terminate_process(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=_WORKER_SHUTDOWN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=_WORKER_SHUTDOWN_TIMEOUT_SECONDS)


class PoBHeadlessCallbackRuntimeAdapter:
    """Compatibility adapter for the explicit callback harness used in tests."""

    def __init__(self, callbacks: Any) -> None:
        self._callbacks = callbacks

    def launch_session(self, request: PoBHeadlessLaunchRequest) -> PoBHeadlessLaunchResult:
        return self._callbacks.launcher(request)

    def create_blank_build(self, handle: PoBHeadlessSessionHandle) -> None:
        self._callbacks.create_blank_build(handle)

    def apply_identity_state(self, handle: PoBHeadlessSessionHandle, identity_payload: dict[str, Any]) -> None:
        callback = getattr(self._callbacks, "apply_identity_state", None)
        if callback is None:
            _fail("runtime_protocol_failed", "Callback runtime does not implement apply_identity_state.")
        callback(handle, identity_payload)

    def apply_tree_state(self, handle: PoBHeadlessSessionHandle, tree_payload: dict[str, Any]) -> None:
        callback = getattr(self._callbacks, "apply_tree_state", None)
        if callback is None:
            _fail("runtime_protocol_failed", "Callback runtime does not implement apply_tree_state.")
        callback(handle, tree_payload)

    def apply_item_state(self, handle: PoBHeadlessSessionHandle, item_payload: dict[str, Any]) -> None:
        callback = getattr(self._callbacks, "apply_item_state", None)
        if callback is None:
            _fail("runtime_protocol_failed", "Callback runtime does not implement apply_item_state.")
        callback(handle, item_payload)

    def apply_skill_state(self, handle: PoBHeadlessSessionHandle, skill_payload: dict[str, Any]) -> None:
        callback = getattr(self._callbacks, "apply_skill_state", None)
        if callback is None:
            _fail("runtime_protocol_failed", "Callback runtime does not implement apply_skill_state.")
        callback(handle, skill_payload)

    def apply_config_state(self, handle: PoBHeadlessSessionHandle, config_payload: dict[str, Any]) -> None:
        callback = getattr(self._callbacks, "apply_config_state", None)
        if callback is None:
            _fail("runtime_protocol_failed", "Callback runtime does not implement apply_config_state.")
        callback(handle, config_payload)

    def read_state(self, handle: PoBHeadlessSessionHandle) -> dict[str, Any]:
        callback = getattr(self._callbacks, "read_state", None)
        if callback is not None:
            return _normalize_unified_state_payload(callback(handle), failure_state="runtime_protocol_failed")
        return _normalize_unified_state_payload(
            self._callbacks.read_equipped_state(handle),
            failure_state="runtime_protocol_failed",
        )

    def read_blank_state(self, handle: PoBHeadlessSessionHandle) -> dict[str, Any]:
        return _legacy_minimal_state_payload(
            self._callbacks.read_blank_state(handle),
            failure_state="runtime_protocol_failed",
        )

    def read_calc_snapshot(self, handle: PoBHeadlessSessionHandle) -> dict[str, Any]:
        callback = getattr(self._callbacks, "read_calc_snapshot", None)
        if callback is None:
            _fail("runtime_protocol_failed", "Callback runtime does not implement read_calc_snapshot.")
        result = callback(handle)
        if not isinstance(result, dict):
            _fail("runtime_protocol_failed", "Callback runtime read_calc_snapshot must return an object payload.")
        return dict(result)

    def read_node_power_report(
        self,
        handle: PoBHeadlessSessionHandle,
        node_power_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        callback = getattr(self._callbacks, "read_node_power_report", None)
        if callback is None:
            _fail("runtime_protocol_failed", "Callback runtime does not implement read_node_power_report.")
        return _native_node_power_report_result(callback(handle, dict(node_power_request or {})))

    def read_ascendancy_node_report(self, handle: PoBHeadlessSessionHandle) -> dict[str, Any]:
        callback = getattr(self._callbacks, "read_ascendancy_node_report", None)
        if callback is None:
            _fail("runtime_protocol_failed", "Callback runtime does not implement read_ascendancy_node_report.")
        result = callback(handle)
        if not isinstance(result, dict):
            _fail("runtime_protocol_failed", "Callback runtime read_ascendancy_node_report must return an object payload.")
        return dict(result)

    def equip_item(
        self,
        handle: PoBHeadlessSessionHandle,
        prepared_item_ref: str,
        normalized_item: dict[str, Any],
    ) -> None:
        self._callbacks.equip_item(handle, prepared_item_ref, normalized_item)

    def read_equipped_state(self, handle: PoBHeadlessSessionHandle) -> dict[str, Any]:
        return _legacy_minimal_state_payload(
            self._callbacks.read_equipped_state(handle),
            failure_state="runtime_protocol_failed",
        )

    def export_build_artifact(self, handle: PoBHeadlessSessionHandle) -> str | bytes:
        return self._callbacks.export_build_artifact(handle)

    def verify_pob_import_code_string(self, handle: PoBHeadlessSessionHandle, import_code: str) -> dict[str, Any]:
        return _native_import_code_string_result(
            self._callbacks.verify_pob_import_code_string(handle, import_code),
            import_code=import_code,
        )

    def read_reopened_state(self, handle: PoBHeadlessSessionHandle) -> Any:
        result = self._callbacks.read_reopened_state(handle)
        if isinstance(result, dict):
            return _normalize_unified_state_payload(result, failure_state="runtime_protocol_failed")
        return result

    def shutdown_session(self, handle: PoBHeadlessSessionHandle) -> PoBHeadlessSessionShutdown:
        return PoBHeadlessSessionShutdown(exit_code=0, termination="process_exit_observed")

    def close(self) -> None:
        return None


__all__ = [
    "POB_HEADLESS_NODE_POWER_REPORT_RECORD_KIND",
    "POB_HEADLESS_NODE_POWER_REPORT_SCHEMA_VERSION",
    "POB_NATIVE_NODE_POWER_REPORT_SOURCE_KIND",
    "POB_NATIVE_NODE_POWER_REPORT_SUPPORTED_PATH",
    "PinnedPoBHeadlessRuntimeAdapter",
    "PoBHeadlessCallbackRuntimeAdapter",
    "PoBHeadlessSessionShutdown",
]


def _native_node_power_report_result(raw_result: Any) -> dict[str, Any]:
    if not isinstance(raw_result, dict):
        _fail("runtime_protocol_failed", "Native node-power report result must be an object.")
    result = dict(raw_result)
    forbidden = sorted(field for field in _FORBIDDEN_NODE_POWER_PAYLOAD_FIELDS if field in result)
    if forbidden:
        _fail(
            "publication_boundary_failed",
            "Native node-power report result must not carry publication payload field(s): " + ", ".join(forbidden),
        )

    result.setdefault("schema_version", POB_HEADLESS_NODE_POWER_REPORT_SCHEMA_VERSION)
    result.setdefault("record_kind", POB_HEADLESS_NODE_POWER_REPORT_RECORD_KIND)
    result.setdefault("source_kind", POB_NATIVE_NODE_POWER_REPORT_SOURCE_KIND)
    result.setdefault("supported_path", POB_NATIVE_NODE_POWER_REPORT_SUPPORTED_PATH)
    if result.get("schema_version") != POB_HEADLESS_NODE_POWER_REPORT_SCHEMA_VERSION:
        _fail("runtime_protocol_failed", "Native node-power report schema_version is unsupported.")
    if result.get("record_kind") != POB_HEADLESS_NODE_POWER_REPORT_RECORD_KIND:
        _fail("runtime_protocol_failed", "Native node-power report record_kind is unsupported.")
    if result.get("source_kind") != POB_NATIVE_NODE_POWER_REPORT_SOURCE_KIND:
        _fail("runtime_protocol_failed", "Native node-power report source_kind is unsupported.")
    if result.get("supported_path") != POB_NATIVE_NODE_POWER_REPORT_SUPPORTED_PATH:
        _fail("runtime_protocol_failed", "Native node-power report supported_path is unsupported.")

    status = _string_value(result.get("status"))
    if status not in _NODE_POWER_REPORT_STATUSES:
        _fail("runtime_protocol_failed", "Native node-power report status must be accepted or unavailable.")
    rows = result.get("rows")
    if not isinstance(rows, list):
        _fail("runtime_protocol_failed", "Native node-power report rows must be an array.")
    normalized_rows = [_normalize_node_power_row(row, index=index) for index, row in enumerate(rows)]
    result["rows"] = normalized_rows
    result["row_count"] = len(normalized_rows)

    selected_metric = result.get("selected_metric")
    if not isinstance(selected_metric, dict):
        _fail("runtime_protocol_failed", "Native node-power report selected_metric must be an object.")
    metric_name = _string_value(selected_metric.get("stat"))
    if not metric_name and status == "accepted":
        _fail("runtime_protocol_failed", "Accepted native node-power report selected_metric.stat must be non-empty.")
    if not isinstance(result.get("source_refs"), list) or not result["source_refs"]:
        _fail("runtime_protocol_failed", "Native node-power report must include source_refs.")
    result["source_refs"] = [_normalize_proof_ref(ref, field_name="source_refs[]") for ref in result["source_refs"]]
    result["limitations"] = _string_list(result.get("limitations"))
    result["unavailable_metrics"] = _string_list(result.get("unavailable_metrics"))
    if status == "unavailable" and not result["limitations"]:
        _fail("runtime_protocol_failed", "Unavailable native node-power report must include limitations.")
    return result


def _normalize_node_power_row(row: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(row, dict):
        _fail("runtime_protocol_failed", "Native node-power report rows must be objects.")
    item = dict(row)
    required = ("row_id", "source_id", "node_name", "target_kind", "metric_lane", "metric_name", "metric_label", "source_locator")
    missing = [field for field in required if not _string_value(item.get(field))]
    if missing:
        _fail("runtime_protocol_failed", "Native node-power report row is missing field(s): " + ", ".join(missing))
    if _optional_int(item.get("node_id")) is None:
        _fail("runtime_protocol_failed", "Native node-power report row.node_id must be an integer.")
    if _optional_float(item.get("node_power_score")) is None:
        _fail("runtime_protocol_failed", "Native node-power report row.node_power_score must be numeric.")
    path_power = _optional_float(item.get("path_power_score"))
    if path_power is None and item.get("path_power_score") is not None:
        _fail("runtime_protocol_failed", "Native node-power report row.path_power_score must be numeric or null.")
    item["row_index"] = index
    item["node_id"] = int(item["node_id"])
    item["node_power_score"] = float(item["node_power_score"])
    item["path_power_score"] = path_power
    item["stats_or_supporting_text"] = _string_list(item.get("stats_or_supporting_text"))
    item["metric_tags"] = _string_list(item.get("metric_tags"))
    item["facets"] = item.get("facets") if isinstance(item.get("facets"), list) else []
    item["matched_branch_axes"] = item.get("matched_branch_axes") if isinstance(item.get("matched_branch_axes"), list) else []
    if not isinstance(item.get("source_context"), dict):
        item["source_context"] = {}
    return item


def _normalize_proof_ref(value: Any, *, field_name: str) -> dict[str, str]:
    if not isinstance(value, dict):
        _fail("runtime_protocol_failed", f"{field_name} must be an object.")
    ref = {
        "ref_id": _string_value(value.get("ref_id")),
        "ref_kind": _string_value(value.get("ref_kind")),
        "locator": _string_value(value.get("locator")),
        "json_pointer": _string_value(value.get("json_pointer")),
        "summary": _string_value(value.get("summary")),
    }
    missing = [key for key, current in ref.items() if not current]
    if missing:
        _fail("runtime_protocol_failed", f"{field_name} is missing field(s): " + ", ".join(missing))
    return ref


def _native_import_code_string_result(raw_result: Any, *, import_code: str) -> dict[str, Any]:
    if not isinstance(raw_result, dict):
        _fail("runtime_protocol_failed", "Native import-code verifier result must be an object.")
    if not isinstance(import_code, str):
        _fail("runtime_protocol_failed", "import_code must be a string.")
    result = dict(raw_result)
    result.pop("import_code", None)
    result.pop("payload", None)
    result.pop("literal_payload", None)
    import_code_valid = result.get("import_code_valid") is True
    native_semantics_valid = result.get("native_pob_import_string_semantics_valid") is True
    accepted = import_code_valid and native_semantics_valid and _string_value(result.get("status")) == "accepted"
    missing_inputs = _string_list(result.get("missing_inputs"))
    invalid_reasons = _string_list(result.get("invalid_reasons"))
    if not accepted and not invalid_reasons and not missing_inputs:
        invalid_reasons = ["native_import_code_invalid"]
    return {
        "status": "accepted" if accepted else "invalid",
        "payload_sha256": hashlib.sha256(import_code.encode("utf-8")).hexdigest(),
        "proof_kind": _NATIVE_POB_IMPORT_STRING_PROOF_KIND,
        "surface_kind": _NATIVE_POB_IMPORT_STRING_SURFACE_KIND,
        "import_code_valid": import_code_valid,
        "native_pob_import_string_semantics_valid": native_semantics_valid,
        "import_code_detail": _string_value(result.get("import_code_detail")),
        "decoded_xml_char_count": _int_or_zero(result.get("decoded_xml_char_count")),
        "imported_build_active": result.get("imported_build_active") is True,
        "missing_inputs": missing_inputs,
        "invalid_reasons": [] if accepted else invalid_reasons,
    }


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _int_or_zero(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    return None
