# 04 — 完成 exact TP lifecycle 与 fused D2H validity

**What to build:** 让 Blockwise DSA lifecycle 在真实的多 TP Decode replica 内只依据精确、rank-aware 的 terminal facts 前进，并把成功的 fused D2H 纳入 Main validity：局部成功、重复 result 或匿名完成计数都不能提前恢复请求或释放 ownership。

**Spec:** [Blockwise DSA PD offload spec](../spec.md)

**Decision basis:** [ADR 0016 — 不为 Unquiesced operation 增加 watchdog](../docs/adr/0016-do-not-watchdog-unquiesced-operations.md)、[ADR 0019 — 使用显式最小完备的 DSA step fields](../docs/adr/0019-use-minimal-complete-dsa-step-fields.md)、[ADR 0020 — 使用 lifecycle action 和 terminal local result](../docs/adr/0020-use-lifecycle-actions-and-terminal-local-results.md)、[ADR 0021 — 使用精确 TP coverage 和跨 step result 累积](../docs/adr/0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md)、[ADR 0023 — 使用 Phase A 后 Phase B 的分阶段验证](../docs/adr/0023-use-staged-phase-a-then-phase-b-validation.md)

**Blocked by:** 03 — 打通并验证 Phase A request lifecycle.

**Status:** ready-for-agent

- [ ] 每个 command 的 expected coverage 是当前 routed Decode DP replica 内的 `0..D_TP-1`，不包含其他 DP、Prefill rank 或全局 device ID。
- [ ] Worker metadata 只合并同一 engine step 的 facts；Decode scheduler 按 request、execution epoch 和 command sequence 跨 step 累积 `results_by_tp`。
- [ ] 相同 identity 和完整内容的 duplicate result 幂等；冲突 result、future command、非法 TP rank及 action/result mismatch fail closed。
- [ ] Stale result 被记录并忽略，不恢复旧 ownership、不推进 validity、不生成 completion；missing rank 使 request 无限期保持 pending。
- [ ] `RECEIVE_REMOTE` 只有在 exact TP coverage 全部为 `RECEIVE_COMPLETE` 后才建立 Indexer/Main validity并生成对应 `finished_recving`。
- [ ] 任一 TP 报告 transfer failure 时，当前 command 先等待其他 TP 的 terminal coverage，不与尚未结束的 destination operation 并发启动 replay。
- [ ] `FUSED_D2H` 只能写入 current bound Main prefix 中从 confirmed boundary 开始的连续 range；exact TP `D2H_COMPLETE` 后推进 confirmed Main valid prefix，且不生成 `finished_recving`。
- [ ] Fused D2H failure 保持 worker/engine fail-fast，不伪造 `TRANSFER_FAILED`、`D2H_COMPLETE` 或 request-local recovery。
- [ ] Focused tests 覆盖跨 step coverage、duplicate/conflict/stale/future/missing、mixed TP outcomes、D2H range/validity 和 default V1 completion isolation。
