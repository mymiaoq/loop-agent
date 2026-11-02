---
name: audit-recorder
description: 记录需求到 Commit 的关联；阶段切换和工具结果产生时时使用。
---

## 用途
记录需求到 Commit 的关联。

## 触发条件
阶段切换和工具结果产生时。

## 输入 Schema
```yaml
required: [change_id, task_id, event, commit]
```

## 允许工具
read_file, append_trace；实际权限取 task_context 与适配器权限的交集。

## 执行步骤
记录实际事件和来源；不输出密钥；记录模拟模式标签。

## 输出 Schema
traces JSONL 和关联记录。所有结果标明 mode 与 status。

## 失败处理
环境、权限或必要业务信息缺失时返回 blocked；保存证据，不自动扩大范围。

## 完成条件
输出可解析，必需字段齐全，需求关联无缺失，实际执行状态已记录。

## 禁止行为
不覆盖基线，不将 not_run 当作 passed，不授予工具权限，不越过角色职责。
