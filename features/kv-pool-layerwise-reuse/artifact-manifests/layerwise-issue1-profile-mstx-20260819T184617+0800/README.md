# Test 2 Profiling + MSTX Artifact Inventory

This directory archives the compact, reviewable products from the 2026-08-19
BULK/REUSE3 Host-load diagnosis and inventories the complete raw profiler tree.

## Archived In Git

- The main diagnosis is
  [`../../layerwise-reuse3-profile-mstx-diagnosis-2026-08-20.md`](../../layerwise-reuse3-profile-mstx-diagnosis-2026-08-20.md).
- `RUN-IDENTITY.md` records source, image, NPU, workload, profiler, overlay, and
  cleanup identity.
- `ACCEPTANCE.json` is the machine-readable acceptance result for the four
  primary points and the corrected stable-c20 window.
- `formal-request-evidence.jsonl` preserves all 42 formal request IDs, response
  checks, and exact 28,800-token initial external hits.
- `profile-mstx-summary.json`, the two layer timeline CSVs, and `analyze.py`
  preserve the structured analysis and its implementation.
- `vllm-ascend-profile-mstx.patch` and `overlay-sha256.txt` preserve the
  diagnostic-only Python overlay.
- `requests/` contains the warmup, seed, and formal-wave client results for the
  four accepted points.

## Raw Payload Status

The complete 17,506,000,331-byte staging tree remains at:

```text
/tmp/layerwise-issue1-profile-mstx-20260819T184617+0800/
```

It contains the TP0/TP1 raw `_ascend_pt` trees, parsed `trace_view.json`, full
service logs, TE metrics, smoke, delay=3 pilots, stable reruns, identity, and
analysis products. `RAW-SHA256SUMS` inventories all 5,388 files and was replayed
successfully against that staging tree.

The raw payload is not committed to Git and has no workspace-external durable
archive. It is transient evidence; this manifest must not be represented as
durable publication of the raw trace payload.

## Offline Verification

```bash
jq -e '.status == "passed" and .formal_request_evidence_rows == 42' ACCEPTANCE.json
test "$(wc -l < formal-request-evidence.jsonl)" -eq 42
sha256sum --check SHA256SUMS
sha256sum --check RAW-SHA256SUMS.digest
```

While the staging tree still exists:

```bash
cd /tmp/layerwise-issue1-profile-mstx-20260819T184617+0800
sha256sum --check \
  /root/ljh/vllm-workspace/features/kv-pool-layerwise-reuse/artifact-manifests/layerwise-issue1-profile-mstx-20260819T184617+0800/RAW-SHA256SUMS
```
