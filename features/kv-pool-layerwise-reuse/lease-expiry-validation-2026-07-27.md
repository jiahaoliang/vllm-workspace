# Mooncake Layerwise Read Lease Expiry Validation

## Result

Formal run `20260727T091720Z` passed the corrected lease-expiry plan.

The test proves three separate behaviors:

1. A 31.5-second delay between layer range puts does not invoke or expire a
   read lease. Layer 1 put and `batch_put_end` both succeeded.
2. After commit, a get session can read layer 0, but its layer 1 ranged read
   returns exactly `-707 LEASE_EXPIRED` when the same session is held for
   31.5 seconds against a 30-second Master lease TTL.
3. A fresh `batch_get_start` returns `0`; layer 1 can then be reread, and the
   recovered two-layer buffer matches the source byte for byte.

This is a session-expiry validation, not a missing-object test. Lease expiry
invalidates the old read session but does not delete the committed object.

## Exact Sequence

| Order | Operation | Result |
| ---: | --- | ---: |
| 1 | `batch_put_start` | `[0]` |
| 2 | put layer 0, offset `0` | `[4096]` |
| 3 | wait `31500.155ms` | passed |
| 4 | put layer 1, offset `4096` | `[4096]` |
| 5 | `batch_put_end` | `[0]` |
| 6 | first `batch_get_start` | `[0]` |
| 7 | get layer 0, offset `0` | `[4096]` |
| 8 | wait `31500.097ms` in the same get session | passed |
| 9 | get layer 1 on the old session | `[-707]` |
| 10 | fresh `batch_get_start` | `[0]` |
| 11 | get layer 1 on the fresh session | `[4096]` |
| 12 | `batch_get_end` | `0` |

There was no `batch_get_start` before commit. Master metrics recorded two new
get queries and zero new get-query failures, so no pre-commit `-703` or missing
key result contributed to the pass.

## Cleanup And Runtime State

- temporary object removal returned `0`;
- both NPU memory unregister operations returned `0`;
- Mooncake client close returned `0`;
- `master_allocated_bytes` was `0` before and after;
- no PutStart discard or release was recorded;
- Prefill/Decode Pods remained Running with vLLM stopped, while Master and
  Proxy remained Ready;
- all Pods retained restart count `0`.

No vLLM, vLLM-Ascend, or Mooncake production source was changed.
The complete deployment unit-test suite passed: `50 passed`.

## Complete Runbook

The hard gates are defined in
[`lease-expiry-validation-plan.md`](lease-expiry-validation-plan.md). Run every
command below from the control-repo checkout. The procedure does not restart
Master or either engine Pod. It deliberately stops any live vLLM child process
so no other client can change Master counters during the test. Execute all
`bash` blocks in order in the same Bash session; later steps reuse variables
and functions declared by earlier steps.

### 1. Initialize a new run

The run ID and paths are generated once and reused by every later step. Do not
reuse a run ID or an existing evidence directory.

```bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "${repo_root}"

namespace=ai-inference
role_selector='app in (prefill,decode,mooncake-master,proxy)'
feature_dir=features/kv-pool-layerwise-reuse
deployment_dir=${feature_dir}/deployment
run_id=$(date -u +%Y%m%dT%H%M%SZ)
scratch_dir=/tmp/lease-expiry-${run_id}
evidence_dir=${feature_dir}/evidence/lease-expiry-${run_id}
remote_summary=/tmp/lease-expiry-summary-${run_id}.json

test ! -e "${scratch_dir}"
test ! -e "${evidence_dir}"
mkdir -p "${scratch_dir}"

printf '%s\n' "${run_id}" | tee "${scratch_dir}/run-id.txt"
kubectl config current-context | tee "${scratch_dir}/kubectl-context.txt"
```

### 2. Resolve exactly one running Pod per role

The helper fails when a selector resolves to zero or multiple Running Pods.

```bash
resolve_one_running_pod() {
  local role=$1 selector=$2
  local -a pods=()
  mapfile -t pods < <(
    kubectl get pod -n "${namespace}" -l "${selector}" \
      --field-selector=status.phase=Running \
      -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'
  )
  if [[ ${#pods[@]} -ne 1 || -z ${pods[0]} ]]; then
    printf 'expected one Running %s Pod, got %s\n' \
      "${role}" "${#pods[@]}" >&2
    return 1
  fi
  printf '%s\n' "${pods[0]}"
}

prefill_pod=$(resolve_one_running_pod Prefill app=prefill)
decode_pod=$(resolve_one_running_pod Decode app=decode)
master_pod=$(resolve_one_running_pod Master app=mooncake-master)
proxy_pod=$(resolve_one_running_pod Proxy app=proxy)

printf 'prefill=%s\ndecode=%s\nmaster=%s\nproxy=%s\n' \
  "${prefill_pod}" "${decode_pod}" "${master_pod}" "${proxy_pod}" \
  | tee "${scratch_dir}/resolved-pods.txt"
kubectl get pod -n "${namespace}" -l "${role_selector}" -o wide \
  | tee "${scratch_dir}/pods-before.txt"
```

### 3. Verify the active 30-second Master lease

Check both the Deployment template and the actual PID 1 command. The test's
`--lease-ttl-ms 30000` value must match these checks.

```bash
master_deployment_args=$(
  kubectl get deployment -n "${namespace}" mooncake-master-deployment -o json \
    | jq -r '.spec.template.spec.containers[]
      | select(.name == "mooncake-master") | .args | join(" ")'
)
printf '%s\n' "${master_deployment_args}" \
  | tee "${scratch_dir}/master-deployment-args.txt"
rg -F -- '--default_kv_lease_ttl=30s' \
  "${scratch_dir}/master-deployment-args.txt"

kubectl exec -n "${namespace}" "${master_pod}" -c mooncake-master -- \
  ps -o args= -p 1 | tee "${scratch_dir}/master-process-args.txt"
rg -F -- '--default_kv_lease_ttl=30s' \
  "${scratch_dir}/master-process-args.txt"
```

### 4. Stop vLLM and verify the runtime API

The engine containers remain Running and keep their NPU allocations. Only the
manually started vLLM child processes are stopped. Both stop scripts are
idempotent.

```bash
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  /opt/vllm-layerwise/stop-engine.sh prefill \
  | tee "${scratch_dir}/stop-prefill.log"
kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- \
  /opt/vllm-layerwise/stop-engine.sh decode \
  | tee "${scratch_dir}/stop-decode.log"

assert_no_vllm() {
  local pod=$1 container=$2
  if kubectl exec -n "${namespace}" "${pod}" -c "${container}" -- \
      pgrep -af '[v]llm.entrypoints.openai.api_server'; then
    printf 'vLLM is still running in %s\n' "${pod}" >&2
    return 1
  fi
}
assert_no_vllm "${prefill_pod}" prefill-engine
assert_no_vllm "${decode_pod}" decode-engine

kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 /opt/vllm-layerwise/check-runtime.py \
  | tee "${scratch_dir}/runtime-api-check.log"
```

### 5. Capture source identity and pre-run state

The test sources are copied byte for byte because they may be newer than the
control-repo HEAD. `repos/*` remain independent repositories.

```bash
git rev-parse HEAD > "${scratch_dir}/control-head.txt"
git status --short > "${scratch_dir}/git-status-before.txt"
git -C repos/vllm-ascend rev-parse HEAD \
  > "${scratch_dir}/vllm-ascend-head.txt"
git -C repos/Mooncake rev-parse HEAD \
  > "${scratch_dir}/mooncake-head.txt"
cp workspace.lock.json "${scratch_dir}/workspace.lock.json"
cp "${deployment_dir}/lease-expiry-test.py" \
  "${deployment_dir}/range-api-smoke.py" \
  "${feature_dir}/lease-expiry-validation-plan.md" \
  "${scratch_dir}/"
sha256sum \
  "${deployment_dir}/lease-expiry-test.py" \
  "${deployment_dir}/range-api-smoke.py" \
  "${feature_dir}/lease-expiry-validation-plan.md" \
  > "${scratch_dir}/source-checksums.txt"

kubectl get deployment -n "${namespace}" mooncake-master-deployment -o yaml \
  > "${scratch_dir}/master-deployment.yaml"
kubectl get pod -n "${namespace}" "${prefill_pod}" -o yaml \
  > "${scratch_dir}/prefill-pod.yaml"
```

Use the Prefill Pod to access the in-cluster Master metrics endpoint:

```bash
fetch_master_metrics() {
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
    python3 -c 'from urllib.request import urlopen; print(urlopen(
      "http://mooncake-master-service:9003/metrics",
      timeout=10).read().decode(), end="")'
}

fetch_master_metrics > "${scratch_dir}/master-before.metrics"
metric_value() {
  local file=$1 metric=$2
  awk -v metric="${metric}" '$1 == metric {print $2; exit}' "${file}"
}
test "$(metric_value "${scratch_dir}/master-before.metrics" \
  master_key_count)" -eq 0
test "$(metric_value "${scratch_dir}/master-before.metrics" \
  master_active_clients)" -eq 0
test "$(metric_value "${scratch_dir}/master-before.metrics" \
  master_allocated_bytes)" -eq 0

kubectl logs -n "${namespace}" "${master_pod}" -c mooncake-master \
  > "${scratch_dir}/master-before.log"
master_before_lines=$(wc -l < "${scratch_dir}/master-before.log")
printf '%s\n' "${master_before_lines}" \
  > "${scratch_dir}/master-before-lines.txt"
```

### 6. Copy and execute the test

Copy both files because `lease-expiry-test.py` imports the ranged smoke helper
from the same directory. Preserve the test exit code instead of allowing
`set -e` to skip evidence collection.

```bash
kubectl cp -n "${namespace}" \
  "${deployment_dir}/range-api-smoke.py" \
  "${prefill_pod}:/tmp/range-api-smoke.py" -c prefill-engine
kubectl cp -n "${namespace}" \
  "${deployment_dir}/lease-expiry-test.py" \
  "${prefill_pod}:/tmp/lease-expiry-test.py" -c prefill-engine

local_test_sha=$(sha256sum "${deployment_dir}/lease-expiry-test.py" \
  | awk '{print $1}')
local_helper_sha=$(sha256sum "${deployment_dir}/range-api-smoke.py" \
  | awk '{print $1}')
remote_test_sha=$(kubectl exec -n "${namespace}" "${prefill_pod}" \
  -c prefill-engine -- sha256sum /tmp/lease-expiry-test.py \
  | awk '{print $1}')
remote_helper_sha=$(kubectl exec -n "${namespace}" "${prefill_pod}" \
  -c prefill-engine -- sha256sum /tmp/range-api-smoke.py \
  | awk '{print $1}')
test "${local_test_sha}" = "${remote_test_sha}"
test "${local_helper_sha}" = "${remote_helper_sha}"
printf 'lease-expiry-test.py\t%s\nrange-api-smoke.py\t%s\n' \
  "${remote_test_sha}" "${remote_helper_sha}" \
  > "${scratch_dir}/pod-source-checksums.txt"

set +e
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 /tmp/lease-expiry-test.py \
    --output "${remote_summary}" \
    --lease-ttl-ms 30000 \
    --wait-margin-ms 1500 \
    --page-size 4096 \
  > "${scratch_dir}/runtime.log" 2>&1
runner_rc=$?
set -e
printf '%s\n' "${runner_rc}" > "${scratch_dir}/runner.exit-code"

set +e
kubectl cp -n "${namespace}" \
  "${prefill_pod}:${remote_summary}" \
  "${scratch_dir}/summary.json" -c prefill-engine
summary_copy_rc=$?
set -e
printf '%s\n' "${summary_copy_rc}" \
  > "${scratch_dir}/summary-copy.exit-code"
```

### 7. Always collect post-run state

Run this section even when the test or summary copy failed.

```bash
fetch_master_metrics > "${scratch_dir}/master-after.metrics"
kubectl logs -n "${namespace}" "${master_pod}" -c mooncake-master \
  > "${scratch_dir}/master-after.log"
master_after_lines=$(wc -l < "${scratch_dir}/master-after.log")

if (( master_after_lines >= master_before_lines )); then
  tail -n +$((master_before_lines + 1)) \
    "${scratch_dir}/master-after.log" \
    > "${scratch_dir}/master-window.log"
else
  cp "${scratch_dir}/master-after.log" \
    "${scratch_dir}/master-window.log"
  printf '%s\n' 'Master log rotated during the run' \
    > "${scratch_dir}/master-log-rotation.txt"
fi

kubectl get pod -n "${namespace}" -l "${role_selector}" -o wide \
  > "${scratch_dir}/pods-final.txt"
kubectl get pod -n "${namespace}" -l "${role_selector}" -o json \
  > "${scratch_dir}/pods-final.json"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  ps -eo pid,stat,args > "${scratch_dir}/prefill-final-ps.txt"
```

### 8. Enforce the structured hard gates

Both the process exit and summary copy must succeed. The `jq` assertion checks
the complete API order, not just the presence of `-707` somewhere in the file.

```bash
test "${runner_rc}" -eq 0
test "${summary_copy_rc}" -eq 0

jq -e '
  .passed == true
  and (.errors | length == 0)
  and all(.cases[]; .passed == true)
  and all(.cleanup[]; .passed == true)
  and (.waits | length == 2)
  and all(.waits[]; .elapsed_ms >= 30000)
  and (.semantic_result == {
    "expired_session_error_code": -707,
    "fresh_batch_get_start_after_expiry_finds_object": true,
    "old_get_session_survives_ttl": false,
    "slow_put_completed_after_read_ttl_gap": true
  })
  and ([.api_calls[]
    | select(.operation | startswith("batch_"))
    | {operation, phase, result}] == [
      {"operation":"batch_put_start",
       "phase":"slow_put","result":[0]},
      {"operation":"batch_put_from_multi_buffer_ranges",
       "phase":"slow_put_layer_0","result":[4096]},
      {"operation":"batch_put_from_multi_buffer_ranges",
       "phase":"slow_put_layer_1","result":[4096]},
      {"operation":"batch_put_end",
       "phase":"commit","result":[0]},
      {"operation":"batch_get_start",
       "phase":"read_session","result":[0]},
      {"operation":"batch_get_into_multi_buffer_ranges",
       "phase":"read_layer_0","result":[4096]},
      {"operation":"batch_get_into_multi_buffer_ranges",
       "phase":"read_layer_1_expired_session","result":[-707]},
      {"operation":"batch_get_start",
       "phase":"fresh_read_session","result":[0]},
      {"operation":"batch_get_into_multi_buffer_ranges",
       "phase":"read_layer_1_fresh_session","result":[4096]},
      {"operation":"batch_get_end",
       "phase":"fresh_read_session","result":0}
    ])
  and ([.cases[]
    | select(.name == "two_layer_data_matches_after_fresh_lease")][0]
    | .actual == true)
' "${scratch_dir}/summary.json"

if rg -i 'Traceback|out of memory|\bOOM\b' \
    "${scratch_dir}/runtime.log"; then
  printf '%s\n' 'fatal pattern found in runtime log' >&2
  exit 1
fi
```

### 9. Verify metrics deltas and final processes

With both vLLM engines stopped, no other client should alter these counters.
The expired ranged read is rejected by the client's cached deadline, so it
must not add a failed Master query.

```bash
assert_metric_delta() {
  local metric=$1 expected=$2
  local before after delta
  before=$(metric_value "${scratch_dir}/master-before.metrics" "${metric}")
  after=$(metric_value "${scratch_dir}/master-after.metrics" "${metric}")
  test -n "${before}" && test -n "${after}"
  delta=$((after - before))
  printf '%s\t%s\t%s\t%s\n' \
    "${metric}" "${before}" "${after}" "${delta}" \
    >> "${scratch_dir}/metrics-delta.tsv"
  test "${delta}" -eq "${expected}"
}

printf 'metric\tbefore\tafter\tdelta\n' \
  > "${scratch_dir}/metrics-delta.tsv"
assert_metric_delta master_batch_put_start_requests_total 1
assert_metric_delta master_batch_put_end_requests_total 1
assert_metric_delta master_batch_get_replica_list_requests_total 2
assert_metric_delta master_batch_get_replica_list_failures_total 0
assert_metric_delta master_remove_requests_total 1
assert_metric_delta master_put_start_discard_cnt 0
assert_metric_delta master_put_start_release_cnt 0

test "$(metric_value "${scratch_dir}/master-before.metrics" \
  master_allocated_bytes)" -eq 0
test "$(metric_value "${scratch_dir}/master-after.metrics" \
  master_allocated_bytes)" -eq 0
test "$(metric_value "${scratch_dir}/master-after.metrics" \
  master_key_count)" -eq 0
test "$(metric_value "${scratch_dir}/master-after.metrics" \
  master_active_clients)" -eq 0

if rg 'lease-expiry-test|vllm.entrypoints|api_server' \
    "${scratch_dir}/prefill-final-ps.txt"; then
  printf '%s\n' 'test or vLLM process remains in Prefill Pod' >&2
  exit 1
fi
jq -e '
  (.items | length) == 4
  and all(.items[];
    .status.phase == "Running"
    and all(.status.containerStatuses[]; .restartCount == 0))
  and all(.items[]
    | select(.metadata.labels.app == "mooncake-master"
      or .metadata.labels.app == "proxy");
    all(.status.containerStatuses[]; .ready == true))
  and all(.items[]
    | select(.metadata.labels.app == "prefill"
      or .metadata.labels.app == "decode");
    all(.status.containerStatuses[]; .ready == false))
' \
  "${scratch_dir}/pods-final.json"
```

### 10. Run the complete deployment test suite

The retained host uses a temporary pytest installation to avoid changing the
workspace. If it is absent, install pytest into that same `/tmp` target from an
available package index or wheel cache before continuing.

```bash
pytest_path=/tmp/layerwise-stress-pytest
PYTHONPATH=${pytest_path} python3 -c 'import pytest'
PYTHONPATH=${pytest_path} python3 -m pytest -q \
  "${deployment_dir}/tests" \
  | tee "${scratch_dir}/unit-tests.log"
rg -F '50 passed' "${scratch_dir}/unit-tests.log"
```

### 11. Publish immutable evidence

Only publish after every gate above succeeds. The temporary full Master logs
remain in `scratch_dir`; the published set keeps the bounded test window.

```bash
publish_dir=${scratch_dir}/publish
mkdir -p "${publish_dir}"

cp \
  "${scratch_dir}/control-head.txt" \
  "${scratch_dir}/git-status-before.txt" \
  "${scratch_dir}/kubectl-context.txt" \
  "${scratch_dir}/lease-expiry-test.py" \
  "${scratch_dir}/lease-expiry-validation-plan.md" \
  "${scratch_dir}/master-after.metrics" \
  "${scratch_dir}/master-before.metrics" \
  "${scratch_dir}/master-deployment-args.txt" \
  "${scratch_dir}/master-deployment.yaml" \
  "${scratch_dir}/master-process-args.txt" \
  "${scratch_dir}/master-window.log" \
  "${scratch_dir}/metrics-delta.tsv" \
  "${scratch_dir}/mooncake-head.txt" \
  "${scratch_dir}/pods-before.txt" \
  "${scratch_dir}/pods-final.json" \
  "${scratch_dir}/pods-final.txt" \
  "${scratch_dir}/pod-source-checksums.txt" \
  "${scratch_dir}/prefill-final-ps.txt" \
  "${scratch_dir}/prefill-pod.yaml" \
  "${scratch_dir}/range-api-smoke.py" \
  "${scratch_dir}/resolved-pods.txt" \
  "${scratch_dir}/run-id.txt" \
  "${scratch_dir}/runner.exit-code" \
  "${scratch_dir}/runtime-api-check.log" \
  "${scratch_dir}/runtime.log" \
  "${scratch_dir}/source-checksums.txt" \
  "${scratch_dir}/stop-decode.log" \
  "${scratch_dir}/stop-prefill.log" \
  "${scratch_dir}/summary-copy.exit-code" \
  "${scratch_dir}/summary.json" \
  "${scratch_dir}/unit-tests.log" \
  "${scratch_dir}/vllm-ascend-head.txt" \
  "${scratch_dir}/workspace.lock.json" \
  "${publish_dir}/"

printf '# Layerwise Read Lease Expiry Evidence\n\nRun `%s` passed. See `summary.json` and `metrics-delta.tsv`.\n' \
  "${run_id}" > "${publish_dir}/README.md"

(
  cd "${publish_dir}"
  find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS
)

mkdir -p "$(dirname "${evidence_dir}")"
mv "${publish_dir}" "${evidence_dir}"
sha256sum "${evidence_dir}/SHA256SUMS"
```

After review, update the feature report and
[`evidence/README.md`](evidence/README.md) with the new run ID and manifest
digest. Do not edit files inside a published evidence directory; a correction
requires a new UTC run.

### 12. Failure handling

When any gate fails:

1. Do not create or update `evidence_dir`.
2. Retain the entire `scratch_dir`, including full before/after Master logs.
3. Confirm no `lease-expiry-test.py` process remains in the Prefill Pod.
4. Inspect `runner.exit-code`, `runtime.log`, partial `summary.json`, metrics,
   and `master-window.log` before changing code or configuration.
5. The Python runner performs `batch_get_end`/`batch_put_revoke`, key removal,
   buffer unregister, and client close in `finally`; any failed cleanup step is
   recorded in `summary.json` and is itself a hard failure.
6. After correcting the concrete cause, use a new UTC run ID and restart from
   Step 1.

Once a successful run is published, the Pod-side temporary files can be
removed without touching the retained Pods or NPU allocations:

```bash
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  rm -f /tmp/lease-expiry-test.py /tmp/range-api-smoke.py "${remote_summary}"
```

The reference formal evidence is archived under
[`lease-expiry-20260727T091720Z`](evidence/lease-expiry-20260727T091720Z/README.md).
