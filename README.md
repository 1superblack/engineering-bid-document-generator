# 工程标书生成器 · 开源引擎版 (Engineering Bid Document Generator — Open Engine)

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python) ![License: MIT](https://img.shields.io/badge/License-MIT-green.svg) ![CI](https://github.com/1superblack/engineering-bid-document-generator/actions/workflows/ci.yml/badge.svg) ![Language](https://img.shields.io/github/languages/top/1superblack/engineering-bid-document-generator?color=yellowgreen) ![Stars](https://img.shields.io/github/stars/1superblack/engineering-bid-document-generator?style=social)

> 本地优先、数据不出本机的工程投标书一键生成引擎。**本仓库是「开源引擎版（Lite）」**：核心生成引擎 + 通用工程语料完全开放可验；竞争性的「评分策略精调 / 差异化弹药库」完整内容托管在 [WorkBuddy SkillHub 完整版](https://skillhub.cn/)。

---

## 这是什么

丢进招标文件（Word/PDF）或一段工程描述，本地生成**可直接交付**的技术标 / 商务标 / 资格标书，并附带：

- 《投标文件偏离表》
- 不废标三级风险扫描与「检查 → 修复」闭环
- 评标专家视角的模拟评审报告（覆盖率 / 废标风险 / 得分预测）

**全部在本地运行，不联网、不上传你的招标文件与标书。** 可选 LLM 扩写需用户显式配置密钥，默认关闭。

---

## 为什么开源「引擎版」而非「完整版」

这是一次 **Open Core** 发布，权衡如下：

| 维度 | 开源引擎版（本仓库） | SkillHub 完整版 |
|------|------|------|
| 生成引擎 / 架构 | ✅ 全部开放 | ✅ |
| 通用工程语料（14 维差异化句池） | ✅ 开放可验 | ✅ 更全 |
| 评分策略库（章节 must_have/bonus） | ✅ 通用框架 | ✅ 精调扩充 |
| 竞争内容精调 / 最新维度 | ❌ 留作完整版卖点 | ✅ |
| 一键安装 / 后续更新 / 官方支持 | ❌ | ✅ |
| 适用人群 | 想看懂原理、二次开发、审计「是否本地/有无后门」的开发者 | 想省事直接产出中标级标书的投标人员 |

> 一句话：**看原理、改代码、验安全 → 用本仓库；要最全内容、最省事、持续更新 → 装 SkillHub 完整版。**

---

## 功能特性

- **招标文件解析**：自动提取评分项、废标红线条款、资质要求（pdf/docx）。
- **评分策略引擎**：按 `must_have / bonus / common_omissions` 三维驱动章节内容深度。
- **14 维竞争力差异化**：BIM 深度应用、绿色双碳、危大工程、创优奖项、智慧工地、质量通病、成品保护、测量试验、季节工况、量化硬指标、应急预案、安全文明、劳务工资、总承包协调。
- **富内容引擎（RichChapter）**：路由失败自动兜底，按评分库 + 企业知识库注入多段落正文，逐章去重协同防相互抢占。
- **不废标风控**：三级风险分级 + 检查→修复循环（最多 3 轮）。
- **暗标清洗**：清除页眉页脚 / 过滤身份信息 / 统一格式。
- **去 AI 化 + 降重**：降低机器痕迹、跨文档查重降重。
- **述标 PPT**：可选生成述标演示文稿。

支持工程类型：施工类（房建/市政/水利/旧改/拆除）、装饰装修、服务类（物业/政府采购），以及商务标 / 资格标。

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

核心依赖：`python-docx`、`PyPDF2`、`python-pptx`。

### 2. 最小可用示例

```python
import sys
from pathlib import Path

# 加载扁平模块 → 包路径映射垫片（Skill 运行环境由 conftest 自动加载）
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _package_shim  # noqa: F401

from main import generate_bid_document

result = generate_bid_document({
    "name": "示例市某办公楼装饰装修工程施工",
    "work_content": "室内装饰装修、给排水、电气安装及消防工程",
    "duration": 180,
    "area": 12000,
    "bid_type": "construction",     # construction / service
    "detail_level": 2,              # 1=精简 / 2=标准 / 3=完整
    "target_pages": 80,
    "output_path": "output/技术标书.docx",
})

print(result["success"], result.get("output_file"))
```

也可直接运行演示脚本（生成 `output/demo_bid.docx`）：

```bash
python examples/demo.py
```

### 3. 运行自检

```bash
pytest test_lite.py -q
```

---

## 架构与执行流程

```
参数校验 → 解析招标文件 → 章节规划(Planner, 评分项驱动)
→ 评分策略增强(ScoringStrategy) → 富内容生成(RichChapter)
→ 附表联动 → 合规检查(Checker) → 模拟评审(EvaluatorCheck)
→ 修复循环(≤3 轮) → 后处理(Hooks: 去AI化/降重) → 格式美化 → 输出 Word
```

主要模块（扁平布局，经 `_package_shim` 映射为 `bid_core.*` / `bid_technical.*` 包路径）：

| 模块 | 职责 |
|------|------|
| `main.py` | 入口：`generate_bid_document()` |
| `bid_generator.py` | 标段路由 + 生成编排 |
| `generator.py` | 技术标生成器（富内容引擎核心） |
| `base/flavor_pools.py` | 14 维差异化句池（SSOT） |
| `scoring_strategy.py` / `data/scoring_strategy.json` | 评分策略引擎与策略库 |
| `evaluator_check.py` | 评标自检（覆盖率/风险/得分） |
| `checker/` `repair/` `dedup/` `deai/` | 合规检查 / 自动修复 / 查重 / 去AI化 |
| `parser.py` | 招标文件解析 |
| `data/user_knowledge_base.json` | 企业知识库（**仅脱敏样例**） |

---

## 数据脱敏与知识产权说明

- 本仓库所有数据文件均为**脱敏样例**：`data/user_knowledge_base.json` 使用「示例建设集团有限公司」等虚构信息，不含任何真实主体、证书编号或联系方式。
- 差异化句池（`base/flavor_pools.py`）与评分策略库均为**公开工程领域通用知识**（国家/行业规范、常见施工工艺），可自由阅读、审计与二次开发。
- 完整版的「竞争内容精调」（最新维度覆盖、扩充弹药、持续更新）作为商业卖点保留在 SkillHub，不在本仓库提供。
- 代码中出现的 `sk-xxx` / `sk-你的密钥` 仅为可选 LLM 扩写功能的占位说明，无任何真实密钥。

---

## 许可证

MIT License — 自由使用、修改与分发，请保留出处。

## 支持与导流

- 📦 **完整版 / 一键安装**：WorkBuddy 搜索「工程标书生成器」（SkillHub skillId=93495）
- 💬 问题反馈：GitHub Issues
- ☕ 觉得引擎有价值，欢迎 Star ⭐ 支持，或前往 SkillHub 体验完整能力

---

> ⚠️ 免责声明：本工具生成的标书为辅助 draft，**正式投标前请由持证人员逐项核对资质、业绩、报价与招标文件实质性要求**，因使用本工具产生的任何投标后果由使用者自行承担。
