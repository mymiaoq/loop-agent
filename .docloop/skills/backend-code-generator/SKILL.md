---
name: backend-code-generator
description: 后端分层代码实现；backend 任务显式选中时使用。
---

## 用途
后端分层代码实现。企业 Profile 专用。

## 触发条件
backend 任务显式选中，且企业 Profile 已选择。

## 输入 Schema
```yaml
required: [task_context, spec, api_contract, schema]
```

## 允许工具
read_file, scoped_write, command_adapter；不能超出 task_context 的权限。

## 执行步骤
仅加载 task_context 允许规则，按下述专业流程执行。

## 输出 Schema
files/reused/model_ids/api_ids/requirement_ids/compile_target；字段和嵌套结构见下述来源契约。

## 失败处理
必需契约、权限、环境或证据缺失返回 blocked，并记录未评估内容。

## 完成条件
对应需求 ID 全覆盖；每项结论有实际依据；输出符合专业契约。

## 禁止行为
不越过角色职责，不覆盖已批准基线，不把配置存在当作技能执行成功。

## 专业流程与契约
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
