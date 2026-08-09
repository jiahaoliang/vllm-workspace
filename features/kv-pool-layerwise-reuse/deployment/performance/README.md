# Mooncake Layerwise Performance Validation

This directory implements the preparation, handoff gate, execution, and raw
reporting contract in the approved
[`2026-08-09-layerwise-performance-rapid-validation-design.md`](../../2026-08-09-layerwise-performance-rapid-validation-design.md).

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
- The formal matrix is exactly DP1, 16384 input tokens, concurrency 8, and five
  points: BULK o128/o1, LAYERWISE o128/o1, and REUSE3 o1.
- Each point has one 8-request warmup wave and one 8-request formal wave. The
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
  prepare --output "/tmp/layerwise-performance-prepare-${prepare_id}"
```

The `m1` kubelet starts a cached CPU-only wrapper image. Preparation verifies
the requested source-image manifest and config digests in local containerd,
mounts that exact image read-only, streams its merged rootfs into the Pod, and
executes benchmark Python through `chroot`. The wrapper is not treated as the
benchmark environment. The retained `layerwise-performance-aisbench` Pod may
be inspected with:

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

After the listener accepts the generation-5 handoff, execute the rapid DP1 run
in a new root. A failed root is retained as diagnostics and is never resumed.

```bash
run_id=$(date -u +%Y%m%dT%H%M%SZ)
run_root="/tmp/layerwise-performance-rapid-${run_id}"
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh \
  run --topology dp1 --output "${run_root}"
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
  python3 -m performance.report check --root "${run_root}" --scope all
```

Render the five raw rows and output-matched direct ratios:

```bash
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
python3 -m performance.report render \
  --root "${run_root}" \
  --output features/kv-pool-layerwise-reuse/layerwise-performance-validation-2026-08-08.md
```

This is single-wave raw characterization, not a steady-state or statistically
significant result. The report does not remove outliers or assign a performance
pass/fail result. Point evidence keeps 10-second telemetry and lightweight
diagnostics; complete Prefill and Decode logs are captured once per variant.
