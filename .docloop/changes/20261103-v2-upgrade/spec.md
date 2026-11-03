# DocLoop Agent V2.0 增量升级需求规格

- 版本：V2.0-draft
- 状态：**draft，等待用户确认；未审批，不是基线**
- 基线：当前代码 `7572c6c`；PPT 15 页 + 用户 V2.0 方案文本 + `upgrade-audit.md`
- 变更 ID：`20261103-v2-upgrade`
- 原则：保留现有架构，增强执行能力，不推倒重构；Spec 未确认前不写实现代码

## 1. 目标

在现有 DocLoop Agent 上增量升级为一个具备以下能力的工程化自治 Agent：

1. 由 LangGraph 统一决定“下一步做什么、谁做、何时暂停/恢复”；不新增第二套全局调度。
2. 通过 Worker Runtime 可靠执行任务：任务领取、租约/心跳、隔离 Worktree、超时/取消、崩溃恢复、Commit 关联。
3. 通过 Task DAG 管理依赖、文件冲突和安全并发；默认并发 1，稳定后再开 2–3。
4. 通过 Codebase Context 和 Codebase Graph 让现有 Agent 真正理解代码库、调用关系和修改影响。
5. 建立三层测试和 REQ→AC→TASK→TC→TEST RUN→evidence→Commit 追溯。
6. 强化 Verify/Review 分离、用户最终验收、证据和归档一致性。
7. 工作台展示 Worker、DAG、时间线、Diff、证据，支持暂停/恢复/取消和最终验收。
8. 保留三个用户决策点：需求输入/澄清、Spec 审批、最终验收。

## 2. 非目标

- 不新增第六个 Agent 角色，不重写 LangGraph，不建立第二套业务 Task 状态机。
- 不在本阶段引入 Neo4j；Codebase Graph 先用 SQLite/本地索引。
- 不把固定“47 测试/82% 覆盖率”设为所有项目门槛；门槛按项目 Profile 配置。
- 不在 Worker 执行安全边界和 Runtime 选型未确认前真正写业务代码、自动合并或推送生产。
- 不声称 Oracle、Docker、真实企业栈、VS Code 已验收；未运行项必须 `not_run`。
- 不修改已批准 Spec 字节，不静默覆盖历史归档，不删除既有运行材料。
- 不整体忽略 `.docloop/`；不改变 `.gitattributes` 的 eol 策略导致基线字节漂移。

## 3. 强制保留约束

1. LangGraph 是唯一核心编排引擎。
2. 一个 orchestrator + 四个专业子 Agent（spec/implement/verify/review）。
3. 需求治理、执行编排、可靠性恢复三个控制中心。
4. Superpowers 负责 Brainstorming/Planning/TDD/Debug/Review 方法论。
5. 四份 Rules（code/api/ui/verification）按 Profile 条件启用。
6. 15 个唯一 Skill（9 平台作用域 + 6 企业领域 + document-parser 共享）；不得重新引入重复 document-parser。
7. Spec 审批后以 SHA256 锁定原字节；修改必须新版本/新 Change。
8. Git Worktree 隔离；Worker 不得直接改主分支。
9. Implement、Verify、Review 职责分离；Agent 不得自己宣布最终交付。
10. `.docloop/` 为活动变更/运行资料空间；`文档/变更记录/` 为正式归档。
11. 本地 Web 工作台 + VS Code 双入口（VS Code 是否本轮新建待确认）。
12. 模型可切换；代码/密钥不出内网约束不变。
13. 保留现有状态机、重试、无进展、修复轮次和预算语义，除非本 Spec 明确扩展。
14. 保留现有 API/ID/浏览器验收选择器；新增字段/路由向后兼容。

## 4. 需求与验收标准

| 需求 | 验收标准 |
|---|---|
| **REQ-201 Worker Runtime**：在 LangGraph 执行控制中心内提供可靠任务执行基础设施，不新增业务调度器。 | AC-201 每个 Worker 有 worker_id/task_id/change_id/run_id/worktree/branch/heartbeat/lease/started/finished/result，可审计。AC-202 任务必须显式领取；租约过期后由恢复流程核验现场，不重复执行已完成的外部副作用。AC-203 每个写任务独立 Worktree，同一 Worktree 同时只有一个写 Worker；不得写主分支；任务完成关联 Commit SHA。AC-204 超时、取消、崩溃、服务重启均可安全停止/恢复；保留 checkpoint、Worktree 和未提交现场；取消不得伪装成完成。 |
| **REQ-202 Task DAG**：任务依赖、文件范围与安全并发。 | AC-205 每个 Task 含 task_id/description/depends_on/AC/read_scope/write_scope/test_targets/parallelizable/risk；循环、悬空依赖、未知 AC 被拒绝。AC-206 只有依赖完成的任务可调度；write_scope 冲突不得并发；默认并发 1，Phase 6 才允许 2–3；并发需独立预算。AC-207 集成阶段检查 Commit/文件冲突/依赖/集成测试；无法安全合并进入 blocked，不覆盖他人代码。 |
| **REQ-203 Codebase Context**：先让 Agent 准确找到代码。 | AC-208 扫描项目语言/技术栈/目录/入口/API/模型/配置/构建/测试/Rules/AGENTS.md；忽略 node_modules/target/dist/build 等生成目录；只访问授权项目。AC-209 建立路径/关键词/符号索引；按任务动态检索并返回文件路径与行号；以 Git Commit/文件 Hash 增量更新。AC-210 Tree-sitter/LSP 作为可选适配器；不可用时退回文件检索并显式标记限制，不伪称已理解。 |
| **REQ-204 Codebase Graph**：代码关系与影响分析。 | AC-211 支持 Project/Module/File/Class/Function/API/Route/Entity/Table/Test 节点和 imports/calls/extends/implements/contains/exposes/maps_to/reads/writes/tests 关系；记录来源、位置和置信度。AC-212 至少支持调用者/被调用者、所属模块、API↔实现、方法↔测试、修改影响、推荐测试、循环依赖、孤立模块查询；静态不确定项必须标 uncertain，不作为唯一事实来源。 |
| **REQ-205 三层测试与追溯**：代码级、接口/集成、UI/E2E；Verify/Review 职责分离。 | AC-213 三层测试可独立执行，记录命令、退出码、耗时、日志/截图路径和 layer；失败/未运行不得计为通过。AC-214 建立 REQ→AC→TASK→TC→TEST RUN→evidence→Commit；每个 AC 至少一个 TC 或明确 not_run 原因；checkList/TC 版本冻结，结果不回写计划。AC-215 verify-agent 只产生证据，review-agent 只审查；review 不得改代码或运行 verify；review 结果限定 approved/rejected/needs_attention，并改变状态。AC-216 evidence schema 版本化，兼容已有合法材料；历史证据不因新规则被误判为伪造。 |
| **REQ-206 可靠性/幂等**：错误分类、预算、无进展、修复、崩溃恢复。 | AC-217 错误按模型/工具/网络/Git/编译/测试/质量/权限/资源/输入分类；瞬时错误最多 3 次，连续 2 轮无进展停止，每 Task 最多 3 轮修复；权限拒绝不可重试。AC-218 Worktree/Branch/Commit/测试写入/归档/Checkpoint 等外部副作用使用 operation_id 台账；恢复前核验，避免重复副作用；Checkpoint 不被当作文件/Git 自动回滚。AC-219 预算覆盖 Task/Run/Token/工具/模型轮次/并发；超出进入 blocked；不同 Task 隔离计量。 |
| **REQ-207 治理/基线/证据/归档**：单一权威、版本化和兼容迁移。 | AC-220 新增 `baseline.json` 并定义权威源；至少含 change_id/spec_sha256/source_bundle_sha256/approver/approved_at/rules_version/skills_version/base_commit_sha；修改 Spec 产生新版本/新审批；旧 approval.json 可读取。AC-221 统一 evidence schema（校验/模板/规则/代码/真实材料一致）；补齐 change_id/task_id/requirement_id/AC/test_id/layer/command/result/exit_code/executed_at/log/screenshot；`not_run` 可表达但不可计通过；历史证据迁移策略明确。AC-222 统一 canonical `checklist.md`；旧 `checkList.md` 兼容读取，不静默覆盖；历史归档不改名或保留双读；大小写不敏感 FS 有测试。AC-223 `.docloop` Git 策略：项目配置/agents/rules/skills/profiles 跟踪；sessions/checkpoints/traces/recovery/indexes 忽略；agent-inputs 与运行日志按策略忽略；正式归档跟踪；不改变 eol/基线字节。AC-224 增加显式用户最终验收状态/角色/证据/UI；accepted 只能由用户在 Review 后确认；演示 Run 与真实 Run 明确区分，不得自动把演示当业务验收。 |
| **REQ-208 工作台**：保留现有交互，增强执行可观测与控制。 | AC-225 工作台显示 Worker 状态、Task DAG、执行时间线、Git Diff、三层证据、暂停/恢复/取消和最终验收；不改变现有任务/审批/产物流程。AC-226 新增 API 向后兼容；保留现有 ID/选择器/浏览器验收；轮询优先，必要时 SSE/WS；敏感信息脱敏。AC-227 如保留 VS Code：共享项目/Change/Branch/Worktree/修改文件/Diff 状态，用户未提交修改不被覆盖；如本轮不做，必须在 decisions/spec 明确 descope。 |
| **REQ-209 Skills/Rules**：可注册、可路由、可校验、可执行。 | AC-228 15 个唯一 Skill 全部注册并可路由（含 document-parser 与 6 企业 Skill）；元数据含 version/input/output/timeout/risk/allowed_tools；不得重复 document-parser。AC-229 Rules 编码前注入、修改后检查、Review 独立检查；企业 Profile 由代码门禁启用；Rules 修改需审批；Rules/Skills 职责不混。 |
| **REQ-210 模型与安全**：内网、最小权限、可审计。 | AC-230 模型提供方统一 Adapter；支持单活动模型或 per-agent 配置（按决策）；记录 Token/耗时/错误；密钥不回显/不入普通日志；MCP/CLI 最小权限；Worker 只访问授权路径；高风险命令需审批；禁止生产部署/危险 DB/敏感外发。AC-231 解决 Worktree 根在用户 home 下被拒的问题：显式配置 home 外根目录或受控例外；Windows/macOS 均有测试；默认桌面数据目录可准备执行。 |
| **REQ-211 交付文档与真实性** | AC-232 交付升级代码、架构变更说明、新增/修改模块、测试报告、evidence、review、changelog、前后差异、未完成/限制；归档命名与清单一致。AC-233 测试计数/覆盖率按实际环境记录，不固定 47/82；未运行项标 not_run；任何“通过”必须有证据和 Commit。 |
| **REQ-212 严格文档模式** | AC-234 用户上传原始文档时：解析、执行前确认、转换为 spec/decisions/tasks/checklist，保留原文与结构化文档来源映射；冲突列出不自动选择；确认后执行；普通自然语言仍走 Brainstorming。 |

## 4.1 执行模型：项目级 Spec 与分阶段 Change

- 本文件是 V2 的项目级程序规格，用于确定总范围、AC 和阶段；**不直接作为一次 Run 的审批基线**。
- 每个 Phase 创建独立 Change（建议 `20261103-v2-p1`、`20261103-v2-p2`……），只声明该 Phase 的 REQ/AC，独立审批、运行、证据、Review 和归档。
- 阶段 Change 必须引用本文件和 `decisions.md`；不得扩大范围。
- 如果用户要求用单一 Change 完成全部 34 个 AC，则必须一次性交付全部阶段；风险高，默认不采用。
- 本文件所在目录是规划包，不创建 baseline；实现从 Phase 1 的独立 Change 开始。

## 5. 目标架构与边界

- 用户层：Web 工作台、VS Code（待确认）、API。
- 需求控制中心：document-parser、brainstorming、spec-agent、Spec 校验、用户审批、SHA256 baseline。
- 执行控制中心：LangGraph 主图、orchestrator、Task DAG 调度、Skill 路由、Checkpoint；`managed_runs` 收敛为执行子图/基础设施，不是第二个业务调度器。
- Worker Runtime：worker 生命周期、任务领取、租约/心跳、Worktree、并发、取消、恢复、Commit 关联。Worker 是现有 Agent 的执行实例，不是新 Agent 角色。
- 四个专业 Agent：spec/implement/verify/review；真实执行适配器待选型。
- 可靠性控制中心：错误分类、预算、重试、无进展、修复、恢复、安全退出。
- 横向：Codebase Context、Codebase Graph、Rules、Skills、MCP/CLI Adapter、模型 Adapter。
- 唯一业务状态权威：LangGraph Run/Change 状态；Task/Worker 状态是运行元数据，不形成第二套业务状态机。
- 用户最终验收在 Review 之后、Archive 之前；Archive 不再自动等于用户验收。

## 6. 数据与契约变更（摘要）

- 新增 `baseline.json`（权威待决策）与兼容 `approval.json`。
- 新增 Task/Worker/Lease/Operation/TestRun/Evidence 索引表（SQLite + Oracle DDL 同步，Oracle 需真实验收）。
- 统一状态分层：Spec / Run / Task / Worker / Review / Evidence，附映射表；不机械替换现有 API 值。
- 新增 `checklist.md` canonical + 旧 `checkList.md` 兼容。
- 扩展 evidence schema，保留历史兼容读取。
- 工作台新增 worker/DAG/diff/evidence/acceptance API 与视图，保留现有 ID/API。

## 7. 实施阶段（待确认）

- Phase 0 现状审计：本文件所在目录的 `upgrade-audit.md`（已完成）。
- Phase 1 契约与可靠性：状态/审批/证据/命名/幂等/修复/预算。
- Phase 2 Worker Runtime：单 Worker 稳定执行、租约/心跳、Task Worktree、取消/恢复、Commit。
- Phase 3A Codebase Context；Phase 3B Codebase Graph。
- Phase 4 三层测试/追溯/Review 门禁/修复闭环。
- Phase 5 工作台 Worker/DAG/时间线/Diff/验收；（可选 VS Code）。
- Phase 6 并发：DAG 调度、冲突检测、Worktree 集成、并发预算、故障测试。
- 每阶段独立验证，不以“代码写完”进入下一阶段。

## 8. 验收与门禁

- 每个 AC 必须有测试或 `not_run` 理由；没有证据不得宣称通过。
- 正常路径和失败/阻塞/恢复路径都要覆盖；演示结果不得作为真实业务验收。
- 真实环境（Windows Edge、Codex/DeepSeek、Oracle、Docker、VS Code）按可用性分别记录；未运行必须明示。
- 浏览器验收保留现有 `tests/acceptance/test_workbench_browser.py` 契约，新增用例不破坏既有选择器。
- 覆盖率按项目 Profile 配置，不以 47/82 作为全局固定门槛。

## 9. 迁移与兼容

- 旧 `checkList.md`、`review.yaml`、`manifest.yaml`、`approval.json` 可读；新 canonical 名称生成新产物，不静默改名历史。
- 旧归档不重写；新版本/新 Change 重新归档。
- 旧 evidence 材料不能被新校验误判；需要迁移/兼容读取，并在 decisions 记录。
- 旧 API 字段/ID/工作台选择器保留；新增字段可选。
- Oracle/Checkpoint 迁移需独立验证，不自动降级 SQLite。
- 不在未审批前创建 V2 baseline 或修改 `.docloop` 配置。

## 10. 待确认决策（进入实现前）

1. 真实编码 Runtime：Codex 写模式 / 可信 CLI / 容器？安全门禁、回滚、网络边界？
2. VS Code：本轮新建插件，还是明确 descope？
3. 审批权威：文件 `baseline.json` 权威 + DB 投影，或 DB 权威？
4. Commit/Verify 顺序：候选 Commit + 最终 Tag，还是两阶段 Commit？
5. 用户最终验收：真实 Run 必须显式；演示是否自动 accepted？
6. 模型：单活动模型先行，还是 per-agent？
7. 旧 `checkList.md`：canonical lowercase + 兼容读取是否接受？
8. Worktree 根：显式 home 外目录/例外策略？
9. `.docloop` 忽略边界：agent-inputs/logs/indexes。
10. 是否清理旧克隆 `loop-agent/`（HEAD 34e4d43）。

## 11. 审批

本 Spec 尚未审批。用户确认范围、阶段和上述决策后，才生成 baseline、进入 Phase 1；确认前不写实现代码。
