# 由 serving request lifecycle 限制 reservation admission 等待

状态：已被 ADR 0008 取代

Blockwise DSA PD offload 的 Main reservation 暂时不足时，Decode connector 继续返回 `None` 并等待重试；首版不在 connector 内增加 pre-admission timeout，而由 serving/proxy request lifecycle 终止等待过久的请求。Prefill source block 继续受 MooncakeConnectorV1 已有的 `VLLM_MOONCAKE_ABORT_REQUEST_TIMEOUT` hard TTL 约束，external D request timeout 必须更短并为 handoff 与 transfer 留出 safety margin。这样可以保持单请求取消语义且不修改 vLLM core，但把正确配置 timeout 的责任明确交给部署与 routing 层。

## 考虑过的方案

- 在 `get_num_new_matched_tokens()` 中设置 connector-local deadline。现有 interface 在 destination allocation 前只有“返回 token 数”或“返回 `None` 稍后重试”，没有安全结束单个请求的结果；抛出异常可能中断 scheduler 或 engine，因此不采用。
- 修改 vLLM core，增加 pre-admission per-request failure result。该方案能由 connector 精确结束超时请求，但超出首版“不修改 vLLM core”的边界。
- 由 serving/proxy 设置更短的 request timeout，并通过现有 abort/cancellation 路径结束 D 请求；P 在收到完成通知时提前释放，否则由现有 hard TTL 最终释放。首版采用该方案。

## 结果

- Connector 不为 Main reservation wait 新增 timeout 配置、后台 timer 或异常路径。
- `VLLM_MOONCAKE_ABORT_REQUEST_TIMEOUT` 仍是 Prefill source block 的 hard TTL，默认 480 秒；首版不增加 lease refresh。
- External D request timeout 必须小于 Prefill source TTL；具体数值和 safety margin 在部署前置条件与测试计划中明确。
- Cancellation 和已经取得的 reservation 按 ADR 0010 的 drain-and-ack 幂等清理；无法产生 quiesced ack 的 operation 按 ADR 0016 保持 ownership 隔离，不增加自动 timeout cleanup。
