# Blockwise DSA CPU/Mock Validation Report

Validated At: 2026-08-23T02:54:10+08:00

## 结论

- Static：`PASS`。
- Phase A：`PASS`，`306 passed in 16.65s`。
- Phase B：`PASS`，`355 passed in 17.14s`。
- DSA 后普通 Mooncake V1 regression：`PASS`，`93 passed, 14 warnings in 19.31s`。
- Standalone scheduler/connector rerun：`PASS`，`43 passed in 15.27s`。
- 综合状态：`CPU/mock validated`。
- NPU runtime：`planned / not run`。本报告不提供 NPU correctness、performance、memory placement 或真实 Mooncake transfer 结论。

## Source Identity

| Item | Identity |
| --- | --- |
| Control branch | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` |
| vLLM-Ascend branch | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` |
| vLLM-Ascend base | `0d6dd0d26ab69219f861c9b312329f4c60fe36f2` |
| Validated vLLM-Ascend tree/commit | `f826ea3f354f87cdf95895addbdaaad6ca92dd7c` |
| Locked vLLM checkout | `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` (`v0.23.0`) |
| Locked Mooncake checkout | `6041a609a8c3af35e778f70db344f145c2914980` (`v0.3.12.post1`) |
| Source sync directory | `/workspace/dsa-final-4rjqdZ` |
| Changed Python files | 28 |
| Host/Pod aggregate SHA256 | `d0e39a7ea0c4f6d07c144206df8c4ef8228eb8179c9453c34c9196b949717b07` |

测试通过 tar 同步 vLLM-Ascend 当前 tree，最终同步内容与 commit `f826ea3f3` 相同。Pod 使用镜像内兼容的 vLLM Python runtime；没有把 locked vLLM checkout 的 Python tree tar 到测试目录，因此本报告不声称 locked vLLM tree 已直接执行。Mooncake native library、CANN 或 `torch_npu` runtime 未改变，也未在本 CPU-only Pod 中验证真实设备路径。

## Pod Identity

| Item | Value |
| --- | --- |
| Kubernetes context | `bke-cluster-kubernetes-admin@bke-cluster` |
| Namespace | `liangjiahao` |
| Pod | `vllm-ascend-ut` |
| Phase / Ready | `Running` / `true` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1` |
| Requests | CPU `1`, memory `4Gi` |
| Limits | CPU `16`, memory `32Gi` |
| Source volume | `emptyDir` mounted at `/workspace` |
| NPU resource request | none |
| NPU device/driver/model-cache mount | none |

该 Pod 是长期运行 CPU/mock UT Pod，不是 Prefill/Decode serving Pod。验证未申请 `huawei.com/Ascend910` 或 `huawei.com/vnpu-number`，未挂载 hostPath、NPU device、driver、`npu-smi` 或模型缓存。

## Sync 与 Identity Commands

最终覆盖 changed Python files：

```bash
tar -cf - $(git diff 0d6dd0d26ab69219f861c9b312329f4c60fe36f2 --name-only -- '*.py') | kubectl exec -i -n liangjiahao vllm-ascend-ut -- tar -xf - -C /workspace/dsa-final-4rjqdZ
```

Host aggregate checksum：

```bash
sha256sum $(git diff 0d6dd0d26ab69219f861c9b312329f4c60fe36f2 --name-only -- '*.py') | sort -k2 | sha256sum
```

Pod aggregate checksum：

```bash
git diff 0d6dd0d26ab69219f861c9b312329f4c60fe36f2 --name-only -z -- '*.py' | kubectl exec -i -n liangjiahao vllm-ascend-ut -- sh -c 'cd /workspace/dsa-final-4rjqdZ && xargs -0 sha256sum | sort -k2 | sha256sum'
```

两侧均返回：

```text
d0e39a7ea0c4f6d07c144206df8c4ef8228eb8179c9453c34c9196b949717b07  -
```

## Static Gates

| Gate | Result |
| --- | --- |
| Compile 28 changed Python files with built-in `compile()` | `PASS` |
| Non-ASCII scan over changed Python files | `PASS`，无输出 |
| Added-line 88-column scan | `PASS`，无输出 |
| `git diff --check` / staged diff check | `PASS`，无输出 |
| Ruff | `NOT AVAILABLE`；Host 无 `ruff` executable，Pod 返回 `No module named ruff` |

Compile command：

```bash
mapfile -t dsa_python_files < <(git diff 0d6dd0d26ab69219f861c9b312329f4c60fe36f2 --name-only -- '*.py')
python3 -c 'import pathlib,sys; [compile(pathlib.Path(raw).read_text(), raw, "exec") for raw in sys.argv[1:]]; print(f"compiled {len(sys.argv) - 1} changed Python files")' "${dsa_python_files[@]}"
```

输出：

```text
compiled 28 changed Python files
```

Added-line length command：

```bash
git diff 0d6dd0d26ab69219f861c9b312329f4c60fe36f2 --unified=0 -- '*.py' | awk '/^\+\+\+ b\// { file=substr($0, 7); next } /^@@ / { h=$0; sub(/^.*\+/, "", h); sub(/[, ].*$/, "", h); line=h-1; next } /^\+[^+]/ { line++; text=substr($0, 2); if (length(text) > 88) print file ":" line ":" length(text) ":" text; next } /^-/ { next } { line++ }'
```

## Phase A

Phase A 覆盖 config、typed metadata、positional data plane、transport、memory registration、worker/adapter、Prefill adapter、rendezvous、Decode runtime 与 central connector public hooks；不包含完整 cross-step scheduler/lifecycle matrix。

```bash
kubectl exec -n liangjiahao vllm-ascend-ut -- env PYTHONPATH=/workspace/dsa-final-4rjqdZ PYTHONDONTWRITEBYTECODE=1 VLLM_PLUGINS= python3 -m pytest -p no:cacheprovider --confcutdir=/workspace/dsa-final-4rjqdZ/tests/ut/kv_offload /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_config.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_metadata.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_data_plane.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_transport.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_memory.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_worker.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_worker_adapter.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_prefill_worker_adapter.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_rendezvous.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_decode_runtime.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_connector.py -q
```

```text
306 passed in 16.65s
```

## Phase B

Phase B 在 Phase A targets 上增加完整 lifecycle 与 scheduler matrix，覆盖 lifetime reservation、HOL、exact TP aggregation、failure/replay、preemption、cancellation、fused D2H、stale/duplicate/conflict/future/missing result 及 release ordering。

```bash
kubectl exec -n liangjiahao vllm-ascend-ut -- env PYTHONPATH=/workspace/dsa-final-4rjqdZ PYTHONDONTWRITEBYTECODE=1 VLLM_PLUGINS= python3 -m pytest -p no:cacheprovider --confcutdir=/workspace/dsa-final-4rjqdZ/tests/ut/kv_offload /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_config.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_metadata.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_data_plane.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_transport.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_memory.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_worker.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_worker_adapter.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_prefill_worker_adapter.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_rendezvous.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_decode_runtime.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_lifecycle.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_scheduler.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_connector.py -q
```

```text
355 passed in 17.14s
```

## Default V1 Regression

该命令在最终 Phase B 后运行，验证 flag=false 时普通 metadata、scheduler、worker、transfer 和 completion path。

```bash
kubectl exec -n liangjiahao vllm-ascend-ut -- env PYTHONPATH=/workspace/dsa-final-4rjqdZ PYTHONDONTWRITEBYTECODE=1 VLLM_PLUGINS= python3 -m pytest -p no:cacheprovider --confcutdir=/workspace/dsa-final-4rjqdZ/tests/ut/kv_offload /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_connector.py -q
```

```text
93 passed, 14 warnings in 19.31s
```

14 条 warning 均来自 `torch.jit.script_method` deprecation，不是 DSA failure。

## Standalone Scheduler/Connector Rerun

```bash
kubectl exec -n liangjiahao vllm-ascend-ut -- env PYTHONPATH=/workspace/dsa-final-4rjqdZ PYTHONDONTWRITEBYTECODE=1 VLLM_PLUGINS= python3 -m pytest -p no:cacheprovider --confcutdir=/workspace/dsa-final-4rjqdZ/tests/ut/kv_offload /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_scheduler.py /workspace/dsa-final-4rjqdZ/tests/ut/kv_offload/test_mooncake_dsa_connector.py -q
```

```text
43 passed in 15.27s
```

## 初始失败与修复

| Scope | 初始结果 | 原因 | 修复与最终状态 |
| --- | --- | --- | --- |
| Data-plane collection | collection error | CPU-only Pod 导入真实 `torch_npu`，缺少 `libascend_hal.so` | 增加 test-local CPU import guard；纳入 Phase A/B 全绿 rerun |
| Worker final `--confcutdir` run | collection error | 同上，import chain 激活 Ascend plugin | 在对应 test module 隔离 plugin/`torch_npu` import；最终全绿 |
| Config/central focused collection | collection error | 同上，locked/source import chain进入真实 `torch_npu` | 使用 test-local guard 和 `VLLM_PLUGINS=`；最终完整 Phase A/B 全绿 |
| Central focused assertion | `1 failed, 122 passed` | `packed_main_indexer_scale` 已正确 fail closed，但 test regex 未接受实际错误文本 | 修正 test oracle；最终 focused 与完整 matrix 全绿 |
| Ordinary V1 collection | collection error | 普通 test module 在 CPU-only Pod 导入真实 `torch_npu` | 增加 test-local import guard；最终 `93 passed` |
| Standalone scheduler collection | collection error | scheduler test 单独运行时触发真实 `torch_npu`；完整 matrix 曾因 config test 先安装 guard 而掩盖顺序依赖 | scheduler test 增加自己的 test-local guard；standalone `43 passed`，完整 Phase B 再次全绿 |

这些 guard 只存在于 tests，不改变 production import 或 NPU runtime 行为。`PACKED_MAIN_INDEXER_SCALE` 保持 production fail closed，因为首版不能在不 split/reformat 的条件下把 packed Main 映射为独立 Decode Host K/V。

## 结论边界

本轮可以声明：

- production source 已实现并形成 commit `f826ea3f3`；
- static gates passed；
- Phase A passed；
- Phase B passed；
- default V1 regression passed；
- `CPU/mock validated`。

本轮不能声明：

- locked vLLM Python tree 已在 Pod 直接执行；
- positional ABI 提供跨 P/D semantic compatibility proof；
- NPU runtime、真实 Mooncake D2D/D2RH、fused D2H correctness 或 performance 已验证；
- 8 个 NPU mandatory cases 已执行。

NPU runtime 的唯一当前权威状态是 [NPU E2E test plan](npu-e2e-test-plan.md) 中的 `planned / not run`。

## Cleanup

- 已精确删除 `liangjiahao/vllm-ascend-ut` 中的 `/workspace/dsa-final-4rjqdZ`；删除后路径不存在。
- 长期 CPU-only UT Pod 未删除，清理后状态为 `Running/Ready`。
- 本轮未创建 serving Deployment、ConfigMap、Mooncake service/session 或 NPU workload；NPU plan 的 final cleanup 尚未执行，仍属于 `planned / not run`。
