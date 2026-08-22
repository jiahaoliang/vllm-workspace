# 05 — 完成全 TP transfer-failure recovery

**What to build:** 让任一 Decode TP 的 initial Indexer/Main transfer 最终失败都能在所有 TP 当前 operation 已返回后，把整个请求安全转入 Decode full-sequence replay；reservation 地址保持隔离，但所有 TP 放弃复用远端 Main 内容并确定性重建完整 cache。

**Spec:** [Blockwise DSA PD offload spec](../spec.md)

**Decision basis:** [ADR 0011 — Indexer 传输失败时不启动 Main](../docs/adr/0011-stop-before-main-when-indexer-transfer-fails.md)、[ADR 0012 — Transfer 最终失败后由 Decode replay](../docs/adr/0012-retry-transfer-then-replay-on-decode.md)、[ADR 0013 — Transfer-failure replay 统一失效所有 TP 的 Main](../docs/adr/0013-invalidate-main-on-all-tps-for-transfer-failure-replay.md)、[ADR 0014 — 仅依赖 Mooncake 内部 retry](../docs/adr/0014-rely-only-on-mooncake-internal-retry.md)、[ADR 0015 — Transfer 前不检查 Prefill source TTL](../docs/adr/0015-do-not-check-prefill-source-ttl-before-transfer.md)、[ADR 0016 — 不为 Unquiesced operation 增加 watchdog](../docs/adr/0016-do-not-watchdog-unquiesced-operations.md)、[ADR 0020 — 使用 lifecycle action 和 terminal local result](../docs/adr/0020-use-lifecycle-actions-and-terminal-local-results.md)、[ADR 0021 — 使用精确 TP coverage 和跨 step result 累积](../docs/adr/0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md)

**Blocked by:** 04 — 完成 exact TP lifecycle 与 fused D2H validity.

**Status:** resolved

- [x] Scheduler 在当前 `RECEIVE_REMOTE` 获得完整 TP terminal coverage 后解释 mixed success/failure，并向所有 TP 下发新的 `PREPARE_REPLAY` command。
- [x] Failure transition 保留 Main reservation identity 和 block IDs，但同时把 scheduler-side 与所有 worker-local `preserved_main_tokens` 统一降为 0。
- [x] 每个 TP 在 `PREPARE_REPLAY` 中 retire/drain 旧 operation、拒绝 stale completion并产生 `REPLAY_READY`；局部 ready 不得提前恢复请求。
- [x] Exact TP `REPLAY_READY` 后，scheduler 先建立 replay state并把 `num_computed_tokens` 置为 0，再通过现有 completion 顺序让请求进入 Decode full-sequence compute replay。
- [x] Replay 从 token 0 重建完整 Indexer并重写完整 Main；failure 前成功 TP 的 Main 内容不能作为 preserved prefix 使用。
- [x] Indexer/Main 每个 phase 仍只有一次 Python-level transfer 调用，不增加 connector retry；发起前只检查 local cancellation、execution epoch 和 destination ownership，不检查 Prefill source age或 remaining TTL。
- [x] 不返回或无法证明 quiesced 的 operation 保持 request 和 destination pending/隔离，不启动 replay、不伪造 completion，也不通过 timeout 强制释放。
- [x] Focused tests 覆盖任一 TP failure、完整 terminal barrier、all-TP validity reset、reservation identity保留、stale generation rejection和 full rewrite。

## Answer

`mooncake_dsa_scheduler.py` 在完整 receive terminal coverage 后统一解释 mixed outcomes，保留 reservation identity、将 all-TP Main validity 清零并发布新 `PREPARE_REPLAY`；exact `REPLAY_READY` 后才把请求从 token 0 恢复。`mooncake_dsa_worker.py`/`mooncake_dsa_decode_runtime.py` retire 旧 operation、拒绝 stale generation，并且不增加 watchdog、connector retry 或 source TTL check。

任一 TP failure、terminal barrier、all-TP reset、identity preservation 与 full rewrite 均由 Phase B focused tests 覆盖，证据见 [验证报告](../cpu-mock-validation-report.md)。
