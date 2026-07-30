# kv-pool-layerwise-reuse Status

Current Phase: 11/11 Mooncake linear integration frozen; full validation terminated at G0 on a production ABI defect

## Baseline

- `repos/vllm`: verified main commit
  `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` declared by the integrated
  vLLM-Ascend branch (release line `v0.25.1`)
- `repos/vllm-ascend`:
  `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723`
  (`14beaf161cca6f1e044e20529ca96c6554dbbe50`), with exactly 11 linear
  Mooncake commits on `collaborator/kv_offload_0723`
  `a46a1dabbc260e8695002969f29528eb555eb583`
- `repos/Mooncake`: collaborator branch `feature/layerwise-kv-session` at PR #2881 head
  `786c77ff7692bed58dd99971afef87d6b690cbe3` (WIP)

## Next Steps

- Resolve the vLLM-Ascend/vLLM coordinator signature mismatch in a separate,
  explicitly authorized source change. The terminated run did not modify
  `repos/*`.
- After a source fix, create a new validation identity and run ID, rebuild the
  complete image, and restart the full sequence from tooling/image/UT through
  G0, G1, lease, G4, smoke, and stress. Do not resume this failed run at G1.
- Preserve run `20260730T130225Z` as immutable failure evidence.

## Latest Validation

- Full validation run `20260730T130225Z` built and proved the exact R4 ARM64
  image, then passed the CPU-only UT gate (`476` AscendStore and `65`
  deployment tests). G0 prestart identity, seven Mooncake APIs, NPU health,
  model hashes, lease TTL, and empty-pool checks all passed. Both Prefill and
  Decode then failed before serving with
  `TypeError: get_kv_cache_coordinator() got an unexpected keyword argument
  'max_num_batched_tokens'`. Static signature evidence shows pinned vLLM
  accepts `max_in_flight_tokens`; the 11 Mooncake commits did not change the
  wrapper. The run terminated before G1, with no production source change.
- Failure cleanup stopped all live vLLM processes, reset Master to zero keys,
  zero allocated bytes, and zero active clients, and retained the UT, Master,
  proxy, Prefill, and Decode Pods. A control-only fix now makes the base
  lifecycle helper classify zombie PIDs correctly; the complete deployment
  collection remained `65 passed` and focused PID tests passed `3` tests.
- The self-contained result is
  `full-validation-rerun-2026-07-30.md`; immutable evidence commit is
  `dfe99a1fa7c246f9d84320deac2f143033cec12b`.

- On 2026-07-30, completed the requested 11/11 linear integration at
  `14beaf161cca6f1e044e20529ca96c6554dbbe50`, pushed it normally, and verified
  source remote equality. The existing CPU-only `liangjiahao/vllm-ascend-ut`
  Pod passed the complete AscendStore suite with `476 passed`; Ruff 0.14.0
  lint/format, Python compilation, range `git diff --check`, merge-base/count,
  subject order, no-merge, protected-ref, and clean-tree gates passed. Full
  image/runtime validation is tracked separately under run
  `20260730T130225Z`.

- Full-validation attempts r1 and r2 exposed control-tooling identity defects,
  not source failures. R1 used a stale vLLM commit and reached the final raw
  `pip check` after both native builds; r2 proved the corrected vLLM wheel uses
  the exact version `0.1.dev1+g54503ecec.empty`, then was terminated before its
  8-character allowlist assumption could fail. Neither attempt loaded an
  image. Attempt r3 pins the observed 9-character version and adds signal-safe
  terminal recording to `run-validation-step.sh`.

- Attempt r3 completed both native builds, the seven-symbol check, and the
  fail-closed raw `pip check` gate. It then failed only because the image probe
  requested `mooncake-transfer-engine` distribution metadata, while this
  Dockerfile installs Mooncake modules directly with CMake and creates no
  `.dist-info`. Attempt r4 uses the existing source-build identity contract:
  exact Git HEAD, installed `store*.so` path, native symbols, and runtime APIs.
  The r3 image was not loaded.

- On 2026-07-30, folded `fix(kv_pool): adapt renamed Mooncake session APIs`
  into rewritten Backend contract commit `700e56cfd`. The remaining 10 commits
  were replayed without conflicts; final source HEAD `08b4f531d` has the exact
  pre-rewrite tree `665e691662fec0292c9f2258e4193dcce01ae949` and was force-pushed
  with an exact lease. The complete CPU/mock AscendStore suite passed `417`
  tests and `63` subtests; Python compilation and `git diff --check` passed.
- On 2026-07-30, rebased the 11 Mooncake layerwise feature commits from
  vLLM-Ascend base `9dcbeaa2a` onto current `upstream/main` `b2f683ca3` and
  force-pushed `origin/feature/mooncake-layerwise-redesign` at
  `4e9bb324613b08e86eaaf95c8d6554ae9ddb5845`. Conflict resolutions preserved
  upstream Memcache `batch_write_finish`, request bookkeeping, key deduplication,
  retention, and GVA-hit behavior together with Mooncake session/range state and
  exception-safe finalization.
- Updated `repos/vllm` to the exact verified main commit `d02df748b` recorded by
  vLLM-Ascend main. The local CPU/mock AscendStore suite passed `417` tests and
  `63` subtests; Python compilation and `git diff --check` passed. Kubernetes was
  unavailable because no kube context is configured, and local Ruff was not
  installed, so neither the dedicated UT Pod nor Ruff was run.
- Public script fix `66d62fd` now handles untagged detached refs and resolves a
  renamed workspace branch to the longest matching feature-directory prefix.
  After merging `main`, both `lock-repos.ps1` and `status-all.ps1` completed;
  all three repo HEADs match `workspace.lock.json`.

- On 2026-07-29, vLLM-Ascend commit
  `b5b65d9bbe325d009ad887fb87b8883b7ecee156` adapted the unchanged internal
  Backend interface to Mooncake's renamed `batch_*_session_*` client methods.
  The dedicated `liangjiahao/vllm-ascend-ut` Pod passed the red/green focused
  gate (`4 failed, 1 passed` before implementation; `5 passed` after), the
  complete Backend file (`80 passed`), and the full AscendStore suite
  (`408 passed`). Ruff 0.14.0 lint passed; both changed files retained the same
  pre-existing whole-file format delta as parent `3f0cbf59c`; in-memory Python
  compilation and `git diff --check` passed.
- The clone-based nerdctl build completed on native `linux/arm64` and loaded
  `vllm-ascend:kv-pool-layerwise-v0.24.0-a2-session-api-20260729` into
  containerd namespace `k8s.io`. Manifest digest is
  `sha256:bd3c7b2324d799c4a1f360bcbc8191cee2e4fa05c58f66bddc5d09bba9ee710f`;
  image labels match vLLM `ee0da84ab`, vLLM-Ascend `b5b65d9bb`, and Mooncake
  `786c77ff`. The Dockerfile's binary symbol gate passed all seven renamed/range
  APIs.

- On 2026-07-29, the Mooncake multi-group layerwise implementation was pushed as
  vLLM-Ascend commit `1800d56dc2ff6553ff0e0f25f63ab9505ff5ac3e`.
  The dedicated `liangjiahao/vllm-ascend-ut` CPU-only Pod passed `454` tests:
  the complete AscendStore suite plus RecomputeScheduler, default Scheduler
  group/block failure patch, and hybrid-recompute rejection targets. Changed-file
  Ruff lint, Python compile, `git diff --check`, and baseline-relative Ruff
  format checks passed. No real model or NPU workload was run.

- The final four-request distinct-cache smoke passed. Each request loaded 12
  shared plus 13 request-specific blocks, followed by the same 15 uncached token
  IDs. The empty-pool baselines were `0/25`; warmup produced exactly 64 Mooncake
  keys; warmed direct decoder and full proxy concurrency both matched all four
  baselines exactly. Per-response logs passed 12/12 checks for `25/25`, 3200 hit
  tokens, and `use_layerwise=True`.
- An earlier same-cache prototype twice observed `CASE_ONE -> CASE_TWO` only on
  the full proxy path, while direct warmed decoder concurrency was correct. That
  fixture loaded identical keys for all requests, so it was an output/request
  isolation signal rather than proof of wrong cache selection. The anomaly did
  not recur in the final distinct-cache run and remains documented as residual
  risk. Neither result claims ranged API coverage; ranged testing is deferred.
  Detailed evidence is in `deployment/validation-2026-07-23.md`.
- On 2026-07-23, the feature deployment smoke passed on two Ascend910B4 NPUs with
  `vllm-ascend/DeepSeek-V2-Lite-W8A8`. This was the original sequential smoke:
  the standard Kubernetes proxy routed both
  requests through one prefiller and one decoder. Starting from an empty Mooncake
  pool, the prefiller logged `0/25` on the first lookup, while the decoder logged
  `25/25`, `kvpool hit tokens: 3200`, and a layerwise load spec. Both HTTP requests
  returned 200. The result and evidence boundary are in
  `deployment/validation-2026-07-23.md`.
- The initial deployment attempt exposed a missing cross-process hash prerequisite:
  without a fixed `PYTHONHASHSEED`, the decoder saw `0/25` even after the producer
  populated Mooncake. Both engine manifests now set `PYTHONHASHSEED=0`, and the
  runtime checker asserts it before startup.

- Folded the accepted MC2/D3 review decisions into vLLM-Ascend orchestration
  commit `9f2aefa59`: Mooncake load timeout now has a bounded fatal drain path without
  early `batch_get_end`, while memcache retains its original drain behavior;
  put-start exception revoke runs on the layer SendingThread control queue.
- Mooncake source remains read-only at collaborator HEAD `786c77ff`; the
  vLLM-Ascend adapter preserves two-argument put-start and four-argument
  ranged-put calls while translating only the renamed session-control method
  names. No Mooncake commit was created or pushed.
- The complete isolated AscendStore CPU suite passed `402` tests. Focused Ruff,
  `py_compile`, `git diff --check`, and all nine rewritten commit checks passed.
  The pre/post-autosquash tree hash is identical. Real Mooncake wheel, memcache
  E2E, and NPU E2E were not run.

- Rebased the feature onto latest `vllm-ascend` `upstream/main`
  `9dcbeaa2ad36bf96789a7f039d11d7cadaf1c384`; the rewritten signed feature HEAD is
  `1c75b507fe268b91a6f4183da0ae6221ffd05568`. The rebase preserved chunk-spanning
  Mooncake session ownership: Worker retains
  `req_id -> keys` and `key -> active request owners`, renews accumulated keys
  on every chunk, promotes only successful PutEnd keys, and calls
  `batch_get_end` only after the final owner releases a shared key.
- The accepted review fixes are folded into that commit: malformed get-start
  cleanup preserves unrelated owners, chunk preparation runs get-start before
  put-start, retry/terminal cleanup uses separate named lifecycle APIs, and a
  request retains ownership of an already-started shared put key when a new
  key's put-start fails.
- The complete isolated AscendStore CPU suite passed `398` tests. Focused Ruff
  lint, `py_compile`, and `git diff --check` passed. New tracker/test files pass
  Ruff format check; no unrelated whole-file formatting was applied to the four
  legacy files with existing format deltas.
- The rebase had semantic conflicts in `kv_transfer.py`, `pool_scheduler.py`, and
  `pool_worker.py`. Resolutions preserve upstream multi-group layer indexing and
  the feature's Mooncake key-major ranges, exception-safe finalization, and
  last-owner session cleanup.
- Real Mooncake wheel contract validation and NPU chunked-prefill E2E remain
  pending; this checkpoint does not claim runtime/NPU validation.
- Folded the accepted cross-layer range-batch test fixup into rewritten builder commit `21bd87100`, then replayed the five later commits without conflicts. Range-diff showed all five later patches unchanged.
- Force-pushed final source HEAD `8cfd1e22f92ee1a40139ea40b487fa5001d1c81f` with an exact `--force-with-lease` against prior remote `6a825ca54761131c9b73c8871a886381c49513d8`.
- On the rewritten HEAD, the complete isolated AscendStore CPU suite passed `362` tests; focused Ruff, format check, full-range `git diff --check`, and all six rewritten commit checks passed.
- Split the former `87c31d1e8` range-transfer commit into four review-sized commits: range batch builder `2b2ae920e`, exception-safe finalization `29f2a8e69`, ranged save `ff2557f74`, and ranged load `89b1a88ea`. The accepted request-accounting and save-key deduplication findings are folded into those commits.
- Replayed session orchestration as `552541f94` and documentation as `6a825ca54`, then force-pushed the rewritten source history with an exact `--force-with-lease` against `a018212f3`.
- On final HEAD `6a825ca54761131c9b73c8871a886381c49513d8`, the isolated AscendStore suite passed `361` tests; focused Ruff, full-range `git diff --check`, and `git show --check` for all 8 feature commits passed.
- Rebasing onto `ader47/feature/new-memcache-layerwise` at `5875ff0b366690c64324d71b47f9409f8cd762da` completed on 2026-07-15.
- The accepted metadata review findings were implemented and folded into the six review-sized commits. The rewritten history was pushed with `--force-with-lease`; its final HEAD is `1143c6470624e8e7d820a841c88117f9df36aebc`.
- On the final rebased HEAD, the CPU AscendStore suite passed with `353 passed`; focused Ruff, full-range `git diff --check`, and `git show --check` for all six commits also passed.
- Rebasing onto the force-updated `ader47/feature/new-memcache-layerwise` at `6d0b2b70c33f70ca8d708870668514afafd1cb7e` completed on 2026-07-16. The collaborator's `d7affe61e` already contains the TP-mismatch initialization fix, so the duplicate local commit was dropped and the review history now contains five commits.
- The Backend contract was adapted to the collaborator's public `ensure_initialized()` API. On the new final HEAD, the CPU AscendStore suite passed with `354 passed`; focused Ruff, full-range `git diff --check`, and `git show --check` for all five commits passed.
- Updated `repos/vllm` to the official v0.24.0 tag `ee0da84ab9e04ac7610e28580af62c365e898389` and re-reviewed the pending Memcache TP-only plan against that source plus vLLM Ascend `bfe697450`. The plan remains applicable with a stricter direct-field validation and Mooncake/Memcache documentation alignment.
- The Windows CPU venv cannot import the real vLLM v0.24.0 package because `vllm._C_stable_libtorch` is unavailable. The baseline review is source-backed, while real cross-repo integration remains pending.
- After switching the checkout, the isolated mock-based AscendStore suite still passed `354` tests.
- Implemented the accepted Memcache TP-only decision and folded the metadata, orchestration, and documentation fixups into the five review commits. Mooncake and Memcache block-key layerwise now reject PP/PCP/DCP greater than one, while TP and non-block-key paths retain their prior behavior.
- On final rewritten HEAD `7ba9937d77189e9bb5703d0bc86727f63d0fd9a9`, the isolated AscendStore suite passed `360` tests; focused Ruff, full-range `git diff --check`, and `git show --check` for all five commits passed.
- Replaced the topology error labels `PP`/`PCP`/`DCP` with the full `ParallelConfig` field names, folded the test and implementation fixups into the metadata and orchestration commits, and rebased onto the latest fetched collaborator head `6d0b2b70c33f70ca8d708870668514afafd1cb7e`.
- On final rewritten HEAD `a018212f32b057f1bdd75b4cbaccd2b132d2e30b`, the isolated AscendStore suite passed `360` tests; focused Ruff, full-range `git diff --check`, and `git show --check` for all five commits passed.
