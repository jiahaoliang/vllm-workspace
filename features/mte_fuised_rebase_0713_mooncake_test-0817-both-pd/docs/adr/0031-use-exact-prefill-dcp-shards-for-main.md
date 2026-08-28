# Main 使用 exact Prefill DCP shard assembly

状态：已接受

Blockwise DSA PD offload 支持 Prefill SFA sparse、`PCP=1`、`DCP>1`，同时 Decode 保持
`DCP=1`、`PCP=1`、`PP=1`。`P_DCP` 必须整除 `P_TP`，既有 `P_TP >= D_TP` 与
`P_TP % D_TP == 0` 继续成立。

对 Decode TP rank `j`，令 `group_count = P_TP / P_DCP`，并选择
`group_index = floor(j * group_count / D_TP)`。Main 从该组连续 `P_DCP` 个 Prefill ranks 的
rank-local cache 按 `cp_kv_cache_interleave_size` 映射回 Decode-global token位置；Indexer 与可选
scale仍只从该组首 rank 的 fixed replica读取。多个 Decode TP可以共享同一 Prefill DCP source
group；`P_DCP=1` 时该公式退化为 ADR 0004 的 fixed-leader mapping。

## 结果

- DSA typed metadata只增加紧凑的 Main sharding geometry：DCP size、source block size与
  interleave size。它不携带 tensor role、地址、dtype、shape或memory kind；ADR 0022 的 positional
  tensor ABI与P/D deployment compatibility preconditions不变。
- Decode在任何Main写入前冻结source plan、验证source capacity与destination exact coverage，并取得
  全部selected endpoints的metadata。随后先执行一次leader Indexer D2D，再按Prefill rank顺序执行
  每个非空Main D2RH shard；全部成功后才产生一个`RECEIVE_COMPLETE`。
- 每个参与endpoint使用稳定排序的per-endpoint锁。每个Decode worker在成功、失败或cancellation
  terminal path中，对全部planned source endpoints各尝试一次`DONE_RECVING_MSG`。共享source group
  使用现有`remote_port_send_num` fanout计数延迟Prefill释放。
- Indexer与任一Main shard final failure继续分别产生`TRANSFER_FAILED/INDEXER_D2D`与
  `TRANSFER_FAILED/MAIN_D2RH`。不增加connector retry、watchdog或reliable cancel；ADR 0016边界不变。
- ordinary `dsa_pd_offload=false`、DSA `DCP=1`、exact Decode-TP completion、async scheduling、replay、
  preemption、QUIESCE与terminal ownership合同保持不变。
- Prefill PCP、Decode CP、跨Prefill DP混合tensor、mixed-version P/D部署和并行Main shard pull不在首版
  范围内。真实Mooncake与NPU DCP2/DCP4 correctness仍须按NPU计划执行，当前不得由CPU/mock结果推断。
