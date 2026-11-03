# 持久任务工作台 Implementation Plan

Goal：实现已批准方案 P0→P1→P2。
Architecture：现有 LangGraph 图、SQLite、后台线程；控制状态落数据库，节点结果落盘；Git 发布作为独立服务。
Tech Stack：Python/FastAPI/LangGraph/SQLAlchemy/原生 JS，不新增依赖。
Spec：spec.md；详细决策见 ../../docs/workbench-durable-task-proposal.md。

约束：复用当前功能分支；不处理已有未跟踪 demo；不触碰正式运行资料。共享存储/服务与前端按顺序整合。
审查重点：崩溃重入、重复启动/继续、跨项目访问、资料批次迟到、提交/上传后未登记。

## TASK-001 Git 产物版本（AC-002）
- [x] tests/test_publications.py：临时仓库/bare远端验证快照清单、幂等重试、远端确认、秘密排除。
- [x] src/docloop/publications.py：publish/list/read/sync；白名单导出；Git tag 定位发布 commit；产物索引。
- [x] workbench.py 增加发布/查询/重试接口；前端产物弹窗展示版本。

## TASK-002 持久运行（AC-003/004）
- [x] tests/test_durable_runs.py：暂停/恢复、取消、重启、输入校验、重复启动。
- [x] store 状态转换；managed_runs 安全节点控制、同 thread_id 续跑；服务关闭保留 interrupted。
- [x] 需求分析也托管，先建立草稿身份，再后台生成；保留旧同步接口兼容。

## TASK-003 中途补充资料（AC-005）
- [x] tests/test_task_updates.py：归属、暂停、固定版本、报告、审批不可变。
- [x] task_updates.py 持久批次、模型差异报告和新草稿；旧 Run 保留，不自动执行未审批需求。

## TASK-004 工作台交互（AC-001/003/005）
- [x] 弹层管理、Skills 中文展示、主区控制、后台分析重连和补充资料入口。
- [x] 浏览器验证焦点、刷新、长文本、1920/1366/窄屏。

## TASK-005 验证及交付（AC-006）
- [x] 全套 unittest、docloop doctor、独立审查、记录 evidence.yaml 与版本索引。
- [x] 白名单提交；配置远端可用时推送独立功能分支并核对远端，不强推。

进度与决策记录在 execution-log.md。用户已明确授权执行，不重复需求审批。
