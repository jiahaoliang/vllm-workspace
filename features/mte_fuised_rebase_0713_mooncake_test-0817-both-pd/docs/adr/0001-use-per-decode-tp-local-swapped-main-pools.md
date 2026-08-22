# 使用 per-Decode-TP local swapped Main pool

状态：已接受

Blockwise DSA PD offload 为每个 Decode TP process 分配独立的 swapped Main KV pool，并将该 TP 的 Main KV 传入本地 pool。这个选择会在不同 Decode TP rank 上重复占用 Host memory 并增加 Main 传输量，但可以避免把 process-local、已由 Mooncake 注册的 swapped address 当作跨进程传输目标，同时与 `model_runner_v1` 和 `sfa_kv_offload_worker` 已有的 `fused_overlap` ownership model 一致。

## 结果

- 每个 Decode TP 向 Mooncake 注册自己的 Main KV destination。
- Main KV 传输完成条件覆盖每个 Decode TP 的本地 destination。
- 容量规划按每个 Decode TP 一个 `1x kv_cache_config.num_blocks` 的完整 swapped Main pool 计算，block ID `0` 保留，首版不提供容量倍率配置。
- Scheduler block manager、runner-owned Host tensor 和 Mooncake 注册范围必须在 startup 阶段通过容量一致性校验。
- Request admission 和容量预留遵循 [ADR 0006](0006-reserve-main-capacity-for-the-request-lifetime.md)。
- 首版不引入跨进程共享 Main pool，也不提取独立的 destination-memory module。
