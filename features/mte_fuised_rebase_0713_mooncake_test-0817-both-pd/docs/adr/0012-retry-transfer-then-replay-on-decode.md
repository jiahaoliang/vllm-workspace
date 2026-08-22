# Transfer 最终失败后由 Decode replay

状态：已接受

Blockwise DSA PD offload 的 Indexer D2D 或 Main D2RH 同步 transfer 最终失败后，整个 request 转入 D-side full-sequence replay，而不是通过当前不支持双 KV group 的 `invalid_block_ids` 路径终止单个 request。每个 phase 只发起一次 connector-level transfer 调用，并按 ADR 0014 仅依赖 Mooncake binding 的 internal retry；binding 最终返回失败时进入 replay。按 ADR 0015，首版不在调用前检查 Prefill source TTL 或 ownership。该选择保持“不修改 upstream vLLM core”的边界，并以异常路径的计算成本换取 request-local recovery。

## 穿刺代码怎么做

穿刺代码没有 retry 或 replay。任一 transfer leg 返回失败时只把 request 加入 `failed_reqs`，仍继续后续 leg/layer，最后向 D 发送失败 callback。D worker 收到失败后清理 request/destination maps，但没有把对应 block IDs 加入 `_invalid_block_ids`，也不返回 `finished_recving`；scheduler 因而没有可靠的 retry、replay 或 terminal failure transition，request 可能停留在 `WAITING_FOR_REMOTE_KVS`。目标实现不能复制这条失败路径。

普通 `MooncakeConnectorV1` 会把同步 read failure 转成 `invalid_block_ids`，再交给 `kv_load_failure_policy=fail|recompute`。当前 vLLM 的 request lookup 仍按单 KV group 解包，本 feature 的 Indexer/Main 双 group 不能在不修改 core 的情况下直接复用。因此首版在 connector scheduler/worker 内维护 phase failure 和 replay transition。

## 考虑过的方案

- Mooncake internal retry 最终失败后 D-side full-sequence replay。它避免 connector/binding 嵌套重试，并在持续失败时使用已有的本地计算恢复方向；首版采用，retry 层级详见 ADR 0014。
- 增加 connector-level bounded retry 后再 replay。它可以覆盖 binding 不重试的部分 failure class，但会形成嵌套提交并延长 source lifetime；首版不采用。
- 最终失败后令 worker/engine fatal。它不需要 request-level failure contract，但会把单请求故障扩大到 Decode instance，不作为首版正常策略。
- 最终失败后只结束当前 request。该语义需要 group-aware request failure channel；在“不修改 upstream vLLM core”约束下暂不采用。

## 状态流

```text
LOCAL_PHASE_ACTIVE
  |
  | one synchronous transfer call
  | (Mooncake internal retry is opaque)
  v
TRANSFER_RETURN
  | success                         | final failure
  v                                 v
NEXT_LOCAL_PHASE or LOCAL_DONE      REQUEST_REPLAY_PENDING
                                      |
                                      | all Decode TP workers quiesced
                                      v
                                   REPLAY_READY
                                      |
                                      | resume with num_computed_tokens = 0
                                      v
                                   D-SIDE FULL-SEQUENCE REPLAY
```

Indexer phase 的同步调用最终成功后，ADR 0011 的 local gate 才允许该 Decode TP 启动 Main phase。Main phase 最终成功后，该 TP 可以上报 local done。任一 TP 的 phase 最终失败都会使整个 request 进入 replay；其他 TP 已经成功的局部结果不能单独形成 receive-complete。

## 结果

- Connector 只处理同步 transfer 的最终结果；Mooncake internal retry 的 attempt 对 connector 不可见。底层调用不返回或 worker 无法证明 quiesced 时按 ADR 0016 沿用普通 V1，不进入 replay，也不增加 drain watchdog 或自动 fail-stop。
- 每个 phase 发起唯一一次 connector-level transfer 前，必须确认 request 未取消或 preempt、execution epoch 与 destination ownership 未变化；任一条件不满足时不启动 transfer，直接转入 replay。按 ADR 0015，不检查 Prefill source age、remaining TTL 或 ownership。
- 最终失败后不根据返回值猜测部分 SG 已成功。Replay 对同一 reservation 地址的完整覆盖必须是幂等的。
- Worker 按 ADR 0017 通过独立的、实现 `KVConnectorWorkerMetadata.aggregate()` 的 DSA worker result metadata 报告 local result。按照 ADR 0020，initial receive failure 使用 `TRANSFER_FAILED(INDEXER_D2D|MAIN_D2RH)`；按照 [ADR 0021](0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md)，scheduler 等待当前 command 的完整 Decode TP terminal coverage 后再下发 `PREPARE_REPLAY`，所有 Decode TP 不再访问 transfer destination 后报告 `REPLAY_READY`。
- Scheduler connector 必须在 core 消费 worker completion 之前把 request 的 `num_computed_tokens` 置为 `0` 并建立 replay state。随后可复用现有等待请求恢复控制流进入本地 full-sequence replay；此 completion 只表示 replay-ready，不表示 external KV receive-complete。
- 按 ADR 0013，transfer-failure replay 统一令所有 TP 的 `preserved_main_tokens=0`，保留 Main reservation ownership，但不复用其他 TP 已经成功接收的 Main 内容。
- Retry 层级由 ADR 0014 确定：首版仅依赖 Mooncake internal retry，不增加 connector attempts、backoff 或 retry 配置。Source TTL handling 由 ADR 0015 确定：沿用普通 V1，不增加 launch-time check。

## 预计实现影响

相对 blockwise DSA connector 的公共实现，本决策预计增加约 110-190 行 production Python 和 190-300 行 focused unit tests，编码与 CPU/mock UT 约 3-6 个工程日，不包含 NPU 故障注入。预计涉及：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：final phase result、worker result、request-level replay transition 和 completion gating；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/config_data.py`：execution epoch、final phase result 和 replay metadata；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`：重置 failure-path validity，并在 replay 中重建 Indexer/Main；
- `tests/ut/kv_offload/test_mooncake_connector.py`：Indexer/Main final failure、单次 engine 调用、跨 TP 聚合和 replay transition；
- `tests/ut/kv_offload/test_sfa_pd_cpu_offload_single_rank.py` 或 focused worker test：failure overwrite、stale epoch 和 replay rebuild。
