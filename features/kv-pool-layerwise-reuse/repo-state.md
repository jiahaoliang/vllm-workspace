# kv-pool-layerwise-reuse Repo State

Captured At: 2026-08-08T19:27:48+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `detached:54503ecec` | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | false | Frozen main-verified validation dependency; the corrected lane passed startup and cold concurrent controls in run 20260731T064607Z |
| vllm-ascend | `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `1829639a1e019d3ed34055787febc7ee89fb0f68` | false | Mooncake layerwise KVPool source with separate full-prefix/HBM-tail shared load metadata; source and focused clean-commit gates passed |
| Mooncake | `repos/Mooncake` | `detached:df3f74ed` | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` | false | Read-only detached checkout of the frozen Mooncake collaborator session/range implementation with retryable local revoke ownership |

The initial Mooncake shared-buffer policy change is confined to
`layerwise_config.py`. Follow-up commits fix decode-only gating, partial snapshot
ownership, per-step load draining, decode slot loading, and committed snapshot
lifetime without changing the public slot-release lifecycle or memcache.
Final focused seams passed `9`, the complete AscendStore suite plus the exact
MLA regression passed `513`, and the expanded layerwise config plus cache-layout
model-runner set passed `30`. Deployment/performance mocks passed `129`, the
performance harness passed `44`, and Ruff, `py_compile`, and `git diff --check`
passed. Source commit `1829639a1` is clean, DCO-signed,
pushed, and has local/origin left-right `0 0`. Its new regression separately
shares full-prefix and HBM-tail Mooncake load metadata. Formal real-NPU
functional acceptance for `kv_producer` and `kv_both` remains pending under
run `20260808T111904Z`.
