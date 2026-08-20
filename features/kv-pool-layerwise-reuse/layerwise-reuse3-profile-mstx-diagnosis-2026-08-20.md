# Test 2 Profiling + MSTX Diagnosis

Compact evidence, analysis code, layer timelines, request identities, overlay
checksums, and the raw checksum inventory are under
[`artifact-manifests/layerwise-issue1-profile-mstx-20260819T184617+0800/`](artifact-manifests/layerwise-issue1-profile-mstx-20260819T184617+0800/README.md).

The 17 GB raw profiler tree remains transient under `/tmp`; it is not committed
or represented as a durable external archive.

## Conclusion

The slowdown is resolved to the layerwise host load path, not to additional model
compute. REUSE3 repeatedly reaches the model thread before the prefetched layer is
ready. Receive-thread queueing and address construction feed a late
`batch_copy_get`; `wait_for_layer_load()` then exposes that delay as NPU Free.
Communication time also increases, but it is secondary to Free in the stable-c20
window.

This diagnosis does not require a Mooncake native change or another software
upgrade. It identifies the Python host orchestration/load boundary only.

## Run Identity

- Namespace: `liangjiahao`
- vLLM: `baf481c7f`
- vLLM-Ascend: `c97cef309`
- Mooncake native: `df3f74ed`
- Prefill: DP1/TP2 on physical NPU 2,3
- Decode: DP1/TP2 on physical NPU 4,5
- Physical NPU0 was held by `profile-mstx-reserve-1`; no model used NPU0.
- Input/output: 32,000 / 1 tokens
- Seed/external hit: 28,800 tokens / 225 keys / 895,795,200 bytes
- Every formal request passed its response token checks and initial Prefill lookup
  check (`kvpool hit tokens: 28800`).

## Primary Evidence

The full-wave client ratio was stable across both runs:

| Point | BULK wall | REUSE3 wall | REUSE3 / BULK |
|---|---:|---:|---:|
| c1 | 9.396 s | 24.414 s | 2.598x |
| c20 stable rerun | 91.663 s | 242.834 s | 2.649x |

The stable-c20 profiler window covered REUSE3 step 485-487. Both TP ranks had
exactly 25 load tasks per step and every task had `request_call_count=20`.
The original delay=3 c20 trace covered ramp steps with about 5, 8, and 20 calls;
it is retained as a pilot and is not used as the stable-window result.

Average across TP0/TP1 for the three-step stable window:

| Variant | Stage | Computing | Non-overlapped communication | Free | Free share |
|---|---:|---:|---:|---:|---:|
| BULK | 10.124 s | 5.819 s | 3.033 s | 1.272 s | 12.6% |
| REUSE3 | 28.665 s | 5.821 s | 6.672 s | 16.172 s | 56.4% |

Computing differs by only 0.003 s. Of the 18.541 s REUSE3 stage increase,
14.899 s (80.4%) is additional Free and 3.639 s (19.6%) is additional
non-overlapped communication. This rejects the compute-path explanation.

The same direction appears in c1. Average Free rises from 2.953 s in BULK to
13.401 s in REUSE3, while average Computing slightly decreases from 3.077 s to
2.910 s. Communication rises from 2.817 s to 7.335 s, so c1 also shows a
secondary communication contribution.

## Host Range Correlation

Stable-c20 REUSE3, aggregated over step 485-487:

| Host stage | TP0 | TP1 | NPU idle inside range |
|---|---:|---:|---:|
| receive queue wait, mean per layer | 881 ms | 919 ms | marker reports preceding queue delay |
| `address_build`, mean | 127 ms | 107 ms | 80.2% / 89.0% |
| `batch_copy_get`, mean from structured timing | 220 ms | 218 ms | request scopes intentionally off |
| `layer_task_total`, mean | 362 ms | 367 ms | 52.3% / 62.5% |
| `model_wait`, mean MSTX range | 238 ms | 264 ms | 45.2% / 57.7% |

Queue p95 is 1.588 s on TP0 and 1.603 s on TP1. Address construction is mostly
NPU-idle wall time, and model wait remains material on every profiled layer.
Therefore the prefetch is not consistently complete before the target layer is
used. The observed sequence is:

`receive queue -> address_build/batch_copy_get -> model_wait -> NPU Free`

This matches the Host orchestration/address-preparation classification.

At c1, request-scoped `batch_copy_get` ranges prove partial overlap with NPU work:
55.5% of TP0 copy-range time and 58.1% of TP1 copy-range time overlaps at least
one NPU task. The remaining 44.5% / 41.9% is NPU idle. Across the 25 chunks,
`address_build` averages about 10 ms per layer, copy averages 17.2/15.7 ms,
receive queue wait averages 41.5/37.8 ms, and model wait p95 is 15.5/13.7 ms
from structured timing. Overlap exists, but it is insufficient to hide the load.

BULK is not free of synchronous load idle. Its c1 `bulk_get` lasts 279/286 ms
and is about 95% NPU idle. The important difference is lifecycle: BULK performs
the request load once, whereas REUSE3 repeatedly schedules address/copy work and
gates model use by layer.

## Artifacts And Limits

- `profile-mstx-summary.json`: structured step, kernel, range, and timing
  aggregates.
- `reuse3-c1-layer-timeline.csv`: rank/chunk/layer address, copy, model-wait, and
  NPU-idle intersections (1,350 rows).
- `reuse3-c20-stable-layer-timeline.csv`: stable three-step layer detail.
- Each formal point contains TP0/TP1 raw `_ascend_pt`, parsed
  `trace_view.json`, CSVs, full Prefill/Decode logs, and client JSON.
- The analyser emits `Unknown communication op type: hccl_batchPut/Get`; both
  ranks still completed with `analyse.done` and valid step/trace exports.
- Mooncake TE text metrics are cumulative service reports. BULK reports
  `Batch Get`, while the layerwise path does not expose an equivalent report.
  They are retained in full logs but are not used for the causal percentages.
- c20 request-scoped copy MSTX was intentionally disabled. Its copy duration is
  taken from `[DEBUG-REUSE3-LOAD]`; NPU intersection is reported for the enclosing
  `layer_task_total` range.

The delay=6 stable rerun is a documented correction to the planned delay=3
window after runtime evidence showed that delay=3 sampled concurrency ramp-up.
All model, scheduler, workload, NPU, and KVPool settings remained unchanged.
