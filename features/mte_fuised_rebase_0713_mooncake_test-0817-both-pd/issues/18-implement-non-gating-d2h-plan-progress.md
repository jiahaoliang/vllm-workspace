# 18 — 实现 non-gating D2H plan/progress vertical slice

**What to build:** 在已发布sync replacement `7401ae79c`上，把decode-time Main D2H从single-active lifecycle `FUSED_D2H` / `D2H_COMPLETE`改为step-local `DsaD2HStepPlan` / `D2HStepProgress`，打通scheduler issued/confirmed ledger、worker persistent Main binding、每step ephemeral SFA view和`wait_for_save()`后progress的两步non-gating闭环。Sync scheduling与async scheduling共用同一step-local contract。

**Spec:** [Blockwise DSA async-compatible spec](../spec.md)

**Decision basis:** [ADR 0024 — non-gating D2H progress](../docs/adr/0024-use-non-gating-d2h-progress-and-dual-main-watermarks.md)、[ADR 0027 — step-local D2H plan与worker binding](../docs/adr/0027-use-step-local-d2h-plans-and-worker-main-bindings.md)

**Planning decision:** [定义 ADR/spec supersession 与 implementation ticket chain](16-define-doc-supersession-implementation-chain.md)

**Blocked by:** None — can start after explicit source-modification authorization.

**Status:** resolved

## Expected source scope

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py`
- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`
- Existing SFA config/scheduler files only when the persistent binding cannot be expressed through their current adapter boundary.
- Focused tests in existing `tests/ut/kv_offload/` files.

## Acceptance

- [x] `DsaAction` no longer contains `FUSED_D2H`; `DsaLocalResultKind` no longer contains `D2H_COMPLETE`. Receive/failure/replay action-result validation remains exact.
- [x] `DsaConnectorMetadata` carries lifecycle requests and independent immutable D2H step plans without duplicating source, Indexer binding or lifecycle command sequence.
- [x] Each nonempty plan uses a request-local, epoch-local D2H step sequence and records reservation identity, ordered Main bound prefix and continuous token range in an immutable issued ledger.
- [x] Scheduler advances issued watermark when publishing metadata, advances confirmed watermark only from current-epoch exact-TP progress, and does not gate publication of the next model step on prior progress.
- [x] Worker retains persistent Main reservation/epoch/bound-prefix state, rebuilds and clears the ephemeral SFA view every model step, and does not require an active lifecycle command for `get_num_cpu_blocks()`.
- [x] Worker returns rank-aware progress only after `wait_for_save()` succeeds. D2H exception paths do not fabricate progress, transfer failure or ordinary completion.
- [x] Focused CPU/mock tests cover two continuously issued D2H steps, exact-TP progress after save drain, ledger continuity and confirmed watermark advancement. Model execution、Mooncake、SFA kernel与NPU tensor使用fake/mock。
- [x] Existing receive/replay exact-TP behavior and default V1 type isolation remain intact.

## Evidence boundary

This ticket proves only the focused plan/progress vertical slice. It does not claim terminal, preemption, NPU, real Mooncake, fused-kernel or graph-capture validation. Creation of this ticket does not authorize changes under `repos/*`.

## Stop and review

Stop before modifying upstream vLLM core, adding another public connector or production module, introducing a second D2H metadata channel, changing positional ABI/Main reservation policy, or adding watchdog/reliable cancel/fatal-latch behavior.

## Answer

Implemented and published as signed-off source commits `e35170d52e85e4553b120cb697d0281f4f681b1b` and
`db43a232d8ba0fb511983cd75ca04e6c12408bc9`. The final GitCode branch ref was verified at
`db43a232d8ba0fb511983cd75ca04e6c12408bc9`, and the source worktree was clean.

CPU/mock validation ran in the CPU-only `liangjiahao/vllm-ascend-ut` Pod against pinned vLLM
`0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`: metadata plus connector targets were `137 passed`, and
the complete remote-prefill lifecycle file was `6 passed`. `py_compile`, `git diff --check`,
`ruff format --check`, and diff-relevant `ruff check` passed. Independent two-axis review found no
blocking Standards or Spec finding after two ownership fixes were added and revalidated.

This evidence is limited to static and CPU/mock validation of the ticket 18 plan/progress slice.
Terminal, preemption, real Mooncake, NPU, fused kernel, graph capture, and serving remain unvalidated;
the runtime categories remain `planned / not run` where applicable.
