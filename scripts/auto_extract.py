# -*- coding: utf-8 -*-
"""从招标文件解析结果自动提取项目参数（名称/工期/类型/内容），减少手工输入。

用法：from auto_extract import auto_extract_params
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict


def _all_text(pr: dict) -> str:
    """把 parse_result 中所有字符串字段拼起来，便于正则检索。"""
    chunks: list[str] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        elif isinstance(obj, str):
            chunks.append(obj)

    walk(pr)
    return "\n".join(chunks)


def _extract_name(pr: dict, tender_file: str) -> str:
    """项目名称：优先解析结果里的「项目名称」，其次文件名。"""
    text = _all_text(pr)
    m = re.search(r"项目名称[：:]\s*([^\n（(]{4,60})", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"工程名称[：:]\s*([^\n（(]{4,60})", text)
    if m:
        return m.group(1).strip()
    stem = Path(tender_file).stem
    stem = re.sub(r"^（招标文件）", "", stem).strip()
    stem = re.sub(r"[（(].*?[)）]", "", stem).strip()
    return stem or "工程项目"


def _extract_duration(pr: dict) -> int:
    """工期（日历天）：匹配「工期…N 日历天 / N 天 / 总工期 N」等。"""
    text = _all_text(pr)
    patterns = [
        r"工期[^。\n]{0,20}?(\d+)\s*(?:日历天|天|个?月)",
        r"总工期[^。\n]{0,10}?(\d+)\s*(?:日历天|天)",
        r"计划工期[^。\n]{0,10}?(\d+)\s*(?:日历天|天)",
        r"(\d+)\s*日历天",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            v = int(m.group(1))
            if 15 <= v <= 3650:
                return v
    return 0


def _extract_bid_type(pr: dict, work_content: str) -> str:
    """工程类型：construction / service，按内容关键词粗判。"""
    text = _all_text(pr) + "\n" + work_content
    service_kw = ("服务", "保洁", "维护", "物业", "养护", "运维", "清洗", "消毒")
    construct_kw = ("施工", "改造", "安装", "拆除", "土建", "装修", "消防", "排危", "市政", "结构")
    s = sum(1 for k in service_kw if k in text)
    c = sum(1 for k in construct_kw if k in text)
    return "service" if s > c else "construction"


def auto_extract_params(pr: dict, tender_file: str) -> Dict[str, Any]:
    """自动提取参数；提取不到返回空值，由调用方决定是否要求用户补充。"""
    name = _extract_name(pr, tender_file)
    duration = _extract_duration(pr)
    bid_type = _extract_bid_type(pr, "")
    return {
        "name": name,
        "duration": duration,
        "bid_type": bid_type,
    }
