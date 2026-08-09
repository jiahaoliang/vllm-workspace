# Mooncake Layerwise Rapid Performance Validation Design

## Status

Approved by the user on 2026-08-09.

This document replaces the performance matrix and sampling protocol in
`2026-08-08-layerwise-performance-validation-design.md` for the next formal
performance run. Unchanged source, image, correctness, namespace, restoration,
and checksum gates remain inherited from the earlier design and the committed
functional handoff.

The earlier run rooted at
`/tmp/layerwise-performance-20260809T082351Z` uses the superseded protocol. It
is calibration and diagnostic evidence only and must not be mixed with the new
formal results.

## Objective

Answer two narrowly defined performance questions with AISBench in an expected
natural wall time of three to six hours:

1. Does layerwise KV transfer improve normal inference relative to whole-block
   transfer by overlapping transfer and compute?
2. Does compute-side reuse with three shared layerwise buffers improve Prefill
   throughput relative to the same layerwise transfer path without reuse?

The run produces a raw single-wave characterization. It does not claim
steady-state behavior, statistical significance, input-length trends,
concurrency scaling, maximum capacity, or DP2 scaling.

Three to six hours is a planning target, not a timeout. The test plan does not
terminate a valid point or the run because it takes longer than expected.
Calibration from the superseded run suggests that the reduced five-point run
will normally finish in approximately one to two hours. The three-to-six-hour
window includes server lifecycle, cluster variance, evidence checks, reporting,
and restoration margin.

## Frozen Scope

The formal run uses exactly:

```text
topology: DP1
input tokens: 16384
concurrency: 8
formal request count: 8
formal repetitions: 1
```

DP1 consists of one Prefill data-parallel rank on two physical NPUs and one
Decode data-parallel rank on two physical NPUs. Tensor parallel size remains
two.

No DP2, 4096-token, 32768-token, or other concurrency point belongs to this
formal matrix.

## Variants

### BULK

```text
use_layerwise: false
layerwise_num_shared_buffers: absent
```

The absent shared-buffer field preserves the default one independent buffer per
logical layer.

### LAYERWISE

```text
use_layerwise: true
layerwise_num_shared_buffers: absent
```

This enables ranged layerwise transfer without compute-side buffer reuse.

### REUSE3

```text
Prefill:
  use_layerwise: true
  layerwise_num_shared_buffers: 3

Decode:
  use_layerwise: true
  layerwise_num_shared_buffers: absent
```

Only the save-capable Prefill producer uses shared compute-side buffers. Decode
remains the no-reuse pure-consumer companion authorized by the functional
handoff.

## Exact Five-Point Matrix

### Test 1: Normal Inference Transfer Comparison

Use `max_tokens=128` and compare:

| Point | Variant | Topology | Input tokens | Concurrency | Requests |
| --- | --- | --- | ---: | ---: | ---: |
| T1-BULK | BULK | DP1 | 16384 | 8 | 8 |
| T1-LAYERWISE | LAYERWISE | DP1 | 16384 | 8 | 8 |

The primary comparison is `LAYERWISE / BULK`.

### Test 2: Compute-Side Shared-Buffer Comparison

Use `max_tokens=1` to isolate Prefill-dominated behavior and compare:

| Point | Variant | Topology | Input tokens | Concurrency | Requests |
| --- | --- | --- | ---: | ---: | ---: |
| T2-BULK | BULK | DP1 | 16384 | 8 | 8 |
| T2-LAYERWISE | LAYERWISE | DP1 | 16384 | 8 | 8 |
| T2-REUSE3 | REUSE3 | DP1 | 16384 | 8 | 8 |

The primary comparison is `REUSE3 / LAYERWISE`. `REUSE3 / BULK` is an
auxiliary end-to-end comparison.

## Server Lifecycle And Ordering

Start each DP1 runtime variant exactly once:

```text
BULK
  -> Test 1 warmup and formal
  -> Test 2 warmup and formal
LAYERWISE
  -> Test 1 warmup and formal
  -> Test 2 warmup and formal
REUSE3
  -> Test 2 warmup and formal
```

This produces three server starts, five warmups, and five formal attempts.
Switching output profiles does not restart the server.

Before each warmup and formal attempt:

1. Remove all Mooncake keys.
2. Require zero key count and zero allocated bytes.
3. Verify Prefill, Decode, proxy, and Mooncake health.
4. Verify the active runtime identity still matches the requested variant.

Warmup and formal attempts use disjoint deterministic fixture slices. Resetting
Mooncake between them prevents the warmup from creating a formal-run KV hit.

## Warmup Protocol

Each workload profile performs one real warmup wave:

```text
concurrency: 8
request count: 8
```

Warmup exercises the complete Prefill, KV transfer, and Decode path. Its result
is excluded from performance comparisons. It is not subject to a stable-stage
duration rule, request-count growth, or automatic retry.

## Formal Protocol

Each point performs one formal wave:

```text
concurrency: 8
request count: 8
formal repetitions: 1
```

The formal attempt does not grow its request count and is not automatically
retried for duration. A slow valid request continues naturally; the performance
plan defines no point or global wall-clock timeout.

The AISBench calculator changes from `StablePerfMetricCalculator` to
`DefaultPerfMetricCalculator`. The default calculator includes every request in
the total stage and is appropriate for the explicitly single-wave contract.
The report must not label these results as steady-state measurements.

## Correctness And Identity Gates

Every formal point requires:

- all eight requests to succeed;
- exact 16384-token prompts and requested completion length;
- valid OpenAI-compatible response structure and finish reason;
- unchanged source, image, model, tokenizer, fixture, and handoff identity;
- the intended whole-key or ranged transfer mode;
- healthy Prefill and Decode workers after traffic;
- empty Mooncake state after cleanup;
- no save-gate stall, corruption, or leaked ownership.

Runtime identity additionally requires:

- BULK to use whole-key transfer and 27 independent physical layer slots;
- LAYERWISE to use ranged transfer and 27 independent physical layer slots;
- REUSE3 Prefill to use ranged transfer and map 27 logical layers to five
  physical slots;
- REUSE3 Decode to remain a no-reuse pure consumer.

Performance values have no pass/fail threshold. Correctness and identity remain
fail-closed.

## Metrics And Interpretation

Test 1 reports:

- input-token and request throughput;
- TTFT and E2EL median and maximum;
- output-token throughput, TPOT, and ITL;
- the direct `LAYERWISE / BULK` ratios.

Test 2 reports:

- input-token and request throughput;
- TTFT and E2EL median and maximum;
- achieved concurrency;
- Prefill NPU utilization and HBM;
- Mooncake ranged-transfer counters;
- direct `REUSE3 / LAYERWISE` and auxiliary `REUSE3 / BULK` ratios.

All eight per-request rows remain visible. P95 may be rendered as a raw AISBench
field but is not a primary conclusion for an eight-request sample. The report
does not delete outliers, calculate significance, or generalize beyond the one
frozen workload point.

## Evidence Design

Store once per run:

- source, remote, handoff, image, model, tokenizer, and cluster identity;
- the 16384-token fixture bank and its checksum;
- rendered runtime configurations;
- pre-run state and restoration targets.

Store once per variant:

- runtime identity and correctness canary;
- complete Prefill and Decode logs;
- variant-level NPU and Mooncake telemetry.

Store once per point:

- AISBench aggregate metrics and all request details;
- effective config and fixture-slice manifest;
- Mooncake pre/post snapshots;
- response correctness and engine-health results;
- reduced NPU/HBM samples.

Sample NPU and Mooncake telemetry every ten seconds rather than every second.
On failure, immediately capture complete logs, Pod state, processes, metrics,
and the failure classification.

The command ledger stores argv, return code, timestamps, and references to
owned artifacts. It does not duplicate a complete log already stored elsewhere.
Point directories reference the shared fixture by slice manifest and checksum
instead of copying full prompt text into every attempt.

The evidence root ends with a replayed `SHA256SUMS`. Expected evidence size is
below 200 MiB under normal logging volume, not a correctness gate based on size.

## Failure And Recovery

The plan defines no performance-duration timeout. A valid slow point keeps
running.

Stop formal publication on:

- a wrong response or token count;
- transfer-path or physical-slot mismatch;
- source, image, handoff, model, tokenizer, or fixture drift;
- worker exit or OOM;
- Mooncake cleanup failure;
- missing evidence or checker failure.

Preserve the failed attempt without overwrite. Do not automatically retry the
same point in the formal root. A tooling or infrastructure repair requires a
new run root and complete five-point rerun under one uniform protocol.

On completion or failure, stop engines created by the run, return Mooncake to
zero keys and zero allocated bytes, prove physical NPU process release, and
restore the exact pre-run Deployments and ConfigMaps. Retain the CPU-only
AISBench Pod.

## Source And Handoff Transition

The redesign changes only feature-local performance tooling, tests, and
documentation. It does not change vLLM, vLLM-Ascend, Mooncake, or the reusable
server image.

Before implementation begins, preserve and stop the superseded runner and
restore its cluster state. After the redesigned tooling passes all CPU/mock
gates:

1. Commit the performance-owned tooling and documentation.
2. Revalidate the unchanged functional source, image, and evidence identities.
3. Publish generation 5 as a handoff-only direct child of the redesign commit.
4. Start the new formal run from the accepted generation-5 checkout.
5. Create no control-repository commit between handoff acceptance and formal
   run completion.

## Test Strategy

CPU/mock tests must prove:

- the matrix contains exactly the five named points;
- only DP1, 16384 input tokens, concurrency 8, and request count 8 are allowed;
- Test 1 has BULK/LAYERWISE with `max_tokens=128`;
- Test 2 has BULK/LAYERWISE/REUSE3 with `max_tokens=1`;
- shared-buffer defaults are absent rather than serialized as a new value;
- `DefaultPerfMetricCalculator` is rendered;
- each workload profile has one warmup and one formal attempt;
- warmup and formal cannot grow request counts or retry automatically;
- the lifecycle starts exactly three runtime variants in the approved order;
- fixtures and complete logs are not duplicated per point;
- the checker rejects missing points, extra points, duplicate repetitions,
  wrong requests, wrong variants, identity drift, and bad checksums;
- the report renders all raw request rows and the three approved ratios.

Run the complete performance tooling tests in the dedicated CPU-only
`liangjiahao/vllm-ascend-ut` Pod. Also run Python compilation, changed-file Ruff
check and format check, shell syntax, `git diff --check`, namespace scans, and
the handoff checker before NPU traffic.

## Completion Criteria

The rapid validation is complete only when:

1. The superseded run is preserved as diagnostic evidence and its cluster state
   is restored.
2. The redesigned CPU/mock and static gates pass.
3. Generation 5 accepts the unchanged functional source, image, and evidence.
4. All five formal points complete under the frozen single-wave protocol.
5. Every correctness and identity gate passes.
6. The report contains all raw rows and approved direct ratios.
7. The evidence checksum replays from the repository import.
8. Mooncake, NPU, Deployment, and ConfigMap state is restored.
9. Performance-owned changes, report, and evidence are committed and pushed,
   and local/remote equality is proven.
