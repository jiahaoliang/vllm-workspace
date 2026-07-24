# Mooncake Ranged API G4 Runtime Audit

## Result

**Status:** Passed.

The user explicitly changed the D1 decision to **Yes** and requested the G4
runtime audit defined by the approved plan. One clean production request proved
that both engines used the physical-layer ranged path for every model layer,
that every returned byte count matched the corresponding fragment sum, that the
prefill committed only after its final ranged save, and that neither engine used
the legacy whole-key path.

## Identity

| Input | Value |
| --- | --- |
| plan | `f2c06f159b326e944129b962de4dcf4b09cc093c` |
| G4 checker/control baseline | `7a09ae11ff00f9500b2ad7a981ef83870c2ac3ee` |
| vLLM | `ee0da84ab9e04ac7610e28580af62c365e898389` |
| vLLM-Ascend runtime source | `849c1a7f1f4643e03de74f6784b69504dd5174b5` |
| Mooncake | `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` |
| image | `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2` |
| image manifest digest | `sha256:661c9bc2c50c1b7253d6f9ec7905cc83f49908ef8cb1919108a5ea828c2cff8d` |
| live image config ID | `sha256:a370384ab214665c3e6d7179aba82d0e5799a290a41370abe372b53f9593283d` |
| model | `vllm-ascend/DeepSeek-V2-Lite-W8A8` |
| physical layers | `27`, read from the captured model `config.json` |
| node / devices | `n1`, two `Ascend910B4` |
| namespace | `ai-inference` |

The image identity remains the G0-G3 base image. G4 used a Python-only sync of
the committed vLLM-Ascend source into the same prefill and decode Pods; neither
engine Pod was replaced. Both live Pods reported the image config ID above.

## Source And Unit Validation

Production changes were limited to the three plan-approved files:

```text
vllm_ascend/envs.py
vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py
vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py
```

Focused tests changed only the three approved test files. The debug variable is
strictly `0` or `1`, defaults to disabled, and returns before constructing the
range payload. Serializer and logger failures are isolated from transfer
results, cleanup, and failure propagation. Events do not contain keys, request
IDs, pointers, GVA values, prompts, or generated text.

Test results:

- three affected files: `138 passed`, 14 existing PyTorch deprecation warnings;
- complete four-file AscendStore target: `248 passed`, the same 14 warnings;
- checker synthetic positive case: passed;
- checker synthetic byte-mismatch, missing-layer, and whole-key case: failed
  closed with all three errors.

`bash format.sh ci` was attempted. Its markdownlint hook could not initialize
because the downloaded Node binary requires unavailable `libatomic.so.1`.
Focused Ruff check and codespell passed. A Ruff whole-file reformat affected
unrelated baseline lines and was discarded; no unrelated formatting remains.

The signed source commit was pushed to
`origin/feature/mooncake-layerwise-kv-pool`, and local and remote SHA matched.

## Runtime Procedure

Both old vLLM processes were stopped before the audit. They required the start
script's final SIGKILL after the 60-second graceful shutdown window. Mooncake
Master was then restarted and reported:

```text
master_key_count 0
master_allocated_bytes 0
master_active_clients 0
```

The committed production Python files were synced to the two existing engine
Pods and matched local SHA-256 values. Both engines were started with
`VLLM_ASCEND_KVPOOL_RANGE_DEBUG=1`; `/proc/<pid>/environ` confirmed the setting
in each process. Both real `/v1/models` endpoints returned HTTP 200. Before the
request, the fresh engine logs contained no completion POST and Master remained
empty. The proxy discovered exactly one prefill and one decode endpoint.

Exactly one non-streaming standard-proxy completion request was sent with
`temperature=0`, seed `2026072304`, 525 prompt tokens, and 16 requested output
tokens. The response was HTTP 200 with one non-empty choice. Each fresh engine
log contained exactly one completion POST, so no other inference traffic was
observed in the audit window. The decoder reported:

```text
kvpool hit tokens: 512, need to load: 512
```

Master ended with four committed keys, 15,925,248 allocated bytes, one batch
put-start, and one batch put-end.

## Checker Result

The machine-readable checker status is `passed` with no errors:

| Assertion | Observed |
| --- | --- |
| prefill save layer set | exactly `0..26`; 27 range events |
| decode load layer set | exactly `0..26`; 27 range events |
| per-event key count | 4 |
| per-key fragments | `[131072, 16384]` bytes |
| per-key requested/result bytes | `147456`; exact match for every event |
| final commit | layer 26, four zero results, after last ranged save |
| prefill whole-key events | 0 |
| decode whole-key events | 0 |

## Evidence

Control-repo evidence directory:

```text
features/kv-pool-layerwise-reuse/evidence/ranged-api-g4-20260723T132919Z/runtime-audit
```

The persistent artifact was imported byte-for-byte into the control repo.
`sha256sum -c SHA256SUMS` passed again in the checked-in directory. Key evidence:

- [SHA256SUMS](evidence/ranged-api-g4-20260723T132919Z/runtime-audit/SHA256SUMS)
- [checker summary](evidence/ranged-api-g4-20260723T132919Z/runtime-audit/range-debug-summary.json)
- [request result](evidence/ranged-api-g4-20260723T132919Z/runtime-audit/request-result.json)
- [prefill log](evidence/ranged-api-g4-20260723T132919Z/runtime-audit/vllm-prefill.log)
- [decode log](evidence/ranged-api-g4-20260723T132919Z/runtime-audit/vllm-decode.log)

The `SHA256SUMS` digest is:

```text
af533b69d6128088bad74dc12dfab95fd31201882ae92577cf0c5908f754181d
```

The artifact contains the complete request and response, model config, both
engine logs, both `/v1/models` responses, empty/final Master metrics, Pod state,
identity, checker source, and machine-readable checker/request summaries. The
completed [G0-G3 evidence](evidence/ranged-api-20260723T094716Z/SHA256SUMS)
was imported separately and was not modified by G4.

## Cleanup And Evidence Boundary

After log collection, both debug vLLM processes were stopped. PID-file,
process-pattern, and direct HTTP checks all confirmed that prefill and decode
vLLM were no longer running. The original engine Pods, proxy Pod, and restarted
Master Pod remained Running; Kubernetes still displayed the engine containers
as Ready during the readiness probe's configured failure window.

G4 proves the physical-layer ranged path for this one clean 1P1D request. It
does not generalize the trace to every production request, and it does not
re-prove shared-owner lifecycle, concurrent isolation, or output equality;
those remain covered by the earlier G2/G3 evidence.
