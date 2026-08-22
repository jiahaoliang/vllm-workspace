# 按 scheduling step 对 Main reservation 实施队首阻塞

状态：已接受

Blockwise DSA PD offload 在 Main lifetime reservation 容量不足时采用与普通 vLLM KV allocation 相同的 head-of-line 结果：当前队首请求不能 admission 时，本 scheduling step 不允许后续 DSA remote-prefill 请求绕过。Decode connector 使用 step-local gate 实现该语义，并在 `build_connector_meta()` 后清除；它不修改 vLLM core，也不长期复制 `fcfs` 或 `priority` queue。该选择牺牲部分 work-conserving capacity utilization，以避免大 reservation 在持续小请求流量下饥饿。

## 考虑过的方案

- 沿用 vLLM 对 connector `None` 的默认 skip-and-retry，让较小请求绕过。该方案改动最少且 work-conserving，但可能让大 reservation 无限等待，并使其 Prefill source 跨过 hard TTL。它保留为后续优化点。
- 在 connector 中维护持久 reservation wait queue。该方案可以实现严格排序，但会复制 vLLM 的 `fcfs`/`priority` 状态，并需要额外处理 priority 变化、取消和双队列一致性，首版不采用。
- 仅在当前 scheduling step 记录第一次 capacity miss，并让本步后续 DSA admission 全部返回 `None`；本步 metadata 构建后清除 gate。该方案跟随 vLLM 每步实际检查顺序，首版采用。

## 结果

- 首个 capacity miss 之前的请求仍可正常 admission；miss 之后，本步不再尝试后续 DSA reservation。
- 下一 scheduling step 从 vLLM 当时的队首重新判断，因此 `priority` 新请求可以按 core 的最新顺序被考虑。
- 首版不新增 feature-specific serving/proxy first-response deadline，继续沿用普通 MooncakeConnectorV1 的 request waiting 行为和 Prefill source TTL。
- Work-conserving bypass 不是删除项；后续只有在 starvation bound、source TTL 和 cancellation/cleanup 同时闭环后才重新启用。
