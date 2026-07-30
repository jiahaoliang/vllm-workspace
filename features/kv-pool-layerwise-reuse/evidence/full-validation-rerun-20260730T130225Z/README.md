# Full Validation Rerun 20260730T130225Z

Status: terminated during G0 because both 1P1D engines reproduced a production
vLLM-Ascend/vLLM ABI defect. G1, lease, G4, smoke, and stress were not run.

## Frozen Identity

- vLLM: `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`
- vLLM-Ascend: `14beaf161cca6f1e044e20529ca96c6554dbbe50`
- Mooncake: `786c77ff7692bed58dd99971afef87d6b690cbe3`
- Image config ID:
  `sha256:60ef6bbf63d353e4d3f06057a8b8eb53233bb4f6942a7f8466c35081cf87a358`

## Family Results

| Family | Result | Primary artifact |
| --- | --- | --- |
| Tooling r4 | PASSED | [`tooling-r4/summary.json`](tooling-r4/summary.json) |
| Image r4 | PASSED | [`image-r4/summary.json`](image-r4/summary.json) |
| CPU/mock UT | PASSED | [`ut/summary.json`](ut/summary.json) |
| G0 | FAILED | [`g0/summary.json`](g0/summary.json) |
| Post-failure cleanup tooling | PASSED | [`tooling-post-failure/summary.json`](tooling-post-failure/summary.json) |

The G0 root cause is:

```text
TypeError: get_kv_cache_coordinator() got an unexpected keyword argument 'max_num_batched_tokens'
```

[`g0/source-abi-classification.json`](g0/source-abi-classification.json) proves
that the vLLM-Ascend wrapper passes this keyword while the pinned vLLM function
does not accept it. The same artifact proves the 11-commit Mooncake range did
not change the wrapper file.

## Cleanup State

Both live vLLM process trees and HTTP endpoints were absent after failure.
Mooncake Master was reset and its final key count, allocated bytes, and active
client count were all zero. The dedicated UT Pod, Master, proxy, Prefill Pod,
and Decode Pod were retained. The post-failure control-only tooling fix makes
the base engine lifecycle helper distinguish zombie PIDs from live processes;
it does not change the failed production-source verdict.

## Offline Replay

Run each family checksum from the control-repo root:

```bash
RUN_ROOT=features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260730T130225Z
for FAMILY in tooling tooling-r2 tooling-r3 tooling-r4 image-r2 image-r3 image-r4 ut g0 tooling-post-failure; do
  (cd "${RUN_ROOT}/${FAMILY}" && sha256sum -c SHA256SUMS)
done
```
