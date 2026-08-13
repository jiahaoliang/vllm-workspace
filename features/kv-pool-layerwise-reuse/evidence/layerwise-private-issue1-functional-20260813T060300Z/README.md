# Issue #1 Seven-File Functional Acceptance

This compact evidence root accepts the derived ARM64 image that combines the
frozen native base with the reviewed vLLM `baf481c7f` and vLLM-Ascend
`8653c6c5e` Python patches. The aggregate seven-file manifest is
`ff6fed10f3f060a7b509625c00331182344deed6f61a10004cabdbf648c96d3d`.

The accepted NPU attempt is `npu/` only. It completed the baseline,
`kv_producer + REUSE3`, and `kv_both + REUSE3` cases with runner exit 0 and an
independent validator PASS. Each case ended with Mooncake Master `0/0/0`, the
isolated resources were deleted, and `m1` returned to four requested and four
free physical `huawei.com/Ascend910` devices.

Two earlier local orchestration attempts and one validator invocation with an
incorrect root argument remain under `/tmp` and are intentionally excluded.
They did not establish a production-source defect and are not part of this
acceptance root.

The CPU gates were rerun against the same clean source identities: focused
instrumentation 191 passed, complete AscendStore 529 passed, env/platform 53
passed with one skipped, and the performance harness 183 passed. Ruff 0.16.2
was unavailable in the current host and UT Pod during the repeat; the image
construction gate had already run it successfully against the same byte-exact
patch, and that result remains a non-repeated validation limit rather than a
new PASS claim.
