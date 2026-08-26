# 定义 non-gating D2H progress 与 confirmed Main validity ledger

Type: grilling
Status: resolved
Blocked by: 08, 09, 10
Parent: [Blockwise DSA Async Scheduling Wayfinder Map](../map.md)

## Question

在不恢复跨 step scheduling gate、也不修改 upstream vLLM core 的前提下，scheduler-issued step identity、worker-returned `D2H step progress`、same-step worker aggregation 与 `confirmed Main watermark` 应采用什么最小 contract？该 contract 如何证明 range 连续、current-epoch、与 lifetime reservation/bound prefix 一致，并拒绝 duplicate conflict、gap、future 或 stale progress？

## Answer

Decision asset: [ADR 0024 - 使用 non-gating D2H progress 与 dual Main watermarks](../docs/adr/0024-use-non-gating-d2h-progress-and-dual-main-watermarks.md).

### Ledger 与 identity

每个 `(request_id, execution_epoch)` 独立维护：

- `issued Main watermark`：连续、immutable Issued D2H steps 已发布到的最大 token boundary；
- `confirmed Main watermark`：scheduler 已消费完整 D2H step progress、且从既有 Main-valid boundary 起无缺口完成的最大 token boundary；
- issued-step ledger：以独立的 request-local `d2h_step_seq` 索引，不复用 lifecycle `command_seq` 或 global scheduler step。

只有非空 D2H range 分配 sequence。每个 issued record 至少包含 `request_id`、`execution_epoch`、`d2h_step_seq`、`reservation_id`、`token_start` 与 `token_end`。发布时必须满足 `token_start == issued Main watermark`、`token_end > token_start`，且 range 不超过当前 Main bound prefix与lifetime reservation capacity；发布成功只推进 issued watermark，不推进 confirmed watermark。

### Progress 与 same-step coverage

每个 Decode TP 只在该 model step 的 Main D2H 完成并经过 `wait_for_save()` 后发布 D2H step progress。Progress 回显 issued record 的 semantic fields，并增加 local `tp_rank`。当前 model step 的 worker metadata 必须聚合为精确 Decode TP rank set；缺失 rank、非法 rank或同一 identity 的冲突内容保持 fail fast。

该 exact coverage只证明当前 worker step，不建立跨-step result tracker，也不阻塞 scheduler继续发布后续 D2H plan。具体 Main block-table与worker binding schema由 [定义 step-local D2H metadata 与 worker binding](14-define-step-local-d2h-metadata-worker-binding.md) 继续决定。

### Completion accumulation

一个已发布的later sequence可以先获得完整 progress并标记completed，但confirmed watermark停在第一个completion gap。缺口补齐后，scheduler按sequence和token range一次推进所有连续completed entries。永久gap不停止后续non-overlapping D2H plan、不增加timeout/watchdog，也不推测completion；preemption只能复用gap之前的confirmed prefix，terminal release仍要求后续terminal ownership barrier证明Quiesced。

### Validation 与 retirement

- Live issued entry收到相同identity和完整内容的duplicate时幂等；同一identity的range、reservation或rank冲突fail fast。
- Current epoch收到尚未发布的future sequence、非法TP rank、reservation mismatch或progress/plan mismatch时fail fast。
- 已confirmed sequence、old execution epoch或released request的late progress只做bounded warning后忽略，不重新建立ledger、不推进validity、不恢复ownership。
- 连续confirmed entries可以从live ledger退休；其后到达的progress按stale处理，不要求保留无界per-step tombstone。

### Initial boundary

Exact-TP `RECEIVE_COMPLETE` 同时把issued/confirmed Main watermark初始化为remote Main已经有效的token boundary，issued-step ledger为空。Initial transfer failure进入full replay时，两条watermark归零，后续local replay从token 0建立新的D2H plans。Preemption时的epoch切换、late old-epoch progress和preserved prefix由 [定义 preemption 与 late D2H progress contract](13-define-preemption-late-progress-contract.md) 继续决定。

本决策不修改upstream vLLM core，不增加D2H cross-step scheduling gate，不处理speculative decoding，也不扩大fused D2H failure的model-step fail-fast边界。
