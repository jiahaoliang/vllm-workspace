# kv-pool-layerwise-reuse Repo State

Captured At: 2026-08-10T17:31:01+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `detached:54503ecec` | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | false | Frozen main-verified validation dependency; the corrected lane passed startup and cold concurrent controls in run 20260731T064607Z |
| vllm-ascend | `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `1f306620cb53076f2979a51ae533db8f1084ab26` | false | Mooncake layerwise KVPool shared-buffer reuse with TP non-save-owner gate preservation |
| Mooncake | `repos/Mooncake` | `detached:df3f74ed` | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` | false | Read-only detached checkout of the frozen Mooncake collaborator session/range implementation with retryable local revoke ownership |

The initial Mooncake shared-buffer policy change is confined to
`layerwise_config.py`. Follow-up fixes cover decode-only gating, partial snapshot
ownership, per-step load draining, decode slot loading, committed snapshot
lifetime, initial pure-consumer partial-load key selection, layout-specific row
state, and TP non-save-owner reuse gates without changing the public slot-release
lifecycle or memcache.

The seven linear commits from `e1675bb` through `535555917` were rewritten as
the single DCO-signed commit `1f306620` with parent `3a34bba9`. The old and new
tips have the identical tree
`01ef10d288deb4c13dbe4e3c4b74e0b5d482c80d`; their endpoint diff is empty,
the rewritten range contains one commit and no merges, and local/origin
left-right is `0 0`. Local recovery ref
`backup/mooncake-reuse-pre-squash-535555917` retains the old tip. This was a
history-only rewrite: no source bytes changed and no new runtime validation is
claimed for the new commit identity.

The latest two-chunk regression uses real send/receive threads and proves that
an MLA non-save-owner rank still publishes the source-layer gate required by
the next shared-buffer occupant. The deterministic test changed from `[False,
False]` to `[True, True]`; the complete AscendStore suite passed `515`, the MLA
regression passed `1`, model-runner reuse passed `3`, and deployment/performance
mocks passed `146`. Ruff, `py_compile`, and `git diff --check` passed against
the source tree now represented by `1f306620`.

The validated reusable `linux/arm64` image remains
`docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-535555917-df3f74ed-20260809T070557Z`
with manifest `sha256:cf5da7c1da7dcb72f4c22e201d628b9e4aa819f53c15711651ebc9241cb955bc`
and config `sha256:b138ce816ae0b4183f77a6e9b83bc95061a6c1053f770d2f0462699de86a7a0c`.
Its source label remains the historical pre-squash commit `535555917`; no new
image was created for the tree-equivalent squash.

Functional run `20260809T071622Z` passed the targeted TP2 4096-token REUSE3
canary with 32/32 block hits, 4095 remote load tokens, `vllm_cached=0`, all-zero
commit results, no gate timeout, and final NPU/Master cleanup. The formal
1-NPU baseline, `kv_producer`, and `kv_both` cold/warm matrix also passed with
exact response equality and 61/61 runtime steps. CPU/mock gates passed `515`
AscendStore, `20` role/default, `1` TP non-save-owner regression, `1` MLA,
`3` model-runner, `146` deployment/performance, and `61` performance harness
tests. The 158-file evidence manifest replayed with digest
`e8cf5ce3fbf332dada8c9bfeb6fd1d3ececc6f02b96fe4a0a5b28b6e1b556876`.

Performance run `20260810T043500Z` completed the five-point DP1/16384/c8
matrix with `64/64` successful formal requests per point. Full report checking,
raw and imported checksum replay, and runtime restoration passed. The runtime
evidence and image identity remain attributed to pre-squash source
`535555917`; tree equivalence permits source comparison but is not a new NPU or
performance run for `1f306620`.
