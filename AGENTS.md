# DocLoop 框架开发入口

每次更新检查并清理已确认无用的临时文件、过期构建包及本次涉及的冗余代码，避免重复产物累积；不得自动删除业务资料、审批基线、审计证据或用途未确认的未提交文件。运行性能变更必须在系统临时数据目录验证内存峰值和重复操作增长，记录负载、阈值及未覆盖场景；优先按需读取和有界处理，不增加不必要的常驻任务或依赖。

本仓库是 Python + LangGraph 的 DocLoop 平台框架。当前实现范围见 `.docloop/changes/20261102-framework/spec.md`，审批记录独立保存在 baseline/approval.json。

第二轮工作台范围与验收计划见 `.docloop/docs/workbench-iteration-plan.md`。工作台业务数据根目录默认位于项目同级 `agent-loop-data`；测试使用系统临时目录，不复用用户的工作台资料、审批或模型设置。普通启动使用根目录 `启动工作台.cmd`，自动关闭匹配项目及数据目录的旧实例并等待端口释放；手动停止可在服务窗口按 Ctrl+C。Oracle 和真实模型的受控结构/fixture 检查与真实环境验收分别记录。

## 开发本框架

本项目的工程方法与专业 Skill 以项目目录为入口：Superpowers 读取 `.docloop/superpowers/skills/<name>/SKILL.md`；DocLoop 专业能力读取 `.docloop/skills/<name>/SKILL.md`。同名 Skill 使用这里的当前内容；不回退到全局安装或插件缓存。开始本项目任务时先读取本地 `using-superpowers`，再按实际任务读取本地 brainstorming、TDD、调试、验证或审查 Skill；配套资源按该 Skill 的本地相对路径读取。用户已明确的范围直接执行，不重复启动已完成的需求确认。

项目配置入口是 `.docloop/project.yaml`，默认 Profile 为 docloop-platform。读取通用 code-standard 和 verification-standard；仅改任务范围内代码。运行 `uv run python -m unittest discover -s tests -v` 和 `uv run docloop doctor`。依赖以 uv.lock 锁定。

五角色文件定义目标运行系统的行为，不会自动将当前开发会话切换为某角色。企业 Vue/Java、端口、组件库和品牌只由 enterprise-vue-java Profile 条件启用。

## 运行 DocLoop

需求、执行、可靠性控制分别见 src/docloop/governance.py、workflow.py、reliability.py。Rules 的唯一权威目录是 `.docloop/rules/`；`.docloop/docs/source-design.md` 是原始设计参考，不能作为第二份可编辑运行规则。

变更材料写入 `.docloop/changes/<change-id>/`。按 REQ → AC → TASK → TC → V → Commit 关联。基线审批后保持原字节；需求变化创建新 Change。实现、验证、审查接口职责分离，失败、阻塞和未执行结论如实记录。

Skills 按任务和阶段选择；平台与领域共15个唯一 Skill，其中 document-parser 为共享定义。Superpowers 文件位于 `.docloop/superpowers/`，`.docloop/superpowers.lock.json` 保留导入时上游基准，project.yaml 记录来源 Commit。当前启用本地读取、采用 editable 策略：允许从该目录直接修改，doctor 报告相对上游的修改/新增/缺失，不覆盖修改。缺少阶段必需 Skill、路径越界或格式错误仍阻止调用。

`src/docloop/skill_runtime.py` 是运行时读取入口，阶段映射由 project.yaml 的 skill_runtime 定义；每次阶段调用读取当前磁盘内容，保存实际上下文和路径/Hash 记录。真实编码/模型/浏览器适配器未配置时仍返回 blocked；上下文已加载不能解释为模型已推理或遵从。上游插件、hooks 和安装脚本不会仅因 Skill 加载而执行。

本地工具采用完整 argv 白名单、固定目录与超时；不以 shell 执行任意字符串。ToolAdapter 是合作式权限边界，不是操作系统沙箱，不用于运行不可信命令。
