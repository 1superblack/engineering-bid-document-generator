# -*- coding: utf-8 -*-
"""招标解析结果清洗：过滤启发式解析产生的噪声，提升章节规划与评分响应质量。

启发式解析（parser.py）会把日期、地址、条款编号、评分档次（优为/良为…）
等误当作评分项；technical_chapters 也会混入「商务标最终/投标报价/技术评审」
等评标办法类别名。本模块在脚本层（CLI）统一清洗后再交给规划与补强，
不改动 parser 本身，避免破坏既有测试基线。
"""
from __future__ import annotations

import re

_DATEISH = re.compile(
    r"\d+\s*年|\d+\s*月|\d+\s*日|\d+\s*时|截止|开标|注册登记|网址|名\s*称|地\s*址|电话|"
    r"北京时间|交易平台|解密提示|报名|投标保证金递交"
)
_NOISE_PREFIXES = (
    "优为", "良为", "一般为", "差为", "的扣", "的，", "分钟（", "投标人可同时对",
    "构成本", "份数：", "小微企业", "满足条件", "政府采购", "串通投标", "H的取值",
    "开标时间", "招标人发出", "☑", "□",
)
_NUMBER_ONLY = re.compile(r"^\d+(\.\d+)*[\.、]?\s*$")
_TECH_CHAPTER_DENY = ("商务标", "报价", "评审", "评标")
_TECH_SCORE_PHRASES = (
    "施工方案", "技术措施", "保障措施", "进度计划", "质量保证", "安全措施",
    "文明施工", "环保", "应急预案", "成品保护", "保修", "平面布置", "组织管理",
    "劳动力", "材料供应", "机械设备", "项目管理班子", "工程概况", "季节性施工",
    "排危", "拆除", "消防改造", "施工部署", "创优", "施工组织设计",
)
_COMMERCIAL_FORM_DENY = (
    "报价", "价格", "金额", "违约", "保证金", "联合体", "营业执照", "许可证",
    "注册建造师", "符合第二章", "符合第八章", "澄清", "串通",
    "弄虚作假", "政府采购", "预留份额", "材料用量", "混凝土用量", "投标工期",
    "投标文件能正常打开", "投标总报价", "安全防护、文明施工及环境保护费",
    "深基坑支护费", "桩基工程", "评标委员会", "开标", "投标人名称", "投标函",
    "误期", "商品混凝土", "工程质量标准", "对质量目标的承诺", "对文明施工管理目标的承诺",
    "对安全生产管理目标的承诺",
    "评分标准", "评审标准", "评审", "评标", "招标", "须知",
)


def _cjk_count(text: str) -> int:
    return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")


def is_good_score_item(item) -> bool:
    """技术标专用评分项清洗：只保留技术评审类条目。

    丢弃：日期/地址/编号/评分档次碎片、评标办法类别（投标报价/技术评审）、
    形式评审与商务/资格条款（报价、保证金、资质证书、联合体等）。
    """
    name = (item.get("name") or item.get("title") or "").strip()
    if not name:
        return False
    if _NUMBER_ONLY.match(name):
        return False
    if name.startswith(_NOISE_PREFIXES):
        return False
    if _DATEISH.search(name):
        return False
    if _cjk_count(name) < 4:
        return False
    if "得分" not in name:
        return False
    if any(k in name for k in _COMMERCIAL_FORM_DENY):
        return False
    return True


def is_good_tech_chapter(name: str) -> bool:
    """技术标一级章节清洗：丢弃评标办法类别名与碎片。"""
    name = (name or "").strip()
    if not name:
        return False
    if any(k in name for k in _TECH_CHAPTER_DENY):
        return False
    if _NUMBER_ONLY.match(name):
        return False
    if _cjk_count(name) < 4:
        return False
    return True


def clean_parse_result(pr: dict) -> dict:
    """返回清洗后的 parse_result（浅拷贝，不修改入参）。"""
    if not isinstance(pr, dict):
        return pr
    pr = dict(pr)
    pr["technical_chapters"] = [
        it for it in (pr.get("technical_chapters") or [])
        if is_good_tech_chapter(it.get("name") or "")
    ]
    # 评分项：过滤 + 按规范化名称去重（保留分值最高的一条）
    cleaned_items: dict[str, dict] = {}
    for it in (pr.get("score_items") or []):
        if not is_good_score_item(it):
            continue
        name = (it.get("name") or it.get("title") or "").strip()
        norm = _normalize_item_name(name)
        if norm not in cleaned_items or (it.get("score") or 0) > (cleaned_items[norm].get("score") or 0):
            cleaned_items[norm] = it
    pr["score_items"] = list(cleaned_items.values())
    return pr


def _normalize_item_name(name: str) -> str:
    """规范化评分项名称用于去重：去编号/空白/「（满分…」后缀。"""
    s = re.sub(r"^\s*\d+(\.\d+)*[\.、]?\s*", "", name)
    s = re.sub(r"\s+", "", s)
    s = re.split(r"（满分|\(满分", s)[0]
    return s.strip()
