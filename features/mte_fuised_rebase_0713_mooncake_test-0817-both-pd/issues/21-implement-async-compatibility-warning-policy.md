# 21 — 实现 async compatibility warning与unverified startup policy

**What to build:** 只把default `MultiprocExecutor`与default `AsyncScheduler`分类为首版validation target。其他executor/scheduler组合允许启动，但warning必须列出实际类型并标记`unverified` / “未测试”；speculative config同样允许启动，但当前不增加validation、correctness适配或support claim。

**Spec:** [Blockwise DSA async-compatible spec](../spec.md)

**Decision basis:** [ADR 0028 — speculative startup](../docs/adr/0028-allow-unvalidated-speculative-blockwise-dsa-startup.md)、[ADR 0029 — default executor/scheduler validation boundary](../docs/adr/0029-validate-only-default-multiproc-and-async-scheduler.md)

**Planning decision:** [定义 ADR/spec supersession 与 implementation ticket chain](16-define-doc-supersession-implementation-chain.md)

**Blocked by:** None — may proceed in parallel after explicit source-modification authorization.

**Status:** resolved

## Expected source scope

- Existing Blockwise DSA startup/configuration path in `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`.
- Focused startup tests in the existing Mooncake connector test file.

## Acceptance

- [x] Default `MultiprocExecutor` + default `AsyncScheduler` starts without an unverified warning.
- [x] Any nondefault executor or scheduler still starts, emits a warning containing both actual type names and the exact unverified/“未测试” classification, and does not infer support from topology or upstream capability methods.
- [x] Executor classification remains independent from P/D DP/TP topology.
- [x] Speculative config is not rejected by the Blockwise DSA startup or metadata boundary. No speculative-specific metadata logic, D2H reconciliation or lifecycle correctness claim is added.
- [x] Focused smoke tests cover default no-warning and one nondefault warning path. Speculative config is not tested in this version.

## Evidence boundary

The warning smoke is not lifecycle validation for the nondefault combination. Speculative and nondefault executor/scheduler lifecycle remain“未测试”。Creation of this ticket does not authorize changes under `repos/*`.

## Stop and review

Stop before building speculative reconciliation, adding executor-specific lifecycle branches, rejecting an unverified combination, or upgrading any combination beyond the exact evidence available.

## Answer

Implemented and published as signed-off source commit `60e50b036abdfa96575f6cc08281535ea0012351`.
The GitCode branch ref was live-verified at the same SHA, and the source worktree was clean.

Ticket 22's real `MultiprocExecutor` startup gate later exposed a missing DSA Decode worker-handshake
setter. The ticket 21 owner fixed that startup defect in signed-off commit
`ffbafcc1e13c3c412918135e3cfbedc15a15ae6d`: DSA Decode accepts and ignores local Decode-worker
handshake metadata, while request positional metadata remains the Prefill endpoint source and the
Prefill/default V1 aggregation path is unchanged. The focused regression was `1 passed`, the complete
connector target was `124 passed`, and an independent two-axis review reported zero findings.

The CPU-only `liangjiahao/vllm-ascend-ut` Pod produced the expected focused red (`2 failed`) against
the old startup behavior and green (`2 passed`) after implementation. The complete connector target
was `123 passed`. Python compile, `git diff --check`, and `git show --check` passed; `ruff` was not
available in the host or Pod environment and was not claimed. Independent two-axis review found no
blocking issue; it retained one Low/non-blocking gap because the smoke test checks class-name substrings
rather than the complete fully-qualified warning strings.

The nondefault warning smoke is not lifecycle validation. Speculative, nondefault lifecycle, real
Mooncake, NPU, fused kernel, graph capture, and serving remain untested or `planned / not run`.
