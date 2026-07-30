# kv-pool-layerwise-reuse Repo State

Captured At: 2026-07-31T01:37:56+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `detached:54503ecec` | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | False | Frozen validation dependency declared by the integrated vLLM-Ascend branch (release line v0.25.1); coordinator signature mismatch captured by terminated G0 validation |
| vllm-ascend | `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `14beaf161cca6f1e044e20529ca96c6554dbbe50` | False | Completed 11/11 Mooncake linear integration onto collaborator/kv_offload_0723 a46a1dabb; source frozen after full validation terminated at G0 on an inherited coordinator ABI mismatch |
| Mooncake | `repos/Mooncake` | `detached:786c77ff` | `786c77ff7692bed58dd99971afef87d6b690cbe3` | False | Read-only detached checkout of Mooncake PR #2881 WIP collaborator tip 786c77ff; local feature/layerwise-kv-session remains at the prior tip |
