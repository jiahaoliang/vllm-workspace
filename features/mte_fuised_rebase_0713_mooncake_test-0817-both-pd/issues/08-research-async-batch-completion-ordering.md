# 验证 async batch completion 与 executor ordering

Type: research
Status: resolved
Blocked by: None
Parent: [Blockwise DSA Async Scheduling Wayfinder Map](../map.md)

## Question

在当前 vLLM `0fc695fc6` 与 vLLM-Ascend replacement `7401ae79c` 中，`schedule()`、`build_connector_meta()`、worker `execute_model()`、`wait_for_save()`、worker-output aggregation 与 `update_from_output()` 的实际顺序是什么？Default `MultiprocExecutor` 能保证哪些 per-step FIFO / all-worker completion facts，preemption、abort 与 normal finish 可以在哪些未回收 batch 边界发生，哪些 executor 或 runtime 语义仍未验证？

## Answer

完整 source evidence 见 [async batch completion 与 executor ordering research](../research/08-async-batch-completion-ordering.md)。

Current default `MultiprocExecutor` 保证 worker RPC execution 与 EngineCore output consumption 的 per-step FIFO；worker output 在 `wait_for_save()` 后生成，并在 scheduler 对应 batch 的 `update_from_output()` 中才可见。它不保证 step N+1 schedule 前已消费 step N completion，且 preemption、abort、normal finish 都可能发生在旧 batch 尚未回收时。

该结论没有覆盖 Ray、external launcher、其他 executor backend、BalanceScheduler 全部分支或真实 NPU/graph-capture runtime，因此 executor compatibility 必须单独决定，不能从 default multiproc source ordering 外推。
