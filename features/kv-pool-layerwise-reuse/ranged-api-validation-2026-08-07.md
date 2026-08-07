# Mooncake Ranged API Revoke Ownership Validation 2026-08-07

## Status And Scope

PASSED. The rebuilt native ARM64 image passed direct Mooncake session and
ranged-transfer validation against the frozen `df3f74ed` Mooncake baseline.
The claim covers three keys, four layers, two fragments per key-layer, exact
bytes, negative session cases, result-zero revoke, same-key restart, cleanup,
and empty Master state. FabricMem and Mooncake multi-group are outside scope.

## Original Validation

The predecessor is the tracked
[2026-08-04 ranged API report](ranged-api-validation-2026-08-04.md).

## Identity

| Item | Value |
| --- | --- |
| Run ID | `20260807T100722Z` |
| Evidence commit base | `66ed7933e898133ef27c3a9eb967e8e4555cda35` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend | `45b2e785b10ca4604cd6314819ed15f3ff674781` |
| Mooncake | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z` |
| Config ID | `sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b` |
| Runtime | `liangjiahao`, node `n1`, Ascend910B4 |

## Gate Results

| Gate | Actual | Result |
| --- | --- | --- |
| Installed APIs | seven session/range APIs | PASSED |
| Direct cases | `45/45` | PASSED |
| Negative cases | `26/26` | PASSED |
| Scatter shape | 3 keys, 4 layers, 2 fragments | PASSED |
| Same-key restart | revoke, restart, cleanup each returned `[0]` | PASSED |
| Byte oracle | every per-key result and final SHA256 matched | PASSED |
| Cleanup | before-reset and after-reset Master `0/0/0` | PASSED |

## Changes From Original Validation

| Area | Change |
| --- | --- |
| Runtime source | exact rebuilt image; no Python overlay |
| Mooncake | `df3f74ed` retains local session after failed revoke |
| Ownership | pending keys fail closed until result-zero cleanup |
| Direct oracle | same-key `PutStart` after revoke is now a hard gate |

## Script Provenance

- Script SHA256: `042e69a69d72309ca098413b7689f7adfb3a8e15684a6902652fb2c8cec6d494` for `deployment/range-api-smoke.py`.
- Family `SHA256SUMS` digest: `ddd842dc17efceaf1e1498da051d9f07e4a7e16c068c187b3a3e37e4e9e6663b`.
- Runtime tooling commit: `3bda70d786db46310994afc689af4fc10da4858e`.

## Live Reproduction Runbook

```bash
kubectl get pods -n liangjiahao -l 'app in (prefill,decode)' -o wide
kubectl exec -n liangjiahao prefill-engine-deployment-75fd46886-pd67q -c prefill-engine -- env PYTHONDONTWRITEBYTECODE=1 python3 /tmp/full-validation-direct-20260807T100722Z/range-api-smoke.py --output /tmp/full-validation-direct-20260807T100722Z/g1-summary.json --num-keys 3 --num-layers 4 --page-size 4096 --run-negative
kubectl rollout restart -n liangjiahao deployment/mooncake-master-deployment
kubectl rollout status -n liangjiahao deployment/mooncake-master-deployment --timeout=300s
```

## Offline Evidence Recheck

```bash
sha256sum -c features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/g1/SHA256SUMS
jq -e '.status == "passed" and .validated == true and .gates.case_count == 45 and .gates.negative_case_count == 26 and .gates.same_key_restart_result == [0] and .gates.source_destination_sha256_equal == true and (.errors | length) == 0' features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260807T100722Z/g1/family-summary.json
git ls-files --error-unmatch features/kv-pool-layerwise-reuse/ranged-api-validation-2026-08-07.md
```

## Attempts And Failures

A pre-G1 tooling correction made same-key restart and second cleanup mandatory
after a successful revoke. Its TDD red/green and complete deployment suite
passed before G1 began. G1 itself had no production-source or semantic failure;
one preflight assertion was replaced because it incorrectly required container
readiness after the intentional G0 engine stop.

## Limitations And Final State

The result covers the frozen single-group A2 path and does not claim FabricMem,
Mooncake multi-group, A3, or benchmark throughput. Both direct test engines
were stopped, and the Master was empty before and after reset.
