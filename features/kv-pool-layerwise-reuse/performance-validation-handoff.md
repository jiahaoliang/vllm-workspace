---
schema_version: 1
status: READY_FOR_PERFORMANCE_VALIDATION
ready: true
placeholders_remaining: false
generation: 1
updated_at: 2026-08-08T21:08:10+08:00
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
| control repo | `kv-pool-layerwise-reuse` functional control parent | `4afdc30bd6976e34495c773be55f931f0ff4db41` | transition parent pushed as `origin/kv-pool-layerwise-reuse=4afdc30bd6976e34495c773be55f931f0ff4db41` |
| `repos/vllm` | frozen detached dependency | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | `workspace.lock=54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`; commit reachable from `upstream/main` |
| `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `a3c97358ccca51e6d9441c66ea5d4ff1bd1645e7` | `origin/feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723=a3c97358ccca51e6d9441c66ea5d4ff1bd1645e7` |
| `repos/Mooncake` | read-only detached collaborator baseline | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` | `collaborator/feature/layerwise-kv-session=df3f74ed8ebdb0c935554beea6299a9f11c723e2` |

## Image Identity

| Field | Value |
| --- | --- |
| Image delivery mode | `ready-image` |
| Base image reference | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z` |
| Base manifest digest | `sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351` |
| Patched file path | `/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py` |
| Patched file SHA256 | `384fe5c2fd5deb785d151be15edc6c4ae0cd32cce75a2cb502aab802f9420040` |
| Patched source commit | `a3c97358ccca51e6d9441c66ea5d4ff1bd1645e7` |
| Derived image reference | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-a3c97358-df3f74ed-20260808T121828Z` |
| Platform | `linux/arm64` |
| Derived manifest digest | `sha256:32b379315a80c590dbaa563310fe70f8ee15a901abc9a67a9ad18c46fa22ef3c` |
| vLLM source label | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend source label | `a3c97358ccca51e6d9441c66ea5d4ff1bd1645e7` |
| Mooncake source label | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Derived-image/run ID | `20260808T121828Z` |

## Functional Acceptance

| Gate | Required result | Actual result | Evidence |
| --- | --- | --- | --- |
| Focused CPU/mock UT | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z/cpu/pytest-layerwise-model-runner.log`; `cpu/pytest-deployment-performance.log` |
| Complete AscendStore CPU/mock UT | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z/cpu/pytest-ascend-store-and-mla.log` |
| Ruff | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z/cpu/ruff-check.log` |
| Python compilation | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z/cpu/py-compile.log` |
| `git diff --check` | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z/cpu/git-diff-check.log` |
| `kv_producer` Mooncake/NPU correctness | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z/npu/producer-reuse/`; `npu/summary.json` |
| `kv_both` Mooncake/NPU correctness | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z/npu/both-reuse/`; `npu/summary.json` |
| Physical-slot/memory-factor proof | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z/REPORT.md`; `validation-config.json` |
| Reuse-mate save-gate timeout/corruption check | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z/npu/validator.log`; `REPORT.md` |
| Final Mooncake resource cleanup | PASS | PASS | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z/npu/summary.json`; per-case `final-assert.log` |

## Evidence Identity

| Field | Value |
| --- | --- |
| Evidence root | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z` |
| Root `SHA256SUMS` path | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z/SHA256SUMS` |
| Root `SHA256SUMS` digest | `15459826acdfca8e875169cf408dd1c5d80c84c43977ef93e16e7e9d7ed5b603` |
| Functional validation report | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z/REPORT.md` |
| Validation config snapshot | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T121828Z/validation-config.json` |

## Authorized Performance Scope

After this handoff becomes ready, performance validation may use only:

- the exact source and image identities frozen above;
- Mooncake `BULK` with `backend=mooncake` and `use_layerwise=false`;
- Mooncake `LAYERWISE` with `backend=mooncake` and `use_layerwise=true`;
- Prefill `REUSE3` with `backend=mooncake`, `use_layerwise=true`,
  `layerwise_num_shared_buffers=3`, and `kv_producer`;
- the no-reuse pure-consumer Decode companion required by DP1/DP2;
- functional validation of `kv_producer` and `kv_both` roles;
- namespace `liangjiahao`;
- model, topology, hardware and namespace explicitly frozen by the final
  validation config snapshot.

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
4. Increment `generation` from 0 to 1.
5. Set `placeholders_remaining: false` after all placeholder values are gone.
6. Set `updated_at` to the completion timestamp.
7. Set `status: READY_FOR_PERFORMANCE_VALIDATION` and `ready: true` last.
8. Commit only this populated handoff as the direct child of the recorded
   functional control commit and recheck remote identity/reachability.

If a production-source defect or invalid functional run prevents acceptance,
set `status: BLOCKED`, keep `ready: false`, record the blocker below, and leave
all unverified fields fail-closed.

## Blocker

None. The earlier correctness defect is preserved in failure/diagnostic
evidence and resolved by vLLM-Ascend `a3c97358ccca51e6d9441c66ea5d4ff1bd1645e7`.

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
