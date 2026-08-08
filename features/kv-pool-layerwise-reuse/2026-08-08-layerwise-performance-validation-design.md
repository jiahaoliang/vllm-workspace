# Mooncake Layerwise Performance Validation Design

## Status

Approved in design review on 2026-08-08. This document defines preparation and
performance-validation behavior for workspace Issue #1. It does not claim that
the Mooncake shared-buffer implementation, functional handoff, or performance
run has completed.

## Sources

- Requirement: <https://github.com/jiahaoliang/vllm-workspace/issues/1>
- Functional implementation session:
  `019fdf27-db45-7e83-b02d-a6a26ff55d9d`
- Fail-closed handoff:
  `features/kv-pool-layerwise-reuse/performance-validation-handoff.md`
- AISBench: <https://github.com/AISBench/benchmark>
- AISBench baseline: version `3.1.0`, commit
  `3fd27b4a5fd022fcb5484fb084307f49955491ba`

The implementation phase saves Markdown snapshots of Issue #1 and the
AISBench performance/stable-stage contracts under
`features/kv-pool-layerwise-reuse/references/snapshots/`, with `Source`,
`Captured At`, and `Notes` headers, and indexes them in
`references/sources.md`.

## Objective

Measure two independent effects on the same frozen Mooncake server image:

1. Compare whole-key KV transfer with layerwise ranged transfer while
   compute-side layer reuse is disabled.
2. Compare the same baselines with Prefill compute-side
   `layerwise_num_shared_buffers=3` enabled.

The run is a characterization. It publishes complete raw comparisons but does
not define a performance pass/fail threshold, confidence interval, statistical
significance claim, or nightly regression gate.

Functional identity, request validity, process health, transfer-path identity,
and evidence completeness remain fail-closed gates. A result that fails one of
those gates is invalid performance evidence.

## Scope

### Included

- Backend: Mooncake.
- Model: `vllm-ascend/DeepSeek-V2-Lite-W8A8`.
- Roles: Prefill `kv_producer` plus a pure `kv_consumer` Decode companion that
  never sets `layerwise_num_shared_buffers`. This authorizes ordinary Decode
  transfer, not pure-consumer compute-side reuse.
- Input lengths: exactly 4096, 16384, and 32768 tokenizer tokens.
- Output lengths:
  - one token to isolate Prefill and transfer behavior;
  - 128 tokens to observe complete inference behavior.
- Mechanism topology: Prefill `DP=1, TP=2`; Decode `DP=1, TP=2`.
- Production topology: Prefill `DP=2, TP=2`; Decode `DP=1, TP=2`.
- Physical hardware: Ascend910 cards explicitly reported by Kubernetes, not
  `huawei.com/vnpu-number` capacity.
- Namespace: `liangjiahao` for every server, client, and helper workload.
- Load generator: AISBench in a dedicated CPU-only Pod on node `m1`.
- Server workloads: node `n1`.

### Excluded

- Pure `kv_consumer` compute-side buffer reuse.
- Real-NPU `kv_consumer + consumer_is_to_put=true` buffer reuse.
- Memcache regression or performance.
- FabricMem, A3, CP, TP mismatch, hybrid layouts, Mooncake multi-group, or
  hardware not authorized by the final handoff.
- Shared-prefix or production-data workloads.
- A full Dockerfile or BuildKit rebuild of the server image.
- Performance acceptance thresholds or claims beyond the measured matrix.

## Handoff And Authorization Boundary

The functional session owns
`features/kv-pool-layerwise-reuse/performance-validation-handoff.md`. The
performance workflow continuously watches that file but does not infer
readiness from session messages, source diffs, an image tag, or a partially
populated handoff.

### Preparation Allowed Before Readiness

Before the handoff is ready, the performance workflow may only:

- create the dedicated CPU-only AISBench client Pod on `m1`;
- bootstrap and lock the client Python environment;
- generate deterministic fixtures offline;
- prepare manifests, runner, parsers, checkers, and documentation;
- run CPU-only tests for those preparation artifacts;
- perform read-only cluster and repository inventory.

It must not modify NPU server workloads, install a derived server image, send a
canary, start a benchmark, or create performance evidence that could be
mistaken for a valid run.

### Readiness Contract

Performance preflight and traffic remain blocked until all of the following are
true and independently rechecked:

1. `status: READY_FOR_PERFORMANCE_VALIDATION`.
2. `ready: true`.
3. `generation` is greater than zero.
4. `placeholders_remaining: false`.
5. All required functional gates report `PASS`.
6. The recorded control, vLLM, vLLM-Ascend, and Mooncake commits equal the
   intended local and remote identities.
7. Image platform, digest, source identity, and patched-file identity match the
   handoff.
8. The functional evidence `SHA256SUMS` replays successfully and its digest
   matches the handoff.
9. The handoff's authorized model, topology, hardware, role, and namespace
   include the requested Prefill `kv_producer` plus no-reuse pure-consumer
   Decode companion configuration.

`WAITING_FOR_FUNCTIONAL_VALIDATION`, `BLOCKED`, a missing field, a non-PASS
gate, identity drift, or checksum failure keeps the run blocked.

The generation-0 handoff currently authorizes only `kv_producer` and `kv_both`.
That text is insufficient for this PD performance topology even though Decode
does not request shared-buffer reuse. The functional session must explicitly
authorize the no-reuse pure-consumer Decode companion in its final committed
handoff; otherwise the performance listener remains blocked.

The listener records each observed file generation, content digest, timestamp,
and state transition. Its `run` entrypoint always revalidates the file; an
earlier ready observation cannot authorize a later changed generation.

## Image Strategy

The existing image
`docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z`
is both:

- the base for the functional session's Python patch image; and
- the image used by the CPU-only AISBench client Pod.

It is not itself a valid `REUSE3` server image because it predates the Mooncake
configuration change.

The performance workflow accepts only one of these handoff outcomes:

1. A ready-to-use derived image with exact tag, platform, manifest digest,
   source commits, base digest, patched paths, and patched-file SHA256.
2. Exact handoff-provided Python patch inputs and an audited procedure that
   copies them into a temporary container based on the image above and creates
   a derived tag with `nerdctl commit` in containerd namespace `k8s.io`.

The performance workflow never substitutes a Dockerfile rebuild. If neither
handoff outcome is complete, performance execution remains blocked.

The derived image must be native `linux/arm64`. Before serving, a runtime probe
proves that Python imports the patched path, that its checksum equals the
handoff, and that the image/base/source identities are internally consistent.
The same derived image is used for `BULK`, `LAYERWISE`, and `REUSE3`; only
runtime configuration changes between variants.

## Client Environment

Create a dedicated, CPU-only Pod in namespace `liangjiahao` with:

- `nodeName: m1`;
- no `huawei.com/Ascend910` or `huawei.com/vnpu-number` request or limit;
- the existing base image named above;
- a writable `emptyDir` for tools, virtual environment, fixtures, and raw
  client output;
- explicit CPU and memory requests/limits sized so the client cannot silently
  contend with the server on `n1`.

The base image is `aarch64` and provides Python 3.12.13, but does not currently
contain an executable `uv`. Bootstrap `uv==0.12.3` into the writable volume,
create an isolated virtual environment, and install AISBench from source at
commit `3fd27b4a5fd022fcb5484fb084307f49955491ba` with the API dependencies needed
for the vLLM OpenAI-compatible streaming endpoint.

Archive the bootstrap command, uv version, resolved dependency lock, installed
package list, source commit, downloaded artifact hashes, and install log. Do not
modify the image's system Python environment and do not reuse the long-running
UT Pod as the load generator.

## Experimental Variables

All variants use `backend=mooncake` and explicitly set
`layerwise_prefetch_layers=3`. Fixing prefetch depth is required because its
implicit default depends on `layerwise_num_shared_buffers`; leaving it implicit
would change two variables in the `LAYERWISE` versus `REUSE3` comparison.

| Variant | Prefill extra config | Decode extra config | Outputs |
| --- | --- | --- | --- |
| `BULK` | `use_layerwise=false`, no `layerwise_num_shared_buffers` | same | 1, 128 |
| `LAYERWISE` | `use_layerwise=true`, no `layerwise_num_shared_buffers` | same | 1, 128 |
| `REUSE3` | `use_layerwise=true`, `layerwise_num_shared_buffers=3` | `use_layerwise=true`, no `layerwise_num_shared_buffers` | 1 |

Decode retains the existing consumer-specific options, including
`consumer_is_to_load=true`. The first Mooncake implementation does not enable
compute-side reuse for its pure-consumer role, so `REUSE3` changes only the
Prefill producer.

Apart from the table above and the topology's Prefill DP size, all variants
freeze the same:

- model and served-model name;
- quantization, tokenizer, trust, eager mode, and random/hash seeds;
- TP, PP, PCP, and DCP sizes;
- block size 128;
- chunked Prefill enabled;
- max model length 65536;
- max batched tokens 1024;
- max sequences 64;
- prefix caching setting;
- GPU memory utilization;
- Mooncake endpoint, lease, segment, and storage configuration;
- proxy, network, node, NPU allocation, and container resources;
- server image and host driver/runtime mounts.

`max_num_seqs=64` is high enough for the requested aggregate concurrency scan;
the scheduler and available KV capacity, rather than a lower static sequence
limit, determine saturation.

## Topologies

### Mechanism Topology

- Prefill: `DP=1`, `TP=2`, two physical Ascend910 cards.
- Decode: `DP=1`, `TP=2`, two physical Ascend910 cards.
- Purpose: remove DP load-balancing variance and expose transfer/reuse behavior.

### Production Topology

- Prefill: `DP=2`, local `TP=2`, four physical Ascend910 cards.
- Decode: `DP=1`, `TP=2`, two physical Ascend910 cards.
- Purpose: characterize aggregate throughput, latency, stable concurrency, and
  per-rank utilization in the current six-card production-like deployment.

Every run captures Ready-node allocatable capacity and all non-terminal Pod NPU
requests before applying a topology. The runner never treats `vnpu-number` as a
physical-card count.

## Fixture Contract

Use deterministic, tokenizer-verified, unique prompts. For each input length:

1. Generate exact token sequences at 4096, 16384, or 32768 tokens.
2. Make every request differ within its first complete 128-token block, so no
   two requests share a Mooncake block key.
3. Decode and re-encode every prompt with the frozen tokenizer and reject any
   token-count change.
4. Save prompt text, token IDs, request ID, seed, tokenizer identity, token
   count, and SHA256.
5. Use disjoint fixture slices for warmup and each formal repetition.

The fixture deliberately excludes shared prefixes. The run measures the
current request's Prefill, PD transfer, and Decode path instead of mixing in
cross-request cache-hit benefits.

Generation uses `temperature=0`. Both output profiles set `ignore_eos=true`, so
the one-token and 128-token cases actually return their configured length.

## AISBench Execution Contract

Use the streaming vLLM-compatible service model so TTFT, TPOT, and ITL are
observable. Each task uses:

```text
mode = perf
pressure = true
summarizer = stable_stage
request_rate = 0
batch_size = requested concurrency
```

### Concurrency Scan

- Mechanism topology: 1, 2, 4, 8, 16, 32.
- Production topology: 2, 4, 8, 16, 32, 64 aggregate client concurrency.

Each configuration/input/output scan stops before its next concurrency when:

- an OOM, worker exit, timeout, malformed response, or non-2xx response occurs;
  or
- two consecutive concurrency increases each improve throughput by less than
  5 percent while increasing P95 latency by more than 50 percent relative to
  the preceding point.

These numbers only bound the adaptive scan. They are not feature acceptance or
performance-regression thresholds.

### Samples Per Point

For concurrency `C`:

- warmup request count: `max(8, 2 * C)`;
- each formal request count: `max(32, 8 * C)`;
- formal repetitions: three.

Warmup results are archived but excluded from the formal comparison. All three
formal raw results are retained; no outlier is deleted.

AISBench stable-stage throughput is accepted as a valid raw measurement only
when the maximum request E2EL is less than one third of the reported stable
Benchmark Duration. If not, archive the insufficient run, increase
`RequestCount`, and rerun it under a new attempt identifier.

Before each warmup or formal repetition, reset Mooncake to zero keys and zero
allocated bytes, confirm the server clients can reconnect, and verify the
requested engine health. If a Master restart does not preserve client recovery,
restart the engines under the same configuration before continuing and record
that lifecycle explicitly.

## Balanced Execution Order

Run one topology at a time and group work by input length. Within a topology,
use this variant rotation:

```text
4K:  BULK -> LAYERWISE -> REUSE3
16K: LAYERWISE -> REUSE3 -> BULK
32K: REUSE3 -> BULK -> LAYERWISE
```

Use the reverse rotation direction for the production topology. A variant is
started once for an input-length block, passes identity/correctness checks, and
then runs all applicable output and concurrency points for that block. This
balances temporal drift without restarting engines for every A/B/C point.

The one-token `BULK` and `LAYERWISE` results serve both Issue #1 comparisons.
They are not rerun for the `REUSE3` comparison.

## Preflight And Correctness Gates

Before a formal matrix starts, capture and verify:

- kube context, namespace, Ready nodes, physical Ascend910 capacity, and
  non-terminal allocations;
- control and nested-repository branch, commit, remote, lock, and dirty state;
- handoff generation, contents, and checksum;
- server and client image/platform/digest identity;
- patched import path and SHA256;
- model files and tokenizer identity;
- exact runtime arguments and environment;
- empty Mooncake state;
- expected Pod placement and physical NPU mapping;
- AISBench and client dependency identity.

Each server variant then runs a low-concurrency correctness canary. It must
prove valid OpenAI-compatible streaming responses, requested token lengths,
healthy engine processes, and the intended transfer mode before performance
traffic begins.

The runtime identity must additionally prove:

- `BULK` uses whole-key transfer and does not emit ranged layerwise events;
- `LAYERWISE` uses ranged layerwise transfer and does not merge compute-side
  shared slots;
- `REUSE3` Prefill maps 27 physical layers to five physical slots, applies the
  expected logical KV-memory factor, and uses ranged transfer;
- `REUSE3` Decode remains a no-reuse pure consumer;
- no non-experimental flag differs across A/B/C.

If any identity or correctness gate fails, do not collect or publish a formal
performance comparison for that variant.

## Metrics

AISBench raw results provide these primary metrics:

| Output profile | Metrics |
| --- | --- |
| one token | Input Token Throughput, Request Throughput, TTFT, E2EL, achieved concurrency |
| 128 tokens | all one-token metrics plus Output Token Throughput, TPOT, and ITL |

For every warmup and formal repetition, also collect:

- complete Prefill and Decode logs;
- vLLM `/metrics` before, during, and after the run;
- per-Prefill-DP-rank request count, input tokens, real context iterations,
  queue state, and busy/idle time;
- per-physical-card utilization, HBM, power, and temperature time series;
- Mooncake key, byte, client, ranged-event, whole-key-event, and error state;
- client Pod CPU, memory, network, and open connections;
- engine process status and Pod state.

For DP2, report per-rank and aggregate data. A request or token imbalance above
10 percent is annotated as a diagnostic; the raw run is retained rather than
silently discarded.

## Result Interpretation

The final report shows all three formal rows per point and direct raw ratios:

- `LAYERWISE / BULK` for output 1 and 128;
- `REUSE3 / LAYERWISE` for output 1;
- `REUSE3 / BULK` for output 1.

It does not assign performance PASS/FAIL, remove outliers, calculate p-values,
claim statistical significance, or convert the first run into a nightly gate.
Capacity failures and adaptive stopping points are reported as observed
boundaries, not generalized regressions.

Functional invalidity is different: a wrong identity, incorrect transfer path,
bad response, server defect, client saturation, or incomplete evidence makes
the affected measurement invalid and prevents a performance claim.

## Components

Implement preparation and execution as bounded feature-local components:

1. Handoff listener/checker: parse and revalidate readiness and immutable
   evidence.
2. Client bootstrap: create the CPU-only Pod and lock its toolchain.
3. Fixture generator: create exact-token unique datasets and checksums.
4. Matrix generator: expand variants, topologies, inputs, outputs, concurrency,
   sample sizes, and rotation order.
5. Runtime profiles: render A/B/C and DP1/DP2 configurations without hidden
   differences.
6. Runner: manage preflight, Master reset, engine lifecycle, AISBench, metrics,
   failure capture, and restoration.
7. Report checker: reject missing runs, identity drift, incomplete raw results,
   invalid checksums, and wrong configuration.
8. Reporter: render raw per-repetition comparisons and diagnostic annotations.

Expose two top-level phases:

```text
prepare
```

This phase is allowed before handoff readiness and cannot reach server/NPU or
performance endpoints.

```text
run
```

This phase always begins with the full handoff and identity gate before it can
perform any mutating or traffic-generating action.

## Error Handling And Recovery

- A failure always writes its command, exit status, logs, partial metrics,
  current Pods/processes, Mooncake state, and failure classification.
- Never rerun in the same artifact directory. A retry receives a new attempt
  ID and links to the failed attempt.
- Harness, manifest, parser, or checker defects may be repaired and the
  invalidated scope rerun.
- A confirmed production-source defect stops the formal performance run and is
  returned to functional implementation; the performance workflow does not
  patch production source opportunistically.
- Never weaken identity, correctness, or checksum checks to retain a result.
- Every cleanup command explicitly names namespace `liangjiahao` and the exact
  resource. Never delete the namespace.
- On completion or failure, stop vLLM, return Mooncake to the required empty
  state, and restore the exact pre-run Deployments and ConfigMaps captured by
  preflight.

## Evidence Contract

At run start, generate `run_id` as a UTC timestamp in
`YYYYMMDDTHHMMSSZ` form. Each performance run then uses:

```text
features/kv-pool-layerwise-reuse/evidence/layerwise-performance-${run_id}/
```

The directory contains:

- source, remote, workspace-lock, handoff, and dirty-state identity;
- base, derived-server, and client image inspection;
- patched files and SHA256 identity;
- cluster, node, Pod, process, physical-NPU, model, and tokenizer identity;
- exact manifests, rendered runtime configurations, commands, and environment;
- uv/AISBench bootstrap lock and installation provenance;
- fixture text/token IDs/metadata and checksums;
- run matrix, rotation order, attempt graph, and step status;
- raw AISBench JSONL/CSV/HTML and stdout/stderr;
- complete server/client logs, vLLM metrics, NPU samples, and Mooncake metrics;
- per-run validity and adaptive-stop decisions;
- failure artifacts and final restored state;
- a root `SHA256SUMS` covering every published artifact.

A fail-closed checker verifies the report against this artifact tree and
replays `SHA256SUMS` before publication.

## Test Strategy

CPU-only tests cover:

- every handoff not-ready and identity/checksum failure mode;
- ready-generation changes and stale-read rejection;
- A/B/C unique-difference validation;
- DP1/DP2 resource and argument rendering;
- matrix size, applicability, and balanced ordering;
- exact-token, first-block-unique fixture generation;
- warmup/formal request-count formulas;
- adaptive stop and stable-duration decisions;
- AISBench raw-result parsing without outlier deletion;
- per-rank imbalance annotation;
- evidence completeness, checksum replay, and failure preservation;
- separation between `prepare` and the gated `run` entrypoint.

Run these CPU/mock tests in the dedicated CPU-only
`liangjiahao/vllm-ascend-ut` Pod using tar synchronization, explicit test
targets, disabled bytecode, and disabled pytest cache. The client Pod may run an
AISBench install/import/CLI smoke, but it is not a substitute for the UT Pod.

Before the full matrix, run focused client-to-proxy connectivity and one
correctness canary per variant/topology. No reduced smoke result is reported as
throughput evidence.

## Delivery And Git Boundaries

All control tooling, snapshots, design, plan, report, and imported evidence live
under `features/kv-pool-layerwise-reuse/` on the feature branch. Do not commit
`repos/*` contents to the control repo. Stage only explicitly approved paths and
preserve unrelated `deployment_yaml/`, `dockerfile.vllm23`, other-session
changes, and research snapshots.

The preparation commit does not modify the functional handoff owned by session
`019fdf27-db45-7e83-b02d-a6a26ff55d9d`. The performance workflow consumes its
final committed generation after readiness.

## Acceptance Criteria For The Performance Workflow

The workflow is complete when:

1. The approved preparation can finish without a ready functional handoff and
   cannot send performance traffic.
2. The listener remains fail-closed until every handoff condition passes.
3. No full server image rebuild occurs; the exact handed-off derived image or
   audited Python patch plus `nerdctl commit` path is used.
4. A/B/C differ only by the frozen experimental variables.
5. DP1 and DP2 execute the approved exact-token, output, concurrency, sample,
   and rotation matrix.
6. All formal raw results, diagnostics, failures, and stopping boundaries are
   retained without statistical or pass/fail embellishment.
7. Source, image, runtime, hardware, client, fixture, and evidence identities
   are complete and checksummed.
8. The fail-closed report checker passes and the pre-run Kubernetes state is
   restored.
