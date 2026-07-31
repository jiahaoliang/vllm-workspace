# Smoke Failure Evidence

Status: **FAILED - confirmed production concurrent layerwise KV-load defect**.

The formal runner passed cold baseline, warmup, proxy concurrency, and 12/12
log correlations. Direct warm concurrency failed only case 2: response
`cmpl-b4925b9042a7f091` omitted `CASE_TWO` while Decode logged `25/25` blocks,
3200 hit tokens, and `use_layerwise=True`. Its serial replay passed.

`diagnostics/focused-replay.py` reduced the trigger to the case 2/case 3 pair.
Warm pair 2/3 failed 9/30 repeat rounds, always case 2. After stopping both
engines and resetting Master, the identical cold pair passed 30/30; all 60
response IDs correlated with `hit_blocks=0/25` in
`diagnostics/cold-hit-correlation.txt`.

Key files:

- `summary.json`: machine-readable terminal classification;
- `artifact-assertions.json`: fail-closed evidence checks;
- `runner-output/`: complete formal runner responses and logs;
- `diagnostics/pair-2-3-repeat-30.json`: warm minimal reproducer;
- `diagnostics/cold-pair-2-3-repeat-30.json`: cold control;
- `diagnostics/cold-vllm-decode.log`: cold Decode log;
- `final-reset.metrics`: zero-key/bytes/client cleanup proof.

The diagnostic driver's first invocation used nonexistent
`decode-engine-service` DNS and failed before reaching the target path. The
evidence driver was corrected to use the formal runner's proxy endpoint
discovery. That validation-only issue is recorded in the plan and report; no
production source changed.

Stress S1-S3 was intentionally not run after this terminal failure.
