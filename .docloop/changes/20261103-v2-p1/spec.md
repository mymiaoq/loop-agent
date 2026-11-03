# DocLoop Agent V2.0 Phase 1：契约与可靠性

状态：approved（用户于 2026-11-03 确认 Phase 1 与推荐默认）；这是 Phase 1 的 Change 基线，不是 V2 全量基线。
上级规格：`../20261103-v2-upgrade/spec.md`；决策：`../20261103-v2-upgrade/decisions.md`。

## 范围

Phase 1 只收敛现有契约与可靠性，不实现 Worker/DAG/Codebase Context/Graph/VS Code/真实编码。

包含：T-101 状态映射、T-102 baseline.json、T-103 evidence schema、T-104 checklist.md、T-105 operation_id、T-106 reliability、T-107 gitignore、T-108 测试发现、T-109 最终验收契约、T-110 Skill 路由、T-111 Rules 门禁。

## 验收标准（Phase 1 子集）

- AC-217 错误分类、有限重试、2 轮无进展、3 轮修复、预算生效；权限错误不可重试。
- AC-218 外部副作用 operation_id 台账；恢复核验，避免重复副作用。
- AC-219 Task/Run/Token/工具/模型/并发预算；超限 blocked。
- AC-220 baseline.json 字段/权威/版本；兼容旧 approval.json；原字节不变。
- AC-221 evidence schema 统一，兼容历史，not_run 可表达且不计通过。
- AC-222 checklist.md canonical，兼容 checkList.md；大小写不敏感 FS 有测试。
- AC-223 .docloop Git 策略：配置跟踪，agent-inputs/indexes 忽略；eol/基线字节不变。
- AC-224 review 后 awaiting_acceptance；用户显式验收才 accepted；演示/真实区分。
- AC-228 15 个唯一 Skill 可注册/路由；document-parser 单份；7 个未路由 Skill 接入。
- AC-229 Rules 编码前/修改后/Review 检查；企业 Profile 代码门禁；Rules 修改审批。
- AC-213 三层测试脚手架可独立执行（Phase 1 只建立骨架和现有测试分层）。
- AC-233 测试/覆盖率按 Profile 配置，不固定 47/82；未运行标 not_run。

## 非范围

Worker Runtime、Task DAG、Codebase Context/Graph、真实编码 Runtime、VS Code、并发 2–3、Oracle/Docker 现场验收。Phase 2 前暂停确认真实编码 Runtime。

## 变更模块

`governance.py`、`workbench_store.py`、`evidence.py`、`workflow.py`、`reliability.py`、`project.py`、`skill_runtime.py`、templates/rules/agents、tests、`.gitignore`。

## 批准

用户于 2026-11-03 选择“先 Phase 1，Phase 2 前再定 Runtime”，并接受推荐默认。批准仅覆盖 Phase 1 子集；Phase 2+ 不在本 Change。
