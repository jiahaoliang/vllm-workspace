# kv-pool-layerwise-reuse Repo State

Captured At: 2026-07-31T19:56:19+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `detached:54503ecec` | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | False | Frozen main-verified validation dependency; the corrected lane passed startup and cold concurrent controls in run 20260731T064607Z |
| vllm-ascend | `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `14beaf161cca6f1e044e20529ca96c6554dbbe50` | False | Completed 11/11 Mooncake linear integration onto collaborator/kv_offload_0723 a46a1dabb; frozen source passed UT, G0, G1, lease, and G4 before validation terminated on a concurrent warm layerwise KV-load defect |
| Mooncake | `repos/Mooncake` | `detached:786c77ff` | `786c77ff7692bed58dd99971afef87d6b690cbe3` | False | Read-only detached checkout of Mooncake PR #2881 WIP collaborator tip 786c77ff; local feature/layerwise-kv-session remains at the prior tip |
