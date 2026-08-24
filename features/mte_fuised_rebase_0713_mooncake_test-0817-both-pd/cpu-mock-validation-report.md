# Blockwise DSA Replacement CPU/Mock Validation Report

Validated At: 2026-08-24

## 结论

- Replacement source：vLLM-Ascend `7401ae79c11d6ec0033ea3ac39085379a0bb81ef`。
- Static：compile 和 `git diff --check` 通过；当前 delta 没有新增 ruff failure。
- Focused DSA/SFA：`47 passed`。
- 完整 `test_mooncake_connector.py`：`111 passed`。
- Broad CPU/mock regression：排除一个已知 baseline-broken 文件后 `221 passed`。
- 完整 CPU/mock root：`241 passed / 5 failed`；五项均为 pre-existing baseline test defect。
- NPU runtime：`planned / not run`。

这份报告替代 `f826ea3f` standalone subsystem 的旧验证记录。旧实现只保留为 behavior reference，不能作为当前 production、lock 或 issue closure evidence。

## Source Identity

| Item | Identity |
| --- | --- |
| Control branch | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` |
| vLLM-Ascend branch | `feature/blockwise-dsa-mooncake-v1-reimplementation` |
| vLLM-Ascend base | `0d6dd0d26ab69219f861c9b312329f4c60fe36f2` |
| Validated/published HEAD | `7401ae79c11d6ec0033ea3ac39085379a0bb81ef` |
| Locked vLLM checkout | `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` |
| Locked Mooncake checkout | `6041a609a8c3af35e778f70db344f145c2914980` (`v0.3.12.post1`) |

Published source range：

| Commit | Purpose |
| --- | --- |
| `4cd51781` | typed Blockwise DSA metadata |
| `341641d9` | parameterized SFA CPU offload capacity |
| `9612b18d` | `MooncakeConnectorV1` Blockwise DSA lifecycle |
| `3a22c5a6` | public replay/preemption tests |
| `7401ae79` | ordering、receiver queue、reservation cap 与 stale observation hardening |

五个 commit 均带 `Signed-off-by`。验证收尾后 replacement worktree clean；GitCode remote branch在 control update 前实时核对为同一 `7401ae79` SHA。

## Architecture And Budget

相对 base `0d6dd0d26` 的 production 变化只有：

- `mooncake_connector.py`：在既有 public connector/sender/receiver/worker 中加入 opt-in lifecycle；
- `mooncake_dsa_metadata.py`：唯一新增 production module，只承载 typed cross-process contract；
- `sfa_pd_cpu_offload/scheduler.py`：thin Host block capacity 参数化。

没有引入旧 `60eb76e` 的 standalone scheduler、runtime、worker、transport、rendezvous、memory 或 data-plane subsystem。

| Scope | Additions | Deletions | Approved stop line |
| --- | ---: | ---: | ---: |
| Production | 1,704 | 41 | 1,770 additions |
| Focused tests | 1,478 | 43 | 1,500 additions |

## CPU/Mock Environment

验证记录使用 `liangjiahao/vllm-ascend-ut` 专用 CPU-only Pod：

| Item | Value |
| --- | --- |
| Namespace | `liangjiahao` |
| Pod | `vllm-ascend-ut` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1` |
| Image ID | `sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57` |
| NPU resource request | none |
| Synced workspace | `/workspace/dsa-budgetA-20260824/` |

当前 vLLM/vLLM-Ascend checkout通过 tar 同步到 Pod 的临时 workspace，没有使用 hostPath。`deepseekv4_tool_parser.py`、`mooncake_connector.py` 和 `test_mooncake_connector.py` 的 Host/Pod SHA256逐项一致。

Pinned vLLM需要`gguf==0.18.0`并依赖`VLLM_VERSION=0.23.0`选择正确patch branch。CPU conftest的fake `torch_npu`缺少`__file__`且full collection会触发C++ JIT loader；验证使用repo外临时pytest bootstrap补齐该属性并stub `torch.utils.cpp_extension.load`。这些环境适配没有修改checkout，也没有加载NPU library。

## Test Results

### Focused DSA/SFA

Metadata、real `vllm.v1.core.sched.Scheduler` A2 lifecycle、affected SFA scheduler和single-rank boundary target group：

```text
47 passed, 14 warnings
```

该组包含：

- transfer-failure token-0 replay；
- real Scheduler preemption和新的 Indexer block table；
- stable Main reservation和suffix-only fused D2H；
- nonzero exact-TP `skipped_d2h_bytes` aggregation；
- reservation snapshot、stale/future result、worker ordering和cancellation boundaries。

### Connector And Default V1

完整 `tests/ut/kv_offload/test_mooncake_connector.py`：

```text
111 passed, 14 warnings
```

其中 ordering/cancellation focused selection单独复跑为`5 passed`。该target同时覆盖opt-in behavior和`dsa_pd_offload=false` default V1 isolation。

### Broad Regression

完整CPU/mock root（显式排除`a2` NPU目录）：

```text
241 passed, 5 failed, 14 warnings
```

五个failure全部来自相对replacement base零diff的`test_mooncake_to_dram_asymmetric_push.py`。该测试调用以下helpers但未import：

- `map_locals_to_indexer_pages`；
- `mooncake_to_dram_chunk_send_window`；
- `align_indexer_ids_to_local_window`。

排除这一已知baseline-failing文件后的broad regression：

```text
221 passed, 14 warnings
```

因此五项不能记录为replacement regression，也不能把完整root描述为全绿。

## Static Results

- Replacement diff中的7个Python文件bytecode compile通过，cache写入临时目录。
- `git diff --check 0d6dd0d26..7401ae79c`通过。
- `ruff==0.14.0`当前7文件为3项，HEAD baseline为5项；replacement delta没有新增lint failure。
- Current与HEAD baseline都有同样5个文件未通过`ruff format --check`，因此不声明full diff format-clean。
- 验证产生的5个ignored CPython 3.9 `.pyc`已按精确路径清理，没有递归删除用户目录。

## Evidence Boundary

当前可以声明Python contract、scheduler/worker state transition、default V1 isolation和fake transfer boundary已有static/CPU/mock evidence。

当前不能声明真实multi-node routing、Mooncake D2D/D2RH、NPU-addressable Host registration、fused kernel、cache contents、performance或八个NPU cases已验证。它们继续保持`planned / not run`；见 [NPU E2E test plan](npu-e2e-test-plan.md)。
