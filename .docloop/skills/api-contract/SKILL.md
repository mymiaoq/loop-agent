---
name: api-contract
description: API 契约和前端封装；API 任务显式选中时使用。
version: 1.0.0
risk_level: medium
timeout: 300
---

## 用途
API 契约和前端封装。企业 Profile 专用。

## 触发条件
API 任务显式选中，且企业 Profile 已选择。

## 输入 Schema
```yaml
required: [task_context, spec, field_mapping]
```

## 允许工具
read_file, scoped_write；不能超出 task_context 的权限。

## 执行步骤
仅加载 task_context 允许规则，按下述专业流程执行。

## 输出 Schema
api_id/path/method/request/response/error_codes/verification_points；字段和嵌套结构见下述来源契约。

## 失败处理
必需契约、权限、环境或证据缺失返回 blocked，并记录未评估内容。

## 完成条件
对应需求 ID 全覆盖；每项结论有实际依据；输出符合专业契约。

## 禁止行为
不越过角色职责，不覆盖已批准基线，不把配置存在当作技能执行成功。

## 专业流程与契约
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
