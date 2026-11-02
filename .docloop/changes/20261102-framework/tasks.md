# DocLoop Framework Implementation Plan

**Goal:** 落地已确认的框架 Spec，提供真实 LangGraph 离线编排和配置体系。
**Architecture:** 三个控制器分离需求、执行和恢复；SQLite 持久化图状态；CLI 驱动审批与恢复。
**Tech Stack:** Python 3.12、LangGraph、SQLite checkpoint、PyYAML、unittest、uv.lock。
**Spec:** 同目录 spec.md；用户于 2026-11-02 明确确认按文档开发。

## 全局约束

保留已审批 Spec 原文；企业规则只按 Profile 启用；模拟结果不能充当真实业务验收；不自动安装或冒称调用上游 Skills。
执行方式：当前会话顺序实现，使用测试先行与完成前验证。当前为新仓库专用 feature 分支，无其他工作需要隔离，不另建工作树。

## TASK-001：需求契约与审批基线

文件：pyproject.toml、src/docloop/contracts.py、src/docloop/governance.py、tests/test_governance.py。
接口：Governance.create(change_id, spec)、approve(change_id, expected_hash, approver)、assert_baseline(change_id)。
- [x] 写测试：未审批拒绝执行、错误 Hash 拒绝审批、篡改被拒绝、重复审批不可覆盖、路径不能越界。
- [x] 执行 `uv run python -m unittest discover -s tests -v` 观察缺失能力失败。
- [x] 实现数据契约、来源索引和不可覆盖基线，再运行对应测试。
覆盖：REQ-002、REQ-003；AC-002、AC-003。

## TASK-002：可靠性与受控工具

文件：src/docloop/reliability.py、src/docloop/adapters.py、tests/test_reliability.py、tests/test_adapters.py。
接口：Reliability.call(operation)、repair(fingerprint, progress)、charge(kind, amount)；ToolAdapter.run(argv, cwd)。
- [x] 测试瞬时失败初次加3次重试、预算耗尽、2轮无进展、3轮修复、超时、熔断、目录和命令白名单。
- [x] 先运行新测试确认失败，再实现；复测不得弱化断言。
覆盖：REQ-005；AC-005。

## TASK-003：图编排、验证与归档

文件：src/docloop/workflow.py、src/docloop/evidence.py、tests/test_workflow.py、tests/test_evidence.py。
接口：Workflow.start/change status/approve/resume；Evidence 验收覆盖与归档。
- [x] 测试图在审批前中断、SQLite 跨实例恢复、失败验证不得审查/归档、验收必须有覆盖和独立角色、归档校验 Hash。
- [x] 运行失败测试，再实现 LangGraph 节点与确定性演示适配器。
- [x] 运行图集成测试，验证失败恢复和审批后篡改处理。
覆盖：REQ-002、REQ-004、REQ-006；AC-002、AC-004、AC-006。

## TASK-004：配置与交付入口

文件：AGENTS.md、.docloop/{project.yaml,agents/,rules/,skills/,profiles/,templates/}、src/docloop/cli.py、README.md、启动演示.cmd、tests/test_project.py。
- [x] 测试五角色、四 Rules、16 Skills 必填契约、默认 Profile 与 CLI 错误码。
- [x] 从原文拆出权威内容，企业规则保留原文且注明适用 Profile，生成配置校验器与 CLI。
- [x] 全套测试、CLI 子进程演示、构建 wheel；写实际证据与交付限制。
覆盖：REQ-001、REQ-007；AC-001、AC-007。

## 依赖与验证

TASK-001 → TASK-003；TASK-002 → TASK-003；TASK-004 消费前三项。共享数据契约和同一 checkout，全部串行修改。
正式测试在 tests/，测试运行数据使用系统临时目录，不写入业务文件或污染框架基线。
