# Mooncake Ranged API Overlay Validation 2026-08-03

## Status And Scope

PASSED. G0 and G1 validated the existing native ARM64 image with the explicit
two-file vLLM-Ascend Python overlay. The claim covers image/runtime identity,
empty-pool isolation, multi-key multi-layer ranged transfer, negative session
and range cases, cleanup, and exact byte comparison. It does not claim that an
image was built at the final overlay commit.

## Original Validation

The comparison baseline is the tracked
[2026-07-23 ranged API report](ranged-api-validation-2026-07-23.md). That run
established the original direct API contract; this run repeats it after the
concurrent request-isolation fix.

## Identity

| Item | Value |
| --- | --- |
| Evidence commit | `03d13567659a30c2df42521f1a0d384c30d220c1` |
| Runtime tooling commit | `faeb2e3978f6db65b503125efc3ec8b71a51b928` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| Image vLLM-Ascend | `14beaf161cca6f1e044e20529ca96c6554dbbe50` |
| Final overlay vLLM-Ascend | `d28c52958a30cebdb7822d56e3dbb0dbe41499bc` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1` |
| ImageID | `sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57` |
| Kubernetes | `liangjiahao`, node `n1` |

Host, Prefill, Decode, and UT checksums matched for `config_data.py` and
`kv_transfer.py`; no other package file entered the overlay.

## Gate Results

| Gate | Expected | Actual | Exit | Result |
| --- | --- | --- | --- | --- |
| G0 identity | Original image plus exact overlay | ImageID unchanged; four-way checksums equal | 0 | PASSED |
| G0 startup | Both 1P1D APIs and proxy Ready | Prefill, Decode, proxy passed | 0 | PASSED |
| G0 isolation | Final keys/bytes/clients all zero | `0 / 0 / 0` | 0 | PASSED |
| G1 shape | 3 keys, 4 layers, 4096-byte pages | exact | 0 | PASSED |
| G1 positive calls | 40 aligned calls and non-zero offsets | 40 calls; 48 non-zero offsets | 0 | PASSED |
| G1 cases | All 43 cases; 24 negative cases | 43/43 and 24/24 | 0 | PASSED |
| Byte oracle | Source equals destination | SHA256 equal | 0 | PASSED |
| Cleanup | keys/bytes/clients all zero | `0 / 0 / 0` | 0 | PASSED |

Primary evidence: [G0 summary](evidence/full-validation-rerun-20260803T124415Z/g0/summary.json),
[four-way checksums](evidence/full-validation-rerun-20260803T124415Z/g0/source-checksums.tsv),
and [G1 summary](evidence/full-validation-rerun-20260803T124415Z/g1/summary.json).

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Image/native dependencies | Unchanged |
| Direct Mooncake ranged API | Unchanged |
| Session API names | Uses the already-adapted `batch_*_session_*` names |
| vLLM-Ascend package | Two-file Python overlay at `d28c52958` |
| Request batching | Concurrent ranged loads are dispatched per request |
| Negative-case oracle | Unchanged; repeated in full |

## Script Provenance

- Runtime script revision: `faeb2e3978f6db65b503125efc3ec8b71a51b928`.
- Evidence commit: `03d13567659a30c2df42521f1a0d384c30d220c1`.
- Script SHA256 for `deployment/range-api-smoke.py`: `b10fbc18f59ff442390c6cebef0855a53fbf8a22eb3b91fef371941df3f1b125`.
- G0 `SHA256SUMS` digest:
  `cb46fb1638b79753c6c446dcb02ff06d06044f650a50c126157ff2a057206f98`.
- G1 `SHA256SUMS` digest:
  `74ffd49df54bdace25a88d9b2d445118d3fba4fe39f1b4428fcf50a84137d311`.

## Live Reproduction Runbook

These are the core commands executed in this run; the complete commands and
timestamps are in the linked family transcripts.

```bash
kubectl exec -n liangjiahao prefill-engine-deployment-69cfdd6cb4-pmb8k -c prefill-engine -- env PYTHONDONTWRITEBYTECODE=1 python3 /tmp/full-validation-direct-20260803T124415Z/range-api-smoke.py --output /tmp/full-validation-direct-20260803T124415Z/g1-summary.json --num-keys 3 --num-layers 4 --page-size 4096 --run-negative
kubectl exec -n liangjiahao prefill-engine-deployment-69cfdd6cb4-pmb8k -c prefill-engine -- python3 -c 'from urllib.request import urlopen; print(urlopen("http://mooncake-master-service:9003/metrics",timeout=10).read().decode(),end="")'
```

See the [G1 transcript](evidence/full-validation-rerun-20260803T124415Z/g1/command-transcript.log)
for setup, cleanup, and independent reset commands.

## Offline Evidence Recheck

```bash
(cd features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/g0 && sha256sum -c SHA256SUMS)
(cd features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/g1 && sha256sum -c SHA256SUMS)
jq -e '.passed == true and (.cases|length) == 43 and (.api_calls|length) == 40 and (.errors|length) == 0' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/g1/summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/g1/summary.json
```

## Attempts And Failures

The first UT checksum collection command over-escaped `awk`; the replacement
used shell `read` and passed. One later command attempted a local reset assertion
from the family directory instead of the workspace root and wrote no family
step; the assertion was rerun from the correct directory. No G0 or G1 runtime
gate failed, and no production source changed during validation.

## Limitations And Final State

This is a Python-overlay validation. Native extensions and dependency layers
remain those of image source `14beaf161`; the result must not be presented as a
new image at `d28c52958`. The final stress Pods are retained with six requested
NPUs, but all vLLM child processes are stopped. Mooncake Master final metrics
are zero keys, zero allocated bytes, and zero active clients.
