# Mooncake 线性集成提交整理报告

Captured At: 2026-08-04T22:50:21+08:00

## 1. 结论

`feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` 上由
`jiahaoliang <gzliangjiahao@gmail.com>` 提交的 16 个连续 commits 已按功能和逻辑关系整理为
8 个 commits。改写没有编辑源码：每个新 commit 都直接采用对应原始分组末端的 Git tree。

最终结果满足以下不变量：

- 固定 parent 仍为 `a46a1dabbc260e8695002969f29528eb555eb583`；
- 旧 tip `d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873` 与新 tip
  `6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7` 的 tree 均为
  `ca363697034538b86626517066940315283ac8ad`；
- `git diff d5f0ea7f8..6bf3fb04c` 为空；
- 新历史为 8 个线性 commits，无 merge commit，全部有 DCO sign-off；
- §5.8 Mooncake multi-group 实现仍未进入目标分支；
- 受保护的 local/origin `feature/mooncake-layerwise-kv-pool` 仍为
  `b5b65d9bbe325d009ad887fb87b8883b7ecee156`；
- source origin 已通过精确 old-SHA lease 改写到 `6bf3fb04c`，远端与本地 left/right 为
  `0 0`。

本次只整理历史，没有改变最终文件内容。原 `d5f0ea7f8` 的完整 NPU validation 可以作为
同一 tree 的既有运行证据，但报告不会把它表述为 `6bf3fb04c` 上新执行的一次 full
validation。

## 2. 边界与基线

| 项目 | 值 |
| --- | --- |
| Source repo | `repos/vllm-ascend` |
| Source branch | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` |
| 固定集成 parent | `a46a1dabbc260e8695002969f29528eb555eb583` |
| 改写前 tip | `d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873` |
| 改写后 tip | `6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7` |
| 最终 tree | `ca363697034538b86626517066940315283ac8ad` |
| 原始 commits | 16 |
| 整理后 commits | 8 |
| 最终总 diff | 23 files, 5483 insertions, 323 deletions |
| 本地恢复 ref | `backup/mooncake-layerwise-kv-pool-merge-kv_offload_0723-pre-squash-d5f0ea7f8` |

开始前执行了 `git fetch --all --prune`。fetch 发现移动 remote
`collaborator/kv_offload_0723` 已从历史固定点 `a46a1dabb` force-update 到
`e4f2dd3e663c4d44b3c770f59424b83252df8608`，两条历史当前已经明显分叉。因此本报告和
后续 reviewer 命令都使用不可变 commit `a46a1dabb`，不使用移动的 collaborator ref
作为本次 squash 的 merge-base。把新 collaborator tip 纳入集成会改变最终 tree，与本次
“代码必须和 `d5f0ea7f8` 一致”的要求冲突。

## 3. 分组策略

分组遵守三个原则：

1. 不重排原始 patch 顺序；新 commit 的 tree 必须等于某个原始 commit endpoint 的 tree。
2. 只有共同构成一个可 review 行为的连续 commits 才 squash；独立的 compatibility 或
   observability 决策继续单独保留。
3. fix 必须与其直接修正的功能合并；例如并发 range-load 修复与 immutable row/request-local
   failure 合为一组，performance gate 与其 contract 修正合为一组。

### 3.1 原始到新历史映射

| 原序号 | 原始 commit | 原始 subject | 新 commit |
| --- | --- | --- | --- |
| 1 | `3676b98f1` | `feat(kv_pool): define Mooncake layerwise backend contract` | `7b5e57d5b` |
| 2 | `7f8bdf290` | `feat(kv_pool): add Mooncake layerwise metadata` | `7b5e57d5b` |
| 3 | `baa547632` | `feat(kv_pool): build Mooncake layer range batches` | `7b5e57d5b` |
| 4 | `d6f6a2622` | `refactor(kv_pool): make layer transfer completion exception-safe` | `309798210` |
| 5 | `4f87dfb6b` | `feat(kv_pool): add Mooncake ranged layer save` | `309798210` |
| 6 | `88f850172` | `feat(kv_pool): add Mooncake ranged layer load` | `309798210` |
| 7 | `bcc2b916f` | `feat(kv_pool): orchestrate Mooncake layerwise sessions` | `c429750b9` |
| 8 | `35d64610c` | `docs(kv_pool): document Mooncake layerwise backend` | `c429750b9` |
| 9 | `a2d654419` | `feat(kv_pool): support Mooncake chunked prefill sessions` | `c429750b9` |
| 10 | `4da8b2deb` | `feat(kv_pool): add ranged transfer audit logging` | `a4e4c8787` |
| 11 | `14beaf161` | `fix(kv_pool): adapt renamed Mooncake session APIs` | `0b4445773` |
| 12 | `d28c52958` | `fix(kv_pool): isolate concurrent Mooncake range loads` | `e6391552c` |
| 13 | `8d9897143` | `fix(kv_pool): isolate single-group ranged row failures` | `e6391552c` |
| 14 | `189dcdd2c` | `refactor(kv_pool): centralize ranged audit events` | `e1979b151` |
| 15 | `6451f9010` | `test(kv_pool): add Mooncake ranged performance gate` | `6bf3fb04c` |
| 16 | `d5f0ea7f8` | `fix(kv_pool): align single-group review backports` | `6bf3fb04c` |

### 3.2 新历史概览

| 新序号 | 新 commit | Subject | 原始 endpoint tree | 规模 |
| --- | --- | --- | --- | --- |
| 1 | `7b5e57d5b` | `feat(kv_pool): establish Mooncake layerwise range foundations` | `baa547632` | 9 files, +1137/-30 |
| 2 | `309798210` | `feat(kv_pool): implement Mooncake ranged layer transfers` | `88f850172` | 4 files, +1167/-163 |
| 3 | `c429750b9` | `feat(kv_pool): orchestrate Mooncake layerwise sessions` | `a2d654419` | 13 files, +2230/-127 |
| 4 | `a4e4c8787` | `feat(kv_pool): add ranged transfer audit logging` | `4da8b2deb` | 6 files, +303/-7 |
| 5 | `0b4445773` | `fix(kv_pool): adapt renamed Mooncake session APIs` | `14beaf161` | 12 files, +134/-346 |
| 6 | `e6391552c` | `fix(kv_pool): isolate Mooncake ranged request failures` | `8d9897143` | 4 files, +396/-36 |
| 7 | `e1979b151` | `refactor(kv_pool): centralize ranged audit events` | `189dcdd2c` | 7 files, +232/-114 |
| 8 | `6bf3fb04c` | `fix(kv_pool): align ranged performance validation contract` | `d5f0ea7f8` | 4 files, +394/-10 |

`a4e4c8787`、`0b4445773` 和 `e1979b151` 刻意保留为单 commit：初始 audit 功能、外部
Mooncake Client API 兼容、audit 模块集中化是三个可以独立接受或拒绝的 reviewer 决策。
为了减少 commit 数而把它们相互 squash，会降低历史表达能力。

## 4. 每个新 commit 的详细解析

### 4.1 `7b5e57d5b`: 建立 ranged transfer 基础

合并原始 `3676b98f1`、`7f8bdf290`、`baa547632`。这三个 commits 共同建立执行层之前的
接口、数据模型和批构建器，缺少任意一部分都还不能形成可消费的 ranged request。

原 `3676b98f1` 的主要变化：

- 在 `backend/backend.py` 增加 `BatchResultShapeError` 和
  `require_aligned_batch_results()`，集中校验后端批量返回值不是 `None`、长度与 keys 对齐、
  且每项是非 bool 的整数；负值作为后端逐项失败码保留给上层处理。
- 扩展 `Backend` 的 layerwise contract：`validate_layerwise_support()`、put/get session
  start、ranged copy put/get、commit/revoke/get end。
- `MooncakeBackend` 校验 Client 是否实现完整 layerwise 方法集合，并将内部 contract
  委托给 Mooncake Client；`MemcacheBackend` 对 commit/revoke 使用显式成功 no-op，避免
  破坏既有 Memcache 路径。
- 后端 UT 覆盖 delegation、缺失方法报告、SSD offload 允许路径、结果 shape guard 和 mock
  dependency 不污染 parallel state。

原 `7f8bdf290` 的主要变化：

- 增加 `make_layerwise_block_key()`，把 model、block hash/tail、TP rank 编入 Mooncake
  layerwise key；增加 `is_block_key_layerwise()` 和 topology fail-closed 校验。
- 扩展 `ReqMeta`，保存 save/load block keys、key offset、partial block、GVA array 和
  load key 等 layerwise 元数据。
- 增加 `LayerRangeReqMeta`、`SharedBlockData`，并扩展 `LayerTransferTask`。原有 positional
  constructor contract 保持兼容；collaborator 的 `GroupTransferData`、`TransferCompletion`、
  `LayerwisePreparation` 和 group-aware GVA 字段继续存在。
- UT 覆盖 block-key topology、fresh container、optional block keys 和 positional argument
  兼容。

原 `baa547632` 的主要变化：

- 增加 `LayerBatchBuilder`，将 request block range 预计算为跨 layer 共享的 block data，
  再按物理 layer 生成地址。
- 对 Mooncake block-key 路径生成 key-major rows：每一行绑定 key、block、多个 buffer、
  size 和 destination/source offset；同一 shared data 可复用于后续 layers。
- 过滤 `None` key 时同步过滤其 block/range 数据，save key 去重，partial-only failed
  session 可以形成合法空 batch。
- 明确 dispatch：`use_key_major_ranges=True` 返回 `LayerRangeReqMeta`；否则继续返回
  collaborator GVA 路径使用的 `LayerBatchReqMeta`。

Reviewer 重点：

- `require_aligned_batch_results()` 只负责 shape/type，不把非负成功码误解为字节数；
- key、block、buffer、size、offset 的行对齐必须同时过滤；
- `LayerTransferTask` 的 `shared_block_data` 和 `cached_process_tokens` positional 位置不能变化；
- Mooncake key-major 与 collaborator shared-buffer GVA 路径必须通过条件 dispatch 并存。

### 4.2 `309798210`: 实现 ranged save/load 与异常安全收尾

合并原始 `d6f6a2622`、`4f87dfb6b`、`88f850172`。三者共同定义 transfer thread 的完整
执行状态机：先保证任何异常都能收尾，再分别加入 ranged save 和 ranged load。

原 `d6f6a2622` 的主要变化：

- 重构 layer sending/receiving thread 的 task finalization，使 queue `task_done()`、layer
  completion event、request completion 和 invalid-block 标记在异常路径上具有明确语义。
- save 异常不会错误发布 request/layer 完成；load 异常会把相关 block 标成 invalid；共享
  worker 的 invalid-block state 被接入 receiver。
- 新增 `_finish_layer_save_task()`、`_finish_layer_load_task()` 等集中收尾逻辑，避免执行
  分支遗漏 finally。

原 `4f87dfb6b` 的主要变化：

- sending thread 使用 `batch_copy_put()` 写每个物理 layer 的 ranges。
- `_active_put_keys` 跨 layer 跟踪仍有效的 keys；某 key ranged write 失败只撤销该 key，
  其他 keys 继续后续 layers。
- 仅在 final layer 对完成全部 ranged writes 的 keys 执行 commit；commit 失败的 keys
  revoke，重复 save key 只写和发布一次。
- malformed results、API exception、commit/revoke exception 都有确定的 cleanup 和 tracker
  更新语义。

原 `88f850172` 的主要变化：

- receiving thread 使用 `batch_copy_get()` 读取每层 range，并维护 active rows/block
  indices。
- 某 row 返回负值时只使对应 block 失效；成功 rows 和后续 layers 继续。
- load abort、异常和最后一层完成都会清理 active state，并与 attention/layer completion
  事件衔接。

Reviewer 重点：

- save 只能在全部 layers 成功后发布 COMPLETE；
- load 失败必须进入 invalid-block 集合，不能把部分填充 buffer 当成 hit；
- 无论 backend 抛异常还是返回 malformed results，queue 和 completion event 都不能悬挂；
- legacy whole-key、Memcache 和 collaborator GVA transfer 分支不能经过 Mooncake ranged
  commit/revoke 状态机。

### 4.3 `c429750b9`: 编排 layerwise session 与 chunked prefill ownership

合并原始 `bcc2b916f`、`35d64610c`、`a2d654419`。`bcc2b916f` 把此前独立的数据面接入
connector/scheduler/worker；`a2d654419` 补齐跨 chunk 生命周期；中间文档属于同一外部行为。

原 `bcc2b916f` 的主要变化：

- connector、scheduler、worker 统一计算 `use_block_key_layerwise` 并执行 topology 校验。
- scheduler 生成 layerwise preparation 和 save/load ranges；worker 完成 Mooncake session
  start、range task preparation、control-only task、完成与撤销编排。
- `LayerwisePreparation.ensure_ready()` 保证跨 layer 共享的准备回调只执行一次，且缓存并
  重抛首次异常。
- 保留 collaborator 的 `GroupBatchPlan`、`GroupTransferData`、`TransferCompletion`、
  group-aware/shared-buffer GVA 路径；Mooncake block-key 路径只在明确条件下启用。

原 `35d64610c` 的主要变化：

- 文档化 layerwise backend、session/control 与 ranged data 调用顺序、配置、限制和失败
  行为，建立实现与用户可见 contract 的对应关系。

原 `a2d654419` 的主要变化：

- 新增 thread-safe `MooncakeSessionTracker`：
  `register_put_keys()` 记录 pending ownership；`commit_put_keys()` 只把成功发布的 key
  提升为未来 chunk 的 load entry；`revoke_put_keys()` 清理失败 pending key。
- `prepare_load_entries()` 合并当前命中与前序 chunk 已提交 key；`record_get_result()`
  记录共享 load-session ownership。
- retry/preemption 使用 `release_for_retry()` 释放 active Client owners 但保留可重试状态；
  terminal completion 使用 `release_terminal()` 同时清 request/load/pending ownership。
- failed get attempt 只释放参与该次尝试的 owner；共享 key 只有最后一个 owner 离开后才
  `batch_get_end`。

Reviewer 重点：

- 未 commit 的 put key 绝不能进入后续 chunk load；
- retry 与 terminal cleanup 的状态删除范围不同；
- 共享 Client session 的最后 owner 语义不能退化为每 request 都调用 end；
- preparation callback 必须 exactly once，且异常对所有等待 layer 可见。

### 4.4 `a4e4c8787`: 引入 ranged transfer audit

保留原始 `4da8b2deb` 为单独 commit。

- 增加默认关闭的 `VLLM_ASCEND_KVPOOL_RANGE_DEBUG`。
- 为物理 layer save/load ranges、final commit 和 legacy whole-key backstop 输出结构化
  `[KVPOOL_RANGE_DEBUG]` JSON 事件。
- instrumentation 是 best-effort：关闭时不构建 payload；serialization/logger 失败不能
  改变传输成功、失败或 cleanup 行为。
- 后端、transfer 和 env tests 覆盖 enabled、disabled、payload failure 和 logger failure。

Reviewer 重点：audit 不能成为 transfer correctness 的依赖，且 whole-key 事件用于证明
layerwise ranged flow 没有静默回退。

### 4.5 `0b4445773`: 适配 Mooncake session API 重命名

保留原始 `14beaf161` 为单独 compatibility commit。

- 内部 `Backend` contract 保持不变，`MooncakeBackend` adapter 将控制面调用映射到
  `batch_put_session_start`、`batch_put_session_end`、
  `batch_put_session_revoke`、`batch_get_session_start`、
  `batch_get_session_end`。
- ranged data API `batch_put_from_multi_buffer_ranges` 和
  `batch_get_into_multi_buffer_ranges` 未重命名，保持原调用。
- 同步修正 mock、connector、scheduler、worker、transfer 和对应 tests，删除集成过程中
  已被新结构替代的重复/过时代码。

Reviewer 重点：重命名必须只停留在 adapter boundary；vLLM-Ascend 内部调用者不应依赖
Mooncake Client 的具体 method names。

### 4.6 `e6391552c`: 隔离并发 request 和 row failure

合并原始 `d28c52958`、`8d9897143`。两者共同修复此前 full validation 暴露的同一类
ownership 缺陷：并发 requests 的 rows 或失败状态不能互相污染。

原 `d28c52958` 的主要变化：

- 保留单个 request 内的 key-major batch，但多个并发 request 分开调用
  `batch_copy_get()`。
- 修复旧逻辑把跨 request rows 合成一个 Mooncake batch 后污染 request buffer/marker 的
  问题；该问题在 warm concurrent pair 中可复现，串行和 cold control 不复现。
- 新增并发 request 构造和 request-local dispatch UT。

原 `8d9897143` 的主要变化：

- 增加 frozen `LayerRangeRow(req_id, block_id, key, buffers, sizes, offsets)`，结构性绑定
  ownership 与 range data，避免六组 parallel lists 再次错位。
- `LayerRangeReqMeta` 以 immutable rows 为真源，同时保留 legacy positional constructor
  和 copy-producing properties；混用 rows/legacy、row count 不齐、segment 不齐均
  fail closed。
- receiver 按 `row.req_id` 划分 active request subgroup。API exception、结果过短/过长、
  非整数和负值只使当前 request 的 indices/blocks 失效，后续 requests 继续执行。
- builder 直接生成 rows；save 热路径最终也直接消费 rows，避免兼容 property 重复物化。

Reviewer 重点：

- 并发 requests 必须分别 dispatch，但单 request 内仍是 key-major ranged batch；
- shared metadata corruption 仍应 task-level abort，只有 backend request failure 才局部化；
- `LayerRangeReqMeta` legacy positional contract 不能破坏；
- 这是 single-group Mooncake 修复，不得推导出 §5.8 multi-group 支持。

### 4.7 `e1979b151`: 集中 ranged audit emitter

保留原始 `189dcdd2c` 为单独 refactor commit。

- 新增依赖方向单一的 `range_debug.py`，集中 `emit_range_event()`、
  `emit_commit_event()` 和 `emit_whole_key_event()`。
- `kv_transfer.py` 与 `mooncake_backend.py` 删除重复 gate、JSON serialization 和
  logger-exception 隔离代码。
- 保持原 `[KVPOOL_RANGE_DEBUG]` prefix 和 payload schema，因此已有 runtime checker/证据
  contract 不变。
- 文档同时纠正 internal Backend methods 与外部 Mooncake Client session API 的名称边界。

Reviewer 重点：共享模块不能反向 import backend/transfer，且 disabled 路径必须连 payload
factory 都不调用。

### 4.8 `6bf3fb04c`: performance gate 与 contract 对齐

合并原始 `6451f9010`、`d5f0ea7f8`。后者是对前者及同批 review backports 的发布前修正，
如果拆开会在历史中保留一个已知错误的 benchmark contract。

原 `6451f9010` 的主要变化：

- 新增 opt-in 真实 Mooncake/NPU nightly test，直接执行 ranged save/load，记录 batch size、
  request/row/layer 数、总 bytes、GB/s 和 p50/p95 latency。
- 外部配置提供最小 GB/s 与最大 p95 ms 硬阈值；未配置时明确 skip，不伪造 performance
  结果。
- 数据回读比较保证 correctness，key cleanup 检查避免 benchmark 污染。

原 `d5f0ea7f8` 的主要变化：

- 修正 benchmark 对 Client 成功码的错误假设：contract 是“长度对齐且每项为非负整数”，
  不是“每项必须等于传输字节数”。新增正/负 contract tests，同时保留真实数据一致性
  oracle。
- 将三个 nightly 环境变量集中注册到 `vllm_ascend/envs.py`。
- save 热路径直接消费 immutable rows；把 pattern modulus `251` 提升为命名常量。
- 文档明确：既有 Memcache 非复用 multi-group 路径与当前不支持的 Mooncake multi-group
  不是同一能力；§5.8 仍 deferred。

Reviewer 重点：真实 performance test 仍需外部 Mooncake/NPU 配置和环境阈值；本次只证明
测试 contract 与 skip behavior，不声明吞吐 gate 已运行或达到阈值。

## 5. 跨 commit 设计关系

### 5.1 两条 layerwise 数据路径继续并存

本分支没有用 Mooncake 逻辑替换 collaborator 的 group-aware GVA 逻辑：

- `GroupBatchPlan` 表达每个 KV cache group 的 save/full-load/HBM-tail ranges；
- `GroupTransferData` 保存 group 的 block IDs 和 base GVAs；
- `TransferCompletion`、`LayerwisePreparation` 和 `LayerTransferArrayBuilder` 继续服务
  shared-buffer GVA transfer；
- Mooncake block-key 分支通过 `use_key_major_ranges` 使用 `SharedBlockData`、
  `LayerRangeReqMeta` 和 ranged Client APIs；
- `LayerBatchBuilder.build_addrs()` 以 `shared.block_keys is not None` 明确 dispatch，未引入
  双方原设计外的新 fallback。

### 5.2 save 生命周期

```text
put session start
  -> 按 layer batch_copy_put
  -> 逐 key 删除 ranged 失败项
  -> final layer 仅 commit 全层成功 keys
  -> commit 失败 keys revoke
  -> 成功 keys 进入 future chunk load ownership
```

### 5.3 load 生命周期

```text
get session start / lease renewal
  -> 为每个 request 单独 dispatch key-major batch_copy_get
  -> request-local exception/shape/negative failure 只失效本 request blocks
  -> 后续 requests 和 layers 继续
  -> retry 释放 active owner 但保留 load entries
  -> terminal owner 完成后 get session end 并删除 request state
```

## 6. 内容等价与历史验证

### 6.1 最终 tree

```text
$ git rev-parse 6bf3fb04c^{tree}
ca363697034538b86626517066940315283ac8ad

$ git rev-parse d5f0ea7f8^{tree}
ca363697034538b86626517066940315283ac8ad

$ git diff --exit-code d5f0ea7f8..6bf3fb04c
# exit 0, no output
```

### 6.2 每组 endpoint tree

| 新 commit tree | 原始 endpoint tree | 结果 |
| --- | --- | --- |
| `7b5e57d5b^{tree}` | `baa547632^{tree}` | 相同 |
| `309798210^{tree}` | `88f850172^{tree}` | 相同 |
| `c429750b9^{tree}` | `a2d654419^{tree}` | 相同 |
| `a4e4c8787^{tree}` | `4da8b2deb^{tree}` | 相同 |
| `0b4445773^{tree}` | `14beaf161^{tree}` | 相同 |
| `e6391552c^{tree}` | `8d9897143^{tree}` | 相同 |
| `e1979b151^{tree}` | `189dcdd2c^{tree}` | 相同 |
| `6bf3fb04c^{tree}` | `d5f0ea7f8^{tree}` | 相同 |

这项检查不仅证明最终结果一致，也证明 squash 没有改变任一 reviewer 分组边界处可见的
代码状态。

### 6.3 历史结构

```text
merge-base a46a1dabb HEAD: a46a1dabbc260e8695002969f29528eb555eb583
commit count a46a1dabb..HEAD: 8
merge commit count: 0
missing DCO count: 0
§5.8 prohibited-symbol matches: 0
source worktree: clean
```

## 7. 验证结果

### 7.1 本次 squash 后重新执行

UT 环境是长期运行的 `liangjiahao/vllm-ascend-ut`：

- namespace 显式为 `liangjiahao`；
- Pod `Running/Ready`；
- requests/limits 无 `huawei.com/Ascend910`；
- volume 只有 `emptyDir`，无 `hostPath`；
- source 通过 tar + `kubectl exec` 同步到独立临时目录；
- `PYTHONDONTWRITEBYTECODE=1`，pytest 使用 `-p no:cacheprovider`。

结果：

| Gate | 结果 |
| --- | --- |
| `tests/ut/distributed/ascend_store` + `tests/ut/test_envs.py` + performance test module | `492 passed, 1 skipped` |
| Performance contract tests | zero/positive success codes通过；malformed/negative 拒绝通过 |
| 未配置真实 Mooncake/NPU benchmark | 预期 `1 skipped` |
| Ruff lint，全部 22 个 Python diff files | passed |
| Ruff format，全部 22 个 Python diff files | `22 files already formatted` |
| `py_compile`，11 个 production Python diff files | passed |
| `git diff --check` | passed |
| tree/endpoint/history/DCO/protected/§5.8 checks | passed |

现有 UT runner 硬编码 full-validation 身份 `d5f0ea7f8`。为了不篡改冻结的历史 validation
identity，本次没有修改该 runner，而是按同一 CPU-only/no-hostPath/tar/bytecode/cache 规范
手动同步到 `/workspace/vllm-ascend-squash-6bf3fb04c`。测试完成后已删除该临时 source 和
隔离 pycache 目录，长期 UT Pod 保留。

### 7.2 既有完整运行证据

相同 tree 的 `d5f0ea7f8` 已在 run `20260804T103209Z` 完成：

- CPU/mock `490 passed`，deployment tooling `82 passed`；
- G1 `43/43`，negative `24/24`；
- lease stale `-707` 与 fresh recovery；
- G4 `27 save + 27 load layers`，whole-key `0`；
- smoke baseline/direct/proxy 均 `4/4`，correlations `12/12`；
- stress S1 `4/4/508`、S2 `16/16/288`、S3 pinned + `4/4/348`；
- stress ledger `162/162`；最终 Master keys/bytes/clients 为 `0/0/0`。

因为 Git tree object 完全相同，这些结果是当前代码内容的强既有证据；但 run identity 仍是
`d5f0ea7f8`，没有改写历史报告、`validation-identity.json` 或 checksummed evidence，也没有
声称新 SHA 又执行了一次完整 NPU flow。

## 8. 发布与恢复

push 前 live remote 为：

```text
d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873
refs/heads/feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723
```

仅目标 ref 使用以下精确 lease 改写：

```text
--force-with-lease=refs/heads/feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723:d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873
```

push 后：

```text
origin target: 6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7
local target:  6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7
left/right:    0 0
protected local/origin: b5b65d9bbe325d009ad887fb87b8883b7ecee156
```

旧 tip 仍可从本地 recovery ref 恢复：

```text
backup/mooncake-layerwise-kv-pool-merge-kv_offload_0723-pre-squash-d5f0ea7f8
  -> d5f0ea7f8c238009b03bc3d5eeeb19a71d80b873
```

该 backup ref 未推到 origin，避免增加不必要的远端分支。旧 commits 仍可通过此本地 ref、
本报告 SHA 和 GitHub force-push retention 查阅。

## 9. 建议 reviewer 顺序

1. 先检查 `7b5e57d5b` 的 Backend contract、metadata alignment 和两条 dispatch 路径；它是
   后续所有 commits 的类型与接口基础。
2. 检查 `309798210` 的 save/load success、failure 和 finally 状态机，特别是 final commit
   与 invalid block 语义。
3. 检查 `c429750b9` 的 worker/scheduler orchestration 和 `MooncakeSessionTracker` ownership，
   这是跨 chunk 生命周期的主要复杂度。
4. 结合检查 `e6391552c` 的 request-local dispatch/immutable rows；这是历史 warm
   concurrent corruption 的直接修复。
5. 检查 `a4e4c8787` + `e1979b151` 的 audit schema 是否保持一致、是否完全 best-effort。
6. 检查 `0b4445773` 是否严格把 Mooncake API rename 限制在 adapter boundary。
7. 最后检查 `6bf3fb04c` 的 benchmark 成功码 contract、env 注册、single-group 文档边界和
   未运行真实 throughput gate 的 residual limitation。

## 10. Reviewer 可复现命令

```bash
cd /root/ljh/vllm-workspace/repos/vllm-ascend

git log --reverse --format='%H %T %P %s%n%b' \
  a46a1dabbc260e8695002969f29528eb555eb583..HEAD

git rev-list --count \
  a46a1dabbc260e8695002969f29528eb555eb583..HEAD

git rev-list --min-parents=2 \
  a46a1dabbc260e8695002969f29528eb555eb583..HEAD

git rev-parse HEAD^{tree} \
  backup/mooncake-layerwise-kv-pool-merge-kv_offload_0723-pre-squash-d5f0ea7f8^{tree}

git diff --exit-code \
  backup/mooncake-layerwise-kv-pool-merge-kv_offload_0723-pre-squash-d5f0ea7f8..HEAD

git rev-list --left-right --count \
  origin/feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723...HEAD
```
