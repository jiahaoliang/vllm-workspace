# 19 — 实现 async terminal ownership barrier

**What to build:** 在non-gating D2H基础上，把normal finish、EOS、stop、length cap与abort统一映射为`Terminal-pending`，通过metadata-only/no-forward `QUIESCE` tail marker、worker Quiesced、ordinary all-worker `finished_recving`和scheduler release-once完成async terminal ownership protocol。

**Spec:** [Blockwise DSA async-compatible spec](../spec.md)

**Decision basis:** [ADR 0025 — QUIESCE tail marker](../docs/adr/0025-use-quiesce-tail-marker-for-terminal-ownership.md)、[ADR 0010 — cancellation drain-and-ack](../docs/adr/0010-use-two-phase-cancellation-drain-and-ack.md)、[ADR 0016 — no watchdog](../docs/adr/0016-do-not-watchdog-unquiesced-operations.md)

**Planning decision:** [定义 ADR/spec supersession 与 implementation ticket chain](16-define-doc-supersession-implementation-chain.md)

**Blocked by:** 18 — 实现 non-gating D2H plan/progress vertical slice.

**Status:** open

## Expected source scope

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`
- Focused connector/worker tests under `tests/ut/kv_offload/`.

## Acceptance

- [ ] Any finish reason after Main admission enters one reason-agnostic terminal state, freezes issued/confirmed validity and prevents new receive/replay/D2H publication.
- [ ] Scheduler can deliver a metadata-only/no-forward `QUIESCE` batch after already queued work without modifying upstream vLLM core.
- [ ] Worker treats `QUIESCE` as a FIFO tail marker, drains all current/old epoch destination access, clears request binding and sends best-effort `DONE_RECVING_MSG` before publishing ordinary completion once.
- [ ] Scheduler releases Main reservation exactly once only after ordinary all-worker completion; delayed NPU blocks remain owned until the existing core completion order releases them.
- [ ] Late legal D2H progress after terminal intent can retire issued records but cannot advance reusable validity or substitute for Quiesced proof.
- [ ] Failure to deliver/complete `QUIESCE` keeps ownership isolated and does not add watchdog、reliable cancel、fatal latch、timeout completion或automatic restart。
- [ ] The only new mandatory runtime test is normal finish: queued work -> `QUIESCE` -> ordinary all-worker completion -> release-once. Preemption、abort与other terminal reasons remain“未测试”。

## Evidence boundary

Passing the normal-finish test does not validate abort, cancellation races, D2H failure, NPU or graph-capture runtime. Creation of this ticket does not authorize changes under `repos/*`.

## Stop and review

Stop before adding typed `QUIESCED`, modifying upstream core completion semantics, adding a non-FIFO executor contract, or introducing forced release for unquiesced operations.
