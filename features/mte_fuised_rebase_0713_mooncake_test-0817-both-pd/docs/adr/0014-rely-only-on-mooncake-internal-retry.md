# 仅依赖 Mooncake 内部 retry

状态：已接受

Blockwise DSA PD offload 首版不在 `MooncakeConnectorV1` Python 层增加 connector-level retry。每个 Decode TP 的 Indexer D2D phase 和 Main D2RH phase 各只发起一次同步 `batch_transfer_sync_*()` 调用；该调用内部由 Mooncake binding 执行已有的有限重提交。Binding 最终返回失败后，connector 将该 local phase 视为失败，并按 ADR 0011、0012 和 0013 进入 gate 或 request-level full-sequence replay，不再从 Python 层重新调用 transfer。

## 穿刺代码怎么做

穿刺 connector 的 Python 数据面同样没有 retry loop：每个 Indexer/Main leg 调用一次 `batch_transfer_sync_write()`。返回负值时 `_transfer_one_leg()` 只把 request 加入 `failed_reqs`，调用方仍会继续后续 leg/layer，最后才发送失败 callback；D 侧没有可靠的 replay transition。使用 Mooncake backend 时，这个单次 Python 调用也会进入 Mooncake binding 的内部重提交，但穿刺代码没有在 binding 最终失败后提供正确的 request recovery。

目标实现保留“一次 Python transfer 调用”的边界，但不保留穿刺的 best-effort continuation：Indexer 调用最终失败时不启动 Main；任一 local phase 最终失败都会参与 request-level replay transition。

## 现有 MooncakeConnectorV1 怎么做

普通 `MooncakeConnectorV1` 对一个 transfer task 只调用一次 `batch_transfer_sync_read()`。返回负值时立即抛出异常，request handler 标记对应 block 无效，并跳过同一 request 的后续 task；connector 自身没有 retry loop。

当前锁定的 Mooncake `v0.3.12.post1` binding 在 `batchTransferSync()` 内最多执行 `numContexts() + 1` 次 batch submit。它只在已提交 batch 的 status 变成 `FAILED` 后继续下一次提交，没有 sleep/backoff，并让所有内部提交共享同一个 wall-clock timeout。`openSegment`、参数校验、`submitTransfer()` 或总 timeout 失败会直接返回；而且 batch entry 的 `advise_retry_cnt` 保持为 `0`，因此这项机制应理解为底层有限重提交，不能假设每次都切换到不同 NIC/context。

## 考虑过的方案

- 仅依赖 Mooncake internal retry。避免 connector 与 binding 形成乘法式嵌套重试，保持普通 `MooncakeConnectorV1` 的数据面调用边界；首版采用。
- 在 binding 外再做一次 connector-level retry。它可以覆盖部分 `openSegment` 或 submit 瞬时失败，但一次 outer retry 仍可能触发两轮 `numContexts() + 1` 次底层提交，并延长 source ownership 与 failure recovery；首版不采用。
- 增加可配置 attempts、backoff 和 wall-clock budget。它能精细控制不同部署的恢复策略，但需要新增配置、attempt metadata、取消/epoch 检查和更大的故障注入矩阵；首版不采用，可在真实故障数据证明 internal retry 不足后重新评估。

## 结果

- Indexer 和 Main 每个 local phase 在 Python connector 层都只有一次同步 transfer 调用；不增加 attempt loop、backoff sleep 或 retry 配置。
- Mooncake internal retry 对 connector 是 opaque operation。Connector 只能看到同步调用的最终返回值，不能在内部 attempt 之间重新检查 cancellation、execution epoch、destination ownership 或 source TTL。
- 发起同步调用前仍必须确认当前 execution epoch 和 destination ownership。按 ADR 0015，首版不检查 Prefill source validity；调用开始后 D destination ownership 保持隔离，直到 binding 返回且 worker 可以证明不再访问 destination。
- Binding 最终返回负值即 local phase 最终失败。Indexer 最终失败受 ADR 0011 gate 约束，不启动 Main；Main 最终失败直接参与 ADR 0012 的 request-level replay 聚合。
- 任何 TP 的 local phase 最终失败触发 request-level replay 时，按 ADR 0013 将所有 TP 的 `preserved_main_tokens` 置为 `0`；不根据 binding 内部可能发生的 partial write 推断有效范围。
- 不修改 Mooncake source，也不把底层 transport 的协议级重传计入 connector 可配置 attempt 数。未来若增加 outer retry，必须先用运行时故障证据确定 failure class，并同时限制嵌套提交的总 wall-clock。

## 预计实现影响

本决策不增加独立 retry subsystem，并相对 connector-level retry 方案减少约 35-70 行 production Python 和 70-120 行 focused unit tests。Failure aggregation 与 replay 本身仍属于 ADR 0012/0013 的实现范围。预计涉及：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：每个 phase 单次调用、最终失败分类和 Indexer-to-Main gate；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/config_data.py`：只记录最终 local phase/replay result，不增加 attempt 字段；
- `tests/ut/kv_offload/test_mooncake_connector.py`：断言 Python boundary 只调用 engine 一次，最终失败触发 gate/replay，成功返回允许下一 phase；
- Mooncake binding 的内部 retry 行为属于锁定 native dependency 的验证边界，不在 vLLM-Ascend mock unit test 中伪装成 connector retry。
