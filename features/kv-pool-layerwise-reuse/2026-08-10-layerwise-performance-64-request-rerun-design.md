# Mooncake Layerwise 64-Request Performance Rerun Design

## Status

Approved by the user on 2026-08-10.

This document changes only the sampling depth of the completed rapid DP1
design in `2026-08-09-layerwise-performance-rapid-validation-design.md`.
The five points, topology, input length, concurrency, variants, server order,
image, correctness gates, telemetry, restoration, and no-retry policy remain
unchanged.

## Frozen Delta

```text
topology: DP1
input tokens: 16384
concurrency: 8
warmup requests per point: 8
formal requests per point: 64
formal repetitions: 1
automatic retries: 0
performance timeout: none
```

The formal request count produces eight concurrency waves inside one AISBench
formal attempt. It replaces the previous one-wave, eight-request sampling
depth. Warmup remains one concurrency wave and is excluded from comparisons.

## Matrix

| Test | Variant | Output tokens | Warmup requests | Formal requests |
| --- | --- | ---: | ---: | ---: |
| Test 1 | BULK | 128 | 8 | 64 |
| Test 1 | LAYERWISE | 128 | 8 | 64 |
| Test 2 | BULK | 1 | 8 | 64 |
| Test 2 | LAYERWISE | 1 | 8 | 64 |
| Test 2 | REUSE3 | 1 | 8 | 64 |

The complete run sends 40 warmup requests and 320 formal requests. BULK,
LAYERWISE, and REUSE3 are still started exactly once each.

## Evidence And Interpretation

Warmup and formal prompts come from disjoint deterministic fixture partitions.
All 64 formal responses per point must succeed with exact input and output token
counts. The checker requires `warmup_request_count=8`,
`formal_request_count=64`, one formal repetition, and eight formal concurrency
waves.

The additional requests improve within-attempt coverage and reduce the effect
of a single concurrency wave. They do not create independent run repetitions,
so the report remains a raw characterization without significance claims or a
performance pass/fail threshold.

The run defines no performance timeout. A valid slow point continues naturally.
An invalid point is not retried in the same evidence root.
