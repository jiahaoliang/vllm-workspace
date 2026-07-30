# vLLM-Ascend Rebase Full Validation Rerun Tracking

> **For agentic workers:** Execute this checklist inline. Every runtime claim must point to tracked evidence produced by the exact final tooling commit.

**Goal:** Validate vLLM `d02df748bf9e`, vLLM-Ascend `08b4f531d585`, and Mooncake `786c77ff7692` from a clean CANN 9.0.1 ARM64 image across CPU/mock, ranged API, lease, 1P1D, audit, and stress gates.

**Architecture:** The control repo owns tooling, manifests, evidence, and reports; the three nested source repositories remain fixed inputs. Every family gets an independent UTC run ID, transcript, checksums, evidence commit, and self-contained report.

**Tech Stack:** Bash, Python 3.12, pytest, Kubernetes, nerdctl/BuildKit, Ascend 910B, vLLM, vLLM-Ascend, Mooncake.

## Global Constraints

- Umbrella run ID: `20260730T094741Z`.
- Kubernetes workloads use namespace `liangjiahao`; only `buildkitd` uses explicit namespace `default`.
- Image: `docker.io/library/vllm-ascend:kv-pool-layerwise-v0.25.1-a2-08b4f531-20260730`.
- Base image: `quay.io/ascend/cann:9.0.1-910b-ubuntu22.04-py3.12`.
- Do not modify `repos/*`, restore prior workloads, delete Pods, or delete a namespace.
- Preserve untracked `deployment_yaml/` and `dockerfile.vllm23`.
- Historical reports and evidence are read-only.

## Frozen Baseline

| Input | Frozen value | Initial state |
| --- | --- | --- |
| Control | `b9a00db1a2ef4b3718a25cde2990685a17f2e976`, branch `kv-pool-layerwise-reuse` | clean except preserved untracked paths |
| vLLM | `d02df748bf9efd99022f1a062597dc3cb3808485`, detached | clean |
| vLLM-Ascend | `08b4f531d585fbfa5e365fa7d5f5e812bc80ab16`, branch `kv-pool-layerwise-reuse` | clean |
| Mooncake | `786c77ff7692bed58dd99971afef87d6b690cbe3`, detached | clean |
| Lock | `workspace.lock.json`, updated `2026-07-30T16:55:42+08:00` | matches all three source HEADs |
| Cluster | `bke-cluster-admin@bke-cluster` | `m1,n1` Ready; `n2` NotReady |
| Existing workload | `liangjiahao/vllm-ascend-ut` | Running; no serving Pods |
| Builder | `default/buildkitd` | Running on `n1` |

## Gate Tracker

| Gate | Status | Run ID | Started UTC | Ended UTC | Exit code | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Tooling/static | RUNNING | `20260730T094741Z-tooling` | `2026-07-30T09:47:41Z` | - | - | `evidence/full-validation-rerun-20260730T094741Z/tooling/` |
| Image build/identity | PENDING | - | - | - | - | - |
| CPU/mock UT | PENDING | - | - | - | - | - |
| G0 base/runtime identity | PENDING | - | - | - | - | - |
| G1 direct ranged contract | PENDING | - | - | - | - | - |
| Lease expiry | PENDING | - | - | - | - | - |
| G4 runtime audit | PENDING | - | - | - | - | - |
| 1P1D smoke/G3 | PENDING | - | - | - | - | - |
| Stress S1-S3 | PENDING | - | - | - | - | - |
| Report/offline replay | PENDING | - | - | - | - | - |
| Publication | PENDING | - | - | - | - | - |
| Finalizer/resource capture | PENDING | - | - | - | - | - |

## Failure Ledger

| Attempt | Classification | Failed gate | Impact | Disposition |
| --- | --- | --- | --- | --- |
| `20260730T094741Z-tooling-red` | expected tooling precheck | identity/session API/report checker | no runtime result exists | add regression tests and update control tooling before formal runs |
| `20260730T094741Z-tooling-pod-fixture-1` | test harness | identity test could not find root lock/Dockerfile; `60 passed, 1 failed` | no product/runtime result exists | preserve failure; tar-sync real workspace-relative fixture and rerun |
| `20260730T094741Z-tooling-pod-fixture-2` | passed retry | complete control deployment suite; `61 passed` | preliminary only; old UT image | rerun as formal gate after rebuilding the UT Pod with the pinned image |

## Execution Order

- [ ] Upgrade and commit final validation tooling.
- [ ] Build and inspect the pinned ARM64 image.
- [ ] Recreate and validate the CPU-only UT Pod, then run the full CPU/mock gate.
- [ ] Run G0, G1, lease-expiry, G4, and 1P1D smoke with reset/empty-pool gates.
- [ ] Switch to the stress profile and run S1-S3 with reset/empty-pool gates.
- [ ] Commit family evidence, publish self-contained reports, and run offline replay.
- [ ] Stop vLLM child processes and capture retained resource/NPU state.
