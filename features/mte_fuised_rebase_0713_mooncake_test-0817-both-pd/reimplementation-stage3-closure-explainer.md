# Blockwise DSA Stage 3 Closure Gate 解释与穿刺假设对照

状态：解释性 companion document；不构成 closure gate 批准，不授权 production source
修改、commit、push、lock/repo-state 刷新或 feature final status 更新

记录日期：2026-08-24

解释对象：

- [`reimplementation-stage3-closure-amendment.md`](reimplementation-stage3-closure-amendment.md)
- replacement worktree：`repos/vllm-ascend-blockwise-dsa-reimplementation`，HEAD
  `0d6dd0d26ab69219f861c9b312329f4c60fe36f2` 加未提交 WIP
- 穿刺行为参考 checkout：`repos/vllm-ascend`，HEAD
  `60eb76e46225e9aaec1493fb247313f8642486ad`
- upstream vLLM checkout：`repos/vllm`，HEAD
  `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`

本文使用以下标签区分事实层级：

- **Decision**：已经由 Stage 1、spec 或 accepted ADR 确定的 contract；
- **Current Code**：上述 replacement WIP 或穿刺 reference 中已经存在的行为；
- **Proposal**：Stage 3 closure amendment 新提出、尚待批准的内容；
- **Risk**：当前实现或候选简化方案保留的 correctness、availability 或 performance 风险；
- **Unverified**：尚未由真实 multi-node/NPU/runtime evidence 验证的内容。

## 1. 一句话 mental model

**Decision**：Blockwise DSA 在 Decode 侧把 KV 分成两类 ownership：Indexer 位于当前
execution epoch 的 HBM blocks，Main 位于跨 request lifetime 保留的 Host blocks。初始
receive 在每个 Decode TP worker 内先执行 Indexer D2D，成功后才执行 Main D2RH；Decode
后续新生成的 Main KV 通过 fused D2H 写回 Host。Preemption 会释放旧 Indexer HBM
ownership，但在可以证明 validity 时保留 Main reservation 和已确认的 Main prefix。

这意味着 Main Host blocks 不能只被看作一次 transfer 的临时 buffer。它们既是 request
lifetime capacity，也是 preemption replay 和 cancellation cleanup 的 destination
ownership。

依据：[`spec.md`](spec.md)、
[`ADR 0009`](docs/adr/0009-replay-preempted-requests-locally-on-decode.md)、
[`ADR 0010`](docs/adr/0010-use-two-phase-cancellation-drain-and-ack.md)。

## 2. Closure gate 实际解决的不是一个孤立 bug

**Current Code**：Stage 1 已经把 replacement 收敛为
`MooncakeConnectorV1 + typed metadata + thin SFA extensions`，没有迁移 `60eb76e` 中的
standalone scheduler、runtime、worker、transport、rendezvous 或 memory subsystem。

**Proposal**：Stage 3 closure gate 把七个相互依赖的缺口放在同一个门禁中处理：

| 缺口 | 为什么不能单独打补丁 |
|---|---|
| 永久 `_dsa_terminal_requests` | 历史 request ID 无界增长，并永久拒绝合法的 request ID reuse |
| Worker-private reservation fence | Worker 看不到已 admission 但从未形成 command 的 reservation gap |
| Private replay test | 只证明 connector state mutation，不证明 public `Scheduler.schedule()` 从 token 0 调度 forward |
| 错误的 skipped-byte 口径 | Main page bytes 可能含 C8 padding/scale，不等于 fused D2H K/V descriptor bytes |
| DSA 未拒绝 `async_scheduling` | normal finish 可能和旧 batch 的 worker operation 重叠 |
| one-shot `finished_req_ids` cleanup | 信号晚于 `start_load_kv()`，丢失后不重试，也不区分 request incarnation |
| synthetic metadata recursive dispatch | 加入 snapshot 后会绕过或回退 worker 已接受的 current truth |

**Risk**：如果只删除 tombstone而不增加 authoritative retirement truth，late command 可以重新
创建已经释放的 state；如果只保留 tombstone，则 request ID reuse 和历史内存都不能闭环。

## 3. 为什么 scheduler-authored snapshot 是当前提案的核心

### 3.1 两个字段表达什么

**Proposal**：每个 Decode scheduler step 都发送完整 immutable snapshot：

```python
reservation_id_upper_bound: int
live_reservation_ids: tuple[int, ...]
```

- `reservation_id_upper_bound` 是下一个可分配 ID，因此所有历史已分配 reservation ID 都
  严格小于它；
- `live_reservation_ids` 是 scheduler 当前仍可能为其产生 command 的完整集合；
- live set 包括已 admission 但尚未取得 Indexer blocks 的 reservation；
- live set 也包括 cancel-pending、尚未得到 all-worker Quiesced completion 的 reservation。

**Decision**：Scheduler 仍是 Main reservation lifecycle 的唯一 owner。Snapshot 只是它向
worker 发布的 current truth，不在 metadata 内建立第二套 mutable lifecycle。

### 3.2 Worker 如何验证时间只能向前

**Proposal**：Worker 原子接受 snapshot 后才 dispatch 本 step command，并执行以下约束：

1. upper bound 不能回退；
2. live IDs 必须严格递增、非负且小于 upper bound；
3. 新 snapshot 中低于旧 upper bound 的 IDs 只能是旧 live set 的子集；
4. 新引入的 IDs 只能落在 `[old_upper_bound, new_upper_bound)`；
5. command 引用的 reservation ID 必须属于同一 snapshot 的 live set；
6. 已退出 live set 的 local state 只有在 operation、pending command、pending quiesce 和
   pending fused save 都为空时才能 purge；
7. 同一 request ID 的新 reservation 只能在旧 incarnation retired 且 Quiesced 后建立。

由此可以推导：

- retired reservation 永远不能被旧 snapshot 或 late command 复活；
- request ID 可以复用，因为真正的 incarnation identity 是单调 reservation ID；
- worker 只保存最新 snapshot 和当前 live state，空间随当前 live reservations 增长，而不是
  随历史请求数增长；
- 没有形成 command 的 reservation 也能由 scheduler 的完整 live set 正确 retire。

### 3.3 为什么不采用 private interval fence

**Current Code**：Replacement 在
`_MooncakeDsaDecodeScheduler.get_num_new_matched_tokens()` 中先分配 Main reservation，再由
vLLM core 尝试 Indexer `allocate_slots()`。Core allocation 可以返回 `None`，此时不会调用
connector `update_state_after_alloc()`，也不会产生 worker command。

源码：

- [replacement reservation admission](../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py)
- [vLLM allocation ordering](../../repos/vllm/vllm/v1/core/sched/scheduler.py)

**Risk**：Worker-private fence 只能记录自己见过的 IDs。反复产生“已分配但无 command”的 gap
时，worker既不能证明这些 IDs 是否仍 live，也不能安全压缩历史 interval；任何 TTL/LRU
eviction又会允许 stale command复活。

## 4. Ordered execution 和 terminal delivery

**Current Code**：vLLM model-runner connector hook 的顺序是：

```text
bind metadata
start_load_kv(metadata)
model execution / wait_for_save
get_finished(finished_req_ids)
build_connector_worker_meta
```

源码：
[`kv_connector_model_runner_mixin.py`](../../repos/vllm/vllm/v1/worker/kv_connector_model_runner_mixin.py)。

**Proposal**：DSA worker 在 `start_load_kv()` 中先接受完整 snapshot、retire/purge旧state，
再dispatch commands。之后到来的 request-ID-only `finished_req_ids` 不再作为DSA reservation
retirement依据。Normal-finish retirement只能来自scheduler snapshot。

**Proposal**：DSA Decode startup在 `scheduler_config.async_scheduling=true` 时fail closed。
这不改变default `MooncakeConnectorV1`或非DSA role，只是保住“normal finish前该同步step的
worker operation已经drain”的首版前提。

**Decision**：Cancellation仍使用typed `QUIESCE` command，worker达到本地Quiesced后先
best-effort发送已有 `DONE_RECVING_MSG`，再上报一次普通 `finished_recving`。Scheduler只有在
vLLM聚合出all-worker completion后才release-once Main reservation。Cancellation不新增typed
`QUIESCED` result。

## 5. Replay 的完整例子

假设当前只有请求 `req-42`：

1. **Proposal**：Admission分配 `main_reservation_id=7`，snapshot为
   `upper_bound=8, live=(7,)`。
2. **Decision**：初始receive完成后，scheduler确认Main中已有128个有效tokens。
3. **Decision**：Core preempt请求并释放旧Indexer HBM blocks；Main reservation 7和可证明
   有效的128-token Main prefix继续保留。
4. **Current Code**：请求恢复、core分配新Indexer blocks后，replacement scheduler产生
   `PREPARE_REPLAY`，execution epoch提高但reservation ID仍为7。
5. **Proposal**：每个Decode TP返回 `REPLAY_READY` 和本rank
   `skipped_d2h_bytes`。Scheduler只有在exact TP rank-set coverage完整后才继续。
6. **Decision**：Scheduler把request token state重置到0，并通过现有`finished_recving` hook让
   core恢复调度。
7. **Proposal**：Real public `Scheduler.schedule()` test证明full-sequence forward确实从token
   0被调度，而且使用新Indexer block table。
8. **Decision**：Replay经过 `[0, 128)` 时不重复Main D2H；超过128后，后继`FUSED_D2H`只写
   preserved boundary之后的suffix。
9. **Proposal**：Normal finish后的新snapshot移除7；worker确认state已Quiesced后purge。
10. **Proposal**：未来另一个同名`req-42`可以用不小于8的新reservation ID进入，不会被旧
    request-ID tombstone拒绝。

**Decision**：如果进入replay的原因是初始transfer failure而不是preemption，则所有TP的
Main validity统一降为0，`reused_main_tokens=0`、`skipped_d2h_bytes=0`，full replay从0重写。

## 6. `skipped_d2h_bytes` 为什么必须来自实际 descriptor geometry

**Decision**：Accepted spec item 44和ADR 0009要求记录：

```text
replay_tokens
reused_main_tokens
skipped_d2h_bytes
```

**Current Code**：C8 Main page bytes可能包含为了page ratio加入的padding；它不是fused D2H
实际复制的K/V payload大小。SFA worker的descriptor使用：

```text
num_offload_layers
token_size_bytes_k
token_size_bytes_v
```

并分别为K、V descriptor写入真实copy size。

**Proposal**：每个TP的local skipped bytes按registration-derived geometry计算：

```text
preserved_main_tokens
* num_offload_layers
* (token_size_bytes_k + token_size_bytes_v)
```

Scheduler在exact TP coverage后求和，只记录一条`scope=decode_dp` aggregate event。若现有
SFA interface不能稳定暴露这些registration facts，最多增加一个protected helper，不建立
metrics、layout或observation subsystem。

源码：

- [C8 page layout](../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/core/kv_cache_interface.py)
- [fused D2H descriptor geometry](../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py)

## 7. 穿刺代码实际采用了什么假设

### 7.1 它没有 lifetime reservation

**Current Code**：穿刺先让vLLM core成功分配NPU blocks，然后才在
`SFAPDCpuOffloadScheduler.update_state_after_alloc()` 中按当前prompt长度分配Main CPU
blocks。Decode增长时再按step增量分配。

源码：

- [core成功allocation后调用connector](../../repos/vllm/vllm/v1/core/sched/scheduler.py)
- [穿刺Main CPU allocation](../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py)

因此穿刺不会产生“Main reservation已分配、Indexer allocation失败、worker从未见过
command”的gap。它不是解决了gap retirement，而是没有建立产生该gap的lifetime
reservation contract。

### 7.2 它按 request ID 保存当前map并直接删除

**Current Code**：穿刺scheduler在`request_finished_all_groups()`中直接pop tracker并立即
归还Main CPU blocks。Worker稍后通过`get_finished(finished_req_ids)`删除：

- `_cpu_blocks_by_req`；
- `request_map`；
- `_dest_blocks_by_req`；
- `_pending_done`。

因此它没有永久terminal set，map规模大致随当前active requests增长，清理后允许request ID
复用。

### 7.3 它解决了一个更窄的same-step ordering问题

**Current Code**：Worker的`get_finished()`先把read thread本step的remote DONE映射回internal
request ID，再处理`finished_req_ids` cleanup。否则同一步先删`request_map`会让DONE无法映射
并永久留在`_pending_done`。

源码：
[`sfa_pd_cpu_offload/worker.py`](../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/worker.py)。

这只解决“DONE和cleanup同一步到达”的map ordering，不证明旧transfer已经不再访问
destination。

### 7.4 Layerwise同步保护的是source layer reuse，不是request retirement

**Current Code**：Decode read thread收到某层`READ_READY_BATCH`后，同步执行
`batch_transfer_sync_read()`，返回后才向Prefill回复该层`READ_DONE`或`READ_FAILED`。

源码：
[`sfa_pd_cpu_offload/read_thread.py`](../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/read_thread.py)。

这可以保护Prefill端单层buffer不过早复用，但它不等于：

- 整个Decode request已Quiesced；
- 所有Decode TP都完成同一command；
- scheduler已经可以安全复用Main destination；
- late result属于当前request incarnation。

## 8. 如果完整采用穿刺假设，会遇到什么问题

### 8.1 Host capacity在运行中才失败

**Current Code**：穿刺按需增量分配Main CPU blocks；`CPUBlockManager.allocate_block()`在容量
不足时直接抛`ValueError("No enough cpu block to allocate")`，没有HOL admission、等待或
request-local fallback。

**Risk**：请求可能已经占用Indexer、完成remote prefill并生成部分tokens，随后在某个Decode
step因为Host capacity不足使engine失败。采用这种假设就放弃了“admission成功后完整Main
lifetime capacity已保证”的contract。

### 8.2 Cancellation可能旧操作写入已复用block

**Current Code**：穿刺scheduler注释直接假定request finished后“不再有inference或KV
transfer”，因此立即free Main blocks；worker destination map却要到后续`get_finished()`才
清理。

**Risk**：如果请求在`WAITING_FOR_REMOTE_KVS`或fused D2H尚未drain时取消：

```text
旧请求仍在transfer到Main block 12
scheduler把block 12归还pool
新请求获得block 12
旧operation返回并继续写block 12
```

结果可能是新请求KV被静默破坏，而不只是显式异常。这是ADR 0010采用两阶段
drain-and-ack的直接原因。

### 8.3 Request ID reuse会与late message混淆

**Current Code**：穿刺没有reservation ID、execution epoch或command sequence。Scheduler
tracker、worker map和completion都只按request ID寻址。

**Risk**：旧request清理后，如果同一ID很快被新request复用，晚到的旧`READ_DONE`、transfer
completion或source消息无法从identity上与新request区分，可能提前完成、清理或写入新
incarnation。

### 8.4 Preemption没有完整闭环

**Current Code**：穿刺PD scheduler没有正确清除或重新绑定首次pull使用的Indexer IDs，worker
可能继续保存旧Indexer destination map；恢复时full replay还会从0重复Main D2H。

**Risk**：它同时保留stale Indexer ownership和重复Main D2H。要完全采用穿刺假设，就必须在
以下方案中重新选择，而不能继续声称满足当前ADR 0009：

- preemption后丢弃并完整重建Main；
- DSA模式禁止preemption；
- 接受当前未闭环行为；
- 或重新实现epoch/rebind/preserved-prefix contract。

### 8.5 Transfer failure不能形成可靠的request-level判断

**Current Code**：穿刺worker主要向scheduler返回request-ID-only completion，没有
`execution_epoch`、`command_seq`、`tp_rank`和`failure_phase`。Layer read失败可以向Prefill
回复`READ_FAILED`，但Decode scheduler没有完整rank-aware typed terminal facts来决定何时
可以replay。

**Risk**：Scheduler不能证明：

- 哪个Decode TP上报；
- 是否所有TP已经停止当前command；
- duplicate是否来自同一TP；
- result是否属于旧execution；
- 是否可以在没有其他DMA竞争时开始full replay。

### 8.6 Async multi-batch破坏“finish即Quiesced”假设

**Risk**：Async scheduling允许core normal finish和旧batch worker operation重叠。
Request-ID-only one-shot finish既不能表达operation identity，也不能在丢失后重试。即使采用
更简单的穿刺allocation，DSA Decode仍至少需要拒绝`async_scheduling`，或者实现完整的
concurrent batch lifecycle。

## 9. 穿刺方案与当前目标的contract差异

| 维度 | 穿刺假设 | 当前accepted target / closure proposal |
|---|---|---|
| Main allocation | Core allocation成功后按当前需要增量分配 | Admission时保留完整request-lifetime capacity |
| Incarnation identity | `request_id` | stable `main_reservation_id`，command另有epoch/sequence |
| Worker history | 不保存，按finished ID删map | 也不保存历史；proposal用latest live snapshot证明retirement |
| Normal finish | Scheduler直接pop/free | Proposal由snapshot retire，worker只在Quiesced后purge |
| Preemption | lifecycle未闭环或完整重写 | 保留reservation、重绑Indexer、token-0 replay、可证明prefix不重复D2H |
| Cancellation | 假定finish后无operation | 两阶段QUIESCE、all-worker completion、release-once |
| Transfer result | request-ID-only channel | typed identity + exact TP rank-set coverage |
| Host capacity | 运行中按需申请，可能中途失败 | Admission时保证完整future capacity |
| Async scheduling | 没有DSA专用拒绝 | Proposal首版DSA Decode fail closed |

**结论**：穿刺看起来“不需要snapshot”，主要因为它没有建立当前target的完整lifetime
reservation和跨preemption Main reuse contract。若删除这两项，command-never-emitted gap会
消失；但cancellation Quiesced、late incarnation、exact-TP failure和async ordering问题不会
随之消失。

## 10. 哪些内容可以复用，哪些不能照搬

可以继续复用：

- **Decision**：positional ABI及其部署前置条件；
- **Decision**：fixed Prefill TP leader routing；
- **Decision**：worker-local Indexer D2D成功后才启动Main D2RH；
- **Decision**：Mooncake同步transfer和现有endpoint/session机制；
- **Decision**：SFA Host pool、CPU block table、fused D2H和save drain；
- **Proposal**：不保留历史request-ID tombstone。

不能直接照搬：

- **Risk**：只用request ID作为lifecycle incarnation；
- **Risk**：normal finish和cancellation立即free；
- **Risk**：preemption后继续使用旧tracker/destination；
- **Risk**：用anonymous `finished_recving`解释receive、failure和replay；
- **Risk**：按需增量分配却声称拥有完整lifetime capacity；
- **Risk**：把per-layer`READ_DONE`当作whole-request Quiesced。

## 11. 已决定、仍待批准和未验证

### 已决定

- **Decision**：最终module shape仍为
  `MooncakeConnectorV1 + typed metadata + thin SFA extensions`；
- **Decision**：不建立standalone scheduler/runtime/worker/transport/memory subsystem；
- **Decision**：typed actions/results、exact TP coverage、positional ABI和routing amendment A；
- **Decision**：preemption token-0 compute replay与可证明Main prefix reuse；
- **Decision**：cancellation必须drain到worker-local Quiesced后release；
- **Decision**：首版不增加watchdog、native reliable cancel或automatic restart；
- **Decision**：`skipped_d2h_bytes`是accepted observation字段。

### 仍待批准

- **Proposal**：scheduler-authored live reservation snapshot；
- **Proposal**：DSA Decode拒绝`async_scheduling`；
- **Proposal**：`REPLAY_READY`携带local skipped bytes并由scheduler按exact TP聚合；
- **Proposal**：真实public Scheduler token-0 replay-forward test；
- **Proposal**：production additions `1,710`、focused tests `1,200`的新停审线。

### 尚未验证

- **Unverified**：真实multi-node transfer；
- **Unverified**：NPU Host registration和Mooncake destination correctness；
- **Unverified**：fused kernel及真实descriptor执行；
- **Unverified**：NPU侧实际skipped bytes证据；
- **Unverified**：runtime performance和preemption tail-latency影响。

以上必须保持`planned / not run`，不能由static或CPU/mock结果代替。

## 12. Closure proposal 对代码和测试的影响

**Proposal**：不新增production file或public connector interface，预计修改：

| File | 计划 |
|---|---|
| `mooncake_connector.py` | async fail-closed、snapshot生成/消费、retirement、single-command dispatch、exact-TP observation、删除tombstone |
| `mooncake_dsa_metadata.py` | snapshot central validation、local skipped-byte result contract |
| `sfa_kv_offload_worker.py` | 仅在需要时增加registration-derived bytes-per-token protected helper |
| `test_mooncake_connector.py` | request-ID reuse、gap、snapshot monotonicity、terminal ordering，压缩private replay cases |
| `test_mooncake_dsa_metadata.py` | snapshot/result invariants |
| `tests/ut/kv_offload/utils.py` | real Scheduler DSA fixture的最小参数化 |
| `a2/test_remote_prefill_lifecycle.py` | public token-0 replay-forward contract |

**Proposal**：最终预计production additions约`1,646-1,696`，focused tests约
`1,150-1,200`。超过`1,710/1,200`、新增production module/public interface、修改vLLM core
或扩大positional ABI/watchdog/restart/async contract时立即停审。

## 13. Glossary

- **Main reservation**：scheduler为一个request lifetime隔离的Decode Host Main capacity；
- **Incarnation**：同一个request ID的一次具体生命周期；target以不复用的reservation ID区分；
- **Live snapshot**：scheduler发布的当前reservation上界和完整live set；
- **Execution epoch**：一次Indexer HBM ownership生命周期；preemption后提高；
- **Command sequence**：同一epoch内严格递增的lifecycle command序号；
- **Quiesced**：worker已证明旧operation不再访问该request destination的本地安全条件；
- **Exact TP coverage**：结果rank集合严格等于当前routed Decode DP replica的TP rank集合；
- **Replay**：Decode从token 0重新执行full-sequence forward以重建Indexer，不是再次从Prefill拉取；
- **Preserved Main prefix**：preemption前已确认写入Host、replay时无需重复D2H的Main token区间；
- **Fail closed**：无法证明状态合法或安全时立即报错并停止推进，不推测completion或释放ownership；
- **`finished_recving`**：现有vLLM core transition hook；receive/replay先由typed results解释，
  cancellation则只在worker Quiesced后作为ordinary all-worker ack使用；
- **`DONE_RECVING_MSG`**：Decode发给Prefill的best-effort source-release notification，不是Decode
  cancellation ack。

## 14. 证据索引

设计与状态：

- [Stage 1 design gate](reimplementation-stage1-design-gate.md)
- [Stage 1 routing amendment](reimplementation-stage1-routing-amendment.md)
- [Stage 3 closure amendment](reimplementation-stage3-closure-amendment.md)
- [Feature spec](spec.md)
- [ADR 0009: preemption replay](docs/adr/0009-replay-preempted-requests-locally-on-decode.md)
- [ADR 0010: cancellation drain-and-ack](docs/adr/0010-use-two-phase-cancellation-drain-and-ack.md)
- [ADR 0016: no watchdog](docs/adr/0016-do-not-watchdog-unquiesced-operations.md)
- [ADR 0017: typed metadata family](docs/adr/0017-use-a-separate-typed-dsa-metadata-family.md)
- [ADR 0020: actions/results](docs/adr/0020-use-lifecycle-actions-and-terminal-local-results.md)
- [ADR 0021: exact TP coverage](docs/adr/0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md)
- [ADR 0022: positional ABI](docs/adr/0022-use-the-puncture-positional-handshake-abi.md)

Replacement WIP：

- [MooncakeConnector lifecycle](../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py)
- [Typed DSA metadata](../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py)
- [SFA fused D2H worker](../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py)
- [Current private replay tests](../../repos/vllm-ascend-blockwise-dsa-reimplementation/tests/ut/kv_offload/test_mooncake_connector.py)

穿刺reference：

- [SFA PD scheduler](../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py)
- [SFA PD worker](../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/worker.py)
- [Layerwise read thread](../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/read_thread.py)
- [SFA CPU block manager](../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_scheduler.py)
- [SFA metadata](../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/config_data.py)

Upstream lifecycle ordering：

- [vLLM Scheduler allocation flow](../../repos/vllm/vllm/v1/core/sched/scheduler.py)
- [vLLM connector model-runner flow](../../repos/vllm/vllm/v1/worker/kv_connector_model_runner_mixin.py)
