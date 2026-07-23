#!/usr/bin/env python3
"""Direct Mooncake ranged API smoke test using Ascend NPU tensors."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import secrets
import socket
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


PLAN_COMMIT_SHA = "a3406334959d8c68537b305c6242450db3c684c2"
G3_FIXTURE_ID = "commit:2d0bd8a7db177b4a3aed2ff69fac845f756ff21d"
TEST_SEGMENT_SIZE = 64 * 1024 * 1024


class ValidationFailure(RuntimeError):
    """Raised after a failed assertion has been recorded in the summary."""


@dataclass(frozen=True)
class SmokeConfig:
    output: str
    num_keys: int = 3
    num_layers: int = 4
    page_size: int = 4096
    run_negative: bool = False

    @property
    def object_size(self) -> int:
        return self.num_layers * self.page_size

    @property
    def total_size(self) -> int:
        return self.num_keys * self.object_size

    def validate(self) -> None:
        if self.num_keys < 1:
            raise ValueError("--num-keys must be at least 1")
        if self.num_layers < 1:
            raise ValueError("--num-layers must be at least 1")
        if self.page_size < 2:
            raise ValueError("--page-size must be at least 2 to form two fragments")
        if not self.output:
            raise ValueError("--output is required")


@dataclass
class Dependencies:
    runtime: Any
    transfer_engine: Any
    store: Any
    local_ip: str


def build_source_pattern(config: SmokeConfig) -> bytes:
    """Return deterministic, key/layer-sensitive bytes for offset validation."""
    pattern = bytearray(config.total_size)
    for key_index in range(config.num_keys):
        key_base = key_index * config.object_size
        for layer in range(config.num_layers):
            layer_base = key_base + layer * config.page_size
            for index in range(config.page_size):
                pattern[layer_base + index] = (
                    key_index * 43 + layer * 17 + index * 31
                ) % 251
    return bytes(pattern)


def build_layer_batch(
    base_ptr: int,
    config: SmokeConfig,
    layer: int,
) -> tuple[list[list[int]], list[list[int]], list[list[int]], list[list[int]]]:
    """Build two fragments per key and return pointers, sizes and offsets."""
    first_size = config.page_size // 2
    fragment_sizes = [first_size, config.page_size - first_size]
    object_offsets = [layer * config.page_size, layer * config.page_size + first_size]
    buffers: list[list[int]] = []
    sizes: list[list[int]] = []
    offsets: list[list[int]] = []
    buffer_offsets: list[list[int]] = []
    for key_index in range(config.num_keys):
        first_buffer_offset = key_index * config.object_size + layer * config.page_size
        relative_buffers = [first_buffer_offset, first_buffer_offset + first_size]
        buffers.append([base_ptr + value for value in relative_buffers])
        sizes.append(list(fragment_sizes))
        offsets.append(list(object_offsets))
        buffer_offsets.append(relative_buffers)
    return buffers, sizes, offsets, buffer_offsets


class AscendRuntime:
    def __init__(self, torch_module: Any, torch_npu_module: Any) -> None:
        self.torch = torch_module
        self.torch_npu = torch_npu_module

    def set_device(self, logical_device: int) -> None:
        self.torch.npu.set_device(logical_device)

    def source_tensor(self, pattern: bytes) -> Any:
        cpu_tensor = self.torch.tensor(list(pattern), dtype=self.torch.uint8)
        return cpu_tensor.to("npu:0")

    def destination_tensor(self, size: int) -> Any:
        return self.torch.full(
            (size,),
            0xA5,
            dtype=self.torch.uint8,
            device="npu:0",
        )

    def tensor_bytes(self, tensor: Any) -> bytes:
        return bytes(tensor.detach().cpu().tolist())

    def synchronize(self) -> None:
        self.torch.npu.synchronize()

    def release_tensors(self, tensors: list[Any]) -> None:
        tensors.clear()
        self.torch.npu.empty_cache()

    def info(self) -> dict[str, Any]:
        logical_device = int(self.torch.npu.current_device())
        visible = (
            os.getenv("ASCEND_RT_VISIBLE_DEVICES")
            or os.getenv("ASCEND_VISIBLE_DEVICES")
            or os.getenv("NPU_VISIBLE_DEVICES")
        )
        try:
            device_name = self.torch.npu.get_device_name(logical_device)
        except Exception as exc:  # pragma: no cover - runtime-specific metadata
            device_name = f"unavailable: {type(exc).__name__}: {exc}"
        return {
            "logical_device": logical_device,
            "physical_device_visibility": visible or "not exposed by environment",
            "device_name": device_name,
            "device_count": int(self.torch.npu.device_count()),
            "torch_version": getattr(self.torch, "__version__", "unknown"),
            "torch_npu_version": getattr(self.torch_npu, "__version__", "unknown"),
            "torch_module": getattr(self.torch, "__file__", None),
            "torch_npu_module": getattr(self.torch_npu, "__file__", None),
        }


def _distribution_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed as a named distribution"


def _discover_local_ip() -> str:
    if os.getenv("POD_IP"):
        return os.environ["POD_IP"]
    try:
        from vllm.utils.network_utils import get_ip

        return str(get_ip())
    except Exception:
        hostname_ip = socket.gethostbyname(socket.gethostname())
        if not hostname_ip or hostname_ip.startswith("127."):
            raise RuntimeError("could not resolve a non-loopback local IP")
        return hostname_ip


def _load_dependencies() -> Dependencies:
    torch_module = importlib.import_module("torch")
    torch_npu_module = importlib.import_module("torch_npu")
    engine_module = importlib.import_module("mooncake.engine")
    store_module = importlib.import_module("mooncake.store")
    return Dependencies(
        runtime=AscendRuntime(torch_module, torch_npu_module),
        transfer_engine=engine_module.TransferEngine(),
        store=store_module.MooncakeDistributedStore(),
        local_ip=_discover_local_ip(),
    )


def _load_store_config() -> dict[str, Any]:
    config_path = os.getenv("MOONCAKE_CONFIG_PATH")
    file_config: dict[str, Any] = {}
    if config_path:
        with open(config_path, encoding="utf-8") as config_file:
            file_config = json.load(config_file)
    master_address = os.getenv("MOONCAKE_MASTER") or file_config.get(
        "master_server_address"
    )
    if not master_address:
        raise ValueError(
            "Mooncake Master address is missing; set MOONCAKE_MASTER or "
            "master_server_address in MOONCAKE_CONFIG_PATH"
        )
    metadata_server = file_config.get("metadata_server", "P2PHANDSHAKE")
    protocol = file_config.get("protocol", "ascend")
    device_name = file_config.get("device_name", "")
    if metadata_server != "P2PHANDSHAKE":
        raise ValueError(
            f"expected metadata_server='P2PHANDSHAKE', got {metadata_server!r}"
        )
    if protocol != "ascend":
        raise ValueError(f"expected protocol='ascend', got {protocol!r}")
    return {
        "config_path": config_path,
        "metadata_server": metadata_server,
        "protocol": protocol,
        "device_name": device_name,
        "master_server_address": master_address,
        "global_segment_size": TEST_SEGMENT_SIZE,
        "local_buffer_size": 0,
    }


def _new_summary(config: SmokeConfig) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "plan_commit_sha": PLAN_COMMIT_SHA,
        "g3_fixture_id": G3_FIXTURE_ID,
        "started_at_unix": time.time(),
        "passed": False,
        "config": {
            "num_keys": config.num_keys,
            "num_layers": config.num_layers,
            "page_size": config.page_size,
            "object_size": config.object_size,
            "total_size": config.total_size,
            "run_negative": config.run_negative,
        },
        "runtime": {
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
            "mooncake_distribution_version": _distribution_version(
                "mooncake-transfer-engine"
            ),
        },
        "api_calls": [],
        "cases": [],
        "cleanup": [],
        "errors": [],
    }


class SmokeRunner:
    def __init__(self, config: SmokeConfig, summary: dict[str, Any]) -> None:
        self.config = config
        self.summary = summary
        self.dependencies: Dependencies | None = None
        self.store_config: dict[str, Any] | None = None
        self.source: Any | None = None
        self.destination: Any | None = None
        self.registered_pointers: list[int] = []
        self.active_put_keys: list[str] = []
        self.active_get_keys: list[str] = []
        self.device_selected = False
        self.key_prefix = (
            f"range-smoke-{int(time.time() * 1000)}-{os.getpid()}-"
            f"{secrets.token_hex(4)}"
        )

    def _record_case(
        self,
        name: str,
        passed: bool,
        *,
        expected: Any,
        actual: Any,
    ) -> None:
        self.summary["cases"].append(
            {
                "name": name,
                "passed": bool(passed),
                "expected": expected,
                "actual": actual,
            }
        )
        if not passed:
            raise ValidationFailure(f"case failed: {name}: expected {expected}, got {actual}")

    def _call(
        self,
        operation: str,
        function: Callable[..., Any],
        *args: Any,
        phase: str,
        keys: Sequence[str] | None = None,
        sizes: Sequence[Sequence[int]] | None = None,
        object_offsets: Sequence[Sequence[int]] | None = None,
        buffer_offsets: Sequence[Sequence[int]] | None = None,
        **kwargs: Any,
    ) -> Any:
        record: dict[str, Any] = {
            "operation": operation,
            "phase": phase,
        }
        if keys is not None:
            record["keys"] = list(keys)
        if sizes is not None:
            record["sizes"] = [list(values) for values in sizes]
        if object_offsets is not None:
            record["object_offsets"] = [list(values) for values in object_offsets]
        if buffer_offsets is not None:
            record["buffer_offsets"] = [list(values) for values in buffer_offsets]
        try:
            result = function(*args, **kwargs)
            if isinstance(result, tuple):
                result = list(result)
            record["result"] = result
            return result
        except Exception as exc:
            record["exception"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.summary["api_calls"].append(record)

    @staticmethod
    def _int_results(result: Any, expected_length: int) -> list[int]:
        if not isinstance(result, (list, tuple)) or len(result) != expected_length:
            return []
        try:
            return [int(value) for value in result]
        except (TypeError, ValueError):
            return []

    def _expect_vector(
        self,
        name: str,
        result: Any,
        expected_length: int,
        predicate: Callable[[int], bool],
        expected: str,
    ) -> list[int]:
        values = self._int_results(result, expected_length)
        passed = len(values) == expected_length and all(predicate(value) for value in values)
        self._record_case(name, passed, expected=expected, actual=result)
        return values

    def _start_put(self, keys: list[str], sizes: list[int], phase: str) -> list[int]:
        assert self.dependencies is not None
        for key in keys:
            if key not in self.active_put_keys:
                self.active_put_keys.append(key)
        result = self._call(
            "batch_put_start",
            self.dependencies.store.batch_put_start,
            keys,
            sizes,
            phase=phase,
            keys=keys,
        )
        values = self._int_results(result, len(keys))
        if len(values) == len(keys):
            for key, value in zip(keys, values):
                if value != 0 and key in self.active_put_keys:
                    self.active_put_keys.remove(key)
        return values

    def _start_get(self, keys: list[str], phase: str) -> list[int]:
        assert self.dependencies is not None
        for key in keys:
            if key not in self.active_get_keys:
                self.active_get_keys.append(key)
        result = self._call(
            "batch_get_start",
            self.dependencies.store.batch_get_start,
            keys,
            phase=phase,
            keys=keys,
        )
        values = self._int_results(result, len(keys))
        if len(values) == len(keys):
            for key, value in zip(keys, values):
                if value != 0 and key in self.active_get_keys:
                    self.active_get_keys.remove(key)
        return values

    def _revoke_put(self, keys: list[str], phase: str, case_name: str) -> None:
        assert self.dependencies is not None
        result = self._call(
            "batch_put_revoke",
            self.dependencies.store.batch_put_revoke,
            keys,
            phase=phase,
            keys=keys,
        )
        values = self._expect_vector(case_name, result, len(keys), lambda value: value == 0, "all 0")
        for key, value in zip(keys, values):
            if value == 0 and key in self.active_put_keys:
                self.active_put_keys.remove(key)

    def _end_get(self, keys: list[str], phase: str, case_name: str) -> None:
        assert self.dependencies is not None
        result = self._call(
            "batch_get_end",
            self.dependencies.store.batch_get_end,
            keys,
            phase=phase,
            keys=keys,
        )
        value = int(result)
        self._record_case(case_name, value == 0, expected=0, actual=result)
        for key in keys:
            if key in self.active_get_keys:
                self.active_get_keys.remove(key)

    def initialize(self, dependencies: Dependencies | None) -> None:
        self.dependencies = dependencies or _load_dependencies()
        self.store_config = _load_store_config()
        runtime = self.dependencies.runtime
        engine = self.dependencies.transfer_engine
        store = self.dependencies.store

        runtime.set_device(0)
        self.device_selected = True
        self.summary["runtime"].update(runtime.info())
        self.summary["runtime"].update(
            {
                "local_ip": self.dependencies.local_ip,
                "mooncake_engine_module": type(engine).__module__,
                "mooncake_engine_module_file": getattr(
                    sys.modules.get(type(engine).__module__), "__file__", None
                ),
                "mooncake_store_module": type(store).__module__,
                "mooncake_store_module_file": getattr(
                    sys.modules.get(type(store).__module__), "__file__", None
                ),
            }
        )
        initialize_result = self._call(
            "TransferEngine.initialize",
            engine.initialize,
            self.dependencies.local_ip,
            self.store_config["metadata_server"],
            self.store_config["protocol"],
            self.store_config["device_name"],
            phase="setup",
        )
        self._record_case(
            "transfer_engine_initialize",
            int(initialize_result) == 0,
            expected=0,
            actual=initialize_result,
        )
        local_endpoint = f"{self.dependencies.local_ip}:{engine.get_rpc_port()}"
        setup_args = {
            "local_hostname": local_endpoint,
            "metadata_server": self.store_config["metadata_server"],
            "global_segment_size": self.store_config["global_segment_size"],
            "local_buffer_size": self.store_config["local_buffer_size"],
            "protocol": self.store_config["protocol"],
            "rdma_devices": self.store_config["device_name"],
            "master_server_addr": self.store_config["master_server_address"],
            "engine": engine.get_engine(),
        }
        self.summary["runtime"]["store_config"] = {
            **self.store_config,
            "local_hostname": local_endpoint,
            "engine_passed_explicitly": True,
        }
        setup_result = self._call(
            "MooncakeDistributedStore.setup",
            store.setup,
            phase="setup",
            **setup_args,
        )
        self._record_case(
            "store_setup",
            int(setup_result) == 0,
            expected=0,
            actual=setup_result,
        )

    def allocate_and_register(self) -> None:
        assert self.dependencies is not None
        runtime = self.dependencies.runtime
        engine = self.dependencies.transfer_engine
        source_pattern = build_source_pattern(self.config)
        self.source = runtime.source_tensor(source_pattern)
        self.destination = runtime.destination_tensor(self.config.total_size)
        source_before = runtime.tensor_bytes(self.source)
        destination_before = runtime.tensor_bytes(self.destination)
        self.summary["source_checksum"] = hashlib.sha256(source_before).hexdigest()
        self.summary["destination_checksum_before"] = hashlib.sha256(
            destination_before
        ).hexdigest()
        self._record_case(
            "source_pattern",
            source_before == source_pattern,
            expected=hashlib.sha256(source_pattern).hexdigest(),
            actual=self.summary["source_checksum"],
        )

        for name, tensor in (("source", self.source), ("destination", self.destination)):
            pointer = int(tensor.data_ptr())
            size = int(tensor.numel() * tensor.element_size())
            result = self._call(
                "TransferEngine.register_memory",
                engine.register_memory,
                pointer,
                size,
                phase="setup",
            )
            self._record_case(
                f"register_{name}",
                int(result) == 0,
                expected=0,
                actual=result,
            )
            self.registered_pointers.append(pointer)

    def run_positive(self) -> None:
        assert self.dependencies is not None
        assert self.source is not None and self.destination is not None
        store = self.dependencies.store
        keys = [f"{self.key_prefix}-positive-{index}" for index in range(self.config.num_keys)]
        object_sizes = [self.config.object_size] * self.config.num_keys

        start_values = self._start_put(keys, object_sizes, "positive")
        self._record_case(
            "positive_put_start",
            len(start_values) == len(keys) and all(value == 0 for value in start_values),
            expected="all 0",
            actual=start_values,
        )

        for layer in range(self.config.num_layers):
            buffers, sizes, offsets, buffer_offsets = build_layer_batch(
                int(self.source.data_ptr()), self.config, layer
            )
            result = self._call(
                "batch_put_from_multi_buffer_ranges",
                store.batch_put_from_multi_buffer_ranges,
                keys,
                buffers,
                sizes,
                offsets,
                phase="positive",
                keys=keys,
                sizes=sizes,
                object_offsets=offsets,
                buffer_offsets=buffer_offsets,
            )
            self._expect_vector(
                f"positive_put_layer_{layer}",
                result,
                len(keys),
                lambda value: value == self.config.page_size,
                f"all {self.config.page_size}",
            )

        commit_result = self._call(
            "batch_put_end",
            store.batch_put_end,
            keys,
            phase="positive",
            keys=keys,
        )
        commit_values = self._expect_vector(
            "positive_put_end", commit_result, len(keys), lambda value: value == 0, "all 0"
        )
        for key, value in zip(keys, commit_values):
            if value == 0 and key in self.active_put_keys:
                self.active_put_keys.remove(key)

        get_start_values = self._start_get(keys, "positive")
        self._record_case(
            "positive_get_start",
            len(get_start_values) == len(keys) and all(value == 0 for value in get_start_values),
            expected="all 0",
            actual=get_start_values,
        )

        for layer in range(self.config.num_layers):
            buffers, sizes, offsets, buffer_offsets = build_layer_batch(
                int(self.destination.data_ptr()), self.config, layer
            )
            result = self._call(
                "batch_get_into_multi_buffer_ranges",
                store.batch_get_into_multi_buffer_ranges,
                keys,
                buffers,
                sizes,
                offsets,
                phase="positive",
                keys=keys,
                sizes=sizes,
                object_offsets=offsets,
                buffer_offsets=buffer_offsets,
            )
            self._expect_vector(
                f"positive_get_layer_{layer}",
                result,
                len(keys),
                lambda value: value == self.config.page_size,
                f"all {self.config.page_size}",
            )

        self._end_get(keys, "positive", "positive_get_end")
        self.dependencies.runtime.synchronize()
        source_bytes = self.dependencies.runtime.tensor_bytes(self.source)
        destination_bytes = self.dependencies.runtime.tensor_bytes(self.destination)
        self.summary["source_checksum"] = hashlib.sha256(source_bytes).hexdigest()
        self.summary["destination_checksum_after"] = hashlib.sha256(
            destination_bytes
        ).hexdigest()
        self._record_case(
            "positive_byte_compare",
            source_bytes == destination_bytes,
            expected=self.summary["source_checksum"],
            actual=self.summary["destination_checksum_after"],
        )
        nonzero_offset = any(
            offset > 0
            for call in self.summary["api_calls"]
            if call["phase"] == "positive"
            for offsets in call.get("object_offsets", [])
            for offset in offsets
        )
        self._record_case(
            "positive_nonzero_object_offset",
            nonzero_offset,
            expected=True,
            actual=nonzero_offset,
        )

    def _single_range(
        self,
        tensor: Any,
        object_offset: int = 0,
    ) -> tuple[list[list[int]], list[list[int]], list[list[int]]]:
        first_size = self.config.page_size // 2
        return (
            [[int(tensor.data_ptr()), int(tensor.data_ptr()) + first_size]],
            [[first_size, self.config.page_size - first_size]],
            [[object_offset, object_offset + first_size]],
        )

    def run_negative(self) -> None:
        assert self.dependencies is not None
        assert self.source is not None and self.destination is not None
        store = self.dependencies.store
        object_size = self.config.object_size

        no_put_key = [f"{self.key_prefix}-no-put-session"]
        buffers, sizes, offsets = self._single_range(self.source)
        result = self._call(
            "batch_put_from_multi_buffer_ranges",
            store.batch_put_from_multi_buffer_ranges,
            no_put_key,
            buffers,
            sizes,
            offsets,
            phase="negative_no_session",
            keys=no_put_key,
            sizes=sizes,
            object_offsets=offsets,
            buffer_offsets=[[0, self.config.page_size // 2]],
        )
        self._expect_vector(
            "negative_no_put_session", result, 1, lambda value: value < 0, "one negative code"
        )

        no_get_key = [f"{self.key_prefix}-no-get-session"]
        result = self._call(
            "batch_get_into_multi_buffer_ranges",
            store.batch_get_into_multi_buffer_ranges,
            no_get_key,
            buffers,
            sizes,
            offsets,
            phase="negative_no_session",
            keys=no_get_key,
            sizes=sizes,
            object_offsets=offsets,
            buffer_offsets=[[0, self.config.page_size // 2]],
        )
        self._expect_vector(
            "negative_no_get_session", result, 1, lambda value: value < 0, "one negative code"
        )

        duplicate_key = [f"{self.key_prefix}-duplicate-put-start"]
        first = self._start_put(duplicate_key, [object_size], "negative_duplicate")
        self._record_case(
            "negative_duplicate_first_start",
            first == [0],
            expected=[0],
            actual=first,
        )
        duplicate = self._call(
            "batch_put_start",
            store.batch_put_start,
            duplicate_key,
            [object_size],
            phase="negative_duplicate",
            keys=duplicate_key,
        )
        self._expect_vector(
            "negative_duplicate_put_start",
            duplicate,
            1,
            lambda value: value < 0,
            "one negative code",
        )
        self._revoke_put(duplicate_key, "negative_duplicate", "negative_duplicate_revoke")

        overflow_key = [f"{self.key_prefix}-offset-overflow"]
        start = self._start_put(overflow_key, [object_size], "negative_overflow")
        self._record_case("negative_overflow_start", start == [0], expected=[0], actual=start)
        overflow_buffers = [[int(self.source.data_ptr())]]
        overflow_sizes = [[self.config.page_size]]
        overflow_offsets = [[object_size]]
        overflow = self._call(
            "batch_put_from_multi_buffer_ranges",
            store.batch_put_from_multi_buffer_ranges,
            overflow_key,
            overflow_buffers,
            overflow_sizes,
            overflow_offsets,
            phase="negative_overflow",
            keys=overflow_key,
            sizes=overflow_sizes,
            object_offsets=overflow_offsets,
            buffer_offsets=[[0]],
        )
        self._expect_vector(
            "negative_offset_overflow", overflow, 1, lambda value: value < 0, "one negative code"
        )
        self._revoke_put(overflow_key, "negative_overflow", "negative_overflow_revoke")

        arity_key = [f"{self.key_prefix}-put-arity"]
        start = self._start_put(arity_key, [object_size], "negative_put_arity")
        self._record_case("negative_put_arity_start", start == [0], expected=[0], actual=start)
        bad_buffers, _, _ = self._single_range(self.source)
        bad_sizes = [[self.config.page_size]]
        bad_offsets = [[0]]
        bad = self._call(
            "batch_put_from_multi_buffer_ranges",
            store.batch_put_from_multi_buffer_ranges,
            arity_key,
            bad_buffers,
            bad_sizes,
            bad_offsets,
            phase="negative_put_arity",
            keys=arity_key,
            sizes=bad_sizes,
            object_offsets=bad_offsets,
            buffer_offsets=[[0, self.config.page_size // 2]],
        )
        self._expect_vector(
            "negative_put_arity_mismatch", bad, 1, lambda value: value < 0, "one negative code"
        )
        self._revoke_put(arity_key, "negative_put_arity", "negative_put_arity_revoke")

        ended_key = [f"{self.key_prefix}-after-end"]
        start = self._start_put(ended_key, [object_size], "negative_after_put_end")
        self._record_case("negative_after_put_end_start", start == [0], expected=[0], actual=start)
        first_size = object_size // 2
        full_buffers = [[int(self.source.data_ptr()), int(self.source.data_ptr()) + first_size]]
        full_sizes = [[first_size, object_size - first_size]]
        full_offsets = [[0, first_size]]
        put = self._call(
            "batch_put_from_multi_buffer_ranges",
            store.batch_put_from_multi_buffer_ranges,
            ended_key,
            full_buffers,
            full_sizes,
            full_offsets,
            phase="negative_after_put_end",
            keys=ended_key,
            sizes=full_sizes,
            object_offsets=full_offsets,
            buffer_offsets=[[0, first_size]],
        )
        self._expect_vector(
            "negative_after_put_end_write",
            put,
            1,
            lambda value: value == object_size,
            f"one {object_size}",
        )
        end = self._call(
            "batch_put_end",
            store.batch_put_end,
            ended_key,
            phase="negative_after_put_end",
            keys=ended_key,
        )
        end_values = self._expect_vector(
            "negative_after_put_end_commit", end, 1, lambda value: value == 0, "one 0"
        )
        if end_values == [0] and ended_key[0] in self.active_put_keys:
            self.active_put_keys.remove(ended_key[0])
        after_put_end = self._call(
            "batch_put_from_multi_buffer_ranges",
            store.batch_put_from_multi_buffer_ranges,
            ended_key,
            buffers,
            sizes,
            offsets,
            phase="negative_after_put_end",
            keys=ended_key,
            sizes=sizes,
            object_offsets=offsets,
            buffer_offsets=[[0, self.config.page_size // 2]],
        )
        self._expect_vector(
            "negative_ranged_put_after_end",
            after_put_end,
            1,
            lambda value: value < 0,
            "one negative code",
        )

        start_get = self._start_get(ended_key, "negative_after_get_end")
        self._record_case(
            "negative_after_get_end_start",
            start_get == [0],
            expected=[0],
            actual=start_get,
        )
        self._end_get(ended_key, "negative_after_get_end", "negative_after_get_end_close")
        after_get_end = self._call(
            "batch_get_into_multi_buffer_ranges",
            store.batch_get_into_multi_buffer_ranges,
            ended_key,
            buffers,
            sizes,
            offsets,
            phase="negative_after_get_end",
            keys=ended_key,
            sizes=sizes,
            object_offsets=offsets,
            buffer_offsets=[[0, self.config.page_size // 2]],
        )
        self._expect_vector(
            "negative_ranged_get_after_end",
            after_get_end,
            1,
            lambda value: value < 0,
            "one negative code",
        )

        get_arity_start = self._start_get(ended_key, "negative_get_arity")
        self._record_case(
            "negative_get_arity_start",
            get_arity_start == [0],
            expected=[0],
            actual=get_arity_start,
        )
        get_bad_buffers = [[int(self.destination.data_ptr())]]
        get_bad_sizes = [[self.config.page_size, self.config.page_size]]
        get_bad_offsets = [[0]]
        get_bad = self._call(
            "batch_get_into_multi_buffer_ranges",
            store.batch_get_into_multi_buffer_ranges,
            ended_key,
            get_bad_buffers,
            get_bad_sizes,
            get_bad_offsets,
            phase="negative_get_arity",
            keys=ended_key,
            sizes=get_bad_sizes,
            object_offsets=get_bad_offsets,
            buffer_offsets=[[0]],
        )
        self._expect_vector(
            "negative_get_arity_mismatch",
            get_bad,
            1,
            lambda value: value < 0,
            "one negative code",
        )
        self._end_get(ended_key, "negative_get_arity", "negative_get_arity_close")

        revoke_key = [f"{self.key_prefix}-revoke"]
        revoke_start = self._start_put(revoke_key, [object_size], "negative_revoke")
        self._record_case(
            "negative_revoke_start",
            revoke_start == [0],
            expected=[0],
            actual=revoke_start,
        )
        self._revoke_put(revoke_key, "negative_revoke", "negative_revoke")
        missing = self._call(
            "batch_get_start",
            store.batch_get_start,
            revoke_key,
            phase="negative_revoke",
            keys=revoke_key,
        )
        self._expect_vector(
            "negative_revoke_not_gettable",
            missing,
            1,
            lambda value: value < 0,
            "one negative code",
        )

    def cleanup(self) -> bool:
        passed = True
        dependencies = self.dependencies
        if dependencies is None:
            return passed

        def cleanup_step(name: str, function: Callable[[], Any], validator: Callable[[Any], bool]) -> None:
            nonlocal passed
            record: dict[str, Any] = {"step": name, "passed": False}
            try:
                result = function()
                record["result"] = result
                record["passed"] = bool(validator(result))
            except Exception as exc:
                record["exception"] = f"{type(exc).__name__}: {exc}"
            if not record["passed"]:
                passed = False
            self.summary["cleanup"].append(record)

        if self.active_get_keys:
            keys = list(self.active_get_keys)
            cleanup_step(
                "batch_get_end",
                lambda: dependencies.store.batch_get_end(keys),
                lambda result: int(result) == 0,
            )
            self.active_get_keys.clear()
        if self.active_put_keys:
            keys = list(self.active_put_keys)
            cleanup_step(
                "batch_put_revoke",
                lambda: dependencies.store.batch_put_revoke(keys),
                lambda result: self._int_results(result, len(keys)) == [0] * len(keys),
            )
            self.active_put_keys.clear()
        if self.device_selected:
            cleanup_step("torch.npu.synchronize", dependencies.runtime.synchronize, lambda result: result is None)
        for pointer in list(self.registered_pointers):
            cleanup_step(
                f"TransferEngine.unregister_memory:{pointer}",
                lambda pointer=pointer: dependencies.transfer_engine.unregister_memory(pointer),
                lambda result: int(result) == 0,
            )
        self.registered_pointers.clear()
        cleanup_step(
            "MooncakeDistributedStore.close",
            dependencies.store.close,
            lambda result: result is None or int(result) == 0,
        )
        tensors = [tensor for tensor in (self.source, self.destination) if tensor is not None]
        self.source = None
        self.destination = None
        cleanup_step(
            "tensor_release_and_empty_cache",
            lambda: dependencies.runtime.release_tensors(tensors),
            lambda result: result is None,
        )
        tensors.clear()
        return passed


def execute(config: SmokeConfig, dependencies: Dependencies | None = None) -> dict[str, Any]:
    summary = _new_summary(config)
    runner = SmokeRunner(config, summary)
    main_passed = False
    try:
        config.validate()
        runner.initialize(dependencies)
        runner.allocate_and_register()
        runner.run_positive()
        if config.run_negative:
            runner.run_negative()
        main_passed = True
    except Exception as exc:
        summary["errors"].append(
            {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        cleanup_passed = runner.cleanup()
    summary["passed"] = bool(main_passed and cleanup_passed)
    summary["finished_at_unix"] = time.time()
    return summary


def _write_summary(path: str, summary: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp-{os.getpid()}")
    with temporary_path.open("w", encoding="utf-8") as output_file:
        json.dump(summary, output_file, indent=2, sort_keys=True)
        output_file.write("\n")
    temporary_path.replace(output_path)


def _parse_args(argv: Sequence[str] | None = None) -> SmokeConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--num-keys", type=int, default=3)
    parser.add_argument("--num-layers", type=int, default=4)
    parser.add_argument("--page-size", type=int, default=4096)
    parser.add_argument("--run-negative", action="store_true")
    args = parser.parse_args(argv)
    return SmokeConfig(
        output=args.output,
        num_keys=args.num_keys,
        num_layers=args.num_layers,
        page_size=args.page_size,
        run_negative=args.run_negative,
    )


def main(argv: Sequence[str] | None = None) -> int:
    config = _parse_args(argv)
    summary = execute(config)
    _write_summary(config.output, summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
