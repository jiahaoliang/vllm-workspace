Source: Local first-party source checkouts `repos/vllm-ascend@45b2e785b10ca4604cd6314819ed15f3ff674781`, `repos/vllm@54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`, `workspace.lock.json`, and the captured first-party PR #10733 patch
Captured At: 2026-08-08T10:22:55+08:00
Notes: Read-only research on the purpose and current backend boundary of `layerwise_num_shared_buffers`; no source implementation or runtime validation was performed. Line references are against the frozen local commits above.

# `layerwise_num_shared_buffers` 的作用与 Mooncake 计算侧边界

## 结论

`layerwise_num_shared_buffers=3` 的含义不是“保留 3 个临时传输
buffer”，而是让非独立 transformer layer 按 round-robin 方式分时复用 3
组实际参与 attention 计算的 NPU KV cache 物理槽。它用更少 HBM 常驻槽换取逐层
load/save，并以 3 层的复用距离给传输与计算重叠留出窗口。

当前 checkout 中，Mooncake 已有 `use_layerwise=true` 的逐层 range/session
传输，但计算侧的内存预算放大和 `KVCacheTensor.shared_by` 合并仍被
`backend == "memcache" and use_layerwise` 显式 gate。因此 Mooncake 下可以有逐层
KVPool 数据流，却不会因为 `layerwise_num_shared_buffers=3` 而把每层计算 KV tensor
压缩成 3 个共享槽，也不会获得对应的 HBM 节省。

## 研究基线

| Repo | Branch | HEAD | Dirty |
| --- | --- | --- | --- |
| control repo | `kv-pool-layerwise-reuse`（比 `origin` 落后 2） | `972a3b78ce69af18eb508f55d7727ef509862011` | 仅保留既有未跟踪 `deployment_yaml/`、`dockerfile.vllm23` |
| `repos/vllm` | detached | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | False |
| `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `45b2e785b10ca4604cd6314819ed15f3ff674781` | False |
| `repos/Mooncake` | detached | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` | False |

三个源码 HEAD、branch 和 remote 均与 `workspace.lock.json` 一致；研究期间未修改
`repos/*`。

## 它复用的到底是什么

vLLM 的 `KVCacheTensor.shared_by` 原生语义就是“共享同一个 KV cache tensor 的
layer names”，不是仅供 connector 使用的 staging buffer。vLLM-Ascend 在分配前把
多个 layer 的 descriptor 合并为一个 `KVCacheTensor(shared_by=[...])`，分配器随后把
这些 layer name 都绑定到同一对 K/V raw tensor。也就是说，复用对象是 attention
直接读写的 paged KV cache NPU storage。

来源：

- vLLM 定义 `KVCacheTensor.size` 和 `shared_by`：
  `repos/vllm/vllm/v1/kv_cache_interface.py:929-938`。
- vLLM-Ascend 根据 slot 构造合并后的 descriptor：
  `repos/vllm-ascend/vllm_ascend/worker/model_runner_v1.py:3982-4055`。
- 实际分配后，同一 descriptor 的所有 layer name 都收到相同的 K/V tensor：
  `repos/vllm-ascend/vllm_ascend/worker/model_runner_v1.py:4569-4590`。

## 27 层、3 个 shared buffer 的具体布局

未显式配置 `layerwise_independent_layers` 时，默认独立层是首尾两层 `[0, 26]`。
其余 25 层 `[1..25]` 依次 round-robin 放入 3 个 shared slot：

| 物理槽 | 负责的 logical layer |
| --- | --- |
| independent 0 | `[0]` |
| independent 1 | `[26]` |
| shared 0 | `[1, 4, 7, 10, 13, 16, 19, 22, 25]` |
| shared 1 | `[2, 5, 8, 11, 14, 17, 20, 23]` |
| shared 2 | `[3, 6, 9, 12, 15, 18, 21, 24]` |

因此这里不是总共 3 个槽，而是 `2 independent + 3 shared = 5` 个物理
layer slot。复用关系是 `4 -> 1`、`5 -> 2`、`6 -> 3`、`7 -> 4` ……：箭头
右侧 layer 用完并释放槽后，左侧 layer 才能把自己的 KV load 到同一地址。

如果显式设置 `layerwise_independent_layers=0`，则只有 layer 0 独立，layer 26
也进入 round-robin 序列，总物理 slot 数变成 `1 + 3 = 4`；这与默认 `[0,26]`
不是同一个布局。

配置算法的一手来源：

- 默认 independent layer、reuse 判定与 `prefetch_layer_map`：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py:124-170`。
- round-robin storage slot 构造：同文件 `:192-205`。
- 当前 UT 用 27 层验证了 `[0,26]` 独立以及 `[1,7,13,19,25]` 这类
  round-robin 布局：
  `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_layerwise_config.py:18-37`。

## 为什么需要多个 buffer

数量最小可以是 1；“多个”主要是流水线并发与 HBM 占用之间的折中，而不是
correctness 的硬性要求：

- 1 个 shared slot 的 HBM 最省，但几乎每个后续 reused layer 都必须等待前一
  owner 完成计算和保存，再覆写同一槽，load 与 compute 的重叠余量最小。
- 3 个 shared slot 让相邻的三个 reused layer 位于不同地址。计算 layer 1 时，
  layer 2/3 的槽可以独立准备；直到 layer 4 才需要回收 layer 1 的槽。
- 增大 slot 数会拉长同槽两任 owner 的距离，更容易隐藏 load/save latency，但
  HBM 节省减少。shared slot 数达到或超过 reused layer 数时，代码将
  `has_layer_reuse` 设为 false，不再进行计算侧合并。

`layerwise_prefetch_layers` 是另一个旋钮：它决定提交多少个前置 layer load/gate，
默认是 `min(layerwise_num_shared_buffers, 8)`。因此 `shared=3` 时默认 prefetch depth
也为 3，但“物理槽数”和“提前提交深度”不是同一概念。

来源：

- 最小值、默认值与 prefetch 默认上限：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py:79-104`。
- reuse 仅在 `len(reused_layers) > num_shared_buffers` 时启用：同文件
  `:149-170`。
- 初始提交 `num_prefetch_layers` 个任务，之后随计算前沿每层补一个：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py:1625-1667`。

## 计算、load、save 如何避免互相覆盖

共享槽的单个生命周期如下：

1. attention 进入某 layer 前，connector 的 `wait_for_layer_load` 等待该 layer 的
   load 完成。
2. KV scatter 完成后立即异步派发 layer save；attention 结束后记录 NPU event。
3. save thread 只有在 KVPool copy 完成、可选 PD 逐层传输完成、并且 attention
   已结束后，才发布 `slot_free`。
4. 同槽下一 owner 的 load task 通过 `wait_for_save_layer=reuse_mate` 等待这个
   `slot_free`，然后才可覆写该物理地址。
5. reused layer 的槽可能已被前一 owner 覆盖，所以 load 必须从 block 0 恢复完整
   cached prefix；独立层保有自己的槽，只需恢复 HBM 本地缓存以后的 tail。

源码把 `slot_free` 定义为 “L2G copy done AND PD transfer done AND attention done”，
并在下一 owner load 前消费对应 save event；这正是 shared buffer correctness 的
核心，而不是仅靠 Python layer 顺序避免覆盖。

来源：

- attention connector hooks：
  `repos/vllm-ascend/vllm_ascend/attention/utils.py:509-558`。
- `reuse_mate`、attention gate 和下一 owner load task：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py:1629-1657`。
- save 侧等待 attention，并发布 `slot_free`：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py:1594-1608`、`:1898-1943`。
- receive 侧消费前一 owner 的 save event 后才传输：同文件 `:2234-2247`。
- reused layer 从 block 0 load：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py:208-218`，调用点在
  `pool_worker.py:1568-1600`。

## HBM 节省与 logical block accounting

以普通单组、各层 KV 形状相同的 27 层模型为例，默认 independent `[0,26]`、
`shared=3` 时，实际只分配 5 个 layer slot。worker 将可用 KV cache memory 按
`27 / 5 = 5.4` 放大后再交给 vLLM 计算 logical `num_blocks`，model runner 随后把
27 个 descriptor 合并为 5 个物理 slot。这样 scheduler 仍按“27 层都具有同样
block 数”记账，而实际 HBM 只承担 5 份 layer storage。

来源：

- 物理 slot 数是 `len(independent_layers) + num_shared_buffers`：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py:182-189`。
- worker 的 logical budget factor：
  `repos/vllm-ascend/vllm_ascend/worker/worker.py:593-613`。
- model runner 在 allocation 前执行 descriptor merge：
  `repos/vllm-ascend/vllm_ascend/worker/model_runner_v1.py:4148-4163`。

对于 SFA main/indexer 等不同 cache component，字节比例会按实际 page size 计算，
不能简单套用 `27/5`；当前 worker 已有按 component page size 计算 factor 的路径：
`repos/vllm-ascend/vllm_ascend/worker/worker.py:931-957`。

## 为什么当前计算侧只对 memcache 生效

决定计算侧 reuse 是否启用的入口是 `get_gva_layerwise_config()`。它会识别
`AscendStoreConnector`、`MooncakeConnectorStoreV1` 和 `MultiConnector` 中的相应
child，但最终只在下面条件成立时返回配置：

```python
backend == "memcache" and extra_config.get("use_layerwise", False)
```

否则返回 `None`。该 gate 位于
`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py:36-67`，
并被两个计算侧关键点共同使用：

- `worker.py:593-613`：是否放大 logical KV memory budget；
- `model_runner_v1.py:3982-4003`：是否把 per-layer descriptor 合并为共享槽。

所以 `backend=mooncake,use_layerwise=true,layerwise_num_shared_buffers=3` 时，
`get_gva_layerwise_config()` 返回 `None`，上述两步都跳过，计算侧仍是一层一份 KV
storage。这是当前 backend 边界的直接原因。

需要注意，Mooncake 下这个参数并非在所有路径都完全无效。逐层传输侧把 memcache
和 Mooncake 都列入 block-key layerwise backend，并会构造
`LayerwiseConfig`、`prefetch_layer_map` 和 full-prefix load 计划：

- backend 集合：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py:20-33`；
- pool worker 读取配置：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py:402-413`；
- Mooncake ranged load/save 的目标 buffer 和 object offset 按 layer 构造：
  `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py:402-443`。

因此当前实际状态是：**Mooncake 传输编排已能看到 reuse plan，但计算侧 allocation
gate 不接受 Mooncake，故没有真实共享地址与 HBM 收益。** 从“作用是什么”的边界
看，Mooncake 尚缺的是让同一份经过验证的 layerwise config 进入计算侧 budget 与
descriptor merge，并用 Mooncake 配置覆盖这一 backend gate 的 focused tests；本文
不展开具体实现方案。

当前用户文档的参数表把 `layerwise_num_shared_buffers` 描述为通用 layerwise 参数，
但 tuning 示例只给出 `backend=memcache`。以当前源码 gate 为准，文档不能作为
Mooncake 计算侧 reuse 已生效的证据：
`repos/vllm-ascend/docs/source/user_guide/feature_guide/layerwise_kv_pool.md:105-116`、`:234-256`。

## Git 历史佐证

当前分支引入该能力的 first-party commit 是
`633e0899809dd434c18fedf9212db2241ab76056`（`feat(kv_pool): support layerwise KV cache reuse`）。
提交说明强调 bounded buffer reuse 与异步 load 消费的 save-completion gate。
早期 first-party PR #10733 patch 的首个提交也明确说明：合并 per-layer
`KVCacheTensor`、按 `total_layers / physical_slots` 修正 memory accounting，并让
shared layer 完整 reload；本地快照为
`features/kv-pool-layerwise-reuse/references/patches/pr-10733-layerwise-kv-pool-reuse.patch`，
来源元数据在相邻的 `snapshots/pr-10733-layerwise-kv-pool-reuse.md`。
