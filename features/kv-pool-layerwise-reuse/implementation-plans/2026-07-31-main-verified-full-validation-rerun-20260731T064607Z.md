# Main-Verified Mooncake Full Validation Rerun Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `writing-plans` to maintain this plan before changing its scope. Execute inline and update each checkbox immediately after its command reaches a terminal state.

**Goal:** Correct the validation-only vLLM compatibility-lane mismatch, rebuild an exact ARM64 image for the completed 11/11 Mooncake integration, and execute the complete layerwise KVPool validation contract without modifying frozen production source.

**Architecture:** The three repositories under `repos/` are frozen inputs. The control repo owns validation identity, manifests, runners, regression tests, evidence, and reports. The selected vLLM input is the target branch's verified-main anchor, so workloads must use the installed development version naturally and must not force the `v0.25.1` release compatibility branch.

**Tech Stack:** Git, Bash, Python 3.12, pytest, Ruff 0.14.0, Kubernetes, BuildKit, nerdctl/containerd `k8s.io`, vLLM, vLLM-Ascend, Mooncake, Ascend 910B.

## Global Constraints

- Workspace root: `/root/ljh/vllm-workspace`.
- Control branch: `kv-pool-layerwise-reuse`.
- Frozen source branch: `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723`.
- Frozen source HEAD: `14beaf161cca6f1e044e20529ca96c6554dbbe50`.
- Frozen source merge base: `a46a1dabbc260e8695002969f29528eb555eb583`.
- The source range must remain exactly 11 commits with no merge commit and the original Mooncake subject order.
- Do not modify any file under `repos/*` during this rerun.
- A validation tooling, checker, manifest, runner, or execution-step defect may be repaired in the control repo with focused regression coverage; rerun every invalidated family.
- A production source, ABI, or runtime defect terminates the run after evidence capture and cleanup. Do not repair production source inside this run.
- Preserve `deployment_yaml/` and `dockerfile.vllm23`; if `features/kv-pool-layerwise-reuse/.full-validation-rerun-2026-07-30.md.swp` reappears, treat it as user-owned and never stage it.
- Preserve the complete failed run `20260730T130225Z` and its checksummed evidence. Do not rewrite or reuse its evidence directories.
- Every test or serving workload must use namespace `liangjiahao`, and every `kubectl` command must include `-n liangjiahao` explicitly.
- The only namespace exception is `default/buildkitd`; every builder command must include `-n default`, and `BUILDKIT_HOST` must be `kube-pod://buildkitd?namespace=default`.
- CPU/mock tests use only `liangjiahao/vllm-ascend-ut`, with no NPU resource, device/driver mount, model cache, or `hostPath`.
- Sync source or control files to the UT Pod only with tar plus `kubectl exec`; do not use `hostPath` or `kubectl cp`.
- Set `PYTHONDONTWRITEBYTECODE=1` and disable pytest cache for every Python test command.
- Retain long-running UT, Master, proxy, Prefill, and Decode Pods unless scoped recreation is required by image identity.
- Use the existing remote-clone image workflow in `Dockerfile.a2`; do not replace it with bundles, named contexts, or tarred source images.
- No force push is permitted. Check the live remote checkpoint before every normal push.

---

## Resume Protocol After Context Compaction

Run these reads before any mutation:

```bash
cd /root/ljh/vllm-workspace
sed -n '1,260p' AGENTS.md
sed -n '1,360p' features/kv-pool-layerwise-reuse/implementation-plans/2026-07-31-main-verified-full-validation-rerun-20260731T064607Z.md
sed -n '1,460p' features/kv-pool-layerwise-reuse/implementation-plans/full-validation-guide.md
git status --short --branch
git -C repos/vllm-ascend status --short --branch
```

Then verify the frozen source before continuing:

```bash
test "$(git -C repos/vllm-ascend rev-parse HEAD)" = 14beaf161cca6f1e044e20529ca96c6554dbbe50
test "$(git -C repos/vllm-ascend merge-base collaborator/kv_offload_0723 HEAD)" = a46a1dabbc260e8695002969f29528eb555eb583
test "$(git -C repos/vllm-ascend rev-list --count collaborator/kv_offload_0723..HEAD)" = 11
test -z "$(git -C repos/vllm-ascend rev-list --merges collaborator/kv_offload_0723..HEAD)"
test -z "$(git -C repos/vllm-ascend status --porcelain)"
```

Resume from the first unchecked step in this file. Do not infer status from chat history. Before resuming a Kubernetes family, inspect its `steps.jsonl`, terminal transcript record, summary, checksum manifest, live processes, and Master metrics; never assume an interrupted command completed.

## Current Checkpoint

Captured after diagnosis on 2026-07-31:

| Item | Exact state |
| --- | --- |
| Control HEAD before tooling fix | `e20e79c5032fccb02e3bcf8209179b4f6162fc37` |
| Control tooling checkpoint | `e97b41a046c03f1926f096740765ae13a56329e9`, pushed and verified `0 0` |
| Frozen vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| Frozen vLLM-Ascend | `14beaf161cca6f1e044e20529ca96c6554dbbe50` |
| Frozen Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` |
| Source integration | 11/11 linear commits, clean, pushed, no merge commit |
| Historical failed image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.25.1-a2-14beaf16-20260730T130225Z-r4` |
| Historical G0 failure | `max_num_batched_tokens` was selected for a pinned signature that accepts `max_in_flight_tokens` |
| Current tracked WIP | Tooling r4, image r2, UT, and corrected main-lane G0 are green; G1 is next |
| Active build or formal validation | Base Pods and CPU-only UT Pod are retained on `n1`; both vLLM child processes are stopped and Master is empty |

The target source branch contains:

```text
.github/vllm-main-verified.commit = 54503ecec0f3ac31e5ecfc5f28652e4cc42307b5
.github/vllm-release-tag.commit   = v0.25.1
```

Commit `0f9fc6850b753b28af11a2e6a17df28dd094a6b5` is an ancestor of the collaborator base and is titled `[Misc]feat: adapt to vLLM main (54503ece) (#12420)`. The previous run incorrectly combined that main anchor with `VLLM_VERSION=0.25.1`.

## Frozen Per-Run Identity

| Field | Value | Derivation |
| --- | --- | --- |
| Umbrella run ID | `20260731T064607Z` | UTC diagnosis run start |
| vLLM lane | `main-verified` | target source branch metadata and adaptation history |
| `VLLM_VERSION` override | unset | main development package must select the non-release path naturally |
| Expected installed distribution | `0.1.dev1+g54503ecec.empty` | previous exact build of the same immutable vLLM commit |
| Expected coordinator keyword | `max_in_flight_tokens` | pinned vLLM source signature |
| Base image | `quay.io/ascend/cann:9.0.1-910b-ubuntu22.04-py3.12` | approved A2 baseline |
| Target image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1` | unique new run identity |
| Platform | `linux/arm64` | `default/buildkitd` on `n1` |
| Namespace | `liangjiahao` | workspace policy |
| Base node | `n1` | current deployment fixture; revalidate capacity before use |
| Model | `/home/llm_cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8` | existing validated fixture |
| Model config SHA256 | `229913ea2a346ccdb571bb3cb23414ca3a0ee1a9455fe88a15a5788bc837cb75` | previous live filesystem proof; recheck before runtime |
| Tokenizer SHA256 | `41f3bf64213da8c012d8bd0871a58a1fdf70463e8f08f110ddbb1082f529f669` | previous live filesystem proof; recheck before runtime |
| Physical layers | `27` | model config; rederive before G4 |
| Block size | `128` | current base/stress contract |
| Lease TTL | `30000 ms` | Master configuration; recheck from args and logs |
| Lease expiry code | `-707` | selected Mooncake contract |

The seven required Mooncake APIs are:

```text
batch_put_session_start
batch_put_from_multi_buffer_ranges
batch_put_session_end
batch_put_session_revoke
batch_get_session_start
batch_get_into_multi_buffer_ranges
batch_get_session_end
```

## Diagnosis Already Completed

- [x] Confirm the current image combines main commit `54503ece` with release override `0.25.1`.
- [x] Confirm real vLLM tag `v0.25.1` points to commit `752a3a504485790a2e8491cacbb35c137339ad34` and accepts `max_num_batched_tokens`.
- [x] Confirm pinned main commit `54503ece` accepts `max_in_flight_tokens`.
- [x] Run the CPU-safe AST reproduction in `liangjiahao/vllm-ascend-ut` with the release override and observe:

```text
AssertionError: selected coordinator keyword 'max_num_batched_tokens' not accepted by pinned vLLM
```

- [x] Run the same AST reproduction with `VLLM_VERSION` unset and observe selection of `max_in_flight_tokens` with a passing assertion.
- [x] Add `test_main_verified_vllm_lane_does_not_force_release_compatibility` to `deployment/tests/test_validation_identity.py`.
- [x] Run that focused regression in the CPU-only UT Pod and observe the expected red result: `KeyError: 'vllm_lane'`.

The first attempted Python-import reproduction failed earlier on `libascend_hal.so` because importing the Ascend plugin is inappropriate in a CPU-only Pod. That attempt is a diagnostic test-step issue, not the target failure. The AST reproduction is the accepted fast feedback loop.

## File Ownership Map

| File or group | Responsibility in this rerun |
| --- | --- |
| `deployment/validation-identity.json` | Machine-readable main-lane identity and exact target image |
| `deployment/tests/test_validation_identity.py` | Regression protection against mixing main commits with release overrides |
| `deployment/10-runtime-config.yaml` | Base prestart signature and Mooncake API checks |
| `deployment/stress/10-runtime-config.yaml` | Stress prestart signature and Mooncake API checks |
| Base/stress/UT workload YAML | Exact image and absence of `VLLM_VERSION` override |
| `run-smoke-test.sh`, `run-stress-test.sh`, `run-vllm-ascend-ut.sh`, `sync-vllm-ascend-python.sh` | Exact image/source identity gates |
| `Dockerfile.a2` | Remote-clone image build and source/compatibility OCI labels |
| `implementation-plans/full-validation-guide.md` | Stable contract updated to support an explicit lane plus optional override |
| This file | Per-run values, attempt ledger, terminal gate state, and compact-resume entry point |
| `evidence/full-validation-rerun-20260731T064607Z/` | Immutable evidence families for this run |
| `full-validation-rerun-2026-07-31.md` | Self-contained outcome and exact tooling fixes |

No file under `repos/*` is in the modification set.

---

### Task 1: Make The Main-Lane Regression Green

**Files:**

- Modify: `features/kv-pool-layerwise-reuse/deployment/validation-identity.json`
- Modify: `features/kv-pool-layerwise-reuse/deployment/tests/test_validation_identity.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/10-runtime-config.yaml`
- Modify: `features/kv-pool-layerwise-reuse/deployment/stress/10-runtime-config.yaml`
- Modify: `features/kv-pool-layerwise-reuse/deployment/40-prefill-engine.yaml`
- Modify: `features/kv-pool-layerwise-reuse/deployment/50-decode-engine.yaml`
- Modify: `features/kv-pool-layerwise-reuse/deployment/60-vllm-ascend-ut-pod.yaml`
- Modify: `features/kv-pool-layerwise-reuse/deployment/stress/40-prefill-engine.yaml`
- Modify: `features/kv-pool-layerwise-reuse/deployment/stress/50-decode-engine.yaml`

**Interfaces:**

- Consumes: frozen main commit `54503ece`, its coordinator signature, and the red test already present.
- Produces: explicit `main-verified` identity with no release override and prestart signature enforcement.

- [x] **Step 1: Replace the ambiguous version field in validation identity**

Set these exact fields while preserving all other frozen inputs:

```json
"run_id": "20260731T064607Z",
"attempt": 1,
"image": "docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1",
"vllm_lane": "main-verified",
"vllm_version_override": null,
"vllm_release_tag": "v0.25.1",
"vllm_package_version": "0.1.dev1+g54503ecec.empty",
"vllm_coordinator_keyword": "max_in_flight_tokens"
```

Remove the old `"vllm_version": "0.25.1"` field so no consumer can mistake it for an override.

- [x] **Step 2: Remove the release override from every vLLM workload**

Delete the `VLLM_VERSION` environment entry from the five Prefill, Decode, stress, and UT manifests listed above. Do not remove `TORCH_DEVICE_BACKEND_AUTOLOAD`, `PYTHONDONTWRITEBYTECODE`, `PYTEST_ADDOPTS`, `PYTHONHASHSEED`, or other deterministic settings.

- [x] **Step 3: Add a fail-fast runtime signature gate to both ConfigMaps**

Each `check-runtime.py` must import `inspect` and the upstream function, then enforce:

```python
from vllm.v1.core.kv_cache_coordinator import get_kv_cache_coordinator

assert not vllm_version_is("0.25.1")
parameters = inspect.signature(get_kv_cache_coordinator).parameters
assert "max_in_flight_tokens" in parameters, parameters
assert os.environ.get("VLLM_VERSION") is None
```

Retain the existing source-path, hash-seed, Mooncake API, and native runtime checks.

- [x] **Step 4: Sync the corrected control fixture to the CPU-only Pod**

Use a new Pod-side directory so the red fixture remains distinguishable:

```bash
kubectl exec -n liangjiahao vllm-ascend-ut -c ut -- \
  mkdir /workspace/control-validation-20260731T064607Z-green
tar --exclude='features/kv-pool-layerwise-reuse/evidence' \
  --exclude='*.swp' \
  -C /root/ljh/vllm-workspace -cf - \
  workspace.lock.json features/kv-pool-layerwise-reuse | \
  kubectl exec -i -n liangjiahao vllm-ascend-ut -c ut -- \
  tar -C /workspace/control-validation-20260731T064607Z-green -xf -
```

- [x] **Step 5: Run the focused regression and require green**

```bash
kubectl exec -n liangjiahao vllm-ascend-ut -c ut -- \
  env PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' \
  python3 -m pytest -q \
  /workspace/control-validation-20260731T064607Z-green/features/kv-pool-layerwise-reuse/deployment/tests/test_validation_identity.py::ValidationIdentityTest::test_main_verified_vllm_lane_does_not_force_release_compatibility
```

Expected: `1 passed`.

### Task 2: Propagate The New Identity Through Current Tooling

**Files:**

- Modify: `features/kv-pool-layerwise-reuse/Dockerfile.a2`
- Modify: `features/kv-pool-layerwise-reuse/deployment/30-mooncake-master.yaml`
- Modify: all workload files from Task 1
- Modify: `features/kv-pool-layerwise-reuse/deployment/run-smoke-test.sh`
- Modify: `features/kv-pool-layerwise-reuse/deployment/run-stress-test.sh`
- Modify: `features/kv-pool-layerwise-reuse/deployment/run-vllm-ascend-ut.sh`
- Modify: `features/kv-pool-layerwise-reuse/deployment/sync-vllm-ascend-python.sh`
- Modify: `features/kv-pool-layerwise-reuse/deployment/README.md`
- Modify: `features/kv-pool-layerwise-reuse/ut-pod-design.md`
- Modify: `features/kv-pool-layerwise-reuse/nerdctl-build.md`
- Modify: `features/kv-pool-layerwise-reuse/implementation-plans/full-validation-guide.md`

**Interfaces:**

- Consumes: exact machine-readable identity from Task 1.
- Produces: one image/lane contract shared by every executable consumer.

- [x] **Step 1: Replace only current executable references to the R4 tag**

Use this exact new tag:

```text
docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1
```

Do not rewrite historical reports or evidence that correctly name R4.

- [x] **Step 2: Add an image compatibility-lane label**

Add an exact Dockerfile argument and OCI label:

```dockerfile
ARG VLLM_COMPATIBILITY_LANE="main-verified"
```

The final label set must include the three source SHAs and `org.opencontainers.image.vllm.compatibility-lane=main-verified`.

- [x] **Step 3: Update the stable guide schema**

Require non-empty `.vllm_lane` and allow `.vllm_version_override` to be either `null` or a non-empty string. Replace the unconditional `VLLM_VERSION=$(...)` example with separate lane and optional-override reads. State that main-verified commits normally leave the override unset, while release-tag validation records the exact release override.

- [x] **Step 4: Update identity tests for the new schema and attempt number**

Rename the old image/version test so it asserts the pinned image and lane. Remove assertions that every manifest contains `VLLM_VERSION`. Require `attempt == 1`, the new Dockerfile label, and exact agreement between identity, runners, and manifests.

- [x] **Step 5: Scan for stale current references**

```bash
rg -n 'kv-pool-layerwise-v0\.25\.1-a2-14beaf16-20260730T130225Z-r4|VLLM_VERSION.*0\.25\.1' \
  features/kv-pool-layerwise-reuse/deployment \
  features/kv-pool-layerwise-reuse/Dockerfile.a2 \
  features/kv-pool-layerwise-reuse/ut-pod-design.md \
  features/kv-pool-layerwise-reuse/nerdctl-build.md
```

Expected: no current executable reference. Historical documents outside this target list may retain old identities.

### Task 3: Run And Freeze The Complete Tooling Gate

**Files:**

- Modify: `features/kv-pool-layerwise-reuse/deployment/run-validation-step.sh`
- Test: `features/kv-pool-layerwise-reuse/deployment/tests/`
- Evidence: `features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260731T064607Z/tooling-r4/`
- Preserve: the byte-exact pre-fix `tooling/` and `tooling-r2/` transcripts through the run-local `.gitattributes`
- Update: this plan's gate tracker and attempts ledger

**Interfaces:**

- Consumes: corrected but uncommitted control tooling.
- Produces: one pushed tooling commit used by all image/runtime evidence.

- [x] **Step 1: Run the complete deployment test collection in the UT Pod**

```bash
kubectl exec -n liangjiahao vllm-ascend-ut -c ut -- \
  env PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' \
  python3 -m pytest -q \
  /workspace/control-validation-20260731T064607Z-green/features/kv-pool-layerwise-reuse/deployment/tests
```

Expected: the complete current collection passes; record the observed count instead of enforcing `65`.

Observed in the final tooling family: `67 passed`, including the recorder
trailing-whitespace regression.

- [x] **Step 2: Run static gates**

Run `bash -n` on every executable shell file, compile Python and rendered ConfigMap Python with `compile()` rather than writing bytecode, run Ruff lint/format with the Pod's pinned Ruff 0.14.0 on the two changed Python tests, and run `git diff --check` in both control and source repositories. Do not format unrelated historical test files merely because a validation command accidentally broadened its scope.

- [x] **Step 3: Dry-run every current manifest**

For base, stress, and UT YAML, run this exact list:

```bash
for manifest in \
  features/kv-pool-layerwise-reuse/deployment/00-namespace.yaml \
  features/kv-pool-layerwise-reuse/deployment/10-runtime-config.yaml \
  features/kv-pool-layerwise-reuse/deployment/20-proxy-server.yaml \
  features/kv-pool-layerwise-reuse/deployment/30-mooncake-master.yaml \
  features/kv-pool-layerwise-reuse/deployment/40-prefill-engine.yaml \
  features/kv-pool-layerwise-reuse/deployment/50-decode-engine.yaml \
  features/kv-pool-layerwise-reuse/deployment/60-vllm-ascend-ut-pod.yaml \
  features/kv-pool-layerwise-reuse/deployment/stress/10-runtime-config.yaml \
  features/kv-pool-layerwise-reuse/deployment/stress/40-prefill-engine.yaml \
  features/kv-pool-layerwise-reuse/deployment/stress/50-decode-engine.yaml
do
  kubectl apply --dry-run=client -n liangjiahao -f "${manifest}"
done
```

- [x] **Step 4: Create checksummed tooling evidence**

Record every command with `deployment/run-validation-step.sh`, create a structured `summary.json`, generate `SHA256SUMS` after terminal records exist, and replay `sha256sum -c SHA256SUMS` from the tooling family directory.

The original `tooling/` and `tooling-r2/` command transcripts contain the
recorder's trailing separator and remain byte-for-byte checksummable. Their
path-scoped `binary` attribute prevents Git from normalizing or rejecting that
historical byte evidence. The corrected `tooling-r4/` transcript remains a
normal text file and has no trailing whitespace.

- [x] **Step 5: Commit and push the tooling checkpoint narrowly**

Stage only the control files listed in Tasks 1-3 and this plan. Verify the live remote is still the expected ancestor, commit with a message describing the main/release identity correction, push normally, then require live `git ls-remote` equality and `git rev-list --left-right --count` equal to `0 0`.

### Task 4: Build And Prove The New ARM64 Image

**Files:**

- Build: `features/kv-pool-layerwise-reuse/Dockerfile.a2`
- Evidence: failed attempt `image-r1/`; unchanged-identity retry `image-r2/`

**Interfaces:**

- Consumes: pushed tooling checkpoint and exact target tag.
- Produces: immutable ARM64 manifest digest/config ID accepted by every later family.

- [x] **Step 1: Verify builder identity and target-tag absence**

```bash
kubectl get pod buildkitd -n default -o wide
kubectl logs buildkitd -n default --tail=100
nerdctl -n k8s.io image inspect docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1
```

The inspect command should report that the unique tag is absent before build. If it exists, compare complete identity; do not overwrite an unrelated image silently.

- [x] **Step 2: Build with the existing remote-clone workflow**

```bash
export BUILDKIT_HOST='kube-pod://buildkitd?namespace=default'
export CONTAINERD_NAMESPACE=k8s.io
nerdctl -n "${CONTAINERD_NAMESPACE}" build \
  --progress=plain \
  -f features/kv-pool-layerwise-reuse/Dockerfile.a2 \
  -t docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1 \
  features/kv-pool-layerwise-reuse
```

- [x] **Step 3: Prove image identity**

Require `linux/arm64`, exact source labels, main-verified lane label, raw fail-closed `pip check`, expected editable Git HEADs, native vLLM-Ascend and Mooncake libraries, no missing `ldd` dependency, seven Mooncake APIs, NPU availability, healthy `npu-smi`, and Pod `imageID` equal to the recorded config ID.

- [x] **Step 4: Checksum image evidence**

Write the actual manifest digest and config ID into `summary.json`, generate `SHA256SUMS`, and replay it from `image-r2/`.

Image r2 completed from `2026-07-31T08:50:59Z` through
`2026-07-31T10:04:30Z`. The accepted identity is manifest
`sha256:866ba89f897464a1e38893a57f6e5c3a035c7aba7dfa196fce9646498eaf6d97`
and config
`sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57`.
The NPU Pod proof passed the main lane, coordinator keyword, seven Mooncake
APIs, exact source HEADs, dynamic imports, `npu-smi`, `ldd`, imageID, and
cleanup gates. A label-based wait first matched the terminating old ReplicaSet
Pod, an attempted JSONPath null predicate selected no Pod, and the first
summary generator embedded JSON booleans as Python. All three validation-step
issues are preserved in `steps.jsonl`; explicit Pod identity and argv-based
summary generation superseded them. No production source changed.

### Task 5: Recreate The CPU-Only UT Pod And Run Full UT

**Files:**

- Apply: `features/kv-pool-layerwise-reuse/deployment/60-vllm-ascend-ut-pod.yaml`
- Execute: `features/kv-pool-layerwise-reuse/deployment/run-vllm-ascend-ut.sh`
- Evidence: `features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260731T064607Z/ut/`

**Interfaces:**

- Consumes: proved image and frozen clean source.
- Produces: source-freeze confirmation under the corrected main lane.

- [x] **Step 1: Recreate only `vllm-ascend-ut` if its image differs**

Capture the old Pod JSON, delete only `pod/vllm-ascend-ut` in `liangjiahao`, apply the exact UT manifest, and wait for Running/Ready. Do not delete the namespace or serving Pods.

- [x] **Step 2: Prove the CPU-only Pod contract**

Require CPU/memory-only resources, no `huawei.com/Ascend910`, no driver/device/model mount, no `hostPath`, `emptyDir` workspace, exact new image, node `n1`, and restart count zero.

- [x] **Step 3: Run complete AscendStore tests**

```bash
features/kv-pool-layerwise-reuse/deployment/run-vllm-ascend-ut.sh -- \
  env PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' \
  python3 -m pytest -q tests/ut/distributed/ascend_store
```

- [x] **Step 4: Run deployment tests and source static gates**

Run the complete deployment collection from the synced control fixture, changed-file Ruff lint/format, Python `compile()` checks, source history assertions, source clean-tree check, and `git diff --check`.

- [x] **Step 5: Classify any failure**

If the failure is control tooling, repair it with a regression test and rerun Tasks 3-5 as invalidated. If it is production source behavior, capture a minimum reproduction and terminate without editing `repos/*`.

The recreated Pod reported config ID
`sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57`,
restart count zero, CPU/memory-only resources, `emptyDir` workspace, and no NPU,
driver, model, or `hostPath` access. The complete AscendStore collection passed
`476` tests with `14` warnings; deployment tests passed `67`; Ruff 0.14.0 lint
and format passed for `19` source/test files; `28` Python files compiled; source
history, clean-tree, and diff checks passed. No UT failure required source or
tooling changes. Evidence is in `ut/` with `SHA256SUMS` digest
`9fe25f229eddd594ee0fbe15ebc80539a96b71c2665be54160fce2c4d2e27426`.

### Task 6: Establish G0 With The Corrected Main Lane

**Files:**

- Apply: base namespace, ConfigMap, Master, Prefill, Decode, and proxy manifests
- Evidence: `features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260731T064607Z/g0/`

**Interfaces:**

- Consumes: proved image, corrected manifests, live capacity, and clean Master.
- Produces: exact healthy base 1P1D suitable for independent runtime gates.

- [x] **Step 1: Re-query context, Ready nodes, physical NPU capacity, active requests, and model checksums**
- [x] **Step 2: Apply every base object with explicit `-n liangjiahao`**
- [x] **Step 3: Require each Pod to report the new imageID and exact editable source HEADs**
- [x] **Step 4: Run both mounted `check-runtime.py` scripts before engine startup**
- [x] **Step 5: Require main lane, unset override, `max_in_flight_tokens`, seven APIs, NPU health, native libraries, model identity, and hash seed**
- [x] **Step 6: Start Prefill and Decode, wait for HTTP/Ready, and fail immediately on the prior coordinator TypeError**
- [x] **Step 7: Stop engines, reset Master, and require keys, allocated bytes, and active clients all equal zero**
- [x] **Step 8: Checksum G0 evidence and write a terminal structured summary**

G0 passed on `n1` with the exact image config ID and source HEADs. Both
Prefill and Decode initialized `AscendStoreConnector`, reached HTTP readiness,
and were discovered by the proxy; the old coordinator `TypeError` did not
recur. The child processes were then stopped and Master was reset to zero keys,
zero allocated bytes, and zero active clients. One Pod snapshot command
specified the resource type twice; its failed output is preserved and the
bare-name retry passed. No source changed. Evidence `SHA256SUMS` digest:
`6416863ddba50d3e716cf6f765869c79488c70707adb78b0b6c1a0a28662524c`.

### Task 7: Run G1, Lease, G4, And 1P1D Smoke Independently

**Files:**

- Execute: `deployment/range-api-smoke.py`
- Execute: `deployment/lease-expiry-test.py`
- Execute: `deployment/check-range-debug-log.py`
- Execute: `deployment/run-smoke-test.sh`
- Evidence families: `g1/`, `lease/`, `g4/`, `smoke/`

**Interfaces:**

- Consumes: G0 identity only; every family starts from stopped engines and an empty Master.
- Produces: direct ranged, lease, production ranged-audit, and request-level correctness evidence.

- [ ] **Step 1: G1 direct ranged API** - require multi-key/multi-layer bytes, non-zero offsets, negative session/range cases, cleanup, and zero final metrics.
- [ ] **Step 2: Reset proof** - stop engines, restart Master, and require all three metrics zero.
- [ ] **Step 3: Lease expiry** - derive waits from live `30000 ms` TTL, require stale read `-707`, fresh-session exact recovery, cleanup, and zero final metrics.
- [ ] **Step 4: Reset proof** - repeat stopped-engine and empty-Master gates.
- [ ] **Step 5: G4 audit** - require Prefill save/load and Decode load across exactly layers `0..26`, byte sums, final-layer commit order, and zero whole-key calls.
- [ ] **Step 6: Reset proof** - repeat stopped-engine and empty-Master gates.
- [ ] **Step 7: Smoke** - execute `run-smoke-test.sh` with a new empty output directory and require HTTP, marker ownership/isolation, token boundary/count, usage, finish reason, routing, and per-request hit correlation.
- [ ] **Step 8: Generate and replay checksums for each family before starting the next family**

### Task 8: Run Stress S1-S3

**Files:**

- Apply: `deployment/stress/10-runtime-config.yaml`
- Apply: `deployment/stress/40-prefill-engine.yaml`
- Apply: `deployment/stress/50-decode-engine.yaml`
- Execute: `deployment/run-stress-test.sh`
- Evidence: `features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-20260731T064607Z/stress/`

**Interfaces:**

- Consumes: six free physical NPUs on the selected Ready node and the proved image.
- Produces: DP/TP, concurrency, long-context, chunked-prefill, ranged-audit, and isolation evidence.

- [ ] **Step 1: Re-query six-card availability immediately before applying stress manifests**
- [ ] **Step 2: Prove Prefill DP2/TP2 and Decode DP1/TP2 from Pod resources, process trees, logs, and active device processes**
- [ ] **Step 3: Run S1 and require configured long-context, chunk-bound, all-layer, commit-order, marker/token/usage, key-count, and whole-key exclusion gates**
- [ ] **Step 4: Stop engines, reset Master, prove empty metrics, and restart before S2**
- [ ] **Step 5: Run S2 and require all concurrent cases plus activity on both Prefill DP ranks**
- [ ] **Step 6: Stop engines, reset Master, prove empty metrics, and restart before S3**
- [ ] **Step 7: Run S3 and require cold long-context, minimum context iterations, concurrent proxy cases, derived key count, and hard isolation gates**
- [ ] **Step 8: Stop all stress engines and checksum the complete stress family**

### Task 9: Finalize Evidence, Reports, And Publication

**Files:**

- Create: `features/kv-pool-layerwise-reuse/full-validation-rerun-2026-07-31.md`
- Update: this plan, feature README/status/repo-state/sync-log, evidence index, and `workspace.lock.json`
- Validate: `deployment/check-validation-report.py`

**Interfaces:**

- Consumes: immutable checksummed family evidence.
- Produces: auditable final state and matching source/control remotes.

- [ ] **Step 1: Capture final Pods, processes, logs, metrics, images, and active NPU requests**
- [ ] **Step 2: Stop every live vLLM child process started by this run and require Master empty**
- [ ] **Step 3: Record the reclassification of the old G0 failure as a validation identity defect**
- [ ] **Step 4: List every test/tooling issue, exact control files changed, regression coverage, and affected gates rerun**
- [ ] **Step 5: Run checksum replay, credential scan, link/Git tracking checks, report checker, JSON checks, and `git diff --check`**
- [ ] **Step 6: Run `pwsh -File` workspace scripts if `pwsh` exists; otherwise run and document Linux-equivalent lock/status/validation checks without claiming PowerShell execution**
- [ ] **Step 7: Commit and push immutable evidence before the report/state commit**
- [ ] **Step 8: Verify the control remote has not advanced, push normally, and require live `ls-remote` plus left/right count `0 0`**
- [ ] **Step 9: Re-run final source history, protected-branch, remote, and clean-tree checks**
- [ ] **Step 10: Preserve every user-owned untracked path exactly as found at finalization**

## Gate Tracker

| Gate | Status | Evidence family | Terminal requirement |
| --- | --- | --- | --- |
| Diagnosis | PASSED | interactive diagnostic record, to be summarized in tooling evidence | red with override; green without override |
| Regression red | PASSED | tooling | focused test failed on missing lane field |
| Tooling green | PASSED | `tooling-r4/` | 20/20 gate steps, 67 tests, recorder regression, static/dry-run/checksums passed |
| Image | RETRYING | `image-r1/` failed infrastructure; `image-r2/` next | build plus static/dynamic identity pass |
| CPU/mock UT | NOT RUN | `ut/` | AscendStore, deployment, Ruff, compile, history pass |
| G0 | NOT RUN | `g0/` | exact identity, engines Ready, empty reset |
| G1 | NOT RUN | `g1/` | direct ranged contract and cleanup pass |
| Lease | NOT RUN | `lease/` | stale expiry, fresh recovery, cleanup pass |
| G4 | NOT RUN | `g4/` | exact 27-layer ranged audit and whole-key exclusion pass |
| Smoke | NOT RUN | `smoke/` | hard marker/token/usage/routing oracles pass |
| Stress S1-S3 | NOT RUN | `stress/` | all topology, ranged, isolation, and reset gates pass |
| Reports/publication | NOT RUN | reports and Git refs | replay/checker/push/remote equality pass |

## Attempts And Failure Ledger

| Attempt | Classification | Observation | Disposition |
| --- | --- | --- | --- |
| Historical run `20260730T130225Z` G0 | validation identity/tooling defect, reclassification pending publication | main commit `54503ece` was forced through release override `0.25.1`, selecting an unsupported keyword | preserve old evidence; repair control identity; rebuild and rerun from tooling |
| Python-import fast loop | diagnostic test-step defect | CPU-only Pod loaded the Ascend plugin and stopped on missing `libascend_hal.so` before the target assertion | preserve in final report; use CPU-safe AST signature loop |
| AST loop with override | expected red | selected `max_num_batched_tokens`, absent from pinned main signature | accepted exact reproduction |
| AST loop without override | expected green | selected `max_in_flight_tokens`, present in pinned main signature | validates the control-only fix direction |
| Focused identity regression | expected red | `KeyError: 'vllm_lane'` | implement Task 1, then require green |
| Tooling r1 | validation formatting defect | 19 of 20 recorded steps passed; Ruff 0.14.0 found two line-wrap deltas in the new identity regression | preserve `tooling/`; apply the exact Ruff diff; rerun the complete family as `tooling-r2/` |
| Tooling r2 | superseded after a passed gate | 20 of 20 gate steps passed and deployment `66 passed`, but staging exposed a trailing space on every transcript `COMMAND` line | preserve byte-exact evidence; add a focused recorder regression and repair the validation runner only |
| Recorder whitespace regression | expected red then green | before the fix, `COMMAND printf %s hello\\ world ` ended in a space; after trimming the final separator, the focused test passed | retain the regression in the full deployment collection and rerun the complete tooling family |
| Tooling r3 | validation scope defect | deployment `67 passed` and Ruff lint passed, but Ruff format was accidentally broadened to four unchanged historical test files | preserve the checksummed failed attempt; do not rewrite unrelated files; restore changed-file scope |
| Tooling r4 | passed | 20 of 20 gate steps passed; deployment `67 passed`; two changed tests passed Ruff; transcript has no trailing whitespace; ten dry-runs, compile, history, identity, diff, and checksum replay passed | freeze and push this tooling tree before image build; `SHA256SUMS` digest `1b57584e8626d8f2afab7edc0b0d261a1cdf9624f555cc004f83293e76b25506` |
| Builder recovery from `/root/buildkitd.yaml` | recovered infrastructure | the user-provided historical manifest recreated `default/buildkitd` but, because it has no node pin, scheduled it on `m1` | delete only that new Pod and reapply the same definition with `nodeName: n1`; Ready, restart 0, worker `linux/arm64` |
| Image r1 | transient infrastructure | after about 50 minutes of successful cold-cache compilation, `default/buildkitd` and the other default-namespace platform Pods received `Killing` at `2026-07-31T08:36:07Z`; BuildKit transport exited 137 and no image was loaded | preserve `image-r1/`; target tag remains absent; unchanged identity and source permit retry as `image-r2/`; checksum digest `8a80443d4f2f4603c528ec653deb386ab689ab9f2c33107bcf9baa7b9c243b33` |

Append every later failed or superseded attempt here immediately. Never erase an attempt after a retry passes.

## Completion Definition

This plan is complete only when every gate has a terminal state, all successful evidence is checksummed and tracked, source remains unchanged and clean, the protected branch remains unchanged, final vLLM processes are stopped, Master is empty, and source/control live remotes match their local heads. A production source defect is also a valid terminal outcome only when the remaining runtime gates are explicitly marked NOT RUN, cleanup succeeds, and a detailed checked failure report is pushed.
