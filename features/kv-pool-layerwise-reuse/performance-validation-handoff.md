---
schema_version: 1
status: READY_FOR_PERFORMANCE_VALIDATION
ready: true
placeholders_remaining: false
generation: 17
updated_at: 2026-08-13T13:28:00+08:00
---

# Mooncake Layerwise Private Issue #1 Performance Handoff

Generation 17 authorizes only the reviewed 32K four-point matrix. It uses the
accepted native ARM64 base plus a byte-exact six-file Python patch; it is not a
full Dockerfile rebuild and does not inherit generation 16 traffic scope.

## Source Identity

| Component | Branch / role | Commit | Remote equality |
| --- | --- | --- | --- |
| control repo | `kv-pool-layerwise-reuse` preparation parent | `033a1b0e5a0e57e2bf06914539102d080e4d3fc0` | local immutable preparation commit `033a1b0e5a0e57e2bf06914539102d080e4d3fc0`; this handoff must be its handoff-only direct child |
| `repos/vllm` | frozen detached dependency | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | frozen dependency commit `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`, reachable from the configured upstream baseline |
| `repos/vllm-ascend` | clean local instrumentation candidate | `8653c6c5e3b554719c8347a0a36fe2109e6a36d9` | reviewed plan explicitly uses local patch commit `8653c6c5e3b554719c8347a0a36fe2109e6a36d9` without pushing the candidate |
| `repos/Mooncake` | read-only collaborator dependency | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` | collaborator baseline `df3f74ed8ebdb0c935554beea6299a9f11c723e2` remains frozen and unmodified |

## Image Identity

| Field | Value |
| --- | --- |
| Image delivery mode | `ready-image` |
| Base image reference | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z` |
| Base manifest digest | `sha256:f8592141757f7e9976898858863e12ccd051ac4a3fd6ade7591f78d9769517e3` |
| Base config digest | `sha256:ce20411d6043d3830be7601c654b2c9a1d41fb923395cad2ea2e7ba200ebbbbd` |
| Patched file path | `/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/perf_metrics.py,/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py,/vllm-workspace/vllm-ascend/vllm_ascend/envs.py,/vllm-workspace/vllm-ascend/vllm_ascend/platform.py` |
| Patched file SHA256 | `9a8d9ea0b560561b3093ab418eaf8f4a320362e8c21ad272b6168e9deebd897e` |
| Patched source commit | `8653c6c5e3b554719c8347a0a36fe2109e6a36d9` |
| Patched source tree | `156a2ebe414aa82bc68102479a61fcca88f3332f` |
| Derived image reference | `docker.io/library/vllm-ascend:layerwise-issue1-8653c6c5e-20260813T045514Z` |
| Platform | `linux/arm64` |
| Derived manifest digest | `sha256:8c9f462c2c59e5c3ca4f6d7e89691ac20ae0f94943c470a7b57f2b9590ea6495` |
| Derived config digest | `sha256:f7aec20a062b9fcc18892b8639c707d9d89b7a29954aa2e23f31d77b0ab88de7` |
| vLLM source label | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend source label | `57d3c214e642cdbb529400f0742d1a98a8d38708` |
| vLLM-Ascend patch label | `8653c6c5e3b554719c8347a0a36fe2109e6a36d9` |
| Mooncake source label | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Derived-image/run ID | `20260813T045514Z` |

The final image has the same filesystem layer descriptors as the pre-metadata
commit image and exactly one more layer than the base (21 to 22). Embedded Git
HEADs and native shared objects remain at the base identities; the effective
Python source is proven by the six-file aggregate manifest above.

## Functional Acceptance

| Gate | Required result | Actual result | Evidence |
| --- | --- | --- | --- |
| Focused CPU/mock UT | PASS | PASS | `cpu/focused-instrumentation.log`: 191 passed at clean patch source |
| Complete AscendStore CPU/mock UT | PASS | PASS | `cpu/ascend-store.log`: 529 passed |
| Ruff | PASS | PASS | `cpu/ruff-version.log` and `cpu/ruff-source.log`: Ruff 0.16.2, all checks passed |
| Python compilation | PASS | PASS | `cpu/python-compile.log`: in-memory compilation without checkout bytecode |
| `git diff --check` | PASS | PASS | `cpu/source-diff-check.log` and `cpu/control-diff-check.log` |
| `kv_producer` Mooncake/NPU correctness | PASS | PASS | `npu/producer-reuse/`: response equals baseline, 27-layer ranged operations valid |
| `kv_both` Mooncake/NPU correctness | PASS | PASS | `npu/both-reuse/`: cold and warm responses equal baseline, 512-token external load valid |
| Physical-slot/memory-factor proof | PASS | PASS | `npu/summary.json`: 27 logical layers, 5 physical slots, factor 5.4 |
| Reuse-mate save-gate timeout/corruption check | PASS | PASS | independent raw-log validator found no timeout, abort-drain failure, traceback, 507018, or corruption |
| Final Mooncake resource cleanup | PASS | PASS | every case ended at Master 0/0/0; isolated resources removed; 4 physical NPUs free |
| Env and scheduler regression | PASS | PASS | `cpu/env-platform.log`: 53 passed, 1 skipped; no partial-prefill reset to one |
| Performance harness | PASS | PASS | `cpu/performance-harness.log`: 183 passed |
| Candidate image static/runtime identity | PASS | PASS | `image/`: platform, labels, layers, six-file hashes, imports and strict env parsing passed |

## Evidence Identity

| Field | Value |
| --- | --- |
| Evidence root | `features/kv-pool-layerwise-reuse/evidence/layerwise-private-issue1-functional-20260813T050200Z` |
| Root SHA256SUMS path | `features/kv-pool-layerwise-reuse/evidence/layerwise-private-issue1-functional-20260813T050200Z/SHA256SUMS` |
| Root SHA256SUMS digest | `3b0e34fe22830f8a3332f9cfcbbebe3ba806471547acbac5d1e4cb4edf9ef110` |
| Functional validation report | `features/kv-pool-layerwise-reuse/evidence/layerwise-private-issue1-functional-20260813T050200Z/functional-acceptance.json` |
| Validation config snapshot | `features/kv-pool-layerwise-reuse/evidence/layerwise-private-issue1-functional-20260813T050200Z/validation-config.json` |

## Authorized Performance Scope

- private Issue #1 four-point characterization only;
- namespace `liangjiahao`, node `m1`, model `vllm-ascend/DeepSeek-V2-Lite-W8A8`;
- exact image/source/evidence identities above;
- `backend=mooncake`, BULK with `use_layerwise=false`, and LAYERWISE/REUSE3 with `use_layerwise=true`;
- REUSE3 Prefill uses `layerwise_num_shared_buffers=3` and `kv_producer`;
- the no-reuse pure-consumer Decode companion is required for every point;
- DP1 Prefill TP2 plus Decode TP2, four physical Ascend910 devices total;
- input=32000 and one shared external hit=28800 prefix, local prefix caching disabled;
- Test 1 output=128, concurrency=8, 125 formal requests for BULK and LAYERWISE;
- Test 2 output=1, concurrency=40, 100 formal requests for BULK and REUSE3;
- `max_model_len=32768`, `max_num_batched_tokens=32768`, `gpu_memory_utilization=0.95`;
- Test 1 `max_num_partial_prefills=8`, `max_long_partial_prefills=8`, threshold 4096;
- Test 2 `max_num_partial_prefills=40`, `max_long_partial_prefills=40`, threshold 768;
- server seed 1024, fixture seed 1023, AISBench closed-loop request rate zero;
- aggregated `KVPOOL_PERF_METRICS` schema v2 and Mooncake Transfer Engine metrics are required;
- `VLLM_ASCEND_KVPOOL_RANGE_DEBUG` is disabled for formal points and enabled only for one-wave short diagnostic attempts;
- each point runs 8 unmeasured warmups, one shared seed, an admission canary, a clean reseed, and one formal attempt;
- Test 1 formal traffic requires at least eight Prefill context requests in one iteration plus multiple running requests in Prometheus;
- Test 2 requires `BULK capacity < 40 <= REUSE3 capacity`; no alternative concurrency or staircase is authorized;
- a larger REUSE3 startup capacity alone is insufficient: sustained running, capacity waiting, or preemption must prove capacity conversion;
- any direct throughput ratio below 1.0 triggers attribution;
- unresolved Test 1 slowdown authorizes one-wave short diagnostic BULK/LAYERWISE c8;
- unresolved Test 2 slowdown authorizes one-wave short diagnostic BULK/LAYERWISE/REUSE3 c40;
- this is the one-wave short diagnostic contract with conditional LAYERWISE c40 diagnostic control;
- profiler use is authorized only if the short diagnostic leaves compute batch efficiency unresolved;
- final reporting is a single-run characterization without a statistical significance claim.

## Explicit Exclusions

- No source push, candidate push, Dockerfile build, or full native image rebuild.
- No memcache, A3, FabricMem, multi-group, unsupported topology, or alternative concurrency claim.
- No formal retry and no combination with prior diagnostic or performance roots.
- A confirmed production-source correctness defect stops performance execution.

## Blocker

None. The functional lane passed and restored all isolated resources. The
performance runner must still recheck exact image content, live physical NPU
capacity, admission/capacity prerequisites, and evidence checksums before
sending traffic.
