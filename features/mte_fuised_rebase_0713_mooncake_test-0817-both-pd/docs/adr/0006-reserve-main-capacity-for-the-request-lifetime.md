# 为请求完整生命周期预留 Main capacity

状态：已接受

Blockwise DSA PD offload 在 Decode admission 时按请求可能达到的最大序列长度建立 Main lifetime reservation，而不是只为当前 prompt 分配 Host block。Decode startup 必须先证明 `cdiv(max_model_len, main_block_size)` 不超过每个 TP 的可用 Swapped Main pool；并发导致当前容量不足时，connector 返回 `(None, False)` 让请求留在 waiting queue。该选择不修改 vLLM core，并保证请求一旦进入远端接收，后续 Decode 增长不会再次申请 Main capacity 或因 pool 耗尽而中途失败。

## 考虑过的方案

- 沿用穿刺代码，在 `update_state_after_alloc()` 中直接分配，容量不足时由 `CPUBlockManager` 抛出 `ValueError`。该方案改动最小，但异常发生在 vLLM 已分配 NPU block 之后，无法保证只失败当前请求及完整清理。
- Startup 校验加 prompt-only admission。该方案能避免请求开始接收时容量不足，但多个请求的未来 Decode 增长量仍可能超过 pool；不修改 vLLM core 时，running request 没有可靠的容量等待点，后续动态分配仍可能抛错。
- Startup 校验加 Main lifetime reservation。该方案降低并发利用率并增加 reservation cleanup 状态，但把容量等待放在 destination allocation 之前，并为已 admission 请求提供完整生命周期保证。
- 采用 work-conserving skip-and-retry，允许后续较小 reservation 绕过当前无法满足的请求。该方案保持 free capacity 利用率，但持续的小请求流量可能使大 reservation 饥饿并跨过 Prefill source TTL；首版不采用，将其保留为后续优化点。
- 采用 per-scheduling-step head-of-line admission gate。该方案会在队首暂时无法满足时闲置本可服务后续请求的容量，但不需要修改 vLLM core，也不需要长期复制 `fcfs`/`priority` queue；首版采用该方案。

## 结果

- 每个 Decode TP 必须在 startup 阶段校验 `cdiv(max_model_len, main_block_size) <= kv_cache_config.num_blocks - 1`，其中 block ID `0` 保留。
- Runner-owned Host Main tensor、scheduler block manager 和 Mooncake 注册范围必须通过实际容量与 layout 一致性校验。
- 每个请求按 `cdiv(min(max_model_len, prompt_len + request.max_tokens), main_block_size)` 预留 Main block capacity。
- 当前 free capacity 不足时返回 `(None, False)`，不分配 Indexer/Main destination，不启动传输，也不回退到本地 Prefill。
- Reservation 等待使用 step-local head-of-line gate：本步第一个容量不足的 DSA 请求返回 `(None, False)` 后，本步后续 DSA remote-prefill 请求也返回 `(None, False)`；`build_connector_meta()` 后清除 gate，下一步重新按 vLLM 当前 `fcfs` 或 `priority` 队首判断。
- Reservation 由 active prefix 和 future reserved suffix 组成；Decode 只激活已有 reservation，不再动态申请 Main capacity。
- Preemption 不是 reservation 释放点；请求恢复时继续使用原 Main block ownership，并按 ADR 0009 复用已经确认有效的 Main prefix。Cancellation 按 ADR 0010 先等待 worker quiesced，再幂等释放完整 reservation。正常完成、提前结束和已经返回且 quiesced 的失败路径最终释放完整 reservation；无法产生 quiesced ack 的 operation 按 ADR 0016 保持 ownership 隔离，不承诺在 live process 中自动释放。
- Work-conserving bypass 保留为后续容量利用率优化；启用前必须同时给出 starvation、Prefill source TTL 和 cleanup 的闭环方案。
- 首版不修改 vLLM core。若未来需要提高 lifetime reservation 本身限制的并发度，可重新评估按实际增长动态 reservation 或 core-level running-request backpressure。
