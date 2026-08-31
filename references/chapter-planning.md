# 章节规划与页数控制

## 页数分配

- 总页数 = `target_pages`；封面 1 + 目录 3 + 附表 20 页预留后，剩余按评分项权重分配到各章节。
- 每章最少 8 页；`detail_level` 由页数自动推导（≤50 精简 / 50-200 标准 / ≥200 完整）。
- 生成后按「段落数/25 + 表格×2」粗估页数，与目标页数偏差可在 CLI 结果中看到。

## 章节来源

- 章节结构优先由招标文件评分项决定（ADR-007/009 原则）；固定模板章节只做兜底。
- 施工类/服务类默认章节模板见 `chapter_config.json`（`construction_chapters` / `service_chapters`）。
- 行业句池与专业内容见 `base/flavor_pools.py`、`db_data.py`、`professional_database.py`。

## 质量门禁（CLI 默认开启）

- 评分响应闭环补强 `enable_scoring_reinforce`：逐条核对评分项覆盖，弱/未覆盖项自动补写。
- 废标风险核验 `enable_risk_grading`：对照招标文件形式要件 + 内置风险模式。
- 质量闸门 `enable_docx_quality_gate`：禁止正文残留评审标准/加分项等字样。
- 元数据与样式清洗 `enable_docx_sanitize`：统一黑体/仿宋、置黑、左对齐。
