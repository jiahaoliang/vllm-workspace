# kv-pool-layerwise-reuse Repo State

Captured At: 2026-08-09T04:33:51+08:00

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
local/origin left-right `0 0`. A new image and generation-2 functional
acceptance are pending; prior generation-1 performance evidence remains bound
to `a3c97358c` and must not be resumed.
