# DocLoop 框架开发入口

本仓库是 Python + LangGraph 的 DocLoop 平台框架。当前实现范围见 `.docloop/changes/20261102-framework/spec.md`，审批记录独立保存在 baseline/approval.json。

## 开发本框架

项目配置入口是 `.docloop/project.yaml`，默认 Profile 为 docloop-platform。读取通用 code-standard 和 verification-standard；仅改任务范围内代码。运行 `uv run python -m unittest discover -s tests -v` 和 `uv run docloop doctor`。依赖以 uv.lock 锁定。

五角色文件定义目标运行系统的行为，不会自动将当前开发会话切换为某角色。企业 Vue/Java、端口、组件库和品牌只由 enterprise-vue-java Profile 条件启用。

## 运行 DocLoop

需求、执行、可靠性控制分别见 src/docloop/governance.py、workflow.py、reliability.py。Rules 的唯一权威目录是 `.docloop/rules/`；`.docloop/docs/source-design.md` 是原始设计参考，不能作为第二份可编辑运行规则。

变更材料写入 `.docloop/changes/<change-id>/`。按 REQ → AC → TASK → TC → V → Commit 关联。基线审批后保持原字节；需求变化创建新 Change。实现、验证、审查接口职责分离，失败、阻塞和未执行结论如实记录。

Skills 按 task_context 选择；平台与领域共15个唯一 Skill，其中 document-parser 为共享定义。Superpowers 版本由 project.yaml 锁定，当前禁用且未安装，不能声称已调用。真实编码/模型/浏览器适配器未配置时返回 blocked。demo 模式仅代表受控流程演示。

本地工具采用完整 argv 白名单、固定目录与超时；不以 shell 执行任意字符串。ToolAdapter 是合作式权限边界，不是操作系统沙箱，不用于运行不可信命令。
