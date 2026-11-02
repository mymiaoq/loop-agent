---
name: frontend-design
description: 前端视觉设计决策；新页面或明确视觉优化时使用。
---

## 用途
前端视觉设计决策。企业 Profile 专用。

## 触发条件
新页面或明确视觉优化，且企业 Profile 已选择。

## 输入 Schema
```yaml
required: [task_context, spec, ui_rules]
```

## 允许工具
read_file, design_output；不能超出 task_context 的权限。

## 执行步骤
仅加载 task_context 允许规则，按下述专业流程执行。

## 输出 Schema
primary_focus/hierarchy/composition/typography/color_usage/motion/reuse；字段和嵌套结构见下述来源契约。

## 失败处理
必需契约、权限、环境或证据缺失返回 blocked，并记录未评估内容。

## 完成条件
对应需求 ID 全覆盖；每项结论有实际依据；输出符合专业契约。

## 禁止行为
不越过角色职责，不覆盖已批准基线，不把配置存在当作技能执行成功。

## 专业流程与契约
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
