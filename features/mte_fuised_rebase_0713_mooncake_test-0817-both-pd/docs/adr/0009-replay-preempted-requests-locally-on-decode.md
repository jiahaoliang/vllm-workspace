# Preemption 后 full compute replay 并复用 Main

状态：已接受；async validity cut与replay barrier部分被ADR 0024、0026取代

后续关系：Decode token-0 full compute replay、Indexer rebuild和Main reservation跨epoch保留继续有效；preserved Main不再由single-active D2H completion推导，而以preemption cut时已消费的confirmed Main watermark为准。Old-epoch late progress与new-epoch `PREPARE_REPLAY` barrier按ADR 0024、0026处理。

Blockwise DSA PD offload 首版沿用 vLLM 的 preemption-recompute 控制流，但区分 compute replay 与 cache rebuild。一个已经从 Prefill 接收 KV、并在 Decode 运行的请求被 preempt 后，不再次从 Prefill 拉取旧 KV；请求恢复时由 Decode 从 token 0 本地执行 full-sequence forward replay，以重建新 HBM ownership 下的 Indexer cache。Main lifetime reservation 及 preemption 前已经确认落入 Host 的 Main KV 保持有效，replay 不重复 D2H 这段 preserved Main prefix。这里的 replay 是异常恢复路径，不是正常请求新增一个 Decode-side Prefill stage。

## 穿刺代码怎么做

穿刺代码没有完整闭环 preemption。vLLM core 会释放请求的 NPU blocks、把 `num_computed_tokens` 重置为 `0` 并重新入队；恢复时 core 会为 group 0 分配新的 Indexer HBM blocks，正常 forward 也会用新的 block table 重建 Indexer。但是 `SFAPDCpuOffloadScheduler` 没有清除或重新绑定 tracker 中第一次 pull 使用的 Indexer IDs，只从 resumed metadata 取 Main group；worker 也继续保留旧 Indexer destination map。与此同时，穿刺以 `offload_token_start=0` 为 replay token 再次生成 Main D2H，覆盖原 Host Main，而不是有意复用 preserved Main。因此穿刺同时存在 stale Indexer ownership 和重复 Main D2H，不能作为正确实现直接沿用。

## 考虑过的方案

- 严格全量重建：沿用 vLLM 默认的 Decode full-sequence replay，并重新写入 Indexer 和 Main。该方案最接近穿刺的计算路径，但浪费仍由原 reservation 持有的有效 Main，并重复产生完整 Main D2H；首版不采用。
- Full compute replay、Indexer rebuild、preserved Main reuse。该方案不修改 vLLM core，也不要求 Prefill 在首次传输完成后继续持有 source KV；它仍承担 full forward replay 的计算成本，但避免重复 Main D2H，首版采用。
- Preemption 后立即终止单个请求。当前 connector interface 没有一个无需修改 vLLM core、且能可靠终止该请求而不扩大为 engine failure 的返回值；首版不采用。
- Preemption 后重新从 Prefill 拉取。保留 Main 时可以先只重拉 Indexer；如果 Main validity 或 ownership 也无法保留，则重拉 Indexer 和 Main。该方案可以避免 Decode full forward replay，但需要重新设计 source KV 的 request-lifetime ownership、再次 rendezvous、TTL 或 lease、transfer generation 与幂等 cleanup；首版不采用，作为后续性能优化记录。
- 在 Decode 保留旧 Indexer HBM ownership 并直接恢复。Indexer blocks 由 vLLM core 在 preemption 时释放，阻止释放会削弱 preemption 释放 HBM 的目的并要求修改 core；首版不采用。

## 结果

- Preemption 后不能把第一次 pull 使用的旧 Indexer IDs 当作有效 destination。首次 P-to-D receive-complete 不会再次触发远端 pull，但 Main reservation 和已确认落入 Host 的 Main coverage 可以继续有效。
- 恢复请求不重新触发 `do_remote_prefill`，而是沿用 vLLM 的 resumed-request scheduling，从 token 0 replay 当前保留的完整 token sequence。
- Tracker 拆分为跨 preemption 保留的 `MainReservationState` 和每次运行重新建立的 `ExecutionEpochState`。前者至少持有 Main CPU block IDs、reservation capacity 和 `preserved_main_tokens`；后者持有 epoch、当前 Indexer IDs、临时 Main HBM IDs 及 transfer/worker state。
- Preemption 不是 Main reservation 的释放点。Scheduler 保留 Main block ownership，并在上一执行步 D2H 已完成、block mapping 未改变且有效边界一致时保留 Main validity。Worker 幂等 retire 旧 execution epoch，清除旧 Indexer IDs、temporary HBM IDs、destination maps 和 pending completion state。
- Resume 从 `scheduled_cached_reqs.new_block_ids[group 0]` 取得 core 新分配的 Indexer IDs，建立新 execution epoch。Full forward replay 为所有 layer 重建整个有效 token 范围的 Indexer，但对 `[0, preserved_main_tokens)` 不重复 Main D2H；replay 超过该边界后恢复正常 `fused_overlap` Main D2H。
- 如果无法证明 Main D2H 已完成、reservation ownership 连续、layout 未变化或 `preserved_main_tokens` 与 request 状态一致，则不能静默复用旧 Main；该请求将 preserved boundary 降为 `0`，在同一次 full replay 中保守地重写 Main。
- 上述 preserved-prefix 规则只适用于能够证明 validity 的 preemption recovery。Transfer failure 按 ADR 0013 在任一 TP 的同步 transfer 最终失败后统一令所有 TP 的 `preserved_main_tokens=0`，不复用局部成功的 Main。
- Metadata 中的 execution epoch 用于拒绝旧 epoch 的 late completion 或 stale worker state，不能让同一 request ID 的新 Indexer allocation 被旧消息命中。
- 该行为不改变正常路径：没有发生 preemption 的 remote-prefilled request 仍只执行 P-to-D Indexer D2D、Main D2RH 和后续 Decode。

## 预计实现影响

该决策相对 blockwise DSA connector 公共实现预计增加约 200-340 行 production Python 和 280-450 行 focused unit tests，预计涉及 5-6 个文件，编码与 CPU/mock UT 约 5-8 个工程日，不包含 NPU E2E、部署和性能调优。主要文件为：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：Main reservation、execution epoch、resumed group 0 rebind 和 metadata cleanup；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/config_data.py`：持久 reservation 与 per-run execution metadata；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`：preserved Main range 的 D2H suppression 和 stale epoch rejection；
- `vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py`：仅当 lifecycle hook 放入可复用 SFA 基类时修改，否则逻辑留在 Mooncake blockwise 子类；
- `tests/ut/kv_offload/test_mooncake_connector.py`：preempt/resume、Indexer rebind、epoch 和 fallback；
- `tests/ut/kv_offload/test_sfa_pd_cpu_offload_single_rank.py` 或 `test_sfa_kv_offload_scheduler.py`：Main reuse、D2H suppression 与幂等 cleanup。

## 性能风险和后续优化

Full-sequence compute replay 仍可能造成明显性能问题，且代价随 preemption 时已有 sequence length 增长：Decode 会重复计算 prompt 和已经生成 token 的模型前向，并重新生成 Indexer；preserved Main reuse 只避免重复 Main D2H，不能消除模型计算。长上下文、高 preemption 频率或 Decode 算力紧张时，仍可能显著增加恢复延迟、降低吞吐并放大 tail latency。实现和测试必须单独统计 preemption 次数、replay token 数、复用的 Main token 数、跳过的 D2H bytes 及恢复耗时，不能把它混入正常 PD transfer 性能。

后续优先优化方向是 preemption 后重新从 Prefill 拉取所需 cache，而不是长期依赖 Decode full forward replay。由于首版保留 Main reservation 和有效 Main prefix，优先评估只重拉 Indexer；只有 Main validity 或 ownership 也无法维持时才重拉 Indexer 和 Main。该优化至少需要解决 Prefill source 的 request-lifetime 保留或可重建性、再次 rendezvous、source TTL/lease、transfer generation、重复 Indexer D2D 与可选 Main D2RH 的幂等性，以及 P/D 双侧取消和 cleanup；在这些条件闭环前不启用。
