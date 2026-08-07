# Full Validation Evidence 20260807T100722Z

Status: SMOKE_VERIFIED. Source/tooling, the exact native ARM64 image,
native-image CPU/mock, base 1P1D runtime identity, direct ranged G1, and lease
expiry/recovery, G4 runtime audit, and 1P1D concurrent smoke are verified. This
directory does not yet claim stress or throughput success.

## Frozen Inputs

- vLLM `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`
- vLLM-Ascend `45b2e785b10ca4604cd6314819ed15f3ff674781`
- Mooncake `df3f74ed8ebdb0c935554beea6299a9f11c723e2`
- Tooling `3bda70d786db46310994afc689af4fc10da4858e`
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
- `g0/summary.json`: live physical capacity was 7 free cards after replacement;
  new 1+1 Pods used the exact config ID, both dynamic runtime/API checks and
  model/native-library gates passed, Prefill/Decode APIs became Ready, proxy
  discovered exactly 1P1D, engines stopped, and final Master keys/bytes/clients
  returned to `0/0/0`.
- `tooling-revoke-restart/summary.json`: a post-G0, pre-G1 tooling correction
  added a hard same-key `PutStart` and cleanup gate after successful revoke.
  TDD red/green, the complete `84`-test deployment suite, Ruff lint,
  `py_compile`, cache-free tar sync, host/Pod SHA256 equality, and checksum
  replay passed. This direct-driver-only correction does not invalidate G0.
- `g1/family-summary.json`: `45/45` cases passed, including `26/26` negative
  cases and result-zero same-key restart/cleanup after revoke. Eight positive
  ranged calls covered three keys, four layers, and two fragments per key;
  per-key bytes and final SHA256 equality passed. Master stayed `0/0/0` before
  and after reset.
- `lease/family-summary.json`: both waits exceeded the live 30 second TTL by
  the frozen 1.5 second margin, stale ranged read returned exact `-707`, fresh
  get recovered both layers, and Master stayed `0/0/0` before and after reset.
- `g4-attempt1-tooling/failure-summary.json`: the runtime request and range
  checker passed, but an evidence-local assertion rejected the valid extra
  `usage.prompt_tokens_details: null` field. Failure cleanup stopped both
  engines and reset Master to `0/0/0`; the corrected validator replayed the
  captured runtime evidence successfully.
- `g4/summary.json`: the complete rerun passed all 41 runtime steps. Prefill
  save and Decode load covered layers `0..26`; every per-key result equaled its
  two-fragment byte sum, final-layer commit results were all zero and ordered
  after save, whole-key calls were zero, Decode hit correlation was `512/512`,
  and final Master metrics were `0/0/0` after stopping both engines.
- `smoke/concurrent-summary.json` and `smoke-wrapper/summary.json`: all 17
  runtime cases passed across cold baseline, warmup, direct load, and proxy
  concurrent load. Marker/token/usage/finish-reason isolation passed for every
  case, all 12 request/role hit correlations passed, and the frozen pool target
  was 64 keys. An immediate post-rollout metrics read raced the endpoint; the
  retry cleanup proved both engines stopped and final Master `0/0/0`.

The structured run identity is in `identity.json`; frozen source and tooling
file hashes are in `source-tooling-sha256.txt`. Each completed family records
its own transcript, structured summary, and checksums.
