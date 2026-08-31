---
name: engineering-bid-document-generator
slug: engineering-bid-document-generator
displayName: 工程标书生成器（一键生成工程标书）
version: 9.4.0
description: >-
  工程标书一键生成：丢入招标文件（Word/PDF），自动解析评分项/星号条款/废标红线/
  资格要求并提取项目参数，按评分权重规划章节，一键生成可直接交付的技术标（docx）。
  内置废标风险自检、评分覆盖率报告、企业资质业绩响应，数据全程本地处理，无需填 API key。
  当用户提供工程招标文件并要求一键生成、编写或审查标书时使用；也用于从招标文件中
  提取评分项摘要。触发词示例：「一键生成标书」「根据这份招标文件写技术标」
  「解析评分项」「写投标书」「帮我做标书」。作者：黑超人。
tags: [工程标书, 投标, 标书生成, 文档自动化, 技术标]
author: 黑超人
---

# 工程标书生成器

收到招标文件（Word/PDF）后，按三步执行：解析 → 生成 → 自检交付。

## 前置条件

- Python 3.9+；首次使用先安装依赖：
  `pip install -r requirements.txt`
- LLM 扩写：自动探测可用凭据，无需单独填 key。探测顺序：
  ① `BIDGEN_LLM_*` 环境变量 → ② `data/llm_config.json` →
  ③ Codex 配置 `~/.codex/config.toml`（跟随 model_provider）→
  ④ `OPENAI_API_KEY/OPENAI_BASE_URL/OPENAI_MODEL` 环境变量（WorkBuddy 等平台常用）。
  全部未配置时自动回退本地模板。
- 企业知识库：编辑 `data/user_knowledge_base.json`（公司资质/人员/业绩/设备）。
  交付前必须替换示例数据，禁止编造资质与业绩。

## 工作流

### 1. 解析招标文件（硬闸门）

运行并展示评分项摘要，确认解析有效：

```bash
python scripts/parse_tender.py --tender-file <招标文件> [--bid-type construction|service]
```

输出评分项/星号条款/废标红线/资格要求数量及前若干条明细。
解析为空或报错时中止，向用户说明原因（扫描件需 OCR）并请用户确认后再继续；
不得跳过解析直接套模板。

注意：本技能**只生成工程技术标**。解析后会自动过滤商务标/报价/形式评审/
资格条款类条目（见 `scripts/bid_clean.py`），章节规划与评分响应只针对
技术评审类内容，产出文档不含商务标章节与报价内容。

### 2. 一键生成

```bash
python scripts/generate_bid.py --tender-file <招标文件> --name <项目名> \
  --duration <工期天数> --work-content "<施工内容概述>" \
  [--bid-type construction] [--target-pages 300] [--output <输出.docx>]
```

常用参数：

| 参数 | 必填 | 说明 |
|------|------|------|
| `--tender-file` | 是 | 招标文件路径（.docx/.pdf） |
| `--name` | 是 | 项目名称 |
| `--duration` | 是 | 工期（日历天） |
| `--work-content` | 否 | 施工/服务内容概述 |
| `--bid-type` | 否 | construction（默认）/ service |
| `--target-pages` | 否 | 目标页数（默认 300） |
| `--output` | 否 | 输出 docx 路径 |
| `--dark-bid` | 否 | 暗标模式（匿名化处理） |
| `--no-llm` | 否 | 禁用 LLM 扩写 |
| `--user-context` | 否 | 企业知识库 JSON 路径 |

`--tender-file` 含空格或中文时用引号包裹。

### 3. 校验并交付

生成脚本会打印：输出路径、估算页数（对比目标）、失败 Stage 列表、
自检报告（评审风险分/评分响应率/风险检出率/重复率/成稿可用度/结论）。

- 全部 Stage 成功或仅非阻断 Stage 失败 → 交付，向用户说明产物路径与自检结论。
- `generation` 阻断失败 → 附上错误信息，请用户提供更多项目信息后重试。
- 评分响应率明显偏低（如 <80%）或估算页数与目标偏差 >10% → 向用户说明并
  建议调整 `--target-pages` 或补充知识库后重跑。

## 输出产物

- 主标书 docx（封面/目录/正文/附表/偏离表）。
- `<主文档名>_交付物/` 子目录：自检报告、评分命中矩阵、进度横道图等辅助产物。

## 边界与安全

- 只使用知识库中的真实资质/业绩/人员/设备，不得编造；最终文档需人工审查后提交。
- LLM 云端模式出网前自动脱敏（pipeline 已挂载 Masker）；api_key 请勿随文档外传。
- 生成结果仅供参考，投标合规性由使用方自行负责。

## 参考资料

- `references/parse-result.md`：解析结果字段与解析失败处理。
- `references/chapter-planning.md`：章节规划与页数控制规则。
- `references/troubleshooting.md`：常见问题排查。
