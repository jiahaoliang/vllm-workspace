---
schema_version: 1
status: READY_FOR_PERFORMANCE_VALIDATION
ready: true
placeholders_remaining: false
generation: 12
updated_at: 2026-08-12T11:10:03+08:00
---

# Mooncake Layerwise Buffer Reuse Performance Validation Handoff

本文件是功能验证 session 与性能验证 session 之间的 fail-closed handoff。
Generation 12 已完成不可变源码、镜像、CPU/mock 和候选源码的真实 NPU
correctness 验收，现授权执行冻结的五点 DP1 performance rerun。

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
| control repo | `kv-pool-layerwise-reuse` generation-12 functional evidence parent | `de8890ea40bd5723c61f2f5b9258ac837cb4bd1e` | functional evidence parent pushed as `origin/kv-pool-layerwise-reuse=de8890ea40bd5723c61f2f5b9258ac837cb4bd1e` before this handoff-only transition |
| `repos/vllm` | frozen detached dependency | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | `workspace.lock=54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`; commit reachable from `upstream/main` |
| `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `57d3c214e642cdbb529400f0742d1a98a8d38708` | `origin/feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723=57d3c214e642cdbb529400f0742d1a98a8d38708` |
| `repos/Mooncake` | read-only detached collaborator baseline | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` | `collaborator/feature/layerwise-kv-session=df3f74ed8ebdb0c935554beea6299a9f11c723e2` |

## Image Identity

| Field | Value |
| --- | --- |
| Image delivery mode | `ready-image` |
| Base image reference | `quay.io/ascend/cann:9.0.1-910b-ubuntu22.04-py3.12` |
| Base manifest digest | BuildKit-resolved base is not used as the runtime identity; the derived manifest and config below are authoritative |
| Patched file path | `/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py` |
| Patched file SHA256 | `54e3198504a3745b21e172d8e66c4c7c217bbc7642498e3bb4cdbab557b8b6ea` |
| Patched source commit | `57d3c214e642cdbb529400f0742d1a98a8d38708` |
| Derived image reference | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z` |
| Platform | `linux/arm64` |
| Derived manifest digest | `sha256:f8592141757f7e9976898858863e12ccd051ac4a3fd6ade7591f78d9769517e3` |
| Derived config digest | `sha256:ce20411d6043d3830be7601c654b2c9a1d41fb923395cad2ea2e7ba200ebbbbd` |
| vLLM source label | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend source label | `57d3c214e642cdbb529400f0742d1a98a8d38708` |
| Mooncake source label | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Derived-image/run ID | `20260811T145302Z` |

## Functional Acceptance

| Gate | Required result | Actual result | Evidence |
| --- | --- | --- | --- |
| Focused CPU/mock UT | PASS | PASS | `evidence/shared-buffer-functional-20260812T023541Z/cpu/focused-self-load.log`: `1 passed`; Mooncake layer-session class `27 passed`; performance harness `91 passed` |
| Complete AscendStore CPU/mock UT | PASS | PASS | `evidence/shared-buffer-functional-20260812T023541Z/cpu/ascend-store.log`: `516 passed` at clean source `57d3c214e` |
| Ruff | PASS | PASS | `evidence/shared-buffer-functional-20260812T023541Z/cpu/ruff-source-delta.log`; `cpu/ruff-performance-delta.log`; Ruff 0.16.2 passed at the recorded scopes |
| Python compilation | PASS | PASS | `evidence/shared-buffer-functional-20260812T023541Z/cpu/python-compile.log`: 2 candidate source-delta plus 20 performance files compiled in memory |
| `git diff --check` | PASS | PASS | `evidence/shared-buffer-functional-20260812T023541Z/cpu/diff-check.log` |
| `kv_producer` Mooncake/NPU correctness | PASS | PASS | `evidence/shared-buffer-functional-20260812T023541Z/npu/producer-reuse/`; response equals baseline and all ranged operations passed |
| `kv_both` Mooncake/NPU correctness | PASS | PASS | `evidence/shared-buffer-functional-20260812T023541Z/npu/both-reuse/`; cold/warm responses equal baseline and all ranged operations passed |
| Physical-slot/memory-factor proof | PASS | PASS | `evidence/shared-buffer-functional-20260812T023541Z/npu/summary.json`: 27 logical layers, 5 physical slots, factor 5.4 |
| Reuse-mate save-gate timeout/corruption check | PASS | PASS | `evidence/shared-buffer-functional-20260812T023541Z/npu/validate-functional.py`; `npu/summary.json`; no timeout, traceback, abort-drain failure, or response corruption |
| Final Mooncake resource cleanup | PASS | PASS | per-case `final.metrics`; `post-cleanup-npu-readiness.json`: Master `0/0/0`, allocatable/free physical NPU `8/8` |
| Candidate image static/runtime identity | PASS | PASS | `evidence/shared-buffer-functional-20260812T023541Z/image-identity.json`; native `linux/arm64`, exact imageID, embedded Git HEADs, labels, and patched-file hash |
| CPU-only AISBench preparation | PASS | PASS | 8 warmup, 64 formal, 72 unique/disjoint IDs, and 72/72 exact 16384-token re-encodes; preparation manifest digest `4d032f8853afd36e34d2e62aace692c3ef96f0e1dad0fe6d59f07cc09aa67d7e` |
| Physical Ascend910 readiness on `m1` | PASS | PASS | `evidence/shared-buffer-functional-20260812T023541Z/pre-run-npu-readiness.json` and `post-cleanup-npu-readiness.json`: exactly 8 allocatable and at least 4 free; `vnpu-number` ignored |

## Evidence Identity

| Field | Value |
| --- | --- |
| Evidence root | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260812T023541Z` |
| Root `SHA256SUMS` path | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260812T023541Z/SHA256SUMS` |
| Root `SHA256SUMS` digest | `0c80987652db2189bd8cf7d91b7bd666622696353660b8f32d01eab3a95a3f96` |
| Functional validation report | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260812T023541Z/REPORT.md` |
| Validation config snapshot | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260812T023541Z/validation-config.json` |
| Independent evidence validator | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260812T023541Z/validate-evidence.py` |
| Fixture `SHA256SUMS` digest | `8848041c4f3cea186c016da8aed080327723e823e706c327991a1639aff05dfe` |
| Client preflight `SHA256SUMS` digest | `f6142f68d2fd4f9a3eb65ce96f0b6ca172fb4c72eafe7bebae2406257383b873` |

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
- the single physical node `m1`, selected explicitly with `--npu-node m1`;
- model `vllm-ascend/DeepSeek-V2-Lite-W8A8`;
- DP1 only, 16384 input tokens, concurrency 8;
- exactly five points: BULK o128/o1, LAYERWISE o128/o1, and REUSE3 o1;
- one 8-request warmup wave and one 64-request formal attempt per point;
- exactly eight concurrency waves within each formal attempt;
- `DefaultPerfMetricCalculator`, `total` stage, one formal repetition, and no
  automatic retry;
- AISBench `sampling_mode=default`; multi-wave and total-stage semantics are
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

None. The administrator-restored device plugin exposes exactly eight physical
Ascend910 resources on `m1`. Candidate run `20260812T023541Z` passed the
required `kv_producer` and `kv_both` NPU correctness gates, and cleanup returned
the node to eight free physical resources. Generation 10's NPU and performance
results remain historical evidence for `535555917`; generation 12 authorizes a
fresh performance root for candidate `57d3c214e` and does not reattribute those
historical measurements.

The earlier TP2 REUSE3 non-save-owner save-gate defect is preserved in the
diagnostic performance root `/tmp/layerwise-performance-20260809T010429Z` and
was resolved by vLLM-Ascend `5355559175f9998f5d70866734fb79569dfc86f9`.

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
Generation 9 freezes the corrected rapid five-point contract, 8 warmup
requests, 64 formal requests, 128 GiB per serving rank, and requires a new
performance run root. It does not authorize resuming or combining any
generation-8 evidence root.

## Generation 10 Rerun Authorization

Generation 10 is a handoff-only direct child of control parent
`057f9fbcc3704a40af03554934084607ef271223`. The performance harness passed
`70` CPU/mock tests in `liangjiahao/vllm-ascend-ut`; all 15 performance Python
files passed source `compile()`, and `git diff --check`, shell syntax, and
namespace scans passed. The UT image does not contain a Ruff executable, so no
new Ruff result is claimed for the performance-only control change; the frozen
vLLM-Ascend functional-source Ruff evidence remains unchanged and valid.

Generation 9's attempted root
`/tmp/layerwise-performance-rapid-64-20260810T031839Z` stopped at the BULK
correctness-canary because its old canary source still named the superseded
`tokens-16384-c64` fixture path. It sent no formal warmup or formal benchmark
requests; `restoration.json` records engines stopped and Mooncake empty. The
canary path is fixed and covered by the new runner regression test. The failed
root must not be resumed or combined.

The authorized generation-10 run completed in the new root recorded below.
That root must not be resumed or combined with any other performance root.

## Generation 10 Performance Acceptance

The generation-10 handoff authorized the following immutable five-point run;
this section was added only after the run completed and its raw evidence was
imported and checked.

| Gate | Result | Evidence |
| --- | --- | --- |
| Exact five-point DP1 matrix | PASS | `evidence/layerwise-performance-20260810T043500Z/raw/run-contract.json` |
| Formal requests | PASS | All five points are `valid: true` with `64/64` successful requests; report rows are in `layerwise-performance-64-request-validation-2026-08-10.md` |
| Full report checker | PASS | `performance.report check --scope all` returned `{"scope":"all","valid":true,"errors":[]}` |
| Raw checksum replay | PASS | `evidence/layerwise-performance-20260810T043500Z/raw/SHA256SUMS`; digest `ebbd9f707589748f4cc12bfaa0edd273eb7183a6efe7d003ed85158439d1d093` |
| Repository import checksum replay | PASS | `evidence/layerwise-performance-20260810T043500Z/SHA256SUMS`; digest `723ac36b231edb68a51328ae6c09d87c4f69cb3c6888e534cdc3d5c3fb6341dd` |
| Runtime cleanup/restoration | PASS | `evidence/layerwise-performance-20260810T043500Z/raw/restoration.json`: completed, engines stopped, no errors, Mooncake empty |
| Raw report | PASS | `layerwise-performance-64-request-validation-2026-08-10.md`; SHA256 `2d1d3fe91b5710e40213cd05a754cd23bbec8ed638b4859344f83c4cebb669f1` |

Observed request throughput was `0.343` (BULK o128), `0.3805` (BULK o1),
`0.2337` (LAYERWISE o128), `0.248` (LAYERWISE o1), and `0.2409` req/s
(REUSE3 o1). REUSE3/LAYERWISE o1 request-throughput ratio was `0.971371x`
in this run. These are single-repetition raw observations from DP1,
16384-input, concurrency-8, eight-wave formal attempts; they do not establish
statistical significance, steady-state behavior, or a performance pass/fail
claim.

Reusable image for follow-up validation:
`docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-535555917-df3f74ed-20260809T070557Z`
with manifest
`sha256:cf5da7c1da7dcb72f4c22e201d628b9e4aa819f53c15711651ebc9241cb955bc`.

## Historical Generation 8 Performance Acceptance

Generation 8 authorized the immutable formal run before this final result was
added. The accepted run is `20260809T184011Z`; this post-run handoff edit does
not change the generation-8 source, image, functional evidence, or authorized
scope.

| Gate | Result | Evidence |
| --- | --- | --- |
| Exact five-point DP1 matrix | PASS | `evidence/layerwise-performance-20260809T184011Z/raw/run-contract.json`; five `points/*/formal-1/attempt-1/raw/summary.json` files |
| Formal requests | PASS | every point is `valid: true` with `8/8` successful requests |
| Full report checker | PASS | `performance.report check --scope all` returned `{"scope":"all","valid":true,"errors":[]}` |
| Raw checksum replay | PASS | `evidence/layerwise-performance-20260809T184011Z/raw/SHA256SUMS` digest `fa9c2bf9b5e73e9eb94f9cb273cb555a4ea0e74fbc49b00a4cd649fc708dd40c` |
| Repository import checksum replay | PASS | `evidence/layerwise-performance-20260809T184011Z/SHA256SUMS` digest `01ff2689580656b70cc381af7a382b53f711f9163a60cf0174a3d8d5b995cff4` |
| Runtime cleanup/restoration | PASS | `raw/restoration.json`: completed, engines stopped, no errors, Mooncake empty; `raw/final-mooncake-empty.metrics`: zero keys and allocated bytes |
| Raw report | PASS | `layerwise-performance-rapid-validation-2026-08-10.md`: five aggregate rows, all 40 formal per-request rows, and approved ratios; SHA256 `56443723eec12deba773a4d2de76e510e0c020c78c6c231842d1c6d30cb6bc65`; renderer `0f88b7a3d95f9748b86c2ddb49b53dbc00428b61` |

Observed request throughput was `0.2063` (BULK o128), `0.3743` (BULK o1),
`0.1552` (LAYERWISE o128), `0.2320` (LAYERWISE o1), and `0.2567` req/s
(REUSE3 o1). REUSE3/LAYERWISE o1 throughput was `1.10647x`, with median TTFT
at `0.933059x`. LAYERWISE/BULK throughput was `0.752302x` for o128 and
`0.619824x` for o1, so this run does not show a layerwise-over-bulk gain.

These are one-wave raw observations from DP1, 16384 input tokens, concurrency
8. They are not steady-state results, have no outlier removal or significance
test, and do not establish a general throughput pass/fail conclusion.

Reusable image for follow-up validation:
`docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-535555917-df3f74ed-20260809T070557Z`
with manifest
`sha256:cf5da7c1da7dcb72f4c22e201d628b9e4aa819f53c15711651ebc9241cb955bc`.

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
