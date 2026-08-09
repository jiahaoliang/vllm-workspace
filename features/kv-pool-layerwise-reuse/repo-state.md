# kv-pool-layerwise-reuse Repo State

Captured At: 2026-08-09T16:05:01+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `detached:54503ecec` | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | false | Frozen main-verified validation dependency; the corrected lane passed startup and cold concurrent controls in run 20260731T064607Z |
| vllm-ascend | `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `5355559175f9998f5d70866734fb79569dfc86f9` | false | Mooncake layerwise KVPool source with TP non-save-owner gate preservation |
| Mooncake | `repos/Mooncake` | `detached:df3f74ed` | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` | false | Read-only detached checkout of the frozen Mooncake collaborator session/range implementation with retryable local revoke ownership |

The initial Mooncake shared-buffer policy change is confined to
`layerwise_config.py`. Follow-up commits fix decode-only gating, partial snapshot
ownership, per-step load draining, decode slot loading, committed snapshot
lifetime, initial pure-consumer partial-load key selection, and TP non-save-owner
reuse gates without changing the public slot-release lifecycle or memcache. The
latest two-chunk regression uses real send/receive threads and proves that an
MLA non-save-owner rank still publishes the source-layer gate required by the
next shared-buffer occupant. The deterministic test changed from `[False,
False]` to `[True, True]`; the complete AscendStore suite passed `515`, the MLA
regression passed `1`, model-runner reuse passed `3`, and deployment/performance
mocks passed `146`. Ruff, `py_compile`, and `git diff --check` passed. Source
commit `535555917` is clean, DCO-signed, pushed, and has local/origin left-right
`0 0`.

Current source uses native `linux/arm64` image
`docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-535555917-df3f74ed-20260809T070557Z`
with manifest `sha256:cf5da7c1da7dcb72f4c22e201d628b9e4aa819f53c15711651ebc9241cb955bc`
and config `sha256:b138ce816ae0b4183f77a6e9b83bc95061a6c1053f770d2f0462699de86a7a0c`.
It is an eight-file cumulative patch of the frozen `45b2e785` base using
`nerdctl commit`; all filesystem layers are unchanged by the subsequent OCI
metadata correction and every in-image file hash matches the checkout.

Functional run `20260809T071622Z` passed the targeted TP2 4096-token REUSE3
canary with 32/32 block hits, 4095 remote load tokens, `vllm_cached=0`, all-zero
commit results, no gate timeout, and final NPU/Master cleanup. The formal
1-NPU baseline, `kv_producer`, and `kv_both` cold/warm matrix also passed with
exact response equality and 61/61 runtime steps. CPU/mock gates passed `515`
AscendStore, `20` role/default, `1` TP non-save-owner regression, `1` MLA,
`3` model-runner, `146` deployment/performance, and `61` performance harness
tests. The 158-file evidence manifest replayed with digest
`e8cf5ce3fbf332dada8c9bfeb6fd1d3ececc6f02b96fe4a0a5b28b6e1b556876`.

Formal performance root `/tmp/layerwise-performance-20260809T010429Z` remains
diagnostic only and must not be resumed. The committed generation-3 handoff is
still bound to `d74269a08`; it must be replaced by a generation-4 handoff-only
child commit before performance restarts from a new root.
