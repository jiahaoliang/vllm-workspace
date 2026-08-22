# 使用嵌套 value object 组织 DSA step request

状态：已接受

Blockwise DSA 的 Decode scheduler-to-worker step metadata 对每个 request 使用一个强类型 envelope，并把 remote source、Decode destination ownership 和 per-step lifecycle command 拆成三个嵌套 value object。Request identity 保留在 envelope 顶层；具体 fields 由后续接受的 [ADR 0019](0019-use-minimal-complete-dsa-step-fields.md) 确定。

概念结构如下，名称不是本 ADR 固定的 public API：

```python
@dataclass(frozen=True)
class DsaStepRequest:
    request_id: str
    source: RemoteSource | None
    destination: DestinationOwnership
    lifecycle: LifecycleCommand
```

不采用一个包含所有 source、destination、reservation、epoch、replay 和 cancellation optional fields 的扁平 request dataclass，也不为每个 action 建立独立的 request subclass/discriminated union。

## 穿刺代码怎么做

穿刺 Decode scheduler 使用扁平的 `sfa_kv_offload.config_data.ReqMeta`：`block_ids_npu` 在 PD 路径中被重解释为 Main HBM IDs，`block_ids_cpu` 表示 Main Host IDs，`block_ids_indexer` 表示 Indexer HBM IDs；同一个对象还携带 partial-block legacy fields、per-step fused-offload token range 和 HBM-to-Host offload block lists。

`SFAKVOffloadConnectorMetadata` 另外用 request 外部的 `unfinished_request_ids` 和 `preempted_req_ids` sets 表达部分 lifecycle state。Worker 使用大量 `getattr()` 接受不同 metadata shape。该结构能打通穿刺功能，但不能在类型边界区分当前 execution epoch 的 Indexer ownership、跨 epoch Main lifetime reservation、remote receive、full-sequence replay、cancellation drain 和 terminal quiesced。

目标实现只把它作为字段来源和 worker adapter 的参考，不沿用其扁平、含义重载的跨组件 contract。

## 普通 MooncakeConnectorV1 怎么做

普通 V1 的 `ReqMeta` 是扁平 dataclass，包含 local/remote block IDs、external/computed token 数、remote endpoint、P/D topology 和 block size。它描述一次普通 remote KV pull，local destination 是普通 KV group block table；不需要表达 Main Host lifetime reservation、active/reserved ownership、execution epoch、replay 或 cancellation quiesced。

因此普通 V1 保持现有扁平 metadata，不因本 feature 引入 nested value object。嵌套结构只属于 `dsa_pd_offload=true` 的 Decode scheduler-to-worker metadata。

## 考虑过的方案

- 单一扁平强类型 request envelope。它最接近穿刺和普通 V1，实现较少，但会形成大量仅对某些 action 合法的 optional fields。新 epoch 携带旧 Indexer IDs、replay 同时携带可启动的 remote source、cancel 同时启动 Main transfer、或 preserved Main prefix 没有对应 reservation 等非法组合只能靠分散检查避免；不采用。
- 嵌套 `source`、`destination` 和 `lifecycle` value object。每类状态只有一个职责边界，并由 envelope factory/validator 集中检查跨对象不变量；采用。
- 为 receive、replay、cancel 和 quiesce 建立 action-specific request union。它最接近“非法状态不可构造”，但会增加 RPC dispatch、serialization、aggregation 和 adapter 类型数量，并在 action/result enum 尚未确定前过早固化变体边界；首版不采用。

## Value object 边界

`RemoteSource` 只描述 Decode scheduler 从普通 V1 `kv_transfer_params` 解析的 remote request、source blocks 和 endpoint/topology，并按 local configuration 计算固定 leader mapping。它不携带每请求 raw address；worker 使用 ADR 0022 的 positional handshake arrays 和 process-local registration 解析地址。P/D topology、leader replica 和 tuple layout 的跨端一致性属于文档化部署前置条件，不由该 value object 证明，也不由本 feature 实现 deployment gate。Replay、cancel 或仅更新 local lifecycle 的 command 可以没有 remote source。

`DestinationOwnership` 只描述 Decode 当前持有的 destination/reservation identity：当前 execution epoch 的 Indexer HBM ownership、跨 epoch 的 Main lifetime reservation，以及 active 与尚未有效的 reserved Main 范围。它不能混入 remote endpoint 或 action-specific status。

`LifecycleCommand` 只描述当前 step 要执行的 lifecycle intent、execution epoch 和进度边界。它不能把 block list 作为第二份 ownership 来源。

本 ADR 不决定 exact fields、action enum、result enum 和 token-progress 表达方式；其中 exact fields 和 token-progress 表达已经由后续 ADR 0019 确定，action/result enums 已由后续 ADR 0020 确定。

## 集中组合校验

Envelope 必须通过唯一的 factory 或集中 validator 构造，worker 不接受任意拼装的 nested objects。至少需要能够表达并校验以下不变量，具体 action 名留给后续决策：

- remote receive 必须同时具有合法 source、当前 epoch 的 Indexer destination 和 Main reservation；
- 不读取 Prefill source 的 replay/cancel command 不能意外启动 remote transfer；
- Indexer ownership 绑定当前 execution epoch，Main reservation 可以跨 epoch 保留；
- active Main 与仅预留、尚未有效的 Main ownership 必须可区分；
- `preserved_main_tokens` 或同等进度只能引用同一个未释放的 Main reservation；
- transfer-failure replay 必须能够表达保留 reservation identity、但令所有 TP 的 preserved Main validity 归零；
- stale epoch 的 source、destination 或 lifecycle 组合必须 fail closed。

这些是跨对象 invariants，不要求每个 value object 单独知道整个 request state machine。

## 结果

- Decode scheduler-to-worker metadata 以 request envelope 为唯一 per-request 事实来源，不再并列维护 `preempted_req_ids` 等会与 request command 冲突的 lifecycle sets；若为 batch orchestration 保留集合，它们只能从 envelope 派生。
- Worker adapter 可以分别消费 source binding、destination binding 和 lifecycle command，不再用字段名猜测 memory role。
- 普通 `MooncakeConnectorMetadata`、普通 `ReqMeta`、Prefill scheduler flow 和 `dsa_pd_offload=false` 行为保持不变。
- 本决策本身没有确定 exact fields、enum、TP aggregation completeness 或 handshake entry schema；其中 exact fields 已由后续 ADR 0019 确定，action/result/phase enums 已由 ADR 0020 确定，TP aggregation completeness 已由 ADR 0021 确定，handshake 已由 [ADR 0022](0022-use-the-puncture-positional-handshake-abi.md) 改为穿刺 positional ABI。

## 预计实现影响

在已经接受独立 DSA metadata family 的基础上，嵌套 value object 相对扁平 DSA request 预计增加约 80-130 行 production Python、130-220 行 focused unit tests，编码与 CPU/mock UT 约 2-3 个工程日，不包含 NPU E2E。预计涉及：

- 新增 `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py`，定义 envelope、value objects 和集中 validator；
- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`，由 Decode scheduler 构造 typed envelope 并进行 mode/type gating；
- blockwise SFA scheduler subclass 所在文件，把 reservation tracker 和普通 V1 source input 投影到独立 value objects；
- `vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/worker.py` 和/或 `sfa_kv_offload_worker.py`，增加 typed adapter，停止通过歧义字段和 `getattr()` 解释 DSA ownership；
- `tests/ut/kv_offload/test_mooncake_connector.py` 及 focused SFA worker tests，覆盖 nested-object isolation、非法组合、stale epoch 和 default-path compatibility。
