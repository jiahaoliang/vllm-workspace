# Test 2 Load-Timing Artifact Inventory

This directory archives the compact, reviewable products from the accepted
2026-08-17 BULK/REUSE3 load-timing diagnosis and inventories the complete raw
staging tree.

## Archived in Git

- The main diagnosis is
  [`../../layerwise-reuse3-load-timing-diagnosis-2026-08-17.md`](../../layerwise-reuse3-load-timing-diagnosis-2026-08-17.md).
- `RUN-IDENTITY.md` records source, image, fixture, NPU, debug, and cleanup
  identity.
- `load-timing-summary.md` and `load-timing-summary.json` preserve the compact
  human-readable and structured analysis results.
- `analyze_load_timing.py` is the analysis program used for the report.
- `vllm-ascend-load-timing-instrumentation.patch` preserves the diagnostic-only
  instrumentation patch.

## Raw Payload Status

The complete raw staging tree is 723 MiB at:

```text
/tmp/layerwise-issue1-load-timing-20260817T181503+0800/
```

`RAW-SHA256SUMS` inventories every file in that tree. The raw payload is not
committed to Git and has no workspace-external durable archive, so it remains
transient evidence. `archive.json` records this boundary explicitly. The
committed report and compact analysis products are durable Git content; the
manifest must not be represented as durable publication of the large raw
logs.

## Verification

While the staging tree still exists:

```bash
cd /tmp/layerwise-issue1-load-timing-20260817T181503+0800
sha256sum --check /root/ljh/vllm-workspace/features/kv-pool-layerwise-reuse/artifact-manifests/layerwise-issue1-load-timing-20260817T181503+0800/RAW-SHA256SUMS
```
