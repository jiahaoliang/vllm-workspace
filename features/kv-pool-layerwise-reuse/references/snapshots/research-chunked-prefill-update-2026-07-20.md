Source: https://hackmd.io/@QQ5HFJZeT1-uFJm16Qaq_Q/HJGESQG4ze; supporting sequence: https://hackmd.io/@QQ5HFJZeT1-uFJm16Qaq_Q/rJUTYuX4Ml
Captured At: 2026-07-20T12:07:50+08:00
Notes: Research note for the 5.7 Chunked Prefill update. It records the authoritative delta, maps it to the current vLLM/vLLM-Ascend/Mooncake source, and separates confirmed requirements from unresolved ownership decisions.

# Chunked Prefill + Layerwise Mooncake 更新核对

## 结论

本次主设计的核心新增不是新的 ranged-transfer API，而是把已有 session API 的生命周期从“单次按层流水”扩展为“跨多个 chunk 的请求级生命周期”：

1. 每个 chunk 在按层流水前调用 `batch_get_start`，参数必须是该请求当时需要保护的全量 `load_keys`，以续约已有 lease 并为新增 key 建 lease。
2. 每个 chunk 只对本 chunk 的 `save_keys` 调用 `batch_put_start`，末层 ranged write 完成后立即 `batch_put_end`，使这些 key 可供后续 chunk load。
3. 正常路径只在 `is_last_chunk` 的最后一次 onload 完成后调用 `batch_get_end`，中间 chunk 不结束 get session。
4. 当前 Mooncake Client 已具备“再次 `batch_get_start` 会重新查 Master 并刷新本地 `lease_deadline`”的底层能力；主要缺口在 vLLM-Ascend 的跨 chunk key 累积和 get-session 收尾条件。
5. 两份 HackMD 都没有定义多个并发 request 共享同一 prefix key 时的 session ownership。当前 Client session 是 process-local `key -> entry`，因此这一点必须先定案，不能直接按单请求时序外推。

来源：主设计 [D] §5.7、§7；时序图 [S]；源码 [A2]、[A3]、[M1]。

## 抓取与版本证据

两份 HackMD 均通过 `/download` 抓取。直连在连接阶段超时，随后经代理成功获取 Markdown。

| 来源 | 抓取正文 | SHA-256 |
|------|----------|---------|
| [D] 主设计 | 632 行，22881 字符 | `3c01afffbfe9c81ab5229cd7565dc344be35031580630268252906e39ef8fe20` |
| [S] Chunked Prefill 时序图 | 82 行，1875 字符 | `9a4425a4ecf93af5ee1d300b6a154950cc6bb5d7aad553f94791d0077bdd2a15` |

源码核对基线：

| 仓库 | branch / 状态 | commit |
|------|---------------|--------|
| `repos/vllm` | detached HEAD | `ee0da84ab9e04ac7610e28580af62c365e898389` |
| `repos/vllm-ascend` | `feature/mooncake-layerwise-kv-pool` | `5957e2a14c7463ab66c1904b9e06f0cc91f36c7b` |
| `repos/Mooncake` | `feature/layerwise-kv-session` | `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` |

## 相对旧设计快照的完整正文差异

更新前本地设计正文与远端正文的实质差异只有三组：

1. `process_layer_data:` 改为 `process_layer_data（单 step / 单 chunk 骨架）:`，明确现有骨架的粒度。
2. 在 §5.6 和 §6 之间新增完整的 `### 5.7 Chunked Prefill：会话 API 挂点`。
3. §7 的 lease 风险从“一个默认 TTL 覆盖整段分层 onload”改为：默认 TTL 只需覆盖单 chunk；多 chunk 依赖每 chunk `batch_get_start` 续约；中途 `get_end` 或续约失败导致淘汰时，后续 onload 失败并由 vLLM fallback 重算。

没有发现 Backend ABC 方法签名、ranged-transfer 形状、per-block key 模型或 `batch_put_end` / `batch_put_revoke` 基础语义的其他改动。来源：[D] §5.5、§5.7、§7，以及更新前后正文的有序行比较。

## 5.7 的规范性要求

### 调用粒度和顺序

| API | 粒度 | 必须满足的顺序与输入 |
|-----|------|----------------------|
| `batch_get_start` | 每 chunk，且该 chunk 需要 load 时 | 进入 chunk、按层流水之前；输入为此前已 `put_end` 的 keys 与本 chunk 需 load 的 keys 的并集，包含初始 prefix hit |
| `batch_put_start` | 每 chunk，仅 saving rank | 同一 chunk 的 `batch_get_start` 之后；只传本 chunk `save_keys`，对象大小为 `page_size_bytes * num_layers` |
| `batch_copy_get` | 每层 | `src_offset = layer_id * page_size_bytes + layer_inner_offset`；必须在有效 get session 和 lease 内 |
| `batch_copy_put` | 每层 | `dst_offset = layer_id * page_size_bytes + layer_inner_offset`；只处理当前 chunk 中仍 active 的 save keys |
| `batch_put_end` | 每 chunk，仅 saving rank | 本 chunk 末层 `batch_copy_put` 完成后；当前 chunk 的 active keys 变为 COMPLETE |
| `batch_get_end` | 仅 last chunk 的正常收尾 | `is_last_chunk` 且最后一次 onload 完成后；中间 chunk 不调用 |

来源：[D] §5.7；[S] 的 Worker chunk loop。

### 每个 chunk 的状态迁移

```text
Scheduler request state
  batch_is_exist(prefix keys) -> ReqMeta / is_last_chunk

Worker request state, chunk Ci
  accumulated_load_keys = prior COMPLETE keys U current load keys
  batch_get_start(accumulated_load_keys)        # renew existing + acquire new
  batch_put_start(current_chunk_save_keys)
  for each layer:
      onload next | compute current | offload previous
  wait final onload of Ci
  if is_last_chunk:
      batch_get_end(accumulated_load_keys)
  wait final offload of Ci
  batch_put_end(current_chunk_active_save_keys) # visible to Ci+1
```

`batch_get_end` 与 `batch_put_end` 分属读、写会话，二者的必要同步点不同：前者不得与最后一个 ranged read 并发；后者不得早于本 chunk 最后一个 ranged write。时序图把 last-chunk `get_end` 放在最终 onload 之后，把 `put_end` 放在最终 `copy_put` 之后。[S]

### lease 语义

- 单次 lease 只要求覆盖一个 chunk 的按层 onload，不要求覆盖整个 multi-chunk prefill。[D] §7
- 每个 chunk 的 `batch_get_start` 必须接收全量 `load_keys`，让已有 key 续约、首次出现的 key 新建 lease。[D] §5.7
- ranged read 不得在 session miss 或 lease expired 时自行查询 Master；失败交给 vLLM 标记 load 失败并 fallback。[D] §4.3.1、§7

## 当前源码映射与缺口

### vLLM

当前 `execute_model` 生命周期会在每个绑定了 `SchedulerOutput` 的 forward 前调用 `start_load_kv`，forward 结束时收集 connector 结果并清 metadata。因此 chunked prefill 的每个调度 step 会重新进入 connector worker，而不是在一个 Python 调用内完成所有 chunk。[V1]

主设计明确不改变 attention hook `wait_for_layer_load` / `save_kv_layer` 契约，所以当前 vLLM hook 不需要新增 API；跨 chunk 状态应由 connector/scheduler-worker metadata 管理。[D] §1.3；[V1]

### vLLM-Ascend 已有可复用部分

- Scheduler 的 `RequestTracker` 跨 step 保存 `token_len` / `num_saved_tokens`，每次 `build_connector_meta` 都会为 running cached request 生成新的 `ReqMeta`；`is_last_chunk` 已由累计 token 长度计算。[A1]
- `ReqMeta` 已带 `save_start_token`、`save_end_token`、`is_last_chunk`、`save_block_keys`、`load_block_keys` 和 `load_keys`。[A1]
- save 线程已把 `_active_put_keys` 限定在一轮 layer 0..N 的 forward batch，末层只对仍 active 的 key 调 `batch_commit`；range 失败会 `batch_revoke` 并从 active set 移除。这与“每 chunk put_end”一致。[A4]
- receive 线程已把 `is_last_chunk` 传播到最终层，并只在 last chunk 标记 request finished，但该标志尚未用于 get-session 收尾。[A4]

### vLLM-Ascend 当前缺口

1. `_prepare_mooncake_get_session` 只在当前 `ReqMeta.load_spec` 存在时构造 load keys；running cached chunk 在 Scheduler 中明确使用 `load_spec = None`。因此后续 chunk 当前不会自然得到“初始 prefix + 之前已 COMPLETE chunk”的全量 `load_keys`。[A1][A2]
2. `_prepare_mooncake_layerwise_sessions` 每次 `process_layer_data` 都调用 `_reset_layerwise_load_sessions`，把 `_opened_load_keys` 清空；状态粒度仍是当前 forward batch，而不是 request 的 multi-chunk 生命周期。[A2]
3. `wait_for_layer_load` 当前在每一批的最终层都调用 `_close_load_sessions_once`，未判断 `request.is_last_chunk`；这正是 §5.7 禁止的中间 chunk `get_end`。[A2]
4. `_opened_load_keys` 是进程级 list，不记录 `req_id -> keys` ownership；一个 `process_layer_data` 又可合并多个请求。这不足以表达不同请求各自到达 last chunk 的时间。[A2][A3]
5. preemption、finished request 和异常路径当前没有清理跨 chunk request-owned get-session 状态，因为这种持久状态尚不存在。引入状态后必须与 `meta.preempted_req_ids` / `finished_req_ids` 对齐回收。[A5]

### Mooncake 已有能力与边界

- `RealClient::batch_get_start` 每次都对传入的全部 keys 执行 `BatchQuery`，选择 COMPLETE memory replica，并覆盖 `get_sessions_[key]` 的 descriptor 与 `lease_deadline`。它不会因为已有本地 session 而跳过查询，因此已经具备每 chunk 续约能力。[M1]
- `batch_get_into_multi_buffer_ranges` 只读本地 session；开始前和 transfer 返回后都会检查 deadline，过期时返回 `LEASE_EXPIRED` 并 erase session，不会二次查 Master。[M1]
- `batch_get_end` 只是对传入 keys 执行 `get_sessions_.erase(key)`，当前没有 owner/refcount。[M1]
- `batch_put_start` / ranged write / `batch_put_end` / `batch_put_revoke` 已实现 current-chunk 写会话所需基础语义。[M1]

因此，5.7 的主功能不要求新增 Mooncake Python API；至少需要补“重复 `batch_get_start` 确实刷新 deadline”的测试。是否在 Client 内增加 ownership 机制取决于下面的共享 key 设计决策，来源没有要求必须落在 Mooncake Client。

## 错误与清理边界

| 失败点 | 已有设计语义 | Chunked Prefill 需要补齐的边界 |
|--------|--------------|--------------------------------|
| `batch_get_start` 部分失败 | 失败 key 不进入 ranged read；标记对应 block load 失败 | 已成功续约的 key 继续；失败的既有 session 可能已被 Client erase，后续 chunk 必须 fallback 或重新 start |
| ranged get 返回负码 / `LEASE_EXPIRED` | 该 row 标记 invalid；不在 ranges 内查 Master | 保持其他 row 可继续；last-chunk 或 request abort 时再统一清可用 session |
| `batch_put_start` 部分失败 | 失败 key 不进 shared / copy | 不得加入后续 chunk 的 accumulated load keys |
| ranged put 失败 | 立即 `batch_revoke`，从 active keys 移除 | 不得 `put_end`，也不得让后续 chunk load 该 key |
| `batch_put_end` 失败 | 当前实现尝试 revoke | 只有成功 COMPLETE 的 key 才能加入后续 chunk load set；需要把逐 key结果反馈到持久状态 |
| 中间 chunk 正常结束 | 新增要求 | 不调用 `batch_get_end`；只依赖下一 chunk `batch_get_start` 续约 |
| last chunk 正常结束 | 新增要求 | 等最后 ranged read 完成后 end 累积 get keys；写侧仍独立等待最后 ranged write 后 end active put keys |
| preempt / cancel / forward abort | §5.7 未细化 | 必须 best-effort end 已开 get sessions、revoke 未完成 put sessions，并清 request-owned state；这是实现必须定义的异常收尾 |

来源：[D] §3、§4.3、§5.7、§7；当前错误传播 [A2]、[A4]、[M1]。

## 未定义但必须先定案：共享 prefix key ownership

来源没有回答以下并发场景：

```text
request A: load key K, 当前 chunk 是 last
request B: load key K, 当前 chunk 不是 last
RealClient: get_sessions_[K] 只有一个 entry
```

如果 A 直接 `batch_get_end([K])`，当前 Client 会 erase K 的唯一 process-local session；这会使 B 的 session 也消失。虽然 B 的下一 chunk 可以再次 `batch_get_start([K])`，但这仍违反“B 的中间 chunk 不 end”的字面生命周期，并且在支持 Master 提前放租约后会产生更明显的语义差异。[M1]

主设计和时序图都只给出单请求/单 chunk 的 API 流程，没有 owner/refcount、共享 key close 规则或 mixed-lastness batch 的规定。[D] §5.7；[S]

实施前必须从以下方向中做明确选择并写入测试，本文不替来源作决定：

- vLLM-Ascend Worker 维护 `key -> active request owners`，仅最后一个 owner 结束时调用 Client `batch_get_end`；
- Worker 保持 request 级 key set，但允许一个 request 的 `get_end` 删除共享 session，并要求其他 owner 下一 chunk强制 reopen；
- Mooncake Client 将 get session 改为带 owner/refcount 的更高层契约，这会改变现有 API 语义。

## 测试影响

### vLLM-Ascend unit tests

1. 两个以上 chunk：C0 `get_start(prefix)` / `put_start(save0)` / `put_end(save0)`；C1 `get_start(prefix + save0 + load1)`；只在 Clast `get_end(accumulated)`。
2. 验证每个 chunk 的 `put_end` 只包含该 chunk 所有层都成功的 active keys，失败或 revoke key 不进入下一 chunk load set。
3. 验证非 last chunk 最后一层不调用 `batch_get_end`，last chunk 在最后 ranged read 完成后恰好调用一次。
4. get-start 续约部分失败、lease 在 chunk 内过期、lease 在两个 chunk 之间过期时，逐 block invalid / fallback 行为可观察，且不误伤成功 rows。
5. preempt、cancel、receiver exception、load timeout 时清 request 持久状态；`batch_get_end` 不与 in-flight ranged read 竞态。
6. mixed batch：A last、B non-last，二者共享 prefix key。期望值必须等 ownership 决策定案后编写。
7. Scheduler/metadata：running cached chunk 必须能表达累计 load keys，`is_last_chunk` 在最后一个 prompt chunk 才为 true。

当前测试只覆盖单批 final-layer 会调用 `batch_get_end`，这会把现有错误行为固定下来，需要按 §5.7 改写；尚无 multi-chunk session 生命周期测试。[A6]

### Mooncake tests

1. 连续两次 `batch_get_start(keys)`：第二次走 Master，并把 `lease_deadline` 向后刷新；刷新后 ranged read 成功。
2. 续约部分失败：失败 key session 被清，成功 key session 仍可 ranged read。
3. `batch_get_end` 幂等以及 end 后 ranged read 返回 session miss 的现有语义继续保留。
4. 如果 ownership 最终落在 Client，再增加 shared-key owner/refcount 测试；否则不扩大 Mooncake API。

现有测试已覆盖 lease 超时后 ranged read 返回 `LEASE_EXPIRED` 并删除 session，以及 `batch_get_end` 后 ranges 失败，但未覆盖重复 start 续约。[M2]

### E2E

- NPU + Mooncake，prompt 至少跨 3 个 chunks；逐 chunk 检查 prefix + 之前 COMPLETE keys 的 onload、当前 chunk save 的可见性和最终 accuracy。
- 使用短 `default_kv_lease_ttl` 证明每 chunk续约有效，再注入一次续约失败验证 vLLM fallback。
- 并发两个共享 prefix 的请求，覆盖 mixed-lastness ownership 决策。

## 证据索引

- [D] `https://hackmd.io/@QQ5HFJZeT1-uFJm16Qaq_Q/HJGESQG4ze/download`，主设计 §1.3、§3、§4.3、§5.5、§5.7、§7，抓取哈希见上表。
- [S] `https://hackmd.io/@QQ5HFJZeT1-uFJm16Qaq_Q/rJUTYuX4Ml/download`，Chunked Prefill + Layerwise 完整流程，抓取哈希见上表。
- [V1] `repos/vllm/vllm/v1/worker/kv_connector_model_runner_mixin.py:75`，每个 `execute_model` 的 connector metadata、`start_load_kv`、finalize 生命周期。
- [A1] `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py:682`、`:801`、`:906`；`config_data.py:837`、`:980`，跨 step tracker、per-step `ReqMeta` 与 `is_last_chunk`。
- [A2] `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py:1295`、`:1320`、`:1404`、`:1495`、`:1544`，当前 get-session 的 batch 级 reset/open/close。
- [A3] `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py:1445`，多请求 key 去重和进程级 `_opened_load_keys`。
- [A4] `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py:1458`、`:1494`、`:1726`、`:1768`，逐层 active set、commit/revoke、load 失败和 last-chunk 标记。
- [A5] `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py:1075`；`pool_worker.py:1949`，preempted/finished metadata 和 Worker finalize。
- [A6] `repos/vllm-ascend/tests/ut/distributed/ascend_store/test_pool_worker.py:2154`、`:2164`、`:2177`，当前 get-session close 单批测试。
- [M1] `repos/Mooncake/mooncake-store/src/real_client.cpp:4892`、`:4941`、`:5044`、`:5052`、`:5198`、`:5247`，Client session/ranges 实现。
- [M2] `repos/Mooncake/mooncake-store/tests/pybind_client_test.cpp:1019`、`:1062`，session end/miss 和 lease-expiry 测试。
