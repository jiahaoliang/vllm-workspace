# Cancellation 使用两阶段 drain-and-ack

状态：已接受

Blockwise DSA PD offload 对已经取得 Main lifetime reservation 的请求采用两阶段 cancellation。Scheduler 收到 cancellation 时只记录 terminal intent，并阻止该请求启动新的 receive、replay 或 D2H；Main reservation 继续归该请求所有。Worker 停止提交新任务，并等待当前 execution epoch 的 Indexer D2D、Main D2RH 或 fused D2H 不再访问该请求的 destination 后，清理 worker state 并通过 `finished_recving` 上报 quiesced。Scheduler 在 `update_connector_output()` 消费该 ack 时幂等归还 Main reservation，随后 vLLM core 释放延迟持有的 NPU blocks。首版不修改 vLLM core。

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
  | worker drains or stops the current execution epoch
  v
QUIESCED
  - 不再有任务访问 Indexer/Main destination
  - worker 清理 request maps、destination maps 和 pending state
  - worker 上报 finished_recving
  |
  | scheduler update_connector_output()
  v
RELEASED
  - scheduler 幂等归还 Main reservation
  - vLLM core 释放 delayed NPU blocks
```

`CANCEL_PENDING -> QUIESCED` 允许当前不可取消的 `TransferSync` drain 完成，但完成结果不能重新激活请求或触发下一条传输。若底层提供可靠 cancel 并能证明 destination 不再被访问，也可以提前进入 `QUIESCED`；“调用了 cancel API”本身不等于 quiesced。

## 结果

- Cancellation 发生在 Main admission 之前时没有 reservation 或 worker epoch，可以立即完成，不需要伪造 quiesced ack。
- Cancellation 发生在 admission 之后时，`request_finished_all_groups()` 将 terminal state 置为 `CANCEL_PENDING` 并返回 `delay_free_blocks=True`，不能立即调用 Main block manager 的 `free()`。
- `WAITING_FOR_REMOTE_KVS` 请求停止启动后续 Indexer/Main phase；已经进入底层同步传输的 phase 必须 drain 或可靠取消。Indexer 成功但 Main 尚未开始时不得再启动 Main。
- `RUNNING` 请求必须先完成或 drain 当前 fused D2H/save barrier；`PREEMPTED` 或 `REPLAY_PENDING` 请求 retire 当前 execution epoch，并释放其仍保留的 Main reservation，但同样只能在 worker quiesced 后执行 release。
- Worker 必须先标记 epoch cancelled，再处理或忽略同一 step 的 completion；cleanup 和 quiesced ack 都按 `(request_id, execution_epoch)` 幂等。旧 epoch completion 不能命中新请求或 resumed epoch。
- `finished_recving` 在 terminal request 上表示“worker 已 quiesced，可以释放 delayed resources”，不表示 receive 成功或请求可以恢复运行。
- Scheduler connector 在 vLLM core 处理 `finished_recving` 之前通过 `update_connector_output()` 释放 Main reservation；release 必须是 release-once，重复 cancellation、重复 worker ack 和 late completion 都是 no-op。
- D worker quiesced 后应向 P 发送 terminal notification，使 P 提前释放 source。通知丢失时继续由现有 Prefill source TTL 兜底，不能因此提前复用 D Main blocks。
- 如果 worker 无法进入 quiesced，Main reservation 和相关 delayed NPU blocks 保持隔离，不能强制归还给 pool。同步 transfer 的最终失败按 ADR 0012-0014 进入 request-level replay；调用不返回或 drain 无法产生 quiesced ack 时按 ADR 0016 沿用普通 V1，不增加 watchdog 或自动 fail-stop，并允许 ownership 在 live process 中无限期保持隔离。

## 预计实现影响

该决策相对 blockwise DSA connector 公共实现预计增加约 160-280 行 production Python 和 220-360 行 focused unit tests，编码与 CPU/mock UT 约 4-7 个工程日，不包含 NPU E2E、部署和故障注入调优。预计涉及：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：terminal state、`delay_free_blocks`、worker quiesced output、`update_connector_output()` 和 release-once；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/config_data.py`：execution-epoch cancellation/terminal metadata；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`：停止新 D2H、drain 当前任务和生成 quiesced ack；
- `vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/read_thread.py`：仅当目标实现复用其 active-read cancel/drain hook 时修改；
- `tests/ut/kv_offload/test_mooncake_connector.py`：各生命周期阶段的 cancellation、重复 ack 和 release ordering；
- `tests/ut/kv_offload/test_sfa_pd_cpu_offload_single_rank.py` 或 focused worker test：D2H drain、stale epoch 和 worker cleanup。
