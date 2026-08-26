# 20 — 实现 async preemption replay barrier

**What to build:** 为queued old-epoch D2H建立preemption validity cut与new-epoch `PREPARE_REPLAY` barrier。Cut只保留当时已消费的confirmed Main prefix；old-epoch late progress不能扩大该prefix。New Indexer ownership rebind和exact-TP `REPLAY_READY`完成后，才允许token-0 replay覆盖未确认suffix。

**Spec:** [Blockwise DSA async-compatible spec](../spec.md)

**Decision basis:** [ADR 0026 — epoch cut与PREPARE_REPLAY barrier](../docs/adr/0026-use-epoch-cut-and-prepare-replay-barrier.md)、[ADR 0009 — Decode full compute replay](../docs/adr/0009-replay-preempted-requests-locally-on-decode.md)、[ADR 0013 — transfer failure invalidates all TP Main](../docs/adr/0013-invalidate-main-on-all-tps-for-transfer-failure-replay.md)

**Planning decision:** [定义 ADR/spec supersession 与 implementation ticket chain](16-define-doc-supersession-implementation-chain.md)

**Blocked by:** 18 — 实现 non-gating D2H plan/progress vertical slice.

**Status:** open

## Expected source scope

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`
- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py` only if existing replay identity validation needs the async epoch binding.
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`

## Acceptance

- [ ] First active-epoch preemption evidence atomically snapshots confirmed prefix `P`, seals old ledger and increments execution epoch once; repeated evidence before resumed compute is idempotent.
- [ ] Old-epoch progress after the cut is observable and ignored after base validation, and cannot mutate `P` or resurrect a retired ledger.
- [ ] New epoch starts with issued/confirmed watermark `P`, empty ledger and a fresh epoch-local D2H sequence namespace; uncertain continuity falls back to `P=0`.
- [ ] `PREPARE_REPLAY` is published only after core supplies resumed Indexer allocation/rebind. Worker drains old operations, replaces ownership binding and returns exact-TP `REPLAY_READY` before replay is admitted.
- [ ] Replay rebuilds Indexer from token 0 and skips Main D2H only for `[0, P)`. Transfer-failure replay remains same-epoch with `P=0`.
- [ ] Terminal intent during preemption-pending switches to latest-epoch `QUIESCE`; late `REPLAY_READY` cannot reopen replay.
- [ ] Modified Python files pass import/compile/static checks. No new preemption runtime test is mandatory in this initial version; Preemption remains“未测试”。

## Evidence boundary

Implementation completion is not a preemption validation claim. NPU、real Mooncake、late-progress runtime and graph capture remain unexecuted. Creation of this ticket does not authorize changes under `repos/*`.

## Stop and review

Stop before modifying upstream vLLM core, adding a new replay cause/result kind, recovering preserved validity from late progress, or weakening ADR 0016 ownership isolation.
