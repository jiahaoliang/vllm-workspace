# kv-pool-layerwise-reuse Sync Log

## 2026-07-03

- Created workspace feature branch `kv-pool-layerwise-reuse`.
- Created `repos/vllm` feature branch from official `v0.20.2`.
- Created `repos/vllm-ascend` feature branch from official `v0.20.2rc1`.
- Checked out `repos/Mooncake` at bundled tag `v0.3.8.post1` for read-only dependency inspection.
- Recorded RFC and reference implementation sources for later design work.

## 2026-07-09

- Archived user-provided preliminary design `DESIGN-mooncake-layerwise-gva-put.md` as a feature snapshot for Mooncake layerwise KVPool put.
- Archived vLLM Ascend PR #11444 as the memcache layerwise KV pooling reference implementation, including a Markdown summary and raw patch.
- Archived vLLM Ascend PR #10733 as the layerwise KV pool reuse coordination target from `ader47/vllm-ascend`, including a Markdown summary and raw patch.
- Updated `references/sources.md` so the design note, PR snapshots, and patch archives are discoverable from the feature source index.

## 2026-07-14

- Established the implementation baseline: `repos/vllm` is detached at `v0.23.0` (`0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`), and `repos/vllm-ascend` is on `feature/mooncake-layerwise-kv-pool` at `b792c37d7fcf2db05111c3ce84358b1fcde6ad0f`.
- Replaced the local collaborator reference with `reference/ader47-new-memcache-layerwise`, tracking `ader47/vllm-ascend` branch `feature/new-memcache-layerwise` at `b792c37d7fcf2db05111c3ce84358b1fcde6ad0f`.
- Mirrored the collaborator branch to the personal fork as `origin/feature/new-memcache-layerwise` without changing the active `kv-pool-layerwise-reuse` baseline branch.
- Checked out `repos/vllm-ascend` to local branch `feature/new-memcache-layerwise`, tracking `origin/feature/new-memcache-layerwise`, and refreshed the workspace lock state.
- Replaced the Mooncake layerwise design snapshot with the latest authoritative HackMD document `HJGESQG4ze`, covering Client sessions, ranged transfers, Backend ABC integration, end-to-end sequencing, tests, and risks.
- Added `ascend-direct-dev/Mooncake` as the Mooncake `collaborator` remote and checked out local branch `feature/layerwise-kv-session`, tracking `collaborator/feature/layerwise-kv-session` at PR #2881 head `c1d5bf1f12b9c44a3d12601ab2fac94dd4fcc3a8`.
- Archived Mooncake PR #2881 as a WIP implementation source, including a Markdown summary and raw patch fixed to the captured head.
- Confirmed that the PR exposes all seven session/range API names and includes abnormal-session, lease-expiry, and TCP E2E coverage. Recorded the current put-end idempotency and ranged-put `config` signature mismatches as blockers for the real-wheel contract gate.
