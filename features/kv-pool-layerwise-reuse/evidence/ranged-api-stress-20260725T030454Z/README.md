# Stress Run 20260725T030454Z

**Status:** Harness readiness failure before engine startup.

Mooncake Master rollout completed, but the first metrics request raced Service
endpoint propagation and received a transient connection refusal. No vLLM
process or workload was started. The bounded readiness correction is commit
`91f75ea`.

Key files:

- `failure.txt`, `runner.exit-code`, and `command-transcript.log`;
- `master-rollout-030558.log` and `master-empty-initial.metrics`;
- `final/mooncake-master.log` and `final-run-state.json`.

