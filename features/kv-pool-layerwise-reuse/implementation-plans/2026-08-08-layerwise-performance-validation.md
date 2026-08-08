# Mooncake Layerwise Performance Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Prepare, gate, execute, verify, and publish the complete DP1/DP2 AISBench characterization defined by 2026-08-08-layerwise-performance-validation-design.md without human intervention.

**Architecture:** A feature-local Python package owns the immutable experiment contract, handoff verification, exact-token fixtures, structured Kubernetes rendering, server-image adoption, resumable orchestration, and fail-closed reporting. A thin shell entrypoint invokes prepare before functional readiness and run only after handoff, source, image, hardware, correctness, and checksum gates pass. Existing proxy, Mooncake Master, server Deployments, step recorder, and stress lifecycle patterns are reused without modifying functional production source.

**Tech Stack:** Python 3.12 standard library, pytest, transformers, AISBench 3.1.0 at commit 3fd27b4a5fd022fcb5484fb084307f49955491ba, uv 0.12.3, Kubernetes, jq, nerdctl/containerd namespace k8s.io, vLLM OpenAI streaming API, Mooncake metrics, Ascend910 telemetry.

## Global Constraints

- Work from /root/ljh/vllm-workspace on control branch kv-pool-layerwise-reuse.
- Preserve every other-session edit and unrelated deployment_yaml/, dockerfile.vllm23, and research snapshot. Never use git add . or git add -A.
- Put new performance code under features/kv-pool-layerwise-reuse/deployment/performance/ and tests under its tests/ child.
- Use namespace liangjiahao explicitly for every workload command. Never delete the namespace.
- The AISBench Pod is CPU-only on m1 and requests neither huawei.com/Ascend910 nor huawei.com/vnpu-number.
- Server Pods run on n1. Count physical huawei.com/Ascend910 capacity separately from vnpu-number.
- Do not build the server image with Dockerfile, BuildKit, nerdctl build, or docker build. Consume the handoff image or apply its exact Python patch and use nerdctl commit.
- Use the same derived server image for BULK, LAYERWISE, and REUSE3.
- Before handoff readiness, only prepare actions are allowed. No NPU server mutation, canary, or performance traffic is allowed.
- Run every CPU/mock pytest target in liangjiahao/vllm-ascend-ut via tar synchronization with bytecode and pytest cache disabled.
- Results are raw characterization only. Identity, correctness, process health, client capacity, and evidence completeness are hard gates; performance values have no PASS/FAIL threshold.
- A retry gets a new attempt ID and never overwrites an artifact directory.
- Stop a formal run on a confirmed production-source defect. Repair only performance tooling, manifests, parsers, checkers, or documentation.
- Every meaningful implementation node is committed with only its owned paths staged.

---

## File Structure

Create:

~~~text
features/kv-pool-layerwise-reuse/deployment/performance/
  __init__.py
  README.md
  00-aisbench-client.yaml
  handoff.py
  contract.py
  fixtures.py
  runtime.py
  image.py
  runner.py
  report.py
  run-performance-test.sh
  tests/
    test_handoff.py
    test_contract.py
    test_fixtures.py
    test_runtime.py
    test_image.py
    test_runner.py
    test_report.py
~~~

Responsibilities:

- handoff.py parses, validates, waits for, and snapshots the functional handoff.
- contract.py defines variants, topologies, points, sample counts, rotations, stable validity, and adaptive stopping.
- fixtures.py creates exact-token, first-block-unique JSONL fixtures and AISBench point configs.
- runtime.py renders ConfigMap and Deployment JSON by structured mutation of captured live objects.
- image.py accepts or materializes the exact handed-off server image without a full build.
- runner.py implements prepare, wait, and resumable run, plus lifecycle, metrics, failure capture, and restoration.
- report.py verifies the evidence tree and renders per-repetition raw tables and direct ratios.
- run-performance-test.sh only resolves paths and invokes python3 -m performance.runner.

Also create:

~~~text
features/kv-pool-layerwise-reuse/references/snapshots/issue-1-performance-validation-2026-08-08.md
features/kv-pool-layerwise-reuse/references/snapshots/aisbench-performance-contract-2026-08-08.md
features/kv-pool-layerwise-reuse/layerwise-performance-validation-2026-08-08.md
~~~

Update references/sources.md and evidence/README.md. Generated evidence uses the actual UTC run ID under evidence/layerwise-performance-$RUN_ID/.

---

### Task 1: Fail-Closed Handoff Listener

**Files:**
- Create: features/kv-pool-layerwise-reuse/deployment/performance/__init__.py
- Create: features/kv-pool-layerwise-reuse/deployment/performance/handoff.py
- Test: features/kv-pool-layerwise-reuse/deployment/performance/tests/test_handoff.py

**Interfaces:**
- Produces HandoffState, parse_handoff(path), validate_handoff(state, workspace), and wait_for_ready(path, workspace, poll_seconds, observations).
- Consumes the committed Markdown handoff, named Git repositories, image identity, and functional evidence.

- [ ] **Step 1: Write failing state and authorization tests**

~~~python
def test_waiting_handoff_is_rejected(tmp_path):
    path = write_handoff(tmp_path, status="WAITING_FOR_FUNCTIONAL_VALIDATION",
                         ready=False, generation=0,
                         placeholders_remaining=True)
    state = handoff.parse_handoff(path)
    assert "status is not READY_FOR_PERFORMANCE_VALIDATION" in \
        handoff.validate_handoff(state, tmp_path)

def test_ready_handoff_requires_decode_companion_authorization(tmp_path):
    path = write_ready_handoff(
        tmp_path, authorized_roles=["kv_producer", "kv_both"])
    errors = handoff.validate_handoff(handoff.parse_handoff(path), tmp_path)
    assert any("no-reuse pure-consumer Decode companion" in e for e in errors)
~~~

- [ ] **Step 2: Run the focused target in the UT Pod and prove red**

~~~bash
features/kv-pool-layerwise-reuse/deployment/run-vllm-ascend-ut.sh -- \
  python3 -m pytest -q -p no:cacheprovider \
  features/kv-pool-layerwise-reuse/deployment/performance/tests/test_handoff.py
~~~

Expected: collection fails because performance.handoff does not exist.

- [ ] **Step 3: Implement structured state parsing**

~~~python
@dataclass(frozen=True)
class HandoffState:
    path: Path
    digest: str
    status: str
    ready: bool
    generation: int
    placeholders_remaining: bool
    source_commits: dict[str, str]
    image_fields: dict[str, str]
    gates: dict[str, str]
    evidence_fields: dict[str, str]
    authorized_scope: tuple[str, ...]

REQUIRED_SCOPE = (
    "backend=mooncake",
    "layerwise_num_shared_buffers=3",
    "kv_producer",
    "no-reuse pure-consumer Decode companion",
    "liangjiahao",
)
~~~

Parse scalar YAML front matter and Markdown tables by named headers. Reject duplicate or missing rows, PENDING actual fields, non-PASS required gates, missing scope, Git/remote mismatch, image mismatch, and failed sha256sum -c replay.

- [ ] **Step 4: Add generation and checksum tests**

~~~python
def test_generation_change_invalidates_ready_observation(tmp_path):
    first = handoff.parse_handoff(write_ready_handoff(tmp_path, generation=1))
    second = handoff.parse_handoff(
        write_ready_handoff(tmp_path, generation=2,
                            image_digest="sha256:changed"))
    assert (first.generation, first.digest) != (second.generation, second.digest)

def test_bad_evidence_checksum_is_rejected(tmp_path):
    path = write_ready_handoff_with_evidence(tmp_path)
    (tmp_path / "evidence" / "identity.json").write_text("changed")
    errors = handoff.validate_handoff(handoff.parse_handoff(path), tmp_path)
    assert any("SHA256SUMS" in error for error in errors)
~~~

- [ ] **Step 5: Implement check and wait CLI**

check writes one JSON result. wait polls every 10 seconds and appends UTC timestamp, inode, mtime, size, SHA256, generation, status, ready, and validation errors to observations.jsonl. BLOCKED is recorded but never accepted. Every content or generation change triggers full revalidation.

- [ ] **Step 6: Run tests and commit**

~~~bash
git add -- \
  features/kv-pool-layerwise-reuse/deployment/performance/__init__.py \
  features/kv-pool-layerwise-reuse/deployment/performance/handoff.py \
  features/kv-pool-layerwise-reuse/deployment/performance/tests/test_handoff.py
git commit -m "test(perf): add fail-closed handoff listener"
~~~

### Task 2: Immutable Experiment Contract And Matrix

**Files:**
- Create: features/kv-pool-layerwise-reuse/deployment/performance/contract.py
- Test: features/kv-pool-layerwise-reuse/deployment/performance/tests/test_contract.py

**Interfaces:**
- Produces Variant, Topology, WorkloadPoint, PointResult, build_matrix(), sample_counts(), stable_measurement_valid(), and adaptive_stop().
- Pure module with no environment dependency.

- [ ] **Step 1: Write exact matrix tests**

~~~python
def test_variant_contract():
    assert VARIANTS["bulk"].prefill["use_layerwise"] is False
    assert VARIANTS["bulk"].prefill["layerwise_prefetch_layers"] == 3
    assert "layerwise_num_shared_buffers" not in VARIANTS["layerwise"].prefill
    assert VARIANTS["reuse3"].prefill["layerwise_num_shared_buffers"] == 3
    assert "layerwise_num_shared_buffers" not in VARIANTS["reuse3"].decode

def test_outputs_and_concurrency():
    assert outputs_for("bulk") == (1, 128)
    assert outputs_for("reuse3") == (1,)
    assert TOPOLOGIES["dp1"].concurrency == (1, 2, 4, 8, 16, 32)
    assert TOPOLOGIES["dp2"].concurrency == (2, 4, 8, 16, 32, 64)
~~~

- [ ] **Step 2: Prove red in the UT Pod**

Expected: import failure for performance.contract.

- [ ] **Step 3: Implement frozen dataclasses and rotations**

~~~python
@dataclass(frozen=True)
class WorkloadPoint:
    topology: str
    input_tokens: int
    output_tokens: int
    variant: str
    concurrency: int

INPUT_TOKENS = (4096, 16384, 32768)
DP1_ROTATION = {
    4096: ("bulk", "layerwise", "reuse3"),
    16384: ("layerwise", "reuse3", "bulk"),
    32768: ("reuse3", "bulk", "layerwise"),
}
DP2_ROTATION = {length: tuple(reversed(order))
                for length, order in DP1_ROTATION.items()}
~~~

Freeze block size 128, max model length 65536, max batched tokens 1024, max sequences 64, GPU utilization 0.90, TP2, PP/PCP/DCP1, chunked Prefill, and topology NPU counts 2+2 or 4+2.

Implement soft saturation as two consecutive points where throughput gain is
strictly below 5 percent and P95 latency growth is strictly above 50 percent
relative to the immediately preceding point. Any OOM, worker exit, timeout,
malformed response, or non-2xx response is a hard stop for higher concurrency
in that scan.

- [ ] **Step 4: Add sample and stop tests**

~~~python
@pytest.mark.parametrize("c,warmup,formal",
                         [(1, 8, 32), (4, 8, 32),
                          (16, 32, 128), (64, 128, 512)])
def test_sample_counts(c, warmup, formal):
    assert sample_counts(c) == (warmup, formal, 3)

def test_soft_stop_requires_two_points():
    history = [point(100, 100), point(104, 160), point(107, 250)]
    assert adaptive_stop(history, hard_failure=False).stop

def test_stable_duration_rule():
    assert stable_measurement_valid(900, 3001)
    assert not stable_measurement_valid(1001, 3000)
~~~

- [ ] **Step 5: Run tests and commit**

~~~bash
git add -- \
  features/kv-pool-layerwise-reuse/deployment/performance/contract.py \
  features/kv-pool-layerwise-reuse/deployment/performance/tests/test_contract.py
git commit -m "test(perf): freeze layerwise benchmark matrix"
~~~

### Task 3: Exact-Token Fixtures And AISBench Configs

**Files:**
- Create: features/kv-pool-layerwise-reuse/deployment/performance/fixtures.py
- Test: features/kv-pool-layerwise-reuse/deployment/performance/tests/test_fixtures.py

**Interfaces:**
- Produces PromptRecord, FixtureManifest, find_roundtrip_tokens(), build_prompt(), write_fixture(), and write_aisbench_config().
- Consumes the frozen tokenizer and WorkloadPoint.

- [ ] **Step 1: Write fake-tokenizer red tests**

~~~python
def test_exact_roundtrip_and_unique_first_block():
    records = [fixtures.build_prompt(FakeTokenizer(), 4096, i, 20260808)
               for i in range(4)]
    assert all(len(record.token_ids) == 4096 for record in records)
    assert all(FakeTokenizer().encode(record.text) == list(record.token_ids)
               for record in records)
    assert len({record.token_ids[:128] for record in records}) == 4

def test_slices_are_disjoint(tmp_path):
    manifest = fixtures.write_fixture(
        FakeTokenizer(), 4096, 32, 20260808, tmp_path)
    assert set(manifest.warmup_ids).isdisjoint(manifest.formal_ids[0])
    assert set(manifest.formal_ids[0]).isdisjoint(manifest.formal_ids[1])
~~~

- [ ] **Step 2: Prove red in the UT Pod**

- [ ] **Step 3: Implement deterministic generation**

Find non-special IDs whose one-token decode re-encodes to the same ID. Encode request_index in base-N at the start of the first 128-token block, fill the rest from a seeded stable cycle, decode, re-encode, and reject any change. Write JSONL rows with question, empty answer, and request_id. Write tokenizer hashes, IDs, counts, first-block hashes, prompt hashes, seed, partition, and fixture SHA256 to the manifest.

- [ ] **Step 4: Implement AISBench config generation**

Generate a compiled Python config using VLLMCustomAPI, CustomDataset, PromptTemplate, ZeroRetriever, and GenInferencer:

~~~python
models = [dict(
    attr="service", type=VLLMCustomAPI, stream=True, retry=0,
    url="http://vllm-proxy-service:8000/",
    model="vllm-ascend/DeepSeek-V2-Lite-W8A8",
    path="/root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8",
    max_out_len=output_tokens, batch_size=concurrency, request_rate=0,
    generation_kwargs=dict(temperature=0, ignore_eos=True),
)]
~~~

Point the dataset to the exact JSONL slice. Validate config text with compile() before writing.
Set reader input_columns to question, output_column to answer, and the
PromptTemplate template to exactly {question}; no Question/Answer prefix,
suffix, or chat template may change the verified prompt token count.

- [ ] **Step 5: Add corruption/config tests, run, and commit**

Verify tokenizer/fixture changes break replay, retry is zero, streaming is true, and output/concurrency equal the point.

~~~bash
git add -- \
  features/kv-pool-layerwise-reuse/deployment/performance/fixtures.py \
  features/kv-pool-layerwise-reuse/deployment/performance/tests/test_fixtures.py
git commit -m "test(perf): add deterministic AISBench fixtures"
~~~

### Task 4: Structured Runtime Rendering

**Files:**
- Create: features/kv-pool-layerwise-reuse/deployment/performance/runtime.py
- Test: features/kv-pool-layerwise-reuse/deployment/performance/tests/test_runtime.py

**Interfaces:**
- Produces RuntimeInputs, RenderedResources, render_resources(), server_argv(), and validate_unique_difference().
- Consumes captured live Deployment/ConfigMap JSON, contract constants, and handed-off image.

- [ ] **Step 1: Write red topology and uniqueness tests**

~~~python
def test_topology_allocations(base_inputs):
    dp1 = runtime.render_resources(
        base_inputs, point("dp1", "bulk"), "image@sha256:x")
    dp2 = runtime.render_resources(
        base_inputs, point("dp2", "bulk"), "image@sha256:x")
    assert (dp1.prefill_npus, dp1.decode_npus) == (2, 2)
    assert (dp2.prefill_npus, dp2.decode_npus) == (4, 2)

def test_reuse3_only_adds_prefill_shared_buffers(base_inputs):
    left = runtime.render_resources(
        base_inputs, point("dp1", "layerwise"), "image@sha256:x")
    right = runtime.render_resources(
        base_inputs, point("dp1", "reuse3"), "image@sha256:x")
    assert runtime.validate_unique_difference(
        {"layerwise": left, "reuse3": right}) == []
~~~

- [ ] **Step 2: Prove red, then implement JSON rendering**

Deep-copy live objects and change only derived image, performance ConfigMap volume, physical NPU requests/limits, generated start scripts, Prefill DP arguments, and variant KV JSON. Preserve all mounts, probes, commands, services, nodes, and non-experimental environment. Emit canonical JSON, not YAML substitution.

- [ ] **Step 3: Implement runtime identity**

Generated check-runtime.py emits variant, topology, image digest, role, DP/TP, model, prefetch depth, shared buffers, max sequences, max batched tokens, and imported source path. Require REUSE3 Prefill to report 27 layers, five physical slots, and the memory factor; Decode reports no reuse. Require whole-key-only BULK and ranged/no-whole-key LAYERWISE/REUSE3.

- [ ] **Step 4: Run tests and commit**

~~~bash
git add -- \
  features/kv-pool-layerwise-reuse/deployment/performance/runtime.py \
  features/kv-pool-layerwise-reuse/deployment/performance/tests/test_runtime.py
git commit -m "test(perf): render isolated runtime variants"
~~~

### Task 5: Server Image Adoption

**Files:**
- Create: features/kv-pool-layerwise-reuse/deployment/performance/image.py
- Test: features/kv-pool-layerwise-reuse/deployment/performance/tests/test_image.py

**Interfaces:**
- Produces ImageIdentity, resolve_server_image(), and verify_import().
- Consumes only a validated HandoffState and CommandRunner.

- [ ] **Step 1: Write rebuild-rejection and identity tests**

~~~python
def test_ready_image_avoids_materialization(fake_runner, ready_state):
    identity = image.resolve_server_image(
        ready_state, fake_runner, Path("out"))
    assert identity.reference == ready_state.image_fields["Image reference"]
    assert not any("buildctl" in text or "docker build" in text
                   for text in fake_runner.command_texts)

def test_patch_mode_requires_hash(patch_state):
    patch_state.image_fields["Patched file SHA256"] = ""
    with pytest.raises(image.ImageContractError,
                       match="Patched file SHA256"):
        image.resolve_server_image(
            patch_state, FakeRunner(), Path("out"))
~~~

- [ ] **Step 2: Implement the two authorized modes**

Ready-image mode verifies linux/arm64, manifest digest, base digest, source labels, patched path, and file hash.

Patch mode uses argument arrays for:

~~~text
nerdctl --namespace k8s.io create --name NAME BASE
nerdctl --namespace k8s.io cp PATCH NAME:/vllm-workspace/vllm-ascend/PATH
nerdctl --namespace k8s.io commit NAME DERIVED
nerdctl --namespace k8s.io inspect DERIVED
nerdctl --namespace k8s.io rm NAME
~~~

Validate source/file equality before create and derived import/digest afterward. Cleanup the temporary container in finally. Never invoke build commands.

- [ ] **Step 3: Add failure-cleanup tests, run, and commit**

~~~bash
git add -- \
  features/kv-pool-layerwise-reuse/deployment/performance/image.py \
  features/kv-pool-layerwise-reuse/deployment/performance/tests/test_image.py
git commit -m "test(perf): consume handed-off patch image"
~~~

### Task 6: Resumable Orchestrator

**Files:**
- Create: features/kv-pool-layerwise-reuse/deployment/performance/runner.py
- Create: features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh
- Test: features/kv-pool-layerwise-reuse/deployment/performance/tests/test_runner.py

**Interfaces:**
- Produces prepare, wait, and run CLI; CommandRunner.run(); append-only steps.jsonl and run-state.jsonl.
- Consumes Tasks 1-5 and the existing run-validation-step.sh.

- [ ] **Step 1: Write red authorization tests**

~~~python
def test_prepare_cannot_mutate_server_or_infer(tmp_path):
    fake = FakeCommandRunner()
    runner.prepare(fake, tmp_path)
    assert not any(call.mutates_server or call.sends_inference
                   for call in fake.calls)

def test_run_checks_handoff_before_mutation(tmp_path):
    fake = FakeCommandRunner()
    with pytest.raises(handoff.HandoffError):
        runner.run(fake, waiting_state(), tmp_path)
    assert fake.calls == []
~~~

- [ ] **Step 2: Implement append-only state**

Use attempt IDs such as dp1-4096-bulk-o1-c1-r0-a1. Resume skips only attempts whose terminal state and checksums validate. Invalid/interrupted work creates attempt-2 and retains attempt-1.

- [ ] **Step 3: Implement prepare**

prepare may only inventory, create the m1 CPU client, bootstrap uv 0.12.3, checkout AISBench 3fd27b4a, install its API dependencies in an isolated Python 3.12 environment, capture locks/hashes, run CLI/import/tokenizer/config smoke, and generate offline fixtures/configs. Prove no inference URL was contacted.

Use client Pod name layerwise-performance-aisbench with label
app=layerwise-performance-aisbench, CPU request 4 and limit 8, memory request
16Gi and limit 32Gi, and a 50Gi disk-backed emptyDir. A read-only preflight may
raise these CPU/memory limits only if m1 allocatable capacity proves the exact
values cannot schedule; any change must be applied uniformly and recorded
before formal execution.

- [ ] **Step 4: Implement gated lifecycle functions**

~~~python
capture_pre_run_state()
apply_variant_block(topology, input_tokens, variant, image)
start_engines_and_wait()
run_correctness_canary(point)
reset_master_and_reconnect()
run_aisbench_attempt(point, phase, repetition, request_count)
collect_point_metrics(point, attempt)
stop_engines()
restore_pre_run_state()
~~~

Register signal/exit restoration before the first mutation. Every kubectl apply, exec, logs, rollout, cp, and wait names liangjiahao. Capture failure state before cleanup.

- [ ] **Step 5: Implement point execution**

For each rotated input/variant block, apply once, pass identity/canary, and run applicable output/concurrency points. Reset Master before warmup and every formal repetition. Run exact sample counts. Double RequestCount under a new attempt when stable duration is insufficient. Apply hard/soft adaptive stopping and preserve all attempts.

Sample Prefill/Decode vLLM metrics, Mooncake metrics, client CPU/memory/network,
and per-card utilization/HBM/power/temperature once per second from request
start through the last response. Capture per-DP-rank request count, input
tokens, real context iterations, queue state, and busy/idle duration from the
same attempt window.

- [ ] **Step 6: Test lifecycle ordering**

~~~python
def test_failure_capture_precedes_restore(tmp_path):
    fake = FakeCommandRunner(fail_step="aisbench")
    runner.execute_point(fake, point(), tmp_path)
    assert fake.index("capture-failure") < \
        fake.index("restore-pre-run-state")

def test_three_formal_repetitions_each_have_raw_output(tmp_path):
    fake = FakeCommandRunner()
    runner.execute_point(fake, point(concurrency=4), tmp_path)
    assert fake.count("reset-master") == 4
    assert len(list(tmp_path.glob("**/formal-*/attempt-*/raw"))) == 3
~~~

- [ ] **Step 7: Run tests and commit**

~~~bash
git add -- \
  features/kv-pool-layerwise-reuse/deployment/performance/runner.py \
  features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh \
  features/kv-pool-layerwise-reuse/deployment/performance/tests/test_runner.py
git commit -m "test(perf): add gated resumable benchmark runner"
~~~

### Task 7: Fail-Closed Report And Raw Tables

**Files:**
- Create: features/kv-pool-layerwise-reuse/deployment/performance/report.py
- Test: features/kv-pool-layerwise-reuse/deployment/performance/tests/test_report.py

**Interfaces:**
- Produces validate_evidence(), load_results(), render_report(), and check/render CLI.
- Consumes runner evidence and AISBench JSONL/CSV outputs.

- [ ] **Step 1: Write missing-evidence and drift tests**

~~~python
def test_missing_formal_repetition_is_rejected(valid_tree):
    shutil.rmtree(valid_tree / "points" / POINT / "formal-2")
    assert any("formal repetition 2" in e
               for e in report.validate_evidence(valid_tree))

def test_image_drift_is_rejected(valid_tree):
    mutate_json(valid_tree / "points" / POINT / "identity.json",
                image_digest="sha256:other")
    assert any("image digest" in e
               for e in report.validate_evidence(valid_tree))
~~~

- [ ] **Step 2: Implement evidence validation**

Require handoff/source/image/runtime/client/fixture identity, expected matrix or recorded stop, warmup, three formal raws, stable decision, logs, metrics, NPU samples, Mooncake states, failure state, restoration, and root checksum. Revalidate archived A/B/C differences.

- [ ] **Step 3: Implement raw rendering**

Render one row per formal repetition with Input Token Throughput, Request Throughput, TTFT, E2EL, achieved concurrency, and for output 128 Output Token Throughput, TPOT, and ITL. Render LAYERWISE/BULK, REUSE3/LAYERWISE, and REUSE3/BULK ratios only for valid paired rows. Annotate DP imbalance, client saturation, capacity boundaries, and insufficient duration. Never compute p-values, confidence intervals, outlier filtering, or performance PASS/FAIL.

- [ ] **Step 4: Run tests and commit**

~~~bash
git add -- \
  features/kv-pool-layerwise-reuse/deployment/performance/report.py \
  features/kv-pool-layerwise-reuse/deployment/performance/tests/test_report.py
git commit -m "test(perf): validate and report raw evidence"
~~~

### Task 8: Client Manifest, Docs, Snapshots, And Full Source Gate

**Files:**
- Create: features/kv-pool-layerwise-reuse/deployment/performance/00-aisbench-client.yaml
- Create: features/kv-pool-layerwise-reuse/deployment/performance/README.md
- Create: features/kv-pool-layerwise-reuse/references/snapshots/issue-1-performance-validation-2026-08-08.md
- Create: features/kv-pool-layerwise-reuse/references/snapshots/aisbench-performance-contract-2026-08-08.md
- Modify: features/kv-pool-layerwise-reuse/references/sources.md
- Test: test_runner.py

**Interfaces:**
- Produces the reviewed prepare/wait/run operational contract.

- [ ] **Step 1: Add manifest static tests**

Require namespace liangjiahao, node m1, exact base image, sleep infinity, writable emptyDir, explicit CPU/memory resources, and absence of both NPU keys.

- [ ] **Step 2: Create manifest and README**

Document exact prepare, wait, run, resume, restore, and checker commands. State that chat cannot authorize run and that run always rechecks handoff. Document the no-BuildKit image policy.

- [ ] **Step 3: Save primary-source snapshots**

Issue snapshot records exact configurations and AISBench requirement. AISBench snapshot records commit 3fd27b4a, supported Python versions, batch_size, request_rate, RequestCount, streaming metrics, and stable duration rule, with source paths. Add source and snapshot links to references/sources.md.

- [ ] **Step 4: Run the full performance CPU gate**

~~~bash
features/kv-pool-layerwise-reuse/deployment/run-vllm-ascend-ut.sh -- \
  python3 -m pytest -q -p no:cacheprovider \
  features/kv-pool-layerwise-reuse/deployment/performance/tests
~~~

Also run Python compilation, changed-file Ruff, shell syntax, git diff --check, and a static namespace scan.

- [ ] **Step 5: Commit only preparation paths**

~~~bash
git add -- \
  features/kv-pool-layerwise-reuse/deployment/performance \
  features/kv-pool-layerwise-reuse/references/sources.md \
  features/kv-pool-layerwise-reuse/references/snapshots/issue-1-performance-validation-2026-08-08.md \
  features/kv-pool-layerwise-reuse/references/snapshots/aisbench-performance-contract-2026-08-08.md
git commit -m "feat(perf): prepare Mooncake layerwise benchmark"
~~~

### Task 9: Execute Preparation

**Generated:** /tmp/layerwise-performance-prepare-$PREPARE_ID/

- [ ] **Step 1: Re-audit kube context, m1, client name, and base image**

Refuse multiple matching Pods or a conflicting owner.

- [ ] **Step 2: Run prepare**

~~~bash
PREPARE_ID=$(date -u +%Y%m%dT%H%M%SZ)
PREPARE_ROOT="/tmp/layerwise-performance-prepare-$PREPARE_ID"
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh \
  prepare --output "$PREPARE_ROOT"
~~~

- [ ] **Step 3: Verify readiness evidence**

Require aarch64, Python 3.12.13, uv 0.12.3, AISBench 3.1.0/3fd27b4a, CLI/import/config smoke, no NPU request, m1 placement, tokenizer identity, exact fixtures, checksum replay, and no inference call.

- [ ] **Step 4: Retain the client Pod**

Do not report preparation as performance evidence.

### Task 10: Wait For And Adopt Functional Handoff

**Read only:** performance-validation-handoff.md

- [ ] **Step 1: Start the listener**

~~~bash
WAIT_ID=$(date -u +%Y%m%dT%H%M%SZ)
WAIT_ROOT="/tmp/layerwise-performance-wait-$WAIT_ID"
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh \
  wait --output "$WAIT_ROOT" --poll-seconds 10
~~~

WAITING remains fail-closed. BLOCKED is archived and does not mutate servers.

- [ ] **Step 2: Verify final committed generation**

Recheck source/remote equality, image mode, all functional gates, physical-slot proof, cleanup, checksum, model/topology/hardware, and explicit no-reuse Decode companion authorization.

- [ ] **Step 3: Resolve the server image**

Use the handed-off image or exact patch-plus-nerdctl-commit path. Verify platform, digest, labels, patched import path, and SHA256. Archive commands and remove the temporary container.

### Task 11: Run And Check DP1

**Generated:** $RUN_ROOT/points/dp1-*/

- [ ] **Step 1: Create formal root and run DP1**

~~~bash
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
RUN_ROOT="/tmp/layerwise-performance-$RUN_ID"
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh \
  run --topology dp1 --output "$RUN_ROOT"
~~~

- [ ] **Step 2: Execute the full mechanism matrix**

Run approved 4K/16K/32K rotation, outputs, concurrency, warmup, three repetitions, resets, stable checks, metrics, and adaptive stops.

- [ ] **Step 3: Check DP1 before DP2**

~~~bash
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
  python3 -m performance.report check --root "$RUN_ROOT" --scope dp1
~~~

Do not continue on identity/correctness/evidence invalidity. Complete capacity boundaries remain observations.

### Task 12: Run And Check DP2

**Generated:** $RUN_ROOT/points/dp2-*/

- [ ] **Step 1: Revalidate unchanged handoff and identities**

A changed generation triggers full revalidation. Refuse source/image/model drift within one formal run.

- [ ] **Step 2: Resume for DP2**

~~~bash
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh \
  run --topology dp2 --output "$RUN_ROOT" --resume
~~~

Execute reverse rotation and aggregate concurrency 2/4/8/16/32/64. Capture per-rank request/token/context/busy data and NPU telemetry.

- [ ] **Step 3: Check full evidence**

~~~bash
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
  python3 -m performance.report check --root "$RUN_ROOT" --scope all
sha256sum -c "$RUN_ROOT/SHA256SUMS"
~~~

### Task 13: Publish, Restore, Push, And Audit

**Files:**
- Create: features/kv-pool-layerwise-reuse/evidence/layerwise-performance-$RUN_ID/
- Create: features/kv-pool-layerwise-reuse/layerwise-performance-validation-2026-08-08.md
- Modify: features/kv-pool-layerwise-reuse/evidence/README.md
- Modify: features/kv-pool-layerwise-reuse/repo-state.md and workspace.lock.json only after concurrent functional work is committed and only if endpoint identity requires it.

- [ ] **Step 1: Prove restoration**

Prove vLLM stopped, Mooncake empty, exact pre-run Deployments/ConfigMaps restored, client final state recorded, and nothing outside liangjiahao changed.

- [ ] **Step 2: Render the raw report**

~~~bash
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
python3 -m performance.report render \
  --root "$RUN_ROOT" \
  --output features/kv-pool-layerwise-reuse/layerwise-performance-validation-2026-08-08.md
~~~

Check every raw-row link, ratio, DP annotation, capacity boundary, and exclusion. Confirm no performance PASS/FAIL or significance claim.

- [ ] **Step 3: Import exact evidence and replay checksums**

Copy without rewriting raw artifacts, append import provenance, update evidence index, generate root SHA256SUMS, and run the checker against the repository path.

- [ ] **Step 4: Run final gates**

Run all performance tests in the UT Pod, shell syntax, Python compile, Ruff, git diff --check, report checker, checksum replay, namespace scan, source/image replay, and expected-matrix versus evidence audit.

- [ ] **Step 5: Commit only performance-owned paths**

~~~bash
git add -- \
  features/kv-pool-layerwise-reuse/deployment/performance \
  features/kv-pool-layerwise-reuse/evidence/README.md \
  "features/kv-pool-layerwise-reuse/evidence/layerwise-performance-$RUN_ID" \
  features/kv-pool-layerwise-reuse/layerwise-performance-validation-2026-08-08.md \
  features/kv-pool-layerwise-reuse/references/sources.md \
  features/kv-pool-layerwise-reuse/references/snapshots/issue-1-performance-validation-2026-08-08.md \
  features/kv-pool-layerwise-reuse/references/snapshots/aisbench-performance-contract-2026-08-08.md
git commit -m "test(perf): publish Mooncake layerwise characterization"
~~~

- [ ] **Step 6: Reconcile state and push normally**

After the functional session commits, refresh lock/repo-state only if needed. Fetch and integrate remote commits without discarding local or other-session work. Rerun final checks, push normally, and verify remote HEAD equals local HEAD. Never force-push.

- [ ] **Step 7: Completion audit**

Map every design requirement to immutable evidence: handoff, image strategy, client, A/B/C identity, topologies, fixtures, AISBench contract, DP1/DP2 points, metrics, raw report, failures, restoration, checksums, commits, and remote equality. Keep the goal active if any evidence is missing, indirect, inconsistent, or unverified.
