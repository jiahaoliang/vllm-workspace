# Mooncake Revoke Ownership Full Validation 2026-08-07

## Status And Scope

G4_VERIFIED. vLLM-Ascend ownership tests, deployment tooling including the
same-key restart oracle, the exact native ARM64 image, native-image CPU/mock,
base 1P1D runtime identity, direct ranged G1, and lease expiry/recovery gates
passed. The 27-layer G4 runtime audit also passed. Smoke, stress, and throughput
remain unclaimed.

## Frozen Identity

| Item | Value |
| --- | --- |
| Run ID | `20260807T100722Z` |
| Tooling base | `3bda70d786db46310994afc689af4fc10da4858e` |
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
| Deployment tooling | `84 passed`; same-key restart/cleanup, Ruff, `py_compile`, diff, cache-free sync, and host/Pod SHA256 checks passed |
| Mooncake checkout | clean read-only detached `df3f74ed...` |
| BuildKit manifest | SHA256 `f7a0c64c330688d6cd6292c3ef3a1022ace0abff7c468aa1b73cb5fe96be5b52` |
| Native image | build exit `0`; OCI labels, three Git HEADs, native modules, exact pip allowlist, and seven static Mooncake APIs passed |
| Image evidence | `image/summary.json` passed; checksums replayed |
| Native-image UT | new CPU-only Pod/config ID; `495` AscendStore and `83` deployment tests; Ruff lint, `py_compile`, diff, cache-free sync passed |
| UT evidence | `ut/summary.json` passed; checksums replayed; long-running Pod retained |
| G0 | 7 free physical cards after replacement; exact new 1+1 Pods; dynamic APIs/model/ldd; 1P1D Ready; proxy 1/1; engines stopped; final Master `0/0/0` |
| G0 evidence | `g0/summary.json` passed; checksums replayed |
| G1 oracle correction | TDD red/green; `negative_revoke_same_key_restart` and cleanup require `[0]`; `tooling-revoke-restart/summary.json` and checksums passed. G0 unaffected; G1 had not started |
| Direct G1 | `45/45` cases and `26/26` negative cases; 3 keys, 4 layers, 2 fragments; same-key restart/cleanup `[0]`; per-key result bytes and final SHA256 equality; Master `0/0/0` before cleanup reset and after reset |
| Lease | live TTL `30000ms`; waits `31500.128ms` and `31500.090ms`; stale ranged read `[-707]`; fresh get exact two-layer recovery; Master `0/0/0` before and after reset |
| G4 attempt 1 | Runtime request/checker passed, but evidence-local assertion rejected valid extra `usage.prompt_tokens_details: null`; failure cleanup stopped engines and reset Master `0/0/0`; corrected validator replay passed |
| G4 rerun | `27/27` Prefill saves and `27/27` Decode loads; each key `147456 == 131072+16384`; final-layer commit `[0,0,0,0]` follows save; whole-key `0`; Decode hit `512/512`; 41 runtime steps green; final Master `0/0/0` |

## Pending Gates

- Run smoke, concurrent smoke, and stress S1-S3 serially.
- Assert final empty Master metrics, generate checksums, replay offline reports,
  stop vLLM processes, and publish final reports/state.

## Evidence

The run evidence root is
`features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/`.
Subsequent evidence must preserve this run ID, exact source/tooling identity,
and immutable image digest/config ID.
