# Python Overlay Full Validation 20260803T124415Z

Status: PASSED

This run validates the unchanged native ARM64 image with the exact user-approved
Python overlay. It is not evidence for an image built at the final source
commit.

## Identity

- Control tooling: `faeb2e3978f6db65b503125efc3ec8b71a51b928`
- vLLM: `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`
- Image vLLM-Ascend: `14beaf161cca6f1e044e20529ca96c6554dbbe50`
- Final vLLM-Ascend overlay: `d28c52958a30cebdb7822d56e3dbb0dbe41499bc`
- Mooncake: `786c77ff7692bed58dd99971afef87d6b690cbe3`
- Image: `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1`
- ImageID: `sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57`
- Namespace/node: `liangjiahao` / `n1`

Only these package files were overlaid, with equal host, Prefill, Decode, and
UT SHA256 values:

- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`

## Gate Results

| Family | Result | Primary structured evidence |
| --- | --- | --- |
| CPU/mock | PASSED: 478 AscendStore and 69 deployment tests | [UT log](ut/ascend-store.log) |
| G0 | PASSED: original image identity, four-way overlay checksums, 1P1D Ready, final empty pool | [summary](g0/summary.json) |
| G1 | PASSED: 3 keys, 4 layers, 40 calls, 43 cases, 24 negative cases | [summary](g1/summary.json) |
| Lease | PASSED: two 31.5 s waits, stale read `-707`, fresh exact recovery | [summary](lease/summary.json) |
| G4 | PASSED: 27 save/load layers, one final commit, zero whole-key calls | [summary](g4/summary.json) |
| Smoke | PASSED: baseline/direct/proxy marker isolation and 12 hit correlations | [summary](smoke/concurrent-summary.json) |
| Stress | PASSED: topology plus S1, S2, and S3 | [summary](stress/overall-summary.json) |
| Final state | PASSED: engines stopped, Master empty, Pods retained | [state](final/final-state.json) |

## Attempts

- UT checksum evidence collection initially over-escaped `awk`; the replacement
  command used shell `read` and proved both checksums equal.
- Lease post-reset metrics had one service-start `ConnectionRefused`; the same
  reset was later proved empty at the G4 preflight. Lease cleanup itself had
  already proved zero keys, bytes, and clients.
- G4 initially required zero active clients after engines started. The corrected
  oracle required two clients while keeping keys and bytes zero; no request had
  been sent before the correction. The corrected request and checker passed.
- The first offline smoke assertion assumed four warmup cases; the fixture has
  five. The corrected phase-specific assertion passed without rerunning runtime.

No production source changed after the formal run started.

## Checksums

| Family | SHA256 of `SHA256SUMS` |
| --- | --- |
| `ut` | `5e4d7a1ff86a434c33c44618c698932e3eec1ecb36dd7a9428fa691b859607f0` |
| `g0` | `cb46fb1638b79753c6c446dcb02ff06d06044f650a50c126157ff2a057206f98` |
| `g1` | `74ffd49df54bdace25a88d9b2d445118d3fba4fe39f1b4428fcf50a84137d311` |
| `lease` | `a02bf3df8826985c3f006e36abd371c2fa99cfe02e7258e260032bead4530f14` |
| `g4` | `0cf474caa30af1d02a5c21abf8df00b97fe3dfa396a2a27b2590b4fb6bc8ab08` |
| `smoke-prep` | `eba5c3713e1e38e42417106f290d13c47e70a2fe0ddb3664a7b819d5896d3377` |
| `smoke` | `f260e76ba5ed87b7cf864bbd71180f92d026be58be25a24eb619513eeec8289b` |
| `stress` | `da8b8880f80bfef620c0553c6688e26b1eafbee17c312e5a8a6d3be6e8d0bbcf` |
| `stress-wrapper` | `210fa2cfd1c6451710d6ee5a4633b6d662ae80c9fc9753f16a7ac2cc6a56bb19` |
| `final` | `4359c24159d25f5e311b6bcaead3a594e7cd81aae98b4119f00cf6d7e753e2fb` |

Replay one family from this directory with:

```bash
(cd stress && sha256sum -c SHA256SUMS)
jq -e '.status == "passed" and .validated == true' stress/overall-summary.json
```
