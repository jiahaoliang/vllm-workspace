# kv-pool-layerwise-reuse Repo State

Captured At: 2026-08-04T16:40:21+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `detached:54503ecec` | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | False | Frozen main-verified validation dependency; the corrected lane passed startup and cold concurrent controls in run 20260731T064607Z |
| vllm-ascend | `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `d28c52958a30cebdb7822d56e3dbb0dbe41499bc` | False | Current merge target; exact Python source delta passed the recorded single-group full validation. Section 5.8 multi-group is deferred and remains only on published WIP `f97aed26f`; no WIP candidate has been applied to this checkout |
| Mooncake | `repos/Mooncake` | `detached:786c77ff` | `786c77ff7692bed58dd99971afef87d6b690cbe3` | False | Read-only detached checkout of Mooncake PR #2881 WIP collaborator tip 786c77ff; local feature/layerwise-kv-session remains at the prior tip |
