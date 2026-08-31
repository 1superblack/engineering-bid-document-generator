# 招标文件解析结果说明

`scripts/parse_tender.py` 与生成流程共用 `parse_tender()`，返回的 `parse_result` 主要字段：

| 字段 | 含义 |
|------|------|
| `score_items` | 评分项列表（含名称/分值/权重），规划章节页数的核心依据 |
| `star_clauses` | 星号（实质性）条款 |
| `red_line_clauses` | 废标红线条款 |
| `qualification_reqs` | 资格/资质要求 |
| `form_requirements` | 形式要件（签章/密封/正副本等），供废标风险核验 |
| `_error` | 非空表示解析失败 |

## 常见解析失败

1. **扫描件 PDF / 图片型 docx**：无文本层，无法提取。先 OCR 成可复制文本再解析。
2. **加密/受限文档**：无法读取，需解除限制。
3. **扩展名不支持**：仅支持 `.docx/.doc/.pdf`。

解析为空时生成流程会中止（硬闸门）。确认文件可解析后重试；确需强行生成可加
`--allow-fallback`（会退化为通用模板章节，不推荐）。
