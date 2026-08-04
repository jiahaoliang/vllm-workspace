# Mooncake Single-Group Review Backports And Overlay Full Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. This run is explicitly authorized for inline execution;
> when those sub-skills are unavailable, execute the same checked steps in the current session.

**Goal:** Backport the three approved single-group review improvements onto
`feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723`, exclude all §5.8 multi-group behavior,
and pass the complete reusable full-validation flow with the existing ARM64 image plus an exact
Python overlay.

**Architecture:** Keep the production branch's single-group `SharedBlockData` and key-major ranged
pipeline. Deepen each ranged row into an immutable value object and isolate request-local backend
failures, centralize best-effort audit emission without changing its JSON contract, and add the
standalone real Mooncake/NPU performance gate. Freeze the final source after source verification;
validation may repair control tooling but may not change `repos/vllm-ascend` production code.

**Tech Stack:** Python 3.12, dataclasses, pytest, Ruff, Bash, Git, Kubernetes, Ascend NPU,
Mooncake Client, JSON/JSONL evidence, Markdown reports.

## Global Constraints

- Source branch starts at `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` commit
  `d28c52958a30cebdb7822d56e3dbb0dbe41499bc` and advances only through normal signed commits.
- Do not rewrite or force-push `d28c52958`; the unsigned historical commit remains unchanged.
- Do not modify or cherry-pick `0dad9ad94c23fb43abac420bf0c7feca5e35ba3d`.
- Do not introduce §5.8 symbols or behavior: group-local Mooncake keys/sessions/object sizes,
  `GroupBlockKeys`, `save_keys_by_group`, `load_keys_by_group`, encoded group/block failures, or
  group-local ranged active-row state.
- Preserve the existing single-group `LayerTransferTask` positional constructor contract,
  collaborator `GroupBatchPlan`/GVA paths, Memcache, Mooncake whole-key, Yuanrong, and MTP behavior.
- Keep `repos/Mooncake` read-only.
- Create three source commits: single-group row/failure backport, audit/docs backport, and the
  performance gate cherry-pick. Every new source commit has
  `Signed-off-by: jiahaoliang <gzliangjiahao@gmail.com>`.
- CPU/mock tests use the CPU-only `liangjiahao/vllm-ascend-ut` Pod, explicit `-n liangjiahao`, tar
  synchronization, `PYTHONDONTWRITEBYTECODE=1`, and `-p no:cacheprovider`.
- Reuse image
  `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1`;
  do not rebuild it.
- The overlay base remains `14beaf161cca6f1e044e20529ca96c6554dbbe50`. The final allowlist is
  derived fail-closed after the three source commits and must contain exactly these package files:
  `config_data.py`, `kv_transfer.py`, `backend/mooncake_backend.py`, and new `range_debug.py` under
  `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/`.
- After the final source commit and source verification, production source is frozen. A production
  failure terminates validation with evidence; only validation scripts, manifests, checkers, and
  reports may be repaired, with focused regression tests and affected-gate reruns.
- Preserve historical evidence and the user-owned untracked `deployment_yaml/` and
  `dockerfile.vllm23`.

---

## File Structure And Responsibilities

| File | Responsibility in this change |
| --- | --- |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py` | Immutable single-group `LayerRangeRow` and legacy metadata view |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py` | Build rows directly; isolate request-local range failures; call shared audit emitters |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/range_debug.py` | Best-effort range/commit/whole-key JSON audit emission |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py` | Reuse shared whole-key audit emitter; preserve Backend API |
| `docs/source/user_guide/feature_guide/layerwise_kv_pool.md` | Correct Client session API names and document nightly gate |
| `tests/ut/distributed/ascend_store/test_config_data.py` | Row immutability, legacy alignment, and segment invariants |
| `tests/ut/distributed/ascend_store/test_kv_transfer.py` | Request-local exception/result-shape behavior and audit contract |
| `tests/ut/distributed/ascend_store/test_range_debug.py` | Shared emitter gate, payload, coercion, serialization, logger isolation |
| `tests/ut/distributed/ascend_store/test_backend.py` | Whole-key emitter integration and Backend result-shape contract |
| `tests/e2e/nightly/single_node/kv_pool/test_mooncake_layerwise_range_performance.py` | Opt-in real NPU/Mooncake throughput and p95 gate |
| `features/kv-pool-layerwise-reuse/deployment/validation-identity.json` | Frozen image and final four-file overlay identity |
| `features/kv-pool-layerwise-reuse/deployment/sync-vllm-ascend-python.sh` | Exact package overlay synchronization and checksum source |
| `features/kv-pool-layerwise-reuse/deployment/run-vllm-ascend-ut.sh` | CPU-only Pod source/allowlist gate |
| `features/kv-pool-layerwise-reuse/deployment/run-smoke-test.sh` | Smoke source/allowlist/checksum gate |
| `features/kv-pool-layerwise-reuse/deployment/run-stress-test.sh` | Stress source identity and overlay gate |
| `features/kv-pool-layerwise-reuse/deployment/tests/test_validation_identity.py` | Regression coverage for every identity consumer |

---

### Task 1: Backport Immutable Single-Group Ranged Rows And Request-Local Failures

**Files:**
- Modify: `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py`
- Modify: `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- Modify: `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_config_data.py`
- Modify: `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_kv_transfer.py`

**Interfaces:**
- Consumes: existing single-group `LayerRangeReqMeta`, `SharedBlockData.row_req_ids`,
  `require_aligned_batch_results`, and `_active_load_indices`.
- Produces: immutable `LayerRangeRow`; `LayerRangeReqMeta.rows`; read-only legacy properties;
  request-local handling for exceptions and malformed batch results.

- [x] **Step 1: Add the row-model red tests from `fdd0713e6`, without group fields**

Add the exact WIP methods
`test_layer_range_metadata_uses_immutable_rows_as_legacy_view_source`,
`test_layer_range_metadata_rejects_misaligned_legacy_rows`, and
`test_layer_range_metadata_rejects_misaligned_segments` to `TestConfigData`.

The first constructs legacy positional metadata, asserts `rows` is a tuple of frozen
`LayerRangeRow` values, and verifies `block_ids`, `keys`, `all_buffers`, `all_sizes`,
`all_offsets`, and `row_req_ids` are derived copies. The latter tests require `ValueError` for
parallel-list length mismatch and per-row buffer/size/offset mismatch.

- [x] **Step 2: Add request-local failure red tests**

Port the exact WIP methods `test_request_exception_does_not_stop_later_range_subgroups`,
`test_request_failure_is_local_for_every_subgroup_and_result_shape`,
`test_malformed_read_results_invalidate_request_without_batch_abort`, and
`test_copy_get_exception_invalidates_request_and_finishes_layer` to the single-group receiver
fixture.

Parameterize first/middle/last request positions and `exception`, `too_short`, `too_long`, and
`non_integer` results. Require later subgroups to execute, only the failed request's block IDs to
be invalid, the layer completion event to be set, and shared metadata corruption to retain the
existing task-level abort.

- [x] **Step 3: Run focused tests and prove the new contract is red**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/ut/distributed/ascend_store/test_config_data.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py
```

Expected: failures because `LayerRangeRow` and request-local exception/result-shape handling are
not present on `d28c52958`.

- [x] **Step 4: Implement `LayerRangeRow` and the compatibility constructor**

```python
@dataclass(frozen=True)
class LayerRangeRow:
    req_id: str
    block_id: int
    key: str
    buffers: tuple[int, ...]
    sizes: tuple[int, ...]
    offsets: tuple[int, ...]
```

Use `@dataclass(init=False)` for `LayerRangeReqMeta`. Accept its existing positional arguments plus
keyword-only `rows`. Normalize legacy inputs once, reject mixed row/legacy inputs, infer owners
only for a single request, validate segment lengths, and expose the six old parallel fields through
copy-producing properties. Do not add `group_id`.

- [x] **Step 5: Build rows directly and isolate subgroup failures**

`LayerBatchBuilder.build` creates `LayerRangeRow` values directly from
`SharedBlockData.row_req_ids`, block IDs, keys, buffers, sizes, and offsets. In
`KVCacheStoreLayerRecvingThread._handle_range_request`, group active indices by `row.req_id`; catch
each subgroup's API exception or `BatchResultShapeError`, invalidate only those indices, remove
them from `_active_load_indices`, and continue. Negative integer results remain row-local. Keep
`_active_load_indices` as one single-group set.

- [x] **Step 6: Run focused and compatibility tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/ut/distributed/ascend_store/test_config_data.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py \
  tests/ut/distributed/ascend_store/test_pool_worker.py
```

- [x] **Step 7: Run Ruff/format/compile/diff gates and commit**

```bash
/workspace/tools/ruff check \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py \
  tests/ut/distributed/ascend_store/test_config_data.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py
/workspace/tools/ruff format --check \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py \
  tests/ut/distributed/ascend_store/test_config_data.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py
git diff --check
git commit -s -m "fix(kv_pool): isolate single-group ranged row failures"
```

---

### Task 2: Backport Client API Documentation And Shared Audit Emitters

**Files:**
- Create: `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/range_debug.py`
- Modify: `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- Modify: `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py`
- Modify: `repos/vllm-ascend/docs/source/user_guide/feature_guide/layerwise_kv_pool.md`
- Create: `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_range_debug.py`
- Modify: `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_backend.py`
- Modify: `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_kv_transfer.py`

**Interfaces:**
- Consumes: `VLLM_ASCEND_KVPOOL_RANGE_DEBUG` and the existing audit JSON schema.
- Produces: `emit_range_event`, `emit_commit_event`, and `emit_whole_key_event`; correct public
  Client API documentation.

- [x] **Step 1: Add shared-emitter red tests**

Port `test_range_debug.py` from `69819f6ea` with the exact tests
`test_emitters_share_the_existing_json_event_contract`,
`test_disabled_emission_does_not_build_or_log_payload`,
`test_payload_coercion_and_serialization_failures_are_best_effort`, and
`test_logger_failures_never_escape_emitters`.

Update backend/transfer tests to patch `range_debug.logger` rather than duplicated local helpers.

- [x] **Step 2: Run focused tests and prove the module is red**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/ut/distributed/ascend_store/test_range_debug.py \
  tests/ut/distributed/ascend_store/test_backend.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py
```

Expected: collection fails because `range_debug.py` does not exist.

- [x] **Step 3: Add the shared module and replace duplicate emitters**

Create the exact best-effort helper from `69819f6ea`:

```python
def _emit(payload_factory: Callable[[], dict[str, object]]) -> None:
    try:
        if not envs.VLLM_ASCEND_KVPOOL_RANGE_DEBUG:
            return
        logger.info(
            "%s %s",
            RANGE_DEBUG_PREFIX,
            json.dumps(payload_factory(), separators=(",", ":")),
        )
    except Exception:
        pass
```

Move the current range/commit payload contract out of `kv_transfer.py` and the whole-key contract
out of `mooncake_backend.py`. Keep every field name and debug prefix unchanged.

- [x] **Step 4: Correct Client API documentation**

Document internal `Backend.batch_get_start`/`batch_commit`/`batch_get_end` separately from Client
`batch_get_session_start`/`batch_put_session_end`/`batch_get_session_end`. List the five
`batch_*_session_*` control calls plus the two unchanged ranged calls. Do not add multi-group
support claims.

- [x] **Step 5: Run focused tests and static gates**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/ut/distributed/ascend_store/test_range_debug.py \
  tests/ut/distributed/ascend_store/test_backend.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py \
  tests/ut/test_envs.py
/workspace/tools/ruff check \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/range_debug.py \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py \
  tests/ut/distributed/ascend_store/test_range_debug.py \
  tests/ut/distributed/ascend_store/test_backend.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py
/workspace/tools/ruff format --check \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/range_debug.py \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py \
  tests/ut/distributed/ascend_store/test_range_debug.py \
  tests/ut/distributed/ascend_store/test_backend.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/range_debug.py \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py
git diff --check
```

- [x] **Step 6: Commit the independent audit/docs backport**

```bash
git commit -s -m "refactor(kv_pool): centralize ranged audit events"
```

---

### Task 3: Apply The Standalone Ranged Performance Gate

**Files:**
- Create: `repos/vllm-ascend/tests/e2e/nightly/single_node/kv_pool/test_mooncake_layerwise_range_performance.py`
- Modify: `repos/vllm-ascend/docs/source/user_guide/feature_guide/layerwise_kv_pool.md`

**Interfaces:**
- Consumes: real registered NPU buffers and configured Mooncake Client.
- Produces: opt-in save/load throughput and p50/p95 regression gate with cleanup.

- [x] **Step 1: Cherry-pick the already independent commit**

```bash
git cherry-pick f97aed26f25a3427f20bdb7587b720dd6ef25bbf
```

Expected: clean application. Preserve its existing DCO sign-off.

- [x] **Step 2: Verify collection and fail-closed configured behavior**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  --confcutdir=tests/e2e/nightly/single_node/kv_pool \
  -q -p no:cacheprovider \
  tests/e2e/nightly/single_node/kv_pool/test_mooncake_layerwise_range_performance.py
```

Expected without config: exactly one skipped test. Source inspection and tests must prove a
configured run fails for missing NPU, missing thresholds, transfer/session failure, data mismatch,
threshold regression, or cleanup failure.

- [x] **Step 3: Prove no §5.8 code entered the source range**

```bash
git diff --check d28c52958..HEAD
git diff d28c52958..HEAD -- vllm_ascend tests docs | \
  rg 'GroupBlockKeys|save_keys_by_group|load_keys_by_group|_encode_group_block_id|_active_load_indices_by_group'
```

Expected: the prohibited-symbol search returns no matches.

---

### Task 4: Run Final Source Verification And Freeze The Source

**Files:**
- Verify: all files changed by `d28c52958..HEAD`.
- Preserve: source branch after final commit.

**Interfaces:**
- Consumes: three signed backport commits.
- Produces: immutable `FINAL_SOURCE_HEAD`, exact four-file package overlay, and pre-validation test
  evidence.

- [x] **Step 1: Tar-sync the clean checkout to `liangjiahao/vllm-ascend-ut`**

Record branch, HEAD, remote, and clean state before sync. Create a new `/workspace` temporary
directory with `mktemp -d`; do not reuse serving Pods or `hostPath`.

- [x] **Step 2: Run the complete CPU/mock gate**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/ut/distributed/ascend_store \
  tests/ut/patch/platform/test_patch_group_block_failures.py \
  tests/ut/test_envs.py
```

If `test_patch_group_block_failures.py` is absent on the target branch, omit that nonexistent
target and record the exact collected scope rather than importing §5.8 patch code.

- [x] **Step 3: Run complete diff-scoped static gates**

```bash
mapfile -t python_files < <(git diff --name-only d28c52958..HEAD | rg '\.py$')
mapfile -t source_files < <(git diff --name-only d28c52958..HEAD | rg '^vllm_ascend/.*\.py$')
/workspace/tools/ruff check "${python_files[@]}"
/workspace/tools/ruff format --check "${python_files[@]}"
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile "${source_files[@]}"
git diff --check d28c52958..HEAD
```

- [x] **Step 4: Verify history, DCO, overlay allowlist, and protected references**

```bash
FINAL_SOURCE_HEAD=$(git rev-parse HEAD)
git rev-list --merges d28c52958..HEAD
git log --format='%H %s%n%b' d28c52958..HEAD
git diff --name-only --diff-filter=ACMRT 14beaf161..HEAD -- vllm_ascend
```

Require exactly four package files in the overlay allowlist, no native/build/dependency files,
three new signed commits, no merge commit, and unchanged
`feature/mooncake-layerwise-kv-pool` at `b5b65d9bb`.

- [x] **Step 5: Freeze production source**

After this checkbox is marked complete, do not modify `repos/vllm-ascend`. A source failure during
formal validation terminates the run with a report instead of triggering an inline source fix.

---

### Task 5: Freeze Four-File Overlay Validation Tooling

**Files:**
- Create: dated tracker under `features/kv-pool-layerwise-reuse/implementation-plans/`
- Modify: `features/kv-pool-layerwise-reuse/deployment/validation-identity.json`
- Modify: `features/kv-pool-layerwise-reuse/deployment/sync-vllm-ascend-python.sh`
- Modify: `features/kv-pool-layerwise-reuse/deployment/run-vllm-ascend-ut.sh`
- Modify: `features/kv-pool-layerwise-reuse/deployment/run-smoke-test.sh`
- Modify: `features/kv-pool-layerwise-reuse/deployment/run-stress-test.sh`
- Modify: `features/kv-pool-layerwise-reuse/deployment/tests/test_validation_identity.py`

**Interfaces:**
- Consumes: frozen `FINAL_SOURCE_HEAD`, image source `14beaf161`, and the existing retained image.
- Produces: one fail-closed tooling commit and a new run identity.

- [x] **Step 1: Add red identity tests for the final source and four-file allowlist**

Update `test_validation_identity.py` to require the derived `FINAL_SOURCE_HEAD` everywhere current
executable tooling expects `d28c52958`, and require exactly:

```python
[
    "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py",
    "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py",
    "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py",
    "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/range_debug.py",
]
```

Run the identity test before tooling edits and require failure on old SHA/two-file assumptions.

- [x] **Step 2: Update every executable identity consumer**

Update the identity JSON, sync helper, UT runner, smoke runner, and stress runner. Keep image commit
`14beaf161`, vLLM `54503ecec`, Mooncake `786c77ff`, image tag, imageID, model, namespace, and all
oracles unchanged. `sync-vllm-ascend-python.sh` must create the destination for new
`range_debug.py` and compare all four checksums after tar synchronization.

- [x] **Step 3: Create a new UTC run tracker and evidence root**

```bash
UMBRELLA_RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
RUN_DATE=$(date -u +%F)
EVIDENCE_ROOT="features/kv-pool-layerwise-reuse/evidence/full-validation-rerun-${UMBRELLA_RUN_ID}"
TRACKER="features/kv-pool-layerwise-reuse/implementation-plans/${RUN_DATE}-single-group-backports-overlay-full-validation-${UMBRELLA_RUN_ID}.md"
test ! -e "$EVIDENCE_ROOT"
test ! -e "$TRACKER"
```

Record the exact source/image split, four paths, test results, cluster snapshot, attempt ledger,
failure policy, and every gate as pending.

- [x] **Step 4: Run tooling validation**

Run the complete `deployment/tests` collection in the dedicated UT Pod, `bash -n` for changed
shell scripts, Ruff/format/compile for changed Python, rendered ConfigMap checks, all manifest
client dry-runs with explicit `-n liangjiahao`, `git diff --check`, credential scan, and the
identity test. Fix only tooling defects with focused tests.

- [ ] **Step 5: Commit the frozen tooling identity**

Commit only current plan/identity/tooling files and the pre-runtime tracker. Record this commit as
`TOOLING_COMMIT`; every formal runtime family must use it.

---

### Task 6: Run Complete Python-Overlay Full Validation

**Files:**
- Use: `features/kv-pool-layerwise-reuse/implementation-plans/full-validation-guide.md`
- Execute: frozen deployment runners and checkers.
- Create: new immutable evidence directories per family.

**Interfaces:**
- Consumes: clean frozen source, frozen tooling commit, retained image, model, and cluster.
- Produces: terminal G0/G1/lease/G4/smoke/S1-S3 results and checksummed evidence.

- [ ] **Step 1: Re-query cluster and prove overlay runtime identity**

Use explicit `-n liangjiahao` for every workload command. Prove retained imageID, node/model/API
identity, source checksums across host/UT/Prefill/Decode, and empty Master. Copy only the four
allowlisted Python files with `sync-vllm-ascend-python.sh`; never copy tests or other source.

- [ ] **Step 2: Run G1 direct ranged contract**

Require 3 keys, 4 layers, non-zero offsets, exact transferred bytes, all 43 cases including 24
negative cases, cleanup, and empty pool. Record actual counts rather than silently accepting drift.

- [ ] **Step 3: Run lease-expiry validation**

Require both waits to exceed live TTL, stale read result `-707`, fresh exact recovery, and final
keys/bytes/clients `0/0/0`.

- [ ] **Step 4: Run G4 runtime audit**

Require Prefill range saves and Decode range loads for exactly physical layers `0..26`, ordered
final commit, exact byte sums, zero whole-key events, and clean final metrics.

- [ ] **Step 5: Run formal 1P1D smoke**

Require cold baseline `4/4`, five warmups, direct concurrent `4/4`, proxy concurrent `4/4`, and
all `12/12` response/hit correlations with unchanged marker/token/usage/finish-reason hard gates.

- [ ] **Step 6: Run stress S1-S3 serially**

Re-query six-card capacity, prove Prefill DP2/TP2 and Decode DP1/TP2, then require S1 `4/4`, S2
`16/16`, S3 pinned plus proxy `4/4`, all-layer range events, expected key arithmetic, both Prefill
DP ranks, zero whole-key events, and every runner step exit 0. Reset and prove empty state between
scenarios.

- [ ] **Step 7: Apply failure policy**

For a tooling defect, preserve the failed attempt, add a regression, fix control tooling, and rerun
every affected gate. For a production-source failure, stop the formal run, capture a detailed
reproduction report, stop engine children, reset Master, and do not modify source or claim success.

---

### Task 7: Publish Source, Evidence, Reports, And Workspace State

**Files:**
- Create: dated family and umbrella reports.
- Update: evidence index, feature README/status/sync log/repo state, `workspace.lock.json`, and this
  plan's checkbox state.

**Interfaces:**
- Consumes: terminal validation results and checksummed evidence.
- Produces: fetchable source/control commits and verified origin refs.

- [ ] **Step 1: Finalize runtime state**

Stop every vLLM child process started by the run, capture retained Pod/process/image state, and
require Master keys/bytes/clients `0/0/0`. Retain the long-running UT Pod and named workloads.

- [ ] **Step 2: Checksum and replay all evidence**

Require root and family `sha256sum -c` success, structured summary `validated=true`, credential
scan, report checker, tracked local links, and offline checker replay.

- [ ] **Step 3: Publish source normally**

Before push, fetch origin and require the remote target still equals the pre-run checkpoint.
Normally push the three source commits without force; verify `git ls-remote` equals
`FINAL_SOURCE_HEAD` and left/right is `0 0`.

- [ ] **Step 4: Publish evidence then reports**

Commit and push evidence first. Create self-contained ranged, lease, G4, smoke, stress, and umbrella
reports with the exact overlay identity and residual risk. Run `check-validation-report.py`, then
commit/push reports and verify the control remote with `git ls-remote` and left/right `0 0`.

- [ ] **Step 5: Completion audit**

Require all three approved changes present, prohibited §5.8 symbols absent from the source diff,
source and control remotes synchronized, all validation families passed, all evidence tracked and
replayable, source/control worktrees clean except preserved user-owned untracked files, and no
claim that the reused image was built from `FINAL_SOURCE_HEAD`.
