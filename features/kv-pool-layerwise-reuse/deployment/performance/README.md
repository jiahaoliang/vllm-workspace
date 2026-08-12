# Mooncake Layerwise Performance Validation

This directory implements the preparation, handoff gate, execution, and raw
reporting contract in the approved
[`2026-08-12-layerwise-high-hit-performance-validation-design.md`](../../2026-08-12-layerwise-high-hit-performance-validation-design.md).

## Safety Boundary

- Every Kubernetes workload command uses namespace `liangjiahao` explicitly.
- The AISBench Pod is CPU-only on `m1`; it requests neither Ascend910 nor vNPU.
- `prepare` cannot contact an inference endpoint or mutate serving workloads.
- Chat or an image tag cannot authorize traffic. `run` reparses and validates
  the committed handoff, source identities, image identity, functional gates,
  role scope, and evidence checksums before its first command.
- Server images are consumed directly or materialized from an exact Python
  patch with `nerdctl commit`. Dockerfile, BuildKit, and image build commands
  are outside this workflow.
- Generated Prefill and Decode start scripts freeze
  `MOONCAKE_GLOBAL_SEGMENT_SIZE=128GB` per serving rank, identically across all
  variants.
- The formal matrix is exactly DP1, 16384 input tokens, output 1, concurrency
  8, and three points: BULK, LAYERWISE, and REUSE3.
- Each point runs 8 runtime warmups, clears Mooncake, seeds 64 paired 13312-token
  prefixes outside the measured interval, then runs one 64-request formal
  attempt without clearing Mooncake. The exact external Prefix KV hit rate is
  `13312/16384 = 81.25%`.
- All serving variants use `--no-enable-prefix-caching`. The run is rejected
  unless every formal Prefill log reports both `kvpool hit tokens: 13312` and
  `need to load: 13312`, proving that the hit is external rather than local HBM.
- At concurrency 8, the formal attempt contains eight concurrency waves. The
  runner starts the server once per variant, does not retry a point, and defines
  no performance timeout. A valid slow point continues naturally.

## Commands

Run all CPU-only tooling tests:

```bash
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-ut.sh -- \
  python3 -m pytest -q performance/tests
```

Prepare the client, locked AISBench environment, tokenizer identity, and exact
fixtures without waiting for the functional handoff:

```bash
prepare_id=$(date -u +%Y%m%dT%H%M%SZ)
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh \
  prepare \
  --output "/tmp/layerwise-performance-prepare-${prepare_id}" \
  --image docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z \
  --manifest-digest sha256:f8592141757f7e9976898858863e12ccd051ac4a3fd6ade7591f78d9769517e3 \
  --config-digest sha256:ce20411d6043d3830be7601c654b2c9a1d41fb923395cad2ea2e7ba200ebbbbd \
  --tokenizer-source /home/llm_cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8
```

The `m1` kubelet starts the exact cached candidate as a CPU-only wrapper.
Preparation verifies its `linux/arm64` platform plus manifest and config
digests in local containerd before creating the Pod, mounts the same image
read-only, streams its merged rootfs into the Pod, and executes benchmark
Python through `chroot`. Only the seven tokenizer/config files required for
exact prompt generation are tar-streamed from the local model directory; the
Pod has no `hostPath` and preparation does not depend on a Prefill Pod. The
retained `layerwise-performance-aisbench` Pod may be inspected with:

```bash
kubectl get pod -n liangjiahao layerwise-performance-aisbench -o json
```

The exact image contains Python 3.12.13 under a custom prefix. `uv==0.12.3`
does not discover that interpreter when the image rootfs is used through
`chroot`, so preparation records the uv version and creates a standard-library
`venv --system-site-packages` overlay with that exact interpreter. AISBench's
runtime and API requirements are installed only into the overlay, and the
method plus resolved package set are archived in client provenance.

Wait for the committed handoff and record every observation:

```bash
wait_id=$(date -u +%Y%m%dT%H%M%SZ)
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh \
  wait --output "/tmp/layerwise-performance-wait-${wait_id}" --poll-seconds 10
```

Before changing a blocked handoff to ready, run the read-only physical-resource
gate. It requires node `m1`, exactly eight allocatable physical Ascend910
resources, and at least four free after non-terminal Pod requests. It ignores
`huawei.com/vnpu-number` and returns exit code 1 while blocked:

```bash
python3 features/kv-pool-layerwise-reuse/deployment/performance/check-npu-readiness.py \
  --node m1 \
  --output /tmp/layerwise-npu-readiness.json
```

After the listener accepts the current ready handoff, execute the high-hit DP1 run
in a new root. A failed root is retained as diagnostics and is never resumed.

```bash
run_id=$(date -u +%Y%m%dT%H%M%SZ)
run_root="/tmp/layerwise-performance-high-hit-${run_id}"
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh \
  run --topology dp1 --npu-node m1 --output "${run_root}"
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
  python3 -m performance.report check --root "${run_root}" --scope all
```

Render the three aggregate rows, all 192 formal request rows, and direct ratios:

```bash
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
python3 -m performance.report render \
  --root "${run_root}" \
  --output features/kv-pool-layerwise-reuse/layerwise-performance-high-hit-validation-2026-08-12.md
```

This is one formal attempt with eight concurrency waves, not an independently
repeated or statistically significant result. Seed traffic is excluded from
the measured results. The report does not remove outliers or assign a
performance pass/fail result. Point evidence keeps 10-second telemetry,
per-request external-hit proof, and lightweight diagnostics; complete Prefill
and Decode logs are captured once per variant.

## Causal Self-load A/B

This historical diagnosis concerns the earlier cold-cache characterization.
It does not replace or validate the high-hit three-point run above. The causal
runner replays only `DP1 / 16384 input tokens / o1 / c8`, with one
8-request warmup and one 64-request formal attempt. Its immutable control is
`evidence/layerwise-performance-20260810T043500Z/`; the candidate source is
vLLM-Ascend commit `57d3c214e642cdbb529400f0742d1a98a8d38708`. This is a
single-point diagnosis of redundant layerwise self-loads, not a replacement
for the five-point characterization.

The candidate image must be `linux/arm64`, expose a manifest digest, and contain
`pool_worker.py` with SHA-256
`54e3198504a3745b21e172d8e66c4c7c217bbc7642498e3bb4cdbab557b8b6ea`.
The selected NPU node must have at least four replaceable physical
`huawei.com/Ascend910` devices. `huawei.com/vnpu-number` is ignored. As of
2026-08-11, the current cluster inventory contains only `m1`, whose allocatable
resources do not advertise `huawei.com/Ascend910`. Do not start the A/B until
an eligible node is restored.

After setting the exact candidate reference and manifest digest:

```bash
: "${CANDIDATE_IMAGE:?set the committed candidate image reference}"
: "${CANDIDATE_DIGEST:?set its sha256 manifest digest}"
run_id=$(date -u +%Y%m%dT%H%M%SZ)
run_root="/tmp/layerwise-self-load-ab-${run_id}"
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
python3 -m performance.run_layerwise_self_load_ab \
  --output "${run_root}" \
  --control features/kv-pool-layerwise-reuse/evidence/layerwise-performance-20260810T043500Z \
  --image "${CANDIDATE_IMAGE}" \
  --image-digest "${CANDIDATE_DIGEST}" \
  --patch-sha256 54e3198504a3745b21e172d8e66c4c7c217bbc7642498e3bb4cdbab557b8b6ea \
  --source-commit 57d3c214e642cdbb529400f0742d1a98a8d38708 \
  --npu-node "${NPU_NODE:-n1}"
```

Then compare the candidate against the original BULK and LAYERWISE Prefill
iterations and Mooncake replica-list counters:

```bash
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
python3 -m performance.diagnose_layerwise_prefill \
  features/kv-pool-layerwise-reuse/evidence/layerwise-performance-20260810T043500Z \
  --candidate "${run_root}"
```

The diagnosis exits zero only for `PRIMARY_CAUSE_CONFIRMED`; partial recovery
is emitted as `PARTIAL_CAUSE_CONFIRMED` with a nonzero exit status so automation
cannot silently promote it to a complete explanation.
