# Mooncake Layerwise KVPool Deployment Validation, 2026-07-23

## Result

The deployment smoke passed for this path:

```text
standard Kubernetes proxy
  -> AscendStoreConnector producer
  -> Mooncake shared KVPool
  -> AscendStoreConnector consumer
```

This is smoke-level evidence for routing, shared block-key visibility, and a
successful consumer layerwise load. It is not strict proof that every physical
layer used the ranged APIs or that the whole-key APIs were never called; the
current source has no structured per-layer operation trace.

## Locked inputs

| Input | Value |
| --- | --- |
| Date | `2026-07-23` |
| Node | `n1` |
| NPU | two `Ascend910B4`, 32 GiB each |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2` |
| Model | `vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| vLLM source | `ee0da84ab9e04ac7610e28580af62c365e898389` |
| vLLM-Ascend source | `663209fd6208a59a48742f75116345bf5f5281ec` |
| Mooncake source | `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` |
| Namespace | `ai-inference` |

The image's shallow editable vLLM install reports
`0.1.dev1+gee0da84ab`; both engine Pods used the supported
`VLLM_VERSION=0.24.0` compatibility override.

## Deployment state

All four workloads were `Running` and Ready on `n1`. The proxy discovered the
current prefiller at `10.250.40.143:8100` and decoder at
`10.250.40.129:8200`.

The prefill and decode containers both retained `sleep` as PID 1. Their vLLM
API servers were started manually with `/opt/vllm-layerwise/start-prefill.sh`
and `/opt/vllm-layerwise/start-decode.sh`; both were PID 113 at capture time.
This confirms that a vLLM process can be stopped, source can be synced, and the
process can be restarted without replacing the Pod.

The runtime check passed in both engine Pods:

- `vllm_ascend` imported from `/vllm-workspace/vllm-ascend`;
- the vLLM-Ascend compatibility gate selected `0.24.0`;
- `PYTHONHASHSEED=0` was identical across processes;
- all seven required Mooncake session/range methods were callable.

## Smoke evidence

Mooncake Master was restarted before the test. Its initial metrics showed zero
allocated bytes and zero keys. The smoke helper generated a 3205-token shared
prefix, then sent two requests through the proxy with different suffixes.

Both proxy requests returned HTTP 200 with non-empty `choices`. For the first
request:

- prefiller: `hit_blocks=0/25`;
- decoder: `hit_blocks=25/25`;
- decoder: `kvpool hit tokens: 3200, need to load: 3200`;
- decoder: `load_async=False use_layerwise=True`.

For the second request, both the prefiller and decoder reported `25/25`, and
both created a 3200-token layerwise load spec. Proxy logs showed each request
was forwarded first to `10.250.40.143:8100` and then to
`10.250.40.129:8200`.

The saved Master metrics showed:

| Metric | Value |
| --- | ---: |
| `master_key_count` | 25 |
| `master_allocated_bytes` | 99,532,800 |
| `master_total_capacity_bytes` | 2,147,483,648 |
| `master_active_clients` | 2 |
| current prefiller segment | 1,073,741,824 bytes |
| current decoder segment | 1,073,741,824 bytes |

Each worker logged a 1 GiB segment mount. A later
`Global segment size is 0, skip mounting segment` line belongs to the
non-contributing scheduler-side client, not to the worker-side store. The
Master capacity and per-segment metrics confirm the two worker segments.

The second prefiller request attempted `batch_put_start` for the 25 already
complete keys. Master recorded one failed batch and logged
`object_already_exists` for each key. This is the expected duplicate-start
conflict; the existing objects remained readable and both decoder loads
succeeded. `batch_put_end` and batch-get failure counters remained zero.

Artifacts are retained in the prefiller Pod under
`/tmp/layerwise-smoke/`: the two JSON responses and the Mooncake Master metrics
snapshot. The helper was then extended to also save `proxy-endpoints.json` on
subsequent runs. These artifacts are ephemeral and disappear when that Pod is
replaced.

## Issue found during validation

The first attempt omitted `PYTHONHASHSEED`. vLLM initializes the root of its
block-hash chain randomly when this variable is absent. The producer could see
its own 25 keys, but the independent decoder process computed different keys
and reported `0/25`.

Both engine manifests now set `PYTHONHASHSEED=0`, and `check-runtime.py`
asserts it. After recreating only the two sleep Pods and manually restarting
vLLM, the first decoder request changed from `0/25` to `25/25`.

## Remaining acceptance work

This run does not claim the strict matrix from
`development-confirmation-request.md`. That requires opt-in structured trace
evidence for every chunk and physical layer, ranged offsets and byte counts,
successful session close semantics, zero whole-key operations, and injected
lease/failure paths. Those assertions cannot be recovered from HTTP status,
scheduler hit logs, or aggregate Master metrics alone.
