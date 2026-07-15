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
- 测试基建：曾新增 `test_mock_deps_does_not_replace_memcache_comm_fence`；后续
  检视确认该测试只覆盖 helper 实现细节，因此已由 fixup 删除。隔离 CPU 测试
  仍通过完整 AscendStore suite 间接覆盖真实 `memcache_comm_fence.py` 的导入。
- Rebase：`#fixup feat(kv_pool): define Mooncake layerwise backend contract`
  已折叠到 `ffd266831`（`feat(kv_pool): define Mooncake layerwise backend contract`）。
- 验证：先前该回归测试在合成模块上失败；修复后运行
  `pytest --confcutdir=tests/ut/distributed/ascend_store -q tests/ut/distributed/ascend_store`
  为 `348 passed`，并通过针对修改文件的 `ruff check` 与 `git diff --check`。

## 2026-07-15: `ffd266831` 的测试基建改动超出 Backend contract 范围

- 检视结论：采纳（P2），已按验证后的调整方案实施，等待统一 rebase。
- 问题：`test_mock_deps.py` 只验证 `_mock_deps.py` 能从 fake
  `vllm_ascend` package 导入真实 `memcache_comm_fence.py`，没有验证
  Mooncake Backend contract 或跨测试污染场景。与之配套的
  `_vllm_ascend_real_path` 和 fake package 搜索路径改动也不是功能需求。
- 根因：本地 review 命令使用
  `--confcutdir=tests/ut/distributed/ascend_store`，因此跳过原本负责加载真实
  `vllm_ascend` 并提供 scoped patch 的 `tests/ut/conftest.py`。路径改动和
  `test_mock_deps.py` 是为了补偿这条隔离命令，而不是为了支持
  `MooncakeBackend`。
- 实施结果：
  1. 已删除 `tests/ut/distributed/ascend_store/test_mock_deps.py`。
  2. 已保留 `_vllm_ascend_real_path`、fake `vllm_ascend.__path__` 和当前
     `--confcutdir`；验证发现标准 `tests/ut/conftest.py` 在当前 CPU venv 中先因
     缺少 `vllm`，加入 sibling `repos/vllm` 后又因缺少编译扩展 `vllm._C` 无法
     加载。移除路径补偿会破坏当前可运行的 CPU suite。
  3. 已保留 `vllm_ascend.distributed.parallel_state.get_global_rank` mock；这是
     `MooncakeBackend` 新增 import 的必要测试依赖。
- 目标提交：`ffd266831 feat(kv_pool): define Mooncake layerwise backend contract`。
- Fixup：`299b873cc81dd7d713f9cb57e97637b1752cd539`
  (`#fixup feat(kv_pool): define Mooncake layerwise backend contract`)；尚未 rebase。

## 2026-07-15: `ffd266831` 的 commit/revoke 默认伪成功

- 检视结论：采纳（P2），已实施，等待统一 rebase。
- 问题：`Backend.batch_commit()` 和 `Backend.batch_revoke()` 对所有 backend
  默认返回与 key 数量对齐的全零结果，相当于宣告操作成功。Yuanrong 等不支持
  Mooncake session 的 backend 也会继承该行为，可能掩盖错误路由。
- 设计来源：implementation plan 为保持旧 backend 行为不变，明确要求 no-op
  默认实现；`0` 来自 control API 的成功码约定。但该兼容策略使 session contract
  不闭合：`batch_put_start()` 默认抛出 `NotImplementedError`，commit/revoke 却
  默认成功。
- 冗余实现：`MemcacheBackend.batch_commit()` 和 `batch_revoke()` 与基类完全
  相同，没有新增行为。Memcache 实际使用 `batch_alloc`、GVA `batch_copy`、
  `batch_add_lease` 和 `batch_remove_lease`，不会进入 Mooncake session 路径。
- 统一修改方案：
  1. 将 `Backend.batch_commit()` 和 `Backend.batch_revoke()` 改为抛出
     `NotImplementedError`，与其他不受支持的 session API 保持一致。
  2. 删除 `MemcacheBackend` 中重复的 commit/revoke no-op override。
  3. 仅由 `MooncakeBackend` 实现真实的 `batch_put_end` /
     `batch_put_revoke` 委托。
  4. 补充或调整测试，确认不支持 session 的 backend 会显式失败，而 Mooncake
     仍返回与 key 对齐的 Client 结果。
- 目标提交：`ffd266831 feat(kv_pool): define Mooncake layerwise backend contract`。
- Fixup：`299b873cc81dd7d713f9cb57e97637b1752cd539`
  (`#fixup feat(kv_pool): define Mooncake layerwise backend contract`)；尚未 rebase。
- 验证：两个新增 lifecycle 测试先因 no-op 未抛异常而失败；修改后 focused test
  通过，完整隔离 AscendStore CPU suite 为 `349 passed`，Ruff 与
  `git diff --check` 通过。
