# kv-pool-layerwise-reuse Repo State

Captured At: 2026-08-07T18:07:22+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `detached:54503ecec` | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | False | Frozen main-verified validation dependency; the corrected lane passed startup and cold concurrent controls in run 20260731T064607Z |
| vllm-ascend | `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `45b2e785b10ca4604cd6314819ed15f3ff674781` | False | Failed Mooncake revoke ownership remains pending until result-zero cleanup. CPU/mock source gate passed `495` tests; local and origin are `0 0` |
| Mooncake | `repos/Mooncake` | `detached:df3f74ed` | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` | False | Read-only frozen collaborator session/range implementation; no Mooncake branch or source modification |

Validation control tooling is frozen at
`3bda70d786db46310994afc689af4fc10da4858e`. Its direct ranged driver requires
same-key `PutStart` and cleanup to return zero after a successful revoke; the
cache-free CPU-only Pod gate passed all `84` deployment tests before G1.
