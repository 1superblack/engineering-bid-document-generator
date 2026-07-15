#!/usr/bin/env python3
"""
BidAssembler - 标书组装器 v1.0
负责标书的最终组装，包括页数分配、章节过渡、目录生成、附件管理、页数校验与填充

核心能力：
1. 智能页数分配：根据target_pages和评分项权重动态分配每章页数
2. 章节间过渡内容：每章开头插入"本章概述"、结尾插入"本章小结"
3. 目录生成集成：文档开头自动插入目录页
4. 附件管理增强：附件目录自动生成、编号规范化
5. 页数校验与填充：未达target_pages时自动识别薄弱章节并追加内容
6. scoring_strategy集成：预留接口，可用时使用其分配方案
"""
import os
import sys
import math
import copy
from typing import List, Dict, Optional, Any

# 章节过渡内容模板
_OVERVIEW_TEMPLATES = {
    'construction': [
        "本章围绕{title}展开论述，系统阐述我方在本工程中的{core}措施与保障方案。",
        "结合{project_name}的工程特点与施工条件，从组织管理、技术措施、资源配置等多个维度进行详细规划。",
        "重点明确{core}的目标、原则、方法和保障机制，确保各项工作有据可依、有章可循。",
        "全章内容严格对标招标文件评分要求，确保各项措施与评分项高度对齐。",
    ],
    'service': [
        "本章聚焦{title}，全面阐述我方针对{project_name}的{core}方案与保障措施。",
        "从服务标准、实施流程、质量管控、人员配置等方面进行系统性规划，确保服务体系完整高效。",
        "核心目标在于通过科学的管理方法和完善的保障机制，确保{core}目标全面达成。",
        "各项措施严格对标招标文件评分项要求，力争{core}部分取得满分。",
    ],
}

_SUMMARY_TEMPLATES = {
    'construction': [
        "综上所述，我方在{title}方面已制定完善的{core}措施体系，从组织、技术、资源、制度等层面构建了全方位保障。",
        "各项措施之间相互支撑、协调配合，形成了完整的{core}闭环管理机制。",
        "我方郑重承诺：严格执行上述措施，确保{project_name}{title}各项目标全面达成。",
        "施工过程中将持续优化改进，确保{core}始终处于受控状态，为工程顺利实施提供坚实保障。",
    ],
    'service': [
        "综上所述，我方在{title}方面已建立完善的服务管理体系和保障机制，确保各项服务目标全面达成。",
        "通过制度保障、过程管控、持续改进的闭环管理，确保{core}水平始终保持行业领先。",
        "我方郑重承诺：严格执行上述方案，确保{project_name}{title}各项目标全面实现。",
        "将持续优化服务流程，提升服务品质，为业主提供优质、高效、专业的服务保障。",
    ],
}

# 页数填充追加段落模板
_FILL_TEMPLATES = {
    '补充措施': [
        "针对{title}，我方进一步补充以下强化措施：建立健全专项管理制度，明确各级管理人员职责，"
        "制定详细的考核标准和奖惩办法，确保各项管理措施有效落实到位。",
        "加强过程监控和动态管理，定期组织专项检查和评估，对发现的问题及时采取纠偏措施，"
        "确保{title}各项工作始终处于受控状态，不偏离既定目标。",
        "建立信息反馈机制，畅通上下沟通渠道，及时收集和处理一线反馈信息，"
        "确保管理层能够第一时间掌握现场动态，做出科学决策。",
    ],
    '延伸说明': [
        "在{title}实施过程中，我方注重经验积累和持续改进，建立完善的知识管理体系，"
        "定期组织技术交流和经验分享，不断提升团队专业水平和管理能力。",
        "积极引入先进的管理理念和技术手段，对标行业标杆，"
        "持续优化{title}的管理流程和技术方案，追求卓越品质。",
        "加强与行业主管部门和专业机构的交流合作，"
        "及时了解和掌握最新的政策法规和技术标准，确保{title}始终与时俱进。",
    ],
    '案例参考': [
        "我方在以往类似工程中积累了丰富的{title}经验，形成了成熟的管控体系和标准化的操作流程。",
        "参考同类工程的成功实践，我方在{title}方面已形成了系统化的管理方案，"
        "能够有效应对各种复杂情况和突发状况，确保项目顺利推进。",
        "结合以往工程中的经验教训，我方对{title}可能面临的风险和挑战进行了充分预判，"
        "制定了针对性的预防和应对措施，最大限度降低风险影响。",
    ],
}

# 核心关键词提取映射
_KEYWORD_CORE_MAP = {
    '进度': '进度管控',
    '工期': '进度管控',
    '质量': '质量管理',
    '安全': '安全管理',
    '文明': '文明施工',
    '环保': '环境保护',
    '施工方案': '施工技术',
    '分项': '施工技术',
    '总承包': '总承包管理',
    '测量': '测量控制',
    '组织': '组织管理',
    '分包': '分包管理',
    '成品': '成品保护',
    '保修': '保修服务',
    '紧急': '应急管理',
    '预案': '应急管理',
    '雨季': '季节性施工',
    '冬季': '季节性施工',
    '平面': '现场布置',
    '重难点': '重难点突破',
    '服务': '服务保障',
    '维护': '维护管理',
    '人员': '人员管理',
    '设备': '设备管理',
    '承诺': '服务承诺',
}


class BidAssembler:
    """标书组装器 — 负责最终组装、页数控制与内容增强"""

    DEFAULT_TARGET_PAGES = 300
    TABLE_PAGES_RESERVE = 20   # 附表预留页数
    TOC_PAGES_RESERVE = 3      # 目录预留页数
    COVER_PAGES_RESERVE = 1    # 封面预留页数
    MIN_PAGES_PER_CHAPTER = 8  # 每章最少页数

    def __init__(self, formatter, project_info: Dict,
                 chapters: List[Dict], tables: List[Dict],
                 target_pages: int = 0, parse_result: Optional[Dict] = None,
                 bid_type: str = 'construction', plan: Optional[Dict] = None):
        """
        Args:
            formatter: NormalFormatter 实例
            project_info: 项目信息字典
            chapters: 章节列表 [{'title': ..., 'keywords': [...], 'plan_info': {...}}]
            tables: 附表列表
            target_pages: 目标总页数，0表示使用默认值
            parse_result: 招标文件解析结果（含评分项）
            bid_type: 标书类型 'construction' / 'service'
            plan: planner.py 返回的规划结果
        """
        self.fmt = formatter
        self.project_info = project_info
        self.chapters = chapters
        self.tables = tables
        self.target_pages = target_pages or self.DEFAULT_TARGET_PAGES
        self.parse_result = parse_result or {}
        self.bid_type = bid_type
        self.plan = plan or {}

        # 页数分配结果
        self._chapter_pages: Dict[str, int] = {}   # title -> allocated_pages
        # 附件清单
        self._attachments: List[Dict] = []

        # scoring_strategy 集成（预留接口）
        self._scoring_strategy = None
        self._init_scoring_strategy()

    # ──────────────────────────────────────────────────────
    # 6. scoring_strategy 集成（预留接口）
    # ──────────────────────────────────────────────────────
    def _init_scoring_strategy(self):
        """尝试加载 scoring_strategy 模块，可用则使用其分配方案"""
        try:
            from scoring_strategy import ScoringStrategy
            self._scoring_strategy = ScoringStrategy(
                parse_result=self.parse_result,
                target_pages=self.target_pages,
                project_info=self.project_info,
            )
        except (ImportError, Exception):
            self._scoring_strategy = None

    def _get_scoring_allocation(self) -> Optional[Dict]:
        """如果 scoring_strategy 可用，获取其页数分配方案"""
        if self._scoring_strategy is None:
            return None
        try:
            allocation = self._scoring_strategy.allocate_pages(
                chapters=self.chapters,
                score_items=self.parse_result.get('score_items', []),
                target_pages=self.target_pages,
            )
            if allocation and isinstance(allocation, dict):
                return allocation
        except Exception as e:
            from bid_core.logger import get_logger
            get_logger(__name__).warning('页数分配失败，降级到默认分配: %s', e)
        return None

    # ──────────────────────────────────────────────────────
    # 1. 智能页数分配
    # ──────────────────────────────────────────────────────
    def allocate_pages(self, chapters: List[Dict],
                       score_items: List[Dict],
                       target_pages: int) -> Dict[str, int]:
        """
        根据 target_pages 和评分项权重动态分配每章页数

        策略：
        a. 优先使用 scoring_strategy 的分配方案（如果可用）
        b. 否则使用默认分配逻辑：
           - 从 target_pages 扣除封面、目录、附表预留页数
           - 对每个章节：基础页 = content_pages × (score_weight / total_score)
           - 高分项增强：score_weight 越高，增强系数越大
           - 确保每章不低于 MIN_PAGES_PER_CHAPTER
           - 修正舍入误差，使总页数恰好等于 target_pages

        Args:
            chapters: 章节列表，每个含 title, plan_info(含 score_weight/page_ratio/target_pages)
            score_items: 评分项列表（来自 parse_result）
            target_pages: 目标总页数

        Returns:
            {chapter_title: allocated_pages} 映射
        """
        # 尝试使用 scoring_strategy
        scoring_alloc = self._get_scoring_allocation()
        if scoring_alloc:
            return scoring_alloc

        if not chapters:
            return {}

        # 计算可用于章节内容的页数
        reserved = (self.COVER_PAGES_RESERVE + self.TOC_PAGES_RESERVE
                    + self.TABLE_PAGES_RESERVE)
        content_pages = max(target_pages - reserved, len(chapters) * self.MIN_PAGES_PER_CHAPTER)

        # 收集每个章节的权重信息
        chapter_weights = []
        for ch in chapters:
            plan_info = ch.get('plan_info') or {}
            score_weight = plan_info.get('score_weight', 0)
            page_ratio = plan_info.get('page_ratio', 0)
            min_pages = plan_info.get('min_pages', self.MIN_PAGES_PER_CHAPTER)

            if score_weight > 0:
                weight = score_weight
            elif page_ratio > 0:
                weight = page_ratio * 100  # 归一化到与 score_weight 相近的量级
            else:
                weight = 1.0  # 等权兜底

            chapter_weights.append({
                'title': ch['title'],
                'weight': weight,
                'min_pages': max(min_pages, self.MIN_PAGES_PER_CHAPTER),
            })

        # 高分项增强分配
        total_weight = sum(cw['weight'] for cw in chapter_weights)
        if total_weight <= 0:
            total_weight = 1.0

        max_weight = max(cw['weight'] for cw in chapter_weights)
        enhanced_ratios = []
        for cw in chapter_weights:
            base_ratio = cw['weight'] / total_weight
            if max_weight > 0:
                enhancement = 1.0 + (cw['weight'] / max_weight) * 0.8
            else:
                enhancement = 1.0
            enhanced_ratios.append(base_ratio * enhancement)

        # 归一化增强后的比例
        total_enhanced = sum(enhanced_ratios)
        if total_enhanced <= 0:
            total_enhanced = 1.0

        # 分配页数
        allocation = {}
        for i, cw in enumerate(chapter_weights):
            ratio = enhanced_ratios[i] / total_enhanced
            allocated = max(cw['min_pages'], round(content_pages * ratio))
            allocation[cw['title']] = allocated

        # 修正舍入误差
        total_allocated = sum(allocation.values())
        diff = content_pages - total_allocated
        if diff != 0 and chapter_weights:
            # 差值分配给权重最大的章节
            sorted_titles = sorted(
                chapter_weights,
                key=lambda x: x['weight'],
                reverse=True
            )
            title = sorted_titles[0]['title']
            allocation[title] += diff

        self._chapter_pages = allocation
        return allocation

    # ──────────────────────────────────────────────────────
    # 2. 章节间过渡内容
    # ──────────────────────────────────────────────────────
    def render_chapter_overview(self, chapter_title: str):
        """在每章开头插入"本章概述"段落（3-5行，概括本章重点）

        Args:
            chapter_title: 章节标题
        """
        core = self._extract_core_keyword(chapter_title)
        project_name = self.project_info.get('name', '本项目')
        templates = _OVERVIEW_TEMPLATES.get(self.bid_type,
                                            _OVERVIEW_TEMPLATES['construction'])
        self.fmt.h2("本章概述")
        # 选取3-5行
        selected = templates[:min(len(templates), 4)]
        for tpl in selected:
            text = tpl.format(title=chapter_title, core=core, project_name=project_name)
            self.fmt.body(text)

    def render_chapter_summary(self, chapter_title: str):
        """在每章结尾插入"本章小结"段落（3-5行，总结关键措施）

        Args:
            chapter_title: 章节标题
        """
        core = self._extract_core_keyword(chapter_title)
        project_name = self.project_info.get('name', '本项目')
        templates = _SUMMARY_TEMPLATES.get(self.bid_type,
                                           _SUMMARY_TEMPLATES['construction'])
        self.fmt.h2("本章小结")
        selected = templates[:min(len(templates), 4)]
        for tpl in selected:
            text = tpl.format(title=chapter_title, core=core, project_name=project_name)
            self.fmt.body(text)

    def _extract_core_keyword(self, title: str) -> str:
        """从章节标题中提取核心关键词

        Args:
            title: 章节标题

        Returns:
            匹配到的核心关键词，默认返回'项目实施'
        """
        for kw, core in _KEYWORD_CORE_MAP.items():
            if kw in title:
                return core
        return '项目实施'

    # ──────────────────────────────────────────────────────
    # 3. 目录生成集成
    # ──────────────────────────────────────────────────────
    def render_toc(self):
        """在文档开头插入目录页

        调用 formatter 的 add_toc() 方法插入Word自动目录域代码，
        并在此基础上补充章节标题列表作为可见的目录内容。
        """
        # 使用 formatter 的 add_toc（插入 Word TOC 域代码）
        self.fmt.add_toc()

        # 额外插入可见章节目录（作为占位内容，打开文档后刷新域即可自动替换）
        self.fmt.body("—  章节目录  —")
        self.fmt.body("")
        for i, ch in enumerate(self.chapters, 1):
            cn_nums = ["", "一", "二", "三", "四", "五", "六", "七", "八",
                       "九", "十", "十一", "十二", "十三", "十四", "十五",
                       "十六", "十七", "十八", "十九", "二十"]
            num_str = cn_nums[i] if i <= 20 else str(i)
            title = ch.get('title', '')
            pages = self._chapter_pages.get(title, 0)
            if pages > 0:
                self.fmt.body(f"{num_str}、{title}··········{pages}页")
            else:
                self.fmt.body(f"{num_str}、{title}")

        self.fmt.page_break()

    # ──────────────────────────────────────────────────────
    # 4. 附件管理增强
    # ──────────────────────────────────────────────────────
    def register_attachment(self, title: str, category: str = '附件',
                           description: str = '') -> str:
        """注册一个附件，返回规范化编号

        Args:
            title: 附件标题
            category: 附件分类（如'附件'、'附图'、'附表'）
            description: 附件简要说明

        Returns:
            规范化编号，如 '附件1'、'附件2'
        """
        idx = len(self._attachments) + 1
        att = {
            'num': idx,
            'code': f'附件{idx}',
            'title': title,
            'category': category,
            'description': description,
        }
        self._attachments.append(att)
        return att['code']

    def render_attachment_directory(self):
        """自动生成附件目录页"""
        if not self._attachments:
            return

        self.fmt.add_heading("附件目录")
        self.fmt.body("以下为本次投标文件所附附件清单：")
        self.fmt.body("")

        headers = ['序号', '编号', '附件名称', '类别', '说明']
        rows = []
        for att in self._attachments:
            rows.append([
                str(att['num']),
                att['code'],
                att['title'],
                att['category'],
                att['description'],
            ])
        self.fmt.table(headers, rows)
        self.fmt.body("")
        self.fmt.body(
            "注：以上附件均为本次投标文件不可分割的组成部分，"
            "与投标文件正文具有同等法律效力。"
        )
        self.fmt.page_break()

    def normalize_attachment_numbers(self, tables: List[Dict]) -> List[Dict]:
        """对附表列表进行编号规范化

        确保每个附表的 num 字段连续且格式统一。

        Args:
            tables: 附表列表

        Returns:
            编号规范化后的附表列表
        """
        normalized = []
        for i, t in enumerate(tables):
            t_copy = copy.deepcopy(t)
            if 'num' not in t_copy or not t_copy['num']:
                t_copy['num'] = f'{i + 1}'
            # 统一编号格式：x.y
            raw = t_copy['num']
            # 已是标准格式(如 2.1)的保持不变
            if '.' not in str(raw):
                t_copy['num'] = f'2.{i + 1}'
            normalized.append(t_copy)
        return normalized

    # ──────────────────────────────────────────────────────
    # 5. 页数校验与填充
    # ──────────────────────────────────────────────────────
    def estimate_rendered_pages(self) -> int:
        """粗估已渲染的页数

        基于文档中的段落数和表格数进行估算。
        约25个段落≈1页，每个表格≈2页。

        Returns:
            估算的页数
        """
        doc = self.fmt.get_document()
        para_count = len(doc.paragraphs)
        table_count = len(doc.tables)
        estimated = para_count / 25.0 + table_count * 2
        return int(estimated)

    def check_and_fill_pages(self, chapters_rendered: List[Dict]):
        """检查总页数并自动填充

        如果未达到 target_pages，自动识别薄弱章节并追加内容。
        追加策略：增加"补充措施""延伸说明""案例参考"等段落。

        Args:
            chapters_rendered: 已渲染的章节列表，每个含 title, plan_info
        """
        if self.target_pages <= 0:
            return

        estimated = self.estimate_rendered_pages()
        shortfall = self.target_pages - estimated

        if shortfall <= 0:
            return  # 已达标

        project_name = self.project_info.get('name', '本项目')

        # 按权重排序，优先补充高分/薄弱章节
        sorted_chapters = sorted(
            chapters_rendered,
            key=lambda c: c.get('plan_info', {}).get('score_weight', 0),
            reverse=True
        )

        # 计算每个薄弱章节应补充的页数
        fill_order = ['补充措施', '延伸说明', '案例参考']
        remaining = shortfall

        for ch_info in sorted_chapters:
            if remaining <= 0:
                break

            title = ch_info['title']
            core = self._extract_core_keyword(title)
            # 每章补充约 2-4 页
            pages_to_add = min(4, max(2, remaining // max(len(sorted_chapters), 1)))

            for section_name in fill_order:
                if remaining <= 0:
                    break

                templates = _FILL_TEMPLATES.get(section_name, [])
                if not templates:
                    continue

                self.fmt.h2(f"{title} — {section_name}")
                for tpl in templates:
                    if remaining <= 0:
                        break
                    text = tpl.format(title=title, core=core, project_name=project_name)
                    self.fmt.body(text)
                    remaining -= 1  # 粗估每段约1/2页

        # 如果仍有差距，循环追加
        loop_count = 0
        while remaining > 0 and loop_count < 3:
            loop_count += 1
            for ch_info in sorted_chapters:
                if remaining <= 0:
                    break
                title = ch_info['title']
                core = self._extract_core_keyword(title)
                self.fmt.h2(f"{title} — 综合保障补充")
                self.fmt.body(
                    f"在{title}方面，我方将进一步强化综合保障措施，"
                    f"确保{project_name}{core}目标的全面实现。"
                    f"通过持续的过程监控、动态的资源调配和完善的应急响应机制，"
                    f"构建全方位、多层次的保障体系。"
                )
                self.fmt.body(
                    f"我方将持续完善{title}的管理制度和技术措施，"
                    f"建立常态化的检查评估机制，定期总结经验、查找不足、持续改进，"
                    f"确保{core}工作水平不断提升，为{project_name}的顺利实施提供坚实保障。"
                )
                remaining -= 1

    # ──────────────────────────────────────────────────────
    # 主组装流程
    # ──────────────────────────────────────────────────────
    def assemble(self, render_chapter_func, render_tables_func,
                 before_render_func=None, after_render_func=None) -> Dict:
        """
        完整的标书组装流程

        Args:
            render_chapter_func: 章节渲染回调函数 (ch_info, plan_info) -> None
            render_tables_func: 附表渲染回调函数 () -> None
            before_render_func: 渲染前钩子（封面等） () -> None
            after_render_func: 渲染后钩子（页码等） () -> None

        Returns:
            组装结果摘要字典
        """
        # 1. 智能页数分配
        score_items = self.parse_result.get('score_items', [])
        allocation = self.allocate_pages(self.chapters, score_items, self.target_pages)

        # 2. 附件编号规范化
        self.tables = self.normalize_attachment_numbers(self.tables)

        # 3. 注册附件
        for t in self.tables:
            att_title = t.get('title', '')
            self.register_attachment(att_title, category='附表')

        # 4. 渲染前钩子（封面）
        if before_render_func:
            before_render_func()

        # 5. 目录生成
        self.render_toc()

        # 6. 遍历章节渲染（含过渡内容）
        for i, ch_info in enumerate(self.chapters, 1):
            title = ch_info.get('title', '')
            plan_info = ch_info.get('plan_info') or {}

            # 章节标题
            self.fmt.h1(i, title)

            # 本章概述
            self.render_chapter_overview(title)

            # 章节正文渲染（调用外部回调）
            render_chapter_func(ch_info, plan_info)

            # 本章小结
            self.render_chapter_summary(title)

        # 7. 附件目录
        self.render_attachment_directory()

        # 8. 附表渲染
        render_tables_func()

        # 9. 页数校验与填充
        self.check_and_fill_pages(self.chapters)

        # 10. 渲染后钩子（页码等）
        if after_render_func:
            after_render_func()

        # 组装结果摘要
        final_pages = self.estimate_rendered_pages()
        return {
            'target_pages': self.target_pages,
            'estimated_pages': final_pages,
            'page_fill_rate': round(final_pages / self.target_pages * 100, 1) if self.target_pages > 0 else 0,
            'chapter_allocation': allocation,
            'attachment_count': len(self._attachments),
            'chapters_count': len(self.chapters),
        }


# ══════════════════════════════════════════════════════════
# 便捷函数：直接与 TechnicalBidGenerator 集成
# ══════════════════════════════════════════════════════════
def assemble_with_generator(generator, output_path: str) -> str:
    """
    使用 BidAssembler 增强 TechnicalBidGenerator 的组装流程

    此函数替换 generator.generate() 中的原有组装逻辑，
    在不修改 generator 代码的前提下，增强页数控制、过渡内容、目录、附件管理。

    Args:
        generator: TechnicalBidGenerator 实例
        output_path: 输出文件路径

    Returns:
        输出文件路径
    """
    assembler = BidAssembler(
        formatter=generator.formatter,
        project_info=generator.project_info,
        chapters=_build_chapters_from_generator(generator),
        tables=generator.tables,
        target_pages=generator.target_pages,
        parse_result=generator.parse_result,
        bid_type=generator.bid_type,
        plan=generator.plan if hasattr(generator, 'plan') else None,
    )

    def render_chapter(ch_info, plan_info):
        generator.render_chapter(ch_info, plan_info=plan_info)

    def render_tables():
        generator.render_tables()

    result = assembler.assemble(
        render_chapter_func=render_chapter,
        render_tables_func=render_tables,
        before_render_func=generator.before_render,
        after_render_func=generator.after_render,
    )

    # 保存文档
    generator.formatter.save(output_path)

    # 打印摘要（调试用）
    if os.environ.get('BID_ASSEMBLER_DEBUG'):
        log.info("组装完成: %s", result)

    return output_path


def _build_chapters_from_generator(generator) -> List[Dict]:
    """从 generator 中提取章节列表（兼容 plan 和 fallback）"""
    chapters_to_render = []
    plan = getattr(generator, 'plan', None) or {}
    planned_chapters = plan.get('chapters', [])

    if planned_chapters:
        for pc in planned_chapters:
            matched_keywords = generator._match_keywords(pc['title']) if hasattr(generator, '_match_keywords') else []
            chapters_to_render.append({
                'title': pc['title'],
                'keywords': matched_keywords,
                'plan_info': pc,
            })
    else:
        for ch in generator.chapters:
            chapters_to_render.append({
                'title': ch['title'],
                'keywords': ch.get('keywords', []),
                'plan_info': None,
            })

    return chapters_to_render
