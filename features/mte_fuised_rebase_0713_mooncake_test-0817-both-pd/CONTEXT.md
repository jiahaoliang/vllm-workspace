# vLLM Ascend KV 传输

本 feature branch 中 KV 传输与 offload 能力的领域语言。

## 术语

**Blockwise DSA PD offload**:
一种 PD 分离模式：Prefill 保持 block 粒度 KV 传输，Decode 使用 sparse KV offload，不启用 Prefill layerwise reuse。
_避免使用_: Layerwise D2RH connector、完整 RFC #48203 实现

**Indexer cache**:
用于选择 sparse-attention KV 条目的 device-resident 索引。在 Blockwise DSA PD offload 中，它从 Prefill device 传输到 Decode device。
_避免使用_: Index cache、D2RD cache

**Main KV cache**:
Sparse attention 完成选择后消费的完整 key/value 状态。在 Blockwise DSA PD offload 中，它从 Prefill device 传输到 Decode Host memory。
_避免使用_: Indexer cache、top-K buffer

**Decode-initiated pull**:
一种由 Decode 分配目标 block，并在收到 Prefill source metadata 后主动从 Prefill 拉取数据的 PD 传输方式。
_避免使用_: Prefill push、layerwise push

**Swapped Main pool**:
保存 sparse-attention offload Main KV cache、且可被 NPU runtime 寻址的 Decode Host memory pool。
_避免使用_: Indexer pool、跨 TP 共享 Host pool

**Main lifetime reservation**:
Decode 在接收远端 Main KV 前，为请求从 prompt 到最大允许输出长度预留的 Swapped Main pool 容量；其中只有已经承载有效 KV 的部分属于 active blocks。
_避免使用_: Prompt-only reservation、全部预留 block 都已有效

**Prefill source TTL**:
Prefill 完成请求后等待 Decode 接收确认期间，source block 可以继续被持有的最长时间；到期后即使 Decode 仍在等待 admission，Prefill 也可以强制释放这些 block。首版 Decode 不检查 source age、remaining TTL 或 ownership。
_避免使用_: Main reservation timeout、单次 transfer timeout

**Source TTL overrun**:
Decode 启动或继续读取时，Prefill source 已超过 hard TTL、原 request 不再获得 block ownership 保证的 unsupported operating region。Transfer 可能失败，也可能从已复用的合法地址成功读取错误 KV；首版没有 launch-time check，不能保证检测后一种情况。
_避免使用_: 必然 transfer failure、可自动 replay、仍受 source ownership 保护

**Positional tensor ABI**:
P/D 使用相同 layer-keyed address arrays 和 cache tuple/list position 解释 Main、Indexer 与可选 scale 的跨端约定。Wire metadata 不携带 semantic role、dtype、shape 或 memory kind；配对环境必须满足文档化的 image、配置和 layout compatibility preconditions。
_避免使用_: Semantic tensor map、自描述 layout、connector 已证明 P/D compatibility

**Deployment compatibility preconditions**:
部署文档规定的 P/D 配对前置条件，包括 immutable image identity、模型/configuration fingerprint、positional ABI、topology、memory placement 和禁止 mixed-version rolling upgrade。本 feature 不实现 deployment admission controller；违反这些条件时，合法地址上的错误 tensor transfer 可能 silent success。
_避免使用_: Feature 内建 deployment gate、handshake version negotiation、运行时 semantic validation

**Phase A quick validation**:
Blockwise DSA 实现的快速迭代门禁，覆盖 opt-in/default isolation、startup/configuration、positional block mapping、单请求 Indexer 后 Main 的基本传输线、主要 transfer failure 和最小 reservation/replay/cleanup。Phase A 通过只表示可以继续扩展 Phase B，不表示 CPU/mock 已完整验收。
_避免使用_: 最终测试门禁、边界场景已覆盖、NPU smoke

**Phase B boundary validation**:
Phase A 通过后必须执行的 contract-complete CPU/mock 门禁，覆盖 lifetime reservation、HOL admission、preemption、cancellation、full replay、exact TP aggregation、fused D2H boundary、多请求交错和 default V1 regression。只有 Phase A 与 Phase B 都通过，才能标记 `CPU/mock validated`。
_避免使用_: 可选增强、NPU runtime validation、只跑 happy path

**NPU E2E test plan**:
以 `P TP8/DP2 -> D TP2/DP8` 为起点、当前只生成不执行的 runtime 验证计划。所有 case 在未获得真实集群证据前标记 `planned / not run`；static 或 CPU/mock 通过不能提升为 `NPU runtime validated`。
_避免使用_: 已执行 NPU 测试、部署验证结果、CPU/mock 结果

**Blockwise DSA metadata family**:
仅在 `dsa_pd_offload=true` 时使用、并按通信方向拆分的强类型 Decode scheduler-to-worker step metadata 和 Decode worker-to-scheduler aggregated result metadata。P/D worker layout 按 ADR 0022 使用穿刺 positional handshake ABI，不属于 semantic strong-type contract。普通 `MooncakeConnectorMetadata`、`ReqMeta` 和默认 V1 路径不增加 DSA optional fields。
_避免使用_: 扩展后的普通 V1 request metadata、Mooncake/SFA 双 envelope、一个覆盖所有通道的通用 metadata

**DSA step request envelope**:
Decode scheduler 发给 worker 的强类型 per-request command container。Request identity 位于顶层，remote source、Decode destination ownership 和 per-step lifecycle command 使用三个嵌套 value object，并由集中 factory/validator 检查跨对象不变量。
_避免使用_: 扁平 optional-field request、用 `getattr()` 推断 memory role、per-action request subclass

**Main bound prefix**:
Main lifetime reservation 中已经发布给 worker、当前 command 可以访问的有序 Host block prefix。它可以包含即将写入但尚未 valid 的 block；完整 future reserved suffix 只由 scheduler 持有，不发送给 worker。
_避免使用_: 已有效 Main prefix、完整 reservation block list、worker-owned reservation

**DSA command sequence**:
同一 `(request_id, execution_epoch)` 内由 scheduler 严格递增的 command identity，用于区分 receive、fused D2H、replay/cancel 和 late completion。相同 sequence 的冲突内容必须 fail closed。
_避免使用_: Execution epoch、scheduler step number、可 last-writer-wins 的版本号

**DSA lifecycle action**:
Scheduler 下发给 worker 的 request-lifecycle command。首版只有 `RECEIVE_REMOTE`、`FUSED_D2H`、`PREPARE_REPLAY` 和 `QUIESCE`；Indexer/Main 是 `RECEIVE_REMOTE` 内部的 serial phases，不是独立 action。
_避免使用_: 每次底层 API 调用、`PULL_INDEXER`/`PULL_MAIN` scheduler round、generic `EXECUTE`

**DSA local result**:
一个 Decode TP worker 对指定 request、execution epoch 和 command sequence 产生的 terminal command outcome：`RECEIVE_COMPLETE`、`D2H_COMPLETE`、`REPLAY_READY` 或带 Indexer/Main phase 的 `TRANSFER_FAILED`。Cancellation 达到 Quiesced 后复用普通 `finished_recving`，不产生 DSA local result。
_避免使用_: Bool done、typed `QUIESCED`、Indexer 中间成功

**DSA TP result coverage**:
一个产生 DSA local result 的 command 在当前 routed Decode DP replica 内收到精确 Decode TP rank 集合的 terminal local results。Worker metadata 只合并同一步事实，connector scheduler 按 `(request_id, execution_epoch, command_seq)` 跨 step 累积；该 contract 不用于 cancellation 的普通 `finished_recving` ack。
_避免使用_: `count >= D_TP`、全局 DP coverage、任一 TP 完成即 request complete

**TP leader group**:
分配给同一个 Decode TP 的连续 Prefill TP replica 集合，其中首个 Prefill TP 是该组唯一的 payload source。
_避免使用_: 多 shard source group、all-P payload group

**Partial block**:
请求末尾只包含部分有效 token 的最后一个物理 cache block；其有效边界来自 request token 状态，而不是缩短后的物理 block。
_避免使用_: Partial-byte block、自动清零尾块

**Preemption-triggered D-side full-sequence replay**:
已经完成 P-to-D KV 接收的请求在 Decode 被 preempt 后，从 token 0 本地执行 full forward replay，以重建新 HBM ownership 下的 Indexer；Main reservation 和已确认有效的 Main prefix 保留并避免重复 D2H。这是首版沿用的异常恢复路径，仍可能因模型重算带来明显性能退化。
_避免使用_: 正常 D-side Prefill、零成本恢复、Indexer/Main 都必然重写

**Execution epoch**:
一个请求在两次 preemption 之间的一次 Decode 运行实例，拥有当次 core 分配的 Indexer HBM IDs、temporary Main HBM IDs 和 transfer/worker state；preemption 会 retire 旧 epoch，但不释放跨 epoch 的 Main lifetime reservation。
_避免使用_: Main reservation lifetime、可跨 preemption 复用的 Indexer IDs

**Receive-complete**:
当前请求和 Execution epoch 所需的 Indexer 与 Main transfer legs 均已成功、对应 destination 可以作为有效 KV 使用的状态；局部成功或任一 leg 被跳过都不属于 Receive-complete。
_避免使用_: Indexer-only ready、partial success、Quiesced

**Transfer-failure replay**:
Indexer 或 Main 的单次 connector-level transfer 调用在 Mooncake internal retry 后最终失败时，由整个 Decode request 从 token 0 执行 full-sequence forward、重新建立可用 KV 的恢复路径；所有 Decode TP 都放弃复用此前远端接收的 Main prefix。
_避免使用_: Connector-level retry、receive-complete、只重放失败 TP

**Mooncake internal retry**:
Mooncake binding 在一次同步 `batchTransferSync()` 调用内部进行的有限 batch 重提交；它对 connector 不透明，不等同于 connector 再次调用 transfer，也不提供 feature-level attempts/backoff 配置。
_避免使用_: Connector-level retry、固定 NIC failover、三次 Python retry

**Replay-ready**:
Transfer-failure replay 开始前的安全边界：所有 Decode TP 都已停止访问该请求的 transfer destination，且请求可以离开 remote-KV wait、进入本地 full-sequence replay；它不表示 external KV 已有效。
_避免使用_: Receive-complete、Quiesced、Main-valid

**Cancellation drain-and-ack**:
一种两阶段取消协议：取消意图产生后，仍可能被传输任务访问的 destination ownership 保持隔离；各 worker 达到 Quiesced 并上报普通 `finished_recving` 后，相关 ownership 才可释放和复用。
_避免使用_: Cancellation 立即释放、收到 cancel 即等于传输已停止

**Quiesced**:
请求的终态安全边界：已经证明当前及旧 Execution epoch 都不会再访问该请求的 Indexer/Main destination，因此这些 destination ownership 可以安全释放和复用。它是 worker 内部安全状态，不是 typed result kind。
_避免使用_: typed `QUIESCED`、已调用 cancel API、receive-complete

**Prefill source-release notification**:
Decode worker 在不再读取某个尚未通知完成的 Prefill source 后发送的一次性 best-effort release 通知，用于让 Prefill 在 hard TTL 前回收 source ownership；它与 Decode 本地 `finished_recving` ack 是不同通道。
_避免使用_: 把 `finished_recving` 发送给 Prefill、cancellation reason message、可靠 lease release

**Unquiesced operation**:
已经启动、但尚未返回 completion，且无法证明不会继续访问 source 或 destination 的 Indexer D2D、Main D2RH 或 fused D2H operation。首版沿用普通 `MooncakeConnectorV1`，不增加 watchdog、可靠 cancel 或自动 fail-stop；D ownership 保持隔离，直到 operation 返回、worker/process 退出或外部重启。超过 Prefill source TTL 后的晚到成功仍属于 Source TTL overrun，不能据此证明 KV 内容正确。
_避免使用_: 已失败的 transfer、可以安全 replay、可以强制释放的 block
