# verification-standard

适用 Profile：所有项目；只执行 task_context.verification 指定的检查，企业构建命令仅适用于企业 Profile。

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
`checklist.md` 中的 Test Case ID：

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
