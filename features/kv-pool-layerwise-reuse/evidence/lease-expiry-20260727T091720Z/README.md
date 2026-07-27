# Layerwise Read Lease Expiry Evidence

Formal run `20260727T091720Z` passed against the retained Ascend/Mooncake
deployment. The exact plan is archived as `lease-expiry-validation-plan.md`.

## Hard Gates

| Phase | API | Actual |
| --- | --- | ---: |
| slow put | `batch_put_start` | `[0]` |
| layer 0 put | `batch_put_from_multi_buffer_ranges` | `[4096]` |
| wait between puts | monotonic elapsed | `31500.155ms` |
| layer 1 put | `batch_put_from_multi_buffer_ranges` | `[4096]` |
| commit | `batch_put_end` | `[0]` |
| open read session | `batch_get_start` | `[0]` |
| layer 0 read | `batch_get_into_multi_buffer_ranges` | `[4096]` |
| wait within get session | monotonic elapsed | `31500.097ms` |
| layer 1 read, same session | `batch_get_into_multi_buffer_ranges` | `[-707]` |
| open fresh read session | `batch_get_start` | `[0]` |
| layer 1 read, fresh session | `batch_get_into_multi_buffer_ranges` | `[4096]` |
| close fresh session | `batch_get_end` | `0` |

The first `batch_get_start` occurred after `batch_put_end`; there was no
pre-commit get or staging-miss oracle. `-707 LEASE_EXPIRED` came only from the
layer 1 ranged read on the get session opened before the second 31.5-second
wait.

The recovered two-layer destination matched the source byte for byte. All
cleanup gates passed: the temporary key was removed, both NPU buffers were
unregistered, and the Mooncake client closed.

## Metrics Delta

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| `master_batch_put_start_requests_total` | 47 | 48 | +1 |
| `master_batch_put_end_requests_total` | 45 | 46 | +1 |
| `master_batch_get_replica_list_requests_total` | 71 | 73 | +2 |
| `master_batch_get_replica_list_failures_total` | 2 | 2 | 0 |
| `master_remove_requests_total` | 1 | 2 | +1 |
| `master_put_start_discard_cnt` | 0 | 0 | 0 |
| `master_put_start_release_cnt` | 0 | 0 | 0 |
| `master_allocated_bytes` | 0 | 0 | 0 |

Exactly two Master get queries occurred: the initial committed-object session
and the fresh recovery session. The expired ranged read used the client-cached
session deadline and did not issue or fail a new Master query.

## Environment

- Master argument: `--default_kv_lease_ttl=30s`.
- Object: one 8 KiB key, two 4 KiB layer ranges.
- Waits: `lease_ttl_ms + 1500ms`, measured with a monotonic clock.
- Control repo HEAD: `bb0c9641e3e04d6b95afbf550f9b2039b4b1e41a` plus the
  archived uncommitted test source.
- vLLM-Ascend: `3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6`.
- Mooncake: `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5`.
- Device: `Ascend910B4`, logical NPU 0 in the retained Prefill Pod.
- vLLM engines remained stopped; Master and Proxy remained Ready and no Pod
  restarted.

## Artifacts

- `summary.json`: authoritative API order, results, waits, cases, and cleanup.
- `runtime.log`: complete client output and printed summary.
- `unit-tests.log`: full deployment suite result (`50 passed`).
- `lease-expiry-validation-plan.md`: exact formal plan.
- `lease-expiry-test.py`, `range-api-smoke.py`: exact executed sources.
- `master-before.metrics`, `master-after.metrics`: metrics snapshots.
- `master-window.log`: Master log lines added during the run.
- `master-deployment.yaml`, `prefill-pod.yaml`: runtime configuration.
- `pods-final.txt`, `prefill-final-ps.txt`: final cluster/process state.
- `control-head.txt`, `vllm-ascend-head.txt`, `mooncake-head.txt`: source IDs.
- `SHA256SUMS`: checksums for every other evidence file.

The human-readable result and replay commands are in
[`lease-expiry-validation-2026-07-27.md`](../../lease-expiry-validation-2026-07-27.md).
