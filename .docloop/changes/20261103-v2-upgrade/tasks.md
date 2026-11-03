# DocLoop Agent V2.0 实施计划

> **For agentic workers:** 本计划只有在 `spec.md` 经用户确认后才可执行。执行时使用 `superpowers:executing-plans` 或 `superpowers:subagent-driven-development`，按任务逐项测试并提交。

**Goal:** 在保留 LangGraph、五角色、三中心、审批/证据门禁的前提下，增量加入可靠的 Worker Runtime、Task DAG、Codebase Context/Graph、三层测试追溯和可观测工作台。

**Architecture:** 主 LangGraph 仍是唯一业务编排/状态权威；`managed_runs` 收敛为执行子图/基础设施；Worker Runtime 负责执行实例与隔离；Task/Worker 状态是运行元数据；Codebase Context/Graph 是现有 Agent 的工具，不是新 Agent。

**Tech Stack:** Python 3.11+、LangGraph、SQLite/LangGraph Checkpointer、FastAPI、原生 HTML/CSS/JS、Git Worktree、Tree-sitter（可选 LSP）、现有模型 Adapter；Oracle 仅在独立环境验收。

**Spec:** `./spec.md`；审计：`./upgrade-audit.md`；决策：`./decisions.md`；验收：`./checklist.md`。

## 全局约束

- 不改已批准 Spec 字节；不建 V2 baseline 直到用户确认。
- 不新增 orchestrator/第二套全局状态机；不整体重写 LangGraph。
- 不跳过测试、弱化 Rules、伪造 evidence；未运行标 `not_run`。
- 默认并发 1；Phase 6 才允许 2–3。
- 现有 API/ID/浏览器验收选择器保持兼容。
- 真实编码 Runtime/VS Code/审批权威/Commit 顺序未确认前不执行相关任务。
- 每个任务先写失败测试，再实现；每阶段独立验证、evidence、review。
- 本文件是项目级计划；每个 Phase 创建独立 Change，只声明本 Phase 的 AC（见 `spec.md` 4.1、`decisions.md` ADR-221）。

## Phase 0：现状审计（已完成）

### T-001 审计与计划

- **状态：** 已完成
- **文件：** `upgrade-audit.md`、`spec.md`、`decisions.md`、`tasks.md`、`checklist.md`
- **覆盖：** 当前代码/PPT 对照、冲突、风险、阶段建议
- **依赖：** 无
- **完成条件：** 用户确认范围与决策；不创建 baseline

## Phase 1：契约、治理与可靠性（先做，不依赖真实编码）

### T-101 状态/契约分层与映射

- **依赖：** T-001
- **AC：** AC-217、AC-224
- **读：** `contracts.py`、`workflow.py`、`workbench_store.py`、`workbench_service.py`
- **写：** 状态映射模块/文档、契约测试
- **测试：** 现有 workflow/契约测试 + 新状态映射测试
- **并行：** 否（契约最先）
- **风险：** 中；会触碰闭集转移表和现有历史断言

定义 Spec/Run/Task/Worker/Review/Evidence 六层状态与现有值映射；新增 `awaiting_acceptance` 但不破坏现有 API；Task/Worker 状态不进入主业务状态机。

### T-102 baseline.json 与审批权威

- **依赖：** T-101
- **AC：** AC-220、AC-221
- **读：** `governance.py`、`workbench_store.py`、`managed_runs.py`、`workflow.py`
- **写：** `governance.py`、`workbench_store.py`、迁移测试
- **测试：** 新旧 approval 兼容、原字节不变、并发审批、Hash 冲突
- **并行：** 可与 T-103 部分并行；不建议
- **风险：** 高（双真源/迁移）

新增 `baseline.json`（权威按 D-03 决策）；DB 投影；保留旧 `approval.json` 读取；版本/reapproval；不重写历史。

### T-103 evidence schema 统一与兼容

- **依赖：** T-101
- **AC：** AC-213、AC-214、AC-216、AC-221
- **读：** `evidence.py`、`templates/evidence.yaml`、`rules/verification-standard.md`、真实 `changes/20261102-framework/evidence.yaml`
- **写：** `evidence.py`、模板/规则、迁移/兼容测试
- **测试：** 旧真实 evidence 可读、not_run 可表达、缺字段拒绝、Hash/日志
- **并行：** 与 T-102 可并行但会有文档冲突
- **风险：** 高（现有材料自拒）

统一 schema；补齐 change/task/TC/layer/exit_code/log/screenshot；保留旧 producer 兼容；必须标明 not_run 不可计通过。

### T-104 checklist.md canonical 与兼容读取

- **依赖：** T-101
- **AC：** AC-222
- **读：** `evidence.py`、`workflow.py`、`managed_runs.py`、`deliverables.py`、`workbench_service.py`、templates/rules/agents
- **写：** 代码、模板、skill 文档、测试
- **测试：** 双读、大小写不敏感 FS、归档旧名、新名
- **并行：** 可与 T-103 并行，但需协调 evidence 文件名
- **风险：** 高（大小写重命名/Git 不记录）

canonical `checklist.md`；读兼容 `checkList.md`；旧归档不改名；用 `git mv` + 测试，不做仅大小写隐式 rename。

### T-105 operation_id/幂等台账

- **依赖：** T-101
- **AC：** AC-218
- **读：** `worktree_runtime.py`、`execution_preparation.py`、`managed_runs.py`、`evidence.py`、`workbench_store.py`
- **写：** 新 operation 表/API/迁移、worker 恢复钩子
- **测试：** 重复 prepare、重复 archive、崩溃后核验
- **并行：** 否
- **风险：** 高（外部副作用）

记录 Worktree/Branch/Commit/测试/归档/Checkpoint 的前后状态；恢复前核验，不做自动回滚。

### T-106 可靠性错误分类/修复/预算接线

- **依赖：** T-101
- **AC：** AC-217、AC-219
- **读：** `reliability.py`、`workflow.py`、`adapters.py`、`model_gateway.py`
- **写：** `reliability.py`、`workflow.py`、测试
- **测试：** 编译/测试/权限分类、3 次重试、2 轮无进展、3 轮修复、预算
- **并行：** 可与 T-103 并行
- **风险：** 中高（会改变 workflow 失败路径）

让 `repair()` 真正接入编译/测试失败；权限错误不可重试；预算按 Task 隔离；blocked 写 recovery。

### T-107 Git 忽略/仓库卫生

- **依赖：** T-001
- **AC：** AC-223
- **读：** `.gitignore`、`.gitattributes`、`.git/info/exclude`、`workflow.py` 的 agent-inputs 写入
- **写：** `.gitignore`、必要的 `.git/info/exclude`/迁移说明
- **测试：** `git check-ignore`、基线字节不变
- **并行：** 是
- **风险：** 低中（eol/基线字节）

忽略 `agent-inputs/`、`indexes/`、运行日志边界；保留配置；清理/忽略旧 `loop-agent/`；不改 eol。

### T-108 测试发现/三层脚手架

- **依赖：** T-001
- **AC：** AC-213、AC-233
- **读：** `tests/`、`pyproject.toml`、README
- **写：** `tests/` 结构/标记、CI/命令文档
- **测试：** `discover` 能发现 acceptance；layer 标记
- **并行：** 是
- **风险：** 低

不设置固定 47/82；按 Profile 可配；现有 109+1 先全绿。

### T-109 最终验收状态/API（契约层）

- **依赖：** T-101
- **AC：** AC-224
- **读：** `contracts.py`、`workflow.py`、`workbench.py`、`workbench_static`
- **写：** 状态/API（不接 UI 前）
- **测试：** review→awaiting→accepted；不可自动 accepted
- **并行：** 否
- **风险：** 高（改变现有 accepted 行为）

先定义 API/状态；UI 在 Phase 5；演示/真实区分。

### T-110 Skill 注册/路由/元数据

- **依赖：** T-001
- **AC：** AC-228
- **读：** `.docloop/project.yaml`、`skill_runtime.py`、`project.py`、15 个 SKILL.md
- **写：** Skill 注册/元数据/路由、测试
- **测试：** 15 个唯一、document-parser 单份、7 个未路由 Skill 接入、输入/输出校验
- **并行：** 可与 T-108 并行
- **风险：** 中

不新增重复 document-parser；保留 editable Superpowers。

### T-111 Rules 强制检查与企业门禁

- **依赖：** T-101
- **AC：** AC-229
- **读：** `.docloop/rules/`、profiles、`contracts.py`、review/adapter
- **写：** 规则检查器/编码前注入/Review 检查、企业 Profile 代码门禁
- **测试：** 企业 Skill 在平台 Profile 被拒；Rules 修改审批；Review 独立
- **并行：** 可与 T-110 并行
- **风险：** 中高

## Phase 2：Worker Runtime（单 Worker 稳定优先）

### T-201 Worker/Task/Lease/Operation 数据模型与 API

- **依赖：** T-101、T-105
- **AC：** AC-201、AC-218
- **读：** `workbench_store.py`、`migrations/oracle/001_workbench.sql`、`managed_runs.py`
- **写：** 新表/迁移/API、Oracle DDL 同步
- **测试：** CRUD、归属、lease 过期、migration
- **并行：** T-202 可并行于 schema 定稿后
- **风险：** 高（SQLite/Oracle 双 schema）

字段：worker_id/task_id/change_id/run_id/worktree/branch/heartbeat/lease/started/finished/result/operation_id。

### T-202 Worker 生命周期/任务领取

- **依赖：** T-201
- **AC：** AC-201、AC-202
- **读：** `managed_runs.py`、`workflow.py`
- **写：** Worker supervisor/worker 执行器（不真实写码时先只读）
- **测试：** 领取、执行、结果回传、重复领取拒绝
- **并行：** 否
- **风险：** 高

不新增 Agent 角色；Worker 是执行实例。

### T-203 租约、心跳与恢复

- **依赖：** T-202
- **AC：** AC-202、AC-204
- **写：** heartbeat/lease 扫描、恢复核验
- **测试：** Worker 退出/租约过期/服务重启/不重复副作用
- **并行：** 否
- **风险：** 高

租约不是现有 `run_lock`；不要复用同名语义。

### T-204 每 Task Worktree 与 Commit 关联

- **依赖：** T-202、T-105
- **AC：** AC-203
- **读/写：** `worktree_runtime.py`、`execution_preparation.py`、DB 新表
- **测试：** 单写者、主分支不写、Commit SHA、干净源、home 根
- **并行：** 否
- **风险：** 高（worktree 根/home 守卫）

先解决 ADR-218 根目录；每个 Task 独立 Worktree/Branch；结果关联 Commit。

### T-205 安全取消/暂停/重启恢复

- **依赖：** T-202
- **AC：** AC-204
- **写：** cancel/pause/resume 执行器；进程树/子进程清理；checkpoint
- **测试：** 取消中/取消后/重启/工作区保留
- **并行：** 否
- **风险：** 高

取消不是杀进程即完成；保留现场；演示 Run 也要可取消或明确不同语义。

### T-206 Worker 回归（崩溃/取消/隔离）

- **依赖：** T-202..205
- **AC：** AC-201..204
- **写：** `tests/test_worker_*.py`
- **测试：** 单 Worker 端到端（只读/准备版）
- **并行：** 否
- **风险：** 中

先单 Worker 全绿，再考虑并发。

### T-207 模型 Adapter/安全边界（与 Worker 同期）

- **依赖：** T-202、D-01/D-06 决策
- **AC：** AC-230
- **读：** `model_gateway.py`、`model_settings.py`、`codex_runtime.py`、workbench 安全中间件
- **写：** 模型 Adapter/记录/脱敏；Worker 路径与命令权限；危险操作审批
- **测试：** 密钥不回显、Token/耗时/错误、路径越界、危险操作拒绝
- **并行：** 可部分并行
- **风险：** 高（安全/运行时选型）

## Phase 3A：Codebase Context

### T-301 项目扫描与索引骨架

- **依赖：** T-001
- **AC：** AC-208
- **读：** `project.py`、`contracts.py`
- **写：** `src/docloop/codebase/scan.py`、index schema
- **测试：** 语言/目录/入口/测试/生成目录忽略/越界
- **并行：** 可与 Phase 2 并行
- **风险：** 中

### T-302 任务级检索与上下文注入

- **依赖：** T-301
- **AC：** AC-209
- **写：** search/ranking/API、Agent 上下文
- **测试：** 路径+行号、任务相关文件、噪声过滤
- **并行：** 否
- **风险：** 中

### T-303 增量索引

- **依赖：** T-301
- **AC：** AC-209
- **写：** Commit/Hash 增量、缓存
- **测试：** 未变不重扫、变更/删除更新
- **并行：** 可与 T-302 并行
- **风险：** 中

### T-304 Tree-sitter/LSP 适配器（可选）

- **依赖：** T-301
- **AC：** AC-210
- **写：** AST/LSP adapter、fallback
- **测试：** Java/TS/Vue 基本符号；不可用标记
- **并行：** 是
- **风险：** 中高（依赖/版本）

## Phase 3B：Codebase Graph

### T-311 Graph schema 与构建

- **依赖：** T-301、T-304
- **AC：** AC-211
- **写：** nodes/edges/source/confidence、SQLite/本地索引
- **测试：** imports/calls/extends/API/tests
- **并行：** 否
- **风险：** 高

不引入 Neo4j；记录来源/位置/置信度。

### T-312 查询与影响分析

- **依赖：** T-311
- **AC：** AC-212
- **写：** callers/callees/API↔impl/tests/impact/cycles/orphans
- **测试：** 查询正确性/循环/孤立/影响测试推荐
- **并行：** 否
- **风险：** 中高

### T-313 不确定性与计划集成

- **依赖：** T-312
- **AC：** AC-212
- **写：** uncertain 标记、plan/tasks/checklist 注入
- **测试：** 反射/动态调用标记；不替代 Spec
- **并行：** 否
- **风险：** 中

## Phase 4：三层测试、追溯与 Review

### T-401 三层测试执行器

- **依赖：** T-108、T-106
- **AC：** AC-213
- **写：** layer runner、命令/退出码/日志/截图
- **测试：** 三层各自执行、失败/not_run
- **并行：** 可与 Phase 3 并行
- **风险：** 中

### T-402 TC/TestRun/evidence 追溯

- **依赖：** T-401、T-103
- **AC：** AC-214、AC-216
- **写：** TC/TestRun 表、evidence 关联、checkList 解析
- **测试：** REQ→AC→TASK→TC→RUN→evidence→Commit
- **并行：** 否
- **风险：** 高

### T-403 Verify/Review 独立门禁

- **依赖：** T-402、T-109
- **AC：** AC-215
- **写：** review 真实结果/状态、review.md/yaml、回退
- **测试：** review 不改代码/不跑 verify；approved/rejected/needs_attention
- **并行：** 否
- **风险：** 高（现有 review 硬编码）

### T-404 修复闭环

- **依赖：** T-106、T-403
- **AC：** AC-217
- **写：** 失败→修复→复验→预算/无进展
- **测试：** 编译/测试失败、修复上限、权限不可重试
- **并行：** 否
- **风险：** 高

### T-405 测试门槛/报告

- **依赖：** T-401、T-108
- **AC：** AC-233
- **写：** per-Profile 配置/报告、not_run 清单
- **测试：** 门槛可配、不固定 47/82
- **并行：** 是
- **风险：** 低

### T-406 严格文档模式

- **依赖：** T-001、T-402
- **AC：** AC-234
- **读：** 文档解析/Spec/来源索引
- **写：** 原始文档确认、来源映射、冲突列表、普通自然语言分流
- **测试：** 文档→spec/decisions/tasks/checklist；冲突不自动选择
- **并行：** 可与 T-401 并行
- **风险：** 中

## Phase 5：工作台

### T-501 Worker/DAG/时间线视图

- **依赖：** T-201、T-202
- **AC：** AC-225
- **写：** API/UI worker 状态、任务 DAG、时间线
- **测试：** 真实状态、空态、移动端、无泄漏
- **并行：** 否
- **风险：** 中

### T-502 Diff/证据/测试视图

- **依赖：** T-402、T-501
- **AC：** AC-225
- **写：** Git diff、三层证据、TC 结果
- **测试：** diff 只读、大文本、敏感信息
- **并行：** 可与 T-503 并行
- **风险：** 中

### T-503 暂停/恢复/最终验收 UI

- **依赖：** T-109、T-202、T-403
- **AC：** AC-224、AC-225
- **写：** 控制按钮/验收弹窗/状态
- **测试：** 安全取消、恢复、验收人/结论
- **并行：** 否
- **风险：** 高

### T-504 API 兼容/流式

- **依赖：** T-501
- **AC：** AC-226
- **写：** 兼容字段/SSE 或轮询退避
- **测试：** 旧客户端/浏览器验收
- **并行：** 可与 T-502 并行
- **风险：** 中

### T-505 VS Code（条件）

- **依赖：** D-02 决策
- **AC：** AC-227
- **写：** 插件或明确 descope 文档
- **测试：** 共享状态/未提交修改保护
- **并行：** 独立
- **风险：** 高（greenfield）

## Phase 6：并发（Worker 稳定后）

### T-601 DAG 调度与冲突

- **依赖：** T-206、T-501
- **AC：** AC-205、AC-206
- **写：** 拓扑调度、write_scope 冲突、预算
- **测试：** 环/悬空/冲突/并行/默认 1
- **并行：** 否
- **风险：** 高

### T-602 集成分支/合并

- **依赖：** T-601
- **AC：** AC-207
- **写：** 集成 Worktree/合并/冲突 blocked/集成测试
- **测试：** 冲突不覆盖、Commit/测试
- **并行：** 否
- **风险：** 高

### T-603 并发预算/Worker 池

- **依赖：** T-601
- **AC：** AC-206、AC-219
- **写：** 2–3 Worker 上限、独立预算
- **测试：** 资源/预算/失败隔离
- **并行：** 否
- **风险：** 高

### T-604 故障与并发回归

- **依赖：** T-601..603
- **AC：** AC-204、AC-207
- **写：** 故障矩阵测试
- **测试：** 崩溃/取消/冲突/合并/恢复
- **并行：** 否
- **风险：** 高

## Phase 7：交付与迁移

### T-701 文档/变更记录/差异/限制

- **依赖：** 全部
- **AC：** AC-232
- **写：** changelog、review、升级前后差异、限制
- **测试：** 文档/清单/Hash
- **并行：** 否
- **风险：** 低

### T-702 全量验证

- **依赖：** T-701
- **AC：** AC-233
- **写：** 测试报告、evidence、not_run
- **测试：** 根测试/acceptance/doctor/build/目标环境
- **并行：** 否
- **风险：** 中

### T-703 迁移/兼容验收

- **依赖：** T-702
- **AC：** AC-221、AC-222、AC-231
- **写：** 迁移脚本/回滚/兼容矩阵
- **测试：** 旧数据/旧归档/新旧 API/Oracle（若可用）
- **并行：** 否
- **风险：** 高

## 执行门

1. 用户确认 `spec.md` 与 D-01..D-10。
2. Phase 1 独立验证通过后才进入 Phase 2。
3. Phase 2 单 Worker 稳定后才进入 Phase 6。
4. 每个 Phase 结束提交 evidence/review/changelog；未运行项必须列出。
