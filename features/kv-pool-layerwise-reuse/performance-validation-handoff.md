---
schema_version: 1
status: READY_FOR_PERFORMANCE_VALIDATION
ready: true
placeholders_remaining: false
generation: 16
updated_at: 2026-08-12T22:57:19+08:00
---

# Mooncake Layerwise Buffer Reuse Performance Validation Handoff

本文件是功能验证 session 与性能验证 session 之间的 fail-closed handoff。
Generation 16 继承已验收的不可变源码、镜像、CPU/mock 和真实 NPU
correctness，并接受 generation 15 授权的三点 DP1 high-hit performance run。
此前的 generation 12 cold-cache 结果仍仅作为历史 characterization 保留。

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
| control repo | `kv-pool-layerwise-reuse` generation-16 high-hit acceptance parent | `647a63eae622dad1f5177e2327062248cf63e7a2` | high-hit evidence, report, and completed plan pushed as `origin/kv-pool-layerwise-reuse=647a63eae622dad1f5177e2327062248cf63e7a2` before this handoff-only transition |
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
| CPU-only AISBench preparation | PASS | PASS | `evidence/layerwise-performance-high-hit-20260812T135700Z/raw/client-identity.json` and `raw/fixtures/tokens-16384-c8/`; 8 warmup, 64 paired seed, and 64 paired formal fixtures archived and replayed |
| Physical Ascend910 readiness on `m1` | PASS | PASS | `evidence/shared-buffer-functional-20260812T023541Z/pre-run-npu-readiness.json` and `post-cleanup-npu-readiness.json`: exactly 8 allocatable and at least 4 free; `vnpu-number` ignored |

## Evidence Identity

| Field | Value |
| --- | --- |
| Evidence root | `features/kv-pool-layerwise-reuse/evidence/layerwise-performance-high-hit-20260812T135700Z` |
| Root `SHA256SUMS` path | `features/kv-pool-layerwise-reuse/evidence/layerwise-performance-high-hit-20260812T135700Z/SHA256SUMS` |
| Root `SHA256SUMS` digest | `b4dc6dcd5e494784ab2d47082d78b8ec8f8cc0017c9599f456355a8734446e7f` |
| Functional validation report | `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260812T023541Z/REPORT.md` |
| Validation config snapshot | `features/kv-pool-layerwise-reuse/evidence/layerwise-performance-high-hit-20260812T135700Z/raw/run-contract.json` |
| Independent evidence validator | `features/kv-pool-layerwise-reuse/deployment/performance/report.py` |
| Fixture `SHA256SUMS` digest | `5db2057b83d35871c1f39d5136ebf418eab8bd50d31eb5ed2d097589ab11d1e8` |
| Client identity SHA256 | `f11c6ee5b068b72496d5b411eea1f8426db9ca7849d24bc0feff08ed7ce3d152` |

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
- DP1 only, 16384 input tokens, output 1, concurrency 8;
- exactly three points: BULK o1, LAYERWISE o1, and REUSE3 o1;
- `--no-enable-prefix-caching` on both Prefill and Decode for every variant;
- one 8-request runtime warmup, one unmeasured 64-request seed attempt, and one
  64-request formal attempt per point;
- each 13312-token seed is the exact first 104 blocks of its paired 16384-token
  formal prompt, and seed/formal token IDs plus digests must replay from the
  shared fixture manifest and metadata;
- clear Mooncake after warmup and before seed, but never between seed and
  formal;
- wait for exactly `master_key_count=6656` after seed publication;
- require exactly 64 unique formal Prefill records with `Total tokens 16384`,
  `kvpool hit tokens: 13312`, and `need to load: 13312`, proving 81.25 percent
  external Prefix KV hits and zero local-prefix contribution;
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
- 10-second point telemetry, per-request hit evidence, lightweight point
  diagnostics, and complete Prefill/Decode logs once per variant;
- no performance timeout; a valid slow point continues naturally;
- hardware and namespace explicitly frozen by the final validation config
  snapshot.

Generation 16 records the completed authorized comparison below. Any follow-up
performance validation must create its own run ID, plan, raw evidence, and
checksum manifest. Functional correctness evidence in this handoff is not a
throughput or latency claim.

## Explicit Exclusions

This handoff does not authorize or claim coverage for:

- pure `kv_consumer` buffer reuse;
- real-NPU `kv_consumer + consumer_is_to_put=true` buffer reuse;
- memcache behavior or memcache performance regression;
- unsupported CP, TP-mismatch or hybrid layouts;
- FabricMem, A3, or hardware not named in the final config snapshot;
- Mooncake multi-group behavior unless the final handoff explicitly adds it;
- any throughput, latency, scaling or capacity result outside the accepted
  single-point high-hit matrix below;
- any REUSE3 capacity benefit claim from this concurrency-8 run; that requires
  a separate capacity-constrained matrix.

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

None at publication time. The administrator-restored device plugin exposed
exactly eight physical Ascend910 resources on `m1`. Candidate run
`20260812T023541Z` passed the required `kv_producer` and `kv_both` NPU
correctness gates, and cleanup returned the node to eight free physical
resources. The performance runner must recheck live capacity before traffic.
Generation 16 accepts the complete high-hit performance root for candidate
`57d3c214e`; it does not reattribute any historical measurements.

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

## Generation 16 High-Hit Performance Acceptance

Generation 15 authorized the immutable run completed on 2026-08-12 in
`evidence/layerwise-performance-high-hit-20260812T135700Z/raw`. It used the
exact source, image, DP1/TP2, 16K/o1/c8, fixture, and lifecycle identities
frozen above. The unmeasured seed phase and the measured formal phase both
completed `64/64` requests for every variant.

| Gate | Result | Evidence |
| --- | --- | --- |
| Exact three-point DP1 matrix | PASS | `raw/run-contract.json`: BULK, LAYERWISE, and REUSE3 at 16K/o1/c8 |
| Paired seed/formal fixtures | PASS | `raw/fixtures/tokens-16384-c8/manifest.json`; every 13,312-token seed is the exact prefix of its paired 16,384-token formal prompt |
| Seed publication | PASS | All three `seed/attempt-1/raw/summary.json` files are `valid: true` with `64/64`; each `seeded-mooncake.metrics` reached 6,656 keys |
| Formal requests | PASS | All three formal summaries are `valid: true` with `64/64`; `192/192` total |
| External KV hit contract | PASS | All three `hit-validation.json` files record 64 requests, exact 13,312 hit tokens, 81.25 percent hit rate, zero inferred local hit tokens, and no errors |
| Variant correctness canaries | PASS | `raw/canaries/` |
| REUSE3 runtime layout | PASS | `raw/runtime-checks/dp1-16384-reuse3-prefill.json`: 27 logical layers, 5 physical slots, factor 5.4 |
| Full report checker | PASS | `performance.report check --scope all` returned `{"scope":"all","valid":true,"errors":[]}` |
| Raw checksum replay | PASS | `raw/SHA256SUMS`; digest `5fe2f5219d82fd33e4763c326df73bc9e5a1583a55aa396ed976b38b66882864` |
| Repository import checksum replay | PASS | outer `SHA256SUMS`; digest `b4dc6dcd5e494784ab2d47082d78b8ec8f8cc0017c9599f456355a8734446e7f` |
| Runtime cleanup/restoration | PASS | `raw/restoration.json`: completed, engines stopped, no errors, Mooncake empty |
| Final Mooncake cleanup | PASS | `raw/final-mooncake-empty.metrics`: key count, allocated bytes, and active clients are zero |
| Raw report | PASS | `layerwise-performance-high-hit-validation-2026-08-12.md`; SHA256 `d8fed3cf7f5fd33c6829fefaede5199eb9a965547d16e08d97ebc1f2f74412def` |

| Variant | Request throughput | Input-token throughput | Median TTFT | P95 TTFT | AISBench duration |
| --- | ---: | ---: | ---: | ---: | ---: |
| BULK | 1.5476 req/s | 25,355.1 tok/s | 5,042.3 ms | 5,359.9 ms | 41.36 s |
| LAYERWISE | 1.1747 req/s | 19,245.8 tok/s | 6,717.6 ms | 6,975.1 ms | 54.48 s |
| REUSE3 | 1.0538 req/s | 17,264.6 tok/s | 7,344.5 ms | 8,546.3 ms | 60.74 s |

Request-throughput ratios were `0.759046x` for LAYERWISE/BULK,
`0.89708x` for REUSE3/LAYERWISE, and `0.680925x` for REUSE3/BULK. This is one
formal repetition at DP1/16K/o1/c8 and exact 81.25-percent external KV hits.
It is raw characterization, not statistical significance, a general scaling
result, a capacity-benefit result, or a performance pass/fail threshold.

The full command wall clock was approximately 45 minutes 48 seconds. Prefill
used physical NPU 4,5 and Decode used 3,6 on `m1`. The run restored the prior
Deployment and ConfigMap state, stopped both engines, and returned Mooncake to
`0/0/0` key/byte/client state.

Reusable image for follow-up validation:
`docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z`
with manifest
`sha256:f8592141757f7e9976898858863e12ccd051ac4a3fd6ade7591f78d9769517e3`
and config digest
`sha256:ce20411d6043d3830be7601c654b2c9a1d41fb923395cad2ea2e7ba200ebbbbd`.

## Historical Generation 15 High-Hit Authorization

The published high-hit harness parent is `6a5bfa785bbc9bc4a37684e4fc0fd643126279d1`.
Its complete performance CPU/mock suite passed `108` tests in the CPU-only
`liangjiahao/vllm-ascend-ut` Pod. All 20 performance Python files compiled in
memory, both shell entrypoints passed `bash -n`, and `git diff --check` passed.
The saved 64-record Prefill hit log also replayed successfully with the actual
control-host Python 3.9.9 runtime.

The 2026-08-12 21:25+08:00 live preflight found eight allocatable physical
Ascend910 devices on Ready node `m1`. The preserved diagnostic fence
`decode-engine-deployment-676dbcb595-gl65k` holds NPU `0,7`; it is not
replaceable. Current `app=prefill` and `app=decode` Pods hold four replaceable
devices, leaving six available after replacement for the four-device DP1 run.
The read-only checker returned `READY` with
`available_after_replacing_current_engines=6`.

If startup or execution fails, the runner skips automatic engine stop,
Kubernetes restoration, ConfigMap deletion, and Mooncake reset. It records
`failed_environment_preserved=true` so the failed Pods and logs remain in
place until explicitly inspected and cleaned up.

The first generation-14 attempt is retained at
`/tmp/layerwise-performance-high-hit-20260812T133600Z`. BULK warmup passed
8/8; seed passed 64/64 and reached the exact 6,656-key publication gate; formal
traffic produced exactly 64 records with `kvpool hit tokens: 13312` and
`need to load: 13312`. The run then failed only while the control-host evidence
parser evaluated Python-3.10-only `zip(..., strict=True)` under Python 3.9.9.
It was not a vLLM, Mooncake, NPU, AISBench, response, or hit-contract failure.
The failed root checksum manifest digest is
`993a13903e84fc06cb190abe0c07ce31a29e8fd1e072b990024ebc7a329f858f`;
its `prefill-hit.log` digest is
`6ef2105641dcfa7dc05b5b21b43509b084257197671d8935e19041ee8a11758c`.
The root must not be resumed or combined. Generation 15 requires a new complete
three-point run after explicit inspection and restoration of the preserved
environment.

This generation requires a new root named
`/tmp/layerwise-performance-high-hit-<run-id>`. It must execute `prepare` first
to generate exact paired fixtures, then run the three authorized points once.
No old run root may be resumed, combined, or accepted under this generation.

The generation-12 Prefill evidence directly contradicts the new hit contract:
for example, the Layerwise `vllm-prefill.log` under
`evidence/layerwise-performance-20260812T102633Z/raw/variants/layerwise/raw/`
repeatedly records `hit_blocks=0/128` during formal traffic. Therefore
generation 12 answers only the cold-cache save-path question and cannot be used
as evidence for the 81.25-percent-hit comparison.

## Historical Generation 12 Cold-Cache Acceptance

Generation 12 authorized the immutable five-point run completed on 2026-08-12
in `evidence/layerwise-performance-20260812T102633Z/raw`. The run used only
the candidate image and source identities frozen above. It is a
single-repetition cold-cache raw characterization and must not be combined
with another run root or presented as a high-hit comparison.

Before the accepted run, Decode repeatedly failed during initialization on
physical NPU `0,7` with `libcpu_kernels.so`, kernel `Log`, and runtime result
`507018`. An otherwise identical Decode probe became Ready on NPU `4,5`.
The accepted run therefore preserved the failed `0,7` Pod as a diagnostic NPU
fence and ran every variant with Prefill on `1,2` and Decode on `4,5`. No
accepted point used NPU `0,7`. The exact startup logs are preserved under
`evidence/layerwise-performance-20260812T102633Z/deployment-diagnostics/`.

| Gate | Result | Evidence |
| --- | --- | --- |
| Exact five-point DP1 matrix | PASS | `evidence/layerwise-performance-20260812T102633Z/raw/run-contract.json` |
| Formal requests | PASS | All five points are `valid: true` with `64/64` successful requests; `320/320` total |
| Variant correctness canaries | PASS | `evidence/layerwise-performance-20260812T102633Z/raw/canaries/` |
| REUSE3 runtime layout | PASS | `evidence/layerwise-performance-20260812T102633Z/raw/runtime-checks/dp1-16384-reuse3-prefill.json`: 27 logical layers, 5 physical slots, factor 5.4 |
| Full report checker | PASS | `performance.report check --scope all` returned `{"scope":"all","valid":true,"errors":[]}` |
| Raw checksum replay | PASS | `evidence/layerwise-performance-20260812T102633Z/raw/SHA256SUMS`; digest `e8ffb6975de785ce68797b7e7a18c572b27d7d74d4ef549242f0cb6bf9a4f0b6` |
| Repository import checksum replay | PASS | `evidence/layerwise-performance-20260812T102633Z/SHA256SUMS`; digest `2b3da6262a81ef01cfc37f8f60e4f63bb07c541f40501458654f5c6ca02dc003` |
| Runtime cleanup/restoration | PASS | `evidence/layerwise-performance-20260812T102633Z/raw/restoration.json`: completed, engines stopped, no errors, Mooncake empty |
| Final live Mooncake cleanup | PASS | Master key count, allocated bytes, and active clients were all zero |
| Raw report | PASS | `layerwise-performance-64-request-validation-2026-08-12.md`; SHA256 `3526d2e91aa02b4fe5a1eeade3d9d507d0273b5dc86c94223ccc2e93cde7548d` |

| Variant | Output tokens | Request throughput | Formal duration | Successful requests |
| --- | ---: | ---: | ---: | ---: |
| BULK | 128 | 0.2943 req/s | 217.44 s | 64/64 |
| BULK | 1 | 0.3187 req/s | 200.79 s | 64/64 |
| LAYERWISE | 128 | 0.2788 req/s | 229.52 s | 64/64 |
| LAYERWISE | 1 | 0.3017 req/s | 212.16 s | 64/64 |
| REUSE3 | 1 | 0.2394 req/s | 267.33 s | 64/64 |

For request throughput, LAYERWISE/BULK was `0.947333x` at o128 and
`0.946658x` at o1. REUSE3/LAYERWISE at o1 was `0.793503x`, and
REUSE3/BULK was `0.751177x`. These ratios are observations from one formal
attempt, not statistical significance or a performance pass/fail threshold.
The runner wall clock from its first captured command through final Mooncake
empty proof was approximately 56 minutes 3 seconds.

Reusable image for follow-up validation:
`docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z`
with manifest
`sha256:f8592141757f7e9976898858863e12ccd051ac4a3fd6ade7591f78d9769517e3`
and config digest
`sha256:ce20411d6043d3830be7601c654b2c9a1d41fb923395cad2ea2e7ba200ebbbbd`.

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
