# Oracle、项目产物与本地资料库设计草案

日期：2026-11-02。状态：设计建议，未开始数据库迁移或改写运行代码。

用户已确定数据库采用 Oracle，版本尚未确定，先按版本兼容设计。此次目标是确定 brainstorming 调整、文件位置、数据库边界及持续增量数据。

## 1. 选型与权威边界

| 方案 | 权衡 |
| --- | --- |
| 全部文件存 Oracle BLOB | 备份集中，但源码、Git Diff、测试工具和大附件管理不便；不推荐默认采用 |
| Oracle 状态库 + 本地文件库（推荐） | 关系数据可查询，代码可版本控制；需要明确 Hash、备份清单和跨存储失败恢复 |
| 文件为主，Oracle 仅做缓存 | 改动小，但任务并发、事务、审计和跨会话恢复仍依赖散落文件；不适合作为目标架构 |

建议：代码和工程规范以 Git 为权威；运行与知识管理数据以 Oracle 为权威；资料原件和大附件以受管理的本地文件库为权威。数据库保留文件 ID、相对位置、内容 Hash 和版本引用。

同一正文不允许数据库和磁盘同时作为可编辑主版本。数据库权威数据导出的 Markdown/YAML/JSON 仅为审阅或交付快照；用户修改快照时，必须通过导入流程生成新的草稿版本，不能静默写回已审批版本。

## 2. 存储矩阵

| 对象 | 权威位置 | Oracle 存什么 | 增量类型 |
| --- | --- | --- | --- |
| 源码、正式测试代码、迁移 SQL | 项目 Git | 路径、Commit、任务关联；不复制全库正文 | Git 版本增长 |
| AGENTS、Rules、Skills、Profile、brainstorming 定制 | 项目 Git | 发布时版本/Hash 和调用记录 | Git 版本增长 |
| 需求原始 DOCX/PDF/图片/Excel/MD | 本地文件库 | 资料 ID、版本、大小、MIME、Hash、来源、权限、状态 | 原件不可变，新版本追加 |
| 解析后的正文、表格结构、来源索引 | Oracle | CLOB 正文、结构化表格/定位、解析器版本和警告 | 按资料版本追加，可重新解析 |
| Spec、决策、任务、测试计划的草稿及版本 | Oracle | 正文版本、结构化 REQ/AC/TASK/TC、依赖和关联 | 草稿乐观锁更新；提交版本追加 |
| 已审批 Spec、审批凭据 | Oracle | 精确原字节 BLOB、SHA256、审批者、版本与时间 | 只新增审批版本，不覆盖 |
| 运行状态、Task 状态、预算当前值 | Oracle | 可查询状态字段、版本号、用量、租约 | 当前行更新，变更事件追加 |
| 会话消息、工具调用、审批事件、修复历史 | Oracle | 分条记录、顺序号、实际结果、关联 ID | 持续追加，按保留策略归档 |
| LangGraph Checkpoint / pending writes | Oracle | thread/namespace/checkpoint/parent、版本化序列化负载、未完成写入 | 运行时高频追加，可受控压缩/清理 |
| 测试运行、断言结果、审查发现 | Oracle | TC/V/AC/Commit/命令/退出码/观察/审查结果 | 每次执行追加，不覆盖上次结果 |
| 完整日志、截图、视频、压缩包、Git Diff 附件 | 本地文件库 | 文件引用、Hash、摘要、检索标签 | 高频新增，滚动归档 |
| 资料分块、Embedding、检索引用 | Oracle；检索方式按版本选择 | chunk 正文、来源、模型版本、向量或索引引用 | 内容变化后增量生成；派生数据可重建 |
| 人工确认的项目知识与复用经验 | Oracle | 知识条目、依据、适用范围、版本、确认者、有效期 | 新增/修订/失效；与日志分开 |
| 已验收交付归档 | 本地文件库 | 归档清单、证据索引、版本、Hash、生命周期状态 | 每个验收版本不可变追加 |
| 临时解压、OCR 中间件、测试沙箱与缓存 | 系统临时目录或本地缓存 | 必要任务状态；不默认保存内容 | 临时生成、任务后清理 |
| 密钥、密码、模型 Token | 本机凭据设施 | 仅保存凭据引用 | 不进入资料库、Prompt、日志或 Git |

不要将“存 evidence.yaml”实现为一个持续增长的大字段：每次运行、每项检查、每份附件分别建记录，evidence.yaml 是对应版本的导出。

## 3. 建议目录

```text
项目根目录/
  src/                            框架及适配器源码，Git
  tests/
    unit/                         单元测试，Git
    integration/                  数据库/图/适配器集成测试，Git
    acceptance/                   长期验收回归代码，Git
    fixtures/                     小型、脱敏、固定测试数据，Git
  migrations/oracle/              版本化 SQL，Git
  docs/                          使用与架构文档，Git
  .docloop/
    project.yaml                 非敏感项目配置，Git
    agents/ rules/ skills/ profiles/  工程规则与能力定义，Git
    docs/                        设计来源及少量维护资料，Git
    changes/<change-id>/          审阅/执行时的文件投影；数据库主版本的导出
  文档/变更记录/<change-id>/       可选人工交付导出，绑定归档 ID 与 Hash

独立数据根目录（位置可配置，不进入 Git）/
  objects/<sha256前两位>/<sha256>  资料和附件原字节，按内容去重
  exports/<project-id>/<change-id>/<version>/
                                 正式交付归档，保留清单与 Hash
  staging/<import-id>/            未完成导入，校验成功后才激活
  cache/                         可重建缓存
```

单机可将数据根目录配置为 `D:\项目\agent-loop-data`；这是建议位置，不自动创建。资料逻辑分类、项目归属和文档名由数据库管理；物理对象共享去重不能绕过项目权限。

现有 `tests/test_*.py` 无需为排版立即搬动；在新增数据库/资料库测试时分层迁移。测试用例定义 TC、测试源文件与测试运行结果是三类不同对象。大量真实项目数据不放 fixtures。

当前仓库已存在的已批准基线与交付记录保持原样；迁移时登记为历史版本，不重写正文或 Hash。

## 4. Oracle 兼容性

- 关系字段优先使用稳定基础类型：VARCHAR2、NUMBER、TIMESTAMP WITH TIME ZONE；长篇中文正文用 CLOB。
- 需要按精确字节校验的审批正文和序列化 Checkpoint 使用 BLOB，保存编码/序列化版本与 SHA256，不能经过换行转换或重新格式化。
- JSON 扩展属性采用版本适配。19c 路径可使用 UTF-8 JSON BLOB 和 IS JSON 校验，热点字段独立为可索引关系列；新版本原生 JSON 属于可选实现，业务接口保持一致。
- 不假定所有 Oracle 都支持 VECTOR。确认具备 AI Vector Search 的版本后，才启用 Oracle 原生向量和索引。
- 19c 兼容路径首先提供 Oracle Text/关键词检索（需确认组件与权限），无全文组件时明确返回受限的基础检索；语义检索作为能力开关。小规模可用受限本地向量索引作可重建派生缓存，需单独确认后实现；不能把 BLOB 内存了向量等同于具备数据库向量检索。
- Oracle CheckpointSaver 需按 LangGraph Checkpointer 接口实现与验证，包括父子 Checkpoint、channel 版本和 pending writes；不能仅改 project.yaml 的 sqlite 字符串。
- 正式 Oracle 模式连接失败时停止推进并保存必要本地故障信息，不静默切回 SQLite 形成两套活动状态。SQLite 仅保留为显式离线演示配置。

版本依据：

- [Oracle 19c JSON LOB 存储说明](https://docs.oracle.com/en/database/oracle/oracle-database/19/adjsn/considerations-when-using-lob-storage-json-data.html)
- [Oracle AI Vector Search 的 23ai 引入及 RAG 检索说明](https://docs.oracle.com/en/learn/oracledb-hybrid-search/index.html)

## 5. 持续增量与生命周期

1. 业务版本增量：资料版本、Spec 版本、审批、知识条目版本。历史不可原地覆盖；“当前有效版本”指针允许更新。
2. 执行流水增量：消息、工具调用、事件、测试运行、验证项、修复轮次、检索引用。最容易持续膨胀，应按项目/运行/时间查询并设保留规则。
3. 恢复状态增量：Checkpoint 与 pending writes。活跃/阻塞运行保留可恢复链，终态运行经过验证后才允许按策略压缩。
4. 派生索引增量：解析结果、chunk、向量、检索索引。以资料版本和处理配置寻址，可删除重建；不能作为唯一原始资料副本。
5. 临时数据：缓存、测试沙箱和中间件，不承诺永久保存。具体保留天数与容量上限另行配置，首次上线不自动清理审批和验收历史。

入库去重至少区分“原文件相同”与“加工结果相同”：

- 原件对象以 SHA256 去重；资料记录仍保留项目归属和权限。
- 解析唯一键：资料版本 + parser 版本 + parser 配置 Hash。
- 分块唯一键：解析版本 + chunker 版本 + chunker 配置 Hash + 块序号。
- 向量唯一键：chunk 内容 Hash + embedding 模型版本 + 维度 + 归一化/任务配置。
- 同一份文件重复导入不重复解析与计算；只有元数据变化时不重算向量。
- 文件修改产生新版本；发布新版本时旧版本从默认检索中退出，历史审批仍能定位原版本。

## 6. 本地资料库与模型使用

资料库按项目隔离，先以 RAG 提供有来源的检索上下文，不把导入当作微调。原始资料、模型生成草稿、用户确认的知识条目分开管理。

导入流程：上传/登记 → staging 校验与 Hash → 原件入对象库 → 数据库登记 → 解析 → 分块 → 按能力建全文/向量索引 → 发布可检索版本。导入状态、索引状态与资料有效状态分开，半成品不进入正式检索。

检索必须先应用项目与用户权限、资料有效版本过滤，再排序，返回资料版本、页码/标题/行号、chunk ID 和引用。Prompt 只装本任务需要的少量片段；缺少证据时明确缺口，不能据资料名称猜正文。审批前记录所用资料版本，保证后续不因资料更新而静默改变依据。

删除采用立即排除检索 + 受控物理清理。派生块和向量同步失效；被审批/验收历史引用的资料按留存规则处理。只有明确启用共享范围，才能跨项目检索或复用经验。

经用户确认、带来源的经验可成为项目知识；模型自述“已成功”和未经核验的失败日志不直接提升为知识。资料中的提示词与指令只作为资料内容，不授予模型工具权限。

## 7. brainstorming 调整范围

定制项目内 `.docloop/skills/spec-create/`，通过有版本的适配策略调用锁定的上游 brainstorming。默认不修改用户全局 Skill，也不直接编辑第三方安装缓存；确需改上游时采用显式 fork/patch 与锁定版本。

新流程建议：识别请求与已有确认 → 检索本项目资料并保留版本引用 → 检查错误前提/缺失信息/矛盾 → 一次汇总必要问题 → 提供有取舍的方案 → 形成 REQ/AC 与存储/测试/数据边界 → 用户审阅 → 审批当前 Spec Hash。

已确认事项直接沿用，不反复提问。允许资料支持的技术判断；未明确的业务事实标为待确认。用户要求直接执行已确认范围时，进入对应阶段，不重新启动整轮探索；仍核对本次实际审批的版本，不把一句确认扩展为以后所有变更的授权。

输出应明确：需求/验收、来源引用、现有实现复用、文件位置、数据库实体、增量类型、权限、测试位置、迁移影响、待确认问题。暂不自动把旧 Spec、模型输出或知识库文章改成新的已批准规则。

## 8. 数据实体与一致性

建议按职责划分实体，实际表名和 DDL 在实施设计时确定：

- 项目与流程：project、change、spec_revision、approval、requirement、acceptance、decision、task、test_case、trace_link。
- 运行与证据：run、task_run、message、event、tool_call、budget_usage、verification_run、verification_check、review、checkpoint、checkpoint_write、recovery_attempt。
- 资料与知识：knowledge_base、document、document_revision、file_object、parse_result、chunk、embedding、knowledge_entry_revision、retrieval_reference、import_job。
- 交付与一致性：artifact_reference、archive_manifest、outbox_job。

不一次性建设全部实体；先保证最小闭环。关系实体使用真实主外键，状态更新使用版本号/条件更新；审批、基线和运行状态在数据库事务内提交。文件系统与 Oracle 不具备普通本地事务的一致提交能力，使用 staging、内容 Hash、状态机和幂等补偿：只有文件校验完成且数据库激活的版本可读；失败任务可重试，不残留“已成功但文件丢失”的状态。

备份必须包含 Oracle 数据、文件库对象和校验清单，按一致版本恢复。只备份 Oracle 或只备份 Git 均不足以恢复完整系统。

## 9. 实施依赖与验收建议

建议顺序：存储接口/文件引用契约 → Oracle 运行数据与 Checkpoint → 资料导入和版本管理 → 基础检索与引用 → 向量能力适配 → brainstorming 接入检索与版本化审批。

共享依赖是 project/document/change/version ID、Hash、事务与权限契约。它们稳定前不并行修改持久化调用链。后续 UI 和解析适配器可在契约冻结后分开实现。

验收至少覆盖：重复导入不重复加工；改文件产生新版本；旧资料即时退出默认检索；跨项目不可见；Oracle 重启后恢复图与预算；文件/数据库单边失败可补偿；真实 Oracle 版本执行迁移与集成测试；检索引用可定位原文；模型输出不自动成为已确认知识；旧审批基线不变。模拟数据库和结构检查不能替代真实 Oracle 验收。

## 文档目录

选型与权威边界 → 存储矩阵 → 建议目录 → Oracle 兼容性 → 增量与生命周期 → 本地资料库 → brainstorming → 数据实体与一致性 → 实施依赖与验收。
