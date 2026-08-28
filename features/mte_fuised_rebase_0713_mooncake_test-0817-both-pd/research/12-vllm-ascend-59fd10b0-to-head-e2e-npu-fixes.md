# Research: vLLM-Ascend `59fd10b0` 到 `117637d20` 的 E2E NPU 闭环修改

## 问题与证据边界

问题是：replacement source checkout 中，从
`59fd10b0dab1b934fc8ba1cc39a76a14a16b9413`（含）到当前最新
`117637d205603b0c1e43aa0ea3e141de926ff3b1`，代码修改了什么；哪些修改有证据
表明使 glm-5.1 / glm5.2 的最终 Blockwise DSA Mooncake PD E2E NPU test 跑通。

本次只读审计使用以下一手材料：

- replacement source checkout 的 Git commit、diff、当前源码和 tests；
- 分支内 [`docs/BLOCKWISE_DSA_MOONCAKE_V1_E2E_ANALYSIS.md`](../../../repos/vllm-ascend/docs/BLOCKWISE_DSA_MOONCAKE_V1_E2E_ANALYSIS.md)；
- control repo 的 [`repo-state.md`](../repo-state.md)、[`sync-log.md`](../sync-log.md) 和 [`workspace.lock.json`](../../../workspace.lock.json)。

证据等级必须分开：

1. **代码事实**：当前 tree 和 `59fd10b0^..117637d20` diff 可直接确认。
2. **分支记录的 runtime 结果**：`59fd10b0` 首版 E2E analysis 与后续文档明确记录的结果；这是作者写入 Git history 的实验记录。
3. **本 workspace 当前验证**：本次没有复跑 NPU、serving 或 unit test。
4. **缺失证据**：文档引用的 `experiments/20260827-blockwise-dsa-mooncake-v1/`
   及其中 `FIXES_FOR_PR.md`、`STATUS_GLM51_BLOCKWISE.md`、`BENCH_4K.md`
   不在 `117637d20` tracked tree 中，因此无法逐请求核验原始命令、日志、时间戳、
   Pod/镜像、设备分配和退出码。

## Checkout 与 commit 范围

当前 replacement checkout 是
`feature/blockwise-dsa-mooncake-v1-reimplementation@117637d205603b0c1e43aa0ea3e141de926ff3b1`，
tracked tree clean，且本地分支与 `origin` 是 `0 ahead / 0 behind`。control repo 的锁与
状态记录指向相同 SHA（[`repo-state.md:5-9`](../repo-state.md#L5-L9)、
[`workspace.lock.json:14-22`](../../../workspace.lock.json#L14-L22)）。

指定的 inclusive range 一共 5 个 commit：

| Commit | 类型 | 实际修改 |
| --- | --- | --- |
| `59fd10b0d` | production fix + tests + 初版 E2E 记录 | 修改 2 个 production Python 文件、1 个 UT 文件并新增 E2E analysis；`809 insertions / 39 deletions` |
| `07dbab1f5` | docs-only | 展开每个 fix 的函数级说明 |
| `b32fb95aa` | docs-only | 补根因与 ownership 分类 |
| `93a4a01f9` | docs-only | 按继承契约/使用错误/状态机缺口重写 |
| `117637d20` | docs-only | 最终 rebase-oriented 必要性、依赖和否决清单 |

关键事实：`git diff --quiet 59fd10b0..117637d20 -- vllm_ascend tests` 返回 0。
因此 **production code 与 tests 在 `59fd10b0` 已定型；后四个 commit 没有继续修 runtime，
只把同一批修复的解释扩展到 724 行**。不能把 `117637d20` 说成另一个 runtime fix。

整个 inclusive range 相对 `59fd10b0^` 最终只触及 4 个文件：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`
- `vllm_ascend/distributed/kv_transfer/utils/transfer_engine_backend.py`
- `tests/ut/kv_offload/test_mooncake_connector.py`
- `docs/BLOCKWISE_DSA_MOONCAKE_V1_E2E_ANALYSIS.md`

## 总结：什么让最后 E2E 跑通

不是一个单点 fix，而是四批按暴露顺序串联的修复：

```text
Decode 能注册并启动
  -> Prefill/Decode 能按真实 Indexer/Main 布局传输
  -> 传输后 Host Main 表不被清空、失败可 replay
  -> 多 DP / 多 batch 并发不再因 rank key 和跨 step plan 崩溃
```

最终文档把 production 必须项列为 F-CODE-001、002、004、006、007、008、009、
010、011、012、013，并把 `GlobalTE.register_buffer(locations=...)` 归入 F-009
（[`E2E_ANALYSIS.md:26-41`](../../../repos/vllm-ascend/docs/BLOCKWISE_DSA_MOONCAKE_V1_E2E_ANALYSIS.md#L26-L41)）。
但从当前最终代码路径看，必要性还应更精确地区分：

- F-001/004/006/007/009/010/011/012/013 是启动、数据传输、生成质量或并发的直接阻断修复。
- F-008 是传输失败后的 replay 韧性修复；成功 happy path 不触发它，但失败恢复不修会二次 EngineDead。
- F-002 是 hybrid/helper 防御性修复；最终 DSA Decode consumer 已由 F-004 改走
  `_dsa_consumer_device_register_regions()`，所以现有 source 不能证明 F-002 对最终成功路径仍不可缺。
  它确实消除了中间调试路径的 `KeyError`，并防止其它 hybrid 调用者重复踩坑。

### 批次 R：注册闭环，先让 Decode 真正 ready

#### F-CODE-001：resident row 不能当 KV block 数

旧 DSA 注册把五元组中 resident K/V 的 `shape[0]` 当成 KV block 数做整除校验；
但 resident 第 0 维是 top-k row / `max_num_seqs`，不是 `num_blocks`。当前代码对
`OFFLOAD_RESIDENT_K/V` 直接跳过，不把它们写入 PD block metadata
（[`mooncake_connector.py:3657-3690`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3657-L3690)）。

必要性：缺它 Decode 在请求到来前就以 `tensor_blocks=4, configured_blocks=372`
一类错误退出；对应回归测试构造真实 resident shape 并确认只留下 Main/Indexer metadata
（[`test_mooncake_connector.py:3517-3535`](../../../repos/vllm-ascend/tests/ut/kv_offload/test_mooncake_connector.py#L3517-L3535)）。

#### F-CODE-002 / F-CODE-004：跳过不存在的独立 Indexer key，Decode device 只注册 Indexer

offload 后 Indexer 已打包在 attention cache tuple 中，`shared_by` 仍可能出现不存在的
`indexer.*` 独立 key。helper 现在对缺 key 和 resident position 均跳过
（[`mooncake_connector.py:3481-3508`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3481-L3508)）。

更关键的最终路径是 F-004：DSA Decode consumer 不再把 Main、Indexer、resident 的
重叠 view 作为 device region 注册，而只收集 Indexer K/scale
（[`mooncake_connector.py:3456-3479`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3456-L3479)、
[`mooncake_connector.py:3692-3704`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3692-L3704)）。

必要性：这消除启动阶段的缺 key `KeyError`、overlapped memory region `ret=-7`，也避免
“把五元组全量 merge”导致 HCCL per-process region 超过 256 的已否决方案。F-004 是
final consumer 路径直接依赖；F-002 在 final path 中属于保留的 helper hardening。

#### F-CODE-009 + `GlobalTE.locations`：device 与 Host 一次注册，Host 标明 `npu:<id>`

`GlobalTE.register_buffer()` 是 process-wide one-shot：第二次调用直接返回。旧代码先注册
device Indexer，之后再注册 Host Main，实际 Host 注册被 no-op。当前 worker 先构造 Host
layout/regions，再与 device regions 合并，在第一次调用中一次提交；Host entries 使用
`npu:<current_device>`，device entries 的 location 为 `None`
（[`mooncake_connector.py:3521-3536`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3521-L3536)、
[`mooncake_connector.py:3706-3745`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3706-L3745)）。

`GlobalTE` API 同步增加逐 region `locations`，兼容 keyword/positional 两种 Mooncake binding，
并在 binding 不支持 location 或注册非零返回时给出带 ptr/size/location 的错误
（[`transfer_engine_backend.py:267-315`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/utils/transfer_engine_backend.py#L267-L315)）。

必要性：Indexer D2D 通过后，Main 目的地址位于 Host；若 Host 没有在 first register 中注册
或没有 swapped location，MAIN_D2RH 会 `Validate address failed`。测试明确断言只有一次调用、
device location 为空而 Host location 以 `npu:` 开头
（[`test_mooncake_connector.py:3452-3496`](../../../repos/vllm-ascend/tests/ut/kv_offload/test_mooncake_connector.py#L3452-L3496)）。

### 批次 T：真实布局传输与可选 Indexer

#### F-CODE-006 / F-CODE-013：Indexer 是 per-layer 可选后缀

glm5.2 的 shared-indexer Prefill layer 可以只有 Main K/V。注册端现在只要求 tuple 至少有
两个 Main tensor，不再要求每层必有 Indexer
（[`mooncake_connector.py:3657-3667`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3657-L3667)）；
测试覆盖 Main-only producer 启动
（[`test_mooncake_connector.py:3537-3560`](../../../repos/vllm-ascend/tests/ut/kv_offload/test_mooncake_connector.py#L3537-L3560)）。

接收端随后必须对称处理：若本地 Indexer position 超过远端 handshake 数组长度就跳过；若
整批 Indexer transfer list 为空则跳过这次 TE read，继续 Main D2RH
（[`mooncake_connector.py:770-789`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L770-L789)、
[`mooncake_connector.py:968-1008`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L968-L1008)）。

必要性：F-006 不修，glm5.2 Prefill 起不来；只修 F-006 不修 F-013，Decode 会在
`remote_base_addrs[layer][2]` 越界并 EngineDead。它们是一对统一语义，不是
`if model == glm52` 的模型特判；glm-5.1 每层有 Indexer 时该 skip 是空操作。

#### F-CODE-007：Prefill 小页到 Decode 大行的 page packing

handshake 现在缓存远端 `block_lens`，receive list 构造同时拿到 remote logical page length
（[`mooncake_connector.py:962-977`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L962-L977)）。
当 Decode local `block_len` 是 Prefill `remote_len` 的整数倍时，多个 Prefill Indexer page
按 `page_slot` 写入同一 Decode manager row；local/remote address 都按 logical
`block_len` / `remote_len` 计算，不再用可能因 padding/shared storage 变大的 tensor stride
（[`mooncake_connector.py:791-835`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L791-L835)）。

必要性：典型 Prefill 约 128 token/page、Decode Indexer 约 512 token/row，源和目的 block id
数量天然不相等。旧等长要求产生 `coverage must match`；仅放宽等长但仍用 stride，又会让
地址落到 TE registered region 外。两个 UT 分别验证 4:1 packing 和 `stride != block_len`
时仍按 logical length 寻址
（[`test_mooncake_connector.py:3562-3600`](../../../repos/vllm-ascend/tests/ut/kv_offload/test_mooncake_connector.py#L3562-L3600)）。

### 批次 S：状态机与 SFA Host Main 交接

#### F-CODE-010：live request 不再被空 SFA metadata 清表

旧顺序是 `set_req_ids` 已填 `cpu_block_table`，DSA `start_load_kv` 随后仍无条件传空
`SFAKVOffloadConnectorMetadata`；SFA worker 对空 metadata 的合法语义是先把 block table
清零，因此传输已经成功也会读到 block 0，表现为空文本、乱码或只有 `Comments`。

当前实现先接受本 step command/plan；若已有 `sfa_worker.req_ids`，就从 DSA binding/plan
重建非空 view；只有无 live batch 且无 plan 的 idle step 才清空
（[`mooncake_connector.py:4664-4685`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L4664-L4685)）。
回归测试确认 rebuild 后 Host block ids 和 D2H token range 都保留，且末尾没有再追加 empty wipe
（[`test_mooncake_connector.py:2983-3011`](../../../repos/vllm-ascend/tests/ut/kv_offload/test_mooncake_connector.py#L2983-L3011)）。

必要性：前两批只保证“能拉过来”；F-010 才保证 fused attention 读的是刚拉到 Host 的 Main，
因此它直接连接“传输成功”与“生成文本正确”。

#### F-CODE-012：rebuild 只消费本 batch 的 D2H plan

并发下 `set_req_ids` 可能早于 `start_load_kv` 更新当前 step plans。旧 plans 可能属于上一 batch，
旧实现把“不属于当前 req_ids”视为 fatal。现在先按 request id 求交；当前 batch 无 plan 的请求
仍保留 Host binding，但 `offload_num_tokens=0`
（[`mooncake_connector.py:5034-5062`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L5034-L5062)）。

必要性：单请求/低并发不一定触发；较高并发下旧行为会以
`D2H plans must target the current model batch` 杀 Engine。当前 commit 调整了既有 D2H/SFA
测试的 production ordering，但没有新增一个明确命名的 cross-request stale-plan 独立 UT；
这一点是 test evidence 的缺口，不能用 E2E 文档替代单测覆盖事实。

#### F-CODE-008：TRANSFER_FAILED replay 允许 Main binding 缩回 preserved prefix

exact-TP receive 任一 rank 报 `TRANSFER_FAILED` 时，scheduler 现在把 issued/confirmed token、
`main_bound_block_count`、D2H sequence/ledger 一并清回 token 0 replay 状态
（[`mooncake_connector.py:2289-2304`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2289-L2304)）。
worker 对 `PREPARE_REPLAY` 只要求 reservation identity/capacity 稳定，允许 Main bound 缩短，
并重置 D2H sequence 与 expected token start
（[`mooncake_connector.py:4857-4873`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L4857-L4873)、
[`mooncake_connector.py:4918-4941`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L4918-L4941)）。

必要性：这是失败恢复而非成功请求的前置条件。F-007/F-009 修好后正常路径少进 replay，
但真实传输失败、超时或对端异常时，不修会在第一次短 D2H plan 上再报
`Main binding is not a prefix extension`。现有 tests 验证 scheduler 清零和 worker 接受 empty shrink
（[`test_mooncake_connector.py:2105-2123`](../../../repos/vllm-ascend/tests/ut/kv_offload/test_mooncake_connector.py#L2105-L2123)、
[`test_mooncake_connector.py:3355-3370`](../../../repos/vllm-ascend/tests/ut/kv_offload/test_mooncake_connector.py#L3355-L3370)）。

### 批次 C：多 DP endpoint 拓扑

#### F-CODE-011：Prefill DP 全局 handshake offset rebase 成 local TP rank

Prefill DP1-3 可能发布连续全局 key block，例如 DP3 的 `12..15`；Decode projection 只认
相对该 engine base port 的 `0..tp_size-1`。当前 `_rebase_remote_endpoint_mapping()` 对已是
local 的 key 原样保留，对连续 TP-sized global block 减去 base，再进入完整/非法 rank 校验
（[`mooncake_connector.py:156-220`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L156-L220)）。

必要性：只打到 Prefill DP0 时不会暴露；并发命中 DP1-3 时旧逻辑会报告 invalid rank keys 并
EngineDead。UT 明确用 DP3 `12..15` 验证投影到 4 个 local endpoint
（[`test_mooncake_connector.py:1747-1769`](../../../repos/vllm-ascend/tests/ut/kv_offload/test_mooncake_connector.py#L1747-L1769)）。

## 附带的 observability 改动

`59fd10b0` 还增加 receive phase 的 one-shot handshake/address diagnostic，以及 INDEXER_D2D、
MAIN_D2RH 失败日志。它们帮助把最初误判为 Indexer 的 Validate failure 定位到 Main Host
注册，但 **日志本身不是让 E2E 成功的 runtime fix**。当前实现位于
[`mooncake_connector.py:860-926`](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L860-L926)
及 receive phase 错误分支。

## 哪些不是本 commit 的 production 修复

最终 analysis 同时记录了运行环境与被否决的弯路，但指定 range 没有把这些实验脚本提交进
tracked production tree：

- 必须使用 Prefill-first blockwise proxy；误用 layerwise Decode-first 会缺
  `remote_block_ids`。
- `ASCEND_BUFFER_POOL=0:0`、代理用可回连真实 host、正确 glm5.2 模型目录、默认关闭
  `VLLM_ASCEND_SFA_DEBUG`、停服覆盖重命名后的 worker 都是实验环境/运维要求。
- 改 `ASCEND_BASE_PORT`、把五元组全量 `collect_storage_merged`、关闭
  `lru_resident_cache` 绕过 resident 校验、按模型名分两套 connector 逻辑均被否决
  （[`E2E_ANALYSIS.md:685-704`](../../../repos/vllm-ascend/docs/BLOCKWISE_DSA_MOONCAKE_V1_E2E_ANALYSIS.md#L685-L704)）。

这些条件可能是复现实验的必要条件，但不能说成 `59fd10b0` 的 tracked code change。

## Runtime 结果：能确认到什么程度

`59fd10b0` 提交时的初版 tracked analysis 记录：

- glm-5.1：长请求 `prompt_tokens=2734`；4k input、concurrency 8 的复测为 `16/0`，
  更早 concurrency 16 为 `64/0`、output throughput 约 `30.5 tok/s`；
- glm5.2：修 F-013 后短请求和 `2734 + 128` 长请求通过；4k input concurrency 8 为
  `32/0`、约 `20.8 tok/s`，concurrency 16 为 `64/0`、约 `33.0 tok/s`；
- 测试拓扑记录为 Prefill-first proxy、DP4 x TP4。

可用以下 Git object 原样复核该提交时的记录：

```bash
git -C repos/vllm-ascend \
  show 59fd10b0:docs/BLOCKWISE_DSA_MOONCAKE_V1_E2E_ANALYSIS.md
```

关键位置是该 object 的第 12-20 行和 129-143 行。最终 analysis 保留较窄的总述：两模型的
冒烟、长请求和约 4096-input 并发都通过，服务已停、卡已释放
（[`E2E_ANALYSIS.md:130-142`](../../../repos/vllm-ascend/docs/BLOCKWISE_DSA_MOONCAKE_V1_E2E_ANALYSIS.md#L130-L142)）。
control repo 也只把它登记为 branch history 记录的 bounded E2E，并明确没有复跑和没有 ledger
（[`repo-state.md:25-28`](../repo-state.md#L25-L28)、
[`sync-log.md:26-30`](../sync-log.md#L26-L30)）。

因此可以严谨地说：

- **有 tracked Git 记录表明** `59fd10b0` 的四批修复之后，两模型在同一套代码上完成了
  short/long generation 和约 4k-input concurrent NPU E2E；初版文档还记录了具体完成/失败数。
- **代码因果与症状链一致**：每批分别消除启动、TE address/packing、Host table/状态机、
  多 DP/跨 step 并发的确定性 fatal condition；这比只引用 commit subject 更强。
- **不能升级成独立复验结论**：当前 workspace 没有重跑 NPU；原始 experiment ledger 未跟踪，
  所以不能独立确认每个命令/退出码，也不能证明旧 8-case NPU plan 全部执行。
- graph capture、完整 failure/preemption/cancellation lifecycle matrix、未记录的 plan cases 和
  性能稳定性仍是 `unverified`，不能由这次 bounded happy-path/benchmark 结果外推。

## 本次静态验证

- `git rev-list 59fd10b0^..117637d20`：确认恰好 5 个 commit。
- `git diff --quiet 59fd10b0..117637d20 -- vllm_ascend tests`：确认后四个 commit 没有 source/test delta。
- `git diff --check 59fd10b0^..117637d20 -- vllm_ascend tests`：通过；完整 range 的 docs
  使用 Markdown hard-break trailing spaces，因此未把 docs whitespace 当 production 静态失败。
- 对两个 production Python 文件和 UT 文件执行 Python 3 `ast.parse`：通过。
- `git fsck --no-dangling`：通过。
- 未运行 UT、serving、NPU E2E，也未访问缺失的外部实验目录。
