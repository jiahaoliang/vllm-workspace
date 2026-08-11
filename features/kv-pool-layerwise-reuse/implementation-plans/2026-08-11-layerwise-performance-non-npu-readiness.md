# Layerwise Performance Non-NPU Readiness Implementation Plan

> **For agentic workers:** Execute this plan inline, task by task. Do not start NPU serving, correctness traffic, or performance traffic while Kubernetes does not advertise the required physical Ascend910 resources.

**Goal:** Finish every non-NPU prerequisite for rerunning the frozen five-point Mooncake layerwise performance characterization from vLLM-Ascend `57d3c214e642cdbb529400f0742d1a98a8d38708` on the single node `m1`.

**Architecture:** Keep the existing five-point contract and fail-closed handoff. Parameterize the performance runner's NPU node while retaining `n1` as its default, render all performance resources onto the selected node, and create an attempt contract before AISBench can send traffic. Build a native ARM64 image containing the exact three repository commits, then use only CPU/mock and static checks until the administrator restores Kubernetes NPU registration.

**Tech Stack:** Python 3.12, pytest, Kubernetes, nerdctl, BuildKit, containerd `k8s.io`, AISBench, vLLM, vLLM-Ascend, Mooncake.

## Global Constraints

- Control branch: `kv-pool-layerwise-reuse`; preserve untracked `deployment_yaml/` and `dockerfile.vllm23`.
- Source identity: vLLM `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`, vLLM-Ascend `57d3c214e642cdbb529400f0742d1a98a8d38708`, Mooncake `df3f74ed8ebdb0c935554beea6299a9f11c723e2`.
- Kubernetes workloads use explicit namespace `liangjiahao`; only `buildkitd` uses explicit namespace `default`.
- Test matrix remains exactly DP1, input 16384, c8, warmup 8, formal 64, one attempt: BULK o128/o1, LAYERWISE o128/o1, REUSE3 o1.
- Default performance-runner node remains `n1`; the single-node rerun explicitly passes `--npu-node m1`.
- No NPU server startup, correctness request, AISBench request, or performance traffic is authorized in this plan.
- Preparation evidence must remain compact: store identities, checksums, rendered JSON, and test logs; do not copy image blobs, repository trees, or model weights into `features/**/evidence`.

---

### Task 1: Single-node placement and attempt contract

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/runtime.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/runner.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/fixtures.py`
- Test: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_runtime.py`
- Test: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_runner.py`
- Test: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_fixtures.py`

**Interfaces:**
- Consumes: `runtime.RuntimeInputs`, `runtime.render_resources()`, `runner.RunEnvironment`, `fixtures.write_aisbench_config()`.
- Produces: `runtime.render_resources(..., node_name: str = "n1")`, `runner.run(..., npu_node: str = "n1")`, and an `attempt-contract.json` written and validated before the AISBench command.

- [x] Add failing tests proving `m1` is written to rendered Prefill and Decode Pod specs while the default remains `n1`.
- [x] Add failing tests proving `--npu-node m1` reaches capacity accounting, rendered resources, and `run-contract.json`.
- [x] Add failing tests proving the complete matrix schedules three variant starts and exactly ten AISBench commands in the frozen order.
- [x] Add failing fixture tests for wrong JSONL line count, malformed JSON, missing `question`, wrong exact token count, and checksum mismatch.
- [x] Implement node propagation without changing the default `n1` behavior.
- [x] Write `attempt-contract.json` with phase, point identity, input/output tokens, request count, concurrency, dataset line count, and SHA-256 before rendering the AISBench config.
- [x] Validate the attempt contract before returning any command marked `sends_inference=True`.
- [x] Run `python3 -m pytest -q performance/tests/test_runtime.py performance/tests/test_fixtures.py performance/tests/test_runner.py` in the CPU-only UT Pod and require zero failures.

### Task 2: CPU/mock and static source gates

**Files:**
- Read: `features/kv-pool-layerwise-reuse/deployment/performance/run-performance-ut.sh`
- Read: `features/kv-pool-layerwise-reuse/deployment/run-vllm-ascend-ut.sh`
- Record: `/tmp/layerwise-non-npu-readiness-20260811/`

**Interfaces:**
- Consumes: clean vLLM-Ascend checkout at `57d3c214e` and the completed Task 1 tooling.
- Produces: compact logs and exit-code records for every CPU/static gate.

- [x] Run the complete performance harness with bytecode and pytest cache disabled.
- [x] Run the focused self-load regression and Mooncake layer-session tests.
- [x] Run the complete AscendStore CPU/mock suite.
- [x] Run targeted Ruff core/import lint, Python compilation, and `git diff --check`; remove formatter-only churn while proving Python token identity.
- [x] Replay the committed formal performance evidence checksum manifests and regenerate its report into `/tmp` without changing historical evidence.
- [x] Write a summary JSON containing commands, exact source commits, counts, exit codes, and explicit NPU exclusions.

### Task 3: Exact native ARM64 candidate image

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/Dockerfile.a2`
- Modify: `features/kv-pool-layerwise-reuse/nerdctl-build.md`
- Record: `/tmp/layerwise-non-npu-readiness-20260811/image/`

**Interfaces:**
- Consumes: the three frozen repository commits and `BUILDKIT_HOST=kube-pod://buildkitd?namespace=default`.
- Produces: a `linux/arm64` candidate reference, manifest digest, config digest, exact source labels, native-module metadata, and runtime file hashes.

- [x] Update the Dockerfile's default vLLM-Ascend pin to `57d3c214e642cdbb529400f0742d1a98a8d38708` and extend static checks only where they can run without a mounted NPU driver.
- [x] Recreate `default/buildkitd` from the previously verified manifest, pin it to `m1`, and prove its worker platform is `linux/arm64`.
- [x] Build through the remote-clone Dockerfile flow with all three exact commit build arguments and a new immutable tag.
- [x] Verify platform, manifest/config digests, OCI labels, embedded Git HEADs, Mooncake session API symbols, ELF architecture, and SHA-256 of the vLLM-Ascend files changed by `535555917..57d3c214e`.
- [x] Keep image blobs in containerd `k8s.io`; archive only compact identity and checksum records.

### Task 4: CPU-only AISBench preparation on m1

**Files:**
- Read: `features/kv-pool-layerwise-reuse/deployment/performance/00-aisbench-client.yaml`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/README.md`
- Record: `/tmp/layerwise-non-npu-readiness-20260811/aisbench/`

**Interfaces:**
- Consumes: the exact candidate image identity from Task 3 and the `prepare` subcommand.
- Produces: a retained CPU-only `liangjiahao/layerwise-performance-aisbench` Pod, exact tokenizer identity, and checksummed 8/64 fixtures.

- [x] Validate the AISBench manifest requests neither `huawei.com/Ascend910` nor `huawei.com/vnpu-number` and pins `nodeName: m1`.
- [x] Run `prepare` without inference endpoint contact or serving-workload mutation.
- [x] Verify 8 warmup plus 64 formal unique request IDs, valid UTF-8 JSONL, disjoint partitions, exact 16384-token round trips, and complete checksum replay.
- [x] Verify the pinned AISBench commit/package set and candidate rootfs marker used by the retained client Pod.

### Task 5: Fail-closed handoff and administrator readiness

**Files:**
- Create: `features/kv-pool-layerwise-reuse/deployment/performance/check-npu-readiness.py`
- Create: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_check_npu_readiness.py`
- Modify: `features/kv-pool-layerwise-reuse/performance-validation-handoff.md`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/README.md`

**Interfaces:**
- Consumes: Kubernetes Node/Pod JSON and all identities/results from Tasks 1-4.
- Produces: a read-only readiness report and generation 11 `BLOCKED` handoff for source `57d3c214e`.

- [x] Test that readiness requires node `m1`, exactly eight allocatable physical `huawei.com/Ascend910` resources, and at least four free after non-terminal Pod requests; ignore `huawei.com/vnpu-number`.
- [x] Implement a read-only checker that never mutates cluster resources.
- [x] Run the checker against current cluster JSON and record the expected blocked result while NPU registration is absent.
- [x] Replace the stale generation 10 authorization with generation 11, `status: BLOCKED`, `ready: false`, the exact candidate identity, completed CPU gates, `m1` topology, and pending NPU correctness/performance gates.
- [x] Validate that `performance.handoff` rejects generation 11 before issuing any cluster command or traffic.

### Task 6: Completion audit and publication

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/repo-state.md`
- Modify: `features/kv-pool-layerwise-reuse/sync-log.md`
- Modify: `workspace.lock.json` only if a nested source commit changes.

**Interfaces:**
- Consumes: all prior task outputs.
- Produces: a pushed control-repo commit containing only approved preparation tooling, documentation, and compact identity records.

- [x] Recheck control and nested repository branches, remotes, clean state, lock equality, and origin left/right counts.
- [x] Run the full performance harness again after documentation and handoff edits.
- [x] Run `git diff --check` and inspect the complete staged diff for unrelated or oversized artifacts.
- [x] Commit without agent attribution, push `origin/kv-pool-layerwise-reuse`, and verify remote equality.
- [x] Report the exact image reference/digests, CPU gate counts, retained Pod state, readiness result, and the NPU-only work still blocked on the administrator.
