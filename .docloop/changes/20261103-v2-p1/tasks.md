# Phase 1 实施任务

- [~] T-101 状态/契约分层与映射（status.py + 测试；workflow/DB 接线待做）
- [~] T-102 baseline.json/审批权威（CLI + Phase 1 baseline + workbench 文件投影已完成；原子性/统一读取待做）
- [~] T-103 evidence schema/兼容（可选字段、change_id、模板、旧证据读取规范化已加；producer 严格门禁/完整迁移待做）
- [x] T-104 checklist.md canonical 与兼容读取（代码/模板/文档/测试完成）
- [~] T-105 operation_id/幂等台账（OperationLedger + Worktree prepare 接线；其他副作用待做）
- [~] T-106 可靠性错误分类/修复/预算（错误分类、非重试权限、repair 拒绝已加；完整失败→修复→复验待做）
- [x] T-107 Git 忽略（agent-inputs/indexes）
- [~] T-108 测试发现/三层脚手架（tests/README.md 命令与字段；集成目录/自动发现待做）
- [~] T-109 最终验收状态/API（Workflow.accept + acceptance 节点 + 测试；workbench/CLI/UI 接线待做）
- [~] T-110 Skill 注册/路由/元数据（15 个全部路由、enterprise gate、version/risk/timeout 元数据；执行器待做）
- [~] T-111 Rules 强制检查与企业门禁（企业 Skill 代码门禁已加；Rules 内容检查待做）

执行顺序：T-101 → T-102/T-103/T-104 合同组 → T-105/T-106 → T-110/T-111 → T-107/T-108/T-109。每项先测试后实现；Phase 1 完成前不进入 Phase 2。

当前进度：T-104/T-107 完成；T-101/T-102/T-103/T-105/T-106/T-108/T-109/T-110/T-111 部分完成。Phase 1 未完成。
