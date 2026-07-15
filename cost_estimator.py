"""
工程造价估算模块 v1.0 — bid_core/cost_estimator

本模块为工程投标（标书）生成提供独立的成本估算能力。
特点：
  - 纯函数、自包含，不依赖 bid 项目的其他模块（仅使用标准库）。
  - 既支持「给定工程量清单(quantities)直接汇总」，也支持「仅凭 project_info 经验建模」。
  - 防御式编码：缺失字段不崩溃，使用经验默认值并写入 notes。
  - 确定性：不使用会改变总价的随机扰动。

注意：当未提供 quantities 时，所有费率均为「经验参考值」，并非官方报价，
仅用于标书建模与量级估算，相关说明会写入返回的 notes 字段。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

# ══════════════════════════════════════════════════════════════════
# 经验参考费率（非官方报价，仅供建模）
# ══════════════════════════════════════════════════════════════════

# 施工类项目：按建筑面积（元/㎡）估算直接费三大要素
REF_LABOR_RATE_PER_M2 = 380.0        # 人工费 经验参考 元/㎡
REF_MATERIAL_RATE_PER_M2 = 1500.0    # 材料费 经验参考 元/㎡
REF_MACHINERY_RATE_PER_M2 = 220.0   # 机械费 经验参考 元/㎡

# 服务类项目：按「人天」估算（元/人天）
REF_SERVICE_LABOR_PER_DAY = 1200.0       # 人工 元/人天
REF_SERVICE_MATERIAL_PER_DAY = 300.0     # 材料 元/人天
REF_SERVICE_MACHINERY_PER_DAY = 120.0    # 机械 元/人天
REF_DEFAULT_TEAM_SIZE = 10                # 默认投入人数

# 缺失字段时使用的默认经验参数
DEFAULT_AREA = 10000          # 默认建筑面积 ㎡
DEFAULT_DURATION = 180        # 默认工期 天

# 间接费组成费率（经验参考）
MANAGEMENT_RATE = 0.06   # 管理费 = 6% × 直接费
PROFIT_RATE = 0.07       # 利润 = 7% × (直接费 + 管理费)
TAX_RATE = 0.09          # 税金 = 9% × (直接费 + 管理费 + 利润)

# 用于区分直接费 / 间接费的类目关键字（大小写不敏感匹配）
DIRECT_CATEGORIES = {'人工', '材料', '机械', 'labor', 'material', 'machinery'}
INDIRECT_CATEGORIES = {'管理', '利润', '税金', 'management', 'profit', 'tax'}


# ────────────────────────────────────────────────────────────────
# 内部工具函数
# ────────────────────────────────────────────────────────────────
def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """安全转换为 float；无法转换时返回 default。"""
    if value is None:
        return default
    try:
        f = float(value)
        # 过滤掉 NaN / 无穷大，避免污染后续计算
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _norm_cat(category: str) -> str:
    """归一化类目名：去空格、转小写，便于集合匹配。"""
    return str(category).strip().lower()


def _classify(category: str) -> str:
    """将类目归类为 'direct'（直接费）或 'indirect'（间接费）。"""
    norm = _norm_cat(category)
    if norm in DIRECT_CATEGORIES:
        return 'direct'
    return 'indirect'  # 未识别类目默认计入间接费，确保总价可被合计


# ────────────────────────────────────────────────────────────────
# 公开 API
# ────────────────────────────────────────────────────────────────
def estimate_cost(project_info: dict, quantities: Optional[list] = None) -> dict:
    """
    估算工程造价。

    参数:
        project_info: 项目信息字典，常见键包括 name/work_content/area/duration/
                      structure_type/divisions/bid_type 等。缺失键会被容错处理。
        quantities:   工程量清单（可选）。每个元素为 dict，需含键：
                      name:str, unit:str, qty:float, unit_price:float, category:str。
                      提供时直接按清单汇总；为 None 时按 project_info 经验建模。

    返回:
        字典，固定包含键：
          currency      货币单位（'人民币元'）
          items         清单项列表，每项 {name,unit,qty,unit_price,amount,category}
          total_direct  直接费合计（float，2 位小数）
          total_indirect 间接费合计（float，2 位小数）
          total         总造价（float，2 位小数）
          breakdown     类目 -> 金额 映射
          notes         说明列表（含建模口径、缺失字段提示等）
    """
    project_info = project_info or {}
    notes: List[str] = []
    currency = '人民币元'

    # 所有金额统一在最后做两位小数取整
    items: List[Dict[str, Any]] = []

    if quantities:
        # 路径 A：给定工程量清单，直接逐项汇总
        for raw in quantities:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get('name', '未命名项'))
            unit = str(raw.get('unit', ''))
            qty = _safe_float(raw.get('qty'), 0.0) or 0.0
            unit_price = _safe_float(raw.get('unit_price'), 0.0) or 0.0
            category = str(raw.get('category', '其他'))
            amount = round(qty * unit_price, 2)
            items.append({
                'name': name,
                'unit': unit,
                'qty': qty,
                'unit_price': round(unit_price, 2),
                'amount': amount,
                'category': category,
            })
    else:
        # 路径 B：凭 project_info 经验建模
        notes.append('成本基于经验参考费率估算，并非官方报价，仅供标书建模与量级参考。')

        area = _safe_float(project_info.get('area'))
        duration = _safe_float(project_info.get('duration'))
        bid_type = str(project_info.get('bid_type', 'construction')).strip().lower()

        missing: List[str] = []
        if area is None:
            missing.append('area')
            area = float(DEFAULT_AREA)
        if duration is None:
            missing.append('duration')
            duration = float(DEFAULT_DURATION)

        if bid_type == 'service':
            # 服务型：以「人天」为基准估算直接费
            team = REF_DEFAULT_TEAM_SIZE
            person_days = max(duration, 1.0) * team
            labor = (person_days, REF_SERVICE_LABOR_PER_DAY, '人天')
            material = (person_days, REF_SERVICE_MATERIAL_PER_DAY, '人天')
            machinery = (person_days, REF_SERVICE_MACHINERY_PER_DAY, '人天')
            notes.append('按服务型项目建模：以工期×投入人数（人天）经验费率估算直接费。')
        else:
            # 施工型：以建筑面积（㎡）为基准估算直接费
            labor = (area, REF_LABOR_RATE_PER_M2, '㎡')
            material = (area, REF_MATERIAL_RATE_PER_M2, '㎡')
            machinery = (area, REF_MACHINERY_RATE_PER_M2, '㎡')
            notes.append('按施工型项目建模：以建筑面积（㎡）经验费率估算直接费。')

        # 构造直接费三项清单
        direct_specs = [
            ('人工费', labor[0], labor[1], labor[2], '人工'),
            ('材料费', material[0], material[1], material[2], '材料'),
            ('机械费', machinery[0], machinery[1], machinery[2], '机械'),
        ]
        for name, qty, price, unit, cat in direct_specs:
            amount = round(qty * price, 2)
            items.append({
                'name': name,
                'unit': unit,
                'qty': qty,
                'unit_price': round(price, 2),
                'amount': amount,
                'category': cat,
            })

        if missing:
            notes.append(
                '未提供字段：{fields}，已使用默认经验参数（面积默认 {a}㎡，工期默认 {d}天）。'.format(
                    fields='、'.join(missing), a=int(DEFAULT_AREA), d=int(DEFAULT_DURATION)
                )
            )

    # ── 汇总直接费 ──
    total_direct = round(sum(it['amount'] for it in items
                             if _classify(it['category']) == 'direct'), 2)

    # ── 若未提供 quantities，则补充间接费三项；提供 quantities 时直接采信清单 ──
    if not quantities:
        management = round(MANAGEMENT_RATE * total_direct, 2)
        profit = round(PROFIT_RATE * (total_direct + management), 2)
        tax = round(TAX_RATE * (total_direct + management + profit), 2)

        indirect_specs = [
            ('管理费', management, '管理'),
            ('利润', profit, '利润'),
            ('税金', tax, '税金'),
        ]
        for name, amount, cat in indirect_specs:
            items.append({
                'name': name,
                'unit': '项',
                'qty': 1,
                'unit_price': amount,
                'amount': amount,
                'category': cat,
            })

    # ── 汇总间接费与总价 ──
    total_indirect = round(sum(it['amount'] for it in items
                               if _classify(it['category']) == 'indirect'), 2)
    total = round(total_direct + total_indirect, 2)

    # ── 类目归集（同名称类目合并）──
    breakdown: Dict[str, float] = {}
    for it in items:
        cat = it['category']
        breakdown[cat] = round(breakdown.get(cat, 0.0) + it['amount'], 2)

    return {
        'currency': currency,
        'items': items,
        'total_direct': total_direct,
        'total_indirect': total_indirect,
        'total': total,
        'breakdown': breakdown,
        'notes': notes,
    }


def cost_table_rows(estimate: dict) -> list:
    """
    将估算结果转换为表格行，便于调用方渲染。

    参数:
        estimate: estimate_cost 的返回字典。
    返回:
        行列表，每行 = [name, unit, qty, unit_price, amount]；
        末尾追加合计行 ['合计','—','—','—', total]。
    """
    rows: List[List[Any]] = []
    for it in estimate.get('items', []):
        rows.append([
            it.get('name', ''),
            it.get('unit', ''),
            it.get('qty', 0),
            it.get('unit_price', 0),
            it.get('amount', 0),
        ])
    rows.append(['合计', '—', '—', '—', estimate.get('total', 0)])
    return rows


def format_cny(amount: float) -> str:
    """
    将金额格式化为人民币展示字符串，如 '¥1,234,567.89'。

    参数:
        amount: 数值金额。
    返回:
        带千分位分隔符、固定 2 位小数的字符串；非法输入回退为 '¥0.00'。
    """
    f = _safe_float(amount, 0.0)
    if f is None:
        f = 0.0
    return '¥' + format(f, ',.2f')
