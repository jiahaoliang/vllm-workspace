Source: https://github.com/kvcache-ai/Mooncake/pull/2881
Captured At: 2026-07-18T19:03:20+08:00
Notes: Refreshed WIP Mooncake Client implementation for the session/range API contract used by this feature; captured at an exact head SHA because the PR is still changing.

# kvcache-ai/Mooncake PR #2881

Title: `[WIP][Store] Add put/get session APIs for ranged multi-buffer transfers`

Status at capture: open, not draft, mergeable_state=`clean`

Author: `ascend-direct-dev`

Head: `ascend-direct-dev/Mooncake` branch `feature/layerwise-kv-session` at
`74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5`

Base: `kvcache-ai/Mooncake` branch `main` at
`9c6fc51339a60411c2e7cd40133f76f6044dbe57`

Created: 2026-07-13T12:09:42Z

Updated: 2026-07-15T10:04:13Z

Diff size: 1 commit, 11 files, +1493 / -5

Patch archive: `../patches/pr-2881-mooncake-layerwise-session-ranges.patch`
(original five-commit capture; retained because the refreshed squash head has
the same source tree)

## Why It Matters Here

This PR is the current Mooncake-side implementation for the cross-team API
contract in `features/kv-pool-layerwise-reuse/implementation-plan.md`. It adds
put/get sessions, key-major ranged multi-buffer transfers, cached replica and
lease state, Python bindings, abnormal-session tests, and a TCP E2E path.

The PR is WIP and is an integration input, not a stable baseline. The workspace
records the exact head SHA so later PR updates can be reviewed and deliberately
adopted. This head is a squash rewrite of the previous five-commit head
`c1d5bf1f12b9c44a3d12601ab2fac94dd4fcc3a8`; both commits have tree
`d87b3b50d223054225157db7add0b11e23f0eaef`, so the refresh changes provenance
but not source behavior.

## Implemented Contract Surface

- `batch_put_start(keys, sizes, config)` reserves objects and opens put sessions.
- `batch_put_from_multi_buffer_ranges(keys, buffers, sizes, dst_offsets)` writes
  object-byte ranges without repeating the Master allocation lookup.
- `batch_put_end(keys)` completes objects and clears put sessions.
- `batch_put_revoke(keys)` revokes incomplete objects and clears put sessions.
- `batch_get_start(keys)` resolves replicas and caches get-session metadata.
- `batch_get_into_multi_buffer_ranges(keys, buffers, sizes, src_offsets)` reads
  object-byte ranges from cached get sessions.
- `batch_get_end(keys)` clears get sessions and returns one control status.
- `TransferWriteRange` and matching read-range plumbing are implemented below
  the Client APIs.

## Test Coverage Present in the PR

- Multi-key, multi-layer ranged put/get with exact byte comparison.
- Revoke-before-end and missing-session behavior.
- Duplicate put start, input-shape mismatch, and object-range overflow.
- Get lease expiry with local session removal and no range-time Master refresh.
- TCP E2E for put start, per-layer ranged writes, put end, get start, per-layer
  ranged reads, get end, data comparison, and revoke.

## WIP Contract Gaps to Close Before Integration

- The current abnormal-session test expects a second `batch_put_end` to return
  `INVALID_PARAMS`. The implementation plan requires put-end idempotency, so the
  real-wheel contract gate must remain blocked until the PR and final contract
  agree.
- The current Python binding for `batch_put_from_multi_buffer_ranges` accepts
  keys, buffers, sizes, and offsets, but not the optional `ReplicateConfig`
  required by the frozen contract signature. Align the PR or explicitly revise
  the authoritative contract before passing the API gate.
- The PR is currently reported as mergeable with `mergeable_state=clean`, but
  unit/E2E presence is not equivalent to a validated target wheel. Record the
  built wheel version/commit and executed results at Task 5.
- Any later PR head must be fetched, reviewed, and recorded before updating the
  workspace lock; do not silently follow the floating branch.

## Changed Files

| File | Status | + | - |
| --- | --- | ---: | ---: |
| `mooncake-integration/store/store_py.cpp` | modified | 104 | 0 |
| `mooncake-store/include/client_service.h` | modified | 57 | 0 |
| `mooncake-store/include/pyclient.h` | modified | 50 | 0 |
| `mooncake-store/include/real_client.h` | modified | 42 | 0 |
| `mooncake-store/include/transfer_task.h` | modified | 8 | 0 |
| `mooncake-store/src/client_service.cpp` | modified | 196 | 4 |
| `mooncake-store/src/real_client.cpp` | modified | 435 | 0 |
| `mooncake-store/src/transfer_task.cpp` | modified | 58 | 1 |
| `mooncake-store/tests/e2e/run_session_ranges_tcp_e2e.sh` | added | 77 | 0 |
| `mooncake-store/tests/e2e/session_ranges_tcp_e2e.py` | added | 152 | 0 |
| `mooncake-store/tests/pybind_client_test.cpp` | modified | 314 | 0 |

## Commits Captured

- `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` - `[WIP][Store] Add put/get session APIs for ranged multi-buffer transfers`
