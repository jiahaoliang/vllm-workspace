# Mooncake Shared-Buffer Functional Acceptance

Run: `20260808T203742Z`

Status: **PASS**

## Frozen Identity

| Field | Value |
| --- | --- |
| Control image-freeze commit | `fb2474c66b871e6c93750603ee9189ee4add4759` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend | `d74269a08e48e3b5b097f9a34f5c421696ddda40` |
| Mooncake | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-d74269a0-df3f74ed-20260808T203742Z` |
| Manifest | `sha256:3c02653463562e8bfff717e6ade962ab1a2c661de59ae9f310bc050528fa81bd` |
| Config | `sha256:7277450f383361eae3481c09be913522e0fa62a11d9c78eaf753a5542f4783eb` |
| Platform | `linux/arm64` |

The image is an eight-file cumulative Python patch of the frozen `45b2e785`
native base followed by `nerdctl commit`. OCI metadata correction changed only
config and manifest metadata; the 22 filesystem layer descriptors are identical
to the pre-metadata commit image. All eight in-image file hashes equal the clean
`d74269a08` checkout.

## CPU And Mock Gates

| Gate | Result |
| --- | --- |
| Complete AscendStore | `514 passed` |
| All role/default layerwise config | `20 passed` |
| Model-runner layer-reuse layout | `3 passed` |
| Deployment + performance mocks | `145 passed` |
| Performance harness | `60 passed` |
| Ruff lint / format | PASS |
| In-memory Python compilation | PASS |
| Source and control `git diff --check` | PASS |

Role coverage includes `kv_producer`, `kv_both`, `kv_consumer` with
`consumer_is_to_put=true`, pure `kv_consumer` startup rejection when a non-null
shared-buffer value is configured, and the absent/null default behavior.

The separate worker memory-factor CPU diagnostic cannot import
`torch_npu.op_plugin.atb` in the CPU-only image and stops before its test body.
This known environment limitation is preserved in
`cpu/pytest-worker-memory-factor.log`; it is not a required gate. The real-NPU
startup log is the hard proof for 27 logical layers, 5 physical slots, and
logical KV factor 5.400.

## NPU Acceptance

The serial 1-NPU functional runner completed `61/61` steps with no failure:

- no-reuse producer baseline;
- `kv_producer` with `layerwise_num_shared_buffers=3`;
- `kv_both` cold and warm with `layerwise_num_shared_buffers=3`.

All four responses are exactly:

```text
 The private audit marker is a marker that is used to indicate that the audit content
```

Each used 525 prompt tokens and 16 completion tokens with
`finish_reason=length`. Producer reuse emitted 405 ranged loads over 15 ordered
layer groups. `kv_both` emitted 837 ranged loads over 31 groups. Every save,
load, and commit result passed; no whole-key call, timeout, abort-drain failure,
traceback, or response corruption was observed. Each case stopped the engine,
released its NPU, and ended with Master metrics `0/0/0`.

## Initial Partial-Load Regression Canary

The DP1 companion canary used the exact prepared 4096-token fixture with a
Mooncake layerwise producer and a pure-consumer Decode, both TP2 on the same
final image. It reproduced the old boundary conditions without the old failure:

- `hit_blocks=32/32`;
- `kvpool hit tokens: 4095`, leaving the same 127-token partial tail;
- `vllm_cached=0`, proving this was the initial remote load path;
- Prefill and Decode each returned HTTP 200;
- response usage was exactly 4096 prompt plus 1 completion token;
- no `KV load failure` or request failure appeared in either log.

This is the runtime companion to the CPU red/green regression that changed the
initial partial-load key from process-local request identity to the block hash.
After the canary, both TP2 process groups released all NPUs and Master returned
to `0/0/0`.

## Preserved Diagnostics

Two invocation-only CPU attempts are retained: an incorrect performance test
target and a deployment sync with insufficient parent directories. Both stopped
before running their intended tests; corrected attempts passed. The historical
performance root `/tmp/layerwise-performance-20260808T155856Z` remains bound to
`a3c97358` and image manifest `sha256:32b379...`; it must not be resumed with
this generation-2 identity.

## Scope

Real-NPU shared-buffer coverage remains limited to `kv_producer` and `kv_both`.
The pure-consumer NPU case is the required no-reuse companion only; it does not
configure `layerwise_num_shared_buffers`. This report does not claim memcache
changes, FabricMem, A3, Mooncake multi-group, or performance results.
