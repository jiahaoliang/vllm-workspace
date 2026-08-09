# kv-pool-layerwise-reuse Repo State

Captured At: 2026-08-09T14:55:41+08:00

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

Historical generation-3 source `d74269a08` used native `linux/arm64` image
`docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-d74269a0-df3f74ed-20260808T203742Z`
with manifest `sha256:3c02653463562e8bfff717e6ade962ab1a2c661de59ae9f310bc050528fa81bd`.
All eight cumulative production files match the checkout. CPU/mock gates passed
`514` AscendStore, `20` role/default, `3` model-runner, `145`
deployment/performance, and `60` performance harness tests. Real-NPU baseline,
`kv_producer`, and `kv_both` cold/warm all passed. The exact DP1 4096-token
Prefill to pure-consumer Decode canary passed with 32/32 block hits, 4095 remote
load tokens, `vllm_cached=0`, and no KV load failure. All NPU processes exited,
final Master metrics are `0/0/0`, and the 115-file evidence manifest replayed
with digest `121a11b331cffeb4d031dac21637d70c0395d83ee971b07a138e4d4f4e03f449`.
Formal performance root `/tmp/layerwise-performance-20260809T010429Z` later
failed at the first REUSE3 canary because TP1 never published layer 1's gate;
that root is diagnostic only and must not be resumed. The image and generation-3
handoff remain bound to `d74269a08` and are not valid for current source
`535555917`. A new patched image, NPU functional run, and incremented handoff are
required before restarting performance from a new root.
