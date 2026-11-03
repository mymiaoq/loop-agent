# DocLoop Agent V2.0 验收清单

- 状态：**draft；未审批；未执行**
- 基线：`7572c6c`；配合 `spec.md`、`upgrade-audit.md`、`decisions.md`、`tasks.md`
- 规则：每个 AC 必须找到测试/证据，或明确 `not_run`；`not_run` 不得计为通过；演示不得当作真实业务验收。

## 0. 用户确认门

- [ ] 用户确认 V2 范围、阶段顺序与 `decisions.md` D-01..D-10。
- [ ] 用户确认本轮不做/延后的项（VS Code、真实编码 Runtime、Oracle/Docker 等）。
- [ ] 确认后才创建 baseline、开始 Phase 1；确认前无实现代码。
- [ ] 每个 Phase 使用独立 Change（只含该阶段 AC），项目级规格不直接作为单次 Run baseline。

## 1. 现有基线（Phase 0 事实）

- [ ] `uv run python -m unittest discover -s tests -v` 当前 109+1 函数结果记录（实际执行后填）。
- [ ] `tests/acceptance/test_workbench_browser.py` 在可用浏览器渠道执行；macOS/Windows 环境差异、DPAPI/Codex 限制如实记录。
- [ ] `uv run docloop doctor` 结果记录。
- [ ] `uv build` 结果记录。
- [ ] 不把 47 用例/82% 覆盖率当作门槛；当前无 coverage 报告。
- [ ] 明确 `tests/acceptance` 未被 discover 的现状，Phase 1 修复并有测试。

## 2. Phase 1：契约/治理/可靠性

- [ ] **AC-217/AC-224** 状态映射文档 + 测试；旧 API 值兼容。
- [ ] **AC-220** `baseline.json` 字段、权威、版本、reapproval；旧 `approval.json` 可读；原字节不变。
- [ ] **AC-221/AC-216** evidence schema 统一；旧真实 evidence（producer=codex-main）可迁移/兼容；not_run 可表达且不计通过；历史不被误判。
- [ ] **AC-222** canonical `checklist.md`；旧 `checkList.md` 兼容读取；大小写不敏感 FS 测试；旧归档不改名。
- [ ] **AC-218** operation_id 台账；Worktree/Branch/Commit/测试/归档/Checkpoint 恢复核验；无重复副作用。
- [ ] **AC-217** 错误分类/3 次重试/2 轮无进展/3 轮修复/权限不可重试；`repair()` 真正接线。
- [ ] **AC-219** Task/Run/Token/工具/模型轮次/并发预算；超预算 blocked。
- [ ] **AC-223** `.docloop` git 策略：agent-inputs/indexes/logs 边界；配置/规则/Skill 跟踪；eol/基线字节不变。
- [ ] **AC-224** review→awaiting_acceptance→accepted；用户验收状态/API；演示/真实区分。
- [ ] **AC-228** 15 个唯一 Skill 注册/路由/元数据；document-parser 单份；7 个未路由 Skill 接入。
- [ ] **AC-229** Rules 编码前/修改后/Review 检查；企业 Profile 代码门禁；Rules 修改审批。
- [ ] Phase 1 独立测试/evidence/review 通过，才进入 Phase 2。

## 3. Phase 2：Worker Runtime（单 Worker）

- [ ] **AC-201** worker_id/task_id/change_id/run_id/worktree/branch/heartbeat/lease/started/finished/result 持久化可查。
- [ ] **AC-202** 任务领取、租约、心跳、过期恢复；已完成外部操作不重复。
- [ ] **AC-203** 每 Task 独立 Worktree；同一 Worktree 单写者；不写主分支；Commit SHA 关联。
- [ ] **AC-204** 超时/取消/暂停/崩溃/服务重启；保留 checkpoint/Worktree/未提交现场；取消不伪装完成。
- [ ] **AC-218** 幂等台账与恢复核验（与 Phase 1 联调）。
- [ ] **AC-231** Worktree 根在 home 外/显式例外；macOS/Windows 测试；默认桌面数据目录可准备。
- [ ] 单 Worker 稳定后才进入 Phase 6；不提前开并发。
- [ ] 真实编码 Runtime 若未选定：只做只读/准备，Worker 不写业务代码，明确 `not_run`。

## 3.1 Phase 2：模型与安全

- [ ] **AC-230** 模型 Adapter 记录 Token/耗时/错误；密钥不回显；Worker 授权路径/命令；危险操作审批；代码不出内网。
- [ ] 真实编码 Runtime 未选定：只读/准备，不写业务代码，`not_run`。

## 4. Phase 3A/3B：Context/Graph

- [ ] **AC-208** 项目扫描：语言/栈/目录/入口/API/模型/配置/构建/测试/Rules/AGENTS；忽略生成目录；路径授权。
- [ ] **AC-209** 路径/关键词/符号检索；任务相关上下文含文件+行号；Git/Hash 增量。
- [ ] **AC-210** Tree-sitter/LSP 适配器可用/不可用降级；不伪称理解。
- [ ] **AC-211** 节点/关系/source/位置/置信度；Graph 存储（SQLite/本地索引，无 Neo4j）。
- [ ] **AC-212** callers/callees/模块/API↔实现/测试/影响/循环/孤立；uncertain 标记；不替代 Spec。
- [ ] **AC-212** Graph 结果进入 plan/tasks/checklist，有测试覆盖。
- [ ] Phase 3 独立验证；Index/Graph 不提交运行数据（遵守 git 策略）。

## 5. Phase 4：三层测试/追溯/Review

- [ ] **AC-234** 严格文档模式：原文确认、来源映射、冲突列出、不自动选择。

- [ ] **AC-213** Layer 1 代码级（lint/type/build/unit）；Layer 2 API/集成；Layer 3 UI/E2E；每层命令/退出码/日志/截图/layer。
- [ ] **AC-214** REQ→AC→TASK→TC→TEST RUN→evidence→Commit；每 AC 有 TC 或 not_run；checkList 解析；TC 版本冻结。
- [ ] **AC-215** verify 只出证据；review 只审查；review 不改代码/不跑 verify；approved/rejected/needs_attention 改变状态。
- [ ] **AC-216** evidence 版本化、历史兼容、缺字段拒绝、not_run 不计通过。
- [ ] **AC-217** 失败→修复→复验；无进展/修复上限；权限不可重试。
- [ ] **AC-233** 测试门槛按 Profile 配置；报告真实计数/覆盖；不固定 47/82。
- [ ] Phase 4 通过后才进入 Phase 5/6。

## 6. Phase 5：工作台

- [ ] **AC-225** Worker 状态、Task DAG、时间线、Git Diff、三层证据、暂停/恢复/取消、最终验收可见可操作。
- [ ] **AC-226** API 兼容；现有 ID/选择器/浏览器验收不破坏；SSE 或轮询退避；敏感信息脱敏。
- [ ] **AC-224** 验收人/结论/时间/证据；accepted 需用户确认；演示与真实区分。
- [ ] **AC-227** 若做 VS Code：共享 project/change/branch/worktree/diff；不覆盖未提交修改；若不做，decisions/spec 明确 descope。
- [ ] 390/1366/1920、紧凑高度、空态、错误态验证；控制台 0 错误。

## 7. Phase 6：并发

- [ ] **AC-205** DAG：depends_on/AC/read/write/test/parallel/risk；循环/悬空/未知 AC 拒绝。
- [ ] **AC-206** 依赖完成才调度；write_scope 冲突不并发；默认 1；Phase 6 才 2–3；独立预算。
- [ ] **AC-207** 集成检查 Commit/冲突/依赖/测试；不安全合并 blocked，不覆盖他人。
- [ ] **AC-219** 并发预算/Task 计量/模型调用；超限 blocked。
- [ ] **AC-204** 并发下的取消/崩溃/恢复/故障矩阵。
- [ ] 故障测试通过后才宣称并发能力。

## 8. 交付文档

- [ ] **AC-232** 升级代码 + 架构变更说明 + 模块说明 + 测试报告 + evidence + review + changelog + 前后差异 + 未完成/限制。
- [ ] 归档采用兼容命名的清单/Hash；旧归档不改写；新产物 canonical。
- [ ] **AC-233** 所有“通过”有真实命令/证据/Commit；所有 `not_run` 列出原因和环境。
- [ ] **AC-234** 严格文档模式：原文解析、确认、来源映射、冲突列出、不自动选择。

## 9. Not run（实现前必填，当前未执行）

- [ ] 真实模型（GPT/DeepSeek）连通性/业务 Spec 生成（按环境）。
- [ ] Oracle 关系存储与 Checkpoint（未连接）。
- [ ] Docker/容器隔离与真实编码执行。
- [ ] 真实企业 Vue/Java 项目、Playwright MCP。
- [ ] VS Code 插件（若不做则标 descope）。
- [ ] Codebase Graph 大规模项目/性能。
- [ ] 并发 2–3 Worker（Phase 6 前）。
- [ ] macOS DPAPI/Codex 限制、Windows Edge 差异。

## 10. 验收结论模板

- 环境/Commit/命令：
- 通过项：
- 失败项：
- `not_run` 项及原因：
- 剩余风险/限制：
- 用户最终验收：待确认/通过/拒绝
