# Mooncake Layerwise Shared-Buffer Reuse Design

## Status

Approved in design review on 2026-08-08. This document defines the first
implementation and validation scope; it does not claim that the implementation
or validation has completed.

## Context

`layerwise_num_shared_buffers` lets non-independent transformer layers
time-multiplex a bounded set of NPU KV-cache storage slots. The current compute
gate in `get_gva_layerwise_config()` only returns configuration for
`backend=memcache,use_layerwise=true`. Mooncake already has the layerwise
session/range transfer and reuse-mate save-gate machinery, but its configuration
does not reach NPU memory accounting or `KVCacheTensor` descriptor merging.

The first Mooncake version intentionally supports only roles that already
publish the save-completion event consumed by the existing reuse-mate gate. It
does not redesign slot release for a pure consumer.

## Goals

1. Let `backend=mooncake,use_layerwise=true` use the existing compute-side
   shared-buffer path when `layerwise_num_shared_buffers` enables effective
   reuse.
2. Support these save-capable configurations:
   - `kv_producer`;
   - `kv_both`;
   - `kv_consumer` with `consumer_is_to_put=true`.
3. Preserve the existing default: an absent or null
   `layerwise_num_shared_buffers` keeps one physical buffer per layer.
4. Reject a pure `kv_consumer` at startup when it supplies a non-null
   `layerwise_num_shared_buffers`.
5. Reuse the existing storage layout, memory-factor, tensor-merge, transfer and
   save-gate implementations without changing their public interfaces.
6. Produce a fail-closed functional-to-performance handoff after correctness
   validation passes.

## Non-Goals

- Implementing pure `kv_consumer` slot release or buffer reuse.
- Changing memcache behavior.
- Changing `Backend`, `MemcacheBackend` or `MooncakeBackend` APIs.
- Changing `KVPoolWorker`, `KVPoolScheduler`, `NPUWorker`, `NPUModelRunner`,
  connector or transfer-thread behavior.
- Defining simultaneous memcache and Mooncake selection in one
  `MultiConnector`; the deployment contract uses at most one applicable
  AscendStore backend.
- Expanding CP, TP-mismatch, hybrid-layout, multi-group, FabricMem, A3 or
  hardware support.
- Making throughput, latency, capacity or scaling claims during functional
  validation.

## Design

### Production Change Surface

The only required production change is in
`vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py`.
The expected production delta is approximately 5-15 lines. No new policy class,
Backend capability interface or constructor parameter is introduced.

### Connector Selection

`get_gva_layerwise_config()` retains its existing direct-connector and
`MultiConnector` traversal. For each recognized `AscendStoreConnector` or
`MooncakeConnectorStoreV1` candidate:

1. Read `backend`, defaulting to `mooncake` as today.
2. Skip the candidate unless `use_layerwise=true`.
3. Accept `backend` values `memcache` and `mooncake`.
4. Return the first matching candidate.

No priority, conflict detection or compatibility behavior is added for a
configuration containing both backends.

### Role Gate

Memcache follows the existing path without a new role check.

Before returning a Mooncake candidate, inspect `kv_role` and
`consumer_is_to_put` using the existing save-capable predicate:

```text
kv_role in {kv_producer, kv_both} OR consumer_is_to_put=true
```

For a pure `kv_consumer`:

- if `layerwise_num_shared_buffers` is absent or null, return the Mooncake
  configuration; the existing parser defaults the shared-buffer count to the
  physical layer count, so effective reuse remains disabled;
- if `layerwise_num_shared_buffers` is non-null, raise `ValueError` before
  serving starts.

The error identifies `backend=mooncake`, the unsupported pure-consumer role and
the first-version save-capable restriction. It tells the operator to remove
`layerwise_num_shared_buffers` or select a save-capable role. The check is
deliberately conservative: it rejects any non-null value without trying to
derive the final physical layer count at this early configuration boundary.

### Existing Data Path Reuse

Once the Mooncake configuration is returned, all behavior remains on existing
paths:

1. `NPUWorker` calculates physical slots and scales the logical KV-memory budget.
2. `NPUModelRunner` groups physical layers and merges `KVCacheTensor.shared_by`
   descriptors before allocation.
3. `KVPoolScheduler` and `KVPoolWorker` parse the same extra configuration and
   construct the existing `layerwise_offload`, independent-layer and
   `prefetch_layer_map` state.
4. Mooncake session/range transfer uses its existing key-major ranged requests.
5. The next owner of a shared slot consumes the existing save-completion gate,
   which covers KVPool copy, optional PD transfer and attention completion.

No Mooncake Client API, Backend adapter behavior, key schema, object layout or
session lifecycle changes.

## Compatibility And Constraints

- Configurations without `layerwise_num_shared_buffers` keep the current
  per-layer allocation behavior.
- Existing parsing and validation for shared-buffer count, independent layers
  and prefetch depth remain authoritative.
- Existing model/layout and TP-only layerwise restrictions remain authoritative.
- memcache code and runtime behavior are outside the change surface.
- `kv_consumer + consumer_is_to_put=true` is source/CPU tested in this version,
  but is not included in the first real-NPU validation claim.
- A future version may replace the pure-consumer startup rejection only after it
  implements and validates a role-appropriate slot-release event.

## Testing Strategy

Implementation follows test-driven development. Focused tests fail before the
production change and pass afterward.

### CPU/Mock Tests

Extend `tests/ut/distributed/ascend_store/test_layerwise_config.py` to cover:

- Mooncake `kv_producer` returns its layerwise config;
- Mooncake `kv_both` returns its layerwise config;
- Mooncake `kv_consumer + consumer_is_to_put=true` returns its layerwise config;
- Mooncake pure `kv_consumer` with a non-null shared-buffer value raises the
  expected `ValueError`;
- Mooncake pure `kv_consumer` without the value retains the no-reuse default;
- a `MultiConnector` containing one Mooncake AscendStore child resolves it;
- `use_layerwise=false`, unrelated connectors and unsupported backends retain
  their current result;
- existing memcache tests remain unchanged and pass.

Reuse the existing worker and model-runner tests to prove memory-factor and
descriptor-merge behavior; do not duplicate storage-layout algorithm coverage.

Run focused targets and the complete AscendStore CPU/mock suite in the
long-running CPU-only `liangjiahao/vllm-ascend-ut` Pod. Tar-sync the exact
checkout, explicitly name every target, disable bytecode and pytest cache, and
run Ruff, Python compilation and `git diff --check`.

### Real Mooncake/NPU Validation

Functional NPU validation covers only:

- `kv_producer` with `layerwise_num_shared_buffers=3`;
- `kv_both` with `layerwise_num_shared_buffers=3`.

For both roles, capture evidence that:

- the process starts with the expected physical-slot count and logical memory
  factor;
- model-runner descriptors are actually merged;
- layerwise ranged transfer succeeds without reuse-mate gate timeout or data
  corruption;
- output correctness checks pass;
- Mooncake sessions, keys, allocated bytes and active clients return to the
  required final state.

The run uses explicit `-n liangjiahao` for every test workload command. It
freezes exact source, image, model, topology and hardware identity before
execution and archives checksummed raw evidence.

### Excluded Validation Claims

The first validation does not claim real-NPU coverage for pure `kv_consumer`,
`kv_consumer + consumer_is_to_put=true`, memcache, unsupported layouts,
FabricMem, A3, multi-group behavior or performance.

## Performance Validation Handoff

The framework is stored at
`features/kv-pool-layerwise-reuse/performance-validation-handoff.md` with
initial status `WAITING_FOR_FUNCTIONAL_VALIDATION` and `ready: false`.

Functional validation may transition it to
`READY_FOR_PERFORMANCE_VALIDATION` only after all required CPU/mock and NPU
gates pass, exact source/image identities are frozen, the evidence manifest is
replayed and every placeholder is replaced. The transition sets `ready: true`
last and increments the handoff generation.

The separate performance session must independently recheck the handoff,
source/image identity and evidence checksum before creating performance
workloads. It may test only `kv_producer` and `kv_both` on the frozen functional
baseline. It creates a separate run ID, plan, thresholds, evidence and checksum
manifest.

## Acceptance Criteria

The feature is functionally accepted only when all of the following are true:

1. The production change is confined to `layerwise_config.py` unless a newly
   discovered source defect makes that scope impossible and the design is
   revisited.
2. Mooncake save-capable roles enter the existing compute-side reuse path.
3. The no-option default remains one buffer per layer.
4. Pure `kv_consumer` with a non-null shared-buffer option fails at startup.
5. Existing memcache focused tests pass without production memcache changes.
6. Focused and complete CPU/mock gates pass in the dedicated UT Pod.
7. Real Mooncake/NPU `kv_producer` and `kv_both` correctness gates pass with
   `layerwise_num_shared_buffers=3`.
8. Source, image, runtime and checksum evidence is complete and internally
   consistent.
9. The performance handoff is populated and moved to ready only after the
   functional report is final.
