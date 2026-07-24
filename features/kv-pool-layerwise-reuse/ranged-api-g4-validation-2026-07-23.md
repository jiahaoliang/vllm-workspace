# Mooncake Ranged API G4 Runtime Audit

## Result

**Status:** Passed.

The user explicitly changed the D1 decision to **Yes** and requested the G4
runtime audit defined by the approved plan. One clean production request proved
that both engines used the physical-layer ranged path for every model layer,
that every returned byte count matched the corresponding fragment sum, that the
prefill committed only after its final ranged save, and that neither engine used
the legacy whole-key path.

## Identity

| Input | Value |
| --- | --- |
| plan | `f2c06f159b326e944129b962de4dcf4b09cc093c` |
| G4 checker/control baseline | `7a09ae11ff00f9500b2ad7a981ef83870c2ac3ee` |
| vLLM | `ee0da84ab9e04ac7610e28580af62c365e898389` |
| vLLM-Ascend runtime source | `849c1a7f1f4643e03de74f6784b69504dd5174b5` |
| Mooncake | `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` |
| image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2` |
| image manifest digest | `sha256:661c9bc2c50c1b7253d6f9ec7905cc83f49908ef8cb1919108a5ea828c2cff8d` |
| live image config ID | `sha256:a370384ab214665c3e6d7179aba82d0e5799a290a41370abe372b53f9593283d` |
| model | `vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| physical layers | `27`, read from the captured model `config.json` |
| node / devices | `n1`, two `Ascend910B4` |
| namespace | `ai-inference` |

The image identity remains the G0-G3 base image. G4 used a Python-only sync of
the committed vLLM-Ascend source into the same prefill and decode Pods; neither
engine Pod was replaced. Both live Pods reported the image config ID above.

## Source And Unit Validation

Production changes were limited to the three plan-approved files:

```text
vllm_ascend/envs.py
vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py
vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py
```

Focused tests changed only the three approved test files. The debug variable is
strictly `0` or `1`, defaults to disabled, and returns before constructing the
range payload. Serializer and logger failures are isolated from transfer
results, cleanup, and failure propagation. Events do not contain keys, request
IDs, pointers, GVA values, prompts, or generated text.

Test results:

- three affected files: `138 passed`, 14 existing PyTorch deprecation warnings;
- complete four-file AscendStore target: `248 passed`, the same 14 warnings;
- checker synthetic positive case: passed;
- checker synthetic byte-mismatch, missing-layer, and whole-key case: failed
  closed with all three errors.

`bash format.sh ci` was attempted. Its markdownlint hook could not initialize
because the downloaded Node binary requires unavailable `libatomic.so.1`.
Focused Ruff check and codespell passed. A Ruff whole-file reformat affected
unrelated baseline lines and was discarded; no unrelated formatting remains.

The signed source commit was pushed to
`origin/feature/mooncake-layerwise-kv-pool`, and local and remote SHA matched.

## Runtime Procedure

Both old vLLM processes were stopped before the audit. They required the start
script's final SIGKILL after the 60-second graceful shutdown window. Mooncake
Master was then restarted and reported:

```text
master_key_count 0
master_allocated_bytes 0
master_active_clients 0
```

The committed production Python files were synced to the two existing engine
Pods and matched local SHA-256 values. Both engines were started with
`VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1`; `/proc/<pid>/environ` confirmed the setting
in each process. Both real `/v1/models` endpoints returned HTTP 200. Before the
request, the fresh engine logs contained no completion POST and Master remained
empty. The proxy discovered exactly one prefill and one decode endpoint.

Exactly one non-streaming standard-proxy completion request was sent with
`temperature=0`, seed `2026072304`, 525 prompt tokens, and 16 requested output
tokens. The response was HTTP 200 with one non-empty choice. Each fresh engine
log contained exactly one completion POST, so no other inference traffic was
observed in the audit window. The decoder reported:

```text
kvpool hit tokens: 512, need to load: 512
```

Master ended with four committed keys, 15,925,248 allocated bytes, one batch
put-start, and one batch put-end.

## Reproduction Runbook

Run the following commands from the control-repo root in Bash. They reproduce
the functional G4 audit in a new staging directory; they do not overwrite the
checked-in reference evidence. The cluster must have the numbered deployment
manifests applied, two free Ascend NPUs on `n1`, the image and model listed in
the Identity table, and no other inference client using this fixture.

The original runtime captured commit `849c1a7f1f4643e03de74f6784b69504dd5174b5`.
That commit was subsequently amended to the currently locked and fetchable
`3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6`. Both commits have Git tree
`5440f0398e03146ccde2f52bfd1f69db793b98a5`; the runtime source content is
identical. A new run should use the current locked commit and verify the tree.

### 1. Freeze inputs and create a new artifact directory

```bash
set -euo pipefail

readonly g4_namespace=ai-inference
readonly g4_deployment_dir=features/kv-pool-layerwise-reuse/deployment
readonly g4_reference_dir=features/kv-pool-layerwise-reuse/evidence/ranged-api-g4-20260723T132919Z/runtime-audit
readonly g4_source_commit=3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6
readonly g4_source_tree=5440f0398e03146ccde2f52bfd1f69db793b98a5

test "$(git branch --show-current)" = kv-pool-layerwise-reuse
test "$(git -C repos/vllm-ascend branch --show-current)" = \
  feature/mooncake-layerwise-kv-pool
test -z "$(git -C repos/vllm-ascend status --porcelain)"
test "$(git -C repos/vllm-ascend rev-parse HEAD)" = "${g4_source_commit}"
test "$(git -C repos/vllm-ascend show -s --format=%T HEAD)" = "${g4_source_tree}"
test "$(jq -r '.repos["vllm-ascend"].commit' workspace.lock.json)" = \
  "${g4_source_commit}"

g4_timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
g4_artifact_dir="/tmp/ranged-api-g4-${g4_timestamp}/runtime-audit"
mkdir -p "${g4_artifact_dir}"
cp "${g4_reference_dir}/request.json" "${g4_artifact_dir}/request.json"
cp "${g4_deployment_dir}/check-range-debug-log.py" \
  "${g4_artifact_dir}/check-range-debug-log.py"
```

For a fresh cluster, apply the same fixture before continuing:

```bash
kubectl apply -f "${g4_deployment_dir}/00-namespace.yaml"
kubectl apply -f "${g4_deployment_dir}/10-runtime-config.yaml"
kubectl apply -f "${g4_deployment_dir}/30-mooncake-master.yaml"
kubectl apply -f "${g4_deployment_dir}/40-prefill-engine.yaml"
kubectl apply -f "${g4_deployment_dir}/50-decode-engine.yaml"
kubectl apply -f "${g4_deployment_dir}/20-proxy-server.yaml"
kubectl rollout status -n "${g4_namespace}" \
  deployment/mooncake-master-deployment --timeout=120s
kubectl rollout status -n "${g4_namespace}" \
  deployment/proxy-server-deployment --timeout=120s
kubectl wait -n "${g4_namespace}" --for=jsonpath='{.status.phase}'=Running \
  pod -l app=prefill --timeout=120s
kubectl wait -n "${g4_namespace}" --for=jsonpath='{.status.phase}'=Running \
  pod -l app=decode --timeout=120s
```

The engine Deployments are intentionally not included in `rollout status`:
their containers run `sleep infinity` and remain `0/1 Ready` until vLLM is
started manually. Resolve exactly one Running Pod for each engine:

```bash
test "$(kubectl get pods -n "${g4_namespace}" -l app=prefill -o json | \
  jq '[.items[] | select(.status.phase == "Running")] | length')" -eq 1
test "$(kubectl get pods -n "${g4_namespace}" -l app=decode -o json | \
  jq '[.items[] | select(.status.phase == "Running")] | length')" -eq 1

g4_prefill_pod="$(kubectl get pods -n "${g4_namespace}" -l app=prefill \
  -o json | jq -r '.items[] | select(.status.phase == "Running") | .metadata.name')"
g4_decode_pod="$(kubectl get pods -n "${g4_namespace}" -l app=decode \
  -o json | jq -r '.items[] | select(.status.phase == "Running") | .metadata.name')"

kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine \
  -- python3 /opt/vllm-layerwise/check-runtime.py
kubectl exec -n "${g4_namespace}" "${g4_decode_pod}" -c decode-engine \
  -- python3 /opt/vllm-layerwise/check-runtime.py
```

### 2. Sync the audited Python source and empty Mooncake

The helper stops both engines, copies only Python package changes relative to
the image baseline, compiles them, and leaves vLLM stopped:

```bash
"${g4_deployment_dir}/sync-vllm-ascend-python.sh"
```

Verify the three instrumented production files byte-for-byte in both Pods:

```bash
g4_source_files=(
  vllm_ascend/envs.py
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py
)
g4_pod_targets=(
  "${g4_prefill_pod}:prefill-engine"
  "${g4_decode_pod}:decode-engine"
)

for g4_source_file in "${g4_source_files[@]}"; do
  g4_expected_sha="$(sha256sum "repos/vllm-ascend/${g4_source_file}" | \
    awk '{print $1}')"
  for g4_pod_target in "${g4_pod_targets[@]}"; do
    g4_pod_name="${g4_pod_target%%:*}"
    g4_container_name="${g4_pod_target##*:}"
    g4_actual_sha="$(kubectl exec -n "${g4_namespace}" "${g4_pod_name}" \
      -c "${g4_container_name}" -- sha256sum \
      "/vllm-workspace/vllm-ascend/${g4_source_file}" | awk '{print $1}')"
    test "${g4_actual_sha}" = "${g4_expected_sha}"
  done
done
```

The original source gate ran inside the prefill Pod because this host had no
pytest installation. Copy the three changed tests, then reproduce the affected
and complete AscendStore targets. The expected results are `138 passed` and
`248 passed`, respectively:

```bash
g4_changed_tests=(
  tests/ut/test_envs.py
  tests/ut/distributed/ascend_store/test_backend.py
  tests/ut/distributed/ascend_store/test_kv_transfer.py
)

tar -C repos/vllm-ascend -cf - "${g4_changed_tests[@]}" | \
  kubectl exec -i -n "${g4_namespace}" "${g4_prefill_pod}" \
    -c prefill-engine -- tar -C /vllm-workspace/vllm-ascend -xf -

kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  env TORCH_DEVICE_BACKEND_AUTOLOAD=0 VLLM_VERSION=0.24.0 \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' \
  python3 -m pytest -q \
  tests/ut/test_envs.py \
  tests/ut/distributed/ascend_store/test_backend.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py \
  | tee "${g4_artifact_dir}/pytest-affected.log"

kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  env TORCH_DEVICE_BACKEND_AUTOLOAD=0 VLLM_VERSION=0.24.0 \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' \
  python3 -m pytest -q \
  tests/ut/distributed/ascend_store/test_backend.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py \
  tests/ut/distributed/ascend_store/test_mooncake_session_tracker.py \
  tests/ut/distributed/ascend_store/test_pool_worker.py \
  | tee "${g4_artifact_dir}/pytest-ascend-store.log"

grep -Eq '138 passed' "${g4_artifact_dir}/pytest-affected.log"
grep -Eq '248 passed' "${g4_artifact_dir}/pytest-ascend-store.log"
```

Restarting Master is the pool reset. Capture metrics before either engine is
started and require all three state gauges to be zero:

```bash
kubectl rollout restart -n "${g4_namespace}" \
  deployment/mooncake-master-deployment
kubectl rollout status -n "${g4_namespace}" \
  deployment/mooncake-master-deployment --timeout=120s

kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  python3 -c 'import sys, urllib.request; sys.stdout.buffer.write(urllib.request.urlopen(sys.argv[1], timeout=10).read())' \
  http://mooncake-master-service:9003/metrics \
  >"${g4_artifact_dir}/mooncake-master-empty.metrics"

grep -Eq '^master_key_count 0$' \
  "${g4_artifact_dir}/mooncake-master-empty.metrics"
grep -Eq '^master_allocated_bytes 0$' \
  "${g4_artifact_dir}/mooncake-master-empty.metrics"
grep -Eq '^master_active_clients 0$' \
  "${g4_artifact_dir}/mooncake-master-empty.metrics"

kubectl cp -n "${g4_namespace}" -c prefill-engine \
  "${g4_prefill_pod}:/root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8/config.json" \
  "${g4_artifact_dir}/model-config.json"
g4_num_layers="$(jq -er '.num_hidden_layers | select(. > 0)' \
  "${g4_artifact_dir}/model-config.json")"
test "${g4_num_layers}" -eq 27
```

### 3. Start a clean debug-log window

The start scripts truncate their engine logs. Set the debug variable on the
script process so the spawned vLLM Python process inherits it:

```bash
kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  env VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1 \
  /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n "${g4_namespace}" "${g4_decode_pod}" -c decode-engine -- \
  env VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1 \
  /opt/vllm-layerwise/start-decode.sh

kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  bash -lc 'pid=$(</tmp/vllm-prefill.pid); tr "\0" "\n" <"/proc/${pid}/environ" | grep -Fx VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1'
kubectl exec -n "${g4_namespace}" "${g4_decode_pod}" -c decode-engine -- \
  bash -lc 'pid=$(</tmp/vllm-decode.pid); tr "\0" "\n" <"/proc/${pid}/environ" | grep -Fx VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1'
```

Wait for the real HTTP endpoints, rather than trusting a possibly stale Ready
condition, and save both `/v1/models` responses:

```bash
g4_wait_for_http_200() {
  local g4_wait_pod=$1
  local g4_wait_container=$2
  local g4_wait_url=$3
  local g4_wait_output=$4
  local g4_wait_tmp="${g4_wait_output}.tmp"

  for _ in $(seq 1 240); do
    if kubectl exec -n "${g4_namespace}" "${g4_wait_pod}" \
      -c "${g4_wait_container}" -- python3 -c \
      'import sys, urllib.request; response = urllib.request.urlopen(sys.argv[1], timeout=5); assert response.status == 200; sys.stdout.buffer.write(response.read())' \
      "${g4_wait_url}" >"${g4_wait_tmp}" 2>/dev/null; then
      mv "${g4_wait_tmp}" "${g4_wait_output}"
      return 0
    fi
    sleep 5
  done
  return 1
}

g4_wait_for_http_200 "${g4_prefill_pod}" prefill-engine \
  http://127.0.0.1:8100/v1/models \
  "${g4_artifact_dir}/prefill-models.json"
g4_wait_for_http_200 "${g4_decode_pod}" decode-engine \
  http://127.0.0.1:8200/v1/models \
  "${g4_artifact_dir}/decode-models.json"
```

Check proxy discovery and recheck that no request or key exists in this log
window:

```bash
kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  python3 -c 'import sys, urllib.request; response = urllib.request.urlopen(sys.argv[1], timeout=10); assert response.status == 200; sys.stdout.buffer.write(response.read())' \
  http://vllm-proxy-service:8000/listEndPoints \
  >"${g4_artifact_dir}/proxy-endpoints.json"
jq -e '.status == "ok" and (.prefill_nodes | length) == 1 and (.decode_nodes | length) == 1' \
  "${g4_artifact_dir}/proxy-endpoints.json"

kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  bash -lc '! grep -q "POST /v1/completions" /tmp/vllm-prefill.log'
kubectl exec -n "${g4_namespace}" "${g4_decode_pod}" -c decode-engine -- \
  bash -lc '! grep -q "POST /v1/completions" /tmp/vllm-decode.log'

kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  python3 -c 'import sys, urllib.request; sys.stdout.buffer.write(urllib.request.urlopen(sys.argv[1], timeout=10).read())' \
  http://mooncake-master-service:9003/metrics \
  >"${g4_artifact_dir}/mooncake-master-before-request.metrics"
grep -Eq '^master_key_count 0$' \
  "${g4_artifact_dir}/mooncake-master-before-request.metrics"
```

### 4. Send exactly one deterministic request through the standard proxy

Use the checked-in 525-token request unchanged. It is non-streaming, uses
`temperature=0`, seed `2026072304`, and requests 16 output tokens.

```bash
jq -e '
  .model == "vllm-ascend/DeepSeek-V2-Lite-W8A8" and
  (.prompt | length) == 525 and
  .max_tokens == 16 and
  .temperature == 0 and
  .seed == 2026072304 and
  .stream == false
' "${g4_artifact_dir}/request.json"

kubectl cp -n "${g4_namespace}" -c prefill-engine \
  "${g4_artifact_dir}/request.json" \
  "${g4_prefill_pod}:/tmp/g4-request.json"

kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  python3 -c '
import sys
import urllib.request
from pathlib import Path

payload = Path(sys.argv[2]).read_bytes()
request = urllib.request.Request(
    sys.argv[1], payload, {"Content-Type": "application/json"}
)
response = urllib.request.urlopen(request, timeout=600)
body = response.read()
Path(sys.argv[3]).write_bytes(body)
print(response.status)
assert response.status == 200
' \
  http://vllm-proxy-service:8000/v1/completions \
  /tmp/g4-request.json /tmp/g4-response.json \
  | tee "${g4_artifact_dir}/http-status.txt"

kubectl cp -n "${g4_namespace}" -c prefill-engine \
  "${g4_prefill_pod}:/tmp/g4-response.json" \
  "${g4_artifact_dir}/response.json"
grep -Eq '^200$' "${g4_artifact_dir}/http-status.txt"
jq -e '.choices | type == "array" and length > 0' \
  "${g4_artifact_dir}/response.json"
```

Do not send retries or health probes to `/v1/completions`. A non-200 response
invalidates this window; reset Master and restart both engines before retrying.

### 5. Collect logs and run the fail-closed checker

Collect both logs immediately after the response, then capture final Master and
Pod state:

```bash
kubectl cp -n "${g4_namespace}" -c prefill-engine \
  "${g4_prefill_pod}:/tmp/vllm-prefill.log" \
  "${g4_artifact_dir}/vllm-prefill.log"
kubectl cp -n "${g4_namespace}" -c decode-engine \
  "${g4_decode_pod}:/tmp/vllm-decode.log" \
  "${g4_artifact_dir}/vllm-decode.log"

kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  python3 -c 'import sys, urllib.request; sys.stdout.buffer.write(urllib.request.urlopen(sys.argv[1], timeout=10).read())' \
  http://mooncake-master-service:9003/metrics \
  >"${g4_artifact_dir}/mooncake-master-after.metrics"
kubectl get pods -n "${g4_namespace}" -o yaml \
  >"${g4_artifact_dir}/pods-after-request.yaml"

python3 "${g4_artifact_dir}/check-range-debug-log.py" \
  --prefill-log "${g4_artifact_dir}/vllm-prefill.log" \
  --decode-log "${g4_artifact_dir}/vllm-decode.log" \
  --num-layers "${g4_num_layers}" \
  --output "${g4_artifact_dir}/range-debug-summary.json"

jq -e '
  .status == "passed" and
  .errors == [] and
  .prefill.range_event_count == 27 and
  .prefill.commit_event_count == 1 and
  .prefill.whole_key_event_count == 0 and
  .decode.range_event_count == 27 and
  .decode.commit_event_count == 0 and
  .decode.whole_key_event_count == 0
' "${g4_artifact_dir}/range-debug-summary.json"

for g4_range_log in \
  "${g4_artifact_dir}/vllm-prefill.log" \
  "${g4_artifact_dir}/vllm-decode.log"; do
  sed -n 's/^.*\[KVPOOL_RANGE_DEBUG\] //p' "${g4_range_log}" | jq -es '
    map(select(.event == "range")) as $events |
    ($events | length) == 27 and
    all($events[];
      .key_count == 4 and
      all(.sizes[]; . == [131072, 16384]) and
      all(.requested_bytes[]; . == 147456) and
      all(.results[]; . == 147456)
    )
  '
done

test "$(rg -c 'POST /v1/completions HTTP/1.1" 200 OK' \
  "${g4_artifact_dir}/vllm-prefill.log")" -eq 1
test "$(rg -c 'POST /v1/completions HTTP/1.1" 200 OK' \
  "${g4_artifact_dir}/vllm-decode.log")" -eq 1
rg -q 'kvpool hit tokens: 512, need to load: 512' \
  "${g4_artifact_dir}/vllm-decode.log"
grep -Eq '^master_key_count 4$' \
  "${g4_artifact_dir}/mooncake-master-after.metrics"
grep -Eq '^master_allocated_bytes 15925248$' \
  "${g4_artifact_dir}/mooncake-master-after.metrics"
grep -Eq '^master_batch_put_start_requests_total 1$' \
  "${g4_artifact_dir}/mooncake-master-after.metrics"
grep -Eq '^master_batch_put_end_requests_total 1$' \
  "${g4_artifact_dir}/mooncake-master-after.metrics"
```

The checker is the authoritative ranged-path gate: it parses only structured
`[KVPOOL_RANGE_DEBUG]` JSON events, requires save/load layer sets exactly
`0..26`, validates every result against its fragment-byte sum, checks final
commit ordering, and rejects any whole-key event.

Create and verify a checksum manifest only after all files are final:

```bash
(
  cd "${g4_artifact_dir}"
  find . -maxdepth 1 -type f ! -name SHA256SUMS -printf '%P\0' \
    | sort -z | xargs -0 sha256sum >SHA256SUMS
  sha256sum -c SHA256SUMS
)
echo "G4 artifact: ${g4_artifact_dir}"
```

### 6. Stop the debug processes without replacing the Pods

Only stop the engines after log and checksum collection:

```bash
kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n "${g4_namespace}" "${g4_decode_pod}" -c decode-engine -- \
  /opt/vllm-layerwise/stop-engine.sh decode

kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  bash -lc 'test ! -s /tmp/vllm-prefill.pid'
kubectl exec -n "${g4_namespace}" "${g4_decode_pod}" -c decode-engine -- \
  bash -lc 'test ! -s /tmp/vllm-decode.pid'
kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  bash -lc '! pgrep -af "[v]llm.entrypoints.openai.api_server.*--port 8100"'
kubectl exec -n "${g4_namespace}" "${g4_decode_pod}" -c decode-engine -- \
  bash -lc '! pgrep -af "[v]llm.entrypoints.openai.api_server.*--port 8200"'

if kubectl exec -n "${g4_namespace}" "${g4_prefill_pod}" -c prefill-engine -- \
  python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8100/v1/models", timeout=2)'; then
  echo 'prefill endpoint still accepts requests after cleanup' >&2
  exit 1
fi
if kubectl exec -n "${g4_namespace}" "${g4_decode_pod}" -c decode-engine -- \
  python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8200/v1/models", timeout=2)'; then
  echo 'decode endpoint still accepts requests after cleanup' >&2
  exit 1
fi
kubectl get pods -n "${g4_namespace}" -o wide
```

The two engine Pods, proxy, and Master stay in place. Replacing an engine Pod
would discard the Python-only source sync.

## Checker Result

The machine-readable checker status is `passed` with no errors:

| Assertion | Observed |
| --- | --- |
| prefill save layer set | exactly `0..26`; 27 range events |
| decode load layer set | exactly `0..26`; 27 range events |
| per-event key count | 4 |
| per-key fragments | `[131072, 16384]` bytes |
| per-key requested/result bytes | `147456`; exact match for every event |
| final commit | layer 26, four zero results, after last ranged save |
| prefill whole-key events | 0 |
| decode whole-key events | 0 |

## Evidence

Control-repo evidence directory:

```text
features/kv-pool-layerwise-reuse/evidence/ranged-api-g4-20260723T132919Z/runtime-audit
```

The persistent artifact was imported byte-for-byte into the control repo.
`sha256sum -c SHA256SUMS` passed again in the checked-in directory. Key evidence:

- [SHA256SUMS](evidence/ranged-api-g4-20260723T132919Z/runtime-audit/SHA256SUMS)
- [checker summary](evidence/ranged-api-g4-20260723T132919Z/runtime-audit/range-debug-summary.json)
- [request result](evidence/ranged-api-g4-20260723T132919Z/runtime-audit/request-result.json)
- [prefill log](evidence/ranged-api-g4-20260723T132919Z/runtime-audit/vllm-prefill.log)
- [decode log](evidence/ranged-api-g4-20260723T132919Z/runtime-audit/vllm-decode.log)

The `SHA256SUMS` digest is:

```text
af533b69d6128088bad74dc12dfab95fd31201882ae92577cf0c5908f754181d
```

The artifact contains the complete request and response, model config, both
engine logs, both `/v1/models` responses, empty/final Master metrics, Pod state,
identity, checker source, and machine-readable checker/request summaries. The
completed [G0-G3 evidence](evidence/ranged-api-20260723T094716Z/SHA256SUMS)
was imported separately and was not modified by G4.

## Cleanup And Evidence Boundary

After log collection, both debug vLLM processes were stopped. PID-file,
process-pattern, and direct HTTP checks all confirmed that prefill and decode
vLLM were no longer running. The original engine Pods, proxy Pod, and restarted
Master Pod remained Running; Kubernetes still displayed the engine containers
as Ready during the readiness probe's configured failure window.

G4 proves the physical-layer ranged path for this one clean 1P1D request. It
does not generalize the trace to every production request, and it does not
re-prove shared-owner lifecycle, concurrent isolation, or output equality;
those remain covered by the earlier G2/G3 evidence.
