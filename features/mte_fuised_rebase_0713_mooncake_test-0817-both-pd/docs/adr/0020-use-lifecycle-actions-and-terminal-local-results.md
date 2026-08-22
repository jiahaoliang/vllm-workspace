# 使用 lifecycle action 和 terminal local result

状态：已接受

Blockwise DSA 的 Decode scheduler-to-worker command 使用 lifecycle-oriented `DsaAction`；Decode worker-to-scheduler metadata 对 receive、fused D2H 和 replay 使用 command-terminal `DsaLocalResultKind`，并只在初始 remote receive failure 时使用独立 `DsaTransferPhase` 标明失败发生在 Indexer D2D 还是 Main D2RH。`QUIESCE` 是例外：worker 达到 Quiesced 后复用普通 `finished_recving`，不增加 typed `QUIESCED` result。

不把 Indexer 和 Main 拆成两个 scheduler actions。一个 `RECEIVE_REMOTE` command 在每个 Decode TP worker 内先执行 local Indexer D2D，成功后才执行 local Main D2RH；Indexer success 只是 worker-local phase gate，不单独向 scheduler 报告 completion。

```python
class DsaAction(Enum):
    RECEIVE_REMOTE = auto()
    FUSED_D2H = auto()
    PREPARE_REPLAY = auto()
    QUIESCE = auto()


class DsaLocalResultKind(Enum):
    RECEIVE_COMPLETE = auto()
    D2H_COMPLETE = auto()
    REPLAY_READY = auto()
    TRANSFER_FAILED = auto()


class DsaTransferPhase(Enum):
    INDEXER_D2D = auto()
    MAIN_D2RH = auto()
```

## 穿刺代码怎么做

穿刺 worker 内部先调用 Indexer D2D，再调用 Main D2RH，但 Indexer transfer 返回负值时只把 request 加入 `failed_reqs`，仍继续执行 Main 和后续 layer。最后一层只产生一个 bool success/failure callback，没有 local phase result、execution epoch、command sequence 或 TP rank。

Decode worker 的 `get_finished()` 虽然从接收线程取出 done/failed sets，但只把 done request 放入 `finished_recving`；failed request 被清理 local maps 后没有 scheduler 可消费的 replay 或 terminal failure transition。目标实现不能沿用这条 failure path。Cancellation 则有意复用 ordinary completion，但只允许在 worker 已证明 Quiesced、过滤 stale epoch 并清理 local state 后上报。

穿刺的 fused D2H 也不是 per-request worker result。`save_current_kv_tokens()` 在 local owner 捕获异常后通过 TP collective 传播 status，然后抛 `RuntimeError`；它不会把失败转换成 request-level connector completion。

## 普通 MooncakeConnectorV1 怎么做

普通 V1 worker 只通过 `get_finished()` 返回 `finished_sending` 和 `finished_recving` request-ID sets，load failure 通过 `invalid_block_ids` 表达。它不生成 `KVConnectorWorkerMetadata`，也不区分 receive-complete、replay-ready 和 cancellation reason。

vLLM core 在处理 `finished_recving` 前先调用 connector `update_connector_output()`。Receive 和 replay 路径利用这个顺序先消费 typed DSA local results、完成 request lifecycle transition，再允许 core 使用普通 completion。Cancellation 路径直接复用 vLLM 对 ordinary `finished_recving` 的 expected-worker-count aggregation；scheduler 已持有 terminal request state，因此不需要再通过 typed result 传递 terminal reason。不修改 upstream core。

## 考虑过的方案

- Phase-oriented actions：分别下发 `PULL_INDEXER`、`PULL_MAIN`、`FUSED_D2H`、retire 和 cancel。它使底层 transfer phase 显式，但 Indexer/Main 之间需要额外 scheduler round，扩大跨 TP 中间状态，并削弱已经接受的 worker-local hard gate；不采用。
- Lifecycle-oriented actions 和 command-terminal results。Scheduler 只下发具有 request lifecycle 含义的 command，worker 内部完成 phase ordering，并向 scheduler 报告可用于状态转换的 terminal local result；采用。
- 为 cancellation 增加 typed `QUIESCED` result。它能携带 epoch、sequence 和 TP rank，但 cancellation 已有 terminal scheduler state，且普通 `finished_recving` 已提供 all-worker aggregation和 delayed-block release hook；额外 result 会形成两条必须保持一致的 ack channel，不采用。
- Cancellation 复用普通 `finished_recving`。Worker 负责在进入 request-ID completion set 前完成 epoch/duplicate guard 和 local cleanup；实现较小，并复用现有 core path；采用。
- Generic `EXECUTE/SUCCESS/FAILED`。它代码较少，但 scheduler 必须根据可变 local state 猜测 success/failure 含义，无法可靠拒绝 stale completion；不采用。

## Action 语义

`RECEIVE_REMOTE` 绑定 ADR 0019 的 source/destination，执行完整初始 receive command：

```text
Indexer D2D
  success -> Main D2RH
  failure -> stop, do not start Main

Main D2RH
  success -> RECEIVE_COMPLETE
  failure -> TRANSFER_FAILED(MAIN_D2RH)
```

Indexer failure 直接产生 `TRANSFER_FAILED(INDEXER_D2D)`。一个 worker 不产生 `INDEXER_COMPLETE` 或 `MAIN_COMPLETE` 中间 result。

`FUSED_D2H` 只把当前 Decode step 新生成的 Main KV 写到 current bound Host prefix。成功 result 是 `D2H_COMPLETE`，它用于推进 confirmed Main valid prefix，不是 remote receive completion，也不进入 `finished_recving`。

`PREPARE_REPLAY` 是非终态恢复 command。它 drain/retire 旧 worker operation、应用新的或当前 execution epoch、清除 stale binding，并按 command 中的 `preserved_main_tokens` 准备 Decode local full-sequence compute replay。成功 result `REPLAY_READY` 只表示可以开始模型 replay，不表示 replay forward 已经执行或 external KV 有效。

Transfer-failure replay 的 `PREPARE_REPLAY` 必须令所有 TP 的 preserved Main validity 为 `0`。Preemption replay 可以按 ADR 0009 保留可证明的 Main prefix。

`QUIESCE` 是 terminal cleanup command，用于 cancellation 和其他 terminal request cleanup。Worker 禁止新 receive/replay/D2H，drain 当前 operation，清理 request/epoch binding，先对自己使用过且尚未通知完成的 Prefill leader source 尝试一次现有 `DONE_RECVING_MSG`，再把 request ID 放入普通 `finished_recving` set。普通 receive 已通知的 source 不重复发送。它不产生 `DsaLocalResultKind`，不释放 scheduler-owned Main reservation，也不传递 terminal 原因。

不增加 `QUIESCED`、`CANCELLED`、`PREEMPTED` 或 `NORMAL_FINISH` local result；这些 terminal facts 已由 scheduler request state和 worker-local Quiesced guard表达。`PREPARE_REPLAY` 与 `QUIESCE` action 已经表达 worker 需要知道的非终态/终态区别。

## Action/result matrix

| `DsaAction` | 成功 result | 可恢复 failure result | `finished_recving` |
| --- | --- | --- | --- |
| `RECEIVE_REMOTE` | `RECEIVE_COMPLETE` | `TRANSFER_FAILED(INDEXER_D2D)` 或 `TRANSFER_FAILED(MAIN_D2RH)` | 仅所有 TP receive-complete 后 |
| `FUSED_D2H` | `D2H_COMPLETE` | 首版无 request-level failure result | 从不 |
| `PREPARE_REPLAY` | `REPLAY_READY` | 无法安全完成时不产生 result | 仅所有 TP replay-ready 且 scheduler 已建立 replay state 后 |
| `QUIESCE` | 无 typed result；worker-local Quiesced | 无法 quiesce 时不产生 completion | 每个 worker 仅在 Quiesced 后上报一次普通 completion |

每个 typed result identity 至少包含 `(request_id, execution_epoch, command_seq, tp_rank)`。相同 identity 的相同 result 幂等；冲突 kind/phase fail closed。跨 TP completeness、跨 step accumulation 和 duplicate merge 按 [ADR 0021](0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md) 使用 exact Decode TP rank coverage：worker metadata 合并同一步 facts，scheduler connector 跨 step 累积。`QUIESCE` 不进入该 typed aggregation；它依赖 worker 内部按 `(request_id, execution_epoch)` 的一次性 guard 和 vLLM 普通 completion aggregation。

## Scheduler 消费规则

- 所有预期 TP 都是 `RECEIVE_COMPLETE` 时，scheduler 建立 Indexer/Main validity，再允许普通 `finished_recving` 解除 `WAITING_FOR_REMOTE_KVS`。
- 任一 TP 是 `TRANSFER_FAILED` 时，本 command 不能产生 `finished_recving`。Scheduler 等待当前 command 的完整 TP terminal coverage，再向所有 TP 下发 `PREPARE_REPLAY`；按 ADR 0013 统一令 `preserved_main_tokens=0`。
- 所有预期 TP 都是 `REPLAY_READY` 时，scheduler 先把 request 置为 replay state、确保 `num_computed_tokens=0`，再产生普通 `finished_recving` 让 request 进入 Decode local replay。
- 所有预期 TP 都是 `D2H_COMPLETE` 时，scheduler 推进 confirmed Main valid prefix，不产生 `finished_recving`。
- Cancellation 中每个 Decode worker 只在本地 Quiesced 后上报一次 ordinary `finished_recving`。vLLM `KVOutputAggregator` 达到 expected worker count 后，scheduler connector 只在 request 已 terminal 且仍持有 reservation 时 release-once Main reservation；随后 core 释放 delayed NPU blocks。
- Stale epoch/command result 不推进 validity，不释放 ownership，也不生成 `finished_recving`。

上述 typed result 的“所有预期 TP”是当前 routed Decode DP replica 的 `set(range(D_TP))`。缺失 result 保持 pending，相同完整 result 重复时幂等，冲突或 impossible future result fail closed；具体规则见 ADR 0021。Cancellation 的 ordinary completion 例外由 ADR 0010 和 ADR 0021 的边界说明约束。

## Fused D2H failure 边界

当前 fused D2H 在 model execution 中运行，请求状态通常是 `RUNNING`。vLLM 的普通 `finished_recving` 只能安全处理 `WAITING_FOR_REMOTE_KVS` 或已经 terminal 的 request；对 running request 发送该 completion 会触发 core 状态断言。现有 connector interface 也没有一个无需修改 upstream core、即可让单个 running request 转入 preemption/replay 的 worker failure channel。

因此首版明确：

- `FUSED_D2H` 成功时产生 `D2H_COMPLETE`；
- fused D2H 同步调用或 TP status check 失败时继续沿用当前 SFA worker 的 fail-fast `RuntimeError`；
- 不产生虚假的 `TRANSFER_FAILED`、`D2H_COMPLETE` 或 `finished_recving`；
- 不直接篡改 vLLM core scheduler private state 来伪造 request-local replay；
- running request 的 fused D2H failure recovery 是后续能力，需要合法的 request failure/preemption channel，首版不实现。

该限制不改变 ADR 0012：初始 Indexer D2D 或 Main D2RH 的最终 failure 仍走 request-level full-sequence replay。Fused D2H 调用不返回或 drain 无法 quiesce 时继续适用 ADR 0016，不增加 watchdog。

## 结果

- Indexer/Main ordering 留在 worker 内，不增加 scheduler round 或跨 TP phase barrier。
- Local result 表达 scheduler 可消费的 lifecycle outcome，而不是底层 API 每次调用的流水账。
- `finished_recving` 继续作为 upstream core transition hook。Receive/replay 必须先由 connector 解释 typed result；cancellation 则直接复用 ordinary completion，并由 terminal request state与 worker-local Quiesced guard限定语义。
- `TRANSFER_FAILED` 必须携带 `DsaTransferPhase`；其他 result kind 不携带 failure phase。
- Cancellation 不增加 typed `QUIESCED`；Prefill 提前释放复用独立的 `DONE_RECVING_MSG` source-release notification，通知失败由 hard TTL 兜底。
- Fused D2H success 纳入 command/result identity 和 Main validity tracking；其 failure 首版是显式 fail-fast boundary，不错误宣称 request-local recovery。

## 预计实现影响

在 ADR 0017-0019 的 typed metadata 基础上，本方案预计增加约 100-170 行 production Python、180-300 行 focused unit tests，编码与 CPU/mock UT 约 3-5 个工程日，不包含 NPU E2E。预计涉及：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py`：action/result/phase enums 和合法组合校验；
- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：command dispatch、typed result interpretation、replay transition、cancellation ordinary completion 和 Prefill notification ordering；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`：`FUSED_D2H` completion、replay prepare、worker-local quiesce 和 stale command rejection；
- `vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/worker.py`：仅在复用 receive/drain adapter 时增加 typed receive result；
- connector 和 focused worker tests：action/result matrix、Indexer hard gate、D2H validity、replay-ready、ordinary cancellation ack、Prefill notification、stale identity 和 fused D2H fail-fast。
