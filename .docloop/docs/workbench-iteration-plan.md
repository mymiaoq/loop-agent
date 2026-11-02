# 第二轮：需求工作台与沙箱闭环

2026-11-02。用户已授权继续开发、在后台沙箱测试，并优先交付便于测试的工作台；当前无 Oracle 实例和模型接口，先做沙箱演示。

目标：双击打开浏览器，在项目隔离的本地资料库中导入 Markdown/TXT，检索引用，生成可编辑 Spec，明确审批当前 Hash，并执行已有 LangGraph 受控验证。演示与真实能力在界面及证据中区分。

技术：Python、FastAPI/Uvicorn、SQLAlchemy、SQLite 显式沙箱后端；原生 HTML/CSS/JS 本地静态资源，无 CDN、无需前端构建。Oracle 关系存储采用可切换适配与迁移入口，实际 Oracle 联通性、方言和 Checkpoint 不冒称已验收。

## 交付契约

- 数据根目录由启动参数指定，测试全部使用系统临时目录。正式默认 D:\项目\agent-loop-data；不把资料原件、密钥和运行数据纳入 Git。
- 本地文件库内容寻址，数据库保存项目、文档版本、Spec/审批、引用、运行和审计事件。文档失效立即退出检索；已批准引用不随新版本漂移。
- SkillRegistry 是唯一角色、规则和 Skill 上下文入口；记录准确来源 Hash。真实模型接口未配置时不自动切成演示，用户明确选择沙箱生成。
- Spec 通过数据库版本号与 Hash 乐观锁保存；已审批正文保持不可变。受控运行仅在审批后执行，使用隔离工作目录，不能修改工程业务代码。
- API 默认仅绑定 loopback，写请求检查本地 Origin，设置会话防跨站请求标识。模型凭据只保留服务进程内存，不回显、不写日志。

## TASK-W01：持久化与资料服务

文件：src/docloop/workbench_store.py、workbench_service.py；tests/test_workbench_store.py、test_workbench_service.py。
- [x] 先测试项目隔离、资料去重/版本、失效检索、审批并发及原字节不可变。
- [x] 实现 SQLAlchemy 关系表、内容对象库、可定位关键词检索与审计记录。
- [x] 真实 Oracle 连接只按显式配置启用，不自动降级；缺环境不计为通过。

## TASK-W02：需求生成与运行接线

文件：src/docloop/model_gateway.py、workbench_service.py、workflow.py；tests/test_model_gateway.py、test_workbench_service.py。
- [x] 用本地 HTTP fixture 测试请求确实包含本地 Skill 和资料引用、错误/超时/凭据脱敏。
- [x] 明确沙箱生成的模式标记；保存草稿及当前 Skill 来源。
- [x] 审批后接现有 Workflow 受控验证；测试进程重启恢复、未审批拒绝及失败不包装成功。

## TASK-W03：HTTP API 与可操作工作台

文件：src/docloop/workbench.py、workbench_static/{index.html,app.css,app.js}；tests/test_workbench_api.py。
- [x] 冻结 API 后，UI 草稿在独立临时目录制作，与后端共享的只是接口契约；主 Agent 串行整合进仓库。
- [x] 提供项目、资料、检索、Spec 编辑/审批、运行记录、Skills 和连接设置。
- [x] 覆盖错误、空数据、加载、长文本、小屏和键盘操作；浏览器不存模型密钥。

## TASK-W04：启动、集成验证与交付

文件：启动工作台.cmd、README.md、相关正式验收测试。
- [x] 在独立系统临时数据根目录启动服务，使用浏览器自动化完成资料→草稿→编辑→审批→运行→刷新恢复。
- [x] 检查1366/1920/窄屏、控制台错误和页面溢出；保存验证证据到运行数据目录。
- [x] 全套测试、打包、独立审查；实际 Oracle 与真实供应商模型若无环境则标为未验证。

依赖：W01 → W02 → W03 集成 → W04。前端草稿仅在 API 契约冻结后独立制作；共享存储/服务文件由主 Agent 顺序修改。此轮不实现自动改业务仓库、完整 OCR、向量检索和 Oracle 原生图 Checkpoint。
