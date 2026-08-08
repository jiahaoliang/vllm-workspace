# Mooncake Layerwise Performance Validation

This directory implements the preparation, handoff gate, execution, and raw
reporting contract in
[`2026-08-08-layerwise-performance-validation-design.md`](../../2026-08-08-layerwise-performance-validation-design.md).

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

After the listener accepts the handoff, execute DP1 then DP2 in the same run
root. A retry uses a new attempt directory; `--resume` never overwrites an
earlier attempt.

```bash
run_id=$(date -u +%Y%m%dT%H%M%SZ)
run_root="/tmp/layerwise-performance-${run_id}"
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh \
  run --topology dp1 --output "${run_root}"
python3 -m performance.report check --root "${run_root}" --scope dp1
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh \
  run --topology dp2 --output "${run_root}" --resume
python3 -m performance.report check --root "${run_root}" --scope all
```

Render raw per-repetition rows and direct ratios:

```bash
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
python3 -m performance.report render \
  --root "${run_root}" \
  --output features/kv-pool-layerwise-reuse/layerwise-performance-validation-2026-08-08.md
```

The report does not remove outliers, calculate statistical significance, or
assign a performance pass/fail result.
