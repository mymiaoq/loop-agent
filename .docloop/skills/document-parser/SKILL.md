---
name: document-parser
description: 解析来源并保留定位；收到 Markdown 或其他设计资料时使用。
version: 1.0.0
risk_level: medium
timeout: 300
---

## 用途
解析来源并保留定位。

## 触发条件
收到 Markdown 或其他设计资料。

## 输入 Schema
```yaml
required: [text, source, type]
```

## 允许工具
read_file, document_adapter；实际权限取 task_context 与适配器权限的交集。

## 执行步骤
读取 Markdown 并记录行号；DOCX/PDF/图片无适配器时返回 blocked，不猜测内容。

## 输出 Schema
Source Bundle，SRC ID、标题、行号、原文 Hash。所有结果标明 mode 与 status。

## 失败处理
环境、权限或必要业务信息缺失时返回 blocked；保存证据，不自动扩大范围。

## 完成条件
输出可解析，必需字段齐全，需求关联无缺失，实际执行状态已记录。

## 禁止行为
不覆盖基线，不将 not_run 当作 passed，不授予工具权限，不越过角色职责。

## 专业来源契约
### 4.1 document-parser（设计资料解析）

**用途：** 读取
Markdown、DOCX、PDF、图片或扫描件，提取文本、表格、页面结构和图片信息，并为结构化需求保留可追溯来源。用于设计文档实现、PRD
解析、截图还原或任何非纯文本需求来源。

**输入路由：**

1.  Markdown/纯文本：直接读取，保留标题和行号。
2.  DOCX：提取段落、标题、表格、图片及其顺序，不依赖手工解压目录。
3.  PDF：先判断文本型或扫描型；文本型提取文字与页码，扫描型执行 OCR
    并标记置信度。
4.  图片/截图：提取可见文字、区域、控件、标注和空间关系。

**输出契约：**

``` yaml
document:
  source: ""
  type: "markdown|docx|pdf|image"
  pages: 0
  sections: []
  tables: []
  images: []
  requirements:
    - id: "SRC-001"
      statement: ""
      source_locator: ""
      confidence: "high|medium|low"
  ambiguities: []
  parse_warnings: []
```

**约束：**

-   不根据文件名、目录名或常规 CRUD 模式臆造内容。
-   每条需求必须包含 `source_locator`。
-   OCR 或视觉判断不确定时降低置信度并加入 `ambiguities`。
-   不把解析阶段的推测标记为已确认需求。
-   临时解压、OCR 和渲染文件放在工作区外的临时目录，完成后清理。
