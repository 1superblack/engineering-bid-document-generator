#!/usr/bin/env python3
"""
章节规划器 v2.2
基于招标文件解析结果，规划章节结构+页数分配
v2.2: 数据从 data/chapter_config.json 加载（P1-3 统一数据源重构）
v2.1: 增强评分项权重页数分配、服务类/施工类自动识别、页数分配算法优化
"""
import json
import re

from bid_core.data_loader import DataLoader

# ══════════════════════════════════════════════════════════════════
# 章节配置数据 — 从 data/chapter_config.json 加载（v2.2 重构）
# 原 DEFAULT_CHAPTERS / SERVICE_CHAPTERS / CHAPTER_KEYWORD_MAP /
# DIVISION_TEMPLATES 硬编码于本文件 L10-75，现已迁移至外部 JSON。
# ══════════════════════════════════════════════════════════════════

_chapter_config = DataLoader().load_chapter_config()

DEFAULT_CHAPTERS: list = _chapter_config.get('construction_chapters', [])
SERVICE_CHAPTERS: list = _chapter_config.get('service_chapters', [])
CHAPTER_KEYWORD_MAP: dict = _chapter_config.get('keyword_map', {})
DIVISION_TEMPLATES: dict = _chapter_config.get('division_templates', {})

# 服务类/施工类识别关键词
_SERVICE_KEYWORDS: list = _chapter_config.get('service_keywords', [
    '服务', '清洗', '消毒', '维护', '巡查', '保洁', '物业管理', '养护',
    '二次供水', '供水设施', '设施管理', '运营管理', '运维',
])
_CONSTRUCTION_KEYWORDS: list = _chapter_config.get('construction_keywords', [
    '施工', '装饰', '装修', '安装', '改造', '新建', '土建',
    '市政', '道路', '管网', '结构', '防水', '涂装',
])


def _match_template_min_pages(item_name, chapter_template):
    """通过关键词匹配找到模板中的min_pages"""
    best_match = None
    best_score = 0
    item_lower = item_name.lower()
    
    for tmpl in chapter_template:
        tmpl_title = tmpl['title']
        # 精确子串匹配
        if tmpl_title[:4] in item_lower or item_lower[:4] in tmpl_title:
            score = 10
            if score > best_score:
                best_score = score
                best_match = tmpl
            continue
        # 关键词匹配
        for key, keywords in CHAPTER_KEYWORD_MAP.items():
            if key in tmpl_title:
                for kw in keywords:
                    if kw in item_lower:
                        score = len(kw)  # 匹配越长关键词得分越高
                        if score > best_score:
                            best_score = score
                            best_match = tmpl
                        break
    
    if best_match:
        return best_match.get('min_pages', 8)
    return 8


def _filter_valid_score_items(items):
    """ADR-007: 只保留真正的技术评分项，剔除日期/勾选项/评标散文/超短碎片。

    返回过滤后的评分项列表（保留原字典结构，供路由与权重计算复用）。
    """
    valid = []
    for it in items or []:
        name = (it.get('name') or it.get('title') or '').strip()
        if not name:
            continue
        # 必须有数值分值（真正的评分项才有）；允许 weight 充当分值
        score = it.get('score')
        if not isinstance(score, (int, float)) or score <= 0:
            score = it.get('weight')
        if not isinstance(score, (int, float)) or score <= 0:
            continue
        # 剔除超短碎片（<3 字基本是噪声，如 "1."、"日 17时"）
        if len(name) < 3:
            continue
        # 剔除纯日期片段（含 年月日）
        if re.search(r'\d{1,4}\s*年|\d{1,2}\s*月|\d{1,2}\s*日', name):
            continue
        # 剔除勾选项（☑/□/√）
        if '☑' in name or '□' in name or '√' in name:
            continue
        valid.append(it)
    return valid


# 评分项名后缀计分标注（如「（4分）」「（2.5分）」），成章时剥离，避免标题带分
_SCORE_SUFFIX_RE = re.compile(r'\s*[（(]\s*\d+(?:\.\d+)?\s*分\s*[）)]\s*$')


def _clean_chapter_title(name):
    """ADR-009：把评分项名清洗为纯章名（去掉「（N分）」后缀与首尾空白）。"""
    name = (name or '').strip()
    name = _SCORE_SUFFIX_RE.sub('', name).strip()
    return name


# 骨架章 → 归属关键词（ADR-007：把评分项路由到唯一正确技术章）
_CHAPTER_ROUTE_KEYWORDS = {
    '工程概况及施工部署': ['概况', '部署', '总体', '综述', '项目概况'],
    '施工总进度计划及保障措施': ['进度', '工期', '节点', '计划', 'timeline', '总进度', '进度计划', '总进度计划'],
    '施工总平面布置': ['平面', '布置', '场布', '临设', '总平', '总平面布置'],
    '主要分部分项工程施工方案': ['施工', '方案', '分部分项', '工艺', '工序', '技术', '实施', '施工方案', '分部分项工程'],
    '质量保证措施和创优计划': ['质量', '创优', '验收', '合格', '标准', '质保'],
    '安全生产保证措施': ['安全', '防护', '事故', '隐患', '消防', '安全生产'],
    '文明施工与环境保护措施': ['文明', '环保', '节能', '绿色', '环境', '扬尘', '围挡'],
    '季节性施工保障措施': ['季节', '雨季', '冬', '夏', '高温', '防汛', '季节性'],
    '应急预案与救援措施': ['应急', '预案', '救援', '演练', '抢险'],
    '劳动力及材料供应计划': ['劳动力', '材料', '供应', '资源', '物资'],
    '施工机械设备配置': ['设备', '机械', '机具', '装备', '仪器', '施工机械', '机械设备', '施工设备'],
    '项目管理班子配备': ['项目机构', '管理班子', '人员', '项目经理', '班子', '机构'],
    '成品保护及工程保修': ['成品保护', '保修', '维保', '养护'],
    # 服务类
    '项目理解与服务方案': ['理解', '服务', '需求', '认识'],
    '服务团队及人员配置': ['团队', '人员', '配置', ' staffing'],
    '服务流程与标准': ['流程', '标准', '规范', '规程'],
    '质量控制与保障措施': ['质量', '控制', '保障'],
    '应急响应机制': ['应急', '响应'],
    '安全与保密管理': ['安全', '保密'],
    '保密与合规管理': ['保密', '合规', '法规'],
}


def _route_score_item_to_chapter(name, chapter_template):
    """ADR-007: 把评分项名路由到唯一骨架章；无匹配返回 None（不建章）。

    命中关键词越长越优先，避免泛词误匹配到多个章。
    """
    if not name:
        return None
    best, best_kw = None, 0
    for ch in chapter_template:
        kws = _CHAPTER_ROUTE_KEYWORDS.get(ch['title'], [])
        for kw in kws:
            if kw in name and len(kw) > best_kw:
                best, best_kw = ch['title'], len(kw)
                break
    return best


def plan_chapters(parse_result=None, user_chapters=None, target_pages=300,
                  project_info=None, work_type=None, aggregate_score_items=True):
    """
    规划章节结构和页数分配 v2.1
    
    v2.1 changes:
    - 评分项高分项分配更多页数（加权分配）
    - 关键词匹配逻辑修复（不再逐字符遍历）
    - 服务类/施工类关键词更全面
    - 页数分配算法优化：高分项获得额外页数奖励
    """
    chapters = []
    source = 'default'
    
    # 判断标书类型
    bid_type = 'construction'
    if parse_result and parse_result.get('bid_type'):
        bid_type = parse_result['bid_type']
    elif project_info and project_info.get('bid_type'):
        bid_type = project_info['bid_type']
    else:
        # 通过工程内容关键词自动识别
        content = ''
        if project_info:
            content = (project_info.get('work_content', '') or '') + (project_info.get('work_type', '') or '')
        # 服务类关键词（v2.1扩展）
        SERVICE_KEYWORDS = _SERVICE_KEYWORDS
        # 施工类关键词
        CONSTRUCTION_KEYWORDS = _CONSTRUCTION_KEYWORDS
        service_score = sum(1 for kw in SERVICE_KEYWORDS if kw in content)
        construction_score = sum(1 for kw in CONSTRUCTION_KEYWORDS if kw in content)
        if service_score > construction_score:
            bid_type = 'service'
    
    # 选择章节模板
    if bid_type == 'service':
        chapter_template = SERVICE_CHAPTERS
    else:
        chapter_template = DEFAULT_CHAPTERS
    
    # 优先级1：技术评审表抽取的技术标一级章（ADR-009 修复：最可靠来源）
    #   招标文件「技术评审」评分表直接列出技术标应包含的章节
    #   （如「施工总进度计划及保障措施」），比泛化的 score_items
    #   （常混入形式/响应性/报价条款）更准确，且章名严格来自招标文件。
    tech_chapters = (parse_result or {}).get('technical_chapters') or []
    user_chapters = user_chapters or []

    # 优先级1：用户显式指定章节（最高优先，覆盖一切自动抽取——
    #   用户明确知道要哪些章，例如直接给出招标文件技术评审表的 13 个评分项）。
    if user_chapters:
        n = len(user_chapters)
        for ch in user_chapters:
            min_p = _match_template_min_pages(ch, chapter_template)
            chapters.append({
                'title': ch,
                'score_weight': 0,
                'page_ratio': 1.0 / n,
                'min_pages': min_p,
                'source': '用户指定',
            })
        source = '用户指定'

    # 优先级2：技术评审表抽取（ADR-009 修复：最可靠来源，章名严格来自招标文件）。
    #   要求 ≥5 项才采用——若仅抽到 1~4 项视为抽取不完整，降级到评分项/模板，
    #   避免残章劫持整份规划（此前武汉三镇中心抽取异常时只抽到 1 项即触发）。
    elif len(tech_chapters) >= 5:
        seen = set()
        n = len(tech_chapters)
        for it in tech_chapters:
            raw = it.get('name') or ''
            title = _clean_chapter_title(raw)
            if not title or title in seen:
                continue
            seen.add(title)
            chapters.append({
                'title': title,
                'score_weight': 0,
                'page_ratio': 1.0 / n,
                'min_pages': 3,
                'score_items': [it],
                'source': '技术评审表',
                'category': '技术',
            })
        source = '技术评审表'

    # 优先级3：解析到的评分项 → 直接作为技术章节（ADR-009：章节名严格来自招标文件）
    elif parse_result and parse_result.get('score_items') and aggregate_score_items:
        score_items = _filter_valid_score_items(parse_result['score_items'])
        if score_items:
            total_score = sum(it.get('score', 0) for it in score_items) or 1
            seen = set()
            for it in score_items:
                raw = it.get('name') or it.get('title') or ''
                title = _clean_chapter_title(raw)
                if not title or title in seen:
                    continue
                seen.add(title)
                w = it.get('score', 0) or 0
                ratio = (w / total_score) if w > 0 else (1.0 / len(score_items))
                chapters.append({
                    'title': title,
                    'score_weight': w,
                    'page_ratio': ratio,
                    'min_pages': 3,
                    'score_items': [it],
                    'source': '评分项驱动',
                    'category': '技术',
                })
            source = '评分项驱动'

    # 优先级4：默认章节模板
    else:
        total_weight = sum(ch['weight'] for ch in chapter_template)
        for ch in chapter_template:
            chapters.append({
                'title': ch['title'],
                'score_weight': 0,
                'page_ratio': ch['weight'] / total_weight,
                'min_pages': ch.get('min_pages', 8),
                'source': '服务类模板' if bid_type == 'service' else '默认模板',
                'bid_type': bid_type,
            })
    
    # 页数分配（v2.1增强）
    table_pages = 20  # 附表预留页数
    if target_pages > 0:
        content_pages = max(target_pages - table_pages, sum(ch['min_pages'] for ch in chapters))
        
        # v2.1: 高分项获得额外页数奖励
        # 计算权重增强：高分项的page_ratio乘以增强系数
        if any(ch.get('score_weight', 0) > 0 for ch in chapters):
            max_score = max(ch.get('score_weight', 0) for ch in chapters)
            if max_score > 0:
                enhanced_ratios = []
                for ch in chapters:
                    base_ratio = ch['page_ratio']
                    score = ch.get('score_weight', 0)
                    # 高分项增强：得分/最高分 * 增强因子(1.0)，最高可达2.0x
                    enhancement = 1.0 + (score / max_score) * 1.0
                    enhanced_ratios.append(base_ratio * enhancement)
                
                # 归一化
                total_enhanced = sum(enhanced_ratios)
                if total_enhanced > 0:
                    for i, ch in enumerate(chapters):
                        ch['page_ratio'] = enhanced_ratios[i] / total_enhanced
        
        # 按增强后的权重分配页数
        for ch in chapters:
            ch['target_pages'] = max(ch['min_pages'], round(content_pages * ch['page_ratio']))
        
        # 修正舍入误差（每章页数不得低于 min_pages，防止把某章压到 0）
        allocated = sum(ch['target_pages'] for ch in chapters)
        diff = content_pages - allocated
        if diff != 0 and chapters:
            # 按当前页数降序调整，仅在高于 min_pages 时减，避免首章被清零
            order = sorted(chapters, key=lambda x: x['target_pages'], reverse=True)
            idx = 0
            guard = len(order) * 20
            while diff != 0 and idx <= guard:
                ch = order[idx % len(order)]
                if diff > 0:
                    ch['target_pages'] += 1
                    diff -= 1
                elif ch['target_pages'] > ch['min_pages']:
                    ch['target_pages'] -= 1
                    diff += 1
                # 该章已到下限且需减：跳过（宁可整体略超 content_pages，不把章压空）
                idx += 1
    else:
        for ch in chapters:
            ch['target_pages'] = 0
    
    # 匹配专项方案
    divisions = _match_divisions(project_info, work_type)
    
    total_pages = sum(ch['target_pages'] for ch in chapters) + table_pages
    
    # 计算detail_level
    detail_level = 2
    if target_pages >= 200:
        detail_level = 3
    elif target_pages > 0 and target_pages <= 50:
        detail_level = 1
    
    return {
        'chapters': chapters,
        'total_chapters': len(chapters),
        'total_pages': total_pages if target_pages > 0 else 0,
        'divisions': divisions,
        'source': source,
        'detail_level': detail_level,
        'bid_type': bid_type,
    }


def _match_divisions(project_info, work_type):
    """匹配工程类型的分项工程模板"""
    if not work_type and project_info:
        work_content = project_info.get('work_content', '') or project_info.get('work_type', '')
        if not work_content:
            work_content = '装饰装修'
    else:
        work_content = work_type or '装饰装修'
    
    divisions = []
    for key, templates in DIVISION_TEMPLATES.items():
        if key in work_content:
            divisions = templates
            break
    
    if not divisions:
        for key, templates in DIVISION_TEMPLATES.items():
            for t in templates:
                if t[:2] in work_content:
                    divisions = templates
                    break
            if divisions:
                break
    
    if not divisions:
        divisions = DIVISION_TEMPLATES['装饰装修']
    
    return divisions


if __name__ == '__main__':
    # 测试1：200页施工类
    r1 = plan_chapters(target_pages=200)
    print(f"测试1 200页施工类：{r1['total_chapters']}章，{r1['total_pages']}页，detail={r1['detail_level']}")
    for ch in r1['chapters']:
        print(f"  {ch['title']}：{ch['target_pages']}页（保底{ch['min_pages']}页）")
    
    # 测试2：评分项驱动（服务类）
    parse_result = {
        'score_items': [
            {'title': '安全生产', 'score': 10},
            {'title': '环境污染', 'score': 7.5},
            {'title': '项目质量', 'score': 7.5},
            {'title': '主要实施方案', 'score': 6},
            {'title': '劳动力', 'score': 6},
            {'title': '机械设备', 'score': 6},
            {'title': '文明施工', 'score': 6},
            {'title': '重难点', 'score': 6},
            {'title': '工程工期', 'score': 5},
        ],
        'bid_type': 'service',
    }
    r2 = plan_chapters(parse_result=parse_result, target_pages=250)
    print(f"\n测试2 250页服务类(评分项)：{r2['total_chapters']}章，{r2['total_pages']}页，detail={r2['detail_level']}")
    for ch in r2['chapters']:
        print(f"  {ch['title']}：{ch['target_pages']}页（评分{ch['score_weight']}分）")
    
    # 测试3：服务类自动识别
    r3 = plan_chapters(target_pages=200, project_info={'work_content': '二次供水设施清洗消毒维护服务'})
    print(f"\n测试3 200页服务类(自动识别)：{r3['total_chapters']}章，type={r3['bid_type']}")
    for ch in r3['chapters']:
        print(f"  {ch['title']}：{ch['target_pages']}页")
