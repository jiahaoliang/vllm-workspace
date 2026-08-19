# Threshold-0 Test 2 BULK Partial Run

## Status

This directory preserves the minimum reviewable evidence from the incomplete
2026-08-17 threshold-0 BULK attempt. It is failure evidence, not a completed
performance point. No throughput, REUSE3 comparison, ratio, or successful
cleanup claim may be derived from it.

The attempted symmetric Test 2 server configuration used DP1/TP2,
`max_num_batched_tokens=32768`, `max_num_seqs=6`, chunked Prefill, and omitted
`--long-prefill-token-threshold`. The client contract was 32,000 input tokens,
a 28,800-token shared prefix, one output token, and concurrency 40.

## Failure

The Prefill `EngineCore` failed at 2026-08-17 10:06:29 +08:00 with:

```text
TimeoutError: RPC call to sample_tokens timed out.
```

The server then returned HTTP 500 responses and shut down. The retained
`failure-excerpt.log` also records `num_running_reqs=6`,
`num_waiting_reqs=3`, and no preempted request at the fatal scheduler dump.
This archive does not establish why the TP worker failed to return before the
RPC timeout.

## Retention boundary

Git retains only the focused failure excerpt, expanded Prefill/Decode argv,
source HEADs, and overlay checksums. The original 5,745,189-byte staging tree
remains at:

```text
/tmp/layerwise-issue1-threshold0-20260817T095300Z/
```

`RAW-SHA256SUMS` inventories all 15 original files. The full logs, image
inspection, NPU allocation snapshot, dirty-state snapshots, and pre-run
manifests are not committed. Therefore the raw payload is transient, while
the focused excerpt and runtime contract are durably archived in Git.

## Verification

Verify the committed subset from this directory:

```bash
sha256sum --check ARCHIVED-SHA256SUMS
```

While the original staging tree still exists:

```bash
cd /tmp/layerwise-issue1-threshold0-20260817T095300Z
sha256sum --check /root/ljh/vllm-workspace/features/kv-pool-layerwise-reuse/evidence/layerwise-issue1-threshold0-partial-20260817T095300Z/RAW-SHA256SUMS
```
