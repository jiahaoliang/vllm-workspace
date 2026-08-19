# Test 2 load timing summary

## Throughput context

- BULK formal: 100/100, 0.2292 req/s, 436371.9513 ms.
- REUSE3 formal: 100/100, 0.0855 req/s, 1170183.1656 ms.
- REUSE3/BULK: 0.3730x.

## Instrumentation summary

- BULK Prefill TP0 whole-key gets: 106; total 30.052 s. Decode gets: 100; total 31.407 s.
- REUSE3 Prefill active steps: 83; TP0 request calls: 62700; TP0 transfer time: 651.520 s.
- REUSE3 Decode active steps: 0; TP0 request calls: 0; TP0 transfer time: 0.000 s.
- REUSE3 TP0 mean `batch_copy_get` call: 10.391 ms.
- REUSE3 Prefill critical model wait total: 814.071 s; Decode: 0.000 s.
- REUSE3 worst-rank address build total: 360.788 s; save gate total: 13.439 s; attention gate total: 2.120 s.
- Model critical wait is 70.0% of summed Prefill context iteration time.

## Mooncake versus orchestration

- BULK Prefill TP0 effective load bandwidth: 3.170 GB/s.
- REUSE3 Prefill TP0 effective `batch_copy_get` bandwidth: 3.363 GB/s.
- REUSE3 transferred 23.00x BULK Prefill bytes and issued 591.5x as many request-scoped calls.
- Layers 1-25 each issued exactly 2,500 TP0 request calls: 100 requests x 25 chunks. Layers 0 and 26 issued 100 calls each.

## Scaling by requests in one chunk step

- 40-call steps: 40; median transfer per TP/step 10.224 s; median critical model wait 12.815 s; median bytes per TP/step 31907.8 MiB.
- 20-call steps: 21; median transfer per TP/step 5.088 s; median critical model wait 6.391 s; median bytes per TP/step 15939.8 MiB.

## Prefill NPU samples

- BULK NPU 2/3 mean AICore: 80.0% / 37.7%.
- REUSE3 NPU 2/3 mean AICore: 32.3% / 9.8%.

## Formal errors

- BULK matching error lines: 0.
- REUSE3 matching error lines: 0.
- BULK first-hit validation: 100/100 requests at 28,800 tokens.
- REUSE3 first-hit validation: 100/100 requests at 28,800 tokens.
