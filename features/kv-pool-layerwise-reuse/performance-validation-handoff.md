---
schema_version: 1
status: READY_FOR_PERFORMANCE_VALIDATION
ready: true
placeholders_remaining: false
generation: 8
updated_at: 2026-08-10T02:38:57+08:00
---

# Mooncake Layerwise Buffer Reuse Performance Validation Handoff

本文件是功能验证 session 与性能验证 session 之间的 fail-closed handoff。
本 generation 已用不可变源码、镜像和功能 evidence 完成验收。

## Listener Contract

性能验证 session 只有在以下条件全部成立时才能开始 preflight 或创建性能 workload：

1. Front matter 同时为
   `status: READY_FOR_PERFORMANCE_VALIDATION` 和 `ready: true`。
2. `generation` 大于 0，且 `placeholders_remaining: false`。
3. `Source Identity` 中的 control commit 等于当前 handoff-only transition
   的直接父提交，三个 nested source commit 与本地 checkout/remote 复核一致。
4. 镜像 platform、manifest digest 和 source labels 与 `Image Identity` 一致。
5. `Functional Acceptance` 所有 required gate 均为 `PASS`。
6. evidence 根 `SHA256SUMS` 回放成功，且 handoff 中记录的 digest 一致。

`WAITING_FOR_FUNCTIONAL_VALIDATION`、`BLOCKED`、缺字段、checksum 不一致或
任一 required gate 非 `PASS` 时必须继续等待，不得从聊天消息推断已经 ready。

## Scope

- Feature: Mooncake support for compute-side
  `layerwise_num_shared_buffers` reuse.
- Validation value: `layerwise_num_shared_buffers=3`.
- Runtime roles required before handoff becomes ready:
  - `kv_producer`
  - `kv_both`
- CPU/mock role coverage:
  - `kv_producer`
  - `kv_both`
  - `kv_consumer + consumer_is_to_put=true`
  - pure `kv_consumer` startup rejection when a non-null
    `layerwise_num_shared_buffers` is configured
- Existing default remains one buffer per layer when
  `layerwise_num_shared_buffers` is absent or null.

## Source Identity

| Component | Branch / role | Commit | Remote equality |
| --- | --- | --- | --- |
| control repo | `kv-pool-layerwise-reuse` performance control parent | `e456668a36b03dd5f9841f5be61b35773c891365` | transition parent pushed as `origin/kv-pool-layerwise-reuse=e456668a36b03dd5f9841f5be61b35773c891365` |
| `repos/vllm` | frozen detached dependency | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | `workspace.lock=54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`; commit reachable from `upstream/main` |
| `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `5355559175f9998f5d70866734fb79569dfc86f9` | `origin/feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723=5355559175f9998f5d70866734fb79569dfc86f9` |
| `repos/Mooncake` | read-only detached collaborator baseline | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` | `collaborator/feature/layerwise-kv-session=df3f74ed8ebdb0c935554beea6299a9f11c723e2` |

## Image Identity

| Field | Value |
| --- | --- |
| Image delivery mode | `ready-image` |
| Base image reference | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z` |
| Base manifest digest | `sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351` |
| Patched file path | `/vllm-workspace/vllm-ascend/vllm_ascend/attention/mla_v1.py,/vllm-workspace/vllm-ascend/vllm_ascend/attention/utils.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/ascend_store_connector.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py` |
| Patched file SHA256 | `7b80604faad9d32750aa072d0540536d6e376a95f158a6e7483af7a9e445d44f` |
| Patched source commit | `5355559175f9998f5d70866734fb79569dfc86f9` |
| Derived image reference | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-535555917-df3f74ed-20260809T070557Z` |
| Platform | `linux/arm64` |
| Derived manifest digest | `sha256:cf5da7c1da7dcb72f4c22e201d628b9e4aa819f53c15711651ebc9241cb955bc` |
| Derived config digest | `sha256:b138ce816ae0b4183f77a6e9b83bc95061a6c1053f770d2f0462699de86a7a0c` |
| vLLM source label | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend source label | `5355559175f9998f5d70866734fb79569dfc86f9` |
| Mooncake source label | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Derived-image/run ID | `20260809T070557Z` |

## Functional Acceptance

| Gate | Required result | Actual result | Evidence |
| --- | --- | --- | --- |
| Focused CPU/mock UT | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/cpu/pytest-non-save-owner.log`; `cpu/pytest-layerwise-roles.log`; `cpu/pytest-mla-decode-load.log`; `cpu/pytest-model-runner-layer-reuse.log`; `cpu/pytest-deployment-performance.log`; `cpu/pytest-performance-harness.log` |
| Complete AscendStore CPU/mock UT | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/cpu/pytest-ascend-store.log` |
| Ruff | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/cpu/ruff-check.log`; `cpu/ruff-format.log` |
| Python compilation | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/cpu/python-compile.log` |
| `git diff --check` | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/cpu/source-diff-check.log`; `cpu/control-diff-check.log` |
| `kv_producer` Mooncake/NPU correctness | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/npu/producer-reuse/`; `npu/summary.json` |
| `kv_both` Mooncake/NPU correctness | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/npu/both-reuse/`; `npu/summary.json` |
| Physical-slot/memory-factor proof | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/REPORT.md`; `validation-config.json`; `npu/producer-reuse/vllm-prefill.log`; `npu/pure-consumer-canary/prefill-runtime.json` |
| Reuse-mate save-gate timeout/corruption check | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/npu/validator.log`; `npu/pure-consumer-canary/validator.log`; `REPORT.md` |
| Exact 4096-token pure-consumer Decode canary | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/npu/pure-consumer-canary/summary.json`; `npu/pure-consumer-canary/validator.log` |
| Final Mooncake resource cleanup | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/npu/summary.json`; per-case `final-assert.log`; `npu/pure-consumer-canary/final.metrics` |
| Performance runtime capacity CPU/mock | PASS | PASS | control parent `e456668a36b03dd5f9841f5be61b35773c891365`; `deployment/performance/tests/test_runtime.py`; complete performance harness `69 passed`; AISBench 3.1.0 `build_dataset_from_cfg` smoke accepted 8-request metadata; pinned `BaseAPIModel.infer` source confirms `retry=1` sends one total attempt; live idle-engine HBM probe returned no errors |

## Evidence Identity

| Field | Value |
| --- | --- |
| Evidence root | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z` |
| Root `SHA256SUMS` path | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/SHA256SUMS` |
| Root `SHA256SUMS` digest | `e8cf5ce3fbf332dada8c9bfeb6fd1d3ececc6f02b96fe4a0a5b28b6e1b556876` |
| Functional validation report | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/REPORT.md` |
| Validation config snapshot | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260809T071622Z/validation-config.json` |

## Authorized Performance Scope

After this handoff becomes ready, performance validation may use only:

- the exact source and image identities frozen above;
- Mooncake `BULK` with `backend=mooncake` and `use_layerwise=false`;
- Mooncake `LAYERWISE` with `backend=mooncake` and `use_layerwise=true`;
- Prefill `REUSE3` with `backend=mooncake`, `use_layerwise=true`,
  `layerwise_num_shared_buffers=3`, and `kv_producer`;
- the no-reuse pure-consumer Decode companion required by DP1;
- `MOONCAKE_GLOBAL_SEGMENT_SIZE=128GB` on every Prefill and Decode serving
  rank, identical across BULK, LAYERWISE, and REUSE3;
- functional validation of `kv_producer` and `kv_both` roles;
- namespace `liangjiahao`;
- model `vllm-ascend/DeepSeek-V2-Lite-W8A8`;
- DP1 only, 16384 input tokens, concurrency 8;
- exactly five points: BULK o128/o1, LAYERWISE o128/o1, and REUSE3 o1;
- one 8-request warmup wave and one 8-request formal wave per point;
- `DefaultPerfMetricCalculator`, `total` stage, one formal repetition, and no
  automatic retry;
- AISBench `sampling_mode=default`; single-wave and total-stage semantics are
  frozen by `run-contract.json`, not encoded as a custom AISBench sample mode;
- AISBench `retry=1`, whose pinned implementation iterates `range(retry)`;
  therefore exactly one request attempt is sent and no retry occurs;
- three server starts in BULK, LAYERWISE, REUSE3 order;
- after each variant stop, wait until every visible NPU reports no more than
  4096 MB HBM usage before applying the next variant;
- 10-second point telemetry, lightweight point diagnostics, and complete
  Prefill/Decode logs once per variant;
- no performance timeout; a valid slow point continues naturally;
- hardware and namespace explicitly frozen by the final validation config
  snapshot.

Performance validation must create its own run ID, plan, thresholds, raw evidence
and checksum manifest. Functional correctness evidence in this handoff is not a
throughput or latency claim.

## Explicit Exclusions

This handoff does not authorize or claim coverage for:

- pure `kv_consumer` buffer reuse;
- real-NPU `kv_consumer + consumer_is_to_put=true` buffer reuse;
- memcache behavior or memcache performance regression;
- unsupported CP, TP-mismatch or hybrid layouts;
- FabricMem, A3, or hardware not named in the final config snapshot;
- Mooncake multi-group behavior unless the final handoff explicitly adds it;
- any throughput, latency, scaling or capacity result before the performance
  session produces its own evidence.

## Ready Transition

The functional-validation session must update this file in one final step:

1. Replace every placeholder with verified immutable values.
2. Record all required gates as `PASS`.
3. Replay the evidence checksum manifest.
4. Increment `generation` monotonically for every new immutable handoff.
5. Set `placeholders_remaining: false` after all placeholder values are gone.
6. Set `updated_at` to the completion timestamp.
7. Set `status: READY_FOR_PERFORMANCE_VALIDATION` and `ready: true` last.
8. Commit only this populated handoff as the direct child of the recorded
   functional control commit and recheck remote identity/reachability.

If a production-source defect or invalid functional run prevents acceptance,
set `status: BLOCKED`, keep `ready: false`, record the blocker below, and leave
all unverified fields fail-closed.

## Blocker

None. The TP2 REUSE3 non-save-owner save-gate defect is preserved in the
diagnostic performance root `/tmp/layerwise-performance-20260809T010429Z` and
resolved by vLLM-Ascend
`5355559175f9998f5d70866734fb79569dfc86f9`. Generation-8 retains the
generation-4 functional evidence and
includes both the real-thread TP non-save-owner CPU regression and an exact
4096-token TP2 REUSE3 producer to pure-consumer Decode NPU canary.

The invalid performance root `/tmp/layerwise-performance-20260809T010429Z`
must not be resumed. Generation 8 also rejects the diagnostic roots
`/tmp/layerwise-performance-rapid-20260809T170330Z` and
`/tmp/layerwise-performance-rapid-20260809T170900Z`; the latter exposed and
preserves the unsupported AISBench sample-mode failure. The diagnostic root
`/tmp/layerwise-performance-rapid-20260809T172651Z` proves `retry=0` sends no
requests in pinned AISBench 3.1.0. The diagnostic roots
`/tmp/layerwise-performance-rapid-20260809T174335Z` and
`/tmp/layerwise-performance-rapid-20260809T175640Z` preserve asynchronous NPU
HBM-release failures during startup/variant switch; the latter contains four
valid formal points but is incomplete and cannot be combined with another run.
Generation 8 freezes the corrected rapid five-point contract and
128 GiB per serving rank, and requires a new performance run root.

## Listener Message Template

```text
Mooncake layerwise_num_shared_buffers=3 functional validation handoff changed.

Read and verify:
/root/ljh/vllm-workspace/features/kv-pool-layerwise-reuse/performance-validation-handoff.md

Start performance-validation preflight only when status is
READY_FOR_PERFORMANCE_VALIDATION, ready is true, generation is greater than 0,
placeholders_remaining is false, and all recorded identities/checksums replay.
Do not infer readiness from this message alone.
```
