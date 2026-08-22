# 05 — 完成全 TP transfer-failure recovery

**What to build:** 让任一 Decode TP 的 initial Indexer/Main transfer 最终失败都能在所有 TP 当前 operation 已返回后，把整个请求安全转入 Decode full-sequence replay；reservation 地址保持隔离，但所有 TP 放弃复用远端 Main 内容并确定性重建完整 cache。

**Blocked by:** 04 — 完成 exact TP lifecycle 与 fused D2H validity.

**Status:** ready-for-agent

- [ ] Scheduler 在当前 `RECEIVE_REMOTE` 获得完整 TP terminal coverage 后解释 mixed success/failure，并向所有 TP 下发新的 `PREPARE_REPLAY` command。
- [ ] Failure transition 保留 Main reservation identity 和 block IDs，但同时把 scheduler-side 与所有 worker-local `preserved_main_tokens` 统一降为 0。
- [ ] 每个 TP 在 `PREPARE_REPLAY` 中 retire/drain 旧 operation、拒绝 stale completion并产生 `REPLAY_READY`；局部 ready 不得提前恢复请求。
- [ ] Exact TP `REPLAY_READY` 后，scheduler 先建立 replay state并把 `num_computed_tokens` 置为 0，再通过现有 completion 顺序让请求进入 Decode full-sequence compute replay。
- [ ] Replay 从 token 0 重建完整 Indexer并重写完整 Main；failure 前成功 TP 的 Main 内容不能作为 preserved prefix 使用。
- [ ] Indexer/Main 每个 phase 仍只有一次 Python-level transfer 调用，不增加 connector retry；发起前只检查 local cancellation、execution epoch 和 destination ownership，不检查 Prefill source age或 remaining TTL。
- [ ] 不返回或无法证明 quiesced 的 operation 保持 request 和 destination pending/隔离，不启动 replay、不伪造 completion，也不通过 timeout 强制释放。
- [ ] Focused tests 覆盖任一 TP failure、完整 terminal barrier、all-TP validity reset、reservation identity保留、stale generation rejection和 full rewrite。
