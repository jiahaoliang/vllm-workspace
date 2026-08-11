#!/usr/bin/env python3
# ruff: noqa: N999
"""Read-only physical Ascend910 readiness check for the rapid DP1 run."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

RESOURCE = "huawei.com/Ascend910"
TERMINAL_PHASES = {"Succeeded", "Failed"}


def _items(value: dict[str, Any]) -> list[dict[str, Any]]:
    items = value.get("items")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return [value]


def _resource_request(container: dict[str, Any]) -> int:
    resources = container.get("resources", {})
    requests = resources.get("requests", {}) if isinstance(resources, dict) else {}
    return int(requests.get(RESOURCE, 0)) if isinstance(requests, dict) else 0


def _pod_request(pod: dict[str, Any]) -> int:
    spec = pod.get("spec", {})
    if not isinstance(spec, dict):
        return 0
    containers = spec.get("containers", [])
    regular = (
        sum(
            _resource_request(container)
            for container in containers
            if isinstance(container, dict)
        )
        if isinstance(containers, list)
        else 0
    )
    init_containers = spec.get("initContainers", [])
    init = (
        max(
            (
                _resource_request(container)
                for container in init_containers
                if isinstance(container, dict)
            ),
            default=0,
        )
        if isinstance(init_containers, list)
        else 0
    )
    overhead = spec.get("overhead", {})
    overhead_request = (
        int(overhead.get(RESOURCE, 0)) if isinstance(overhead, dict) else 0
    )
    return max(regular, init) + overhead_request


def evaluate(
    nodes: dict[str, Any],
    pods: dict[str, Any],
    node_name: str = "m1",
    expected_allocatable: int = 8,
    required_free: int = 4,
) -> dict[str, Any]:
    matching = [
        node
        for node in _items(nodes)
        if isinstance(node.get("metadata"), dict)
        and node["metadata"].get("name") == node_name
    ]
    blockers: list[str] = []
    if len(matching) != 1:
        allocatable = 0
        blockers.append(
            f"expected exactly one node named {node_name}, got {len(matching)}"
        )
    else:
        status = matching[0].get("status", {})
        capacity = status.get("allocatable", {}) if isinstance(status, dict) else {}
        allocatable = (
            int(capacity.get(RESOURCE, 0)) if isinstance(capacity, dict) else 0
        )
        if allocatable != expected_allocatable:
            blockers.append(
                f"{node_name} allocatable {RESOURCE} must equal "
                f"{expected_allocatable}, got {allocatable}"
            )

    requested = 0
    for pod in _items(pods):
        spec = pod.get("spec", {})
        status = pod.get("status", {})
        if not isinstance(spec, dict) or not isinstance(status, dict):
            continue
        if spec.get("nodeName") != node_name or status.get("phase") in TERMINAL_PHASES:
            continue
        requested += _pod_request(pod)
    free = allocatable - requested
    if free < required_free:
        blockers.append(
            f"{node_name} free {RESOURCE} must be at least {required_free}, got {free}"
        )
    return {
        "schema_version": 1,
        "status": "READY" if not blockers else "BLOCKED",
        "ready": not blockers,
        "node": node_name,
        "resource": RESOURCE,
        "expected_allocatable": expected_allocatable,
        "allocatable": allocatable,
        "requested_by_non_terminal_pods": requested,
        "free": free,
        "required_free": required_free,
        "vnpu_number_ignored": True,
        "blockers": blockers,
    }


def _kubectl_json(*args: str) -> dict[str, Any]:
    result = subprocess.run(
        ("kubectl", *args, "-o", "json"),
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise TypeError("kubectl output is not a JSON object")
    return value


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"inventory is not a JSON object: {path}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default="m1")
    parser.add_argument("--nodes-json", type=Path)
    parser.add_argument("--pods-json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if (args.nodes_json is None) != (args.pods_json is None):
        parser.error("--nodes-json and --pods-json must be provided together")
    if args.nodes_json is None:
        nodes = _kubectl_json("get", "node", args.node)
        pods = _kubectl_json("get", "pods", "--all-namespaces")
    else:
        nodes = _read_json(args.nodes_json)
        pods = _read_json(args.pods_json)
    report = evaluate(nodes, pods, node_name=args.node)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
