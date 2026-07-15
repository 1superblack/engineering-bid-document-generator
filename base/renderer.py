"""
富内容章节引擎 v7.1 — 数据驱动的章节正文生成器（对标 WPS AI / 喜鹊标书 AI 的"正文生成"能力）

设计目标：
    1. 用 scoring_strategy.json 的 must_have / bonus / common_omissions / structure_layers
       作为"评分专家知识库"，把每个要点展开成多段落、项目定制的专业正文，
       取代旧版"一句占位话 + 要点列表"的薄回退。
    2. 注入真实项目上下文（project_info）与企业知识库（company / 项目经理 / 类似业绩 /
       设备），让正文"对得上这个项目"，而不是放之四海皆准的套话。
    3. detail_level 控制篇幅（1 精简 ~ 5 极详），支撑 20~300 页目标。
    4. 兼容两种调用上下文：
         - 完整生成：generator 已加 h1(title)，本类只渲染 h2+（add_title=False）
         - 单章节：调用方未加标题，本类自身加 h1（add_title=True，默认）

可作为所有缺失章节类的统一兜底（ROUTES 解析失败时回退到本类），
亦可在接入 LLM 后作为"骨架/格式/数据注入层"，由大模型在富内容上二次扩写。
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple


# ────────────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────
# 富内容模板池：统一从 flavor_pools 引入（单一来源，避免多份副本导致轮转状态分裂）
# ────────────────────────────────────────────────────────────
from .utils import _rotate
from .flavor_pools import (
    _POOL_ROTATION,
    _DOMAIN_POOL, _CONNECTORS, _BIDTYPE_POOL, _KEYPOINT_POOL,
    _TECH10_POOL, _BIM_POOL, _GREEN_POOL, _DEFECT_POOL,
    _DEFECT_KEYWORDS, _DEFECT_DEFAULT, _SMART_POOL, _PROTECT_POOL,
    _MEASURE_POOL, _EMERGENCY_POOL, _CIVIL_POOL, _LABOR_POOL,
    _COORD_POOL, _SEASON_POOL, _RISK_POOL, _RISK_DEFAULT, _RISK_KEYWORDS,
    _AWARD_POOL, _AWARD_TARGET, _STD_ROUTES, _STD_DEFAULTS, _TOPIC_TAGS,
)


class RichChapter:
    """数据驱动的富内容章节生成器。"""

    def __init__(self, formatter, randomizer=None, user_context=None,
                 detail_level: int = 3, parse_result: Optional[Dict[str, Any]] = None,
                 plan_info: Any = None, llm_client: Any = None,
                 differentiator: Any = None, image_library: Any = None):
        self.formatter = formatter
        self.randomizer = randomizer
        self.user_context = self._normalize_uc(user_context)
        self.detail_level = max(1, min(5, int(detail_level or 3)))
        self.parse_result = parse_result or {}
        self.plan_info = plan_info
        self.llm_client = llm_client  # 可选：LLM 扩写客户端（未配置则回退模板）
        self._strategy_cache: Optional[Dict[str, Any]] = None
        # v7.3: 防重差异化引擎（默认随机指纹 ⇒ 同项目每次生成内容不同）
        if differentiator is None:
            from bid_core.dedup import Differentiator
            differentiator = Differentiator(project_info=(plan_info or {}))
        self.differentiator = differentiator
        # v7.3: 企业图片库（配图）。未显式传入时从 user_context 派生
        if image_library is None:
            try:
                image_library = self.user_context.get_images()
            except Exception:
                image_library = None
        self.image_library = image_library or []
        self._inserted_images: List[str] = []

    # ────────────────────────────────────────────────────────────
    # 公共入口
    # ────────────────────────────────────────────────────────────
    def render(self, project_info: Dict[str, Any], add_title: bool = True) -> None:
        """渲染本章节内容到 formatter。

        Args:
            project_info: 项目信息字典
            add_title: True 时自行添加 h1 章节标题（单章节模式）；
                       False 时假设调用方已添加标题（完整生成模式）
        """
        project_info = project_info or {}
        title = project_info.get('current_chapter_title') or project_info.get('chapter_title') or \
                (self.plan_info or {}).get('title') or '本章内容'
        self._chapter_title = title  # v7.16: 供 tech10/season 注入按章节级相关性判定
        if add_title:
            self.formatter.h1(1, title)

        # v7.3: 企业图片库配图（暗标模式不插图）
        if not project_info.get('is_dark_bid'):
            self._maybe_insert_images(title)

        ctx = self._build_context(project_info)
        self._dark_bid = bool(project_info.get('is_dark_bid'))
        self._emitted_extra = set()  # v7.12/7.15/7.16: 量化/新技术/季节 逐章去重保证各出现至少一次
        # v7.11: 技术评分项逐条显式响应（直击 WPS/喜鹊"评分点逐条响应"卖点）
        self._emit_score_responses(title, ctx)
        entry = self._resolve_entry(title, ctx.get('bid_type', 'construction'))

        if not entry:
            self._render_generic(title, ctx)
            return

        # 1) 结构层 → 多级子标题 + 多段落
        layers = entry.get('structure_layers') or []
        if layers:
            for layer in layers:
                self._render_layer(layer, entry, ctx)
        else:
            # 无结构层时，以 must_have 作为子标题骨架
            self._render_must_have_as_sections(entry, ctx)

        # 2) 必须包含要点（detail>=3 展开为段落，否则列表）
        must_have = entry.get('must_have') or []
        if must_have:
            self._render_must_have(must_have, ctx)

        # 3) 加分项策划
        bonus = entry.get('bonus') or []
        if bonus and self.detail_level >= 2:
            self._render_bonus(bonus, ctx)

        # 4) 常见扣分规避
        omissions = entry.get('common_omissions') or []
        if omissions and self.detail_level >= 3:
            self._render_omissions(omissions, ctx)

    # ────────────────────────────────────────────────────────────
    # v7.11: 技术评分项逐条显式响应
    # ────────────────────────────────────────────────────────────
    def _relevant_score_items(self, title: str) -> List[Dict[str, Any]]:
        """从 parse_result.score_items 中筛出与本章节标题相关的技术评分项。

        采用"最长公共子串 ≥ 3 字"判定相关性，避免"施工/措施"等泛词导致跨章节误匹配。
        """
        items = (self.parse_result or {}).get('score_items') or []
        if not items:
            return []
        out = []
        for it in items:
            name = (it.get('name') or it.get('title') or '').strip()
            if not name:
                continue
            if len(self._longest_common_substr(title or '', name)) >= 3:
                out.append(it)
        return out

    @staticmethod
    def _longest_common_substr(a: str, b: str) -> str:
        """返回两字符串的最长公共连续子串（标题与评分项名称相关性判定用）。"""
        if not a or not b:
            return ''
        prev = [0] * (len(b) + 1)
        best = ''
        for i in range(1, len(a) + 1):
            cur = [0] * (len(b) + 1)
            for j in range(1, len(b) + 1):
                if a[i - 1] == b[j - 1]:
                    cur[j] = prev[j - 1] + 1
                    if cur[j] > len(best):
                        best = a[i - cur[j]:i]
            prev = cur
        return best

    def _emit_score_responses(self, title: str, ctx: Dict[str, Any]) -> None:
        """针对本章相关的技术评分项，逐条输出显式响应段，便于评标人对应得分点。"""
        items = self._relevant_score_items(title)
        if not items:
            return
        comp = '我司' if getattr(self, '_dark_bid', False) else ctx.get('company_name', '我司')
        seed = self._hash_mod('score|' + title, 100000)
        for i, it in enumerate(items[:3]):
            name = (it.get('name') or it.get('title') or '').strip()
            score = it.get('score') or it.get('weight') or 0
            rng = (seed + i * 37) % 100000
            ev = self._evidence_sentence(ctx, rng) if (rng % 2 == 0) else ''
            tail = ('；' + ev) if ev else ''
            sent = (f"针对「{name}」（{score}分）评分项，{comp}从组织保障、技术措施与资源配置三方面"
                    f"专项落实，明确控制标准与验收节点，确保该评分点应得尽得{tail}")
            self.formatter.body(sent)

    # ────────────────────────────────────────────────────────────
    # 结构层渲染
    # ────────────────────────────────────────────────────────────
    def _render_layer(self, layer: str, entry: Dict[str, Any], ctx: Dict[str, Any]) -> None:
        # 结构层可能是 "总计划 → 分阶段计划 → 关键线路 → 保障措施" 形式
        subs = [s.strip() for s in re.split(r'[→\-—]', layer) if s.strip()]
        if len(subs) <= 1:
            subs = [layer]
        self.formatter.h2(layer if len(subs) == 1 else subs[0])
        # 用子主题逐个展开段落
        topics = subs if len(subs) > 1 else [layer]
        n_para = self.detail_level
        for i, topic in enumerate(topics):
            if i > 0:
                self.formatter.h3(topic)
            self._emit_block(topic, [topic], ctx, layer + topic, min(n_para, 3))

    # ────────────────────────────────────────────────────────────
    # 要点渲染
    # ────────────────────────────────────────────────────────────
    def _render_must_have_as_sections(self, entry: Dict[str, Any], ctx: Dict[str, Any]) -> None:
        for item in (entry.get('must_have') or [])[:max(3, self.detail_level)]:
            self.formatter.h2(item)
            self._emit_block(item, [item], ctx, item, min(self.detail_level, 3))

    def _render_must_have(self, must_have: List[str], ctx: Dict[str, Any]) -> None:
        self.formatter.h2('必须包含要点及落实措施')
        if self.detail_level >= 3:
            for item in must_have:
                self.formatter.h3(item)
                self._emit_block(item, [item], ctx, 'mh' + item, 2)
        else:
            self.formatter.body_list([self._one_liner(it, ctx) for it in must_have])

    def _render_bonus(self, bonus: List[str], ctx: Dict[str, Any]) -> None:
        self.formatter.h2('加分项策划')
        items = bonus[:max(2, self.detail_level)]
        if self.detail_level >= 4:
            for it in items:
                self.formatter.h3(it)
                self._emit_block(it, [it], ctx, 'bn' + it, 2)
        else:
            for it in items:
                self.formatter.body_bold(f'• {it}')
                self._emit_block(it, [it], ctx, 'bn2' + it, 1)

    def _render_omissions(self, omissions: List[str], ctx: Dict[str, Any]) -> None:
        self.formatter.h2('常见扣分点规避')
        for it in omissions[:self.detail_level]:
            self.formatter.body_bold(f'⚠ {it}')
            self._emit_block('规避：' + it, ['规避：' + it], ctx, 'co' + it, 1)

    def _render_generic(self, title: str, ctx: Dict[str, Any]) -> None:
        """未匹配到评分策略条目时的通用但项目定制的渲染。"""
        self.formatter.h2('实施方案概述')
        self._emit_block(title, [title], ctx, 'gen' + title, min(self.detail_level + 1, 4))
        # 尝试从 parse_result 的 star/red_line 抽取针对性承诺
        star = self.parse_result.get('star_clauses') or []
        if star:
            self.formatter.h2('实质性要求响应')
            for s in star[:self.detail_level]:
                content = s.get('content') if isinstance(s, dict) else str(s)
                if content:
                    self.formatter.body_bold(f'【必须响应】{content}')
                    self._emit_block('响应' + content, ['响应' + content], ctx, 'st' + content, 1)

    # ────────────────────────────────────────────────────────────
    # 段落生成核心（模板 + 数据注入）
    # ────────────────────────────────────────────────────────────
    def _emit_paragraphs(self, topic: str, ctx: Dict[str, Any], count: int, seed: str) -> None:
        for i in range(count):
            self.formatter.body(self._paragraph(topic, ctx, seed + str(i), i))

    def _emit_block(self, block_title: str, bullets: List[str], ctx: Dict[str, Any],
                    fallback_seed: str, fallback_count: int) -> None:
        """LLM 优先、模板回退的单内容块渲染。

        若已配置且启用了 llm_client，调用其 expand_section 获取大模型扩写正文；
        成功则按段落输出，失败/未配置则回退到模板 _emit_paragraphs。
        所有输出段落经 differentiator 做措辞差异化旋转并收集进原创性自查。
        """
        llm_text: Optional[str] = None
        if self.llm_client is not None:
            try:
                llm_text = self.llm_client.expand_section(
                    block_title, bullets or [], ctx, self.parse_result)
            except Exception:
                llm_text = None
        if llm_text:
            paras = [p.strip() for p in re.split(r'\n\s*\n', llm_text) if p.strip()]
        else:
            paras = self._paragraphs_text(block_title, ctx, fallback_count, fallback_seed)
        for para in paras:
            rotated = self.differentiator.rotate(para)
            self.differentiator.add_sentence(rotated)
            self.formatter.body(rotated)

    def _paragraphs_text(self, topic: str, ctx: Dict[str, Any], count: int, seed: str) -> List[str]:
        """模板段落纯文本列表（供 _emit_block 统一旋转/收集）。"""
        return [self._paragraph(topic, ctx, seed + str(i), i) for i in range(count)]

    def _paragraph(self, topic: str, ctx: Dict[str, Any], seed: str, idx: int) -> str:
        """生成一段与主题相关、且注入项目/企业数据的专业正文。"""
        rng = self._hash_mod(seed, 100000)
        proj = ctx.get('proj_brief', '本工程')
        comp = ctx.get('company_name', '我司')
        pm = ctx.get('pm_name') or '项目经理'
        pm_cert = ctx.get('pm_cert') or '一级建造师'
        dur = ctx.get('duration') or '合同工期'
        area = ctx.get('area')
        divs = ctx.get('divisions') or []
        similar = ctx.get('similar_top') or ''
        quals = ctx.get('quals_top') or ''
        div_txt = '、'.join(divs[:2]) if divs else '各施工'

        openers = [
            f'针对「{topic}」，{comp}结合{proj}的特点，制定了系统化的实施方案，明确目标、责任与节点。',
            f'关于「{topic}」，我司将其作为本项目的重点管控环节，确保全过程可控、可追溯、可核查。',
            f'在「{topic}」方面，{comp}依托类似工程经验与自有资源，建立了闭环管理机制并配套专项预案。',
            f'对于「{topic}」，我司将在{proj}全周期内统筹部署，实行清单化、节点化管理。',
            f'围绕「{topic}」的落实，{comp}坚持"策划先行、样板引路、过程严控"的工作思路。',
            f'就「{topic}」而言，{comp}将其纳入项目全生命周期管理，前置策划、过程留痕、闭环验证。',
            f'在「{topic}」的执行上，{comp}贯彻"标准化、精细化、信息化"的管理原则，确保实施有据可依。',
            f'针对「{topic}」，我司以{proj}的实际工况为出发点，配置专职管理与作业力量。',
        ]
        bodies = [
            f'由{pm}（{pm_cert}）牵头组织专项小组，将相关要求分解到{div_txt}等环节，'
            f'并纳入项目总体进度与质量管理体系统一管控。',
            f'我司具备{quals}等资质条件，并已在{similar}等类似项目中验证本项措施的可行性与有效性，'
            f'可确保在{dur}内稳定落地。',
            f'实施中采用"方案编制—技术交底—过程检查—偏差纠偏"的递进式管控，关键节点设置量化验收标准，'
            f'全过程留存影像与书面记录以备核查。',
            f'我司将与监理、业主建立定期沟通与联合检查机制，对「{topic}」的执行偏差做到早发现、早预警、早处置。',
            f'同时将该项工作纳入智慧化工地管理平台，实现进度、质量、安全数据的实时采集与动态调度。',
            f'针对重点部位与关键工序编制专项作业指导书，组织交底与培训，确保一线作业人员掌握控制要点。',
            f'结合{proj}特点，我司编制专项实施方案，明确工艺流程、控制标准与应急预案，并组织全员技术交底。',
            f'在施工组织上实行"平面分区、立体交叉、专业流水"的作业组织，提升资源利用效率并削减窝工。',
            f'我司建立周例会、月总结与专项协调会制度，对「{topic}」的进展与风险实行滚动跟踪与动态纠偏。',
            f'围绕本项工作建立责任矩阵与考核机制，将目标分解到岗、压力传导到人，确保闭环落地。',
        ]
        closers = [
            f'上述安排已纳入我司投标承诺，中标后将形成专项实施方案报审，确保「{topic}」在{proj}中高标准落实。',
            f'综上，我司有信心通过精细化组织，将「{topic}」的执行风险降至最低，保障整体工期与质量目标。',
            f'该措施与项目总体部署协同推进，可为「{topic}」提供稳定、可靠的实施保障。',
            f'该机制已在{comp}多个在施项目中稳定运行，可为「{topic}」在本项目的高标准履约提供保障。',
            f'通过上述系统化安排，我司有信心将「{topic}」的建设标准与交付品质控制在预期目标之内。',
        ]
        opener = openers[rng % len(openers)]
        body = bodies[(rng // 13) % len(bodies)]
        closer = closers[(rng // 29) % len(closers)]
        domain = self._domain_sentence(topic, rng)
        keypoint = ''
        if any(k in topic for k in ('重点', '难点', '关键', '控制要点')) and idx >= 1:
            keypoint = self._keypoint_sentence(ctx, rng)
        ev = ''
        if idx >= 1 and (rng // 5) % 2 == 0:
            ev = self._evidence_sentence(ctx, rng)
        area_txt = ''
        if area and idx == 0 and rng % 3 == 0:
            area_txt = f'本项目建筑面积约{area}㎡，'

        if idx == 0:
            return f'{area_txt}{opener}{body}'
        connector = _CONNECTORS[(rng // 7 + idx) % len(_CONNECTORS)]
        craft = self._craft_sentence(ctx, rng)
        scope = f'{topic} {getattr(self, "_chapter_title", "")}'
        is_bim = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('BIM', '模型', '深化设计', '数字化交付', '碰撞检查',
                                 '管线综合', '4D', '机电深化', '智慧运维'))
        is_tech = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('技术', '工艺', '方案', '新技术', '创优', '重难点', '设计'))
        is_season = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('工期', '季节', '雨', '冬', '高温', '台风', '气象',
                                 '防汛', '防洪', '防暑', '防冻'))
        is_risk = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('安全', '危大', '专项', '风险', '防护',
                                 '基坑', '模板', '吊装', '塔吊', '脚手架', '拆除', '高处'))
        is_award = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('创优', '精品', '优质', '质量奖', '鲁班', '国优', '省优',
                                 '质量目标', '目标管理', '质量策划', '一次成优'))
        is_green = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('绿色施工', '双碳', '碳排放', '四节一环保', '节能减排',
                                 '扬尘治理', '绿色建造', '环境保护', '节能环保'))
        is_defect = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('质量通病', '通病防治', '防治', '渗漏', '开裂', '空鼓',
                                 '质量缺陷', '细部处理', '观感', '防开裂', '防渗漏', '防空鼓'))
        is_smart = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('智慧工地', '智慧建造', '数字化监管', '劳务实名制', '智能监控',
                                 '塔吊监测', '扬尘在线', '人员定位', '智慧运维'))
        is_protect = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('成品保护', '工程保护', '已完工程', '产品保护', '交工保护',
                                 '工程保修', '保修工作', '保修措施'))
        is_measure = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('测量', '试验', '检测', '见证取样', '复试', '计量',
                                 '检验计划', '材料检验'))
        is_emergency = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('应急', '预案', '应急救援', '突发事件', '消防', '防汛',
                                 '防灾', '事故处置', '抢险', '演练'))
        is_civil = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('安全文明', '文明施工', 'CI形象', '场容', '场貌', '围挡',
                                 '标化工地', '标准化', '工完场清', '材料码放', '临时设施',
                                 '七牌一图', '封闭管理'))
        is_labor = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('劳务', '劳动力', '农民工', '工资支付', '工资保障', '用工',
                                 '分账', '作业人员', '人力', '分包', '专业分包'))
        is_coord = (ctx.get('bid_type') != 'service') and any(
            k in scope for k in ('总承包管理', '协调管理', '界面管理', '穿插施工', '接口管理',
                                 '专业分包配合', '分包协调', '总包对分包', '对分包'))
        std = ''
        if idx >= 2 and (rng // 17) % 4 == 0:
            std = self._standard_sentence(topic, ctx, rng)
        # v7.12/7.15/7.16/7.17/7.18: 量化/新技术/季节/危大/创优 逐章去重保证各出现至少一次。
        # 首个可注入段落一次性补发"尚未出现的专属类型"(tech10/season/risk/award) + 量化基线(quant)，
        # 确保单块章节也能全覆盖，杜绝各专属类型与量化相互饿死。
        extra = ''
        if idx >= 1 and not std:
            if not hasattr(self, '_emitted_extra'):
                self._emitted_extra = set()
            specials = []
            # v7.22: BIM 专章用深度 BIM 句替换通用 tech10，避免"新技术+BIM"双堆过度注水
            if is_bim:
                specials.append('bim')
            elif is_smart:
                specials.append('smart')
            elif is_tech:
                specials.append('tech10')
            if is_season:
                specials.append('season')
            if is_risk:
                specials.append('risk')
            if is_award:
                specials.append('award')
            if is_green:
                specials.append('green')
            if is_defect:
                specials.append('defect')
            if is_smart:
                specials.append('smart')
            if is_protect:
                specials.append('protect')
            if is_measure:
                specials.append('measure')
            if is_emergency:
                specials.append('emergency')
            if is_civil:
                specials.append('civil')
            if is_labor:
                specials.append('labor')
            if is_coord:
                specials.append('coord')
            due = [t for t in specials if t not in self._emitted_extra]
            parts = []
            for t in due:
                if t == 'tech10':
                    parts.append(self._tech10_sentence(ctx, rng))
                elif t == 'bim':
                    parts.append(self._bim_sentence(ctx, rng))
                elif t == 'smart':
                    parts.append(self._smart_sentence(ctx, rng))
                elif t == 'season':
                    parts.append(self._season_sentence(ctx, rng))
                elif t == 'risk':
                    parts.append(self._risk_sentence(ctx, rng, topic))
                elif t == 'green':
                    parts.append(self._green_sentence(ctx, rng))
                elif t == 'defect':
                    parts.append(self._defect_sentence(ctx, rng, topic))
                elif t == 'protect':
                    parts.append(self._protect_sentence(ctx, rng))
                elif t == 'measure':
                    parts.append(self._measure_sentence(ctx, rng))
                elif t == 'emergency':
                    parts.append(self._emergency_sentence(ctx, rng))
                elif t == 'civil':
                    parts.append(self._civil_sentence(ctx, rng))
                elif t == 'labor':
                    parts.append(self._labor_sentence(ctx, rng))
                elif t == 'coord':
                    parts.append(self._coord_sentence(ctx, rng))
                else:
                    parts.append(self._award_sentence(ctx, rng))
                self._emitted_extra.add(t)
            # 量化基线独立于专属类型：即便本章无专属类型（如服务类），也必注入量化承诺
            if 'quant' not in self._emitted_extra:
                parts.append(self._quant_sentence(ctx, rng))
                self._emitted_extra.add('quant')
            extra = ''.join(parts)
        # v7.32: 默认 detail_level=2 时段落 idx 最大为 1，原 idx>=2 阈值使其永不触发，
        # 导致 tech10/季节/危大/创优/绿色/质量通病/智慧工地/成品保护/测量/应急/文明/劳务/量化
        # 等维度在成稿中形同虚设（仅模板巧合命中）。现下移至 idx>=1 并在 idx==1 段补发 flavor，
        # 使全部维度在成稿真实落位；同时收窄 season/risk 的过宽关键词(去除 施工/进度/方案/部署 等
        # 近乎全章命中的词)，避免非相关章节被误注季节/危大句。
        if idx == 1:
            return f'{connector}{body}{ev}{keypoint}{extra}'
        return f'{connector}{body}{domain}{craft}{ev}{closer}{keypoint}{std}{extra}'

    def _domain_sentence(self, topic: str, rng: int) -> str:
        """按主题关键词匹配领域专业句，增强行业可信度（无匹配返回空串）。"""
        if not topic:
            return ''
        for kw, sent in _DOMAIN_POOL.items():
            if kw in topic:
                return sent
        return ''

    def _evidence_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """按企业知识库注入真实业绩/资质/人员作为论据句（无则静默回退，绝不编造）。"""
        similar = ctx.get('similar_top') or ''
        quals = ctx.get('quals_top') or ''
        pm = ctx.get('pm_name') or ''
        pm_cert = ctx.get('pm_cert') or ''
        opts = []
        if similar:
            opts.append(f'我司在{similar}等同类项目中已落地同类工艺，相关质量与工期指标均满足验收标准，可为本项目提供可复用经验。')
        if quals:
            opts.append(f'依托{quals}等资质与自有资源，本项措施具备充分的合规基础与实施保障。')
        if pm:
            pc = f'（{pm_cert}）' if pm_cert else ''
            opts.append(f'由{pm}{pc}领衔的团队曾负责多项同类工程，关键工序一次验收合格率稳定可控。')
        if not opts:
            return ''
        return opts[rng % len(opts)]

    def _craft_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """按工程类型注入专属施工工艺句（无匹配回退房建综合池），让措施可落地、可辨识。"""
        bid_type = ctx.get('bid_type') or 'construction'
        text = ' '.join(str(x) for x in (
            ctx.get('work_content', ''), ctx.get('proj_brief', ''),
            ctx.get('divisions', ''), ctx.get('structure_type', '')))
        for kw, key in (('装饰', 'decor'), ('市政', 'municipal'), ('旧改', 'renovation'),
                        ('水利', 'water'), ('拆除', 'demolition'),
                        ('物业', 'service'), ('服务', 'service'), ('政府采购', 'service')):
            if kw in text:
                bid_type = key
                break
        pool = _BIDTYPE_POOL.get(bid_type) or _BIDTYPE_POOL['construction']
        return pool[rng % len(pool)]

    def _keypoint_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """按工程类型注入"重点难点+应对"专项句（供重难点章节使用），让分析有针对性。"""
        bid_type = ctx.get('bid_type') or 'construction'
        text = ' '.join(str(x) for x in (
            ctx.get('work_content', ''), ctx.get('proj_brief', ''),
            ctx.get('divisions', ''), ctx.get('structure_type', '')))
        for kw, key in (('装饰', 'decor'), ('市政', 'municipal'), ('旧改', 'renovation'),
                        ('水利', 'water'), ('拆除', 'demolition'),
                        ('物业', 'service'), ('服务', 'service'), ('政府采购', 'service')):
            if kw in text:
                bid_type = key
                break
        pool = _KEYPOINT_POOL.get(bid_type) or _KEYPOINT_POOL['construction']
        return pool[rng % len(pool)]

    def _one_liner(self, item: str, ctx: Dict[str, Any]) -> str:
        comp = ctx.get('company_name', '我司')
        return f'{comp}将严格落实「{item}」，并纳入专项管控清单全程跟踪。'

    def _standard_sentence(self, topic: str, ctx: Dict[str, Any], rng: int) -> str:
        """引用真实 GB 国标条文（直击竞品'套话不专业'软肋）。数据源 professional_database.QUALITY_STANDARDS。"""
        if not hasattr(self, '_std_cache'):
            try:
                from bid_technical.professional_database import ProfessionalDatabase
                self._std_cache = ProfessionalDatabase.QUALITY_STANDARDS or {}
            except Exception:
                self._std_cache = {}
        qs = self._std_cache
        if not qs:
            return ''
        bid_type = ctx.get('bid_type') or 'construction'
        chosen = None
        for kw, sids in _STD_ROUTES.items():
            if kw in topic:
                chosen = sids
                break
        if not chosen:
            chosen = _STD_DEFAULTS.get(bid_type) or _STD_DEFAULTS['construction']
        sid = chosen[rng % len(chosen)]
        meta = qs.get(sid)
        if not meta:
            return ''
        inds = meta.get('key_indicators') or []
        ind_names = '、'.join(i.get('indicator', '') for i in inds[:3] if i.get('indicator'))
        std_id = meta.get('standard_id') or sid
        full = meta.get('full_name', '')
        if ind_names:
            return (f'本项工作严格按《{std_id} {full}》执行，'
                    f'重点控制{ind_names}等指标，检验批主控项目全部合格、'
                    f'一般项目合格率不低于80%。')
        return (f'本项工作严格按《{std_id} {full}》执行，'
                f'检验批主控项目全部合格、一般项目合格率不低于80%。')

    def _quant_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """注入量化承诺句（工期节点达成率/一次验收合格率/拟投入资源），破竞品'量化不足'软肋。"""
        bid_type = ctx.get('bid_type') or 'construction'
        area = ctx.get('area')
        dur = ctx.get('duration')  # 'X天' 或 None
        # 服务类量化只与响应时效相关，工期/区段/设备指标不适用，固定返回 SLA 句，
        # 避免 rng 选中工期句而丢失"30分钟响应"这一服务类硬指标（v7.32 修复）。
        if bid_type == 'service':
            return '服务团队网格化驻点，工单接报30分钟内响应、一般问题4小时内闭环、重大诉求2小时到场。'
        opts = []
        if dur:
            opts.append(f'工期节点达成率承诺100%，并预留5%机动工期应对极端工况，确保{dur}总目标不突破。')
        if area:
            zones = max(2, area // 2000)
            opts.append(f'建筑面积约{area}㎡，按专业划分为{zones}个施工区段，实行平面分区分段流水作业。')
        if bid_type == 'construction':
            mgmt = max(8, area // 1500) if area else 12
            equip = max(10, area // 1000) if area else 20
            opts.append(f'拟投入管理人员{mgmt}人、主要施工设备{equip}台套，关键设备一用一备、动态调配。')
            opts.append('分部分项工程一次验收合格率目标≥95%，单位工程优良率目标≥80%，杜绝不合格品流入下道工序。')
        else:
            opts.append('关键工序实行样板引路、首件认可，样板覆盖率与交底覆盖率均达100%。')
        return opts[rng % len(opts)]

    def _tech10_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """注入建筑业10项新技术应用句（技术先进性，竞品模板极少具体提）。"""
        return _TECH10_POOL[(rng + _rotate('tech10', len(_TECH10_POOL))) % len(_TECH10_POOL)]

    def _bim_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """注入 BIM 全周期深度应用句（碰撞检查/4D模拟/工程量联动/数字化交付）。

        区别于竞品（WPS/钛投标）泛写"应用BIM技术"的噱头式表述，给出可落地的具体场景。
        仅在 BIM/模型/深化/数字化交付 相关章节触发，且替换通用 tech10 以免过度堆叠注水。
        """
        return _BIM_POOL[(rng + _rotate('bim', len(_BIM_POOL))) % len(_BIM_POOL)]

    def _green_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """注入绿色施工/双碳专项句（四节一环保 + 碳量化管理，带硬指标）。

        竞品(WPS/喜鹊)与市面模板多把"绿色施工"当标配话术泛写"节约资源保护环境"，
        仅顶尖竞争者做成可量化、可验证的低碳履约。本句把"绿色"从口号做成带节能率/节水率/
        建筑垃圾资源化率/碳排放强度等硬指标的低碳履约保障。跨章节轮转降重复率。
        """
        return _GREEN_POOL[(rng + _rotate('green', len(_GREEN_POOL))) % len(_GREEN_POOL)]

    def _defect_sentence(self, ctx: Dict[str, Any], rng: int, topic: str = '') -> str:
        """注入质量通病防治专项句（按缺陷类别给出节点做法+规范+量化标准）。

        竞品(喜鹊等)质量/通病章节多"内容空洞、套话占比高"，评委按"质量通病是否有针对性防治"
        打分（混凝土裂缝/卫生间渗漏/外墙空鼓/路面沉降须具体防治）。本句按 渗漏/开裂/空鼓/平整
        四类给可落地防治，区别于竞品泛写"加强质量管理"。未命中关键词则按工程类型兜底。
        """
        scope = f'{getattr(self, "_chapter_title", "")} {topic}'
        cat = None
        for kw, c in _DEFECT_KEYWORDS.items():
            if kw in scope:
                cat = c
                break
        if cat is None:
            bt = ctx.get('bid_type') or 'construction'
            cat = (_DEFECT_DEFAULT.get(bt) or _DEFECT_DEFAULT['construction'])[0]
        pool = _DEFECT_POOL[cat]
        return pool[(rng + _rotate('defect_' + cat, len(pool))) % len(pool)]

    def _smart_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """注入智慧工地/数字化监管专项句（实名制/AI监控/塔吊监测/扬尘在线/人员定位）。

        区别于 tech10 一句话提及"应用智慧工地技术"与 BIM 的数字化交付（设计/4D 维度），
        专注现场 IoT 监管的可落地场景。2026 多地已强制"智慧工地投入单列≥建安费2.1%，
        否则扣3.8-5.2分"，且竞品/模板空白具体运营细节，本句据此做出针对性响应。
        """
        return _SMART_POOL[(rng + _rotate('smart', len(_SMART_POOL))) % len(_SMART_POOL)]

    def _protect_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """注入成品保护/工程保修专项句（组织/运输存放/过程/施工后/保修，可落地）。

        多份招标评分表将"成品保护"列为独立评分项（许昌招标 5分、缺项即0分），评分明细要求
        组织机构/运输存放/过程/施工后保护每少一样扣分；竞品多空白或泛写。本句据此给出
        责任到岗、交接制度、易损件防护、交叉作业隔离、三检挂牌、全周期保修等可落地内容。
        """
        return _PROTECT_POOL[(rng + _rotate('protect', len(_PROTECT_POOL))) % len(_PROTECT_POOL)]

    def _measure_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """注入测量与试验检测专项句（控制网复核/见证取样/试验计划/实体检验/计量检定）。

        施工组织设计必有"工程测量"与"试验检验"章节，属合规刚性项（toutiao 评分拆解将其列为
        质量措施的强制评审内容）；竞品/模板多空白具体做法（控制网闭合复核、CMA试验室、
        见证取样100%、试块留置、计量检定），评委按"措施可实施性"打分。本句给出可落地控制手段。
        """
        return _MEASURE_POOL[(rng + _rotate('measure', len(_MEASURE_POOL))) % len(_MEASURE_POOL)]

    def _emergency_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """注入场景化、可量化的应急预案与演练句（组织/流程/物资/演练四维，带响应时限与专项预案）。

        区别于 v7.17 危大工程（事前预防危险作业）与 v7.16 季节工况（季节性施工保障），
        本句专注突发事件"响应就绪度"。竞品/模板应急预案多"网上抄一遍"——98%雷同、仅写
        "发生火灾立即启动预案组织疏散"（新华社 2026-07-08 专评批评"复制粘贴的防汛预案防不住风雨"，
        toutiao 高分秘籍指出真正好的预案需场景化：响应流程图+岗位分工+响应时限(到分钟)+物资清单+
        专项预案）。本句给出可落地、可核查的应急能力，跨章节轮转降重复率。
        """
        return _EMERGENCY_POOL[(rng + _rotate('emergency', len(_EMERGENCY_POOL))) % len(_EMERGENCY_POOL)]

    def _civil_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """注入安全文明施工 / CI 形象标准化句（封闭围挡/七牌一图/工完场清/材料码放/临时设施）。

        区别于 v7.17 控危大（事前防危险作业）、v7.23 绿双碳（节能减排）、v7.25 智工地（IoT）、
        v7.29 应急（响应就绪），本句专注**场容场貌标准化**这一可视化、评标常单列扣分的维度。
        竞品/模板安全文明施工章节多"加强安全文明施工管理"泛话；青岛评分表单列 6 分且明确
        "描述空洞得 1 分"、滨州文件细化文明施工子项（围挡/封闭管理/施工场地/物料堆放/办公宿舍/
        公示牌/生活设施）。本句给出可落地、可核查的标准化做法，跨章节轮转降重复率。
        """
        return _CIVIL_POOL[(rng + _rotate('civil', len(_CIVIL_POOL))) % len(_CIVIL_POOL)]

    def _labor_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """注入劳务管理 / 农民工工资支付保障句（专用账户/分账/总包代发/保证金/维权公示牌）。

        法律依据《保障农民工工资支付条例》及山西/贵州/红河州办法强制：专用账户、人工费用分账
        （房建≥20%/交通≥10%/市政等≥15%）、总包代发、工资保证金、维权信息告示牌、劳资专管员；
        铜鼓县招标文件(2026-01)把整套"农民工工资保障条款"写进评分答疑。区别于 v7.25 智慧工地
        （仅覆盖 实名制人脸识别闸机 的 IoT 监管），本句专注"工资支付合规"这一法定刚性项。
        竞品/模板劳务章节多"加强劳务管理"泛话，空白 专户/分账/代发/保证金/公示牌 等法定要求。
        """
        return _LABOR_POOL[(rng + _rotate('labor', len(_LABOR_POOL))) % len(_LABOR_POOL)]

    def _coord_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """注入总承包对专业分包的协调管理句（接口清单表/工序交接单/三级计划/例会/预警纠偏）。

        招标文件评审因素(西安工程总承包导则/湖南计分表)明确列"对分包工程的配合、协调、管理、服务方案"
        与"总承包管理方案(8-10分)"；高分逻辑要求"工程接口管理专章+接口清单表"。本句给出可落地机制：
        接口清单表/工序交接单/三级进度计划/每日生产例会/进度预警纠偏/样板引路三检制，破竞品泛写。
        """
        return _COORD_POOL[(rng + _rotate('coord', len(_COORD_POOL))) % len(_COORD_POOL)]

    def _season_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """注入季节性/特殊工况施工保障句（雨期/冬施/高温/台风，常考却被模板略过）。"""
        return _SEASON_POOL[(rng + _rotate('season', len(_SEASON_POOL))) % len(_SEASON_POOL)]

    def _risk_sentence(self, ctx: Dict[str, Any], rng: int, topic: str = '') -> str:
        """注入危大工程（危险性较大的分部分项工程）专项管控句。

        按章节标题/主题命中具体 hazard（深基坑/高支模/起重吊装/脚手架/拆除/高处有限空间），
        未命中则按工程类型兜底（construction→深基坑+高支模 等），给出"专项方案+专家论证+具体管控"，
        对标竞品"仅泛写编制专项方案"的空洞表述。
        """
        scope = f'{getattr(self, "_chapter_title", "")} {topic}'
        hazard = None
        for kw, h in _RISK_KEYWORDS.items():
            if kw in scope:
                hazard = h
                break
        if not hazard:
            bid_type = ctx.get('bid_type') or 'construction'
            defaults = _RISK_DEFAULT.get(bid_type) or _RISK_DEFAULT['construction']
            hazard = defaults[rng % len(defaults)]
        pool = _RISK_POOL.get(hazard) or _RISK_POOL['深基坑']
        return pool[(rng + _rotate('risk_' + hazard, len(pool))) % len(pool)]

    def _award_sentence(self, ctx: Dict[str, Any], rng: int) -> str:
        """注入创优目标与质量奖项策划句（按工程类型给出贴合的奖项目标，破竞品"仅泛写确保合格"）。"""
        bid_type = ctx.get('bid_type') or 'construction'
        target = _AWARD_TARGET.get(bid_type) or _AWARD_TARGET['construction']
        base = _AWARD_POOL[(rng + _rotate('award', len(_AWARD_POOL))) % len(_AWARD_POOL)]
        # v7.32: 原 base.replace(占位串, target) 因池中无该占位串而永不命中(_AWARD_TARGET 形同虚设)。
        # 改为池中统一 {target} 占位 + format 注入，使房建类真实落位"鲁班奖/国家优质工程"等具体奖项。
        return base.format(target=target)

    # ────────────────────────────────────────────────────────────
    # v7.3: 企业图片库配图
    # ────────────────────────────────────────────────────────────
    def _maybe_insert_images(self, title: str) -> None:
        """按主题相关性从企业图库为本章选 1 张最匹配图插入（破竞品"图文准确度低"）。"""
        img = self._choose_best_image(title)
        if not img:
            return
        try:
            self.formatter.image(img['path'], caption=img.get('desc') or img.get('name') or None, width_cm=14)
            self._inserted_images.append(img['path'])
        except Exception:
            pass

    def _choose_best_image(self, title: str) -> Optional[Dict[str, Any]]:
        """返回与章节标题主题相关性最高的图片（score>=1），无则 None。"""
        if not self.image_library:
            return None
        best = None
        best_score = 0
        for img in self.image_library:
            path = img.get('path') or ''
            if not path:
                continue
            text = ' '.join([
                str(img.get('desc') or ''),
                str(img.get('name') or ''),
                ' '.join(img.get('tags') or []) if isinstance(img.get('tags'), list) else str(img.get('tags') or ''),
                str(img.get('category') or ''),
            ])
            s = self._image_relevance(title, text)
            if s > best_score:
                best_score = s
                best = img
        return best if best_score >= 1 else None

    def _image_relevance(self, title: str, text: str) -> int:
        """章节标题与图片文本（desc/name/tags/category）的主题相关性打分。"""
        title_l = (title or '').lower()
        text_l = (text or '').lower()
        score = 0
        # 直接包含：图片文本前 6 字出现于标题，或标题前 6 字出现于图片文本
        if text_l[:6] and text_l[:6] in title_l:
            score += 2
        if title_l[:6] and title_l[:6] in text_l:
            score += 2
        # 关键词命中（图片文本中的 2+ 字片段出现在标题）
        for kw in re.split(r'[\s，,、；;：:。/_\-—（）()]+', text):
            if len(kw) >= 2 and kw in title:
                score += 1
        # 主题标签命中：标题含主题词则匹配带该标签的图（强信号）
        for topic, tags in _TOPIC_TAGS.items():
            if topic in title:
                for tg in tags:
                    if tg and tg in text_l:
                        score += 2
        return score

    def get_generation_report(self) -> Dict[str, Any]:
        """供生成器聚合「内容原创性 + 配图」自查报告。"""
        # 兼容 Differentiator 的私有 _sentences 与可能的公开 sentences 属性
        _sent = getattr(self.differentiator, 'sentences',
                        getattr(self.differentiator, '_sentences', []))
        return {
            'fingerprint': self.differentiator.fingerprint,
            'sentence_count': len(_sent),
            'self_similarity': round(self.differentiator.self_similarity(), 4),
            'inserted_images': list(self._inserted_images),
            'sentences': list(_sent),
        }

    # ────────────────────────────────────────────────────────────
    # 上下文构建
    # ────────────────────────────────────────────────────────────
    def _build_context(self, project_info: Dict[str, Any]) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {}
        ctx['bid_type'] = project_info.get('bid_type', 'construction')
        name = project_info.get('name') or (self.plan_info or {}).get('name') or '本工程'
        area = project_info.get('area')
        dur = project_info.get('duration')
        struct = project_info.get('structure_type') or project_info.get('structureType')
        divs = project_info.get('divisions') or []
        work = project_info.get('work_content') or ''
        brief = f'{area}㎡的{struct or "工程"}' if area else (struct or name)
        if work:
            brief += f'（{work}）'
        ctx['proj_brief'] = brief
        ctx['duration'] = f'{dur}天' if dur else None
        ctx['area'] = area
        ctx['divisions'] = divs if isinstance(divs, list) else [divs]

        # 企业知识库
        uc = self.user_context
        if uc is not None:
            try:
                comp = uc.get_company() or {}
                ctx['company_name'] = comp.get('name') or '我司'
                quals = comp.get('qualifications') or []
                ctx['quals_top'] = '、'.join(quals[:3]) if quals else ''
                pm = uc.get_project_manager() or {}
                ctx['pm_name'] = pm.get('name')
                ctx['pm_cert'] = pm.get('cert')
                sims = uc.get_similar_projects() or []
                ctx['similar_top'] = sims[0].get('name') if sims else ''
            except Exception:
                pass
        if not ctx.get('company_name'):
            ctx['company_name'] = '我司'
        return ctx

    # ────────────────────────────────────────────────────────────
    # 评分策略条目解析
    # ────────────────────────────────────────────────────────────
    def _resolve_entry(self, title: str, bid_type: str) -> Optional[Dict[str, Any]]:
        try:
            from bid_core.data_loader import DataLoader
            strategy = (self._strategy_cache
                        or DataLoader().load_scoring_strategy())
            self._strategy_cache = strategy
        except Exception:
            return None
        db_key = f"{bid_type}_strategy_db"
        db = strategy.get(db_key, {})
        # 1) 标题精确匹配
        if title in db:
            return db[title]
        # 2) chapter_match_keywords 反查
        keywords_map = strategy.get('chapter_match_keywords', {})
        for t, kws in keywords_map.items():
            if t in db and any(kw in title for kw in (kws or [])):
                return db[t]
        # 3) 标题包含 db 键
        for t in db:
            if t and t in title:
                return db[t]
        return None

    # ────────────────────────────────────────────────────────────
    # 工具
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def _normalize_uc(uc) -> Any:
        if uc is None:
            return None
        try:
            from bid_core.user_context import UserContext
            if isinstance(uc, UserContext):
                return uc
            if isinstance(uc, dict):
                return UserContext(uc)
        except Exception:
            pass
        return uc

    @staticmethod
    def _hash_mod(s: str, mod: int) -> int:
        h = hashlib.md5((s or '').encode('utf-8')).digest()
        return int.from_bytes(h[:4], 'big') % mod


def cpm_or(x):
    return x or '项目'


def resolve_chapter_class(path: str):
    """尝试按路径导入真实章节类；若该类缺失（历史遗留的 31 个章节类未实现），
    统一回退到 RichChapter 富内容引擎，保证任意章节都能产出项目定制的充实正文。"""
    try:
        parts = path.rsplit('.', 1)
        module = __import__(parts[0], fromlist=[parts[1]])
        return getattr(module, parts[1])
    except Exception:
        return RichChapter

