# 使用精确 TP coverage 和跨 step result 累积

状态：已接受

Blockwise DSA worker result 采用 rank-aware、command-scoped aggregation。`KVConnectorWorkerMetadata.aggregate()` 只合并同一个 engine step 内各 worker 报告的事实；Decode connector scheduler 按 `(request_id, execution_epoch, command_seq)` 跨 scheduler step 累积结果。只有当前 command 收到精确的 expected Decode TP rank coverage 后，scheduler 才能执行 request-level lifecycle transition。

## 穿刺代码怎么做

穿刺的每个 Decode worker 只维护 local `done_requests` 和 `failed_requests` set。`get_and_clear_done_requests()` 与 `get_and_clear_failed_requests()` 取出并清空这些 request IDs；结果不包含 execution epoch、command sequence 或 TP rank。

穿刺 Decode connector 的 `get_finished()` 虽然读取 failed set，但最终只返回 `done_recving`。它依赖普通 vLLM 对 request ID 的匿名完成计数，没有可供 scheduler 消费的 receive failure、replay-ready 或 quiesced result。该路径不能检测同一 TP 的重复上报、缺失 TP 被重复结果替代、stale epoch completion 或相同 identity 的冲突内容。

## 普通 MooncakeConnectorV1 和 vLLM 怎么做

普通 `MooncakeConnectorV1` 的每个 worker 通过 `get_finished()` 返回 local `finished_sending`/`finished_recving` request-ID sets。vLLM `KVOutputAggregator` 为每个 request 维护 remaining worker count；每看到一次 request ID 就减一，减到零后产生 aggregated completion。该计数可以跨 engine step 保留，但不记录具体由哪个 TP 报告，也不区分 command 和 result kind。

`kv_connector_worker_meta` 的 `aggregate()` 只在当前 `KVOutputAggregator.aggregate(outputs)` 调用中合并 worker outputs。已有 CPU offload manager 会在 scheduler side 再跨 step 累积 event count；这证明 scheduler-side accumulation 符合现有 connector extension contract，但 Blockwise DSA 需要比匿名 count 更严格的 rank/epoch/command identity。

## Aggregation contract

每个 local result 的 identity 为：

```text
(request_id, execution_epoch, command_seq, tp_rank)
```

每个已下发 command 的 scheduler tracker 至少保存：

```text
CommandResultTracker
  request_id
  execution_epoch
  command_seq
  action
  expected_tp_ranks
  results_by_tp
```

`expected_tp_ranks` 是当前 routed Decode DP replica 内的 worker TP ranks。首版已经要求 Decode PP=1 且 `DCP * PCP == 1`，因此该集合由当前 Decode `tensor_parallel_size` 生成：

```python
expected_tp_ranks = frozenset(range(decode_tp_size))
```

DP rank 不参与同一个 request 的 tensor completion aggregation；其他 Decode DP replica、Prefill ranks 和测试拓扑中的全局 device IDs 都不能加入该集合。实现不能把 `P TP8/DP2 -> D TP2/DP8` 硬编码为 coverage。

## 两阶段合并

第一阶段由 DSA `KVConnectorWorkerMetadata.aggregate()` 完成，只负责合并同一个 engine step 内的 local results：

- identity 和完整 result 内容都相同的重复是幂等的，只保留一份；
- identity 相同但 result kind、failure phase 或其他内容不同，属于 protocol corruption，立即 fail closed；
- `aggregate()` 不推进 Main validity、不释放 reservation、不生成 `finished_recving`，也不下发下一个 command。

第二阶段由 Decode scheduler connector 的 `update_connector_output()` 完成，把当前 step 的 merged facts 合入对应 `CommandResultTracker.results_by_tp`：

- 同一 TP 跨 step 重复上报相同完整 result 时幂等；
- 同一 TP 跨 step 上报冲突 result 时 fail closed；
- 只有 `set(results_by_tp) == expected_tp_ranks` 才满足 completeness；不能使用 `len(results_by_tp) >= decode_tp_size` 或匿名完成计数；
- 缺失任一 TP 时保持 pending，不产生 timeout-based completion。

## Result validation

Scheduler 消费 result 前必须校验 request、epoch、command、rank 和 action/result matrix：

- Active request 的旧 execution epoch、旧 command sequence 或已经完成 command 的相同 late result，不推进 validity、不释放 ownership、不生成 `finished_recving`，只记录 rate-limited warning/metric 后忽略；
- 已完成并释放的 terminal request 收到 late result 时同样忽略，不能重新创建 tracker 或重复 release；
- active request 收到尚未下发的 future epoch/command、非法 TP rank、相同 identity 的冲突内容或不符合 ADR 0020 action/result matrix 的 result 时 fail closed；
- 缺失 result 或 worker operation 不返回时，request、destination 和 Main reservation 继续保持 pending/隔离，沿用 ADR 0016，不增加 aggregation timeout、watchdog 或推测性 completion。

## Completeness 后的 transition

完整 TP coverage 只表示 scheduler 现在拥有足够事实，可以解释当前 command；具体 transition 继续由 ADR 0020 的 action/result matrix 决定：

- `RECEIVE_REMOTE` 的所有 TP 都是 `RECEIVE_COMPLETE`：建立 Indexer/Main validity，并允许产生 `finished_recving`；
- `RECEIVE_REMOTE` 中任一 TP 是 `TRANSFER_FAILED`：即使其他 TP 成功，整个 command 也失败；等待所有 TP terminal coverage 后统一令 `preserved_main_tokens=0`，不产生 `finished_recving`，并向所有 TP 下发新的 `PREPARE_REPLAY` command；
- `FUSED_D2H` 的所有 TP 都是 `D2H_COMPLETE`：推进 confirmed Main valid prefix，不产生 `finished_recving`；
- `PREPARE_REPLAY` 的所有 TP 都是 `REPLAY_READY`：scheduler 先建立 replay state 并把 `num_computed_tokens` 置为 `0`，然后才允许产生 `finished_recving`；
- `QUIESCE` 的所有 TP 都是 `QUIESCED`：scheduler release-once Main reservation，并只在 terminal cleanup path 产生用于释放 delayed NPU blocks 的 `finished_recving`。

收到第一个 `TRANSFER_FAILED` 后不能立即启动 replay。其他 TP 可能仍在对当前 destination 执行 Indexer D2D 或 Main D2RH；只有完整 terminal coverage 才能证明所有 TP 的当前同步 operation 均已返回。某个 TP 永不返回时，request 将无限期 pending，这是 ADR 0016 已接受的首版边界。

## 考虑过的方案

- 精确 TP rank coverage 加 scheduler-side 跨 step accumulation：可以检测重复、缺失、冲突和 stale result，并与现有 epoch/command contract 一致；采用。
- 匿名 count 跨 step accumulation：实现较少，但同一 TP 重复可能替代缺失 TP，无法证明 destination coverage；不采用。
- 直接复用普通 `finished_recving`：无法表达 receive failure、replay-ready、D2H completion 或 quiesced，也无法拒绝 stale epoch；不采用。
- 第一个 TP failure 后立即下发 replay：可能与其他 TP 尚未结束的 destination 写入竞争；在没有可靠 cancel/barrier 的首版中不采用。

## 结果

- `aggregate()` 是事实合并层，request lifecycle transition 只发生在 scheduler connector。
- Completeness 是 exact rank-set equality，不是匿名 count threshold。
- 相同完整 result 重复是幂等的；冲突 result 和 impossible future result fail closed。
- Stale result 只能被观察和忽略，不能恢复旧 ownership 或触发重复 release。
- 任一 initial receive failure 都等待完整 TP terminal coverage，再进入 request-level `PREPARE_REPLAY`。
- 该方案不修改 upstream vLLM core，也不改变普通 `MooncakeConnectorV1` 的 completion path。

## 预计实现影响

在 ADR 0017-0020 的 typed metadata、identity 和 lifecycle result 基础上，本决策预计增加约 120-190 行 production Python、180-300 行 focused unit tests，编码与 CPU/mock UT 约 2.5-4 个工程日，不包含 NPU E2E。该估算与 ADR 0017 的 metadata 总量有部分重叠，不能简单相加。预计涉及：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py`：rank-aware result container、同一步 `aggregate()` 和 duplicate/conflict validation；
- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：per-command tracker、跨 step accumulation、exact coverage、stale/future validation 和 lifecycle transition gating；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`：携带 local TP rank 的 terminal result emission；
- `tests/ut/kv_offload/test_mooncake_connector.py`：跨 step coverage、重复、冲突、stale/future、mixed success/failure 和 completion gating；
- focused SFA worker tests：每个 action 只产生一个 terminal local result，并携带正确 identity。
