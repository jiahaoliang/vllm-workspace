# kv-pool-layerwise-reuse Repo State

Captured At: 2026-08-08T12:19:29+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `detached:54503ecec` | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | false | Frozen main-verified validation dependency; the corrected lane passed startup and cold concurrent controls in run 20260731T064607Z |
| vllm-ascend | `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `2770cd3ae66522c2eccb1c568889a55137836c0d` | false | Mooncake layerwise KVPool source with compute-side shared-buffer reuse for save-capable Mooncake roles; CPU/mock source gates passed 504 AscendStore tests |
| Mooncake | `repos/Mooncake` | `detached:df3f74ed` | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` | false | Read-only detached checkout of the frozen Mooncake collaborator session/range implementation with retryable local revoke ownership |

The Mooncake shared-buffer change is confined to `layerwise_config.py`. Focused
role/default tests passed `20`, the complete AscendStore CPU/mock suite passed
`504`, the existing model-runner reuse targets passed `2`, and Ruff,
`py_compile`, and `git diff --check` passed. Source commit `2770cd3ae` is clean,
DCO-signed, pushed, and has local/origin left-right `0 0`. Real NPU functional
validation for `kv_producer` and `kv_both` remains in progress under run
`20260808T042014Z`.
