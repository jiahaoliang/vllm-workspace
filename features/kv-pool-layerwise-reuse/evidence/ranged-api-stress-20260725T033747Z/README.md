# Stress Run 20260725T033747Z

**Status:** Reproduced runtime acceptance failure at S1 exact-output gate.

The unchanged-strength retry completed all four S1 pinned requests. Every
ranged checker passed with Prefill load/save and Decode load layers 0..26,
16 context iterations per request, 127 committed keys per request, and zero
whole-key events. Marker isolation was 4/4, but case 3 cached Decode text did
not exactly match its empty-pool baseline, producing 3/4 exact matches. The run
failed closed before S2 and S3.

Key files:

- `s1-pinned-16k/remote-artifacts-after-failure/scenario-summary.json`;
- `s1-pinned-16k/remote-artifacts-after-failure/{baseline,pinned}/`;
- `s1-pinned-16k/case-0-check.json` through `case-3-check.json`;
- `topology/check.json`, `static/pytest.log`, `failure.txt`,
  `command-transcript.log`, and `final-run-state.json`.

