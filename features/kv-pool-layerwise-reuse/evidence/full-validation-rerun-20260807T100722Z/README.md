# Full Validation Evidence 20260807T100722Z

Status: SOURCE_AND_TOOLING_FROZEN. This directory does not yet contain a native
image or A2 runtime success claim.

## Frozen Inputs

- vLLM `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`
- vLLM-Ascend `45b2e785b10ca4604cd6314819ed15f3ff674781`
- Mooncake `df3f74ed8ebdb0c935554beea6299a9f11c723e2`
- Tooling `4b5e49900a9ea3cd50344cb053747dc9e5a5b07b`
- Target `linux/arm64` image
  `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z`
- Runtime namespace `liangjiahao`; BuildKit namespace `default`
- Python overlay disabled; FabricMem disabled and out of scope

The structured pre-runtime identity is in `identity.json`; frozen source and
tooling file hashes are in `source-tooling-sha256.txt`. Runtime evidence and
its checksums will be added only after the corresponding gates execute.
