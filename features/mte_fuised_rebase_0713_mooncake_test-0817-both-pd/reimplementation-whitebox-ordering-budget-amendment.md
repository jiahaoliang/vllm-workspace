# Blockwise DSA replacement ordering implementation budget amendment

状态：已批准并用于sync replacement的历史budget/evidence；`1770/1500` stop lines与source/test授权不延伸到async delta

## 1. 为什么再次停审

已批准的
[`reimplementation-whitebox-ordering-amendment.md`](./reimplementation-whitebox-ordering-amendment.md)
把相对 base `0d6dd0d26ab69219f861c9b312329f4c60fe36f2` 的 stop line修订为 production
`1,770` additions、focused tests `1,460` additions。当前 source HEAD仍为
`3a22c5a6d697250dbf942354bfdac1781af3077d`；未 commit的 approved implementation delta
完成首轮 TDD 后，完整 `git diff --numstat <base>` 为：

| 范围 | Additions | Deletions | Stop line | 结果 |
|---|---:|---:|---:|---|
| Production | 1,704 | 41 | 1,770 | 低于门槛66行 |
| Focused tests | 1,478 | 43 | 1,460 | 超过门槛18行 |

本轮 worktree delta本身是 production `+129/-97`、focused tests `+165/-7`；由于其中删除
和替换了base diff中已有的added lines，相对base的最终净变化是 production additions
`+34`、focused-test additions `+158`。此前批准的保守 final estimate是 production
`1,723-1,765`、focused tests `1,396-1,457`；production低于估算，focused tests比估算
上限多21行。

超出的 test code全部位于既有
`tests/ut/kv_offload/test_mooncake_connector.py` public connector/worker seam，没有新增 test
module、private framework或product contract。主要增量来自：

- reservation截断与released/stale result observation；
- receiver queue延迟执行、per-peer branch和error callback；
- receive与FUSED_D2H overlap fail-closed；
- `QUIESCE` publish/completion deterministic reentrancy；
- ordinary completion在drain交错中不丢ack。

这些是已批准行为的直接 evidence，不应仅为满足数字删除或压缩。

## 2. 已完成实现与TDD evidence

当前未提交实现仍限定在批准的两个文件：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`；
- `tests/ut/kv_offload/test_mooncake_connector.py`。

已取得以下真实 red到green：

- reservation未截断时大请求被capacity gate拒绝；修复后按`max_model_len`得到两块Main
  reservation；
- stale/released result原先无bounded observation；修复后调用`logger.warning_once()`再忽略；
- DSA receive原先在`add_dsa_request()`中直接submit；修复后先进入现有receiver
  `request_queue`，再由per-peer handler执行；
- blocked receive期间的newer replay原先进入generic pending；修复后立即fail closed；
- ordinary ack原先可在`update(); clear()`交错中永久丢失`request-2`；修复后atomic queue
  drain一次取得两个request并保持once语义。

CPU/mock Pod `liangjiahao/vllm-ascend-ut` 已通过：

- 完整 `test_mooncake_connector.py`：`111 passed, 14 warnings`；
- ordering/cancellation focused cases：`5 passed`。

更广suite尚未形成通过或失败证据：直接collection会加载真实`torch_npu`并缺少
`libascend_hal.so`；启用`tests/ut` CPU mock后，当前matching vLLM checkout又缺少已注册的
`vllm.tool_parsers.deepseekv4_tool_parser`。该环境兼容问题尚未继续处理，因为预算门槛先触发。
NPU状态保持`planned / not run`。

## 3. 推荐方案A：只修订focused-test stop line

保持 production stop line `1,770`，把 focused-test stop line从`1,460`修订为`1,500`。

`1,500`是stop-and-review threshold，不是quota；相对当前`1,478`保留22行，只用于更广
CPU/mock验证发现的、仍属于现有allowlist和accepted contract的必要修正。它不授权新增
production/test module、public interface、completion mailbox、generic pending queue、vLLM core
修改或任何已排除的lifecycle contract。

批准后继续顺序为：

1. 解决匹配vLLM checkout的CPU/mock collection环境，不修改vLLM core；
2. 重跑metadata、A2 lifecycle、affected SFA、完整`tests/ut/kv_offload`和default V1 regression；
3. 运行ruff/format、AST/compile与`git diff --check`；
4. 再次计算完整budget并分别报告static、CPU/mock、default V1、multi-node与NPU evidence；
5. 展示最终diff、tests、残余风险和staging allowlist，继续等待commit/push批准。

## 4. 不推荐方案B：保持1,460并压缩至少18行

可以通过合并setup或压缩assertion机械减少行数，但不会减少production complexity，也不会增加
correctness evidence。当前新增cases分别覆盖不同的approved failure/ordering boundary；在没有
等价替代证据前删除它们违反原amendment的“不以压缩可读性或删除必要tests满足数字”要求。

## 5. 批准边界

用户于 2026-08-24 明确批准方案A：focused-test stop line修订为`1,500`，并恢复现有
allowlist内的source/test必要修正和CPU/mock验证。NPU、commit、push、
`workspace.lock.json`、repo-state、issues和final feature status仍不授权。

## 6. Post-approval validation evidence

本节记录方案A批准后的实际验证，不表示release closure或NPU completion。

### 6.1 Source与环境身份

- vLLM-Ascend replacement branch：`feature/blockwise-dsa-mooncake-v1-reimplementation`；
  source HEAD `3a22c5a6d697250dbf942354bfdac1781af3077d`，仅allowlist内两个文件dirty；
- vLLM pinned checkout：`0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`，branch
  `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd`，clean；
- CPU/mock Pod：`liangjiahao/vllm-ascend-ut`，无NPU resource；image
  `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1`，
  image ID `sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57`；
- current checkouts通过tar同步到`/workspace/dsa-budgetA-20260824/`，没有hostPath；
  `deepseekv4_tool_parser.py`、`mooncake_connector.py`和`test_mooncake_connector.py`的
  host/Pod SHA256逐项一致；
- pinned vLLM源码需要`gguf==0.18.0`，仅安装到本轮`deps-min`临时目录；显式设置
  `VLLM_VERSION=0.23.0`，避免镜像旧installed metadata错误选择patch分支；
- 仓库CPU conftest的fake`torch_npu`缺少`__file__`且full collection会触发C++ JIT loader；
  使用repo外临时pytest bootstrap补`__file__`并stub `torch.utils.cpp_extension.load`，不修改
  checkout、不加载NPU library、不把结果解释为NPU evidence。

### 6.2 CPU/mock results

- Metadata、real Scheduler A2 mock lifecycle、SFA scheduler和single-rank boundary：
  `47 passed, 14 warnings`；其中包含transfer-failure token-0 replay、real scheduler
  preemption、new Indexer ownership、stable Main reservation与suffix-only D2H evidence；
- 完整`tests/ut/kv_offload` CPU root（显式排除`a2` NPU目录）：
  `241 passed, 5 failed, 14 warnings`；
- 5个failure全部来自相对replacement base零diff的
  `test_mooncake_to_dram_asymmetric_push.py`：测试调用
  `map_locals_to_indexer_pages`、`mooncake_to_dram_chunk_send_window`和
  `align_indexer_ids_to_local_window`但未import，属于pre-existing baseline test defect；
- 排除该一个已知baseline-failing文件后的broad regression：
  `221 passed, 14 warnings`；
- 同一pinned-vLLM环境复跑完整`test_mooncake_connector.py`为
  `111 passed, 14 warnings`；ordering/cancellation focused cases为`5 passed`。

### 6.3 Static与budget

- 7个replacement diff Python文件bytecode compile通过，cache重定向到临时目录；
- `git diff --check <base>`通过；worktree中精确识别的5个ignored CPython 3.9 `.pyc`已逐文件
  删除，没有递归删除用户目录；
- `ruff==0.14.0`与repo pre-commit版本一致。当前7文件lint为3项，HEAD baseline为5项；
  当前没有新增lint failure。Current与HEAD baseline均有同样5个文件触发
  `ruff format --check`，因此replacement全diff尚不能声明ruff clean；未扩大allowlist做全文件
  机械格式化；
- final budget仍为production `1,704 additions / 41 deletions`、focused tests
  `1,478 additions / 43 deletions`，分别低于已批准`1,770/1,500` stop lines。

NPU、真实multi-node transfer、D2D、D2RH、NPU-addressable Host registration、fused kernel、
cache contents和performance均为`planned / not run`。本节不授权commit、push或control-repo
final update。
