# kv-pool-layerwise-reuse Repo State

Captured At: 2026-08-04T13:00:16+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `detached:54503ecec` | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | False | Frozen main-verified validation dependency; the corrected lane passed startup and cold concurrent controls in run 20260731T064607Z |
| vllm-ascend | `repos/vllm-ascend` | `wip/mooncake-review-findings-d28c529` | `f97aed26f25a3427f20bdb7587b720dd6ef25bbf` | False | Independent five-commit WIP implementing SP1/SP2/ST1-ST5 on the reviewed `d28c52958` tree: CPU/mock `534 passed`, Ruff/format/py_compile/diff/history gates passed; real Mooncake/NPU ranged benchmark remains unrun; origin publication is blocked because the configured GitHub token authenticates an account without write permission to `jiahaoliang/vllm-ascend` |
| Mooncake | `repos/Mooncake` | `detached:786c77ff` | `786c77ff7692bed58dd99971afef87d6b690cbe3` | False | Read-only detached checkout of Mooncake PR #2881 WIP collaborator tip 786c77ff; local feature/layerwise-kv-session remains at the prior tip |
