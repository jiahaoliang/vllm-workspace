# Blockwise DSA Async Reporter Happy-Path CPU/Mock Validation Report

Validated At: 2026-08-27T03:42:15+08:00

## Conclusion

`GitCode reporter happy path 已通过 CPU/mock validation`.

This claim is limited to the ticket 22 mandatory gate. It is not a claim that all async scheduling,
the reporter deployment, real Mooncake, NPU, fused kernel, graph capture, or serving passed.

## Source Identity

| Item | Identity |
| --- | --- |
| vLLM-Ascend branch | `feature/blockwise-dsa-mooncake-v1-reimplementation` |
| Validated and published HEAD | `e61dacccc27ee965410c60c0d8cedaf38d66ccc6` |
| Async delta base | `7401ae79c11d6ec0033ea3ac39085379a0bb81ef` |
| Pinned vLLM | `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` |
| Pinned Mooncake source | `6041a609a8c3af35e778f70db344f145c2914980` |
| Final test file SHA256 | `fbc20026d117fee69f8d533b63af1aaedc1867b67c0a45419acf2f08535856ba` |

The source worktree was clean. The GitCode remote ref was live-verified at the same final HEAD.

## CPU/Mock Environment

| Item | Value |
| --- | --- |
| Kubernetes context | `bke-cluster-kubernetes-admin@bke-cluster` |
| Namespace / Pod | `liangjiahao` / `vllm-ascend-ut` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1` |
| Image ID | `sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57` |
| Pod source workspace | `/workspace/ticket22-60e50b-red` |
| Pod vLLM workspace | `/workspace/ticket22-vllm-0fc695fc` |
| NPU resources / mounts | none |

The source was synchronized through a temporary Pod workspace rather than hostPath. Bytecode and
pytest cache were disabled. The existing CPU/mock dependency directory and bootstrap supplied
`gguf==0.18.0`, fake `torch_npu` metadata, and a stubbed C++ extension loader; they did not modify the
source checkout or load NPU libraries.

## Mandatory Gate

| Requirement | Evidence | Result |
| --- | --- | --- |
| Reporter topology | Production config/routing facts produced `P DP2/TP8 -> D DP2/TP8` | PASS |
| Per-DP receive | DP0 and DP1 each completed one exact-TP8 `RECEIVE_REMOTE` independently | PASS |
| Queue depth | Real `AsyncScheduler` and `EngineCore.step_with_batch_queue()` observed depth exactly 2 | PASS |
| Two steps before output | Two production D2H plans were published before the first D2H output was consumed | PASS |
| Default executor/scheduler | Real resolver selected `MultiprocExecutor` and `AsyncScheduler`; only worker process/transport boundaries were fake | PASS |
| Progress after save | Eight production worker connectors emitted rank-aware progress only after fake SFA `wait_for_save()` | PASS |
| Continuous exact TP | Ranges `[16,17)` and `[17,18)` each covered TP ranks 0-7 and advanced confirmed watermark to 18 | PASS |
| DP isolation | DP0 and DP1 used independent request IDs, worker fleets, rank sets, and aggregators | PASS |
| Normal finish | Request-specific trace proved `QUIESCE` after prior request work, all-worker completion, then release exactly once | PASS |
| Same-source smokes | Sync exact-TP receive, default V1 initialization, default async no-warning, and nondefault warning targets passed | PASS |
| Static | Supervisor `py_compile` and `git diff --check` passed; implementation run also reported ruff format/lint pass | PASS |

The harness uses real `MultiprocExecutor` driver methods, `FutureWrapper`, and `KVOutputAggregator`.
Fakes replace only worker process/message transport, model execution, Mooncake transport, SFA kernel,
and NPU tensor boundaries. Independent final review reported zero Spec findings and no blocking issue.

## Test Result

Supervisor reran the focused integration file and four named smoke targets in the CPU-only Pod:

- `tests/ut/kv_offload/test_mooncake_dsa_async_happy_path.py`
- `TestMooncakeConnector::test_decode_receive_completes_only_after_exact_tp_coverage`
- `TestMooncakeConnector::test_scheduler_initialization`
- `TestMooncakeConnector::test_dsa_default_async_pair_starts_without_unverified_warning`
- `TestMooncakeConnector::test_dsa_nondefault_pair_starts_with_actual_type_warning`

```text
5 passed, 14 warnings in 1.82s
```

The warnings were the existing `torch.jit.script_method` deprecation warnings from the CPU/mock
environment. Host and Pod copies of the integration test had the same SHA256 before execution.

## Evidence Boundary

Preemption, abort, D2H failure, late progress, adversarial metadata, multi-request interleaving,
`P TP8 -> D TP2`, speculative configuration, and nondefault executor/scheduler lifecycle remain
“未测试”. NPU, real Mooncake transfer, fused kernel, graph capture, serving, cache contents, and
performance remain `planned / not run`.
