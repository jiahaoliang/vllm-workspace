# Blockwise DSA Stage 1 增量门禁：multi-node endpoint routing

状态：用户已于 2026-08-23 明确批准方案 A；批准时尚未据此修改 production source

## 1. 为什么需要重新过门禁

已批准的 Stage 1 设计和 ADR 0019 要求 Blockwise DSA 复用普通
`MooncakeConnectorV1` endpoint routing，并让 fixed Prefill TP leader 的
multi-node rank endpoint 命中对应 positional handshake session。

当前 replacement WIP 没有满足该要求：

- `RemoteSource` 只保存一个 scalar `remote_host`、`remote_port` 和
  `remote_engine_id`；
- Decode scheduler 把普通 V1 `kv_transfer_params` 中的
  `remote_multi_nodes_meta_mapping` 丢弃；
- 所有 Decode TP worker 收到同一个 command，但 worker 只计算
  `remote_port + leader_rank`，仍使用同一个 scalar host/engine；
- 普通 V1 已经通过 `_get_remote_host_info_by_port()` 按 remote port/rank
  选择 host 和 engine，DSA path 没有复用它。

因此 single-node CPU/mock 可以通过，但当一个 routed Prefill DP replica 的
TP leaders 跨节点时，worker 可能向错误 host 请求 metadata，并用错误 engine
查 cache。即使 port 数值正确，也不能证明命中了正确 handshake session。

这不是 NPU-only 风险，而是 Python routing correctness blocker。修复会改变
ADR 0019 已接受的 typed `RemoteSource` schema，所以必须先取得增量批准。

## 2. 推荐方案 A：typed Prefill-rank endpoint tuple

把 endpoint selection 收进现有 typed metadata seam，不新增 scheduler、worker、
runtime、transport、rendezvous 或 memory module。

目标 interface：

```python
@dataclass(frozen=True, slots=True)
class RemoteEndpoint:
    remote_host: str
    remote_port: int
    remote_engine_id: str


@dataclass(frozen=True, slots=True)
class RemoteSource:
    remote_request_id: str
    endpoints_by_prefill_rank: tuple[RemoteEndpoint, ...]
    indexer_block_ids: tuple[int, ...]
    main_block_ids: tuple[int, ...]
```

`endpoints_by_prefill_rank[prefill_rank]` 是该 rank 的 concrete handshake
endpoint。移除现有三个 scalar base endpoint fields，避免 base 与 override
成为两份事实来源。Tuple 是 immutable、可 pickle 的 current-command snapshot；
它不拥有 session、socket、metadata cache 或 request lifecycle state。

数据流保持在现有 module 内：

1. Prefill 普通 `MooncakeConnectorScheduler.request_finished()` 继续产生现有
   base endpoint 和 `remote_multi_nodes_meta_mapping`，default V1 contract 不变。
2. Decode DSA scheduler 在 reservation 前把该开放 dict 一次性 normalize 为
   完整 `endpoints_by_prefill_rank`。host/engine 解析与普通 V1 共用
   `mooncake_connector.py` 内一个 private pure helper；concrete port 在此固定。
3. Decode TP worker 仍按 accepted formula 计算
   `leader_rank = d_tp_rank * (P_TP / D_TP)`，然后只做 tuple lookup，不再推导
   host/engine，也不再重算 endpoint。
4. `KVCacheRecvingThread` 对 GET_META、remote metadata cache、Mooncake session、
   transfer 和 `DONE_RECVING_MSG` 全部使用同一个 selected endpoint。

这让 endpoint routing 只有一个权威投影：scheduler 负责把普通 V1 rendezvous
input 变成 typed snapshot；worker 只选择自己的 fixed leader；receiver 只执行
已选择的 endpoint。没有新增 process-local lifecycle state。

## 3. Invariants 与 failure boundary

- `endpoints_by_prefill_rank` 非空，长度必须等于 local configured `P_TP`。
- 每个 endpoint 的 host/engine 非空，port 是 `1..65535` 的非-bool integer。
- `P_TP >= D_TP` 且整除继续由现有 startup validation 保证；每个 computed
  `leader_rank` 必须在 endpoint tuple 范围内。
- `remote_multi_nodes_meta_mapping` 为空时，允许按普通 V1 single-node fallback
  为每个 Prefill rank生成 concrete endpoint。
- mapping 非空时必须覆盖当前 routed Prefill DP replica 的 expected rank set；
  partial、非法 key/value、非法 port 或缺 leader均在 reservation/transfer 前
  fail closed，不能静默 fallback 到错误节点。
- GET_META 返回的 engine identity 必须命中 selected endpoint；mismatch、缺失
  session 或非法 endpoint 是 programming/rendezvous error，走 worker poll
  fail-fast，不转换为 typed `TRANSFER_FAILED`。
- 只有一次同步 Mooncake Indexer/Main transfer 的负返回继续转换为现有
  phase-aware `TRANSFER_FAILED`。
- Fixed leader、positional tensor ABI、source block IDs、Main reservation、exact
  TP result coverage 和 cancellation contract均不改变。
- Prefill PP/PCP 分片和 multi-endpoint shard assembly不由本 amendment 扩大；
  fixed leader仍必须满足现有“持有完整 Main/Indexer replica”部署前置条件。

## 4. 为什么不选其他方案

### B. 首版限制 single-node Prefill

不推荐。它会删减 accepted product scope，而不是修复实现：spec 和 ADR 0019
已经要求 multi-node rank endpoint routing，首个 `P TP8/DP2 -> D TP2/DP8`
NPU 计划也不能被解释为整个 Prefill deployment 只能单机。

Decode startup 时还没有 remote request endpoint；不新增启动期协议就只能在
request admission 时拒绝 multi-node。若要可靠 startup fail-closed，反而需要
扩大 Prefill handshake coverage validation，并同步限制 P PP/CP，改动 spec、
ADR 0019、ADR 0022、CONTEXT、issues 和 NPU plan。它不是更薄的方案。

### C. 共享 generic endpoint directory

考虑过把 `base + immutable overrides + resolve()` 封装成一个 directory，并让
ordinary V1 与 DSA 共用。若两个 path 都迁移，它可以集中 offset canonicalization、
fallback 和 duplicate validation，不是纯 pass-through；但它也会让 ordinary V1 的
开放 mapping 解析进入 DSA metadata contract，保留 base/override precedence，并
扩大 default path 的实现改动和回归面。本次只需要在 connector 内共用一个 private
pure resolver，再把 DSA snapshot materialize 为 concrete tuple，因此不采用
directory class，也不增加 resolver adapter 或 transport seam。

### D. 保留 scalar base endpoint，再增加 overrides

不采用。它机械兼容当前字段，但让 base、override 和 concrete selected endpoint
同时存在，增加 precedence、partial mapping 和 duplicate truth invariants。直接用
完整 immutable tuple 的 interface 更小、更深。

## 5. ADR 与领域文档影响

批准方案 A 后：

- 修订 ADR 0019 的 `RemoteSource` shape 和 RemoteSource/central validation 段落；
- ADR 0022 的 positional tensor ABI 与 endpoint routing原则不变，无需建立新的
  semantic handshake protocol；
- 在 `CONTEXT.md` 增加 `Prefill rank endpoint` 术语，明确它是 concrete
  `(host, handshake port, engine identity)`，不是 TP leader replica proof；
- spec 的 product scope不收缩，只补充 typed endpoint projection的实现决策；
- NPU 仍为 `planned / not run`。

## 6. 逐文件实现计划与增量预算

当前相对 `0d6dd0d` 的 WIP：

| 类别 | Additions | Deletions |
|---|---:|---:|
| Production | 1,419 | 17 |
| Focused tests | 1,100 | 40 |

当前 production additions 已比原批准估算上限 1,385 多 34 行；tests 已达到
1,100 stop-and-review threshold。本 amendment 显式披露并重新评审预算，不能把
1,950 production threshold 当作原估算自动扩容。

方案 A 预计：

| File | Additional additions | Additional deletions | 计划 |
|---|---:|---:|---|
| `mooncake_dsa_metadata.py` | 18-28 | 6-12 | `RemoteEndpoint`、tuple normalization/validation；移除 scalar endpoint fields |
| `mooncake_connector.py` | 27-42 | 8-18 | 共用 private resolver、scheduler projection、worker selection、receiver endpoint wiring |
| `test_mooncake_dsa_metadata.py` | 15-25 | 15-25 | 替换 scalar source cases，覆盖 immutable/pickle/invalid endpoint tuple |
| `test_mooncake_connector.py` | 25-35 | 25-35 | 在现有 public lifecycle/receiver cases中替换并压缩，覆盖 same-node与multi-node leader routing |

目标 final budget：

- Production additions约 1,464-1,489，仍低于 1,950 stop threshold；唯一 module
  shape仍是 `MooncakeConnectorV1` + typed metadata + thin SFA extension。
- Focused test additions必须保持不超过 1,100。新增 endpoint assertions必须替换
  或压缩现有 DSA test code，不能叠加出第 1,101 行。
- 不新增 production module，不修改 SFA scheduler/worker，不新增 public interface。

如果实现证明需要新增 module、改变 positional ABI、支持 multi-endpoint shard
assembly、使 focused tests超过 1,100，或使 production additions预计超过 1,550，
立即停止并再次评审。

## 7. 批准后的 TDD 与验证

1. 先把现有 scalar endpoint test改成 multi-node failing lifecycle test，证明
   Decode TP0/TP1分别命中 fixed leader rank 0/rank 4 的不同 host/engine/port。
2. 增加同一 selected endpoint贯穿 GET_META、metadata cache、Mooncake session 和
   DONE notification的 assertions。
3. 增加 empty/partial/bad endpoint、engine mismatch 和 out-of-range leader的
   fail-closed cases；保留 metadata pickle/frozen evidence。
4. 复跑 metadata、public connector lifecycle、affected SFA tests、完整
   `kv_offload` suite和 default V1 regression；CPU/mock仍在
   `liangjiahao/vllm-ascend-ut` 中按 workspace rules执行。
5. Ruff 与 format单独报告；真实 multi-node/NPU transfer仍为 `planned / not run`。
6. 完成后重新展示 base/head、逐文件 diffstat、production/test totals、test
   commands/results、剩余风险和 staging allowlist；未经用户再次批准不 commit、
   push、刷新 lock/repo-state/issues或修改 final feature status。

## 8. 已批准决策

用户于 2026-08-23 批准方案 A：用完整 immutable Prefill-rank endpoint tuple替换
scalar `RemoteSource` endpoint，并按以上预算完成 TDD 修复与 Stage 3 复验。

若用户选择方案 B，必须把它视为 product scope reduction，先重新设计并修改
accepted spec/ADR；不能在当前 implementation 中静默加入 single-node 假设。
