# Stress Run 20260725T014317Z

**Status:** Harness failure before workload execution.

The initial Master reset failed because the Pod resolver counted a terminating
Pod together with its Running replacement. No S1-S3 request was sent. The
resolver correction is commit `4d5a17e`.

Key files:

- `failure.txt` and `runner.exit-code`: terminal result;
- `command-transcript.log` and `steps.jsonl`: exact executed commands;
- `pods-before.json` and `final/`: cluster state and cleanup evidence.

