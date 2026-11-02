# DocLoop Agent 项目框架

根据 `.docloop/docs/source-design.md` 构建的 Python + LangGraph 编排骨架。包含需求、执行、可靠性三个控制中心，五个角色契约、Rules、Skills、Profile、审批基线、SQLite Checkpoint、证据与归档。

## 启动

Windows 双击根目录 **启动演示.cmd**。当前机器已准备 Python 环境；首次在新机器运行需要 uv、Git 和网络下载依赖。脚本优先使用现有 `.venv`，不会自动更新依赖。

选择正常或失败演示，阅读显示的 Spec 与 SHA256，输入 `APPROVE` 后才执行。其他输入保留 draft；每次演示生成独立 Change ID。正常演示会写实际沙箱文件、Git Commit、独立子进程检查日志和 Hash 归档。失败演示预期停在 blocked，属于门禁生效。

## 开发与命令

在项目目录使用以下可选命令：

```powershell
uv sync --frozen --python 3.12
uv run docloop doctor
uv run python -m unittest discover -s tests -v
uv build
uv run docloop demo --change-id demo-001
uv run docloop status demo-001
uv run docloop approve demo-001 --hash <上一步显示的SHA256> --by <审批人>
uv run docloop resume demo-001
uv run docloop recover demo-001
```

`resume` 用于已审批且因进程中断而留有下一节点的 Checkpoint。`recover` 仅对 blocked 运行显式重试原失败节点，保留预算和 Spec 基线；预算耗尽需要新的经审阅 Change。审批等待不自动计入开始执行后的时间预算。修复业务文件导致 Commit 变化时原证据身份失效，应使用新 Change，不复用旧结果。

读取自有 Markdown Spec：`uv run docloop start change-001 --spec D:\资料\spec.md`。Spec 需含 `AC-001` 等验收 ID。默认 `real` 模式在审批后因模型/工具/上游适配器未配置而明确 blocked。只有显式 `--mode demo` 才走受控示例，不会实现自有 Spec 的业务需求。

退出码：0 表示命令成功或等待审批；2 表示门禁、环境、失败验证或阻塞。状态 JSON 的 mode 必须与 status 一起解读：`accepted + demo` 只是演示流程通过。

## 目录与扩展点

| 路径 | 职责 |
| --- | --- |
| `src/docloop/governance.py` | 来源索引、Hash 审批、不可覆盖基线 |
| `src/docloop/workflow.py` | LangGraph 状态图、审批中断、执行/验证/审查、恢复 |
| `src/docloop/reliability.py` | 独立预算、瞬时错误重试、无进展、修复上限、熔断 |
| `src/docloop/adapters.py` | 完整 argv/工作目录白名单、超时、确定性演示角色 |
| `src/docloop/evidence.py` | AC 覆盖门禁、角色/Commit 检查、Hash 归档 |
| `.docloop/agents/` | 五个专业角色的源文档契约 |
| `.docloop/rules/` | 通用及条件启用的企业规则，唯一事实来源 |
| `.docloop/skills/` | 15个唯一 Skill；document-parser 在两类清单共享 |
| `.docloop/profiles/` | 平台默认 Profile、可选 Vue/Java 企业 Profile |
| `.docloop/templates/` | Change 文档和 task_context 模板 |
| `.docloop/changes/` | 活动变更、baseline、计划、实际证据 |
| `.docloop/checkpoints/` | SQLite 图状态及持久化预算 |
| `.docloop/sessions/` | 演示隔离 Git 沙箱 |
| `.docloop/traces/`、`recovery/` | 追踪及阻塞现场 |
| `文档/变更记录/` | 成功归档及文件 SHA256 清单 |

默认 Profile 不启用 API/UI 企业规则。`project.yaml` 中的 limits 由运行时实际读取；LLM、Token、模型轮次和并发计量接口供未来真实适配器调用，不表示当前已有真实模型活动。当前执行器同步串行，实际并发为1。瞬时错误重试和修复检测由可靠性模块提供，演示验证失败直接阻塞，不自动修改业务文件。

接入真实模型时应实现四个专业角色的隔离执行会话，消费 task_context，计量 LLM/Token/轮次，检查目录和工具权限，并由独立 verifier 生成证据。Skill 文件属于能力契约，本身不会执行代码。ToolAdapter 是合作式边界，不是 OS 沙箱；完整 argv 白名单应由可信管理员配置。

## Superpowers 与交付边界

`project.yaml` 锁定了查询所得的 Superpowers Commit。默认 disabled，尚未安装或加载；未复制上游 Skills。真实适配器应在调用前检查安装目录、Git HEAD、技能存在性及兼容性，不能仅凭锁文件认为已接入。

已实现：本地框架、Markdown 输入、真实 LangGraph + SQLite、审批及证据门禁、受控离线演示与测试。未接入：真实 LLM 自动开发、真实工作树调度、Web UI、MCP 浏览器、DOCX/PDF/OCR/Excel 解析、生产部署。各项限制不影响框架离线演示，但不能据此宣称完整生产平台或业务验收通过。

上游接口使用方式核对自 [LangGraph interrupt 文档](https://reference.langchain.com/python/langgraph/types/interrupt) 与 [StateGraph compile 文档](https://reference.langchain.com/python/langgraph/graph/state/StateGraph/compile)。
