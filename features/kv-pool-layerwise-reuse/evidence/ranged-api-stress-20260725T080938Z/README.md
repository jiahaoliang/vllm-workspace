# Stress Run 20260725T080938Z

**Status:** Passed the complete S1 to S2 to S3 sequence.

This formal run used control commit `988f475`, vLLM `ee0da84`, vLLM-Ascend
`3f0cbf5`, Mooncake `74b0acf`, and image
`docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2`. The Master
deployment and startup log both confirm a 30-second read lease
(`default_kv_lease_ttl=30000`).

- S1: 4/4 marker prefix matches, 4/4 isolation checks, 4/4 diagnostic full
  matches, and 508 keys.
- S2: 16/16 marker prefix matches, 16/16 isolation checks, 7/16 diagnostic
  full matches, and 288 keys. Every divergent continuation first differs at
  token index 7, after the dynamically encoded marker.
- S3: 4/4 marker prefix matches, 4/4 isolation checks, 4/4 diagnostic full
  matches, and 348 keys. The cold 32K checker and aggregate checker both
  passed, with physical layers 0 through 26, DP0 and DP1 activity, 1024-token
  chunk ceiling, and zero whole-key events.

`overall-summary.json` is the top-level machine-readable result. Raw baseline
and candidate responses, fixtures, metrics, complete engine logs, topology,
per-scenario checker outputs, command transcript, and final stopped state are
all retained. `static/pytest.log` records 48 passing tests and
`static/offline-recheck.log` records the independent offline assertions.
