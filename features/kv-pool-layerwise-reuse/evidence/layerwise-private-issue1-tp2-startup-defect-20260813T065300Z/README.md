# Issue #1 TP2 Startup Defect

Generation 19 stopped before warmup, seed, admission canary, or formal traffic.
The first BULK Prefill TP2 engine failed while constructing the scheduler-side
Mooncake backend with performance metrics enabled.

`_configure_perf_metric_labels()` resolves `get_global_rank()` during
`MooncakeBackend.__init__`. In this scheduler-side construction path, vLLM's
world group is not initialized yet, so `get_world_group()` raises
`AssertionError: world group is not initialized`. The API server consequently
reports EngineCore initialization failure. This is a production-source
correctness defect in the accepted `8653c6c5e` Python patch, not a throughput
result.

The TP1 functional gate did not exercise this TP2 initialization order. The
existing CPU/mock test also replaces `get_global_rank` with a `MagicMock`, so
it cannot catch the defect. Two attempts to build a seconds-long reproduction
are retained under `defect/`; one was blocked by missing Ascend runtime libraries
in a no-NPU container, and one by the CPU/mock environment's `zmq` stub before
the target function. Neither is claimed as the target reproduction.

The live Pod stack was inspected before recovery, but the runner had not yet
archived `/tmp/vllm-prefill.log`; the raw Pod log is therefore unavailable
after deletion. `defect/tp2-startup-stack.txt` is an observation excerpt and
records that limitation explicitly.

Recovery used the runner's own `_restore_pre_run_state()` helper with the
captured pre-run snapshots. It restored the base Prefill/Decode deployments and
`layerwise-runtime-config`, deleted `layerwise-issue1-test1-bulk-c8`, restarted
Mooncake Master, proved Master `0/0/0`, and returned `m1` to four requested and
four free physical `huawei.com/Ascend910` devices. The restored wrappers are
Running with no vLLM engine process.

No four-point performance result exists. Re-entry requires a source fix, a TP2
startup regression gate that does not mock away rank initialization, a wrapper
fix that treats zombie engine PIDs as dead, a new derived image, and a fresh
functional/handoff generation.
