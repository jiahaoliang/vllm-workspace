# 使用显式最小完备的 DSA step fields

状态：已接受

Blockwise DSA 的 Decode scheduler-to-worker request envelope 使用显式、最小完备的字段集。静态 topology、tensor layout、block/page geometry 和 rank endpoint mapping 属于已经严格校验的 handshake session；完整 Main lifetime reservation block list 属于 scheduler ownership state。Per-step metadata 只携带 worker 执行当前 command、绑定 destination 和拒绝 stale state 必须知道的信息。

本决策采用 immutable、process-independent values；示例中的 class/field names 是目标实现名称，若编码时因 repo naming convention 做机械调整，语义和边界不得变化：

```python
@dataclass(frozen=True)
class DsaStepRequest:
    request_id: str
    source: RemoteSource | None
    destination: DestinationOwnership
    lifecycle: LifecycleCommand


@dataclass(frozen=True)
class RemoteSource:
    remote_engine_id: str
    remote_request_id: str
    remote_host: str
    remote_port: int
    indexer_block_ids: tuple[int, ...]
    main_block_ids: tuple[int, ...]


@dataclass(frozen=True)
class DestinationOwnership:
    main_reservation_id: int
    main_reservation_block_count: int
    main_bound_host_block_ids: tuple[int, ...]
    indexer_hbm_block_ids: tuple[int, ...]


@dataclass(frozen=True)
class LifecycleCommand:
    execution_epoch: int
    command_seq: int
    action: DsaAction
    num_computed_tokens: int
    num_external_tokens: int
    preserved_main_tokens: int
    d2h_token_start: int
    d2h_token_count: int
```

`DsaAction` 的精确 enum members 由后续接受的 [ADR 0020](0020-use-lifecycle-actions-and-terminal-local-results.md) 确定；本 ADR 固定 action 必须参与字段组合校验。

## 穿刺代码怎么做

穿刺把 Main HBM、Main Host、Indexer HBM、legacy partial-block fields 和 fused D2H token range 放在同一个扁平 `sfa_kv_offload.config_data.ReqMeta` 中。Scheduler 每步重复发送当前已经分配的完整 `block_ids_cpu`，worker 用它重建 CPU block table；`num_tokens_after_step` 与 `offload_token_start + offload_num_tokens` 同时存在。

穿刺没有完整 Main lifetime reservation，因此没有 stable reservation identity、future reserved suffix 或 bound-prefix contract；也没有 `execution_epoch` 和 `command_seq`。Worker 主要用 request ID 和 `getattr()` 查找状态，无法区分同一 request/epoch 的旧 step command、preemption 后的新 Indexer ownership 或已经释放并复用的 Main block IDs。

目标实现保留 fused worker 真正需要的 Main Host block table 和 D2H range，但不复制穿刺的歧义字段、冗余 token total 或动态 Host allocation contract。

## 普通 MooncakeConnectorV1 怎么做

普通 V1 的 request metadata 每次包含 local/remote block IDs、remote engine/request/host/port、P TP/PCP/DCP topology、remote block size、prompt block count 和 external/computed token 数。它通过 `do_remote_prefill` gate 对每个 request 只启动一次 receive，因此不需要 execution epoch、per-epoch command sequence 或跨 preemption destination reservation。

Blockwise DSA 继续从普通 V1 `kv_transfer_params` 读取 remote rendezvous/source input，但 Decode scheduler 必须先把它解析为本 ADR 的 typed fields。Worker 不能直接消费开放的 `kv_transfer_params` dict。

## 考虑过的方案

- 搬运普通 V1 与穿刺字段。该方案最接近现有代码，但会在每个 request 重复 topology/layout，保留歧义 block names 和冗余 token totals，并缺少 stable reservation identity；不采用。
- 显式最小完备 fields。Static topology 留在 local configuration/rendezvous，positional address layout 留在 handshake，完整 future reservation 留在 scheduler；step metadata 只传 remote source reference、semantic source blocks、current destination binding 和 lifecycle progress；采用。
- Handle-only delta。首次 bind block IDs 后，后续只发 reservation/epoch handle。它减少 metadata，但要求 worker 维护可恢复镜像并新增 missed/out-of-order command resync protocol；首版不采用。

## RemoteSource

`RemoteSource` 只在 action 需要读取 Prefill source 时出现：

- `remote_engine_id`、`remote_host` 和 `remote_port` 必须命中一个已经 ready 的 DSA handshake session；
- `remote_request_id` 是 Prefill source ownership 使用的 request identity，不假定与 Decode local `request_id` 相同；
- `indexer_block_ids` 和 `main_block_ids` 在 Decode step metadata 内继续使用 semantic names；Main K/V 共用 Main block list，可选 Indexer scale 与 Indexer 共用 Indexer block list。按照 ADR 0022，从这些 block IDs 到 remote/local layer address arrays 的解析使用跨端 positional ABI；
- source TP leader 和 P TP/PCP/DCP 从 local configuration 与普通 V1 rendezvous 计算，multi-node rank endpoint 命中 positional handshake session；block size、page ratio 和 tensor layout compatibility 由 deployment gate 保证，不在每个 request 重复；
- 不携带 raw address、source generation、source expiry、remaining TTL 或 launch grant。

## DestinationOwnership

`main_reservation_id` 是 scheduler 为一次 Main lifetime reservation 分配的稳定 opaque integer identity。它跨 execution epoch 保持不变，reservation release 后不能为同一 live scheduler 中的新 ownership 立即复用。

`main_reservation_block_count` 表示 scheduler 已经隔离的完整 reservation capacity，但不暴露 future suffix 的物理 block IDs。Scheduler tracker 是完整 reservation block list 的唯一权威来源。

`main_bound_host_block_ids` 是当前 command 可以访问的、按逻辑 token 顺序排列的 reservation prefix。它可能包含本 command 即将写入、但尚未成为 valid Main 的 block，因此不能把 `len(main_bound_host_block_ids)` 解释为有效 token boundary。对同一个 live reservation，后续 command 只能保持或 append 该 prefix，不能重排、缩短后继续访问、替换既有 block ID 或超过 `main_reservation_block_count`。

`indexer_hbm_block_ids` 绑定当前 execution epoch。Preemption retire 旧 epoch 后，新 epoch 必须重新发布 core 新分配的 Indexer IDs；旧 epoch command/result 不能命中新 binding。

Temporary Main HBM block IDs 不进入 DSA step metadata。首版只支持 `fused_overlap`，worker 使用当前 model execution 的 slot mapping 计算 D2H source；scheduler 可以在本地 `ExecutionEpochState` 中保留 temporary Main HBM ownership，但不能把它复制成 worker 的第二份 source-of-truth。

## LifecycleCommand

`execution_epoch` 区分同一 request 的 preemption/resume execution。`command_seq` 在同一 `(request_id, execution_epoch)` 内对新 command 严格递增，用于区分 receive、后续 fused D2H、replay/cancel 和 late completion。相同 sequence 的完全相同 command 可以作为幂等重复处理；相同 sequence 的冲突内容必须 fail closed。

`num_computed_tokens` 和 `num_external_tokens` 沿用 vLLM scheduler 已有 token state，用于验证 P-to-D source/destination block coverage。它们不是新增的 `valid_token_count`、`transfer_token_start` 或 `transfer_token_count`。

`preserved_main_tokens` 是 command 开始前已经证明由同一 live Main reservation 持有的 valid prefix。Transfer-failure replay 必须为 `0`；preemption compute replay 只有在 ADR 0009 的 validity 条件成立时才能大于 `0`。

`d2h_token_start` 和 `d2h_token_count` 只控制 Decode 每步 `fused_overlap` Main D2H，不描述 P-to-D blockwise transfer。`num_tokens_after_step` 不进入新 schema，因为 D2H end 可以由两者相加得到。

## 集中校验

Envelope factory/validator 至少执行以下检查：

- `request_id` 非空，epoch/sequence 和所有 token/count fields 非负；
- 需要 Prefill read 的 action 必须有 `RemoteSource`；不读取 Prefill 的 replay/cancel command 不能携带可启动 remote transfer 的 source；
- remote endpoint 必须命中已经取得 positional layer/address arrays 的 handshake session；connector 不据此宣称已验证 remote mode、role、topology 或 tensor layout compatibility；
- semantic source block lists 与现有 token state、Main block size 和 Indexer page ratio 能够相互覆盖；partial block 仍按完整 block/page 传输；
- reservation identity 未释放，capacity 与 scheduler tracker 一致，bound Host IDs 是其有序 prefix、非零、无重复且不超过 capacity；
- Indexer IDs 属于当前 epoch；新 epoch 不得沿用旧 Indexer binding；
- `preserved_main_tokens` 不超过 bound Main capacity；transfer-failure replay 时必须为 `0`；
- 非零 fused D2H range 不能越过 bound Main capacity，并且只能写入从当前 valid prefix 开始的连续 token range；
- cancellation/quiesce command 不能同时要求启动新的 remote read 或 fused D2H；
- 同一 epoch 新 `command_seq` 必须前进；重复 sequence 内容不一致时 fail closed。

具体 action-to-field matrix 按 ADR 0020 的 action/result matrix 补齐。

## 结果

- Scheduler 独占完整 Main reservation block list 和 release ownership；worker 不能释放 reservation，也不需要接收 future reserved block IDs。
- Worker 只绑定当前 command 可访问的 Main prefix。新 block 在 sequence 增长时由 scheduler append 到 bound prefix，尚未 bound 的 future suffix 不能被寻址或写入。
- Worker-to-scheduler result identity 至少包含 `request_id`、`execution_epoch`、`command_seq` 和 local TP rank；exact result enum 由 ADR 0020 确定，exact TP coverage 和跨 step accumulation 由 [ADR 0021](0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md) 确定。
- Static topology/layout 不在 per-request metadata 重复；remote engine/host/port 解析 source endpoint 后使用 ADR 0022 的 positional handshake arrays，P/D layout compatibility 由 deployment gate 保证。
- 普通 V1 metadata 和非 DSA path 保持不变。

## 预计实现影响

在 ADR 0017/0018 已接受的 metadata family 和 nested envelope 基础上，本方案相对直接字段搬运预计增加约 130-210 行 production Python、240-380 行 focused unit tests，编码与 CPU/mock UT 约 3-5 个工程日，不包含 NPU E2E。预计涉及：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py`：immutable value objects、factory 和 validator；
- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：解析普通 V1 source input，维护 reservation/epoch/command sequence 并构造 envelope；
- blockwise SFA scheduler subclass 所在文件：完整 reservation ownership、bound-prefix projection 和 lifecycle counters；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`：typed Main bound-prefix table 与 fused D2H range adapter；
- `vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/worker.py`：仅在复用其 receive/drain adapter 时修改，不能继续用 `getattr()` 解释 DSA fields；
- connector 和 focused SFA worker tests：source normalization、reservation binding、epoch/sequence、token range、非法组合和 default-path isolation。
