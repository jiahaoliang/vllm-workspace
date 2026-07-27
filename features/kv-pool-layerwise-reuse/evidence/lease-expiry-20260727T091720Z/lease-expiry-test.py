#!/usr/bin/env python3
"""Validate two-layer put visibility and ranged-read lease expiration."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


OBJECT_NOT_FOUND = -704
LEASE_EXPIRED = -707


def _load_range_smoke() -> Any:
    path = Path(__file__).with_name("range-api-smoke.py")
    spec = importlib.util.spec_from_file_location("range_api_smoke", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load ranged smoke helper: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


range_api_smoke = _load_range_smoke()


@dataclass(frozen=True)
class LeaseExpiryConfig:
    output: str
    lease_ttl_ms: int = 30_000
    wait_margin_ms: int = 1_500
    page_size: int = 4_096

    @property
    def wait_ms(self) -> int:
        return self.lease_ttl_ms + self.wait_margin_ms

    def validate(self) -> None:
        if not self.output:
            raise ValueError("--output is required")
        if self.lease_ttl_ms < 1:
            raise ValueError("--lease-ttl-ms must be at least 1")
        if self.wait_margin_ms < 1:
            raise ValueError("--wait-margin-ms must be at least 1")
        if self.page_size < 2:
            raise ValueError("--page-size must be at least 2")


class LeaseExpiryRunner:
    def __init__(
        self,
        config: LeaseExpiryConfig,
        summary: dict[str, Any],
        base_runner: Any,
        *,
        sleep_fn: Callable[[float], None],
        monotonic_fn: Callable[[], float],
    ) -> None:
        self.config = config
        self.summary = summary
        self.base = base_runner
        self.sleep_fn = sleep_fn
        self.monotonic_fn = monotonic_fn
        self.committed_key: str | None = None

    @property
    def store(self) -> Any:
        assert self.base.dependencies is not None
        return self.base.dependencies.store

    def _expect_exact_vector(
        self,
        name: str,
        result: Any,
        expected: list[int],
    ) -> list[int]:
        values = self.base._int_results(result, len(expected))
        self.base._record_case(
            name,
            values == expected,
            expected=expected,
            actual=result,
        )
        return values

    def _wait_past_lease(self, phase: str) -> None:
        started = self.monotonic_fn()
        self.sleep_fn(self.config.wait_ms / 1_000)
        elapsed_ms = (self.monotonic_fn() - started) * 1_000
        self.summary["waits"].append(
            {
                "phase": phase,
                "requested_ms": self.config.wait_ms,
                "elapsed_ms": elapsed_ms,
            }
        )
        self.base._record_case(
            f"{phase}_wait_exceeded_lease_ttl",
            elapsed_ms >= self.config.lease_ttl_ms,
            expected=f">= {self.config.lease_ttl_ms}ms",
            actual=elapsed_ms,
        )

    def _range_call(
        self,
        *,
        operation: str,
        function: Callable[..., Any],
        key: str,
        tensor: Any,
        layer: int,
        phase: str,
    ) -> Any:
        smoke_config = self.base.config
        buffers, sizes, offsets, buffer_offsets = range_api_smoke.build_layer_batch(
            int(tensor.data_ptr()), smoke_config, layer
        )
        return self.base._call(
            operation,
            function,
            [key],
            buffers,
            sizes,
            offsets,
            phase=phase,
            keys=[key],
            sizes=sizes,
            object_offsets=offsets,
            buffer_offsets=buffer_offsets,
        )

    def run(self) -> None:
        assert self.base.source is not None and self.base.destination is not None
        key = f"{self.base.key_prefix}-lease-expiry"
        keys = [key]
        object_size = self.base.config.object_size

        put_start = self.base._start_put(keys, [object_size], "slow_put")
        self._expect_exact_vector("slow_put_start", put_start, [0])

        layer_zero_put = self._range_call(
            operation="batch_put_from_multi_buffer_ranges",
            function=self.store.batch_put_from_multi_buffer_ranges,
            key=key,
            tensor=self.base.source,
            layer=0,
            phase="slow_put_layer_0",
        )
        self._expect_exact_vector(
            "slow_put_layer_0", layer_zero_put, [self.config.page_size]
        )

        self._wait_past_lease("between_put_layers")

        layer_one_put = self._range_call(
            operation="batch_put_from_multi_buffer_ranges",
            function=self.store.batch_put_from_multi_buffer_ranges,
            key=key,
            tensor=self.base.source,
            layer=1,
            phase="slow_put_layer_1",
        )
        self._expect_exact_vector(
            "slow_put_layer_1", layer_one_put, [self.config.page_size]
        )

        put_end = self.base._call(
            "batch_put_end",
            self.store.batch_put_end,
            keys,
            phase="commit",
            keys=keys,
        )
        put_end_values = self._expect_exact_vector("slow_put_end", put_end, [0])
        if put_end_values == [0]:
            self.committed_key = key
            if key in self.base.active_put_keys:
                self.base.active_put_keys.remove(key)

        first_get_start = self.base._start_get(keys, "read_session")
        self._expect_exact_vector("committed_object_get_start", first_get_start, [0])

        layer_zero_get = self._range_call(
            operation="batch_get_into_multi_buffer_ranges",
            function=self.store.batch_get_into_multi_buffer_ranges,
            key=key,
            tensor=self.base.destination,
            layer=0,
            phase="read_layer_0",
        )
        self._expect_exact_vector(
            "read_layer_0_before_expiry",
            layer_zero_get,
            [self.config.page_size],
        )

        self._wait_past_lease("between_get_layers")

        expired_layer_one_get = self._range_call(
            operation="batch_get_into_multi_buffer_ranges",
            function=self.store.batch_get_into_multi_buffer_ranges,
            key=key,
            tensor=self.base.destination,
            layer=1,
            phase="read_layer_1_expired_session",
        )
        self._expect_exact_vector(
            "read_layer_1_old_session_lease_expired",
            expired_layer_one_get,
            [LEASE_EXPIRED],
        )

        fresh_get_start = self.base._start_get(keys, "fresh_read_session")
        self._expect_exact_vector(
            "fresh_batch_get_start_after_expiry_finds_object",
            fresh_get_start,
            [0],
        )

        recovered_layer_one_get = self._range_call(
            operation="batch_get_into_multi_buffer_ranges",
            function=self.store.batch_get_into_multi_buffer_ranges,
            key=key,
            tensor=self.base.destination,
            layer=1,
            phase="read_layer_1_fresh_session",
        )
        self._expect_exact_vector(
            "read_layer_1_with_fresh_lease",
            recovered_layer_one_get,
            [self.config.page_size],
        )
        self.base._end_get(keys, "fresh_read_session", "fresh_batch_get_end")

        self.base.dependencies.runtime.synchronize()
        source_bytes = self.base.dependencies.runtime.tensor_bytes(self.base.source)
        destination_bytes = self.base.dependencies.runtime.tensor_bytes(
            self.base.destination
        )
        self.base._record_case(
            "two_layer_data_matches_after_fresh_lease",
            source_bytes == destination_bytes,
            expected=True,
            actual=source_bytes == destination_bytes,
        )
        self.summary["semantic_result"] = {
            "slow_put_completed_after_read_ttl_gap": True,
            "old_get_session_survives_ttl": False,
            "fresh_batch_get_start_after_expiry_finds_object": True,
            "expired_session_error_code": LEASE_EXPIRED,
        }

    def cleanup_object(self) -> bool:
        if self.committed_key is None or self.base.dependencies is None:
            return True
        key = self.committed_key
        record: dict[str, Any] = {
            "step": f"MooncakeDistributedStore.remove:{key}",
            "passed": False,
        }
        try:
            result = self.store.remove(key, True)
            record["result"] = int(result)
            record["passed"] = int(result) in (0, OBJECT_NOT_FOUND)
        except Exception as exc:
            record["exception"] = f"{type(exc).__name__}: {exc}"
        self.summary["cleanup"].append(record)
        self.committed_key = None
        return bool(record["passed"])


def _new_summary(config: LeaseExpiryConfig) -> dict[str, Any]:
    smoke_config = range_api_smoke.SmokeConfig(
        output=config.output,
        num_keys=1,
        num_layers=2,
        page_size=config.page_size,
    )
    summary = range_api_smoke._new_summary(smoke_config)
    summary.update(
        {
            "test_name": "two_layer_put_gap_and_read_lease_expiry",
            "config": {
                "num_keys": 1,
                "num_layers": 2,
                "page_size": config.page_size,
                "object_size": smoke_config.object_size,
                "lease_ttl_ms": config.lease_ttl_ms,
                "wait_margin_ms": config.wait_margin_ms,
                "wait_ms": config.wait_ms,
            },
            "waits": [],
            "semantic_result": None,
        }
    )
    return summary


def execute(
    config: LeaseExpiryConfig,
    dependencies: Any | None = None,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    summary = _new_summary(config)
    smoke_config = range_api_smoke.SmokeConfig(
        output=config.output,
        num_keys=1,
        num_layers=2,
        page_size=config.page_size,
    )
    base_runner = range_api_smoke.SmokeRunner(smoke_config, summary)
    lease_runner = LeaseExpiryRunner(
        config,
        summary,
        base_runner,
        sleep_fn=sleep_fn,
        monotonic_fn=monotonic_fn,
    )
    main_passed = False
    try:
        config.validate()
        base_runner.initialize(dependencies)
        base_runner.allocate_and_register()
        lease_runner.run()
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
        object_cleanup_passed = lease_runner.cleanup_object()
        base_cleanup_passed = base_runner.cleanup()
    summary["passed"] = bool(
        main_passed and object_cleanup_passed and base_cleanup_passed
    )
    summary["finished_at_unix"] = time.time()
    return summary


def _parse_args(argv: Sequence[str] | None = None) -> LeaseExpiryConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--lease-ttl-ms", type=int, default=30_000)
    parser.add_argument("--wait-margin-ms", type=int, default=1_500)
    parser.add_argument("--page-size", type=int, default=4_096)
    args = parser.parse_args(argv)
    return LeaseExpiryConfig(
        output=args.output,
        lease_ttl_ms=args.lease_ttl_ms,
        wait_margin_ms=args.wait_margin_ms,
        page_size=args.page_size,
    )


def main(argv: Sequence[str] | None = None) -> int:
    config = _parse_args(argv)
    summary = execute(config)
    range_api_smoke._write_summary(config.output, summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
