# 只验证 default MultiprocExecutor 与 default AsyncScheduler

状态：已接受

Blockwise DSA async scheduling首版只把default `MultiprocExecutor`与default `AsyncScheduler`纳入correctness contract和static/CPU/mock validation target。Executor classification与P/D topology相互独立；Ray、`UniProcExecutor`、external launcher、`BalanceScheduler`、custom executor/scheduler及其他组合均允许启动，但startup只warning为`unverified` / “未测试”，兼容性文档不展开具体影响范围。

未测试组合不会因为upstream `supports_async_scheduling()`、class inheritance或一次无报错运行自动升级。加入validation target前必须完成对应source audit，证明per-worker step FIFO、FIFO output consumption、all-worker aggregation与metadata-only/no-forward batch ordering，再通过相同CPU/mock completion gate并更新compatibility matrix；NPU和graph-capture runtime仍按独立证据标记`planned / not run`。
