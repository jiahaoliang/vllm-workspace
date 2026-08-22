# Blockwise DSA PD Offload Status

Updated At: 2026-08-23T02:54:10+08:00

| Area | Status | Evidence |
| --- | --- | --- |
| Issues 01-07 | `resolved` | [Issue map](map.md) |
| Production source | committed locally | vLLM-Ascend `f826ea3f354f87cdf95895addbdaaad6ca92dd7c` |
| Static | `PASS` | [CPU/mock report](cpu-mock-validation-report.md) |
| Phase A | `PASS` | `306 passed in 16.65s` |
| Phase B | `PASS` | `355 passed in 17.14s` |
| Default V1 regression | `PASS` | `93 passed, 14 warnings in 19.31s` |
| CPU/mock | `validated` | Host/Pod aggregate SHA256 matched |
| NPU runtime | `planned / not run` | [8-case plan](npu-e2e-test-plan.md) |
| vLLM-Ascend publish | blocked | no GitCode credential in current environment |
| Cross-machine restore | blocked | source commit is not fetchable until GitCode push succeeds |

Control repo 和 vLLM-Ascend 都保留在各自 feature branch。vLLM 与 Mooncake checkout clean；validation 临时目录 `/workspace/dsa-final-4rjqdZ` 已删除，长期 CPU-only UT Pod 保留且为 `Running/Ready`。
