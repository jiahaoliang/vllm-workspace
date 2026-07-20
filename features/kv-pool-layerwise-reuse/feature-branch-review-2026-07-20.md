# Mooncake Layerwise KV Pool Feature Branch 整体检视

Captured At: 2026-07-20

## 检视范围

- vLLM Ascend feature branch：`feature/mooncake-layerwise-kv-pool`
- feature HEAD：`1c75b507fe268b91a6f4183da0ae6221ffd05568`
- review fixed point：`upstream/main`
- review 时 `upstream/main`：`bb474a6a94a999d54a5a6c54663bce70502d7aad`
- feature merge-base：`9dcbeaa2ad36bf96789a7f039d11d7cadaf1c384`
- Mooncake collaborator branch：`feature/layerwise-kv-session`
- Mooncake collaborator HEAD：`74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5`
- 权威设计：
  `features/kv-pool-layerwise-reuse/references/snapshots/design-mooncake-layerwise-gva-put.md`

本轮使用 `git diff upstream/main...HEAD` 检视 vLLM Ascend 的 9 个 feature
commits，并对当前锁定的 Mooncake collaborator source 进行 contract 复核。检视重点：

1. feature 是否对原有 memcache 路径造成 breaking change；
2. 整体实现是否 100% 符合权威设计文档；
3. Standards 与测试证据是否达到合入要求。

## 总结论

当前结论是：**存在 memcache 兼容性收缩，且不能认定为 100% 符合设计文档。**

支持范围内的 `backend=memcache + use_layerwise=true + TP-only` 正常路径，在静态
检视与 CPU mock UT 中未发现确认回归。但是，非 TP topology 已从“允许启动”改为
fail-fast；公共 layerwise load timeout 还引入了潜在的永久等待。设计符合性方面，
Mooncake contract、memcache alloc failure filtering、线程职责和真实运行验证均有未闭环
项。

## Memcache 兼容性 Findings

### MC1：非 TP topology 被拒绝

- 严重级别：Medium
- 类型：确认的 breaking change；刻意的 correctness guard
- 状态：不采纳；该 breaking change 是 intentional boundary
- 代码：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py:39`
- 入口：connector、scheduler、worker 均调用
  `validate_block_key_layerwise_topology(...)`。
- 行为：`backend=memcache`、`use_layerwise=true` 时，只要 PP、PCP、DCP 任一个大于
  `1`，初始化立即抛 `ValueError`。
- 影响：此前配置可以启动；当前配置面被明确缩小。canonical block key 不编码这些
  rank 坐标，因此 fail-fast 能阻止潜在 key collision，但它仍属于兼容性破坏。
- 测试：connector、scheduler、worker 均有拒绝非 TP topology 的 UT。
- 设计关系：权威设计 §5.1/§5.3 要求保留 memcache 路径，没有明确要求新增该限制；
  TP-only 是后续 implementation plan 的决策扩展。

### MC2：load timeout 后可能永久等待

- 严重级别：Medium
- 类型：潜在 fault-path breaking change
- 状态：已采纳
- 代码：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py:1777`
- 行为：第一次 `event.wait(timeout=10)` 超时后，再执行一次无 timeout 的
  `event.wait()`。
- 影响：如果 memcache `batch_copy` 卡死而不是抛异常或最终返回，forward 会永久
  阻塞。旧基线会在 10 秒后继续，虽然可能消费不完整 KV。
- 判断：新行为优先保证 correctness，但改变了 liveness contract。现有 UT 只覆盖
  “第二次 wait 最终完成”，没有覆盖 backend 永久不返回。
- 采纳方案：保留“in-flight transfer 完成后才能执行 Mooncake `batch_get_end`”的
  drain barrier；增加有界终止、backend cancel 或进程级失败策略，避免 backend 永久
  不返回时无限阻塞 forward；并将 Mooncake session cleanup 竞态处理与 memcache
  fault-path 分开。

### MC3：失败 GVA 仍进入 transfer

- 严重级别：Medium
- 类型：设计要求未落实；既有故障，不是 feature 新增 regression
- 状态：不采纳并忽略；属于继承的 memcache 既有问题，非本 feature 引入
- 代码：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py:1199`
- 行为：`batch_alloc` 返回 `gva <= 0` 时只记录日志，随后仍把该值写入
  `block_gvas` 与 `_allocated_gvas`。返回 list 过短时，非 strict `zip` 还会静默遗留
  `0` GVA。
- 影响：坏 GVA 会进入本批 `batch_copy`，并且缓存到 `_allocated_gvas` 后抑制后续
  allocation retry。
- 设计关系：权威设计 §3 明确要求 `gva <= 0` 的 key 不进入 shared/copy；最终验收
  标准还要求所有 list-returning API 在 index/zip 前验证 shape。
- 测试：没有 memcache allocation failure/shape mismatch 覆盖。

## Memcache 未发现回归的部分

| 路径 | 检视结论 |
| --- | --- |
| `use_layerwise=false` | block-key gate 为 false，仍选择 whole-key threads |
| TP-only layerwise Scheduler | 仍使用 `batch_get_key_info` 判断 hit |
| Worker save | 仍使用 worker-local `batch_alloc` 与 flat GVA |
| Worker load | 仍使用 `batch_get_key_info`、`batch_add_lease`、`batch_remove_lease` |
| `LayerBatchBuilder` | memcache 仍生成 flat `addr_array/size_array/gvas_array` |
| Sending/Recving | 仍调用 `_batch_copy_with_limits(..., direction=0/1)` |
| Mooncake range branch | `use_key_major_ranges=false`，memcache 不会进入 |
| commit/revoke | MemcacheBackend 为显式 success no-op，正常 GVA path 不调用 |
| Yuanrong/MTP | 未发现 feature 引入的确认 breaking change |

以上只证明 source 与 mock UT 层面的兼容性，不代表真实 memcache/NPU E2E 已验证。

## Design 符合性 Findings

### D1：`batch_put_end` 不幂等

- 严重级别：Blocker
- 状态：先采纳，后被最新实施边界覆盖；本轮不修改 Mooncake
- Mooncake 代码：
  `repos/Mooncake/mooncake-store/src/real_client.cpp:5198`
- Mooncake 测试：
  `repos/Mooncake/mooncake-store/tests/pybind_client_test.cpp:1004`
- 当前行为：第一次 `batch_put_end` 成功后清理 session；第二次调用返回
  `INVALID_PARAMS`。
- 设计关系：权威设计 §6.1 要求 `batch_put_end` 幂等。
- 影响：正常 vLLM path 当前只调用一次，因此不一定立即破坏推理；但 frozen contract
  gate 明确不能通过。

### D2：ranged put 缺少可选 `ReplicateConfig`

- 严重级别：Medium
- 状态：先采纳，后被最新实施边界覆盖；vLLM-Ascend 保持适配当前四参数 contract
- Mooncake 接口：`repos/Mooncake/mooncake-store/include/pyclient.h:325`
- 当前行为：`batch_put_from_multi_buffer_ranges` 只接受 keys、buffers、sizes、offsets；
  `ReplicateConfig` 被放在 `batch_put_start`。
- 设计关系：权威设计 §4.3.2 的 frozen signature 把
  `Optional[ReplicateConfig]` 放在 ranged put API。
- 影响：当前 vLLM Backend 使用默认 allocation policy 时可运行，但接口并非 frozen
  contract 的 100% 实现。

### D3：put-start 异常 cleanup 在 Worker 主线程 revoke

- 严重级别：Medium
- 状态：已采纳
- 代码：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py:1427`
- 当前行为：`batch_put_start` 抛异常或结果 shape 错误时，Worker 主线程同步调用
  `_best_effort_revoke_layerwise_keys(...)`。
- 设计关系：权威设计 §1.4 要求 ranges、`batch_put_end`、`batch_put_revoke` 在传输
  线程执行，避免阻塞 forward 热路径。
- 影响：异常 cleanup 的 Master RPC 可能阻塞 chunk setup。正常 ranged-write revoke
  已在 SendingThread，只有该异常路径不符合。

### D4：memcache alloc failure filtering 未实现

- 严重级别：Medium
- 状态：不采纳并忽略；与 MC3 相同，非本 feature 引入
- 内容：与 MC3 相同，但在本节作为明确的设计符合性缺口单列。
- 设计关系：权威设计 §3 和最终验收标准均要求失败 key 不进入后续 transfer，并对
  list result 做严格 shape validation。

### D5a：真实 Mooncake wheel contract 未完成

- 严重级别：Blocker
- 状态：Pending
- 当前证据：完整 AscendStore CPU suite 与 fake Client/mock NPU tests。
- 缺少证据：
  - 真实 Mooncake wheel contract；
  - PROCESSING visibility 与 Master/Client session cleanup；
  - 真实 Client 下的 lease renewal 与 session cleanup。
- 设计关系：权威设计 §6.1 把真实 Client/Transfer/wheel contract 列为验收项；该验证
  不等同于 NPU E2E，因此暂时保持 Pending。

### D5b：NPU E2E 未完成

- 严重级别：Residual risk
- 状态：不采纳为本地实施/验收项；当前没有 NPU 测试环境
- 未执行范围：NPU prefix hit 与 accuracy、至少三个 prompt chunks 的 lease renewal、
  mixed-lastness shared-prefix ownership、renewal/lease failure 后的 recompute，以及真实
  memcache NPU regression。
- 处理：报告继续明确“未经 NPU 验证”，但不要求当前 workspace 在缺少 NPU 环境时
  完成或阻塞于这些测试。

## 已对齐的 Design 行为

- connector/scheduler/worker 使用统一 block-key layerwise gate；
- per-block、带 rank 后缀的 canonical key；
- Scheduler 对 Mooncake 使用 `batch_is_exist` 且要求 COMPLETE；
- key-major local pointer、size 与 object byte offset；
- 正数 ranged result 为成功，负数映射 invalid block；
- per-key ranged write failure、revoke、后续 layer filtering；
- 最终只 commit active keys；
- get-start 先于 put-start；
- 只把成功 PutEnd 的 key promotion 到后续 chunk load set；
- 每 chunk 对累计 load keys 执行 get-start/renewal；
- request owner 与 key active owners 双向状态；
- mixed-lastness 下，只有最后 owner 释放后才调用 `batch_get_end`；
- abort 保留 desired keys 供 retry，terminal cleanup 删除 request 状态。

上述结论的证据等级是 source review + fake CPU UT，不等价于真实 runtime validation。

## Standards Findings

### ST1：缺少真实 NPU/E2E/性能验证

- 严重级别：Hard violation
- 状态：不采纳为本地实施/验收项；当前没有 NPU 测试环境
- 原因：vLLM Ascend `AGENTS.md` 要求 NPU-specific change 在真实硬件验证，并为性能
  敏感路径提供 E2E/nightly 或性能证据。
- 处理：保留为 upstream/目标环境 residual risk，不在当前本地实施范围内补齐。

### ST2：未命名的 timeout magic number

- 严重级别：Low
- 状态：Pending
- 代码：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py:1872`
- 内容：`wait(timeout=10)` 实际充当循环日志间隔，应使用有语义的常量。

### ST3：batch variant 状态表达复杂

- 严重级别：Low；judgement call
- 状态：Pending
- 内容：nullable `block_gvas_arr`、nullable `block_keys` 与
  `use_key_major_ranges: bool` 共同表达 GVA/range batch variant，存在非法组合，并在多个
 位置重复分派。

### ST4：等待逻辑与测试 setup 重复

- 严重级别：Low；judgement call
- 状态：Pending
- 内容：receiver 的 save-event 等待/清理重复；多个 Worker session tests 重复相同
  active-session setup。

## 验证结果

- 隔离 AscendStore CPU suite：`398 passed`
- Ruff：passed
- `py_compile`：passed
- `git diff --check upstream/main...HEAD`：passed
- 9 个 feature commits 的 `git show --check`：passed
- 真实 Mooncake wheel：未验证
- NPU E2E：未执行
- 真实 memcache E2E：未执行

review 时 feature 比实时 `upstream/main` 落后 2 个提交。两个上游提交分别修改 NZ
prefetch offloader/model runner 和 MathJax 文档，没有触及 AscendStore/KV transfer；这只
能证明没有直接文件重叠，不能替代 rebase 后验证。

## 待用户决策

请分别决定是否采纳：

| ID | 待决建议 | 当前状态 |
| --- | --- | --- |
| MC1 | 接受 memcache block-key layerwise 的 TP-only breaking boundary，并明确作为兼容性限制 | 不采纳；intentional |
| MC2 | 保留 drain barrier，并增加有界终止/取消/进程级失败策略，避免 backend 永久阻塞 forward | 已采纳 |
| MC3/D4 | 过滤失败 GVA，并对 `batch_alloc` result 做严格 shape validation | 不采纳并忽略；既有 memcache 问题 |
| D1 | 要求 Mooncake `batch_put_end` 满足 frozen contract 的幂等语义 | 不纳入本轮实现；禁止修改 Mooncake |
| D2 | 按 frozen design 对齐 ranged put 的可选 `ReplicateConfig` signature | 不纳入本轮实现；Ascend 适配现有四参数 API |
| D3 | 将 put-start 异常 revoke 移出 Worker forward 主线程 | 已采纳 |
| D5a | 完成真实 Mooncake wheel contract 验证 | Pending |
| D5b/ST1 | 完成 NPU E2E、NPU benchmark 与真实硬件验证 | 不采纳；当前无 NPU 环境 |
| ST2 | 把 `timeout=10` 提取为具名常量 | Pending |
| ST3 | 用显式 batch variant 收敛 nullable fields + boolean switch | Pending |
| ST4 | 抽取重复等待 helper 与 test setup helper | Pending |

本报告保存全部候选 findings；只有用户明确采纳的项目才进入
`features/kv-pool-layerwise-reuse/review-decisions.md`，并且只有收到明确实施指令后才修改
源码。
