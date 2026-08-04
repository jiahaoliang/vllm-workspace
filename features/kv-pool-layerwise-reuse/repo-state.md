# kv-pool-layerwise-reuse Repo State

Captured At: 2026-08-04T22:50:21+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `detached:54503ecec` | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | False | Frozen main-verified validation dependency; the corrected lane passed startup and cold concurrent controls in run 20260731T064607Z |
| vllm-ascend | `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7` | False | Current merge target after a history-only 16-to-8 functional squash. Tree `ca363697034538b86626517066940315283ac8ad` exactly matches `d5f0ea7f8`; run `20260804T103209Z` remains the immutable full-validation evidence for that tree. Section 5.8 multi-group remains deferred and excluded |
| Mooncake | `repos/Mooncake` | `detached:786c77ff` | `786c77ff7692bed58dd99971afef87d6b690cbe3` | False | Read-only detached checkout of Mooncake PR #2881 WIP collaborator tip 786c77ff; local feature/layerwise-kv-session remains at the prior tip |
