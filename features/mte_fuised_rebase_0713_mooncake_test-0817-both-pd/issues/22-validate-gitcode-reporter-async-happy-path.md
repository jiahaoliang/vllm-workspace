# 22 — 验证 GitCode reporter async happy path

**What to build:** 用最小CPU/mock integration harness验证GitCode Issue #1 reporter的`P DP2/TP8 -> D DP2/TP8`单请求happy path。Harness使用真实`AsyncScheduler`与EngineCore depth-2 queue、production DSA scheduler/worker connector和default executor/scheduler classification，同时fake/mock model execution、Mooncake、SFA kernel、NPU tensor与executor worker process。

**Spec:** [Blockwise DSA async-compatible spec](../spec.md)

**Decision basis:** [ADR 0030 — reporter async happy path gate](../docs/adr/0030-validate-only-the-gitcode-reporter-async-happy-path.md)、[ADR 0029 — default executor/scheduler boundary](../docs/adr/0029-validate-only-default-multiproc-and-async-scheduler.md)

**Planning decision:** [定义 ADR/spec supersession 与 implementation ticket chain](16-define-doc-supersession-implementation-chain.md)

**Blocked by:** 18, 19, 20, 21.

**Status:** open

## Expected test and evidence scope

- One focused async happy-path test file or an equivalently isolated existing test section under `tests/ut/kv_offload/`.
- Existing sync DSA happy-path、default V1 isolation与startup warning smoke targets。
- A concise feature-local async happy-path validation report created only after execution.
- No production feature expansion in this ticket. Production defects return to the owning implementation ticket or trigger stop-and-review.

## Mandatory gate

- [ ] A single request first completes `RECEIVE_REMOTE` for each routed Decode DP replica.
- [ ] Real `AsyncScheduler` and EngineCore queue publish two consecutive Decode model steps before the first output is consumed; observed queue depth reaches exactly 2.
- [ ] Default `MultiprocExecutor` + default `AsyncScheduler` classification is active. Executor worker processes themselves are fake/mock.
- [ ] Production DSA scheduler/worker connector publishes step-local D2H plans, and each step returns rank-aware progress only after fake SFA `wait_for_save()`.
- [ ] Exact TP8 progress advances confirmed watermark across both continuous ranges without using cross-DP aggregation.
- [ ] Decode DP rank 0 and rank 1 are exercised separately with independent TP rank sets.
- [ ] Normal finish emits a FIFO `QUIESCE` tail marker, reaches ordinary all-worker completion and releases Main reservation exactly once.
- [ ] Sync DSA happy-path smoke、default V1 isolation smoke与nondefault startup warning smoke pass in the same source identity.
- [ ] Static checks for modified files pass.

## Execution requirements

- Use the `liangjiahao` namespace CPU-only UT Pod required by workspace `AGENTS.md` when the Kubernetes execution environment is available.
- Record vLLM-Ascend branch、commit、dirty state、vLLM commit、explicit test targets and results. Disable bytecode and pytest cache in the synchronized checkout.
- Do not request or mount NPU resources. Do not run real Mooncake transfer, fused kernel or graph-capture runtime.
- A broad CPU/mock root or complete Phase B rerun is not required.

## Allowed final claim

Only after every mandatory gate passes:

`GitCode reporter happy path 已通过 CPU/mock validation`

Do not write `async CPU/mock validated`, reporter deployment passed, NPU validated, Mooncake transfer validated, fused kernel validated or graph-capture validated.

Preemption、abort、D2H failure、late progress、adversarial metadata、多请求交错、`P TP8 -> D TP2`、speculative config与非默认executor/scheduler lifecycle只写“未测试”。NPU、真实Mooncake、fused kernel与graph-capture保持`planned / not run`。

## Stop and review

Stop before modifying upstream vLLM core, adding NPU or serving workloads, expanding the validation claim, or hiding a production defect behind a test-only bypass.
