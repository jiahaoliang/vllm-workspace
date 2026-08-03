# kv-pool-layerwise-reuse Repo State

Captured At: 2026-08-03T20:48:10+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `detached:54503ecec` | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | False | Frozen main-verified validation dependency; the corrected lane passed startup and cold concurrent controls in run 20260731T064607Z |
| vllm-ascend | `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `d28c52958a30cebdb7822d56e3dbb0dbe41499bc` | False | 11/11 Mooncake linear integration plus post-validation fix `d28c52958`: Mooncake ranged loads retain key-major batching within each request and dispatch concurrent requests separately; source passed 478 AscendStore UT and two independent warm pair 2/3 loops at 0/120 failures each before the formal overlay rerun |
| Mooncake | `repos/Mooncake` | `detached:786c77ff` | `786c77ff7692bed58dd99971afef87d6b690cbe3` | False | Read-only detached checkout of Mooncake PR #2881 WIP collaborator tip 786c77ff; local feature/layerwise-kv-session remains at the prior tip |
