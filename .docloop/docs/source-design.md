# DocLoop Agent + Superpowers Agent-Skill + Rules 工程化体系设计

> 基于 DocLoop Agent 的多 Agent 协作工程化方案：一个主 Agent
> 调度，四个专业子 Agent 分工，三个核心控制中心统一治理；Superpowers
> 提供软件工程工作流，Rules 作为强制规范，Skills 作为可插拔专业能力。
> 本文保留原有企业项目 Agent、Rules 和 Skills 定义，并将其接入 DocLoop
> Agent 的 LangGraph 编排、Superpowers
> 开发流程、审批门禁、证据验证和可靠性恢复体系。

------------------------------------------------------------------------

**版本：** V1.0\
**适用对象：** DocLoop Agent、Coding Runtime、企业项目开发 Agent\
**核心基线：** Spec
审批后开发；实现、验证、审查职责分离；所有结论证据化。

## 0. DocLoop Agent 与 Superpowers 集成总则

### 0.1 架构职责边界

本文不依赖任何第三方 IDE 平台的专属 Agent
调度、配置或工具调用能力。DocLoop Agent
是唯一的运行与治理平台；Superpowers 是被 DocLoop 调度的软件工程方法论和
Skills 集合。

  ---------------------------------------------------------------------------------------------------------------------
  组成部分         职责                                                                      不负责
  ---------------- ------------------------------------------------------------------------- --------------------------
  需求控制中心     输入解析、需求澄清、Spec 生成、审批、基线锁定                             不直接编写业务代码

  执行控制中心     LangGraph 编排、Agent 调度、Task 调度、Skill 路由                         不替代专业 Agent

  可靠性控制中心   错误分类、预算、重试、无进展检测、恢复和安全退出                          不修改需求、不绕过权限

  Superpowers      Brainstorming、Worktree、Planning、TDD、Debugging、Review、Verification   不管理 DocLoop
                                                                                             全局状态、审批和预算

  Agent            按角色完成规格设计、实现、验证或审查                                      不越权执行其他角色职责

  Skills           提供可复用专业步骤和输出契约                                              不取代
                                                                                             Rules，不授予工具权限

  Rules            定义强制规范和禁区                                                        不负责任务调度

  MCP / CLI        提供受控文件、Git、终端、浏览器等工具                                     不决定业务流程和验收结论
  Adapter                                                                                    
  ---------------------------------------------------------------------------------------------------------------------

### 0.2 三个核心控制中心

**A. 需求控制中心（Requirement Governance Controller）**

-   接收自然语言、DOCX、PDF、Markdown、图片、Excel、OpenAPI 等输入。
-   通过 `document-parser` 和项目上下文适配器生成结构化资料及来源索引。
-   调用 Superpowers `brainstorming`，由 `spec-agent` 生成 `spec.md` 和
    `decisions.md` 草稿。
-   校验需求 ID、来源定位、范围、验收标准和待确认事项。
-   等待用户确认 Spec；未确认不得进入正式开发。
-   审批时重新计算 Spec SHA256，生成不可变的 Spec Baseline。
-   已批准 Spec 的变更必须创建 Change Request 和新版本，不允许 Agent
    原地覆盖。

**B. 执行控制中心（Agent Execution Controller）**

-   由 LangGraph 负责主状态机、节点编排、条件路由和 Checkpoint。
-   由 `orchestrator-agent` 生成统一 `task_context` 并调度四个专业子
    Agent。
-   Spec 审批后调用 Superpowers `using-git-worktrees`、`writing-plans`。
-   生成 `tasks.md`，再调用 DocLoop `checklist-create` 生成
    `checkList.md`。
-   按任务依赖调用 `implement-agent`，执行 Superpowers TDD 和 Subagent
    工作流。
-   按"实现 → 独立验证 → 证据审查"顺序调度 `verify-agent` 和
    `review-agent`。
-   每个 Task 的代码变更、测试结果、审查结论必须关联稳定 ID 和 Git
    Commit。

**C. 可靠性控制中心（Agent Reliability & Recovery Controller）**

-   监控模型调用、Agent、Skill、MCP、CLI、Git、构建和测试异常。
-   对网络超时、限流等瞬时错误执行有限重试。
-   对编译、测试、接口、UI 和代码审查问题调用 Superpowers
    `systematic-debugging`。
-   为每个 Task 设置修复轮次、Token、时间、工具调用和并发预算。
-   通过 Error Fingerprint 和 Progress Detector
    识别重复错误及无进展循环。
-   超出预算、权限拒绝、关键业务信息缺失时进入 `blocked` 或
    `needs_input`，保存 Checkpoint 和现场。
-   不得通过跳过测试、删除断言、修改已批准 Spec 或放宽 Rules 伪造成功。

### 0.3 DocLoop Agent 目录结构

``` text
项目根目录/
├── AGENTS.md
├── .docloop/
│   ├── project.yaml
│   ├── agents/
│   ├── rules/
│   │   ├── code-standard.md
│   │   ├── api-standard.md
│   │   ├── ui-standard.md
│   │   └── verification-standard.md
│   ├── skills/
│   ├── profiles/
│   ├── changes/<change-id>/
│   │   ├── spec.md
│   │   ├── decisions.md
│   │   ├── tasks.md
│   │   ├── checkList.md
│   │   └── evidence.yaml
│   ├── sessions/
│   ├── checkpoints/
│   ├── traces/
│   └── recovery/
├── 文档/变更记录/<change-id>/
└── src/、frontend/、backend/
```

-   `.docloop/rules/` 是规则唯一事实来源（SSOT）。
-   `.docloop/skills/` 存放 DocLoop 自定义 Skills；Superpowers 上游
    Skills 由运行时按锁定版本加载。
-   `.docloop/changes/<change-id>/` 是当前变更的活动工作区。
-   验收后将正式产物归档到 `文档/变更记录/<change-id>/`，归档保留 Hash
    和版本信息。
-   `.docloop/sessions/`、`checkpoints/`、`traces/`、`recovery/`
    保存运行数据，不与业务代码混杂。

### 0.4 Superpowers 与 DocLoop 工作流映射

  ---------------------------------------------------------------------------------------------------------------------------------------------
  阶段         DocLoop 调度                              Superpowers 能力                                           产物 / 门禁
  ------------ ----------------------------------------- ---------------------------------------------------------- ---------------------------
  输入读取     `orchestrator-agent`、`document-parser`   ---                                                        Source Bundle、来源索引

  需求分析     `spec-agent`                              `brainstorming`                                            `spec.md`、`decisions.md`
                                                                                                                    草稿

  Spec 审批    需求控制中心                              ---                                                        Spec
                                                                                                                    Hash、审批记录、Baseline

  工作区准备   `orchestrator-agent`                      `using-git-worktrees`                                      隔离 Branch / Worktree

  任务规划     `orchestrator-agent`                      `writing-plans`                                            `tasks.md`

  测试规划     `checklist-create`                        TDD 思路                                                   `checkList.md`

  代码实现     `implement-agent`                         `subagent-driven-development`、`test-driven-development`   代码 Diff、快速检查

  故障修复     可靠性控制中心                            `systematic-debugging`                                     修复记录、复测结果

  独立验证     `verify-agent`                            `verification-before-completion`                           `evidence.yaml`

  代码审查     `review-agent`                            `requesting-code-review`、`receiving-code-review`          审查报告

  最终交付     `orchestrator-agent`                      `finishing-a-development-branch`                           归档、交付报告
  ---------------------------------------------------------------------------------------------------------------------------------------------

**强制顺序：**

`需求输入 → Brainstorming → Spec 草稿 → 用户审批 → Spec Baseline Lock → Worktree → Writing Plans → tasks.md → checkList.md → Implement/TDD → Verify → Review → Accepted/Archive`

不得在 Spec
未批准时生成正式可执行开发任务或修改业务代码。需求澄清阶段可以输出草稿和待确认问题，但不能把推测写成已确认需求。

### 0.5 状态分层

Change 生命周期状态：

``` text
draft → ready → in_progress → implemented → verified → accepted
```

扩展状态：`blocked`、`failed`、`cancelled`、`needs_input`。

-   `draft`：Spec 草稿阶段，尚未审批。
-   `ready`：Spec 已审批并锁定，任务和测试计划通过结构校验。
-   `in_progress`：至少一个 Task 已开始执行。
-   `implemented`：实现者完成代码修改和快速检查，不代表验收通过。
-   `verified`：独立验证者确认强制验证项通过并写入证据。
-   `accepted`：验证通过、审查通过、无阻塞项，主 Agent 完成验收。
-   `blocked`：权限、环境、外部依赖或业务决策阻塞。
-   `failed`：不可恢复的系统或执行失败。
-   `cancelled`：用户主动取消。
-   `needs_input`：缺少必须由用户提供的业务信息。

`implement-agent` 最多将任务推进到 `implemented`；只有 `verify-agent`
可以给出独立验证结论；只有验证和审查均通过后，`orchestrator-agent`
才能标记 `accepted`。

### 0.6 Superpowers 上游 Skills 调用规则

-   `brainstorming`：需求探索和 Spec 草稿，不直接修改业务代码。
-   `using-git-worktrees`：Spec 审批后创建隔离工作区。
-   `writing-plans`：Spec 审批后生成任务计划。
-   `subagent-driven-development`：将独立 Task 分配给实现子 Agent。
-   `test-driven-development`：实现任务先定义或运行针对性测试，再完成代码。
-   `systematic-debugging`：处理编译、测试、接口、UI 和运行时问题。
-   `requesting-code-review` /
    `receiving-code-review`：组织审查并处理意见。
-   `verification-before-completion`：最终结论必须有真实验证证据。
-   `finishing-a-development-branch`：质量门禁通过后整理分支和交付。

上游 Skills 必须锁定版本或 Commit
SHA；升级时执行兼容性和回归测试。不得复制多份上游 Skill
文件造成版本漂移。

### 0.7 项目 Profile 与规则适用范围

本文后续的代码、API、UI、安全规则保留原有企业项目约定，但不是所有技术栈项目的全局默认值。DocLoop
必须通过 `AGENTS.md` 或 `.docloop/project.yaml` 显式选择项目
Profile。Vue 3、Java 8、MyBatis Plus、FastJSON、Log4j2、特定端口、UI
组件库和品牌设计令牌仅适用于匹配的企业项目。其他项目不得自动套用。未配置
Profile 时，先识别项目现有技术栈和相邻实现，不得臆造规范。

### 0.8 Change 文档契约

每个 Change 必须维护：

-   `spec.md`：需求、范围、约束、来源和验收标准。
-   `decisions.md`：已确认决策、待确认问题、风险和阻塞项。
-   `tasks.md`：任务、依赖、文件范围和完成条件。
-   `checkList.md`：测试用例和验证计划。
-   `evidence.yaml`：实际验证命令、观察值和证据引用。

统一路径：`.docloop/changes/<change-id>/`。

追踪链必须完整：

``` text
REQ-001 → AC-001 → TASK-001 → TC-001 → V-001 → evidence.yaml → Commit SHA
```

### 0.9 可靠性控制硬性约束

可靠性控制必须由程序实施，不能只依赖 Prompt：

-   普通瞬时错误默认最多重试 3 次。
-   每个 Task 默认最多 3 轮完整自动修复。
-   相同错误指纹重复出现且无进展时停止当前修复路径。
-   连续 2 轮无有效进展时停止原地循环。
-   分别限制 LLM 调用、Token、工具调用、Task 时长、Run 总时长、Subagent
    并发和 LangGraph 图执行步数。
-   LangGraph recursion limit、模型轮次和修复轮次必须分别配置。
-   外部 MCP/API 连续失败时使用 Circuit Breaker。
-   `blocked` 时保存 Checkpoint、Git
    Diff、日志、错误指纹、修复历史和下一步建议；不得自动无限唤醒重试。

## 一、体系总览

### 1.1 目录结构约定

``` text
项目根目录/
├── AGENTS.md
├── .docloop/
│   ├── project.yaml
│   ├── docs/                       # 项目设计资料和参考文档
│   ├── agents/                     # 五个 Agent 的角色定义
│   ├── rules/                      # 强制规范（SSOT）
│   │   ├── code-standard.md
│   │   ├── api-standard.md
│   │   ├── ui-standard.md
│   │   └── verification-standard.md
│   ├── skills/                     # DocLoop 自定义 Skills
│   ├── profiles/                   # 企业/项目技术栈 Profile
│   ├── changes/<change-id>/
│   │   ├── spec.md
│   │   ├── decisions.md
│   │   ├── tasks.md
│   │   ├── checkList.md
│   │   └── evidence.yaml
│   ├── sessions/
│   ├── checkpoints/
│   ├── traces/
│   └── recovery/
├── 文档/变更记录/<change-id>/        # 已验收变更的正式归档
└── src/、frontend/、backend/
```

活动变更统一写入 `.docloop/changes/<change-id>/`；已验收产物归档到
`文档/变更记录/<change-id>/`。不得再使用旧的 `specs/<change-id>/`
作为第二套事实来源。

### 1.2 状态机

    draft → ready → in_progress → implemented → verified → accepted

门禁规则：

-   有阻塞决策时停止，不得自行扩大业务假设。
-   implement-agent 最多输出 `implemented`，是否 `verified` 由
    verify-agent 独立判定。
-   验证项未全部通过时不得输出 `verified`。
-   `failed`、`blocked`、`not_run` 不得包装为完成。

### 1.3 DocLoop Agent 工作流

**自动模式：**

``` text
task_context
→ document-parser / Source Bundle
→ spec-agent（调用 Superpowers brainstorming）
→ spec.md + decisions.md（draft）
→ Spec Validation
→ 用户审批 / SHA256 基线锁定
→ using-git-worktrees
→ orchestrator-agent 调用 writing-plans
→ tasks.md
→ checklist-create
→ checkList.md
→ implement-agent（Subagent + TDD）
→ verify-agent（独立验证并写 evidence.yaml）
→ review-agent（审查代码和验证证据）
→ 汇总状态、归档和交付
```

**分步模式：** Spec 草稿完成后等待用户确认；Spec
审批通过后才生成正式任务计划；可按项目配置在任务规划或每个 Task
批次后设置人工检查点。验证必须发生在最终审查之前。

**审查模式：** 纯代码审查请求直接调
`review-agent`，不擅自修改代码。若用户要求确认运行状态、功能验收或测试结论，必须先调
`verify-agent` 生成独立证据，再交由 `review-agent`
审查。修复后必须重新验证和审查。

**可靠性接管：**
任一阶段发生错误，由可靠性控制中心分类。普通技术错误进入有限重试和
Systematic Debugging；需求歧义、权限拒绝、安全策略冲突或外部依赖缺失进入
`blocked` / `needs_input`。恢复后从最近有效 Checkpoint 继续。

------------------------------------------------------------------------

## 二、五个 Agent 定义

### 2.1 orchestrator-agent（项目主 Agent）

**职责：**

1.  按 `AGENTS.md` 判断任务领域和模式。
2.  生成统一 `task_context`，明确规则、Skill、验证项和阻塞项。
3.  只调度流程，不重复维护专业规则或代码模板。
4.  确保状态按
    `draft → ready → in_progress → implemented → verified → accepted`
    推进。

**Skill 路由：**

  需求                  Skill
  --------------------- --------------------------
  DOCX/PDF/图片解析     `document-parser`
  Vue 页面和组件        `component-generator`
  API 契约 / 前端 API   `api-contract`
  后端分层实现          `backend-code-generator`
  视觉提升              `frontend-design`
  UI 专项质量           `frontend-quality-check`
  安全专项              `security-check`

只把任务实际需要的 Skill 加入 `task_context.skills`。

**最终输出：**

``` yaml
任务结果:
  change_id: ""
  status: "implemented|verified|accepted|failed|blocked"
  artifacts: []
  changed_files: []
  rules_loaded: []
  skills_used: []
  verification_evidence: ""
  remaining_risks: []
```

------------------------------------------------------------------------

### 2.2 spec-agent（规格设计子 Agent）

**输入：** 主 Agent 生成的 `task_context`、用户指令、`.docloop/docs/`
下的设计资料。

**规则：**

1.  读取 `AGENTS.md` 和 `task_context.rules`
    允许的规则；禁止读取排除规则。
2.  Markdown 可直接读取；DOCX、PDF、图片或扫描件调用 `document-parser`。
3.  只扫描与需求直接相关的目录，同类参考文件读取 1---2 个。
4.  每条需求、决策和验收标准保留稳定 ID 及来源定位。
5.  不明确的表结构、接口复用、权限、数据来源或业务规则列为待确认问题。
6.  存在影响实现的未决问题时输出 `blocked`，不得用常规 CRUD
    假设代替业务决策。

**流程：**

1.  定位并解析需求来源，生成来源索引。
2.  根据 `task_context.domains` 提取对应领域需求，忽略非相关规则。
3.  扫描现有组件、页面、API、Controller、Service、Mapper
    和工具类的可复用模式。
4.  明确 In Scope、Out of
    Scope、数据模型、接口契约、页面/交互和非功能要求。
5.  为每个功能点定义可验证的验收标准。
6.  输出技术决策、文件变更清单、禁止修改清单、依赖关系和分批实现顺序。

**持久化产物：** 写入 `.docloop/changes/<change-id>/`

-   `spec.md`：范围、需求、来源、数据、接口、页面和验收标准
-   `decisions.md`：已确认决策、待确认问题、阻塞项和风险
-   `tasks.md`：Spec 审批后由 orchestrator-agent 调用 Superpowers
    `writing-plans` 生成正式任务计划。
-   `checkList.md`：由 DocLoop `checklist-create` 在 tasks.md
    生成后创建。
-   `evidence.yaml`：由 verify-agent 在独立验证时生成。

**输出：**

``` yaml
规格结果:
  change_id: ""
  status: "draft|blocked"
  spec_path: ".docloop/changes/<change-id>/spec.md"
  decisions_path: ".docloop/changes/<change-id>/decisions.md"
  tasks_path: null
  rules_loaded: []
  skills_used: []
  reusable_items: []
  blocked_by: []
```

------------------------------------------------------------------------

### 2.3 implement-agent（代码实现子 Agent）

**输入：** `task_context`、已锁定的 Spec Baseline，以及
`.docloop/changes/<change-id>/` 下的 `spec.md` / `decisions.md` /
`tasks.md` / `checkList.md`。必须使用 Superpowers
`test-driven-development`；适合拆分的任务使用
`subagent-driven-development`。

**职责：**

1.  校验状态为 `ready` 且无阻塞项。
2.  按 Superpowers `writing-plans` 生成的 Tasks 顺序执行，每批不超过 5
    个文件；扩大文件范围前必须更新任务计划并记录原因。
3.  优先复用 Spec 列出的现有组件、函数、类和模式。
4.  严守禁止修改清单，不做任务外重构。
5.  根据文件类型调用 Skill：
    -   Vue 组件/页面：`component-generator`
    -   API 契约与前端 API 封装：`api-contract`
    -   后端分层代码：`backend-code-generator`
6.  只加载 `task_context.rules` 允许的规则。

**快速反馈：**

-   后端批次：编译受影响模块。
-   前端批次：执行构建。
-   UI/API 快速检查仅在对应领域存在时执行。
-   快速反馈用于及时修复实现错误，不构成最终验收。

**输出：**

``` yaml
实现结果:
  status: "implemented|failed|blocked"
  changed_files: []
  skills_used: []
  quick_checks: []
  remaining_risks: []
```

完成后状态最多为 `implemented`，由 verify-agent 独立决定是否达到
`verified`。

------------------------------------------------------------------------

### 2.4 verify-agent（独立验证子 Agent）

**输入：** `task_context`、spec.md、implement-agent
输出的变更文件清单和快速检查结果。

**规则：**

1.  读取 `AGENTS.md`、`.docloop/rules/verification-standard.md` 和
    `task_context.rules`。
2.  只执行 `task_context.verification` 列出的检查。
3.  不修改业务代码；发现失败时返回 implement-agent。
4.  不采信实现者的"已通过"描述，必须独立观察结果。
5.  无法执行时标记 `blocked` 或 `not_run`，不得推定通过。

**流程：**

1.  从 Spec 提取验收标准 ID。
2.  建立"验收标准 → 验证检查"映射，发现无覆盖项时直接失败。
3.  按 `.docloop/rules/verification-standard.md` 执行分类验证。
4.  将命令结果、实际观察值和限制写入
    `.docloop/changes/<change-id>/evidence.yaml`。
5.  只有全部强制检查通过且无阻塞问题时，输出 `verified`。

**输出：**

``` yaml
验证结果:
  状态: "verified|failed|blocked"
  证据路径: ".docloop/changes/<change-id>/evidence.yaml"
  通过检查: []
  失败检查: []
  未执行检查: []
  剩余风险: []
```

------------------------------------------------------------------------

### 2.5 review-agent（代码审查子 Agent）

**输入：** `task_context`、Spec/决策/任务文件、implement-agent
的变更文件清单、verify-agent 生成的 `evidence.yaml`、UI 任务下的
`frontend-quality-check` 结果、安全任务下的 `security-check` 结果。

**审查边界：**

1.  只审查变更文件及必要的 1---2 个参考文件。
2.  通用检查：禁区、命名、重复代码、无用抽象、异常处理、敏感信息和任务外修改。
3.  后端检查：Controller/Service/Mapper 分层、事务边界和 Mapper 映射。
4.  API 检查仅在 API 领域执行：路径、方法、参数和响应契约。
5.  UI 专项检查交给 `frontend-quality-check`，不在此重复维护 UI 清单。
6.  安全专项检查交给 `security-check`，普通审查不宣称完成等保评估。
7.  验证执行属于 verify-agent；本 Agent 只审查证据覆盖度和结论是否可信。

**门禁：**

-   每个验收标准必须关联证据。
-   `failed`、`blocked`、`not_run` 不得表述为通过。
-   发现代码问题时返回 implement-agent；修复后重新验证和审查。

**输出：**

``` yaml
审查报告:
  status: "passed|changes_required|blocked"
  reviewed_files: []
  findings:
    critical: []
    required: []
    suggestions: []
  missing_evidence: []
  remaining_risks: []
```

------------------------------------------------------------------------

## 三、四份 Rules 规范

### 3.1 前后端代码规范（code-standard.md）

> SSOT：所有代码任务必须遵守。项目结构和技术栈以 `AGENTS.md`
> 为准；UI、API 和验证专项规则按 `task_context` 条件加载。

#### 通用原则

1.  优先复用现有组件、函数、类和相邻模块模式。
2.  只修改任务范围内文件，禁止顺手重构。
3.  使用最小、可回滚的实现，不做当前需求不需要的抽象。
4.  函数保持单一职责，通常不超过 50 行；参数超过 4 个时使用对象。
5.  使用卫语句减少嵌套。
6.  禁止硬编码魔法值，使用常量、枚举或设计令牌。
7.  关键代码添加中文注释，解释"为什么"；公共方法使用 JSDoc/Javadoc。
8.  不吞掉异常，不保留空 catch。

#### 命名规范

**前端：**

  类型          规范                     示例
  ------------- ------------------------ ------------------------
  组件          PascalCase               `UserList.vue`
  页面          模块目录下 `index.vue`   `views/user/index.vue`
  JS/工具文件   camelCase                `formatDate.js`
  Composable    `use` + camelCase        `useTable.js`
  变量          camelCase                `tableData`
  布尔值        is/has/can 前缀          `isLoading`
  常量          全大写下划线             `MAX_PAGE_SIZE`
  函数          动词+名词                `fetchUserList`
  事件          handle 前缀              `handleSubmit`

**后端：**

  类型              规范
  ----------------- ------------------------------
  Controller        `XxxEndpoint`
  Service 接口      `IXxxService`
  Service 实现      `XxxServiceImpl`
  Mapper 接口/XML   `XxxMapper`、`XxxMapper.xml`
  Model             `Xxx`
  工具类            `XxxUtil` / `XxxUtils`

方法使用
`get/list/select`、`add/save/insert`、`update/modify`、`delete/remove`、`check/validate`
等明确动词。

#### 前端代码要点

-   使用 ES6+，优先 `const/let`、箭头函数、解构、可选链和空值合并，禁止
    `var`。
-   Vue 组件使用 `<script setup>`，结构顺序为 script → template → scoped
    SCSS。
-   Props 定义类型和默认值，Emits 显式声明。
-   `v-for` 使用稳定唯一 key；不得与 `v-if` 放在同一元素。
-   样式使用 `scoped`，深度选择器使用 `:deep()`。
-   页面私有状态使用 ref/reactive 或 composable；只有跨页面共享状态进入
    Pinia。
-   Store 命名为 `useXxxStore`，避免在 Store 中操作 DOM 或执行页面跳转。
-   路由名使用 kebab-case，路由组件懒加载。
-   环境变量以 `VITE_` 开头，敏感信息禁止硬编码。
-   定时器、事件监听和其他副作用在组件卸载时清理。
-   长列表考虑虚拟滚动，大组件和路由按需加载。

#### 后端分层（强制）

    Endpoint → Service → Mapper → Model

-   Endpoint 只接收/校验参数、调用 Service
    和返回结果，**绝对禁止直接操作 Mapper**。
-   Service 处理业务逻辑和事务，接口继承 `IService<T>`，实现继承
    `ServiceImpl<Mapper,T>`。
-   需要事务的方法使用 `@Transactional(rollbackFor = Exception.class)`。
-   Mapper 继承 `BaseMapper<T>`；自定义参数使用 `@Param`。
-   Mapper XML 的 namespace 必须是 Mapper 接口全限定名。
-   XML 定义 `BaseResultMap` 和 `Base_Column_List`；分页交给现有 MyBatis
    Plus 分页插件。
-   Model 使用 `@TableName`、`@TableId`、必要的 `@TableField`，包含
    `serialVersionUID` 和 getter/setter。
-   使用 Java 8 语法、4 空格缩进和 K&R 大括号风格。

#### 异常、日志和敏感信息

-   前端异步操作使用 `try/catch/finally`，失败给出友好提示，finally 恢复
    loading。
-   后端异常至少记录日志并返回友好信息，禁止向客户端暴露堆栈、SQL、密码或内部配置。
-   后端使用 Log4j2，禁止 `System.out.println`。
-   前端禁止遗留调试 `console.log` 和
    `debugger`；必要错误日志不得包含敏感数据。
-   密码、密钥、Token 和数据库连接信息不得硬编码或写入日志。

#### 性能

-   高频事件使用防抖/节流；无依赖异步任务可并行。
-   避免重复请求和无效计算，合理使用缓存。
-   大表查询必须分页，避免 N+1 和无条件全表扫描。
-   批量操作优先批量 SQL，合理利用索引。
-   Redis/Ehcache 只缓存适合的数据，并保持失效策略明确。

#### 文件与禁区

-   禁止在项目中生成无关临时脚本、截图、临时 node_modules、缓存或 `_tmp`
    目录。
-   临时验证产物放在工作区外，使用后清理。
-   可追溯 Spec 产物放在 `.docloop/changes/<change-id>/`。
-   不生成任务未要求的 README、示例、辅助脚本或备份文件。

**前端禁区：**
`src/main.js`、`src/App.vue`、`src/service/request.js`、`vite.config.js`、`.env.*`、`package.json`、`package-lock.json`

**后端禁区：** 根目录和模块
`pom.xml`（明确需要新增依赖时除外）、`application.yml`、`log4j2.xml`、`ehcache.xml`、`BaseController.java`
等公共框架类

#### 验证与提交

-   验证项由 `task_context.verification` 和 `verification-standard.md`
    决定，禁止执行非相关领域检查。
-   实现者快速检查不能替代 verify-agent 的独立证据。
-   提交前移除调试代码、格式化变更并确认对应构建/编译结果。
-   提交信息简洁说明前端、后端或全栈范围。
-   禁止提交任务外文件。

------------------------------------------------------------------------

### 3.2 前后端接口规范（api-standard.md）

> SSOT：API 任务必须遵守。即使被自动加载，非 API 任务也必须按
> `AGENTS.md` 忽略本文件。

#### 基础路径

-   前端开发代理：`/api` → `http://localhost:8081/main`。
-   yi-main-web：端口 `8081`，context-path `/main`。
-   yi-auth-server：端口 `8098`，context-path `/authserver`。
-   前端业务 API 路径不包含 `/main`，由代理负责重写。
-   生产地址从环境配置读取，禁止在业务代码中硬编码。

#### 响应与分页（强制）

``` json
{"code": 200, "message": "success", "data": {}}
{"code": 500, "message": "错误信息"}
{"code": 0, "count": 100, "data": []}
```

  场景       code   必需字段
  ---------- ------ ---------------
  普通成功   200    message、data
  失败       500    message
  分页成功   0      count、data

-   分页参数固定为 `page` 和 `limit`，页码从 1 开始，默认
    `page=1`、`limit=20`。
-   日期使用时间戳或 `yyyy-MM-dd HH:mm:ss`，同一接口前后端保持一致。
-   状态值和空值语义必须在 Spec 中明确，前后端保持一致。

#### 前端 API 封装

-   API 统一放在 `frontend/src/api/`，按业务模块划分。
-   必须使用 `src/service/request.js` 封装的 service
    实例，禁止直接使用原生 axios。
-   查询参数使用 `params`，请求体使用 `data`。
-   参数默认值使用 `params = {}`、`data = {}`，避免传递 undefined。
-   公共字典、上传和导出优先复用现有公共 API。
-   函数添加 JSDoc，说明参数和返回值。

**命名前缀：**

  操作        前缀
  ----------- ----------------------------------
  列表/详情   get、fetch、list
  新增        create、add
  修改        update、modify
  删除        delete、remove
  字典/选项   dict、options
  文件        export、import、upload、download

**请求类型：**

  类型   配置
  ------ -------------------------------------------------
  JSON   `dataType: 'json'`
  上传   `dataType: 'upload'` + FormData，可提供进度回调
  下载   `responseType: 'blob'`

#### 后端接口实现

-   Controller 命名为 `XxxEndpoint`，使用
    `@RestController`、`@RequestMapping` 并继承 `BaseController`。
-   使用 `@Resource` 或现有项目统一方式注入 Service。
-   Controller 只接收和校验参数、调用 Service、返回结果，禁止直接操作
    Mapper。
-   普通/GET 参数使用 `@RequestParam` 或项目现有 Map 形式；JSON
    请求体使用 `@RequestBody`。
-   参数校验失败返回 `code=500` 和明确、友好的 message。
-   返回使用项目现有 FastJSON `JSONObject` 格式。
-   Service 处理业务逻辑和事务；需要原子性的写操作使用
    `@Transactional(rollbackFor = Exception.class)`。
-   异常必须记录日志，禁止向客户端暴露敏感堆栈或内部配置。

**路径沿用项目约定：**

  操作        路径
  ----------- -----------------------------
  列表        `/xxx/list`
  详情        `/xxx/detail`
  新增        `/xxx/add`
  修改        `/xxx/update`
  删除        `/xxx/delete`
  字典/选项   `/xxx/dict`、`/xxx/options`

-   前端 API 路径必须与后端 `@RequestMapping` 完全一致。
-   本项目存在历史 POST 风格，不强制改造成
    RESTful；优先保持相邻接口风格一致。

#### 前端调用

-   使用 `try/catch/finally` 管理异常和 loading。
-   全局网络错误由 request 拦截器处理；业务错误在调用处给出友好提示。
-   禁止空 catch。
-   表单提交和数据变更成功后提示；常规列表查询不提示成功。
-   调用前校验关键参数并格式化日期、数字等字段。
-   高频搜索使用约 `300ms` 防抖，组件卸载时取消。
-   无依赖请求使用 `Promise.all`；字典等低频变化数据可缓存。

#### 文件接口

-   上传使用 FormData，校验类型、大小和业务必填项。
-   下载/导出使用 blob，正确处理文件名和失败响应。
-   文件名可加入时间戳，避免浏览器缓存或覆盖。

#### 环境与拦截器

-   开发环境基础地址使用 `/api`，代理重写为 `/main`。
-   环境变量以 `VITE_` 开头，生产地址由部署配置提供。
-   `vite.config.js`、`.env.*` 和 `src/service/request.js`
    属于禁区，除非用户明确要求。
-   GET 防缓存、登录超时和公共请求头沿用现有 request 拦截器，不在业务
    API 重复实现。

#### 联调门禁

API
验证必须覆盖：路径和请求方法一致；参数名、位置、类型和必填性一致；分页参数为
`page/limit`；普通、分页和失败响应格式一致；日期、状态值和空值语义一致；文件接口的
content type、文件名和错误响应正确。

未覆盖的契约不得进入 `verified`。

------------------------------------------------------------------------

### 3.3 前端 UI 设计规范（ui-standard.md）

> SSOT：UI 任务必须遵守。违反强制规则的代码不得交付。

#### 原则与组件库

-   同类型页面保持结构、组件和交互一致。
-   PC 优先，默认适配桌面端，同时保证移动端基本可用。
-   用户操作必须有明确反馈。
-   使用设计令牌，禁止硬编码非标准颜色、字号、间距和尺寸。
-   组件库优先级：tkui-plus → Element Plus；沿用项目已有 PrimeVue
    组件，不新增其他 UI 库。
-   禁止新增 Ant Design Vue、Naive UI、Vuetify、View UI 等 UI 库。
-   图标优先级：项目 iconfont → Element Plus 图标。
-   顶部导航图标使用 Element Plus 图标，禁止 emoji
    或特殊字符；通知图标支持 `el-badge` 未读角标。

#### 设计令牌

**色彩：**

  类型             值
  ---------------- -----------
  主色（铁科蓝）   `#013f97`
  辅色（铁科绿）   `#90c31e`
  成功             `#67C23A`
  警告             `#E6A23C`
  危险             `#F56C6C`
  信息             `#909399`
  主文字           `#303133`
  常规文字         `#606266`
  次要文字         `#909399`
  占位文字         `#C0C4CC`
  一级边框         `#DCDFE6`
  二级边框         `#E4E7ED`
  页面背景         `#F5F7FA`
  表格斑马纹       `#FAFAFA`

-   品牌主色用于主要按钮、选中态和重点信息。
-   危险色只用于删除、错误和高风险操作。
-   图表使用品牌色及功能色形成统一色板，禁止直接采用组件默认随机配色。
-   渐变只用于品牌强调或统计展示，常规表单和表格保持平面清晰。

**排版：**

  类型       字号/行高     字重
  ---------- ------------- ------
  页面标题   `20px/30px`   600
  区块标题   `16px/24px`   600
  正文       `14px/22px`   400
  辅助文字   `12px/20px`   400

-   表格数字和状态通常居中；名称、描述等文本左对齐；金额和统计数字右对齐。

**圆角、阴影和动效：**

  ------------------------------------------------------------------------------------
  项目                规则
  ------------------- ----------------------------------------------------------------
  按钮圆角            `2px`

  输入框圆角          `2px`

  默认卡片阴影        `0 1px 3px rgba(1,63,151,0.04), 0 1px 2px rgba(1,63,151,0.02)`

  常规过渡            `0.2s`
  ------------------------------------------------------------------------------------

-   动效用于反馈和层级表达，禁止无意义连续动画。
-   尊重 `prefers-reduced-motion`。

#### 间距系统（强制）

  名称   SCSS 变量         像素
  ------ ----------------- ------
  xs     `$spacing-xs`     4
  sm     `$spacing-sm`     8
  md     `$spacing-md`     12
  base   `$spacing-base`   16
  lg     `$spacing-lg`     24
  xl     `$spacing-xl`     32

-   所有间距从 `4/8/12/16/24/32px` 中选择，**禁止** `5/10/14/15/18/20px`
    等非标准值。
-   flex/grid 子元素间距优先使用父容器 `gap`。
-   同一方向禁止同时使用父 `gap` 和子元素 `margin`。
-   平级区块间距由父容器控制，禁止子元素各自设置 `margin-bottom`。
-   容器上下 padding 必须对称；禁止通过按钮单独底部 margin 制造不对称。

**常用值：**

  场景               间距
  ------------------ ------
  页面内容 padding   16px
  卡片间距           16px
  查询区与表格       16px
  查询项横向         16px
  查询项换行纵向     12px
  按钮组内部         8px
  弹窗内容 padding   24px
  分页与表格         16px
  左树与右表         16px

#### 布局

-   页面默认采用 Flexbox。
-   多卡片同行禁止使用 `el-row/el-col`，使用
    `display:flex; gap:16px; align-items:stretch`。
-   等宽列使用 `flex:1; min-width:0`。
-   纵向页面使用 `display:flex; flex-direction:column; gap:16px`。
-   需要占满剩余高度的区域使用 `flex:1; min-height:0; overflow:hidden`。
-   flex 内独立滚动元素必须设置 `min-height:0` 或 `min-width:0`。
-   表格卡片必须占满内容区宽度。
-   左树右表优先复用 `TreeTableLayout`：左树默认宽度 `240px`，左右间距
    `16px`，左右容器设置 `min-width:0`。

#### 查询区域（强制）

-   优先复用 `SearchForm`。
-   `.search-form` 不设置 `margin-bottom`；与表格间距由页面父容器
    `gap:16px` 控制。
-   `.el-form--inline` 使用 `gap:12px 16px`。
-   查询、重置按钮放在条件行最后，通过 `margin-left:auto` 居右。
-   查询区上下 padding 均为 `16px`。
-   label 默认宽度 `88px`；超过 7 个汉字的标签可统一扩展为
    `110px`。同一页面 label 宽度必须统一。
-   输入框、选择器默认宽度 `200px`、高度 `32px` 并保持顶部对齐。
-   日期范围组合占两列，整体约 `416px`，内部控件各约 `200px`。
-   搜索输入框使用 `clearable`；下拉选项超过 8 项时使用 `filterable`。
-   查询条件超过 2 行时必须支持折叠：默认显示前 2 行。

#### 通用组件

**按钮：** 查询区和顶部按钮使用默认 `32px` 高度，禁止
`size="small"`；按钮文字使用明确业务动作，避免"OK"；同组按钮间距
`8px`；危险操作使用危险样式并配合二次确认；移动端可点击区域至少
`44×44px`。

**表格（强制）：**

-   主表格不设置 `size="small"`，使用默认 `40px` 行高。
-   使用 `stripe`，背景 `#FAFAFA`；表头加粗并使用项目统一浅色背景。
-   表格 `width:100%`，禁止固定表格总宽度导致右侧留白。
-   标准 CRUD 页面中表格撑满剩余高度并内部滚动，禁止页面出现双滚动条。
-   表格及其父级 flex 链路设置 `flex:1; min-height:0; overflow:hidden`。
-   所有文本列单行显示，禁止换行撑大行高；超长文本使用
    `show-overflow-tooltip`。
-   列宽优先级：操作列 \> 名称/编号等主要列 \> 时间/备注等辅助列。
-   操作列使用 `fixed="right"`，按钮不得被遮挡或换行。
-   表格上方批量按钮组使用 `margin-left:auto`
    右对齐；未选中数据时批量按钮必须 `disabled`。
-   必须处理 loading、空状态和错误状态。

**分页：** 默认每页 `20` 条；右对齐紧贴表格底部，与表格间距 `16px`；设置
`flex-shrink:0`。

**Dialog 和表单：** 默认宽度 `640px`、最小高度
`200px`；必须包含标题、关闭入口和底部操作区；弹窗内容 padding
`24px`；弹窗表单 label 统一 `100px` 右对齐；表单项超过 5
项时在表单上方统一提示"带 \* 为必填项"；校验失败必须定位并提示具体字段。

#### 反馈

-   表单提交、删除和数据变更成功后使用统一成功反馈。
-   常规列表查询不显示成功提示。
-   删除必须使用
    `ElMessageBox.confirm`，提示"确定要删除吗？删除后不可恢复。"
-   确认按钮文字使用"确定删除"等业务动作，禁止只写"确定"或"OK"。
-   加载达到 3 秒必须显示 loading，默认文案"加载中..."。
-   请求失败必须给用户友好提示，不得空 catch。

#### 开发期 Mock

-   后端未就绪或开发环境无有效数据时提供可切换 Mock，生产环境自动禁用。
-   Mock 字段、格式、业务关系和数量级与真实接口一致。
-   列表 Mock 至少 20 条，覆盖分页、不同状态和边界情况。
-   模拟 `200—500ms` 延迟以验证 loading。
-   禁止 Mock 逻辑进入生产环境，禁止仅提供 1---2 条无法验证分页的数据。

#### 响应式

-   断点沿用项目统一断点；必须检查 `1920px` 和 `1366px`。
-   间距保持固定 px 值，不用 vw/vh 按比例缩放。
-   查询条件自然换行，纵向间距仍为 `12px`。
-   表格小屏允许横向滚动，操作列保持固定。
-   禁止出现页面级横向溢出、内容截断或双滚动条。
-   移动端不依赖 hover 完成关键操作。

#### UI 验收

-   页面创建或修改后必须按 `verification-standard.md` 使用 DocLoop
    Browser Adapter（Playwright MCP / Chrome DevTools MCP） 验证。
-   禁止为了单次验收在业务仓库中手写临时 Playwright/Puppeteer
    脚本或保存临时截图。优先使用 DocLoop Browser Adapter
    进行交互式检查；项目已有 Playwright Test
    或需要长期回归的正式测试时，可以运行或提交受版本管理的测试用例。
-   必检：布局、颜色、字体、间距、主要交互、loading/空/错误状态、控制台错误和响应式。
-   使用 `browser_evaluate` 测量 Spec
    要求的尺寸；查询区与表格、同行卡片、左右分栏等标准间距应为
    `16px`，查询项换行纵向间距应为 `12px`。
-   控制台 error 必须修复；warning 需判断是否与本次修改相关并记录。
-   未满足 UI 验收证据时不得进入 `verified`。

------------------------------------------------------------------------

### 3.4 验证与证据规范（verification-standard.md）

> 目的：按任务分类选择验证项，并用可复核证据决定是否达到 `verified`。

#### 验证路由

  -----------------------------------------------------------------------------------
  领域              必须验证
  ----------------- -----------------------------------------------------------------
  UI                前端构建、浏览器视觉、交互、控制台、状态展示、关键尺寸测量

  API               编译/构建、接口路径、方法、参数、响应契约；可运行时执行接口调用

  纯前端逻辑        前端构建、针对性逻辑验证

  纯后端逻辑        目标模块编译、分层和针对性逻辑验证

  构建/依赖         对应项目构建

  文档/工作流配置   结构、引用、格式和冲突检查
  -----------------------------------------------------------------------------------

不得执行 `task_context.verification` 之外的领域验证。

#### 独立验证原则

1.  implement-agent 负责实现阶段的快速反馈，不负责最终验收。
2.  verify-agent 必须从 Spec、变更文件和 `task_context` 独立得出结论。
3.  review-agent 只在验证证据生成后进行最终审查。
4.  未执行、被阻塞或环境不可用的检查必须标为 `not_run` 或
    `blocked`，不得写成通过。

#### 证据格式

验证结果写入 `.docloop/changes/<change-id>/evidence.yaml`，并关联
`checkList.md` 中的 Test Case ID：

``` yaml
verification:
  change_id: ""
  status: "passed|failed|blocked"
  checks:
    - id: "V-001"
      requirement_ids: ["AC-001"]
      type: "build|compile|browser|api|static|human"
      command_or_method: ""
      result: "passed|failed|blocked|not_run"
      observed: ""
      evidence: ""
  failures: []
  remaining_risks: []
```

每项 `passed` 必须包含实际观察值或命令结果摘要。Markdown
勾选框不构成证据。

#### 完成门禁

-   所有阻塞问题已解决。
-   所有必须验证项均为 `passed`。
-   Spec 中每个验收标准至少关联一项验证证据。
-   构建或编译失败时状态必须为 `failed`。
-   环境无法启动时状态为 `blocked`，不得宣称功能已完成。

#### 领域验证要求

**UI：**

-   使用 DocLoop Browser Adapter（优先 Playwright MCP 或 Chrome DevTools
    MCP）检查页面，不编写临时 Playwright/Puppeteer 脚本。
-   检查 1920px 和 1366px、控制台错误、主要交互、加载/空/错误状态。
-   使用 `browser_evaluate` 测量需求明确要求的间距和尺寸。
-   间距、布局和组件规则以 `ui-standard.md` 为准。

**API：**

-   接口路径、方法、参数位置和响应格式以 `api-standard.md` 为准。
-   修改 Controller 时检查注解与分层；修改 Mapper 时检查
    namespace/resultMap。
-   可以运行服务时执行代表性的成功、失败和分页调用；无法运行时明确记录限制。

**构建和编译：**

-   前端：`npm run build`
-   后端：优先编译受影响模块；需要跨模块验证时再编译全部模块。

------------------------------------------------------------------------

## 四、七个 Skills 定义

### 4.0 DocLoop 平台级工作流 Skills（与 Superpowers 配合）

以下平台级 Skills 与后续七个企业领域 Skills 分层管理。平台级 Skill
负责标准化流程和产物，领域 Skill 负责具体技术实现。

  -----------------------------------------------------------------------------------------
  Skill                  调用阶段            职责
  ---------------------- ------------------- ----------------------------------------------
  `document-parser`      输入解析            解析 DOCX/PDF/图片/Markdown 并保留来源

  `spec-create`          需求分析            封装 Superpowers `brainstorming`，生成标准
                                             Spec 草稿

  `plan-create`          任务规划            Spec 审批后封装 `writing-plans`，生成 tasks.md

  `checklist-create`     测试规划            根据 Spec、Tasks 和 Rules 生成 checkList.md

  `project-bootstrap`    工作区准备          检查项目、依赖、Git Worktree 和执行环境

  `test-runner`          快速检查/独立验证   按 task_context 调用项目构建、单测、接口和 UI
                                             验证

  `audit-recorder`       全流程              记录需求、Task、Diff、Commit、测试和审查关联

  `recovery-diagnosis`   故障恢复            错误分类、指纹识别、修复建议和恢复记录

  `project-archiving`    最终交付            归档正式文档、证据、版本清单和交付报告
  -----------------------------------------------------------------------------------------

每个自定义 Skill 的 `SKILL.md` 必须声明：名称、用途、触发条件、输入
Schema、允许工具、执行步骤、输出
Schema、失败处理、完成条件和禁止行为。Superpowers 上游 Skills
由运行时按锁定版本加载，不得复制多份维护。

### 4.1 document-parser（设计资料解析）

**用途：** 读取
Markdown、DOCX、PDF、图片或扫描件，提取文本、表格、页面结构和图片信息，并为结构化需求保留可追溯来源。用于设计文档实现、PRD
解析、截图还原或任何非纯文本需求来源。

**输入路由：**

1.  Markdown/纯文本：直接读取，保留标题和行号。
2.  DOCX：提取段落、标题、表格、图片及其顺序，不依赖手工解压目录。
3.  PDF：先判断文本型或扫描型；文本型提取文字与页码，扫描型执行 OCR
    并标记置信度。
4.  图片/截图：提取可见文字、区域、控件、标注和空间关系。

**输出契约：**

``` yaml
document:
  source: ""
  type: "markdown|docx|pdf|image"
  pages: 0
  sections: []
  tables: []
  images: []
  requirements:
    - id: "SRC-001"
      statement: ""
      source_locator: ""
      confidence: "high|medium|low"
  ambiguities: []
  parse_warnings: []
```

**约束：**

-   不根据文件名、目录名或常规 CRUD 模式臆造内容。
-   每条需求必须包含 `source_locator`。
-   OCR 或视觉判断不确定时降低置信度并加入 `ambiguities`。
-   不把解析阶段的推测标记为已确认需求。
-   临时解压、OCR 和渲染文件放在工作区外的临时目录，完成后清理。

------------------------------------------------------------------------

### 4.2 component-generator（Vue 组件和页面实现）

**用途：** 根据 Spec 复用或生成 Vue 3 组件、页面、表单和交互代码。仅用于
task_context 包含 UI 并选择本 Skill 的任务；UI 细节遵循 ui-standard.md。

**输入：** `task_context`、Spec 中的页面/组件/交互/验收标准
ID、目标文件、复用清单和 1---2 个相似实现。

**流程：**

1.  优先复用现有公共组件、composable 和页面模式。
2.  判断目标属于公共组件、业务组件或页面，选择现有目录结构。
3.  定义 Props、Emits、状态、计算属性、事件和父子组件契约。
4.  按 `code-standard.md` 实现 Vue 代码，按 `ui-standard.md`
    实现模板和样式。
5.  处理 loading、空、错误、禁用和提交反馈状态。
6.  返回修改文件及对应验收标准 ID。

**边界：**

-   不设计 API 契约；接口由 `api-contract` 提供。
-   不复制 ui-standard 中的颜色、间距或组件规则。
-   不新建已有能力的替代组件。
-   不执行最终浏览器验收。

**输出：**

``` yaml
组件实现:
  files: []
  reused: []
  requirement_ids: []
  self_check: []
```

------------------------------------------------------------------------

### 4.3 api-contract（API 契约设计与前端封装）

**用途：** 根据 Spec
定义路径、方法、参数、响应、分页和错误码，输出前后端字段映射及前端 API
封装。用于 task_context 包含 API
的接口设计、联调和契约变更；不生成后端分层实现。

**规则：**

1.  以 `.docloop/rules/api-standard.md` 为接口 SSOT。
2.  明确路径、方法、参数位置、字段类型、必填性、成功/失败和分页响应。
3.  保持前端字段、Java 字段和数据库字段映射清晰。
4.  优先复用现有公共接口和错误处理。
5.  可以生成前端 `src/api/` 封装和 Swagger/OpenAPI 描述。
6.  不生成 Entity、Mapper、Service 或 Controller 实现；后端代码交给
    `backend-code-generator`。

**输出：**

``` yaml
接口契约:
  api_id: ""
  path: ""
  method: ""
  request: {}
  response: {}
  error_codes: []
  frontend_api_file: ""
  backend_target: ""
  verification_points: []
```

------------------------------------------------------------------------

### 4.4 backend-code-generator（后端分层代码实现）

**用途：** 根据 Spec 和 API 契约生成或修改
Model、Mapper/XML、Service/Impl 和 Endpoint。仅用于 task_context 包含
backend 并选择本 Skill 的任务。

**流程：**

1.  确认表结构、字段映射、接口契约和权限决策已明确；未明确则返回
    blocked。
2.  优先复用现有 Model、Service、Mapper 方法和工具类。
3.  按 `code-standard.md` 实现 Model → Mapper/XML → Service/Impl →
    Endpoint。
4.  API 任务严格消费 `api-contract`，不重新设计路径、参数或响应。
5.  事务只放在需要原子性的 Service 方法。
6.  输出文件与模型/接口/验收标准 ID 映射。

**边界：**

-   不生成前端 API 封装或 Swagger 说明文档。
-   不自行决定表结构、接口复用、权限策略和业务状态含义。
-   不复制 code-standard 或 api-standard 中的完整代码模板。
-   不修改禁区文件，除非用户明确要求。

**输出：**

``` yaml
后端实现:
  files: []
  reused: []
  model_ids: []
  api_ids: []
  requirement_ids: []
  compile_target: ""
```

------------------------------------------------------------------------

### 4.5 frontend-design（前端视觉提升）

**用途：** 在 ui-standard
强制规则内选择排版、层级、构图、色彩节奏和动效方向。用于新页面、首页、统计页、数据大屏或用户明确要求视觉优化的
UI 任务。

**流程：**

1.  明确页面核心任务和第一视觉焦点。
2.  选择与业务匹配的排版密度、层级、留白和数据表达方式。
3.  优先通过字体层级、构图、空间节奏和信息分组提升质感。
4.  图表使用统一色板和明确标题、单位、图例与空状态。
5.  动效只服务反馈和状态变化，避免通用 AI
    式渐变、发光、悬浮卡片堆叠和无意义动画。
6.  输出可由 component-generator 直接落实的设计决策。

**边界：**

-   `ui-standard.md` 是强制 SSOT，冲突时以其为准。
-   不重复定义颜色、间距、按钮、表格或响应式规则。
-   不改变既有品牌、组件库和交互习惯。
-   普通修复任务不默认触发本 Skill。

**输出：**

``` yaml
视觉方案:
  primary_focus: ""
  hierarchy: []
  composition: ""
  typography: []
  color_usage: []
  motion: []
  reuse: []
```

------------------------------------------------------------------------

### 4.6 frontend-quality-check（前端 UI 专项质量检查）

**用途：** 检查 Vue
页面和组件的视觉还原、响应式、可访问性、交互状态和浏览器表现。仅用于
task_context 包含 UI 且明确选择本 Skill 的任务。

**检查范围：**

1.  视觉与布局：按 `ui-standard.md`
    检查颜色、字体、间距、层级和组件使用。
2.  响应式：检查规定分辨率、溢出、滚动区域和触摸目标。
3.  交互状态：检查加载、空、错误、禁用、提交和反馈状态。
4.  可访问性：检查语义标签、表单标签、键盘操作、焦点、alt 和必要 ARIA。
5.  浏览器表现：检查控制台错误、布局测量和主要交互证据。
6.  前端安全基线：仅报告明显危险的 `v-html`、不安全 URL
    和敏感日志；深度安全评估交给 `security-check`。

不重复执行构建，不检查后端，不代替 verify-agent 判定最终状态。

**输出：**

``` yaml
前端质量报告:
  status: "passed|changes_required|blocked"
  requirement_coverage: []
  findings:
    critical: []
    required: []
    suggestions: []
  evidence_gaps: []
```

------------------------------------------------------------------------

### 4.7 security-check（等保三级安全检查）

**用途：** 按照国家网络安全等级保护三级标准（GB/T
22239-2019）对系统进行全面安全检查。仅当用户明确要求安全审查，或
`task_context.skills` 包含 `security-check` 时执行。检查范围必须由
`task_context.domains`
限定；缺少部署、网络、主机或管理制度证据时，只能标记"未评估"，不得推定符合等保要求。

**检查范围：**

    安全技术要求
    ├── 1. 物理安全（机房环境）
    ├── 2. 网络安全（网络架构、访问控制、入侵防范）
    ├── 3. 主机安全（服务器操作系统、数据库）
    ├── 4. 应用安全（Web 应用、中间件）
    ├── 5. 数据安全（数据完整性、保密性、备份恢复）
    └── 6. 安全管理（管理制度、人员、运维）

    代码级检查（本技能重点）
    ├── 前端安全
    ├── 后端安全
    ├── API 安全
    ├── 数据库安全
    └── 依赖安全

#### 前端安全检查要点

  检查项            等保要求                                              风险等级
  ----------------- ----------------------------------------------------- ----------
  输入过滤          用户输入必须经过过滤/转义                             高
  输出编码          动态输出到 HTML 的内容必须编码（v-html、innerHTML）   高
  富文本过滤        富文本内容必须经过 XSS 过滤                           高
  URL 参数          URL 参数输出到页面时必须编码                          中
  Cookie 安全       Cookie 设置 HttpOnly 和 Secure                        中
  CSRF Token        关键操作使用 CSRF Token                               高
  SameSite          Cookie 设置 SameSite 属性                             中
  X-Frame-Options   设置 X-Frame-Options 响应头                           中
  控制台输出        生产环境不输出敏感信息到 console                      中
  环境变量          敏感配置不暴露给前端                                  高

**典型反例：**

``` javascript
// 危险：直接使用 v-html 渲染用户输入
<div v-html="userInput"></div>

// 危险：动态设置 href 可能是 javascript:alert(1)
<a :href="userUrl">链接</a>
```

**安全写法：**

``` javascript
// 使用文本插值（自动转义）
<div>{{ userInput }}</div>

// 富文本使用 DOMPurify 等库过滤
<div v-html="DOMPurify.sanitize(userInput)"></div>

// 校验 URL 协议
function isSafeUrl(url) {
  return /^https?:\/\//i.test(url)
}
```

#### 后端安全检查要点

  检查项         等保要求                                        风险等级
  -------------- ----------------------------------------------- ----------
  参数化查询     必须使用预编译 SQL，MyBatis 中禁止 `${}` 拼接   高
  密码存储       密码必须加盐哈希存储，禁止明文                  高
  会话管理       SessionID 随机、有过期时间、可注销              高
  登录失败处理   登录失败次数限制、锁定机制                      高
  权限验证       每个接口都有权限校验                            高
  越权访问       防止水平越权和垂直越权                          高
  文件类型校验   上传文件类型白名单                              高
  文件名处理     随机化文件名，避免路径穿越                      高
  命令执行       禁止直接执行用户可控的系统命令                  高
  反序列化       避免反序列化不可信数据                          高
  依赖升级       升级有漏洞的第三方依赖（如 Fastjson）           高

**典型反例：**

``` xml
<!-- 危险：使用 ${} 直接拼接 SQL -->
<select id="getUser" resultType="User">
    SELECT * FROM SYS_USER WHERE USER_NAME = '${userName}'
</select>
```

**安全写法：**

``` xml
<!-- 使用 #{} 预编译 -->
<select id="getUser" resultType="User">
    SELECT * FROM SYS_USER WHERE USER_NAME = #{userName}
</select>
```

#### API 安全检查要点

  检查项       等保要求                         风险等级
  ------------ -------------------------------- ----------
  身份认证     API 必须经过身份认证             高
  接口鉴权     每个接口有权限控制               高
  输入校验     所有接口参数进行校验             高
  速率限制     防止暴力破解和爬虫               中
  HTTPS 传输   敏感接口使用 HTTPS               高
  敏感数据     响应中不返回敏感字段（如密码）   高

#### 数据库安全检查要点

  检查项       等保要求                                      风险等级
  ------------ --------------------------------------------- ----------
  数据加密     敏感数据加密存储（本项目密码使用 SM4 国密）   高
  数据完整性   重要数据有完整性校验                          中
  备份恢复     数据定期备份，可恢复                          高
  审计日志     数据库操作审计日志                            中
  最小权限     数据库账号权限最小化                          中

#### 依赖安全检查要点

  检查项     等保要求                     风险等级
  ---------- ---------------------------- ----------
  已知漏洞   依赖无已知高危漏洞           高
  依赖来源   依赖从可信来源获取           中
  依赖数量   最小化依赖，删除未使用依赖   低

#### 检查方法与工具

-   **静态代码扫描：** 前端 ESLint + eslint-plugin-security；Java 用
    SpotBugs、SonarQube、FindSecBugs；依赖用 npm audit、OWASP
    Dependency-Check。
-   **动态安全测试：** OWASP ZAP、Burp Suite；XSS 测试用 XSS Cheat
    Sheet；SQL 注入测试用 sqlmap。

``` bash
# 前端依赖安全检查
cd frontend && npm audit

# Java 依赖安全检查
cd backend && mvn org.owasp:dependency-check-maven:check
```

#### 等保三级核心技术要求速查

  ------------------------------------------------------------------------------------------
  层面       控制点       三级要求
  ---------- ------------ ------------------------------------------------------------------
  物理安全   机房安全     物理访问控制、防盗窃、防破坏、防雷、防火、防水、防潮、温湿度控制

  网络安全   访问控制     网络设备访问控制、IP/MAC 绑定、端口最小化

  网络安全   入侵防范     入侵检测/防御系统、异常监控

  主机安全   身份鉴别     双因素认证、登录失败处理、口令复杂度

  主机安全   访问控制     最小权限、账号管理、权限分离

  主机安全   安全审计     审计覆盖到每个用户、审计记录保存 6 个月以上

  应用安全   身份鉴别     登录认证、会话管理、超时退出

  应用安全   访问控制     功能权限、数据权限、操作权限

  应用安全   安全审计     用户行为审计、审计日志不可删除

  应用安全   通信保密性   敏感数据加密传输（HTTPS）

  应用安全   软件容错     输入校验、异常处理、错误提示不泄露敏感信息

  数据安全   数据完整性   重要数据完整性保护

  数据安全   数据保密性   敏感数据加密存储

  数据安全   数据备份     本地备份+异地备份，定期恢复测试
  ------------------------------------------------------------------------------------------

#### 输出报告结构

``` markdown
# 等保三级安全检查报告

## 检查概览
- 检查范围、时间、标准（GB/T 22239-2019）
- 风险总数：高危 X / 中危 X / 低危 X

## 风险等级说明
- 🔴 高危：直接影响系统安全，必须立即修复
- 🟡 中危：存在安全隐患，建议尽快修复
- 🟢 低危：安全加固建议，可按版本计划修复

## 分层面问题清单（前端/后端/API/数据库/依赖）
每条问题包含：位置、问题描述、风险影响、整改建议、代码示例

## 整改优先级
1. 🔴 高危1 — 立即修复
2. 🟡 中危1 — 本周修复
3. 🟢 低危1 — 后续版本优化

## 合规性评估
| 层面 | 符合项 | 不符合项 | 符合率 |
```

**参考标准：** GB/T 22239-2019、GB/T 28448-2019、OWASP Top 10、CWE/SANS
Top 25。

------------------------------------------------------------------------

## 五、关键设计原则速查

1.  **SSOT（单一事实来源）：**
    每类规则只有一份权威文件，其他地方引用而不是复制。
2.  **职责分离：** spec 不写代码，implement 不定规则，verify
    不修改代码，review 不跑验证。
3.  **证据驱动：** 任何 `verified` 结论必须落到
    `evidence.yaml`，Markdown 勾选框不算证据。
4.  **门禁不可绕过：** `failed/blocked/not_run`
    不得包装为完成；阻塞决策必须停下来问用户。
5.  **Skill 可插拔：** 主 Agent 只做路由，专业能力全部下沉到
    Skill，避免主 Agent 臃肿。
6.  **禁止范围蔓延：**
    只改任务范围内文件，禁止顺手重构；禁区文件除非用户明确要求否则不动。
7.  **复用优先：** 所有实现先扫现有组件/函数/模块，能复用就不新建。
8.  **可追溯：** 每条需求、决策、验收标准都有稳定 ID
    和来源定位；每次变更产物落盘到 `.docloop/changes/<change-id>/`。

------------------------------------------------------------------------

## 六、DocLoop Agent 执行前检查清单（AI 必须逐项执行）

在任何正式代码任务开始前，`orchestrator-agent` 必须检查：

-   [ ] 已识别项目、仓库和技术栈。
-   [ ] 已读取项目入口 `AGENTS.md`。
-   [ ] 已确认适用的项目 Profile。
-   [ ] 已加载本次任务所需 Rules，且没有加载无关领域规则。
-   [ ] 已识别本次任务所需 Skills 和 Superpowers Skills。
-   [ ] 已解析用户资料，并为需求保留来源定位。
-   [ ] 已生成 Spec 草稿并处理阻塞问题。
-   [ ] 已取得用户对当前 Spec Hash 的明确审批。
-   [ ] 已创建 Spec Baseline，后续执行不会静默修改该基线。
-   [ ] 已创建隔离 Git Branch / Worktree。
-   [ ] 已由 Superpowers `writing-plans` 生成 tasks.md。
-   [ ] 已生成 checkList.md，并完成 REQ/AC/TASK/TC 映射检查。
-   [ ] 已确认执行预算、超时、重试和并发限制。
-   [ ] 已确认工具权限、目录范围和命令白名单。

任意强制项未通过时，不得进入业务代码修改阶段。

## 七、最终状态判定契约

  -----------------------------------------------------------------------------------
  最终状态             必须满足的条件
  -------------------- --------------------------------------------------------------
  `implemented`        实现者完成任务范围内代码修改，快速检查有真实结果

  `verified`           verify-agent
                       独立执行所有强制验证；每个验收标准均有证据；无未解决强制失败

  `accepted`           verified + review-agent 审查通过 + 无阻塞项 + 产物归档成功

  `blocked`            存在权限、环境、外部依赖或必须由用户决策的问题；现场已保存

  `failed`             系统或执行失败，且可靠性控制中心判定不可恢复

  `cancelled`          用户主动取消，执行已停止且现场已保存
  -----------------------------------------------------------------------------------

**严禁：**

-   由 implement-agent 自行宣布 verified 或 accepted。
-   由 review-agent 代替 verify-agent 执行最终验证。
-   由模型根据日志片段推断测试通过。
-   将未执行、环境不可用或证据缺失的检查标记为 passed。
-   为通过门禁而删除测试、放宽断言、跳过验证或修改已批准 Spec。
-   未经授权修改主分支、执行 Force Push 或进行生产环境变更。

**最终原则：DocLoop Agent 负责控制流程，Superpowers 负责工程方法，专业
Agent 负责分工执行，Rules 负责约束，Skills 负责能力复用，verify-agent
负责独立证据，可靠性控制中心负责有限恢复与安全退出。**
