# Transfer 前不检查 Prefill source TTL

状态：已接受

Blockwise DSA PD offload 首版沿用普通 `MooncakeConnectorV1` 的 source lifetime 行为：Prefill 从请求完成时开始按 `VLLM_MOONCAKE_ABORT_REQUEST_TIMEOUT` 延迟释放 source blocks，收到 Decode completion 时提前释放，超时后允许强制释放。Decode 在 admission 或启动 Indexer/Main transfer 前不检查 source age、remaining TTL 或当前 block ownership，也不增加 request-specific launch grant、source generation、absolute expiry、lease refresh 或 clock-skew handshake。

该选择保持普通 V1 的控制面和 metadata 边界，但接受一个明确的 correctness residual risk：如果 Decode 因 Main reservation head-of-line wait 等原因跨过 Prefill source TTL，remote address 可能已经被 P 侧其他请求复用。此时 transfer 可能返回失败并触发 ADR 0012 replay，也可能从仍然合法的注册地址成功读取错误 KV；后者不能被现有 return code 检测，也不会自动触发 replay。

## 穿刺代码怎么做

穿刺代码不做 blockwise source TTL 检查。它采用 P-driven layerwise buffer gate：P 在当前 layer 数据 ready 后发送 `READ_READY_BATCH`，D 立即读取并回复 `READ_DONE` 或 `READ_FAILED`；P 在回复到达前不复用该 layer buffer，并在 `wait_for_layer_send()` 中使用 10 秒等待上限。其 source ownership 由逐 layer 的实时 ready/done 时序维持，不存在 target blockwise 方案中“D admission 长时间等待后再读取 P request blocks”的同一种 TTL 窗口。

目标实现不迁移这项 layerwise gate，也不为 blockwise source 增加等价 launch-time ownership protocol。

## 普通 MooncakeConnectorV1 怎么做

普通 `MooncakeConnectorV1` 在 P 侧 `request_finished()` 时记录 delayed-free 起点，并将 remote block IDs、engine/session 和静态 memory metadata 交给 D。默认 hard TTL 为 480 秒；P 的 delayed tracker 在收到 completion 时提前结束，或在 hard TTL 后允许 core 回收 blocks。

D 收到的 `kv_transfer_params` 不包含 expiry、generation 或 remaining TTL。现有 `GET_META_MSG` 也不携带 request ID，只返回 process-level engine 地址和 layout；因此普通 V1 没有 request-specific source ownership validation。首版完整沿用该行为。

## 考虑过的方案

- 不检查，沿用普通 V1。改动最小，不增加额外 control-plane RTT 或 metadata 字段；首版采用，并显式接受 TTL overrun 的 correctness residual risk。
- P 下发 absolute expiry，由 D 本地检查。它需要可信的跨节点 wall clock 和 clock-skew fail-closed handshake，否则 expiry 比较本身不可靠；首版不采用。
- D 在 transfer 前向 P 请求 request-specific launch grant。它可以由 P 使用本地 tracker 原子判断 ownership 和 remaining TTL，不依赖跨节点时钟，但需要新消息、source generation 和 denied-to-replay transition；首版不采用。
- D 等待期间 refresh/延长 P lease。它改变现有 hard TTL/no-refresh 语义，并扩大 P resource retention 和 cleanup 状态空间；首版不采用。

## 结果

- `kv_transfer_params`、connector metadata 和 worker phase metadata 不增加 `source_expire_at`、`source_generation`、`remaining_ttl`、`required_hold` 或 grant result。
- P/D handshake 不增加 wall-clock、clock-skew、request ownership 或 lease capability 字段；`GET_META_MSG` 保持静态 engine metadata 语义。
- D 在本地 reservation admission 后，按现有 remote block IDs 发起 Indexer 和 Main 的唯一一次 connector-level transfer，不因等待时长跳过 transfer。
- Connector 在 transfer 前仍检查本地 cancellation、execution epoch 和 destination ownership；这些检查不能证明 P source 仍有效。
- Mooncake binding 最终返回负值时仍按 ADR 0011-0014 gate/replay。返回成功只表示 transport 调用成功，不能在 TTL overrun 场景下证明读取内容仍属于原 request。
- 部署必须把“P source 在 D 启动并完成 Indexer/Main 前未被 TTL 回收”视为未被代码强制执行的 operational assumption。超过 TTL 的请求行为不属于首版正确性保证。
- 后续若观察到 reservation wait 接近 TTL、remote read 成功但输出异常，或需要把该 operational assumption 变成可证明 contract，应优先重新评估 P-authoritative launch grant，而不是仅增加 D 本地时间比较。

## 预计实现影响

本决策不增加 production source validation 代码，并相对 P-authoritative launch grant 方案减少约 130-220 行 production Python 和 190-320 行 focused unit tests。现有实现仍需覆盖普通 transfer failure/replay，但不实现或伪测 TTL ownership validation。预计影响为：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：保持普通 V1 metadata、GET_META 和 delayed-free behavior，不增加 TTL branch；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/config_data.py`：不增加 source lease/generation 字段；
- `tests/ut/kv_offload/test_mooncake_connector.py`：只需确认本 feature 没有因 metadata age 拒绝 transfer，不把过期地址成功返回模拟成可检测 failure；
- NPU 测试计划记录接近或跨过 TTL 的 risk-characterization case，但不能把该 case 的成功输出列为首版验收要求。
