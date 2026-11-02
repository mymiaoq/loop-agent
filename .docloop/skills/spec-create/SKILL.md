---
name: spec-create
description: 生成可审批 Spec 草稿；需求探索阶段时使用。
---

## 用途
生成可审批 Spec 草稿。

## 触发条件
需求探索阶段。

## 输入 Schema
```yaml
required: [task_context, source_bundle]
```

## 允许工具
read_file, write_change, superpowers_adapter；实际权限取 task_context 与适配器权限的交集。

## 执行步骤
核对范围、约束和阻塞项；通过项目 SkillRegistry 读取 `superpowers:brainstorming`，实际文件为 `.docloop/superpowers/skills/brainstorming/SKILL.md`；使用本地当前内容，不从全局路径读取同名文件。模型未配置时仅准备上下文并明确阻塞，不能声称已生成 Spec。保留待确认事项。

## 输出 Schema
spec.md、decisions.md，REQ/AC ID 和来源定位。所有结果标明 mode 与 status。

## 失败处理
环境、权限或必要业务信息缺失时返回 blocked；保存证据，不自动扩大范围。

## 完成条件
输出可解析，必需字段齐全，需求关联无缺失，实际执行状态已记录。

## 禁止行为
不覆盖基线，不将 not_run 当作 passed，不授予工具权限，不越过角色职责。
