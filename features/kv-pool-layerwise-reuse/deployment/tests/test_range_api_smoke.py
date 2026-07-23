from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


RUNNER_PATH = Path(__file__).resolve().parents[1] / "range-api-smoke.py"
SPEC = importlib.util.spec_from_file_location("range_api_smoke", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
range_api_smoke = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = range_api_smoke
SPEC.loader.exec_module(range_api_smoke)


class FakeTensor:
    def __init__(self, pointer: int, data: bytes) -> None:
        self.pointer = pointer
        self.data = bytearray(data)

    def data_ptr(self) -> int:
        return self.pointer

    def numel(self) -> int:
        return len(self.data)

    def element_size(self) -> int:
        return 1


class FakeRuntime:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.tensors: list[FakeTensor] = []
        self.source_pattern = b""

    def set_device(self, logical_device: int) -> None:
        assert logical_device == 0
        self.events.append("set_device")

    def source_tensor(self, pattern: bytes) -> FakeTensor:
        self.source_pattern = pattern
        tensor = FakeTensor(100_000, pattern)
        self.tensors.append(tensor)
        self.events.append("source_tensor")
        return tensor

    def destination_tensor(self, size: int) -> FakeTensor:
        tensor = FakeTensor(200_000, bytes([0xA5]) * size)
        self.tensors.append(tensor)
        self.events.append("destination_tensor")
        return tensor

    def resolve(self, pointer: int, size: int) -> tuple[FakeTensor, int]:
        for tensor in self.tensors:
            offset = pointer - tensor.pointer
            if 0 <= offset and offset + size <= len(tensor.data):
                return tensor, offset
        raise AssertionError(f"unmapped fake pointer {pointer} size {size}")

    def tensor_bytes(self, tensor: FakeTensor) -> bytes:
        return bytes(tensor.data)

    def synchronize(self) -> None:
        self.events.append("synchronize")

    def release_tensors(self, tensors: list[FakeTensor]) -> None:
        self.events.append(f"release:{len(tensors)}")
        tensors.clear()

    def info(self) -> dict[str, object]:
        return {
            "logical_device": 0,
            "physical_device_visibility": "fake-physical-0",
            "device_name": "FakeAscend",
            "device_count": 1,
        }


class FakeTransferEngine:
    def __init__(
        self,
        events: list[str],
        unregister_failure_pointer: int | None = None,
    ) -> None:
        self.events = events
        self.inner_engine = object()
        self.unregister_failure_pointer = unregister_failure_pointer

    def initialize(self, host: str, metadata: str, protocol: str, device: str) -> int:
        self.events.append(f"initialize:{host}:{metadata}:{protocol}:{device}")
        return 0

    def get_rpc_port(self) -> int:
        return 17814

    def get_engine(self) -> object:
        return self.inner_engine

    def register_memory(self, pointer: int, size: int) -> int:
        self.events.append(f"register:{pointer}:{size}")
        return 0

    def unregister_memory(self, pointer: int) -> int:
        self.events.append(f"unregister:{pointer}")
        return -1 if pointer == self.unregister_failure_pointer else 0


class FakeStore:
    def __init__(
        self,
        runtime: FakeRuntime,
        events: list[str],
        fail_operation: str | None = None,
    ) -> None:
        self.runtime = runtime
        self.events = events
        self.fail_operation = fail_operation
        self.setup_kwargs: dict[str, object] | None = None
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.put_sessions: dict[str, bytearray] = {}
        self.objects: dict[str, bytes] = {}
        self.get_sessions: set[str] = set()

    def _maybe_fail(self, operation: str) -> None:
        if self.fail_operation == operation:
            self.events.append(f"raise:{operation}")
            raise RuntimeError(f"injected {operation} failure")

    def setup(self, **kwargs: object) -> int:
        self.setup_kwargs = kwargs
        self.events.append("setup")
        self._maybe_fail("setup")
        return 0

    def batch_put_start(self, keys: list[str], sizes: list[int]) -> list[int]:
        self.calls.append(("put_start", (keys, sizes)))
        results = []
        if len(keys) != len(sizes):
            return [-22] * len(keys)
        for key, size in zip(keys, sizes):
            if key in self.put_sessions:
                results.append(-22)
            else:
                self.put_sessions[key] = bytearray(size)
                results.append(0)
        return results

    def batch_put_from_multi_buffer_ranges(
        self,
        keys: list[str],
        all_buffers: list[list[int]],
        all_sizes: list[list[int]],
        all_offsets: list[list[int]],
    ) -> list[int]:
        self.calls.append(("put_ranges", (keys, all_buffers, all_sizes, all_offsets)))
        self._maybe_fail("put_ranges")
        results = []
        for key, buffers, sizes, offsets in zip(keys, all_buffers, all_sizes, all_offsets):
            if key not in self.put_sessions or not (len(buffers) == len(sizes) == len(offsets)):
                results.append(-22)
                continue
            output = self.put_sessions[key]
            if any(offset + size > len(output) for size, offset in zip(sizes, offsets)):
                results.append(-22)
                continue
            for pointer, size, offset in zip(buffers, sizes, offsets):
                tensor, tensor_offset = self.runtime.resolve(pointer, size)
                output[offset : offset + size] = tensor.data[tensor_offset : tensor_offset + size]
            results.append(sum(sizes))
        return results

    def batch_put_end(self, keys: list[str]) -> list[int]:
        self.calls.append(("put_end", (keys,)))
        results = []
        for key in keys:
            if key not in self.put_sessions:
                results.append(-22)
            else:
                self.objects[key] = bytes(self.put_sessions.pop(key))
                results.append(0)
        return results

    def batch_put_revoke(self, keys: list[str]) -> list[int]:
        self.events.append("revoke")
        self.calls.append(("put_revoke", (keys,)))
        results = []
        for key in keys:
            if key not in self.put_sessions:
                results.append(-22)
            else:
                del self.put_sessions[key]
                results.append(0)
        return results

    def batch_get_start(self, keys: list[str]) -> list[int]:
        self.calls.append(("get_start", (keys,)))
        results = []
        for key in keys:
            if key not in self.objects or key in self.get_sessions:
                results.append(-2)
            else:
                self.get_sessions.add(key)
                results.append(0)
        return results

    def batch_get_into_multi_buffer_ranges(
        self,
        keys: list[str],
        all_buffers: list[list[int]],
        all_sizes: list[list[int]],
        all_offsets: list[list[int]],
    ) -> list[int]:
        self.calls.append(("get_ranges", (keys, all_buffers, all_sizes, all_offsets)))
        self._maybe_fail("get_ranges")
        results = []
        for key, buffers, sizes, offsets in zip(keys, all_buffers, all_sizes, all_offsets):
            if key not in self.get_sessions or not (len(buffers) == len(sizes) == len(offsets)):
                results.append(-22)
                continue
            source = self.objects[key]
            if any(offset + size > len(source) for size, offset in zip(sizes, offsets)):
                results.append(-22)
                continue
            for pointer, size, offset in zip(buffers, sizes, offsets):
                tensor, tensor_offset = self.runtime.resolve(pointer, size)
                tensor.data[tensor_offset : tensor_offset + size] = source[offset : offset + size]
            results.append(sum(sizes))
        return results

    def batch_get_end(self, keys: list[str]) -> int:
        self.events.append("get_end")
        self.calls.append(("get_end", (keys,)))
        for key in keys:
            self.get_sessions.discard(key)
        return 0

    def close(self) -> None:
        self.events.append("close")


def make_dependencies(
    *,
    fail_operation: str | None = None,
    unregister_failure_pointer: int | None = None,
) -> tuple[range_api_smoke.Dependencies, FakeRuntime, FakeTransferEngine, FakeStore, list[str]]:
    events: list[str] = []
    runtime = FakeRuntime(events)
    engine = FakeTransferEngine(events, unregister_failure_pointer)
    store = FakeStore(runtime, events, fail_operation)
    dependencies = range_api_smoke.Dependencies(runtime, engine, store, "10.0.0.8")
    return dependencies, runtime, engine, store, events


def run_smoke(
    dependencies: range_api_smoke.Dependencies,
    *,
    run_negative: bool = False,
) -> dict[str, object]:
    config = range_api_smoke.SmokeConfig(
        output="/tmp/not-written-by-unit-test.json",
        num_keys=3,
        num_layers=4,
        page_size=8,
        run_negative=run_negative,
    )
    with mock.patch.dict(
        os.environ,
        {"MOONCAKE_MASTER": "mooncake-master-service:30089"},
        clear=True,
    ):
        return range_api_smoke.execute(config, dependencies)


def cleanup_events(events: list[str]) -> list[str]:
    return [
        event
        for event in events
        if event in {"get_end", "revoke", "synchronize", "close"}
        or event.startswith("unregister:")
        or event.startswith("release:")
    ]


def _check_success_uses_production_setup_multifragment_batches_and_pattern() -> None:
    dependencies, runtime, engine, store, events = make_dependencies()
    summary = run_smoke(dependencies, run_negative=True)

    assert summary["passed"] is True
    assert summary["plan_commit_sha"] == range_api_smoke.PLAN_COMMIT_SHA
    assert store.setup_kwargs == {
        "local_hostname": "10.0.0.8:17814",
        "metadata_server": "P2PHANDSHAKE",
        "global_segment_size": 64 * 1024 * 1024,
        "local_buffer_size": 0,
        "protocol": "ascend",
        "rdma_devices": "",
        "master_server_addr": "mooncake-master-service:30089",
        "engine": engine.inner_engine,
    }
    positive_puts = [
        call
        for call in summary["api_calls"]
        if call["operation"] == "batch_put_from_multi_buffer_ranges"
        and call["phase"] == "positive"
    ]
    assert len(positive_puts) == 4
    assert positive_puts[0]["sizes"] == [[4, 4], [4, 4], [4, 4]]
    assert positive_puts[0]["object_offsets"] == [[0, 4], [0, 4], [0, 4]]
    assert positive_puts[1]["object_offsets"] == [[8, 12], [8, 12], [8, 12]]
    assert positive_puts[0]["buffer_offsets"] == [[0, 4], [32, 36], [64, 68]]
    assert positive_puts[0]["result"] == [8, 8, 8]
    expected_pattern = range_api_smoke.build_source_pattern(
        range_api_smoke.SmokeConfig("unused", 3, 4, 8)
    )
    assert runtime.source_pattern == expected_pattern
    assert summary["source_checksum"] == summary["destination_checksum_after"]
    assert cleanup_events(events)[-5:] == [
        "synchronize",
        "unregister:100000",
        "unregister:200000",
        "close",
        "release:2",
    ]


def _check_setup_exception_closes_store_and_propagates_failure() -> None:
    dependencies, _, _, _, events = make_dependencies(fail_operation="setup")
    summary = run_smoke(dependencies)

    assert summary["passed"] is False
    assert summary["errors"][0]["message"] == "injected setup failure"
    assert cleanup_events(events) == ["synchronize", "close", "release:0"]


def _check_mid_put_exception_revokes_before_memory_cleanup() -> None:
    dependencies, _, _, _, events = make_dependencies(fail_operation="put_ranges")
    summary = run_smoke(dependencies)

    assert summary["passed"] is False
    failure_index = events.index("raise:put_ranges")
    assert cleanup_events(events[failure_index + 1 :]) == [
        "revoke",
        "synchronize",
        "unregister:100000",
        "unregister:200000",
        "close",
        "release:2",
    ]


def _check_mid_get_exception_ends_get_before_memory_cleanup() -> None:
    dependencies, _, _, _, events = make_dependencies(fail_operation="get_ranges")
    summary = run_smoke(dependencies)

    assert summary["passed"] is False
    failure_index = events.index("raise:get_ranges")
    assert cleanup_events(events[failure_index + 1 :]) == [
        "get_end",
        "synchronize",
        "unregister:100000",
        "unregister:200000",
        "close",
        "release:2",
    ]


def _check_cleanup_return_code_failure_makes_summary_fail() -> None:
    dependencies, _, _, _, events = make_dependencies(
        unregister_failure_pointer=100_000
    )
    summary = run_smoke(dependencies)

    assert summary["passed"] is False
    failed_cleanup = [item for item in summary["cleanup"] if not item["passed"]]
    assert [item["step"] for item in failed_cleanup] == [
        "TransferEngine.unregister_memory:100000"
    ]
    assert cleanup_events(events)[-5:] == [
        "synchronize",
        "unregister:100000",
        "unregister:200000",
        "close",
        "release:2",
    ]


class TestRangeApiSmoke(unittest.TestCase):
    def test_success_uses_production_setup_multifragment_batches_and_pattern(self) -> None:
        _check_success_uses_production_setup_multifragment_batches_and_pattern()

    def test_setup_exception_closes_store_and_propagates_failure(self) -> None:
        _check_setup_exception_closes_store_and_propagates_failure()

    def test_mid_put_exception_revokes_before_memory_cleanup(self) -> None:
        _check_mid_put_exception_revokes_before_memory_cleanup()

    def test_mid_get_exception_ends_get_before_memory_cleanup(self) -> None:
        _check_mid_get_exception_ends_get_before_memory_cleanup()

    def test_cleanup_return_code_failure_makes_summary_fail(self) -> None:
        _check_cleanup_return_code_failure_makes_summary_fail()


if __name__ == "__main__":
    unittest.main()
