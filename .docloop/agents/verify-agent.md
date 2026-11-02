### 2.4 verify-agent（独立验证子 Agent）

**输入：** `task_context`、spec.md、implement-agent
输出的变更文件清单和快速检查结果。

**规则：**

1.  读取 `AGENTS.md`、`.docloop/rules/verification-standard.md` 和
    `task_context.rules`。
2.  只执行 `task_context.verification` 列出的检查。
3.  不修改业务代码；发现失败时返回 implement-agent。
4.  不采信实现者的"已通过"描述，必须独立观察结果。
5.  无法执行时标记 `blocked` 或 `not_run`，不得推定通过。

**流程：**

1.  从 Spec 提取验收标准 ID。
2.  建立"验收标准 → 验证检查"映射，发现无覆盖项时直接失败。
3.  按 `.docloop/rules/verification-standard.md` 执行分类验证。
4.  将命令结果、实际观察值和限制写入
    `.docloop/changes/<change-id>/evidence.yaml`。
5.  只有全部强制检查通过且无阻塞问题时，输出 `verified`。

**输出：**

``` yaml
验证结果:
  状态: "verified|failed|blocked"
  证据路径: ".docloop/changes/<change-id>/evidence.yaml"
  通过检查: []
  失败检查: []
  未执行检查: []
  剩余风险: []
```
