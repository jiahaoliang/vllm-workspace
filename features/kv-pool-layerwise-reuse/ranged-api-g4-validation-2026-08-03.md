# Mooncake G4 Range Audit Overlay Validation 2026-08-03

## Status And Scope

PASSED. One clean 1P1D proxy request produced a fail-closed audit of every
physical model layer. The result covers ranged save/load byte accounting,
final-layer commit order, whole-key exclusion, response usage, and request-log
correlation on the explicit Python overlay.

## Original Validation

The original contract is the tracked
[2026-07-23 G4 report](ranged-api-g4-validation-2026-07-23.md). This run repeats
that audit after the concurrent Mooncake range-load isolation fix.

## Identity

| Item | Value |
| --- | --- |
| Evidence commit | `03d13567659a30c2df42521f1a0d384c30d220c1` |
| Runtime tooling | `faeb2e3978f6db65b503125efc3ec8b71a51b928` |
| Image vLLM-Ascend | `14beaf161cca6f1e044e20529ca96c6554dbbe50` |
| Final overlay | `d28c52958a30cebdb7822d56e3dbb0dbe41499bc` |
| vLLM / Mooncake | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` / `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| ImageID | `sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57` |
| Model dimensions | 27 physical layers, block size 128 |
| Runtime | `liangjiahao`, node `n1`, base 1P1D |

## Gate Results

| Gate | Expected | Actual | Exit | Result |
| --- | --- | --- | --- | --- |
| Preflight | stopped engines; empty keys/bytes | passed | 0 | PASSED |
| Debug inheritance | both child processes set range debug | 2/2 | 0 | PASSED |
| Request | HTTP 200; 525 prompt + 16 completion | 200; 525 + 16 | 0 | PASSED |
| Prefill ranges | save layers exactly `0..26` | 27/27 | 0 | PASSED |
| Prefill commit | one commit after layer 26 | one, ordered | 0 | PASSED |
| Decode ranges | load layers exactly `0..26` | 27/27 | 0 | PASSED |
| Bytes | every result equals fragment sum | all equal | 0 | PASSED |
| Whole-key path | zero events | zero | 0 | PASSED |
| Decode cache | 512 hit tokens | 512 | 0 | PASSED |
| Final isolation | engines stopped; Master `0/0/0` | passed | 0 | PASSED |

Evidence: [G4 summary](evidence/full-validation-rerun-20260803T124415Z/g4/summary.json),
[range checker output](evidence/full-validation-rerun-20260803T124415Z/g4/range-debug-summary-rerun.json),
and [contract assertions](evidence/full-validation-rerun-20260803T124415Z/g4/g4-contract.json).

## Changes From Original Validation

| Area | Change |
| --- | --- |
| G4 request fixture | Unchanged |
| 27-layer checker contract | Unchanged |
| Image and native libraries | Unchanged |
| Python runtime | Two-file overlay at `d28c52958` |
| Load batching | Per-request Mooncake ranged dispatch |
| Evidence privacy | Cluster-wide capacity snapshots retain only resource fields |

## Script Provenance

- Runtime and published checker revision:
  `faeb2e3978f6db65b503125efc3ec8b71a51b928`.
- Evidence commit: `03d13567659a30c2df42521f1a0d384c30d220c1`.
- Script SHA256 for `deployment/check-range-debug-log.py`: `217d6024f44c335d0af0705008514ea2ec6bed5fdc41ec098eab4c488beb9fed`.
- G4 `SHA256SUMS` digest:
  `0cf474caa30af1d02a5c21abf8df00b97fe3dfa396a2a27b2590b4fb6bc8ab08`.

## Live Reproduction Runbook

```bash
kubectl exec -n liangjiahao prefill-engine-deployment-69cfdd6cb4-pmb8k -c prefill-engine -- env VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1 PYTHONDONTWRITEBYTECODE=1 /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n liangjiahao decode-engine-deployment-56559b48fc-48kcr -c decode-engine -- env VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1 PYTHONDONTWRITEBYTECODE=1 /opt/vllm-layerwise/start-decode.sh
kubectl exec -n liangjiahao prefill-engine-deployment-69cfdd6cb4-pmb8k -c prefill-engine -- env PYTHONDONTWRITEBYTECODE=1 python3 -c 'import sys,urllib.request; from pathlib import Path; payload=Path(sys.argv[2]).read_bytes(); request=urllib.request.Request(sys.argv[1],payload,{"Content-Type":"application/json"}); response=urllib.request.urlopen(request,timeout=600); Path(sys.argv[3]).write_bytes(response.read()); print(response.status)' http://vllm-proxy-service:8000/v1/completions /tmp/full-validation-20260803T124415Z/g4/request.json /tmp/full-validation-20260803T124415Z/g4/response-rerun.json
```

The complete sequence is in the
[G4 transcript](evidence/full-validation-rerun-20260803T124415Z/g4/command-transcript.log).

## Offline Evidence Recheck

```bash
(cd features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/g4 && sha256sum -c SHA256SUMS)
python3 features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/g4/check-range-debug-log.py --prefill-log features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/g4/vllm-prefill-rerun.log --decode-log features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/g4/vllm-decode-rerun.log --num-layers 27 --output /tmp/g4-offline-replay.json
jq -e '.status == "passed" and .prefill.range_event_count == 27 and .decode.range_event_count == 27' /tmp/g4-offline-replay.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260803T124415Z/g4/summary.json
```

## Attempts And Failures

Before the request, the first manual oracle incorrectly required
`master_active_clients=0` after both engines had connected; the correct live
value was 2 while keys and bytes were zero. Because the command chain stopped,
no request had been sent. The following response capture and checker therefore
also failed on missing files. The corrected oracle, new response/log artifacts,
and checker all passed. These three superseded steps remain checksummed.

## Limitations And Final State

The audit validates production calls made by the overlaid Python source but not
a newly built image at `d28c52958`. It covers one clean request, while broader
concurrency is covered by smoke and stress. After G4, both engines were stopped,
Master was reset to zero keys, bytes, and clients, and all Pods were retained.
