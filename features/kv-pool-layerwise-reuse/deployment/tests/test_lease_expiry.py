from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


DEPLOYMENT_DIR = Path(__file__).resolve().parents[1]
LEASE_TEST_PATH = DEPLOYMENT_DIR / "lease-expiry-test.py"
RANGE_TEST_PATH = Path(__file__).with_name("test_range_api_smoke.py")


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lease_expiry = _load_module("lease_expiry_test", LEASE_TEST_PATH)
range_test = _load_module("lease_range_test_helpers", RANGE_TEST_PATH)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeLeaseStore(range_test.FakeStore):
    def __init__(self, runtime, events, clock: FakeClock, lease_ttl_ms: int) -> None:
        super().__init__(runtime, events)
        self.clock = clock
        self.lease_ttl_seconds = lease_ttl_ms / 1_000
        self.get_deadlines: dict[str, float] = {}

    def batch_get_start(self, keys: list[str]) -> list[int]:
        self.calls.append(("get_start", (keys,)))
        results = []
        for key in keys:
            if key in self.put_sessions:
                results.append(-703)
            elif key not in self.objects:
                results.append(lease_expiry.OBJECT_NOT_FOUND)
            else:
                self.get_sessions.add(key)
                self.get_deadlines[key] = self.clock.monotonic() + self.lease_ttl_seconds
                results.append(0)
        return results

    def batch_get_into_multi_buffer_ranges(
        self,
        keys: list[str],
        all_buffers: list[list[int]],
        all_sizes: list[list[int]],
        all_offsets: list[list[int]],
    ) -> list[int]:
        results: list[int] = []
        for index, key in enumerate(keys):
            if key in self.get_sessions and self.clock.monotonic() >= self.get_deadlines[key]:
                self.get_sessions.discard(key)
                self.get_deadlines.pop(key, None)
                results.append(lease_expiry.LEASE_EXPIRED)
                continue
            result = super().batch_get_into_multi_buffer_ranges(
                [key],
                [all_buffers[index]],
                [all_sizes[index]],
                [all_offsets[index]],
            )
            results.extend(result)
        return results

    def batch_get_end(self, keys: list[str]) -> int:
        for key in keys:
            self.get_deadlines.pop(key, None)
        return super().batch_get_end(keys)

    def remove(self, key: str, force: bool = False) -> int:
        del force
        if key not in self.objects:
            return lease_expiry.OBJECT_NOT_FOUND
        del self.objects[key]
        return 0


class TestLeaseExpiry(unittest.TestCase):
    def test_long_put_gap_and_expired_read_session_have_distinct_results(self) -> None:
        clock = FakeClock()
        events: list[str] = []
        runtime = range_test.FakeRuntime(events)
        engine = range_test.FakeTransferEngine(events)
        store = FakeLeaseStore(runtime, events, clock, lease_ttl_ms=50)
        dependencies = lease_expiry.range_api_smoke.Dependencies(
            runtime,
            engine,
            store,
            "10.0.0.8",
        )
        config = lease_expiry.LeaseExpiryConfig(
            output="/tmp/not-written-by-unit-test.json",
            lease_ttl_ms=50,
            wait_margin_ms=10,
            page_size=8,
        )

        with mock.patch.dict(
            os.environ,
            {"MOONCAKE_MASTER": "mooncake-master-service:30089"},
            clear=True,
        ):
            summary = lease_expiry.execute(
                config,
                dependencies,
                sleep_fn=clock.sleep,
                monotonic_fn=clock.monotonic,
            )

        self.assertTrue(summary["passed"], summary["errors"])
        cases = {case["name"]: case for case in summary["cases"]}
        self.assertEqual(cases["slow_put_layer_1"]["actual"], [8])
        self.assertEqual(
            cases["read_layer_1_old_session_lease_expired"]["actual"],
            [lease_expiry.LEASE_EXPIRED],
        )
        self.assertEqual(
            cases["fresh_batch_get_start_after_expiry_finds_object"]["actual"],
            [0],
        )
        self.assertEqual(
            summary["semantic_result"],
            {
                "slow_put_completed_after_read_ttl_gap": True,
                "old_get_session_survives_ttl": False,
                "fresh_batch_get_start_after_expiry_finds_object": True,
                "expired_session_error_code": lease_expiry.LEASE_EXPIRED,
            },
        )
        calls = [
            (call["operation"], call["phase"])
            for call in summary["api_calls"]
            if call["operation"].startswith("batch_")
        ]
        put_end_index = calls.index(("batch_put_end", "commit"))
        first_get_start_index = calls.index(("batch_get_start", "read_session"))
        self.assertGreater(first_get_start_index, put_end_index)
        self.assertFalse(
            any(operation == "batch_get_start" for operation, _ in calls[:put_end_index])
        )
        self.assertEqual(len(summary["waits"]), 2)
        self.assertEqual(summary["cleanup"][0]["result"], 0)

    def test_config_rejects_nonpositive_ttl_and_margin(self) -> None:
        with self.assertRaisesRegex(ValueError, "lease-ttl"):
            lease_expiry.LeaseExpiryConfig("out.json", lease_ttl_ms=0).validate()
        with self.assertRaisesRegex(ValueError, "wait-margin"):
            lease_expiry.LeaseExpiryConfig("out.json", wait_margin_ms=0).validate()


if __name__ == "__main__":
    unittest.main()
