Status: sync replacement and async delta implemented; GitCode reporter happy path 已通过 CPU/mock validation; bounded glm-5.1/glm5.2 NPU E2E passed at `117637d20`; graph-capture and full runtime matrix unverified

## Problem Statement

已发布的 vLLM-Ascend replacement commit `7401ae79c11d6ec0033ea3ac39085379a0bb81ef` 已在 `MooncakeConnectorV1` 内实现显式 opt-in 的 Blockwise DSA PD offload：Prefill 保持 request-level block pull，Decode 将 Indexer 放入 HBM、将 Main K/V 放入每个 Decode TP process 的 Swapped Main pool，并建立 Main lifetime reservation、receive/replay exact-TP completion、preemption、cancellation 与 fused D2H validity。

该 replacement 的 decode-time D2H 仍是 single-active lifecycle `FUSED_D2H` command，并以跨 scheduler step 的 exact-TP `D2H_COMPLETE` 作为下一条 command 的 gate。它还在 startup 拒绝 async scheduling。GitCode Issue #1 reporter 使用 default `MultiprocExecutor`、default `AsyncScheduler` 和 `P DP2/TP8 -> D DP2/TP8`，因此旧 contract 无法覆盖 reporter 的 queued multi-batch execution。

目标是在不修改 upstream vLLM core、不改变普通 `MooncakeConnectorV1` 默认行为的前提下，使 `dsa_pd_offload=true` 同时支持 sync 和 async scheduling。Async scheduler 可以在前一 batch output 尚未回收时继续发布下一 step；实现必须区分已经发布的 D2H range 与已经完成并可复用的 Main range，并在 terminal/preemption 与 queued work 交错时维持 destination ownership。

当前没有 NPU 资源。Static、CPU/mock、真实 Mooncake、NPU、fused kernel 与 graph-capture evidence 必须分开，不能把 planned 或 fake/mock 结果表述为真实 runtime 通过。

2026-08-28 runtime update: origin branch history records passing glm-5.1/glm5.2 smoke, long-request and approximately 4k-input concurrent NPU E2E after the fixes in `59fd10b0d`; final branch HEAD is `117637d20`. This external evidence does not retroactively expand the initial async CPU/mock gate or prove every case in the older 8-case NPU plan. The current workspace did not rerun those NPU jobs, and the referenced experiment ledger is not tracked in the fetched source tree.

## Current Replacement Baseline

- Source identity: vLLM-Ascend `7401ae79c11d6ec0033ea3ac39085379a0bb81ef`，vLLM `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`。
- Existing sync replacement、focused DSA/SFA、connector/default V1 与 broad CPU/mock evidence 保持有效；详见 [CPU/mock validation report](cpu-mock-validation-report.md)。
- Existing positional ABI、fixed TP leader、per-Decode-TP Swapped Main pool、Main lifetime reservation、Indexer-before-Main receive gate、transfer-failure replay、source TTL 与 unquiesced-operation boundaries 继续有效。
- Current source still uses lifecycle `FUSED_D2H` / `D2H_COMPLETE` and rejects async scheduling. These are baseline facts, not the target async contract.

## Target Async Contract

### Mode and topology

- `kv_connector_extra_config.dsa_pd_offload=true` 显式启用该 mode；关闭时普通 V1 scheduler、metadata、worker、transfer 与 completion 行为不变。
- Prefill 为 `kv_producer`，Decode 为 `kv_consumer`；Prefill 不启用 layerwise reuse/offload，Decode 使用 `fused_overlap` 与 Mooncake SFA backend。
- 产品 topology 保持 `P_TP >= D_TP`、`P_TP % D_TP == 0`、Decode PP=1 和 Decode `DCP * PCP == 1`。Reporter 的 `P DP2/TP8 -> D DP2/TP8` 是初版 validation target，不是产品唯一 topology。
- Prefill TP 按 `P_TP / D_TP` 连续分组，每组首个 rank 是对应 Decode TP 的唯一 payload source。P/D positional ABI、block/page geometry、image 与 configuration compatibility 是 deployment preconditions，不由 connector handshake 证明。

### Reservation and initial receive

- 每个 Decode TP process 拥有独立 Swapped Main pool。Scheduler 在 remote admission 前为请求的最大允许 sequence length 建立 Main lifetime reservation，并独占完整 future reservation block list。
- Worker 只看到 stable reservation identity、capacity 和当前可访问的 ordered Main bound prefix。Bound prefix 可以包含即将写入但尚未 confirmed 的 blocks，不能被解释为 valid Main boundary。
- 一个 `RECEIVE_REMOTE` lifecycle command 在每个 Decode TP worker 内先执行 Indexer D2D，成功后才执行 Main D2RH。Indexer 或 Main final failure 使用 phase-aware `TRANSFER_FAILED`；两者成功才产生 `RECEIVE_COMPLETE`。
- Receive、transfer failure 与 replay 继续使用 `(request_id, execution_epoch, command_seq, tp_rank)` typed result identity，以及当前 routed Decode DP replica 内的 exact TP rank-set coverage。
- Python connector 每个 transfer phase 只调用一次同步 Mooncake transfer，只依赖 Mooncake internal retry；不增加 outer retry、source TTL check 或 launch lease。

### Lifecycle metadata and D2H progress

- Blockwise DSA 使用独立 metadata family。`DsaConnectorMetadata` 并列携带 lifecycle request envelopes 与 step-local D2H plans；普通 V1 metadata 不增加 DSA optional fields。
- Async-compatible lifecycle actions 只有 `RECEIVE_REMOTE`、`PREPARE_REPLAY` 和 `QUIESCE`。Decode-time Main D2H 不是 lifecycle action，`FUSED_D2H` 与 `D2H_COMPLETE` 从目标 contract 删除。
- 每个非空 `DsaD2HStepPlan` 以 request、execution epoch、request-local D2H step sequence、Main reservation、ordered bound Host prefix 和 token range形成 immutable issued fact。D2H step sequence 与 lifecycle command sequence 是独立 namespace。
- Scheduler 维护 issued Main watermark、confirmed Main watermark 和 immutable issued-step ledger。发布 plan 时只推进 issued watermark；只有消费 current-epoch、`wait_for_save()` 后返回的 rank-aware `D2HStepProgress`，并取得本 step exact Decode TP coverage 后，才能推进 confirmed watermark。
- Later step 可以先完成，但 confirmed watermark 不能跨越 ledger gap。Duplicate 完整 progress 幂等；conflict、future identity、非法 rank/range/reservation fail fast；old-epoch、已 confirmed 或 released progress 只观察并忽略。
- D2H progress 不形成跨 scheduler step gate。永久 progress gap 不新增 timeout、watchdog 或推测性 completion。

### Worker Main binding

- Worker 为 live request 保留 persistent Main reservation、execution epoch、Main bound prefix binding 与轻量 D2H continuity state；每个 model step 按实际 batch 重建 ephemeral SFA view。
- 没有 nonempty D2H plan 的 step 仍可以从 persistent binding 访问 preserved Main，并必须清除上一 step 的 ephemeral SFA state。
- Worker 只有在 SFA `wait_for_save()` 成功后才返回 D2H step progress。D2H failure 继续作为 model-step exception fail fast，不伪造 progress、typed transfer failure 或 ordinary completion。

### Terminal ownership

- Normal finish、EOS、stop、length cap 与 abort 统一进入 reason-agnostic `Terminal-pending`。进入后不再发布新的 receive、replay 或 D2H plan，并冻结 issued/confirmed validity。
- Scheduler 通过 metadata-only/no-forward batch 下发 `QUIESCE` tail marker。对满足 per-worker step FIFO 的 executor，该 marker 位于该 request 所有已发布 work 之后。
- Worker 只有在 current/old epoch operation 不再访问 destination、request binding 已清理，并对实际使用且尚未通知的 Prefill source 尝试一次 best-effort `DONE_RECVING_MSG` 后，才达到 Quiesced 并上报一次 ordinary `finished_recving`。
- Scheduler 只在 ordinary all-worker completion 到达后 release-once Main reservation；vLLM core 随后释放 delayed NPU blocks。Queued late progress 可以退休 issued record，但不推进 terminal validity，也不替代 `QUIESCE` ownership proof。
- 无法下发或完成 `QUIESCE`、operation 不返回或 worker 无法证明 Quiesced 时，ownership 按 ADR 0016 保持隔离；不增加 watchdog、reliable cancel、fatal latch 或 automatic restart。

### Preemption and replay

- Scheduler 第一次观察到 active epoch preemption 时形成 epoch cut：以当时已消费的 confirmed Main watermark 快照 immutable preserved prefix `P`，封存 old-epoch ledger，并只递增一次 execution epoch。无法证明连续性时 `P=0`。
- Cut 后的 old-epoch D2H progress 在基础校验后只观察并忽略，不能扩大 `P`。New epoch 从 issued/confirmed watermark `P` 和空 ledger 开始。
- Core 完成 resumed request 的新 Indexer allocation/rebind 后，scheduler 下发 new-epoch `PREPARE_REPLAY`。Worker drain old-epoch operations、清理旧 binding并安装新 Indexer ownership后才返回 exact-TP `REPLAY_READY`。
- Replay 从 token 0 重建完整 Indexer，Main D2H 跳过 `[0, P)` 并覆盖未确认 suffix。Transfer-failure replay 继续使用 same-epoch `PREPARE_REPLAY` 与 `P=0`。
- Preemption-pending期间出现 terminal intent时，`Terminal-pending` 主导并改走 latest-epoch `QUIESCE`；late `REPLAY_READY` 不能重新放行 replay。

### Compatibility classification

- 首版 validation target 只有 default `MultiprocExecutor` 与 default `AsyncScheduler`。其他 executor/scheduler 组合允许启动，但 startup warning 必须列出实际类型并标记 `unverified` / “未测试”。
- Executor classification 与 P/D topology 相互独立；upstream `supports_async_scheduling()`、class inheritance 或一次无报错运行不能自动升级 validation status。
- `dsa_pd_offload=true` 与 speculative config 的组合允许启动，但本版不 validation、不测试，也不承诺 draft acceptance/rejection 下的 D2H/Main/replay correctness。Metadata mode/type isolation仍然有效，但不新增 speculative startup gate。

## User Stories

1. 作为 default V1 用户，我希望关闭 `dsa_pd_offload` 时现有 Mooncake behavior 不变。
2. 作为 async Decode scheduler，我希望连续发布多个 model steps，而不等待前一步 D2H progress。
3. 作为 Main validity owner，我希望 issued range 与 confirmed range 分离，从而不把 queued work 当作完成事实。
4. 作为 Decode worker，我希望每 step 重建 SFA view，同时跨 step 保留同一 reservation 的 Main binding。
5. 作为 scheduler，我希望只消费 `wait_for_save()` 后的 exact-TP progress，从而推进连续 confirmed watermark。
6. 作为 terminal request，我希望 `QUIESCE` 排在既有 queued work 之后，并只在 all-worker Quiesced 后释放 destination。
7. 作为 preempted request，我希望 cut 后晚到的 old-epoch progress不能扩大 preserved Main prefix。
8. 作为 replay owner，我希望 `PREPARE_REPLAY` 建立 drain/rebind barrier，再开始 token-0 replay。
9. 作为 operator，我希望非默认 executor/scheduler 能启动但明确显示“未测试”，而不是被误报为已支持。
10. 作为 reviewer，我希望 speculative 组合不被当前版本拒绝，但也不被写成已验证。
11. 作为 reporter regression owner，我希望 `P DP2/TP8 -> D DP2/TP8` 的 default async 单请求 happy path 有一个最小、可复核的 CPU/mock gate。
12. 作为 NPU validation owner，我希望未运行的真实 transfer、fused kernel 与 graph-capture case保持 `planned / not run`。

## Implementation Decisions

1. 不增加新的 public connector，不修改 upstream vLLM core。
2. Stable positional ABI、leader mapping、Main reservation、receive ordering、transfer-failure replay、source TTL 与 unquiesced-operation contracts保持不变。
3. 删除 lifecycle `FUSED_D2H` 与 typed `D2H_COMPLETE`；receive/failure/replay typed results继续保留。
4. D2H plan/progress与 lifecycle request/result属于同一 Blockwise DSA metadata family，但使用独立 value objects、identity namespace与aggregation规则。
5. Scheduler 是 issued/confirmed ledger、Main validity与reservation release的唯一权威；worker不能根据 bound prefix或scheduled token count推测 validity。
6. Terminal completion复用ordinary `finished_recving`，不增加 typed `QUIESCED`。
7. Preemption reuse只基于epoch cut前已消费的confirmed prefix，不基于late progress、issued watermark或block ID数值变化。
8. D2H failure继续model-step fail-fast；不实现running-request request-local recovery。
9. 非默认executor/scheduler和speculative组合允许启动但保持unverified；不增加validation-based admission controller。
10. ADR 0016边界保持：不增加watchdog、reliable cancel、fatal latch或automatic restart contract。

## Validation Evidence

| Scope | Status | Allowed claim |
| --- | --- | --- |
| Published sync replacement at `7401ae79c` | existing CPU/mock evidence retained | 仅使用既有报告中的精确 sync replacement claim |
| GitCode reporter async happy path | `PASS` | GitCode reporter happy path 已通过 CPU/mock validation |
| Preemption | 未测试 | 未测试 |
| Abort | 未测试 | 未测试 |
| D2H failure | 未测试 | 未测试 |
| Late progress | 未测试 | 未测试 |
| Adversarial metadata | 未测试 | 未测试 |
| 多请求交错 | 未测试 | 未测试 |
| `P TP8 -> D TP2` | 未测试 | 未测试 |
| Speculative config | 未测试 | 未测试 |
| 非默认 executor/scheduler lifecycle | 未测试 | 未测试 |
| NPU、真实 Mooncake、fused kernel、graph-capture runtime | `planned / not run` | 不得声明 runtime validated |

## Initial Async Completion Gate

Mandatory CPU/mock gate只覆盖以下 happy path：

1. Reporter topology为`P DP2/TP8 -> D DP2/TP8`，default `MultiprocExecutor`与default `AsyncScheduler`。
2. 单请求先完成`RECEIVE_REMOTE`，然后真实`AsyncScheduler`与EngineCore queue连续发布两个Decode steps，queue depth实际达到2。
3. Production DSA scheduler/worker connector参与；model execution、Mooncake transport、SFA kernel、NPU tensor和executor worker process使用fake/mock。
4. 每个step的`wait_for_save()`后返回exact TP8 progress，confirmed watermark按连续range推进。
5. Normal finish通过`QUIESCE`、ordinary all-worker completion和release-once结束。
6. Decode DP rank 0与1分别验证，不把两个DP replica混入同一个TP aggregation。
7. 另保留sync DSA happy-path smoke、default V1 isolation smoke与非默认executor/scheduler startup warning smoke。

该gate不要求broad CPU/mock root或完整Phase B rerun。执行时按照workspace `AGENTS.md`使用`liangjiahao` namespace的CPU-only UT Pod，记录source branch、commit、dirty状态与显式test targets；当前没有NPU，不创建NPU workload。

## Out of Scope

- 修改upstream vLLM core，或新增core-level running-request D2H failure/completion channel。
- Prefill layerwise reuse、layerwise push或完整实现vLLM issue #48203。
- 改变positional tensor ABI、TP leader mapping、Main reservation policy或default `MooncakeConnectorV1` behavior。
- `P_TP < D_TP`、`P_TP % D_TP != 0`、Decode PP>1、Decode `DCP * PCP != 1`、multi-P shard assembly或跨P DP replica混合tensor。
- Speculative decoding配合实现、correctness validation与support claim。
- 非默认executor/scheduler lifecycle validation。
- Fused D2H request-local recovery、watchdog、reliable native cancel、fatal latch或automatic restart。
- NPU runtime执行、performance threshold、完整failure/lifecycle runtime validation、GitCode回帖或关闭external issue。

## Further Notes

- [Blockwise DSA Async Scheduling Wayfinder Map](map.md)记录async delta的decision history；ADR 0024-0030是当前async contract入口。
- [MooncakeConnectorV1 Blockwise DSA PD Offload设计](blockwise-dsa-pd-offload-design.md)与reimplementation amendments记录已发布sync replacement的历史设计和evidence，不覆盖本spec的async delta。
- 当前实现、目标contract和validation evidence是三个不同事实层。Implementation agent必须先修改source并完成规定gate，才能更新async status；仅更新文档或通过static checks不能升级claim。
