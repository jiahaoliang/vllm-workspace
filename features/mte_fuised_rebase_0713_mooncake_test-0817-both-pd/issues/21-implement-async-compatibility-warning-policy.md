# 21 — 实现 async compatibility warning与unverified startup policy

**What to build:** 只把default `MultiprocExecutor`与default `AsyncScheduler`分类为首版validation target。其他executor/scheduler组合允许启动，但warning必须列出实际类型并标记`unverified` / “未测试”；speculative config同样允许启动，但当前不增加validation、correctness适配或support claim。

**Spec:** [Blockwise DSA async-compatible spec](../spec.md)

**Decision basis:** [ADR 0028 — speculative startup](../docs/adr/0028-allow-unvalidated-speculative-blockwise-dsa-startup.md)、[ADR 0029 — default executor/scheduler validation boundary](../docs/adr/0029-validate-only-default-multiproc-and-async-scheduler.md)

**Planning decision:** [定义 ADR/spec supersession 与 implementation ticket chain](16-define-doc-supersession-implementation-chain.md)

**Blocked by:** None — may proceed in parallel after explicit source-modification authorization.

**Status:** open

## Expected source scope

- Existing Blockwise DSA startup/configuration path in `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`.
- Focused startup tests in the existing Mooncake connector test file.

## Acceptance

- [ ] Default `MultiprocExecutor` + default `AsyncScheduler` starts without an unverified warning.
- [ ] Any nondefault executor or scheduler still starts, emits a warning containing both actual type names and the exact unverified/“未测试” classification, and does not infer support from topology or upstream capability methods.
- [ ] Executor classification remains independent from P/D DP/TP topology.
- [ ] Speculative config is not rejected by the Blockwise DSA startup or metadata boundary. No speculative-specific metadata logic, D2H reconciliation or lifecycle correctness claim is added.
- [ ] Focused smoke tests cover default no-warning and one nondefault warning path. Speculative config is not tested in this version.

## Evidence boundary

The warning smoke is not lifecycle validation for the nondefault combination. Speculative and nondefault executor/scheduler lifecycle remain“未测试”。Creation of this ticket does not authorize changes under `repos/*`.

## Stop and review

Stop before building speculative reconciliation, adding executor-specific lifecycle branches, rejecting an unverified combination, or upgrading any combination beyond the exact evidence available.
