# Full Validation Rerun 20260731T064607Z Evidence

Status: tooling gate passed in `tooling-r4`; image r1 ended as a transient
infrastructure failure, the unchanged-identity image r2 retry passed, and the
corrected-image CPU-only UT, G0, G1, lease, and G4 families passed. Smoke then
confirmed a concurrent warm layerwise KV-load production defect. Stress S1-S3
was not run.

## Frozen Identity

- vLLM lane: `main-verified`
- vLLM: `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`
- vLLM-Ascend: `14beaf161cca6f1e044e20529ca96c6554dbbe50`
- Mooncake: `786c77ff7692bed58dd99971afef87d6b690cbe3`
- `VLLM_VERSION` override: unset
- Coordinator keyword: `max_in_flight_tokens`
- Target image:
  `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1`

## Tooling Attempts

- [`tooling/`](tooling/summary.json): failed as a validation formatting defect.
  Nineteen of twenty recorded gate steps passed; Ruff 0.14.0 found two
  line-wrap deltas in the new identity regression. The attempt is preserved,
  and its `SHA256SUMS` digest is
  `aa18caf875dcca86934d03faf1622afe026cbcea4d6a37078dd4f7fce51a141f`.
- [`tooling-r2/`](tooling-r2/summary.json): passed after applying the exact Ruff
  diff. All 20 gate steps passed, but the later staged diff check exposed a
  validation-recorder defect: every transcript `COMMAND` line ended in the
  separator space emitted by `printf -v command_text '%q '`. Its original
  `SHA256SUMS` digest remains
  `628a9b9bcbec4b077b8b41d95a745f7d34e6135b017e09deb5ba4294fbc7f8c4`.
- [`tooling-r3/`](tooling-r3/summary.json): failed as a validation scope defect.
  The complete collection passed `67` tests, but Ruff format was accidentally
  broadened to four unchanged historical test files. Those files were not
  modified. Its `SHA256SUMS` digest is
  `bac9d285b042f7c1d7c31ff5aee2942e089aee0bd0c98995ef09d83765f5aa55`.
- [`tooling-r4/`](tooling-r4/summary.json): passed after adding a focused
  recorder regression, trimming only the final command separator, and
  restoring Ruff to the two changed Python tests. All 20 gate steps passed,
  including `67` deployment tests, Ruff, shell/Python checks, three rendered
  ConfigMap Python files, ten manifest dry-runs, source identity/history/diff
  checks, and a transcript trailing-whitespace assertion. Its `SHA256SUMS`
  digest is
  `1b57584e8626d8f2afab7edc0b0d261a1cdf9624f555cc004f83293e76b25506`.

All checksum manifests replay successfully from their own directories. The
run-local `.gitattributes` marks only the two pre-fix command transcripts as
binary so their exact bytes and original manifests remain intact; the r4
transcript is ordinary text. No file under `repos/*` changed. The frozen
tooling checkpoint is `e97b41a046c03f1926f096740765ae13a56329e9`.

## Image Attempts

- [`image-r1/`](image-r1/summary.json): failed as transient infrastructure.
  The cold-cache build had compiled Mooncake and was compiling vLLM-Ascend
  without a source error when `default/buildkitd` and the other platform Pods
  in `default` were killed together at `2026-07-31T08:36:07Z`. The BuildKit
  transport ended with exit `137`; the target tag remained absent. Its
  `SHA256SUMS` digest is
  `8a80443d4f2f4603c528ec653deb386ab689ab9f2c33107bcf9baa7b9c243b33`.
- [`image-r2/`](image-r2/summary.json): passed. The recovered builder was
  explicitly pinned to `n1`; the image is `linux/arm64`, manifest
  `sha256:866ba89f897464a1e38893a57f6e5c3a035c7aba7dfa196fce9646498eaf6d97`,
  and config
  `sha256:c30f98cf41591582bdb78dde264074a834b68137c5c9254e886cb1347f88bf57`.
  Static build gates and the short-lived NPU Prefill proof verified the exact
  source labels and HEADs, main compatibility lane, coordinator signature,
  seven Mooncake APIs, dynamic imports, native libraries, NPU health, Pod
  imageID, and cleanup. Superseded Pod-selection and summary-generation steps
  are retained and classified in the structured summary. Its `SHA256SUMS`
  digest is
  `c4cac6d81d0887153f63046f3111cf76eebec60b90b30cc45171ae229e0a98db`.

## Unit Test Gate

- [`ut/`](ut/summary.json): passed in the recreated dedicated CPU-only
  `liangjiahao/vllm-ascend-ut` Pod. The Pod used the exact image config ID,
  requested no NPU, mounted no host path, driver, or model cache, and was
  retained Running with restart count zero. The complete AscendStore suite
  passed `476` tests, deployment tooling passed `67`, Ruff lint/format and
  Python compilation passed, and the frozen 11-commit source history remained
  clean. Its `SHA256SUMS` digest is
  `9fe25f229eddd594ee0fbe15ebc80539a96b71c2665be54160fce2c4d2e27426`.

## G0 Base Runtime Gate

- [`g0/`](g0/summary.json): passed. Exact-image Prefill and Decode Pods passed
  main-lane, coordinator-signature, seven-API, source HEAD, NPU, native-library,
  model, and hash-seed checks. Both engines reached HTTP readiness and the
  proxy discovered exactly one endpoint for each role; the previous
  coordinator keyword `TypeError` did not recur. Both vLLM child processes were
  stopped afterward and the restarted Master reported zero keys, zero
  allocated bytes, and zero active clients. Its `SHA256SUMS` digest is
  `6416863ddba50d3e716cf6f765869c79488c70707adb78b0b6c1a0a28662524c`.

## G1 Direct Ranged API

- [`g1/`](g1/summary.json): passed in the stopped-engine Prefill Pod against an
  empty Master. Three keys across four layers verified non-zero ranged object
  offsets, exact fragment/result byte sums, equal source/destination content,
  and 24 negative session/range cases. Cleanup and an independent Master reset
  both ended with zero keys, zero allocated bytes, and zero active clients. Its
  `SHA256SUMS` digest is
  `637c2451583a108228d67c589b785c35884d29aa323bf1f29dc2b63f2035eee9`.

## Lease Expiry Boundary

- [`lease/`](lease/summary.json): passed with live TTL `30000 ms` and two
  requested `31500 ms` waits. A slow put committed after the first gap, the
  stale get session returned exact `-707`, and a fresh session recovered the
  remaining layer with exact full-object bytes. Cleanup and the independent
  reset both ended with zero Master metrics. Its `SHA256SUMS` digest is
  `5027b79d7453f14c8dbb71e71788f69c5ed3310246c114fe3bf9cf8c36753650`.

## G4 Production Ranged Audit

- [`g4/`](g4/summary.json): passed for one clean request. Prefill ranged saves
  and Decode ranged loads each covered exactly layers `0..26`; one successful
  Prefill commit followed its final save, every result matched fragment bytes,
  and neither role emitted a whole-key event. The request/response, one-POST
  windows, 512 hit tokens, Master counters, engine cleanup, and zero-metric
  reset are all archived. Its `SHA256SUMS` digest is
  `bf34acfcb48358613a7a3931443e737444d19c6f14770f02e7c10aaa0d872999`.

## 1P1D Smoke

- [`smoke/`](smoke/README.md): failed and terminated the run. The formal
  direct concurrent case 2 response omitted `CASE_TWO` despite `25/25` blocks,
  3200 hit tokens, and `use_layerwise=True`; serial replay passed. A focused
  case 2/case 3 warm replay reproduced 9 failures in 30 rounds, always case 2.
  After an empty-Master reset, the identical cold pair passed 30/30 and all 60
  response IDs correlated with `hit_blocks=0/25`. Both engines were stopped
  and the final Master reset reported zero keys, zero allocated bytes, and zero
  active clients. Its `SHA256SUMS` digest is
  `b781d2598c1d7a397a11d650abb9b7448b8354bf20f46762a15844164e35bffb`.

## Stress S1-S3

Not run. The source-freeze contract requires termination after a confirmed
production correctness defect; no stress manifests were applied.
