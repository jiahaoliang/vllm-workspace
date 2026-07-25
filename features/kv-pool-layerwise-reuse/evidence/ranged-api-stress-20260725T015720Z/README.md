# Stress Run 20260725T015720Z

**Status:** Harness contract failure during S1 case 0.

The driver rejected a valid `kv_transfer_params: null` Prefill response. The
preserved raw artifacts proved the shared-hash KVPool contract and per-chunk
commit behavior used by correction commit `2dc15c7`.

Key files:

- `failure.txt`, `runner.exit-code`, and `command-transcript.log`;
- `s1-pinned-16k/remote-artifacts-after-failure/`;
- `final/vllm-prefill.log` and `final/vllm-decode.log`;
- `final-run-state.json`.

