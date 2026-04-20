from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise RuntimeError(f"Failed to load JSON from {path}: {exc}") from exc


def validate_workflow(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    data = load_json(path)
    if not isinstance(data, dict):
        return [f"{path}: top-level JSON must be an object"], warnings

    nodes = data.get("nodes")
    connections = data.get("connections")

    if not isinstance(nodes, list):
        errors.append(f"{path}: `nodes` must be a list")
        return errors, warnings

    if not isinstance(connections, dict):
        errors.append(f"{path}: `connections` must be an object")
        return errors, warnings

    node_names: dict[str, dict[str, Any]] = {}
    node_ids: set[str] = set()
    inbound: dict[str, int] = {}
    outbound: dict[str, int] = {}

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"{path}: node at index {index} is not an object")
            continue

        name = node.get("name")
        node_id = node.get("id")
        node_type = node.get("type")

        if not isinstance(name, str) or not name.strip():
            errors.append(f"{path}: node at index {index} has missing/invalid `name`")
            continue

        if name in node_names:
            errors.append(f"{path}: duplicate node name `{name}`")
        else:
            node_names[name] = node
            inbound[name] = 0
            outbound[name] = 0

        if not isinstance(node_id, str) or not node_id.strip():
            errors.append(f"{path}: node `{name}` has missing/invalid `id`")
        elif node_id in node_ids:
            errors.append(f"{path}: duplicate node id `{node_id}`")
        else:
            node_ids.add(node_id)

        if not isinstance(node_type, str) or not node_type.strip():
            errors.append(f"{path}: node `{name}` has missing/invalid `type`")

        if "credentials" in node:
            warnings.append(f"{path}: node `{name}` contains `credentials`; verify nothing sensitive is being shared")

    for source_name, source_connections in connections.items():
        if source_name not in node_names:
            errors.append(f"{path}: `connections` references missing source node `{source_name}`")
            continue

        if not isinstance(source_connections, dict):
            errors.append(f"{path}: connection block for `{source_name}` must be an object")
            continue

        for connection_type, outputs in source_connections.items():
            if not isinstance(outputs, list):
                errors.append(f"{path}: connection list for `{source_name}`/{connection_type} must be a list")
                continue

            for output_index, branch in enumerate(outputs):
                if not isinstance(branch, list):
                    errors.append(
                        f"{path}: branch `{source_name}`/{connection_type}[{output_index}] must be a list"
                    )
                    continue

                for edge_index, edge in enumerate(branch):
                    if not isinstance(edge, dict):
                        errors.append(
                            f"{path}: edge `{source_name}`/{connection_type}[{output_index}][{edge_index}] must be an object"
                        )
                        continue

                    target_name = edge.get("node")
                    target_type = edge.get("type")
                    target_index = edge.get("index")

                    if target_name not in node_names:
                        errors.append(
                            f"{path}: edge from `{source_name}` points to missing target node `{target_name}`"
                        )
                    else:
                        outbound[source_name] += 1
                        inbound[target_name] += 1

                    if not isinstance(target_type, str):
                        errors.append(
                            f"{path}: edge from `{source_name}` to `{target_name}` has invalid `type`"
                        )

                    if not isinstance(target_index, int):
                        errors.append(
                            f"{path}: edge from `{source_name}` to `{target_name}` has invalid `index`"
                        )

    webhook_nodes = [
        node for node in nodes
        if node.get("type") == "n8n-nodes-base.webhook"
    ]
    respond_nodes = [
        node for node in nodes
        if node.get("type") == "n8n-nodes-base.respondToWebhook"
    ]

    for node in webhook_nodes:
        response_mode = (
            node.get("parameters", {}).get("responseMode")
            if isinstance(node.get("parameters"), dict)
            else None
        )
        if response_mode == "responseNode" and not respond_nodes:
            errors.append(
                f"{path}: webhook `{node.get('name')}` uses `responseNode` but no `Respond to Webhook` node exists"
            )

    if respond_nodes and not webhook_nodes:
        warnings.append(f"{path}: workflow has `Respond to Webhook` node(s) but no `Webhook` trigger")

    for name, node in node_names.items():
        node_type = node.get("type")
        if node_type == "n8n-nodes-base.stickyNote":
            continue
        if inbound.get(name, 0) == 0 and outbound.get(name, 0) == 0 and node_type != "n8n-nodes-base.webhook":
            warnings.append(f"{path}: node `{name}` is isolated")

    return errors, warnings


def iter_targets(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(p for p in path.rglob("*.json") if p.is_file())
    return [path]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate exported n8n workflow JSON files.")
    parser.add_argument("path", help="Path to a workflow JSON file or a directory containing them")
    args = parser.parse_args()

    target = Path(args.path)
    if not target.exists():
        print(f"Path does not exist: {target}", file=sys.stderr)
        return 1

    files = iter_targets(target)
    if not files:
        print("No JSON files found.", file=sys.stderr)
        return 1

    any_errors = False

    for file_path in files:
        errors, warnings = validate_workflow(file_path)
        if errors:
            any_errors = True
            print(f"[FAIL] {file_path}")
            for item in errors:
                print(f"  ERROR: {item}")
        else:
            print(f"[OK]   {file_path}")

        for item in warnings:
            print(f"  WARN: {item}")

    return 1 if any_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

