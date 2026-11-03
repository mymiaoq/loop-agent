# DocLoop Agent V2.0 现状审计（Phase 0）

- 审计日期：2026-11-03
- 代码基线：`7572c6c`（工作树干净；`b22269a` 的下一提交，仅含工作台/模型错误提示与两个测试）
- 方案来源：用户提供的 V2.0 技术升级方案；PPT 原文从 `DocLoop Agent 项目方案_副本.pptx` 提取，共 15 页
- 审计性质：只读。本文不是已批准 Spec，不创建 baseline，不进入实现
- 结论一句话：原始架构与 PPT 的核心设计已基本落地；真正缺失的是 Worker Runtime、Task DAG、Codebase Context/Graph、三层测试追溯和最终验收，且当前代码已有两套编排图、两套审批真源和三套状态词汇，V2 必须先收口这些冲突再做增量。

## 一、PPT 15 页与当前实现对照

| PPT 页 | PPT 主张 | 当前实现 | 判断 |
|---|---|---|---|
| 3 | 三个控制中心、Superpowers、Rules/Skills、五角色边界 | `governance.py`、`workflow.py`、`reliability.py` 三中心；`.docloop/agents` 五角色；`.docloop/project.yaml` 阶段 Skill 路由 | 已具备，但角色是文档/配置字符串，没有真实 Agent Runtime |
| 4 | orchestrator + 四个专业子 Agent；implement 不能自称 verified | `contracts.py` 五角色与转移矩阵；`workflow.py` 用 DemoAdapter 分离 implement/verify/review | 契约/职责分离具备；实际是确定性演示适配器，不是真实子 Agent |
| 5 | 12 步工作流；审批→开发；Verify + Review 双签后归档 | LangGraph 6 节点 `approval → plan → implement → verify → review → archive`；`review` 不进入状态，`archive` 直接置 accepted | 核心门禁在；步骤/状态被压缩，review 不是独立状态，用户最终验收缺失 |
| 7 | draft→ready→in_progress→implemented→verified→accepted；失败回退；blocked/recovery | `contracts.py` 转移表 + `RunState`；失败直接 blocked；`repair()` 在 src 中从未调用；accepted 由 archive 自动产生 | 主链具备；失败回退/修复环未闭环；状态词汇与 DB/evidence 不一致 |
| 8 | `.docloop` 目录、checklist.md、review.md、evidence.yaml、归档 | 现有 `checkList.md`、`review.yaml`、`manifest.yaml`；`文档/变更记录/` 只有 `.gitkeep` | 目录结构接近；命名和归档实现与 PPT 不一致 |
| 9 | 本地工作台（127.0.0.1:3000，聊天式）、VS Code 双入口 | 本地工作台 8765，任务需求输入、运行记录、产物文档中心、模型/运行准备；无 VS Code 插件 | 工作台具备且比 PPT 更细；聊天式交互不是当前定位；VS Code 为空白 |
| 10 | 9 平台 + 7 领域 Skill（document-parser 复用） | 15 个唯一 Skill；document-parser 单份；9 平台作用域 + 6 企业领域 + 1 共享；7 个 Skill 未被阶段路由 | 唯一性已解决；分类应写为 9+6+1，不是 9+7；路由不完整 |
| 12 | Vue 3/Element Plus、Java 8/MyBatis Plus、Playwright MCP、真实编码 | 双模型/Codex 只读；Vue/Java 仅企业 Profile 与规则文本；浏览器验收为直接 Playwright；真实业务编码门禁 blocked | 技术栈规则具备；真实编码、MCP、企业技术栈执行均未落地 |
| 12/13 | 47 用例、82% 覆盖率、test-report、changelog | 根测试 109+1；无 coverage 配置/报告；无 changelog；文档历史计数 28/61/63 不一致 | PPT 数字是演示案例，不能成为全局门槛；仓库当前没有覆盖率事实 |
| 15 | 三个用户决策点；6 步演示 | 审批有；需求输入有；最终验收无独立状态/接口；运行准备可取消 | 两个决策点具备，最终验收缺失 |

## 二、当前架构事实

### 2.1 编排与状态

- `src/docloop/workflow.py`：LangGraph `StateGraph(RunState)`，6 个节点，`SqliteSaver` 每 change 一个 checkpoint。
- `RunState` 只有 change/status/mode/scenario/acceptance_ids/history/commit/error/evidence/review/archive/task_context，没有 task/worker/lease/timeline/operation 字段。
- `contracts.py`：`draft → ready → in_progress → implemented → verified → accepted`；`review` 不产生状态；`accepted` 由 `_archive` 自动设置。
- `managed_runs.py`：另有一套 `StateGraph(State)`（approval → plan → prepare）与独立 `checkpoint.sqlite`，按 run 起线程，服务级一个全局锁、一个活动 Run。它不是第二套业务状态机，但已经是第二套编译图和执行调度路径。
- `workbench_store.py`：只有 project/document/spec/run/event 五张表；“任务”是 Spec + 最近 Run 的派生视图，没有 Task/Worker/Timeline/Evidence 表。

### 2.2 Worker/执行基础

- `managed_runs.py`：开始、状态、取消、等待、服务关闭取消；启动时把遗留 `in_progress` runtime run 标 blocked；没有 task claim、worker_id、lease、heartbeat、任务队列、worker 池。
- `execution_preparation.py`：登记干净 Git 仓库，绑定批准 Spec Hash 和 baseline Commit，幂等准备 Worktree，快照 status/diff；始终返回 `execution_gate: blocked`，不执行生成代码。
- `worktree_runtime.py`：安全路径、注册仓库、全 Commit、分支 `docloop/<run>`、manifest 身份、幂等 prepare、snapshot(diff)；未接入 `workflow.py`，没有按 Task 的 Worktree，也没有合并/集成。
- 并发：`project.yaml limits.concurrency=1` 从未被预算消费；实际并发上限是 `ManagedRuns` 的硬编码单活动 Run + 服务级锁。
- 取消：runtime 计划/模型等待可取消；演示 Run 同步执行不可取消；Git 子进程可能在安全边界后留下工作区。

### 2.3 需求治理与证据

- `governance.py`：Spec 原文 + `baseline/spec.md` + `baseline/approval.json`（sha256/approver/approved_at/version=1），不可覆盖；没有 `baseline.json`，没有 rules/skills 版本、base commit、source bundle hash。
- `workbench_store.py` 另存 `approved_hash/approval_blob/approved_by`；文件基线与 DB 是两套真源。
- `evidence.py`：校验 producer=`verify-agent`、Commit SHA、AC 覆盖、test_case_id、evidence 文件存在；`not_run`/failed/blocked 一律拒绝，不能作为通过记录。
- 实际 `changes/20261102-framework/evidence.yaml` 的 producer 是 `codex-main`，按当前 `validate_evidence` 会被自己的门禁拒绝；模板、规则文档、代码、真实文件是四套不同 schema。
- 归档：`archive_change` 要求 `spec.md/decisions.md/tasks.md/checkList.md/evidence.yaml/review.yaml`，写 `manifest.yaml`，拒绝覆盖；`文档/变更记录/` 实际为空。

### 2.4 Skills / Rules

- 15 个唯一 Skill；`document-parser` 只有一份，V2 所述重复定义在当前仓库已经不存在。
- 实际作用域：9 个平台作用域（含 document-parser）+ 6 个企业领域 + 1 个共享；不是 9+7 的算术。
- 阶段路由只覆盖 8 个 docloop Skill + Superpowers；document-parser、component-generator、api-contract、backend-code-generator、frontend-design、frontend-quality-check、security-check 共 7 个没有可执行路由；`project.yaml routing:` 的 ui/api/backend/security 基本是死配置。
- Skill 元数据只有 frontmatter `name/description` + 9 个中文 section；没有 version/timeout/risk_level/input_schema/output_schema/allowed_tools 的机器可读注册。
- 四份 Rules 为 code/api/ui/verification；`enterprise/code-standard.md` 是第五个文件；企业 Profile 条件只靠 `project.yaml profile:`，src 中没有 enterprise 运行时门禁；Rules 只注入 Prompt，没有内容检查器。
- 项目自身有“9 平台 + 7 领域”的文档表述与 15 个唯一文件的现实差异，需在 V2 文档中统一口径。

### 2.5 工作台与 UI

- 已有：任务/项目、Spec 编辑审批、执行记录（trace/evidence）、产物文档中心（当前 Spec + 全部历史运行正式材料）、模型双档案、执行工作区准备/取消、移动端抽屉、390/1366/1920 布局。
- 缺失：Worker 状态、Task DAG、按 Task 的时间线、Git diff 查看器、三层测试证据视图、pause/resume、最终用户验收、VS Code 联动。
- 运行控制目前位于设置页；`#start-runtime`/`#cancel-runtime`/`#register-repository` 被浏览器验收依赖，移动时需保留。
- 前端固定 4 阶段条 + 记录流，不是 Task 时间线；trace 记录多数没有 `created_at`；轮询 800ms，无 SSE/WS。
- 安全：只绑定 loopback、CSRF token、Origin/CSP、路径校验；任何本机进程可 GET `/api/state` 读取 csrf_token，没有额外认证。

### 2.6 测试与文档

- 根测试：18 个 `tests/test_*.py` + `tests/acceptance/test_workbench_browser.py`；约 109+1 个测试函数；没有 coverage 配置/报告；`tests/acceptance` 没有 `__init__.py`，`discover -s tests` 不会自动发现。
- 历史文档计数不一致：28/61/63/47+82%；47 用例/82% 只是 PPT/第三方材料中的演示声明，不能作为项目固定门槛。
- 三层测试、REQ→AC→TASK→TC→TEST RUN→evidence→Commit 的完整链没有代码层建模；`managed_runs.validate_plan` 只保证计划级 AC↔TASK↔TC 覆盖，checkList.md 从未被解析。
- 现有 `technical-design-comparison.md` 审的是另一份 26 章技术方案，不是本次 15 页 PPT；其中“无 VSCode/DAG/Worker/真实编码”的结论仍然有效，但测试计数需要以本次审计为准。

## 三、V2 能力差距矩阵

| V2 能力 | 现状 | 关键差距 |
|---|---|---|
| LangGraph 唯一编排 | 部分 | 主图 + `managed_runs` 第二编译图/第二 checkpoint/线程调度；需收敛为子图/执行基础设施，不能变成第二业务状态机 |
| Worker Runtime | 部分 | 有准备 Run/取消/Worktree/快照；无 worker_id、claim、lease、heartbeat、任务队列、按 Task Worktree、Commit 关联、worker 恢复 |
| 幂等/operation_id | 部分 | 有幂等 Worktree manifest、确定性 prep run_id、归档同 Hash 复用、审批 replay；无 operation 台账、崩溃后外部副作用对账 |
| Task DAG | 缺失 | 计划只有扁平 tasks/test_cases；无 depends_on、read/write scope、环检测、冲突检测、合并 |
| Codebase Context | 缺失 | 无项目扫描、索引、增量更新、按任务检索、Tree-sitter/LSP |
| Codebase Graph | 缺失 | 无节点/边、调用链、API↔实现、测试关联、影响分析、置信度 |
| 三层测试/追溯 | 缺失/部分 | 无 layer/exit_code/log hash/duration/screenshot；无 TEST RUN；evidence 只校验 AC/Commit；checkList 未解析 |
| Verify/Review 独立 | 名义 | review 硬编码 producer/status=passed，不改变状态；真实证据会被自身门禁拒绝 |
| 最终用户验收 | 缺失 | accepted 由 archive 自动置；没有验收人/结论/证据接口/UI |
| 可靠性闭环 | 部分 | 重试/预算/无进展原语有；`repair()` 在 src 未调用；无编译/测试/权限错误分类；blocked 终态 |
| 双审批真源 | 冲突 | 文件 `baseline/approval.json` vs DB `approved_hash/approval_blob`；无权威定义 |
| baseline.json | 缺失 | 只有 approval.json；缺 source bundle/rules/skills/base commit 字段 |
| checklist.md | 冲突 | 代码/模板/真实变更用 `checkList.md`；PPT/方案要求 `checklist.md`；大小写不敏感 FS 风险 |
| .docloop Git 策略 | 部分 | 配置/规则/Skill 已跟踪；`changes/*/agent-inputs` 未忽略；无 indexes 忽略；日志被跟踪 |
| 工作台 Worker/DAG/Diff | 缺失/部分 | 有准备/取消/产物/记录；无 worker、DAG、diff 查看、pause/resume、验收 |
| VS Code | 缺失 | 仓库无插件、无共享 project/change/branch/worktree 通道 |
| 模型/安全 | 部分 | 双模型/GPT Codex 只读/DeepSeek DPAPI；单活动模型；无 per-agent 模型；无代码外发防护/容器隔离 |
| 真实编码执行 | 缺失 | 只读 Codex/规划/准备；真实编码门禁 blocked；Docker 不可用 |
| 测试门槛 | 冲突 | 47/82 与仓库 109+/无 coverage 不一致；无分层测试脚手架 |

## 四、必须在实现前收敛的冲突与风险

1. **两套编排图**：`workflow.py` 与 `managed_runs.py` 各自 compile + checkpoint。V2 要求“不新增第二套调度中心”，但当前已经有一套准备调度；必须先定义它属于执行中心子图/执行基础设施，并保留一个业务状态权威。
2. **两套审批真源**：文件 baseline 与 DB approval blob。新增 `baseline.json` 前必须决定权威、投影和迁移；否则会出现第三套。
3. **三套状态词汇**：contracts（draft/ready/.../accepted）、DB spec（draft/approved/active）、run（in_progress/blocked/cancelled/planned）、evidence（passed/failed/blocked/not_run）。需分层映射，不能机械替换。
4. **Review 名存实亡**：review 不产生状态、结果硬编码 passed；真实 review.yaml 与代码 schema 不同；accepted 自动产生，违反“用户最终验收”。
5. **Commit 与 Verify 顺序冲突**：当前 implement 先 Commit，verify 绑定 HEAD+干净树；V2 要求 TEST RUN→evidence→Commit。需要候选 Commit/最终 Commit 双阶段或等价方案，并同步修改 `adapters.assert_commit` 与测试。
6. **Evidence 自拒**：现有真实 evidence producer=`codex-main`，代码要求 `verify-agent`；模板/规则/代码/真实文件四套 schema；`not_run` 无法表达。V2 统一 schema 必须兼容历史，不能把历史合法材料判为伪造。
7. **归档不可重试**：`archive_change` 拒绝覆盖；修复/重跑产生新字节会撞“Existing archive differs”。需要版本化归档或显式新 change。
8. **Worktree 根目录/用户目录守卫**：默认数据根在用户 home 下时，`WorktreeRuntime` 拒绝“inside user home”；测试用 `/tmp` 绕过。桌面默认布局会阻挡 V2 每 Task Worktree。
9. **并发硬编码**：`concurrency` 配置未消费；单活动 Run + 全局锁是现有测试契约。先单 Worker 稳定，再改契约。
10. **Schema/Oracle**：只有 5 张表；新增 Task/Worker/Timeline/Evidence 需同时更新 `create_all`、Oracle DDL 与迁移；Oracle 从未真实验收。
11. **checkList 大小写重命名**：仅 `evidence.py` 硬失败；macOS/Windows 大小写不敏感 + Git 可能不记录；零测试覆盖；历史运行/归档都会受影响。
12. **7 个 Skill 不可达**：document-parser/6 企业 Skill 仅通过 REQUIRED_SKILLS 校验，不在阶段路由；企业门禁只在文字里。
13. **测试事实**：109+1 个函数、无 coverage、acceptance 不被 discover；PPT 47/82 不是仓库门槛。不得用固定数字绑定所有项目。
14. **VS Code 是空白**：PPT 和 V2 都要求“保留”，但仓库没有插件；这是新建，不是保留，必须先决定范围。
15. **真实编码 Runtime 未选型**：Codex 当前只读；企业栈执行、容器、写权限、回滚、密钥边界都未定义。V2 Worker 不能在没有这个决策的情况下直接写业务代码。
16. **旧克隆目录 `loop-agent/`**：独立 `.git`，HEAD 34e4d43，含重复 Skill；仅被本地 `.git/info/exclude` 排除，未进 `.gitignore`（未提交的本地保护），新检出可能误提交。审计建议清理或明确忽略。

## 五、建议保留 / 不做 / 待确认

### 保留

- LangGraph、五角色、三中心、Superpowers、四 Rules、15 唯一 Skill、SHA256 审批、Git Worktree、Verify/Review 分工、SQLite/可选 Oracle、本地工作台、产物文档中心、双模型、PowerShell 启动入口。
- 所有现有 API/ID/验收脚本契约；新增能力只做增量字段/路由，不重写。

### 不做（本轮 V2 范围外或需单独立项）

- 不新增第二个 orchestrator / 第二套业务状态机。
- 不引入 Neo4j（先 SQLite/本地索引）；不做向量检索/语义压缩。
- 不把 47/82 覆盖率设为全项目硬门槛。
- 不在 Runtime 未选型/未授权前真正写业务代码或推生产。
- 不宣称 Oracle、Docker、真实企业栈、VS Code 已验收。
- 不整体忽略 `.docloop`，也不改 `.gitattributes` 的 eol 导致审批字节漂移。

### 待用户确认的决策

- 真实编码 Runtime：Codex 写模式、可信 CLI、容器或其他？安全门禁/回滚/网络边界？
- VS Code：新建插件（greenfield）还是本轮明确不做？
- 审批权威：文件 `baseline.json` 为权威、DB 投影，还是 DB 为权威？迁移策略？
- Commit/Verify 顺序：两阶段 Commit 还是候选 Commit + 最终 Tag？
- 用户最终验收：真实 Run 必须显式验收；演示是否自动 accepted？
- 每 Agent 模型：先单一活动模型，还是直接 per-role？
- 旧 `checkList.md`：canonical lowercase + 兼容读取，是否接受历史归档不改名？
- `.docloop` 忽略：`agent-inputs/`、`logs/`、`indexes/` 的边界。
- Worktree 根：允许显式配置到 home 外；桌面默认数据根如何迁移？
- 是否删除/保留旧克隆 `loop-agent/`。

## 六、Phase 0 结论

当前项目是“审批 + 受控编排 + 工作台 + 证据/产物”的可信框架，不是 V2 所描述的自治工程平台。V2 的正确做法不是重写，而是：

1. 先统一状态、审批、证据、命名和幂等契约（Phase 1）。
2. 把现有准备 Run 收敛为 Worker Runtime 的单 Worker 稳定执行（Phase 2）。
3. 先 Codebase Context，再 Codebase Graph（Phase 3A/3B）。
4. 三层测试/追溯与独立 Review（Phase 4）。
5. 工作台 Worker/DAG/Diff/验收（Phase 5）。
6. 最后才开并发（Phase 6）。

在上述冲突和用户决策没有确认前，不进入实现。
