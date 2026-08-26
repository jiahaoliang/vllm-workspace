# 20 — 实现 async preemption replay barrier

**What to build:** 为queued old-epoch D2H建立preemption validity cut与new-epoch `PREPARE_REPLAY` barrier。Cut只保留当时已消费的confirmed Main prefix；old-epoch late progress不能扩大该prefix。New Indexer ownership rebind和exact-TP `REPLAY_READY`完成后，才允许token-0 replay覆盖未确认suffix。

**Spec:** [Blockwise DSA async-compatible spec](../spec.md)

**Decision basis:** [ADR 0026 — epoch cut与PREPARE_REPLAY barrier](../docs/adr/0026-use-epoch-cut-and-prepare-replay-barrier.md)、[ADR 0009 — Decode full compute replay](../docs/adr/0009-replay-preempted-requests-locally-on-decode.md)、[ADR 0013 — transfer failure invalidates all TP Main](../docs/adr/0013-invalidate-main-on-all-tps-for-transfer-failure-replay.md)

**Planning decision:** [定义 ADR/spec supersession 与 implementation ticket chain](16-define-doc-supersession-implementation-chain.md)

**Blocked by:** 18 — 实现 non-gating D2H plan/progress vertical slice.

**Status:** resolved

## Expected source scope

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`
- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py` only if existing replay identity validation needs the async epoch binding.
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`

## Acceptance

- [x] First active-epoch preemption evidence atomically snapshots confirmed prefix `P`, seals old ledger and increments execution epoch once; repeated evidence before resumed compute is idempotent.
- [x] Old-epoch progress after the cut is observable and ignored after base validation, and cannot mutate `P` or resurrect a retired ledger.
- [x] New epoch starts with issued/confirmed watermark `P`, empty ledger and a fresh epoch-local D2H sequence namespace; uncertain continuity falls back to `P=0`.
- [x] `PREPARE_REPLAY` is published only after core supplies resumed Indexer allocation/rebind. Worker drains old operations, replaces ownership binding and returns exact-TP `REPLAY_READY` before replay is admitted.
- [x] Replay rebuilds Indexer from token 0 and skips Main D2H only for `[0, P)`. Transfer-failure replay remains same-epoch with `P=0`.
- [x] Terminal intent during preemption-pending switches to latest-epoch `QUIESCE`; late `REPLAY_READY` cannot reopen replay.
- [x] Modified Python files pass import/compile/static checks. No new preemption runtime test is mandatory in this initial version; Preemption remains“未测试”。

## Evidence boundary

Implementation completion is not a preemption validation claim. NPU、real Mooncake、late-progress runtime and graph capture remain unexecuted. Creation of this ticket does not authorize changes under `repos/*`.

## Stop and review

Stop before modifying upstream vLLM core, adding a new replay cause/result kind, recovering preserved validity from late progress, or weakening ADR 0016 ownership isolation.

## Answer

Implemented and published as signed-off source commits `9053bd1d532b9010595a7cb167dbe7a0fecd0765`
and `4fbd759c7cd2806ee55410c6e1e695aebf5ed8f5`. The final GitCode branch ref was verified at
`4fbd759c7cd2806ee55410c6e1e695aebf5ed8f5`, and the source worktree was clean.

Focused deterministic CPU/mock tests covered cut-time `P`, stale old-epoch progress, repeated evidence
before resumed compute, fresh epoch-local D2H sequence, same-ID Indexer rebind, old-D2H drain before
`REPLAY_READY`, exact-once ready, latest-epoch `QUIESCE`, and terminal dominance over late rebind/result.
In the CPU-only `liangjiahao/vllm-ascend-ut` Pod, metadata plus connector targets were `145 passed`,
the A2 lifecycle file was `6 passed`, and the broad kv_offload root excluding the known baseline-broken
file was `228 passed`. `py_compile`, `git diff --check`, `ruff format --check`, and production
`ruff check` passed. Independent two-axis rereview found no blocking finding.

This evidence verifies focused CPU/mock state transitions but does not expand the canonical runtime
claim: Preemption remains “未测试”. NPU, real Mooncake, fused kernel, graph capture, serving, and
nondefault executor lifecycle remain `planned / not run` or untested as specified.
