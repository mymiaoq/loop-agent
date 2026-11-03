---
name: project-archiving
description: 归档正式文档和校验清单；验证和审查均通过时使用。
version: 1.0.0
risk_level: low
timeout: 300
---

## 用途
归档正式文档和校验清单。

## 触发条件
验证和审查均通过。

## 输入 Schema
```yaml
required: [task_context, evidence, review, commit]
```

## 允许工具
read_file, archive_adapter；实际权限取 task_context 与适配器权限的交集。

## 执行步骤
校验基线及覆盖；使用 staging 归档；冲突拒绝覆盖；归档成功才 accepted。

## 输出 Schema
文档/变更记录/change-id 和 manifest Hash。所有结果标明 mode 与 status。

## 失败处理
环境、权限或必要业务信息缺失时返回 blocked；保存证据，不自动扩大范围。

## 完成条件
输出可解析，必需字段齐全，需求关联无缺失，实际执行状态已记录。

## 禁止行为
不覆盖基线，不将 not_run 当作 passed，不授予工具权限，不越过角色职责。
