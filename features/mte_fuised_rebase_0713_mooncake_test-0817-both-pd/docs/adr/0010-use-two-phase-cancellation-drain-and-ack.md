# Cancellation 使用两阶段 drain-and-ack

状态：已接受

Blockwise DSA PD offload 对已经取得 Main lifetime reservation 的请求采用两阶段 cancellation。Scheduler 收到 cancellation 时只记录 terminal intent，并阻止该请求启动新的 receive、replay 或 D2H；Main reservation 继续归该请求所有。Worker 停止提交新任务，并等待当前 execution epoch 的 Indexer D2D、Main D2RH 或 fused D2H 不再访问该请求的 destination 后，清理 worker state，先通过现有 `DONE_RECVING_MSG` best-effort 通知相应 Prefill source，再通过普通 `finished_recving` 上报本地 quiesced。Scheduler 只会看到 vLLM `KVOutputAggregator` 汇聚后的 request completion，并在 `update_connector_output()` 中幂等归还 Main reservation，随后 vLLM core 释放延迟持有的 NPU blocks。Cancellation 不增加 typed `QUIESCED` result，首版不修改 vLLM core。

## 穿刺代码怎么做

穿刺 scheduler 在 `request_finished_all_groups()` 中立即从 `_request_trackers` 移除请求并把 `allocated_block_ids_cpu` 归还 `CPUBlockManager`，假定请求终态意味着不再存在 inference 或 KV transfer。Worker 却要到后续 `get_finished(finished_req_ids)` 才清理 `_cpu_blocks_by_req`、`request_map`、`_dest_blocks_by_req` 和 `_pending_done`。对于仍在 `WAITING_FOR_REMOTE_KVS`、仍有 Mooncake read 或 fused D2H 的请求，这会形成 scheduler 已把 Main block ID 分配给新请求、旧 worker 仍可能写入同一 Host address 的竞态。穿刺没有 worker-to-scheduler quiesced ack，也没有覆盖该竞态的 cancellation unit test，不能直接沿用。

## 考虑过的方案

- Scheduler 在 `request_finished()` 中立即释放 Main reservation。该方案改动最少，但无法证明异步 receive/D2H 已经停止，存在 use-after-free-style block reuse，首版不采用。
- 两阶段 drain-and-ack。该方案增加 terminal state 和一次 worker ack，但可以复用 vLLM 已有的 `delay_free_blocks`、`finished_recving` 和 `update_connector_output()` 顺序，不修改 core；首版采用。
- 只标记 cancellation，让既有 transfer 自然完成后沿用普通 receive-complete。该方案实现较简单，但取消请求仍消耗全部带宽，卡住的 transfer 会长期占有 Main reservation 和 P source；不作为首版正常策略。

## 状态机

```text
ACTIVE
  |
  | cancellation
  v
CANCEL_PENDING
  - 禁止提交新的 receive/replay/D2H
  - Main reservation 仍归原请求
  - request_finished() 返回 delay_free_blocks=True
  |
  | each worker drains the current execution epoch to return
  v
EACH WORKER QUIESCED (worker-local condition)
  - 不再有任务访问 Indexer/Main destination
  - worker 清理 request maps、destination maps 和 pending state
  - worker 尝试向相应 P source 发送 DONE_RECVING_MSG
  - worker 上报一次普通 finished_recving
  |
  | KVOutputAggregator emits all-worker finished_recving
  | scheduler update_connector_output()
  v
RELEASED
  - scheduler 幂等归还 Main reservation
  - vLLM core 释放 delayed NPU blocks
```

Quiesced 是每个 worker 的本地安全条件，不是 scheduler request status 或 typed result。`CANCEL_PENDING` 后，当前不可取消的 `TransferSync` 必须 drain 到返回，且完成结果不能重新激活请求或触发下一条传输；首版不增加 reliable/native cancel，“调用了 cancel API”本身不等于 Quiesced。

## 结果

- Cancellation 发生在 Main admission 之前时没有 reservation 或 worker epoch，可以立即完成，不需要伪造 quiesced ack；worker 尚未绑定 Prefill endpoint 时不保证主动 source-release notification，由 Prefill hard TTL 兜底。
- Cancellation 发生在 admission 之后时，`request_finished_all_groups()` 将 terminal state 置为 `CANCEL_PENDING` 并返回 `delay_free_blocks=True`，不能立即调用 Main block manager 的 `free()`。
- `WAITING_FOR_REMOTE_KVS` 请求停止启动后续 Indexer/Main phase；已经进入底层同步传输的 phase 必须 drain 到返回，首版不增加 reliable/native cancel。Indexer 成功但 Main 尚未开始时不得再启动 Main。
- `RUNNING` 请求必须先完成或 drain 当前 fused D2H/save barrier；`PREEMPTED` 或 `REPLAY_PENDING` 请求 retire 当前 execution epoch，并释放其仍保留的 Main reservation，但同样只能在 worker quiesced 后执行 release。
- Worker 必须先标记 epoch cancelled，再处理或忽略同一 step 的 completion；cleanup 按 `(request_id, execution_epoch)` 幂等，并在 worker 内保证当前 cancellation 只把 request ID 放入普通 `finished_recving` set 一次。该信号本身不携带 epoch 或 TP rank，旧 epoch 和重复 completion 必须在进入普通 completion channel 前过滤。
- `finished_recving` 在 terminal request 上表示“各 Decode worker 已 quiesced，可以释放 delayed resources”，不表示 receive 成功或请求可以恢复运行。Cancellation 不生成 `DsaLocalResultKind.QUIESCED`，也不进入 ADR 0021 的 typed result aggregation。
- vLLM `KVOutputAggregator` 按 connector 的 expected worker count 汇聚各 worker 的普通 `finished_recving`；只有 aggregated request ID 到达 scheduler 后，connector 才在 core 处理该 completion 前通过 `update_connector_output()` release-once Main reservation。重复 cancellation、重复 worker ack 和 late completion 都必须是 no-op。
- 每个 D worker 达到本地 quiesced 后，必须先对自己实际读取、且尚未完成 source-release notification 的 Prefill leader endpoint 尝试发送一次现有 `DONE_RECVING_MSG`，再暴露本地 `finished_recving`。普通 receive 已成功通知的 endpoint 不因后续 cancellation 重发。P 收到通知后沿用普通 V1 delayed-free tracker 提前释放 source；通知发送或 ACK 失败时继续由现有 Prefill source TTL 兜底，不能因此提前复用尚未 quiesced 的 D Main blocks。
- 如果 worker 无法进入 quiesced，Main reservation 和相关 delayed NPU blocks 保持隔离，不能强制归还给 pool。同步 transfer 的最终失败按 ADR 0012-0014 进入 request-level replay；调用不返回或 drain 无法产生 quiesced ack 时按 ADR 0016 沿用普通 V1，不增加 watchdog 或自动 fail-stop，并允许 ownership 在 live process 中无限期保持隔离。

## 预计实现影响

该决策相对 blockwise DSA connector 公共实现预计增加约 130-230 行 production Python 和 200-330 行 focused unit tests，编码与 CPU/mock UT 约 3-6 个工程日，不包含 NPU E2E、部署和故障注入调优。预计涉及：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：terminal state、`delay_free_blocks`、普通 `finished_recving`、`DONE_RECVING_MSG` ordering、`update_connector_output()` 和 release-once；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/config_data.py`：execution-epoch cancellation command 和 worker-local guard；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`：停止新 D2H、drain 当前任务、清理 state 和一次性普通 completion；
- `vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/read_thread.py`：仅当目标实现复用其 active-read cancel/drain hook 时修改；
- `tests/ut/kv_offload/test_mooncake_connector.py`：各生命周期阶段的 cancellation、Prefill notification ordering、普通 completion 聚合、重复 ack 和 release ordering；
- `tests/ut/kv_offload/test_sfa_pd_cpu_offload_single_rank.py` 或 focused worker test：D2H drain、stale epoch 和 worker cleanup。
