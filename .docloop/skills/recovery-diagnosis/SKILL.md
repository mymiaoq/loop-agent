---
name: recovery-diagnosis
description: 分类故障并建议有界恢复；异常或验证失败时使用。
version: 1.0.0
risk_level: medium
timeout: 300
---

## 用途
分类故障并建议有界恢复。

## 触发条件
异常或验证失败。

## 输入 Schema
```yaml
required: [task_context, error, checkpoint, budget]
```

## 允许工具
read_file, checkpoint_adapter, write_recovery；实际权限取 task_context 与适配器权限的交集。

## 执行步骤
先定位根因；瞬时错误有界重试；技术修复使用 systematic-debugging；业务和权限问题停止。

## 输出 Schema
错误指纹、现场、修复历史、下一步建议。所有结果标明 mode 与 status。

## 失败处理
环境、权限或必要业务信息缺失时返回 blocked；保存证据，不自动扩大范围。

## 完成条件
输出可解析，必需字段齐全，需求关联无缺失，实际执行状态已记录。

## 禁止行为
不覆盖基线，不将 not_run 当作 passed，不授予工具权限，不越过角色职责。
