# Layerwise KVPool Reusable Full Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-run the complete layerwise KVPool validation after source, dependency, image, model, or validation-tooling changes without carrying version assumptions from an earlier run.

**Architecture:** This document is the stable validation contract. Exact source commits, compatibility versions, images, model identity, runtime dimensions, and run IDs belong to a new dated run record and `deployment/validation-identity.json`; manifests, runners, checkers, reports, and evidence must agree with that frozen identity before runtime testing begins.

**Tech Stack:** Bash, Python, pytest, Kubernetes, nerdctl/BuildKit, Ascend NPU, vLLM, vLLM-Ascend, Mooncake, JSON/JSONL evidence, Markdown reports.

## Global Constraints

- Preserve [the interrupted 2026-07-30 run tracker](2026-07-30-full-validation-rerun.md) as historical execution state. Do not reuse its SHA, tag, date, cluster snapshot, or result as a future run input.
- All UT, serving, proxy, Master, and stress workloads use explicit namespace `liangjiahao`.
- Only shared `buildkitd` uses namespace `default`; set `BUILDKIT_HOST=kube-pod://buildkitd?namespace=default` explicitly.
- Never use `ai-inference` as an executable namespace and never rely on the kube context's default namespace.
- A validation claim applies only to the exact per-run identity frozen before the image build. Do not rebase, fetch a moving ref into the claim, or substitute source after a gate has passed.
- Rebuild the complete image when source, native code, dependency metadata, Mooncake, vLLM, or vLLM-Ascend identity changes. Do not combine new Python source with old native/dependency layers through `kubectl cp`.
- Keep `repos/Mooncake` read-only unless the user explicitly authorizes source changes.
- Preserve unrelated worktree files. Do not stash, reset, use `git add -A`, or commit `repos/*` into the control repo.
- CPU/mock unit tests run in the dedicated long-running `liangjiahao/vllm-ascend-ut` Pod with no NPU, device, driver, model cache, or `hostPath` access.
- Do not modify production source to make a validation failure pass. A production-code failure terminates the run after evidence and failure reports are captured.
- Do not delete a namespace. Finalization stops vLLM child processes and records retained resources; it does not restore the pre-run workload unless the user explicitly requests restoration.
- Historical reports and evidence are immutable. Every attempt uses a new UTC run ID and a new evidence directory.

---

## Stable Files And Responsibilities

| File or directory | Stable responsibility | Per-run mutation |
| --- | --- | --- |
| `implementation-plans/full-validation-guide.md` | Version-independent gates and workflow | Change only when the validation contract changes |
| `implementation-plans/${RUN_DATE}-full-validation-rerun.md` | One run's frozen inputs, tracker, attempts, and final disposition | Create for every run; never reuse a prior tracker |
| `deployment/validation-identity.json` | Machine-readable current validation identity | Update to the exact selected run inputs before tooling tests |
| `Dockerfile.a2` | Remote-clone build and exact source pins | Keep pins consistent with identity JSON |
| `deployment/*.yaml`, `deployment/stress/*.yaml` | Current executable workload definitions | Keep image, compatibility version, namespace, topology, and model contract consistent |
| `deployment/run-*.sh`, drivers, and checkers | Identity gates, execution, evidence, and hard oracles | Update when API/runtime/report contracts change |
| `deployment/tests/` | Regression tests for validation tooling | Add coverage before fixing a tooling defect |
| `evidence/` | Immutable raw output, transcript, structured summaries, and checksums | New directory for every attempt/family |
| Dated validation reports | Self-contained conclusion and reproduction record | New files for every completed or terminated run |

`RUN_DATE` and `UMBRELLA_RUN_ID` are resolved at execution time:

```bash
RUN_DATE=$(date -u +%F)
UMBRELLA_RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
TRACKING_FILE="features/kv-pool-layerwise-reuse/implementation-plans/${RUN_DATE}-full-validation-rerun.md"
test ! -e "${TRACKING_FILE}"
```

If a run already exists for that UTC date, choose a filename containing the umbrella run ID instead of overwriting it.

## Per-Run Identity Contract

Before editing tooling or starting a build, resolve every field below. Explicit values supplied by the user take precedence. Any field the user did not specify must be derived from the current clean checkout, lock, model, or live runtime and then frozen; it must never be copied implicitly from the previous run.

| Field | Authoritative source for this run | Required form |
| --- | --- | --- |
| Control branch and tooling base | Current control checkout | Branch name plus full commit SHA |
| vLLM | User-specified ref or `repos/vllm` | Full commit SHA and remote containing it |
| vLLM-Ascend | User-specified ref or `repos/vllm-ascend` | Full commit SHA, branch, and remote containing it |
| Mooncake | User-specified ref or `repos/Mooncake` | Full commit SHA and remote containing it |
| Compatibility version | User specification or vLLM-Ascend release contract | Exact `VLLM_VERSION` value |
| Base image | User specification or approved platform baseline | Registry-qualified immutable tag or digest |
| Target image | Derived after all identities are known | Registry-qualified unique tag; record digest/config ID after build |
| Platform | Builder and node inspection | Exact OS/architecture, normally `linux/arm64` for this workflow |
| Session/range APIs | Selected Mooncake client contract | Exact symbol list used by runtime checker and fakes |
| Model | User specification or current fixture | Path, config checksum or revision, tokenizer identity, max positions |
| Runtime dimensions | Model config and scenario definition | Layer count, block size, prompt/token targets, expected key arithmetic |
| Lease contract | Master configuration and client error contract | TTL, wait margin, symbolic and numeric expiry result |
| Kubernetes target | Live kube context and scheduling decision | Context, namespace, node, resource name, requested topology |

Load the selected machine-readable identity without embedding its values in this guide:

```bash
IDENTITY_FILE=features/kv-pool-layerwise-reuse/deployment/validation-identity.json
jq -e '
  .schema_version >= 1 and
  (.base_image | type == "string" and length > 0) and
  (.image | type == "string" and length > 0) and
  (.vllm_version | type == "string" and length > 0) and
  (.commits.vllm | test("^[0-9a-f]{40}$")) and
  (.commits.vllm_ascend | test("^[0-9a-f]{40}$")) and
  (.commits.mooncake | test("^[0-9a-f]{40}$")) and
  (.session_apis | type == "array" and length > 0)
' "${IDENTITY_FILE}"
VLLM_COMMIT=$(jq -er '.commits.vllm' "${IDENTITY_FILE}")
VLLM_ASCEND_COMMIT=$(jq -er '.commits.vllm_ascend' "${IDENTITY_FILE}")
MOONCAKE_COMMIT=$(jq -er '.commits.mooncake' "${IDENTITY_FILE}")
TARGET_IMAGE=$(jq -er '.image' "${IDENTITY_FILE}")
BASE_IMAGE=$(jq -er '.base_image' "${IDENTITY_FILE}")
VLLM_VERSION=$(jq -er '.vllm_version' "${IDENTITY_FILE}")
```

The dated tracker must record whether each value was user-specified or derived. A user-specified version does not remove the requirement to resolve it to a full fetchable SHA.

## Version-Independent Hard Gates

| Area | Hard gate |
| --- | --- |
| Identity | Lock, clean source HEADs, Dockerfile pins, image labels, editable Git HEADs, manifests, runners, and checker expectations agree exactly |
| Image | Full build from selected base; target platform, source labels, fail-closed dependency health, native extension, imports, and selected Mooncake symbols pass |
| CPU/mock | Dedicated Pod contract passes; complete selected collection passes with current count; Ruff/compilation/diff checks pass |
| Pool isolation | Engines are stopped before Master reset; key count, allocated bytes, and active clients prove empty before each independent scenario |
| Direct ranged API | Multi-key/multi-layer transfer, non-zero offsets, per-key result bytes, final byte comparison, negative session/range cases, and cleanup pass |
| Lease | Slow put survives a wait longer than read TTL; stale get returns the selected expiry code; a fresh get recovers exact bytes; final pool is empty |
| Runtime audit | Prefill save/load and Decode load cover every physical layer `0..NUM_LAYERS-1`; result bytes equal fragment sums; commits follow final-layer saves; whole-key events are zero |
| 1P1D smoke | HTTP/choices, marker ownership, foreign-marker exclusion, returned token boundary/count, usage, finish reason, proxy/direct routing, and per-request hit correlation pass |
| Stress | Required DP/TP ranks, chunk bounds, all-layer ranged events, commit ordering, marker/token/metadata gates, expected key arithmetic, and whole-key exclusion pass for S1-S3 |
| Evidence | Every executed command is in `steps.jsonl` and transcript; local report links are tracked; `SHA256SUMS` and offline replay pass |

Full continuation equality is diagnostic. It can strengthen a conclusion when true, but it cannot replace marker ownership/isolation, token boundary/count, usage, or finish-reason gates.

Numeric expectations that depend on a model or tokenizer must be derived during the run and written to evidence. Examples include `NUM_LAYERS`, prompt tokens, hit blocks, hit tokens, fragment bytes, and Master key counts. Checkers must compare against those frozen derived values rather than a number copied from an older report.

## Task 1: Instantiate And Freeze A Run

**Files:**

- Create: dated tracker under `features/kv-pool-layerwise-reuse/implementation-plans/`
- Modify when selected values differ: `deployment/validation-identity.json`, `Dockerfile.a2`, manifests, runners, checkers, current runbooks, and identity tests
- Preserve: all dated reports, existing evidence, `deployment_yaml/`, and `dockerfile.vllm23`

**Interfaces:**

- Consumes: explicit user version selections, current nested repositories, `workspace.lock.json`, current cluster state
- Produces: one immutable run identity and one final tooling commit used by every green family

- [ ] Record control and nested repository branch, HEAD, tree status, and remotes before edits.

```bash
git status --short --branch
git remote -v
for repo in repos/vllm repos/vllm-ascend repos/Mooncake; do
  git -C "${repo}" status --short --branch
  git -C "${repo}" rev-parse HEAD
  git -C "${repo}" remote -v
done
jq . workspace.lock.json
```

- [ ] Resolve user-specified refs to full commits, verify they are fetchable from the recorded remotes, and update checkouts only through a workspace-safe workflow.
- [ ] Fill `validation-identity.json` with the resolved run identity and update every consumer detected by `test_validation_identity.py`.
- [ ] Run the identity consistency test before runtime work. If it fails, treat the mismatch as tooling drift, not as runtime evidence.

```bash
python3 -m unittest discover \
  -s features/kv-pool-layerwise-reuse/deployment/tests \
  -p 'test_validation_identity.py' -v
```

- [ ] Create the dated tracker with gate status, independent family run IDs, timestamps, exit codes, evidence paths, and an attempts/failures ledger.
- [ ] Freeze one final tooling commit before the first formal build. Any later shared manifest, runtime helper, oracle, identity, or checker change invalidates affected green results and requires a new tooling commit plus rerun.

## Task 2: Validate Tooling Before Build

**Files:**

- Test: `deployment/tests/`
- Test: all executable shell/Python files and Kubernetes manifests
- Evidence: `evidence/full-validation-rerun-${UMBRELLA_RUN_ID}/tooling/`

**Interfaces:**

- Consumes: frozen identity and final tooling tree
- Produces: static proof that later runners and reports enforce the selected contract

- [ ] Run report checker, identity, smoke-oracle, driver, and log-checker tests.
- [ ] Run `bash -n`, Python compilation, `git diff --check`, and changed-file Ruff.
- [ ] Run Kubernetes client-side dry-run for every base, stress, and UT manifest with explicit namespace.
- [ ] Render ConfigMap data and compile the actual Python files mounted into Pods.
- [ ] Record every command through `deployment/run-validation-step.sh`; require terminal END/exit records for normal completion, failure, SIGINT, and SIGTERM; checksum the completed tooling evidence.

Expected: all current tests pass without relying on a historical test count, every manifest parses, and all Pod-side scripts compile.

## Task 3: Build And Prove The Exact Image

**Files:**

- Modify before build: `Dockerfile.a2`
- Append after build: image build/identity documentation and the current run's image evidence

**Interfaces:**

- Consumes: exact base image, source SHAs, API symbol list, compatibility version, and unique target image tag
- Produces: one immutable image digest/config ID used by UT and all runtime gates

- [ ] Confirm `default/buildkitd` is Running and the target tag is absent or resolves to the exact intended digest.
- [ ] Build with the repository's remote-clone workflow.

```bash
export BUILDKIT_HOST='kube-pod://buildkitd?namespace=default'
export CONTAINERD_NAMESPACE=k8s.io
nerdctl -n "${CONTAINERD_NAMESPACE}" build \
  --progress=plain \
  -f features/kv-pool-layerwise-reuse/Dockerfile.a2 \
  -t "${TARGET_IMAGE}" \
  features/kv-pool-layerwise-reuse
```

- [ ] Run raw `pip check` and fail on every unexpected issue. If the selected immutable base/plugin contract has known unsatisfiable metadata, the run identity may carry an exact, regression-tested allowlist; record every allowed line as a limitation and reject all other output. Also verify platform, manifest digest, config ID, source labels, editable Git HEADs, dependency versions, native extension, dynamic imports in an NPU Pod, and every API in `.session_apis`. For a Mooncake source build installed directly by CMake, do not require wheel distribution metadata that the install path does not create; prove its exact Git HEAD, installed module path, native symbols, and runtime APIs instead.
- [ ] Fail if a Pod reports the requested tag but its `imageID` does not match the recorded digest.
- [ ] Append the new result; do not overwrite a prior image record.

## Task 4: Run Static And CPU/Mock Gates In The Pinned UT Pod

**Files:**

- Apply: `deployment/60-vllm-ascend-ut-pod.yaml`
- Execute: `deployment/run-vllm-ascend-ut.sh`
- Evidence: image/UT family directory with Pod JSON/YAML, source identity, commands, logs, summaries, and checksums

**Interfaces:**

- Consumes: pinned image and clean vLLM-Ascend checkout
- Produces: CPU/mock correctness evidence without NPU resource use

- [ ] Recreate only `liangjiahao/vllm-ascend-ut` when its image identity differs.
- [ ] Prove the Pod has no `huawei.com/Ascend910`, device/driver mount, `npu-smi`, model cache, or `hostPath`.
- [ ] Tar-sync the current checkout and record commit, branch, and dirty state.
- [ ] Run the complete AscendStore suite, `deployment/tests/`, changed-file Ruff, Python compilation, and `git diff --check` with explicit targets and cache/bytecode disabled.
- [ ] Use the complete current collection as the gate; record the observed count instead of enforcing an old count.
- [ ] Retain the long-running UT Pod.

## Task 5: Establish G0 Base 1P1D And Runtime Identity

**Files:**

- Apply in order: `deployment/00-namespace.yaml`, `10-runtime-config.yaml`, `30-mooncake-master.yaml`, `40-prefill-engine.yaml`, `50-decode-engine.yaml`, `20-proxy-server.yaml`
- Evidence: G0 environment, Pod YAML, node/resource state, model identity, runtime checks, logs, metrics

**Interfaces:**

- Consumes: pinned image, model, selected node, base topology, namespace
- Produces: live Prefill, Decode, Master, and proxy whose identity is suitable for G1, lease, G4, and smoke

- [ ] Re-query live NPU capacity from Ready-node allocatable minus active Pod requests.
- [ ] Apply every object with explicit `-n liangjiahao` and wait for the exact named rollouts/Pods.
- [ ] Verify device injection, `npu-smi`, imageID/digest, editable paths and HEADs, compatibility version, dynamic imports, native libraries, model config, driver mounts, and selected Mooncake APIs.
- [ ] Start each engine with one physical NPU, verify endpoints, then stop child processes before resetting Master.
- [ ] Verify the configured lease TTL from Deployment args and Master startup logs.
- [ ] Capture empty-pool metrics: key count, allocated bytes, and active clients must all be zero.

## Task 6: Run G1 Direct Ranged Contract

**Files:**

- Execute: `deployment/range-api-smoke.py`
- Evidence: driver source/checksum, configuration, API calls/results, bytes/checksums, negative cases, cleanup, metrics

**Interfaces:**

- Consumes: one NPU-capable engine Pod, stopped vLLM processes, empty Master, selected API contract
- Produces: direct proof independent of vLLM orchestration

- [ ] Start a unique multi-key, multi-layer test session using the selected driver dimensions.
- [ ] Require non-zero object offsets, fragment sums equal requested bytes, per-key results equal transferred bytes, and final source/destination bytes match.
- [ ] Run negative cases for no session, overflow, arity mismatch, duplicate start, operations after end, revoke, and cleanup.
- [ ] Stop immediately on an unexpected API shape or result; do not reinterpret a new code without first updating the contract and tests.
- [ ] Force cleanup and prove the pool returns to zero.

## Task 7: Run Lease Expiry Validation

**Files:**

- Execute: `deployment/lease-expiry-test.py`
- Reference contract: `lease-expiry-validation-plan.md`
- Evidence: Master configuration/logs, exact waits, API sequence/results, byte comparison, cleanup, metrics

**Interfaces:**

- Consumes: selected TTL/error contract, stopped engines, empty Master, direct ranged API fixture
- Produces: stale-read-session expiry and fresh-session recovery proof

- [ ] Derive both waits from the live TTL and require each elapsed wait to exceed TTL by the recorded safety margin.
- [ ] Require slow put to succeed across the first wait without opening a read lease before commit.
- [ ] Require the stale get session's next layer read to return the selected exact `LEASE_EXPIRED` result.
- [ ] Open a fresh get session, recover all layer bytes exactly, end it successfully, and clear the key.
- [ ] Require final key count, allocated bytes, and active clients to be zero.

## Task 8: Run G4 Runtime Audit

**Files:**

- Execute: `deployment/check-range-debug-log.py`
- Evidence: exact request, response, bounded Prefill/Decode log windows, checker input/output, model dimensions, metrics

**Interfaces:**

- Consumes: audit-enabled base 1P1D, empty Master, frozen `NUM_LAYERS`
- Produces: fail-closed production-call audit for every physical layer

- [ ] Start audit-enabled 1P1D only after empty-pool proof.
- [ ] Send the recorded request and capture bounded log windows without truncation.
- [ ] Require Prefill save and load plus Decode load to cover exactly `0..NUM_LAYERS-1`.
- [ ] Require every result byte count to equal its fragment-size sum.
- [ ] Require successful commits to follow final-layer saves and require zero whole-key calls.
- [ ] Fail on malformed/missing fields, missing/extra layers, truncated logs, bytes mismatch, or whole-key events.

## Task 9: Run 1P1D Smoke

**Files:**

- Execute: `deployment/run-smoke-test.sh`
- Evidence: fixtures, baselines, warmups, direct/proxy responses, structured summary, correlation checker, logs, metrics

**Interfaces:**

- Consumes: base 1P1D, tokenizer/model fixture, empty Master, smoke hard-oracle contract
- Produces: end-to-end routing, cache ownership/isolation, token/usage, and hit-correlation proof

- [ ] Stop engines, reset Master, prove empty metrics, restart engines, and verify exact runtime identity.
- [ ] Run the wrapper with a new empty host output directory.
- [ ] Derive request count, block layout, expected hit tokens, and expected Master keys from the current fixture/tokenizer and archive those values.
- [ ] Require every baseline, warmup, direct load, and proxy load to return HTTP 200 with complete choices.
- [ ] Require own-marker text/token prefix, no foreign marker, generated token count, prompt/completion usage, finish reason, and request ID correlation.
- [ ] Require the expected per-request hit logs for every role/phase defined by the current fixture.
- [ ] Record full continuation equality and serial replay only as diagnostics.

## Task 10: Run Stress S1-S3

**Files:**

- Apply: `deployment/stress/10-runtime-config.yaml`, `40-prefill-engine.yaml`, `50-decode-engine.yaml`
- Execute: `deployment/run-stress-test.sh`, `stress-test.py`, `check-stress-log.py`
- Evidence: topology, per-scenario fixtures/responses/log windows/checkers/metrics/summaries, reset proof, final retained state

**Interfaces:**

- Consumes: selected image/model, six-card stress topology, scenario definitions, empty-pool reset contract
- Produces: Multi-DP/TP, concurrency, long-context, chunked-prefill, ranged-audit, and isolation evidence

- [ ] Re-query six-card availability and switch to Prefill DP2/TP2 plus Decode DP1/TP2 using `Recreate` Deployments.
- [ ] Prove requested topology from Pod resources, process trees, DP/TP logs, and active device processes.
- [ ] For S1, execute the configured pinned long-context cases across both Prefill DP ranks; enforce chunk bound, all-layer events, commit order, whole-key zero, marker/token/usage gates, and fixture-derived key count.
- [ ] Stop engines, reset Master, prove empty metrics, and restart before S2.
- [ ] For S2, run the configured concurrent medium-context cases; require all cases pass hard oracles and both Prefill DP ranks are active.
- [ ] Stop engines, reset Master, prove empty metrics, and restart before S3.
- [ ] For S3, run the cold long-context probe and concurrent proxy cases; require the configured minimum real context iterations and fixture-derived key count.
- [ ] Record full equality counts as diagnostics and require no whole-key event in every scenario.

## Task 11: Publish Evidence And Self-Contained Reports

**Files:**

- Create dated Smoke, ranged, G4, lease, stress, and umbrella reports
- Update: `evidence/README.md` and feature `README.md`
- Validate: `deployment/check-validation-report.py`

**Interfaces:**

- Consumes: immutable family evidence and evidence commits
- Produces: auditable claims or explicit failure/publication-blocked reports

Resolve report paths from `RUN_DATE` instead of embedding a date in this guide:

```bash
SMOKE_REPORT="features/kv-pool-layerwise-reuse/deployment/validation-${RUN_DATE}.md"
RANGED_REPORT="features/kv-pool-layerwise-reuse/ranged-api-validation-${RUN_DATE}.md"
G4_REPORT="features/kv-pool-layerwise-reuse/ranged-api-g4-validation-${RUN_DATE}.md"
LEASE_REPORT="features/kv-pool-layerwise-reuse/lease-expiry-validation-${RUN_DATE}.md"
STRESS_REPORT="features/kv-pool-layerwise-reuse/multi-dp-tp-stress-validation-${RUN_DATE}.md"
UMBRELLA_REPORT="features/kv-pool-layerwise-reuse/full-validation-rerun-${RUN_DATE}.md"
```

Each family report must include:

1. Status, scope, and explicit correctness boundaries.
2. Control/source/image/model/cluster identity and whether values were specified or derived.
3. Expected, actual, exit code, result, and tracked evidence for every gate.
4. `Changes From Original Validation`, including `Unchanged` rows for reviewed areas with no change.
5. Original/current script revisions, SHA256 checksums, and relevant diff or commit.
6. Complete live reproduction commands actually executed, with inputs, expected output, state transitions, and final state.
7. Offline checksum, `jq`, checker replay, Git tracking, and link verification commands.
8. Every failed or superseded attempt, classification, invalidation scope, fix commit, and rerun outcome.
9. Limitations, residual risk, and final Kubernetes/NPU state.

Reports must not contain invented commands, absolute evidence links, credentials, unexplained variables, placeholders, or links to untracked files. Run the report checker against every family report before publication.

## Task 12: Finalize Without Hiding State

- [ ] Stop all vLLM child processes started by this run, including failure paths.
- [ ] Capture final engine/Master/proxy/UT Pod YAML, process state, logs, metrics, image IDs, and active NPU requests.
- [ ] Retain the final UT, Master, proxy, and stress Pods unless the user explicitly requests scoped cleanup.
- [ ] Never delete `liangjiahao`; keep `default/buildkitd` operations explicit.
- [ ] Check checksums, credential scan, report checker, links, Git tracking, and offline replay.
- [ ] Commit and push evidence before reports so report links can name an evidence commit. If publication fails, keep local results and mark `publication-blocked` without rerunning a passing validation.

## Failure Classification And Invalidation

| Classification | Action | May modify `repos/*`? | Rerun scope |
| --- | --- | --- | --- |
| Validation tooling defect | Preserve failed attempt, add regression test, make the smallest control-repo fix, re-run static gates | No | Every family affected by the changed helper/manifest/oracle/checker |
| Production/code/ABI/runtime defect | Capture minimum reproduction, call chain, source locations, logs, metrics, and failed report; terminate | No | No automatic rerun; source fix is a separate user-authorized task |
| Transient infrastructure | Preserve attempt and safely retry at most three times | No | Failed family only if tooling and runtime identity are unchanged |
| Persistent infrastructure | Publish infrastructure failure after repeated identical failure | No | None until external state changes |
| Git/network/credential publication failure | Keep local checksummed results and mark `publication-blocked` | No | Do not rerun validation |

Shared manifest, runtime helper, identity, oracle, or checker changes invalidate all dependent results. A report-only correction does not invalidate runtime evidence if checksums and claims are unchanged. An image tag change always requires image identity re-verification; a source or dependency change requires a full rebuild and all runtime families to rerun.

## Completion Checklist

- [ ] A new dated tracker records all specified and derived inputs.
- [ ] One final tooling commit produced every green runtime family.
- [ ] The image digest/config ID and all source identities are exact and consistent.
- [ ] Static, CPU/mock, G0, direct ranged, lease, G4, smoke, and S1-S3 gates have terminal states.
- [ ] Every numeric model/runtime expectation is derived and archived for this run.
- [ ] Every family has complete tracked evidence, checksums, transcript, structured summary, and self-contained report.
- [ ] Failure attempts and invalidation decisions are preserved.
- [ ] Offline replay and report checker pass.
- [ ] vLLM child processes are stopped and retained Kubernetes/NPU state is recorded.
- [ ] The umbrella report makes no claim beyond the frozen per-run identity and completed gates.
