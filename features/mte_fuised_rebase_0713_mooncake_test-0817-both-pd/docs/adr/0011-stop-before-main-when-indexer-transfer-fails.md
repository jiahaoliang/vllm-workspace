# Indexer 传输失败时不启动 Main

状态：已接受

Blockwise DSA PD offload 在每个 Decode TP worker 内将 local Indexer D2D 作为 local Main D2RH 的 hard gate。对当前 request 和 execution epoch，只有该 TP 的 Indexer phase 最终成功后才能启动该 TP 的 Main；Indexer 的单次 connector-level 调用在 Mooncake internal retry 后仍返回失败时，不能提交 local Main，也不能把该 TP 标记为 local done。该选择避免失败 TP 继续消耗 Main 链路，同时不在两个 transfer phases 之间增加跨 TP barrier。

## 穿刺代码怎么做

穿刺代码先调用 Indexer D2D，再调用 Main D2RH，但 `_transfer_one_leg()` 在 `batch_transfer_sync_write()` 返回负值时只把 request 加入 `failed_reqs`，既不抛异常也不返回失败结果。调用方因此仍会立即执行 Main leg，并继续尝试后续 layer；直到最后一层才根据 `failed_reqs` 发送失败 callback。穿刺没有记录可供 retry 使用的 per-leg validity，因此即使 Main 成功，也不能可靠表达“Main 已有效、只需重试 Indexer”。目标实现不能沿用这项 best-effort 行为。

普通 `MooncakeConnectorV1` 在 `batch_transfer_sync_read()` 返回负值时抛出异常；request handler 随后标记该 request 的 load failure，并跳过已知失败 request 的后续 task。首版采用这个 fail-fast 方向，但将 Indexer 和 Main 保持为两个有明确先后关系的 transfer phases。

## 考虑过的方案

- Indexer 失败后立即停止，不启动 Main。该方案不会产生 partially-valid Main prefix，也不需要为本决策增加 per-leg preserved validity；首版采用。
- Indexer 失败后仍 best-effort 传输 Main。该方案可能为未来“只重试 Indexer”保留部分进度，但必须增加 per-leg validity、重试 generation 和 partial-success cleanup，且在尚未决定 retry contract 时只会增加状态空间；首版不采用。

## 结果

- 每个 Decode TP 的 local Indexer phase 必须先完成并确认成功，该 TP 的 local Main phase 才能启动；实现不能只是按顺序提交两个相互独立、无失败 gate 的调用。
- Local Indexer 的同步调用最终失败时，该 TP 在当前 execution epoch 不得产生 Main D2RH task，不得增加 `preserved_main_tokens`，也不得上报 local done。
- Main lifetime reservation 在失败处理完成前继续归原 request 所有，不能因为 Main 尚未写入就绕过 drain-and-ack 或提前复用。
- Indexer failure 按 ADR 0014 只依赖 Mooncake internal retry；同步调用最终失败后按 ADR 0012 令整个 request 进入 D-side full-sequence replay。按 ADR 0015，首版不检查 source TTL；调用不返回或无法证明 quiesced 时按 ADR 0016 沿用普通 V1，不增加 drain watchdog。
- Local gate 不包含跨 TP barrier：其他 Decode TP 如果已经通过自己的 Indexer gate，可以继续或已经完成 local Main。Request-level completion 仍必须等待所有 Decode TP 的聚合结果，任何局部成功都不能单独上报为 receive-complete。

## 预计实现影响

相对 blockwise DSA connector 的公共实现，本决策预计增加约 25-50 行 production Python 和 60-100 行 focused unit tests，编码与 CPU/mock UT 约 0.5-1.5 个工程日。预计涉及：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：Indexer phase 返回明确结果，并以成功结果 gate Main phase；
- `tests/ut/kv_offload/test_mooncake_connector.py`：Indexer failure 不调用 Main、不得 receive-complete、不得建立 Main validity；
- Phase result 按 ADR 0017 放入独立的 DSA worker result metadata。按照 ADR 0020，Indexer failure 产生 `TRANSFER_FAILED(INDEXER_D2D)`，不会产生 `RECEIVE_COMPLETE`；按照 [ADR 0021](0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md)，worker metadata 合并同一步 rank-aware facts，scheduler connector 跨 step 累积，并在完整 Decode TP terminal coverage 后进入 request-level failure transition。实现可能同时涉及 `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/config_data.py` 的 worker adapter。
