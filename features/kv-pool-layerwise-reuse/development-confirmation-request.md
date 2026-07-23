# Mooncake Layerwise KVPool 部署前开发确认请求

## 目标

计划在 Ascend A2 Kubernetes 环境验证以下路径：

```text
AscendStoreConnector
  + backend=mooncake
  + use_layerwise=true
  + PD disaggregation
  + chunked prefill
```

目标不是 `MooncakeLayerwiseConnector`，也不验证 `/v1/metaserver` P2P 路径。

## 当前环境

- 镜像：`vllm-ascend:kv-pool-layerwise-v0.24.0-a2`
- 镜像 digest：`sha256:661c9bc2c50c1b7253d6f9ec7905cc83f49908ef8cb1919108a5ea828c2cff8d`
- vLLM：`ee0da84ab9e04ac7610e28580af62c365e898389`
- vLLM-Ascend：`663209fd6208a59a48742f75116345bf5f5281ec`
- Mooncake：`74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5`
- Mooncake 七个 session/range API 已在镜像内确认存在。
- 本机已有完整 `Qwen/Qwen3-8B` 缓存，暂未发现 MLA 模型缓存。

## 问题一：Qwen3-8B 能否验证 Layerwise 数据路径？

设计与 implementation plan 包含 GQA block-key 及 GQA NPU E2E：

- `references/snapshots/design-mooncake-layerwise-gva-put.md` 第 2.3 节定义了 MLA 和 GQA key。
- `implementation-plan.md` 的约束声明首期支持 TP-only MLA/GQA。
- `implementation-plan.md` Task 5 要求 MLA、GQA 都执行 NPU E2E。

但当前实现存在以下静态证据：

1. 本机 Qwen3-8B 配置为 32 attention heads、8 KV heads，属于普通 GQA，不是 MLA。
2. `vllm_ascend/platform.py` 将非 MLA、非 sparse 模型映射到
   `vllm_ascend.attention.attention_v1.AscendAttentionBackend`。
3. `vllm_ascend/attention/attention_v1.py` 的 forward 中没有发现
   `wait_for_kv_layer_from_connector` 或 `maybe_save_kv_layer_to_connector` 调用。
4. `mla_v1.py`、`sfa_v1.py` 和 `dsa_v1.py` 明确包含上述逐层调用。
5. 当前 `docs/source/user_guide/feature_guide/layerwise_kv_pool.md` 也写明
   `attention_v1` 尚未集成 layerwise wait/save。

请明确回答：

- 当前 commit 是否声称支持 Qwen3-8B/GQA 的 layerwise KVPool？
- 如果支持，请给出
  `attention_v1 -> AscendStoreConnector.wait_for_layer_load/save_kv_layer`
  的实际调用链和代码位置。
- 如果不支持，implementation plan 中的“GQA 支持”和 GQA NPU E2E 是文档范围错误，
  还是当前分支遗漏了实现？
- 若确实遗漏，实现 GQA 支持最少需要修改哪些 attention 路径和测试？

## 问题二：本路径需要哪一种 Proxy？

Design snapshot 明确本功能不替代 `MooncakeLayerwiseConnector`，而是针对
`AscendStoreConnector + KVPool prefix cache`。

源码中 `/v1/metaserver` 参数、回调和访问逻辑位于
`vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_layerwise_connector.py`；standard
Kubernetes proxy 则从 prefiller 响应取得标准 `kv_transfer_params` 后转发给 decoder。

但是 `layerwise_kv_pool.md` 仍要求 dedicated layerwise proxy 和
`/v1/metaserver`，与上述设计边界和调用链冲突。

请确认：

- `AscendStoreConnector + backend=mooncake + kv_producer/kv_consumer` 是否可以使用
  standard disaggregated proxy？
- `/v1/metaserver` 是否只属于 `MooncakeLayerwiseConnector` 的 P2P 逐层推送协议？
- 当前 `layerwise_kv_pool.md` 的 proxy 说明是否继承自旧实现，需要修正？

## 问题三：完整 E2E 应使用什么模型和证据？

若 Qwen3-8B 当前不支持，请指定一个适合单张 64GB A2、TP=1 的 MLA 验证模型。
当前候选为 `deepseek-ai/DeepSeek-V2-Lite`。

同时请给出能够证明以下调用真实发生的正向证据：

- 每 chunk `batch_get_start`
- 每 chunk `batch_put_start`
- 每层 `batch_put_from_multi_buffer_ranges`
- 每层 `batch_get_into_multi_buffer_ranges`
- 每 chunk 完成后的 `batch_put_end`
- 仅 last chunk 执行的 `batch_get_end`
- 第二次相同 prefix 请求出现外部 KVPool hit

只验证请求成功或输出正确不够，因为它不能区分 layerwise ranged 路径、whole-key
路径和普通重计算。

## 期望回复格式

1. Qwen3-8B layerwise 支持：`支持 / 不支持 / 当前实现缺失`
2. 正确 proxy：`standard proxy / layerwise metaserver proxy`
3. 推荐 E2E 模型及最小启动参数
4. 可作为验收依据的日志、metric 或 trace
5. 如有实现缺口，列出必须先完成的代码与测试项

## 开发确认回复

以下结论针对本文“当前环境”中锁定的 commit：

- vLLM：`ee0da84ab9e04ac7610e28580af62c365e898389`
- vLLM-Ascend：`663209fd6208a59a48742f75116345bf5f5281ec`
- Mooncake：`74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5`

### 1. Qwen3-8B layerwise 支持：当前实现缺失

当前 commit 不能使用 `Qwen/Qwen3-8B` 验证
`AscendStoreConnector + Mooncake` 的 layerwise ranged 数据路径。

Qwen3-8B 是普通 GQA 模型，会进入
`vllm_ascend.attention.attention_v1.AscendAttentionBackend`。当前
`AscendAttentionBackendImpl.forward` 和
`AscendC8AttentionBackendImpl.forward` 均没有调用：

- `wait_for_kv_layer_from_connector`
- `maybe_save_kv_layer_to_connector`

因此不存在
`attention_v1 -> AscendStoreConnector.wait_for_layer_load/save_kv_layer`
的实际调用链。即使 Qwen3-8B 请求成功或输出正确，也不会触发本文要验证的逐层
Mooncake range get/put。

MLA 的实际调用链可作为对照：

```text
AscendMLAImpl._mla_preprocess
  -> wait_for_kv_layer_from_connector
  -> AscendStoreConnector.wait_for_layer_load
  -> KVPoolWorker.wait_for_layer_load
  -> KVCacheStoreLayerRecvingThread
  -> MooncakeBackend.batch_copy_get
  -> batch_get_into_multi_buffer_ranges

AscendMLAImpl.forward
  -> maybe_save_kv_layer_to_connector
  -> AscendStoreConnector.save_kv_layer
  -> KVPoolWorker.save_kv_layer
  -> KVCacheStoreLayerSendingThread
  -> MooncakeBackend.batch_copy_put
  -> batch_put_from_multi_buffer_ranges
```

#### 历史归因

这不是 Mooncake feature 删除或漏移植了一个在 Memcache 合入点已经可用的 GQA
路径。Git 历史显示：

1. `6666e5265`（2025-09，KV connector v1）曾给 `attention_v1` 加入上述
   wait/save hooks，并记录过 Qwen/LMCache layerwise 验证。
2. `3158742a9`（2025-10，attention forward refactor）删除了这些 hooks。
3. Memcache layerwise commit `9f692f3db`（2026-07）合入前后，
   `attention_v1` 均没有 wait/save；该 commit 的产品文档也明确将
   `attention_v1` 列为未支持，实际 E2E 使用的是 MLA 模型。
4. 本 feature 从 `0e5c41c00` 到 `663209fd6` 的 Mooncake commits 修改的是
   AscendStore backend、metadata、range、session、orchestration 和文档，没有删除
   `attention_v1` hooks，也没有造成 GQA 回归。

Memcache commit 中虽然存在 GQA 的 `put_step=1`、per-rank key 和 save-owner
布局逻辑，但这只说明内部 block-key/range 数据结构考虑了 GQA；没有 attention
forward hook，就不构成 GQA layerwise E2E 支持。

所以应使用两个口径描述该缺口：

- 若 feature 目标只是让 Mooncake 达到当时 Memcache 的能力范围，这是从 main/
  Memcache 继承的既有 GQA 缺口，不是 Mooncake backend 实现造成的回归。
- 但 `implementation-plan.md` 已明确承诺首期支持 TP-only MLA/GQA，并要求 GQA
  NPU E2E；相对于本 feature 自己的验收范围，当前仍是未完成的实现项，不能把
  key-schema 单测视为 GQA 已交付。

#### 最小 GQA 补齐范围

1. 在 `AscendAttentionBackendImpl.forward` 中，仅当本 step 含 prefill 时，在
   `reshape_and_cache` 或任何 paged KV 读取前调用 layerwise wait，并在当前层 KV
   已写入后调用 layerwise save。
2. 同步覆盖独立覆写 `forward` 的 `AscendC8AttentionBackendImpl`。FA3 的 impl
   继承普通 attention base forward，base hook 接入正确后应由测试确认其覆盖关系。
3. hook 必须使用真实 `layer.layer_name`，decode-only step 不得错误推进
   `KVPoolWorker.current_layer`。
4. CP attention 暂不补；block-key layerwise 已限制 `PP=PCP=DCP=1`，CP 仍应明确
   快速失败或保持 unsupported。
5. 增加普通 GQA、C8 的 hook 次数、顺序、layer name、mixed prefill/decode 和
   decode-only unit tests。
6. 增加 fake backend 多层集成测试，断言每层调用 ranged get/put，且 whole-key
   `put/get` 未被调用。
7. 使用 Qwen3-8B 执行独立 GQA NPU E2E 后，才可将 GQA 标记为完成。

### 2. 正确 proxy：standard proxy

本路径应使用：

```text
examples/disaggregated_prefill_v1/load_balance_proxy_server_example.py
```

standard proxy 先请求 prefiller，再请求 decoder；若 prefiller 返回标准
`kv_transfer_params`，它会将其透传给 decoder。对于 `AscendStoreConnector`，KV
数据通过共享 KVPool 和 block key 查找，不需要交换远端 NPU KV 地址，也不依赖
`/v1/metaserver`。

`/v1/metaserver`、`remote_host`、`remote_port`、`remote_engine_id` 和对应回调只属于
`MooncakeLayerwiseConnector` 的 P2P 逐层推送协议。本次目标明确不是该 connector，
因此不应使用 `load_balance_proxy_layerwise_server_example.py`。

当前 `layerwise_kv_pool.md` 的 dedicated layerwise proxy 内容来自 Memcache
layerwise commit `9f692f3db`，与 `AscendStoreConnector` 的共享 KVPool 路径不符，
需要修正为 standard proxy。

另外，decoder 必须显式配置：

```json
"consumer_is_to_load": true
```

`KVPoolScheduler` 中该配置默认是 `false`。仅设置 `kv_role=kv_consumer` 而不设置
`consumer_is_to_load=true` 时，decoder 的 external KVPool lookup 会直接返回零，
无法验证 layerwise load。当前 `layerwise_kv_pool.md` 的 consumer 示例也遗漏了该
配置，需要一并修正。

### 3. 推荐 E2E 模型及最小启动参数

首选模型：`deepseek-ai/DeepSeek-V2-Lite`。

该模型使用 MLA，可进入已经具备逐层 wait/save hooks 的 `mla_v1`。单个 TP=1
实例适合放在一张 64GB A2 上。完整 1P1D 需要 prefiller 和 decoder 两个同时运行的
模型实例，即两个各分配一张 64GB A2 的 Pod；若环境总共只有一张卡，只能先用
`kv_role=kv_both` 验证 ranged 数据路径，不能作为完整 PD disaggregation E2E。

若环境已有 `vllm-ascend/DeepSeek-V2-Lite-W8A8`，它也可作为单卡 MLA 候选；第一轮
connector 验收优先使用未额外引入量化变量的 `deepseek-ai/DeepSeek-V2-Lite`。

两端共同的最小参数：

```text
--trust-remote-code
--enforce-eager
--data-parallel-size 1
--tensor-parallel-size 1
--pipeline-parallel-size 1
--prefill-context-parallel-size 1
--decode-context-parallel-size 1
--block-size 128
--enable-chunked-prefill
--max-model-len 4096
--max-num-batched-tokens 1024
--max-num-seqs 1
--no-enable-prefix-caching
--gpu-memory-utilization 0.90
```

Prefiller 的 connector 配置：

```json
{
  "kv_connector": "AscendStoreConnector",
  "kv_role": "kv_producer",
  "kv_load_failure_policy": "fail",
  "kv_connector_extra_config": {
    "backend": "mooncake",
    "use_layerwise": true,
    "layerwise_prefetch_layers": 1
  }
}
```

Decoder 的 connector 配置：

```json
{
  "kv_connector": "AscendStoreConnector",
  "kv_role": "kv_consumer",
  "kv_load_failure_policy": "fail",
  "kv_connector_extra_config": {
    "backend": "mooncake",
    "use_layerwise": true,
    "layerwise_prefetch_layers": 1,
    "consumer_is_to_load": true
  }
}
```

首轮 Mooncake 配置要求：

- `metadata_server=P2PHANDSHAKE`
- `protocol=ascend`
- prefiller/decoder 指向同一 `mooncake_master`
- `enable_ssd_offload=false`，确保 ranged API 使用 memory-backed replica
- 运行时探测七个 session/range API，不以 package version 代替 capability check

使用 `--max-num-batched-tokens 1024` 时，测试 prompt 应大于 3072 tokens 且小于
`--max-model-len`，从而稳定产生至少三个 prompt chunks。两次请求使用相同的、至少
跨多个完整 128-token blocks 的 prefix，并使用不同 suffix。

### 4. 可作为验收依据的日志、metric 或 trace

当前 commit 的成功路径日志不足以独立完成严格验收：

- Scheduler 的 INFO 日志可以给出 `kvpool hit tokens`。
- Mooncake Master metric 可以给出部分聚合的 put-start/put-end 计数。
- 但七个 API 的成功调用没有统一的 per-request/per-chunk/per-layer 正向日志；仅看
  error log、HTTP 200 或输出正确，无法区分 ranged、whole-key 和 recompute。

因此 NPU E2E 前应在 **vLLM-Ascend 范围内** 增加 opt-in structured trace；不需要
修改 Mooncake。每条事件至少记录：

```text
request_id
role
chunk_seq 或 token range
layer_id
operation
key_count
range_count
bytes
offsets 或 offset 范围
results
is_last_chunk
```

推荐埋点位置：

- `pool_worker.py` 的 Mooncake put/get session open/close：
  `batch_put_start`、`batch_get_start`、`batch_get_end`
- `kv_transfer.py` 的 `KVCacheStoreLayerSendingThread._handle_range_request`：
  ranged put 和 final-layer `batch_put_end`
- `kv_transfer.py` 的 `KVCacheStoreLayerRecvingThread._handle_range_request`：
  ranged get
- `pool_scheduler.py` 的 external hit/load spec：外部命中 token 数
- whole-key `MooncakeBackend.put/get`：作为必须保持为零的负向计数

严格验收矩阵：

| 验收项 | 必须观察到的正向证据 |
|---|---|
| chunked save session | 每个产生新 key 的 chunk 有成功的 `batch_put_start` |
| layerwise save | 每个物理层都有 `batch_put_from_multi_buffer_ranges`，`layer_id` 连续覆盖全部层 |
| publish | 每个 chunk 的 active keys 仅在最后一层 ranged put 成功后执行 `batch_put_end` |
| chunked load session | hit 请求的每个 chunk 对累计 load keys 执行成功的 `batch_get_start` |
| layerwise load | 每个物理层都有 `batch_get_into_multi_buffer_ranges`，并且 bytes 大于零 |
| lease release | intermediate chunk 不执行 `batch_get_end`；仅 last chunk 或终止清理执行一次 |
| external hit | 第二次共享 prefix 请求出现 `kvpool hit tokens > 0` |
| ranged offset | remote offset 与 `layer_id * page_size_bytes + layer_inner_offset` 对应 |
| 排除 whole-key | `batch_put_from_multi_buffers` 和 `batch_get_into_multi_buffers` 调用数为零 |
| 排除 recompute | `kv_load_failure_policy=fail` 且所有 range 返回码为零，无 fallback |

验收前启动一个空的 Mooncake pool 或清理旧对象，确保第一次请求是 miss。两端使用
`--no-enable-prefix-caching`，这样第二次请求的 cached tokens 才不会被本地 HBM prefix
cache 混淆。除 trace 外，还应保留两次请求的响应、prefiller/decoder 日志、Master
日志与 metrics 快照，并按同一 request ID 对齐。

### 5. 必须先完成的代码与测试项

MLA E2E 前必须完成：

1. 在 vLLM-Ascend 增加上述 opt-in structured trace 或等价的可机器断言观测点。
2. 修正 `layerwise_kv_pool.md`：使用 standard proxy，移除 `/v1/metaserver` 要求，
   consumer 增加 `consumer_is_to_load=true`，并使用 `lookup_rpc_port` 而不是已弃用的
   `mooncake_rpc_port` 示例名。
3. 使用 memory-backed Mooncake 配置运行至少三个 prompt chunks 的 MLA 1P1D E2E，
   按验收矩阵留存证据。

GQA/Qwen3-8B E2E 前还必须完成：

1. 补齐 `attention_v1` 和 C8 forward 的 layerwise wait/save hooks。
2. 增加普通 GQA/C8 hook 顺序和 decode-only guard unit tests。
3. 增加 AscendStore fake backend 多层 ranged 调用链集成测试及 whole-key 负向断言。
4. 完成 Qwen3-8B miss -> layerwise save -> external hit -> layerwise load NPU E2E。

在上述 GQA 项完成前，`implementation-plan.md` 中的 GQA 状态应保持 pending；当前
可先使用 DeepSeek-V2-Lite 验证 MLA + Mooncake + PD disaggregation + chunked prefill。
