# 不为 Unquiesced operation 增加 watchdog

状态：已接受；async terminal与preemption barrier继续受此边界约束

后续关系：ADR 0025、0026无法完成`QUIESCE`或`PREPARE_REPLAY` barrier时，不伪造completion、不释放ownership，也不新增watchdog、reliable cancel、fatal latch或automatic restart。

Blockwise DSA PD offload 首版对同步 transfer 不返回、background handler 长时间无 completion 或 cancellation drain 无法产生 quiesced ack 的情况，不增加 feature-specific watchdog、thread-health poll、per-request quarantine timeout、worker fatal latch 或 Mooncake native cancel。该行为沿用普通 `MooncakeConnectorV1`：只有同步调用实际返回后，connector 才根据返回值继续 success、failure/replay 或 cleanup；调用未返回时，对应 request 和 D destination ownership 继续保持 pending/隔离。

这是为了缩小首版对极罕见故障的实现范围，不代表系统已经证明 operation 会在有限时间内返回。首版接受由此产生的无限等待、容量占用和 Source TTL overrun correctness residual risk；恢复依赖 operation 最终返回、已有 worker/process failure 行为或外部进程/Pod 重启，不新增自动恢复 contract。

## 穿刺代码怎么做

穿刺 connector 同样没有针对卡死同步调用的 watchdog。`batch_transfer_sync_write()` 返回负值时只把 request 加入 `failed_reqs`，而调用不返回时，当前 layer 的 callback、pending-event 清理和 finished-event 都无法执行。Prefill 的 layer buffer reuse gate 最多等待 10 秒后抛 `RuntimeError`，但该异常不是 D destination quiesced ack，也没有协调 P source、D Indexer HBM 和 D Main Host ownership。

目标实现不迁移这个 10 秒 layerwise gate。它既不把等待超时解释成可靠 cancel，也不在超时后释放或复用 D block。

## 普通 MooncakeConnectorV1 怎么做

普通 `MooncakeConnectorV1` 在 background request handler 中同步调用 `batch_transfer_sync_read()`。调用返回负值时抛异常并标记 load failure；只有 `_handle_request()` 进入 `finally` 后才更新 task tracker、发送 completion 并执行远端 cleanup notification。

如果调用一直不返回，`finally` 不会执行。`get_finished()` 只读取 send/receive tracker，不检查 active transfer 的开始时间、background thread health 或 request-level deadline。Mooncake binding 通常有 internal timeout，但当前 native timeout 路径已注明 waiting task 可能导致 `freeBatchID()` 失败和 memory leak；首版不在 Python connector 层为这个极端情况再建立一套 watchdog。

## 考虑过的方案

- 完全不检查，沿用普通 V1。没有额外 production code、timeout 配置或部署前置条件；首版采用。
- Bounded watchdog 后 fail-stop Decode logical instance。它能给 D pool 建立明确的 process-lifetime reclaim boundary，但需要 operation tracking、fatal propagation、focused UT 和部署 restart contract；对于当前判断为极罕见的故障，首版不采用。
- 永久 quarantine 单个 request、Decode instance 继续服务。它避免立即复用 destination，但会永久损失容量并使各 TP 可用容量失衡；首版不采用。
- Mooncake reliable cancel。只有 cancel 返回能够证明不再发生 DMA 时，才允许 request-level reclaim；当前没有该 contract，且可能需要修改 Mooncake native，首版不采用。
- Timeout 后强制释放并 replay。旧 operation 可能继续写入已分配给其他请求的地址，存在 use-after-free-style silent corruption；任何版本都不能在没有 quiesced 证明时采用。

## 结果

- `mooncake_connector.py` 不增加 active-operation deadline、watchdog thread、fatal latch、background-thread liveness poll 或 unquiesced timeout 配置。
- 同步 Indexer/Main transfer 最终返回负值时，仍按 ADR 0011-0014 进入 local gate 和 request-level replay；本 ADR 只覆盖调用没有返回或无法证明 quiesced 的情况。
- Cancellation drain 没有 quiesced ack 时，不得释放 Main reservation 或 delayed NPU blocks，也不得伪造 `finished_recving`。这些 ownership 可以在 live process 中无限期保持隔离。
- 未返回的 active transfer 不进入 replay。Replay 会覆盖同一 destination，但旧 operation 仍可能继续写入，因此不满足 replay-ready。
- D 不向 P 发送伪 completion。P 仍按普通 V1 的 delayed-free tracker 和 480 秒 hard TTL 回收 source。
- 如果 operation 在 P source TTL 之后返回成功，connector 无法判断读取期间 source 是否已经被复用。该情况属于 ADR 0015 的 Source TTL overrun：可能读取错误 KV 并被当作成功，首版不提供 correctness 保证。
- Worker 或 EngineCore 自身崩溃时沿用 vLLM 现有 process failure 行为；本 feature 不承诺 API server/container 自动退出，也不把 Kubernetes liveness probe 设为功能前置条件。
- 外部进程或 Pod 重启会丢弃当前 Decode pool、reservation 和 request state，并重新完成 memory registration/handshake；这是 operational recovery，不是 connector 自动 recovery。

## 预计实现影响

本决策不增加 production watchdog 或 request recovery 代码，也不增加专门模拟永久阻塞调用的 unit test。现有 failure/replay 和 cancellation tests 只覆盖 transfer 返回或 worker 能产生 quiesced ack 的情况，不能声称验证了永久卡死后的自动恢复。

验证计划只需记录一个 risk-characterization case：人为阻塞 transfer 时，请求和相关 D ownership 不应被错误标记为 receive-complete、replay-ready 或 released；测试必须由外部 harness 设置有限总时长并负责结束/重启进程，不能让 unit test 自身永久等待。
