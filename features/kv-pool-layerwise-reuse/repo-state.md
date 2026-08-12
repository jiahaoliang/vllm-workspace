# kv-pool-layerwise-reuse Repo State

Captured At: 2026-08-12T00:51:50+08:00

| Repo | Path | Branch | HEAD | Dirty | Lock Role |
| --- | --- | --- | --- | --- | --- |
| vllm | `repos/vllm` | `detached:54503ecec` | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` | false | Frozen main-verified validation dependency; the corrected lane passed startup and cold concurrent controls in run 20260731T064607Z |
| vllm-ascend | `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool-merge-kv_offload_0723` | `57d3c214e642cdbb529400f0742d1a98a8d38708` | false | Mooncake layerwise KVPool shared-buffer reuse with TP non-save-owner gate preservation |
| Mooncake | `repos/Mooncake` | `detached:df3f74ed` | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` | false | Read-only detached checkout of the frozen Mooncake collaborator session/range implementation with retryable local revoke ownership |

The initial Mooncake shared-buffer policy change is confined to
`layerwise_config.py`. Follow-up fixes cover decode-only gating, partial snapshot
ownership, per-step load draining, decode slot loading, committed snapshot
lifetime, initial pure-consumer partial-load key selection, layout-specific row
state, and TP non-save-owner reuse gates without changing the public slot-release
lifecycle or memcache.

The seven linear commits from `e1675bb` through `535555917` were rewritten as
the single DCO-signed commit `1f306620` with parent `3a34bba9`. The old and new
tips have the identical tree
`01ef10d288deb4c13dbe4e3c4b74e0b5d482c80d`; their endpoint diff is empty,
the rewritten range contains one commit and no merges, and local/origin
left-right is `0 0`. Local recovery ref
`backup/mooncake-reuse-pre-squash-535555917` retains the old tip. This was a
history-only rewrite: no source bytes changed and no new runtime validation is
claimed for the new commit identity.

The latest two-chunk regression uses real send/receive threads and proves that
an MLA non-save-owner rank still publishes the source-layer gate required by
the next shared-buffer occupant. The deterministic test changed from `[False,
False]` to `[True, True]`; the complete AscendStore suite passed `515`, the MLA
regression passed `1`, model-runner reuse passed `3`, and deployment/performance
mocks passed `146`. Ruff, `py_compile`, and `git diff --check` passed against
the source tree represented by `1f306620`.

Commit `57d3c214e642cdbb529400f0742d1a98a8d38708` is a normal DCO-signed child of
`1f306620`. It skips tracker-history reloads only for ordinary Mooncake
layerwise requests whose per-layer HBM buffers remain resident and which have
no explicit remote recovery request. Shared-buffer reuse and explicit recovery
retain the accumulated tracker behavior; tracker ownership, release lifecycle,
and memcache are unchanged. After the Kubernetes reinstall, the current dirty
checkout was tar-synchronized into the recreated CPU-only, no-hostPath
`liangjiahao/vllm-ascend-ut` Pod on `m1`. The new regression passed `1`, the
Mooncake layer-session class passed `27`, and the complete AscendStore
collection passed `516`; `git diff --check` also passed.

The new reusable `linux/arm64` candidate image is
`docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z`
with manifest `sha256:f8592141757f7e9976898858863e12ccd051ac4a3fd6ade7591f78d9769517e3`
and config `sha256:ce20411d6043d3830be7601c654b2c9a1d41fb923395cad2ea2e7ba200ebbbbd`.
Embedded Git HEADs and OCI labels match all three frozen commits;
`pool_worker.py` has SHA-256
`54e3198504a3745b21e172d8e66c4c7c217bbc7642498e3bb4cdbab557b8b6ea`.
The seven Mooncake session/range APIs, AArch64 native modules, dynamic
dependencies, and CPU-only import smoke were verified. This is image and
non-NPU evidence only; it is not a new NPU correctness or performance result.

Functional run `20260809T071622Z` passed the targeted TP2 4096-token REUSE3
canary with 32/32 block hits, 4095 remote load tokens, `vllm_cached=0`, all-zero
commit results, no gate timeout, and final NPU/Master cleanup. The formal
1-NPU baseline, `kv_producer`, and `kv_both` cold/warm matrix also passed with
exact response equality and 61/61 runtime steps. CPU/mock gates passed `515`
AscendStore, `20` role/default, `1` TP non-save-owner regression, `1` MLA,
`3` model-runner, `146` deployment/performance, and `61` performance harness
tests. The 158-file evidence manifest replayed with digest
`e8cf5ce3fbf332dada8c9bfeb6fd1d3ececc6f02b96fe4a0a5b28b6e1b556876`.

Performance run `20260810T043500Z` completed the five-point DP1/16384/c8
matrix with `64/64` successful formal requests per point. Full report checking,
raw and imported checksum replay, and runtime restoration passed. The runtime
evidence and image identity remain attributed to pre-squash source
`535555917`; neither tree equivalence nor `57d3c214e` is a new NPU or
performance run.

Generation-11 non-NPU preparation parameterizes the server node while keeping
the public default `n1`, renders the single-node rerun explicitly onto `m1`,
validates each dataset and writes `attempt-contract.json` before AISBench can
send traffic. The complete performance harness passed `91` tests in the
CPU-only UT Pod. Targeted Ruff 0.16.2 core/import lint passed for all 11 changed
performance Python files, and 20 performance Python files compiled in memory.
Formatter-only churn was removed mechanically while proving that every Python
token remained identical.

The retained CPU-only `liangjiahao/layerwise-performance-aisbench` Pod uses the
exact candidate image and has no NPU or hostPath resources. AISBench is pinned
to `3fd27b4a5fd022fcb5484fb084307f49955491ba` / `3.1.0`; its prepared fixture
contains 8 warmup and 64 formal rows, 72 unique/disjoint request IDs, and 72/72
exact 16384-token re-encodes. The compact preparation root is 7.7 MB under
`/tmp/layerwise-non-npu-readiness-20260811/aisbench-success`; its checksum
manifest digest is
`4d032f8853afd36e34d2e62aace692c3ef96f0e1dad0fe6d59f07cc09aa67d7e`.
The real CPU-only client preflight also passed current-tooling sync, candidate
config marker validation, tokenizer-link validation, and fixture archive; its
2.8 MB root checksum manifest digest is
`f6142f68d2fd4f9a3eb65ce96f0b6ca172fb4c72eafe7bebae2406257383b873`.

The administrator restored the physical Ascend device plugin on `m1`. The
read-only gate now reports exactly eight allocatable
`huawei.com/Ascend910` resources; it reported eight free before validation and
again after cleanup, while deliberately ignoring `huawei.com/vnpu-number`.

Candidate functional run `20260812T023541Z` used the exact `57d3c214e` image
above on `m1`. Its no-reuse baseline, `kv_producer` REUSE3, and `kv_both`
REUSE3 cold/warm requests passed with identical responses. The strict validator
proved all 27 layers, five physical slots, logical memory factor 5.4, and
all-zero ranged save/load/commit results. All 63 runtime ledger steps passed;
each case released its NPU and ended with Mooncake Master `0/0/0`.

Current-candidate CPU/mock reruns passed the complete performance harness
(`91`), focused self-load regression (`1`), Mooncake layer-session class (`27`),
and complete AscendStore suite (`516`) in the no-NPU, no-hostPath UT Pod.
Candidate source-delta Ruff including import checks, performance-delta Ruff
core checks, Python compilation, and `git diff --check` passed. The compact
89-file functional evidence root is
`evidence/shared-buffer-functional-20260812T023541Z`; its checksum manifest
digest is `0c80987652db2189bd8cf7d91b7bd666622696353660b8f32d01eab3a95a3f96`.
