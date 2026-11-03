# DocLoop Agent 项目框架

根据 `.docloop/docs/source-design.md` 构建的 Python + LangGraph 编排骨架。包含需求、执行、可靠性三个控制中心，五个角色契约、Rules、Skills、Profile、审批基线、SQLite Checkpoint、证据与归档。

## 启动

Windows 双击根目录 **启动工作台.cmd**，浏览器会打开本地工作台。默认地址为 `http://127.0.0.1:8765`，默认数据目录为项目同级的 `agent-loop-data`（本机为 `D:\项目\agent-loop-data`）。每次启动会先关闭同一项目、同一数据目录的旧工作台，等待端口和数据锁释放后启动最新代码；不会关闭其他项目的服务。资料、审批和模型配置均保留。需要停止时，在服务窗口按 Ctrl+C。

当前机器已准备运行环境；新机器首次需要 uv、Git 和网络下载依赖。启动脚本优先使用已安装环境，只在缺少依赖时安装锁定版本。日常操作无需输入 PowerShell。

工作台采用“左侧任务区、右侧执行区”：左侧选择项目、搜索/选择任务、查看阶段，并直接描述新需求；任务名自动取需求首行，点击↑创建任务。模型选择紧凑放在输入框底部，与附件、发送同一行，不再单占一行或另放模式下拉。演示规格在设置页明确勾选，未配置模型时不会自动转演示。所有下拉在支持的浏览器中使用统一的原生可定制菜单，保留键盘选择及不支持时的原生回退。右侧展示真实执行记录，可筛选、展开、切换规格编辑审批并查看产物。

资料、历史运行、本地 Skills 与设置使用左下入口打开弹层，关闭后保留右侧任务及未保存编辑。Skills 展示中文名称与功能，隐藏内部 ID、路径与 Hash；内部来源仍保留审计。支持 UTF-8 Markdown/TXT（单文件≤2MiB）、关键词检索、版本化来源、Spec Hash审批和 LangGraph 受控验证。SQLite 自动补建请求去重表 dl_request，旧资料与审批不改写；Oracle 需先部署新增表，真实环境仍待验收。手机端通过顶部“任务”按钮打开左侧抽屉。

右侧记录取自当前任务的真实审计、阶段JSONL及验证证据；默认范围为最近20次受控运行与最多100条相关审计。用户切换任务时会立即清空旧任务记录，在途响应不能抢回当前选择。资料同名换版保留旧引用；停用后立即退出新检索。

仅支持 **GPT 6.1 Sol** 和 **DeepSeek V4.1 Flash**。GPT通过本机Codex CLI复用已有登录，在只读临时工作区生成Spec，不复制登录令牌；DeepSeek通过Chat Completions调用官方`deepseek-flash`别名。模型选择和独立配置持久保存到数据目录`.settings/model-settings.json`；DeepSeek密钥用当前Windows用户DPAPI加密，API不回显密钥，留空沿用已保存值。切换和重启不丢配置；新机器仍需自己的Codex登录或DeepSeek Key。已配置模型默认用于规格生成，也可明确选择演示。GPT真实连通性及Spec生成已在隔离测试中验证；DeepSeek仅完成fixture验证，尚无真实Key验收。

设置页可为当前项目登记干净的本地Git仓库，并为已批准的当前任务准备独立Worktree。准备绑定精确Spec Hash与Commit、拒绝脏源仓库，禁用Git hook/filter/fsmonitor/外部diff，不覆盖用户改动。当前只完成执行准备；Docker不可用或真实编码门禁未启用时明确阻止生成代码执行。真实业务编码/修复/验收仍待后续闭环；只读Codex调用已支持超时、取消和Windows Job Object进程树清理。

右侧“启动规划与准备”创建独立 runtime Run，后台 LangGraph 核对审批、生成 TASK/TC 计划并准备 Worktree；新需求分析也在后台运行，刷新只读取原任务。右侧支持暂停、继续/恢复与取消；暂停在安全步骤落盘后生效，服务退出或强制终止后标记可恢复，恢复沿用同一 Run/检查点/冻结输入，完整保存的计划不重复调用模型。取消是终态，优先于关闭或恢复。首版并发上限为1；仓库绑定或执行版本变化时拒绝旧运行恢复。已开始的Git步骤可能留下工作区，不宣称回滚；未返回的模型调用可能需要重试。真实编码、业务测试、修复及人工最终验收仍未启用。

点击右侧“补充资料”将 Markdown/TXT 关联当前任务：先保存并暂停原运行，再分析新增、修改、冲突与影响，创建独立新草稿。在“资料变更”查看差异报告，打开新草稿审阅审批后显式启动新规划。原审批不覆盖，旧运行在新审批后标为已替代；仅存入资料库时不暂停任务。分析输入（原需求+补充正文+报告）当前上限12000字符，超限明确失败且保留已上传版本。连续批次需先处理或放弃前一批，避免新旧输入混用。重启后可重试差异分析并对账。

“查看产物 → Git 版本与上传”可冻结当前正式文档、生成 SHA-256 清单并本地提交，再上传/重试同一版本。版本位于登记仓库的专用 `docloop-deliveries/…` 分支与 `docloop/…` 标签，源分支工作区不变；各交付分支内有 `文档/产物版本索引.md`。界面区分待上传、上传失败、远端分支与标签已确认。发布冻结仓库与远端指纹，变更目标后不自动迁移旧发布；不收录数据库、检查点、模型输入、凭据、原始资料或临时文件。版本快照不代表业务功能或最终人工验收通过。框架自身交付索引见 [产物版本索引](文档/产物版本索引.md)。

**当前默认是明确标记的 SQLite 沙箱。** Oracle 关系存储入口和 SQL 已准备，真实数据库未连接。所有“运行沙箱验证”都只检查受控文件与流程，不代表生成的 Spec 已完成业务编码或业务验收。

根目录仅保留 **启动工作台.cmd** 启动入口；受控演示从工作台内运行。

“查看产物”打开文档目录，默认显示交付总览。可以逐份查看当前规格及该任务全部历史运行现存的计划、清单、决策、审批基线、证据、日志、恢复和归档材料，下载当前文档或全部Markdown汇编。不会读取模型输入快照、密钥、数据库或Checkpoint；未生成的业务材料不会补写成已完成。单份文本上限2 MiB，全部汇编上限8 MiB，超限会提示本地处理。

技术方案逐章对照、22项AT和下一步优先级见 [.docloop/docs/technical-design-comparison.md](.docloop/docs/technical-design-comparison.md)。

选择成功或失败场景，先审阅Spec并通过按钮批准当前SHA256，再运行受控演示。未批准时不能运行；每次运行生成独立ID。成功路径写实际沙箱文件、Git Commit、独立子进程检查日志和Hash归档；失败路径预期停在blocked，属于门禁生效。

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
| `src/docloop/model_gateway.py` | 双模型路由、有限重试、服务关闭取消 |
| `src/docloop/model_settings.py` | 双档案持久化与Windows用户DPAPI密钥保护 |
| `src/docloop/codex_runtime.py` | 单一Codex只读Runtime、输出预算及进程树清理 |
| `src/docloop/worktree_runtime.py` | 显式登记仓库的幂等Worktree准备与快照 |
| `src/docloop/execution_preparation.py` | 项目仓库绑定、审批门禁、准备API及执行阻断 |
| `src/docloop/managed_runs.py` | 后台LangGraph准备Run、计划映射校验、取消和检查点 |
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
