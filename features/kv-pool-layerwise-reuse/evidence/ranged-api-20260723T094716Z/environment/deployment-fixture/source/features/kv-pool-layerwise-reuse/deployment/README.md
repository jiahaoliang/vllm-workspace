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
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2` |
| vLLM | `ee0da84ab9e04ac7610e28580af62c365e898389` |
| vLLM-Ascend | `663209fd6208a59a48742f75116345bf5f5281ec` |
| Mooncake | `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` |
| Model in Pod | `/root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| Namespace | `ai-inference` |

The image contains editable installs rooted at `/vllm-workspace/vllm` and
`/vllm-workspace/vllm-ascend`. The engine Deployments do not replace these
paths with a `hostPath` mount.

The shallow vLLM clone in this image reports package version
`0.1.dev1+gee0da84ab` even though its exact source commit is the `v0.24.0` tag.
Both engine Pods therefore set the vLLM-Ascend supported compatibility override
`VLLM_VERSION=0.24.0`; without it, the plugin selects incompatible main-branch
patches and fails while importing Transformers 5.13.

Both engine Pods also set `PYTHONHASHSEED=0`. vLLM initializes the root of its
block-hash chain from this value; without the same fixed seed in both processes,
identical prompts produce different Mooncake keys and the decoder cannot observe
objects written by the prefiller.

## Preflight

Run these checks from the workspace root:

```bash
kubectl config current-context
kubectl describe node n1
nerdctl -n k8s.io images --digests \
  docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2
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
kubectl apply -f "${deployment_dir}/00-namespace.yaml"
kubectl apply -f "${deployment_dir}/10-runtime-config.yaml"
kubectl apply -f "${deployment_dir}/30-mooncake-master.yaml"
kubectl apply -f "${deployment_dir}/40-prefill-engine.yaml"
kubectl apply -f "${deployment_dir}/50-decode-engine.yaml"
kubectl apply -f "${deployment_dir}/20-proxy-server.yaml"

kubectl rollout status -n ai-inference \
  deployment/mooncake-master-deployment --timeout=120s
kubectl get pods -n ai-inference -o wide
```

The prefill and decode Pods are expected to show `Running` but `0/1 Ready`
until their vLLM processes are started manually. Their container PID 1 remains
`sleep infinity`, so a vLLM failure does not recreate the Pod.

## Runtime checks and manual start

Check the installed Mooncake API and editable source path in both Pods:

```bash
kubectl exec -n ai-inference deploy/prefill-engine-deployment \
  -c prefill-engine -- python3 /opt/vllm-layerwise/check-runtime.py
kubectl exec -n ai-inference deploy/decode-engine-deployment \
  -c decode-engine -- python3 /opt/vllm-layerwise/check-runtime.py
```

Start the two vLLM processes explicitly:

```bash
kubectl exec -n ai-inference deploy/prefill-engine-deployment \
  -c prefill-engine -- /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n ai-inference deploy/decode-engine-deployment \
  -c decode-engine -- /opt/vllm-layerwise/start-decode.sh

kubectl wait -n ai-inference --for=condition=Ready pod \
  -l app=prefill --timeout=20m
kubectl wait -n ai-inference --for=condition=Ready pod \
  -l app=decode --timeout=20m
```

The vLLM processes are children started by `kubectl exec`, not the container
main process. Read their logs inside the corresponding Pod:

```bash
kubectl exec -n ai-inference deploy/prefill-engine-deployment \
  -c prefill-engine -- tail -F /tmp/vllm-prefill.log
kubectl exec -n ai-inference deploy/decode-engine-deployment \
  -c decode-engine -- tail -F /tmp/vllm-decode.log
```

Stop them without replacing the Pods:

```bash
kubectl exec -n ai-inference deploy/prefill-engine-deployment \
  -c prefill-engine -- /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n ai-inference deploy/decode-engine-deployment \
  -c decode-engine -- /opt/vllm-layerwise/stop-engine.sh decode
```

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

Each KV-load response uses the same fixed seed as its baseline. Exact response
matches are accepted directly. Whitespace-only text changes are also accepted
after normalization. For other quantized concurrent batching differences, the
response must retain its own marker, contain no foreign marker, keep identical
finish/token metadata, and a serial KV-load replay must match the no-KV baseline
exactly. The marker exists only in the request-specific cached blocks; the
uncached question suffix is identical for all four cases.

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
  in both `direct_kv_load` and `proxy_kv_load`; each case is `exact_match` or
  `concurrent_generation_variation`;
- proxy `/health` succeeds and `/listEndPoints` reports exactly one prefiller and
  one decoder;
- `log-validation.json` reports complete per-response KV hit evidence in the
  decoder log for direct loads and in both engine logs for proxy loads;
- no load failure is hidden by recompute because `kv_load_failure_policy=fail`;
- the host output directory contains Pod-side response artifacts, summary,
  Master metrics, engine/proxy/Master logs, and before/after Pod state.

The no-KV comparison detects a concurrent request reading another request's KV
state or otherwise loading corrupted cache content. Together with the per-ID
decoder hit logs, it validates deployment, routing, concurrent external KVPool
loads, and output correctness. The current commit still has no structured
per-layer range trace, so this smoke test does not independently prove that
every physical layer called the ranged Mooncake APIs or that whole-key APIs
remained unused.

The result from the first run on this machine is recorded in
[`validation-2026-07-23.md`](validation-2026-07-23.md).
