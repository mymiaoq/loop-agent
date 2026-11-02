---
name: checklist-create
description: 建立验收和测试追踪链；tasks.md 已生成时使用。
---

## 用途
建立验收和测试追踪链。

## 触发条件
tasks.md 已生成。

## 输入 Schema
```yaml
required: [task_context, spec, tasks]
```

## 允许工具
read_file, write_change；实际权限取 task_context 与适配器权限的交集。

## 执行步骤
逐一覆盖所有 AC；区分强制与可选检查；缺映射返回 blocked。

## 输出 Schema
checkList.md，REQ/AC/TASK/TC/V 映射。所有结果标明 mode 与 status。

## 失败处理
环境、权限或必要业务信息缺失时返回 blocked；保存证据，不自动扩大范围。

## 完成条件
输出可解析，必需字段齐全，需求关联无缺失，实际执行状态已记录。

## 禁止行为
不覆盖基线，不将 not_run 当作 passed，不授予工具权限，不越过角色职责。
