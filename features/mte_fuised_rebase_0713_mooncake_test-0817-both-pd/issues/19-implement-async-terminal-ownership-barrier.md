# 19 — 实现 async terminal ownership barrier

**What to build:** 在non-gating D2H基础上，把normal finish、EOS、stop、length cap与abort统一映射为`Terminal-pending`，通过metadata-only/no-forward `QUIESCE` tail marker、worker Quiesced、ordinary all-worker `finished_recving`和scheduler release-once完成async terminal ownership protocol。

**Spec:** [Blockwise DSA async-compatible spec](../spec.md)

**Decision basis:** [ADR 0025 — QUIESCE tail marker](../docs/adr/0025-use-quiesce-tail-marker-for-terminal-ownership.md)、[ADR 0010 — cancellation drain-and-ack](../docs/adr/0010-use-two-phase-cancellation-drain-and-ack.md)、[ADR 0016 — no watchdog](../docs/adr/0016-do-not-watchdog-unquiesced-operations.md)

**Planning decision:** [定义 ADR/spec supersession 与 implementation ticket chain](16-define-doc-supersession-implementation-chain.md)

**Blocked by:** 18 — 实现 non-gating D2H plan/progress vertical slice.

**Status:** resolved

## Expected source scope

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`
- Focused connector/worker tests under `tests/ut/kv_offload/`.

## Acceptance

- [x] Any finish reason after Main admission enters one reason-agnostic terminal state, freezes issued/confirmed validity and prevents new receive/replay/D2H publication.
- [x] Scheduler can deliver a metadata-only/no-forward `QUIESCE` batch after already queued work without modifying upstream vLLM core.
- [x] Worker treats `QUIESCE` as a FIFO tail marker, drains all current/old epoch destination access, clears request binding and sends best-effort `DONE_RECVING_MSG` before publishing ordinary completion once.
- [x] Scheduler releases Main reservation exactly once only after ordinary all-worker completion; delayed NPU blocks remain owned until the existing core completion order releases them.
- [x] Late legal D2H progress after terminal intent can retire issued records but cannot advance reusable validity or substitute for Quiesced proof.
- [x] Failure to deliver/complete `QUIESCE` keeps ownership isolated and does not add watchdog、reliable cancel、fatal latch、timeout completion或automatic restart。
- [x] The only new mandatory runtime test is normal finish: queued work -> `QUIESCE` -> ordinary all-worker completion -> release-once. Preemption、abort与other terminal reasons remain“未测试”。

## Evidence boundary

Passing the normal-finish test does not validate abort, cancellation races, D2H failure, NPU or graph-capture runtime. Creation of this ticket does not authorize changes under `repos/*`.

## Stop and review

Stop before adding typed `QUIESCED`, modifying upstream core completion semantics, adding a non-FIFO executor contract, or introducing forced release for unquiesced operations.

## Answer

Implemented and published as signed-off source commits `2fc7037402979ab4a9036c790ba276a4722aebea` and
`8f7c17f9f8490b001107e498b3db297c91f81531`. The final GitCode branch ref was verified at
`8f7c17f9f8490b001107e498b3db297c91f81531`, and the source worktree was clean.

CPU/mock validation ran in the CPU-only `liangjiahao/vllm-ascend-ut` Pod: metadata plus connector
targets were `140 passed`, and the complete remote-prefill lifecycle file was `6 passed` in an
independent pytest process. The focused red-green cases covered normal finish, terminal late-progress
retirement, both `wait_for_save() -> QUIESCE` and `QUIESCE -> wait_for_save()` orderings, ordinary
completion once, and release-once. `py_compile`, `git diff --check`, `ruff format --check`, and
diff-relevant `ruff check` passed. Independent two-axis rereview found no blocking ticket 19 finding.

Preemption-pending latest-epoch `QUIESCE` and late rebind terminal dominance belong to ticket 20 and
remain pending there. Abort and other terminal runtime reasons are untested. Real Mooncake, NPU,
fused kernel, graph capture, serving, and nondefault executor lifecycle remain `planned / not run` or
untested as specified.
