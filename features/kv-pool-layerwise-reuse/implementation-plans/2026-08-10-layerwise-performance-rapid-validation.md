# Mooncake Layerwise Rapid Performance Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the superseded exhaustive DP1/DP2 benchmark with the approved five-point DP1 single-wave characterization, execute it from a new generation-5 handoff, and publish checked raw evidence and ratios.

**Architecture:** Keep the existing feature-local `performance` package boundaries: `contract.py` owns the exact matrix, `fixtures.py` renders AISBench input, `runner.py` owns lifecycle and evidence capture, and `report.py` validates and renders results. The redesign removes adaptive scans and stable-stage retries, groups all work into three server starts, records total-stage single-wave metrics, and retains fail-closed source, image, correctness, restoration, and checksum gates.

**Tech Stack:** Python 3.12 standard library, pytest, AISBench 3.1.0 at `3fd27b4a5fd022fcb5484fb084307f49955491ba`, Kubernetes, Mooncake metrics, Ascend910 telemetry, Git.

## Global Constraints

- Use namespace `liangjiahao` explicitly for every UT, serving, client, helper, log, rollout, exec, and cleanup command.
- The persistent CPU/mock Pod is `liangjiahao/vllm-ascend-ut`; synchronize source with tar plus `kubectl exec`, disable bytecode and pytest cache, and retain the Pod.
- The AISBench Pod remains CPU-only on `m1` and requests neither `huawei.com/Ascend910` nor `huawei.com/vnpu-number`.
- Preserve `deployment_yaml/`, `dockerfile.vllm23`, all preparation evidence, all functional evidence, and unrelated dirty work.
- Do not use `git add .` or `git add -A`; stage only named performance-owned paths.
- Do not modify vLLM, vLLM-Ascend, Mooncake, memcache behavior, public slot-release lifetime, or the reusable server image.
- Use the exact functional image `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-535555917-df3f74ed-20260809T070557Z` with manifest `sha256:cf5da7c1da7dcb72f4c22e201d628b9e4aa819f53c15711651ebc9241cb955bc`.
- The new formal matrix is exactly DP1, 16384 input tokens, concurrency 8, five points, eight warmup requests, eight formal requests, and one formal repetition.
- Use `DefaultPerfMetricCalculator`; do not claim stable-stage behavior or statistical significance.
- The plan defines no point or global performance timeout. A valid slow point continues naturally.
- A failed formal root is preserved and never resumed after tooling, manifest, source, image, or handoff changes.
- No control-repository commit is allowed between generation-5 handoff acceptance and completion of the new formal run.

---

## File Structure

- `deployment/performance/contract.py`: exact five-point matrix, variant order, request and repetition constants.
- `deployment/performance/fixtures.py`: total-stage AISBench config generation and shared fixture references.
- `deployment/performance/runner.py`: three-variant lifecycle, single warmup/formal phases, reduced telemetry, artifact-referencing command ledger, restoration.
- `deployment/performance/report.py`: total-stage parsing, exact-matrix evidence validation, raw rows and approved ratios.
- `deployment/performance/tests/test_contract.py`: matrix and sampling contract tests.
- `deployment/performance/tests/test_fixtures.py`: calculator and config tests.
- `deployment/performance/tests/test_runner.py`: lifecycle, no-retry, three-start, telemetry, fixture and log deduplication tests.
- `deployment/performance/tests/test_report.py`: total-stage parser, exact evidence and rendering tests.
- `deployment/performance/tests/test_image.py`: retain the existing multi-file image-import regression.
- `deployment/performance/README.md`: new runbook and removal of DP2 resume instructions.
- `performance-validation-handoff.md`: generation-5 ready transition before NPU execution and final performance result after publication.
- `layerwise-performance-rapid-validation-2026-08-10.md`: rendered final report.
- `evidence/layerwise-performance-${RUN_ID}/`: imported immutable formal evidence.

## Task 1: Preserve And Stop The Superseded Run

**Files:**
- Read: `/tmp/layerwise-performance-20260809T082351Z/`
- Read: `features/kv-pool-layerwise-reuse/2026-08-09-layerwise-performance-rapid-validation-design.md`
- No repository file modifications.

**Interfaces:**
- Consumes: unified runner session `55265` and the old root's `pre-run-state/` snapshots.
- Produces: a quiescent cluster, preserved diagnostic root, and verified Mooncake/NPU cleanup before source edits.

- [ ] **Step 1: Record current repository and cluster identity**

Run:

```bash
git status --short --branch
git rev-parse HEAD
kubectl get pods -n liangjiahao -o wide
kubectl get deployment -n liangjiahao prefill-engine-deployment decode-engine-deployment mooncake-master-deployment -o json
```

Expected: HEAD contains the approved design commit; all commands name `liangjiahao`; unrelated dirty paths remain present.

- [ ] **Step 2: Interrupt only the superseded runner**

Send `SIGINT` to unified session `55265`, then wait for its terminal result. The runner catches `BaseException`, invokes `_restore_pre_run_state`, writes `restoration.json` and `SHA256SUMS`, and exits nonzero because the interrupted root is diagnostic.

- [ ] **Step 3: Verify restoration and release**

Run:

```bash
kubectl get pods -n liangjiahao -o wide
kubectl exec -n liangjiahao deployment/mooncake-master-deployment -c mooncake-master -- sh -c 'wget -qO- http://127.0.0.1:9003/metrics'
kubectl exec -n liangjiahao deployment/prefill-engine-deployment -c prefill-engine -- npu-smi info
kubectl exec -n liangjiahao deployment/decode-engine-deployment -c decode-engine -- npu-smi info
```

Expected: the performance engines are stopped or restored to the captured pre-run replicas, Mooncake key count and allocated bytes are zero, and no stale performance process owns a physical Ascend910 card.

If the interrupted shell exits before `restoration.json` is written, restore
only the exact captured resources:

```bash
kubectl apply -n liangjiahao -f /tmp/layerwise-performance-20260809T082351Z/pre-run-state/runtime-configmap.json
kubectl apply -n liangjiahao -f /tmp/layerwise-performance-20260809T082351Z/pre-run-state/prefill-deployment.json
kubectl apply -n liangjiahao -f /tmp/layerwise-performance-20260809T082351Z/pre-run-state/decode-deployment.json
kubectl rollout status -n liangjiahao deployment/prefill-engine-deployment
kubectl rollout status -n liangjiahao deployment/decode-engine-deployment
```

Do not delete the namespace or any resource not named by the snapshots.

- [ ] **Step 4: Preserve diagnostic identity**

Run:

```bash
sha256sum /tmp/layerwise-performance-20260809T082351Z/run-contract.json
du -sh /tmp/layerwise-performance-20260809T082351Z
find /tmp/layerwise-performance-20260809T082351Z/points -mindepth 1 -maxdepth 1 -type d | wc -l
```

Record these values in the implementation transcript. Do not import this root as final performance evidence.

## Task 2: Freeze The Five-Point Contract

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/contract.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_contract.py`

**Interfaces:**
- Produces: `FORMAL_REPETITIONS: int`, `REQUEST_COUNT: int`, `VARIANT_ORDER: tuple[str, ...]`, `build_matrix(topology: str | None = None) -> tuple[WorkloadPoint, ...]`, and `sample_counts(concurrency: int) -> tuple[int, int, int]`.
- Consumes: existing `Variant`, `Topology`, and `WorkloadPoint` dataclasses.

- [ ] **Step 1: Write the failing exact-matrix test**

Replace the broad matrix assertions with:

```python
def test_rapid_matrix_is_exactly_five_points() -> None:
    assert contract.build_matrix() == (
        contract.WorkloadPoint("dp1", 16384, 128, "bulk", 8),
        contract.WorkloadPoint("dp1", 16384, 1, "bulk", 8),
        contract.WorkloadPoint("dp1", 16384, 128, "layerwise", 8),
        contract.WorkloadPoint("dp1", 16384, 1, "layerwise", 8),
        contract.WorkloadPoint("dp1", 16384, 1, "reuse3", 8),
    )
    assert contract.build_matrix("dp1") == contract.build_matrix()
    with pytest.raises(ValueError, match="unsupported topology"):
        contract.build_matrix("dp2")


def test_single_wave_counts_are_frozen() -> None:
    assert contract.sample_counts(8) == (8, 8, 1)
    with pytest.raises(ValueError, match="concurrency must be 8"):
        contract.sample_counts(1)
```

- [ ] **Step 2: Prove the contract tests fail in the UT Pod**

Run:

```bash
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-ut.sh -- \
  python3 -m pytest -q performance/tests/test_contract.py -p no:cacheprovider
```

Expected: FAIL because the current matrix contains 180 points and uses three formal repetitions.

- [ ] **Step 3: Implement the minimal fixed contract**

Set:

```python
TOPOLOGIES = MappingProxyType({"dp1": Topology("dp1", 1, 2, 1, 2, (8,))})
INPUT_TOKENS = (16384,)
VARIANT_ORDER = ("bulk", "layerwise", "reuse3")
REQUEST_COUNT = 8
FORMAL_REPETITIONS = 1


def build_matrix(topology: str | None = None) -> tuple[WorkloadPoint, ...]:
    if topology not in (None, "dp1"):
        raise ValueError(f"unsupported topology: {topology}")
    return (
        WorkloadPoint("dp1", 16384, 128, "bulk", 8),
        WorkloadPoint("dp1", 16384, 1, "bulk", 8),
        WorkloadPoint("dp1", 16384, 128, "layerwise", 8),
        WorkloadPoint("dp1", 16384, 1, "layerwise", 8),
        WorkloadPoint("dp1", 16384, 1, "reuse3", 8),
    )


def sample_counts(concurrency: int) -> tuple[int, int, int]:
    if concurrency != 8:
        raise ValueError("concurrency must be 8")
    return REQUEST_COUNT, REQUEST_COUNT, FORMAL_REPETITIONS
```

Remove DP2 rotations, adaptive-stop types/functions, and stable-duration helpers after their callers are removed in later tasks.

- [ ] **Step 4: Run the focused contract tests**

Run the Step 2 command again. Expected: PASS.

## Task 3: Render Total-Stage AISBench Configs

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/fixtures.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_fixtures.py`

**Interfaces:**
- Consumes: `WorkloadPoint` and `request_count=8`.
- Produces: `write_aisbench_config(...) -> Path` importing `DefaultPerfMetricCalculator` and writing `sampling_mode: "single-wave-total"` metadata.

- [ ] **Step 1: Write the failing calculator test**

Update `test_aisbench_config_preserves_point_and_prompt` to assert:

```python
assert "DefaultPerfMetricCalculator" in text
assert "StablePerfMetricCalculator" not in text
assert "batch_size=8" in text
assert metadata == {"request_count": 8, "sampling_mode": "single-wave-total"}
```

- [ ] **Step 2: Prove the fixture test fails in the UT Pod**

Run:

```bash
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-ut.sh -- \
  python3 -m pytest -q performance/tests/test_fixtures.py::test_aisbench_config_preserves_point_and_prompt -p no:cacheprovider
```

Expected: FAIL because the config imports `StablePerfMetricCalculator` and writes `sampling_mode: default`.

- [ ] **Step 3: Implement total-stage config generation**

Render:

```python
from ais_bench.benchmark.calculators import DefaultPerfMetricCalculator

summarizer = dict(
    attr="performance",
    type=DefaultPerfSummarizer,
    calculator=dict(
        type=DefaultPerfMetricCalculator,
        stats_list=["Average", "Min", "Max", "Median", "P75", "P90", "P95", "P99"],
    ),
)
```

Write dataset metadata with `{"request_count": request_count, "sampling_mode": "single-wave-total"}`.

- [ ] **Step 4: Run all fixture tests**

Run:

```bash
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-ut.sh -- \
  python3 -m pytest -q performance/tests/test_fixtures.py -p no:cacheprovider
```

Expected: PASS.

## Task 4: Execute One Warmup And One Formal Attempt

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/runner.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_runner.py`

**Interfaces:**
- Consumes: `sample_counts(8) == (8, 8, 1)` and `report.summarize_aisbench_attempt(...)`.
- Produces: `execute_point(...) -> tuple[dict[str, object], ...]` containing exactly one formal summary, with no request growth or duration retry.

- [ ] **Step 1: Replace repetition/retry tests with failing single-wave tests**

Add:

```python
def test_execute_point_runs_one_warmup_and_one_formal(tmp_path: Path) -> None:
    fake = FakeCommandRunner()
    point = WorkloadPoint("dp1", 16384, 128, "bulk", 8)

    summaries = runner.execute_point(fake, point, tmp_path)

    assert len(summaries) == 1
    descriptions = [call.description for call in fake.calls]
    assert descriptions.count("aisbench") == 2
    assert descriptions.count("remove-all-keys") == 2
    assert len(list(tmp_path.glob("points/**/warmup/attempt-1/raw"))) == 1
    assert len(list(tmp_path.glob("points/**/formal-1/attempt-1/raw"))) == 1
    assert not list(tmp_path.glob("points/**/formal-2"))


def test_invalid_single_wave_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def invalid(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"valid": False, "errors": ["bad response"], "metrics": {}}

    monkeypatch.setattr(runner.report, "summarize_aisbench_attempt", invalid)
    with pytest.raises(RuntimeError, match="bad response"):
        runner.execute_point(
            FakeCommandRunner(),
            WorkloadPoint("dp1", 16384, 1, "bulk", 8),
            tmp_path,
            runner.RunEnvironment(image_digest="sha256:image"),
        )
    assert calls == 1
    assert not list(tmp_path.glob("points/**/attempt-2"))
```

- [ ] **Step 2: Prove the new runner tests fail in the UT Pod**

Run:

```bash
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-ut.sh -- \
  python3 -m pytest -q \
  performance/tests/test_runner.py::test_execute_point_runs_one_warmup_and_one_formal \
  performance/tests/test_runner.py::test_invalid_single_wave_is_not_retried \
  -p no:cacheprovider
```

Expected: FAIL because the current runner creates three formal phases and retries insufficient-duration warmups.

- [ ] **Step 3: Simplify `execute_point`**

Use exactly:

```python
warmup_count, formal_count, repetitions = sample_counts(point.concurrency)
assert repetitions == 1
phases = (("warmup", warmup_count), ("formal-1", formal_count))
```

For each phase, create only `attempt-1`, run `_attempt_commands`, summarize once, append the formal summary only for `formal-1`, and raise immediately when `valid` is not true. Remove request doubling and insufficient-duration resume logic.

- [ ] **Step 4: Run the focused runner tests**

Run the Step 2 command again. Expected: PASS.

## Task 5: Group The Run Into Three Variant Starts

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/runner.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_runner.py`

**Interfaces:**
- Consumes: `build_matrix("dp1")` in variant-grouped order and `VARIANT_ORDER`.
- Produces: `run(...)` that starts BULK, LAYERWISE, and REUSE3 once each and writes a single-wave `run-contract.json`.

- [ ] **Step 1: Write a failing three-start lifecycle test**

Add a runner test that stubs handoff, image, identity, pre-run state, rendering, canary, point execution, restoration, and checksum functions, then asserts:

```python
assert applied_variants == ["bulk", "layerwise", "reuse3"]
assert executed_points == [
    "dp1-16384-bulk-o128-c8",
    "dp1-16384-bulk-o1-c8",
    "dp1-16384-layerwise-o128-c8",
    "dp1-16384-layerwise-o1-c8",
    "dp1-16384-reuse3-o1-c8",
]
assert stopped_variants == ["bulk", "layerwise", "reuse3"]
assert contract["formal_repetitions"] == 1
assert contract["request_count"] == 8
assert contract["calculator"] == "total"
assert contract["single_wave"] is True
```

- [ ] **Step 2: Prove the lifecycle test fails in the UT Pod**

Run the exact new test through `run-performance-ut.sh`. Expected: FAIL because the current runner groups by input length, calculates adaptive stops, and writes three repetitions.

- [ ] **Step 3: Implement the variant-grouped loop**

Render all three variants once, validate unique differences, and execute:

```python
for variant in VARIANT_ORDER:
    block_points = tuple(point for point in points if point.variant == variant)
    representative = block_points[0]
    _apply_variant_block(...)
    _run_variant_canary(...)
    for point in block_points:
        _write_json(point_root / "identity.json", point_identity)
        execute_point(command_runner, point, output_dir, environment)
        executed_points.append(_point_id(point))
    _capture_variant_diagnostics(...)
    _stop_engines(...)
```

Remove adaptive histories and stop decisions. Write `run-contract.json` with the exact five expected point IDs, `formal_repetitions: 1`, `request_count: 8`, `calculator: "total"`, `single_wave: true`, and `raw_characterization_only: true`.

- [ ] **Step 4: Restrict the CLI to DP1**

Keep `--topology` for runbook compatibility but set `choices=("dp1",)`. Remove DP2 resume flow from the runbook and reject a nonempty output root.

- [ ] **Step 5: Run all runner lifecycle tests**

Run:

```bash
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-ut.sh -- \
  python3 -m pytest -q performance/tests/test_runner.py -p no:cacheprovider
```

Expected: PASS after obsolete adaptive, DP2-resume, and three-repetition tests are replaced by approved-protocol tests.

## Task 6: Layer And Deduplicate Evidence

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/runner.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_runner.py`

**Interfaces:**
- Adds to `Command`: `stdout_artifact: str | None = None`.
- Produces: command records that reference captured artifacts, ten-second telemetry, shared fixture archive, point diagnostics without complete service logs, and one complete service-log capture per variant.

- [ ] **Step 1: Write failing command-ledger and telemetry tests**

Add:

```python
def test_capture_references_artifact_without_duplicate_stdout(tmp_path: Path) -> None:
    command_runner = runner.SubprocessCommandRunner(tmp_path)
    attempt = tmp_path / "variants" / "bulk"
    raw = attempt / "raw" / "vllm-prefill.log"
    runner._capture(
        command_runner,
        runner.Command(("sh", "-c", "printf payload"), description="prefill-log"),
        attempt,
        "vllm-prefill.log",
    )
    command_dir = next((tmp_path / "commands").iterdir())
    result = json.loads((command_dir / "result.json").read_text())
    assert raw.read_text() == "payload"
    assert result["stdout_artifact"] == str(raw.relative_to(tmp_path))
    assert not (command_dir / "stdout.txt").exists()


def test_sampler_uses_ten_second_interval() -> None:
    command = runner._sampled_aisbench_command(
        ("true",), runner.RunEnvironment()
    )
    assert "sleep 10" in command.argv[2]
    assert "sleep 1" not in command.argv[2]
```

- [ ] **Step 2: Prove evidence tests fail in the UT Pod**

Run the two new tests through `run-performance-ut.sh`. Expected: FAIL because the command runner always writes `stdout.txt` and the sampler sleeps one second.

- [ ] **Step 3: Implement artifact references**

When `Command.stdout_artifact` is set, `SubprocessCommandRunner.run` captures stdout in memory but does not create `stdout.txt`; it validates and writes the evidence-root-relative artifact reference to `result.json`. `_capture` computes `attempt / "raw" / filename`, calls `_invoke(command_runner, replace(command, stdout_artifact=str(destination)), attempt)`, and writes the returned text once.

- [ ] **Step 4: Split point and variant diagnostics**

Point diagnostics retain Mooncake metrics, Prefill/Decode NPU snapshots, and engine Pods. Variant diagnostics capture complete Prefill and Decode logs once under `variants/${variant}/`. Failure diagnostics retain complete logs immediately.

- [ ] **Step 5: Archive shared fixtures once**

Before server mutation, copy only `tokens-16384-c64/manifest.json`, `warmup.jsonl`, and `formal-1.jsonl` into `output_dir/fixtures/tokens-16384-c64/`. After each AISBench archive, hash and remove attempt-local `dataset.jsonl`, then write `fixture-reference.json` containing the shared relative path, slice name, and SHA256.

- [ ] **Step 6: Run runner and fixture tests**

Run:

```bash
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-ut.sh -- \
  python3 -m pytest -q performance/tests/test_runner.py performance/tests/test_fixtures.py \
  -p no:cacheprovider
```

Expected: PASS.

## Task 7: Parse And Check Total-Stage Evidence

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/report.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_report.py`

**Interfaces:**
- Produces: `summarize_aisbench_attempt(...)` reading the AISBench `total` stage, `validate_evidence(root) -> list[str]` enforcing the five-point contract, and `render_report(root) -> str` rendering raw rows and approved ratios.

- [ ] **Step 1: Replace the stable-stage fixture with a failing total-stage test**

Create AISBench common JSON and CSV rows whose stage is `total`, then assert:

```python
assert summary["valid"] is True
assert summary["measurement_stage"] == "total"
assert summary["single_wave"] is True
assert summary["request_count"] == 8
assert summary["success_count"] == 8
assert summary["metrics"]["TTFT Median"] == 800
assert summary["metrics"]["TTFT Max"] == 900
```

Do not include or assert `stable_duration_valid`.

- [ ] **Step 2: Prove the parser test fails in the UT Pod**

Run the new parser test through `run-performance-ut.sh`. Expected: FAIL because `_stable_value` requires `stable` and the current parser rejects a single wave.

- [ ] **Step 3: Implement total-stage parsing**

Replace `_stable_value` with:

```python
def _stage_value(common: dict[str, object], name: str, stage: str = "total") -> float:
    stages = common.get(name)
    if not isinstance(stages, dict) or stage not in stages:
        raise ValueError(f"AISBench common metric lacks {stage} stage: {name}")
    return _metric_number(stages[stage])
```

Read CSV rows where `Stage == "total"`. Extract Median, Max, and raw P95 for TTFT, E2EL, TPOT, and ITL. Require exactly eight details, eight successes, exact input/output token counts, total requests eight, and failed requests zero.

- [ ] **Step 4: Write failing exact-evidence tests**

The valid-tree fixture must contain all five point IDs, one warmup, one `formal-1`, variant logs, fixture references, restoration evidence, and checksums. Add parametrized mutations proving rejection of an extra point, missing point, `formal-2`, request count other than eight, calculator other than total, duplicated attempt, missing variant log, missing fixture reference, and checksum drift.

- [ ] **Step 5: Implement exact evidence validation**

Compare `run-contract.json.expected_points` to `_point_id(point)` for every `build_matrix("dp1")` point with order preserved. Reject extra point directories and any `formal-*` other than `formal-1`. Require `formal_repetitions == 1`, `request_count == 8`, `calculator == "total"`, and `single_wave is True`.

- [ ] **Step 6: Update raw rendering tests and report text**

Assert the report contains five raw rows, `LAYERWISE / BULK` only for output 128, and `REUSE3 / LAYERWISE` plus `REUSE3 / BULK` only for output 1. Include the statement `Single-wave raw characterization; not a steady-state or statistically significant result.`

- [ ] **Step 7: Run all report tests**

Run:

```bash
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-ut.sh -- \
  python3 -m pytest -q performance/tests/test_report.py -p no:cacheprovider
```

Expected: PASS.

## Task 8: Update Runbook And Complete CPU/Mock Gates

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/README.md`
- Modify: `features/kv-pool-layerwise-reuse/2026-08-08-layerwise-performance-validation-design.md`
- Modify: `features/kv-pool-layerwise-reuse/implementation-plans/2026-08-08-layerwise-performance-validation.md`
- Modify: `features/kv-pool-layerwise-reuse/implementation-plans/2026-08-08-layerwise-functional-performance-execution.md`
- Modify: `features/kv-pool-layerwise-reuse/evidence/README.md`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/image.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_image.py`

**Interfaces:**
- Produces: one authoritative rapid-validation runbook and complete green CPU/static evidence.

- [ ] **Step 1: Update documentation authority**

Mark the 2026-08-08 exhaustive matrix as superseded for the next formal run and link to `2026-08-09-layerwise-performance-rapid-validation-design.md` and this plan. Replace DP1/DP2 resume commands with one command:

```bash
run_id=$(date -u +%Y%m%dT%H%M%SZ)
run_root="/tmp/layerwise-performance-rapid-${run_id}"
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh \
  run --topology dp1 --output "${run_root}"
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
  python3 -m performance.report check --root "${run_root}" --scope all
```

Document the five points, single-wave limitation, no performance timeout, three server starts, and evidence layering.

- [ ] **Step 2: Retain and verify the multi-file image fix**

Keep the existing TDD change in `image.py` and `test_image.py` that interprets comma-separated patched paths as an aggregate digest. Run:

```bash
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-ut.sh -- \
  python3 -m pytest -q performance/tests/test_image.py -p no:cacheprovider
```

Expected: four image tests pass.

- [ ] **Step 3: Run the complete performance harness**

Run:

```bash
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-ut.sh -- \
  python3 -m pytest -q performance/tests -p no:cacheprovider
```

Expected: all tests pass with no skipped required gate.

- [ ] **Step 4: Run static gates in the UT Pod**

Run changed-file Ruff check and format check, Python compilation, and shell syntax through the UT helper. Also run locally:

```bash
git diff --check
rg -n 'ai-inference|kubectl (apply|exec|logs|cp|rollout|delete)(?![^\n]*-n liangjiahao)' \
  features/kv-pool-layerwise-reuse/deployment/performance \
  --pcre2
bash -n features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh
bash -n features/kv-pool-layerwise-reuse/deployment/performance/run-performance-ut.sh
```

Expected: all gates pass and no executable namespace violation is reported.

## Task 9: Commit Tooling And Publish Generation 5

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/performance-validation-handoff.md`
- Stage only files explicitly listed in Tasks 2-8 plus this implementation plan.

**Interfaces:**
- Produces: a pushed redesign control commit followed by a pushed handoff-only generation-5 commit accepted by the checker.

- [ ] **Step 1: Commit performance-owned redesign paths**

Inspect `git diff --name-status`, stage only the named files, and commit:

```bash
git commit -m "refactor(perf): bound layerwise validation matrix"
```

Do not stage evidence preparation roots, functional evidence roots, `deployment_yaml/`, or `dockerfile.vllm23`.

- [ ] **Step 2: Push and prove redesign remote equality**

Run:

```bash
git push origin kv-pool-layerwise-reuse
git fetch origin kv-pool-layerwise-reuse
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/kv-pool-layerwise-reuse)"
```

Expected: equality succeeds without force-push.

- [ ] **Step 3: Populate generation 5**

Update only `performance-validation-handoff.md`: set `generation: 5`, update `updated_at`, record the redesign commit as the control source parent, retain the exact nested source/image/functional evidence identities, and replace the authorized matrix with DP1/16384/c8/five points/single-wave total-stage scope.

- [ ] **Step 4: Commit the handoff-only transition**

Stage only the handoff and commit:

```bash
git commit -m "docs(kv_pool): release rapid performance generation 5"
```

Verify `git diff-tree --no-commit-id --name-only -r HEAD` prints only `features/kv-pool-layerwise-reuse/performance-validation-handoff.md` and `HEAD^` equals the recorded control source parent.

- [ ] **Step 5: Run and push the handoff checker**

Run:

```bash
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
  python3 -m performance.handoff check \
  --path features/kv-pool-layerwise-reuse/performance-validation-handoff.md \
  --workspace /root/ljh/vllm-workspace
git push origin kv-pool-layerwise-reuse
git fetch origin kv-pool-layerwise-reuse
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/kv-pool-layerwise-reuse)"
```

Expected: checker JSON has `valid: true`, generation 5, and remote equality passes.

## Task 10: Execute The New Five-Point Formal Run

**Files:**
- Create: `/tmp/layerwise-performance-rapid-${RUN_ID}/`
- No repository modifications during the run.

**Interfaces:**
- Consumes: accepted generation-5 handoff, exact image digest, retained CPU-only AISBench client.
- Produces: complete checked raw run root with restoration and `SHA256SUMS`.

- [ ] **Step 1: Re-audit exclusive runtime ownership**

Capture kube context, `liangjiahao` Pods, physical Ascend910 allocation, NPU processes, Mooncake metrics, current HEAD/remote equality, nested source identities, and dirty state. Stop if another runner mutates Prefill, Decode, or Mooncake.

- [ ] **Step 2: Start the new root**

Run:

```bash
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
RUN_ROOT="/tmp/layerwise-performance-rapid-${RUN_ID}"
features/kv-pool-layerwise-reuse/deployment/performance/run-performance-test.sh \
  run --topology dp1 --output "${RUN_ROOT}"
```

Do not add a shell or runner timeout. Monitor the command session, point summaries, Pod restarts, response failures, and Mooncake cleanup until natural completion.

- [ ] **Step 3: Check exact run evidence**

Run:

```bash
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
  python3 -m performance.report check --root "${RUN_ROOT}" --scope all
cd "${RUN_ROOT}"
sha256sum -c SHA256SUMS
```

Expected: checker reports `valid: true`, exactly five point IDs exist, all checksums pass, and restoration is complete.

- [ ] **Step 4: Recheck cluster cleanup**

Verify restored Deployments/ConfigMaps, zero Mooncake keys and bytes, no performance engine NPU process, and retained CPU-only AISBench Pod.

## Task 11: Render, Import, Publish, And Audit

**Files:**
- Create: `features/kv-pool-layerwise-reuse/layerwise-performance-rapid-validation-2026-08-10.md`
- Create: `features/kv-pool-layerwise-reuse/evidence/layerwise-performance-${RUN_ID}/`
- Modify: `features/kv-pool-layerwise-reuse/evidence/README.md`
- Modify: `features/kv-pool-layerwise-reuse/performance-validation-handoff.md`

**Interfaces:**
- Consumes: checked `${RUN_ROOT}`.
- Produces: repository evidence, final report, final handoff result, pushed commit, and requirement-to-evidence audit.

- [ ] **Step 1: Render the report**

Run:

```bash
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
  python3 -m performance.report render \
  --root "${RUN_ROOT}" \
  --output features/kv-pool-layerwise-reuse/layerwise-performance-rapid-validation-2026-08-10.md
```

Verify five raw rows and only the approved output-matched ratios.

- [ ] **Step 2: Import exact evidence**

Create `features/kv-pool-layerwise-reuse/evidence/layerwise-performance-${RUN_ID}/raw/` and copy `${RUN_ROOT}/.` into it without rewriting raw artifacts. Add `IMPORT_PROVENANCE.json` beside `raw/` containing run ID, source path, import timestamp, control/nested commits, image digest, raw `SHA256SUMS` digest, and report path. Generate a repository-root `SHA256SUMS` covering provenance and every file under `raw/`, then replay both repository and raw manifests.

- [ ] **Step 3: Re-run checker against imported raw evidence**

Run:

```bash
PYTHONPATH=features/kv-pool-layerwise-reuse/deployment \
  python3 -m performance.report check \
  --root "features/kv-pool-layerwise-reuse/evidence/layerwise-performance-${RUN_ID}/raw" \
  --scope all
```

Expected: valid.

- [ ] **Step 4: Update evidence index and final handoff result**

Add the run ID, report, checker result, checksum digest, limitations, and reusable image identity to `evidence/README.md` and a final `Performance Acceptance` section in `performance-validation-handoff.md`. Preserve generation 5 source/image fields and record that the final handoff content changed only after the archived generation-5 snapshot authorized the run.

- [ ] **Step 5: Run final CPU/static/report/checksum gates**

Repeat the complete performance harness, Ruff, Python compilation, shell syntax, `git diff --check`, namespace scan, imported checker, raw checksum replay, repository checksum replay, source/image identity checks, cluster restoration checks, and expected-five-points audit.

- [ ] **Step 6: Commit only final performance-owned paths**

Stage the report, imported evidence root, evidence index, final handoff, and any final tooling fixes already covered by tests. Commit:

```bash
git commit -m "test(perf): publish rapid layerwise characterization"
```

- [ ] **Step 7: Push and prove final equality**

Run:

```bash
git push origin kv-pool-layerwise-reuse
git fetch origin kv-pool-layerwise-reuse
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/kv-pool-layerwise-reuse)"
```

Expected: equality passes without force-push.

- [ ] **Step 8: Complete requirement-to-evidence audit**

Map every requirement in `2026-08-09-layerwise-performance-rapid-validation-design.md` to immutable source, CPU/mock logs, handoff generation 5, five point identities, raw AISBench rows, variant runtime checks, Mooncake/NPU evidence, restoration, checksum manifests, report, commits, and remote equality. Keep the goal active if any mapping is missing, indirect, or inconsistent.
