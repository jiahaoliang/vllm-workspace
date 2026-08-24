# MooncakeConnectorV1 Blockwise DSA PD Offload 设计

状态：设计决策与 issue 01-07 已闭环；CPU/mock validated；NPU planned / not run

本文解释 [spec.md](spec.md) 中交付合同背后的技术设计、决策依据和失败边界。它是实现参考，不替代 accepted ADR、spec、implementation issue 或独立验证证据。

## 文档关系与当前状态

- [spec.md](spec.md) 是交付与验收合同，当前 production 实现为已发布的 vLLM-Ascend replacement commit `7401ae79c`，CPU/mock evidence见独立验证报告。
- [docs/adr/](docs/adr/) 保存架构决策及其取代关系。ADR 0003 已被 ADR 0022 取代，ADR 0007 已被 ADR 0008 取代，ADR 0017 的 handshake 部分已被 ADR 0022 取代；其余在本设计中引用的决策均按各 ADR 当前状态解释。
- Implementation issues 是执行状态的权威来源，线性 blocking chain [01](issues/01-blockwise-dsa-opt-in-control-plane.md) -> [02](issues/02-positional-data-plane-main-reservation.md) -> [03](issues/03-phase-a-request-lifecycle.md) -> [04](issues/04-exact-tp-lifecycle-fused-d2h.md) -> [05](issues/05-all-tp-transfer-failure-recovery.md) -> [06](issues/06-preemption-cancellation-ownership-recovery.md) -> [07](issues/07-phase-b-validation-npu-plan.md) 已全部 `resolved`。
- Replacement production code、focused DSA/SFA、public Scheduler lifecycle、完整 connector/default V1 和 broad CPU/mock regression已完成，证据见 [CPU/mock validation report](cpu-mock-validation-report.md)。完整CPU root仍有5个未修改baseline测试的缺失import failure。NPU runtime未执行，8个mandatory case必须保持`planned / not run`，直到未来保存真实运行证据。

若文档之间出现冲突，先按 accepted/superseding ADR 核对具体架构决策，再修正 spec 的交付合同和受影响 issues；本 design 只负责同步解释，不能单独改变实现范围。

## 目标

在不启用 Prefill layerwise reuse 的前提下，为 `MooncakeConnectorV1` 增加显式的 blockwise DSA PD offload mode：

```text
Indexer cache: Prefill NPU -> Decode NPU/HBM       (D2D)
Main KV cache: Prefill NPU -> Decode swapped DRAM (D2RH)
```

目标实现迁移 `mooncake_layerwise_to_dram_connector.py` 已打通的 DSA destination-memory 和完成语义，但保留 `MooncakeConnectorV1` 的 request-level block transfer 与 Decode-initiated pull。

## 范围

首版范围已经确认：

- 在 `MooncakeConnectorV1` 内增加 mode，不新增另一个公开 connector；
- Indexer cache 使用 D2D，Main KV cache 使用 D2RH；
- 两条传输链路都采用 block 粒度；
- 仅支持 Prefill 为 `kv_producer`、Decode 为 `kv_consumer` 的 PD disaggregation；
- 复用 Decode 的 `fused_overlap` sparse-offload lifecycle；
- 不使用 Prefill layerwise reuse、layerwise push 或 layerwise save/load hooks；
- 首版不支持 `kv_both` 或 P/D colocate。

该目标是 vLLM issue #48203 的一个变体：Decode 使用 DSA offload，但 Prefill 不使用 RFC 中的 layerwise reuse/offload 方案。

## Mode 与启动契约

新行为由以下配置显式开启：

```text
kv_connector_extra_config.dsa_pd_offload=true
```

该配置未提供或为 false 时，`MooncakeConnectorV1` 的现有行为必须完全保持不变。

Prefill 必须满足：

```text
kv_role=kv_producer
use_offload=false
```

Decode 必须满足：

```text
kv_role=kv_consumer
use_offload=true
kv_offload_mode=fused_overlap
kv_connector_extra_config.sfa_kv_offload_backend=mooncake
```

该 mode 要求 P/D 配对部署。按照 [ADR 0022](docs/adr/0022-use-the-puncture-positional-handshake-abi.md)，connector 不再通过自描述 handshake 证明双方的 mode、版本和 tensor layout 一致；这些一致性被记录为流量进入前必须满足的 deployment compatibility preconditions。Local role 或 offload 配置可以在各自进程初始化时校验，但 P/D 跨端错配属于 unsupported configuration，可能显式失败，也可能 silent corruption。本 feature 只提供前置约束、检查方法和证据要求，不实现或选择 production deployment system、manifest generator、release gate 或 admission controller。

## Handshake 与 tensor layout

P/D 双方沿用穿刺 connector 的 positional ABI。Handshake 按 layer name 保存四个等长数组：`tensor_group_idx`、`kv_caches_base_addr`、`block_len` 和 `block_size_scale`。Main K/V、Indexer 和可选 Indexer scale 的含义来自配对 image 中相同的 cache tuple/list position、layer-name/layer-index helper 和 transfer builder，不在 wire metadata 中使用 semantic role 命名。

Connector 只检查本地能够直接证明的结构和 registration 事实，例如数组等长、地址与 block geometry 可用、Swapped Main pool 容量与注册成功。Connector 不跨端校验 protocol version、mode、dtype、shape、memory kind、page ratio、leader replica coverage 或 tuple ordering，也不提供 compatibility hash。

Feature 部署文档规定，配对 P/D 在流量进入前必须使用同一个 immutable image digest、相同 model/configuration fingerprint 和 positional ABI，并禁止 mixed-version rolling upgrade。实际执行这些检查的外部部署系统不在本开发范围内。违反该前置条件时，transfer 可能在合法地址上成功但写入错误 tensor；此类 silent corruption 不会触发 transfer-failure replay。

首版的 block/page compatibility 明确为：

- Main K/V 的 P/D token block size 和每 block 字节数必须分别相等；
- Indexer 允许一个 Decode page 容纳整数个 Prefill page，Decode page 的 token capacity 和字节数必须按同一个正整数比例放大；
- 不支持 Prefill Indexer page 大于 Decode page、非整数 page ratio，或需要 Main block 拆分、拼接和重排的 layout；
- 上述静态关系属于文档化 deployment compatibility preconditions，不由 connector handshake 跨端证明，也不由本 feature 实现 production gate；request-level token 范围与实际 block list 的一致性仍在请求进入传输前校验。

Tuple/list position 是首版 P/D 共享 ABI。任何位置、可选项或 layer mapping 变化都要求配对 P/D 同时升级 image，并刷新部署配置 fingerprint。

## 拓扑契约

新 mode 保持 `MooncakeConnectorV1` 已有约束：

- `P_TP >= D_TP`；
- Decode pipeline parallel size 必须为 `1`。

在此基础上，首版沿用穿刺 connector 的固定 leader mapping，并增加更严格的 mode-specific 约束：

```text
P_TP % D_TP == 0
```

该整除要求不是普通 `MooncakeConnectorV1` 的通用约束，只在 `dsa_pd_offload=true` 时生效。

Decode scheduler 同时继承当前 SFA 的正确性约束：

```text
DCP * PCP == 1
```

`P TP8/DP2 -> D TP2/DP8` 只是测试计划的第一个拓扑，不是产品硬约束。当前环境无法部署该拓扑，因此本工作只生成 NPU end-to-end 测试计划，不会声称已经执行或验证该计划。

## TP source coverage

首版不使用普通 Mooncake 的 request-hash replica selection，也不支持多个 P TP shard 在 D 侧拼装。对一个已经路由到具体 P DP replica 和 D DP replica 的 request，定义：

```text
ratio = P_TP / D_TP
TP leader group(j) = [P_(j * ratio), ..., P_((j + 1) * ratio - 1)]
leader(j) = P_(j * ratio)
source(D_j, main_k)        = leader(j)
source(D_j, main_v)        = leader(j)
source(D_j, indexer)       = leader(j)
source(D_j, indexer_scale) = leader(j), when present
```

例如 `P TP8 -> D TP2`：

```text
P0 is the payload source for D0; P1-P3 send no payload.
P4 is the payload source for D1; P5-P7 send no payload.
```

非 leader rank 可以参与既有控制与完成协调，但不能写入 Indexer HBM 或 Main Host destination。该规则避免同组多个 P rank 覆盖同一 D block，并明确假定 leader 持有目标 D TP 所需的完整 Main 与 Indexer replica。按照 ADR 0022，该 placement 是文档化部署前置条件，handshake 不证明完整 replica，本 feature 也不实现跨 deployment 校验；首版遇到需要多 P shard 拼装的 layout 属于可能 silent corruption 的 unsupported configuration。

DP 不参与同一份 tensor 的拼装。每个 request 只从实际处理该 request 的 P DP replica 内选择 TP leader，不跨 P DP replica 混合 block ID 或 memory address。

## 组件职责

### Prefill scheduler

Prefill 继续使用 `MooncakeConnectorScheduler` 及其现有的 request-finish metadata flow。它不分配 Decode Host block，不在 scheduler state 中接收 Decode Host block ID，不运行 `SFAPDCpuOffloadScheduler`，也不参与 layerwise hooks。

Prefill worker 仍需要 mode-specific 改动，用于暴露 Main K/V 与 Indexer 的 source layout，并让每个 TP leader 为对应 Decode TP 提供完整 replica。非 leader 不发送 payload。Prefill scheduler 基本不变，不等于 Prefill worker 不变。

### Decode scheduler

Decode 使用一个继承自 `SFAPDCpuOffloadScheduler` 的新 blockwise scheduler，负责：

- 分配 Decode HBM 中的 Indexer cache destination block；
- 从 SFA CPU block manager 为请求建立 Main lifetime reservation，并区分 active 与尚未使用的 reserved block；
- 在 connector metadata 中同时携带两类 destination block list；
- 跟踪完整 receive lifecycle；
- 在失败、取消、preemption 或正常完成时协调两个 pool 的资源；
- 在 preemption 后保留 Main reservation 和已确认有效的 Main prefix，retire 旧 execution epoch，并为 Decode 本地 full-sequence compute replay 重建 Indexer ownership。

该 scheduler 直接集成到 `MooncakeConnectorV1`。首版不引入独立的 destination-memory module。

### Decode worker

每个 Decode TP 拥有独立的 local swapped Main pool。Worker 绑定 runner-owned Host K/V tensor，向 Mooncake 注册本地 Indexer HBM 与 swapped Main memory，解析 Prefill source block，并执行两条 pull 链路。

当前 `model_runner_v1` 的 allocation 路径和 `sfa_kv_offload_worker` 的 binding 路径是复用基线。只有 blockwise connector 缺少必要 interface 或 lifecycle hook 时才修改它们。

## 请求生命周期

对于 remote-prefilled request：

1. Decode 识别远端可用的 prompt token 数量。
2. Decode 根据请求的最大允许序列长度检查并建立 Main lifetime reservation；当前容量不足时保持 waiting，不分配 destination。
3. Admission 成功后，Decode 分配 Indexer HBM block，并只激活覆盖 prompt 的 Main swapped-DRAM block。
4. Prefill 完成 prompt，并通过 Mooncake 现有 request-level PD flow 返回 source block metadata。
5. Decode 解析 Prefill source coverage 和本地两类 destination block list。
6. Decode 通过一个 `TransferSync` phase 完成 Indexer D2D 传输。
7. Indexer `TransferSync` phase 返回后，Decode 再通过独立的 `TransferSync` phase 执行 Main D2RH 传输。
8. 只有两条链路都成功，请求才上报为 receive-complete。
9. Decode 随后通过现有 `fused_overlap` 路径，从 HBM 消费 Indexer，从本地 swapped pool 消费 Main KV；序列跨过 Main block 边界时激活已经预留的下一个 block，不再申请新容量。

Indexer 与 Main 明确采用串行传输。穿刺 connector 已经拆分两者，因为一个 ADXL buffer-mode `TransferSync` 不能混合 NPU-to-NPU 与 NPU-to-Host destination。首版 blockwise 实现保留该顺序，不引入跨链路 overlap。

## Partial block

首版沿用穿刺 connector 在 `fused_overlap` 下的 partial-block 语义：最后一个只含部分有效 token 的 source block/page 仍按完整物理长度传输，connector 不按有效 token 数裁剪传输字节，也不负责清零尾部未使用位置。

对 Main KV，Decode 按 `cdiv(prompt_len, main_block_size)` 从 local swapped Main pool 分配完整 Host block，因此 partial Main block 也直接接收到 Host memory，不使用 legacy non-fused 路径中的 `partial_hbm_bid`。对 Indexer，Prefill 的完整 source page 写入 Decode page 的对应 `page_slot`；Decode page 中未被请求覆盖的其他 slot 不属于该请求的有效 cache。

Decode 使用已有的 `prompt_len`、`num_computed_tokens`、`num_external_tokens` 和 request sequence length 确定有效 token 范围。首版不新增 `valid_token_count`、`transfer_token_start` 或 `transfer_token_count` 字段，避免为同一个 request token 边界引入第二个可能不一致的事实来源。传输前必须校验现有 token 状态与 source/destination block 数能够相互覆盖；不一致时该请求 fail closed，不能把尾部未使用位置视为有效 KV。

## Destination memory

Main KV 使用 [ADR 0001](docs/adr/0001-use-per-decode-tp-local-swapped-main-pools.md) 已确认的 per-Decode-TP local swapped-pool 方案。每个 Decode TP 独立分配、注册、接收并消费一个完整 local Main pool。

该选择用额外的 Host memory 与传输量换取 process-local ownership，并与当前 `fused_overlap` execution path 保持一致。

### Swapped Main pool capacity

首版沿用穿刺 connector 的 `fused_overlap` 容量基线。每个 Decode TP 的 local swapped Main pool 物理 block 数等于 `kv_cache_config.num_blocks`，block ID `0` 保留，因此通常可分配的 request block 数为：

```text
usable_main_host_blocks = kv_cache_config.num_blocks - 1
```

首版不新增 Host pool capacity multiplier。Scheduler block manager 的物理容量、runner-owned Host Main tensor 的第一维容量和 Mooncake 注册范围必须在 startup 阶段严格一致；任一 TP 不一致时初始化失败，不能用较小值静默截断。

每个 Decode TP 还必须在 startup 阶段证明一个最大合法请求能够独占装入该 pool：

```text
max_request_main_blocks = cdiv(max_model_len, main_block_size)
max_request_main_blocks <= usable_main_host_blocks
```

不满足时 Decode 初始化 fail closed，并报告 `max_model_len`、Main block size、物理/保留/可用 block 数和最大可支持 token 数。可行的配置修复是降低 `max_model_len`、增加 KV block 与对应 Host memory，或关闭 `dsa_pd_offload`；不能启动后等待一个永远无法满足的请求。

Runner 绑定 Host Main tensor 后，worker 必须再次以实际 tensor 校验所有 Main K/V layer 的 block capacity、block size、dtype、contiguous layout 和 memory kind，并确认与 scheduler capacity 及 Mooncake 注册范围一致。

### Admission and Main lifetime reservation

首版采用 [ADR 0006](docs/adr/0006-reserve-main-capacity-for-the-request-lifetime.md) 的完整生命周期容量预留，不采用 prompt-only admission。对每个 remote-prefilled request，Decode 计算：

```text
request_max_tokens = min(max_model_len, prompt_len + request.max_tokens)
reservation_blocks = cdiv(request_max_tokens, main_block_size)
```

在 `get_num_new_matched_tokens()` 阶段，如果当前 free Main blocks 少于 `reservation_blocks`，connector 返回 `(None, False)`。请求保留在 vLLM waiting queue，且本轮不分配 Indexer HBM、Main Host block，不通知 Prefill 开始传输。该行为复用现有 connector contract，不修改 vLLM core，也不回退到本地 Prefill。

Reservation 等待采用 [ADR 0008](docs/adr/0008-use-per-step-head-of-line-reservation-admission.md) 的 per-scheduling-step head-of-line blocking。Scheduler 仍按配置的 `fcfs` 或 `priority` 顺序调用 connector；本步第一个请求因 free Main blocks 不足返回 `None` 时，Decode connector 设置一个 step-local admission gate，本步后续 DSA remote-prefill 请求也返回 `None`，不能由较小 reservation 绕过。`build_connector_meta()` 完成本步收尾时清除 gate，下一 scheduling step 再按 vLLM 当时的队首顺序重新判断，因此不需要在 connector 中长期复制一套 request queue，也能跟随 priority 重排。

Admission 成功后，Decode 一次性从 CPU block manager 取得完整 reservation。Reservation 不新增物理 DRAM；Host tensor 已在 startup 分配，它只隔离一组 block ID，防止其他请求占用。Tracker 必须区分：

- active Main blocks：已经承载 prompt 或 Decode 新生成有效 KV 的 reservation prefix；
- future reserved Main blocks：属于该请求但尚未承载有效 KV 的 reservation suffix。

首次 D2RH 只发布和写入覆盖 prompt 的 active prefix。Decode 序列跨过 Main block 边界时，将下一个 future reserved block 转为 active，不再调用动态容量分配。Preemption 只 retire 当前 execution epoch，active 与 future reserved blocks 继续归该请求所有；正常完成、提前结束、取消或已经返回且 quiesced 的失败路径才最终归还完整 reservation。Cancellation 按 ADR 0010 两阶段释放；无法产生 quiesced ack 的 operation 按 ADR 0016 保持 ownership 隔离，不承诺自动归还。

该方案以较低的并发利用率换取 running request 的容量确定性。请求声明较大的 `max_tokens` 但提前结束时，未使用 reservation 在请求释放前不能被其他请求使用。Head-of-line blocking 还可能闲置不足以满足队首、但足以满足后续小请求的 free capacity；首版接受该利用率损失，以避免大 reservation 被持续小请求流量饿死。

### Admission blocking and Prefill source TTL

首版不在 connector 的 pre-admission 路径增加本地 timeout。`get_num_new_matched_tokens()` 返回 `None` 时，vLLM connector interface 只表达“稍后重试”，没有在 destination allocation 之前安全终止单个请求的返回值；用异常模拟 timeout 可能扩大为 scheduler 或 engine failure，而修改 vLLM core 不在首版范围内。

首版沿用普通 MooncakeConnectorV1 的 admission wait 边界，不新增 feature-specific serving/proxy first-response deadline。当前 proxy 的 `timeout=None` 不因本 feature 改变；客户端或 routing 层已有的取消仍通过正常 cancellation 路径清理 Decode 本地等待或 reservation 状态。

Prefill source block 继续使用 MooncakeConnectorV1 已有的 `VLLM_MOONCAKE_ABORT_REQUEST_TIMEOUT` 作为 hard TTL，默认值为 480 秒。P 收到 Decode 完成通知时提前释放；没有完成通知时在 TTL 到期后允许强制释放。按照 [ADR 0015](docs/adr/0015-do-not-check-prefill-source-ttl-before-transfer.md)，首版不增加 source lease refresh，也不让 Decode admission wait 延长 P 的 hard TTL；D 不检查等待时长、source expiry 或 current ownership，仍按 remote block IDs 启动 transfer。

这意味着“P source 在 D 启动并完成 Indexer/Main 前未被 TTL 回收”是未由代码强制执行的 operational assumption。等待跨过 TTL 后，transfer 可能显式失败并进入 replay，也可能从已复用但仍合法的地址成功读取错误 KV；首版不能检测后一种 silent corruption。TTL overrun 不属于首版正确性保证，NPU 测试计划只把它作为 risk-characterization case。

Work-conserving bypass 作为后续优化点保留：未来可以移除 step-local gate，让后续较小 reservation 使用暂时空闲的容量，但必须同时解决大请求 starvation、Prefill source TTL 过期和取消/cleanup 的协调问题，不能只删除 gate。

## Preemption recovery

首版采用 [ADR 0009](docs/adr/0009-replay-preempted-requests-locally-on-decode.md) 的 preemption-recompute 语义，并区分 full-sequence compute replay 与 cache rebuild。一个已经完成 P-to-D 接收、并在 Decode 运行的请求被 vLLM preempt 后，不重新从 Prefill 拉取旧 KV；恢复时由 Decode 从 token 0 本地执行 full forward replay，为所有 layer 重建整个有效 token 范围的 Indexer。Main lifetime reservation 和 preemption 前已经确认落入 Host 的 Main prefix 保持有效，replay 不重复 D2H 该范围。这是异常恢复路径，不是正常请求增加 Decode-side Prefill stage。

该选择来自 vLLM 默认行为，不是穿刺 connector 已经正确实现的能力。vLLM core 会在 preemption 时释放 NPU blocks、把 `num_computed_tokens` 重置为 `0` 并重新入队；普通 Mooncake remote pull 又会在第一次 destination allocation 后清除一次性的 `do_remote_prefill`。穿刺虽然由 core 在 resume 时分配新 Indexer blocks 并通过 forward 隐式重建 Indexer，但 connector tracker 仍保留第一次 pull 的旧 Indexer IDs；它还会从 token 0 重复 Main D2H。因此目标实现必须显式重新绑定 group 0、retire 旧 worker state 并跳过 preserved Main range 的重复 D2H，不能直接复制穿刺状态管理。

Tracker 使用两个生命周期：`MainReservationState` 跨 preemption 保留 Main CPU block IDs、capacity 和 `preserved_main_tokens`；`ExecutionEpochState` 只属于一次运行，持有 epoch、当前 Indexer IDs、temporary Main HBM IDs 和 transfer/worker state。Preemption 不释放 Main reservation，而是 retire 旧 epoch。Resume 从 `scheduled_cached_reqs.new_block_ids[group 0]` 取得新 Indexer IDs，并建立新 epoch；旧 epoch 的 late completion 必须被拒绝。

只有上一执行步 D2H 已完成、Main reservation ownership 连续、layout 未变化且 preserved boundary 与 request 状态一致时，才复用 Main。无法证明时将 `preserved_main_tokens` 降为 `0`，在同一次 full replay 中保守地重写 Main。该内部恢复边界不改变 P/D partial-block protocol 不新增 `valid_token_count` 的决定。

该方案可能产生明显性能问题。Preemption 发生得越晚，Decode 重算的 prompt 与已生成 token 越多；preserved Main reuse 能避免重复 Main D2H，但不能消除模型 forward 和 Indexer 重建。长上下文或频繁 preemption 可能显著增加恢复延迟、降低吞吐并放大 tail latency。验证必须将 preemption 次数、replay token 数、Main reused token 数、跳过的 D2H bytes 和恢复耗时与正常 PD transfer 指标分开记录。

后续性能优化采用候选 4 的方向：preemption 后重新从 Prefill 拉取所需 cache，而不是长期依赖 Decode full forward replay。基于首版保留的 Main，优先评估只重拉 Indexer；只有 Main 也无法保持有效时才重拉 Indexer/Main。该方向需要额外解决 Prefill source 的 request-lifetime ownership 或可重建性、再次 rendezvous、TTL/lease、transfer generation、重复传输幂等性以及 P/D 双侧 cleanup，首版不实现。

## Cancellation cleanup

首版采用 [ADR 0010](docs/adr/0010-use-two-phase-cancellation-drain-and-ack.md) 的两阶段 cancellation。已经取得 Main reservation 的请求被取消时，scheduler 只将其标记为 `CANCEL_PENDING`，禁止新的 receive、replay 和 D2H，并从 `request_finished_all_groups()` 返回 `delay_free_blocks=True`；它不能立即归还 Main block IDs。Worker retire 对应 execution epoch，并等待已提交的 Indexer D2D、Main D2RH 或 fused D2H 不再访问 destination。Worker 先按 active `(request_id, execution_epoch)` 过滤 stale/duplicate completion，清理 request/destination/pending state并达到 worker-local Quiesced；cancellation 不产生 typed `QUIESCED` local result。

按照 [ADR 0020](docs/adr/0020-use-lifecycle-actions-and-terminal-local-results.md) 和 [ADR 0021](docs/adr/0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md)，每个 worker 达到 Quiesced 后先向自己实际读取、且尚未通知完成的 Prefill leader endpoint best-effort 发送一次现有 `DONE_RECVING_MSG`，再把 request ID 放入普通 `finished_recving` set 一次；普通 receive 已通知的 endpoint 不重发。vLLM `KVOutputAggregator` 按 expected worker count 跨 step 汇聚；aggregated request ID 到达 scheduler 后，`update_connector_output()` 才能 release-once Main reservation，随后 core 释放 delayed NPU blocks。普通 signal 只携带 request ID，因此 worker 必须在上报前完成 epoch 和 duplicate guard。`finished_recving` 对 terminal request 不能把请求重新放回可运行状态。

Cancellation 的阶段规则为：admission 前没有 reservation，立即完成；admission 后统一进入两阶段 cleanup；`WAITING_FOR_REMOTE_KVS` 停止启动后续 transfer phase，已经进入的底层同步 phase 必须 drain 到返回，首版不增加 reliable/native cancel；`RUNNING` 先 drain 当前 fused D2H/save barrier；`PREEMPTED` 或 `REPLAY_PENDING` retire 当前 epoch，并在 worker Quiesced 后释放仍保留的 Main reservation。重复 cancellation、重复 ack 和旧 epoch completion 都必须是幂等 no-op。

`DONE_RECVING_MSG` 是 Prefill source-release notification，不是 cancellation reason，也不是 Decode 本地 ack。目标 cancellation path 必须先尝试该通知，再暴露普通 `finished_recving`；通知发送或 ACK 失败时由现有 Prefill source TTL 兜底，不阻止已经 Quiesced 的 Decode 释放本地 ownership。如果 worker 无法进入 quiesced，按照 [ADR 0016](docs/adr/0016-do-not-watchdog-unquiesced-operations.md) 沿用普通 `MooncakeConnectorV1`：D Main reservation 和 delayed NPU blocks 在 live process 中无限期保持隔离，不发送伪通知，不增加 drain watchdog、fatal latch 或自动 fail-stop，也不能为了回收容量而强制复用。恢复依赖 operation 最终返回、已有 process failure 或外部重启。

## Transfer phase failure ordering

首版采用 [ADR 0011](docs/adr/0011-stop-before-main-when-indexer-transfer-fails.md) 的 per-Decode-TP local phase gate。对当前 request 和 execution epoch，每个 Decode TP worker 必须先完成自己的 Indexer D2D；只有 local Indexer phase 最终成功后，该 worker 才能启动 local Main D2RH。Local Indexer 的同步调用最终失败时，该 worker 不得提交 Main task，不得增加 `preserved_main_tokens`，也不得上报 local done。

该语义不同于穿刺代码。穿刺的 Indexer leg 失败只会把 request 加入 `failed_reqs`，控制流仍继续调用 Main leg，并继续后续 layer，最后才统一上报失败；它也没有可证明 Main validity 的 per-leg 状态。目标 blockwise Decode-pull 实现沿用普通 `MooncakeConnectorV1` 的 fail-fast 方向，不复制这项 best-effort 行为。

Local gate 不增加跨 TP barrier。其他 Decode TP 如果已经通过各自的 Indexer gate，可以继续或已经完成 local Main；但跨 TP 的局部成功不能单独形成 request-level receive-complete。独立的 DSA worker result metadata 通过 `KVConnectorWorkerMetadata.aggregate()` 只合并当前 engine step 内的 local phase facts；scheduler connector 再按 `(request_id, execution_epoch, command_seq)` 跨 step 累积，并用 exact Decode TP rank coverage 决定 receive、failure、replay 和 fused-D2H transition。普通 `finished_recving` 不能单独决定这些语义，只在 scheduler 已知 request terminal 的 cancellation path 作为 all-worker Quiesced ack复用。

Indexer failure 发生后，Main lifetime reservation 在 failure handling 完成前仍保持隔离；Main 尚未开始不等于 reservation 可以立即释放。按照 [ADR 0014](docs/adr/0014-rely-only-on-mooncake-internal-retry.md)，Indexer 和 Main phase 在 Python connector 层都只发起一次同步 transfer 调用，依赖 Mooncake binding 的 internal retry；binding 最终返回失败时，按 [ADR 0012](docs/adr/0012-retry-transfer-then-replay-on-decode.md) 将整个 request 转入 D-side full-sequence replay。按照 ADR 0015，transfer 前不证明 P source 可靠。

Worker 只有在同步 transfer 已返回、所有 local transfer task 都停止访问 destination 后，才能上报 local replay-ready。所有 Decode TP 的结果聚合后，scheduler connector 在 core 消费 completion 前将 request 的 `num_computed_tokens` 置为 `0`，使等待请求恢复后从 token 0 本地执行 full forward。这里用于解除 `WAITING_FOR_REMOTE_KVS` 的 completion 表示 replay-ready，不表示 external KV receive-complete。该路径不使用当前只支持单 KV group request lookup 的 `invalid_block_ids`，也不修改 upstream vLLM core。

首版不增加 connector attempts、backoff 或 retry 配置；Mooncake internal retry 对 connector 不可见。Source TTL 沿用普通 V1，不增加 launch-time check。按照 [ADR 0013](docs/adr/0013-invalidate-main-on-all-tps-for-transfer-failure-replay.md)，任一 TP 的同步 transfer 最终失败并触发 request-level replay 时，所有 TP 都将 `preserved_main_tokens` 置为 `0`。Main reservation IDs 保持原 ownership，但 replay 从 token 0 重写所有 TP 的完整 Main prefix；failure 前其他 TP 已经成功接收的 Main 不复用。

## Unquiesced operation handling

首版按照 [ADR 0016](docs/adr/0016-do-not-watchdog-unquiesced-operations.md) 对同步 transfer 不返回、background handler 长时间无 completion 或 cancellation drain 无法产生 quiesced ack 的情况完全沿用普通 `MooncakeConnectorV1`，不增加 active-operation deadline、thread-health poll、per-request quarantine timeout、worker fatal latch、Kubernetes restart 前置条件或 Mooncake native cancel。

这类 operation 未返回时不能进入 transfer-failure replay，因为 replay 会重写同一 destination，而旧 DMA/D2H 是否仍会继续写入无法证明。对应 Main reservation、Indexer/Main destination 和 delayed NPU ownership 保持 pending/隔离；不产生 `finished_recving`，也不向 P 发送伪 completion。P source 仍由现有 480 秒 hard TTL 回收。若 operation 在 source TTL 后返回成功，可能读取已经复用的 source address，属于 ADR 0015 已接受的 Source TTL overrun correctness residual risk。

首版不保证该状态能够在有限时间内自动恢复。Operation 最终返回时恢复普通 success/failure 流程；worker/process 自身退出或外部重启时，Decode pool 和 request state 随进程生命周期重建。这一选择以保留罕见故障下的 hang、容量占用和潜在 TTL silent corruption 风险，换取不实现额外 watchdog/fail-stop subsystem。

## Metadata boundaries

首版按照 [ADR 0017](docs/adr/0017-use-a-separate-typed-dsa-metadata-family.md) 使用独立、强类型、按通信方向分离的 Decode step/result metadata。Prefill scheduler-to-worker 继续使用普通 `MooncakeConnectorMetadata`；Decode scheduler-to-worker 使用 DSA step metadata；Decode worker-to-scheduler 对 receive、failure、replay 和 fused D2H 使用可跨 TP 聚合的 DSA result metadata，cancellation 则复用普通 `KVConnectorOutput.finished_recving`。按照 ADR 0022，P/D worker layout 使用穿刺 positional handshake ABI，不属于 semantic metadata family。普通 V1 `ReqMeta`、`MooncakeConnectorMetadata` 和非 DSA request 路径不增加 optional DSA fields。

Scheduler/worker metadata 只携带 process-independent typed values 和 block IDs，不携带 tensor、event、thread 或每请求 raw address。Positional handshake 继续使用 MessagePack-compatible layer/address arrays，但不提供 semantic compatibility validation；普通 V1 `kv_transfer_params` 继续作为 JSON-compatible rendezvous/source input，由 Decode scheduler 转换成 DSA request metadata。Typed worker result identity 至少覆盖 request、execution epoch、command sequence 和 TP rank；冲突重复结果 fail closed，不能 last-writer-wins。Cancellation ordinary completion只携带 request ID，epoch和duplicate由worker-local guard在上报前处理。

`finished_recving` 仍复用 vLLM 的现有 transition hook。Receive-complete 和 replay-ready 路径中，scheduler 必须先在 `update_connector_output()` 消费匹配 epoch 和完整 TP coverage 的 typed DSA result；cancellation 路径不生成 typed result，aggregated ordinary completion直接表示所有 worker已通过本地Quiesced guard。

按照 [ADR 0018](docs/adr/0018-use-nested-value-objects-for-dsa-step-requests.md)，Decode scheduler-to-worker 的每个 request 使用一个强类型 envelope，并把 remote source、Decode destination ownership 和 per-step lifecycle command 拆成嵌套 value object。Request identity 位于 envelope 顶层，组合通过集中 factory/validator 校验；普通 V1 `ReqMeta` 保持扁平结构。

按照 [ADR 0019](docs/adr/0019-use-minimal-complete-dsa-step-fields.md)，step request 使用显式最小完备 fields：source 只携带 remote engine/request/endpoint 和 semantic Indexer/Main block IDs；destination 只携带 stable Main reservation identity/capacity、当前 command 可访问的 bound Host prefix 和当前 epoch Indexer IDs；lifecycle 携带 execution epoch、per-epoch command sequence、现有 external/computed token state、preserved Main boundary 和 Decode fused D2H range。完整 future reservation block IDs 只由 scheduler tracker 持有，不发送给 worker；static topology 来自 local configuration 和普通 V1 rendezvous，layer address layout 来自 positional handshake，跨端一致性只作为文档化部署前置条件。

按照 [ADR 0020](docs/adr/0020-use-lifecycle-actions-and-terminal-local-results.md)，scheduler actions 为 `RECEIVE_REMOTE`、`FUSED_D2H`、`PREPARE_REPLAY` 和 `QUIESCE`；typed local result kinds 为 `RECEIVE_COMPLETE`、`D2H_COMPLETE`、`REPLAY_READY` 和 `TRANSFER_FAILED`。只有 `TRANSFER_FAILED` 携带 `INDEXER_D2D` 或 `MAIN_D2RH` failure phase。`QUIESCE` 达到 worker-local Quiesced 后直接进入普通 completion channel，不产生 typed result。Indexer/Main 是一个 receive command 内的 worker-local serial phases，不拆成 scheduler actions。

`FUSED_D2H` 只有在当前 command 获得 exact TP `D2H_COMPLETE` coverage 后，才推进 confirmed Main valid prefix；该 transition 从不生成 `finished_recving`。Fused D2H 的同步调用或 TP status check 失败时沿用 SFA worker 的 fail-fast `RuntimeError`，不伪造 `TRANSFER_FAILED`、`D2H_COMPLETE` 或 connector completion。

按照 [ADR 0021](docs/adr/0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md)，DSA worker metadata 的 `aggregate()` 只合并当前 engine step 的 rank-aware typed local results；Decode scheduler connector 按 `(request_id, execution_epoch, command_seq)` 跨 step 累积。Expected coverage 是当前 routed Decode DP replica 内的精确 TP rank 集合 `set(range(D_TP))`，不包含其他 DP replica 或 Prefill ranks。相同完整 result 重复时幂等，冲突或 impossible future result fail closed，stale result 只记录并忽略。缺失 TP result 时保持 pending；任一 initial receive failure 也必须等待完整 TP terminal coverage 后才能向所有 TP 下发 `PREPARE_REPLAY`。Cancellation 是窄例外，只使用ordinary expected-worker-count aggregation。

## 预计源码改动

实现预计集中在以下文件：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：opt-in mode、Decode scheduler 选择、blockwise metadata/handshake、D2D/D2RH receive logic、cancellation ordinary completion和`DONE_RECVING_MSG` ordering；
- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py` 或同等隔离的 feature-local module：DSA step 和 worker result strong types；positional handshake layer metadata 可以放在该 module 或 `mooncake_connector.py`，但不构成 semantic contract；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`：绑定、寻址、消费和释放 local swapped Main pool 所需的 interface；
- `vllm_ascend/worker/model_runner_v1.py`：优先复用现有 runner-owned swapped allocation 与 `bind_runner_host_main` 路径，仅在现有 contract 无法被 connector 使用时修改；
- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_layerwise_to_dram_connector.py`：仅作为 DSA layout、memory registration、transfer ordering 和 completion semantics 的参考实现，不作为目标 connector 或目标 protocol。

这是改动量预估，不是固定 file allowlist。任何额外源码改动都必须由缺失 contract 驱动，不能从 layerwise connector 整体复制。

## 失败边界

已经确认：

- Local process 中不支持的 role、topology 或 offload 组合在 startup fail closed；P/D 跨端 mode/configuration mismatch 不保证由 handshake 检测；
- 单个 `max_model_len` 请求无法装入 per-TP Swapped Main pool 时 Decode startup fail closed；
- 任意一条传输链路失败都不能把请求标记为完成；
- 部分成功不能上报为 cache hit；
- Indexer D2D 是 per-Decode-TP local Main D2RH 的 hard gate；local Indexer 同步调用最终失败时该 TP 不启动 Main，也不建立 Main validity；
- Indexer/Main transfer 在 connector 层各调用一次，仅依赖 Mooncake internal retry；最终失败后整个 request 转入 D-side full-sequence replay；
- Transfer 前不检查 Prefill source TTL 或 ownership；TTL overrun 属于 unsupported operating region，显式 transfer failure 可以 replay，但成功读取已复用地址不能被检测；
- Transfer-failure replay 保留 Main reservation ownership，但统一令所有 TP 的 `preserved_main_tokens=0` 并完整重写 Main；
- Preemption 后首版在 Decode 本地执行 full-sequence compute replay、重建 Indexer 并复用已确认有效的 Main prefix；不重新从 Prefill 拉取，并将 compute replay 明确视为潜在性能退化路径；
- Admission 后 cancellation 采用两阶段 drain-and-ack，worker Quiesced 前不得释放或复用 Main reservation；Quiesced 是 worker-local state，不是 typed result；
- Unquiesced operation 不增加 watchdog、fatal latch、reliable cancel 或自动 restart contract；D ownership 在 live process 中保持隔离，P source 仍可能在 hard TTL 后复用，有限时间自动恢复和 TTL 后晚到成功的内容正确性均不属于首版保证。
- Blockwise DSA 使用独立、强类型、按方向拆分的 metadata family；普通 V1 metadata 不增加 DSA optional fields。`KVConnectorWorkerMetadata.aggregate()` 只合并同一 engine step 的 receive/replay/fused-D2H rank-aware facts，Decode scheduler connector 负责按 command identity 跨 step 累积并检查 exact TP coverage；cancellation复用普通completion。
- Decode scheduler-to-worker request 使用嵌套 `source`、`destination ownership` 和 `lifecycle` value object，并集中校验跨对象不变量；不使用扁平 optional-field envelope 或 per-action request union。
- Step fields 使用显式最小完备 schema；scheduler 独占完整 future Main reservation IDs，worker 只接收 reservation identity/capacity 和当前 command 可访问的 bound prefix，并以 `(request, execution epoch, command sequence)` 拒绝 stale command。
- DSA 使用 lifecycle-oriented actions 和 command-terminal local results；Indexer/Main failure 可触发 request-level replay，running request 的 fused D2H failure 首版继续 fail-fast，不伪造 connector completion。
- Typed worker result 使用 exact Decode TP rank coverage 和 scheduler-side 跨 step accumulation；匿名 count、重复 rank 或局部 TP success 不能形成 receive、failure、replay或D2H request-level transition。Cancellation只在terminal path复用ordinary count。
- P/D positional ABI、dtype、memory kind、page ratio 或 leader coverage 错配不保证被 connector 检测；feature文档要求外部部署流程核对image digest和配置fingerprint，但本开发不实现该流程。

Preemption recovery、Main ownership、execution-epoch 边界、cancellation cleanup、retry 层级、source TTL handling、unquiesced operation handling、metadata type boundary、worker-result aggregation 和 positional handshake ABI 已经确定。

## 验证边界

按照 [ADR 0023](docs/adr/0023-use-staged-phase-a-then-phase-b-validation.md)，后续实现采用 Phase A 后 Phase B 的分阶段测试门禁：

- Phase A 先运行 opt-in/default isolation、startup/configuration、positional block mapping、单请求 Indexer D2D -> Main D2RH ordering、Indexer/Main failure 和最小 reservation/replay/cleanup tests，快速验证基本功能线；
- Phase A 全绿后必须继续 Phase B，覆盖完整 lifetime reservation、HOL admission、preemption、drain-and-ack、Prefill source-release notification、ordinary all-worker cancellation completion、transfer-failure full replay、exact TP cross-step aggregation、fused D2H boundary、多请求交错和 default V1 regression；
- Phase A 只是快速反馈检查点，不能标记为 `CPU/mock validated`；只有 Phase A 和 Phase B 都通过才具有该状态；
- static、CPU/mock 和 NPU runtime evidence 分开记录，不能用 mock address calculation 证明真实 D2D/D2RH、NPU-addressable Host registration 或 fused kernel 正确性；
- 首版以 deterministic Phase A/Phase B matrix 作为 CPU/mock 门禁，不采用 property/model-based lifecycle testing；后者只作为后续增强候选。

测试按 ADR 0023 的 ownership 分为一个主 seam 和两个支持 seam：

- 主 seam 是 `MooncakeConnectorV1` public connector lifecycle，覆盖 opt-in/default isolation，以及从 admission、allocation、metadata、worker result 到 scheduler output consumption 和 request finish 的完整 request lifecycle；
- DSA metadata contract seam 直接验证 typed envelope、validator、action/result matrix、serialization-safe values、same-step `aggregate()` 和 scheduler-side cross-step exact TP accumulation；cancellation ordinary completion 在主 lifecycle seam验证；
- SFA memory-binding/data-plane seam 使用 fake tensor/address 和现有 registration、runner Host Main binding、fused-save interface，验证 Indexer HBM、Main Host、positional mapping、bound prefix 和 D2H range。

CPU/mock unit tests 必须在 `liangjiahao` namespace 的专用长期运行 CPU-only UT Pod 中执行，显式指定 test target，并通过 tar 同步当前 checkout。执行报告分别保存 Phase A 和 Phase B 的源码身份、命令与结果。

当前环境只生成以 `P TP8/DP2 -> D TP2/DP8` 为起点的 NPU end-to-end 测试计划。计划必须覆盖文档化 compatibility preconditions 的preflight、happy path、partial/multi-block、correctness oracle、ordering/failure injection、reservation pressure、preemption、cancellation、default V1 isolation 和 cleanup，并统一标记 `planned / not run`。Preflight是测试执行步骤，不是本feature实现production deployment system。在未来真实执行全部 mandatory cases 前，不得声称 `NPU runtime validated`。

## 决策闭环与下一阶段

当前架构决策已闭环。Metadata type boundary、per-request envelope、exact step fields、action/result enums、aggregation schema、positional handshake ABI、Phase A/Phase B CPU/mock matrix 和 NPU 测试计划成功标准均已确定。

Issue 01-07 已按 replacement architecture 重新闭环，当前 production tree 为已发布的 vLLM-Ascend commit `7401ae79c`。Focused DSA/SFA、connector/default V1 和排除已知baseline-broken文件后的broad CPU/mock regression全绿；完整CPU root明确保留`241 passed / 5 pre-existing failures`。下一阶段只在满足 [NPU E2E test plan](npu-e2e-test-plan.md) preflight 后执行真实runtime cases；在此之前不产生或推断NPU结果。
