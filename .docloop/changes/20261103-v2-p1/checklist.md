# Phase 1 验收清单

- [~] AC-220 baseline.json + 旧 approval 兼容（CLI + Phase 1 + workbench 投影；原子性/统一读取待做）
- [~] AC-217/AC-224 状态分层/映射已加；workflow/DB 接线待做
- [~] AC-221 evidence 统一/历史兼容（旧证据可读并补齐字段；完整迁移/producer 策略待做）
- [x] AC-222 checklist.md canonical + checkList 兼容 + 大小写测试
- [~] AC-218 operation_id 台账（ledger + Worktree prepare；其他副作用待做）
- [~] AC-217 错误分类/非重试权限/repair/RepairLoop（workflow 修复→复验待做）
- [ ] AC-219 预算
- [~] AC-224 Workflow 显式最终验收节点/accept API（workbench/CLI/UI 接线待做）
- [~] AC-228 15 唯一/全部路由/enterprise gate/元数据（执行器待做）
- [~] AC-229 企业 Profile 门禁 + protected_paths（Rules 内容检查/审批待做）
- [x] AC-223 gitignore/agent-inputs/indexes
- [~] AC-213 三层测试命令/字段骨架（独立集成目录/自动发现待做）
- [ ] AC-233 测试门槛/真实报告
- [ ] 全量相关测试 + evidence + review；未运行项 not_run

当前：Phase 1 未完成；T-104/T-107 完成，T-102/T-103 部分；测试环境全量 111 项中 16 项受 macOS 临时目录/启动限制，相关套件通过。
