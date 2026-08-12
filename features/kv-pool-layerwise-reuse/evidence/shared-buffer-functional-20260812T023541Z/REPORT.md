# Mooncake Shared-Buffer Candidate Functional Acceptance

Run: `20260812T023541Z`

Status: **PASS**

## Identity

- vLLM: `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`
- vLLM-Ascend: `57d3c214e642cdbb529400f0742d1a98a8d38708`
- Mooncake: `df3f74ed8ebdb0c935554beea6299a9f11c723e2`
- Image: `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z`
- Manifest: `sha256:f8592141757f7e9976898858863e12ccd051ac4a3fd6ade7591f78d9769517e3`
- Runtime: namespace `liangjiahao`, node `m1`, physical `huawei.com/Ascend910`

## CPU And Mock Gates

- Performance harness: `91 passed`.
- Focused no-self-load regression: `1 passed`.
- Mooncake layer-session class: `27 passed`.
- Complete AscendStore suite: `516 passed`.
- Ruff 0.16.2 passed the two-file candidate source delta with rules
  `E4,E7,E9,F,I` and the 11-file performance delta with core error rules.
- Two source-delta and 20 performance Python files compiled in memory.
- vLLM-Ascend and control-repo `git diff --check` passed before evidence import.

All CPU/mock tests ran in the dedicated `liangjiahao/vllm-ascend-ut` Pod on
`m1`. The Pod requested neither physical Ascend910 nor vNPU resources and had
no `hostPath` volume. The synchronized source marker records clean
`57d3c214e642cdbb529400f0742d1a98a8d38708`.

## Real NPU Gates

The serial one-NPU runner completed all 63 recorded steps with no failure:

- no-reuse `kv_producer` baseline;
- `kv_producer` with `layerwise_num_shared_buffers=3`;
- `kv_both` cold and warm with `layerwise_num_shared_buffers=3`.

All four responses had identical text, `525` prompt tokens, `16` completion
tokens, and `finish_reason=length`. The strict validator proved all 27 logical
layers, five physical slots, logical memory factor 5.4, key-major ranged
save/load/commit results, zero whole-key calls, and no timeout, abort-drain
failure, traceback, or response corruption. Expected Mooncake key counts were
4 for baseline, 20 for producer reuse, and 20 then 36 for `kv_both` cold/warm.

Each case stopped the engine, released the NPU, restarted Mooncake Master, and
ended at `master_key_count=0`, `master_allocated_bytes=0`, and
`master_active_clients=0`. After deleting only the functional Prefill/Master
resources, Kubernetes reported `allocatable=8`, `free=8`, and the host reported
no running NPU process.

## Scope

Real-NPU shared-buffer coverage is limited to `kv_producer` and `kv_both`, as
approved. CPU/mock coverage retains every role and the pure-consumer startup
rejection. This run does not claim memcache changes, pure-consumer shared-buffer
support, FabricMem, A3, Mooncake multi-group support, or performance results.
