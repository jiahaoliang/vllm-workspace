# Multi-DP/TP Stress Validation Detailed Execution Plan

**Status:** Approved for execution on 2026-07-24.

**Source acceptance plan:**
[multi-dp-tp-stress-validation-plan.md](multi-dp-tp-stress-validation-plan.md)

**Audience:** This document is intentionally explicit. An execution agent must follow the tasks in order and
must not invent a different topology, workload, artifact schema, cleanup policy, or Git publication flow.
Within those boundaries, the agent owns routine diagnosis and retry decisions and must continue without
waiting for new user direction.

**Goal:** Implement and run one Kubernetes stress profile that validates Prefill `DP=2/TP=2`, Decode
`DP=1/TP=2`, 16-way concurrency, 16K/32K prompts, runtime chunked prefill, and Mooncake ranged layerwise
save/load. Publish all evidence and a step-by-step reproduction report to the control repo feature branch.

**Runtime contract correction (2026-07-25):** Failed run `20260725T015720Z` proved that this KVPool path
uses shared block hashes rather than response-carried PD metadata. The running proxy accepts
`kv_transfer_params: null` from Prefill and sends Decode the original request body. The same run also proved
that chunked Prefill emits one successful final-layer commit per chunk, not one commit per whole request.
The pinned driver and checker requirements below incorporate that evidence; the final report must link the
failed run and describe this correction.

**Master readiness correction (2026-07-25):** Failed run `20260725T030454Z` reached a successful Mooncake
Master rollout but its first Service metrics request received a transient connection refusal before endpoint
propagation completed. No vLLM process or workload started, and the same endpoint returned HTTP 200 shortly
afterward. `capture_metrics` therefore performs a bounded 60-second readiness retry before returning the
complete metrics response. The downstream empty-pool and key-count assertions remain unchanged and strict.

## 1. Non-Negotiable Rules

1. Work from `/root/ljh/vllm-workspace` unless a step explicitly changes directory.
2. The control repo branch must be `kv-pool-layerwise-reuse`.
3. Do not modify production source in `repos/vllm`, `repos/vllm-ascend`, or `repos/Mooncake` for this task.
4. Keep `repos/Mooncake` read-only.
5. Do not change the existing G0-G4 manifests or reports. The stress profile is additive.
6. Do not add a hostPath source mount. The image contains source; use the existing `kubectl cp` sync flow.
7. Engine containers keep `sleep infinity` as PID 1. vLLM is started and stopped manually in each Pod.
8. Do not recreate engine Pods between S1, S2, and S3. Only restart the in-Pod vLLM processes and Master.
9. Do not stop, scale, delete, or patch workloads outside `ai-inference`.
10. Preserve these unrelated untracked paths and never stage them:

    ```text
    deployment_yaml/
    dockerfile.vllm23
    ```

11. Never use `git add -A`, `git add .`, `git reset --hard`, or `git checkout --`.
12. Use native Linux Git commands. Do not invoke the PowerShell workspace helpers.
13. Any failed runtime gate ends the current run. Capture the failure, stop both vLLM processes, and do not
    continue to the next scenario with uncertain state.
14. Do not silently rerun a failed scenario in the same artifact directory. A rerun gets a new UTC run ID.
15. Never claim evidence is uploaded until the evidence commit is visible on
    `origin/kv-pool-layerwise-reuse`.
16. A failed run does not end the overall execution task. After preserving its artifacts, diagnose it, make
    evidence-backed fixes limited to the validation harness, manifests, checker, runner, or documentation,
    commit those fixes locally, and retry the complete run with a new UTC run ID without waiting for user
    direction.
17. Do not push intermediate implementation, harness-fix, evidence, or report commits. Push GitHub once,
    only after the final passing run, evidence import, report, and all offline verification are complete.
18. Request new user direction only before changing production source, weakening the frozen topology or
    workload, performing a destructive operation, or expanding the validation scope.

## 2. Frozen Inputs

The implementation and runtime preflight must use these values:

| Name | Value |
|---|---|
| namespace | `ai-inference` |
| node | `n1` |
| image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2` |
| model path | `/root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| served model | `vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| vLLM commit | `ee0da84ab9e04ac7610e28580af62c365e898389` |
| vLLM-Ascend commit | `3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6` |
| vLLM-Ascend image baseline used by sync helper | `663209fd6208a59a48742f75116345bf5f5281ec` |
| Mooncake commit | `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` |
| block size | `128` |
| model layers | `27` |
| max model length | `65536` |
| max batched tokens | `1024` |
| max sequences | `16` |
| request timeout | `1800` seconds |

Do not replace the model, lower the prompt lengths, change DP/TP, enable PP/PCP/DCP, or change the KV
connector when a runtime failure occurs. Preserve the evidence and report the failure first.

## 3. Required Deliverables

Create exactly these implementation files:

```text
features/kv-pool-layerwise-reuse/deployment/stress/README.md
features/kv-pool-layerwise-reuse/deployment/stress/10-runtime-config.yaml
features/kv-pool-layerwise-reuse/deployment/stress/40-prefill-engine.yaml
features/kv-pool-layerwise-reuse/deployment/stress/50-decode-engine.yaml
features/kv-pool-layerwise-reuse/deployment/stress-test.py
features/kv-pool-layerwise-reuse/deployment/check-stress-log.py
features/kv-pool-layerwise-reuse/deployment/run-stress-test.sh
features/kv-pool-layerwise-reuse/deployment/tests/test_stress_test.py
features/kv-pool-layerwise-reuse/deployment/tests/test_check_stress_log.py
```

After the live run, create these generated deliverables using the actual UTC timestamp/date:

```text
features/kv-pool-layerwise-reuse/evidence/ranged-api-stress-<UTC>/
features/kv-pool-layerwise-reuse/multi-dp-tp-stress-validation-<YYYY-MM-DD>.md
```

Also update:

```text
features/kv-pool-layerwise-reuse/evidence/README.md
```

Do not add runtime artifacts to `repos/*`.

## 4. File-Level Implementation Contract

### 4.1 Stress Runtime ConfigMap

Create `deployment/stress/10-runtime-config.yaml` with ConfigMap name
`layerwise-stress-runtime-config`. Include exactly these data entries:

```text
mooncake.json
start-prefill.sh
start-decode.sh
stop-engine.sh
check-runtime.py
```

Copy `mooncake.json`, `stop-engine.sh`, and `check-runtime.py` behavior from the current
`deployment/10-runtime-config.yaml`. Do not include the old embedded `smoke-test.py`; the new workload driver
is copied separately by the host runner.

Both start scripts must retain the existing PID-file and startup-failure behavior:

```text
/tmp/vllm-prefill.pid
/tmp/vllm-prefill.log
/tmp/vllm-decode.pid
/tmp/vllm-decode.log
```

Before starting, reject a live PID recorded by the PID file. Truncate the role log, start with `nohup`, save
the new PID, wait 3 seconds, and fail with the last 80 log lines if the process exited.

Use the following common serving arguments on both roles:

```text
--model /root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8
--served-model-name vllm-ascend/DeepSeek-V2-Lite-W8A8
--quantization ascend
--trust-remote-code
--enforce-eager
--distributed-executor-backend mp
--tensor-parallel-size 2
--pipeline-parallel-size 1
--prefill-context-parallel-size 1
--decode-context-parallel-size 1
--block-size 128
--enable-chunked-prefill
--max-model-len 65536
--max-num-batched-tokens 1024
--max-num-seqs 16
--no-enable-prefix-caching
--enable-logging-iteration-details
--gpu-memory-utilization 0.90
```

Use this environment for the `nohup` process:

```text
VLLM_USE_V1=1
PYTHONUNBUFFERED=1
VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1
```

Prefill-specific arguments:

```text
--host 0.0.0.0
--port 8100
--data-parallel-size 2
--data-parallel-size-local 2
--data-parallel-backend mp
--kv-transfer-config {"kv_connector":"AscendStoreConnector","kv_role":"kv_producer","kv_load_failure_policy":"fail","kv_connector_extra_config":{"backend":"mooncake","use_layerwise":true,"layerwise_prefetch_layers":1,"lookup_rpc_port":0}}
```

Decode-specific arguments:

```text
--host 0.0.0.0
--port 8200
--data-parallel-size 1
--data-parallel-backend mp
--kv-transfer-config {"kv_connector":"AscendStoreConnector","kv_role":"kv_consumer","kv_load_failure_policy":"fail","kv_connector_extra_config":{"backend":"mooncake","use_layerwise":true,"layerwise_prefetch_layers":1,"lookup_rpc_port":0,"consumer_is_to_load":true}}
```

Pass each `--kv-transfer-config` as one shell-quoted JSON argument. Do not add
`--data-parallel-size-local` to Decode.

### 4.2 Stress Engine Manifests

Create full Deployment manifests, not partial `kubectl patch` documents.

For `stress/40-prefill-engine.yaml`:

- Copy the existing Prefill Deployment structure and resource name unchanged.
- Keep `replicas: 1`, `strategy.type: Recreate`, `nodeName: n1`, labels, ports, probes, image, host driver
  mounts, model cache, and `sleep infinity` command.
- Change both NPU request and limit from `1` to `4`.
- Change the runtime ConfigMap reference to `layerwise-stress-runtime-config`.
- Keep `/dev/shm` at `24Gi` unless static validation proves the manifest cannot start; do not tune it in
  response to an unrelated runtime failure.

For `stress/50-decode-engine.yaml`:

- Preserve the same base structure and resource name.
- Change both NPU request and limit from `1` to `2`.
- Change the runtime ConfigMap reference to `layerwise-stress-runtime-config`.
- Preserve every other volume, port, probe, environment variable, and `sleep infinity` behavior.

`deployment/stress/README.md` must contain:

- the fixed `Prefill DP2/TP2 + Decode DP1/TP2` topology;
- the 6-NPU requirement on `n1`;
- the apply order;
- the fact that applying these Deployments recreates the old 1+1-card Pods once;
- manual start/stop commands;
- a warning that the final state retains a 6-card allocation until the base manifests are deliberately
  restored.

### 4.3 Workload Driver CLI

Implement `deployment/stress-test.py` using Python standard library plus the packages already present in the
image: `httpx` and `transformers`. It must expose these subcommands:

```text
prepare       Build and validate deterministic request fixtures.
baseline      Send all scenario requests directly to Decode with an empty pool.
pinned-load   Run one direct Prefill -> Decode request with an explicit Prefill DP rank.
proxy-load    Send all scenario requests concurrently through proxy.
finalize      Compare outputs and write the scenario summary.
```

Every subcommand accepts:

```text
--scenario s1|s2|s3
--output <existing scenario directory>
--proxy-base-url http://vllm-proxy-service:8000
```

`pinned-load` additionally requires:

```text
--case-index <integer>
--prefill-rank 0|1
--decode-rank 0
```

The driver must query `<proxy-base-url>/listEndPoints`, require exactly one prefill and one decode endpoint,
and use the returned Pod endpoints for direct calls. Do not assume a Prefill or Decode Kubernetes Service
exists.

Use atomic JSON writes: write `<path>.tmp`, flush/close it, then `os.replace` it. A subcommand must refuse to
overwrite a raw response file that already exists. This prevents a partial retry from disguising an earlier
result.

### 4.4 Fixture Algorithm

Use `AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)` and
`add_special_tokens=False` for every fixture component.

Use these immutable scenario definitions:

| Scenario | Cases | Shared blocks | Unique blocks/case | Cached blocks/case | Expected keys |
|---|---:|---:|---:|---:|---:|
| S1 | 4 | 0 | 127 | 127 | 508 |
| S2 | 16 | 48 | 15 | 63 | 288 |
| S3 | 4 | 224 | 31 | 255 | 348 |

Build shared tokens by repeating this ASCII unit and truncating to the exact shared-token target:

```text
Shared stress validation prefix is identical across requests.
```

Treat the repeated unit as that sentence followed by one ASCII space.

For each case, repeat a case-specific unit that starts with its marker and case index, then truncate to the
exact unique-token target. Use markers:

```text
S1_CASE_00 ... S1_CASE_03
S2_CASE_00 ... S2_CASE_15
S3_CASE_00 ... S3_CASE_03
```

Append this common instruction after the cached boundary:

```text
\nQuestion: Return exactly the private cache identity marker and no other words.\nAnswer:
```

The instruction must tokenize to at least 1 and fewer than 128 tokens. It must contain none of the scenario
markers.

Before writing fixtures, validate all of the following:

1. Every request has exactly the configured number of full cached blocks.
2. The prompt tail is byte-for-byte/token-for-token identical across all cases.
3. No marker occurs in the tail.
4. Each marker occurs in its own cached tokens.
5. The first `shared_blocks` are identical for all cases.
6. Every later full block has exactly `case_count` distinct token sequences.
7. Blocks never converge after the shared/unique boundary.
8. `expected_keys == shared_blocks + case_count * unique_blocks`.
9. Total prompt length is greater than the cached boundary and less than the next 128-token boundary.

Write one request file per case with this payload:

```json
{
  "model": "vllm-ascend/DeepSeek-V2-Lite-W8A8",
  "prompt": [],
  "max_tokens": 24,
  "temperature": 0,
  "seed": 2026072400,
  "stream": false
}
```

Set `prompt` to the generated token list. Set seed to `2026072400 + scenario_offset + case_index`, where
scenario offsets are S1=`0`, S2=`100`, S3=`200`.

Write `fixture.json` with the scenario definition, actual token counts, markers, seeds, cached boundary,
request file paths, and expected key count. Do not duplicate full prompt arrays into `fixture.json`.

### 4.5 HTTP Behavior

For `baseline`:

- Read all request files.
- Send them concurrently to the discovered Decode endpoint.
- Add headers `X-Request-Id: stress-<scenario>-baseline-<case>` and
  `X-data-parallel-rank: 0`.
- Do not add `kv_transfer_params`.
- Use an `httpx.AsyncClient` timeout of 1800 seconds and connection limits equal to case count.
- Use `asyncio.gather(..., return_exceptions=True)` so every case gets an artifact even if one fails.
- Write raw status/body/error for every case, then fail if any status is not 200 or any body lacks choices.

For `pinned-load`:

1. Copy the original request payload.
2. Set Prefill `stream=false` and `max_tokens=1`.
3. Add the same `kv_transfer_params` request object used by the running proxy:

   ```json
   {
     "do_remote_decode": true,
     "do_remote_prefill": false,
     "remote_engine_id": null,
     "remote_block_ids": null,
     "remote_host": null,
     "remote_port": null,
     "aborted_request": []
   }
   ```

4. POST to Prefill with `X-Request-Id: stress-<scenario>-pinned-<case>` and the requested
   `X-data-parallel-rank`.
5. Require HTTP 200. Accept `kv_transfer_params` as null, an empty dictionary, or a non-empty dictionary;
   reject every other type. This matches the running proxy and is expected for shared-hash KVPool.
6. Copy the original, unmodified generation payload. Attach the returned transfer params only when they are
   a non-empty dictionary; otherwise send Decode the original payload without that field.
7. POST to Decode with the same request ID and `X-data-parallel-rank: 0`.
8. Persist both raw responses and the selected ranks.

For `proxy-load`:

- Send all original request payloads concurrently to
  `http://vllm-proxy-service:8000/v1/completions`.
- Use request IDs `stress-<scenario>-proxy-<case>`.
- Do not add `X-data-parallel-rank`; the current proxy does not forward it.
- Persist all responses before returning failure.

Use the existing response signature fields exactly:

```text
text
finish_reason
stop_reason
prompt_tokens
completion_tokens
```

For each candidate response, require exact signature equality with its baseline, its own marker in text, and
zero foreign markers. Also record normalized-text equality for diagnosis, but normalized equality is not a
substitute for exact equality.

### 4.6 Scenario State And Summary

Each scenario directory contains:

```text
fixture.json
requests/
baseline/
pinned/                 # S1 all four cases; S3 case 0 only
proxy/                  # S2 and S3
scenario-state.json
scenario-summary.json
```

`scenario-state.json` records completed actions and raw paths. `finalize` must reject missing actions:

- S1 requires `prepare`, `baseline`, and pinned cases `0,1,2,3` with Prefill ranks `0,1,0,1`.
- S2 requires `prepare`, `baseline`, and `proxy-load`.
- S3 requires `prepare`, `baseline`, pinned case 0 on Prefill rank 0, and `proxy-load` for all four cases.

`finalize` accepts `--master-metrics <path>` and `--log-check-summary <path>`. It must verify the final
`master_key_count`, import the log-check status, and write:

```json
{
  "schema_version": 1,
  "scenario": "s1",
  "status": "passed",
  "validated": true,
  "prompt_layout": {},
  "baseline": {},
  "candidate": {},
  "exact_match_count": 4,
  "isolated_count": 4,
  "expected_key_count": 508,
  "actual_key_count": 508,
  "log_validation": {},
  "timing": {},
  "errors": []
}
```

Write a failed summary before raising any final validation exception.

### 4.7 Log Checker CLI

Implement `deployment/check-stress-log.py` with three subcommands:

```text
topology
pinned
aggregate
```

Common ranged-event validation must reuse the field and return-code rules from
`deployment/check-range-debug-log.py`:

- range fields match exactly;
- Prefill permits ranged load of blocks committed by earlier chunks and ranged save of the current chunk;
  Decode permits ranged load only;
- `layer_id` is in `0..26`;
- vector lengths equal `key_count`;
- fragment sizes/offsets are non-negative integers;
- requested bytes equal the fragment sum;
- every result equals requested bytes;
- every Prefill chunk commit is on layer 26, all results are zero, and immediately follows that chunk's last
  save; the sum of successful commit `key_count` values in a pinned window equals its cached block count;
- Decode has no commit;
- whole-key event count is zero.

Parse iteration lines using the built-in format:

```text
Iteration(<n>): <x> context requests, <y> context tokens, <g> generation requests,
<z> generation tokens, iteration elapsed time: <ms> ms
```

Capture an optional `EngineCore_DP<rank>` from the log prefix. Treat lines ending in `(dummy)` as dummy and
never count them as context work.

`topology` inputs and checks:

```text
--prefill-log
--decode-log
--prefill-pod-yaml
--decode-pod-yaml
--prefill-ps
--decode-ps
--prefill-npu-info
--decode-npu-info
--output
```

Require Prefill config `DP=2/TP=2`, Decode `DP=1/TP=2`, 4/2 allocated NPU resources, Prefill process titles
for DP0 and DP1, and active vLLM NPU processes on all assigned devices. Do not infer TP key multiplicity from
Mooncake key count.

`pinned` inputs and checks:

```text
--prefill-log-window
--decode-log-window
--expected-prefill-dp-rank
--expected-prompt-tokens
--expected-hit-tokens
--min-context-iterations
--max-context-tokens 1024
--num-layers 27
--output
```

Require the expected Prefill DP rank to be the only rank with non-dummy context work in the window. Require
context iteration count to meet the minimum, every context-token count to be at most 1024, and the context
token sum to equal expected prompt tokens. The isolated window attributes its ranged events to that pinned
request; do not require every range line itself to contain a DP rank.

For S1, expected hit tokens are 16256 and minimum iterations are 16. For the S3 cold probe, expected hit
tokens on Decode are 32640 and minimum iterations are 32; Prefill hit check must show `0/255` before save.
Both pinned windows require Prefill ranged-load and ranged-save layer sets and the Decode ranged-load layer
set to equal `0..26`. Multiple Prefill commits are required when multiple chunks save new blocks.

`aggregate` inputs and checks:

```text
--prefill-log-window
--decode-log-window
--required-prefill-dp-ranks 0,1
--max-context-tokens 1024
--num-layers 27
--output
```

Require both Prefill ranks to have non-dummy context work, all context iterations to respect the 1024-token
budget, save/load layer union to equal `0..26`, all ranged calls to succeed, at least one successful Prefill
commit, no Decode commit, and zero whole-key events. Do not require event count to equal
`request_count * 27`; the transfer thread may batch requests.

Every checker output uses:

```json
{
  "schema_version": 1,
  "mode": "pinned",
  "status": "passed",
  "validated": true,
  "checks": {},
  "errors": []
}
```

Unknown lines may be ignored, but malformed lines containing `[KVPOOL_RANGE_DEBUG]` or `Iteration(` are
errors. Missing required evidence is always an error.

### 4.8 Host Orchestrator CLI

Implement `deployment/run-stress-test.sh` with this only public interface:

```text
run-stress-test.sh [output-directory]
```

Default output:

```text
/tmp/layerwise-stress-$(date -u +%Y%m%dT%H%M%SZ)
```

Reject a non-empty output directory. Do not add skip, retry, restore, or keep-running flags. The runner always
applies the stress profile, executes S1-S3 in order, captures evidence, stops vLLM, and leaves stress Pods.

Use `set -uo pipefail`, an explicit `overall_rc`, and best-effort collection helpers. Do not use plain
`set -e` in a way that skips failure evidence. The runner must install an EXIT trap that:

1. captures current Pod state and engine/Master/proxy logs if Pod names are known;
2. attempts to stop Prefill and Decode vLLM processes;
3. writes `final-run-state.json` and `runner.exit-code`;
4. never deletes the staging directory.

Implement these shell functions and keep each function single-purpose:

```text
require_command
resolve_running_pod
record_step
collect
stop_engines
reset_master
start_engines
wait_for_http
capture_metrics
capture_role_log
capture_log_window
run_remote_driver
run_log_checker
fail_run
```

Record every major command, start/end timestamp, exit code, and artifact path in `command-transcript.log` and
`steps.jsonl`. `steps.jsonl` uses one JSON object per step and is written with `jq -cn`; do not construct JSON
with shell string concatenation.

The host runner may copy `stress-test.py` into the Prefill Pod under
`/tmp/layerwise-stress-tools/stress-test.py`. It runs workload subcommands in that Pod because the model
tokenizer and cluster-local endpoints are available there. The log checker runs on the host against collected
log windows.

The host runner must not commit or push. The execution agent may create local commits at recoverable
milestones, but GitHub publication occurs only once after runtime evidence, the final report, and offline
verification are complete.

## 5. Implementation Tasks

Execute Tasks 1-5 before touching live cluster state.

### Task 1: Add Stress Manifests

- [ ] Create `deployment/stress/README.md`.
- [ ] Create the stress ConfigMap with the exact startup contract in section 4.1.
- [ ] Create full Prefill/Decode stress Deployments by copying the current manifests and changing only the
      approved ConfigMap name, NPU count, and stress-specific identity annotations if useful.
- [ ] Confirm both Deployment containers still execute `sleep infinity`.
- [ ] Confirm there is no source hostPath mount.
- [ ] Run:

  ```bash
  kubectl apply --dry-run=client \
    -f features/kv-pool-layerwise-reuse/deployment/stress/10-runtime-config.yaml \
    -f features/kv-pool-layerwise-reuse/deployment/stress/40-prefill-engine.yaml \
    -f features/kv-pool-layerwise-reuse/deployment/stress/50-decode-engine.yaml
  ```

- [ ] Inspect dry-run output for ConfigMap plus exactly two Deployments.

### Task 2: Implement Fixture And HTTP Driver

- [ ] Add `stress-test.py` with the five fixed subcommands.
- [ ] Keep fixture generation pure and callable from unit tests without tokenizer/network access by accepting a
      tokenizer-like dependency in helper functions.
- [ ] Implement deterministic block-layout validation before file writes.
- [ ] Implement exact response signature and marker isolation helpers by adapting the existing smoke code.
- [ ] Implement endpoint discovery and direct/proxy request paths.
- [ ] Persist all raw responses before failing.
- [ ] Implement atomic state and summary writes.
- [ ] Add `test_stress_test.py` covering:
  - S1/S2/S3 block arithmetic and expected key counts;
  - shared prefix and fully distinct unique blocks;
  - marker in cached region and absent from tail;
  - tail length bounds;
  - deterministic seeds/request IDs;
  - exact versus normalized response comparison;
  - foreign-marker rejection;
  - missing actions rejected by `finalize`;
  - failed summary written before exception.

Do not unit-test live HTTP or import torch/NPU in these tests.

### Task 3: Implement The Fail-Closed Log Checker

- [ ] Extract or duplicate only the minimal ranged parsing logic from `check-range-debug-log.py`; do not modify
      the historical checker.
- [ ] Implement topology, pinned, and aggregate modes.
- [ ] Parse DP rank and dummy markers from log prefixes.
- [ ] Keep range and iteration errors in one output summary.
- [ ] Add `test_check_stress_log.py` covering:
  - valid DP0 and DP1 pinned windows;
  - wrong active DP rank;
  - non-dummy work on two ranks in a pinned window;
  - context chunk over 1024;
  - context-token sum mismatch;
  - fewer than 16/32 iterations;
  - missing/duplicate-safe layer union;
  - invalid JSON after range prefix;
  - ranged byte mismatch and negative result;
  - commit before final save or nonzero commit result;
  - whole-key event;
  - valid aggregate repeated layers from batching;
  - aggregate missing DP1 activity.
  - null/empty/non-empty Prefill transfer metadata matching proxy behavior;
  - valid multiple per-chunk commits and committed-key-count mismatch.

### Task 4: Implement Host Orchestration

- [ ] Add `run-stress-test.sh` with the lifecycle in section 4.8.
- [ ] Make all selectors require exactly one Running Pod.
- [ ] Add read-only preflight before the first `kubectl apply`.
- [ ] Add one-time stress profile apply and Pod recreation.
- [ ] Reuse `sync-vllm-ascend-python.sh`; do not reimplement source sync.
- [ ] Add source checksum capture after sync.
- [ ] Add Master reset and empty metrics gates.
- [ ] Add topology collection/check.
- [ ] Add S1/S2/S3 execution exactly as Tasks 7-11 below specify.
- [ ] Add best-effort EXIT collection and process cleanup.
- [ ] Ensure collection errors affect `overall_rc`.
- [ ] Ensure no path points into the checked-in evidence directory during live execution.

### Task 5: Static Verification And Local Implementation Commit

Run from control repo root:

```bash
bash -n features/kv-pool-layerwise-reuse/deployment/run-stress-test.sh
python3 -m py_compile \
  features/kv-pool-layerwise-reuse/deployment/stress-test.py \
  features/kv-pool-layerwise-reuse/deployment/check-stress-log.py
python3 -m pytest -q \
  features/kv-pool-layerwise-reuse/deployment/tests/test_stress_test.py \
  features/kv-pool-layerwise-reuse/deployment/tests/test_check_stress_log.py
git diff --check
```

If host pytest is unavailable, run the two tests in the existing Prefill Pod with
`TORCH_DEVICE_BACKEND_AUTOLOAD=0`, `PYTHONDONTWRITEBYTECODE=1`, and cache provider disabled, then copy the
pytest log back. Do not install new system packages for these narrow tests.

Review the path-scoped diff. Stage only the approved plan, this execution plan, stress manifests, runner,
checker, workload driver, and their tests. Commit message:

```text
test(kv_pool): add multi-DP TP stress validation
```

Do not push this commit yet. Record its local SHA for the final report, then begin live validation from the
clean committed tree. The final publication task pushes the complete commit chain after all runtime and
offline gates pass.

## 6. Live Execution Tasks

Tasks 6-11 are strictly sequential. No two agents may mutate the cluster concurrently.

### Task 6: Freeze Identity And Preflight

- [ ] Confirm branch and source revisions:

  ```bash
  test "$(git branch --show-current)" = kv-pool-layerwise-reuse
  test "$(git -C repos/vllm rev-parse HEAD)" = ee0da84ab9e04ac7610e28580af62c365e898389
  test "$(git -C repos/vllm-ascend rev-parse HEAD)" = 3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6
  test "$(git -C repos/Mooncake rev-parse HEAD)" = 74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5
  test -z "$(git -C repos/vllm status --porcelain)"
  test -z "$(git -C repos/vllm-ascend status --porcelain)"
  test -z "$(git -C repos/Mooncake status --porcelain)"
  ```

- [ ] Confirm `workspace.lock.json` contains the same commits.
- [ ] Create a new empty UTC staging directory.
- [ ] Capture `git status`, local/remote HEAD, image identity, node JSON, and all current NPU-requesting Pods.
- [ ] Calculate available NPU capacity after excluding the old `app=prefill` and `app=decode` Pods. Require at
      least 6 free `huawei.com/Ascend910` resources on `n1`.
- [ ] Require the local image on `n1`, the model path, and model `max_position_embeddings >= 65536`.
- [ ] Run the existing `check-runtime.py` in both current Pods before replacement if the file is available.
- [ ] Abort before `kubectl apply` if any preflight check fails.

The capacity calculation must count Running and Pending Pods assigned to `n1`, sum container NPU requests,
exclude only the two Deployments being replaced, and never delete another workload to make the check pass.

### Task 7: Apply Profile, Sync Source, And Prove Topology

- [ ] Stop both old vLLM processes using the currently mounted stop script.
- [ ] Apply in this order:

  ```bash
  kubectl apply -f features/kv-pool-layerwise-reuse/deployment/stress/10-runtime-config.yaml
  kubectl apply -f features/kv-pool-layerwise-reuse/deployment/stress/40-prefill-engine.yaml
  kubectl apply -f features/kv-pool-layerwise-reuse/deployment/stress/50-decode-engine.yaml
  ```

- [ ] Do not use `kubectl rollout status` for engine Deployments before vLLM starts; readiness intentionally
      fails while PID 1 only sleeps.
- [ ] Wait for exactly one Prefill and one Decode Pod with phase Running, then save their names.
- [ ] Run `sync-vllm-ascend-python.sh`; confirm it leaves both vLLM processes stopped.
- [ ] Build a list of every Python file synced relative to the image baseline and compare host/Pod SHA-256 in
      both Pods. Save the manifest.
- [ ] Run `/opt/vllm-layerwise/check-runtime.py` in both Pods and save outputs.
- [ ] Restart Mooncake Master while engines are stopped. Wait for Master rollout and save empty metrics.
- [ ] Assert `master_key_count`, `master_allocated_bytes`, and `master_active_clients` are all zero.
- [ ] Start Prefill, then Decode, and wait up to 1800 seconds for both Pods Ready and both `/v1/models` calls.
- [ ] Wait for proxy `/health` and require exactly one endpoint for each role.
- [ ] Capture startup logs, Pod YAML, process trees, and `npu-smi info`.
- [ ] Run checker `topology`; abort if it does not pass.

### Task 8: Execute S1 Pinned 16K

- [ ] Create host and Prefill-Pod scenario directories named `s1-pinned-16k`.
- [ ] Copy the workload driver to the Prefill Pod tool directory.
- [ ] Run `prepare --scenario s1`.
- [ ] Confirm Master is empty, then run `baseline --scenario s1`.
- [ ] Capture Master metrics and require key count remains zero.
- [ ] For cases 0-3, using Prefill ranks `0,1,0,1`:
  1. record Prefill and Decode log line counts;
  2. run `pinned-load` for that case;
  3. capture only newly appended lines from both logs;
  4. read actual prompt tokens from `fixture.json`;
  5. run checker `pinned` with 16256 hit tokens and minimum 16 iterations;
  6. require checker passed before starting the next case;
  7. require cumulative Master key count equals `127 * (case_index + 1)`.
- [ ] Capture final metrics and require 508 keys.
- [ ] Run `finalize --scenario s1` with the four pinned checker summaries.
- [ ] Require `exact_match_count=4`, `isolated_count=4`, and `validated=true`.
- [ ] Copy the complete S1 remote directory and full role logs to host staging before resetting processes.

### Task 9: Reset Between S1 And S2

- [ ] Stop Prefill and Decode vLLM.
- [ ] Capture process state proving both PIDs stopped.
- [ ] Restart Mooncake Master and wait for rollout.
- [ ] Require all three empty metrics to be zero.
- [ ] Start Prefill and Decode with the same scripts; do not apply or recreate engine Pods.
- [ ] Wait for Ready and proxy health.
- [ ] Confirm log files were freshly truncated by the start scripts.

### Task 10: Execute S2 Concurrent 16x8K

- [ ] Create scenario directories named `s2-concurrent-16x8k`.
- [ ] Run `prepare --scenario s2`.
- [ ] Run `baseline --scenario s2` against empty Decode.
- [ ] Require 16 successful baselines and Master key count zero.
- [ ] Record both role log line counts.
- [ ] Run `proxy-load --scenario s2` once. Do not retry individual failures.
- [ ] Capture aggregate Prefill/Decode log windows.
- [ ] Run checker `aggregate` requiring Prefill ranks `0,1`, max 1024 context tokens, all 27 layers, successful
      commits, and zero whole-key events.
- [ ] Capture final metrics and require 288 keys.
- [ ] Run `finalize --scenario s2`.
- [ ] Require `exact_match_count=16`, `isolated_count=16`, `validated=true`, and no HTTP/error cases.
- [ ] Copy all S2 files and full logs to host staging.

### Task 11: Reset And Execute S3 Concurrent 4x32K

- [ ] Repeat the exact process-only/Master reset from Task 9.
- [ ] Create scenario directories named `s3-concurrent-4x32k`.
- [ ] Run `prepare --scenario s3`.
- [ ] Run four direct Decode baselines and require Master key count zero.
- [ ] Record log line counts, then run pinned-load for S3 case 0 on Prefill rank 0.
- [ ] Capture isolated log windows and run checker `pinned` with:
  - expected Prefill rank 0;
  - expected hit tokens 32640 on Decode;
  - minimum 32 context iterations;
  - maximum 1024 context tokens;
  - cold Prefill hit check `0/255`.
- [ ] Require Master key count 255 after the cold probe.
- [ ] Without resetting Master, record new log line counts and run all four S3 cases concurrently through proxy.
- [ ] Capture the aggregate log window and run checker `aggregate`, requiring Prefill DP0 and DP1 activity.
- [ ] Capture final metrics and require 348 keys.
- [ ] Run `finalize --scenario s3` against proxy responses, not the pinned probe response.
- [ ] Require `exact_match_count=4`, `isolated_count=4`, and `validated=true`.
- [ ] Copy all S3 files and full logs to host staging.

## 7. Final Evidence Assembly

### Task 12: Build Overall Summary And Stop Runtime

- [ ] Build `overall-summary.json` from the tracked identity plus topology/S1/S2/S3 summaries using `jq -n`.
- [ ] Set overall `validated=true` only when every required summary is passed.
- [ ] Capture final Master metrics, Pod YAML, proxy endpoints, process trees, NPU info, and logs.
- [ ] Stop both vLLM processes.
- [ ] Confirm PID files are absent and direct `/v1/models` no longer accepts requests.
- [ ] Leave Master, proxy, Prefill sleep Pod, and Decode sleep Pod Running.
- [ ] Record that 6 NPUs remain allocated.
- [ ] Run all final `jq -e` assertions against overall and scenario summaries.
- [ ] Set `runner.exit-code=0` only after collection and assertions succeed.

Minimum overall assertion:

```bash
jq -e '
  .status == "passed" and
  .validated == true and
  .topology.validated == true and
  .scenarios.s1_pinned_16k.validated == true and
  .scenarios.s2_concurrent_16x8k.validated == true and
  .scenarios.s3_concurrent_4x32k.validated == true and
  (.errors | length) == 0
' overall-summary.json
```

### Task 13: Import And Verify Evidence

The final run referenced by the report must be imported whether it passed or failed. If multiple run IDs were
used, import every run referenced by the report; do not present a later pass without linking the earlier
failure that motivated it.

- [ ] Copy the selected staging directory byte-for-byte to:

  ```text
  features/kv-pool-layerwise-reuse/evidence/ranged-api-stress-<UTC>/
  ```

- [ ] Add an evidence-local `README.md` containing identity, status, scenario results, directory map, and key
      evidence links.
- [ ] Update the feature evidence index.
- [ ] Scan for credentials/private material. Internal operational identifiers and IPs are allowed.
- [ ] Find files at or above 95 MiB. If any exist, split logs by scenario or gzip them losslessly and document
      the command. Never omit content to reduce size.
- [ ] Generate checksums from the evidence root, excluding `SHA256SUMS` itself:

  ```bash
  find . -type f ! -name SHA256SUMS -print0 | sort -z | \
    xargs -0 sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS
  ```

- [ ] Re-run offline checkers and `jq -e` assertions against the control-repo copy.
- [ ] Confirm every evidence file is under the intended feature evidence directory.
- [ ] Stage only the evidence directory and evidence index.
- [ ] Commit:

  ```text
  test(kv_pool): archive multi-DP TP stress evidence
  ```
- [ ] Do not push yet. Record the local evidence commit SHA for the report and retain the complete local
      commit chain for Task 15.

## 8. Final Validation Report

### Task 14: Write A Reproducible Report

Create `features/kv-pool-layerwise-reuse/multi-dp-tp-stress-validation-<YYYY-MM-DD>.md`.

Required sections, in this order:

1. `Result`
2. `Identity`
3. `Topology Evidence`
4. `S1 Pinned 16K`
5. `S2 Concurrent 16x8K`
6. `S3 Concurrent 4x32K`
7. `Chunked Prefill Evidence`
8. `Ranged API Evidence`
9. `Performance Observations`
10. `Live Reproduction Runbook`
11. `Offline Evidence Recheck`
12. `Evidence Links`
13. `Final Cluster State`
14. `Limitations`

The report must record:

- implementation commit and evidence commit;
- image digest/config ID and all three source commits;
- actual Pod names, assigned devices, DP/TP evidence, model limits, and serving arguments;
- exact S1/S2/S3 counts, prompt lengths, hit tokens, key counts, response matches, iteration counts, ranged layer
  sets, commits, and whole-key count;
- latency/throughput as observations without pass threshold;
- any failed attempt or deviation referenced by the final conclusion.

The Live Reproduction Runbook must expand all 12 stages from section 8 of the acceptance plan. It must contain
the commands actually used, beginning with `set -euo pipefail` and fixed variables. Do not substitute prose for
commands and do not hide S1/S2/S3 behind only one runner invocation. Include the one-command runner entry point
first, then the expanded manual sequence.

The Offline Evidence Recheck must include executable commands for:

- `sha256sum -c SHA256SUMS`;
- overall/S1/S2/S3 `jq -e` assertions;
- topology, pinned, and aggregate checker replay;
- required path existence and `git ls-tree` tracking checks.

Evidence Links must use relative Markdown links to the pushed evidence directory. At minimum link:

```text
README.md
SHA256SUMS
identity.json
overall-summary.json
topology-summary.json
S1 scenario and pinned checker summaries
S2 scenario and aggregate checker summaries
S3 scenario, cold pinned, and aggregate checker summaries
Prefill/Decode logs for each scenario
final-run-state.json
```

Do not link `/tmp`, `/root`, Pod filesystem paths, or untracked files.

Before the final push, these links target tracked paths in the local commit chain. They become pushed evidence
links when Task 15 publishes that chain.

### Task 15: Verify, Commit, And Publish The Complete Result

- [ ] Check every relative evidence link exists.
- [ ] Check every linked path appears in `git ls-tree -r HEAD` after the evidence commit.
- [ ] Run Bash syntax checks over every fenced `bash` block in the report.
- [ ] Run the report's offline commands exactly as written.
- [ ] Run `git diff --check`.
- [ ] Stage only the report and any intentionally updated feature index/status document.
- [ ] Commit:

  ```text
  docs(kv_pool): document multi-DP TP stress validation
  ```
- [ ] Confirm the local commit chain contains the implementation, every evidence-backed harness correction,
      all referenced failed and passing evidence runs, and the final report.
- [ ] Push exactly once to `origin/kv-pool-layerwise-reuse`:

  ```bash
  git push origin HEAD:kv-pool-layerwise-reuse
  ```

- [ ] Verify local HEAD equals remote branch HEAD.
- [ ] Verify the remote tree contains every evidence and report path linked by the report.

The task is complete only after the single final push makes the implementation, corrections, evidence, and
report commits remotely available. If that push fails, mark the report `publication-blocked`, preserve local
commits, and report the exact authentication/network error; do not alter or rerun a passing validation merely
because publication failed.

## 9. Stop Conditions And Diagnosis Boundaries

Stop the current run after evidence capture if any of these occurs:

- source commit/tree or workspace lock mismatch;
- fewer than 6 schedulable NPUs on `n1`;
- image or model missing;
- Mooncake session/range API check fails;
- more or fewer than one Pod per role;
- stress Pod does not reach Running;
- source checksum mismatch after sync;
- Master is non-empty after reset;
- either engine fails startup or readiness;
- topology checker fails;
- any baseline populates Mooncake;
- any HTTP response is non-200 or missing choices;
- exact response or marker isolation fails;
- DP rank, chunk budget, layer set, bytes, commit, whole-key, or key-count gate fails;
- evidence collection or checksum fails.

For a failure, stop that run, capture best-effort evidence, and preserve its artifact directory. The execution
agent must then diagnose the failure and continue autonomously when the correction is within the validation
harness, manifests, runner, checker, evidence assembly, or documentation. Commit each evidence-backed
correction locally and rerun the complete validation with a new UTC run ID. Never reuse or overwrite a failed
run directory.

New user direction is not required for ordinary harness failures or retries. It is required before changing
the frozen topology or workload, lowering a gate, editing production source, rebuilding the image, performing
a destructive operation, or expanding scope. Until such a boundary is reached, continue through diagnosis,
local repair, static verification, and new-run retry to a final result.

## 10. Completion Checklist

- [ ] Acceptance plan status is Approved.
- [ ] Stress manifests and tools are tracked in local commits before live execution.
- [ ] Static/unit checks pass.
- [ ] One final live run has immutable identity and complete artifacts.
- [ ] S1 proves both Prefill DP ranks with isolated 16K chunk windows.
- [ ] S2 proves 16 concurrent 8K requests through proxy.
- [ ] S3 proves a cold 32K chunk window and 4 concurrent 32K proxy requests.
- [ ] TP2 is proven by config/process/device evidence on both roles.
- [ ] All required ranged events succeed and whole-key count is zero.
- [ ] All cached responses exactly match empty-pool baselines.
- [ ] vLLM processes are stopped and final cluster state is recorded.
- [ ] Evidence is copied into the control repo, checksummed, and committed locally.
- [ ] Final report links tracked evidence and contains step-by-step live/offline reproduction commands.
- [ ] Report is committed locally after all checks pass.
- [ ] The complete implementation, correction, evidence, and report commit chain is published by one final
      GitHub push.
- [ ] Local and remote feature branch HEADs match.
