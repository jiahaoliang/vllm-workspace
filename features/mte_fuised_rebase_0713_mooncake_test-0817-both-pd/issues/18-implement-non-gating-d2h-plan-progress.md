# 18 — 实现 non-gating D2H plan/progress vertical slice

**What to build:** 在已发布sync replacement `7401ae79c`上，把decode-time Main D2H从single-active lifecycle `FUSED_D2H` / `D2H_COMPLETE`改为step-local `DsaD2HStepPlan` / `D2HStepProgress`，打通scheduler issued/confirmed ledger、worker persistent Main binding、每step ephemeral SFA view和`wait_for_save()`后progress的两步non-gating闭环。Sync scheduling与async scheduling共用同一step-local contract。

**Spec:** [Blockwise DSA async-compatible spec](../spec.md)

**Decision basis:** [ADR 0024 — non-gating D2H progress](../docs/adr/0024-use-non-gating-d2h-progress-and-dual-main-watermarks.md)、[ADR 0027 — step-local D2H plan与worker binding](../docs/adr/0027-use-step-local-d2h-plans-and-worker-main-bindings.md)

**Planning decision:** [定义 ADR/spec supersession 与 implementation ticket chain](16-define-doc-supersession-implementation-chain.md)

**Blocked by:** None — can start after explicit source-modification authorization.

**Status:** open

## Expected source scope

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py`
- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`
- Existing SFA config/scheduler files only when the persistent binding cannot be expressed through their current adapter boundary.
- Focused tests in existing `tests/ut/kv_offload/` files.

## Acceptance

- [ ] `DsaAction` no longer contains `FUSED_D2H`; `DsaLocalResultKind` no longer contains `D2H_COMPLETE`. Receive/failure/replay action-result validation remains exact.
- [ ] `DsaConnectorMetadata` carries lifecycle requests and independent immutable D2H step plans without duplicating source, Indexer binding or lifecycle command sequence.
- [ ] Each nonempty plan uses a request-local, epoch-local D2H step sequence and records reservation identity, ordered Main bound prefix and continuous token range in an immutable issued ledger.
- [ ] Scheduler advances issued watermark when publishing metadata, advances confirmed watermark only from current-epoch exact-TP progress, and does not gate publication of the next model step on prior progress.
- [ ] Worker retains persistent Main reservation/epoch/bound-prefix state, rebuilds and clears the ephemeral SFA view every model step, and does not require an active lifecycle command for `get_num_cpu_blocks()`.
- [ ] Worker returns rank-aware progress only after `wait_for_save()` succeeds. D2H exception paths do not fabricate progress, transfer failure or ordinary completion.
- [ ] Focused CPU/mock tests cover two continuously issued D2H steps, exact-TP progress after save drain, ledger continuity and confirmed watermark advancement. Model execution、Mooncake、SFA kernel与NPU tensor使用fake/mock。
- [ ] Existing receive/replay exact-TP behavior and default V1 type isolation remain intact.

## Evidence boundary

This ticket proves only the focused plan/progress vertical slice. It does not claim terminal, preemption, NPU, real Mooncake, fused-kernel or graph-capture validation. Creation of this ticket does not authorize changes under `repos/*`.

## Stop and review

Stop before modifying upstream vLLM core, adding another public connector or production module, introducing a second D2H metadata channel, changing positional ABI/Main reservation policy, or adding watchdog/reliable cancel/fatal-latch behavior.
