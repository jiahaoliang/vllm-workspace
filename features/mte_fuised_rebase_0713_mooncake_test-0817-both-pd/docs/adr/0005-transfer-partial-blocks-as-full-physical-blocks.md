# 将 partial block 按完整物理 block 传输

状态：已接受

Blockwise DSA PD offload 沿用穿刺 connector 的 `fused_overlap` 语义：最后一个 partial Main block 和 Indexer page 均按完整物理长度传输，Decode 使用已有 request token 状态限制有效范围。首版不新增 `valid_token_count` 或 token-range 字段，因为 Decode 已经拥有 `prompt_len`、`num_computed_tokens`、`num_external_tokens` 和 sequence length；重复表达同一边界会引入冲突来源，却不会为当前整块 request-level pull 提供新信息。

## 结果

- Main K/V 要求 P/D token block size 和每 block 字节数相等。
- Indexer 只允许 Decode page 按同一个正整数比例容纳 Prefill page。
- Decode `fused_overlap` 按 `cdiv` 为 partial Main block 分配完整 local swapped Host block，不使用 legacy `partial_hbm_bid`。
- Connector 不裁剪或清零尾块，尾部未使用位置不属于请求的有效 cache。
- 请求进入传输前必须校验已有 token 状态与 source/destination block list 相互一致，不一致时 fail closed。
