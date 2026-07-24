# Mooncake Layerwise KVPool Deployment Validation, 2026-07-23

## Result

The original sequential deployment smoke passed for this path:

```text
standard Kubernetes proxy
  -> AscendStoreConnector producer
  -> Mooncake shared KVPool
  -> AscendStoreConnector consumer
```

This is smoke-level evidence for routing, shared block-key visibility, and a
successful consumer layerwise load. It is not strict proof that every physical
layer used the ranged APIs or that the whole-key APIs were never called; the
current source has no structured per-layer operation trace.

The final distinct-cache concurrent correctness smoke also passed. Four
requests shared 12 leading blocks and each had 13 request-specific blocks. Both
direct decoder and full proxy concurrency returned each request's own marker,
with per-response logs proving that all 25 blocks were loaded layerwise.

An earlier same-cache prototype did reproduce `CASE_ONE -> CASE_TWO` through
the proxy. Because all four requests in that prototype loaded the same block
keys, it did not test cache selection. The anomaly remains a separate proxy
concurrency risk even though it did not recur in the final distinct-cache run.
Neither test is a ranged API test; ranged API validation is deferred.

## Locked inputs

| Input | Value |
| --- | --- |
| Date | `2026-07-23` |
| Node | `n1` |
| NPU | two `Ascend910B4`, 32 GiB each |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2` |
| Model | `vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| vLLM source | `ee0da84ab9e04ac7610e28580af62c365e898389` |
| vLLM-Ascend source | `663209fd6208a59a48742f75116345bf5f5281ec` |
| Mooncake source | `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` |
| Namespace | `ai-inference` |

The image's shallow editable vLLM install reports
`0.1.dev1+gee0da84ab`; both engine Pods used the supported
`VLLM_VERSION=0.24.0` compatibility override.

## Historical Reproduction Runbook

This runbook was reconstructed from the committed fixture, scripts, and
checked-in evidence after the validation completed. Adding it did not rerun the
cluster test. It has two distinct uses:

- the evidence replay below verifies the original result without Kubernetes;
- the live procedure creates a new result and must never overwrite or be
  represented as the 2026-07-23 evidence.

Run all commands from the control-repo root in Bash. The accepted result is the
final distinct-cache smoke; its warmup phase also retains the sequential
populate/reuse coverage. The earlier same-cache prototype is historical
diagnostic evidence and is not a reproduction target.

### Verify the checked-in result without rerunning

```bash
set -euo pipefail

readonly deployment_evidence_root=features/kv-pool-layerwise-reuse/evidence/ranged-api-20260723T094716Z
readonly deployment_evidence="${deployment_evidence_root}/deployment"

(
  cd "${deployment_evidence_root}"
  sha256sum -c SHA256SUMS
)

grep -qx '0' "${deployment_evidence}/smoke-test.exit-code"
grep -qx '0' "${deployment_evidence}/log-validation.exit-code"
jq -e '
  .status == "passed" and
  .validated == true and
  .diagnosis == "passed" and
  .expected_master_key_count == 64 and
  .actual_master_key_count == 64 and
  (.phases.empty_pool_baseline.cases | length) == 4 and
  all(.phases.empty_pool_baseline.cases[];
    .http_status == 200 and .validated == true) and
  (.phases.warmup.cases | length) == 5 and
  all(.phases.warmup.cases[];
    .http_status == 200 and .validated == true) and
  ([.phases.direct_kv_load.cases[] |
    select(.validated == true and .exact_match == true)] | length) == 4 and
  ([.phases.proxy_kv_load.cases[] |
    select(.validated == true and .exact_match == true)] | length) == 4
' "${deployment_evidence}/concurrent-summary.json"

jq -e '
  .passed == true and
  .errors == [] and
  (.checks | length) == 12 and
  all(.checks[];
    .passed == true and .hit_blocks == true and
    .hit_tokens == true and .layerwise_load == true)
' "${deployment_evidence}/log-validation.json"

grep -Eq '^master_key_count 0$' \
  "${deployment_evidence}/smoke-artifacts/mooncake-master-initial.metrics"
grep -Eq '^master_key_count 64$' \
  "${deployment_evidence}/mooncake-master.metrics"
```

The complete checksum command verifies the G0-G3 archive because the deployment
files share that immutable artifact root. The deployment-specific assertions
then reproduce the acceptance decision recorded in this report.

### Prepare the frozen fixture for a future live rerun

The historical source snapshot and runner are committed under the evidence
tree. Use them instead of the evolving files in the current branch:

```bash
readonly deployment_namespace=ai-inference
readonly historical_fixture_root="${deployment_evidence_root}/environment/deployment-fixture"
readonly historical_source_root="${historical_fixture_root}/source"
readonly historical_deployment_dir="${historical_source_root}/features/kv-pool-layerwise-reuse/deployment"
readonly historical_vllm_ascend_commit=663209fd6208a59a48742f75116345bf5f5281ec
readonly historical_fixture_manifest_sha=3d6671676e1959f2f7967102e1f53ae5289ac57fcbafa4eca889642a383ec79d

grep -Fx 'G3_FIXTURE_ID=commit:2d0bd8a7db177b4a3aed2ff69fac845f756ff21d' \
  "${historical_fixture_root}/IDENTITY.txt"
test "$(sha256sum "${historical_source_root}/SOURCE-SHA256SUMS" | awk '{print $1}')" = \
  "${historical_fixture_manifest_sha}"
(
  cd "${historical_source_root}"
  sha256sum -c SOURCE-SHA256SUMS
)

for deployment_manifest in \
  00-namespace.yaml \
  10-runtime-config.yaml \
  30-mooncake-master.yaml \
  40-prefill-engine.yaml \
  50-decode-engine.yaml \
  20-proxy-server.yaml; do
  kubectl apply -f "${historical_deployment_dir}/${deployment_manifest}"
done

kubectl rollout status -n "${deployment_namespace}" \
  deployment/mooncake-master-deployment --timeout=120s
kubectl rollout status -n "${deployment_namespace}" \
  deployment/proxy-server-deployment --timeout=120s
kubectl wait -n "${deployment_namespace}" \
  --for=jsonpath='{.status.phase}'=Running pod -l app=prefill --timeout=120s
kubectl wait -n "${deployment_namespace}" \
  --for=jsonpath='{.status.phase}'=Running pod -l app=decode --timeout=120s
```

Before changing process state, require exactly the image baseline in each engine
Pod. `git status` catches Python files copied during a later G4 session even
though the embedded Git `HEAD` remains unchanged:

```bash
test "$(kubectl exec -n "${deployment_namespace}" \
  deploy/prefill-engine-deployment -c prefill-engine -- \
  git -C /vllm-workspace/vllm-ascend rev-parse HEAD)" = \
  "${historical_vllm_ascend_commit}"
test -z "$(kubectl exec -n "${deployment_namespace}" \
  deploy/prefill-engine-deployment -c prefill-engine -- \
  git -C /vllm-workspace/vllm-ascend status --porcelain)"
test "$(kubectl exec -n "${deployment_namespace}" \
  deploy/decode-engine-deployment -c decode-engine -- \
  git -C /vllm-workspace/vllm-ascend rev-parse HEAD)" = \
  "${historical_vllm_ascend_commit}"
test -z "$(kubectl exec -n "${deployment_namespace}" \
  deploy/decode-engine-deployment -c decode-engine -- \
  git -C /vllm-workspace/vllm-ascend status --porcelain)"

kubectl exec -n "${deployment_namespace}" \
  deploy/prefill-engine-deployment -c prefill-engine -- \
  python3 /opt/vllm-layerwise/check-runtime.py
kubectl exec -n "${deployment_namespace}" \
  deploy/decode-engine-deployment -c decode-engine -- \
  python3 /opt/vllm-layerwise/check-runtime.py
```

If either source check fails, the existing Pods are not the historical fixture.
Do not silently copy `663209fd` over later work. Preserve the synced files and
use a clean, deliberately prepared fixture. A run against another source tree
is valid only as a new experiment with a newly recorded identity.

### Reset, start, and execute the future rerun

Stop only the child vLLM processes, reset Master, and prove the pool is empty:

```bash
kubectl exec -n "${deployment_namespace}" \
  deploy/prefill-engine-deployment -c prefill-engine -- \
  /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n "${deployment_namespace}" \
  deploy/decode-engine-deployment -c decode-engine -- \
  /opt/vllm-layerwise/stop-engine.sh decode

kubectl rollout restart -n "${deployment_namespace}" \
  deployment/mooncake-master-deployment
kubectl rollout status -n "${deployment_namespace}" \
  deployment/mooncake-master-deployment --timeout=120s

deployment_empty_metrics="/tmp/mooncake-master-empty-$(date -u +%Y%m%dT%H%M%SZ).metrics"
kubectl exec -n "${deployment_namespace}" \
  deploy/prefill-engine-deployment -c prefill-engine -- python3 -c \
  'import sys, urllib.request; sys.stdout.buffer.write(urllib.request.urlopen(sys.argv[1], timeout=10).read())' \
  http://mooncake-master-service:9003/metrics >"${deployment_empty_metrics}"
grep -Eq '^master_key_count 0$' "${deployment_empty_metrics}"
grep -Eq '^master_allocated_bytes 0$' "${deployment_empty_metrics}"

kubectl exec -n "${deployment_namespace}" \
  deploy/prefill-engine-deployment -c prefill-engine -- \
  /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n "${deployment_namespace}" \
  deploy/decode-engine-deployment -c decode-engine -- \
  /opt/vllm-layerwise/start-decode.sh
```

Wait for the real HTTP endpoints rather than relying only on Kubernetes Ready:

```bash
deployment_wait_for_url() {
  local deployment_resource=$1
  local container_name=$2
  local endpoint=$3

  for _ in $(seq 1 240); do
    if kubectl exec -n "${deployment_namespace}" "${deployment_resource}" \
      -c "${container_name}" -- python3 -c \
      'import sys, urllib.request; response = urllib.request.urlopen(sys.argv[1], timeout=5); assert response.status == 200' \
      "${endpoint}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  return 1
}

deployment_wait_for_url deploy/prefill-engine-deployment prefill-engine \
  http://127.0.0.1:8100/v1/models
deployment_wait_for_url deploy/decode-engine-deployment decode-engine \
  http://127.0.0.1:8200/v1/models

deployment_rerun_dir="/tmp/layerwise-smoke-reproduction-$(date -u +%Y%m%dT%H%M%SZ)"
bash "${historical_deployment_dir}/run-smoke-test.sh" \
  "${deployment_rerun_dir}"
```

Apply the same fail-closed acceptance checks to the new directory, then create
its own checksum manifest:

```bash
jq -e '
  .status == "passed" and .validated == true and .diagnosis == "passed" and
  .expected_master_key_count == 64 and .actual_master_key_count == 64 and
  ([.phases.direct_kv_load.cases[] |
    select(.validated == true and .exact_match == true)] | length) == 4 and
  ([.phases.proxy_kv_load.cases[] |
    select(.validated == true and .exact_match == true)] | length) == 4
' "${deployment_rerun_dir}/concurrent-summary.json"
jq -e '
  .passed == true and .errors == [] and (.checks | length) == 12 and
  all(.checks[]; .passed == true)
' "${deployment_rerun_dir}/log-validation.json"
grep -qx '0' "${deployment_rerun_dir}/smoke-test.exit-code"
grep -qx '0' "${deployment_rerun_dir}/log-validation.exit-code"

(
  cd "${deployment_rerun_dir}"
  find . -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum >SHA256SUMS
  sha256sum -c SHA256SUMS
)
```

After collection, stop vLLM without replacing either engine Pod:

```bash
kubectl exec -n "${deployment_namespace}" \
  deploy/prefill-engine-deployment -c prefill-engine -- \
  /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n "${deployment_namespace}" \
  deploy/decode-engine-deployment -c decode-engine -- \
  /opt/vllm-layerwise/stop-engine.sh decode
```

## Deployment state

All four workloads were `Running` and Ready on `n1`. The proxy discovered the
current prefiller at `10.250.40.143:8100` and decoder at
`10.250.40.129:8200`.

The prefill and decode containers both retained `sleep` as PID 1. Their vLLM
API servers were started manually with `/opt/vllm-layerwise/start-prefill.sh`
and `/opt/vllm-layerwise/start-decode.sh`; both were PID 113 at capture time.
This confirms that a vLLM process can be stopped, source can be synced, and the
process can be restarted without replacing the Pod.

The runtime check passed in both engine Pods:

- `vllm_ascend` imported from `/vllm-workspace/vllm-ascend`;
- the vLLM-Ascend compatibility gate selected `0.24.0`;
- `PYTHONHASHSEED=0` was identical across processes;
- all seven required Mooncake session/range methods were callable.

## Smoke evidence

Mooncake Master was restarted before the test. Its initial metrics showed zero
allocated bytes and zero keys. The smoke helper generated a 3205-token shared
prefix, then sent two requests through the proxy with different suffixes.

Both proxy requests returned HTTP 200 with non-empty `choices`. For the first
request:

- prefiller: `hit_blocks=0/25`;
- decoder: `hit_blocks=25/25`;
- decoder: `kvpool hit tokens: 3200, need to load: 3200`;
- decoder: `load_async=False use_layerwise=True`.

For the second request, both the prefiller and decoder reported `25/25`, and
both created a 3200-token layerwise load spec. Proxy logs showed each request
was forwarded first to `10.250.40.143:8100` and then to
`10.250.40.129:8200`.

The saved Master metrics showed:

| Metric | Value |
| --- | ---: |
| `master_key_count` | 25 |
| `master_allocated_bytes` | 99,532,800 |
| `master_total_capacity_bytes` | 2,147,483,648 |
| `master_active_clients` | 2 |
| current prefiller segment | 1,073,741,824 bytes |
| current decoder segment | 1,073,741,824 bytes |

Each worker logged a 1 GiB segment mount. A later
`Global segment size is 0, skip mounting segment` line belongs to the
non-contributing scheduler-side client, not to the worker-side store. The
Master capacity and per-segment metrics confirm the two worker segments.

The second prefiller request attempted `batch_put_start` for the 25 already
complete keys. Master recorded one failed batch and logged
`object_already_exists` for each key. This is the expected duplicate-start
conflict; the existing objects remained readable and both decoder loads
succeeded. `batch_put_end` and batch-get failure counters remained zero.

Artifacts are retained in the prefiller Pod under
`/tmp/layerwise-smoke/`: the two JSON responses and the Mooncake Master metrics
snapshot. The helper was then extended to also save `proxy-endpoints.json` on
subsequent runs. These artifacts are ephemeral and disappear when that Pod is
replaced.

## Concurrent KV cache correctness evidence

The final helper constructed four prompts with 12 identical leading blocks and
13 request-specific blocks. Each unique region repeatedly contained one of
`CASE_ZERO` through `CASE_THREE`; the uncached question suffix was identical for
all requests. Prompts were sent as token IDs, and the runtime assertion recorded
exactly 3200 cached tokens followed by 15 token-for-token identical uncached
tokens. Therefore a request could return its own marker only after using the
corresponding request-specific prompt state. The tokenizer predicted 64 unique
Mooncake objects:

```text
12 shared + (4 requests * 13 unique) = 64 keys
```

Starting from an empty Master, all four concurrent direct decoder baselines
reported `0/25`, returned their own markers, and left `master_key_count=0`.
Case 0 was then populated and reused sequentially through the proxy, followed
by cases 1 through 3. Master reached 25 keys after case 0 and exactly 64 keys
after all four caches were warm.

The final concurrent phases produced:

| Path | Semantic result | Exact responses | KV evidence |
| --- | --- | ---: | --- |
| warmed decoder direct | 4/4 validated | 4/4 | decoder 4/4 at `25/25`, 3200 tokens |
| standard proxy | 4/4 validated | 4/4 | prefiller and decoder 8/8 at `25/25`, 3200 tokens |

All responses exactly matched their no-KV baselines, contained their own cached
marker, and contained no foreign marker. The Master key count remained 64, so
neither consumer loads nor duplicate producer requests created unexpected
objects. `log-validation.json` passed all 12 role/case checks and confirmed
`use_layerwise=True` for every target response ID.

The original host-side evidence was retained at
`/tmp/layerwise-smoke-distinct-cache-20260723-r4/`. A byte-identical persistent
copy is now tracked under
`features/kv-pool-layerwise-reuse/evidence/ranged-api-20260723T094716Z/deployment/`.
Its `concurrent-summary.json` reports `status=passed`, `validated=true`, and
`diagnosis=passed`; both smoke and log-validation exit codes are zero.

### Earlier same-cache anomaly

Before the distinct-cache fixture was introduced, four requests loaded the
same 25 cached blocks and varied only in their uncached suffix. Direct warmed
decoder concurrency returned all expected markers, while the full proxy path
twice produced `CASE_ONE -> CASE_TWO`; serial replay returned `CASE_ONE`. The
corrupted response ID was `cmpl-39c907d6-520f-4238-953a-8904b437389d`.

That prototype detected a real request/output isolation anomaly but could not
show that a request selected another cache because all cache keys were shared.
The final distinct-cache run did not reproduce it. Investigation should still
trace proxy request bodies and prefiller-returned `kv_transfer_params` if this
anomaly appears again.

## Issue found during validation

The first attempt omitted `PYTHONHASHSEED`. vLLM initializes the root of its
block-hash chain randomly when this variable is absent. The producer could see
its own 25 keys, but the independent decoder process computed different keys
and reported `0/25`.

Both engine manifests now set `PYTHONHASHSEED=0`, and `check-runtime.py`
asserts it. After recreating only the two sleep Pods and manually restarting
vLLM, the first decoder request changed from `0/25` to `25/25`.

## Remaining acceptance work

The requested distinct-cache concurrent load path is accepted for this smoke
run. The earlier same-cache proxy anomaly remains a residual concurrency risk;
any recurrence must preserve foreign-marker output as a hard failure and trace
the request body plus prefiller-returned `kv_transfer_params` into the decoder.

This run does not claim the strict matrix from
`development-confirmation-request.md`. That requires opt-in structured trace
evidence for every chunk and physical layer, ranged offsets and byte counts,
successful session close semantics, zero whole-key operations, and injected
lease/failure paths. Those assertions cannot be recovered from HTTP status,
scheduler hit logs, or aggregate Master metrics alone. Ranged API testing is
explicitly deferred and is not part of the concurrent smoke result above.
