# Mooncake Shared-Buffer Functional Acceptance

Run: `20260809T071622Z`

Status: **PASS**

## Frozen Identity

| Field | Value |
| --- | --- |
| Control source parent | `e200f4574ebac32d090f577994df742925ed1dd5` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend | `5355559175f9998f5d70866734fb79569dfc86f9` |
| Mooncake | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-535555917-df3f74ed-20260809T070557Z` |
| Manifest | `sha256:cf5da7c1da7dcb72f4c22e201d628b9e4aa819f53c15711651ebc9241cb955bc` |
| Config | `sha256:b138ce816ae0b4183f77a6e9b83bc95061a6c1053f770d2f0462699de86a7a0c` |
| Platform | `linux/arm64` |

The image is an eight-file cumulative Python patch of the frozen `45b2e785`
native base followed by `nerdctl commit`. OCI metadata correction changed only
config and manifest metadata: the pre-metadata and final images have the same
22 filesystem layer descriptors. All eight in-image file hashes equal the
clean `535555917` checkout. The additional patch layer is
`sha256:a35b3719277716bb4b9eeb5e001b26bf151752f6d4943addb94696e47f8402c1`.

## CPU And Mock Gates

| Gate | Result |
| --- | --- |
| TP2 non-save-owner threaded regression | `1 passed` |
| Complete AscendStore | `515 passed` |
| All role/default layerwise config | `20 passed` |
| MLA decode scoped layer wait | `1 passed` |
| Model-runner layer-reuse layout | `3 passed` |
| Deployment + performance mocks | `146 passed` |
| Performance harness | `61 passed` |
| Ruff lint / format | PASS |
| Python compilation and shell syntax | PASS |
| Source and control `git diff --check` | PASS |

Role coverage includes `kv_producer`, `kv_both`, `kv_consumer` with
`consumer_is_to_put=true`, pure `kv_consumer` startup rejection when a non-null
shared-buffer value is configured, and absent/null default behavior. Every
source test log records clean vLLM-Ascend `535555917` synchronized by tar into
the dedicated CPU-only `liangjiahao/vllm-ascend-ut` Pod.

## Targeted TP2 Regression Canary

The exact prepared 4096-token fixture ran through the DP1 proxy topology with:

- Prefill: `kv_producer`, Mooncake layerwise, `layerwise_num_shared_buffers=3`,
  TP2, 5 physical slots, logical KV factor 5.4;
- Decode: pure `kv_consumer`, Mooncake layerwise, no shared-buffer setting,
  TP2, 27 physical slots;
- chunked Prefill, block size 128, output length 1.

The corrected canary returned HTTP 200 from both engines and proved:

- `hit_blocks=32/32`;
- `kvpool hit tokens: 4095`, with a 127-token partial tail;
- `vllm_cached=0`, so this was the initial remote load path;
- exact usage `4096 + 1` and `finish_reason=length`;
- 27 Prefill save layers and all-zero commit results;
- no `KV load failure`, timeout, save-gate timeout, traceback, or response
  corruption;
- post-request Master state `32` keys, `127401984` bytes, `4` active clients;
- final NPU release and Master `0/0/0` after reset.

Two invocation-only diagnostics are retained. The first render attempt stopped
before Kubernetes mutation because the historical template did not create its
`rendered/` directory. The first client attempt stopped before sending traffic
because it addressed fixtures outside the AISBench exact-rootfs chroot. The
corrected retry used the performance harness chroot contract and passed. Neither
diagnostic is a production-source failure.

## Real-NPU Role Acceptance

The serial 1-NPU functional runner completed all 61 runtime steps with no
failure:

- no-reuse producer baseline;
- `kv_producer` with `layerwise_num_shared_buffers=3`;
- `kv_both` cold and warm with `layerwise_num_shared_buffers=3`.

All four responses are exactly:

```text
 The private audit marker is a marker that is used to indicate that the audit content
```

Each used 525 prompt tokens and 16 completion tokens with
`finish_reason=length`. Producer reuse emitted 405 ranged loads over 15 ordered
layer groups. `kv_both` emitted 837 ranged loads over 31 groups, including the
warm prefix. Every save, load, and commit result passed; no whole-key call,
timeout, abort-drain failure, traceback, or response corruption was observed.
Each case stopped the engine, released its NPU, and ended with Master metrics
`0/0/0`.

## Scope

Real-NPU shared-buffer coverage is limited to `kv_producer` and `kv_both`. The
pure-consumer TP2 case is the required no-reuse companion and does not configure
`layerwise_num_shared_buffers`. This report does not claim memcache changes,
pure-consumer shared-buffer support, FabricMem, A3, Mooncake multi-group, or
performance results.
