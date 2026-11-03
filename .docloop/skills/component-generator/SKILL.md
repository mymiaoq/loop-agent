---
name: component-generator
description: Vue 组件和页面实现；UI 任务显式选中时使用。
version: 1.0.0
risk_level: medium
timeout: 300
---

## 用途
Vue 组件和页面实现。企业 Profile 专用。

## 触发条件
UI 任务显式选中，且企业 Profile 已选择。

## 输入 Schema
```yaml
required: [task_context, spec, target_files, reuse]
```

## 允许工具
read_file, scoped_write；不能超出 task_context 的权限。

## 执行步骤
仅加载 task_context 允许规则，按下述专业流程执行。

## 输出 Schema
files/reused/requirement_ids/self_check；字段和嵌套结构见下述来源契约。

## 失败处理
必需契约、权限、环境或证据缺失返回 blocked，并记录未评估内容。

## 完成条件
对应需求 ID 全覆盖；每项结论有实际依据；输出符合专业契约。

## 禁止行为
不越过角色职责，不覆盖已批准基线，不把配置存在当作技能执行成功。

## 专业流程与契约
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
