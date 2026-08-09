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
