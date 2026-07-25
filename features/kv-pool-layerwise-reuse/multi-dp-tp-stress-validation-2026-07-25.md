# Multi-DP/TP Stress Validation Report

## Result

**Status:** Failed closed.

The stress topology and Mooncake ranged layerwise path worked, but the frozen
exact-response gate did not pass. Run `20260725T031659Z` passed S1 and reached
S2 with all 16 proxy requests successful, then produced only 8/16 exact
baseline matches. An unchanged-strength retry, `20260725T033747Z`, reproduced
the divergence in S1 case 3 and produced 3/4 exact matches.

No acceptance condition was weakened. No production source was modified. S3
was not executed because the runner stops the current run at the first failed
gate. This report therefore does not validate the 32K scenario.

## Identity

| Item | Value |
|---|---|
| implementation commit | `be77d47` |
| terminating-Pod resolver correction | `4d5a17e` |
| runtime-contract correction | `2dc15c7` |
| autonomous execution policy | `76213e5` |
| Master readiness correction | `91f75ea` |
| evidence commit | `4acd08cc90fa0aa78c1017c742c441f15bc20329` |
| image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2` |
| image digest | `sha256:661c9bc2c50c1b7253d6f9ec7905cc83f49908ef8cb1919108a5ea828c2cff8d` |
| image config ID | `sha256:a370384ab214665c3e6d7179aba82d0e5799a290a41370abe372b53f9593283d` |
| vLLM | `ee0da84ab9e04ac7610e28580af62c365e898389` |
| synced vLLM-Ascend | `3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6` |
| image vLLM-Ascend baseline | `663209fd6208a59a48742f75116345bf5f5281ec` |
| Mooncake | `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` |
| model | `vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| namespace / node | `ai-inference` / `n1` |

The image label records the image baseline. The tracked sync helper copied the
changed Python files from vLLM-Ascend `3f0cbf5` into both retained Pods, and
`source-checksums.tsv` proves host/Prefill/Decode equality for each copied file.

## Topology Evidence

The topology checker passed in both workload-bearing runs:

- Prefill: one Pod, 4 Ascend910 devices, `DP=2`, `TP=2`, active DP0 and DP1
  processes;
- Decode: one Pod, 2 Ascend910 devices, `DP=1`, `TP=2`;
- both containers retained `sleep infinity` as PID 1 and vLLM was managed as an
  in-Pod process;
- `--max-model-len 65536`, `--max-num-batched-tokens 1024`,
  `--max-num-seqs 16`, and `--enable-chunked-prefill` were present.

See [topology summary](evidence/ranged-api-stress-20260725T033747Z/topology/check.json),
[Prefill process tree](evidence/ranged-api-stress-20260725T033747Z/topology/prefill-ps.txt),
[Decode process tree](evidence/ranged-api-stress-20260725T033747Z/topology/decode-ps.txt),
[Prefill NPU info](evidence/ranged-api-stress-20260725T033747Z/topology/prefill-npu-info.txt),
and [Decode NPU info](evidence/ranged-api-stress-20260725T033747Z/topology/decode-npu-info.txt).

## S1 Pinned 16K

Run `20260725T031659Z` passed S1 completely:

| Gate | Observed |
|---|---|
| requests | 4, pinned to Prefill ranks `0,1,0,1` |
| prompt length | 16274 tokens each |
| cached boundary | 127 blocks / 16256 tokens |
| exact output | 4/4 |
| marker isolation | 4/4 |
| Master keys | 508 |
| per-request chunk iterations | 16 |
| maximum context chunk | 1024 tokens |
| per-request committed keys | 127 |
| whole-key events | 0 |

The unchanged retry completed the same ranged and key-count gates but failed
output equality at case 3. Its empty-pool text ended with
`Question: Return exactly...`; its cached Decode text repeated
`S1_CASE_03 private...`. Both carried 24 completion tokens, 16274 prompt
tokens, the correct own marker, and no foreign marker. The retry summary is
[here](evidence/ranged-api-stress-20260725T033747Z/s1-pinned-16k/remote-artifacts-after-failure/scenario-summary.json).

## S2 Concurrent 16x8K

Run `20260725T031659Z` reached and executed S2:

| Gate | Observed |
|---|---|
| empty-pool baseline | 16/16 HTTP 200; Master remained at 0 keys |
| proxy load | 16/16 HTTP 200 |
| prompt length | 8082 tokens each |
| concurrency | 16 requests in one `asyncio.gather` |
| Prefill DP activity | DP0 and DP1 |
| context iterations | 44 aggregate |
| maximum context chunk | 1024 tokens |
| Prefill range layers | load/save `0..26` |
| Decode range layers | load `0..26` |
| commits / committed keys | 38 / 288 |
| Master keys | 288 |
| whole-key events | 0 |
| marker isolation | 16/16 |
| exact output | **8/16, failed** |

Cases 4, 5, 6, 9, 10, 12, 13, and 15 differed from their empty-pool response
signatures. The raw [baseline](evidence/ranged-api-stress-20260725T031659Z/s2-concurrent-16x8k/remote-artifacts-after-failure/baseline/case-04.json)
and [proxy response](evidence/ranged-api-stress-20260725T031659Z/s2-concurrent-16x8k/remote-artifacts-after-failure/proxy/case-04.json)
for case 4 show the two observed greedy continuations. The complete result is
in the [S2 summary](evidence/ranged-api-stress-20260725T031659Z/s2-concurrent-16x8k/remote-artifacts-after-failure/scenario-summary.json).

## S3 Concurrent 4x32K

**Not executed.** Run `20260725T031659Z` stopped at the S2 exact-output gate.
The retry stopped at the reproduced S1 exact-output gate. Running S3 after
either failure would have violated the approved fail-closed sequence and made
the state inheritance uncertain. No 32K result is claimed.

## Chunked Prefill Evidence

The chunked-prefill mechanism itself passed the observed gates. Every isolated
16K request produced 16 non-dummy context iterations, summed to 16274 tokens,
and never exceeded the configured 1024-token budget. The S2 concurrent window
recorded 44 context iterations with the same 1024-token maximum.

The four retry checker files are [case 0](evidence/ranged-api-stress-20260725T033747Z/s1-pinned-16k/case-0-check.json),
[case 1](evidence/ranged-api-stress-20260725T033747Z/s1-pinned-16k/case-1-check.json),
[case 2](evidence/ranged-api-stress-20260725T033747Z/s1-pinned-16k/case-2-check.json),
and [case 3](evidence/ranged-api-stress-20260725T033747Z/s1-pinned-16k/case-3-check.json).

## Ranged API Evidence

For each S1 request, Prefill ranged load and save and Decode ranged load covered
every physical layer `0..26`. Each request emitted 16 successful final-layer
commits whose `key_count` sum was 127. Decode emitted no commits. All ranged
results matched requested byte counts, and the checker found zero whole-key
events.

The S2 [aggregate checker](evidence/ranged-api-stress-20260725T031659Z/s2-concurrent-16x8k/aggregate-check.json)
also passed: 2808 Prefill range events, 864 Decode range events, 38 successful
commits, 288 committed keys, both Prefill DP ranks, and zero whole-key events.
This proves ranged API execution, but it does not override the failed response
correctness gate.

## Performance Observations

These are observations, not pass thresholds:

- passing S1 run: cached Decode request mean 5.93 s, min 5.75 s, max 6.18 s;
- S2: 16-request wall time 49.70 s; per-request mean 34.92 s, min 19.35 s,
  max 49.48 s;
- S1 retry: cached Decode request mean 6.07 s, min 5.92 s, max 6.21 s.

## Live Reproduction Runbook

The one-command entries actually used were:

```bash
set -euo pipefail
cd /root/ljh/vllm-workspace

bash features/kv-pool-layerwise-reuse/deployment/run-stress-test.sh \
  /tmp/layerwise-stress-20260725T031659Z
bash features/kv-pool-layerwise-reuse/deployment/run-stress-test.sh \
  /tmp/layerwise-stress-20260725T033747Z
```

Both commands are expected to exit 1 with this source/image combination. The
following expands the runner stages so a future rerun is reproducible. Create a
new UTC directory; never reuse the recorded paths.

### 1. Freeze identity

```bash
set -euo pipefail
cd /root/ljh/vllm-workspace

readonly namespace=ai-inference
readonly node_name=n1
readonly image=docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2
readonly model_path=/root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8
readonly deployment_dir=features/kv-pool-layerwise-reuse/deployment
readonly checker=${deployment_dir}/check-stress-log.py
readonly run_id="$(date -u +%Y%m%dT%H%M%SZ)"
readonly artifact_root="/tmp/layerwise-stress-${run_id}"
test ! -e "${artifact_root}"
mkdir -p "${artifact_root}"

test "$(git branch --show-current)" = kv-pool-layerwise-reuse
test "$(git -C repos/vllm rev-parse HEAD)" = ee0da84ab9e04ac7610e28580af62c365e898389
test "$(git -C repos/vllm-ascend rev-parse HEAD)" = 3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6
test "$(git -C repos/Mooncake rev-parse HEAD)" = 74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5
test -z "$(git -C repos/vllm status --porcelain)"
test -z "$(git -C repos/vllm-ascend status --porcelain)"
test -z "$(git -C repos/Mooncake status --porcelain)"
cp workspace.lock.json "${artifact_root}/workspace.lock.json"
```

### 2. Preflight dependencies

```bash
command -v kubectl jq nerdctl python3 sha256sum
kubectl get node "${node_name}" -o json >"${artifact_root}/node.json"
kubectl get pods -A -o json >"${artifact_root}/pods-before.json"
nerdctl -n k8s.io image inspect "${image}" >"${artifact_root}/image-inspect.json"

prefill_pod="$(kubectl get pod -n "${namespace}" -l app=prefill -o json |
  jq -er '[.items[] | select(.metadata.deletionTimestamp == null and .status.phase == "Running")]
    | if length == 1 then .[0].metadata.name else error("Prefill count") end')"
decode_pod="$(kubectl get pod -n "${namespace}" -l app=decode -o json |
  jq -er '[.items[] | select(.metadata.deletionTimestamp == null and .status.phase == "Running")]
    | if length == 1 then .[0].metadata.name else error("Decode count") end')"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 -c 'import json,sys; c=json.load(open(sys.argv[1]+"/config.json")); assert c["max_position_embeddings"] >= 65536' \
  "${model_path}"
```

### 3. Apply stress profile

This stops existing engines and keeps a 4-NPU Prefill plus 2-NPU Decode
allocation on `n1`.

```bash
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- \
  /opt/vllm-layerwise/stop-engine.sh decode
kubectl apply -f "${deployment_dir}/stress/10-runtime-config.yaml"
kubectl apply -f "${deployment_dir}/stress/40-prefill-engine.yaml"
kubectl apply -f "${deployment_dir}/stress/50-decode-engine.yaml"
kubectl get pod -n "${namespace}" -l app=prefill -w
kubectl get pod -n "${namespace}" -l app=decode -w
```

Resolve the new unique Running Pod names again before continuing.

### 4. Sync and verify source

```bash
"${deployment_dir}/sync-vllm-ascend-python.sh"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 /opt/vllm-layerwise/check-runtime.py
kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- \
  python3 /opt/vllm-layerwise/check-runtime.py

git -C repos/vllm-ascend diff --name-only --diff-filter=ACMRT \
  663209fd6208a59a48742f75116345bf5f5281ec -- vllm_ascend |
  sort -u >"${artifact_root}/synced-python-files.txt"
```

For every listed Python file, compare `sha256sum` on the host and at
`/vllm-workspace/vllm-ascend/<path>` in both Pods. Any mismatch stops the run.

### 5. Reset and start runtime

```bash
kubectl rollout restart -n "${namespace}" deployment/mooncake-master-deployment
kubectl rollout status -n "${namespace}" deployment/mooncake-master-deployment --timeout=300s
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- python3 -c '
import time
from urllib.request import urlopen
deadline=time.monotonic()+60
while time.monotonic()<deadline:
 try:
  print(urlopen("http://mooncake-master-service:9003/metrics",timeout=5).read().decode(),end="")
  raise SystemExit(0)
 except Exception:
  time.sleep(0.5)
raise SystemExit("Master metrics unavailable")
' >"${artifact_root}/master-empty-initial.metrics"
grep -qx 'master_key_count 0' "${artifact_root}/master-empty-initial.metrics"

kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- /opt/vllm-layerwise/start-decode.sh
kubectl wait -n "${namespace}" --for=condition=Ready "pod/${prefill_pod}" --timeout=1800s
kubectl wait -n "${namespace}" --for=condition=Ready "pod/${decode_pod}" --timeout=1800s
```

### 6. Prove topology

```bash
mkdir -p "${artifact_root}/topology"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- cat /tmp/vllm-prefill.log >"${artifact_root}/topology/vllm-prefill.log"
kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- cat /tmp/vllm-decode.log >"${artifact_root}/topology/vllm-decode.log"
kubectl get pod -n "${namespace}" "${prefill_pod}" -o yaml >"${artifact_root}/topology/prefill-pod.yaml"
kubectl get pod -n "${namespace}" "${decode_pod}" -o yaml >"${artifact_root}/topology/decode-pod.yaml"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- ps -efww >"${artifact_root}/topology/prefill-ps.txt"
kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- ps -efww >"${artifact_root}/topology/decode-ps.txt"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- npu-smi info >"${artifact_root}/topology/prefill-npu-info.txt"
kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- npu-smi info >"${artifact_root}/topology/decode-npu-info.txt"
python3 "${checker}" topology \
  --prefill-log "${artifact_root}/topology/vllm-prefill.log" \
  --decode-log "${artifact_root}/topology/vllm-decode.log" \
  --prefill-pod-yaml "${artifact_root}/topology/prefill-pod.yaml" \
  --decode-pod-yaml "${artifact_root}/topology/decode-pod.yaml" \
  --prefill-ps "${artifact_root}/topology/prefill-ps.txt" \
  --decode-ps "${artifact_root}/topology/decode-ps.txt" \
  --prefill-npu-info "${artifact_root}/topology/prefill-npu-info.txt" \
  --decode-npu-info "${artifact_root}/topology/decode-npu-info.txt" \
  --output "${artifact_root}/topology/check.json"
```

### 7. Run S1

The recorded runner copied `stress-test.py` to the Prefill Pod and used these
subcommands. The host runner additionally captured per-request log line
windows and invoked `check-stress-log.py pinned` with ranks `0,1,0,1`.

```bash
readonly remote_tools=/tmp/layerwise-stress-tools
readonly remote_root=/tmp/layerwise-stress-run-${run_id}
readonly s1_remote=${remote_root}/s1-pinned-16k
mkdir -p "${artifact_root}/s1-pinned-16k"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- mkdir -p "${remote_tools}" "${s1_remote}"
kubectl cp -n "${namespace}" -c prefill-engine "${deployment_dir}/stress-test.py" "${prefill_pod}:${remote_tools}/stress-test.py"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 "${remote_tools}/stress-test.py" prepare --scenario s1 --output "${s1_remote}"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 "${remote_tools}/stress-test.py" baseline --scenario s1 --output "${s1_remote}"

ranks=(0 1 0 1)
for index in 0 1 2 3; do
  kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
    python3 "${remote_tools}/stress-test.py" pinned-load --scenario s1 \
    --output "${s1_remote}" --case-index "${index}" \
    --prefill-rank "${ranks[$index]}" --decode-rank 0
done
```

Require 127 additional keys after each case, replay each isolated checker with
`--expected-prompt-tokens 16274 --expected-hit-tokens 16256
--min-context-iterations 16 --max-context-tokens 1024 --num-layers 27`, then
run `finalize`. The second recorded run fails at this final command.

### 8. Reset between scenarios

These commands were executed between S1 and S2 in run `031659Z`:

```bash
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- /opt/vllm-layerwise/stop-engine.sh decode
kubectl rollout restart -n "${namespace}" deployment/mooncake-master-deployment
kubectl rollout status -n "${namespace}" deployment/mooncake-master-deployment --timeout=300s
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- /opt/vllm-layerwise/start-prefill.sh
kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- /opt/vllm-layerwise/start-decode.sh
kubectl wait -n "${namespace}" --for=condition=Ready "pod/${prefill_pod}" --timeout=1800s
kubectl wait -n "${namespace}" --for=condition=Ready "pod/${decode_pod}" --timeout=1800s
```

The S2-to-S3 reset was not executed because S2 failed.

### 9. Run S2

```bash
readonly s2_remote=${remote_root}/s2-concurrent-16x8k
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- mkdir -p "${s2_remote}"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 "${remote_tools}/stress-test.py" prepare --scenario s2 --output "${s2_remote}"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 "${remote_tools}/stress-test.py" baseline --scenario s2 --output "${s2_remote}"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 "${remote_tools}/stress-test.py" proxy-load --scenario s2 --output "${s2_remote}"
```

The runner then captured log windows, ran aggregate checking, required 288
keys, and ran `finalize`. The recorded run failed only at `finalize` because
`exact_match_count` was 8 rather than 16.

### 10. Run S3

These are the tracked continuation commands, but they were **not executed** in
the reported runs. They must only run after S1 and S2 pass in a new run:

```bash
readonly s3_remote=${remote_root}/s3-concurrent-4x32k
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- mkdir -p "${s3_remote}"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 "${remote_tools}/stress-test.py" prepare --scenario s3 --output "${s3_remote}"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 "${remote_tools}/stress-test.py" baseline --scenario s3 --output "${s3_remote}"
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 "${remote_tools}/stress-test.py" pinned-load --scenario s3 \
  --output "${s3_remote}" --case-index 0 --prefill-rank 0 --decode-rank 0
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- \
  python3 "${remote_tools}/stress-test.py" proxy-load --scenario s3 --output "${s3_remote}"
```

Required future gates are a cold `hit_blocks=0/255`, at least 32 context
iterations, 4/4 exact matches, both Prefill DP ranks, layers 0..26, zero
whole-key events, and 348 keys.

### 11. Collect and validate evidence

```bash
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- cat /tmp/vllm-prefill.log >"${artifact_root}/final-vllm-prefill.log"
kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- cat /tmp/vllm-decode.log >"${artifact_root}/final-vllm-decode.log"
kubectl get pod -n "${namespace}" "${prefill_pod}" "${decode_pod}" -o yaml >"${artifact_root}/final-engine-pods.yaml"

readonly evidence_dir=features/kv-pool-layerwise-reuse/evidence/ranged-api-stress-${run_id}
test ! -e "${evidence_dir}"
cp -a "${artifact_root}" "${evidence_dir}"
(
  cd "${evidence_dir}"
  find . -type f ! -name SHA256SUMS -print0 | sort -z |
    xargs -0 sha256sum >SHA256SUMS
  sha256sum -c SHA256SUMS
)
```

### 12. Cleanup and final state

```bash
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- /opt/vllm-layerwise/stop-engine.sh prefill
kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- /opt/vllm-layerwise/stop-engine.sh decode
kubectl exec -n "${namespace}" "${prefill_pod}" -c prefill-engine -- sh -c 'test ! -e /tmp/vllm-prefill.pid && ps -efww'
kubectl exec -n "${namespace}" "${decode_pod}" -c decode-engine -- sh -c 'test ! -e /tmp/vllm-decode.pid && ps -efww'
kubectl get pod -n "${namespace}" -o wide
```

This intentionally retains Master, proxy, and the two `sleep infinity` stress
Pods. Restoring the base 1+1-card profile is a separate deliberate operation.

## Offline Evidence Recheck

Run from the control-repo root:

```bash
set -euo pipefail
readonly evidence_root=features/kv-pool-layerwise-reuse/evidence
readonly run4=${evidence_root}/ranged-api-stress-20260725T031659Z
readonly run5=${evidence_root}/ranged-api-stress-20260725T033747Z
readonly checker=features/kv-pool-layerwise-reuse/deployment/check-stress-log.py

for evidence_dir in ${evidence_root}/ranged-api-stress-20260725T*; do
  (cd "${evidence_dir}" && sha256sum -c SHA256SUMS)
done

jq -e '.validated == true and .exact_match_count == 4 and
  .isolated_count == 4 and .actual_key_count == 508' \
  "${run4}/s1-pinned-16k/artifacts/scenario-summary.json"
jq -e '.validated == false and .exact_match_count == 8 and
  .isolated_count == 16 and .actual_key_count == 288 and
  (.log_validation | all(.validated == true))' \
  "${run4}/s2-concurrent-16x8k/remote-artifacts-after-failure/scenario-summary.json"
jq -e '.validated == false and .exact_match_count == 3 and
  .isolated_count == 4 and .actual_key_count == 508 and
  (.log_validation | all(.validated == true))' \
  "${run5}/s1-pinned-16k/remote-artifacts-after-failure/scenario-summary.json"
jq -e '.engines_stopped == true and .stress_pods_retained == true and
  .allocated_npus_retained == 6' "${run5}/final-run-state.json"

python3 "${checker}" aggregate \
  --prefill-log-window "${run4}/s2-concurrent-16x8k/prefill-window.log" \
  --decode-log-window "${run4}/s2-concurrent-16x8k/decode-window.log" \
  --required-prefill-dp-ranks 0,1 --max-context-tokens 1024 \
  --num-layers 27 --output /tmp/stress-s2-replay.json

git ls-tree -r --name-only HEAD -- features/kv-pool-layerwise-reuse/evidence |
  rg 'ranged-api-stress-20260725T(014317|015720|030454|031659|033747)Z'
```

Pinned and topology replay commands are recorded verbatim in each
`command-transcript.log`; they were also rerun successfully against the
control-repo copy before the evidence commit.

## Evidence Links

- [Evidence index](evidence/README.md)
- [Run 014317Z README](evidence/ranged-api-stress-20260725T014317Z/README.md)
- [Run 015720Z README](evidence/ranged-api-stress-20260725T015720Z/README.md)
- [Run 030454Z README](evidence/ranged-api-stress-20260725T030454Z/README.md)
- [Run 031659Z README](evidence/ranged-api-stress-20260725T031659Z/README.md)
- [Run 031659Z checksums](evidence/ranged-api-stress-20260725T031659Z/SHA256SUMS)
- [Run 031659Z command transcript](evidence/ranged-api-stress-20260725T031659Z/command-transcript.log)
- [Passing S1 summary](evidence/ranged-api-stress-20260725T031659Z/s1-pinned-16k/artifacts/scenario-summary.json)
- [Failed S2 summary](evidence/ranged-api-stress-20260725T031659Z/s2-concurrent-16x8k/remote-artifacts-after-failure/scenario-summary.json)
- [S2 Prefill window](evidence/ranged-api-stress-20260725T031659Z/s2-concurrent-16x8k/prefill-window.log)
- [S2 Decode window](evidence/ranged-api-stress-20260725T031659Z/s2-concurrent-16x8k/decode-window.log)
- [Run 033747Z README](evidence/ranged-api-stress-20260725T033747Z/README.md)
- [Run 033747Z checksums](evidence/ranged-api-stress-20260725T033747Z/SHA256SUMS)
- [Run 033747Z command transcript](evidence/ranged-api-stress-20260725T033747Z/command-transcript.log)
- [Reproduced S1 failure](evidence/ranged-api-stress-20260725T033747Z/s1-pinned-16k/remote-artifacts-after-failure/scenario-summary.json)
- [Static pytest log](evidence/ranged-api-stress-20260725T033747Z/static/pytest.log)
- [Final run state](evidence/ranged-api-stress-20260725T033747Z/final-run-state.json)

## Final Cluster State

The final EXIT trap stopped both vLLM processes and removed their PID files.
The Prefill and Decode Pods remain Running with PID 1 `sleep infinity`; their
readiness probes are expected to be false while vLLM is stopped. Mooncake
Master and proxy remain Running. The stress Pods retain 4+2 Ascend910 devices.

## Limitations

- S3 4x32K was not run because the prerequisite exact-output gate failed.
- The evidence proves ranged APIs, layers, chunk budget, DP/TP topology, key
  counts, and marker isolation; it does not explain the exact greedy output
  divergence.
- Determining whether the divergence is caused by numerical batch invariance,
  cached-KV reconstruction, or another production behavior requires a separate
  production-source investigation. This validation did not authorize or make
  such a change.
