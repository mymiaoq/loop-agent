# DocLoop 0.2.0 工作台验收记录

2026-11-02，Windows 本机。范围为本地沙箱工作台与需求审批闭环，不是完整生产平台验收。

## 实际执行结果

| 检查 | 实际结果 |
| --- | --- |
| `python -m unittest discover -s tests -v` | 61项通过 |
| `python -m unittest discover -s tests/acceptance -v` | 1项真实Microsoft Edge浏览器全流程通过 |
| `docloop doctor` | passed；本地Superpowers 231文件与导入基准一致 |
| `uv build` | 0.2.0 wheel和sdist构建成功 |
| Wheel内容检查 | HTML、CSS、JS和favicon均存在 |
| Windows启动入口预检 | 原生cmd调用、独立数据根目录通过 |
| 独立代码审查 | UI问题修复后复查通过；最新服务启动/停止逻辑复查无重要阻断 |

浏览器实际操作：文本资料导入 → 本地Skill上下文支持的沙箱草稿 → 未保存修改后台刷新保留 → 暂挂保存请求期间编辑器只读 → 保存 → 明确审批当前Hash → 独立LangGraph受控运行 → 刷新恢复 → 资料换版后旧引用仍保留版本/Hash与历史标记 → 本地Skill预览 → 项目隔离及选中项目刷新恢复 → 服务身份匹配及正常停止。

检查1366、1920、390像素宽度，无页面级横向溢出；页面JS与控制台错误为0。完整测试日志、浏览器截图和结果位于本机数据根目录 `validation/20261102-workbench/`，不纳入Git资料或凭据存储。

## 验收中修复的问题

- Windows创建Spec时自动转CRLF导致数据库审批Hash与文件Hash不一致：改为精确UTF-8原字节写入，并增加回归。
- 资料刷新覆盖未保存Spec、保存期间可继续输入导致丢失：本地草稿缓存和操作期间只读保护，真实浏览器回归通过。
- 历史引用缺少版本和指纹：现展示版本、Hash及历史引用标记。
- 输入快照指纹未覆盖最终组装的模型消息：重算最终负载Hash并测试。
- 服务异常退出遗留运行中状态：重启将未完成演示标为blocked，不自动重跑；数据目录由OS锁保护。

## 未执行与边界

- Oracle：只检查共享关系契约及19c兼容DDL生成，未连接真实Oracle，未验证其真实事务/权限/字符集。
- 模型：通用Chat-Completions网关通过受控HTTP fixture测试；没有真实供应商地址或凭据，未验证真实推理。
- 工作台“运行沙箱验证”只验证受控文件、Commit和工作流门禁，结果明确 `real_business_acceptance: false`；不执行所写Spec的业务编码。
- Oracle LangGraph CheckpointSaver、向量检索、完整多格式解析、真实业务代码/Worktree执行和多实例生产治理仍待后续迭代。

日常使用双击 `启动工作台.cmd`；双击 `停止工作台.cmd` 停止。资料和审批留在项目同级 `agent-loop-data`，模型凭据只保留服务内存。
