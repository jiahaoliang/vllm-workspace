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

## Historical Reproduction Runbook

This runbook was reconstructed from the approved plan, frozen G3 fixture,
committed runners, and checked-in evidence. It was added without rerunning G0,
G1, G2, or G3. The first section reproduces the recorded acceptance decision
offline; the second section is the procedure for a future live rerun that must
write a new artifact directory.

The 2026-07-23 run used vLLM-Ascend commit
`663209fd6208a59a48742f75116345bf5f5281ec`. A later checkout or a Pod with
Python-only source sync is a different input. Do not update this report's
identity or reuse its artifact paths for such a run.

### Verify G0-G3 evidence without rerunning

Run from the control-repo root:

```bash
set -euo pipefail

readonly ranged_evidence_root=features/kv-pool-layerwise-reuse/evidence/ranged-api-20260723T094716Z
readonly ranged_direct_summary="${ranged_evidence_root}/direct/range-api-summary.json"
readonly ranged_unit_dir="${ranged_evidence_root}/unit"
readonly ranged_deployment_dir="${ranged_evidence_root}/deployment"

(
  cd "${ranged_evidence_root}"
  sha256sum -c SHA256SUMS
)
test "$(sha256sum "${ranged_evidence_root}/SHA256SUMS" | awk '{print $1}')" = \
  e5b4a768485f1aaf2b39d7421ab1c2f1308077f06f8f010f059a640cfb95d1f9

jq -e '
  .passed == true and
  (.cases | length) == 43 and
  all(.cases[]; .passed == true) and
  .source_checksum == .destination_checksum_after and
  all(.cleanup[]; .passed == true)
' "${ranged_direct_summary}"

cmp "${ranged_unit_dir}/git-status-before.txt" \
  "${ranged_unit_dir}/git-status-after.txt"
grep -Eq '242 passed, 14 warnings' "${ranged_unit_dir}/pytest.log"

jq -e '
  .status == "passed" and .validated == true and .diagnosis == "passed" and
  .expected_master_key_count == 64 and .actual_master_key_count == 64 and
  ([.phases.direct_kv_load.cases[] |
    select(.validated == true and .exact_match == true)] | length) == 4 and
  ([.phases.proxy_kv_load.cases[] |
    select(.validated == true and .exact_match == true)] | length) == 4
' "${ranged_deployment_dir}/concurrent-summary.json"
jq -e '
  .passed == true and .errors == [] and (.checks | length) == 12 and
  all(.checks[];
    .passed == true and .hit_blocks == true and
    .hit_tokens == true and .layerwise_load == true)
' "${ranged_deployment_dir}/log-validation.json"
grep -qx '0' "${ranged_deployment_dir}/smoke-test.exit-code"
grep -qx '0' "${ranged_deployment_dir}/log-validation.exit-code"
```

These checks validate the immutable evidence used for this report. They do not
turn archived output into a new runtime result.

### Create a new artifact root for a future live rerun

Use the exact archived runner and frozen deployment source, not their evolving
counterparts on the branch:

```bash
readonly ranged_namespace=ai-inference
readonly ranged_historical_vllm_ascend=663209fd6208a59a48742f75116345bf5f5281ec
readonly ranged_runner="${ranged_evidence_root}/direct/range-api-smoke.py"
readonly ranged_fixture_root="${ranged_evidence_root}/environment/deployment-fixture"
readonly ranged_fixture_source="${ranged_fixture_root}/source"
readonly ranged_historical_deployment="${ranged_fixture_source}/features/kv-pool-layerwise-reuse/deployment"

ranged_timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
ranged_artifact_root="/tmp/ranged-api-reproduction-${ranged_timestamp}"
test ! -e "${ranged_artifact_root}"
mkdir -p \
  "${ranged_artifact_root}/environment" \
  "${ranged_artifact_root}/direct" \
  "${ranged_artifact_root}/unit"

grep -Fx 'G3_FIXTURE_ID=commit:2d0bd8a7db177b4a3aed2ff69fac845f756ff21d' \
  "${ranged_fixture_root}/IDENTITY.txt"
(
  cd "${ranged_fixture_source}"
  sha256sum -c SOURCE-SHA256SUMS
)
test "$(sha256sum "${ranged_runner}" | awk '{print $1}')" = \
  b37cfe0812a7b843aedac44dc7d9dbce9bbce3b6cab106a38d3e94a53dbf01da
```

### G0: verify the live image, Pods, model, NPU, and APIs

Resolve exactly one Running Pod for each role and save the environment before
using either NPU:

```bash
for ranged_selector in \
  app=prefill app=decode app=proxy app=mooncake-master; do
  test "$(kubectl get pods -n "${ranged_namespace}" \
    -l "${ranged_selector}" -o json | \
    jq '[.items[] | select(.status.phase == "Running")] | length')" -eq 1
done

ranged_prefill_pod="$(kubectl get pods -n "${ranged_namespace}" \
  -l app=prefill -o jsonpath='{.items[0].metadata.name}')"
ranged_decode_pod="$(kubectl get pods -n "${ranged_namespace}" \
  -l app=decode -o jsonpath='{.items[0].metadata.name}')"

kubectl get pods -n "${ranged_namespace}" -o yaml \
  >"${ranged_artifact_root}/environment/pods.yaml"
nerdctl -n k8s.io image inspect \
  docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2 \
  >"${ranged_artifact_root}/environment/image-inspect.json"

for ranged_target in \
  "${ranged_prefill_pod}:prefill-engine" \
  "${ranged_decode_pod}:decode-engine"; do
  ranged_pod="${ranged_target%%:*}"
  ranged_container="${ranged_target##*:}"
  test "$(kubectl exec -n "${ranged_namespace}" "${ranged_pod}" \
    -c "${ranged_container}" -- \
    git -C /vllm-workspace/vllm-ascend rev-parse HEAD)" = \
    "${ranged_historical_vllm_ascend}"
  test -z "$(kubectl exec -n "${ranged_namespace}" "${ranged_pod}" \
    -c "${ranged_container}" -- \
    git -C /vllm-workspace/vllm-ascend status --porcelain)"
  kubectl exec -n "${ranged_namespace}" "${ranged_pod}" \
    -c "${ranged_container}" -- \
    python3 /opt/vllm-layerwise/check-runtime.py
  kubectl exec -n "${ranged_namespace}" "${ranged_pod}" \
    -c "${ranged_container}" -- python3 -c '
from mooncake.engine import TransferEngine

required = ("get_engine", "get_rpc_port", "register_memory", "unregister_memory")
missing = [name for name in required if not callable(getattr(TransferEngine, name, None))]
assert not missing, missing
'
done

kubectl exec -n "${ranged_namespace}" "${ranged_prefill_pod}" \
  -c prefill-engine -- npu-smi info \
  >"${ranged_artifact_root}/environment/npu-prefill.txt"
kubectl exec -n "${ranged_namespace}" "${ranged_decode_pod}" \
  -c decode-engine -- npu-smi info \
  >"${ranged_artifact_root}/environment/npu-decode.txt"
test "$(kubectl exec -n "${ranged_namespace}" "${ranged_prefill_pod}" \
  -c prefill-engine -- bash -lc \
  'find /root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8 -maxdepth 1 -name "*.safetensors" | wc -l')" -eq 4
```

If the commit or clean-status check fails, stop. Reusing a G4-synced Pod would
change both the G2 test count and the production source identity. Prepare a
clean historical fixture rather than overwriting later in-Pod work.

### G1: run the direct Ascend ranged contract

Stop prefill vLLM so the runner has exclusive use of its visible NPU. The stop
script removes its PID file only after the process exits or is killed:

```bash
kubectl exec -n "${ranged_namespace}" "${ranged_prefill_pod}" \
  -c prefill-engine -- /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n "${ranged_namespace}" "${ranged_prefill_pod}" \
  -c prefill-engine -- bash -lc \
  'test ! -s /tmp/vllm-prefill.pid && ! pgrep -af "[v]llm.entrypoints.openai.api_server.*--port 8100"'
kubectl exec -n "${ranged_namespace}" "${ranged_prefill_pod}" \
  -c prefill-engine -- npu-smi info \
  >"${ranged_artifact_root}/direct/npu-before-g1.txt"
grep -Fq 'No running processes found' \
  "${ranged_artifact_root}/direct/npu-before-g1.txt"

kubectl cp -n "${ranged_namespace}" -c prefill-engine \
  "${ranged_runner}" "${ranged_prefill_pod}:/tmp/range-api-smoke.py"
test "$(kubectl exec -n "${ranged_namespace}" "${ranged_prefill_pod}" \
  -c prefill-engine -- sha256sum /tmp/range-api-smoke.py | awk '{print $1}')" = \
  b37cfe0812a7b843aedac44dc7d9dbce9bbce3b6cab106a38d3e94a53dbf01da

kubectl exec -n "${ranged_namespace}" "${ranged_prefill_pod}" \
  -c prefill-engine -- python3 /tmp/range-api-smoke.py \
  --run-negative --output /tmp/range-api-summary.json \
  2>&1 | tee "${ranged_artifact_root}/direct/range-api.log"
kubectl cp -n "${ranged_namespace}" -c prefill-engine \
  "${ranged_prefill_pod}:/tmp/range-api-summary.json" \
  "${ranged_artifact_root}/direct/range-api-summary.json"
kubectl exec -n "${ranged_namespace}" "${ranged_prefill_pod}" \
  -c prefill-engine -- npu-smi info \
  >"${ranged_artifact_root}/direct/npu-after-g1.txt"
grep -Fq 'No running processes found' \
  "${ranged_artifact_root}/direct/npu-after-g1.txt"

jq -e '
  .passed == true and (.cases | length) == 43 and
  all(.cases[]; .passed == true) and
  .source_checksum == .destination_checksum_after and
  all(.cleanup[]; .passed == true)
' "${ranged_artifact_root}/direct/range-api-summary.json"

kubectl exec -n "${ranged_namespace}" "${ranged_prefill_pod}" \
  -c prefill-engine -- /opt/vllm-layerwise/start-prefill.sh
```

Require the restarted prefill API to return HTTP 200 before continuing:

```bash
ranged_wait_for_url() {
  local ranged_wait_pod=$1
  local ranged_wait_container=$2
  local ranged_wait_url=$3

  for _ in $(seq 1 240); do
    if kubectl exec -n "${ranged_namespace}" "${ranged_wait_pod}" \
      -c "${ranged_wait_container}" -- python3 -c \
      'import sys, urllib.request; response = urllib.request.urlopen(sys.argv[1], timeout=5); assert response.status == 200' \
      "${ranged_wait_url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  return 1
}

ranged_wait_for_url "${ranged_prefill_pod}" prefill-engine \
  http://127.0.0.1:8100/v1/models
```

### G2: run the existing AscendStore tests without source changes

Run the four historical test files in the clean prefill Pod and prove that the
source status is unchanged:

```bash
kubectl exec -n "${ranged_namespace}" "${ranged_prefill_pod}" \
  -c prefill-engine -- \
  git -C /vllm-workspace/vllm-ascend status --porcelain=v1 \
  >"${ranged_artifact_root}/unit/git-status-before.txt"

kubectl exec -n "${ranged_namespace}" "${ranged_prefill_pod}" \
  -c prefill-engine -- bash -lc '
cd /vllm-workspace/vllm-ascend
TORCH_DEVICE_BACKEND_AUTOLOAD=0 \
VLLM_VERSION=0.24.0 \
PYTHONDONTWRITEBYTECODE=1 \
PYTEST_ADDOPTS="-p no:cacheprovider" \
python3 -m pytest -q \
  tests/ut/distributed/ascend_store/test_backend.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py \
  tests/ut/distributed/ascend_store/test_mooncake_session_tracker.py \
  tests/ut/distributed/ascend_store/test_pool_worker.py
' 2>&1 | tee "${ranged_artifact_root}/unit/pytest.log"

kubectl exec -n "${ranged_namespace}" "${ranged_prefill_pod}" \
  -c prefill-engine -- \
  git -C /vllm-workspace/vllm-ascend status --porcelain=v1 \
  >"${ranged_artifact_root}/unit/git-status-after.txt"
cmp "${ranged_artifact_root}/unit/git-status-before.txt" \
  "${ranged_artifact_root}/unit/git-status-after.txt"
grep -Eq '242 passed, 14 warnings' \
  "${ranged_artifact_root}/unit/pytest.log"
```

### G3: rerun the frozen deployment smoke

Use the reset/start procedure in the
[deployment validation runbook](deployment/validation-2026-07-23.md#historical-reproduction-runbook),
but set its output directory to this new artifact root:

```bash
kubectl exec -n "${ranged_namespace}" \
  deploy/prefill-engine-deployment -c prefill-engine -- \
  /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n "${ranged_namespace}" \
  deploy/decode-engine-deployment -c decode-engine -- \
  /opt/vllm-layerwise/stop-engine.sh decode
kubectl rollout restart -n "${ranged_namespace}" \
  deployment/mooncake-master-deployment
kubectl rollout status -n "${ranged_namespace}" \
  deployment/mooncake-master-deployment --timeout=120s

kubectl exec -n "${ranged_namespace}" \
  deploy/prefill-engine-deployment -c prefill-engine -- python3 -c \
  'import sys, urllib.request; data = urllib.request.urlopen(sys.argv[1], timeout=10).read().decode(); print(data, end=""); assert "master_key_count 0" in data.splitlines()' \
  http://mooncake-master-service:9003/metrics \
  >"${ranged_artifact_root}/environment/mooncake-master-before-smoke.metrics"

kubectl exec -n "${ranged_namespace}" \
  deploy/prefill-engine-deployment -c prefill-engine -- \
  /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n "${ranged_namespace}" \
  deploy/decode-engine-deployment -c decode-engine -- \
  /opt/vllm-layerwise/start-decode.sh
ranged_wait_for_url "${ranged_prefill_pod}" prefill-engine \
  http://127.0.0.1:8100/v1/models
ranged_wait_for_url "${ranged_decode_pod}" decode-engine \
  http://127.0.0.1:8200/v1/models

bash "${ranged_historical_deployment}/run-smoke-test.sh" \
  "${ranged_artifact_root}/deployment"

jq -e '
  .status == "passed" and .validated == true and .diagnosis == "passed" and
  .expected_master_key_count == 64 and .actual_master_key_count == 64 and
  ([.phases.direct_kv_load.cases[] |
    select(.validated == true and .exact_match == true)] | length) == 4 and
  ([.phases.proxy_kv_load.cases[] |
    select(.validated == true and .exact_match == true)] | length) == 4
' "${ranged_artifact_root}/deployment/concurrent-summary.json"
jq -e '
  .passed == true and .errors == [] and (.checks | length) == 12 and
  all(.checks[]; .passed == true)
' "${ranged_artifact_root}/deployment/log-validation.json"
```

### Finalize the future artifact and preserve the historical decision

Stop both vLLM processes after collection, then checksum the new artifact:

```bash
kubectl exec -n "${ranged_namespace}" \
  deploy/prefill-engine-deployment -c prefill-engine -- \
  /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n "${ranged_namespace}" \
  deploy/decode-engine-deployment -c decode-engine -- \
  /opt/vllm-layerwise/stop-engine.sh decode

(
  cd "${ranged_artifact_root}"
  find . -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum >SHA256SUMS
  sha256sum -c SHA256SUMS
)
echo "new G0-G3 artifact: ${ranged_artifact_root}"
```

For this historical run D1 remains **No**. G4 was authorized and executed only
later, using a separate source identity and artifact; its procedure and result
are recorded in
[the G4 validation report](ranged-api-g4-validation-2026-07-23.md).

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
