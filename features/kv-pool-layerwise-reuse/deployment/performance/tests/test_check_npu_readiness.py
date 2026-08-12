from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check-npu-readiness.py"
SPEC = importlib.util.spec_from_file_location("check_npu_readiness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
readiness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(readiness)


def node_inventory(physical: int, vnpu: int = 0) -> dict[str, object]:
    return {
        "items": [
            {
                "metadata": {"name": "m1"},
                "status": {
                    "allocatable": {
                        "huawei.com/Ascend910": str(physical),
                        "huawei.com/vnpu-number": str(vnpu),
                    }
                },
            }
        ]
    }


def pod_inventory(
    *requests: int,
    apps: tuple[str | None, ...] = (),
) -> dict[str, object]:
    return {
        "items": [
            {
                "metadata": {
                    "name": f"pod-{index}",
                    "labels": (
                        {"app": apps[index]}
                        if index < len(apps) and apps[index]
                        else {}
                    ),
                },
                "spec": {
                    "nodeName": "m1",
                    "containers": [
                        {
                            "resources": {
                                "requests": {
                                    "huawei.com/Ascend910": str(request),
                                    "huawei.com/vnpu-number": "64",
                                }
                            }
                        }
                    ],
                },
                "status": {"phase": "Running"},
            }
            for index, request in enumerate(requests)
        ]
    }


def test_ready_requires_exactly_eight_physical_and_four_free() -> None:
    report = readiness.evaluate(node_inventory(8, vnpu=64), pod_inventory(2, 2))

    assert report["ready"] is True
    assert report["allocatable"] == 8
    assert report["requested_by_non_terminal_pods"] == 4
    assert report["free"] == 4
    assert report["vnpu_number_ignored"] is True


def test_current_engines_are_replaceable_but_diagnostic_fence_is_not() -> None:
    pods = pod_inventory(
        2,
        2,
        2,
        apps=("prefill", "decode", "decode-failed-npu-isolation"),
    )

    report = readiness.evaluate(node_inventory(8), pods)

    assert report["free"] == 2
    assert report["requested_by_replaceable_engines"] == 4
    assert report["requested_by_other_non_terminal_pods"] == 2
    assert report["available_after_replacing_current_engines"] == 6
    assert report["ready"] is True


def test_vnpu_does_not_substitute_for_missing_physical_resources() -> None:
    report = readiness.evaluate(node_inventory(0, vnpu=64), pod_inventory())

    assert report["ready"] is False
    assert report["allocatable"] == 0
    assert any("must equal 8" in blocker for blocker in report["blockers"])


def test_non_terminal_requests_are_counted_but_terminal_pods_are_ignored() -> None:
    pods = pod_inventory(4)
    pods["items"].append(
        {
            "metadata": {"name": "finished"},
            "spec": {
                "nodeName": "m1",
                "containers": [
                    {"resources": {"requests": {"huawei.com/Ascend910": "8"}}}
                ],
            },
            "status": {"phase": "Succeeded"},
        }
    )

    assert readiness.evaluate(node_inventory(8), pods)["free"] == 4


def test_wrong_node_name_is_blocked() -> None:
    report = readiness.evaluate(node_inventory(8), pod_inventory(), node_name="n1")

    assert report["ready"] is False
    assert report["allocatable"] == 0
    assert "expected exactly one node named n1" in report["blockers"][0]


def test_init_container_and_pod_overhead_follow_scheduler_accounting() -> None:
    pods = {
        "items": [
            {
                "metadata": {"name": "with-init"},
                "spec": {
                    "nodeName": "m1",
                    "containers": [
                        {"resources": {"requests": {"huawei.com/Ascend910": "1"}}},
                        {"resources": {"requests": {"huawei.com/Ascend910": "1"}}},
                    ],
                    "initContainers": [
                        {"resources": {"requests": {"huawei.com/Ascend910": "3"}}}
                    ],
                    "overhead": {"huawei.com/Ascend910": "1"},
                },
                "status": {"phase": "Pending"},
            }
        ]
    }

    report = readiness.evaluate(node_inventory(8), pods)

    assert report["requested_by_non_terminal_pods"] == 4
    assert report["ready"] is True
