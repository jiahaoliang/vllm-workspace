# Mooncake Revoke Ownership Full Validation 2026-08-07

## Status And Scope

NATIVE_IMAGE_AND_UT_VERIFIED. vLLM-Ascend ownership tests, deployment tooling,
the exact native ARM64 image, and native-image CPU/mock gates passed. A2 runtime
families have not run at this checkpoint, so this document does not yet claim
NPU, smoke, stress, or throughput success.

## Frozen Identity

| Item | Value |
| --- | --- |
| Run ID | `20260807T100722Z` |
| Tooling base | `4b5e49900a9ea3cd50344cb053747dc9e5a5b07b` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend | `45b2e785b10ca4604cd6314819ed15f3ff674781` |
| Mooncake | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z` |
| Platform | `linux/arm64` |
| Manifest digest | `sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351` |
| Config ID | `sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b` |
| BuildKit node | `m1`; Ready native ARM64 worker |
| Runtime namespace | `liangjiahao` |
| BuildKit namespace | `default` |
| Python overlay | disabled; image source equals final source |
| FabricMem | disabled and outside this run |

## Completed Gates

| Gate | Result |
| --- | --- |
| Source TDD red | `10 failed, 33 passed` for the expected missing behavior |
| Source focused green | `43 passed` before the stale-retry audit addition |
| Source full gate | `495 passed`; Ruff, `py_compile`, `git diff --check` passed |
| Source publication | local/origin `45b2e785b...`; left/right `0 0` |
| Deployment tooling | `83 passed`; Ruff, shell, JSON, diff checks passed |
| Mooncake checkout | clean read-only detached `df3f74ed...` |
| BuildKit manifest | SHA256 `f7a0c64c330688d6cd6292c3ef3a1022ace0abff7c468aa1b73cb5fe96be5b52` |
| Native image | build exit `0`; OCI labels, three Git HEADs, native modules, exact pip allowlist, and seven static Mooncake APIs passed |
| Image evidence | `image/summary.json` passed; checksums replayed |
| Native-image UT | new CPU-only Pod/config ID; `495` AscendStore and `83` deployment tests; Ruff lint, `py_compile`, diff, cache-free sync passed |
| UT evidence | `ut/summary.json` passed; checksums replayed; long-running Pod retained |

## Pending Gates

- Run installed-module and direct session/range byte-equality tests.
- Run G0, G1, lease, G4, smoke, concurrent smoke, and stress S1-S3 serially.
- Assert final empty Master metrics, generate checksums, replay offline reports,
  stop vLLM processes, and publish final reports/state.

## Evidence

The run evidence root is
`features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/`.
Subsequent evidence must preserve this run ID, exact source/tooling identity,
and immutable image digest/config ID.
