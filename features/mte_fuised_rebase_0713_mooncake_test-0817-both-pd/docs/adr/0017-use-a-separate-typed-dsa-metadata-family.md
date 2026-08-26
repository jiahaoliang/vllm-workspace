# 使用独立的强类型 DSA metadata family

状态：已接受；handshake部分被ADR 0022取代，decode-time D2H metadata部分被ADR 0024、0027取代

后续关系：独立DSA metadata family与default V1 type isolation继续有效。Async contract把lifecycle request/result与step-local D2H plan/progress作为同一family中的并列value objects；D2H completion不再使用lifecycle command/result。

Blockwise DSA PD offload 为 `dsa_pd_offload=true` 建立独立、强类型、按通信方向分离的 metadata family，不给普通 `MooncakeConnectorV1` 的 `ReqMeta` 或 `MooncakeConnectorMetadata` 增加 optional DSA fields，也不把现有 Mooncake metadata 和 `SFAKVOffloadConnectorMetadata` 并排塞入一个双 envelope。

该 family 包含两类 contract：Decode scheduler-to-worker 的 per-step request/action metadata，以及 Decode worker-to-scheduler 的可跨 TP 聚合 result metadata。按照 [ADR 0018](0018-use-nested-value-objects-for-dsa-step-requests.md)，per-step request 使用包含 `source`、`destination` 和 `lifecycle` value object 的嵌套 envelope；exact fields 按照 [ADR 0019](0019-use-minimal-complete-dsa-step-fields.md) 使用显式最小完备 schema；action/result/phase enums 按照 [ADR 0020](0020-use-lifecycle-actions-and-terminal-local-results.md) 表达 lifecycle command 和 terminal local outcome。实现不得合并这些通道或退回弱类型 `dict[str, Any]` 作为 DSA lifecycle contract。P/D worker layout 已由 [ADR 0022](0022-use-the-puncture-positional-handshake-abi.md) 改为穿刺 positional ABI，不再属于该 semantic metadata family。

## 穿刺代码怎么做

穿刺 Decode scheduler 直接返回 `SFAKVOffloadConnectorMetadata`，并复用 `sfa_kv_offload.config_data.ReqMeta`。该 `ReqMeta` 的 `block_ids_npu` 在 PD 路径中实际被重解释为 Main HBM IDs，`block_ids_cpu` 表示 Main Host IDs，另加 `block_ids_indexer` 表示 Indexer HBM IDs；同时保留 legacy `num_full`、`partial_hbm_bid` 和 per-step offload range。Worker 通过大量 `getattr()` 同时兼容 SFA、layerwise 和 Mooncake shape。

P 侧则使用另一套 layerwise `SfaPDProducerMetadata`。D 侧 completion 主要依赖 done/failed sets，没有 `(request_id, execution_epoch, tp_rank)` worker result，也不能在 scheduler 侧区分 receive-complete、replay-ready 和 stale completion。Cancellation quiesce 不需要增加新的 typed result；目标实现由 worker 内部 epoch guard 决定何时安全进入普通 `finished_recving`。

这种复用减少了穿刺代码量，但同一个字段在不同路径代表不同 memory role，无法为 blockwise DSA 的 reservation、epoch、phase gate 和跨 TP replay 提供稳定 contract，目标实现不沿用。

## 普通 MooncakeConnectorV1 怎么做

普通 V1 的 scheduler-to-worker `MooncakeConnectorMetadata` 持有 `dict[str, ReqMeta]`。Request metadata 包含 local/remote block IDs、external/computed token 数、remote endpoint、P/D topology 和 block size；其 block lists 按普通 KV groups 对应，不表达 Main Host lifetime reservation 或 Indexer/Main 分阶段结果。

P/D worker layout 使用单独的 `MooncakeAgentMetadata` msgspec payload。Worker-to-scheduler 主要依赖 `finished_sending`、`finished_recving` 和 `invalid_block_ids`；普通 Mooncake connector 当前不生成 `KVConnectorWorkerMetadata`。

目标模式保留 Prefill scheduler 的普通 V1 request-finish metadata flow。独立 DSA scheduler metadata 只替换 Decode 的 scheduler-to-worker contract；Prefill worker 在 opt-in mode 下发布穿刺式 positional layer/address metadata，Prefill scheduler 不切换成 SFA metadata。

## 考虑过的方案

- 给普通 V1 `ReqMeta` 和 `MooncakeConnectorMetadata` 增加 optional DSA fields。改动较少，但默认路径会接受大量只在 DSA 下有意义的非法组合，也可能让 worker 静默按普通 HBM destination 解释 Main Host block；不采用。
- 将普通 Mooncake metadata 与 `SFAKVOffloadConnectorMetadata` 并排组合。同一 request、token boundary 和 block ownership 会出现两份事实来源，且现有 SFA 字段已经存在 role 重解释；不采用。
- 建立独立的强类型 DSA metadata family。每条通道只有一个事实来源，mode branch 必须显式处理新类型，默认 V1 类型和行为保持不变；采用。
- 把普通 V1、SFA 和 DSA 全部重构成通用 semantic role-to-memory protocol。它可能长期更统一，但会扩大到非目标 connector 和 upstream contract；首版不采用。

## 通道边界

```text
Prefill scheduler -> Prefill worker
  existing MooncakeConnectorMetadata

Decode scheduler -> Decode workers
  Blockwise DSA step metadata
    request identity + execution epoch
    remote source descriptor
    Indexer HBM and Main Host ownership
    per-step lifecycle/action data

Decode workers -> Decode scheduler
  Blockwise DSA worker result metadata
    local TP phase result
    replay-ready/receive-complete/fused-D2H evidence
    aggregate() across worker outputs

  existing KVConnectorOutput.finished_recving
    cancellation quiesced ack after worker-local epoch guard

Prefill workers <-> Decode workers
  puncture-compatible positional handshake metadata
    layer key + parallel address/length/scale arrays
    compatibility required by documented deployment preconditions
```

Scheduler-to-worker 和 worker-to-scheduler metadata 使用当前 vLLM RPC 可传输的 Python strong types，只允许 process-independent data，例如 scalar、enum、tuple/list、dict with typed values 和 block IDs；不能携带 `torch.Tensor`、NPU event、thread object 或依赖某个 process address space 的对象。P/D handshake 使用 MessagePack-compatible positional arrays，不提供 semantic role 或 version compatibility validation。

现有 `kv_transfer_params` 继续承载普通 V1 request rendezvous/source fields，并保持 JSON-compatible；Decode scheduler 在 mode 已通过 handshake 后，将这些 source fields 解析并校验到 DSA request metadata，worker 不直接把未校验的开放 dict 当作 lifecycle state。

## Worker result aggregation

DSA worker result 必须继承 `KVConnectorWorkerMetadata` 并实现 `aggregate()`，复用 vLLM 现有 `KVOutputAggregator`，不修改 upstream core。按照 ADR 0019，每个 typed local result 的 identity 至少覆盖 request、execution epoch、command sequence 和 TP rank。按照 [ADR 0021](0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md)，`aggregate()` 只合并同一个 engine step 的 rank-aware facts；scheduler connector 按 command identity 跨 step 累积，并要求当前 routed Decode DP replica 的精确 TP rank coverage。同一 identity 的相同完整 result 是幂等的，冲突内容必须 fail closed，不能 last-writer-wins。

`finished_recving` 仍用于触发 vLLM 已有 request transition。Receive-complete 和 replay-ready 路径不能单独依赖它：scheduler `update_connector_output()` 必须先消费匹配 epoch、满足精确 TP coverage 的 typed DSA result，再让 core 处理同一步 completion。Cancellation 是显式例外：worker 达到 Quiesced 后直接复用普通 `finished_recving`，由现有 expected-worker-count 聚合触发 terminal release，不生成 typed `QUIESCED`。Worker 必须在放入普通 request-ID set 前过滤 stale epoch 和重复 ack。

## 不进入 metadata 的内容

按照既有决策，DSA metadata family 不新增：

- `valid_token_count`、`transfer_token_start` 或 `transfer_token_count` 形式的第二套 prompt transfer boundary；
- source expiry、remaining TTL、source generation 或 launch grant；
- connector retry attempts、backoff 或 NIC selection；
- 每请求 raw source/destination address；address 由 positional handshake arrays 和 process-local registered pool 结合 block IDs 解析，P/D layout compatibility 属于文档化部署前置条件；
- 测试拓扑 `P TP8/DP2 -> D TP2/DP8` 的硬编码字段。

## 结果

- 普通 `MooncakeConnectorMetadata`、普通 `ReqMeta` 和非 DSA worker path 保持源码与行为兼容；`dsa_pd_offload=false` 不构造或接受 DSA metadata。
- DSA mode 收到普通 scheduler lifecycle metadata、或普通 mode 收到 DSA lifecycle metadata 时仍 fail closed；P/D handshake type/version/mode 一致性属于文档化部署前置条件，不由本 feature 实现跨 deployment gate。
- Prefill scheduler 继续普通 V1 flow；Decode scheduler 构造 DSA step metadata；P/D workers 通过 positional handshake arrays 暴露地址和 block geometry。
- `SFAKVOffloadConnectorMetadata` 和现有 `ReqMeta` 可以作为 worker 内部 adapter 的输入参考，但不再是 blockwise DSA 的跨组件 contract。
- Request envelope、exact fields、action/local-result/transfer-phase enums 和 typed result aggregation completeness rules 已分别由 ADR 0018-0021 确定；cancellation 普通 completion 由 ADR 0010 单独规定。

## 预计实现影响

本 ADR 原始估算包含后来被 ADR 0022 取代的 semantic handshake。调整后，独立 step/result metadata family 相对直接给普通 V1 metadata 增加 optional fields，预计增加约 140-250 行 production Python 和 220-360 行 focused unit tests，编码与 CPU/mock UT 约 3-6 个工程日，不包含 positional handshake 和 NPU E2E；handshake 增量以 ADR 0022 为准。预计涉及：

- 新增 `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py`，或在实现评审时选择同等隔离的 feature-local module；
- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：mode-specific step construction、binding、worker result output，以及 ADR 0022 单独估算的 positional handshake；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/config_data.py` 与 `sfa_kv_offload_worker.py`：从 DSA strong type 适配现有 fused offload interface，停止依赖歧义字段；
- `tests/ut/kv_offload/test_mooncake_connector.py`：default/DSA lifecycle type isolation、serialization、mode mismatch 和 result aggregation；positional ABI tests 按 ADR 0022 单独计算；
- focused SFA worker tests：epoch、memory role、offload range 和 stale completion adapter。
