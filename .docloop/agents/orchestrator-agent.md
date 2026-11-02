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
