# Mooncake Layerwise Functional And Performance Execution Plan

## Status

Approved in chat on 2026-08-08 and written for final user review. Execution
must not begin until the user approves this written version.

This document is the authoritative sequence and gate plan for completing the
Mooncake `layerwise_num_shared_buffers=3` functional work and then running the
approved DP1/DP2 performance characterization in the same session.

The checkbox state in
`implementation-plans/2026-08-08-layerwise-performance-validation.md` is a
historical implementation checklist, not the live progress board. Runtime
authority comes from the committed functional handoff, listener observations,
immutable evidence directories, and the checks described here.

## Related Contracts

- Performance design:
  `features/kv-pool-layerwise-reuse/2026-08-08-layerwise-performance-validation-design.md`
- Detailed performance implementation plan:
  `features/kv-pool-layerwise-reuse/implementation-plans/2026-08-08-layerwise-performance-validation.md`
- Performance runbook:
  `features/kv-pool-layerwise-reuse/deployment/performance/README.md`
- Functional-to-performance handoff:
  `features/kv-pool-layerwise-reuse/performance-validation-handoff.md`
- Reusable preparation evidence:
  `features/kv-pool-layerwise-reuse/evidence/performance-preparation-20260808T170000Z/`
- Historical listener observations:
  `/tmp/layerwise-performance-handoff-wait-resumed/observations.jsonl`

The performance design remains unchanged. This plan changes ownership and
sequencing: one session completes functional validation, publishes the ready
handoff, and then executes DP1 and DP2 serially.

## Execution Strategy

Use a single-owner serial pipeline:

```text
exclusive runtime audit
  -> clean rerun of the existing candidate
  -> conditional production-source fix
  -> complete CPU/mock gates
  -> immutable source/image freeze
  -> new formal functional NPU run
  -> generation-1 ready handoff
  -> performance preflight
  -> DP1 + checker
  -> automatic DP2 + checker
  -> restoration, report, evidence, and publication
```

Do not overlap functional and performance server activity. The retained
CPU-only AISBench Pod may remain running on `m1`, but it must not send traffic
until the ready handoff and performance preflight both pass.

## Non-Negotiable Constraints

- Use Kubernetes namespace `liangjiahao` explicitly for every UT, serving,
  client, helper, log, rollout, exec, and cleanup command.
- Do not delete a namespace. Clean up only exact named resources after checking
  context, namespace, and target identity.
- Preserve unrelated work, including `deployment_yaml/`, `dockerfile.vllm23`,
  performance-preparation evidence, and other-session changes.
- Do not change memcache behavior or the public slot-release lifecycle.
- CPU/mock tests cover all configured roles. Real NPU functional validation
  covers `kv_producer` and `kv_both`, plus a no-reuse baseline oracle.
- Do not rebuild the server image with Dockerfile, BuildKit, `nerdctl build`, or
  `docker build`.
- If a source fix is required, patch final Python files into a temporary
  container based on
  `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z`
  and create the reusable image with `nerdctl commit` in containerd namespace
  `k8s.io`.
- Every retry uses a new UTC run or attempt ID and preserves prior evidence.
- Performance results are raw characterization. Performance values have no
  PASS/FAIL threshold; identity, correctness, health, and evidence completeness
  remain fail-closed gates.
- After the DP1 checker passes, proceed to DP2 automatically without another
  human approval. Any identity or correctness failure still stops execution.

## Phase 0: Establish Exclusive Runtime Ownership

1. Re-query the live cluster and host process state. Do not rely on the PIDs or
   Pod names observed while this plan was written.
2. Capture current Prefill, Decode, Mooncake Master, proxy, UT, and AISBench Pod
   identities, exact engine command lines, NPU processes, and Master metrics.
3. Confirm that no other functional or performance runner/listener is mutating
   the server workloads. A passive stopped listener is not an authorization
   source.
4. Stop any residual Prefill and Decode engine through the existing exact
   stop scripts. Wait until `npu-smi` reports no process on every involved
   physical card.
5. Restart only the exact Mooncake Master Deployment in `liangjiahao`, then
   require key count, allocated bytes, and active clients to be `0/0/0`.
6. Recreate the Prefill Pod from its immutable image when necessary to discard
   any Python overlay or `[DEBUG-8f31]` instrumentation left in the container
   writable layer.
7. Preserve the CPU-only AISBench Pod. It must remain on `m1` with no Ascend910
   or vNPU resource request.

Gate P0 passes only when the serving environment is idle, clean, and owned by
this execution.

## Phase 1: Test The Interference Hypothesis First

The existing vLLM-Ascend candidate is commit
`2d179d07c86e5f820fd6591c0c7fdef2b5132c14`. Its earlier NPU runs observed
corrupt output, but at least one run overlapped another runner. Do not infer a
new source fix until the candidate is retested in isolation.

1. Remove all temporary local tracker logging and verify the vLLM-Ascend tree
   equals the committed candidate before the test.
2. Verify the existing candidate image identity and prove the running container
   imports unmodified committed files.
3. Create a fresh functional run ID and use the frozen deterministic request.
4. Run a no-reuse baseline, one `kv_producer` reuse request, and `kv_both` cold
   plus warm requests without any overlapping runner.
5. Compare exact response text, prompt/completion usage, finish reason, request
   identity, range events, physical slots, engine health, and cleanup.

Branch after P1:

- If every correctness gate passes, classify the overlapping historical runs as
  invalid diagnostic evidence. Keep `2d179d07` and its existing derived image as
  the source/image candidate and continue to Phase 3.
- If corruption reproduces in isolation, preserve the failed run and continue
  to Phase 2.

## Phase 2: Conditional Production-Source Repair

This phase runs only when Phase 1 reproduces the defect in isolation.

1. Continue from the established boundary: `MooncakeSessionTracker` retains
   block snapshots and consistent request IDs through decode, so trace the
   downstream path from `request.load_block_keys` through `LayerBlockRange`,
   layer task construction, `LayerBatchBuilder.build_addrs`, and ranged load.
2. Add temporary observation only at the smallest missing boundary. Do not
   leave runtime debug output in the final source.
3. Convert the observed lifecycle into a minimal failing CPU/mock test proving
   that all required committed full blocks and the partial block reach the
   transfer task during shared-buffer decode.
4. Make the smallest production fix that passes the RED test while preserving
   current role restrictions, memcache behavior, and slot-release semantics.
5. Remove every temporary `[DEBUG-8f31]` or equivalent diagnostic statement.

Gate P2 requires a focused green test and a clean production diff with no
unrelated refactor.

## Phase 3: Complete CPU/Mock And Static Validation

Run from the exact final vLLM-Ascend tree through tar synchronization into the
dedicated CPU-only `liangjiahao/vllm-ascend-ut` Pod. Disable Python bytecode and
pytest cache.

Required coverage:

- focused Mooncake shared-buffer and session lifecycle tests;
- the complete AscendStore suite and MLA regression coverage;
- layerwise/model-runner tests;
- deployment, validation, and performance mock tests;
- all role configurations: `kv_producer`, `kv_both`, save-capable consumer, and
  pure-consumer startup rejection for non-null shared buffers;
- performance harness tests, including the current 44-test suite;
- Ruff check and format check, Python compilation, shell syntax, and
  `git diff --check`.

Any failed required test blocks source freeze and NPU validation.

## Phase 4: Freeze Source And Reusable Image

1. Commit and push the final vLLM-Ascend source on
   `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723`.
2. Verify local/remote equality and record branch, commit, remotes, and dirty
   state.
3. Refresh `workspace.lock.json`, `repo-state.md`, and validation identity only
   through explicitly staged functional-owned paths.
4. If Phase 1 passed without a source change, reuse the already verified
   candidate image after replaying its platform, manifest, config, labels, and
   file checksums.
5. If Phase 2 changed source, start from the named `45b2e785` base image, patch
   every cumulative final production Python file, and use `nerdctl commit` to
   create a new immutable tag. Do not patch only the last delta when earlier
   feature files are also absent from the base.
6. Record the base and derived references, platform, manifest/config digests,
   source labels, every patched path and SHA256, temporary container lifecycle,
   and parent filesystem-layer identity.

Gate P4 requires a native `linux/arm64` image whose imported production files
match the final checkout.

## Phase 5: New Formal Functional Acceptance

Create a new evidence root. Do not reuse `083140Z`, `093733Z`, or `093917Z`.

1. Re-run the complete CPU/mock and image identity gates in the formal evidence
   workflow, or import them only through checksummed immutable artifacts when
   the checker explicitly supports that provenance.
2. Run the no-reuse deterministic baseline.
3. Run real-NPU `kv_producer` with
   `backend=mooncake`, `use_layerwise=true`, and
   `layerwise_num_shared_buffers=3`.
4. Run real-NPU `kv_both` cold and warm requests with the same reuse settings.
5. Require exact response equality with the baseline, expected usage and finish
   reason, correct ranged transfers, the 27-logical-layer physical-slot proof,
   expected KV-memory factor, and no save-gate timeout or corruption.
6. Stop engines, wait for all NPU processes to exit, restart the Master when the
   workflow requires it, and prove final Mooncake metrics `0/0/0`.
7. Generate the functional report, validation config snapshot, command ledger,
   failure classification if any, and root `SHA256SUMS`; replay every checksum.

Any wrong output is a production correctness failure and blocks performance.

## Phase 6: Publish A Valid Generation-1 Handoff

Before changing readiness, resolve the control-repository commit self-reference:

1. Add a focused performance-handoff test that accepts a clean handoff
   transition commit whose direct parent is the recorded functional control
   commit.
2. Keep exact equality for vLLM, vLLM-Ascend, and Mooncake identities. Do not
   weaken arbitrary source-drift checks.
3. Run the focused handoff tests and the complete performance harness suite
   after implementing the parent-commit rule.
4. Do not create another control commit between the ready handoff and the end of
   DP2; DP1 and DP2 must run from the same accepted handoff transition checkout.

Populate the handoff with:

- the four source identities and remote evidence;
- final image and patched-file identities;
- every required functional gate as `PASS` with immutable evidence links;
- functional evidence root and checksum digest;
- the exact model, namespace, topology, and physical-hardware bounds;
- explicit performance authorization for `BULK(use_layerwise=false)`,
  `LAYERWISE`, and Prefill `REUSE3`;
- explicit authorization for the no-reuse pure-consumer Decode companion,
  without claiming pure-consumer compute-side reuse.

Replace every placeholder, set `generation: 1`, then set
`placeholders_remaining: false`, `ready: true`, and
`status: READY_FOR_PERFORMANCE_VALIDATION` last. Commit and push the transition,
then re-run the listener and require an accepted observation for the committed
generation.

## Phase 7: Performance Preflight

1. Replay
   `evidence/performance-preparation-20260808T170000Z/SHA256SUMS` and verify the
   preparation evidence was produced without server authorization or traffic.
2. Recheck the retained AISBench Pod identity, `m1` placement, CPU/memory limits,
   absence of NPU requests, exact client rootfs, Python 3.12.13, uv 0.12.3,
   AISBench 3.1.0/`3fd27b4a`, installed packages, tokenizer, and fixtures.
3. If the Pod or its `emptyDir` contents drifted, run `prepare` under a new ID
   and use only the new checksummed preparation evidence. Otherwise reuse the
   existing prepared state.
4. Re-run the performance harness CPU tests.
5. Invoke the performance `run` entrypoint, which must independently revalidate
   the ready handoff, source, image, patch, hardware, role scope, and functional
   checksums before any server mutation or request.
6. Capture the exact pre-run Deployments, ConfigMaps, Pods, physical NPU
   allocation, processes, and Mooncake state for restoration.

Gate P7 requires all preflight and per-variant correctness canaries to pass.

## Phase 8: Execute And Check DP1

Use one new performance run root and the mechanism topology. Execute the
approved 4K/16K/32K rotations, applicable output lengths, concurrency scan,
warmups, three formal repetitions, Master resets, telemetry, stable-duration
checks, and adaptive stopping contract.

After DP1 completes:

```bash
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
python3 -m performance.report check --root "$RUN_ROOT" --scope dp1
```

Identity, correctness, health, client-capacity, or evidence invalidity stops the
run. A valid observed saturation or capacity boundary does not block DP2.

## Phase 9: Automatically Execute And Check DP2

When the DP1 checker passes, continue without another human approval:

1. Revalidate that handoff generation, source, image, model, tokenizer, client,
   and pre-run contract have not changed.
2. Resume in the same run root with production topology DP2.
3. Execute the reverse variant rotation and aggregate concurrency
   `2/4/8/16/32/64` with all approved samples and telemetry.
4. Capture per-Prefill-rank and aggregate request, token, context-iteration,
   busy/idle, NPU, and imbalance evidence.
5. Run the full evidence checker and replay the root checksum manifest.

No commit, source edit, image replacement, or handoff transition is allowed
between DP1 and DP2.

## Phase 10: Restore, Report, Publish, And Audit

1. Stop every engine started by the run and prove NPU release.
2. Return Mooncake to the required empty state.
3. Restore the exact pre-run Deployments and ConfigMaps and record the resulting
   object identities. Preserve the long-running CPU-only AISBench Pod unless
   the runbook explicitly requires otherwise.
4. Render all three formal raw rows per point, direct A/B/C ratios, DP
   annotations, invalid attempts, capacity boundaries, and adaptive-stop
   decisions. Do not remove outliers or claim statistical significance.
5. Import the exact run root under
   `features/kv-pool-layerwise-reuse/evidence/layerwise-performance-$RUN_ID/`
   without rewriting raw artifacts. Add import provenance and a repository root
   `SHA256SUMS`.
6. Run the complete performance UT/static/report/checksum/identity/namespace
   audit against the repository evidence path.
7. Commit only performance-owned report, evidence, index, and tooling paths.
   Reconcile state files only when endpoint identity requires it and never
   discard unrelated dirty work.
8. Push normally, verify remote equality, and map every functional and
   performance requirement to immutable evidence.

The final deliverables are:

- a ready functional handoff containing the usable image identity;
- a complete checksummed functional evidence root;
- a complete checksummed DP1/DP2 performance evidence root;
- the raw performance characterization report;
- restoration and remote-equality evidence.

## Failure And Retry Policy

- Confirmed functional production-source defect: preserve evidence, return to
  Phase 2, fix test-first, create a new source/image identity, and rerun all
  invalidated functional gates.
- Performance harness, manifest, parser, checker, or documentation defect:
  repair only the owned tooling, run its CPU tests, create a new attempt ID, and
  rerun the invalidated performance scope.
- External resource or infrastructure failure: capture processes, Pods, logs,
  metrics, and cleanup state; restore the cluster; retry only under a new
  attempt after capacity and health revalidation.
- Performance slowdown or saturation with correct identity and responses:
  retain and report it as characterization; do not patch production source to
  improve a formal measurement.
- Never weaken response, identity, health, role, or checksum gates to keep a
  result.

## Completion Criteria

Work is complete only when all of the following are true:

1. The interference hypothesis has been tested in a clean, exclusive run.
2. Final source and image identities are committed, pushed, and reproducible.
3. CPU/mock coverage and `kv_producer`/`kv_both` NPU correctness all pass.
4. The generation-1 handoff is accepted and includes the exact reusable image.
5. The prepared client identity and exact tokenizer fixtures are verified.
6. DP1 and DP2 finish or terminate only at contract-authorized boundaries.
7. The fail-closed checker and every checksum replay pass.
8. The cluster is restored and Mooncake/NPU resources are clean.
9. Reports and immutable evidence are committed and remote equality is proven.
