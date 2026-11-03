# 模型持久化与执行基础迭代

2026-11-03。用户确认：持久保存模型配置，仅支持GPT 6.1 Sol和DeepSeek V4.1 Flash；配置当前GPT；下拉切换；去掉新任务标题；缩短生成模式选择；继续上一轮开发顺序。

模型：GPT使用本机已登录Codex CLI与精确模型名gpt-6.1-sol，不复制OAuth令牌或冒充API Key；Spec生成是只读临时工作区调用。DeepSeek显示V4.1 Flash，按官方文档调用deepseek-flash；地址/加密密钥按模型独立保存，切换不丢另一模型配置。Windows使用当前用户DPAPI保护密钥，配置在独立数据目录.settings，原子写入；响应、Prompt及日志不含密钥。自动回归用临时配置和fixture；独立的真实连通性/Spec验证复用本机已授权登录，未写入用户业务资料。

已落地：双模型持久档案、下拉切换、自动任务名、紧凑模式选择；单一Codex只读Runtime，Windows Job Object进程树所有权、超时/取消/输出预算，服务关闭时取消本服务持有的Codex调用；项目仓库登记、批准字节/Hash/Commit绑定、幂等Worktree准备与保留Diff。Git准备禁用hook、filter、fsmonitor、外部diff与textconv；需要LFS等过滤器的业务项目仍需独立适配，不能按普通准备成功视为可构建。

执行边界：准备API不是正式Run。即使Docker可达，当前真实编码执行门禁仍为blocked；只读模型调用取消不等于完整业务Run取消。未接入真实写代码、业务测试、自动修复、人工最终验收。仓库源代码不自动commit/push，也不清理已有改动；已批准基线未修改。

真实结果：gpt-6.1-sol连通性24.14秒返回DOCLOOP_MODEL_OK；加固后的只读Runtime在68.45秒生成实际Spec，含AC-001，mode=real、business_code_execution=false。原始登录令牌没有复制到工程、数据库或Prompt。DeepSeek无真实Key，只完成受控HTTP/DPAPI验证。当前机器GPT档案已预置并持久保存；切换DeepSeek后填写一次Key即可保存。

回归结果：94项框架测试，93通过、1跳过（Windows缺少符号链接创建权限）；真实Edge完整验收1项通过，含双模型下拉、加密配置保存后刷新、自动任务名、模式选择刷新保留、文档中心及原有审批/隔离回归。服务进程真实重启测试验证配置和Key仍保留且API不回显Key。doctor passed，wheel/sdist构建通过。独立复核无新增重要问题。

加固回归：Git hook/filter两个marker测试在修复前失败、修复后通过；父Codex进程退出但子进程继承管道测试在Job Object加固前失败、加固后通过。浏览器夹具使用替代CLI路径并拦截真实模型生成，不依赖真实供应商登录。独立真实模型验证在系统临时目录执行，只保存脱敏结果摘要。

证据位置：`D:/项目/agent-loop-data/validation/20261103-model-runtime/`，包含浏览器截图、browser-result.json及real-model-spec-result.json。本轮为Windows本机验收；Oracle、DeepSeek真实推理、Docker及业务写执行未验收。

UI：输入需求自动取首行作为任务名；模型下拉放在输入区，可直接切换；模式简写“演示/模型”；设置页面只显示相关连接项，留空密钥表示沿用已保存值。

执行：先落地单一Codex只读Runtime及取消/超时/输出预算，再接Git Worktree基线与幂等准备。正式写代码前必须满足隔离和权限门禁。当前Docker引擎不可达，不能把只读模型响应或Git目录当真实编码/容器隔离验收。Oracle仍保持既定选型，不在本轮伪造实例验收。

实施：持久化/安全/切换回归→界面交互→CLI真实只读连通性→Worktree临时Git测试→框架/浏览器/重启持久化验证→独立审查。开发与验证串行整合，独立草稿只写ignored sessions目录。

参考：[Codex非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)、[Codex登录](https://learn.chatgpt.com/docs/auth?surface=cli)、[DeepSeek调用与模型别名](https://api-docs.deepseek.com/quick_start/agent_integrations/)。官方资料已打开核对；运行能力以本机实际结果为准。
