---
schema_version: 1
status: WAITING_FOR_FUNCTIONAL_VALIDATION
ready: false
placeholders_remaining: true
generation: 0
updated_at: 2026-08-08T11:47:33+08:00
---

# Mooncake Layerwise Buffer Reuse Performance Validation Handoff

本文件是功能验证 session 与性能验证 session 之间的 fail-closed handoff。
当前仅提供框架；所有 `PENDING` 字段都必须在功能验收完成后用不可变证据替换。

## Listener Contract

性能验证 session 只有在以下条件全部成立时才能开始 preflight 或创建性能 workload：

1. Front matter 同时为
   `status: READY_FOR_PERFORMANCE_VALIDATION` 和 `ready: true`。
2. `generation` 大于 0，且 `placeholders_remaining: false`。
3. `Source Identity` 中的四个 commit 与本地 checkout/remote 复核一致。
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
| control repo | `kv-pool-layerwise-reuse` | `PENDING` | `PENDING` |
| `repos/vllm` | frozen dependency | `PENDING` | `PENDING` |
| `repos/vllm-ascend` | implementation branch | `PENDING` | `PENDING` |
| `repos/Mooncake` | read-only collaborator baseline | `PENDING` | `PENDING` |

## Image Identity

| Field | Value |
| --- | --- |
| Image reference | `PENDING` |
| Platform | `PENDING` |
| Manifest digest | `PENDING` |
| vLLM source label | `PENDING` |
| vLLM-Ascend source label | `PENDING` |
| Mooncake source label | `PENDING` |
| Build/run ID | `PENDING` |

## Functional Acceptance

| Gate | Required result | Actual result | Evidence |
| --- | --- | --- | --- |
| Focused CPU/mock UT | PASS | `PENDING` | `PENDING` |
| Complete AscendStore CPU/mock UT | PASS | `PENDING` | `PENDING` |
| Ruff | PASS | `PENDING` | `PENDING` |
| Python compilation | PASS | `PENDING` | `PENDING` |
| `git diff --check` | PASS | `PENDING` | `PENDING` |
| `kv_producer` Mooncake/NPU correctness | PASS | `PENDING` | `PENDING` |
| `kv_both` Mooncake/NPU correctness | PASS | `PENDING` | `PENDING` |
| Physical-slot/memory-factor proof | PASS | `PENDING` | `PENDING` |
| Reuse-mate save-gate timeout/corruption check | PASS | `PENDING` | `PENDING` |
| Final Mooncake resource cleanup | PASS | `PENDING` | `PENDING` |

## Evidence Identity

| Field | Value |
| --- | --- |
| Evidence root | `PENDING` |
| Root `SHA256SUMS` path | `PENDING` |
| Root `SHA256SUMS` digest | `PENDING` |
| Functional validation report | `PENDING` |
| Validation config snapshot | `PENDING` |

## Authorized Performance Scope

After this handoff becomes ready, performance validation may use only:

- the exact source and image identities frozen above;
- `backend=mooncake` and `use_layerwise=true`;
- `layerwise_num_shared_buffers=3`;
- `kv_producer` and `kv_both` roles;
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

1. Replace every `PENDING` with verified immutable values.
2. Record all required gates as `PASS`.
3. Replay the evidence checksum manifest.
4. Increment `generation` from 0 to 1.
5. Set `placeholders_remaining: false` after all placeholder values are gone.
6. Set `updated_at` to the completion timestamp.
7. Set `status: READY_FOR_PERFORMANCE_VALIDATION` and `ready: true` last.
8. Commit the populated handoff together with, or after, the final validation
   report and recheck remote equality.

If a production-source defect or invalid functional run prevents acceptance,
set `status: BLOCKED`, keep `ready: false`, record the blocker below, and leave
all unverified fields fail-closed.

## Blocker

`PENDING`

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
