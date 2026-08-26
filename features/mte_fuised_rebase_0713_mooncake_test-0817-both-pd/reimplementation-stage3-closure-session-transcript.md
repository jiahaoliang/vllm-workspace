# Session 原文记录

Session ID: `01a02a71-1bf8-7d83-9180-45f1d32df6b1`

## User

Read features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage3-closure-amendment.md  completely and explain it in plain language.

  Assume I understand software engineering but not this feature.

  Structure the explanation as:
  1. What problem the document solves
  2. The proposed solution
  3. How the main workflow behaves, with one concrete example
  4. Which modules own which responsibilities
  5. Important constraints and failure cases
  6. What is already decided versus still proposed
  7. What code or tests would change
  8. A short glossary

  Do not paraphrase section by section. Build a coherent mental model.
  Clearly label claims as Decision, Current Code, Proposal, Risk, or Unverified.
  Cite the relevant document sections and source files where useful.

## Assistant

已完整阅读。先建立一个背景：Blockwise DSA 把 KV 分成驻留 Decode HBM 的 Indexer，以及保存在 Decode Host pool 的 Main。初始接收顺序是 Indexer D2D 成功后再做 Main D2RH；Decode 后续生成的 Main KV 通过 fused D2H 写回 Host。[spec.md](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/spec.md:21)

源码引用指向 replacement worktree：它以 `0d6dd0d` 为 HEAD，保留未提交 WIP；普通 `repos/vllm-ascend` checkout 的 `60eb76e` 是旧 subsystem 行为参考，不是这里讨论的实现。

**1. 文档解决什么问题**

- **Decision**：Stage 1 已决定把实现收敛为 `MooncakeConnectorV1 + typed metadata + thin SFA extensions`，不保留 standalone scheduler/runtime/worker/transport/memory subsystem。[Stage 1 gate](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage1-design-gate.md:15)

- **Current Code**：replacement WIP 已经符合这个 module shape，规模是 production `+1,541/-39`、focused tests `+1,099/-40`。[closure amendment §1](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage3-closure-amendment.md:7)

- **Risk**：worker 用永久 `_dsa_terminal_requests: set[str]` 记住所有结束过的 request ID。它既会随历史请求无限增长，也会把以后合法复用同一 request ID 的新请求当作旧请求拒绝。[当前初始化](/root/ljh/vllm-workspace/repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py:2698) [当前拒绝逻辑](/root/ljh/vllm-workspace/repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py:4214)

- **Risk**：worker 也不能单靠自己见过的 command 推断哪些 reservation 已结束。scheduler 会先分配 Main reservation，随后 vLLM core 的 Indexer `allocate_slots()` 可能失败；这样 reservation 存在，但永远没有 command 到达 worker。[reservation 分配](/root/ljh/vllm-workspace/repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py:1741) [core allocation failure](/root/ljh/vllm-workspace/repos/vllm/vllm/v1/core/sched/scheduler.py:761)

- **Risk**：现有 replay test 直接改 request private state并伪造后继 scheduler output，只证明 connector 内部状态跳转，没有证明真实 `Scheduler.schedule()` 会从 token 0 调度 forward。[当前 replay test](/root/ljh/vllm-workspace/repos/vllm-ascend-blockwise-dsa-reimplementation/tests/ut/kv_offload/test_mooncake_connector.py:1704)

- **Risk**：`skipped_d2h_bytes` 不能用 Main page size估算。C8 page包含 padding，而 fused D2H descriptor实际只复制 K/V payload。[C8 layout](/root/ljh/vllm-workspace/repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/core/kv_cache_interface.py:58) [实际 descriptor size](/root/ljh/vllm-workspace/repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py:1072)

**2. 提议的方案**

- **Proposal**：scheduler 每个 engine step发送一份完整的 reservation snapshot：

  ```text
  reservation_id_upper_bound = 下一个可分配的 reservation ID
  live_reservation_ids       = 当前仍合法存活的全部 reservation IDs
  ```

  `request_id` 只是可复用名称；单调递增、不复用的 `main_reservation_id` 才代表一次具体 incarnation。[closure amendment §2](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage3-closure-amendment.md:44)

- **Proposal**：snapshot 中也包括“已 admission、但尚未取得 Indexer blocks”的 reservation。因此即使 worker从未见过该 reservation 的 command，也能在后续 snapshot 中确定它何时退出 live set。

- **Proposal**：worker 只保存最新 snapshot和当前 live request state。upper bound不能倒退；旧 ID只能继续存活或退出，不能复活；新 ID只能出现在新扩展出来的 ID 区间。command引用 non-live ID、旧 snapshot复活 ID、或试图 retire non-Quiesced state时全部 fail closed。[snapshot invariants](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage3-closure-amendment.md:73)

- **Proposal**：DSA Decode 启动时拒绝 `async_scheduling`。这样每个同步 step结束时，worker operation已完成或明确 pending，不会发生 core已经 normal-finish并释放 reservation、后台 batch却还在写旧地址的情况。[closure amendment §3](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage3-closure-amendment.md:91)

- **Proposal**：`_start_dsa_commands()` 拆成“接受 snapshot”和“dispatch单条已验证 command”。当前 `_finish_dsa_operation()` 会递归构造缺少 snapshot 的 synthetic metadata，加入 snapshot后必须消除这条旁路。[当前递归位置](/root/ljh/vllm-workspace/repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py:4355)

- **Proposal**：每个 TP 的 `REPLAY_READY` 增加 local `skipped_d2h_bytes`；scheduler在 exact TP coverage完成后求和，只写一条 Decode-DP aggregate replay event。

**3. 主流程示例**

假设只有一个请求 `req-42`：

1. **Proposal**：scheduler admission时分配 `main_reservation_id=7`，发送 `upper_bound=8, live=(7,)`。即使 Indexer暂时分配失败，7仍在 live set里。
2. **Current Code**：初始 receive完成后，scheduler记录例如 `confirmed_main_tokens=128`；Main reservation 7继续属于该请求。
3. **Decision**：请求被 preempt时，core释放旧 Indexer HBM blocks，但 Main reservation和已确认的128-token Main prefix保留。[ADR 0009](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/docs/adr/0009-replay-preempted-requests-locally-on-decode.md:19)
4. **Current Code**：请求恢复并获得新 Indexer blocks后，connector下发 `PREPARE_REPLAY`，reservation ID仍是7，但 execution epoch和 Indexer IDs已更新。[preemption/rebind逻辑](/root/ljh/vllm-workspace/repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py:1784)
5. **Proposal**：每个 Decode TP返回 `REPLAY_READY`，并报告本 rank因复用128-token Main prefix而避免的 D2H bytes。只有 exact TP rank set全部到齐，scheduler才把 request token state重置为0并记录聚合 event。
6. **Proposal**：真实 public `Scheduler.schedule()` 随后从 token 0调度 full-sequence forward，使用新的 Indexer block table；当 replay超过第128个 token后，`FUSED_D2H`只写 `[128, replay_end)` suffix。
7. **Proposal**：normal finish后，下一份 snapshot移除7。worker只有确认本地没有 `in_flight`、pending command、pending quiesce或pending fused save后才清除该 state。
8. **Proposal**：以后仍可出现名为 `req-42` 的新请求，但它会获得不小于8的新 reservation ID，因此不会与旧 incarnation混淆。
9. **Decision**：若原因是 transfer failure而不是 preemption，Main prefix不可信，`reused_main_tokens=0`、`skipped_d2h_bytes=0`，full replay从0重写。

**4. Module ownership**

| 标签 | Module | 责任 |
|---|---|---|
| **Decision** | vLLM `Request` / `SchedulerOutput` | request状态、token进度、当前 Indexer HBM allocation |
| **Decision + Proposal** | `mooncake_connector.py` private Decode scheduler | Main reservation分配、live set、epoch/command、confirmed prefix、cross-step exact-TP结果和 replay event |
| **Decision + Proposal** | `mooncake_dsa_metadata.py` | immutable command/result；新增完整 live-reservation snapshot，但不拥有历史或 mutable lifecycle |
| **Current Code + Proposal** | `MooncakeConnectorWorker` | process-local command、operation、Quiesced和result queue；改为保存最新 snapshot，不保存永久 tombstone |
| **Current Code** | `KVCacheRecvingThread` | 执行本地 Indexer D2D → Main D2RH及Mooncake endpoint/session操作 |
| **Current Code** | `SFAKVOffloadWorker` | Host Main tensor registration、CPU block table、fused D2H和真实 K/V descriptor geometry |
| **Current Code** | `KVOutputAggregator` | cancellation的普通 all-worker `finished_recving` 汇聚；不判断 typed TP completeness |
| **Decision** | upstream vLLM core | 保持不修改；通过现有 connector hooks消费结果 |

完整 ownership boundary见 [Stage 1 state map](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage1-design-gate.md:155)。

**5. 重要约束和失败场景**

- **Proposal**：snapshot必须排序、去重、非负，所有 ID小于 upper bound；旧 snapshot、ID resurrection、non-live command、non-Quiesced retirement均立即失败。
- **Proposal**：DSA `finished_req_ids` 不再负责删除 worker state。当前 vLLM确实先调用 `start_load_kv()`，随后才把 one-shot finish IDs交给 `get_finished()`。[调用顺序](/root/ljh/vllm-workspace/repos/vllm/vllm/v1/worker/kv_connector_model_runner_mixin.py:91)
- **Decision**：cancellation仍使用 typed `QUIESCE` drain到worker-local Quiesced，再通过普通 `finished_recving`做all-worker completion；不增加 typed `QUIESCED`。
- **Decision**：不增加 watchdog、reliable/native cancel、fatal latch或automatic restart。operation若永远不返回，对应 request和destination可以无限期占用且保持隔离。[ADR 0016](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/docs/adr/0016-do-not-watchdog-unquiesced-operations.md:3)
- **Risk**：P/D positional ABI不在 connector内校验 shape/dtype/layout。部署错配可能发生 transport success但写错 tensor的 silent corruption。[ADR 0022](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/docs/adr/0022-use-the-puncture-positional-handshake-abi.md:3)
- **Risk**：snapshot解决的是 live process内的 lifecycle和有界内存证明，不解决process crash、永久阻塞DMA或跨进程恢复。
- **Unverified**：真实 multi-node routing、NPU transfer、Host registration、fused kernel correctness、实际 descriptor bytes和性能仍是 `planned / not run`。

**6. 已决定与仍提议**

- **Decision**：lean module shape、typed metadata family、positional ABI、四种 lifecycle actions、exact TP coverage、preemption保留可证明的 Main prefix、cancellation到Quiesced，以及“不增加watchdog/native cancel”均已由 Stage 1/spec/ADR接受。
- **Decision**：routing amendment方案A已经批准并实现，即按 Prefill rank携带完整 immutable endpoint tuple。[routing amendment](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage1-routing-amendment.md:186)
- **Decision**：`skipped_d2h_bytes` 作为观察字段已经进入 accepted spec；amendment只提议如何准确计算它。[spec item 44](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/spec.md:78)
- **Proposal**：scheduler-authored live snapshot、DSA async rejection、`REPLAY_READY.skipped_d2h_bytes`、public token-0 test，以及新的 `1,710/1,200` stop lines。
- **Current Code**：metadata目前只有 `requests`，local result也没有 skipped bytes。[metadata现状](/root/ljh/vllm-workspace/repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py:215)
- **Proposal**：整份 closure amendment仍是“待用户批准”，因此目前不授权继续修改 production source，也不授权 commit/push。[文档状态](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage3-closure-amendment.md:3)

**7. 将修改的代码和测试**

- **Proposal**：`mooncake_connector.py` 额外 `+75~105/-15~30`：snapshot生成/消费、retirement、async fail-closed、single-command dispatch、exact-TP event，并删除 tombstone。
- **Proposal**：`mooncake_dsa_metadata.py` 额外 `+25~40/-0~5`：snapshot validation和local skipped-bytes contract。
- **Proposal**：`sfa_kv_offload_worker.py` 最多增加 `+5~10` 的 protected bytes-per-token helper，而且只有现有 registration facts无法稳定读取时才加。
- **Proposal**：压缩并更新 `test_mooncake_connector.py`、`test_mooncake_dsa_metadata.py`；轻量参数化 `tests/ut/kv_offload/utils.py`；在 `a2/test_remote_prefill_lifecycle.py` 增加真实 public Scheduler replay test。[逐文件预算](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage3-closure-amendment.md:167)
- **Proposal**：最终预计 production additions `1,646~1,696`，focused tests `1,150~1,200`。超过 `1,710/1,200`、新增 production module/public connector API、修改vLLM core或扩大async/watchdog/restart contract时必须停审。
- **Proposal**：验证顺序是先写失败测试，再实现，然后 static、CPU/mock、default V1和affected SFA suites分别报告；NPU不能被CPU/mock结果代替。[TDD顺序](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/reimplementation-stage3-closure-amendment.md:193)

**8. 简短术语表**

- **Decision** `Main reservation`：scheduler为一个请求整个生命周期保留的Decode Host Main block容量。
- **Proposal** `reservation snapshot`：scheduler每步发布的“已分配上界 + 当前全部live IDs”。
- **Decision** `incarnation`：同一request ID的一次具体生命周期；这里用不复用的reservation ID区分。
- **Decision** `Quiesced`：worker已证明旧operation不会再访问该request destination的本地安全状态。
- **Decision** `exact TP coverage`：结果的rank集合必须严格等于当前Decode TP集合，不能用匿名计数代替。
- **Decision** `replay`：Decode从token 0重新执行full-sequence forward以重建Indexer；不是再次从Prefill拉取。
- **Decision** `FUSED_D2H`：把本step新生成的Main K/V从NPU写入Host reservation。
- **Decision** `finished_recving`：现有core transition hook；receive/replay先经typed result解释，cancellation则用它聚合Quiesced ack。
- **Proposal** `fail closed`：遇到矛盾或无法证明安全的状态立即报错并停止推进，不猜测成功或释放ownership。



---

## User

穿刺代码实现layerwise dsa时怎么解决这个问题的

## Assistant

如果你指的是上一条里的“永久 tombstone、request ID复用和 reservation gap”，结论是：

**穿刺代码没有解决同一个问题。它通过更弱的资源生命周期绕开了 reservation gap，同时没有完整解决 preemption/cancellation 下的旧操作写入问题。**

**穿刺实际怎么做**

1. 穿刺没有 lifetime reservation ID。

   它不会在 connector admission时预留整个 `prompt + max_tokens` 的 Main容量。vLLM core先成功执行 `allocate_slots()`，之后才调用 connector的 `update_state_after_alloc()`：[scheduler.py](/root/ljh/vllm-workspace/repos/vllm/vllm/v1/core/sched/scheduler.py:761)

   穿刺随后才按当前prompt长度分配 Main CPU blocks，并把它们放进以 `request_id` 为key的tracker：[sfa_pd_cpu_offload/scheduler.py](/root/ljh/vllm-workspace/repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py:317)

   因此不会出现：

   ```text
   已分配 Main reservation
   -> Indexer allocate_slots()失败
   -> worker从未收到command
   ```

   也就没有 amendment 所说的 command-never-emitted reservation gap。

2. 它只保存当前request的map，不保存历史tombstone。

   Scheduler和worker都按 `request_id` 保存当前状态。正常结束时scheduler直接：

   ```python
   tracker = self._request_trackers.pop(request.request_id, None)
   self.cpu_block_manager.free(tracker.allocated_block_ids_cpu)
   ```

   见 [sfa_pd_cpu_offload/scheduler.py](/root/ljh/vllm-workspace/repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py:598)。

   Worker稍后通过 `finished_req_ids` 删除：

   - `request_map`
   - `_dest_blocks_by_req`
   - `_cpu_blocks_by_req`
   - `_pending_done`

   见 [sfa_pd_cpu_offload/worker.py](/root/ljh/vllm-workspace/repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/worker.py:298)。

   所以这些map的规模大致等于当前active requests，request ID清理后可以直接复用，不需要永久terminal set。

3. 它确实处理了一个更窄的ordering race。

   `get_finished()`先把本step收到的remote DONE映射回internal request ID，然后才根据 `finished_req_ids`删除map。否则同一步既收到DONE又收到finish时，先删map会让DONE永远无法映射：[worker.py](/root/ljh/vllm-workspace/repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/worker.py:306)

4. Layerwise的同步只保护单层source reuse。

   Decode read thread对一层执行同步 `batch_transfer_sync_read()`，返回后才向Prefill回复 `READ_DONE`：[read_thread.py](/root/ljh/vllm-workspace/repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/read_thread.py:133)

   这能阻止Prefill过早复用这一层的source buffer，但它不是“整个Decode request已经Quiesced”的证明，也不保护scheduler刚刚归还的Main destination blocks。

**它没有解决什么**

- 穿刺没有 `main_reservation_id`、`execution_epoch`、`command_seq`，因此无法区分同一request ID的新旧incarnation。
- 它没有worker-to-scheduler Quiesced ack。`request_finished_all_groups()`只是直接假定“request结束意味着不会再有inference或KV transfer”。
- 如果取消发生在 `WAITING_FOR_REMOTE_KVS`，background read仍可能在执行，而scheduler已经把CPU block归还并分配给新请求。这就是旧DMA写入新ownership的风险。该缺口已在 [ADR 0010](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/docs/adr/0010-use-two-phase-cancellation-drain-and-ack.md:7) 明确记录。
- 穿刺的preemption也没有闭环：它没有正确替换tracker中的旧Indexer IDs，worker仍可能保留旧destination map，而且replay会从0重复Main D2H。[ADR 0009](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/docs/adr/0009-replay-preempted-requests-locally-on-decode.md:7)

**两者的本质差异**

| 问题 | 穿刺代码 | 当前目标 |
|---|---|---|
| Main分配时机 | core分配成功后，按需递增分配 | admission时预留完整lifetime容量 |
| identity | `request_id` | `main_reservation_id`，command再带epoch/sequence |
| normal finish | 直接pop和free | snapshot移除reservation，worker确认Quiesced后purge |
| preemption | lifecycle未闭环 | 保留Main、重新绑定Indexer、token-0 replay |
| cancellation | 假定finish后无操作 | 两阶段drain → all-worker ack → release |
| 历史状态 | 不保存 | 也不保存；用scheduler完整live snapshot证明retirement |

所以，穿刺代码看起来“不需要snapshot”，不是因为它有更简单而同等安全的解决方案，而是因为它没有提供当前目标要求的三项保证：

1. 完整request-lifetime Main容量；
2. 跨preemption保留Main并安全replay；
3. cancellation期间旧operation停止访问后才复用destination。

一旦保留这三项要求，单纯照搬穿刺的“按request ID直接free并删map”是不安全的；closure amendment的snapshot正是用来在不保留历史tombstone的前提下，证明哪些reservation仍然live、哪些已经永久retire。



---

## User

如果按穿刺代码的假设实现，会遇到什么问题

## Assistant

结论：如果完整采用穿刺代码的假设，基本 happy path可能工作，但会放弃当前设计中一部分已经接受的 correctness 和 capacity guarantees。主要问题不是内存泄漏，而是错误释放、旧操作写入新请求、preemption状态错配和运行中Host容量耗尽。

**会遇到的具体问题**

| 场景 | 穿刺假设下的行为 | 后果 |
|---|---|---|
| 普通、无抢占、无取消 | step结束后直接清理 | 通常可工作 |
| Host容量不足 | 运行到需要新block时才分配 | 请求运行中直接抛异常 |
| cancellation期间仍在transfer | scheduler立即free | 旧DMA可能写入已复用block |
| request ID很快复用 | 只有request-ID keyed map | late DONE/旧操作可能命中新请求 |
| preemption/resume | 没有epoch和稳定reservation identity | 旧Indexer ownership残留 |
| 某些TP失败、其他TP成功 | 没有rank-aware typed结果 | 无法证明完整TP状态 |
| async multi-batch | finish和worker operation可能重叠 | “finish即安全释放”假设失效 |

**1. Host容量可能在请求运行中突然耗尽**

穿刺只在初始prompt或每个Decode step实际需要时分配Main CPU blocks，而不是在admission时预留整个 `prompt + max_tokens` 容量：[scheduler.py](/root/ljh/vllm-workspace/repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py:470)

`CPUBlockManager`没有backpressure或等待机制，容量不足直接：

```python
raise ValueError("No enough cpu block to allocate")
```

见 [sfa_kv_offload_scheduler.py](/root/ljh/vllm-workspace/repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_scheduler.py:40)。

这意味着请求可以已经：

- 占用了Indexer HBM；
- 完成了remote prefill；
- 生成了一部分tokens；

然后因为另一个请求占用了Host blocks，在后续Decode step直接使engine失败。当前lifetime reservation设计正是为了在admission时证明该请求以后不会因Main容量不足而半途失败。

**2. Cancellation可能产生use-after-free式数据破坏**

穿刺的 `request_finished_all_groups()` 直接pop tracker并归还CPU blocks，源码注释明确假设“request finished以后没有KV transfer”：[scheduler.py](/root/ljh/vllm-workspace/repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py:598)

但worker要到后续 `get_finished(finished_req_ids)` 才删除destination map：[worker.py](/root/ljh/vllm-workspace/repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/worker.py:298)

如果请求在 `WAITING_FOR_REMOTE_KVS` 时被取消：

```text
旧请求仍在同步Mooncake read
scheduler归还Main block 12
新请求获得Main block 12
旧read返回并继续写block 12
```

这可能静默破坏新请求的KV，而不只是抛异常。ADR 0010已经把这条竞态列为不能直接沿用穿刺的原因：[ADR 0010](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/docs/adr/0010-use-two-phase-cancellation-drain-and-ack.md:7)

**3. Request ID复用会与late message混淆**

穿刺只用 `request_id` 建立：

- scheduler tracker；
- `request_map`；
- destination block map；
- finished set。

没有reservation ID、execution epoch或command sequence。

旧请求清理后，如果同一ID立即被新请求复用，晚到的旧 `READ_DONE`、旧transfer completion或旧source消息无法从identity上与新请求区分。最坏情况下，它会：

- 提前把新请求标记为receive complete；
- 清理新请求state；
- 或把旧数据写入新请求的destination。

永久禁止request ID复用可以回避这一点，但那又回到永久tombstone和无界历史状态问题。

**4. Preemption恢复不正确**

穿刺的PD scheduler没有完整处理preemption：

- core已经释放旧Indexer blocks；
- tracker仍可能保存首次receive时的旧Indexer IDs；
- worker仍可能保留旧destination map；
- replay从token 0重新执行时，又从0重复Main D2H。

这既有stale Indexer ownership风险，也损失Main prefix复用收益。[ADR 0009](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/docs/adr/0009-replay-preempted-requests-locally-on-decode.md:7)

如果完全按穿刺实现，就只能选择：

- preemption后丢弃全部Main并完整重建；
- 禁止该模式发生preemption；
- 或接受当前未闭环行为。

它不能满足当前“保留Main reservation、重新绑定Indexer、从token 0 compute replay但跳过有效Main prefix D2H”的决定。

**5. Transfer failure无法形成可靠的request级判断**

穿刺read thread在layer transfer失败时向Prefill回复 `READ_FAILED`，但当前循环随后仍会把该batch携带的 `done_ext_ids`加入本地done set：[read_thread.py](/root/ljh/vllm-workspace/repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/read_thread.py:146)

而worker上报的仍然只是request-ID set，没有：

```text
execution_epoch
command_seq
tp_rank
failure_phase
```

因此scheduler无法可靠判断：

- 哪个TP失败；
- 是否所有TP都已停止DMA；
- duplicate是否来自同一TP；
- late result是否属于旧execution；
- 何时可以安全进入full replay。

当前exact-TP typed result contract就是为了解决这组问题。[spec.md](/root/ljh/vllm-workspace/features/mte_fuised_rebase_0713_mooncake_test-0817-both-pd/spec.md:122)

**6. Async scheduling会进一步破坏释放假设**

穿刺的“request finished即没有worker operation”只在严格同步、所有save/transfer都已drain的情况下近似成立。

开启async multi-batch后，core可能正在完成batch N+1，而worker仍处理batch N的operation。此时：

- `finished_req_ids`只是一次性的request-ID信号；
- worker没有incarnation identity；
- scheduler可能先free；
- worker随后完成旧operation。

所以即使采用更简单的穿刺生命周期，DSA Decode仍至少需要拒绝 `async_scheduling`，或者实现完整的跨batchoperation tracking。

**可以保留哪些穿刺假设**

可以继续复用：

- positional ABI；
- fixed Prefill TP leader；
- Indexer D2D成功后才启动Main D2RH；
- layerwise同步transfer；
- SFA Host pool、CPU block table和fused D2H；
- 不保存历史request tombstone。

不能直接复用：

- 只用request ID作为lifecycle identity；
- normal finish/cancellation立即free；
- preemption后沿用旧tracker；
- anonymous `finished_recving`承担receive/failure/replay语义；
- 按需增量分配却声称拥有完整lifetime capacity。

因此，采用穿刺假设可以删掉snapshot的前提，是同时放弃完整Main lifetime reservation。即便如此，cancellation Quiesced、request incarnation、exact-TP failure和async ordering问题仍然存在，并不会随reservation消失。
