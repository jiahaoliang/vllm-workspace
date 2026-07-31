# KVPool Validation Evidence

This directory contains immutable evidence captured by the ranged API,
Multi-DP/TP stress, and lease-expiry validation runs. The files were imported
byte-for-byte from their verified workspace-external archives.

Use the current runbooks linked from the feature
[README](../README.md). Commands and script copies inside archived run
directories describe their original environment and must not be executed as
current test entry points.

## Full Validation Rerun 20260731T064607Z

- Plan:
  [main-verified rerun](../implementation-plans/2026-07-31-main-verified-full-validation-rerun-20260731T064607Z.md)
- Evidence:
  [full-validation-rerun-20260731T064607Z](full-validation-rerun-20260731T064607Z/README.md)
- Current result: the validation-only main/release compatibility mismatch and
  the recorder trailing-whitespace defect are regression-tested and corrected.
  Formal `tooling-r4` passed all 20 recorded gates with `67` deployment tests.
  Image r1 is preserved as checksummed transient-infrastructure evidence;
  image r2 passed the complete static and NPU-backed image identity proof.
  Corrected-image UT and runtime families are not yet run.
- Passing tooling `SHA256SUMS` digest:
  `1b57584e8626d8f2afab7edc0b0d261a1cdf9624f555cc004f83293e76b25506`.
- Passing image r2 `SHA256SUMS` digest:
  `c4cac6d81d0887153f63046f3111cf76eebec60b90b30cc45171ae229e0a98db`.

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
