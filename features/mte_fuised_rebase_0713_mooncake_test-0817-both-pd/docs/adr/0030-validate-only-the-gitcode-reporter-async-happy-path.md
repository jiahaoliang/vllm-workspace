# 初版 async 只验证 GitCode reporter happy path

状态：已接受

Blockwise DSA async scheduling的初版implementation completion gate只验证GitCode Issue #1 reporter的`P DP2/TP8 -> D DP2/TP8`单请求happy path。Gate使用真实`AsyncScheduler`与EngineCore depth-2 batch queue，并以CPU fake/mock替代model execution、Mooncake、SFA kernel、NPU tensor和`MultiprocExecutor` worker process；通过后只声明`GitCode reporter happy path已通过CPU/mock validation`，因为当前没有NPU资源，不能据此保证真实reporter deployment或graph-capture runtime。

Preemption、abort、D2H failure、late progress、adversarial metadata、多请求交错、asymmetric TP、speculative与非默认executor/scheduler lifecycle均不进入初版gate，只标记“未测试”；NPU、真实Mooncake transfer、fused kernel和graph-capture runtime保持`planned / not run`。这一收窄保留已接受的lifecycle correctness合同，但优先用最小测试证明external report的happy path，不把完整Phase B重跑作为初版async implementation的完成条件。
