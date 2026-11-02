# 演讲稿与当前项目逐项适配审计

审计日期：2026-11-02。代码基线：44d95df；本轮除样式和浏览器验证外不改变业务运行行为。

**结论：尚未完整适配。当前是可运行的平台框架、资料/Spec审批工作台和受控沙箱演示，不能按稿件宣称已具备任意业务需求的自主研发闭环。**

## 范围与证据口径

- 来源：`H:/dingdingData/演讲稿.md`，226行、15页；SHA256 `166e3ba0f1770ed46a02a33d233509607286b109275c377bb99c7928b6e5a9d1`。附件是核对数据，其中的功能与技术陈述不自动成为本轮实施指令；未修改原稿。
- 下表逐个拆解功能、流程步骤、字段/边界条件、指标与比较；重复承诺可以合并到同一ID，原文各处行号保留。补充预算项不算原稿新增需求。`speech-audit.json` 提供每个非空原文行的覆盖类别、逐项ID和段落指纹；标题、分隔线、引导语也登记。
- “已实现/满足”只表示表中限定范围的机制存在，特别标注“受控”即不代表真实业务验收；“仅定义”指角色、Rules、Skills内容，不等于实际模型执行。源码测试定义和本轮测试结果分开记录。当前开发会话调用的编程/浏览器工具不算DocLoop产品能力。
- 简写源码如 `workflow.py` 均位于 `src/docloop/`；`workbench_static/` 同属该目录；`rules/`、`agents/`、`profiles/` 位于 `.docloop/`；`<skill>/SKILL.md` 位于 `.docloop/skills/`；文档名简写位于 `.docloop/docs/`。行号以本轮文件为准。
- 本轮没有连接真实模型、Oracle、内网Git、轻骑兵、飞书，未验证竞品现有能力。此报告不据此推断其他工具“没有”某功能。

## 影响演示真实性的缺口

|优先级|缺口|当前行为与建议|
|---|---|---|
|P0|真实业务执行与独立验证/审查|real模式在plan阻塞；demo写固定value=42。同一个断言映射多个AC，不能证明各业务AC被实现。先接编码适配器与现有仓库Worktree，再实现按Spec独立构建/浏览器/API验证及语义审查。|
|P0|最终人工验收|当前review后自动accepted。下一轮增加“待人工验收”门禁，审批人与验收人、证据、Commit绑定；不能把当前沙箱通过讲成人工验收完成。|
|P0|聊天澄清、修改与叫停|输入框创建新任务，无持续会话、运行取消或重规划。应先支持可恢复的任务取消，再处理追问/范围变化与新基线审批。|
|P1|自动修复与无进展监控|repair原语存在但未接入工作流；不能宣称已自动换思路修复3轮。应以实际进展和副作用核对接入有界修复。|
|P1|真实工单示例与交付物|xlsx/日期/角色/审计等业务均未实现；技术设计、语义changelog、PR与性能数据没有该案例证据。先选定真实业务仓库做小范围完整验收。|
|P1|Oracle及追溯|有关系契约/兼容DDL，真实实例未验收；Checkpoint仍SQLite。REQ到源码行、完整聊天与真实运行尚缺。按后续Oracle+本地对象库方案补齐，不回退成“所有数据都在源码.docloop”。|
|稿件修订|指标、绝对化与设计冲突|删除或标为目标：47用例/82%/40分钟/已提PR；默认端口改8765（可另配3000）；RESTful改为遵循历史接口契约；Hash改为偏离可检测并阻断；竞品比较改为有证据的同口径比较。|

建议现场口径：“已完成平台框架、本地资料与需求审批工作台、Hash基线和受控成功/失败演示；真实业务自动编码、独立业务验证、持续聊天与人工最终验收仍在下一阶段。”不报告含混的完成百分比。

## 逐项检查

以下前后两部分均来自独立只读核对，主审复核关键源码和本轮运行结果后合并。表中“未跑测试”指分项审计员；统一执行结果见文末。

## 第1页：端到端与交付物

|ID|原稿行|承诺|结论|代码/测试证据与界限|
|---|---|---|---|---|
|SP-01-01|15|理解需求|部分/真实效果未验证|workbench_service.py:110-145 有生成Spec路径，real调用gateway、sandbox填固定草稿；非持续对话理解。tests/test_workbench_service.py:20,30,35 为相关用例。|
|SP-01-02|15|自动拆任务|部分|workflow.py:231-241 只生成固定TASK-001沙箱计划，real在233阻塞。|
|SP-01-03|15|自动写代码|缺失（业务能力）|adapters.py:40-57 仅写result.json并提交；workflow.py:233直接声明无业务实现执行。|
|SP-01-04|15|自动跑测试|部分|adapters.py:65-86 实跑子进程解析JSON断言value=42，未实现业务测试选择/生成/运行。|
|SP-01-05|15|自动整理文档|部分|workflow.py:237-241,255-271 写固定计划、证据、审查；evidence.py:29-51复制归档，无通用技术设计/报告生成器。|
|SP-01-06|15|一整套自己跑完|部分且表述过强|demo能走审批后六阶段，real在plan阻塞；tests/test_workflow.py:20,42覆盖这两种语义。|
|SP-01-07|15|每一步留痕|部分|workflow.py:199-205记阶段/状态/mode/usage；181-197记上下文hash；不是每个模型思考或业务动作日志。|
|SP-01-08|15|交付需求文档|已实现（Spec保存）|governance.py:38-46保存spec与来源，51-63保存基线。|
|SP-01-09|15|交付设计文档|缺失（通用自动产出）|evidence.py:31必需清单只有spec/decisions/tasks/checkList/evidence/review，没有technical-design。|
|SP-01-10|15|交付测试报告|部分|workflow.py:255-256写evidence.yaml，但具体内容来自固定JSON验证。|
|SP-01-11|15|交付变更记录|部分|evidence.py:29-51归档文件与hash清单；不是自动语义changelog。|
|SP-01-12|17|干活并自己写报告|部分|固定demo控制流会写结构化证据；真实业务Agent报告闭环尚无。|

## 第2—4页：五角色与三控制中心

|ID|原稿行|承诺|结论|代码/测试证据与界限|
|---|---|---|---|---|
|SP-02-01|27,55|orchestrator总调度、不写业务代码|部分|.docloop/agents/orchestrator-agent.md:3-24定义；workflow.py:52-64固定节点路由是真实编排，非模型自主派工。|
|SP-02-02|28,56|spec-agent将模糊话整理成Spec|部分/真实效果未验证|workbench_service.py:118-134构造本地Skill上下文并可调用模型；135-145为沙箱固定模板。|
|SP-02-03|56|spec-agent主动列疑问并追问|部分|workbench_service.py:120-122在提示中要求待确认事项；缺少多轮追问状态机/问答闭环，不能把提示要求当模型已遵从。|
|SP-02-04|28,57|implement-agent照测试写业务代码|仅定义/业务执行缺失|.docloop/agents/implement-agent.md:3-26规定TDD和编译；adapters.py:40-57为确定性result.json写入。|
|SP-02-05|57|implement快速编译/构建|仅定义|.docloop/agents/implement-agent.md:22-27有要求；DemoAdapter未运行应用构建。|
|SP-02-06|57|implement最多推到implemented|已实现（契约级）|contracts.py:5-21将in_progress→implemented限定implement，implemented→verified限定verify；tests/test_governance.py:41。角色是调用传入的字符串，非独立身份认证。|
|SP-02-07|28,58|verify-agent独立验证|部分|adapters.py:65-76另起子进程不消费实现者通过声明，是真实独立检查；仍同一Python适配器实现，非独立模型主体。|
|SP-02-08|58|verify按Spec验收语义制定测试|缺失|adapters.py:67-69固定断言42；80-85把同一结果复制给每个AC，不能证明多个不同AC的语义覆盖。|
|SP-02-09|58|verify自己跑业务构建|仅定义|.docloop/rules/verification-standard.md:11-26为领域路由；adapters.py:65-86只跑JSON脚本。|
|SP-02-10|58|verify自己开浏览器点一遍|仅定义/未接入|project.yaml adapters.browser=null；workflow._verify仅DemoAdapter；浏览器验收测试不等于运行时Browser Adapter。|
|SP-02-11|58|verify自己测业务接口|仅定义/未接入|workflow.py:252-258未调用HTTP业务验证，只有JSON验证。|
|SP-02-12|58|verify产evidence|已实现（受控）|workflow.py:255-257写evidence.yaml并校验，adapters.py:78-85含Commit、TC、观察、日志引用。|
|SP-02-13|28,59|review检查命名和分层|仅定义|.docloop/agents/review-agent.md:9-15定义；workflow.py:260-271仅检查证据结构/文件，明确无语义业务代码审查。|
|SP-02-14|59|review检查禁区|仅定义/部分基础边界|角色规则有要求；ToolAdapter:17-27限定cwd和完整argv，非review自动扫描保护文件差异。|
|SP-02-15|59|review检查证据充分性|部分|workflow.py:262-267验证覆盖字段和引用文件存在，不验证测试含义是否满足业务AC。|
|SP-02-16|59|review不跑测试、不写代码|部分|当前_review仅读证据、写review.yaml；角色文本有职责分离，未形成OS级身份/权限隔离。|
|SP-02-17|29,40|需求中控管来源/审批，不碰业务代码|已实现（治理机制）|governance.py:38-75负责source、baseline、hash；不含业务写入。需求语义澄清由另一路径模型提示实现。|
|SP-02-18|29,41|执行中控安排Agent和Skill|部分|workflow.py:52-64固定阶段；181-197加载当前本地上下文，不调用真实编码Agent。|
|SP-02-19|29,42|可靠性中控管重试、停止|部分|reliability.py:43-84有预算、重试、repair原语；repair未在当前src调用，不能说已自动运行修复循环。|
|SP-02-20|42|可靠性不改需求、不绕权限|部分|governance.py:66-75每阶段前hash断言（workflow.py:158），ToolAdapter完整argv；合作式边界，不是OS沙箱。|
|SP-02-21|30,45|Rules/Skills存在|已实现（资源/加载）|project.py:26-42加载按profile选的规则；44-76检查五角色、15技能格式与路由；skill_runtime相关测试:39-117。|
|SP-02-22|43|Superpowers先想清楚|仅定义/加载已实现|project.yaml stage.spec映射brainstorming；workflow.py:181-197记录加载，未调用模型证明遵从。|
|SP-02-23|43|自动Git Worktree隔离|仅定义/缺失执行|project.yaml stage.plan加载using-git-worktrees；adapters.py:43是git init -b demo，新仓库，不是现有主仓库worktree。|
|SP-02-24|43|TDD先测试后代码|仅定义|project.yaml stage.implement映射TDD，DemoAdapter没有红绿循环。|
|SP-02-25|43|写完自己审查|部分|固定证据review有实现，无专业语义review。|
|SP-02-26|25,32,44,47,61|五Agent各不越权，独立裁判|部分且表述过强|contracts.py:5-21有角色状态契约，五角色文件存在；同一进程按字符串分配producer，尚无五独立模型/进程/身份权限系统。|
|SP-02-27|45|Rules/Skills不调度、不授权|已实现（框架设计边界）|project.py与skill_runtime加载内容；流程由Workflow负责，工具权限由ToolAdapter负责；加载Skill不执行插件hooks/任意命令。|

## 第5页：12步逐项

|ID|步/原稿行|承诺|结论|代码证据|
|---|---|---|---|---|
|SP-05-01|1 / 69|聊天输入需求|部分|workbench_service.py:110-124接受requirement字符串，不是完整多轮聊天。|
|SP-05-02|1 / 69|扔文档|部分|workbench_store.py:123-165文档导入/版本；工作台上传支持范围需另审，不是任意文件解析。|
|SP-05-03|1 / 69|贴代码|部分|requirement可接收文本，非专门代码仓库导入/语义解析。|
|SP-05-04|2 / 70|先澄清，有疑问先问|仅定义/缺少交互闭环|Spec提示要求待确认事项（workbench_service.py:120-122），无持续需求问答节点。|
|SP-05-05|3 / 71|出Spec草稿|已实现（路径）；真实质量未验证|workbench_service.py:110-145；real调用网关，sandbox固定模板。|
|SP-05-06|4 / 72|人看、驳回后改|已实现（保存/审批）|workbench_store.py:243-273带revision保存与审批；workflow.py:103-109显式SHA256+approver；无专门驳回意见循环。|
|SP-05-07|5 / 73|基线锁死|已实现（检测/拒绝）|governance.py:51-75独占审批记录、原字节副本、每次比hash；不是文件系统不能改，篡改后会被检测阻断。|
|SP-05-08|6 / 74|开现有仓库Git分支隔离主线|缺失（生产流程）|adapters.py:43创建独立demo仓库；无git worktree add/现有主仓库branch操作。|
|SP-05-09|7 / 75|拆真实任务|部分|workflow.py:237-239固定TASK-001，无真实需求任务分解。|
|SP-05-10|7 / 75|列验收清单|部分|workflow.py:235-241从AC标识生成映射，未解析验收语义。|
|SP-05-11|8 / 76|实现业务代码|缺失|workflow.py:231-233 real阻断；adapters.py:51-52只写result.json。|
|SP-05-12|9 / 77|验证业务功能|部分|adapters.py:65-86仅value=42受控验证。|
|SP-05-13|10 / 78|专业代码审查签字|部分|workflow.py:260-271确定性证据审查并写producer；没有真实审查模型签名/代码语义判断。|
|SP-05-14|11 / 79|orchestrator认定结束|已实现（受控门禁）|workflow.py:274-281要求review passed、证据合格、Commit一致再accepted。|
|SP-05-15|12 / 80|全部归档|已实现（Change目录）|evidence.py:29-51复制source目录并写manifest；不是所有外部聊天/模型/主仓库都纳入。|
|SP-05-16|总体 / 67|12步不能跳|部分且表述过强|图只有approval→plan→implement→verify→review→archive六节点（workflow.py:52-63）；需求接收/澄清/Spec创建在图外，未强制12独立门禁。|
|SP-05-17|总体 / 82|审批人拍板|已实现|workflow.py:103-109,212-229；approver是显式字符串，无用户认证证明。|
|SP-05-18|总体 / 82|最终验收人拍板|缺失（当前工作流）|workflow.py:274-281审查后自动accepted，无human-acceptance interrupt/accept API；不能把Spec审批等同最终人工验收。|

## 第6页：四类规则内容、适用范围与执行强度

|ID|原稿行|承诺|结论|证据|
|---|---|---|---|---|
|SP-06-01|88,95|4份硬规矩全局必须遵守|部分/适用范围有误|当前profile=docloop-platform，仅code/verification；.docloop/profiles/docloop-platform.yaml:1-7。enterprise profile才按领域选UI/API（enterprise-vue-java.yaml:1-13）；规则文本不是自动静态检查器。|
|SP-06-02|90|Vue3/ElementPlus/Java8/MyBatisPlus|仅定义且条件启用|enterprise-vue-java.yaml:11-13与rules/enterprise/code-standard.md；当前平台Python，不能说全平台定死企业栈。|
|SP-06-03|90|命名、分层、注释、禁区|仅定义/部分边界|rules/code-standard.md:9-18为原则；agents/review-agent.md:9-15为审查要求；无全量代码合规检查器。|
|SP-06-04|91|RESTful路径|仅定义且原稿绝对化|rules/api-standard.md:94允许保持相邻接口风格、不强制改RESTful；受enterprise/API条件加载。|
|SP-06-05|91|返回体、错误码、分页|仅定义|rules/api-standard.md:18-35规定code/count/data/page/limit；运行时未自动扫描或强制企业项目输出。|
|SP-06-06|91|鉴权、网关|仅定义/不能等于实现|存在规范不代表运行框架已为目标应用生成鉴权网关；Workflow无业务API适配器（231-245）。|
|SP-06-07|92|铁科蓝/绿|仅定义且条件启用|rules/ui-standard.md:3,28-29明确enterprise，当前docloop-platform不加载该UI规则。|
|SP-06-08|92|组件复用|仅定义|ui-standard.md:11-20给组件优先级；无运行时组件生成验证器。|
|SP-06-09|92|响应式|仅定义|ui-standard.md:184起；自动业务浏览器验证未接入。|
|SP-06-10|92|无障碍保证|部分规则/缺少完整定义/未验证|ui-standard.md:74尊重减少动态偏好、190移动端不依赖hover；未见完整键盘/焦点/语义/对比度无障碍条款及自动a11y验收适配器，不能讲保证。|
|SP-06-11|93|evidence格式|已实现（核心字段校验）|evidence.py:9-26检查producer/commit/必填项/结果/AC覆盖/阻塞项。|
|SP-06-12|93|截图、日志|部分|workflow.py:264-267检查引用存在；adapters.py:74-85产生日志，没有截图自动采集。|
|SP-06-13|93|过/不过标准|已实现（结构门禁）|evidence.py:17拒绝非passed、23覆盖不足拒绝、25阻塞拒绝；业务语义真实性仍未验证。|
|SP-06-14|95|公司Harness法条自动执行|仅定义/来源未验证|规则文本存在，但本审计没有外部公司规范对照，也无自动证明模型遵从机制。|

## 第7页：状态及每一个limit

|ID|原稿行/配置|承诺|结论|证据与准确语义|
|---|---|---|---|---|
|SP-07-01|103|draft→ready|已实现|contracts.py:6；workflow.py:242由orchestrator角色推进。|
|SP-07-02|103|ready→in_progress|已实现|contracts.py:7；workflow.py:248。|
|SP-07-03|103|in_progress→implemented|已实现|contracts.py:8；workflow.py:250。|
|SP-07-04|103|implemented→verified|已实现|contracts.py:9；workflow.py:257-258先验证证据。|
|SP-07-05|103|verified→accepted|已实现（受控）|contracts.py:10；workflow.py:274-281审查/证据/commit门禁，但没有最终人工验收节点。|
|SP-07-06|105|failed不算完成|已实现|contracts.py:16终态；evidence.py:17非passed拒绝。|
|SP-07-07|105|blocked不算完成|已实现|workflow.py:60-62提前END，165-178写blocked恢复；evidence.py:17拒绝。|
|SP-07-08|105|not_run不算完成|已实现（证据结果），非任务状态|evidence.py:17拒绝；contracts.py未定义not_run任务状态转换。|
|SP-07-09|107 / no_progress=2|连续两轮无进展自动停|部分|reliability.py:75-84原语存在，首次设基准，后两次相同progress在第三次repair调用阻塞；src没有repair调用点，未接进业务修复循环。tests/test_reliability.py:34-44只是原语测试。|
|SP-07-10|107 / retries=3|小毛病最多重试3次|已实现（限定异常类型）|reliability.py:57-72仅TimeoutError/ConnectionError，初次+3重试=4次调用；model_gateway.py:74实际使用。业务逻辑错误不重试（tests/test_reliability.py:15）。|
|SP-07-11|107 / repairs=3|任务最多修3轮|部分|reliability.py:77-84有计数上限，当前Workflow没有自动repair调用或重实现边。|
|SP-07-12|limits.llm=30|LLM预算|部分|Reliability.charge支持；Workflow不调LLM；Spec网关自行建Limits(llm=4)（model_gateway.py:40），不是共享项目30次。|
|SP-07-13|limits.tokens=100000|token预算|部分|reliability.py:49-55计量；model_gateway.py:67-68仅供应商返回有效total_tokens才charge，不能完整衡量未知usage；非跨阶段统一模型账本。|
|SP-07-14|limits.tools=100|工具预算|已实现（适配器调用）|adapters.py:24每次ToolAdapter.run charge；不覆盖绕开适配器的任意外部操作。|
|SP-07-15|limits.model_rounds=20|模型轮数|部分|网关charge model_rounds但自行Limits(model_rounds=4)，Workflow无真实模型循环。|
|SP-07-16|limits.task_seconds=600|任务时限|部分|reliability.py:43-47在charge/call/repair前后检查；非抢占式取消；阻塞操作依赖其自身timeout。|
|SP-07-17|limits.run_seconds=3600|运行时限|部分|同上；workflow.py:137-150持久化开始时间和预算，恢复不重置。|
|SP-07-18|limits.concurrency=1|并发上限|部分|Reliability具计量字段，但未见工作流charge concurrency；execution_lock提供运行锁，不能直接当全局资源并发计量。|
|SP-07-19|limits.graph_steps=50|图步数|已实现|workflow.py:74 recursion_limit；157逐阶段charge，预算137-150持久化。|
|SP-07-20|limits.circuit_failures=5|外部熔断|部分|reliability.py:60-61有原语；网关使用外部call但每次complete新建Reliability，不能视为跨多次请求持久熔断。|
|SP-07-21|107|不会死循环耗着|部分|固定LangGraph有上限/END、工具超时；真实自修复Agent loop尚不存在，不能以有限demo证明未来业务循环行为。|

## 第8页：目录与追溯

|ID|原稿行|承诺|结论|证据与界限|
|---|---|---|---|---|
|SP-08-01|113|所有东西都在项目.docloop|有误/部分|配置在项目.docloop，但工作台默认数据根在同级agent-loop-data（workbench.py:297）；runs/inputs/文档数据不全在源仓库.docloop。|
|SP-08-02|115|agents提示词|已实现|五个文件在.docloop/agents；project.py:44-52检查角色集合。|
|SP-08-03|116|四类rules|已实现（文件），有额外enterprise代码规范|.docloop/rules/{code,api,ui,verification}-standard.md及enterprise/code-standard.md；并非只有四个规则文件。|
|SP-08-04|117|skills现成工具|部分|15个专业Skill定义+本地superpowers目录；project.py:10-14,53-68校验契约；不是每个Skill都具真实工具执行实现。|
|SP-08-05|118|每个Change独立目录|已实现|governance.py:27-46限制ID、拒绝目录复用，生成.docloop/changes/id。|
|SP-08-06|118|Spec|已实现|governance.py:43写原文，60基线副本。|
|SP-08-07|118|决策记录|部分|governance.py:44仅初始化No approved decisions yet，未见通用决策自动提取/增量更新器。|
|SP-08-08|118|任务拆分|部分|workflow.py:237-239固定demo任务。|
|SP-08-09|118|验收清单|部分|workflow.py:235-241固定映射表。|
|SP-08-10|118|测试证据|已实现（受控）|workflow.py:255-257；adapters.py:74-86含实际日志、commit。|
|SP-08-11|118|审查记录|已实现（确定性证据审查）|workflow.py:268-271写review.yaml；无语义代码review。|
|SP-08-12|119|聊天记录|缺失（通用多轮聊天）/部分输入记录|governance.py:45-46只记录来源Spec行；workbench_service.py:129保存最终模型输入快照；workbench_store表为documents/specs/runs/audit，无通用会话messages历史。|
|SP-08-13|119|检查点快照|已实现|workflow.py:49-64 SQLite SqliteSaver；137-150预算快照。|
|SP-08-14|119|执行轨迹|已实现（阶段/Skill记录）|workflow.py:191-205 JSONL；工作台读取最多1000条/trace（workbench_service.py:73）。|
|SP-08-15|119|恢复记录|已实现|workflow.py:165-178保存失败节点/指纹/预算/diff/下一步；118-135需人工recover，不自动唤醒。|
|SP-08-16|121|验收后归档文档/变更记录|已实现（受控accepted）|evidence.py:29-51含hash manifest、staging rename、防覆盖；“验收”不是人工最终验收，工作台归档在独立run root下。|
|SP-08-17|121|业务代码在src|部分/目标未实现|框架Python代码确在src/docloop；demo产物实际在.docloop/sessions/id/result.json（workflow.py:245），不是生成业务src。|
|SP-08-18|121|用Git管理|已实现（demo真实提交）|adapters.py:43-57 git init/add/commit/rev-parse；不是目标主仓库集成/PR。|
|SP-08-19|123|从原话追到需求|部分|sources.json带原始Spec行（governance.py:45-46）；工作台references有资料版本与行（store.py:184-205）；不等于所有历史聊天都保留。|
|SP-08-20|123|REQ→AC→TASK→TC→V|部分|workflow.py:235-241只生成AC→TASK→TC→V；未强制REQ解析或REQ覆盖，TaskContext无这类关联结构。|
|SP-08-21|123|追到哪行代码|缺失（自动行级关联）|evidence.py只关联AC/TC/Commit，DemoAdapter未记录需求→源码路径/行映射。|
|SP-08-22|123|追到哪个Commit|已实现（受控）|adapters.py:71,78与89-97核对HEAD和洁净工作区；evidence.py:12要求SHA字段。|
|SP-08-23|123|追到哪份测试报告|已实现（受控路径）|workflow.py:255固定evidence.yaml，引用日志且review校验其在change内存在（264-267）。|
|SP-08-24|123|三个月后完整可追溯|部分/时间跨度未验证|归档hash/SQLite/JSONL具备持久化机制，未做三个月保存/备份/迁移/外部模型真实性验收。|


## 第9页（原稿127—139）

| ID | 原稿行 | 承诺 | 判定及代码/测试证据 |
|---|---|---|---|
|SP-09-01 |131、138|VSCode 写代码、直接打开、提交/分支/diff|部分；源码文件可由编辑器打开，但无 VSCode 集成实现。`adapters.py:43-57,89-96` 是受控独立 Git 仓库提交和洁净检查；不是用户业务仓库的 Worktree/IDE 工作流。`workbench-acceptance.md:35` 明列真实业务 Worktree 待实现。稿件需修订。|
|SP-09-02 |132|本地3000端口看记录|部分；本地工作台及记录存在 `workbench.py:181-183,252-267`，默认端口实际8765（同文件290行、`cli.py:28`）。3000需改8765或明确另行配置。|
|SP-09-03 |136|聊天框追问、改主意|缺失；`workbench_static/index.html:1` 明示“提交将新建任务，不会修改当前任务”；`workbench.py:177-195` 仅创建/编辑/审批Spec和运行API，无会话消息/追问API。生成器 `workbench_service.py:110-145` 单次草稿，不能称持续聊天。|
|SP-09-04 |137|看改文件、测试、文档|部分；`workbench_service.py:40-108` 显示实际阶段、Skill加载、检查与产物，但仅受控沙箱 result.json、tasks/checkList/evidence/review；非业务 diff/真实业务测试。`tests/test_workbench_service.py:58` 起测试执行区，未证明业务编码。|
|SP-09-05 |139|说“停”立即刹车、“改成XX”改变运行|缺失；无任务取消/自然语言控制API（`workbench.py:157-210`完整路由）；`shutdown:149-155` 是停止整个服务，`contracts.py:18` 有 cancelled 状态也不构成叫停入口。必须删除即时承诺。|

## 第10页（原稿143—151）

专业 Skill 文件确有15个唯一目录；9通用+7领域中的 document-parser 是同一个共享定义，不能称16个独立工具。各文件 `SKILL.md:2-3` 是名称/描述证据；内容加载器 `skill_runtime.py:107-142` 组装上下文，显式 model_invoked=false；`workflow.py:181-197` 记录 skill.loaded；`tests/test_skill_runtime.py:72-99` 证明本地内容和加载，不证明模型执行。以下逐项不把文档存在当功能完成。

| ID |原稿行|逐项Skill|判定与证据|
|---|---|---|---|
|SP-10-01 |147|解析文档|部分；`.docloop/skills/document-parser/SKILL.md:2-3` 定义；`workbench_store.py:123-128` 只接受UTF-8 md/txt、2MiB；非多格式解析。|
|SP-10-02 |147|生成spec|部分；`spec-create/SKILL.md:2-3`；`workbench_service.py:118-145` 可组装本地输入、固定沙箱草稿或调用已配置网关；真实生成效果未验证，未持续澄清。|
|SP-10-03 |147|拆任务|部分；`plan-create/SKILL.md:2-3`；`workflow.py:231-239` 固定TASK-001，不是实际业务拆解。|
|SP-10-04 |147|验收清单|部分；`checklist-create/SKILL.md:2-3`；`workflow.py:235-241` 按AC编号生成表，未生成业务测试。|
|SP-10-05 |147|项目初始化|部分；`project-bootstrap/SKILL.md:2-3`；`adapters.py:43-50` 只初始化demo仓库，无真实Worktree适配。|
|SP-10-06 |147|跑测试|部分；`test-runner/SKILL.md:2-3`；`adapters.py:65-86` 只检查value=42。|
|SP-10-07 |147|审计日志|满足（框架记录）；`audit-recorder/SKILL.md:2-3`；`workflow.py:193-205` 实际记录阶段、状态、Skill指纹。不能扩为业务导出审计。|
|SP-10-08 |147|卡壳诊断|部分；`recovery-diagnosis/SKILL.md:2-3`；`workflow.py:165-178` 保存阻塞、错误指纹与下一步；无真实模型分析证明。|
|SP-10-09 |147|归档|满足（受控产物）；`project-archiving/SKILL.md:2-3`；`workflow.py:274-281`、`tests/test_workflow.py:20-30` 定义验证归档门禁；非业务全套交付。|
|SP-10-10 |149|Vue组件生成|未验证；`component-generator/SKILL.md:2-3` 定义，真实coding未配置 `project.yaml:59-64`；`workflow.py:231-233` blocked。|
|SP-10-11 |149|Java接口生成|未验证；`api-contract/SKILL.md:2-3` 只定义API契约和前端封装，不能等同Java接口生成；Java后端生成定义对应 `backend-code-generator/SKILL.md:2-3`，同上无真实Java生成适配。|
|SP-10-12 |149|MyBatis Plus CRUD|未验证；`backend-code-generator/SKILL.md:2-3`、enterprise Profile stack定义；同上无业务执行。|
|SP-10-13 |149|铁科蓝页面|未验证；`frontend-design/SKILL.md:2-3` 及UI Rules是规则内容；默认Profile `project.yaml:2` 为docloop-platform，当前工作台原生HTML/JS/CSS，不是企业Vue应用。|
|SP-10-14 |149|前端质量检查|未验证；`frontend-quality-check/SKILL.md:2-3` 定义；`project.yaml:61` browser=null；真实企业检查未执行。|
|SP-10-15 |149|等保三级/国密检查|未验证；`security-check/SKILL.md:2-3` 是范围明确的审查定义，不是认证/自动合规证明。|
|SP-10-16 |149|复用解析|部分；共享document-parser，支持范围同147行，不应重复算唯一Skill。|
|SP-10-17 |151|直接插入新工具、不影响整体流程|部分；`workbench_service.py:168-175` 枚举磁盘Skill；`skill_runtime.py:28-41,87-98,107-116` 仍校验路由、命名、frontmatter，阶段需配置。应称可按规范扩展，需验证，不能保证无影响。|

## 第11页（155—169）：工单导出例子的每个条件

原稿157“实际例子”与159“假设”冲突。应明确“目标需求示例，尚未实现验收”。`src/` 是DocLoop框架，无工单实体、导出服务或xlsx实现；`workbench_service.py:138-144` 沙箱只嵌入原始文本和通用AC，不能自动生成稿中业务细则。真实模型草稿效果未验证（`.docloop/docs/workbench-acceptance.md:33-35`）。

| ID |原稿行|条件/示例|判定与定位|
|---|---|---|---|
|SP-11-01 |159|飞书输入|缺失；`workbench.py:157-210` 无飞书路由/连接器；只本地API。|
|SP-11-02 |159、163|理解PM随意需求并生成用户故事|未验证；`workbench_service.py:130-134` 仅具备通用网关调用；135-144沙箱无语义分析。|
|SP-11-03 |159、164|日期范围筛选|缺失；`workflow.py:237-239`、`adapters.py:51-52` 只固定JSON。|
|SP-11-04 |159、164|点导出生成文件并下载|缺失；`workbench.py:157-210` 无业务导出/下载接口，`adapters.py:51-52` 产物仅JSON。|
|SP-11-05 |159|标准xlsx而非CSV|缺失；同上无xlsx序列化或业务测试。|
|SP-11-06 |165|工单号字段|缺失；`adapters.py:51-52` 只有mode/value。|
|SP-11-07 |165|客户字段|缺失；同上。|
|SP-11-08 |165|金额字段|缺失；同上。|
|SP-11-09 |159、165|导出人字段|缺失；同上，审批人不是导出人。|
|SP-11-10 |159、165|导出时间字段|缺失；同上，审批时间不是导出时间。|
|SP-11-11 |159、166|按角色控权限、无权不见按钮|缺失；`workbench.py:94-108` 本机/来源/会话防护不等于业务RBAC。|
|SP-11-12 |159、167|历史数据、一年前可导|缺失；固定JSON，无工单历史查询。|
|SP-11-13 |167|单次10000条|缺失；无工单数量规则及边界测试；固定JSON不能证明。|
|SP-11-14 |167|超量提示分批|缺失；同上。|
|SP-11-15 |167|失败能重试|缺失（业务）；`reliability.py:57-72` 仅通用瞬态Timeout/ConnectionError重试，不是xlsx导出重试。|
|SP-11-16 |167|导出审计|缺失（业务）；`workflow.py:199-205` 工作流记录不等于导出审计。|
|SP-11-17 |167、169|自动把模糊需求变为可验收细则|稿件需修订；163行“对账”目的、165行工单号/客户/金额字段，以及一年/10000/重试/审计并非159行明确要求，不能默认为已确认业务事实；`workbench_service.py:120-122,140` 明确禁止臆造缺失事实。应列“待确认建议”。|

## 第12—13页（173—197）：产物、技术、指标

| ID |原稿行|承诺/指标|判定及证据|
|---|---|---|---|
|SP-12-01 |177|锁定Spec、任务、证据、审查文件|满足（框架/受控）；`governance.py:51-74`、`workflow.py:237-241,252-281`；不能冠以工单实战完成。|
|SP-12-02 |177|src中Vue3+ElementPlus、SpringBoot+MyBatisPlus业务实现|缺失；当前`src/docloop/workbench_static/index.html:1` 原生HTML，`project.yaml:4-7` Python/LangGraph；企业技术栈仅`.docloop/profiles/enterprise-vue-java.yaml:13-15`配置意图。|
|SP-12-03 |177|功能与测试两个Git提交|未验证/稿件需修订；未提供业务Commit IDs；`adapters.py:43-57` 仅固定产物单个提交。不能用本仓库开发提交冒充工单提交。|
|SP-12-04 |177、191、195|47个用例全过|未验证/稿件需修订；无该工单测试列表/日志/Commit关联；已有`.docloop/docs/workbench-acceptance.md:9-10` 记录61单测+1浏览器，属于框架历史检查，不能替代本轮记录或工单47项证据；本轮63项框架测试见统一验证结果。|
|SP-12-05 |177、191、195|覆盖率82%|未验证/稿件需修订；无覆盖率命令、报告、分母与业务Commit证据；`adapters.py:65-86` 没有覆盖率采集。|
|SP-12-06 |179|LangGraph调度|满足；`workflow.py:12-14,52-64` 实际编译持久化状态图。|
|SP-12-07 |179|按Superpowers TDD写|部分；`project.yaml:30-34` 加载TDD/验证Skill，`skill_runtime.py:141` model_invoked=false；不能证明运行时模型执行TDD。|
|SP-12-08 |179|Vue3/Java8|部分；企业Profile定义，当前框架是Python，未生成该工单企业代码。|
|SP-12-09 |179|Playwright浏览器测试|部分；`tests/acceptance/test_workbench_browser.py` 是工作台测试，已有验收记录10行；`project.yaml:61` 运行时browser未配置，不代表自动测生成业务。|
|SP-12-10 |179|Git Worktree隔离|缺失（真实执行）；`project.yaml:26` 是Skill路由；`adapters.py:43` git init不是git worktree；已有验收记录35行明确待实现。|
|SP-12-11 |179|模型DeepSeek Flash、随时换|未验证/部分；`model_gateway.py:23,48-50` 可配置模型名与Chat Completions网关；无已配置该模型/真实推理证据，`project.yaml:60` model=null。换模型还受供应商兼容性约束。|
|SP-12-12 |181|自动重试3次|部分；`reliability.py:57-72` 仅瞬态网络/超时最多3次重试（含首次共4次），不能泛化一切失败。|
|SP-12-13 |181|换思路、拆小步|缺失；`workflow.py:165-178` 捕获后写blocked恢复记录；无模型重规划/自动小步修复执行。|
|SP-12-14 |181|两轮无进展自动停|部分；`reliability.py:75-84` 有repair进展计数；当前`workflow.py`没有调用repair，不能宣称业务循环已集成。|
|SP-12-15 |181|恢复记录等人决定|满足（框架）；`workflow.py:165-178` 写恢复记录，`resume:111-121` 限制blocked直接恢复；不等于可无条件续跑。|
## 第13页交付明细（承接上表）

|ID|原稿行|承诺/指标|判定及证据|
|---|---|---|---|
|SP-13-01 |189|需求文档第二版补边界异常|缺失/稿件需修订；无工单v2；`governance.py:55-60,73-74` 基线不覆盖，需求变化应新Change审批，不应暗示直接改已锁Spec。|
|SP-13-02 |190|技术设计、接口、表结构、导出逻辑文档|缺失（工单）；`workbench_service.py:94-104` 产物枚举不含工单技术设计；固定JSON不能代替。|
|SP-13-03 |192|自动变更记录及原因|部分；`workflow.py:199-205` 状态trace存在，未生成工单逐文件原因说明；`evidence.py:29`起归档是复制产物而非自动语义changelog。|
|SP-13-04 |193|验收清单逐项打勾交PM|部分；`workflow.py:235-241` 追踪表存在，但固定value=42不得作为每个业务条件通过；无工单PM真实验收。|
|SP-13-05 |195|PR已提等review|未验证/稿件需修订；无PR URL、远程目标或关联Commit；`adapters.py:43-57` 无push/PR创建动作。|
|SP-13-06 |195|人两天、Agent40分钟|未验证/稿件需修订；无起止时间、相同范围/质量的人类基线、人工干预统计。预算600/3600秒（`reliability.py:20-21`）不是40分钟耗时证据。|
|SP-13-07 |197|一个PR包含代码测试文档全部交付|缺失（该实战）；无PR及工单交付，受控归档只能证明受控材料。|

## 第14页（201—210）：六项竞品对比

按委托不联网验证竞品；仓库没有同版本同任务同口径的竞品对照实验，不能从“没有接入/没看到证据”推断“竞品没有”。六项绝对比较均应撤下或改为本框架目标定位。

| ID |原稿行|比较项|判定与本方边界|
|---|---|---|---|
|SP-14-01 |205|ChatGPT/Cursor只能打字、Devin仅任务描述，本方多输入|稿件需修订；无竞品可比证据；本方 `workbench_store.py:123-128` 只md/txt及文本，本方不支持任意文件解析。|
|SP-14-02 |206|别的都不能整理文档、我们自动spec|稿件需修订；无可比证据；本方沙箱固定草稿，真实模型效果未验证 `workbench_service.py:130-144`。|
|SP-14-03 |207|关窗就忘/记录翻不到/日志散，本方自动changelog和更新文档|稿件需修订；无可比证据；本方持久化与trace存在 `workflow.py:49-64,199-205`，但不等于自动业务文档更新。|
|SP-14-04 |208|别的根本不能公司项目，本方对接内网Git/轻骑兵|缺失/稿件需修订；无可比证据；`project.yaml:57-64` 权限空、coding null，受控git init不是内网仓库接入；无轻骑兵实际连接验收。|
|SP-14-05 |209|别的无需求锁定，本方SHA256谁也改不了|部分/稿件需修订；`governance.py:51-74` 是应用校验与拒绝覆盖，不是OS只读/防管理员改写；无竞品可比证据。改“按Hash校验，发现偏离拒绝推进”。|
|SP-14-06 |210|别的无本地台，本方3000/VSCode|部分/稿件需修订；无可比证据；本方默认8765 `workbench.py:252,290`，无专用VSCode插件。|

## 第15页（214—222）：六步演示逐步判定

| ID |原稿行|步骤|判定及证据|
|---|---|---|---|
|SP-15-01 |218|1上传需求|满足（限定md/txt、2MiB）；`workbench.py:161-166`、`workbench_store.py:123-128`。|
|SP-15-02 |218|2聊天问清楚|缺失；无持续会话入口；`workbench_service.py:110-145` 单次草稿与待确认事项。改“生成草稿，人工编辑待确认项”。|
|SP-15-03 |218|3人审Spec|满足；`workbench.py:185-191` 保存审批，`governance.py:51-74` Hash绑定。|
|SP-15-04 |218|4自己实现和验证|部分（受控流程）；`workbench_service.py:147-165` 强制demo，`adapters.py:40-86` 固定JSON。真实业务缺失。|
|SP-15-05 |218|5人验收|部分；当前图`workflow.py:274-281` 验证审查后自动accepted，只有前置Spec审批interrupt（213行），无独立最终人验收暂停/API。不能把沙箱accepted当PM验收。|
|SP-15-06 |218|6归档|满足（受控）；`workflow.py:274-281` 与`tests/test_workflow.py:20-30`；若指真实工单归档则缺失。|
|SP-15-07 |220|人只做3件，中间全自动编码测试审查|缺失（真实业务）；real模式在plan被blocked `workflow.py:231-233`，review为确定性演示 `workflow.py:269-270`。|
|SP-15-08 |222|文档先行|部分；Spec审批链存在，实际业务文档生成未实现。|
|SP-15-09 |222|基线锁死|部分；精确Hash检测拒绝推进，非物理不可修改 `governance.py:66-74`。|
|SP-15-10 |222|人拍板|部分；人审Spec存在，最后人工验收未接入当前图。|
|SP-15-11 |222|全程能查|部分；已实现阶段、输入Hash、受控Commit、证据归档，真实业务未执行则不存在对应业务追踪；`workbench_service.py:107` UI还有最近20次运行/100条审计显示范围。|


## 引导语、重复表述与补充核对

|ID|原稿行|内容|结论|
|---|---|---|---|
|SP-META-01|3|15页、演讲12—15分钟及动作提示|非产品功能；15页结构已核对，实际演讲时长未计时，不当成功能验收。|
|SP-01-13|13|其他AI写完不留记录、关窗遗忘|稿件需修订；没有同版本、同任务的竞品对照证据，不应把场景铺垫当外部产品事实。与SP-14系列同口径。|
|SP-01-14|9|项目名DocLoop Agent|满足（命名）；pyproject.toml:2及workbench_static/index.html:1，产品名称可核对。|
|SP-07-22|101|每个任务都有状态、不能装完成|部分；contracts.py:5-21有状态契约，工作台任务用Spec和最近受控运行映射；不是独立的完整业务任务运行器。详见SP-07各项。|
|SP-09-06|129|不用学新东西、两边都能用|体验性承诺未验证；本地浏览器可用、源码可在VSCode打开，但无用户学习成本/可用性研究，不能承诺零学习成本。|

无独立产品功能的引导、场景提示或重复概括行：11, 23, 38, 53, 134, 145, 157, 161, 169, 175, 187, 203, 216, 226。其中145的可插拔归入SP-10-17；157/161/169的实际案例/自动细化归入SP-11；203强弱比较归入SP-14；216六步跑起来归入SP-15。所有标题与分隔线属于结构信息。


## 本轮实施与验证

- 样式：沿用左右布局和全部现有业务行为，替换工作台CSS为铁蓝主色、灰蓝任务区、白执行区；增强字号、文字对比、选中/焦点/禁用/错误状态、模态框及移动端长记录换行。无新增前端依赖或远程字体。
- 根目录测试：`uv run python -m unittest discover -s tests -v`，63项通过。本次用例数属于框架，不能替代演讲稿的工单47项。
- 真实Edge：现有完整浏览器验收1项通过，覆盖资料导入、草稿/修改、Hash审批、受控成功/失败、资料版本、刷新恢复、任务切换竞态、Skills查看、项目隔离、服务身份与停止；补充1366×640检查输入区、任务列表和底部操作可达。1366/1920/390无页面级横向及纵向溢出，控制台错误0。
- `uv run docloop doctor` passed，本地Superpowers 231文件与基准一致；`uv build` 成功生成0.2.0 wheel和sdist。
- 独立只读复核：无重要阻断；核对了原稿SHA、199个唯一ID、逐行指纹与引用，以及关键缺口和CSS边界。已修正历史61项测试与本轮63项测试的文字混淆。
- 证据目录：`D:/项目/agent-loop-data/validation/20261102-speech-style/`，截图及browser-result.json。业务验证数据在独立临时目录，不复用用户资料。
- PR查询：本轮 `gh pr list --state all --limit 10 --json number,title,state,url` 返回 `[]`，没有当前查询仓库PR记录支持演讲稿的案例声明。不推断其他仓库情况。
- 未执行：Oracle实例、真实供应商推理、工单业务、覆盖率、竞品对照实验和40分钟基准。构建与受控测试通过不改变这些边界。

## 覆盖登记

完整逐项数据见同目录 `speech-audit.json`。每条包含原文行号、结论与证据；逐行覆盖仅检查是否登记，不能替代人工核对语义或证明功能满足。

本轮共登记 199 项（含 9 项额外配置核对），137 个非空原文行全部有分类；未映射0、重复ID 0。
