# KVPool Validation Evidence

This directory contains immutable evidence captured by validation and
diagnostic runs. Unless an entry explicitly states otherwise, the files were
imported byte-for-byte from verified workspace-external archives.

Use the current runbooks linked from the feature
[README](../README.md). Commands and script copies inside archived run
directories describe their original environment and must not be executed as
current test entry points.

The current high-hit formal import follows the three-point design in
[`2026-08-12-layerwise-high-hit-performance-validation-design.md`](../2026-08-12-layerwise-high-hit-performance-validation-design.md).
The older five-point imports remain accepted cold-cache characterizations, but
they do not answer the external Prefix KV high-hit comparison. No diagnostic
performance root is indexed as accepted performance evidence.

## Threshold-0 Test 2 Partial Run 20260817T095300Z

- Evidence:
  [layerwise-issue1-threshold0-partial-20260817T095300Z](layerwise-issue1-threshold0-partial-20260817T095300Z/README.md)
- Result: FAILED/INCOMPLETE. The BULK Prefill `EngineCore` ended with
  `TimeoutError: RPC call to sample_tokens timed out`; no formal BULK result,
  REUSE3 point, ratio, or cleanup proof was produced.
- Contract: DP1/TP2, 32,000 input tokens, 28,800-token shared prefix, output
  1, concurrency 40, `max_num_seqs=6`, `max_num_batched_tokens=32768`, and
  omitted `--long-prefill-token-threshold`.
- Retention: Git contains a focused failure excerpt, expanded argv, source and
  overlay identity, and a complete checksum inventory. The 5,745,189-byte raw
  staging tree remains transient in `/tmp` and is not committed. This failure
  evidence is not accepted performance evidence.

## Layerwise High-Hit Performance Characterization 20260812T135700Z

- Report:
  [layerwise-performance-high-hit-validation-2026-08-12.md](../layerwise-performance-high-hit-validation-2026-08-12.md)
- Evidence:
  [layerwise-performance-high-hit-20260812T135700Z](layerwise-performance-high-hit-20260812T135700Z/)
- Contract: DP1/TP2, 16,384 input tokens, output 1, concurrency 8, one
  repetition, 8 warmup requests, 64 unmeasured seed requests, and 64 formal
  requests for each of BULK, LAYERWISE, and REUSE3. Local prefix caching was
  disabled.
- Hit validation: all `192/192` formal requests loaded exactly 13,312 external
  KV tokens, or `81.25%` of the 16,384-token prompt; inferred local hits were
  zero. Every seed and formal phase completed `64/64` requests.
- Result: request throughput was `1.5476` req/s for BULK, `1.1747` req/s for
  LAYERWISE, and `1.0538` req/s for REUSE3. LAYERWISE/BULK was `0.759046x`;
  REUSE3/LAYERWISE was `0.89708x`; REUSE3/BULK was `0.680925x`.
- Validation: `performance.report check --scope all` returned `valid: true`;
  restoration completed with both engines stopped and Mooncake empty. Raw and
  repository checksum replay both passed.
- Raw `SHA256SUMS` digest:
  `5fe2f5219d82fd33e4763c326df73bc9e5a1583a55aa396ed976b38b66882864`.
- Repository evidence `SHA256SUMS` digest:
  `b4dc6dcd5e494784ab2d47082d78b8ec8f8cc0017c9599f456355a8734446e7f`.
- Report SHA256:
  `d8fed3cf7f5fd33c6829fefaede5199eb9a965547d16e08d97ebc1f2f74412def`.
- Reusable `linux/arm64` image:
  `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z`,
  manifest
  `sha256:f8592141757f7e9976898858863e12ccd051ac4a3fd6ade7591f78d9769517e3`.
- Limits: one topology, one input length, one concurrency, one formal
  repetition, no outlier removal, no significance test, and no capacity-benefit
  claim. This is raw characterization only.

## Layerwise 64-request Performance Characterization 20260810T043500Z

- Report:
  [layerwise-performance-64-request-validation-2026-08-10.md](../layerwise-performance-64-request-validation-2026-08-10.md)
- Evidence:
  [layerwise-performance-20260810T043500Z](layerwise-performance-20260810T043500Z/)
- Result: all five DP1/16384/c8 points passed the exact-matrix checker with
  `64/64` successful formal requests: BULK o128 `0.343` req/s, BULK o1
  `0.3805` req/s, LAYERWISE o128 `0.2337` req/s, LAYERWISE o1 `0.248`
  req/s, and REUSE3 o1 `0.2409` req/s.
- Formal protocol: one 8-request warmup wave and one 64-request formal
  attempt per point, eight formal concurrency waves, `total` stage, and no
  automatic retry or performance timeout.
- Validation: `performance.report check --scope all` returned
  `{"scope":"all","valid":true,"errors":[]}`; restoration completed with
  both engines stopped and Mooncake empty. Raw and imported checksum replay
  both passed.
- Raw `SHA256SUMS` digest:
  `ebbd9f707589748f4cc12bfaa0edd273eb7183a6efe7d003ed85158439d1d093`.
- Repository evidence `SHA256SUMS` digest:
  `723ac36b231edb68a51328ae6c09d87c4f69cb3c6888e534cdc3d5c3fb6341dd`.
- Report SHA256:
  `2d1d3fe91b5710e40213cd05a754cd23bbec8ed638b4859344f83c4cebb669f1`.
- Reusable `linux/arm64` image:
  `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-535555917-df3f74ed-20260809T070557Z`,
  manifest
  `sha256:cf5da7c1da7dcb72f4c22e201d628b9e4aa819f53c15711651ebc9241cb955bc`.
- Limits: one topology, one input length, one concurrency, one formal
  repetition, no outlier removal, no significance test, and no performance
  pass/fail threshold. This is raw characterization only.

## Layerwise Rapid Performance Characterization 20260809T184011Z

- Report:
  [layerwise-performance-rapid-validation-2026-08-10.md](../layerwise-performance-rapid-validation-2026-08-10.md)
- Evidence:
  [layerwise-performance-20260809T184011Z](layerwise-performance-20260809T184011Z/)
- Result: all five DP1/16384/c8 single-wave points passed the exact-matrix
  checker with `8/8` successful requests. Raw request throughput was `0.2063`
  (BULK o128), `0.3743` (BULK o1), `0.1552` (LAYERWISE o128), `0.2320`
  (LAYERWISE o1), and `0.2567` req/s (REUSE3 o1).
- Report coverage: five aggregate point rows, all 40 formal per-request rows,
  and all output-matched direct ratios. Report SHA256 is
  `56443723eec12deba773a4d2de76e510e0c020c78c6c231842d1c6d30cb6bc65`;
  renderer commit is `0f88b7a3d95f9748b86c2ddb49b53dbc00428b61`.
- Direct observation: REUSE3 improved o1 request throughput by `1.10647x`
  over LAYERWISE and reduced median TTFT to `0.933059x`. LAYERWISE did not
  outperform BULK in this single wave; no statistical significance or
  steady-state claim is made.
- Validation: `performance.report check --scope all` returned `valid: true`;
  restoration completed with both engines stopped, no errors, and Mooncake
  keys/allocated bytes at zero.
- Raw `SHA256SUMS` digest:
  `fa9c2bf9b5e73e9eb94f9cb273cb555a4ea0e74fbc49b00a4cd649fc708dd40c`.
- Repository import `SHA256SUMS` digest (1128 entries):
  `01ff2689580656b70cc381af7a382b53f711f9163a60cf0174a3d8d5b995cff4`.
- Reusable `linux/arm64` image:
  `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-535555917-df3f74ed-20260809T070557Z`,
  manifest
  `sha256:cf5da7c1da7dcb72f4c22e201d628b9e4aa819f53c15711651ebc9241cb955bc`.
- Limits: one topology, one input length, one concurrency, one formal wave,
  no outlier removal, no significance test, and no performance pass/fail
  threshold. The result is raw characterization only.

## Native Revoke Ownership Full Validation 20260807T100722Z

- Plan:
  [Mooncake revoke ownership full validation](../implementation-plans/2026-08-07-mooncake-revoke-ownership-full-validation.md)
- Evidence:
  [full-validation-rerun-20260807T100722Z](full-validation-rerun-20260807T100722Z/README.md)
- Umbrella report:
  [full-validation-rerun-2026-08-07.md](../full-validation-rerun-2026-08-07.md)
- Family reports:
  [G1](../ranged-api-validation-2026-08-07.md),
  [lease](../lease-expiry-validation-2026-08-07.md),
  [G4](../ranged-api-g4-validation-2026-08-07.md),
  [1P1D smoke](../deployment/validation-2026-08-07.md), and
  [stress](../multi-dp-tp-stress-validation-2026-08-07.md).
- Result: PASSED. Exact rebuilt `linux/arm64` image source is vLLM
  `54503ece`, vLLM-Ascend `45b2e785`, and Mooncake `df3f74ed`; no Python
  overlay was used. Source/tooling, native-image UT, G0, G1, lease, G4, smoke,
  and stress S1-S3 passed. Stress recorded `164/164` green steps and final
  Master metrics are `0/0/0` with engine children stopped.
- Stress `SHA256SUMS` digest over 392 files:
  `1fd99b15ad418508d0ff97b162fb563f33b3c097aeffbd9f3dc4d8ae3938c88c`.
- Complete run `SHA256SUMS` digest over 797 files:
  `e5a13d163cfd98fe547c44ec22dc6c1c9688a07e42609d885f88935892a37f08`.

## Python Overlay Full Validation 20260803T124415Z

- Plan:
  [Python overlay rerun](../implementation-plans/2026-08-03-python-overlay-full-validation-rerun-20260803T124415Z.md)
- Evidence:
  [full-validation-rerun-20260803T124415Z](full-validation-rerun-20260803T124415Z/README.md)
- Umbrella report:
  [full-validation-rerun-2026-08-03.md](../full-validation-rerun-2026-08-03.md)
- Family reports:
  [G0/G1](../ranged-api-validation-2026-08-03.md),
  [lease](../lease-expiry-validation-2026-08-03.md),
  [G4](../ranged-api-g4-validation-2026-08-03.md),
  [1P1D smoke](../deployment/validation-2026-08-03.md), and
  [stress](../multi-dp-tp-stress-validation-2026-08-03.md).
- Result: PASSED. The unchanged ARM64 image at vLLM-Ascend `14beaf161` was
  validated with the explicit two-file Python overlay at `d28c52958`.
  CPU/mock, G0, G1, lease, G4, four-request concurrent smoke, and stress S1-S3
  all passed. Final vLLM child processes are stopped; the Master is empty and
  the six-NPU stress Pods are retained.
- Stress `SHA256SUMS` digest:
  `da8b8880f80bfef620c0553c6688e26b1eafbee17c312e5a8a6d3be6e8d0bbcf`.
- Final-state `SHA256SUMS` digest:
  `4359c24159d25f5e311b6bcaead3a594e7cd81aae98b4119f00cf6d7e753e2fb`.
- Complete run `SHA256SUMS` digest (616 files):
  `e66b4909df7a3bcf6e870c434f37590aad3927f800dfdfadc1f5c710fc7f4aa5`.

## Full Validation Rerun 20260731T064607Z

- Plan:
  [main-verified rerun](../implementation-plans/2026-07-31-main-verified-full-validation-rerun-20260731T064607Z.md)
- Evidence:
  [full-validation-rerun-20260731T064607Z](full-validation-rerun-20260731T064607Z/README.md)
- Report:
  [full-validation-rerun-2026-07-31.md](../full-validation-rerun-2026-07-31.md)
- Result: the validation-only main/release compatibility mismatch and
  the recorder trailing-whitespace defect are regression-tested and corrected.
  Formal `tooling-r4` passed all 20 recorded gates with `67` deployment tests.
  Image r1 is preserved as checksummed transient-infrastructure evidence;
  image r2 passed the complete static and NPU-backed image identity proof, and
  the corrected-image CPU-only UT family passed. G0 also passed under the main
  lane, including both engine startups and final empty-Master reset. G1 direct
  ranged validation, lease-expiry boundary, and G4 production ranged-call
  audit also passed. Smoke confirmed a concurrent warm layerwise KV-load
  production defect through a warm `9/30` versus cold `0/30` focused
  differential. Stress S1-S3 was intentionally not run after the terminal
  correctness failure.
- Passing tooling `SHA256SUMS` digest:
  `1b57584e8626d8f2afab7edc0b0d261a1cdf9624f555cc004f83293e76b25506`.
- Passing image r2 `SHA256SUMS` digest:
  `c4cac6d81d0887153f63046f3111cf76eebec60b90b30cc45171ae229e0a98db`.
- Passing UT `SHA256SUMS` digest:
  `9fe25f229eddd594ee0fbe15ebc80539a96b71c2665be54160fce2c4d2e27426`.
- Passing G0 `SHA256SUMS` digest:
  `6416863ddba50d3e716cf6f765869c79488c70707adb78b0b6c1a0a28662524c`.
- Passing G1 `SHA256SUMS` digest:
  `637c2451583a108228d67c589b785c35884d29aa323bf1f29dc2b63f2035eee9`.
- Passing lease `SHA256SUMS` digest:
  `5027b79d7453f14c8dbb71e71788f69c5ed3310246c114fe3bf9cf8c36753650`.
- Passing G4 `SHA256SUMS` digest:
  `bf34acfcb48358613a7a3931443e737444d19c6f14770f02e7c10aaa0d872999`.
- Failed smoke `SHA256SUMS` digest:
  `b781d2598c1d7a397a11d650abb9b7448b8354bf20f46762a15844164e35bffb`.
- Smoke evidence commit:
  `25bc3f55546de727fcdddfba0110b3d1d2b93614`.

## Full Validation Rerun 20260730T130225Z

- Report:
  [full-validation-rerun-2026-07-30.md](../full-validation-rerun-2026-07-30.md)
- Evidence:
  [full-validation-rerun-20260730T130225Z](full-validation-rerun-20260730T130225Z/README.md)
- Result: tooling r4, exact ARM64 image identity, and CPU/mock UT passed. G0
  terminated because both engine roles reproduced a production
  vLLM-Ascend/vLLM coordinator keyword ABI defect. G1, lease, G4, smoke, and
  stress were not run.
- G0 `SHA256SUMS` digest:
  `35db818c1ec6ec005e838eeeb17f464ed73f600f8837f78d6e64ee7631e6c212`.
- Post-failure tooling `SHA256SUMS` digest:
  `367db24d7daa19a560a21c5745c207c0cc6a31fe58a47bc0935702bb346a1e10`.
- Evidence commit: `dfe99a1fa7c246f9d84320deac2f143033cec12b`.

## G0-G3

- Report: [ranged-api-validation-2026-07-23.md](../ranged-api-validation-2026-07-23.md)
- Evidence: [ranged-api-20260723T094716Z](ranged-api-20260723T094716Z/SHA256SUMS)
- `SHA256SUMS` digest:
  `e5b4a768485f1aaf2b39d7421ab1c2f1308077f06f8f010f059a640cfb95d1f9`

## G4

- Report:
  [ranged-api-g4-validation-2026-07-23.md](../ranged-api-g4-validation-2026-07-23.md)
- Evidence:
  [ranged-api-g4-20260723T132919Z](ranged-api-g4-20260723T132919Z/runtime-audit/SHA256SUMS)
- `SHA256SUMS` digest:
  `af533b69d6128088bad74dc12dfab95fd31201882ae92577cf0c5908f754181d`

## Multi-DP/TP Stress Validation

- Report:
  [multi-dp-tp-stress-validation-2026-07-25.md](../multi-dp-tp-stress-validation-2026-07-25.md)
- Result: complete S1 to S2 to S3 sequence passed with tokenizer-derived marker
  prefixes as the hard output oracle; full continuation equality is retained as
  a diagnostic.
- Archived runs:
  [014317Z](ranged-api-stress-20260725T014317Z/README.md),
  [015720Z](ranged-api-stress-20260725T015720Z/README.md),
  [030454Z](ranged-api-stress-20260725T030454Z/README.md),
  [031659Z](ranged-api-stress-20260725T031659Z/README.md), and
  [033747Z](ranged-api-stress-20260725T033747Z/README.md).
- Corrected-oracle runs:
  [074648Z lease-failure diagnosis](ranged-api-stress-20260725T074648Z/README.md)
  and [080938Z formal pass](ranged-api-stress-20260725T080938Z/README.md).
- Formal `SHA256SUMS` digest:
  `f800ce9610201024c2d2823374402a7f63318f518d593a9301516f842fcadc53`.

## Lease Expiry Boundary

- Plan:
  [lease-expiry-validation-plan.md](../lease-expiry-validation-plan.md).
- Report:
  [lease-expiry-validation-2026-07-27.md](../lease-expiry-validation-2026-07-27.md).
- Evidence:
  [lease-expiry-20260727T091720Z](lease-expiry-20260727T091720Z/README.md).
- Result: the corrected call sequence passed. There was no pre-commit get. The
  old committed-object get session returned `-707 LEASE_EXPIRED` on layer 1;
  a fresh `batch_get_start` returned `0` and reread layer 1 successfully.
- `SHA256SUMS` digest:
  `73b12568caa02b6464d19143ae18407ccee4658fe17dc37d383d92e2e3bf8726`.

Verify from the control-repo root:

```bash
evidence_root=features/kv-pool-layerwise-reuse/evidence

(cd "${evidence_root}/ranged-api-20260723T094716Z" && \
  sha256sum -c SHA256SUMS)
(cd "${evidence_root}/ranged-api-g4-20260723T132919Z/runtime-audit" && \
  sha256sum -c SHA256SUMS)

for evidence_dir in "${evidence_root}"/ranged-api-stress-20260725T*; do
  (cd "${evidence_dir}" && sha256sum -c SHA256SUMS)
done

(cd "${evidence_root}/lease-expiry-20260727T091720Z" && \
  sha256sum -c SHA256SUMS)
```

Do not edit evidence files in place. A changed artifact requires a new run
identity and a regenerated checksum manifest.
