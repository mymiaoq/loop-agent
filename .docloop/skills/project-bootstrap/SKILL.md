---
name: project-bootstrap
description: 检查项目和隔离工作区；审批后的执行准备时使用。
version: 1.0.0
risk_level: medium
timeout: 300
---

## 用途
检查项目和隔离工作区。

## 触发条件
审批后的执行准备。

## 输入 Schema
```yaml
required: [task_context, profile, baseline]
```

## 允许工具
read_file, git_adapter, command_adapter；实际权限取 task_context 与适配器权限的交集。

## 执行步骤
确认 Profile 和工具允许范围；真实执行调用 worktree 适配器，未配置则阻塞。

## 输出 Schema
环境、Git、Worktree、依赖和权限检查报告。所有结果标明 mode 与 status。

## 失败处理
环境、权限或必要业务信息缺失时返回 blocked；保存证据，不自动扩大范围。

## 完成条件
输出可解析，必需字段齐全，需求关联无缺失，实际执行状态已记录。

## 禁止行为
不覆盖基线，不将 not_run 当作 passed，不授予工具权限，不越过角色职责。
