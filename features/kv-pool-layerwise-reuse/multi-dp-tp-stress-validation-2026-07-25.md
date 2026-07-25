# Multi-DP/TP Layerwise KVPool Stress Validation

**Date:** 2026-07-25

**Final status:** Passed

**Formal run:** `20260725T080938Z`

## Result

The complete S1 to S2 to S3 sequence passed with the original topology,
request counts, prompt lengths, chunked-prefill budget, and 24-token generation
budget. The final run proves marker correctness and request isolation while
retaining full-continuation differences as diagnostics.

No vLLM, vLLM-Ascend, or Mooncake production source was modified for this
correction. The only runtime configuration correction was increasing the
Mooncake read lease from its 5-second default to 30 seconds after a fail-closed
32K run proved that the default expired during valid layerwise reads.

The top-level result is the [overall summary](evidence/ranged-api-stress-20260725T080938Z/overall-summary.json).

## Identity

| Item | Value |
|---|---|
| oracle and PID correction | `13c820c` |
| 32K read-lease correction / formal control commit | `988f475ffcb578d386e36b1c384f626b103fd2f4` |
| image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2` |
| image digest | `sha256:661c9bc2c50c1b7253d6f9ec7905cc83f49908ef8cb1919108a5ea828c2cff8d` |
| vLLM | `ee0da84ab9e04ac7610e28580af62c365e898389` |
| vLLM-Ascend | `3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6` |
| Mooncake | `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` |
| model | `vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| namespace / node | `ai-inference` / `n1` |
| Prefill | one Pod, `DP=2`, `TP=2`, 4 Ascend910 devices |
| Decode | one Pod, `DP=1`, `TP=2`, 2 Ascend910 devices |
| Master read lease | `30000ms`, confirmed by Deployment and startup log |

The [topology checker](evidence/ranged-api-stress-20260725T080938Z/topology/check.json)
confirmed both Prefill DP processes, all six allocated devices, and the expected
DP/TP split. Both engine containers retained `sleep infinity` as PID 1; vLLM
was started and stopped as an in-Pod child process.

## Correctness Oracle

Each fixture records `expected_marker_text = " " + marker` and obtains
`expected_marker_token_ids` from the model tokenizer with
`add_special_tokens=False`. The observed marker length was 7 tokens for every
case, but neither the driver nor the tests hard-code 7.

Both the empty-pool baseline and cached candidate must satisfy all of these
hard gates:

- response `token_ids` exist and contain exactly 24 generated tokens;
- generated token IDs start with that case's expected marker token IDs;
- text starts with that case's expected marker text and contains no foreign
  marker;
- `prompt_tokens` equals the fixture, `completion_tokens=24`, and
  `finish_reason=length`.

Full 24-token equality, normalized text equality, common token-prefix length,
first divergence position, full token IDs, and full text are retained in the
scenario summary. They do not affect `validated`.

## Scenario Results

| Gate | S1 pinned 4x16K | S2 concurrent 16x8K | S3 concurrent 4x32K |
|---|---:|---:|---:|
| marker prefix | 4/4 | 16/16 | 4/4 |
| marker isolation | 4/4 | 16/16 | 4/4 |
| full exact, diagnostic | 4/4 | 7/16 | 4/4 |
| Master keys | 508 | 288 | 348 |
| Prefill DP ranks | `0,1,0,1` pinned | DP0 and DP1 | DP0 and DP1 |
| max context chunk | 1024 | 1024 | 1024 |
| physical range layers | `0..26` | `0..26` | `0..26` |
| whole-key events | 0 | 0 | 0 |
| result | passed | passed | passed |

### S1: Pinned 4x16K

All four requests passed at Prefill ranks `0,1,0,1`. Each prompt contained
16274 tokens with a 16256-token cached boundary. Each checker observed 16
context iterations, a 1024-token maximum chunk, 127 committed keys, Prefill
range load/save and Decode range load across layers `0..26`, and no whole-key
event. Key count advanced exactly `127,254,381,508`.

See the [S1 summary](evidence/ranged-api-stress-20260725T080938Z/s1-pinned-16k/artifacts/scenario-summary.json)
and [case 0 checker](evidence/ranged-api-stress-20260725T080938Z/s1-pinned-16k/case-0-check.json).

### S2: Concurrent 16x8K

The baseline and proxy phases each issued 16 requests in one
`asyncio.gather`. The empty-pool baseline left Master at zero keys. The proxy
phase returned 16 HTTP 200 responses, exercised both Prefill DP ranks, and
reached exactly 288 keys.

Nine cases (`1,3,4,5,6,8,11,12,15`) differed from their baseline after the
marker. Every first divergence index was 7, while all 16 marker prefixes and
all 16 isolation checks passed. This is the intended diagnostic separation:
the continuation varied, but cache identity did not.

The [aggregate checker](evidence/ranged-api-stress-20260725T080938Z/s2-concurrent-16x8k/aggregate-check.json)
recorded 44 context iterations, 2808 Prefill ranged events, 864 Decode ranged
events, 38 commits, 288 committed keys, layers `0..26`, and zero whole-key
events. See the [S2 summary](evidence/ranged-api-stress-20260725T080938Z/s2-concurrent-16x8k/artifacts/scenario-summary.json).

### S3: Concurrent 4x32K

The four empty-pool baselines left Master at zero. The separate cold pinned
probe then observed Prefill `hit_blocks=0/255`, 32 context iterations totaling
32658 tokens, a 1024-token maximum chunk, and 255 committed keys. Decode loaded
all 255 blocks through ranged APIs across layers `0..26`.

The final four-way proxy phase exercised DP0 and DP1 and added 93 unique keys
for a final count of 348. Its aggregate checker recorded 1026 Prefill ranged
events, 216 Decode ranged events, 12 commits, and zero whole-key events. All
four marker and isolation gates passed.

See the [cold checker](evidence/ranged-api-stress-20260725T080938Z/s3-concurrent-4x32k/pinned-check.json),
[aggregate checker](evidence/ranged-api-stress-20260725T080938Z/s3-concurrent-4x32k/aggregate-check.json),
and [S3 summary](evidence/ranged-api-stress-20260725T080938Z/s3-concurrent-4x32k/artifacts/scenario-summary.json).

## Failure History And Diagnosis

The earlier failures remain evidence, but their full-continuation acceptance
gate is no longer treated as a correctness oracle:

- `20260725T031659Z`: S1 passed; S2 had 16/16 isolation, 288 keys, and all
  ranged gates, but only 8/16 full response signatures matched. The old runner
  stopped before S3.
- `20260725T033747Z`: the unchanged retry had 4/4 isolation, 508 keys, and all
  S1 ranged gates, but only 3/4 full response signatures matched. It stopped at
  S1.

The old failure summaries remain at [031659Z S2](evidence/ranged-api-stress-20260725T031659Z/s2-concurrent-16x8k/remote-artifacts-after-failure/scenario-summary.json)
and [033747Z S1](evidence/ranged-api-stress-20260725T033747Z/s1-pinned-16k/remote-artifacts-after-failure/scenario-summary.json).

A local no-Mooncake control at `/tmp/no-kv-aa-control-20260725T062129Z/`
showed that full continuation variability persists without KVPool. Across
three strict 16-way S2 rounds with the connector disabled, 10/16 cases produced
more than one continuation variant, while all 48 responses started with their
own marker and Master remained at zero keys and zero allocated bytes. Per user
decision, those raw control artifacts are not copied into the control repo.

After the oracle correction, diagnostic run `20260725T074648Z` passed S1 and
S2 but failed closed at the S3 cold Decode request. Prefill produced 255 keys
and Decode found `255/255` blocks, but layers 22 and 23 returned `-707` for all
510 ranged results. Mooncake defines `-707` as `LEASE_EXPIRED`; the Master log
confirmed its 5000ms default, and the Decode operation crossed that deadline.
The archived [diagnostic run](evidence/ranged-api-stress-20260725T074648Z/README.md)
contains the raw response, metrics, and complete logs.

The feature deployment now sets `--default_kv_lease_ttl=30s`. The formal run
confirmed `30000ms` in the [Master startup log](evidence/ranged-api-stress-20260725T080938Z/master-startup.log),
then completed the same 32K load through layer 26. This changes neither the
connector contract nor workload strength; it prevents a valid long transfer
from outliving the Master's default read lease.

## PID Lifecycle

The in-Pod start scripts now remove absent or zombie stale PID files and reject
only live, non-zombie processes. The stop script waits for absent or zombie
state before deleting the PID file. The formal run exercised this on every
scenario reset and final cleanup; the [final state](evidence/ranged-api-stress-20260725T080938Z/final-run-state.json)
records exit 0, both engines stopped, retained stress Pods, and six retained
NPU allocations. Both HTTP endpoints returned connection refused after stop.

## Reproduction Runbook

Run from the control-repo root. Do not reuse an existing run ID or output
directory.

### 1. Verify source and branch identity

```bash
cd /root/ljh/vllm-workspace
test "$(git branch --show-current)" = kv-pool-layerwise-reuse
test "$(git -C repos/vllm rev-parse HEAD)" = ee0da84ab9e04ac7610e28580af62c365e898389
test "$(git -C repos/vllm-ascend rev-parse HEAD)" = 3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6
test "$(git -C repos/Mooncake rev-parse HEAD)" = 74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5
git diff --check
```

### 2. Run offline tests

```bash
python3 -m pytest -q features/kv-pool-layerwise-reuse/deployment/tests
python3 -m py_compile \
  features/kv-pool-layerwise-reuse/deployment/stress-test.py \
  features/kv-pool-layerwise-reuse/deployment/check-stress-log.py
bash -n features/kv-pool-layerwise-reuse/deployment/run-stress-test.sh
```

The formal evidence records [48 passing tests](evidence/ranged-api-stress-20260725T080938Z/static/pytest.log).

### 3. Run the complete sequence

```bash
run_id="$(date -u +%Y%m%dT%H%M%SZ)"
output_dir="/tmp/layerwise-stress-${run_id}"
test ! -e "${output_dir}"
bash features/kv-pool-layerwise-reuse/deployment/run-stress-test.sh \
  "${output_dir}"
```

The runner performs, in order: identity and six-NPU capacity checks; image and
runtime-contract checks; Master/ConfigMap/engine apply; source sync and checksum
comparison; 30-second lease verification; empty-Master reset; topology check;
S1; full stop/reset; S2; full stop/reset; S3; overall assertions; final metrics;
engine stop; PID-file and HTTP-down checks. Any failing step returns nonzero,
copies the active remote scenario and failure metrics, captures complete logs,
and stops both engines.

### 4. Recheck scenario summaries

```bash
evidence=features/kv-pool-layerwise-reuse/evidence/ranged-api-stress-20260725T080938Z

jq -e '.validated and .marker_prefix_match_count == 4 and
  .isolated_count == 4 and .actual_key_count == 508' \
  "${evidence}/s1-pinned-16k/artifacts/scenario-summary.json"
jq -e '.validated and .marker_prefix_match_count == 16 and
  .isolated_count == 16 and .actual_key_count == 288' \
  "${evidence}/s2-concurrent-16x8k/artifacts/scenario-summary.json"
jq -e '.validated and .marker_prefix_match_count == 4 and
  .isolated_count == 4 and .actual_key_count == 348' \
  "${evidence}/s3-concurrent-4x32k/artifacts/scenario-summary.json"
jq -e '.status == "passed" and .validated and .topology.validated' \
  "${evidence}/overall-summary.json"
```

### 5. Recheck immutable evidence

```bash
for evidence_dir in \
  features/kv-pool-layerwise-reuse/evidence/ranged-api-stress-20260725T074648Z \
  features/kv-pool-layerwise-reuse/evidence/ranged-api-stress-20260725T080938Z
do
  (cd "${evidence_dir}" && sha256sum -c SHA256SUMS)
done
```

The SHA256SUMS manifest digests are:

- `074648Z`: `68dfdc82f51cfaa1cb5662d61f1db929b725bfee36d4ded92cc57be8806974c1`;
- `080938Z`: `f800ce9610201024c2d2823374402a7f63318f518d593a9301516f842fcadc53`.

## Validation Boundary

This test validates the KVPool integration boundary: cache-key selection,
per-request marker isolation, full HTTP/usage contracts, multi-DP scheduling,
chunked-prefill accounting, ranged layer coverage, byte-count/result contracts,
commit/key arithmetic, and fail-closed behavior.

It does **not** claim that baseline and cached KV tensors are byte-for-byte
identical. It also does not use full generated-continuation equality as a proxy
for tensor equality. The strongest output claim is exact agreement on each
request's tokenizer-derived marker prefix plus absence of every foreign marker.

## Evidence Index

- [Formal run README](evidence/ranged-api-stress-20260725T080938Z/README.md)
- [Formal checksums](evidence/ranged-api-stress-20260725T080938Z/SHA256SUMS)
- [Formal command transcript](evidence/ranged-api-stress-20260725T080938Z/command-transcript.log)
- [Formal overall summary](evidence/ranged-api-stress-20260725T080938Z/overall-summary.json)
- [Lease-failure diagnostic README](evidence/ranged-api-stress-20260725T074648Z/README.md)
- [Lease-failure diagnostic checksums](evidence/ranged-api-stress-20260725T074648Z/SHA256SUMS)
- [Final stopped state](evidence/ranged-api-stress-20260725T080938Z/final-run-state.json)
- [Offline recheck log](evidence/ranged-api-stress-20260725T080938Z/static/offline-recheck.log)
