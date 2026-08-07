# Full Validation Evidence 20260807T100722Z

Status: NATIVE_IMAGE_AND_UT_VERIFIED. Source/tooling, the exact native ARM64
image, and native-image CPU/mock gates are verified. This directory does not
yet claim A2 runtime, smoke, stress, or throughput success.

## Frozen Inputs

- vLLM `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`
- vLLM-Ascend `45b2e785b10ca4604cd6314819ed15f3ff674781`
- Mooncake `df3f74ed8ebdb0c935554beea6299a9f11c723e2`
- Tooling `4b5e49900a9ea3cd50344cb053747dc9e5a5b07b`
- Target `linux/arm64` image
  `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z`
- Runtime namespace `liangjiahao`; BuildKit namespace `default`
- Python overlay disabled; FabricMem disabled and out of scope

## Completed Runtime Artifacts

- `image/summary.json`: manifest
  `sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351`,
  config
  `sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b`,
  native `linux/arm64`, exact source labels/HEADs, native modules, dependency
  allowlist, and seven static Mooncake session/range APIs.
- The actual BuildKit Pod ran on ARM64 node `m1`. The earlier frozen
  `builder_node: n1` value was a metadata error and was corrected before any
  UT or A2 runtime family. Runtime workloads remain pinned to `n1`.
- `ut/summary.json`: recreated CPU-only `liangjiahao/vllm-ascend-ut` at config
  `sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b`;
  tar-synced clean source passed `495` AscendStore tests, cache-free control
  sync passed `83` deployment tests, and Ruff lint, `py_compile`, source diff,
  package/native-path, and cache-pollution gates passed.

The structured run identity is in `identity.json`; frozen source and tooling
file hashes are in `source-tooling-sha256.txt`. Each completed family records
its own transcript, structured summary, and checksums.
