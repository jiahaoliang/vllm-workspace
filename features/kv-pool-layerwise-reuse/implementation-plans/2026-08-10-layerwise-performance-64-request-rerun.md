# Mooncake Layerwise 64-Request Performance Rerun Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the rapid DP1 benchmark from eight to 64 formal requests per point while keeping warmup at eight, then publish one new checked run.

**Architecture:** Retain the existing contract, fixture, runner, report, and handoff boundaries. Split the shared request-count constant, generate a runtime-concurrency fixture partition, enforce the new counts in the checker, and leave the serving lifecycle unchanged.

**Tech Stack:** Python 3.12, pytest, AISBench 3.1.0, Kubernetes, Mooncake, Ascend910.

## Global Constraints

- Use namespace `liangjiahao` explicitly for UT, client, serving, and cleanup commands.
- Keep DP1, 16384 input tokens, concurrency 8, and the existing five points.
- Use eight warmup requests and 64 formal requests exactly once per point.
- Do not retry a point and do not define a performance timeout.
- Preserve the reusable image and all vLLM, vLLM-Ascend, Mooncake, and memcache source.
- Preserve all prior evidence and unrelated untracked files.
- Stop before NPU execution so the user can switch to `gpt-5.6-luna max`.

---

## Task 1: Split The Sampling Contract

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/contract.py`
- Test: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_contract.py`

**Interfaces:**
- Produces: `sample_counts(8) == (8, 64, 1)`.
- Produces: run-contract fields for warmup count, formal count, and eight formal concurrency waves.

- [x] Add assertions for the new counts and contract fields.
- [x] Split `REQUEST_COUNT` into `WARMUP_REQUEST_COUNT=8` and `FORMAL_REQUEST_COUNT=64`.
- [x] Run the complete performance collection in `liangjiahao/vllm-ascend-ut`; `70 passed`.

## Task 2: Align Fixtures, Runner, And Evidence Validation

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/runner.py`
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/report.py`
- Test: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_fixtures.py`
- Test: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_runner.py`
- Test: `features/kv-pool-layerwise-reuse/deployment/performance/tests/test_report.py`

**Interfaces:**
- Consumes: `sample_counts(8)`.
- Produces: `tokens-16384-c8` with disjoint 8-request warmup and 64-request formal partitions.
- Produces: a checker requiring 64 successful formal details and eight concurrency waves.

- [x] Update fixture cardinality and request metadata assertions.
- [x] Generate and archive the runtime-concurrency fixture at `tokens-16384-c8`.
- [x] Require 64 formal request rows and mark the formal attempt as multi-wave.
- [x] Run the complete `performance/tests` collection in the CPU-only UT Pod; `70 passed`.

## Task 3: Freeze Documentation And Handoff

**Files:**
- Modify: `features/kv-pool-layerwise-reuse/deployment/performance/README.md`
- Create: `features/kv-pool-layerwise-reuse/2026-08-10-layerwise-performance-64-request-rerun-design.md`
- Modify: `features/kv-pool-layerwise-reuse/performance-validation-handoff.md`

**Interfaces:**
- Produces: an executable 64-request runbook and a handoff-only successor generation.

- [ ] Run static checks and `git diff --check`.
- [ ] Commit and push performance tooling and documentation.
- [ ] Publish a handoff-only direct child freezing the new parent commit and request contract.
- [ ] Run the handoff checker and stop at the requested model-switch boundary.

## Task 4: Execute And Publish The Real Run

**Files:**
- Create: `features/kv-pool-layerwise-reuse/evidence/layerwise-performance-<run-id>/`
- Create: `features/kv-pool-layerwise-reuse/layerwise-performance-64-request-validation-2026-08-10.md`
- Modify: `features/kv-pool-layerwise-reuse/performance-validation-handoff.md`

**Interfaces:**
- Consumes: the accepted successor handoff and unchanged validated image.
- Produces: five aggregate rows, 320 formal request rows, checksums, restoration evidence, and final ratios.

- [ ] After the user confirms the model switch, regenerate exact fixtures with `prepare`.
- [ ] Run DP1 once in a new root with no retry and no performance timeout.
- [ ] Check evidence, render the report, replay checksums, and verify restoration.
- [ ] Import only the new immutable evidence, commit, push, and prove remote equality.
