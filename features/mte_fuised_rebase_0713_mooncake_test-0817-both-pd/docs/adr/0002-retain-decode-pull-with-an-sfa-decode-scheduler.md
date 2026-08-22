# 保留 Decode pull 并使用 SFA Decode scheduler

状态：已接受

Blockwise DSA PD offload 保留 `MooncakeConnectorV1` 现有的 Decode-initiated request-level pull。Prefill 继续使用 `MooncakeConnectorScheduler`，Decode 则新增继承自 `SFAPDCpuOffloadScheduler` 的 blockwise scheduler，让 Indexer HBM block 和 Main Host block 复用现有 SFA request lifecycle。这个选择不迁移穿刺 connector 的 layerwise Prefill push，并将改动范围收敛在 blockwise connector 内。

## 结果

- Prefill scheduler 不接收 Decode Host IDs，不执行 SFA allocation，也不运行 layerwise hooks。
- Decode 负责 destination allocation、address publication、receive completion、preemption 和 cleanup。
- 只有串行执行的 Indexer D2D `TransferSync` 与 Main D2RH `TransferSync` 都成功后，请求才进入 receive-complete 状态。
- 除非设置 `kv_connector_extra_config.dsa_pd_offload=true`，否则 `MooncakeConnectorV1` 现有行为保持不变。
