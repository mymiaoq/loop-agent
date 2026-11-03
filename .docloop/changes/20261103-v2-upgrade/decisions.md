# DocLoop Agent V2.0 架构决策与兼容性记录

- 状态：**draft；待用户确认**。本文件不是已批准决策。
- 基线：`7572c6c`；与 `upgrade-audit.md`、`spec.md` 配套。
- 记号：**[用户已定]** 来自用户 V2 方案；**[建议]** 需要确认；**[待定]** 必须由用户选择。

## ADR-201 LangGraph 唯一编排与 `managed_runs` 的归属

- **[用户已定]** LangGraph 是唯一核心编排引擎；不得新增第二套全局调度中心/业务状态机。
- **现状**：`workflow.py` 与 `managed_runs.py` 各编译一个图、各有一份 SQLite checkpoint；`ManagedRuns` 用线程做执行准备调度。
- **[建议]** 把 `managed_runs` 收敛为执行控制中心的**执行子图/基础设施**：
  - 业务 Run/Task 状态仍由主 LangGraph/唯一状态权威决定；
  - 子图只负责准备、Worker、租约、恢复；
  - 不新增第三个图，不把线程池当第二调度中心；
  - 迁移期保留现有 runtime API/字段，逐步替换内部实现。
- **[待定]** 主图与执行子图是否共用一个 checkpointer，还是两个物理库但单一逻辑状态权威。建议先逻辑统一、物理可分，避免一次性迁移风险。

## ADR-202 Worker Runtime 是执行基础设施，不是新 Agent

- **[用户已定]** Worker 是现有 Agent 的执行实例；不新增角色，不增加重复 orchestrator。
- **[建议]** 扩展 `ManagedRuns`：
  - 新增 Worker/Task/Lease/Operation 表与 API；
  - worker_id、task_id、change_id、run_id、worktree、branch、heartbeat、lease、started/finished/result；
  - 任务领取、心跳、租约过期核验、取消、恢复、并发限制；
  - 真实 Agent 执行器后续接入，不在本阶段伪造。
- **现状**：只有单活动准备 Run、线程、Event、全局文件锁；没有 worker 身份/claim/heartbeat/任务队列。
- **[待定]** 真实编码 Runtime（Codex 写模式/可信 CLI/容器）必须先选型并定义安全门禁，否则 Worker 只能做只读/准备。

## ADR-203 状态分层，禁止第二套业务状态机

- **[用户已定]** 保留 draft/ready/in_progress/implemented/verified/accepted + blocked/failed/needs_input；Task/Worker 状态只是运行元数据。
- **现状冲突**：`contracts.py`、DB spec（draft/approved/active）、run（in_progress/blocked/cancelled/planned）、evidence（passed/failed/blocked/not_run）各自为政；review 没有状态。
- **[建议]** 定义明确的层：
  - Spec：draft/approved/superseded；
  - Run/Change：现有主链 + `awaiting_acceptance`（Review 后、用户确认前）；
  - Task：pending/ready/claimed/running/implemented/verified/failed/blocked/cancelled；
  - Worker：starting/ready/busy/draining/stopped/lost；
  - Evidence：passed/failed/blocked/not_run（不得计通过）。
  提供双向映射表；API/UI 保留旧值兼容。
- **[待定]** 演示 Run 是否自动 accepted；建议真实 Run 必须用户验收，演示可显式标记 demo accepted 但仍不算业务验收。

## ADR-204 审批权威：文件 baseline.json + DB 投影

- **现状**：`baseline/spec.md` + `baseline/approval.json`（文件）与 `dl_spec.approval_blob/approved_hash`（DB）双真源；`managed_runs` 同时写两边。
- **[建议]** 以文件 `baseline.json` + 原字节 `baseline/spec.md` 为权威；DB 只保存投影/索引（spec id、hash、revision、approver、approved_at）。理由：CLI/Workflow 与归档天然面向文件；DB 是工作台索引。
- **[建议]** 新 `baseline.json` 字段：change_id/spec_sha256/source_bundle_sha256/approver/approved_at/rules_version/skills_version/base_commit_sha。保留 `approval.json` 兼容读取；旧记录不改写。
- **[待定]** 如果工作台必须离线于文件系统，是否改为 DB 权威、文件投影。此决策影响归档、恢复和双写顺序。

## ADR-205 候选 Commit 与最终 Commit

- **现状**：implement 先 Commit，verify 绑定 HEAD + 干净树；任何 verify 后提交会使证据失效（测试明确断言）。V2 目标写的是 TEST RUN→evidence→Commit。
- **[建议]** 两阶段 Commit：
  1. implement 在 Task Worktree 产出候选 Commit；
  2. verify 在该候选上执行并绑定 tree/commit；
  3. review 后由受控集成产生最终集成 Commit/Tag，证据同时记录 candidate/final；
  4. 最终提交不得改变已证据化的业务树；若改变，重新验证。
- **[待定]** 是否接受“证据绑定候选 Commit + 最终集成 Commit 不重复验证”；需用户确认。

## ADR-206 Task DAG、冲突与并发

- **[用户已定]** 任务必须有 depends_on、读写范围、AC/TC；默认并发 1；稳定后 2–3。
- **[建议]** 在计划 JSON/DB 中新增 DAG；先做拓扑校验/冲突检测，再做调度；写冲突用 write_scope 交集 + 同一 Worktree 单写者；集成由 orchestrator 控制。
- **[建议]** Phase 2 单 Worker；Phase 6 才开并发。现有 `if self._active` 单活动限制在 Phase 2 保留，Phase 6 移除并加预算/回滚。
- **[待定]** 文件冲突的粒度（路径前缀/文件/符号）与危险合并策略。

## ADR-207 Codebase Context 先于 Graph

- **[用户建议]** 先 Context，再 Graph。
- **[建议]** Phase 3A：项目扫描 + 路径/关键词/符号索引 + 按任务检索 + Git/Hash 增量；Phase 3B：Tree-sitter AST + 可选 LSP 关系 + SQLite/本地索引图；不引入 Neo4j。
- **[建议]** 不确定的反射/动态调用标 `uncertain`，不阻塞但降低置信度；Graph 只作辅助决策，不替代 Spec/证据。
- **[待定]** 首批语言：Java 8/Vue 3/TypeScript；其他 Profile 扩展。

## ADR-208 checklist 命名与兼容迁移

- **[用户已定]** canonical 使用 `checklist.md`。
- **现状**：代码/模板/真实变更使用 `checkList.md`；`evidence.py` 硬性要求该大小写；零测试覆盖。
- **[建议]** 新产物写 `checklist.md`；读取时兼容 `checkList.md`（大小写不敏感 FS 要显式检查两个名字）；历史归档不改名，新增归档用 canonical；迁移需 `git mv` + 测试，不做仅大小写的隐式重命名。
- **[待定]** 旧 `checkList.md` 是否也复制为新名称（建议保留历史，不复制以免双份）。

## ADR-209 `.docloop` Git 策略

- **现状**：配置/agents/rules/skills/profiles/changes/docs 已跟踪；checkpoints/sessions/traces/recovery 忽略；`changes/*/agent-inputs` 未忽略；无 indexes。
- **[建议]** 跟踪：project.yaml、agents、rules、skills、profiles、changes 的计划/证据/审查/基线、正式归档；忽略：sessions/checkpoints/traces/recovery/indexes、`changes/*/agent-inputs/`、运行日志中可能含模型上下文的文件。保留 `.gitattributes` eol=lf；不为忽略规则改变基线字节。
- **[待定]** `changes/*/logs/` 与 `agent-inputs/` 的具体边界；历史日志已跟踪，是否清理需单独决策。

## ADR-210 测试与覆盖率

- **事实**：仓库约 109+1 个测试函数；无 coverage 工具/报告；acceptance 无 `__init__.py`；47/82 是 PPT/第三方材料中的演示声明，不是仓库门槛。
- **[建议]** 不采用固定 47/82；按 Profile 配置每层门槛；新增三层测试目录/标记；把现有测试按 layer 标注；acceptance 单独命令或修复 discover；以真实运行记录为准。
- **[建议]** V2 自身先满足现有 110 个测试 + 新增测试，再谈覆盖率目标。

## ADR-211 VS Code：空白，不是保留

- **事实**：仓库无 VS Code 插件/package.json（除 Superpowers 上游文件）；`technical-design-comparison.md` 已标 P2。
- **[待定]** 选项：
  1. Phase 5 新建 thin extension（共享 project/change/branch/worktree/diff，通过本地 API）；
  2. 本轮明确 descope，只保留 Web 工作台，后续单独立项。
- **建议** 先做 Web 工作台 + 共享 API 契约，VS Code 作为独立增量，不阻塞 Worker/DAG。

## ADR-212 真实编码 Runtime 与安全边界

- **现状**：Codex 只读、DeepSeek Chat Completions、Docker 不可用、真实编码 gate blocked；没有写业务代码的 Runtime。
- **建议** 在 Phase 2 前由用户选择：
  - Codex 写模式（如果支持）并加只读/写隔离、超时/取消、Job/Object 清理；
  - 可信 CLI/本地 Coding Agent（白名单 argv、目录、网络）；
  - 容器/沙箱（需要 Docker/等价能力）。
  同时定义：允许目录、命令、网络、密钥、危险操作审批、回滚/保留 Diff。
- **[用户已定]** 代码不出内网；禁止生产部署/危险 DB/敏感外发。
- **结论**：未选定前，Worker 只实现准备/只读，不伪造真实编码。

## ADR-213 模型路由

- **[建议]** 先保留单一活动模型（GPT/DeepSeek），新增 Agent 时再支持 per-role 覆盖；模型调用记录 Token/耗时/错误；密钥不进入日志/Prompt/DB 明文。
- **[现状]** 双档案持久化；DPAPI 仅 Windows；Codex 失败/不可用时要明确 blocked；macOS 只能演示/受控 fixture。
- **[待定]** per-agent 模型是否在 Phase 2/3 引入。

## ADR-214 Review 与用户最终验收

- **现状**：review 结果硬编码 passed；不改变状态；accepted 由 archive 自动产生；没有用户验收。
- **[建议]** Review 独立产出 `review.md`（人读）+ 机器结果；status approved/rejected/needs_attention；Rejected → implemented/in_progress 按规则回退；approved → `awaiting_acceptance`；用户明确验收 → accepted → archive；演示 Run 与真实 Run 区分。
- **[待定]** 演示是否允许自动 accepted（建议不允许作为业务验收，只可标 demo accepted）。

## ADR-215 归档命名与兼容

- **现状**：要求 spec/decisions/tasks/checkList/evidence/review.yaml，写 manifest.yaml；`文档/变更记录` 实际为空。
- **[建议]** 新产物使用 `checklist.md`/`review.md`/`changelog.md`/`manifest.json`（或保留 manifest.yaml 但版本化），同时兼容读取旧 `review.yaml`/manifest.yaml/checkList.md；归档写入清单与前缀 Hash；修复/重跑使用新版本目录或显式新 Change。
- **[待定]** manifest.json vs manifest.yaml；review.yaml 是否继续生成机器副本。建议人读 review.md + 机器 review.yaml 双份，但需避免双真源。

## ADR-216 Skills/Rules

- **事实**：15 个唯一 Skill；document-parser 单份；9 平台作用域 + 6 企业领域 + 1 共享；7 个 Skill 未被阶段路由；Skill 元数据只有 name/description；Rules 只注入 Prompt。
- **[建议]** 补齐 machine-readable 元数据（version/timeout/risk/allowed_tools/input/output schema）；把 7 个 Skill 接入路由/配置；企业 Profile 用代码门禁而不是仅文字；Rules 增加编码前后检查器和 Review 检查；保留 editable Superpowers。
- **[建议]** 文档统一写 9+6+1（15 unique），不再写 9+7（除非明确 document-parser 双列统计）。

## ADR-217 PPT 数字与演示声明

- **事实**：PPT 的 47 用例/82% 覆盖率、演示工时是案例，不是当前仓库统计；当前约 109+1 测试、无 coverage。
- **[建议]** 在正式 Spec/验收中不复制 47/82 为门槛；改为每项目 Profile 配置；报告实际命令/环境/结果；未运行标记 not_run。

## ADR-218 Worktree 根与 home 守卫

- **事实**：`WorktreeRuntime` 拒绝 root 在用户 home 下；默认数据目录在项目同级，macOS 下位于 home；测试用 `/tmp` 绕过。
- **[建议]** 显式配置 worktree/data 根到 home 外，或增加受控例外（用户确认路径+审计）；默认桌面数据目录迁移/设置引导；新增 macOS/Windows 测试。
- **[待定]** 默认数据目录是否迁移到非 home 位置（影响现有数据）。

## ADR-219 旧克隆与仓库清洁

- **事实**：工作区有未跟踪 `loop-agent/` 独立克隆（HEAD 34e4d43，含重复 Skill），仅本地 `.git/info/exclude` 排除，不在 `.gitignore`。
- **[建议]** 移到 `/tmp` 备份或删除；若保留，加入 `.gitignore`/明确不入库；V2 检出前清理，避免误提交重复 Skill/规则。

## ADR-220 版本与发布

- **建议**：V2.0 分阶段提交；每阶段独立验证、evidence、review；不一次性重构；失败/未运行如实记录；不自动推生产。
- **交付**：完整代码、架构变更说明、模块说明、测试报告、evidence、review、changelog、前后差异、未完成事项/限制。

## ADR-221 项目级规格与分阶段 Change

- **现状**：现有 Change 模型以一个 spec 的 AC 集合作为一次 Run 的验收范围；V2 有 34 个 AC、跨 6 个阶段。
- **[建议]** V2 使用项目级规格 + 每阶段独立 Change；每阶段只声明本阶段 AC，独立审批/证据/归档；项目级规格不作为单次 Run 的 baseline。
- **理由**：符合“每阶段独立验证”；避免一次 Run 未完成全部 AC 就无法 accepted；仍保留一个总 Spec 作为范围/决策权威。
- **[待定]** 用户若坚持单一 Change，则需接受更长周期和一次性验收。

## 待确认决策清单

| 编号 | 决策 | 建议默认 | 影响 |
|---|---|---|---|
| D-01 | 真实编码 Runtime | 先只读/准备，选定后再写 | Phase 2 能否真实编码 |
| D-02 | VS Code | 本轮 descope 或 Phase 5 新建 | 交付范围/工期 |
| D-03 | 审批权威 | 文件 baseline.json 权威 + DB 投影 | 迁移/一致性 |
| D-04 | Commit/Verify 顺序 | 候选 Commit + 最终集成 Commit | 证据/测试改动 |
| D-05 | 演示验收 | 不自动业务 accepted | 状态/UI/测试 |
| D-06 | 模型路由 | 先单活动模型 | Phase 2/3 |
| D-07 | checklist 迁移 | canonical + 兼容读取 | 代码/归档/FS |
| D-08 | Worktree 根 | 显式 home 外目录 | 桌面可用性 |
| D-09 | .docloop 忽略 | agent-inputs/logs/indexes 忽略 | Git 体积/审计 |
| D-10 | 旧克隆 | 清理 | 仓库卫生 |
