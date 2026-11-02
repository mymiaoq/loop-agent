---
name: plan-create
description: 已审批基线转为任务计划；基线已锁定且无阻塞时使用。
---

## 用途
已审批基线转为任务计划。

## 触发条件
基线已锁定且无阻塞。

## 输入 Schema
```yaml
required: [task_context, baseline]
```

## 允许工具
read_file, write_change, superpowers_adapter；实际权限取 task_context 与适配器权限的交集。

## 执行步骤
重验基线；调用已锁定 writing-plans；逐项映射需求，依赖先行。

## 输出 Schema
tasks.md，TASK ID、依赖和文件范围。所有结果标明 mode 与 status。

## 失败处理
环境、权限或必要业务信息缺失时返回 blocked；保存证据，不自动扩大范围。

## 完成条件
输出可解析，必需字段齐全，需求关联无缺失，实际执行状态已记录。

## 禁止行为
不覆盖基线，不将 not_run 当作 passed，不授予工具权限，不越过角色职责。
