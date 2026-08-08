# kv-pool-layerwise-reuse Repo State

Captured At: 2026-08-09T05:23:00+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `detached:54503ecec` | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | false | Frozen main-verified validation dependency; the corrected lane passed startup and cold concurrent controls in run 20260731T064607Z |
| vllm-ascend | `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `d74269a08e48e3b5b097f9a34f5c421696ddda40` | false | Mooncake layerwise KVPool source with content-addressed initial partial loads |
| Mooncake | `repos/Mooncake` | `detached:df3f74ed` | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` | false | Read-only detached checkout of the frozen Mooncake collaborator session/range implementation with retryable local revoke ownership |

The initial Mooncake shared-buffer policy change is confined to
`layerwise_config.py`. Follow-up commits fix decode-only gating, partial snapshot
ownership, per-step load draining, decode slot loading, committed snapshot
lifetime, and initial pure-consumer partial-load key selection without changing
the public slot-release lifecycle or memcache. The final regression proves that
the first remote partial load uses the block hash instead of the process-local
Decode request ID, while later incremental Decode keeps its request-scoped
snapshot. The focused regression passed `1`, the Mooncake layer-session class
passed `26`, worker/scheduler/transfer tests passed `306`, and the complete
AscendStore suite passed `514`. Ruff, `py_compile`, and `git diff --check`
passed. Source commit `d74269a08` is clean, DCO-signed, pushed, and has
local/origin left-right `0 0`.

Generation-2 run `20260808T203742Z` created native `linux/arm64` image
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
Prior generation-1 performance evidence remains bound to `a3c97358c` and must
not be resumed.
