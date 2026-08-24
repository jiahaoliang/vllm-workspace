# Blockwise DSA replacement white-box review amendment

状态：用户已于 2026-08-24 明确采纳 Main reservation 截断、DSA receiver queue
复用和 stale-result observability 三项 corrective direction；当前只授权文档记录与代码量
评估，不授权 production source/test 修改、commit、push 或 control-repo final update。
`pending-command` ordering 仍为独立待决项。

## 1. Scope 与 authority

本 amendment 记录 replacement four-commit implementation完成后、相对干净 base
`0d6dd0d26ab69219f861c9b312329f4c60fe36f2` 对 source HEAD
`3a22c5a6d697250dbf942354bfdac1781af3077d` 的 white-box review。当前 source diff为：

| 类别 | Additions | Deletions |
|---|---:|---:|
| Production | 1,670 | 39 |
| Focused tests | 1,320 | 43 |

本轮不等待或执行 NPU validation。NPU 资源当前不可用，状态继续为
`planned / not run`；以下三项由 accepted spec/ADR、Python source ownership和线程/queue
结构直接判定，不依赖 NPU runtime evidence。

这三项不是 product-scope 或 wire-contract 变更：

- reservation 截断恢复 ADR 0006 已接受的 capacity公式；
- receiver queue 复用恢复 Stage 1 design gate 已接受的 existing-code reuse boundary；
- stale-result observation 恢复 spec item 36 与 ADR 0021 已接受的 result-validation行为。

因此当前不修改 `spec.md`、ADR 0006 或 ADR 0021，也不建立新 ADR。若实现需要改变这些
既有 contract、增加 standalone subsystem或修改 upstream vLLM core，必须重新停审。

## 2. 已采纳 corrective decisions

### 2.1 Main lifetime reservation 必须按 `max_model_len` 截断

Accepted formula是：

```text
cdiv(min(max_model_len, prompt_len + request.max_tokens), main_block_size)
```

当前 `_MooncakeDsaDecodeScheduler.get_num_new_matched_tokens()` 使用未截断的
`prompt_tokens + request.max_tokens`。vLLM `Request.max_tokens` 保留 sampling limit，core在
调度/finish阶段另按 `max_model_len` 截断实际序列；因此未截断 reservation可能要求一个请求
永远无法合法使用的 Host capacity，并通过 step-local HOL gate阻塞后续 DSA admission。

实现必须复用 scheduler initialization 已读取的 `max_model_len`，不新增第二个 capacity owner，
不改变 startup最大请求容量校验、HOL语义或 `CPUBlockManager` ownership。

### 2.2 DSA receive 必须复用 receiver request queue 和 per-peer serialization

普通 `KVCacheRecvingThread.add_request()` 经 `request_queue`、`_submit_request()` 和
`peer_request_queues[(remote_host, remote_handshake_port)]`，确保同一个 peer同时只有一个 active
handler，并通过 `MAX_REQUESTS_PER_PEER_HANDLER` 在 peers之间让出 executor worker。

当前 `add_dsa_request()` 直接调用 `executor.submit(_execute_dsa_receive, ...)`，绕过上述
queue、per-peer serialization和fairness boundary。实现必须把 DSA receive表示为现有 receiver
queue中的typed/local task branch；不得新增 transport、executor、runtime或第二套 peer queue。
普通 V1 request task tracking/completion语义不得被 DSA callback混用。

该偏差已确认；但当前 static evidence没有证明 Mooncake同-peer并发必然造成 cache corruption。
修复理由是恢复 accepted concurrency envelope和existing-code reuse contract，不把未验证风险描述为
已执行故障。

### 2.3 Stale result 必须可观察后再忽略

当前 `_MooncakeDsaDecodeScheduler.update_connector_output()` 对已经释放的 request和旧
`(execution_epoch, command_seq)` result直接 `continue`。这保持 ownership安全，但没有满足
ADR 0021的“rate-limited warning/metric后忽略”。

实现应优先复用当前 `vllm.logger.logger.warning_once` 或仓库已有的bounded warning机制，至少区分：

- terminal/released request的late result；
- active request的旧 epoch/command result。

Observation不得重新创建 tracker、推进 validity、生成 `finished_recving`或建立新的 metrics/
history subsystem。相同 duplicate的正常幂等路径不应产生warning storm。

## 3. 三项修复的增量代码量估算

以下是相对当前 HEAD的additional additions/deletions，不是相对base的总diff，也不是quota目标：

| Corrective item | Production additions | Production deletions | Focused-test additions | Focused-test deletions |
|---|---:|---:|---:|---:|
| `max_model_len` reservation截断 | 3-6 | 1-2 | 8-14 | 0-4 |
| DSA receiver queue/per-peer复用 | 28-45 | 8-18 | 24-40 | 4-12 |
| stale-result bounded observation | 6-12 | 0-2 | 8-16 | 0-4 |
| **合计** | **37-63** | **9-22** | **40-70** | **4-20** |

若不删除或替换任何现有added lines，预计相对base的总additions变为：

- Production：`1,707-1,733`；现有 `1,710` stop line在估算中段会触发；
- Focused tests：`1,360-1,390`；现有 `1,320` stop line必然触发。

不得仅为维持数字删除 typed negative boundaries、public Scheduler replay/preemption evidence、
default V1 regression或worker ordering tests。可以通过把新 assertions并入现有同一 lifecycle case、
替换只证明旧错误行为的case或删除真正重复/dead scaffolding降低净 additions，但coverage replacement
必须逐项说明。

由于 `pending-command` 方案的 production net delta可能为 `-5..+45`，focused tests可能再增加
`10..50` 行，
本 amendment不提前设定统一的新 stop line。完成该决策后应提交一份包含四项工作总量、可替换测试
和新 stop line的单一 implementation budget gate，再决定是否授权 source/test修改。

## 4. `pending-command` ordering：待决，不计入前三项批准

当前已确认的facts：

- DSA receive在 `ThreadPoolExecutor` worker中执行，并从该线程调用
  `_finish_dsa_operation()` callback；
- engine thread通过 `start_load_kv()`接受snapshot并dispatch command；
- `state.in_flight` check、`state.pending_command` publish、completion clear/read之间没有lock；
- private worker test允许新 `PREPARE_REPLAY` 在旧receive drain前进入pending；
- accepted scheduler failure path等待exact TP terminal coverage，public preemption evidence也在receive
  complete后才产生preemption；当前未证明production scheduler会把非`QUIESCE` command送入具体的
  lost-wakeup窗口；
- cancellation使用独立的 `pending_quiesce` drain path，不能直接作为
  `pending_command` lost-wakeup的可达性证明。

因此上一轮把该问题直接定为confirmed High correctness bug证据不足。下一步必须在以下问题上做
显式选择：

1. Worker contract是否承诺任意validated successor command都可与旧local operation completion并发；
2. 若承诺，选择per-request atomic state transition还是把completion重新投递到single-owner queue；
3. 若不承诺，是否把scheduler causality写成显式invariant并删除无法从production到达的
   `pending_command`支持；
4. 无论选择哪条路径，如何用deterministic interleaving/public lifecycle test证明，而不是依赖线程时序。

在该决策获得明确批准前，不修改worker synchronization、pending state或相关tests。

## 5. 下一门禁

下一步只深入 `pending-command` ownership和可达性决策。完成后展示：

- 选定invariant与被拒绝方案；
- 对receive、preemption、transfer failure、cancellation和fused D2H的逐场景影响；
- 四项合并后的production/test增量预算与新stop line；
- proposed failing tests和source staging allowlist。

未经用户再次明确批准，不进入 source/test编辑、Pod验证、commit或push。
