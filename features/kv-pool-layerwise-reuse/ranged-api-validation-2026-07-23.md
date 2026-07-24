# Mooncake Ranged API Validation Report

## Result

**Status:** Passed for mandatory gates G0-G3.

This run verified three distinct layers of the feature:

1. the image's Mooncake Client and TransferEngine can perform ranged put/get
   against real Ascend NPU buffers;
2. the locked vLLM-Ascend branch passes its existing AscendStore session and
   failure-orchestration unit tests;
3. the Kubernetes 1P1D deployment performs external KVPool save/load and keeps
   four concurrent requests isolated, with exact output equality in this run.

G4 runtime instrumentation was not executed. This report does not claim that
production-process logs independently reconstruct every ranged API call for
every physical model layer.

## Identity

| Item | Value |
|---|---|
| plan commit | `a3406334959d8c68537b305c6242450db3c684c2` |
| G3 fixture | `commit:2d0bd8a7db177b4a3aed2ff69fac845f756ff21d` |
| direct runner commit | `f0498d8a60e31e99c33cfee63603802133a2b3e5` |
| image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2` |
| image manifest digest | `sha256:661c9bc2c50c1b7253d6f9ec7905cc83f49908ef8cb1919108a5ea828c2cff8d` |
| image config ID | `sha256:a370384ab214665c3e6d7179aba82d0e5799a290a41370abe372b53f9593283d` |
| vLLM | `ee0da84ab9e04ac7610e28580af62c365e898389` |
| vLLM-Ascend | `663209fd6208a59a48742f75116345bf5f5281ec` |
| Mooncake | `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` |
| model | `vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| node | `n1` |
| namespace | `ai-inference` |

The live engine and Master Pods reported the same image config ID. OCI labels
inside the image matched all three locked source commits.

## G0 Preflight

G0 passed.

- Prefill, decode, proxy, and Mooncake Master each had exactly one Running Pod.
- Prefill used physical NPU 0 and decode used physical NPU 2. Both were
  `Ascend910B4` with `Health=OK`.
- The model directory was readable and occupied 17 GiB. It contained four W8A8
  safetensor shards.
- Both engine Pods imported vLLM-Ascend from
  `/vllm-workspace/vllm-ascend/vllm_ascend/__init__.py`.
- Both runtime checks found all seven Mooncake session/range methods callable.
- `TransferEngine.get_engine`, `get_rpc_port`, `register_memory`, and
  `unregister_memory` were callable.
- The loaded Mooncake extensions were
  `/usr/local/Ascend/ascend-toolkit/latest/python/site-packages/mooncake/engine.cpython-312-aarch64-linux-gnu.so`
  and the corresponding `store` extension.

`pip show mooncake-transfer-engine` returned no distribution metadata. This is
not an import or runtime failure: the image contains the built extension in the
Ascend Python site-packages path, the required APIs were callable, the image
label identifies the Mooncake commit, and G1 exercised the extension directly.

## G1 Direct Ascend Contract

G1 passed with the committed runner copied to the prefill Pod at
`/tmp/range-api-smoke.py`.

- Host and Pod runner SHA-256:
  `b37cfe0812a7b843aedac44dc7d9dbce9bbce3b6cab106a38d3e94a53dbf01da`.
- The prefill vLLM process was stopped first; `npu-smi` showed no process using
  the assigned NPU.
- The runner selected logical device 0, which reported `Ascend910B4`.
- The source and destination were `torch.uint8` NPU tensors registered through
  the initialized TransferEngine.
- The store received `engine=transfer_engine.get_engine()`, `protocol=ascend`,
  `metadata_server=P2PHANDSHAKE`, and a 64 MiB test segment.

Positive result:

- 3 keys, 4 layers, 4096 bytes per key/layer, two fragments per layer;
- every ranged put returned `[4096, 4096, 4096]`;
- every ranged get returned `[4096, 4096, 4096]`;
- put-start, put-end, get-start, and get-end all succeeded;
- non-zero object offsets were exercised;
- source and destination SHA-256 were both
  `7d1e6c4abf707792c756417dfd026d12b037e95d92f0a582aab68a025bed2260`.

Selected negative cases all returned negative error codes without crashing:

- no put/get session: `-600`;
- duplicate put-start: `-600`;
- offset overflow: `-600`;
- put/get fragment arity mismatch: `-600`;
- ranged call after put-end/get-end: `-600`;
- get-start after revoke: `-704`.

All 43 recorded cases passed. Cleanup synchronized the NPU, unregistered both
tensor pointers with return code 0, closed the store, released tensor
references, and left no runner process on the NPU. Prefill was restarted and
its `/v1/models` endpoint returned HTTP 200 before the next gate.

## G2 AscendStore Unit Tests

G2 passed without changing `repos/vllm-ascend`.

```bash
TORCH_DEVICE_BACKEND_AUTOLOAD=0 \
VLLM_VERSION=0.24.0 \
PYTHONDONTWRITEBYTECODE=1 \
PYTEST_ADDOPTS="-p no:cacheprovider" \
pytest -q \
  tests/ut/distributed/ascend_store/test_backend.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py \
  tests/ut/distributed/ascend_store/test_mooncake_session_tracker.py \
  tests/ut/distributed/ascend_store/test_pool_worker.py
```

Result: `242 passed, 14 warnings in 1.74s`. The warnings were PyTorch
`torch.jit.script_method` deprecation warnings. Source status files before and
after the test were byte-identical and empty.

An initial collection attempt without `VLLM_VERSION=0.24.0` selected the wrong
compatibility line from the editable vLLM dev version and failed while importing
the DFlash model. The successful run used the same supported compatibility
override as both engine Deployments. No product assertion failed.

## G3 Deployment E2E

The first read-only fixture review found two acceptance bugs in the prior smoke:

- it rejected only HTTP status codes at or above 400 instead of requiring 200;
- a normalized concurrent text match could bypass the required exact serial
  replay in fallback cases.

Commit `2d0bd8a7db177b4a3aed2ff69fac845f756ff21d` fixed both conditions and became
the new frozen G3 fixture. Embedded Python syntax, shell syntax, live ConfigMap
content, image, command, mounts, and critical workload configuration were
rechecked before execution.

The execution stopped both vLLM children, confirmed both NPUs had no remaining
process, restarted Mooncake Master, and then started fresh prefill/decode
processes. Both `/v1/models` endpoints returned HTTP 200. Master metrics showed
`master_key_count 0` before the smoke.

G3 result:

| Phase | Result |
|---|---|
| empty-pool direct decoder baseline | 4/4 HTTP 200; pool remained empty |
| sequential warmup/reuse | 5/5 HTTP 200; expected 64 keys reached |
| direct decoder concurrent KV load | 4/4 passed; 4 exact matches |
| proxy concurrent KV load | 4/4 passed; 4 exact matches |
| per-response log validation | 12/12 role/case checks passed |

Every concurrent response retained its own marker, contained no foreign marker,
preserved response metadata, and exactly matched its no-KV baseline signature.
Each target response ID had `hit_blocks=25/25`, `kvpool hit tokens: 3200`, and
`use_layerwise=True` evidence. The live config used
`kv_load_failure_policy=fail`, so a load failure could not silently recompute.

`concurrent-summary.json` and `log-validation.json` both report `passed`.

## D1 Decision

D1 is **No**. G1-G3 are mutually consistent, and no reviewer required a
production per-physical-layer call trace. No vLLM, vLLM-Ascend, or Mooncake
production source was modified.

The remaining evidence boundary is deliberate: G1 proves the Ascend ranged API
contract directly, G2 proves adapter/session orchestration, and G3 proves the
real 1P1D deployment behavior. This run does not independently reconstruct all
production ranged calls per physical layer or prove whole-key call count zero.

## Evidence

Control-repo evidence directory:

```text
features/kv-pool-layerwise-reuse/evidence/ranged-api-20260723T094716Z
```

The directory was first staged under `/tmp`, persisted outside the workspace,
and then imported byte-for-byte into the control repo at the path above.
`sha256sum -c SHA256SUMS` passed again in the checked-in directory.

Key evidence:

- [SHA256SUMS](evidence/ranged-api-20260723T094716Z/SHA256SUMS)
- [G1 direct summary](evidence/ranged-api-20260723T094716Z/direct/range-api-summary.json)
- [G2 pytest log](evidence/ranged-api-20260723T094716Z/unit/pytest.log)
- [G3 concurrent summary](evidence/ranged-api-20260723T094716Z/deployment/concurrent-summary.json)
- [G3 log validation](evidence/ranged-api-20260723T094716Z/deployment/log-validation.json)

`SHA256SUMS` digest:

```text
e5b4a768485f1aaf2b39d7421ab1c2f1308077f06f8f010f059a640cfb95d1f9
```

The artifact includes environment identity, exported fixture source and source
checksums, live Kubernetes objects, the exact direct runner, G1 JSON/logs, G2
pytest/status logs, G3 response summaries, per-response validation, Pod states,
Master metrics, and all component logs.
