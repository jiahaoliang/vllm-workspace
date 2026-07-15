# Mooncake Layerwise 检视采纳记录

本文记录已采纳的检视建议、对应修复，以及可复现的验证证据。后续检视发现继续追加到此文件。

## 检视处理规则

- 检视过程中只把检视建议及采纳结论记录到本文，不逐条修改源码。
- 只有收到用户明确的“统一修改”命令后，才集中实现已采纳的检视建议。
- 每项修改按其所属原提交分别创建 fixup 提交，提交标题严格使用
  `#fixup <原 commit message>`（GitExtensions style）。
- fixup 提交创建后保持独立；只有收到用户明确的“统一 rebase”命令后，才将
  fixup 折叠到对应原提交。

## 2026-07-15: `ce51636e5` 的 `memcache_comm_fence` 测试隔离

- 检视结论：采纳（P2）。
- 问题：`tests/ut/distributed/ascend_store/_mock_deps.py` 在模块导入时向
  `sys.modules` 注册合成的 `vllm_ascend.memcache_comm_fence`。该全局替换会
  泄漏到同一 pytest session 的其他 UT，并且缺少真实模块的
  `record_attention_compute_start`。
- 根因：`ce51636e5` 新增的 `MooncakeBackend` 仅需要
  `vllm_ascend.distributed.parallel_state.get_global_rank` 的 mock；全局替换
  `memcache_comm_fence` 与新增的 Backend contract 无关。去除替换后发现，
  `_mock_deps.py` 创建的空 `vllm_ascend` package 会阻止 CPU 测试导入这个
  应保留真实实现的模块。
- 修复：删除 `memcache_comm_fence` 的全局替身注册，恢复原有注释；将测试中
  创建的 `vllm_ascend` package 的搜索路径指向真实源码目录。这样
  `memcache_comm_fence` 与 `ascend_config` 保持真实实现，而
  `tests/ut/conftest.py` 仍按单个 `ascend_store` 测试作用域 patch 所需符号。
- 回归测试：新增 `test_mock_deps_does_not_replace_memcache_comm_fence`，确认
  导入的模块来自真实 `memcache_comm_fence.py`，并暴露
  `record_attention_compute_start`。
- Rebase：`#fixup feat(kv_pool): define Mooncake layerwise backend contract`
  已折叠到 `ffd266831`（`feat(kv_pool): define Mooncake layerwise backend contract`）。
- 验证：先前该回归测试在合成模块上失败；修复后运行
  `pytest --confcutdir=tests/ut/distributed/ascend_store -q tests/ut/distributed/ascend_store`
  为 `348 passed`，并通过针对修改文件的 `ruff check` 与 `git diff --check`。
