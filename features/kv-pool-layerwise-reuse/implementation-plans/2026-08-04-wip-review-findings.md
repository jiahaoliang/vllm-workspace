# Mooncake Review Findings WIP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. This run is explicitly authorized for inline execution.

**Goal:** Create an isolated vLLM-Ascend WIP branch from the reviewed `d28c52958` tree and implement
all pending `SP1`, `SP2`, and `ST1` through `ST5` findings without modifying the public merge branch.

**Architecture:** Preserve the collaborator's `GroupBatchPlan`, `GroupTransferData`,
`TransferCompletion`, `LayerwisePreparation`, `LayerTransferArrayBuilder`, and flat-GVA transfer
modules. Deepen the Mooncake key-major module with group-local key/session/completion state and an
immutable ranged-row model; keep the existing `Backend` interface as the adapter seam. Centralize
best-effort audit emission in one internal module shared by ranged and whole-key callers.

**Tech Stack:** Python 3.11, dataclasses, NumPy, PyTorch/NPU, pytest/unittest, Ruff, Kubernetes CPU
UT Pod, Git.

## Global Constraints

- Source WIP branch: `wip/mooncake-review-findings-d28c529`.
- Reviewed source tree: `d28c52958a30cebdb7822d56e3dbb0dbe41499bc`.
- Rebuild the WIP history from `14beaf161cca6f1e044e20529ca96c6554dbbe50` so the ranged-load
  isolation patch receives a `Signed-off-by` trailer; do not rewrite the original merge branch.
- Keep `feature/mooncake-layerwise-kv-pool`, its origin ref, and
  `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` unchanged.
- Do not modify `repos/Mooncake` or the internal vLLM-Ascend `Backend` interface.
- Preserve the positional `LayerTransferTask(layer_id, block_ranges, ...)` contract.
- Keep single-group Mooncake, memcache flat-GVA, Mooncake whole-key, Yuanrong, and MTP behavior.
- Use `1800d56dc2ff6553ff0e0f25f63ab9505ff5ac3e` only as a source/test reference; port it onto the
  current collaborator base and reject unrelated stale code.
- CPU/mock UT runs in the CPU-only `liangjiahao/vllm-ascend-ut` Pod with explicit namespace,
  `PYTHONDONTWRITEBYTECODE=1`, disabled pytest cache, and tar plus `kubectl exec` source sync.
- Preserve control-repo untracked `deployment_yaml/` and `dockerfile.vllm23`.

---

### Task 1: Create the signed WIP history

**Files:**
- Modify: Git refs and commit metadata only.

**Interfaces:**
- Consumes: `14beaf161` plus the patch from `d28c52958`.
- Produces: `wip/mooncake-review-findings-d28c529` with a tree identical to `d28c52958` and a
  signed replacement for the last fix commit.

- [x] **Step 1: Record immutable branch checkpoints**

```bash
git rev-parse feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723
git rev-parse origin/feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723
git rev-parse feature/mooncake-layerwise-kv-pool
git rev-parse origin/feature/mooncake-layerwise-kv-pool
```

- [x] **Step 2: Create the WIP branch from the parent of the unsigned fix**

```bash
git switch -c wip/mooncake-review-findings-d28c529 14beaf161cca6f1e044e20529ca96c6554dbbe50
git cherry-pick -s d28c52958a30cebdb7822d56e3dbb0dbe41499bc
```

- [x] **Step 3: Prove the rebuilt tree is identical**

```bash
git diff --exit-code d28c52958a30cebdb7822d56e3dbb0dbe41499bc HEAD
git log -1 --format='%H%n%B'
```

Expected: empty tree diff and one `Signed-off-by: jiahaoliang <gzliangjiahao@gmail.com>` trailer.

### Task 2: Make Mooncake metadata and scheduler state group-local

**Files:**
- Modify: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py`
- Modify: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py`
- Test: `tests/ut/distributed/ascend_store/test_config_data.py`
- Test: `tests/ut/distributed/ascend_store/test_pool_scheduler.py`

**Interfaces:**
- Consumes: collaborator `block_ids_by_group`, `kv_cache_group_ids`, group block sizes, and common
  prefix coordinator behavior.
- Produces: `GroupBlockKeys`, group-aware `make_layerwise_block_key(..., group_id=...)`, and
  `ReqMeta.save_keys_by_group` / `ReqMeta.load_keys_by_group` with group-zero compatibility
  properties.

- [x] **Step 1: Add failing key and metadata tests**

```python
def test_make_layerwise_block_key_includes_group_for_multi_group_objects():
    assert make_layerwise_block_key("model", "abc", 3, group_id=2) == "model@2@abc@3"


def test_group_block_keys_keep_group_zero_compatibility_properties():
    meta = ReqMeta(
        req_id="r1",
        block_ids_by_group=[[10], [20]],
        save_block_keys=["g0"],
        save_keys_by_group={1: GroupBlockKeys(block_keys=["g1"], block_offset=4)},
    )
    assert meta.save_block_keys == ["g0"]
    assert meta.save_keys_by_group[1].block_keys == ["g1"]
```

- [x] **Step 2: Run the focused tests and confirm they fail**

```bash
python3 -m pytest -q -p no:cacheprovider \
  tests/ut/distributed/ascend_store/test_config_data.py \
  tests/ut/distributed/ascend_store/test_pool_scheduler.py
```

- [x] **Step 3: Implement group-local metadata**

```python
@dataclass
class GroupBlockKeys:
    block_keys: list[str | None] = field(default_factory=list)
    block_offset: int = 0
    last_block_key: str | None = None
    last_block_index: int | None = None


def make_layerwise_block_key(model_name, block_hash_or_tail, head_or_tp_rank, *, group_id=None):
    if group_id is not None:
        return f"{model_name}@{group_id}@{block_hash_or_tail}@{head_or_tp_rank}"
    return f"{model_name}@{block_hash_or_tail}@{head_or_tp_rank}"
```

Store group-zero compatibility through properties backed by the group dictionaries; do not keep
two mutable sources of truth. Update Mooncake hit lookup to query every participating group and
return the minimum common-prefix token count.

- [x] **Step 4: Run focused tests and commit**

```bash
python3 -m pytest -q -p no:cacheprovider \
  tests/ut/distributed/ascend_store/test_config_data.py \
  tests/ut/distributed/ascend_store/test_pool_scheduler.py
git add vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py \
  vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py \
  tests/ut/distributed/ascend_store/test_config_data.py \
  tests/ut/distributed/ascend_store/test_pool_scheduler.py
git commit -s -m "feat(kv_pool): make Mooncake keys group-local"
```

Execution note: metadata and Worker changes were replayed together from the proven candidate and
committed as `0dad9ad94c23fb43abac420bf0c7feca5e35ba3d`; the combined focused gate passed `394`
tests in `liangjiahao/vllm-ascend-ut`.

### Task 3: Implement group-local Worker sessions, transfers, and failures

**Files:**
- Modify: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py`
- Modify: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- Modify: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/mooncake_session_tracker.py`
- Create: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/group_block_id.py`
- Modify: `vllm_ascend/patch/__init__.py`
- Create: `vllm_ascend/patch/platform/patch_group_block_failures.py`
- Test: `tests/ut/distributed/ascend_store/test_pool_worker.py`
- Test: `tests/ut/distributed/ascend_store/test_kv_transfer.py`
- Test: `tests/ut/distributed/ascend_store/test_mooncake_session_tracker.py`
- Create: `tests/ut/distributed/ascend_store/test_group_block_id.py`
- Create: `tests/ut/patch/platform/test_patch_group_block_failures.py`

**Interfaces:**
- Consumes: `GroupBlockKeys`, collaborator group plans/builders, and Worker-owned session cleanup.
- Produces: group-specific put/get start, ranged offsets, commit/revoke, tracker entries, and encoded
  invalid block IDs accepted by vLLM failure handling.

- [x] **Step 1: Add failing multi-group Worker and transfer tests**

Add `test_prepare_mooncake_put_sessions_use_group_keys_and_sizes`,
`test_prepare_mooncake_get_sessions_merge_all_groups`,
`test_multi_group_range_save_uses_group_layer_offsets`,
`test_multi_group_range_load_accepts_two_tasks_for_one_physical_layer`,
`test_multi_group_commits_at_each_group_last_layer`, and
`test_multi_group_failure_preserves_other_group_rows`.

```python
assert store.put_start_calls == [
    (["model@0@hash@0"], [group0_page * group0_layers]),
    (["model@1@hash@0"], [group1_page * group1_layers]),
]
assert first_group_offsets == [[group0_layer_index * group0_page]]
assert second_group_offsets == [[group1_layer_index * group1_page]]
```

- [x] **Step 2: Run focused tests and confirm failures**

```bash
python3 -m pytest -q -p no:cacheprovider \
  tests/ut/distributed/ascend_store/test_pool_worker.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py \
  tests/ut/distributed/ascend_store/test_mooncake_session_tracker.py
```

- [x] **Step 3: Port the proven group-local semantics from `1800d56`**

Use these exact reference reads and preserve current collaborator code around each hunk:

```bash
git show 1800d56 -- vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py
git show 1800d56 -- vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py
git show 1800d56 -- vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/mooncake_session_tracker.py
git show 1800d56 -- vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/group_block_id.py
```

Keep session tracker keys group-qualified, build each group's shared data with its own block IDs,
call `build_addrs(..., task.layer_idx_in_group)`, allow multiple group tasks per physical layer,
and commit each group at that group's last participating layer.

Encode invalid IDs without changing the external connector interface:

```python
_GROUP_BLOCK_ID_SHIFT = 32


def encode_group_block_id(group_id: int, block_id: int) -> int:
    return (group_id << _GROUP_BLOCK_ID_SHIFT) | block_id
```

- [x] **Step 4: Run focused tests and commit**

```bash
python3 -m pytest -q -p no:cacheprovider \
  tests/ut/distributed/ascend_store/test_pool_worker.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py \
  tests/ut/distributed/ascend_store/test_mooncake_session_tracker.py \
  tests/ut/distributed/ascend_store/test_group_block_id.py \
  tests/ut/patch/platform/test_patch_group_block_failures.py
git commit -s -m "feat(kv_pool): support Mooncake multi-group sessions"
```

Execution note: the port was resolved commit-by-commit against the collaborator transfer
architecture and committed as `0dad9ad94c23fb43abac420bf0c7feca5e35ba3d`. Ruff and format checks
passed for all 17 touched Python files; focused tests passed `394`.

### Task 4: Bind ranged-row ownership and isolate request-local failures

**Files:**
- Modify: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py`
- Modify: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- Test: `tests/ut/distributed/ascend_store/test_config_data.py`
- Test: `tests/ut/distributed/ascend_store/test_kv_transfer.py`

**Interfaces:**
- Consumes: group-local `LayerRangeReqMeta` and Mooncake `batch_copy_get` adapter.
- Produces: immutable `LayerRangeRow` plus a compatibility constructor and request-local failure
  isolation.

- [x] **Step 1: Add failing row-invariant and subgroup-failure tests**

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

Test first/middle/last request exceptions plus short, long, and non-integer results. Assert later
request batches still execute and only rows belonging to the failed request become invalid.

- [x] **Step 2: Run focused tests and confirm failures**

```bash
python3 -m pytest -q -p no:cacheprovider \
  tests/ut/distributed/ascend_store/test_config_data.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py
```

- [x] **Step 3: Implement the deep ranged-row module**

`LayerRangeReqMeta` stores `tuple[LayerRangeRow, ...]` as its invariant. Its legacy positional
constructor validates all parallel inputs once and converts them into rows; read-only compatibility
properties expose `keys`, `block_ids`, `all_buffers`, `all_sizes`, `all_offsets`, and
`row_req_ids`. `LayerBatchBuilder` constructs rows directly.

Catch `batch_copy_get` exceptions and `BatchResultShapeError` inside each request subgroup, mark
only those subgroup indices invalid, remove only those indices from that group's active set, and
continue. Shared metadata corruption remains a transfer-task abort.

- [x] **Step 4: Run focused tests and commit**

```bash
python3 -m pytest -q -p no:cacheprovider \
  tests/ut/distributed/ascend_store/test_config_data.py \
  tests/ut/distributed/ascend_store/test_kv_transfer.py
git commit -s -m "fix(kv_pool): isolate Mooncake ranged row failures"
```

Execution note: committed as `fdd0713e607ab919e08272e81f2925f191de678d`. The focused gate
passed `150` tests, including first/middle/last request failures for exception, short, long, and
non-integer Backend results; Ruff and format checks passed for all four touched files.

### Task 5: Centralize audit emission and correct Client documentation

**Files:**
- Create: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/range_debug.py`
- Modify: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- Modify: `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py`
- Modify: `docs/source/user_guide/feature_guide/layerwise_kv_pool.md`
- Create: `tests/ut/distributed/ascend_store/test_range_debug.py`
- Modify: `tests/ut/distributed/ascend_store/test_backend.py`

**Interfaces:**
- Consumes: `VLLM_ASCEND_KVPOOL_RANGE_DEBUG`, logger, and raw transfer result data.
- Produces: `emit_range_event`, `emit_commit_event`, and `emit_whole_key_event`; callers do not know
  feature-gate, JSON formatting, or instrumentation failure behavior.

- [x] **Step 1: Add failing emitter tests**

```python
emit_range_event("load", 2, [[16]], [[32]], [16])
emit_commit_event(2, 1, [0])
emit_whole_key_event("put", 3)
```

Verify disabled, enabled, payload, non-serializable/coercion failure, and logger exception cases.

- [x] **Step 2: Implement the shared audit module and replace duplicated emitters**

```python
def _emit(payload: dict[str, object]) -> None:
    try:
        if not envs.VLLM_ASCEND_KVPOOL_RANGE_DEBUG:
            return
        logger.info("%s %s", RANGE_DEBUG_PREFIX, json.dumps(payload, separators=(",", ":")))
    except Exception:
        return
```

- [x] **Step 3: Correct the public Client contract**

Document `batch_put_session_start`, `batch_put_session_end`, `batch_put_session_revoke`,
`batch_get_session_start`, `batch_get_session_end`, and the two unchanged ranged methods. Explicitly
distinguish these Client methods from internal `Backend.batch_put_start` / `batch_get_start` names.

- [x] **Step 4: Run focused tests and commit**

```bash
python3 -m pytest -q -p no:cacheprovider \
  tests/ut/distributed/ascend_store/test_range_debug.py \
  tests/ut/distributed/ascend_store/test_backend.py \
  tests/ut/test_envs.py
git commit -s -m "refactor(kv_pool): centralize ranged audit events"
```

Execution note: committed as `69819f6ea9a67944c14f749a66bffeba02d0db3f`. The focused gate
passed `178` tests; all six touched Python files passed Ruff and format checks. Documentation now
lists the five `batch_*_session_*` Client methods and the two unchanged ranged Client methods while
retaining the internal `Backend` method names as adapter terminology.

### Task 6: Add a repeatable ranged-transfer performance gate

**Files:**
- Create: `tests/e2e/nightly/single_node/kv_pool/test_mooncake_layerwise_range_performance.py`
- Modify: `docs/source/user_guide/feature_guide/layerwise_kv_pool.md`

**Interfaces:**
- Consumes: a configured Mooncake Client, registered NPU buffers, and environment-provided Master
  and metadata endpoints.
- Produces: a nightly pytest that records ranged save/load throughput and p50/p95 latency for fixed
  layer, row, and request counts, with explicit environment-controlled regression thresholds.

- [x] **Step 1: Add the benchmark with an explicit environment contract**

Use `VLLM_ASCEND_NIGHTLY_MOONCAKE_CONFIG` for the JSON setup path and
`VLLM_ASCEND_NIGHTLY_KVPOOL_MIN_GBPS` / `VLLM_ASCEND_NIGHTLY_KVPOOL_MAX_P95_MS` for thresholds.
Skip only when the external Mooncake/NPU fixture is absent; do not silently pass a configured run.

```python
assert throughput_gbps >= float(os.environ["VLLM_ASCEND_NIGHTLY_KVPOOL_MIN_GBPS"])
assert p95_ms <= float(os.environ["VLLM_ASCEND_NIGHTLY_KVPOOL_MAX_P95_MS"])
```

- [x] **Step 2: Verify collection and document invocation**

```bash
python3 -m pytest --collect-only -q -p no:cacheprovider \
  tests/e2e/nightly/single_node/kv_pool/test_mooncake_layerwise_range_performance.py
```

- [x] **Step 3: Commit**

```bash
git commit -s -m "test(kv_pool): add Mooncake ranged performance gate"
```

Execution note: committed as `f97aed26f25a3427f20bdb7587b720dd6ef25bbf`. The CPU-only Pod
collected exactly one test with `--confcutdir` and verified its unconfigured skip behavior; Ruff,
format, and `py_compile` passed. The real NPU/Mooncake benchmark was not executed in the CPU Pod and
remains a required nightly-runner gate with explicit configuration and thresholds.

### Task 7: Run source verification

**Files:**
- Verify all modified source and test files.

**Interfaces:**
- Consumes: completed WIP tree.
- Produces: focused and full test evidence plus static/history checks.

- [x] **Step 1: Run focused tests in `liangjiahao/vllm-ascend-ut`**

```bash
features/kv-pool-layerwise-reuse/deployment/run-vllm-ascend-ut.sh -- \
  python3 -m pytest -q -p no:cacheprovider tests/ut/distributed/ascend_store
```

- [x] **Step 2: Run static gates**

```bash
mapfile -t review_python_files < <(git diff --name-only 14beaf161..HEAD | rg '\.py$')
mapfile -t review_source_files < <(git diff --name-only 14beaf161..HEAD | rg '^vllm_ascend/.*\.py$')
/workspace/tools/ruff check "${review_python_files[@]}"
/workspace/tools/ruff format --check "${review_python_files[@]}"
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile "${review_source_files[@]}"
git diff --check d28c52958...HEAD
```

- [x] **Step 3: Verify history and protected refs**

```bash
git log --format='%H %s%n%b' 14beaf161..HEAD
git rev-list --merges 14beaf161..HEAD
git rev-parse feature/mooncake-layerwise-kv-pool
git rev-parse origin/feature/mooncake-layerwise-kv-pool
git rev-parse feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723
git rev-parse origin/feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723
```

Execution note: final CPU/mock verification passed `534` tests in the clean tar-synced
`liangjiahao/vllm-ascend-ut` checkout. All 22 Python diff files passed Ruff and format checks; all
12 changed source files passed `py_compile`; `git diff --check` passed. The five WIP commits since
`14beaf161` are signed and contain no merge commits. Protected local/origin refs remain
`b5b65d9bb` and `d28c52958` respectively.

### Task 8: Record WIP state

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/review-decisions.md`
- Modify: `features/kv-pool-layerwise-reuse/repo-state.md`
- Modify: `features/kv-pool-layerwise-reuse/sync-log.md`
- Modify: `workspace.lock.json` only if the control branch is intentionally moved to the WIP source.

**Interfaces:**
- Consumes: final source commits and verification output.
- Produces: recoverable WIP branch/SHA, decision status, test evidence, and explicit residual NPU
  benchmark status.

- [x] **Step 1: Mark implemented findings without calling unrun gates passed**

Record each of `SP1`, `SP2`, `ST1`, `ST2`, `ST3`, `ST4`, and `ST5` with its owning source commit
and verification result. Keep the old public/merge branch state separate from WIP state.

- [x] **Step 2: Commit control state narrowly**

```bash
git add features/kv-pool-layerwise-reuse/review-decisions.md \
  features/kv-pool-layerwise-reuse/repo-state.md \
  features/kv-pool-layerwise-reuse/sync-log.md \
  features/kv-pool-layerwise-reuse/implementation-plans/2026-08-04-wip-review-findings.md
git commit -s -m "docs(review): record Mooncake WIP findings implementation"
```

Do not stage `deployment_yaml/` or `dockerfile.vllm23`.

Execution note: `review-decisions.md`, `repo-state.md`, `sync-log.md`, and `workspace.lock.json`
were prepared for WIP HEAD `f97aed26f25a3427f20bdb7587b720dd6ef25bbf`. Source publication was
attempted as a normal push to `origin/wip/mooncake-review-findings-d28c529` but GitHub returned
HTTP 403 because the shared workspace token authenticates `swallowCXY`, which lacks write access
to `jiahaoliang/vllm-ascend`. No remote ref was created or modified. Control validation and the
narrow local state commit continue independently; remote publication remains credential-blocked.
`pwsh` and `powershell` are unavailable on this host, so the Linux equivalents of
`lock-repos.ps1`, `status-all.ps1`, and `validate-workspace.ps1` were run from the scripts' exact
checks and passed. Control `git diff --check`, lock JSON parsing, WIP DCO/history checks, and
protected-ref checks also passed.
The subsequent normal control push to `origin/kv-pool-layerwise-reuse` also returned HTTP 403 for
the same authenticated account. The control remote remained
`bc75cb6adf7aa3dd9bc0a2089e8ff6efa94c3a0f`; neither target repository was modified remotely.
After the workspace-only token was replaced, the source WIP branch was normally pushed without
force. Live `git ls-remote` and the local HEAD both returned
`f97aed26f25a3427f20bdb7587b720dd6ef25bbf`; left/right count was `0 0`. The earlier 403 entries
remain as historical execution evidence and no longer describe the current source publication
state.
The refreshed control state was committed as `b22dff4080dcc7e89a191ad41882adb6c8eee2a5` and normally
fast-forward pushed from checkpoint `bc75cb6adf7aa3dd9bc0a2089e8ff6efa94c3a0f`. Live
`git ls-remote` returned `b22dff4080dcc7e89a191ad41882adb6c8eee2a5`; left/right count was
`0 0`. A metadata-only follow-up records that completed publication check.
