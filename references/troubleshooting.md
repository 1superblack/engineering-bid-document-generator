# 常见问题排查

## 解析失败（退出码 2）

- 扫描件：先 OCR。
- 提示"文件不存在"：检查 `--tender-file` 路径是否正确（含空格/中文用引号包裹）。

## 生成失败（退出码 1）

看 `[结果]` 后的 `failed_stages` 列表，常见原因：

- `generation`（阻断）：引擎异常，看完整报错信息（`--json` 输出 message）。
- 非阻断 Stage 失败（如 `charts` 缺 matplotlib、`kb_rag` 缺知识库）不影响主文档生成。

## LLM 未生效

- 自动探测顺序：`BIDGEN_LLM_*` 环境变量 → `data/llm_config.json` →
  Codex 配置 `~/.codex/config.toml`（跟随 model_provider）→
  `OPENAI_API_KEY/OPENAI_BASE_URL/OPENAI_MODEL` 环境变量（WorkBuddy 等平台常用）。
- 无任何有效凭据时自动回退本地模板（正文为句子池拼装，质量明显下降）。
- 排查：先确认上述任一来源存在有效 api_key；平台若用别的变量名注入，
  可映射到 `BIDGEN_LLM_API_KEY` 或在 `data/llm_config.json` 中填写。
- 仍未配置时自动回退本地模板（正文为句子池拼装，质量明显下降）。

## 企业知识库

- 默认读取 `data/user_knowledge_base.json`（公司资质/人员/业绩/设备）。
- 不填真实数据时，资格响应和评分补强会使用示例占位，交付前必须替换。
