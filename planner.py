#!/usr/bin/env python3
"""
章节规划器 v2.2
基于招标文件解析结果，规划章节结构+页数分配
v2.2: 数据从 data/chapter_config.json 加载（P1-3 统一数据源重构）
v2.1: 增强评分项权重页数分配、服务类/施工类自动识别、页数分配算法优化
"""
import json

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


def plan_chapters(parse_result=None, user_chapters=None, target_pages=300,
                  project_info=None, work_type=None):
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
    
    # 优先级1：解析到的评分项
    if parse_result and parse_result.get('score_items'):
        score_items = parse_result['score_items']
        total_score = sum(item.get('score', 0) for item in score_items)
        if total_score > 0:
            for item in score_items:
                item_name = item.get('name') or item.get('title') or '未命名章节'
                score = item.get('score', 0)
                # v2.1: 使用关键词匹配找模板min_pages（修复逐字符遍历bug）
                min_p = _match_template_min_pages(item_name, chapter_template)
                chapters.append({
                    'title': item_name,
                    'score_weight': score,
                    'page_ratio': score / total_score,
                    'min_pages': min_p,
                    'source': '评分项',
                    'category': item.get('category', '技术'),
                })
            source = '评分项'
    
    # 优先级2：用户自定义章节
    elif user_chapters:
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
    
    # 优先级3：默认章节模板
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
        
        # 修正舍入误差
        allocated = sum(ch['target_pages'] for ch in chapters)
        diff = content_pages - allocated
        if diff != 0 and chapters:
            # 把差值加到权重最大的章节
            sorted_chapters = sorted(chapters, key=lambda x: x.get('score_weight', 0), reverse=True)
            sorted_chapters[0]['target_pages'] += diff
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
