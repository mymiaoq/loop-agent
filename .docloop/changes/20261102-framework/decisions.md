# 框架决策草稿

状态：draft。

- DEC-001（已知事实）：当前工作目录为 D:\项目\agent-loop，初始为空；使用用户明确给定的目录。
- DEC-002（来源事实）：原文指定 LangGraph，但企业 Vue/Java 规则须按 Profile 条件启用。
- DEC-003（待审批建议）：首轮交付 Python + LangGraph 可运行骨架、配置体系和离线测试。
- DEC-004（范围建议）：真实模型、工具网关、浏览器与多格式解析预留接口；不可用时明确阻塞。
- DEC-005（待审批事项）：用户是否认可 spec.md 中推荐方案与 AC-001 至 AC-007。
- DEC-006（当前限制）：未审批，因此未生成 tasks.md、checkList.md、证据或代码，未创建已批准基线。

DEC-007（用户确认）：2026-11-02 用户明确确认本次需求并要求直接开发；审批 Hash 见 baseline/approval.json。保留原草稿字节以保证基线可复核。
DEC-008（原文去重）：9个平台 Skill 与7个领域 Skill 共用 document-parser，因此生成15个唯一目录；原 Spec 和计划中的16按清单去重解释，不重复维护同名 Skill。
