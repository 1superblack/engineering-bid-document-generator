"""
资质-评分点响应映射 v7.5
────────────────────────────────────────────────────────────────
将招标文件解析出的 score_items（评分项）与投标人企业知识库(KB)能力做关联，
产出"评分项 → 我方响应保障"映射表。

对标主流产品差异点：
- 投标龙：工程类"资质有效性/项目经理业绩匹配度"自动校验（准确率≈90%）
- 链企AI：自动匹配评分点，调用行业模板与企业知识库/图库

设计原则：
- 纯数据计算，不依赖 Word 渲染（渲染在 bid_technical.tables.score_response_table）
- 与 user_context / 知识库解耦：能验证的尽量验证，不能验证的默认"承诺补充"
- 不阻断主流程：任何异常都降级为"返回空映射"，不影响标书生成
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# 评分项名称 → 响应保障类别 路由关键词
_KW_ROUTES = [
    ('业绩', ['业绩', '类似项目', '已完成', '成功案例', '项目经验']),
    ('人员', ['项目经理', '建造师', '负责人', '团队', '人员', '技术负责人',
             '项目管理机构', '岗位', '执业资格']),
    ('资质', ['资质', '资格', '证书', '许可', '认证', '等级']),
    ('设备', ['设备', '机械', '车辆', '仪器', '机具', '装备']),
    ('安全', ['安全', '防护', '应急', '事故']),
    ('财务', ['注册资金', '注册资本', '净资产', '财务', '营业额', '营业收入',
             '资产', '审计']),
]


def _route(score_name: str) -> str:
    for cat, kws in _KW_ROUTES:
        if any(k in score_name for k in kws):
            return cat
    return 'other'


def _to_dict(uc: Any) -> Dict[str, Any]:
    """统一 user_context 为 dict 形式（兼容 UserContext 实例与 dict）。"""
    if uc is None:
        return {}
    if isinstance(uc, dict):
        return uc
    if hasattr(uc, 'to_dict'):
        try:
            return uc.to_dict()
        except Exception:
            pass
    if hasattr(uc, 'data'):
        return getattr(uc, 'data') or {}
    return {}


def _asset_detail(cat: str, uc: Dict[str, Any]) -> Dict[str, Any]:
    """返回该类别下的我方响应保障说明与是否已有数据支撑。"""
    if cat == '业绩':
        projs = uc.get('similar_projects', []) or []
        if projs:
            names = '、'.join(str(p.get('name', '')) for p in projs if p.get('name'))[:40]
            return {'available': True, 'type_label': '企业业绩',
                    'detail': f'已录入 {len(projs)} 项类似业绩（{names}…），可逐条响应'}
        return {'available': False, 'type_label': '企业业绩',
                'detail': '需补充类似项目业绩证明（承诺附相关合同/中标通知书/验收证明）'}

    if cat == '人员':
        persons = uc.get('key_personnel', []) or []
        if persons:
            roles = '、'.join(str(p.get('role', '')) for p in persons if p.get('role'))[:40]
            return {'available': True, 'type_label': '项目团队',
                    'detail': f'已配置 {len(persons)} 名关键人员（{roles}），附执业资格证'}
        return {'available': False, 'type_label': '项目团队',
                'detail': '需配置项目经理及关键岗位人员并附执业资格/岗位证书'}

    if cat == '资质':
        comp = uc.get('company', {}) or {}
        quals = comp.get('qualifications') or uc.get('qualifications') or []
        if quals:
            return {'available': True, 'type_label': '企业资质',
                    'detail': '；'.join(str(q) for q in quals)[:60]}
        return {'available': False, 'type_label': '企业资质',
                'detail': '需附营业执照、资质证书等并承诺在有效期内'}

    if cat == '设备':
        eq = uc.get('equipment_owned', []) or []
        if eq:
            return {'available': True, 'type_label': '设备资源',
                    'detail': f'已配置 {len(eq)} 类主要设备/机械，承诺按进度到位'}
        return {'available': False, 'type_label': '设备资源',
                'detail': '需列明主要施工设备清单并承诺按工期进场'}

    if cat == '安全':
        return {'available': True, 'type_label': '安全体系',
                'detail': '承诺建立安全生产管理体系、投入专项安全经费并编报应急预案'}

    if cat == '财务':
        comp = uc.get('company', {}) or {}
        cap = comp.get('registered_capital') or comp.get('capital') or comp.get('net_assets')
        if cap:
            return {'available': True, 'type_label': '财务实力', 'detail': f'注册资本/净资产：{cap}'}
        return {'available': False, 'type_label': '财务实力',
                'detail': '需提供近三年财务审计报告并承诺主要财务指标达标'}

    return {'available': False, 'type_label': '综合响应',
            'detail': '投标人承诺完全满足本评分项要求，详见对应章节内容'}


def build_score_response_map(parse_result: Optional[Dict[str, Any]],
                             user_context: Any = None) -> Dict[str, Any]:
    """构建评分项 → 我方响应保障映射。

    Returns:
        {
          'rows':   [{'score_name','score','asset_type','asset_detail','satisfied'}],
          'total':  int,     # 评分项总数
          'mapped': int,     # 已有 KB 数据支撑的评分项数
          'coverage': int,   # 响应覆盖率(%)
        }
    """
    score_items = (parse_result or {}).get('score_items', []) or []
    if not score_items:
        return {'rows': [], 'total': 0, 'mapped': 0, 'coverage': 0}

    uc = _to_dict(user_context)
    rows: List[Dict[str, Any]] = []
    mapped = 0
    for it in score_items:
        name = (it.get('name') or it.get('title') or '').strip()
        score = it.get('score') or 0
        cat = _route(name)
        asset = _asset_detail(cat, uc)
        if asset['available']:
            mapped += 1
        rows.append({
            'score_name': name,
            'score': score,
            'asset_type': asset['type_label'],
            'asset_detail': asset['detail'],
            'satisfied': asset['available'],
        })

    coverage = round(mapped / len(score_items) * 100) if score_items else 0
    return {'rows': rows, 'total': len(score_items), 'mapped': mapped, 'coverage': coverage}


def summarize_score_response(parse_result: Optional[Dict[str, Any]],
                             user_context: Any = None) -> Dict[str, Any]:
    """便捷入口。"""
    return build_score_response_map(parse_result, user_context)
