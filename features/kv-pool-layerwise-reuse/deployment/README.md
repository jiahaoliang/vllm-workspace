# Mooncake Layerwise KVPool 1P1D Deployment

This deployment is a smoke test for the following path at the locked feature
commits:

```text
standard Kubernetes proxy
  -> AscendStoreConnector producer
  -> Mooncake shared KVPool
  -> AscendStoreConnector consumer
```

It is not a `MooncakeLayerwiseConnector` P2P deployment. It does not use Redis,
`/v1/metaserver`, `remote_engine_id`, or host-mounted source code.

## Fixed inputs

| Input | Value |
| --- | --- |
| Node | `n1` (`Ascend910B4`, 32 GiB per NPU) |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.25.1-a2-14beaf16-20260730T130225Z` |
| vLLM | `d02df748bf9efd99022f1a062597dc3cb3808485` |
| vLLM-Ascend | `14beaf161cca6f1e044e20529ca96c6554dbbe50` |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| Model in Pod | `/root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| Namespace | `liangjiahao` |

The image contains editable installs rooted at `/vllm-workspace/vllm` and
`/vllm-workspace/vllm-ascend`. The engine Deployments do not replace these
paths with a `hostPath` mount.

The image uses an editable vLLM install at the exact commit above. Both engine
Pods set the vLLM-Ascend release-line compatibility override
`VLLM_VERSION=0.25.1`; the runtime identity gate records both the installed
package version and editable Git HEAD instead of inferring source identity from
the generated package version.

Both engine Pods also set `PYTHONHASHSEED=0`. vLLM initializes the root of its
block-hash chain from this value; without the same fixed seed in both processes,
identical prompts produce different Mooncake keys and the decoder cannot observe
objects written by the prefiller.

## Preflight

Run these checks from the workspace root:

```bash
readonly namespace=liangjiahao
test "${namespace}" = liangjiahao
kubectl -n liangjiahao config current-context
kubectl get namespace -n liangjiahao "${namespace}"
kubectl describe node -n liangjiahao n1
nerdctl -n k8s.io images --digests \
  docker.io/library/vllm-ascend:kv-pool-layerwise-v0.25.1-a2-14beaf16-20260730T130225Z
du -sh /home/llm_cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8
sha256sum \
  /home/llm_cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8/*.safetensors
```

The two engine Pods require two free `huawei.com/Ascend910` resources on `n1`.
The manifests also require the driver, `hccn.conf`, `hccn_tool`, and model-cache
host paths defined in the engine YAML files.

The Kubernetes API endpoint is hosted by `m1`, but the workspace, model cache,
and locally built image used by this run are on `n1`. Check the CRI-visible
image on the selected workload node; the API-server node is not evidence that
the image exists there.

## Apply

Apply the numbered files in order:

```bash
deployment_dir=features/kv-pool-layerwise-reuse/deployment
kubectl apply -n liangjiahao -f "${deployment_dir}/00-namespace.yaml"
kubectl apply -n liangjiahao -f "${deployment_dir}/10-runtime-config.yaml"
kubectl apply -n liangjiahao -f "${deployment_dir}/30-mooncake-master.yaml"
kubectl apply -n liangjiahao -f "${deployment_dir}/40-prefill-engine.yaml"
kubectl apply -n liangjiahao -f "${deployment_dir}/50-decode-engine.yaml"
kubectl apply -n liangjiahao -f "${deployment_dir}/20-proxy-server.yaml"

kubectl rollout status -n liangjiahao \
  deployment/mooncake-master-deployment --timeout=120s
kubectl get pods -n liangjiahao -o wide
```

Do not delete the `liangjiahao` namespace during cleanup. Stop the engine
processes or delete only the exact resources created by these manifests.

The prefill and decode Pods are expected to show `Running` but `0/1 Ready`
until their vLLM processes are started manually. Their container PID 1 remains
`sleep infinity`, so a vLLM failure does not recreate the Pod.

## Runtime checks and manual start

Check the installed Mooncake API and editable source path in both Pods:

```bash
kubectl exec -n liangjiahao deploy/prefill-engine-deployment \
  -c prefill-engine -- python3 /opt/vllm-layerwise/check-runtime.py
kubectl exec -n liangjiahao deploy/decode-engine-deployment \
  -c decode-engine -- python3 /opt/vllm-layerwise/check-runtime.py
```

Start the two vLLM processes explicitly:

```bash
kubectl exec -n liangjiahao deploy/prefill-engine-deployment \
  -c prefill-engine -- /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n liangjiahao deploy/decode-engine-deployment \
  -c decode-engine -- /opt/vllm-layerwise/start-decode.sh

kubectl wait -n liangjiahao --for=condition=Ready pod \
  -l app=prefill --timeout=20m
kubectl wait -n liangjiahao --for=condition=Ready pod \
  -l app=decode --timeout=20m
```

The vLLM processes are children started by `kubectl exec`, not the container
main process. Read their logs inside the corresponding Pod:

```bash
kubectl exec -n liangjiahao deploy/prefill-engine-deployment \
  -c prefill-engine -- tail -F /tmp/vllm-prefill.log
kubectl exec -n liangjiahao deploy/decode-engine-deployment \
  -c decode-engine -- tail -F /tmp/vllm-decode.log
```

Stop them without replacing the Pods:

```bash
kubectl exec -n liangjiahao deploy/prefill-engine-deployment \
  -c prefill-engine -- /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n liangjiahao deploy/decode-engine-deployment \
  -c decode-engine -- /opt/vllm-layerwise/stop-engine.sh decode
```

## Lease expiry boundary test

`lease-expiry-test.py` isolates two timeout boundaries with one two-layer
Mooncake object. It first waits longer than the active read lease TTL between
layer 0 and layer 1 ranged puts, while leaving the PutStart session open and
without opening a get session. It then commits the object, opens one get
session, reads layer 0, waits past the same TTL, and attempts the layer 1 ranged
read on that same session.

The expected results are:

- layer 1 put and `batch_put_session_end` succeed after the long put gap, and no
  `batch_get_session_start` occurs before commit;
- the layer 1 ranged get on the expired read session returns
  `-707 LEASE_EXPIRED`;
- a fresh `batch_get_session_start` returns `0`, and layer 1 can be read with the new
  lease;
- the final two-layer byte comparison and all cleanup steps pass.

Run it only while vLLM is stopped in the selected Prefill Pod. Copy both the
test and its existing ranged API helper, then pass the deployed Master TTL:

```bash
PREFILL_POD=$(kubectl get pod -n liangjiahao -l app=prefill \
  -o jsonpath='{.items[0].metadata.name}')
kubectl cp -n liangjiahao \
  features/kv-pool-layerwise-reuse/deployment/range-api-smoke.py \
  "${PREFILL_POD}:/tmp/range-api-smoke.py" -c prefill-engine
kubectl cp -n liangjiahao \
  features/kv-pool-layerwise-reuse/deployment/lease-expiry-test.py \
  "${PREFILL_POD}:/tmp/lease-expiry-test.py" -c prefill-engine
kubectl exec -n liangjiahao "${PREFILL_POD}" -c prefill-engine -- \
  python3 /tmp/lease-expiry-test.py \
  --output /tmp/lease-expiry-summary.json \
  --lease-ttl-ms 30000 --wait-margin-ms 1500
```

The formal run and exact API results are archived in
[`lease-expiry-20260727T091720Z`](../evidence/lease-expiry-20260727T091720Z/README.md).

## Python source update without Pod replacement

For Python-only changes under `repos/vllm-ascend/vllm_ascend/`, run:

```bash
features/kv-pool-layerwise-reuse/deployment/sync-vllm-ascend-python.sh
```

The helper compares the working tree with the image commit, stops both vLLM
processes, copies only added or modified package files, applies exact deletions,
and runs `compileall`. It deliberately leaves vLLM stopped so both roles can be
started manually after review. It refuses native, build-system, or dependency
changes; those require rebuilding the image. Pod replacement also discards all
synced container-layer changes.

## Dedicated CPU UT Pod

CPU/mock unit tests run in a separate long-running Pod. It uses the feature
image as its dependency environment but does not request an Ascend NPU, mount
NPU drivers or devices, mount the model cache, or reuse either engine Pod.

Create the namespace and Pod from the workspace root:

```bash
deployment_dir=features/kv-pool-layerwise-reuse/deployment
kubectl apply -n liangjiahao -f "${deployment_dir}/00-namespace.yaml"
kubectl apply -n liangjiahao \
  -f "${deployment_dir}/60-vllm-ascend-ut-pod.yaml"
kubectl wait -n liangjiahao --for=jsonpath='{.status.phase}'=Running \
  pod/vllm-ascend-ut --timeout=120s
```

The host helper synchronizes the current `repos/vllm-ascend` checkout into an
`emptyDir` snapshot and then executes exactly the command supplied after `--`.
It has no default test target:

```bash
features/kv-pool-layerwise-reuse/deployment/run-vllm-ascend-ut.sh -- \
  python3 -m pytest -q \
  tests/ut/distributed/ascend_store/test_backend.py
```

Every invocation verifies that the live Pod uses the expected image and has no
NPU request/limit or `hostPath` volume. It serializes sync/test operations,
records source identity in `/workspace/vllm-ascend/.workspace-source`, excludes
generated caches, and atomically replaces the prior source snapshot.

The Pod remains Running after each command. To remove only this test runtime:

```bash
kubectl delete pod -n liangjiahao vllm-ascend-ut --wait=true
```

Do not delete the `liangjiahao` namespace. Tests explicitly routed to an NPU
directory are outside this CPU/mock Pod contract.

The initial live proof on 2026-07-28 synchronized clean source
`feature/mooncake-layerwise-kv-pool@3f0cbf59` and ran only:

```text
tests/ut/distributed/ascend_store/test_backend.py::TestBackendABC::test_commit_and_revoke_default_to_successful_noops
```

It passed with `1 passed, 14 warnings in 0.21s`. The live Pod had no NPU
request/limit, device plugin, or `hostPath` volume and remained Running after
the command.

## Smoke test

Both engines use `--max-num-seqs 4`, so the scheduler can admit all four
concurrent cases instead of merely queueing them behind a single sequence.

The smoke helper requires an empty Mooncake pool. Stop both vLLM processes,
restart Mooncake Master, then manually start the engines again before running
it. It builds four 25-block prompts with 12 identical leading blocks and 13
request-specific blocks. The unique `CASE_ZERO` through `CASE_THREE` markers
exist only in those cached request-specific blocks. The prompt is sent as token
IDs so the suffix after the 3200-token cache boundary is token-for-token identical
for all cases; loading another request's KV state is therefore a hard failure.
The helper performs four phases:

1. It sends four requests concurrently and directly to the decoder while the
   pool is empty. These responses are the full-recompute correctness baselines;
   the pure consumer must leave `master_key_count` at zero.
2. It sends case 0 twice through the proxy to retain the original populate and
   reuse check, then warms cases 1 through 3. The expected key count is derived
   from the tokenizer-verified shared and unique blocks.
3. It sends all four warmed payloads concurrently and directly to the decoder,
   isolating consumer-side concurrent KV loading from proxy behavior.
4. It sends the same four payloads concurrently through the proxy, covering
   the complete prefiller-to-decoder path.

Each response must start with its own marker in both text and returned token
IDs, contain no foreign marker, return exactly 16 generated token IDs, report
matching prompt/completion usage, and finish with `finish_reason=length`. These
are the hard correctness gates. Full continuation equality with the empty-pool
baseline and any serial replay are retained as diagnostics for deterministic or
batch-dependent generation; they do not replace the marker/token/usage gates.
The marker exists only in request-specific cached blocks, while the uncached
question suffix is identical for all four cases.

Run the host-side wrapper from the workspace root. Its optional argument is an
empty output directory; the default is `/tmp/layerwise-smoke-<timestamp>`.

```bash
features/kv-pool-layerwise-reuse/deployment/run-smoke-test.sh

features/kv-pool-layerwise-reuse/deployment/run-smoke-test.sh \
  /tmp/my-layerwise-smoke
```

The wrapper discovers exactly one Running Pod for each component, clears only
the old `/tmp/layerwise-smoke` artifacts in the prefiller Pod, and runs the
embedded test there. Whether the test passes or fails, it copies the partial
summary and response artifacts and captures final Master metrics, both engine
logs, proxy logs, Master logs, and Pod state. It then correlates every completed
direct and proxy phase response ID with `hit_blocks=25/25`,
`kvpool hit tokens: 3200`, and `use_layerwise=True` log evidence. A smoke,
collection, or log-validation failure makes the wrapper exit nonzero while
retaining all available evidence.

Expected smoke evidence:

- all four direct decoder baselines return HTTP 200 while the pool remains empty;
- all five sequential warmup requests return HTTP 200 and Mooncake reaches the
  tokenizer-derived expected key count;
- both warmed concurrent phases return four HTTP 200 responses with non-empty
  `choices`;
- `concurrent-summary.json` reports `status: passed` and four validated cases
  in both `direct_kv_load` and `proxy_kv_load`; every case passes marker text,
  marker token-prefix, token-count, usage, finish-reason, and isolation gates;
- proxy `/health` succeeds and `/listEndPoints` reports exactly one prefiller and
  one decoder;
- `log-validation.json` reports complete per-response KV hit evidence in the
  decoder log for direct loads and in both engine logs for proxy loads;
- no load failure is hidden by recompute because `kv_load_failure_policy=fail`;
- the host output directory contains Pod-side response artifacts, summary,
  Master metrics, engine/proxy/Master logs, and before/after Pod state.

The marker oracle detects a concurrent request reading another request's KV
state. Together with token-boundary, usage, finish-reason, and per-ID hit-log
checks, it validates deployment, routing, and concurrent external KVPool loads.
Full continuation equality remains diagnostic. Per-layer ranged-call and
whole-key exclusion claims belong to the separate G4 audit checker.

The result from the first run on this machine is recorded in
[`validation-2026-07-23.md`](validation-2026-07-23.md).
