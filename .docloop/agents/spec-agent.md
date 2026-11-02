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
