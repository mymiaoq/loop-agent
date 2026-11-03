---
name: test-runner
description: 执行本任务明确允许的验证；实现快速检查或独立验证阶段时使用。
version: 1.0.0
risk_level: medium
timeout: 300
---

## 用途
执行本任务明确允许的验证。

## 触发条件
实现快速检查或独立验证阶段。

## 输入 Schema
```yaml
required: [task_context, verification, commit]
```

## 允许工具
command_adapter, browser_adapter, write_evidence；实际权限取 task_context 与适配器权限的交集。

## 执行步骤
使用完整 argv 白名单和目录范围；检查退出码；独立验证重新运行，不能复用实现结论。

## 输出 Schema
命令、退出码、观察、日志、TC/V ID。所有结果标明 mode 与 status。

## 失败处理
环境、权限或必要业务信息缺失时返回 blocked；保存证据，不自动扩大范围。

## 完成条件
输出可解析，必需字段齐全，需求关联无缺失，实际执行状态已记录。

## 禁止行为
不覆盖基线，不将 not_run 当作 passed，不授予工具权限，不越过角色职责。
