### 2.3 implement-agent（代码实现子 Agent）

**输入：** `task_context`、已锁定的 Spec Baseline，以及
`.docloop/changes/<change-id>/` 下的 `spec.md` / `decisions.md` /
`tasks.md` / `checklist.md`。必须使用 Superpowers
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
