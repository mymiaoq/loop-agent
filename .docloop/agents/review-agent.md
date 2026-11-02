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
