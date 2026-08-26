# 允许 speculative 配置启动但暂不承诺 Blockwise DSA correctness

状态：已接受

`dsa_pd_offload=true`与speculative config的组合不在startup或metadata boundary被拒绝，本版也不为该组合增加validation或completion-gate test。该配置组合可以启动，但Blockwise DSA不承诺draft acceptance/rejection下的D2H range连续性、Main validity、preemption replay或cache correctness，也不能据此标记为supported或validated；具体配合方式留给后续实现。

这是对本map原“首版speculative decoding fail closed”边界的明确替换。现有source只展示`scheduled - current draft count`的range计算，不能证明async queue中optimistic computed-token state与accepted/rejected draft positions可以形成连续Host Main range；因为本决策同时拒绝startup gate和validation，该风险不由当前contract检测或恢复。Implementation acceptance必须排除该组合，文档与测试报告只能标记为out of scope / unverified。

普通`dsa_pd_offload=false`的`MooncakeConnectorV1` isolation保持不变；metadata mode/type checks继续防止default V1与DSA metadata互相混用，但不检查speculative config。完整scope决定见[定义 step-local D2H metadata 与 worker binding](../../issues/14-define-step-local-d2h-metadata-worker-binding.md)。
