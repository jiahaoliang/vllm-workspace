Source: https://github.com/AISBench/benchmark/tree/3fd27b4a5fd022fcb5484fb084307f49955491ba
Captured At: 2026-08-08T13:54:11+08:00
Notes: First-party documentation and source-code contract for the pinned AISBench 3.1.0 checkout at /tmp/aisbench-benchmark-3fd27b4a; the checkout commit was verified and its worktree was clean.

# AISBench Performance Contract At `3fd27b4a`

## Immutable Baseline And Python Support

The inspected checkout resolves exactly to
`3fd27b4a5fd022fcb5484fb084307f49955491ba`. At that commit, the package reports
version `3.1.0` in
[`ais_bench/benchmark/__init__.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/__init__.py#L1),
and its packaging metadata requires Python `>=3.10.0` in
[`setup.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/setup.py#L153-L165).
The project README additionally states that its published multi-architecture
images include `aarch64` with Python 3.10, 3.11, and 3.12 combinations
([`README_en.md`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/README_en.md#L34-L37)).
Consequently, Python 3.12 is inside the declared package range; install success
and the resolved dependency set still need to be captured for the actual client
environment.

## `VLLMCustomAPI` Streaming Contract

`VLLMCustomAPI` targets the OpenAI-compatible `v1/completions` endpoint. Its
constructor exposes `stream`, and the request builder sends `prompt`, `stream`,
`max_tokens`, and the selected model. With streaming enabled it also sends
`stream_options={"include_usage": true}`; streamed text is accumulated and
usage supplies `prompt_tokens` and `completion_tokens`
([`vllm_custom_api.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/models/api_models/vllm_custom_api.py#L15-L31),
[`vllm_custom_api.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/models/api_models/vllm_custom_api.py#L78-L82),
[`vllm_custom_api.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/models/api_models/vllm_custom_api.py#L114-L157)).

The pinned streaming example uses `type=VLLMCustomAPI`, `stream=True`, and
defines `request_rate`, `max_out_len`, `batch_size`, and generation arguments
in one model configuration
([`vllm_api_general_stream.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/configs/models/vllm_api/vllm_api_general_stream.py#L1-L25)).
`max_out_len` becomes request-body `max_tokens`, so one-token and 128-token
profiles must use the corresponding `max_out_len`; `ignore_eos=True` is the
documented way to force a backend that supports it to reach the configured
maximum output length
([performance benchmark guide](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/docs/source_en/base_tutorials/scenes_intro/performance_benchmark.md#L364-L392)).

## `batch_size` And `request_rate`

For a service API model, AISBench defines:

- `batch_size` as the maximum concurrent request count, with documented range
  `(0, 64000]`;
- `request_rate` as requests per second, one request every
  `1 / request_rate` seconds; values below `0.1` cause requests to be merged and
  sent in batches.

These definitions and the warning that a large `batch_size` can load the client
CPU are in the
[`models` parameter reference](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/docs/source_en/base_tutorials/all_params/models.md#L64-L95).
When AISBench pressure mode is used, its steady-stage guide describes
`batch_size` as maximum concurrency, `--pressure-time` as the fixed stress
duration, and `request_rate` as the frequency of adding clients per process
([steady-stage guide](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/docs/source_en/advanced_tutorials/stable_stage.md#L223-L244)).
The effective achieved concurrency and client resource data therefore need to
be retained; configured concurrency alone is not proof that the client reached
or sustained that load.

## `RequestCount` And `--num-prompts`

For a synthetic dataset, `RequestCount` is mandatory, must be an integer in
`[1, 2^20]`, and drives the number of generated dataset entries
([`synthetic.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/datasets/synthetic.py#L128-L168),
[`synthetic.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/datasets/synthetic.py#L266-L287)).
The performance guide likewise labels `RequestCount` as the number of requests
or dataset entries
([performance benchmark guide](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/docs/source_en/base_tutorials/scenes_intro/performance_benchmark.md#L345-L360)).

`--num-prompts` is a separate CLI-side limit: it selects the first positive
number of dataset cases in dataset order; if omitted or larger than the dataset,
AISBench uses the entire dataset
([CLI reference](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/docs/source_en/base_tutorials/all_params/cli_args.md#L25-L38)).
The performance guide explicitly notes that this selection is sequential and
is neither randomized nor shuffled
([performance benchmark guide](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/docs/source_en/base_tutorials/scenes_intro/performance_benchmark.md#L395-L401)).
Thus `RequestCount` establishes available data while `--num-prompts` can only
truncate it; a benchmark must archive both values and use separate prepared
slices when it requires warmup and repetitions to be disjoint.

## `stable_stage` Selection And Duration

Selecting `--summarizer stable_stage` changes metric calculation to requests in
the calculated steady interval
([steady-stage guide](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/docs/source_en/advanced_tutorials/stable_stage.md#L10-L40)).
The implementation constructs start/end concurrency events, finds requests
starting at maximum or near-maximum concurrency, ignores the first request that
reached maximum concurrency, and raises an error if no steady request remains
([`stable_perf_metric_calculator.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/calculators/stable_perf_metric_calculator.py#L62-L181)).
The stable Benchmark Duration is the selected interval end minus start
([`stable_perf_metric_calculator.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/calculators/stable_perf_metric_calculator.py#L184-L203)).

AISBench documents a specific reliability condition for steady-stage
throughput: the maximum single-request E2EL from the entire test must be less
than one third of the reported stable Benchmark Duration. The document warns
that otherwise boundary accounting around ramp-up and ramp-down can distort
throughput
([steady-stage guide](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/docs/source_en/advanced_tutorials/stable_stage.md#L25-L35)).
This is the first-party basis for increasing the request count and rerunning an
insufficient-duration point instead of treating that result as valid raw
throughput evidence.

## Metrics And One-Token Boundary

AISBench defines per-request E2EL, TTFT, TPOT, ITL, input/output token counts,
output-token throughput, and Prefill-token throughput. It separately reports
common metrics including Benchmark Duration, request counts, concurrency,
request throughput, and input/output/total token throughput
([performance metric reference](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/docs/source_en/base_tutorials/results_intro/performance_metric.md#L1-L17),
[`performance_metric.md`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/docs/source_en/base_tutorials/results_intro/performance_metric.md#L31-L45)).
The implementation computes per-request Prefill-token throughput as
`input_tokens / ttft`, and removes TTFT or TPOT when the accumulated values are
zero
([`base_perf_metric_calculator.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/calculators/base_perf_metric_calculator.py#L364-L388)).
It sets TPOT and ITL sample count to requests that actually have decode latency
([`base_perf_metric_calculator.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/calculators/base_perf_metric_calculator.py#L390-L430)).

Accordingly, a `max_tokens=1` run has no multi-token Decode interval on which to
base TPOT or ITL. Its useful raw characterization fields are TTFT, E2EL, input
token throughput, request throughput, achieved concurrency, token counts, and
request validity. The 128-token profile can additionally use output token
throughput, TPOT, and ITL.

Common throughput is calculated from successful requests or tokens divided by
the selected Benchmark Duration
([`base_perf_metric_calculator.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/calculators/base_perf_metric_calculator.py#L481-L523)).
AISBench refuses calculation when every request failed, but for partial failure
it reports `Failed Requests` and emits a warning rather than automatically
invalidating the run
([`stable_perf_metric_calculator.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/calculators/stable_perf_metric_calculator.py#L30-L48),
[`base_perf_metric_calculator.py`](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/ais_bench/benchmark/calculators/base_perf_metric_calculator.py#L432-L471)).
Therefore any stricter rule requiring zero failed, empty, malformed, or non-2xx
responses is a benchmark-study validity gate built from AISBench raw evidence,
not an automatic AISBench performance verdict.

## Evidence Files

The steady-stage guide documents dumped configurations, inference logs,
per-request CSV, common-metric JSON, complete-detail JSON/HDF5, and the request
concurrency HTML plot as outputs
([steady-stage guide](https://github.com/AISBench/benchmark/blob/3fd27b4a5fd022fcb5484fb084307f49955491ba/docs/source_en/advanced_tutorials/stable_stage.md#L185-L208)).
Those artifacts are the first-party basis for retaining raw per-request rows,
aggregate metrics, exact effective configuration, duration checks, request
validity, and achieved-concurrency evidence for every attempt.
