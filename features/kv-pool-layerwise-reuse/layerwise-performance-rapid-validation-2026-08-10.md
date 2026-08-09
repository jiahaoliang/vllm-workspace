# Mooncake Layerwise Performance Raw Characterization

Single-wave raw characterization; not a steady-state or statistically significant result.

## Raw Results

| Topology | Input | Output | Variant | Concurrency | Repetition | Input Token Throughput | Request Throughput | TTFT Median | TTFT Max | TTFT P95 | E2EL Median | E2EL Max | E2EL P95 | Achieved Concurrency | Output Token Throughput | TPOT P95 | ITL P95 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dp1 | 16384 | 128 | BULK | 8 | 1 | 3380.67 | 0.2063 | 12729.9 | 22164.6 | 21217.9 | 29739.6 | 38732.7 | 37846.6 | 6.125 | 26.4115 | 135.7 | 137.4 |
| dp1 | 16384 | 1 | BULK | 8 | 1 | 6132.14 | 0.3743 | 12176.3 | 21252.1 | 20344.5 | 12176.3 | 21252.2 | 20344.6 | 4.5673 | 0.3743 |  | 0.9 |
| dp1 | 16384 | 128 | LAYERWISE | 8 | 1 | 2542.74 | 0.1552 | 19587.2 | 34584.2 | 33054.1 | 36374.2 | 51510.2 | 49910.4 | 5.6698 | 19.8652 | 135.4 | 147.1 |
| dp1 | 16384 | 1 | LAYERWISE | 8 | 1 | 3801.59 | 0.232 | 19109.4 | 34440 | 32656.3 | 19109.6 | 34440.1 | 32656.4 | 4.4522 | 0.232 |  | 0.2 |
| dp1 | 16384 | 1 | REUSE3 | 8 | 1 | 4205.8 | 0.2567 | 17830.2 | 31125.5 | 29801.1 | 17830.3 | 31125.6 | 29801.2 | 4.5616 | 0.2567 |  | 0.2 |

## Per-Request Results

These rows retain the stable request identity and correctness fields from each formal AISBench details artifact.
Complete prompt and prediction payloads remain in the immutable raw evidence.

| Point | Repetition | Request | Data ID | UUID | Success | Input Tokens | Output Tokens |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |
| dp1-16384-bulk-o128-c8 | 1 | 1 | 0 | ea1f4f994b35454599e5636a1f07d09d | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 2 | 1 | cd64422473cb449fb4eb0d9a5ed3d7dc | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 3 | 2 | f9f7a4f63ec147a6adc5788ceb92b32c | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 4 | 3 | 8482216e74b84c7ab69b3fb9c1f0aa92 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 5 | 4 | d9a6401eb413495b804d432742979e06 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 6 | 5 | 38bc71f7b91743e0ba01d65cd183a1bd | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 7 | 6 | 63130abfe67444fdb714d1e54a4a9000 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 8 | 7 | 6420a1cbe1df46e581afdc9e4833d387 | true | 16384 | 128 |
| dp1-16384-bulk-o1-c8 | 1 | 1 | 1 | 6f0106d1007e46a4a87077a36ac247b9 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 2 | 2 | 0373f9f85abe45eeab729a73b08067c8 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 3 | 0 | ddc3fe6f829e43a4be8f195537182219 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 4 | 3 | 640c984a586c4af7aa529c2eebe2221a | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 5 | 4 | 2b3278b8f04a415bb09595c1db197070 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 6 | 5 | 41c8f478905b440d8cb817fab0f86da7 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 7 | 6 | 527411e3544445a3b969fef6ecdd62f8 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 8 | 7 | aed5ef969242430da193002d595352d2 | true | 16384 | 1 |
| dp1-16384-layerwise-o128-c8 | 1 | 1 | 0 | df89e9e76825477e81638b191dcd42b2 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 2 | 1 | df8fc0e17bca4c50a7cfee83b74f6b4f | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 3 | 2 | 6429a2c73ddd49aca58fa3245622049c | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 4 | 3 | b450578454154e7fb5d7124ec4ea0537 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 5 | 4 | e0dcadbeacc94f7b949a98c4d01c6640 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 6 | 5 | 89e0e6789ba3403a805ce91d709bcfcf | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 7 | 6 | 5e365294da2244888b8e2527a9da94e6 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 8 | 7 | 5569e83bf76249098c77bfaefa4b87e3 | true | 16384 | 128 |
| dp1-16384-layerwise-o1-c8 | 1 | 1 | 1 | b720d1fb726e400f9a951db12ec41a19 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 2 | 0 | 4167ecd693be4193b71039b2e56c4432 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 3 | 2 | 421b79ece98940e0853cfa04d59980a7 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 4 | 3 | e4d8c636668348469ff1e1f9c615ab3b | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 5 | 4 | 9984c0efeb8941618376e645ae5dd657 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 6 | 5 | 0b0323227cb44633a1ed6f169a8c7109 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 7 | 6 | 3efeee420f7e41d59781063a75945050 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 8 | 7 | 3d5416c962db483b88e51f53a4a3eab4 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 1 | 1 | bf46eb91151444f885ff593f74b7a093 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 2 | 0 | fb0cfe385b974400afd27056575a5264 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 3 | 2 | c08cb0766cdb47dbbed92f8c33930688 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 4 | 3 | f3d3aa6a645c4b73919007e3b9a2aa53 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 5 | 4 | 85f393a5ba104451a396e8e8fb8449d5 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 6 | 5 | 4a100fdb5c3049f0b1258d59d3102fa1 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 7 | 6 | cbd660df8edf4ca388c21d0369589ed1 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 8 | 7 | d0dd683168564d0e84e486f06a4386a8 | true | 16384 | 1 |

## Direct Ratios

| Comparison | Topology | Input | Output | Concurrency | Repetition | Metric | Ratio |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Input Token Throughput | 0.619946 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Request Throughput | 0.619824 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Median | 1.56939 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Max | 1.62055 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT P95 | 1.60517 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Median | 1.56941 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Max | 1.62054 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL P95 | 1.60516 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Achieved Concurrency | 0.974799 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Output Token Throughput | 0.619824 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | ITL P95 | 0.222222 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | Input Token Throughput | 0.752141 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | Request Throughput | 0.752302 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | TTFT Median | 1.53868 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | TTFT Max | 1.56033 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | TTFT P95 | 1.55784 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | E2EL Median | 1.22309 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | E2EL Max | 1.32989 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | E2EL P95 | 1.31876 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | Achieved Concurrency | 0.925682 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | Output Token Throughput | 0.752142 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | TPOT P95 | 0.997789 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | ITL P95 | 1.0706 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Input Token Throughput | 1.10633 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Request Throughput | 1.10647 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | TTFT Median | 0.933059 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | TTFT Max | 0.90376 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | TTFT P95 | 0.912568 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | E2EL Median | 0.933055 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | E2EL Max | 0.90376 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | E2EL P95 | 0.912568 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Achieved Concurrency | 1.02457 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Output Token Throughput | 1.10647 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | ITL P95 | 1 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Input Token Throughput | 0.685862 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Request Throughput | 0.685814 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Median | 1.46434 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Max | 1.46458 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT P95 | 1.46482 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Median | 1.46434 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Max | 1.46458 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL P95 | 1.46482 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Achieved Concurrency | 0.998752 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Output Token Throughput | 0.685814 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | ITL P95 | 0.222222 |
