# DocLoop Agent 项目框架

根据 `.docloop/docs/source-design.md` 构建的 Python + LangGraph 编排骨架。包含需求、执行、可靠性三个控制中心，五个角色契约、Rules、Skills、Profile、审批基线、SQLite Checkpoint、证据与归档。

## 启动

Windows 双击根目录 **启动工作台.cmd**，浏览器会打开本地工作台。默认地址为 `http://127.0.0.1:8765`，默认数据目录为项目同级的 `agent-loop-data`（本机为 `D:\项目\agent-loop-data`）。再次双击会打开同一项目、同一数据目录的现有服务。双击 **停止工作台.cmd** 或在服务窗口按 Ctrl+C 停止；资料和审批保留，模型会话凭据清空。

当前机器已准备运行环境；新机器首次需要 uv、Git 和网络下载依赖。启动脚本优先使用已安装环境，只在缺少依赖时安装锁定版本。日常操作无需输入 PowerShell。

工作台采用“左侧任务区、右侧执行区”：左侧选择项目、搜索/选择任务、查看阶段，并在底部输入新需求；名称可选，点击↑提交后创建任务。右侧集中展示真实执行记录，可筛选类型、展开详情、切换需求规格进行编辑审批，并查看实际产物。

资料、历史运行、本地 Skills 与设置保留在左下辅助入口。仍支持 UTF-8 Markdown/TXT（单文件≤2MiB）、关键词检索、版本化来源、Spec Hash审批和 LangGraph 受控验证。任务沿用现有规格与运行数据，不需要数据库结构迁移；刷新保留项目和任务选择。手机端通过顶部“任务”按钮打开左侧抽屉。

右侧记录取自当前任务的真实审计、阶段JSONL及验证证据；默认范围为最近20次受控运行与最多100条相关审计。用户切换任务时会立即清空旧任务记录，在途响应不能抢回当前选择。资料同名换版保留旧引用；停用后立即退出新检索。

已配置明确的通用 Chat-Completions 地址时，也可在设置页填写模型名和 API Key，测试连接后选择真实模型生成。凭据仅保留服务进程内存，不写数据库或浏览器存储。未配置真实模型时不会自动伪装成真实调用。本轮没有真实接口，实际模型验收尚未执行。

**当前默认是明确标记的 SQLite 沙箱。** Oracle 关系存储入口和 SQL 已准备，真实数据库未连接。所有“运行沙箱验证”都只检查受控文件与流程，不代表生成的 Spec 已完成业务编码或业务验收。

原有命令行演示入口 **启动演示.cmd** 仍可使用。

选择正常或失败演示，阅读显示的 Spec 与 SHA256，输入 `APPROVE` 后才执行。其他输入保留 draft；每次演示生成独立 Change ID。正常演示会写实际沙箱文件、Git Commit、独立子进程检查日志和 Hash 归档。失败演示预期停在 blocked，属于门禁生效。

## 开发与命令

在项目目录使用以下可选命令：

```powershell
uv sync --frozen --python 3.12
uv run docloop doctor
uv run docloop workbench --open
uv run docloop skill superpowers:brainstorming
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
| `src/docloop/skill_runtime.py` | 项目唯一 Skill 解析入口，阶段路由、当前内容读取和 Agent 上下文构建 |
| `src/docloop/workbench.py` | 本机 HTTP API、静态工作台、会话令牌和启动入口 |
| `src/docloop/workbench_store.py` | 项目、资料版本、Spec/审批、运行及事件的关系存储 |
| `src/docloop/workbench_service.py` | 资料引用、需求生成及隔离运行的业务服务 |
| `src/docloop/model_gateway.py` | 可配置模型接口、有限重试和进程内凭据 |
| `src/docloop/workbench_static/` | 无 CDN 的 HTML/CSS/JS 工作台资源 |
| `migrations/oracle/` | Oracle 工作台关系表 SQL，需在专用 Schema 审阅后执行 |
| `.docloop/agents/` | 五个专业角色的源文档契约 |
| `.docloop/rules/` | 通用及条件启用的企业规则，唯一事实来源 |
| `.docloop/skills/` | 15个唯一 Skill；document-parser 在两类清单共享 |
| `.docloop/superpowers/` | 锁定版本的完整上游源码，含15个 Skills、配套脚本/资源/文档/插件文件与 MIT 许可证 |
| `.docloop/superpowers.lock.json` | 上游来源、Commit、231个文件的 Hash、大小和原始权限记录 |
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

`project.yaml` 记录 Superpowers 来源 Commit `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b`，完整上游文件位于 `.docloop/superpowers/`，没有嵌套 `.git`。保留目录结构、相对引用及 MIT LICENSE。`.docloop/superpowers.lock.json` 是导入时上游基准，不是覆盖本地文件的来源。`docloop doctor` 报告是否安装、是否仍与上游完全一致，以及修改/新增/缺失清单。

本地 Skill 读取已启用（`superpowers.enabled: true`），默认 `integrity_policy: editable`：直接编辑本地文件即可在下一次阶段调用时生效，无需复制到全局 Skill 目录或重写上游清单。若显式改为 strict，任何与基准不一致的文件会在 doctor 和实际加载入口被拒绝。项目根 AGENTS.md 也要求本项目开发任务读取这些本地入口。

| 修改目标 | 本地入口 |
| --- | --- |
| brainstorming | `.docloop/superpowers/skills/brainstorming/SKILL.md` |
| TDD、调试、验证、规划等工程方法 | `.docloop/superpowers/skills/<name>/SKILL.md` |
| DocLoop 专业 Skills | `.docloop/skills/<name>/SKILL.md` |
| Agent 角色 | `.docloop/agents/<role>.md` |
| Rules | `.docloop/rules/`，按 task_context 选择 |
| 阶段选哪些 Skills | `.docloop/project.yaml` → `skill_runtime` |

每个阶段从磁盘重新读取所选 Skill、角色、规则，将完整 Agent 输入保存到 `.docloop/changes/<change-id>/agent-inputs/`，并向 traces 写入 `skill.loaded` 路径与 Hash。旧快照不被新修改覆盖；当前阶段已生成的输入保持记录，后续调用读取新版本。本地缺失或格式不合法时明确报错，不回退到全局 Skill。

本地上下文与真实模型调用分别记录，`model_invoked: false` 表示该输入尚未调用模型；真实生成成功时另记模型响应与用量。工作台已使用统一 messages 入口，但不自动执行业务开发或上游脚本。doctor 只检查配置与来源，不宣称执行过模型。

已实现：本地框架、Web 工作台、文本资料库、项目隔离、资料版本及来源、关系存储、可编辑 Spec 与原字节审批、可配置需求模型网关、真实 LangGraph 受控验证、启动恢复和测试。模型网关已通过 HTTP fixture 测试；Oracle 仅完成接口与方言结构检查，不能据此宣称真实模型/数据库验收通过。

尚未实现/验收：真实模型驱动业务编码、真实工作树调度、Oracle LangGraph CheckpointSaver、向量检索、MCP 浏览器适配、DOCX/PDF/OCR/Excel 解析、生产部署与多实例协调。工作台中启用 Oracle 关系存储时，受控演示的图 Checkpoint 仍位于本地隔离 SQLite。

## 沙箱与高级配置

资料原件存于数据目录 `objects/<Hash前缀>/<SHA256>`；SQLite 关系数据在 `workbench.sqlite`；模型输入快照在 `inputs/`；受控运行及证据在 `runs/<run-id>/`。备份需包含完整数据目录，仅备份 Git 不包含资料与审批。测试始终用系统临时目录，浏览器验收证据可另行导出。

Oracle 模式使用 `DOCLOOP_ORACLE_USER`、`DOCLOOP_ORACLE_PASSWORD`、`DOCLOOP_ORACLE_DSN` 环境变量；只在本机配置凭据，不提交 Git。先由数据库管理员审阅并执行 `migrations/oracle/001_workbench.sql`，再以 `--storage oracle` 启动。无可用配置或表结构时明确失败，不回退到 SQLite。`--init-db` 仅为显式的初始建表操作，不代表可自动迁移已有数据库。

可选高级命令：

```powershell
uv run python -m docloop.workbench --root . --data-root D:\项目\agent-loop-data --port 8765 --open
uv run python -m docloop.workbench --root . --storage oracle --port 8765 --open
uv run python -m unittest discover -s tests -v
uv run python -m unittest discover -s tests/acceptance -v
```

浏览器验收默认使用已安装 Microsoft Edge，所有业务数据使用系统临时目录；`DOCLOOP_BROWSER_CHANNEL` 可指定其他已安装的 Chromium 通道，`DOCLOOP_BROWSER_EVIDENCE` 可指定截图与日志输出目录。不会因接口返回200而认定真实模型或 Oracle 已通过验收。

上游接口使用方式核对自 [LangGraph interrupt 文档](https://reference.langchain.com/python/langgraph/types/interrupt) 与 [StateGraph compile 文档](https://reference.langchain.com/python/langgraph/graph/state/StateGraph/compile)。
