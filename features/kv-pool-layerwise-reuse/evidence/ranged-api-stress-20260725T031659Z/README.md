# Stress Run 20260725T031659Z

**Status:** Runtime acceptance failure at S2 exact-output gate.

S1 passed all gates. S2 completed 16 concurrent HTTP requests, exercised both
Prefill DP ranks, covered ranged load/save on layers 0..26, committed exactly
288 keys, and emitted zero whole-key events. Marker isolation was 16/16, but
only 8/16 cached Decode response signatures exactly matched their empty-pool
baselines, so the run failed closed. S3 was not executed.

Key files:

- `s1-pinned-16k/artifacts/scenario-summary.json`;
- `s2-concurrent-16x8k/aggregate-check.json`;
- `s2-concurrent-16x8k/remote-artifacts-after-failure/scenario-summary.json`;
- `s2-concurrent-16x8k/remote-artifacts-after-failure/{baseline,proxy}/`;
- `failure.txt`, `runner.exit-code`, `command-transcript.log`, and
  `final-run-state.json`.

