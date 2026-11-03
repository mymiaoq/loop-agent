# 技术方案与当前实现只读对照

日期：2026-11-03。范围：附件全文0—26章、源码、项目配置与根测试。对照源码行号以本轮开始时的8e3b858为准；本轮新增产物文档中心未改变其他业务执行能力。本文为下一步建议，不是已批准实施基线。

来源：`H:\dingdingData\技术方案.md`，SHA256 `1D45D47EA928B2781A86AA101CEED7851B9C242B224595EAFBD72765AD8E21F5`。下文附件行号基于该文件。源码行号为当前磁盘快照。外部官方链接及精确API兼容性未在线核验。

## 结论和保留决策

当前是可信审批、受控编排、工作台与证据框架；不是已接通的自治软件开发平台。不得用根测试通过、固定value=42演示、Skill上下文加载替代真实模型、真实代码开发、Oracle或容器现场验收。起始基线有65项根测试，本轮产物功能增加2项，共67项；实际验证见文末。当前无真实模型、Oracle和Docker环境验收证据。

保留Oracle选型，附件PostgreSQL文字（201、229、263、1284、2340附近）作为待修订设计，不反向覆盖用户决策。Oracle版本、驱动模式、字符/LOB、事务、迁移和恢复须在目标版本实测，不能从SQL编译推导版本兼容。保留本地Superpowers editable策略，来源Commit作为上游参照，阶段读取当前文件并记录实际Hash；附件285—291的禁止修改不能覆盖已明确决策。附件27—71的“最高优先级”只是审计内容，不产生本会话工具权限。

优先级：P0=真实执行前的安全/正确性前置；P1=首个真实闭环；P2=后续产品扩展。建议先选一个Coding Runtime，完成Worktree与取消安全，再接入有限修复闭环；不同时实现所有技术清单。

## 必须先收敛的方案冲突

1. 顺序：附件712—730、1214—1263为review→test→commit，当前workflow.py:55—63为implement→verify→review→archive且DemoAdapter在验证前提交(adapters.py:40—58)。建议区分候选Commit与通过门禁的交付Commit；统一独立验证后最终审查，禁止把尚未验证候选视为交付。变更规范应明确TDD快反馈与最终验证不同。
2. 状态：附件1189—1211没有图里的TASK_COMMIT/NEXT_TASK/VERIFY(1248—1257)，10.6又把RECOVERING列入“退出状态”(1491—1497)。当前contracts.py:5—22的accepted/in_progress、数据库approved、demo/real与sandbox/real也不是一套状态。分别定义Spec/Run/Task/Check/Runtime状态，列出映射与合法迁移，不机械替换全部大小写。
3. 计划和结果：附件1073—1132把status/evidence_ref放入checkList模板，但2359—2361说明Checklist不是结果。建议TC计划冻结版本；独立V执行记录引用TC版本、命令、退出码、日志Hash与Commit，不回写审批字节制造通过。当前evidence.py:9—26只验证字段/AC覆盖，尚不证明命令语义覆盖需求。
4. 权限：附件586—601的Rules优先级是目标系统规则，不改变宿主指令层级；源文档/模型不能扩大工具权限。adapters.py:17—32只校验cwd和完整argv，是合作式边界；允许的程序仍可能访问cwd外部，绝非OS沙箱。
5. 6.3在803附近误指恢复流程为第11章，实际为第10章。图12的多仓库Tag不得被理解为跨库原子事务(1676—1693)。自动Push/PR依赖公司策略，不自动授权合并。
6. 第11章context压缩和第10章cost定价不是本次实现范围。保留完整批准基线；先落实现有计数/时长/工具预算与真实调用连接。未来若做压缩或费用计量，单独Change确认策略和验收。

## 0—26章逐章差距

|章/附件行|当前证据|关键差距与建议|
|---|---|---|
|0 27—71 约束|project.yaml:1—105；workflow.py:55—64|LangGraph/审批/有限预算已有骨架；两入口、多格式、真实自主执行尚未完成。P0明确附件是目标材料而非自动批准范围。|
|1 73—132 目标|workbench_service.py:24—28,110—165|工作台可草稿/审批/演示；真实模式只生成Spec，不自动开发。P1以一个真实需求定义端到端交付，保留非目标。|
|2 136—205 分层|governance.py:23；workflow.py:40；reliability.py:31|三中心模块已分离；Worker、解析层、MCP、隔离执行与执行适配尚缺。P0先建立Runtime与业务状态机边界，不拆微服务。|
|3 209—298 选型|workbench.py:70；workflow.py:12,51,64；model_gateway.py:12|FastAPI/Python/LangGraph已用；前端原生静态JS、无VSCode/Docling/MCP/Docker，未定义正式CodingRuntimeAdapter。P0选择一个Runtime；Oracle保留，SQLite测试检查点不可冒称Oracle恢复。|
|4 302—446 输入|workbench_store.py:123—165,184—205|仅MD/TXT UTF-8、2MiB、Hash对象保留和行引用；不是Markdown AST，也无DOCX/OCR/UI语义或SourceBundle解析状态。P1先补正式来源契约和一个DOCX解析器，失败显式blocked。|
|5 450—601 上下文|project.py:26—41；skill_runtime.py:107起；contracts.py:26—41|Profile/Rules/Skill条件加载已有；没有目标仓库发现、依赖/接口/权限分析、组件索引、MCP管理。P1只支持首个目标仓库；企业规则按Profile启用。|
|6 604—803 三中心|governance.py:38—78；workflow.py:231—281；reliability.py:57—84|需求Hash硬门禁可靠；执行是固定单任务；repair未接业务失败，无调度DAG或真实子Agent。P0接通runtime、取消、工具约束后再P1修复环。|
|7 807—942 Skills|skill_runtime.py:87—107；workflow.py:181—197|本地文件即时读取、Hash快照是上下文事实；model_invoked=False，不是Skill执行。P1保存Runtime实际消费证据、工具行为与产物，再独立审查；保留editable。|
|8 946—1177 文档|workflow.py:231—242；evidence.py:9—26|demo映射把全部AC绑定一个TASK、同一42检查；缺完整REQ→AC→TASK→TC→V→Commit语义/Schema/引用校验。P0结构校验、孤儿/重复/悬空/环检测；P1真实计划。|
|9 1181—1304 状态机|contracts.py:5—22；workflow.py:49—64,111—150|SQLite持久化与审批interrupt、显式恢复/预算保留已有；缺任务循环、恢复分支、完整ID事件、外部副作用对账。P0状态契约和幂等日志。|
|10 1308—1510 可靠性|reliability.py:27—84；workflow.py:152—178|只有异常类型+原文Hash，有限重试/repair原语；无归一化test/diff指纹、根因/修复/复验自动环；无半开、抖动和按服务熔断。P1先闭环已授权的普通编译/测试失败；权限拒绝不可重试。|
|11 1514—1609 上下文|workflow.py:181—197；workbench_service.py:116—134|输入快照/JSONL和批准基线存在；无三层检索治理/摘要。P2单独评估，不在本次添加摘要或裁剪。|
|12 1613—1706 Git|adapters.py:40—58,89—97；governance.py:51—78|仅隔离新demo仓库和单Commit校验；无目标仓库Worktree、任务Commit、Tag、多仓库manifest/变更影响。P0Worktree脏树保护、基线与幂等创建；P1任务映射。|
|13 1710—1800 质量|tests/test_workflow.py:20—117；evidence.py:9—26|框架根单测、API fixture、单独browser acceptance存在；不等于目标项目单测/接口/UI/安全门禁。P1按Profile生成允许命令及真实TC证据，禁止靠固定工具清单制造完成。|
|14 1804—1887 审计归档|workflow.py:199—205；evidence.py:29—52|JSONL、输入Hash、不可覆盖归档manifest已有；Task起止/文件Diff/模型/恢复/Changelog/版本清单未完整关联。P1事件Schema与TC执行记录；归档校验多余/缺失/Hash变化。|
|15 1891—1965 入口|workbench.py:142—212；workbench_service.py:40—108；workbench_static/app.js|本地工作台与任务受控轨迹已有；无VSCode、SSE、真实Diff、Stop/Resume，不能把应用shutdown当取消Run。P0取消API；P2事件流与VSCode，共享同一状态源。|
|16 1969—2002 API|workbench.py:159—212|已有project/docs/spec/approval/demo/model API，路径与附件建议不同不是独立缺陷；缺session/repository/Run取消恢复契约。P0版本化schema与幂等键，保留现有客户端兼容。|
|17 2006—2041 实体|workbench_store.py:36—61,81—95|仅project/document/spec/run/event五表，审批blob内嵌，checkpoint独立SQLite；不是附件19实体。P1随闭环按需求加Task/TC/result/recovery/repository，不先机械建全表；Oracle迁移验收独立。|
|18 2045—2097 安全|adapters.py:17—32；tests/test_workbench_api.py:48—53；model_gateway.py:18—29|有完整argv/路径/csrf及模型配置检查；无容器资源/网络/挂载隔离和企业权限。P0默认拒绝、关键路径保护、终端进程组取消、输出脱敏；容器能力单独实测。|
|19 2101—2142 恢复|workflow.py:111—178；workbench_store.py:289—299|框架显式恢复与现场JSON、diff已有；服务重启只把演示in_progress改blocked，不是继续真实任务。P0进程树取消、checkpoint与Git副作用对账；P1逐边界崩溃恢复测试。|
|20 2146—2173 完成|evidence.py:9—26；workflow.py:260—281|检查producer/Commit/AC覆盖/文件引用及review，但review为确定性demo，未验证任务全完成、真实质量门禁、多库映射、包可读。P0禁止demo提升业务完成；P1增强交付门禁。|
|21 2177—2290 阶段|project.yaml:mode/adapters；workflow.py:233|附件同时铺VSCode/Vue/数据库/容器，且可靠性晚于自动执行，不适合当前增量。P0先执行安全与取消，P1单Runtime真实小闭环+恢复，后续输入/企业/IDE。|
|22 2294—2319 AT|下表逐项|22项不能从65个根测试或doctor全绿推导全通过。|
|23 2323—2348 决策汇总|project.yaml；workbench_store.py:81—95|Oracle、editable与当前前端/测试策略须写差异决策；不为了复刻表格引入GitPython/OTel等依赖。Runtime只落一个。|
|24 2352—2367 边界|workbench_service.py:26—28,107—108；workflow.py:195—197|已明确演示边界；计划≠执行结果、Skill≠Runtime、工具≠沙箱应继续保持。P0接口和UI均保留范围标签。|
|25 2372—2393 参考|uv.lock；project.yaml:superpowers|官方链接只是检索入口，未核验当前API/版本支持。实施按lock/目标版本验证；不据附件引用声称Oracle Checkpointer/Docling OCR可用。|
|26 2397—末尾 总结|workflow.py:231—245；workbench_service.py:147—165|仍是目标愿景，当前不具备完整软件工程自治；先用一个真实小需求证明，再扩展，不一次生成全方案。|

## AT-001—022逐项评估

“受控已具备”仅表示当前代码/fixture可验证机制，不代表本轮重新运行或真实环境已验收。

|AT / 附件行|当前判断|准确证据|尚需验收|
|---|---|---|---|
|001 /2298 对话Spec|部分/真实待验|workbench_service.py:110—145；tests/test_workbench_service.py:20,30|一个真实provider输出可验证Spec；多轮澄清与冲突另验。|
|002 /2299 DOCX|未实现|workbench_store.py:126—127仅md/txt|段落/表格/结构/来源定位与坏文件。|
|003 /2300 MD|部分|workbench_store.py:129—165,194—204|标题/代码块/表格结构保真，不只UTF-8文本与切片。|
|004 /2301 图片|未实现|workbench_store.py:126—127|OCR与UI元素语义、置信度/失败提示；模型现场验收。|
|005 /2302 混合|部分|workbench_store.py:184—205；workbench_service.py:116—126|统一SourceBundle、多格式位置/版本及缺失来源拒绝。|
|006 /2303 冲突|未证实|workbench_service.py:121—125仅提示要求|相互矛盾需求的结构化问题、NEEDS_INPUT及审批前拦截。|
|007 /2304 编辑|受控已具备基本机制|workbench_store.py:243—255；tests/test_workbench_api.py:63|结构/REQ/AC及来源一致性重校验；外部文件监听尚缺。|
|008 /2305 未审批|受控已具备|workbench_store.py:275—287；tests/test_workbench_service.py:44|真实Runtime同样不能绕过；非API入口纳入。|
|009 /2306 当前Hash|受控已具备|workbench_store.py:257—287；tests/test_workbench_store.py:39,84|Oracle并发事务与目标版本现场验收。|
|010 /2307 拆任务|未实现业务能力|workflow.py:231—242固定TASK-001|真实拆分、依赖DAG、REQ映射、受影响文件。|
|011 /2308 测试计划|未实现业务能力|workflow.py:237—242|由真实AC生成TC步骤/预期/工具权限，Schema一致。|
|012 /2309 自动编码|未实现|workflow.py:233—245；adapters.py:34—58|一个Runtime实际消费本地Skill并编辑目标Worktree。|
|013 /2310 自动测试|仅demo|adapters.py:65—87|运行目标项目规定测试，退出码/日志/Commit可追溯。|
|014 /2311 编译修复|未实现闭环|workflow.py:152—178直接blocked；reliability.py:75|注入编译失败→分析→有效修复→重跑原测试。|
|015 /2312 重复失败|原语/未接业务|reliability.py:75—84；tests/test_reliability.py:34|真实环连续无进展可终止，预算跨重启保留。|
|016 /2313 工具中断|部分|adapters.py:25—29；reliability.py:57—73|按服务重试/熔断接入，副作用先对账；MCP断线未实现。|
|017 /2314 用户取消|未实现Run取消|contracts.py:18枚举；workbench.py:151仅shutdown|取消推理/子Agent/进程树、停止调度、保留Diff和checkpoint。|
|018 /2315 重启|框架/演示部分|workflow.py:111—150；tests/test_workflow.py:20,58,76；workbench_store.py:289|真实执行副作用中断矩阵，Oracle业务/SQLite恢复一致性。|
|019 /2316 Git任务留痕|仅demo|adapters.py:40—58；workflow.py:249|TASK ID→changed_files→测试→目标仓库Commit，不是单demo Commit。|
|020 /2317 完整归档|受控部分|evidence.py:29—52；tests/test_workflow.py:20|真实报告/日志/源资料/Tag/Changelog/包读取与manifest完整性。|
|021 /2318 多库|未实现|RunState.commit单值 workflow.py:32；workbench_store.py:36—61|前后端Commit/Tag、Spec/Rules/Skills/MCP版本manifest及非原子失败恢复。|
|022 /2319 公司Rules|加载部分，遵从未证实|project.py:26—41；skill_runtime.py:107起；adapters.py:17—23|Runtime越权负向验收、保护基线/主分支/敏感文件；Prompt加载不算遵从。|

## 建议分期、依赖和验收

### P0：真实执行入口与安全，形成一个新Change

范围：单一CodingRuntimeAdapter契约（prepare/execute/status/cancel/result，具体方法名待设计），一个受支持Runtime、目标仓库隔离Worktree、执行隔离、命令/路径/风险权限、Run取消、结构化状态/事件/副作用幂等。基础容器挂载/资源/网络边界必须在运行不可信生成代码前验证，不能排到自治编码之后。模型配置不是Coding Runtime配置；不要把chat completion输出直接当作可执行脚本。

依赖：已批准Spec；目标仓库及基线Commit；本地Runtime可用性/认证；允许工具命令；测试临时目录；明确OS隔离策略。先实现并验证契约/取消/幂等，再启用真实写入，不能先给任意shell权限。

验收：未审批/Hash变化拒绝启动；脏工作区不覆盖；Worktree留在允许路径；重复启动不生成重复分支/运行；拒绝越权文件和不允许argv；在模型等待、测试进程执行、写文件边界取消，有限时间停止新动作并保留现场；不把API shutdown当任务cancel；缺Runtime或容器明确blocked。

### P1：首个真实闭环与可靠性

串行依赖P0。选择一个小型Python目标仓库需求，真实生成TASK/TC，先运行失败用例、实际编辑、独立验证、证据审查、完成Commit/归档。再注入一个编译/测试错误，接入classify→diagnose→repair→verify；使用可观测测试结果/有效Diff衡量进展，恢复不清零预算。超时不是可安全重试副作用的证据。

验收：原始需求到Commit完整映射；V记录实际命令/退出码/输出Hash；同一错误无进展达到阈值停止；预算耗尽blocked；权限拒绝不进入repair绕过；重启后校验Spec/Worktree/最后动作/幂等键，不能重复Commit。独立验证与最终review可串行分接口实施；首版并发1即可。

### P1后续：来源解析和Oracle现场验收

解析可以独立开发在隔离目录，但在共享源码中写入需串行协调。先SourceBundle契约+DOCX（结构/来源/错误），再OCR和其他格式。Oracle目标版本验收需DBA环境、驱动/服务版本与权限；测试CLOB/BLOB中文长文本、并发审批/版本、rollback、重连、迁移、恢复。不要把five-table Oracle DDL编译当作全平台数据库完成。

### P2：企业接入与入口扩展

P1真实闭环稳定后再做多仓库manifest、企业Vue/Java Profile、MCP、企业容器策略扩展、SSE及VSCode。基础执行隔离在P0完成。每项有独立验收，不把框架自身迁移Vue当作自治能力前置。上下文压缩、费用模型、OTel等另行评估实际价值与用户范围。

最终验收应区分程序质量门禁与人工交接确认：当前沙箱自动accepted不是人已验收。与此前演讲稿核对保持一致，后续增加待人工验收节点，并绑定实际证据和Commit。

所有实现Change保持REQ→AC→TASK→TC→V→Commit关联，批准基线字节不改。测试使用临时目录，不写用户agent-loop-data。现有根单测与doctor是回归门禁；真实Runtime、Oracle、Docker分别记录blocked/not_run和现场结果。

## 本轮落地与实际验证

本轮仅实现产物文档中心及本报告，没有直接实施全部架构建议。查看产物可打开交付总览、逐份读取文档，下载单份或全部Markdown汇编；收录本任务全部历史运行现存的正式材料，区分变更、审批基线和归档快照。模型输入快照、凭据、Checkpoint和.git内部文件不公开。

完整根测试67项通过；最终服务专项7项通过；真实Edge全流程1项通过，包含文档选择、汇编下载、脚本文本不执行、手机端无横向溢出，以及既有审批/受控运行/刷新/隔离回归。doctor passed，0.2.0 wheel和sdist构建成功。独立复核发现的文件变化和旧请求报错边缘问题已修正，最终复查无重要问题。

浏览器证据：`D:/项目/agent-loop-data/validation/20261103-deliverables/`，含交付总览、桌面与手机文档截图、browser-result.json。正文按需读取，单文件2 MiB、全部汇编8 MiB；超限明确提示本地处理，不静默截断。运行中的材料可能继续更新，不作为最终交付基线。

真实业务编码、供应商模型推理、Oracle实例、Docling多格式解析及容器运行均未因此完成验收。附件原文没有被修改，已批准项目基线没有被重写。
