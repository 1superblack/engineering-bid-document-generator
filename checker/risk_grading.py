"""P2: 三级废标风险分级（high / medium / low）

v8.2 从 legacy_backup/checker.py 迁移回 checker 包（扁平化打包时丢失）。
提供 grade_risk() 与 render_risk_markdown() 两个模块级函数。
"""
from typing import Any, Dict, List, Optional

_SEVERITY_TO_LEVEL = {
    'critical': 'high', 'high': 'high', 'medium': 'medium', 'low': 'low',
}


def _map_severity(sev: str) -> str:
    return _SEVERITY_TO_LEVEL.get((sev or '').lower(), 'medium')


def grade_risk(parse_result: Optional[Dict[str, Any]] = None,
               check_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """三级废标风险分级。

    high   : 100% 废标风险（废标/星号/强制/红线条款）
    medium : 可能扣分（warning 级合规问题）
    low    : 不影响中标（info 级提示）

    Args:
        parse_result: parser.py 解析结果
        check_result: 可选，BidChecker.run_all() 的返回，用于纳入合规检查结论
    """
    pr = parse_result or {}
    findings: List[Dict[str, Any]] = []

    # 1. 废标条款（结构化，含 severity）
    for dc in pr.get('disqualify_clauses_structured', []) or []:
        findings.append({
            'level': _map_severity(dc.get('severity', 'critical')),
            'type': '废标条款',
            'content': (dc.get('content') or '').strip(),
            'clause_number': dc.get('clause_number', '') or '',
        })

    # 2. 星号 / 强制条款
    for sc in pr.get('star_clauses', []) or []:
        if sc.get('type') in ('star_marked', 'mandatory'):
            findings.append({
                'level': 'high',
                'type': '星号/强制条款',
                'content': (sc.get('content') or '').strip(),
                'clause_number': '',
            })

    # 3. 红线条款
    for rc in pr.get('red_line_clauses', []) or []:
        findings.append({
            'level': 'high',
            'type': '红线条款',
            'content': (rc.get('content') or '').strip(),
            'clause_number': '',
        })

    # 4. 合规检查结论（若提供）
    if check_result:
        for lvl, key in (('high', 'critical'), ('medium', 'warning'), ('low', 'info')):
            for it in check_result.get('results', {}).get(key, []):
                findings.append({
                    'level': lvl,
                    'type': '合规检查',
                    'content': f"{it.get('name', '')}：{it.get('detail', '')}",
                    'clause_number': it.get('id', ''),
                })

    graded = {'high': [], 'medium': [], 'low': []}
    for f in findings:
        f['content'] = (f['content'] or '')[:200]
        if f['content']:
            graded[f['level']].append(f)

    overall = 'high' if graded['high'] else ('medium' if graded['medium'] else 'low')
    return {
        'high': graded['high'],
        'medium': graded['medium'],
        'low': graded['low'],
        'overall_level': overall,
        'total': len(graded['high']) + len(graded['medium']) + len(graded['low']),
    }


def render_risk_markdown(grading: Dict[str, Any]) -> str:
    """将三级风险分级渲染为 Markdown 报告。"""
    if not grading or not grading.get('total'):
        return '## 废标风险分级\n\n✅ 未识别到明确废标风险条款。'
    lines = ['## 废标风险三级预警', '']
    labels = {
        'high': '🔴 高（100% 废标风险）',
        'medium': '🟡 中（可能扣分）',
        'low': '🟢 低（不影响中标）',
    }
    for lvl in ('high', 'medium', 'low'):
        items = grading.get(lvl, [])
        if not items:
            continue
        lines.append(f'### {labels[lvl]}（{len(items)} 项）')
        for it in items:
            cl = f"[{it.get('clause_number')}] " if it.get('clause_number') else ''
            lines.append(f"- {it.get('type', '')} {cl}{it.get('content', '')}")
        lines.append('')
    overall = grading.get('overall_level')
    lines.append(f'**综合风险等级：{labels.get(overall, overall)}**')
    return '\n'.join(lines)
