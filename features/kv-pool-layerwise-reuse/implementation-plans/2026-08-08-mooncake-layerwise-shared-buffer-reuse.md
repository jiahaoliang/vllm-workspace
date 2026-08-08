# Mooncake Layerwise Shared-Buffer Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: execute this plan inline task-by-task with TDD. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable compute-side `layerwise_num_shared_buffers` reuse for Mooncake save-capable roles, prove source behavior in CPU/mock UT, and complete real Mooncake/NPU correctness validation for `kv_producer` and `kv_both`.

**Architecture:** Extend only `get_gva_layerwise_config()` in production code so a Mooncake layerwise candidate reaches the existing memory-accounting and tensor-merge path. Preserve memcache behavior, reject a pure Mooncake consumer only when it supplies a non-null shared-buffer option, and reuse the existing Mooncake range/session and reuse-mate save-gate implementation.

**Tech Stack:** Python 3.12, pytest, vLLM/vLLM-Ascend, Mooncake, Ruff, Kubernetes, nerdctl/containerd, ARM64 Ascend A2.

## Global Constraints

- Implement the approved design in `features/kv-pool-layerwise-reuse/2026-08-08-mooncake-layerwise-shared-buffer-reuse-design.md` exactly.
- The only production source file changed is `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py`.
- Do not change `Backend`, `MemcacheBackend`, `MooncakeBackend`, `KVPoolWorker`, `KVPoolScheduler`, `NPUWorker`, `NPUModelRunner`, connector or transfer-thread behavior.
- Keep memcache behavior unchanged.
- Mooncake save-capable roles are `kv_producer`, `kv_both`, and `kv_consumer` with `consumer_is_to_put=true`.
- A pure Mooncake `kv_consumer` with a non-null `layerwise_num_shared_buffers` fails at startup; absence or null preserves one buffer per layer.
- Do not add simultaneous memcache/Mooncake priority or conflict handling.
- vLLM remains fixed at `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` and Mooncake remains read-only at `df3f74ed8ebdb0c935554beea6299a9f11c723e2`.
- Do not rebuild the E2E image. Patch only the validated `layerwise_config.py`
  into `kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z`
  and use `nerdctl commit` to create the reusable derived image.
- UT, serving and validation workloads use explicit namespace `liangjiahao`; only `buildkitd` uses `default`.
- CPU/mock UT uses a dedicated CPU-only Pod, tar synchronization, `PYTHONDONTWRITEBYTECODE=1`, and disabled pytest cache.
- Preserve unrelated `deployment_yaml/`, `dockerfile.vllm23`, the untracked research snapshot, historical evidence and retained Pods.
- Do not claim pure-consumer, real-NPU consumer-to-put, memcache NPU, CP, TP-mismatch, unsupported hybrid layout, multi-group, FabricMem, A3 or performance coverage.

---

### Task 1: Mooncake Role-Selection Regression Tests

**Files:**
- Modify: `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_layerwise_config.py:70-97`

**Interfaces:**
- Consumes: `get_gva_layerwise_config(kv_transfer_config: Any) -> dict[str, Any] | None`.
- Produces: executable role/default/error expectations for direct and `MultiConnector` Mooncake configurations.

- [x] **Step 1: Replace the memcache-only test with explicit configuration builders**

Add a helper local to the test module:

```python
def _make_transfer_config(
    *,
    backend: str = "mooncake",
    kv_role: str = "kv_producer",
    use_layerwise: bool = True,
    shared_buffers: int | None = 3,
    consumer_is_to_put: bool = False,
) -> SimpleNamespace:
    extra_config = {
        "backend": backend,
        "use_layerwise": use_layerwise,
    }
    if shared_buffers is not None:
        extra_config["layerwise_num_shared_buffers"] = shared_buffers
    if consumer_is_to_put:
        extra_config["consumer_is_to_put"] = True
    return SimpleNamespace(
        kv_connector="AscendStoreConnector",
        kv_role=kv_role,
        kv_connector_extra_config=extra_config,
    )
```

- [x] **Step 2: Add role/default/error tests**

Add these focused contracts:

```python
@pytest.mark.parametrize(
    ("kv_role", "consumer_is_to_put"),
    [("kv_producer", False), ("kv_both", False), ("kv_consumer", True)],
)
def test_gva_config_accepts_mooncake_save_capable_roles(kv_role, consumer_is_to_put):
    config = _make_transfer_config(
        kv_role=kv_role,
        consumer_is_to_put=consumer_is_to_put,
    )
    assert get_gva_layerwise_config(config) is config.kv_connector_extra_config


def test_gva_config_rejects_mooncake_pure_consumer_reuse():
    config = _make_transfer_config(kv_role="kv_consumer")
    with pytest.raises(ValueError, match="save-capable"):
        get_gva_layerwise_config(config)


def test_gva_config_allows_mooncake_pure_consumer_without_reuse_option():
    config = _make_transfer_config(kv_role="kv_consumer", shared_buffers=None)
    assert get_gva_layerwise_config(config) is config.kv_connector_extra_config
    assert get_layerwise_config(27, config.kv_connector_extra_config).has_layer_reuse is False
```

Retain a memcache assertion, add `use_layerwise=false` and unsupported-backend assertions, and make one `MultiConnector` contain a single Mooncake AscendStore child whose config is returned.

- [x] **Step 3: Tar-sync the dirty TDD checkout to an isolated CPU-only Pod directory**

Run only after verifying context, namespace, Pod name and CPU-only contract:

```bash
kubectl get pod -n liangjiahao vllm-ascend-ut -o json
kubectl exec -n liangjiahao vllm-ascend-ut -c ut -- mkdir -p /workspace/vllm-ascend-shared-buffer-tdd
tar --exclude=.git --exclude=__pycache__ --exclude=.pytest_cache --exclude=.ruff_cache -C repos/vllm-ascend -cf - . | kubectl exec -i -n liangjiahao vllm-ascend-ut -c ut -- tar -C /workspace/vllm-ascend-shared-buffer-tdd -xf -
```

Record local HEAD, branch and dirty status beside the test log.

- [x] **Step 4: Run the focused test and prove the red state**

```bash
kubectl exec -n liangjiahao vllm-ascend-ut -c ut -- env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/vllm-ascend-shared-buffer-tdd python3 -m pytest -q -p no:cacheprovider /workspace/vllm-ascend-shared-buffer-tdd/tests/ut/distributed/ascend_store/test_layerwise_config.py
```

Expected result: the new Mooncake save-capable assertions fail because the current function returns `None`, and the pure-consumer error assertion fails because no `ValueError` is raised. Preserve this red log.

### Task 2: Minimal Mooncake Compute-Gate Implementation

**Files:**
- Modify: `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py:1-67`
- Modify: `repos/vllm-ascend/docs/source/user_guide/feature_guide/layerwise_kv_pool.md:105-118,234-256`
- Test: `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_layerwise_config.py`

**Interfaces:**
- Consumes: `is_kv_save_role(kv_role: str, consumer_is_to_put: bool) -> bool` from `config_data.py`.
- Produces: the unchanged `get_gva_layerwise_config(...) -> dict | None` API with Mooncake role gating.

- [x] **Step 1: Implement the smallest production change**

Import `is_kv_save_role` from `config_data`. Replace the memcache-only return block with:

```python
        use_layerwise = extra_config.get("use_layerwise", False)
        if backend not in ("memcache", "mooncake") or not use_layerwise:
            continue
        if (
            backend == "mooncake"
            and extra_config.get(_EXTRA_CONFIG_KEY_NUM_SHARED_BUFFERS) is not None
            and not is_kv_save_role(
                getattr(kv_transfer_config, "kv_role", ""),
                bool(extra_config.get("consumer_is_to_put", False)),
            )
        ):
            raise ValueError(
                "Mooncake layerwise KV cache buffer reuse requires a save-capable "
                "role; remove layerwise_num_shared_buffers or use kv_producer, "
                "kv_both, or kv_consumer with consumer_is_to_put=true."
            )
        return extra_config
```

Do not modify any other production source file.

- [x] **Step 2: Re-sync the isolated Pod directory and prove the focused test is green**

Repeat the Task 1 tar sync after removing and recreating only
`/workspace/vllm-ascend-shared-buffer-tdd`, then rerun the same explicit pytest
target. Expected result: every test in `test_layerwise_config.py` passes.

- [x] **Step 3: Update the user guide**

Document that Mooncake compute-side shared-buffer reuse is supported only for
the three save-capable configurations in this version, that absence/null keeps
one buffer per layer, and that a pure consumer with a non-null value fails at
startup. Keep the existing memcache text and general layerwise transfer support
unchanged.

- [x] **Step 4: Run changed-file static checks in the Pod**

```bash
kubectl exec -n liangjiahao vllm-ascend-ut -c ut -- env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/vllm-ascend-shared-buffer-tdd /workspace/tools/ruff check /workspace/vllm-ascend-shared-buffer-tdd/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py /workspace/vllm-ascend-shared-buffer-tdd/tests/ut/distributed/ascend_store/test_layerwise_config.py
kubectl exec -n liangjiahao vllm-ascend-ut -c ut -- env PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile /workspace/vllm-ascend-shared-buffer-tdd/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py /workspace/vllm-ascend-shared-buffer-tdd/tests/ut/distributed/ascend_store/test_layerwise_config.py
git -C repos/vllm-ascend diff --check
```

Expected result: all commands exit zero and no cache/bytecode is written into the synced checkout.

### Task 3: Complete CPU/Mock Gates And Source Publication

**Files:**
- Verify: `repos/vllm-ascend/tests/ut/distributed/ascend_store`
- Verify: `repos/vllm-ascend/tests/ut/worker/a2/test_worker_v1.py`
- Verify: `repos/vllm-ascend/tests/ut/worker/a2/test_model_runner_v1.py`
- Modify after source commit: `workspace.lock.json`
- Modify after source commit: `features/kv-pool-layerwise-reuse/repo-state.md`
- Modify after source commit: `features/kv-pool-layerwise-reuse/sync-log.md`

**Interfaces:**
- Produces: one signed-off vLLM-Ascend source commit pushed to the current personal-fork branch, plus control metadata that records the exact SHA.

- [x] **Step 1: Run focused worker/model-runner reuse tests**

Inspect exact collected names first, then run the existing methods covering
`_get_layerwise_kv_cache_memory_info` and
`_merge_kv_cache_tensors_for_layer_reuse` in the isolated Pod checkout. Do not
invent class or method names; preserve the collected-target output in evidence.

- [x] **Step 2: Run the complete AscendStore CPU/mock suite**

```bash
kubectl exec -n liangjiahao vllm-ascend-ut -c ut -- env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/vllm-ascend-shared-buffer-tdd python3 -m pytest -q -p no:cacheprovider /workspace/vllm-ascend-shared-buffer-tdd/tests/ut/distributed/ascend_store
```

Expected result: zero failures or errors. A skip is accepted only if it is the
existing opt-in real Mooncake/NPU benchmark and its reason is recorded.

- [x] **Step 3: Re-run Ruff, Python compilation and diff checks after the full suite**

Run `/workspace/tools/ruff check` on both changed Python files, compile the
production file with bytecode redirected outside the checkout or disabled, and
run `git diff --check`. Confirm the source repo contains only the three approved
source/test/doc changes.

- [x] **Step 4: Commit and push vLLM-Ascend**

```bash
git -C repos/vllm-ascend add -- vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py tests/ut/distributed/ascend_store/test_layerwise_config.py docs/source/user_guide/feature_guide/layerwise_kv_pool.md
git -C repos/vllm-ascend commit -s -m 'feat(kv_pool): enable Mooncake layerwise buffer reuse'
git -C repos/vllm-ascend push origin feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723
git -C repos/vllm-ascend rev-list --left-right --count HEAD...origin/feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723
```

Expected left/right count: `0 0`.

- [x] **Step 5: Refresh control identity**

Run `pwsh -File scripts/lock-repos.ps1` when available. If PowerShell is not
installed, update only the vLLM-Ascend commit/branch/purpose fields in
`workspace.lock.json` with structured JSON tooling, then validate JSON and
compare all three recorded commits to their checkouts. Update `repo-state.md`
and `sync-log.md` with the source commit and CPU gate results.

### Task 4: Freeze And Create The Derived ARM64 Image

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/10-runtime-config.yaml`
- Modify: `features/kv-pool-layerwise-reuse/deployment/40-prefill-engine.yaml`
- Modify: `features/kv-pool-layerwise-reuse/deployment/60-vllm-ascend-ut-pod.yaml`
- Modify: `features/kv-pool-layerwise-reuse/deployment/run-vllm-ascend-ut.sh`
- Modify: `features/kv-pool-layerwise-reuse/deployment/validation-identity.json`
- Create: `features/kv-pool-layerwise-reuse/implementation-plans/2026-08-08-mooncake-shared-buffer-functional-validation.md`
- Create at execution: `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-${run_id}/`

**Interfaces:**
- Consumes: pushed vLLM-Ascend source SHA and fixed vLLM/Mooncake SHAs.
- Produces: a provenance-bearing derived `linux/arm64` image and frozen validation identity.

- [x] **Step 1: Create the run identity and tracker**

Derive `run_id=$(date -u +%Y%m%dT%H%M%SZ)`. Create the evidence directory and
a dated tracker that records the four Git identities, dirty state, remote
left/right counts, Kubernetes context, exact namespace, model path/hash,
physical NPU allocation, image tag and every gate below.

- [x] **Step 2: Make the existing start script accept an explicit validation config**

In `10-runtime-config.yaml`, set a shell variable before the API-server command:

```bash
kv_transfer_config=${PREFILL_KV_TRANSFER_CONFIG:-'{"kv_connector":"AscendStoreConnector","kv_role":"kv_producer","kv_load_failure_policy":"fail","kv_connector_extra_config":{"backend":"mooncake","use_layerwise":true,"layerwise_prefetch_layers":1,"lookup_rpc_port":0}}'}
```

Pass `--kv-transfer-config "${kv_transfer_config}"`. This control-only hook
lets the same retained Prefill Pod run baseline, producer-reuse and both-reuse
configurations without changing production source. Add a deployment unit test
that proves the default JSON remains unchanged and the environment override is
quoted as one CLI argument.

- [ ] **Step 3: Freeze source/image pins and commit control state**

Update the Prefill and UT Pod image references, the UT runner source/image
expectations, and `validation-identity.json` to the new source SHA and set
`vllm_ascend_short=$(git -C repos/vllm-ascend rev-parse --short=8 HEAD)`.
Use this exact tag expression:

```text
docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-${vllm_ascend_short}-df3f74ed-${run_id}
```

Run deployment focused tests and `git diff --check`. Commit only the approved
control/tooling paths before creating the derived image.

- [x] **Step 4: Verify the base image and patch input**

Inspect the existing base image in containerd namespace `k8s.io`. Record its
platform, manifest/config digests and labels. Prove the local patch file is from
the clean pushed vLLM-Ascend commit and record its SHA256:

```bash
nerdctl -n k8s.io image inspect docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z
git -C repos/vllm-ascend show 2770cd3ae66522c2eccb1c568889a55137836c0d:vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py | sha256sum
```

The committed source blob SHA256 must equal the working-tree file SHA256.

- [ ] **Step 5: Patch one Python file, commit and inspect the derived image**

Create an explicitly named temporary container from the base image, copy only
`/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py`
into it with `nerdctl cp`, and verify its in-container SHA256. Use
`nerdctl -n k8s.io commit` with labels for the base manifest digest, patch
SHA256 and source commit to create the frozen derived tag. Inspect the derived
platform, manifest digest and labels; run an import/config probe proving the
patched behavior. Remove only the exact temporary container after commit. Do
not claim a native rebuild.

### Task 5: Real Mooncake/NPU Correctness Validation

**Files:**
- Execute: `features/kv-pool-layerwise-reuse/deployment/10-runtime-config.yaml`
- Execute: `features/kv-pool-layerwise-reuse/deployment/30-mooncake-master.yaml`
- Execute: `features/kv-pool-layerwise-reuse/deployment/40-prefill-engine.yaml`
- Record at execution: `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-${run_id}/`

**Interfaces:**
- Consumes: frozen image and `PREFILL_KV_TRANSFER_CONFIG` override.
- Produces: checksummed correctness evidence for `kv_producer` and `kv_both` with three shared buffers.

- [ ] **Step 1: Run the derived-image CPU gate**

Apply the updated UT Pod manifest in `liangjiahao`, retain the CPU-only contract,
and use the updated runner for the focused tests, complete AscendStore suite,
Ruff and compilation. The synced source must be clean and exactly equal to the
image label.

- [ ] **Step 2: Apply only the required runtime resources**

Stop any retained Prefill/Decode child processes, verify NPU capacity, then
apply the runtime ConfigMap, Mooncake Master and Prefill engine with explicit
`-n liangjiahao`. Do not start or modify the pure Decode consumer. Verify exact
imageID, source labels, model mount and one physical `huawei.com/Ascend910`
request for the Prefill Pod.

- [ ] **Step 3: Establish the no-reuse producer baseline**

Restart Mooncake Master to an empty state. Start Prefill with the default
producer config, wait for port 8100, and send one fixed temperature-zero request.
Archive normalized response text, token IDs/usage, engine log and Master metrics.
Stop only the Prefill child process.

- [ ] **Step 4: Validate `kv_producer` reuse**

Restart Master empty and start Prefill with:

```json
{"kv_connector":"AscendStoreConnector","kv_role":"kv_producer","kv_load_failure_policy":"fail","kv_connector_extra_config":{"backend":"mooncake","use_layerwise":true,"layerwise_num_shared_buffers":3,"layerwise_prefetch_layers":1,"lookup_rpc_port":0}}
```

Send the identical request. Require the same normalized output as the baseline,
the expected 27-layer/5-slot layout, logical factor `5.400`, descriptor-merge
log, all 27 layerwise ranged saves, no gate timeout/corruption, and successful
Mooncake publication. Archive logs and metrics, then stop the child process.

- [ ] **Step 5: Validate `kv_both` reuse**

Restart Master empty and start Prefill with the same config except
`"kv_role":"kv_both"`. Send the fixed request once cold and once warm. Require
both responses to satisfy the correctness oracle, the warm request to report a
Mooncake hit and ranged load, the same 5-slot/factor/merge proof, all expected
save/load layers, and no timeout, foreign data or session leak.

- [ ] **Step 6: Clean the functional run and prove final state**

Stop the Prefill child, restart Master, wait for empty metrics, and require
`master_key_count=0`, `master_allocated_bytes=0`, and
`master_active_clients=0`. Retain the named Pods and any existing `default/buildkitd`; do not
delete the namespace.

### Task 6: Evidence, Handoff And Final Publication

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/performance-validation-handoff.md`
- Modify: `features/kv-pool-layerwise-reuse/repo-state.md`
- Modify: `features/kv-pool-layerwise-reuse/status.md`
- Modify: `features/kv-pool-layerwise-reuse/sync-log.md`
- Modify: `features/kv-pool-layerwise-reuse/evidence/README.md`
- Create: `features/kv-pool-layerwise-reuse/shared-buffer-functional-validation-2026-08-08.md`
- Create: evidence `SHA256SUMS` and final report artifacts for the run ID.

**Interfaces:**
- Consumes: every source, image, CPU and NPU result from Tasks 1-5.
- Produces: a fail-closed final report and `READY_FOR_PERFORMANCE_VALIDATION` handoff.

- [ ] **Step 1: Build and replay immutable evidence manifests**

Generate per-family and root `SHA256SUMS`, replay them from the workspace root,
and record the root manifest digest. Run all applicable offline report/checker
tests with cache and bytecode disabled.

- [ ] **Step 2: Audit every design acceptance criterion**

Verify the production diff contains only `layerwise_config.py`, all documented
roles/default/error cases have direct CPU evidence, both required NPU roles have
direct runtime evidence, memcache production is unchanged, exclusions are
explicit, and source/image/runtime identities agree.

- [ ] **Step 3: Populate the performance handoff fail-closed**

Replace every placeholder value with verified identities and evidence paths,
set every required gate to `PASS`, set `Blocker` to `None`, replay the checksum,
increment `generation` to 1, set `placeholders_remaining: false`, update the
timestamp, then set `status: READY_FOR_PERFORMANCE_VALIDATION` and `ready: true`
last.

- [ ] **Step 4: Commit and push final control evidence**

Stage only approved feature/control paths. Commit with sign-off, reconcile the
control branch's existing remote divergence without rewriting unrelated work,
push normally, and verify local/origin left-right count `0 0`. Recheck all three
nested checkout HEADs against `workspace.lock.json` after publication.

- [ ] **Step 5: Completion audit**

Read the design, this plan, final report and handoff from disk. Confirm every
numbered goal and acceptance criterion has authoritative evidence, no required
gate is indirect or missing, and the performance session can independently
replay identity/checksum checks. Only then mark the active goal complete.
