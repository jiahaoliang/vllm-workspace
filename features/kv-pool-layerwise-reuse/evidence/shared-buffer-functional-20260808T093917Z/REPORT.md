# Mooncake Shared-Buffer Functional Validation Report

## Result

- Run ID: `20260808T093917Z`
- Status: `BLOCKED_PRODUCTION_CORRECTNESS_DEFECT`
- Performance handoff: not authorized
- DP1/DP2 traffic: not started

## Frozen Identity

| Field | Value |
| --- | --- |
| Control commit | `6aa170083694d15aa9df0057bae29428177d6239` |
| vLLM commit | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend commit | `2d179d07c86e5f820fd6591c0c7fdef2b5132c14` |
| Mooncake commit | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Derived image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-2d179d07-df3f74ed-20260808T085132Z` |
| Manifest digest | `sha256:e4333425928a1566f07e03e19744e7a88a48a379bbb00afffe8d4e3c8e8bfb01` |
| Platform | `linux/arm64` |

The control and vLLM-Ascend commits were each equal to their configured
`origin` branch (`0 0`) before the run.

## Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Focused CPU/mock UT | PASS | `cpu/pytest-focused.log` (`9 passed`) |
| Complete AscendStore CPU/mock UT | PASS | `cpu/pytest-ascend-store-and-mla.log` (`512 passed`) |
| Layerwise/model-runner CPU/mock UT | PASS | `cpu/pytest-layerwise-and-model-runner.log` (`22 passed`) |
| Deployment tests | PASS | `cpu/pytest-deployment.log` (`129 passed`) |
| Ruff and compilation | PASS | `cpu/ruff-check.log`, `cpu/ruff-format.log`, `cpu/py-compile.log` |
| Image identity | PASS | `image/summary.json` |
| Baseline runtime lifecycle | PASS | `npu/baseline/`, `npu/steps.jsonl` |
| `kv_producer` runtime lifecycle | PASS | `npu/producer-reuse/`, 20 keys, final empty Master |
| `kv_both` runtime lifecycle | PASS | `npu/both-reuse/`, 20 then 36 keys, final empty Master |
| 27-layer/5-slot/5.4 proof | PASS | startup logs in both reuse cases |
| Output correctness oracle | FAIL | `npu/validator.log` and response JSON files |
| Final Master cleanup | PASS | final metrics are keys/bytes/clients `0/0/0` |
| Final NPU release | PASS | `npu/both-reuse/npu-released.txt` |

## Defect Evidence

The exact same request used `temperature=0`, seed `2026072304`, 525 prompt
tokens and 16 output tokens. Baseline generated:

```text
 The private audit marker is a marker that is used to indicate that the audit content
```

`kv_producer` and the cold `kv_both` request instead generated:

```text
 The,3,,,4，，，4，，4，，
```

The warm `kv_both` request generated a third, also corrupted continuation.
The same mismatch is present in the earlier `20260808T083140Z` run, so this is
not a one-run startup anomaly. Mooncake range transfers and commits reported
successful byte counts/results, but successful transport does not satisfy the
output correctness gate.

## Restoration

The runner stopped Prefill after every case, proved no NPU process remained,
restarted Mooncake Master, and proved `master_key_count=0`,
`master_allocated_bytes=0`, and `master_active_clients=0`. The dedicated
AISBench client Pod was not used for traffic.

Performance validation remains fail-closed until a new production-source fix,
new derived image, full functional rerun, and generation-1 ready handoff replace
this blocked result.
