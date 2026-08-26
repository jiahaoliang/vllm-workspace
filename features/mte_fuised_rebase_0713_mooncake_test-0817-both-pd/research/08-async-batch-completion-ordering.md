# Research: async batch completion 与 executor ordering

## Question

在当前 vLLM `0fc695fc6` 与 vLLM-Ascend replacement `7401ae79c` 中，
`schedule()`、`build_connector_meta()`、worker `execute_model()`、
`wait_for_save()`、worker-output aggregation 与 `update_from_output()` 的实际
顺序是什么？Default `MultiprocExecutor` 能保证哪些 per-step FIFO / all-worker
completion facts，preemption、abort 与 normal finish 可以在哪些未回收 batch
边界发生，哪些 executor 或 runtime 语义仍未验证？

## Checkout identities

本次 research 在 2026-08-26 对以下 live checkout 做只读源码审计：

| Repository | Path | Branch | Commit | Dirty |
| --- | --- | --- | --- | --- |
| vLLM | `repos/vllm` | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` | `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` | false |
| vLLM-Ascend replacement | `repos/vllm-ascend-blockwise-dsa-reimplementation` | `feature/blockwise-dsa-mooncake-v1-reimplementation` | `7401ae79c11d6ec0033ea3ac39085379a0bb81ef` | false |

没有运行 unit test、integration test 或 NPU runtime。本文件中的
`Confirmed` 只表示当前 checkout 的源码控制流或已有 upstream test 明确支持该
结论；不等于 NPU runtime 已验证。

## Conclusion

Default `MultiprocExecutor` 保证 scheduler command、单个 worker 的 RPC 执行和
EngineCore 对 batch output 的消费保持 FIFO。它不保证 scheduler 在发出 step
`N+1` 前已经消费 step `N` 的 completion。Decode PP=1 且启用
`async_scheduling` 时，batch queue 深度为 2，因此同一 request 的 `N+1` 可以在
`N` 尚未 `update_from_output()` 时被 schedule。

Blockwise DSA 当前把 `FUSED_D2H` completion 放在 worker output 中返回。
worker 会在该 step 的 `wait_for_save()` 完成后产生本地 `D2H_COMPLETE`，但
scheduler 只有在对应 batch 被 EngineCore 从队列取出、聚合所有 worker output，
并进入 `update_from_output()` 后才能看到 exact-TP completion。物理 worker 顺序
与 scheduler 可见 completion 因此是两个不同事实。

## Confirmed facts

### 1. Scheduler 与 batch queue 的实际顺序

单个非 queue step 是 `schedule -> execute_model -> future.result ->
update_from_output`。启用 batch queue 后，EngineCore 优先填充 queue：当 queue
未满时，它调用 `schedule()` 和 non-blocking `execute_model()`，将 future 与
`SchedulerOutput` 入队；只要仍有容量便直接返回，不等待该 future。queue 满或无
新 batch 可排时，EngineCore 才从另一端 `pop()` 最老 batch，等待其 future，处理
abort queue，然后调用 `update_from_output()`。

Source:

- [`EngineCore` 选择 batch-queue step function](../../../repos/vllm/vllm/v1/engine/core.py#L188-L220)
- [`step_with_batch_queue()` 的 schedule、入队、FIFO pop 与 update](../../../repos/vllm/vllm/v1/engine/core.py#L484-L598)
- [async scheduling 的 concurrent batch 数；PP=1 时为 2](../../../repos/vllm/vllm/config/vllm.py#L496-L507)

`Scheduler.schedule()` 先构造 `SchedulerOutput`，然后调用
`connector.build_connector_meta(scheduler_output)`，再调用
`_update_after_schedule()`。基础 scheduler 在 `_update_after_schedule()` 中乐观
推进 `request.num_computed_tokens`，源码明确说明这是为了允许下一次 scheduling
step 立即继续排同一 prefill request。`AsyncScheduler` 随后为 decode output 和
spec tokens 增加 placeholders，使 request 在旧 output 未回收时仍可继续 schedule。

Source:

- [`SchedulerOutput -> build_connector_meta -> _update_after_schedule`](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L932-L967)
- [基础 `_update_after_schedule()` 的乐观推进和 async-race 注释](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L997-L1027)
- [`AsyncScheduler` 增加 output/spec placeholders](../../../repos/vllm/vllm/v1/core/sched/async_scheduler.py#L19-L41)

因此 PP=1 的典型 async 时间线是：

```text
schedule N -> execute N -> queue N
schedule N+1 -> execute N+1 -> queue N+1
pop/update N
schedule N+2 -> execute N+2 -> queue N+2
pop/update N+1
```

这里的 `execute` 表示 EngineCore 已向 executor 发出 RPC；它不表示 scheduler
已经消费该 step 的结果。

### 2. Default MultiprocExecutor 保证的 FIFO 边界

`MultiprocExecutor.execute_model()` 通过 `collective_rpc()` 把 RPC 放入同一个
broadcast message queue。每个 `WorkerProc` 在单一 busy loop 中逐条 dequeue 并
调用对应 worker method，所以同一 worker 看到的 `execute_model` / `sample_tokens`
RPC 顺序与 enqueue 顺序一致。

Engine 侧的 `FutureWrapper` 也维护 FIFO：每个 future 用 `appendleft()` 入队；读取
某个 future 时会先从另一端 `pop()` 并 drain 排在它前面的 future。EngineCore
自己的 batch queue 使用相同的 `appendleft()` / `pop()` 模式。因此在 default
multiproc path 上，scheduler 不会先用 step `N+1` 的 output 更新状态、再用 step
`N` 的 output 更新状态。

Source:

- [`execute_model()` 使用带 KV aggregator 的 collective RPC](../../../repos/vllm/vllm/v1/executor/multiproc_executor.py#L307-L317)
- [`collective_rpc()` enqueue、response collection 与 FutureWrapper 创建](../../../repos/vllm/vllm/v1/executor/multiproc_executor.py#L340-L404)
- [`FutureWrapper` 按创建顺序 drain response](../../../repos/vllm/vllm/v1/executor/multiproc_executor.py#L70-L101)
- [`WorkerProc.worker_busy_loop()` 串行 dequeue 和执行 RPC](../../../repos/vllm/vllm/v1/executor/multiproc_executor.py#L969-L995)

这个 FIFO 保证不等于资源生命周期 barrier。后续 `schedule()` 可以在旧 batch 的
`update_from_output()` 前分配或释放 KV blocks、preempt request，EngineCore 也会
在旧 batch 的 output 处理前接受 abort。

### 3. All-worker aggregation 能证明什么

当 `collective_rpc()` 收到 `kv_output_aggregator` 时，它不会只等待
`unique_reply_rank`，而是从全部 `response_mqs` 取回该 RPC 的 response，再调用
aggregator。`KVOutputAggregator` 遍历全部 `ModelRunnerOutput`，聚合
`finished_sending`、`finished_recving` 和 `kv_connector_worker_meta`，最后只用指定
output rank 的普通 model output 作为承载对象。

`DsaWorkerResultMetadata.aggregate()` 按
`(request_id, execution_epoch, command_seq, tp_rank)` 合并并去重本地结果。scheduler
侧还会等待 `terminal_results` 的 rank key 集合与当前 Decode TP rank 集合完全相等，
然后才接受 `FUSED_D2H` 的 exact-TP outcome。

Source:

- [all-response collection 与 KV aggregation](../../../repos/vllm/vllm/v1/executor/multiproc_executor.py#L361-L404)
- [`KVOutputAggregator` 聚合全部 worker connector output](../../../repos/vllm/vllm/distributed/kv_transfer/kv_connector/utils.py#L50-L170)
- [`DsaWorkerResultMetadata` 的 rank-aware merge](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py#L313-L340)
- [scheduler 建立 expected TP rank set](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1735-L1739)
- [exact-TP coverage 后才接受 `D2H_COMPLETE`](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1979-L1989)

这里的 all-worker completion 只证明该 RPC 的 worker response 已齐，并不自动证明
所有 connector background operation 都结束。例如 `RECEIVE_REMOTE` 仍可在后台
继续，并通过后续 `finished_recving` 报告。对当前 `FUSED_D2H`，另有更强的本地
事实：worker 只有在 SFA save drain 后才生成 `D2H_COMPLETE`。

### 4. `FUSED_D2H` 从 step metadata 到 scheduler ACK 的路径

DSA scheduler 在该 step 的 `build_connector_meta()` 中先处理 preemption，再根据
`SchedulerOutput` 计算 D2H range。只有 tracker 的 `active_action is None` 时才会
创建新的 `FUSED_D2H`；创建后立即把 tracker 置为 active 并标记 command emitted。
因此 scheduler 尚未消费前一个 ACK 时，下一 step 会跳过新的 D2H command。

Source:

- [DSA `build_connector_meta()` 和 `_queue_scheduled_d2h()`](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1830-L1925)

worker 收到 `FUSED_D2H` 后，把它登记为 in-flight，转换成
`SFAKVOffloadConnectorMetadata`，并调用 `sfa_worker.start_load_kv()`。worker 的
`wait_for_save()` 会等待 SFA pending layer save events；只有 drain 完成后才结束
in-flight operation 并产生该 TP rank 的 `D2H_COMPLETE`。随后
`build_connector_worker_meta()` 把本 step 累积的 DSA results 放入 worker output。

Source:

- [`FUSED_D2H` in-flight 检查与 SFA metadata 构造](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L4320-L4455)
- [SFA `wait_for_save()` 等待实际 HBM-to-CPU copy 落地](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py#L1836-L1854)
- [DSA `wait_for_save()` 产生本地 `D2H_COMPLETE`](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2855-L2877)
- [worker result queue 与 `build_connector_worker_meta()`](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L4527-L4557)

vLLM model-runner connector lifecycle 在 forward 前 bind metadata 并启动 load，在
finally/post-forward 阶段执行 `wait_for_save()`、读取 finished state、构造 worker
metadata，再清理本 step metadata。这使 `D2H_COMPLETE` 成为对应 worker step 的
output fact。

Source:

- [connector bind、start、wait、result collection 与 clear](../../../repos/vllm/vllm/v1/worker/kv_connector_model_runner_mixin.py#L74-L112)
- [Mooncake DSA worker adapter 的 start、worker metadata 与 wait](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2230-L2258)

scheduler 直到 `update_from_output()` 的末段才调用
`_update_from_kv_xfer_finished()`，后者再调用 scheduler-side
`connector.update_connector_output()`。因此即使 worker 已经物理完成 step `N` 的
D2H，只要 `N` 的 output 仍在 EngineCore batch queue 中，scheduler tracker 的
`active_action` 和 `confirmed_main_tokens` 就尚未更新。

Source:

- [`update_from_output()` 读取 connector output](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L1329-L1341)
- [request output 处理后才更新 KV connector state](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L1574-L1597)
- [`_update_from_kv_xfer_finished()` 调用 connector](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L2221-L2248)
- [exact-TP D2H ACK 推进 `confirmed_main_tokens`](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1979-L1989)

### 5. Preemption 可以越过未回收 batch

基础 scheduler 的源码明确承认 concurrent `schedule()` 可以在旧
`update_from_output()` 前 preempt request 并 free blocks。已有 upstream unit test
也构造了该顺序：先 schedule request 2，在其 output 尚未 update 时通过后续
schedule preempt request 2，最后再消费 request 2 的旧 output。

Source:

- [async scheduling race 的源码注释](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L1021-L1027)
- [preempt 会 free KV、清 computed state 并移回 waiting](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L974-L995)
- [`test_preempt_during_execution`](../../../repos/vllm/tests/v1/core/test_scheduler.py#L687-L743)

DSA scheduler 在随后构造 metadata 时读取 `preempted_req_ids`，递增 execution
epoch、清 active action、进入 awaiting-rebind。旧 identity 的 late result 在
`update_connector_output()` 中按 stale result 忽略。

Source:

- [DSA `_mark_preempted()`](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1879-L1893)
- [stale/future DSA result 处理](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L1950-L1966)

### 6. Abort 可以越过未回收 batch

EngineCore 在等待到最老 batch output 后、调用 `update_from_output()` 前先 drain
abort queue。`update_from_output()` 本身也明确允许 request 在 model execution
期间被 abort，并在看到已 finished request 时跳过 token update。Async scheduler
unit test 先连续创建两个 `SchedulerOutput`，再在逐个 output update 前 abort
request，直接证明 abort 与 queued output 可以交错。

Source:

- [batch output 与 `update_from_output()` 之间处理 abort](../../../repos/vllm/vllm/v1/engine/core.py#L554-L572)
- [`update_from_output()` 允许 execution 期间 abort](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L1393-L1407)
- [async scheduler abort test](../../../repos/vllm/tests/v1/core/test_async_scheduler.py#L67-L100)

DSA abort path 不立即释放 Main reservation。`request_finished()` 将 tracker 置为
`cancel_pending`，发出 `QUIESCE` 并返回 delayed-free；worker 只在当前 in-flight
operation 已结束时完成 quiescence 和报告 `finished_recving`。

Source:

- [DSA abort 转为 `QUIESCE` 并延迟 free](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2036-L2053)
- [worker quiescence 等待 in-flight 清空](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L4486-L4525)

### 7. Normal finish 可以发生在更新旧 batch 时，而更新后的 step 已在队列中

因为 EngineCore 在消费 `N` 前可以先排 `N+1`，`N` 的 token output 可能在
`update_from_output(N)` 中触发 stop/EOS，而 `N+1` 已经 queued。基础 scheduler
会在 request stop 时调用 `_free_request()`；该函数先调用 connector
`request_finished()`，然后才在 `update_from_output()` 末段处理本 batch 的
connector output。

当前 DSA 只对 `FINISHED_ABORTED` 走 `QUIESCE`。其他 normal-finish status 会立即
删除 scheduler tracker 并释放 Swapped Main reservation。该控制流组合是源码可
确认的 async ownership hazard；本次没有用 NPU runtime 重现 reservation 被复用
时的具体 interleaving。

Source:

- [stop 后调用 `_free_request()`](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L1519-L1531)
- [`_free_request()` 先调用 connector request-finished hook](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L1888-L1905)
- [normal finish 立即删除 DSA tracker 并释放 Main blocks](../../../repos/vllm-ascend-blockwise-dsa-reimplementation/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2036-L2057)

## Unverified boundary

- **NPU runtime 未验证。** 没有运行真实 Ascend forward、HCCL/TP aggregation、
  SFA D2H、stream/event 或 host-buffer reuse 测试。源码中的 event wait 是 primary
  source，但本次没有设备侧 trace 或数据正确性证据。
- **非 default executor 未验证。** 本次 FIFO 与 all-worker response 结论只直接
  审计了 `MultiprocExecutor`。Ray、external launcher 和其他 executor backend 的
  task ordering/response semantics 没有审计。
- **Balance scheduling runtime 未验证。** replacement 含条件启用的 Ascend
  `BalanceScheduler` patch；issue 的实际 runtime 是否启用该配置没有 live 证据。
  其 copied schedule path 保留 `build_connector_meta -> _update_after_schedule`
  顺序，但本次没有完整审计其所有 request-selection 与 DP collective 分支。
- **Model runner 组合未穷举。** V1/V2、spec decode、structured output deferred
  sampling、ACL graph capture 与 eager execution 的全部组合没有逐一验证。
- **Background operation 的全局完成语义未验证。** all-worker RPC response 只
  表示该 step 的 worker response 已齐；除当前由 `wait_for_save()` 明确 drain 的
  fused D2H 外，不能把它泛化为所有 connector background transfer 都完成。
- **DSA async integration 尚不存在。** 当前 constructor 会拒绝 Decode
  `dsa_pd_offload=true` 与 `async_scheduling=true`，因此没有现成 runtime path 能
  直接验证 queued D2H、preemption、abort、normal finish 与 late result 的组合。

## Research answer

可以依赖的最窄事实是：default multiproc worker 与 EngineCore 都按 step FIFO
执行/消费；对应 step 的 `FUSED_D2H` 在 worker 生成 `D2H_COMPLETE` 前已经完成
本地 SFA save drain；all-worker aggregation 在 scheduler 消费该 step output 前
收集所有 worker response。不能依赖的事实是“scheduler 在排下一 step 前已看到
上一 step completion”或“未回收 batch 期间不会发生 preemption、abort、stop 与
reservation lifecycle 变化”。
