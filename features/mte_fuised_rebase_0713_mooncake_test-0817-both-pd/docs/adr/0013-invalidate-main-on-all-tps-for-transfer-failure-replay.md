# Transfer-failure replay 统一失效所有 TP 的 Main

状态：已接受

任一 Decode TP 的 Indexer/Main 同步 transfer 在 Mooncake internal retry 后最终失败、整个 request 按 ADR 0012 转入 full-sequence replay 时，所有 Decode TP 都将 `preserved_main_tokens` 置为 `0`。Main lifetime reservation 及其 block IDs 继续归原 request 所有，但此前通过远端传输落入各 local Swapped Main pool 的内容不再被视为有效；replay 在所有 TP 上从 token 0 重写完整 Main prefix。该选择用重复 D2H 换取一致、可证明的跨 TP validity 边界。

## 穿刺代码怎么做

穿刺代码没有 transfer-failure replay，也没有跨 TP Main validity contract。失败 request 只进入 `failed_reqs`；D 收到失败 callback 后清理 `_main_ids_by_req`、`_indexer_ids_by_req` 等映射，既不记录哪些 TP 的 Main 成功，也不维护可跨 failure transition 使用的 `preserved_main_tokens`。因此穿刺不能证明“成功 TP 的 Main 可以复用”，目标实现不能从现存 Host 内容非零或某个 local transfer 返回成功推导 request-level preserved validity。

## 考虑过的方案

- 所有 TP 统一失效 Main，并在 replay 中完整重写。该方案恢复边界对称，不需要 per-TP validity 或不对称 fused D2H range；首版采用。
- 按 TP 保留已确认成功的 Main prefix。该方案可以减少成功 TP 的重复 D2H，但需要 per-TP validity、跨 epoch 校验以及不对称 fused-offload coverage；首版不采用。
- 取所有 TP 的 common preserved prefix。当前同步 phase 只返回整批成功/失败，没有可信的分段完成边界；任一 TP 失败时 common prefix 只能保守降为 `0`，首版效果与统一失效相同，不单独实现。

## 结果

- Request-level replay transition 必须把 scheduler-side 和所有 worker-local Main validity 一起降为 `0`，并以新的 replay generation 拒绝旧 transfer completion。
- 清零 validity 不释放 Main lifetime reservation，也不改变 block IDs；这些地址在 replay D2H 完成前仍保持隔离，不能分配给其他 request。
- 所有 TP 都执行 full-sequence forward、重建完整 Indexer，并从 token 0 把 Main D2H 到各自 local Swapped Main pool。其他 TP 在 failure 前已经成功接收的 Main 会被确定性覆盖。
- Replay 只有在所有 TP 的完整 Main rewrite 和 Indexer rebuild 都完成后才能重新建立 `preserved_main_tokens` 并进入 receive-complete/running；局部完成不能提前恢复 request。
- 该规则只适用于 transfer-failure replay。ADR 0009 的 preemption replay 仍可在 ownership 连续且 validity 可证明时保留 Main prefix；无法证明时同样降为 `0`。

## 预计实现影响

相对 ADR 0012 的公共 retry/replay 实现，本决策预计增加约 30-60 行 production Python 和 70-120 行 focused unit tests，编码与 CPU/mock UT 约 1-2 个工程日。预计涉及：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：request-level replay generation 和 all-TP Main validity reset；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/config_data.py`：统一的 replay/preserved boundary；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`：完整 Main rewrite 与 stale completion rejection；
- `tests/ut/kv_offload/test_mooncake_connector.py`：单 TP failure 导致所有 TP validity 清零；
- `tests/ut/kv_offload/test_sfa_pd_cpu_offload_single_rank.py` 或 focused worker test：reservation IDs 保留但 Main 从 token 0 覆盖。
