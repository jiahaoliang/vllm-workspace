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
已发布 sync replacement 使用的快速迭代门禁，覆盖 opt-in/default isolation、startup/configuration、positional block mapping和最小request lifecycle。它是历史validation阶段，不是async初版completion gate。
_避免使用_: Async happy-path gate、当前最终测试门禁、NPU smoke

**Phase B boundary validation**:
已发布 sync replacement 在 Phase A 后执行的完整CPU/mock边界门禁。它保留为历史sync evidence和未来扩展检查表，但不属于GitCode reporter async happy-path的初版completion gate。
_避免使用_: Async CPU/mock validated、GitCode reporter happy-path gate、NPU runtime validation

**NPU E2E test plan**:
以 `P TP8/DP2 -> D TP2/DP8` 为起点、当前只生成不执行的 runtime 验证计划。所有 case 在未获得真实集群证据前标记 `planned / not run`；static 或 CPU/mock 通过不能提升为 `NPU runtime validated`。
_避免使用_: 已执行 NPU 测试、部署验证结果、CPU/mock 结果

**Blockwise DSA metadata family**:
仅在 `dsa_pd_offload=true` 时使用的强类型 metadata family，包括 Decode lifecycle command/result、step-local D2H plan/progress 与独立的 P/D positional handshake。普通 `MooncakeConnectorMetadata`、`ReqMeta` 和 default V1 path 不增加 DSA optional fields。
_避免使用_: 扩展后的普通 V1 request metadata、一个覆盖所有通道的通用 metadata

**Async executor compatibility boundary**:
Blockwise DSA async scheduling的验证边界：只有default `MultiprocExecutor`与default `AsyncScheduler`属于首版validation target；其他executor/scheduler组合允许启动但标记为`unverified`。P/D topology与该executor classification相互独立。
_避免使用_: 所有async-capable executor均已验证、DP/TP topology证明executor支持、非默认组合启动fail closed

**GitCode reporter happy-path CPU/mock validation**:
针对GitCode Issue #1的`P DP2/TP8 -> D DP2/TP8`、default `MultiprocExecutor`与default `AsyncScheduler`单请求happy path门禁。它只描述指定source identity的CPU/mock证据，不等于完整Phase B、广义async correctness或真实runtime通过。
_避免使用_: Phase B boundary validation、async CPU/mock validated、NPU runtime validated、reporter deployment passed

**DSA step request envelope**:
Decode scheduler 发给 worker 的强类型 per-request lifecycle command container，用于 remote receive、replay preparation 和 terminal quiesce。Step-local D2H plan 是同一 metadata family 中的独立 value object，不属于该 envelope。
_避免使用_: D2H step plan、扁平 optional-field request、per-action request subclass

**Main bound prefix**:
Main lifetime reservation 中已经发布给 worker、当前 lifecycle command 或 D2H step plan 可以访问的有序 Host block prefix。它可以包含即将写入但尚未 valid 的 block；完整 future reserved suffix 只由 scheduler 持有。
_避免使用_: 已有效 Main prefix、完整 reservation block list、worker-owned reservation

**Step-local Main binding**:
一个model step对live Main lifetime reservation与当前可访问Main bound prefix的视图。它不表示该prefix已经confirmed；即使本step没有Issued D2H step，preserved Main仍可通过该binding被寻址。
_避免使用_: Active `FUSED_D2H` command、confirmed Main validity、完整future reservation

**DSA command sequence**:
同一 `(request_id, execution_epoch)` 内由 scheduler 严格递增的 lifecycle command identity，用于区分 receive、replay、quiesce 和 late completion。Step-local D2H 使用独立的 D2H step sequence。
_避免使用_: D2H step sequence、execution epoch、scheduler step number

**DSA lifecycle action**:
Scheduler 下发给 worker 的 request-lifecycle command。Async-compatible contract 只有 `RECEIVE_REMOTE`、`PREPARE_REPLAY` 和 `QUIESCE`；step-local D2H 不属于 lifecycle action。
_避免使用_: `FUSED_D2H`、每次底层 API 调用、generic `EXECUTE`

**DSA local result**:
一个 Decode TP worker 对指定 request、execution epoch 和 lifecycle command sequence 产生的 terminal command outcome：`RECEIVE_COMPLETE`、`REPLAY_READY` 或带 Indexer/Main phase 的 `TRANSFER_FAILED`。D2H completion 使用 D2H step progress；Quiesced completion 复用普通 `finished_recving`。
_避免使用_: `D2H_COMPLETE`、typed `QUIESCED`、Bool done

**DSA TP result coverage**:
一个产生 DSA local result 的 lifecycle command 在当前 routed Decode DP replica 内收到精确 Decode TP rank 集合的 terminal local results。该跨-step accumulation contract 只用于 receive/failure/replay，不用于 D2H progress 或普通 `finished_recving`。
_避免使用_: D2H progress coverage、`count >= D_TP`、全局 DP coverage

**Issued D2H step**:
Scheduler 为一个 request 和 execution epoch 发布的 immutable、step-local Main D2H plan。它占用独立的 request-local D2H step sequence，但不占用 lifecycle command sequence，也不阻塞下一次 schedule。
_避免使用_: `FUSED_D2H` command、completed D2H、global scheduler step

**D2H step sequence**:
同一 `(request_id, execution_epoch)` 内由 scheduler 为非空 Issued D2H step 单调分配的 request-local identity。它与 DSA command sequence 是两个独立 namespace。
_避免使用_: DSA command sequence、global scheduler step、output index

**Issued Main watermark**:
当前 execution epoch 中由连续 Issued D2H steps 覆盖到的最大 Main token boundary。它表示 worker 已获准写入的范围，可以领先于 confirmed Main watermark。
_避免使用_: confirmed Main watermark、有效 Main prefix、`num_computed_tokens`

**D2H step progress**:
一个 Decode TP worker 在本 step Main D2H 完成并经过 `wait_for_save()` 后返回的 rank-aware completion fact。它在当前 model step 内进行 exact TP aggregation，但不形成跨-step scheduling gate。
_避免使用_: `D2H_COMPLETE` lifecycle result、anonymous completion、issued plan

**Confirmed Main watermark**:
Scheduler 已消费 current-epoch D2H step progress、并能证明从既有 Main-valid boundary 起连续完成的最大 token boundary。Issued 但未 confirmed 的 range 不能用于 preemption Main-prefix reuse。
_避免使用_: Issued Main watermark、scheduled token count、乐观 `num_computed_tokens`

**Prefill DCP source group**:
分配给一个 Decode TP 的连续 `P_DCP` 个 Prefill TP ranks。Main由该组的exact rank-local shards拼装；
组首 rank仍是Indexer与可选scale的fixed replica leader。多个Decode TP可以共享同一source group，
`P_DCP=1` 时退化为原fixed-leader mapping。
_避免使用_: all-P payload group、Indexer multi-source、跨P DP tensor group

**Prefill rank endpoint**:
一个 Prefill TP rank 对应的 concrete `(host, handshake port, engine identity)`，用于选择同一个 positional handshake session；它只描述路由，不证明该 rank 持有完整 Main/Indexer replica。
_避免使用_: Scalar base endpoint、TP leader replica proof、semantic tensor map

**Partial block**:
请求末尾只包含部分有效 token 的最后一个物理 cache block；其有效边界来自 request token 状态，而不是缩短后的物理 block。
_避免使用_: Partial-byte block、自动清零尾块

**Preemption-triggered D-side full-sequence replay**:
已经完成 P-to-D KV 接收的请求在 Decode 被 preempt 后，从 token 0 本地执行 full forward replay，以重建新 HBM ownership 下的 Indexer；Main reservation 和已确认有效的 Main prefix 保留并避免重复 D2H。这是首版沿用的异常恢复路径，仍可能因模型重算带来明显性能退化。
_避免使用_: 正常 D-side Prefill、零成本恢复、Indexer/Main 都必然重写

**Execution epoch**:
一个请求在两次 preemption 之间的一次 Decode 运行实例，拥有当次 core 分配的 Indexer HBM ownership、temporary Main HBM ownership 和 transfer/worker state；preemption 会 retire 旧 epoch，但不释放跨 epoch 的 Main lifetime reservation。重新分配可以返回相同的 block ID 数值，新 epoch 与明确 rebind 才是新 Indexer ownership identity。
_避免使用_: Main reservation lifetime、block ID 数值变化即新 ownership、可跨 preemption 复用的旧 Indexer binding

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
Decode local full-sequence replay 开始前的安全边界：所有 Decode TP 都已停止通过被 retire 的 operation 访问 destination，并已应用本次 replay 所需的 Execution epoch 与 ownership binding。它不表示 replay forward 已执行或 external KV 已有效。
_避免使用_: Receive-complete、Quiesced、Main-valid、只适用于 transfer failure

**Cancellation drain-and-ack**:
一种两阶段取消协议：取消意图产生后，仍可能被传输任务访问的 destination ownership 保持隔离；各 worker 达到 Quiesced 并上报普通 `finished_recving` 后，相关 ownership 才可释放和复用。
_避免使用_: Cancellation 立即释放、收到 cancel 即等于传输已停止

**Terminal-pending**:
Blockwise DSA 请求在 normal finish、EOS、stop、length cap 或 abort 后进入的 reason-agnostic scheduler state。进入后不再发布新的 receive、replay 或 Issued D2H step，但 Main reservation 与 delayed NPU blocks 继续保持 ownership，直到 Terminal ownership barrier 完成。
_避免使用_: 仅 abort 的 `cancel_pending`、已经 Quiesced、可以立即释放

**Terminal ownership barrier**:
请求进入 Terminal-pending 后使用的终态 ownership protocol。Scheduler 通过 metadata-only/no-forward batch 在所有既有 queued work 之后下发 `QUIESCE` tail marker；满足 per-worker step FIFO 的 worker drain 既有 operation、清理 request/epoch state，并在 Quiesced 后上报一次普通 `finished_recving`。只有 all-worker completion 到达后才能 release-once Main reservation 和 delayed NPU blocks。
_避免使用_: Scheduler issued-count 即 completion、typed `QUIESCED` result、timeout 后强制释放

**Preemption replay barrier**:
被 preempt 的请求在新 Execution epoch 开始 replay 前的安全边界：旧 epoch 已不再访问 destination，新的 Indexer ownership 已绑定，Main lifetime reservation 继续保持且只有 preemption cut 前的 Confirmed Main prefix 可以复用。
_避免使用_: Terminal ownership barrier、epoch increment 即安全、drain 前的 `REPLAY_READY`

**Quiesced**:
请求的终态安全边界：已经证明当前及旧 Execution epoch 都不会再访问该请求的 Indexer/Main destination，因此这些 destination ownership 可以安全释放和复用。它是 worker 内部安全状态，不是 typed result kind。
_避免使用_: typed `QUIESCED`、已调用 cancel API、receive-complete

**Prefill source-release notification**:
Decode worker 在不再读取某个尚未通知完成的 Prefill source endpoint 后发送的一次性 best-effort release 通知，用于让 Prefill 在 hard TTL 前回收 source ownership。一个request可以计划多个source endpoints，并对每个endpoint各通知一次；它与 Decode 本地 `finished_recving` ack 是不同通道。
_避免使用_: 把 `finished_recving` 发送给 Prefill、cancellation reason message、可靠 lease release

**Unquiesced operation**:
已经启动、但尚未返回 completion，且无法证明不会继续访问 source 或 destination 的 Indexer D2D、Main D2RH 或 fused D2H operation。首版沿用普通 `MooncakeConnectorV1`，不增加 watchdog、可靠 cancel 或自动 fail-stop；D ownership 保持隔离，直到 operation 返回、worker/process 退出或外部重启。超过 Prefill source TTL 后的晚到成功仍属于 Source TTL overrun，不能据此证明 KV 内容正确。
_避免使用_: 已失败的 transfer、可以安全 replay、可以强制释放的 block
