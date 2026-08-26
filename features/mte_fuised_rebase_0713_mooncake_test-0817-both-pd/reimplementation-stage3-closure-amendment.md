# Blockwise DSA Stage 3 统一收尾增量门禁

状态：已批准并用于sync replacement；async startup rejection、single-active D2H与terminal ordering条款已被ADR 0024-0030部分取代；其余历史closure evidence保留

解释材料：[`reimplementation-stage3-closure-explainer.md`](reimplementation-stage3-closure-explainer.md)

## 1. 当前边界与必须再次停审的原因

Stage 1 design gate 和 multi-node endpoint routing amendment 方案 A 已批准并实现。当前
replacement WIP 仍以 `0d6dd0d26ab69219f861c9b312329f4c60fe36f2` 为 HEAD，改动只有
`MooncakeConnectorV1` lifecycle、typed metadata、一个 thin SFA scheduler extension 和
focused tests，没有 standalone scheduler、worker、runtime、decode-worker、transport、
rendezvous 或 memory subsystem。

当前相对 base 的实际规模为：

| 类别 | Additions | Deletions |
|---|---:|---:|
| Production | 1,541 | 39 |
| Focused tests | 1,099 | 40 |

Stage 3 static review 发现以下相互关联的收尾缺口：

1. Worker 的永久 `_dsa_terminal_requests: set[str]` 无界增长，并永久拒绝合法复用的
   `request_id`。
2. Private reservation interval fence 的 bounded-memory proof 不成立：reservation ID 在
   connector admission 时分配，但 core 的 Indexer `allocate_slots()` 随后可以失败；该
   reservation 从未形成 command，worker 无法自行 retire。反复出现这种 gap 时，即使
   live reservation 为 0，terminal intervals 也可以无界增长。
3. Replay test 直接修改 private request state 并注入后继 `SchedulerOutput`，没有证明
   public core scheduler lifecycle 真正从 token 0 调度 forward。
4. Accepted spec item 44 和 ADR 0009 要求记录 `skipped_d2h_bytes`；scheduler 的 Main
   `page_size_bytes / block_size` 包含 C8 padding/scale，不能冒充 fused D2H 实际复制的
   K/V bytes。
5. DSA Decode 尚未拒绝 `async_scheduling`。异步多 batch 允许 core normal finish 与
   worker operation 重叠，破坏“释放 Main reservation 前 worker 已 Quiesced”的前提。
6. Worker 先执行 `start_load_kv(metadata)`，后在 `get_finished(finished_req_ids)` 收到
   request-ID-only、one-shot finish 信号。当前 state 若尚未 Quiesced 会静默跳过且不会
   重试；该信号也不能区分同一 request ID 的新 incarnation。
7. `_finish_dsa_operation()` 通过构造仅含 pending command 的新
   `DsaConnectorMetadata` 递归 dispatch。加入 retirement snapshot 后，这会绕过或回退
   已接受 snapshot，必须拆开 snapshot admission 与 single-command dispatch。

这些问题必须在同一 closure gate 中解决；不得再批准互斥的 terminal gate。

## 2. 方案 A：scheduler-authored live reservation snapshot

删除永久 request-ID tombstone。`request_id` 不是 incarnation identity；现有单调递增、
不复用的 `main_reservation_id` 才是 Main lifetime incarnation identity。

在现有 typed metadata 中增加完整 immutable snapshot：

```python
@dataclass(frozen=True, slots=True)
class DsaConnectorMetadata(KVConnectorMetadata):
    requests: tuple[DsaStepRequest, ...] = ()
    reservation_id_upper_bound: int = 0
    live_reservation_ids: tuple[int, ...] = ()
```

`reservation_id_upper_bound` 是下一个可分配 ID，即所有已分配 reservation ID 的严格
上界；`live_reservation_ids` 是 scheduler 当前仍可合法产生 command 的完整、排序、
去重集合。它包含已 admission 但尚未获得 Indexer blocks、cancel-pending 但尚未收到
all-worker completion 的 reservation。Snapshot 只传递 current truth，不拥有 mutable
lifecycle、operation、tensor 或历史 tombstone。

Scheduler 继续是唯一 reservation lifecycle owner：

- admission 分配 ID 后立即提高 upper bound并加入 live set；
- core allocation 暂时失败不 retire reservation，因此 command-never-emitted gap 仍被
  snapshot 明确表示；
- normal finish 或 all-worker Quiesced cancellation release-once 后移出 live set；
- 每个 command 的 reservation ID 必须属于同一 snapshot 的 live set。

Worker 在 dispatch command 前原子接受 snapshot，并保持上一份
`(upper_bound, live_ids)`：

- upper bound 不得回退；live IDs 必须严格递增、非负且小于 upper bound；
- 新 snapshot 中小于旧 upper bound 的 live IDs 必须是旧 live set 的子集；提高 upper
  bound 时只允许在 `[old_upper_bound, new_upper_bound)` 引入新 ID；因此 retired ID 永不
  复活，旧 snapshot replay 会 fail closed；
- command 引用 non-live ID 时 fail closed；
- 不再 live 的 request-local state 只有在 `in_flight`、`pending_command`、
  `pending_quiesce` 和 pending fused save 全为空时才能 purge，否则 fail closed；
- 同一 request ID 使用更大的 live reservation ID 时，只有旧 incarnation 已从 snapshot
  retire 且 Quiesced 后才能建立新 state；旧 incarnation 仍 live 或 non-Quiesced 时
  fail closed。

Worker 只保存最新 snapshot 与当前 live request state，空间复杂度为当前 live
reservations，而不是历史 request 数。缺少 command 的 reservation 也能由 scheduler
推进的 upper bound 与完整 live set永久判定为 stale。

## 3. Terminal delivery 与 ordered execution

DSA Decode startup 必须在 `scheduler_config.async_scheduling` 为 true 时 fail closed；不
修改普通 `MooncakeConnectorV1` 或非 DSA role 的 async behavior。首版不增加 concurrent
batch lifecycle、watchdog、native cancel、automatic restart 或 process-failure recovery。

每个 synchronous engine step按现有顺序处理：

1. `start_load_kv()` 先接受完整 snapshot、retire/purge旧 state，再 dispatch本 step
   commands。
2. `get_finished(finished_req_ids)` 后执行。DSA 不再使用 request-ID-only
   `finished_req_ids` retire或删除 state；normal finish retirement只能来自刚接受的
   scheduler snapshot，避免 one-shot 丢失和 request-ID reuse歧义。
3. Snapshot 若要求 retire non-Quiesced state立即 fail closed，不能静默跳过。
4. Cancellation 仍由 typed `QUIESCE` drain worker operation、ordinary
   `finished_recving` all-worker aggregation和scheduler release-once闭环；该 contract不变。

把 `_start_dsa_commands(metadata)` 拆为“接受/校验 snapshot”与 private
single-command dispatch。`_finish_dsa_operation()` 只能继续 dispatch已经在当前 accepted
snapshot下验证过的 pending command，不得构造缺失 snapshot 的 synthetic metadata。

## 4. Public token-0 replay-forward evidence

保留 private transition tests，但用 real `vllm.v1.core.sched.Scheduler` 增加一条 public
contract test；复用现有 `tests/ut/kv_offload/utils.py` 和
`tests/ut/kv_offload/a2/test_remote_prefill_lifecycle.py`，不修改 vLLM core source：

1. 通过 `add_request() -> schedule()` 建立 remote request、Main reservation 和初始
   `RECEIVE_REMOTE` command。
2. 通过 connector worker-output seam 注入 exact-TP transfer results，证明 coverage 完整
   前不进入 replay。
3. 由真实 `update_from_output()` 消费 `PREPARE_REPLAY` 的 exact-TP
   `REPLAY_READY`/`finished_recving`，不手工构造后继 `SchedulerOutput`。
4. 再调用 public `schedule()`，断言 token-0 forward被真实调度、使用 replay 后的新
   Indexer block table且 Main reservation identity不变。
5. 通过 public output update返回 fake runner output，断言后继 `FUSED_D2H` range：
   transfer failure从0重写；preemption continuity成立时只写 preserved Main suffix。

该测试只证明 CPU/mock scheduler/runner contract，不声称执行真实 model/NPU forward、
fused kernel或验证 cache contents。

## 5. Structured replay observation

保留 accepted event字段，不以 storage bytes替换或静默重开 spec/ADR：

```text
blockwise_dsa_replay scope=decode_dp request_id=... reservation_id=...
replay_tokens=... reused_main_tokens=... skipped_d2h_bytes=...
```

- `replay_tokens` 是 transition 时 request从 token 0重算的完整 token 数；
- `reused_main_tokens` 是 continuity proof 后保留、无需再次 D2H 的 request-level Main
  token 数；
- 每个 Decode TP worker 在 SFA registration完成后，使用 fused D2H descriptor实际采用的
  `num_offload_layers`、`token_size_bytes_k` 和 `token_size_bytes_v` 计算 local
  `skipped_d2h_bytes`；不得使用可能包含 C8 padding/scale 的 Main page bytes；
- `REPLAY_READY` typed local result携带该 rank的 nonnegative skipped bytes。Scheduler只在
  exact TP coverage 后求和并写一条 `scope=decode_dp` aggregate event；transfer failure的
  reused/skipped值均为0。

若现有 SFA interface不能稳定取得上述 registration facts，只允许在
`SFAKVOffloadWorker` 增加一个返回 fused D2H bytes-per-token 的 protected helper；不得建立
metrics、observation、layout或data-plane subsystem。Static/CPU mock可以证明字段来源、
TP aggregation和event语义；真实 descriptor执行与NPU bytes evidence仍为
`planned / not run`。

## 6. 不采用的 terminal/observation 方案

- 永久 request-ID set：拒绝 request-ID reuse且内存无界。
- Bounded LRU/TTL：eviction后 stale command可以复活。
- Private interval fence：command-never-emitted reservation形成无界 gaps，bounded proof
  已被推翻。
- 单一 retirement floor：低 ID长生命周期会阻塞 floor；补 gap tombstone后仍可能无界。
- 用 `page_size_bytes / block_size` 估算 `skipped_d2h_bytes`：C8 padding/scale下语义错误。
- 新 lifecycle/fence/metrics subsystem：镜像 scheduler、worker与typed metadata已有 truth。

## 7. Module shape、逐文件预算与停审线

方案不增加 production file或 public connector interface，最终 production shape仍为
`MooncakeConnectorV1 + typed metadata + thin SFA extensions`。

| File | Additional additions | Additional deletions | 计划 |
|---|---:|---:|---|
| `mooncake_connector.py` | 75-105 | 15-30 | async fail-closed、snapshot生成/消费、retirement、single-command dispatch、exact-TP observation，删除 tombstone |
| `mooncake_dsa_metadata.py` | 25-40 | 0-5 | snapshot central validation、local skipped-bytes result contract |
| `sfa_kv_offload_worker.py` | 5-10 | 0 | 仅在需要时暴露 registration-derived fused D2H bytes-per-token helper |
| `test_mooncake_connector.py` | 25-45 | 60-90 | request-ID reuse、snapshot monotonicity、async/terminal ordering；压缩 private replay cases |
| `test_mooncake_dsa_metadata.py` | 20-30 | 15-25 | snapshot/result invariants，替换重复 schema cases |
| `tests/ut/kv_offload/utils.py` | 10-20 | 0 | real Scheduler DSA fixture所需最小参数化 |
| `a2/test_remote_prefill_lifecycle.py` | 75-105 | 0 | public token-0 replay-forward contract |

预计 final production additions约 `1,646-1,696`，focused test additions约
`1,150-1,200`。这是审阅预算，不是 quota目标。新的 stop-and-review thresholds为：

- production additions超过 `1,710`；
- focused test additions超过 `1,200`；
- 需要新增 production module、public connector interface或修改 vLLM core source；
- 需要扩大 positional ABI、reliable cancel、watchdog、automatic restart、async
  multi-batch或process-failure contract。

触发任一条件立即停止并重新提交门禁，不以压缩可读性或删除必要 public tests维持数字。

## 8. 批准后的 TDD 与验证顺序

1. 先增加 failing tests：request-ID reuse、command-never-emitted gap、old snapshot
   resurrection、non-Quiesced retirement、async rejection、public token-0 forward和准确
   Decode-DP skipped-byte aggregation。
2. 在 typed metadata、现有 connector和最多一个 thin SFA helper内实现方案 A。
3. 先跑 AST、`git diff --check` 与可用 formatter/linter，再按 `AGENTS.md` 同步当前
   checkout到 `liangjiahao/vllm-ascend-ut`，显式运行 focused CPU/mock、完整
   `kv_offload`、default V1和affected SFA suites。
4. 分开报告 static、CPU/mock、default V1、multi-node与NPU evidence；真实
   multi-node/NPU/runtime/performance仍为 `planned / not run`。
5. 展示最终 base/head、逐文件 diffstat、预算、commands/results、剩余风险和control repo
   staging allowlist；未经再次批准，不 commit、push、刷新 lock/repo-state/issues或修改
   final feature status。

## 9. 已批准决策

用户于 2026-08-24 批准本统一 closure gate 的方案 A，以及 production `1,710`、
focused tests `1,200` 的新停审线。该批准只授权完成 Stage 3 source/test 收尾；不授权
commit、push、lock/repo-state/issues 更新或 control-repo final update。
