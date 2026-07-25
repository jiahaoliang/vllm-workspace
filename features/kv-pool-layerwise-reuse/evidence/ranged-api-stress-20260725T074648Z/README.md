# Stress Run 20260725T074648Z

**Status:** Failed closed during the S3 cold pinned Decode request.

This diagnostic run used control commit `13c820c`. S1 passed with 4/4 marker
prefix matches, 4/4 isolation checks, and 508 keys. S2 passed with 16/16
marker prefix matches, 16/16 isolation checks, 11/16 diagnostic full-output
matches, and 288 keys.

The S3 empty-pool baseline passed and the cold Prefill path produced 255 keys.
Decode found `255/255` blocks, but ranged loads at physical layers 22 and 23
returned `-707` for every key. Mooncake defines `-707` as `LEASE_EXPIRED`; the
Master log records the default `default_kv_lease_ttl=5000`, and Decode returned
HTTP 500 after about 5.2 seconds of layerwise reads. The runner copied the
remote scenario, raw responses, metrics, and complete logs before stopping both
engines. No S3 aggregate request was executed.

Key files:

- `s3-concurrent-4x32k/remote-artifacts-after-failure/pinned/`;
- `s3-concurrent-4x32k/failure.metrics`;
- `final/vllm-decode.log`, `final/vllm-prefill.log`, and
  `final/mooncake-master.log`;
- `failure.txt`, `command-transcript.log`, and `final-run-state.json`.
