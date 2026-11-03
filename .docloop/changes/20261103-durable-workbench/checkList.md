# 验收清单

| TC | AC | TASK | 检查与预期 |
| --- | --- | --- | --- |
| TC-001 | AC-001 | TASK-004 | 浏览器打开四个辅助弹层，工作区不隐藏，关闭保留草稿；Skills 名称与功能可读，无内部路径 |
| TC-002 | AC-002 | TASK-001 | test_publications：冻结、SHA、标签、本地提交与远端确认；断网复用同一版本 |
| TC-003 | AC-002 | TASK-001 | 发布仓库/远端变更拒绝；中断前后对账；CRLF基线不变；Windows深路径可发布 |
| TC-004 | AC-003 | TASK-002 | test_durable_runs：暂停后无后续准备，继续同Run且计划不重复推理；持久取消优先于恢复 |
| TC-005 | AC-004 | TASK-002 | 杀死真实子进程树，再打开SQLite并恢复同Run；输入Hash/仓库变化拒绝恢复 |
| TC-006 | AC-003 | TASK-002 | test_background_analysis：后台任务身份、重复请求去重、刷新重连、原输入重试；分析未完成不可审批 |
| TC-007 | AC-005 | TASK-003 | test_task_updates：上传暂停、差异新草稿、旧审批原字节保留、新审批使旧Run失效及崩溃对账 |
| TC-008 | AC-006 | TASK-005 | 全部unittest、doctor、浏览器1920/1366/390及控制台；Git远端引用核对 |

实际证据见 evidence.yaml。物理断电、Oracle实际迁移和真实供应商语义质量不以fixture测试替代。
