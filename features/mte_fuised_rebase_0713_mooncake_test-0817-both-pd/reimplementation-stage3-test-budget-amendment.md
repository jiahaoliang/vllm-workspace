# Blockwise DSA Stage 3 public replay test-budget 增量门禁

状态：已批准并用于sync replacement的历史test budget；async fail-closed与`FUSED_D2H` evidence条款已被ADR 0024-0030部分取代；旧授权与stop line不延伸到async delta

本文件只处理
[`reimplementation-stage3-closure-amendment.md`](./reimplementation-stage3-closure-amendment.md)
批准后触发的 test budget 与 public replay correctness blocker。它不改变已经批准的
scheduler-authored live reservation snapshot、structured replay observation、module shape
或 failure boundary，也不授权 commit、push、lock/repo-state/issues 更新或 final feature
status。

## 1. 为什么必须再次停审

相对干净 base `0d6dd0d26ab69219f861c9b312329f4c60fe36f2`，当前 replacement WIP
的完整规模为：

| 类别 | Additions | Deletions |
|---|---:|---:|
| Production | 1,663 | 39 |
| Focused tests | 1,237 | 43 |

Production 仍低于已批准的 `1,710` stop line；focused tests 已超过 `1,200` 共 37 行。
`test_mooncake_dsa_metadata.py` 当前是 untracked 新文件，普通 `git diff --numstat` 会漏掉
它的 173 行；以上数字已显式计入该文件。

最新 public test 尚未在 UT Pod 中运行。Static source trace 同时证明它不是单纯 test wiring
问题：真实 replay/resume 会命中当前 production admission bug，因此不能把该 test 当作
已经完成的 evidence。

## 2. Current Code：public replay admission blocker

当前 `_MooncakeDsaDecodeScheduler.get_num_new_matched_tokens()` 对任意 existing tracker
都返回 `(tracker.num_external_tokens, True)`。这混淆了三个不同阶段：

1. 首次 `RECEIVE_REMOTE` 或 allocation retry：需要正 external token count 和
   `load_kv_async=True`；
2. preemption 后等待新 Indexer ownership：需要先按当前 full sequence 分配新 blocks，
   发布 `PREPARE_REPLAY`，并在 exact `REPLAY_READY` 前保持 async waiting；
3. exact `REPLAY_READY` 后的 local full-sequence forward：必须返回 `(0, False)`，让 core
   从 token 0 真正调度 compute，而不是再次进入 remote load。

Transfer failure transition 已把 tracker 的 `num_external_tokens` 置 0。真实 core 再调用
hook 时会得到 `(0, True)`，随后触发 vLLM scheduler 对 async load 的
`num_external_computed_tokens > 0` assertion。Preemption resume 则会把旧 prompt external
tokens再次当成 remote load，无法进入最终 token-0 forward。

推荐 thin fix 仍位于现有 `mooncake_connector.py` scheduler seam：

- `RECEIVE_REMOTE` allocation retry继续返回原 external tokens与 `True`；
- `awaiting_rebind` 返回当前 full-sequence token count与 `True`，只用于分配新 Indexer
  blocks并等待 `PREPARE_REPLAY` exact completion；
- rebind 后清除后续 remote-load token事实；
- exact `REPLAY_READY` 后 existing tracker返回 `(0, False)`，进入本地 token-0 forward。

该修复不修改 vLLM core，不新增 state owner、module、public interface、action/result kind
或 standalone subsystem。预计 production 增量为 `+8..15/-1..3`，final production
additions约 `1,671..1,678`，仍低于既有 `1,710` stop line。

## 3. Current Evidence 与缺口

当前 `a2/test_remote_prefill_lifecycle.py` 的 public test已经使用 real
`vllm.v1.core.sched.Scheduler` 串联 `add_request() -> schedule() ->
update_from_output()`，并尝试证明 transfer failure 的 partial-TP barrier、
`PREPARE_REPLAY` 和 token-0 schedule。

它尚未证明：

- 当前 test在真实环境中能越过上述 replay admission assertion；
- token-0 forward 的 fake runner output被 public `update_from_output()` 消费；
- real scheduler因 KV pressure产生 preemption，而不是手工注入 `preempted_req_ids`；
- resume 使用相对旧 epoch真正不同的新 Indexer block table；
- Main reservation identity跨 epoch保持；
- continuity成立时 `FUSED_D2H` 只写 preserved Main suffix；
- exact TP coverage前不写 replay event，coverage后只写一条
  `scope=decode_dp` aggregate event；
- nonzero per-rank `skipped_d2h_bytes` 正确求和；
- transfer-failure `confirmed_main_tokens=0` 携带 nonzero skipped bytes时 fail closed；
- old incarnation仍 live时直接拒绝 conflicting request-ID incarnation。

Worker test目前能证明 registration-derived local bytes公式和 pending receive ordering；typed
metadata test能证明字段schema。两者都不能替代 Decode-DP scheduler exact aggregation或
public preemption lifecycle evidence。

## 4. 可删除与不可删除的 test code

`test_mooncake_connector.py` 中以下 38 行 helper当前完全无调用，可以删除：

- `_scheduler_output()`；
- `_complete_decode_receive()`；
- `_complete_dsa_command()`，其唯一 caller也是上述 dead helper。

这是删除 private transition tests 后留下的 dead test scaffolding，移除它不会减少
evidence。删除后 focused test additions从 `1,237` 降为 `1,199`。

以下 tests不能为满足数字而删除：

- typed schema、immutability/pickle、action/result matrix、snapshot validation和same-step
  aggregate conflict；
- startup/config/async fail-closed matrix；
- command-never-emitted cancellation、Quiesced前隔离、release-once和HOL；
- multi-node endpoint projection、receiver phase ordering和engine mismatch；
- duplicate/conflict/stale/future/missing/exact-rank result admission与multi-request isolation；
- worker save drain/fail-fast、snapshot retirement/resurrection/request-ID reuse、pending
  operation ordering、registration-derived bytes和capacity mismatch。

Public preemption test green后，可以删除其中被public path真正覆盖的少量positive transition
assertions；negative matrix和worker-local boundaries仍须保留。删除必须以coverage替代为依据，
不能以行数为依据。

## 5. 方案 A：保持 production line，修订 focused-test line

推荐保持 production stop line `1,710`，把 focused-test stop line从 `1,200` 修订为
`1,320`。预计 test 变化为：

| File | Additional additions | Removed current additions | 计划 |
|---|---:|---:|---|
| `test_mooncake_connector.py` | 5-10 | 38-48 | 删除dead helpers；补zero-boundary/nonzero-bytes与conflicting-incarnation boundary；仅在public coverage成立后裁positive duplicate |
| `a2/test_remote_prefill_lifecycle.py` | 65-85 | 0 | 修复并完成transfer-failure forward；增加real preemption、new Indexer table、stable reservation、suffix D2H和single aggregate event |
| `test_mooncake_dsa_metadata.py` | 0 | 0 | 现有schema evidence足够 |
| `tests/ut/kv_offload/utils.py` | 0 | 0 | 现有role、extra config和hybrid group参数化足够 |

在不假设可选 positive-test 裁剪的保守口径下，预计 final focused-test additions约
`1,269..1,294`；`1,320` 是 stop-and-review threshold，不是 quota目标。该修订仍比
`60eb76e` 的 6,034 test additions少约 78%，且没有恢复其14个shallow subsystem test
suites。

批准方案 A 后，以下条件任一触发时必须再次停止：

- production additions超过 `1,710`；
- focused-test additions超过 `1,320`；
- 需要新增 production module、public connector interface或修改 vLLM core source；
- 需要删除上述不可替代 boundary evidence；
- 需要扩大 positional ABI、reliable cancel、watchdog、automatic restart、async
  multi-batch或process-failure contract。

## 6. 不采用的方案

### B. 保持 `1,200` 并删除 boundary tests

不采用。除38行dead helpers外，当前private tests分别验证public Scheduler不能观察的typed
contract、worker ordering、memory/data-plane与negative failure boundary。删除至少额外
69-94行才能容纳缺失public evidence，会让数字变小但contract不再有证明。

### C. 只保留当前 transfer-failure public test

不采用。它没有覆盖accepted preemption contract，也没有证明new Indexer ownership、Main
reservation continuity、suffix-only D2H或structured Decode-DP observation。

### D. 继续依赖 private scheduler transition test或 `60eb76e` oracle

不采用。Closure gate和Stage 1 oracle-gap已经明确要求real core scheduler lifecycle；旧
private state injection只能证明connector内部transition，不能证明core实际从token 0 forward。

## 7. 批准后的 TDD 与验证顺序

1. 先同步当前 checkout到 `liangjiahao/vllm-ascend-ut`，运行现有public transfer-failure
   test取得真实red，并记录具体assertion/traceback；不得把static source trace写成已运行结果。
2. 增加state-qualified admission与public preemption failing tests，使用KV pressure让real
   scheduler产生preemption，不直接调用private `_preempt_request()`或手工构造后继
   `SchedulerOutput`。
3. 只在 `mooncake_connector.py` 的现有private SFA scheduler seam实现thin fix；不修改
   vLLM core。
4. Public flow必须证明：exact-TP receive/replay、new Indexer IDs、stable Main reservation、
   token-0 runner update、preserved suffix-only D2H、nonzero TP sum和single structured event。
5. 删除38行dead helpers；只有public replacement green后才裁掉真正重复的positive private
   assertions。
6. 重新计算包含untracked files的完整预算，然后运行metadata、connector focused、A2、
   affected SFA、完整 `tests/ut/kv_offload`和default V1 regression。
7. Static、CPU/mock、default V1、multi-node与NPU evidence分开报告；真实multi-node/NPU/
   runtime/performance仍为 `planned / not run`。
8. 展示最终base/head、逐文件diffstat、预算、test commands/results、剩余风险和staging
   allowlist；未经再次明确批准，不commit、push或更新lock/repo-state/issues/final status。

## 8. 批准边界

用户已于 2026-08-24 明确批准“Stage 3 test-budget amendment 方案 A”。该批准只把
focused-test stop line修订为 `1,320`，并授权本文件第2、3、5、7节描述的thin replay
admission修复与evidence闭环；所有其他accepted decisions和发布门禁保持不变。
