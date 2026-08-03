# 2026-08-03 Mooncake Python Overlay Full Validation Tracker

Run ID: `20260803T124415Z`

Status: PASSED

Stable contract: [full-validation-guide.md](full-validation-guide.md)

## Frozen Identity

| Component | Frozen value | Source |
| --- | --- | --- |
| Control branch/base | `kv-pool-layerwise-reuse` / `71f49c9aebf11591a47f047966c70c292ba3b250` | existing pushed checkpoint |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | existing native image |
| vLLM-Ascend image base | `14beaf161cca6f1e044e20529ca96c6554dbbe50` | existing native image |
| vLLM-Ascend final source | `d28c52958a30cebdb7822d56e3dbb0dbe41499bc` | user-authorized Python fix |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3` | existing native image |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1` | explicitly reused; no rebuild |
| Model | `vllm-ascend/DeepSeek-V2-Lite-W8A8` | existing mounted fixture on `n1` |
| Namespace | `liangjiahao` | workspace contract |

The image remains pinned to the 14beaf161 native/dependency state. Only these
files are overlaid from the clean d28c52958 checkout:

- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py`
- `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`

## Failure Attribution And Fix

- [x] Reproduced the prior concurrent warm failure on the existing image and
  Pods: pair 2/3 failed `20/120`, always case 2, while all responses had 25/25
  remote block hits and 3200 hit tokens.
- [x] Proved scheduler `block_ids`, worker `ReqMeta`, local transfer buffers, and
  the actual attention block-table rows agree for failed requests.
- [x] Falsified duplicate-key-only batching and post-transfer NPU synchronize
  hypotheses.
- [x] Identified cross-request rows in one Mooncake ranged batch as the causal
  boundary. Commit `d28c52958` records row ownership and dispatches one
  key-major ranged batch per request.
- [x] Added regression coverage for separate request batches and row-local
  failure filtering. Red before fix; green after fix.
- [x] Runtime causal validation passed twice across independent engine starts:
  `0/120` failures plus `0/120` failures.
- [x] Removed all `[DEBUG-KVPAIR-20260803]` source and bytecode artifacts.
- [x] Source fix pushed and verified at origin with left/right `0 0`.

## Execution Gates

- [x] T0 overlay identity, tooling tests, shell syntax, rendered Python compile,
  manifest dry-run, diff check, and control tooling commit. The frozen runtime
  tooling commit is `faeb2e3978f6db65b503125efc3ec8b71a51b928`.
- [x] U0 dedicated CPU-only `liangjiahao/vllm-ascend-ut` contract and clean
  d28c52958 tar sync.
- [x] U1 complete `tests/ut/distributed/ascend_store` collection: `478 passed`.
- [x] U2 deployment tooling tests, Ruff check/format, targeted py_compile, and
  source/control `git diff --check`.
- [x] G0 base 1P1D deployment, imageID, model/runtime/API identity, stopped-engine
  Master reset, and empty-pool proof.
- [x] G1 direct multi-key/multi-layer ranged API contract and cleanup.
- [x] G2 lease-expiry stale-session and fresh-session recovery contract.
- [x] G4 all 27 physical layer range audit with zero whole-key calls.
- [x] G3 formal four-request smoke with marker ownership, token/usage, and
  request-log correlation.
- [x] S1 DP2/TP2 Prefill plus TP2 Decode pinned long-context scenario.
- [x] S2 16-request concurrent medium-context scenario.
- [x] S3 cold long-context plus concurrent proxy scenario.
- [x] E0 family checksums, offline replay, reports, final stopped process state,
  retained resources, control state update, commit, push, and remote verification.

## Final Gate Summary

| Gate | Result |
| --- | --- |
| T0/U0-U2 | tooling passed; AscendStore `478 passed`; final deployment collection `70 passed` |
| G0 | original ImageID plus exact two-file overlay; four-way checksums equal; final pool empty |
| G1 | 3 keys, 4 layers, 40 API calls, 43/43 cases, 24/24 negative cases |
| G2 | two 31.5 s waits; stale read `-707`; fresh exact recovery |
| G4 | 27 Prefill range saves, one ordered commit, 27 Decode range loads, zero whole-key calls |
| G3 | baseline/direct/proxy 4/4, warmup 5/5, 12/12 hit correlations |
| S1/S2/S3 | all `validated=true`; key arithmetic 508/288/348 |
| Runtime ledger | 163/163 stress steps exited 0 |
| Evidence | 616 files; root `SHA256SUMS` digest `e66b4909df7a3bcf6e870c434f37590aad3927f800dfdfadc1f5c710fc7f4aa5` |
| Final state | engines stopped; Master keys/bytes/clients `0/0/0`; retained Pods unchanged |

## Failure Policy

- Validation-tooling, runner, checker, or manifest defects may be fixed with a
  focused regression test; rerun every affected gate.
- A new vLLM-Ascend production correctness failure stops downstream validation
  and produces a detailed reproduction report. Production source is frozen at
  `d28c52958` for the formal run.
- Transient infrastructure may be retried at most three times without changing
  identity. Stop only if the Kubernetes cluster is reorganized or the same
  infrastructure failure persists.

## Attempt Ledger

| Attempt | Stage | Result | Decision |
| --- | --- | --- | --- |
| diagnosis-base | warm pair 2/3, 120 rounds | FAILED, 20/120 | production correctness defect; instrument source |
| experiment-key-groups | warm pair 2/3, 120 rounds | FAILED, 26/120 | falsified; reverted |
| experiment-npu-sync | warm pair 2/3, 120 rounds | FAILED, 19/120 | falsified; reverted |
| fix-request-batches-a | warm pair 2/3, 120 rounds | PASSED, 0/120 | repeat after independent restart |
| fix-request-batches-b | warm pair 2/3, 120 rounds | PASSED, 0/120 | accept source fix; begin formal run |
| tooling-host-collection | deployment tests on host | NOT RUN, host Python lacked pytest | run in the required dedicated UT Pod; no environment package changes |
| tooling-fixture-1 | deployment tests in UT Pod | FAILED, fixture omitted `workspace.lock.json` and `Dockerfile.a2` | correct the tar root and rerun the complete collection |
| tooling-fixture-2 | deployment tests in UT Pod | PASSED, `68 passed` | add explicit bytecode-disable coverage before freezing tooling |
| tooling-bytecode-format | Ruff format gate | FAILED, new assertion wrapping only | apply Ruff's deterministic formatting and rerun lint, format, and the full collection |
| tooling-final | complete T0 pre-commit gates | PASSED, `69 passed`; 9 identity tests; 10 manifests; 3 embedded Python and 8 embedded shell entries | freeze control tooling before runtime validation |
| ut-checksum-quoting | first four-way checksum command | FAILED, over-escaped `awk` | replace with shell `read`; rerun checksum gate to green |
| lease-post-rollout-read | immediate metrics read after Master restart | FAILED, one `ConnectionRefused` | preserve race; later G4 preflight proved the same reset empty |
| g4-active-client-oracle | pre-request empty assertion | FAILED before request, expected 0 connected clients while two engines were live | require keys/bytes zero and exactly two live clients; rerun request and checker |
| smoke-offline-assertion | first summary replay | FAILED, assumed four warmup operations | require phase-specific counts including five warmups; unchanged runtime summary passed |
| capacity-credential-scan | final publication scan | FAILED, cluster-wide snapshots included unrelated Pod arguments | project namespace/name/node/phase/resources only; add regression; replay capacity unchanged; `70 passed` |
| completion-process-probe | live completion audit | FAILED, `pgrep` matched the probe command itself | use bracketed `ps` pattern; both retained engines confirmed stopped |
| publication-full-tree-ruff | completion audit outside frozen change scope | FAILED on one pre-existing unused checker read and seven pre-existing format differences | do not rewrite the frozen checker after runtime; rerun the formal changed-file source/tooling scope, which passed |

## Current Runtime State

- The retained stress Prefill and Decode Pods use the original image and request
  four plus two NPUs respectively. Their UIDs match the final evidence.
- Both vLLM child processes are stopped and both HTTP endpoints are closed.
- Final d28c52958 Python files are checksum-identical on host, Prefill, Decode,
  and the dedicated CPU-only retained UT Pod.
- Master and proxy are retained; final Master keys, allocated bytes, and active
  clients are all zero.
- Live completion audit at `2026-08-03T14:41:06Z` confirmed the same node UID,
  Pod UIDs, image, overlay checksums, stopped processes, and empty Master. The
  Kubernetes cluster was not reorganized.
- Runtime evidence is committed and pushed at
  `03d13567659a30c2df42521f1a0d384c30d220c1`; all six dated reports pass the
  fail-closed report checker.
- `deployment_yaml/` and `dockerfile.vllm23` are user-owned untracked files and
  must not be staged.
