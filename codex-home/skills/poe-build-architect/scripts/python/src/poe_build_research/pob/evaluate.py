"""Fixture-oriented scripted Path of Building evaluation and artifact emission."""

from __future__ import annotations

import json
import math
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from string import Formatter
from typing import Any

from .artifacts import (
    DEFAULT_RUNS_ROOT,
    PoBRunLayout,
    build_manifest,
    prepare_run_layout,
    sha256_file,
    validate_token,
    write_json,
    write_text,
)
from .release_manager import PoBReleaseManager, utc_now_iso


class EvaluationContractError(RuntimeError):
    """Raised when the scripted evaluation contract cannot be satisfied."""


def _placeholder_names(template: str) -> set[str]:
    formatter = Formatter()
    return {field_name for _, field_name, _, _ in formatter.parse(template) if field_name}


def _render_template(template: str, values: dict[str, str], field_name: str) -> str:
    placeholders = _placeholder_names(template)
    missing = sorted(placeholders - values.keys())
    if missing:
        raise EvaluationContractError(
            f"{field_name} references unsupported placeholders: {', '.join(missing)}"
        )
    return template.format_map(values)


def _normalize_metric_map(payload: Any, field_name: str) -> dict[str, float]:
    if not isinstance(payload, dict) or not payload:
        raise EvaluationContractError(f"{field_name} must be a non-empty object of numeric metrics.")

    normalized: dict[str, float] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not key.strip():
            raise EvaluationContractError(f"{field_name} metric keys must be non-empty strings.")
        if isinstance(value, bool):
            raise EvaluationContractError(f"{field_name}.{key} must be numeric, not boolean.")
        if isinstance(value, (int, float)):
            normalized_value = float(value)
        elif isinstance(value, str):
            try:
                normalized_value = float(value)
            except ValueError as exc:
                raise EvaluationContractError(f"{field_name}.{key} must be parseable as a number.") from exc
        else:
            raise EvaluationContractError(f"{field_name}.{key} must be numeric or a numeric string.")

        if not math.isfinite(normalized_value):
            raise EvaluationContractError(f"{field_name}.{key} must be a finite number.")

        normalized[key] = normalized_value
    return dict(sorted(normalized.items()))


def _normalize_warnings(payload: Any) -> list[str]:
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise EvaluationContractError("warnings must be a JSON array when provided.")
    warnings: list[str] = []
    for entry in payload:
        if not isinstance(entry, str) or not entry.strip():
            raise EvaluationContractError("warnings entries must be non-empty strings.")
        warnings.append(entry)
    return warnings


@dataclass(frozen=True, slots=True)
class ScriptedRuntimeSpec:
    """Structured command template for fixture-only scripted PoB paths."""

    supported_path: str
    command: tuple[str, ...]
    environment: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.supported_path.strip():
            raise EvaluationContractError("supported_path must be a non-empty string.")
        if not self.command:
            raise EvaluationContractError("command must contain at least one template element.")

    def render(self, values: dict[str, str]) -> tuple[list[str], dict[str, str]]:
        rendered_command = [
            _render_template(template, values, "command")
            for template in self.command
        ]
        rendered_environment = {
            key: _render_template(value, values, f"environment[{key}]")
            for key, value in sorted(self.environment.items())
        }
        return rendered_command, rendered_environment


@dataclass(frozen=True, slots=True)
class PoBEvaluationRequest:
    """Inputs required to evaluate one build through the pinned PoB runtime."""

    run_id: str
    build_id: str
    build_payload: dict[str, Any]
    runtime: ScriptedRuntimeSpec
    build_source: str = "fixture"
    build_filename: str = "build.json"
    rule_context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_token(self.run_id, "run_id")
        if not self.build_id.strip():
            raise EvaluationContractError("build_id must be a non-empty string.")
        validate_token(self.build_filename, "build_filename")
        if not isinstance(self.build_payload, dict) or not self.build_payload:
            raise EvaluationContractError("build_payload must be a non-empty JSON object.")
        if not isinstance(self.rule_context, dict):
            raise EvaluationContractError("rule_context must be a JSON object.")


@dataclass(frozen=True, slots=True)
class PoBRun:
    """Observed artifact bundle for one PoB evaluation run."""

    run_id: str
    build_id: str
    run_root: Path
    manifest_path: Path
    raw_metrics_path: Path
    normalized_metrics_path: Path
    normalized_metrics: dict[str, Any]


def _read_raw_metrics(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda token: (_ for _ in ()).throw(
                EvaluationContractError(
                    f"metrics_raw.json contains non-finite numeric literal: {token}"
                )
            ),
        )
    except json.JSONDecodeError as exc:
        raise EvaluationContractError(f"metrics_raw.json is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise EvaluationContractError("metrics_raw.json must contain a top-level JSON object.")
    return payload


def _normalize_metrics(
    raw_metrics: dict[str, Any],
    *,
    request: PoBEvaluationRequest,
    layout: PoBRunLayout,
    evaluated_at: str,
    lock_fingerprint: str,
    raw_metrics_fingerprint: str,
    input_fingerprint: str,
    release_payload: dict[str, Any],
) -> dict[str, Any]:
    runtime_metadata = raw_metrics.get("metadata")
    if runtime_metadata is None:
        runtime_metadata = {}
    elif not isinstance(runtime_metadata, dict):
        raise EvaluationContractError("raw metrics metadata must be a JSON object when provided.")

    return {
        "baseline": {
            "metrics": _normalize_metric_map(raw_metrics.get("baseline"), "baseline"),
        },
        "conditional": {
            "metrics": _normalize_metric_map(raw_metrics.get("conditional"), "conditional"),
        },
        "metadata": {
            "run_id": request.run_id,
            "build_id": request.build_id,
            "build_source": request.build_source,
            "evaluated_at": evaluated_at,
            "supported_path": request.runtime.supported_path,
            "input_fingerprint": input_fingerprint,
            "raw_metrics_fingerprint": raw_metrics_fingerprint,
            "runtime_metadata": runtime_metadata,
            "pob_release": {
                "repo": str(release_payload["repo"]),
                "tag": str(release_payload["tag"]),
                "asset_name": str(release_payload["asset_name"]),
                "asset_sha256": str(release_payload["asset_sha256"]),
                "lock_fingerprint": lock_fingerprint,
            },
            "artifact_root": str(layout.run_root),
        },
        "warnings": _normalize_warnings(raw_metrics.get("warnings")),
    }


def evaluate_build(
    request: PoBEvaluationRequest,
    *,
    release_manager: PoBReleaseManager | None = None,
    artifacts_root: Path = DEFAULT_RUNS_ROOT,
    evaluated_at: str | None = None,
) -> PoBRun:
    """Evaluate one build through the pinned PoB runtime and emit the required bundle."""

    manager = release_manager or PoBReleaseManager()
    layout = prepare_run_layout(request.run_id, artifacts_root=artifacts_root)
    build_input_path = layout.build_input_path(request.build_filename)
    evaluated_at_value = evaluated_at or utc_now_iso()

    write_json(build_input_path, request.build_payload)
    write_json(
        layout.input_request_path,
        {
            "run_id": request.run_id,
            "build_id": request.build_id,
            "build_source": request.build_source,
            "build_input_path": layout.relative_path(build_input_path),
            "supported_path": request.runtime.supported_path,
            "evaluated_at": evaluated_at_value,
        },
    )
    write_json(layout.rule_context_path, request.rule_context)

    fetch_report = manager.fetch()
    verify_report = manager.verify()
    release_payload = manager.show_lock()
    lock_fingerprint = sha256_file(manager.lock_path)
    input_fingerprint = sha256_file(build_input_path)

    template_values = {
        "artifact_root": str(layout.run_root),
        "build_id": request.build_id,
        "build_input_path": str(build_input_path),
        "input_request_path": str(layout.input_request_path),
        "raw_metrics_path": str(layout.metrics_raw_path),
        "rule_context_path": str(layout.rule_context_path),
        "run_id": request.run_id,
        "runtime_root": str(fetch_report.extract_dir),
        "workspace_root": str(layout.workspace_dir),
    }
    rendered_command, rendered_environment = request.runtime.render(template_values)
    environment = dict(os.environ)
    environment.update(rendered_environment)

    completed = subprocess.run(
        rendered_command,
        cwd=layout.workspace_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        check=False,
    )
    write_text(layout.stdout_log_path, completed.stdout)
    write_text(layout.stderr_log_path, completed.stderr)

    if completed.returncode != 0:
        raise EvaluationContractError(
            f"Supported path {request.runtime.supported_path} exited with code {completed.returncode}."
        )
    if not layout.metrics_raw_path.exists():
        raise EvaluationContractError(
            f"Supported path {request.runtime.supported_path} did not emit metrics_raw.json."
        )

    try:
        raw_metrics = _read_raw_metrics(layout.metrics_raw_path)
    except EvaluationContractError:
        # Do not preserve a raw artifact that contains invalid JSON numerics.
        layout.metrics_raw_path.unlink(missing_ok=True)
        raise
    raw_metrics_fingerprint = sha256_file(layout.metrics_raw_path)
    normalized_metrics = _normalize_metrics(
        raw_metrics,
        request=request,
        layout=layout,
        evaluated_at=evaluated_at_value,
        lock_fingerprint=lock_fingerprint,
        raw_metrics_fingerprint=raw_metrics_fingerprint,
        input_fingerprint=input_fingerprint,
        release_payload=release_payload,
    )
    write_json(layout.metrics_normalized_path, normalized_metrics)
    write_json(
        layout.pob_runtime_path,
        {
            "repo": release_payload["repo"],
            "tag": release_payload["tag"],
            "asset_name": release_payload["asset_name"],
            "asset_sha256": release_payload["asset_sha256"],
            "lock_path": str(manager.lock_path),
            "lock_fingerprint": lock_fingerprint,
            "archive_path": str(fetch_report.archive_path),
            "extract_dir": str(fetch_report.extract_dir),
            "verified_asset_sha256": verify_report.asset_sha256,
            "verified_asset_size": verify_report.asset_size,
            "runtime_present": verify_report.extracted_runtime_present,
            "supported_path": request.runtime.supported_path,
            "command": rendered_command,
        },
    )
    write_json(
        layout.run_manifest_path,
        build_manifest(
            layout,
            run_id=request.run_id,
            build_id=request.build_id,
            supported_path=request.runtime.supported_path,
            evaluated_at=evaluated_at_value,
        ),
    )

    return PoBRun(
        run_id=request.run_id,
        build_id=request.build_id,
        run_root=layout.run_root,
        manifest_path=layout.run_manifest_path,
        raw_metrics_path=layout.metrics_raw_path,
        normalized_metrics_path=layout.metrics_normalized_path,
        normalized_metrics=normalized_metrics,
    )
