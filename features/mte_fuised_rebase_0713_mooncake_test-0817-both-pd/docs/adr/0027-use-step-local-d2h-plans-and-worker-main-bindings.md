# 使用 step-local D2H plan 与 worker Main binding

状态：已接受

Async scheduling允许scheduler在前一batch output尚未回收时继续发布下一step，因此Blockwise DSA的decode-time Main D2H不再使用single-active `FUSED_D2H` lifecycle command。`DsaConnectorMetadata`改为并列携带lifecycle requests与独立`DsaD2HStepPlan`；每个nonempty plan以request、execution epoch、request-local D2H step sequence、Main reservation、ordered bound Host block prefix和token range形成immutable issued fact。

Scheduler从当前`SchedulerOutput`计算model-step token end，以issued Main watermark为D2H range起点，并在metadata发布时推进issued ledger而非confirmed validity。Replay尚未追上preserved prefix `P`时不发布plan，跨过`P`时只发布suffix；bound table精确覆盖range end且同epoch只能保持或append。Plan不携带lifecycle command sequence、Indexer binding、remote source、global scheduler step或冗余token total。

Worker为live request保留persistent Main reservation/epoch/bound-prefix binding与轻量D2H continuity cursor，每个model step再按实际batch重建ephemeral SFA view。没有nonempty D2H plan的step仍能从persistent binding获得preserved Main block table，并必须清空上一step的SFA state；`get_num_cpu_blocks()`不再依赖active lifecycle command。`PREPARE_REPLAY` barrier完成后才允许切换epoch或把可访问prefix重置到`P`，同epochplan只能扩展binding。

Worker只有在SFA `wait_for_save()`成功后才返回rank-aware `D2HStepProgress`。Plan identity/range/reservation必须连续且匹配live binding；duplicate完整内容幂等，conflict、gap、future epoch或非法bound prefix fail fast。Barrier后的old-epoch plan不得访问destination；D2H failure继续作为model-step exception传播，不伪造progress、typed transfer failure或ordinary completion。Scheduler仍独占issued/confirmed ledger、Main validity与reservation release authority。

该方案采用self-contained per-step plan加persistent binding，而不采用把D2H fields继续塞进lifecycle envelope、另开普通SFA metadata通道或只发送handle delta。前两者会重新耦合lifecycle gate或产生双重source of truth；handle-only方案需要额外resync protocol。完整schema与worker规则见[定义 step-local D2H metadata 与 worker binding](../../issues/14-define-step-local-d2h-metadata-worker-binding.md)。
