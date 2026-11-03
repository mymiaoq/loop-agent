---
name: frontend-quality-check
description: 前端 UI 专项质量检查；UI 任务且明确选中时使用。
version: 1.0.0
risk_level: medium
timeout: 300
---

## 用途
前端 UI 专项质量检查。企业 Profile 专用。

## 触发条件
UI 任务且明确选中，且企业 Profile 已选择。

## 输入 Schema
```yaml
required: [task_context, spec, browser_evidence]
```

## 允许工具
read_file, browser_adapter, write_evidence；不能超出 task_context 的权限。

## 执行步骤
仅加载 task_context 允许规则，按下述专业流程执行。

## 输出 Schema
status/requirement_coverage/findings/evidence_gaps；字段和嵌套结构见下述来源契约。

## 失败处理
必需契约、权限、环境或证据缺失返回 blocked，并记录未评估内容。

## 完成条件
对应需求 ID 全覆盖；每项结论有实际依据；输出符合专业契约。

## 禁止行为
不越过角色职责，不覆盖已批准基线，不把配置存在当作技能执行成功。

## 专业流程与契约
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
