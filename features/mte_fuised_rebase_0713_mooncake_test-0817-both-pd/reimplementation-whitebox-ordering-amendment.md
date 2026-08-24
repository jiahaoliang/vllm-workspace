# Blockwise DSA replacement worker ordering amendment

状态：用户已于 2026-08-24 明确批准 scheduler-causality invariant、删除 generic
`pending_command`、修复 cancellation ack race并收紧 terminal transition atomicity，以及 production `1,770`、focused tests
`1,460` 的新 stop line。授权按本文件执行 TDD source/test 修改与 CPU/mock focused
validation；不授权 NPU validation、commit、push、lock/repo-state/issues 更新或 control-repo
final status。

## 1. Scope 与 supersession

本 amendment 延续
[`reimplementation-whitebox-review-amendment.md`](./reimplementation-whitebox-review-amendment.md)
已经采纳的三项 corrective direction，并解决其中留下的 `pending-command` ordering 决策。

本决定 supersede
[`reimplementation-stage3-closure-amendment.md`](./reimplementation-stage3-closure-amendment.md)
中以下 implementation requirement：

- worker retirement 不再等待 generic `pending_command` 为空；
- `_finish_dsa_operation()` 不再继续 dispatch pending successor；
- private positive ordering test 不再要求 worker缓存与旧 operation重叠的
  `PREPARE_REPLAY`。

Scheduler-authored reservation snapshot、exact-TP result coverage、`pending_quiesce`、ordinary
`finished_recving` cancellation ack、ADR 0016 unquiesced residual risk及其他 accepted contract
保持不变。本决定不新增 ADR、production module、public connector interface或 upstream vLLM
core修改。

## 2. 已批准 scheduler-causality invariant

对同一个 live Main reservation，除 `QUIESCE` 外，scheduler只有在前一 command的所有 Decode
TP local operation已经 terminal后，才能发出 strictly newer command。Worker不承诺缓存、排序
或执行与旧 `in_flight` operation重叠的 newer non-`QUIESCE` successor；遇到该输入必须 fail
closed。

Duplicate/stale command继续在 overlap check前按现有 identity规则幂等忽略；相同 identity但内容
冲突继续 fail closed。错误必须包含 request、旧 operation identity和新 command identity/action，
使未来 async/PP或scheduler行为变化可观察。

该 invariant 的当前 production causality依据是：

- DSA Decode startup拒绝 `async_scheduling=true` 和 Decode PP大于1，因此只存在一个同步 batch；
- `RECEIVE_REMOTE -> PREPARE_REPLAY` 必须先收齐 exact Decode TP terminal coverage，每个 worker
  又在上报本地 result前结束自己的 operation；
- 普通 receive成功后，core只有收到 completion才把 `WAITING_FOR_REMOTE_KVS` 恢复为可调度状态，
  该状态本身不可 preempt；
- `PREPARE_REPLAY` 同步产生 `REPLAY_READY`，后继 replay forward仍等待 exact TP coverage；
- `FUSED_D2H` 在当前同步 engine step的 `wait_for_save()` 中 drain并上报结果；
- operation不返回时不会产生 non-`QUIESCE` successor，继续按 ADR 0016保持 ownership隔离。

因此 `PREPARE_REPLAY` 的 drain/retire语义由 scheduler exact-TP barrier保证，而不是由 worker建立
第二个隐式 successor scheduler。现有 synthetic receive-to-replay overlap不是合法 production
command sequence。

## 3. 已批准 worker implementation boundary

- 删除 `_DsaWorkerRequestState.pending_command`、pending merge/overwrite规则、completion后的递归
  dispatch和只为该路径存在的 private single-command wrapper。
- newer non-`QUIESCE` command遇到 `state.in_flight is not None` 时立即 fail closed。
- 保留 `pending_quiesce`；`QUIESCE` 是唯一允许与 local operation overlap的 successor。
- 仅对 terminal transition增加窄的 per-request synchronization，原子维护 `in_flight`、
  `pending_quiesce` 和 ordinary-completion-once。所有 Mooncake/SFA调用、logger、result emission和
  ordinary ack emission必须在锁外执行。
- Completion必须使用提交时捕获的 reservation/epoch/sequence/action token校验，不能把旧 result
  按随后到达的 `QUIESCE` action解释，也不能让 request-ID reuse后的 callback清理新 incarnation。
- `_dsa_finished_recving` 改用 `queue.SimpleQueue[str]` 或等价 atomic drain机制；禁止 callback
  `add()` 与 engine `update(); clear()` 交错丢失一次性 ack。

## 4. Cancellation ordering evidence

最初 white-box review提出两个 cancellation邻接风险。TDD deterministic interleaving对第一项
进行了反证和收窄：

1. 旧实现把 `_dsa_active_commands[request_id]` 改为更高 identity的 `QUIESCE` 后，插入的旧
   `RECEIVE_COMPLETE` 会先被 identity comparison当作 stale并忽略，不会进入 action validation；
   因此“当前代码必然按 QUIESCE错误 fail-fast”不是 confirmed bug。实现改为 callback捕获具体
   operation token后，仍必须先原子发布 `pending_quiesce`，确保 cancellation intent抑制旧 result，
   但这是新 transition的正确性要求，不冒充旧代码已执行故障。
2. Receiver callback向裸 `_dsa_finished_recving` set执行 `add()`，engine thread执行
   `update(); clear()`；另一个 request的 ack可能在两步之间被永久清除，而 finished-once guard
   不会重发。Deterministic drain test已得到真实 red，因此这是 confirmed pre-existing bug。

`pending_quiesce` 的 completion-once claim仍可能由 engine与callback同时进入，故 approved
request-local synchronization继续必要。Terminal intent、`in_flight` clear和finished-once claim
原子化，ack使用 atomic queue drain；不恢复 generic pending queue或 completion mailbox。

## 5. TDD seams 与 cases

测试继续使用已批准的 public `MooncakeConnector` lifecycle seam和现有 controllable receiver
adapter，不直接断言 lock、queue或 private transition object：

1. 将 synthetic pending-replay positive case替换为 deterministic fail-closed case：blocked
   receive期间提交 newer replay必须失败；receive terminal并发布 result后相同 replay可接受。
2. 参数化证明 blocked `RECEIVE_REMOTE` 和尚未 `wait_for_save()` 的 `FUSED_D2H` 都拒绝 newer
   non-`QUIESCE` command。
3. 使用 `Event`/`Barrier` 控制 `QUIESCE` publish与 receive completion的两种交错，证明不发生
   action/result错配，只产生一次 ordinary completion，且旧 result不重新激活 request。
4. 控制 `get_finished()` drain与多个 callback completion交错，证明每个 request ack恰好可取一次
   且不会永久丢失。
5. 保留 real Scheduler exact-TP transfer-failure replay、preemption/new Indexer ownership、stable
   Main reservation、suffix-only D2H和snapshot retirement证据。

测试禁止使用 sleep或重复概率运行证明线程安全。NPU资源当前不可用，NPU状态保持
`planned / not run`。

## 6. 合并预算与 stop line

相对当前 source HEAD `3a22c5a6d697250dbf942354bfdac1781af3077d` 的 additional churn：

| 范围 | Production additions | Production deletions | Focused-test additions | Focused-test deletions |
|---|---:|---:|---:|---:|
| 已采纳三项 corrective change | 37-63 | 9-22 | 40-70 | 4-20 |
| 删除 generic `pending_command` | 4-8 | 29-34 | 6-12 | 2-6 |
| Cancellation terminal synchronization | 12-24 | 7-14 | 30-55 | 4-10 |
| **合计** | **53-95** | **45-70** | **76-137** | **10-36** |

在不折抵被替换的当前 additions时，相对 base `0d6dd0d26ab69219f861c9b312329f4c60fe36f2`
的保守 final additions预计为 production `1,723-1,765`、focused tests `1,396-1,457`。
新的 stop-and-review thresholds为：

- production additions超过 `1,770`；
- focused-test additions超过 `1,460`；
- 需要新增 production module、public interface、completion mailbox、generic pending queue或修改
  vLLM core；
- 需要扩大 async scheduling、Decode PP、watchdog、native cancel、automatic restart或
  process-failure contract；
- 需要删除 public Scheduler、typed negative、default V1、cancellation或worker ordering必要证据。

触发任一条件必须停止并重新提交门禁，不能以压缩可读性或删除必要 tests满足数字。

## 7. Source/test allowlist 与验证边界

批准的 source/test staging allowlist仅包含：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`；
- `tests/ut/kv_offload/test_mooncake_connector.py`；
- 仅在补强已批准 real Scheduler证据确有必要时，
  `tests/ut/kv_offload/a2/test_remote_prefill_lifecycle.py`。

Static、CPU/mock、default V1、multi-node与NPU evidence必须分开报告。本批准允许按
`AGENTS.md`在 `liangjiahao` namespace的专用 UT Pod运行 CPU/mock验证；当前用户已要求跳过
NPU，不得据此创建或运行 NPU workload。

## 8. 批准边界

用户于 2026-08-24 明确批准本 amendment 的 invariant、cancellation邻接修复和
production `1,770`、focused tests `1,460` stop line。批准只授权本文件与 parent
white-box amendment范围内的 TDD source/test修改和 CPU/mock验证；不授权 commit、push、
`workspace.lock.json`、repo-state、issues或 final feature status更新。
