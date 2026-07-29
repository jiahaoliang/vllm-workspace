# Mooncake Multi-group Layerwise KV Cache 设计

Status: Implemented, ready for written review

Date: 2026-07-28

Implementation: `repos/vllm-ascend@1800d56dc2ff6553ff0e0f25f63ab9505ff5ac3e`

Validation: `454 passed` in the dedicated CPU-only UT Pod; changed-file Ruff
lint, Python compile, and `git diff --check` passed.

## 1. 背景

Mooncake layerwise KVPool 已支持单 group 的 block-key object、chunked-prefill
会话续租和 ranged transfer。vLLM-Ascend v0.24.0 基线同时包含 Memcache 的
multi-group layerwise 编排，但 Mooncake 会话路径仍使用单 group 元数据：统一
`block_size`、统一 `page_size * num_layers`、flat save/load keys、physical layer
offset，以及全局末层 commit。

DeepSeek-V4 的 KV cache 是异构布局。vLLM-Ascend PR #12083/#12147 的代表配置
产生 6 个 runtime groups，包含不同 compression ratio、block size、page layout
和 retention semantics。group 数量和顺序属于 `KVCacheConfig` 的运行时结果，
不是 connector contract。

`KVCacheGroupSpec` 表示共享一个 block table 的 cache entries。它不是 MLA、
indexer 或 attention branch 的固定语义标签：

- 一个 group 可以包含同一物理层的 main cache 和 indexer cache；
- 一个物理层可以映射到多个 groups；
- DeepSeek-V3.2 的 MLA cache 与 indexer cache 不必属于不同 groups；
- connector 不得硬编码 C4、C128、indexer、SWA 或 6 个 group IDs。

详细依据见
[`references/snapshots/research-deepseek-multi-group-kv-cache-2026-07-28.md`](references/snapshots/research-deepseek-multi-group-kv-cache-2026-07-28.md)。

## 2. 目标

在不修改 vLLM 和 Mooncake 仓库的前提下，为 AscendStoreConnector 的
`backend=mooncake + use_layerwise=true` 增加通用 N-group 支持：

1. key、object、session、range layout 和 completion state 全部 group-local；
2. Scheduler 只返回所有必要 groups 共同可用的 prefix；
3. 同一物理层能够搬运多个 group tasks；
4. 写失败按 `(group, key)` 隔离；
5. 读失败按 `(group, key)` 定位，并在默认 `failure_policy=fail` 下只结束受影响
   request；
6. 单-group Mooncake 和现有 Memcache 行为保持兼容。

## 3. 非目标

- 不实现 hybrid `kv_load_failure_policy=recompute`。
- 不修改 `repos/vllm`、`repos/Mooncake` 或 Mooncake Client API。
- 不为 C4、C128、indexer、SWA 或 compressor state 编写模型名分支。
- 不重构现有 Memcache multi-group 路径。
- 不在本阶段运行真实模型或申请 NPU。

## 4. 既有能力与缺口

现有 vLLM-Ascend multi-group 编排已经提供：

- `physical_layer_to_group_layers`；
- per-group `group_block_len`、`group_block_stride` 和 `group_num_layers`；
- per-group `LayerBatchBuilder`；
- per-group block ids、effective block sizes 和 cache families；
- Memcache multi-group key、GVA allocation 和 common-prefix lookup。

Mooncake 路径的主要缺口是：

- `ReqMeta.save_block_keys/load_block_keys` 只表达 group 0；
- block key 不包含 `group_id`；
- put/get session preparation 使用 `self.block_size` 和 group 0 block ids；
- `batch_put_start` object size 固定为 `self.page_size_bytes * self.num_layers`；
- range builder 使用 physical layer id 作为 key-major offset；
- transfer thread 拒绝同一物理层的多个 Mooncake range tasks；
- active put/load state 和 commit boundary 是 batch-global，而非 group-local；
- Scheduler 的 Mooncake hit lookup 只查询一个 group；
- `invalid_block_ids: set[int]` 无法区分不同 group 的同号 block id。

## 5. 架构

### 5.1 `config_data.py`

新增 `GroupBlockKeys`，表达一个 request 在一个 group 内的 key slots：

```python
@dataclass
class GroupBlockKeys:
    block_keys: list[str | None]
    block_offset: int = 0
    last_block_key: str | None = None
    last_block_index: int | None = None
```

`ReqMeta` 新增：

```python
save_keys_by_group: dict[int, GroupBlockKeys]
load_keys_by_group: dict[int, GroupBlockKeys]
load_keys: list[str]
```

现有 flat save/load fields 保留为 group 0 compatibility properties，构造函数
把 legacy inputs 归一化到 group 0。`load_keys` 保持现有含义，但扩展为所有
groups 成功打开的扁平、去重 session key 列表。单-group 调用者和已有 tests
不需要改用新的容器。

`last_block_index` 必须按 group effective block size 独立计算。不得把现有全局
`partial_block_index` 直接复用到不同 block size 的 groups。

`LayerRangeReqMeta` 增加 `group_id`。每个 row 的 `block_ids`、keys、buffers、
sizes 和 offsets 继续严格对齐，使 transfer failure 能产生准确的
`(group_id, block_id)`。

### 5.2 `MooncakeLayerwiseGroupPlan`

`pool_worker.py` 在 KV caches 注册完成后，从现有 group metadata 构造只读的
轻量 plan：

```python
@dataclass(frozen=True)
class MooncakeLayerwiseGroupPlan:
    group_id: int
    effective_block_size: int
    object_size: int
    num_group_layers: int
    physical_to_local_layers: tuple[tuple[int, int], ...]
    final_local_layer: int
```

plan 只归一化现有数据，不替代或重构 Memcache metadata。初始化必须验证：

- group id、block size、layer count 和 object size 均有效；
- 每个 physical/local layer 映射唯一且在范围内；
- builder 产生的所有 ranges 均落在 `[0, object_size)`；
- group 中每个 cache entry 都被且只被一个 layer tuple 覆盖；
- 不允许缺失 metadata 时回退到 group 0 或使用平均 page size。

### 5.3 `LayerBatchBuilder`

`LayerBatchBuilder` 是 object layout 的唯一权威。它根据注册后的 cache entry
sizes 建立每个 group-local layer tuple 的精确 prefix offsets，并公开
`object_size`。

```text
tuple_offset[ell] = sum(size of every entry in tuples before ell)
entry_offset       = tuple_offset[ell] + inner prefix sum
object_size        = sum(size of every entry in the group object)
```

如果当前 layout 是等宽 tuple，该结果自然等价于
`ell * page_size[g] + inner_offset`，但代码不从平均 page size 反推 layout。

### 5.4 `MooncakeSessionTracker`

tracker 的 request entry 从 `(key, block_index)` 扩展为
`(key, group_id, block_index)`。key ownership、跨 chunk 续租和 exactly-once
close 仍按完整 key 管理；tracker 不解析 key 字符串来恢复 group。

## 6. Key 与 Object Contract

单-group 保留现有格式：

```text
{model}@{block_hash_or_tail}@{head_or_tp_rank}
```

multi-group 使用：

```text
{model}@{group_id}@{block_hash_or_tail}@{head_or_tp_rank}
```

尾块也必须 group-local：

```text
{model}@{group_id}@{req_id}_lastblock@{head_or_tp_rank}
```

每个 key 对应一个 group block object。`batch_put_start` 的 size 必须取对应
group plan 的 `object_size`。Scheduler、saving worker 和 loading worker 必须使用
同一 key helper，禁止分别拼接字符串。

## 7. Scheduler Hit Flow

Mooncake lookup 复用现有 Memcache multi-group 算法结构，仅把存在性查询换成
`batch_is_exist`：

1. 遍历 runtime groups，而非固定 group IDs；
2. 使用 group effective block size 从 request hashes 生成 group hashes；
3. 为每个 hash 生成全部 saving ranks 的 keys；
4. 一个 group block 只有在所需 rank keys 全部为 COMPLETE 时命中；
5. 非 `0/1` 状态、结果长度或类型异常均 fail closed；
6. 按现有 group mask/alignment 规则得到每个 group 的连续 prefix；
7. 返回所有参与 groups 的 common usable prefix。

一个 group 的额外命中可以保留，但不能提高其他必要 group 缺失处之后的整体
hit length。

## 8. Worker Chunk Flow

每个 chunk 按以下顺序执行：

1. 为每个 request/group 生成 load metadata，包括 group block ids、full block
   keys 和 group-specific tail key。
2. 合并并去重本 chunk 所需的全部 load session keys，写入 `load_keys`。
3. 在任何 put start 之前调用 `batch_get_start(load_keys)`。
4. 按 group 生成 save keys，并使用 group object size 调用
   `batch_put_start(keys, sizes)`。
5. 只把成功 start 的 keys 写回该 group 的 `GroupBlockKeys`；失败 slots 保持
   `None`。
6. 对每个 physical layer 遍历其全部 `(group_id, layer_idx_in_group)` 并创建
   transfer tasks。
7. 分别构建 per-group shared save/load data。
8. last chunk 的最后一次 onload drain 后，对成功打开的读 sessions exactly once
   调用 `batch_get_end`。

chunk N 的 `batch_get_start` 继续包含 prefix hit keys 和此前 chunks 已成功
`put_end` 的 keys，以延续现有 lease renewal contract。

## 9. Transfer 与 Completion Flow

Sending/Receiving thread 不再把同一 physical layer 上的多个 Mooncake range
tasks 合并成一个单-group task，也不再因 task 数大于 1 抛错。每个 group task
独立调用 `batch_copy_put/get`，以保留 aligned per-key results 和故障隔离。

Sending thread 维护 per-group active key sets：

1. group 的第一个 local layer 初始化 active keys；
2. copy failure 只移除并 revoke 失败 keys；
3. 后续 local layers 只搬运仍 active 的 keys；
4. 到达该 group 的 `final_local_layer` 后，对 active keys 调用 `batch_put_end`；
5. commit/revoke 后清理 `_put_started_keys` 和 session tracker 状态。

Receiving thread 同样维护 per-group active rows。一个 row 失败后，该
`(group, key)` 不再执行后续 reads；其他 rows、groups 和 requests 继续完成。

## 10. Failure Contract

### 10.1 Write

- `batch_put_start` 逐 key 接受成功结果。
- 结果 shape/type 异常时，所有状态不确定的新 keys 进入 ordered revoke task，
  并暂时阻止重复 PutStart。
- `batch_copy_put` 失败只 revoke 对应 key。
- 只有完成该 key 全部 required ranges 的 key 才能 `batch_put_end`。
- 其他 group/key objects 可以独立保持 COMPLETE；Scheduler common-prefix 规则
  阻止其被误当成完整逻辑 prefix。

### 10.2 Read

- `batch_get_start` 或 `batch_copy_get` 失败记录准确的
  `(group_id, block_id)`，并停止该 row 后续 ranges。
- 传输隔离粒度仍是 group/key；同批其他请求不受影响。
- 当前 request 的逻辑 prefix 只有在全部必要 group state 可用时才可消费。
- 任何成功打开的 get session 都必须 exactly once `batch_get_end`。
- timeout 时先等待 in-flight range call drain，再关闭 sessions。

### 10.3 Hybrid Failure Compatibility

vLLM v0.24.0 的 `invalid_block_ids: set[int]` 假设单 group，且 Ascend 已禁止
hybrid 使用 `kv_load_failure_policy=recompute`。本方案通过私有负整数编码在不改
vLLM 的前提下传递 group identity：

```text
payload = (group_id << 32) | block_id
encoded = -(payload + 1)
```

编码器验证 `0 <= group_id, block_id < 2**32`。真实 block ids 为非负，因此不会
与原 contract 冲突。

窄范围 scheduler compatibility patch：

1. 将 input 分成普通非负 ids 和 vLLM-Ascend encoded ids；
2. 普通 ids 完整委托原 vLLM 实现；
3. encoded ids 按准确 group block table 匹配受影响 requests；
4. 返回这些 request ids，让现有 `failure_policy=fail` 流程产生
   `FINISHED_ERROR`；
5. 不执行 token truncation、hybrid recompute 或模糊的跨 group
   `evict_blocks(set[int])`；
6. request 正常结束流程释放其 block references；共享同一失败 block 的请求会
   被同一准确 `(group_id, block_id)` 一并识别；
7. patch 只在收到 encoded ids 时接管行为。

## 11. 测试设计

### 11.1 CPU/mock UT

`test_config_data.py`：

- group-indexed save/load metadata；
- group 0 compatibility properties；
- 不同 offsets 和 group-specific tail keys。

`test_pool_scheduler.py`：

- 至少两个不同 effective block size 的 groups；
- group-aware keys 和全部 saving ranks；
- common-prefix truncation；
- malformed `batch_is_exist` fail closed。

`test_pool_worker.py`：

- exact object size，包含同层多个 cache entries；
- 所有 `get_start` 先于任何 `put_start`；
- per-group `put_start` 和 partial failures；
- non-saving ranks；
- group-specific tail block；
- chunk renewal 和 prior committed keys；
- 一个 physical layer 映射多个 groups。

`test_kv_transfer.py`：

- 同一 physical layer 的多个 Mooncake range tasks；
- builder-provided tuple/entry offsets；
- per-group final layer commit；
- per-key put revoke 和 get failure isolation；
- exactly-once cleanup。

compatibility patch tests：

- group/block encode/decode 和边界检查；
- 不同 groups 使用相同数字 block id 时准确匹配；
- 只结束受影响 requests；
- 非负 ids 委托原实现；
- hybrid recompute 继续被拒绝。

### 11.2 Kubernetes UT Pod

所有 CPU/mock tests 在 `liangjiahao` namespace 的专用长期 UT Pod 中执行：

1. 记录 host checkout branch、commit 和 dirty state；
2. 使用 tar + `kubectl exec -n liangjiahao` 同步临时 workspace；
3. 禁用 bytecode 和 pytest cache；
4. 显式运行 focused targets；
5. 运行完整 `tests/ut/distributed/ascend_store/`；
6. 运行 focused Ruff、Python compile 和 `git diff --check`；
7. 不申请 NPU，不挂载 NPU driver/device/model cache；
8. 测试后保留 UT Pod。

### 11.3 真实模型/NPU 后续计划

仅在用户明确下令后执行。计划使用真实 DeepSeek-V4 multi-group layout 验证：

- cold miss、warm save、prefix hit；
- chunked prefill 与跨 chunk lease renewal；
- runtime group/object/range audit logs；
- direct/proxy 输出正确性；
- per-group put/get failure injection；
- default `failure_policy=fail` 只结束受影响请求。

所有 workload 必须显式使用 `liangjiahao` namespace。

## 12. 验收条件

本阶段完成需同时满足：

1. 单-group Mooncake key、session 和 tests 无回归；
2. Memcache multi-group tests 无回归；
3. synthetic N-group tests 覆盖多 entry layer、不同 block size 和不同完成边界；
4. Scheduler 不会把 partial-group object 计为完整 prefix hit；
5. write failure 不影响其他成功 keys；
6. read failure 不会让 attention 接受 partial group state，并只结束受影响请求；
7. 所有成功打开的 read sessions 和不完整 write sessions 均正确收尾；
8. dedicated UT Pod 中 focused 和完整 AscendStore suites 通过；
9. 没有运行真实模型或占用 NPU；
10. 没有修改 `repos/vllm` 或 `repos/Mooncake`。

## 13. Review Baseline

- Fixed point: `3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6`.
- Candidate: `1800d56dc2ff6553ff0e0f25f63ab9505ff5ac3e`.
- Review diff:
  `git -C repos/vllm-ascend diff 3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6...1800d56dc2ff6553ff0e0f25f63ab9505ff5ac3e`.
- Source branch: `origin/feature/mooncake-layerwise-kv-pool`.
- Validation boundary: CPU/mock only; no real model, Mooncake deployment, NPU
  benchmark, or NPU E2E claim is included in this handoff.
