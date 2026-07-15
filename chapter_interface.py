"""
ChapterInterface - 章节接口定义 v4.1
v4.1:
- 新增 render_professional_content() 根据章节名自动渲染专业数据库内容（工法/通病/设备/安全）
- 增强 render_score_item_content() 支持plan_info中的content_strategy指导内容生成方向
- 导入ProfessionalDatabase，提供章节级专业内容渲染能力
v3.0:
- 新增 get_disqualify_clauses() 获取相关废标条款
- 新增 render_disqualify_response() 通用废标条款响应
- 增强 render_score_aligned() 输出包含子项
v4.0:
- 新增 render_extended_content() 自动补充扩展内容（质量/安全/文明施工/环保/资源保障）
- 新增 render_professional_standards() 自动生成国标/行标引用表
- 新增 render_inspection_checklist() 自动生成检查验收清单表
- 新增 render_responsibility_table() 自动生成岗位职责分工表
- render() 末尾增加自动内容填充逻辑（is_full + target_pages 条件触发）
"""
from abc import ABC, abstractmethod

# v8.0: 兼容扁平化结构与正式 bid_technical 包两种部署环境
try:
    from bid_technical.professional_database import ProfessionalDatabase
except ImportError:
    from professional_database import ProfessionalDatabase

# v8.0: 静态数据已拆分至 standards_db.py
from standards_db import _STANDARDS_DB, _CHECKLIST_DB, _RESPONSIBILITY_DB

class ChapterInterface(ABC):
    """章节接口——所有标书章节都实现这个"""

    def __init__(self, formatter, randomizer=None, user_context=None,
                 detail_level=2, parse_result=None, plan_info=None):
        self.fmt = formatter              # 格式化引擎
        self.rand = randomizer            # 随机化引擎
        self.ctx = user_context or {}     # 用户信息
        self.detail_level = detail_level  # 内容深度等级 1/2/3
        self.parse_result = parse_result  # 招标文件解析结果
        self.plan_info = plan_info or {}  # 评分项规划信息

    @abstractmethod
    def render(self, project_info):
        """渲染章节内容——唯一必须实现的方法
        
        子类实现时应在末尾调用 self._auto_fill_if_needed(project_info)
        以支持自动内容填充
        """
        raise NotImplementedError

    def pre_render(self, project_info):
        """渲染前钩子"""
        pass

    def post_render(self, project_info):
        """渲染后钩子"""
        pass

    def get_title(self):
        """获取章节标题"""
        return self.__class__.__name__

    def get_target_pages(self):
        """获取评分项规划中的目标页数"""
        return self.plan_info.get('target_pages', 0)

    def get_chapter_score_items(self, keyword=None):
        """
        从parse_result获取与keyword匹配的评分项

        Args:
            keyword: 过滤关键词，为None则获取所有评分项

        Returns:
            匹配的评分项列表
        """
        if not self.parse_result:
            return []
        items = self.parse_result.get('score_items', [])
        if keyword is None:
            return items
        return [i for i in items if keyword in (i.get('name', '') + i.get('title', ''))]

    def render_score_item_content(self, item, project_info):
        """
        以评分项为主轴渲染章节内容

        v4.1增强: 如果plan_info中有content_strategy信息，用它来指导内容生成方向

        Args:
            item: 单个评分项字典，包含 name/title, score, sub_items 等
            project_info: 项目信息字典

        Returns:
            生成的评分项数量（子项数量）
        """
        name = item.get('name') or item.get('title', '')
        score = item.get('score', 0)
        sub_items = item.get('sub_items', item.get('includes', []))
        project_name = self.pn(project_info)

        # v4.1: 从plan_info获取content_strategy
        strategy_info = None
        if self.plan_info:
            cs = self.plan_info.get('content_strategy', {})
            if cs:
                strategy_info = cs

        # h2: 评分项名称（XX分）
        if name:
            self.fmt.h2(f"{name}（{score}分）")

        # v4.1: 如果有content_strategy，先输出必须包含要素和结构指引
        if strategy_info:
            must_have = strategy_info.get('must_have', [])
            bonus = strategy_info.get('bonus', [])
            common_omissions = strategy_info.get('common_omissions', [])
            structure_template = strategy_info.get('structure_template', '')

            if must_have and self.is_standard():
                self.fmt.h3("核心响应要素")
                for i, mh in enumerate(must_have, 1):
                    self.fmt.body(f"{i}、{mh}：我方将严格落实该项要求，确保在本工程中充分体现。")

            if bonus and self.is_full():
                self.fmt.h3("加分项响应")
                for i, bn in enumerate(bonus, 1):
                    self.fmt.body(f"{i}、{bn}：我方将积极落实该项加分内容，提升标书竞争力。")

            if common_omissions and self.is_full():
                self.fmt.h3("常见遗漏防范")
                self.fmt.body("针对本评分项，我方特别关注以下常见遗漏问题，确保逐一落实：")
                for i, om in enumerate(common_omissions, 1):
                    self.fmt.body(f"{i}、{om}")

            if structure_template and self.is_standard():
                self.fmt.body(f"本评分项内容按「{structure_template}」组织，确保结构完整、层次清晰。")

        count = 0
        # 对每个sub_item: h3 + body承诺 + body措施概述
        if sub_items:
            for si in sub_items:
                if isinstance(si, str):
                    si_name = si
                elif isinstance(si, dict):
                    si_name = si.get('content', si.get('name', ''))
                else:
                    continue

                if not si_name or len(si_name) < 2:
                    continue

                self.fmt.h3(si_name)
                self.fmt.body(
                    f"针对{project_name}「{name}」评分项中的「{si_name}」，"
                    f"我方郑重承诺：严格按照招标文件要求，"
                    f"全面落实相关标准和规范，确保该项得满分。"
                )
                self.fmt.body(
                    f"我方将采取以下措施保障「{si_name}」的落实："
                    f"建立健全管理制度，明确责任分工，"
                    f"加强过程管控与监督检查，"
                    f"确保各项工作有序推进、按期达标。"
                )
                count += 1

        # 如果没有子项，至少输出总体承诺
        if count == 0 and name:
            self.fmt.body(
                f"针对评分项「{name}（{score}分）」，"
                f"我方将严格按照招标文件要求，"
                f"制定详细的实施方案和保障措施，确保该项得满分。"
            )
            count = 1

        return count

    # ── 便捷方法 ──────────────────────────────────────────
    def p(self, project_info, key, default=''):
        """安全获取项目信息"""
        return project_info.get(key, default)

    def pn(self, project_info):
        """快捷获取项目名称"""
        return project_info.get('name', '本项目')

    def pd(self, project_info):
        """快捷获取工期"""
        return project_info.get('duration', 90)

    def pa(self, project_info):
        """快捷获取面积"""
        return project_info.get('area', '—')

    def is_full(self):
        """是否完整模式"""
        return self.detail_level >= 3

    def is_standard(self):
        """是否标准模式"""
        return self.detail_level >= 2

    def get_score_items(self, keyword=None):
        """获取与本章相关的评分项"""
        if not self.parse_result:
            return []
        items = self.parse_result.get('score_items', [])
        if keyword:
            return [i for i in items if keyword in (i.get('name', '') + i.get('title', ''))]
        return items

    def get_disqualify_clauses(self, keyword=None):
        """
        获取与本章相关的废标条款 - v3.0 新增
        
        Args:
            keyword: 过滤关键词，为空则返回所有
        
        Returns:
            相关废标条款列表
        """
        if not self.parse_result:
            return []
        
        clauses = []
        
        # 红线条款
        red_lines = self.parse_result.get('red_line_clauses', [])
        for r in red_lines:
            content = r.get('content', '')
            if keyword:
                if keyword in content:
                    clauses.append(content)
            else:
                clauses.append(content)
        
        # 普通废标条款
        disq_clauses = self.parse_result.get('disqualify_clauses', [])
        for c in disq_clauses:
            if isinstance(c, str):
                if not keyword or keyword in c:
                    clauses.append(c)
            elif isinstance(c, dict):
                content = c.get('content', c.get('clause', ''))
                if content and (not keyword or keyword in content):
                    clauses.append(content)
        
        return clauses[:10]  # 限制数量

    def render_score_aligned(self, project_info, keyword=None):
        """
        评分项对齐渲染 v3.0 - 增强版
        如果parse_result有评分项，按评分项展开二级标题
        同时输出"包含但不限于"子项作为三级标题
        """
        items = self.get_score_items(keyword)
        if not items:
            return False
        
        for item in items:
            name = item.get('name') or item.get('title', '')
            score = item.get('score', 0)
            sub_items = item.get('sub_items', item.get('includes', []))
            
            if name:
                self.fmt.h2(f"{name}（{score}分）")
            
            # v3.0: 输出评分项子项作为h3
            if sub_items and self.is_standard():
                for si in sub_items:
                    if isinstance(si, str):
                        if len(si) >= 4:  # 太短的不作为标题
                            self.fmt.h3(si)
                    elif isinstance(si, dict):
                        content = si.get('content', si.get('name', ''))
                        if content and len(content) >= 4:
                            self.fmt.h3(content)
            
            # 如果没有子项但评分较高，生成通用内容
            if not sub_items and score >= 5 and self.is_standard():
                self.fmt.body(f"针对评分项「{name}」，我方将严格按照招标文件要求，制定详细的实施方案和保障措施，确保该项得满分。")
        
        return True

    def render_disqualify_response(self, keyword=None, section_index=None):
        """
        废标条款响应渲染 - v3.0 新增
        
        在章节末尾自动生成相关废标条款的响应声明
        
        Args:
            keyword: 过滤关键词（只响应与本章主题相关的条款）
            section_index: 章节序号（用于标题编号）
        """
        clauses = self.get_disqualify_clauses(keyword)
        if not clauses:
            return
        
        # 生成标题
        if section_index:
            cn_nums = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
            idx = cn_nums[section_index] if section_index <= 10 else str(section_index)
            self.fmt.h2(f"（{idx}）废标条款响应")
        else:
            self.fmt.h2("废标条款响应")
        
        for clause in clauses:
            # 生成响应文本
            response = self._generate_clause_response(clause)
            self.fmt.body(response)
    
    def _generate_clause_response(self, clause):
        """
        生成废标条款响应文本
        
        根据条款内容自动生成专业的响应声明
        """
        # 基础响应模板
        templates = {
            '安全': '我方严格遵守安全生产法律法规，{clause}已在安全施工专项方案中充分体现并落实，'
                    '确保施工全过程安全生产合法合规。',
            '质量': '我方承诺工程质量目标满足招标文件要求，{clause}已在质量保证方案中充分体现并落实，'
                    '确保施工质量满足设计要求和规范规定。',
            '工期': '我方承诺在招标文件规定的工期内完成全部施工任务，{clause}已在进度保障方案中充分体现并落实。',
            '资质': '我方具有履行合同所需的资质条件和能力，{clause}相关资质文件随投标文件递交。',
            '人员': '我方承诺按照投标文件中的人员配置计划组织施工队伍，{clause}相关人员资格证书随投标文件递交。',
            '设备': '我方承诺按照投标文件中的设备配置计划投入施工机械设备，{clause}相关设备清单详见附表。',
            '报价': '我方投标报价合理、完整、准确，{clause}已在投标函中明确响应。',
            '业绩': '我方具有履行本合同所需的类似工程业绩，{clause}相关业绩证明材料随投标文件递交。',
        }
        
        # 匹配模板
        clause_short = clause[:50]
        for keyword, template in templates.items():
            if keyword in clause:
                return template.format(clause=clause_short)
        
        # 默认响应
        return f'我方严格响应：{clause_short}，已在相关方案中充分体现并落实。'

    # ══════════════════════════════════════════════════════
    # v4.0 新增方法 — 自动内容填充与扩展
    # ══════════════════════════════════════════════════════

    def render_extended_content(self, project_info, keyword):
        """
        自动补充扩展内容 — 当章节内容不足target_pages时调用
        
        按顺序输出五大承诺模块：
        a. 质量保证承诺段（3-5段）
        b. 安全保证承诺段（3-5段）
        c. 文明施工承诺段（2-3段）
        d. 环保承诺段（2-3段）
        e. 资源保障承诺段（2-3段）
        
        Args:
            project_info: 项目信息字典
            keyword: 章节主题关键词，用于个性化内容
        """
        pn = self.pn(project_info)
        
        # a. 质量保证承诺段（3-5段）
        self.fmt.h2("质量保证承诺")
        quality_paragraphs = [
            f"我方郑重承诺：{pn}工程质量达到国家现行施工质量验收规范合格标准，"
            f"确保单位工程一次验收合格率达到100%，"
            f"工程质量目标满足招标文件的各项要求。"
            f"我方将严格按照ISO 9001质量管理体系和GB/T 50430工程建设施工企业质量管理规范的要求，"
            f"建立完善的项目质量管理体系，明确各级质量管理职责，"
            f"确保质量管理体系有效运行。",

            f"我方承诺建立健全质量管理制度，包括但不限于：原材料进场检验制度、"
            f"施工过程质量检查制度、隐蔽工程验收制度、技术交底制度、"
            f"工序交接检查制度、质量例会制度等。"
            f"严格执行「三检制」（自检、互检、专检），确保每道工序质量合格后方可进入下道工序施工。"
            f"对关键工序和特殊过程实行重点监控，设立质量控制点，实施旁站监理。",

            f"我方承诺加强原材料和半成品的质量控制，所有进场材料必须有合格证、质量证明文件，"
            f"并按规定进行复试检验，未经检验或检验不合格的材料严禁使用。"
            f"建立材料追溯制度，确保工程所用材料可追溯来源和检验状态。"
            f"对涉及结构安全的试块、试件及有关材料，实行见证取样和送检。",

            f"我方承诺加强施工过程中的质量监控，采用先进的检测手段和方法，"
            f"对施工质量进行全过程、全方位监控。"
            f"定期组织质量检查和质量分析会议，及时发现和纠正质量问题。"
            f"对质量缺陷和质量事故严格按照「四不放过」原则进行处理，"
            f"即原因未查清不放过、责任人未处理不放过、整改措施未落实不放过、有关人员未受到教育不放过。",

            f"我方承诺建立完善的质量档案管理制度，施工过程中及时收集、整理、归档各类质量文件和记录，"
            f"确保质量资料的真实性、完整性和可追溯性。"
            f"工程竣工后，按规定编制完整的竣工资料，"
            f"确保竣工档案符合城市建设档案管理要求。"
            f"质量承诺期限：自工程竣工验收合格之日起，按国家规定和合同约定承担工程质量保修责任。",
        ]
        for para in quality_paragraphs:
            self.fmt.body(para)

        # b. 安全保证承诺段（3-5段）
        self.fmt.h2("安全保证承诺")
        safety_paragraphs = [
            f"我方郑重承诺：{pn}施工期间严格遵守《中华人民共和国安全生产法》《建设工程安全生产管理条例》"
            f"等法律法规，坚决贯彻「安全第一、预防为主、综合治理」的安全生产方针，"
            f"杜绝重大安全事故的发生，确保安全生产零事故目标。"
            f"我方将建立以项目经理为第一责任人的安全生产责任制，"
            f"层层签订安全生产责任书，明确各级人员的安全生产职责。",

            f"我方承诺建立健全安全管理体系和各项安全管理制度，"
            f"包括但不限于：安全生产责任制、安全教育培训制度、安全检查制度、"
            f"安全专项施工方案编制及专家论证制度、安全技术交底制度、"
            f"应急救援预案制度、安全隐患排查治理制度等。"
            f"确保安全投入到位，专款专用，为安全生产提供充足的物资和资金保障。"
            f"施工现场配备足够数量的专职安全管理人员，负责日常安全检查和监督工作。",

            f"我方承诺加强施工现场安全防护，严格执行JGJ 59《建筑施工安全检查标准》，"
            f"确保「三宝」（安全帽、安全带、安全网）的正确使用，"
            f"做好「四口」（楼梯口、电梯井口、预留洞口、通道口）和「五临边」（基坑周边、"
            f"尚未安装栏杆或栏板的阳台及料台与挑平台周边、雨篷与挑檐边、"
            f"无外脚手架的屋面与楼层周边、水箱与水塔周边）的安全防护。"
            f"对脚手架、模板支撑体系、深基坑、起重吊装等危险性较大的分部分项工程，"
            f"编制专项施工方案并按规定组织专家论证。",

            f"我方承诺加强施工用电安全管理，严格执行JGJ 46《施工现场临时用电安全技术规范》，"
            f"采用TN-S接零保护系统，做到「三级配电两级保护」，"
            f"实行「一机一闸一漏一箱」制度。"
            f"加强消防安全管理，按规定配备消防器材，设置消防通道，"
            f"建立动火审批制度，定期进行消防安全检查和消防演练。",

            f"我方承诺建立完善的应急救援体系，编制综合应急预案和专项应急预案，"
            f"定期组织应急演练，确保突发事件能够得到及时有效的处置。"
            f"建立安全事故报告和调查处理制度，一旦发生安全事故，"
            f"按规定及时上报，不得瞒报、谎报、迟报或漏报。"
            f"安全承诺期限：自进场施工之日起至工程竣工验收合格之日止。",
        ]
        for para in safety_paragraphs:
            self.fmt.body(para)

        # c. 文明施工承诺段（2-3段）
        self.fmt.h2("文明施工承诺")
        civilization_paragraphs = [
            f"我方郑重承诺：{pn}施工期间严格执行文明施工各项规定，"
            f"按照JGJ 146《建设工程施工现场环境与卫生标准》和当地文明施工管理办法的要求，"
            f"做好施工现场文明施工工作。"
            f"施工现场实行封闭管理，设置标准化围挡，围挡牢固、整洁、美观；"
            f"出入口设置冲洗设施，确保车辆不带泥上路；"
            f"施工现场主要道路、材料加工区等区域进行硬化处理；"
            f"材料堆放整齐有序，标识清晰；"
            f"生活区与施工区严格分隔，生活设施齐全、卫生整洁。",

            f"我方承诺做好施工现场的宣传和标识工作，"
            f"在施工现场醒目位置设置「五牌一图」（工程概况牌、管理人员名单及监督电话牌、"
            f"消防保卫牌、安全生产牌、文明施工牌和施工现场平面图），"
            f"施工区域设置安全警示标志和宣传标语。"
            f"加强施工现场的治安管理，建立门卫制度，实行来访登记。"
            f"合理安排施工时间，控制施工噪声，减少对周边居民的影响，"
            f"努力构建和谐施工环境，维护良好的社会形象。",

            f"我方承诺做好施工现场的卫生防疫工作，"
            f"设置符合卫生要求的食堂、宿舍、厕所等生活设施，"
            f"定期消毒，保持清洁卫生。"
            f"保障施工人员的合法权益，按时足额发放工资，"
            f"不拖欠农民工工资。"
            f"积极配合当地政府和社区的工作，妥善处理与周边居民的关系，"
            f"做到施工不扰民、便民、利民。",
        ]
        for para in civilization_paragraphs:
            self.fmt.body(para)

        # d. 环保承诺段（2-3段）
        self.fmt.h2("环保承诺")
        environment_paragraphs = [
            f"我方郑重承诺：{pn}施工期间严格遵守《中华人民共和国环境保护法》"
            f"《中华人民共和国大气污染防治法》"
            f"《中华人民共和国水污染防治法》《中华人民共和国固体废物污染环境防治法》"
            f"《中华人民共和国噪声污染防治法》等法律法规，"
            f"严格执行GB 12523《建筑施工场界环境噪声排放标准》等环保标准，"
            f"认真落实环境影响评价文件及审批意见中的各项环保措施。"
            f"坚持「预防为主、综合治理」的环保方针，最大限度减少施工对周边环境的影响。",

            f"我方承诺做好以下环保工作："
            f"（1）扬尘控制：施工现场采取洒水降尘、覆盖防尘、封闭运输等措施，"
            f"确保扬尘排放达标；土方开挖及运输过程中加强覆盖，减少扬尘污染。"
            f"（2）噪声控制：合理安排施工时间，避免夜间进行高噪声作业，"
            f"采用低噪声设备，设置隔声屏障，确保施工场界噪声达标。"
            f"（3）废水处理：施工现场设置沉淀池等污水处理设施，"
            f"施工废水经处理达标后方可排放，严禁未经处理直接排放。"
            f"（4）固废管理：建筑垃圾分类收集、分类处置，危险废物委托有资质的单位处理。",

            f"我方承诺建立环保自检自查制度，定期对施工现场的环境状况进行检查，"
            f"发现问题及时整改。"
            f"配置专职环保管理人员，负责环保措施的落实和监督。"
            f"施工完成后，及时恢复临时用地，做好生态修复工作，"
            f"确保施工区域的环境质量恢复到施工前水平或更好。"
            f"积极配合环保部门的监督检查，如实提供相关资料和信息。",
        ]
        for para in environment_paragraphs:
            self.fmt.body(para)

        # e. 资源保障承诺段（2-3段）
        self.fmt.h2("资源保障承诺")
        resource_paragraphs = [
            f"我方郑重承诺：{pn}施工期间将投入充足的资源，"
            f"确保工程顺利实施。"
            f"（1）人力资源保障：按照投标文件承诺的项目管理班子和施工队伍组织进场，"
            f"项目经理、技术负责人等关键岗位人员具备相应的执业资格和丰富的施工经验，"
            f"特殊工种人员持证上岗。根据施工进度需要，及时调配增补施工人员，"
            f"确保各阶段施工力量充足。"
            f"（2）物资保障：建立完善的物资采购和供应体系，"
            f"与主要材料供应商签订长期合作协议，确保材料供应及时、质量可靠。"
            f"设置合理的材料储备，防止因材料短缺影响施工进度。",

            f"（3）机械设备保障：按照施工方案配置足够的施工机械设备，"
            f"主要设备有备用方案，确保设备故障时能及时替换。"
            f"建立设备维护保养制度，定期检查维护，确保设备正常运行。"
            f"（4）资金保障：设立项目专项资金账户，专款专用，"
            f"确保工程款优先用于本项目的材料采购、人工费用支付等，"
            f"不挪用、不拖欠，保障施工正常运转。"
            f"（5）技术保障：配备经验丰富的技术团队，"
            f"及时解决施工中遇到的技术难题，积极应用新技术、新工艺、新材料、新设备，"
            f"提高施工效率和质量水平。",

            f"我方承诺在施工全过程中，根据工程进展需要，动态调整资源配置，"
            f"确保各阶段资源投入满足施工要求。"
            f"建立资源调配应急预案，当出现资源不足的情况时，"
            f"能在24小时内调配到位，不影响正常施工。"
            f"定期对资源投入情况进行评估，及时纠偏，"
            f"确保项目资源保障体系高效运行。",
        ]
        for para in resource_paragraphs:
            self.fmt.body(para)

    def render_professional_standards(self, keyword):
        """
        自动生成与keyword相关的8-15个国标/行标引用表
        
        根据关键词匹配标准数据库，输出规范引用表格。
        如果keyword无精确匹配，使用default库。
        
        Args:
            keyword: 章节主题关键词（如"施工"、"质量"、"安全"等）
        """
        # 查找匹配的标准库
        standards = None
        for db_key in _STANDARDS_DB:
            if db_key in keyword or keyword in db_key:
                standards = _STANDARDS_DB[db_key]
                break
        if standards is None:
            standards = _STANDARDS_DB['default']

        # 限制8-15条
        if len(standards) > 15:
            standards = standards[:15]
        if len(standards) < 8:
            # 补充default中的条目
            default_extra = [s for s in _STANDARDS_DB['default'] if s not in standards]
            standards = standards + default_extra[:8 - len(standards)]

        self.fmt.h2("主要引用标准及规范")
        self.fmt.body(
            f"本章节内容编制依据以下国家和行业标准，"
            f"施工过程中严格执行相关标准规范的最新版本："
        )

        headers = ['序号', '标准编号', '标准名称']
        rows = []
        for idx, (code, name) in enumerate(standards, 1):
            rows.append([str(idx), code, name])

        self.fmt.table(headers, rows)

        self.fmt.body(
            "注：以上标准均采用最新版本（含所有修改单），"
            "当上述标准被修订时，按修订后的最新版本执行。"
            "当标准之间出现矛盾时，以较严格的标准为准。"
        )

    def render_inspection_checklist(self, keyword):
        """
        自动生成10-15项的检查验收清单表
        
        根据关键词匹配检查清单数据库，输出检查清单表格。
        
        Args:
            keyword: 章节主题关键词
        """
        # 查找匹配的清单库
        checklist = None
        for db_key in _CHECKLIST_DB:
            if db_key in keyword or keyword in db_key:
                checklist = _CHECKLIST_DB[db_key]
                break
        if checklist is None:
            checklist = _CHECKLIST_DB['default']

        # 限制10-15条
        if len(checklist) > 15:
            checklist = checklist[:15]
        if len(checklist) < 10:
            default_extra = [c for c in _CHECKLIST_DB['default'] if c not in checklist]
            checklist = checklist + default_extra[:10 - len(checklist)]

        self.fmt.h2("检查验收清单")
        self.fmt.body(
            "为确保各项管理措施有效落实，特制定以下检查验收清单，"
            "各责任人应严格按照清单要求进行检查验收工作："
        )

        headers = ['序号', '检查项目', '检查时间/频次', '检查责任人', '验收标准']
        rows = []
        for idx, (item, freq, person, standard) in enumerate(checklist, 1):
            rows.append([str(idx), item, freq, person, standard])

        self.fmt.table(headers, rows)

        self.fmt.body(
            "以上检查验收项目由各责任人负责落实，检查结果应及时记录并存档。"
            "对检查中发现的问题应立即整改，整改完成后进行复查，"
            "确保问题得到彻底解决。"
        )

    def render_responsibility_table(self, keyword):
        """
        自动生成5-8个岗位的职责分工表
        
        根据关键词匹配岗位职责数据库，输出职责分工表格。
        
        Args:
            keyword: 章节主题关键词
        """
        # 查找匹配的职责库
        responsibilities = None
        for db_key in _RESPONSIBILITY_DB:
            if db_key in keyword or keyword in db_key:
                responsibilities = _RESPONSIBILITY_DB[db_key]
                break
        if responsibilities is None:
            responsibilities = _RESPONSIBILITY_DB['default']

        # 限制5-8条
        if len(responsibilities) > 8:
            responsibilities = responsibilities[:8]
        if len(responsibilities) < 5:
            default_extra = [r for r in _RESPONSIBILITY_DB['default'] if r not in responsibilities]
            responsibilities = responsibilities + default_extra[:5 - len(responsibilities)]

        self.fmt.h2("岗位职责分工")
        self.fmt.body(
            "为确保各项管理工作责任到人，特制定以下岗位职责分工表，"
            "各岗位人员应严格按照职责要求开展工作："
        )

        headers = ['序号', '岗位名称', '主要职责', '关键工作内容']
        rows = []
        for idx, (position, duty, tasks) in enumerate(responsibilities, 1):
            rows.append([str(idx), position, duty, tasks])

        self.fmt.table(headers, rows)

        self.fmt.body(
            "各岗位人员应充分理解自身职责，切实履行岗位责任。"
            "项目经理作为项目第一责任人，应加强协调与监督，"
            "确保各岗位职责落实到位，各项工作有序推进。"
            "对于职责不清或交叉事项，由项目经理负责协调明确。"
        )

    # ══════════════════════════════════════════════════════
    # v4.1 新增方法 — 专业数据库内容渲染
    # ══════════════════════════════════════════════════════

    # 章节名→专业数据库内容映射
    _PROFESSIONAL_CONTENT_MAP = {
        # 施工类章节映射
        '质量': {'methods': ['抹灰工程', '涂料工程', '饰面工程'], 'defects': ['空鼓', '裂缝', '色差']},
        '施工方案': {'methods': ['抹灰工程', '涂料工程', '地面工程'], 'defects': ['空鼓', '裂缝']},
        '分项': {'methods': ['抹灰工程', '涂料工程', '地面工程'], 'defects': ['空鼓', '裂缝']},
        '安全': {'safety': ['脚手架安全', '高处作业', '临时用电', '消防安全']},
        '文明': {'safety': ['消防安全'], 'defects': ['污染']},
        '装饰': {'methods': ['抹灰工程', '涂料工程', '饰面工程', '吊顶工程', '地面工程', '门窗工程'], 'defects': ['空鼓', '裂缝', '色差', '起皮', '渗漏']},
        '装修': {'methods': ['抹灰工程', '涂料工程', '饰面工程', '吊顶工程', '地面工程', '门窗工程'], 'defects': ['空鼓', '裂缝', '色差', '起皮', '渗漏']},
        '外立面': {'methods': [], 'defects': ['脱落', '渗漏', '裂缝'], 'safety': ['脚手架安全', '高处作业']},
        '测量': {'methods': [], 'defects': []},
        '进度': {'methods': [], 'defects': []},
        '总承包': {'methods': [], 'defects': []},
        '组织': {'methods': [], 'defects': []},
        '分包': {'methods': [], 'defects': []},
        '成品': {'methods': [], 'defects': ['污染', '脱落']},
        '紧急': {'safety': ['消防安全', '临时用电']},
        '预案': {'safety': ['消防安全', '临时用电']},
        '冬季': {'methods': [], 'defects': ['裂缝']},
        '雨季': {'methods': [], 'defects': ['渗漏']},
        '平面布置': {'methods': [], 'defects': []},
        # 服务类章节映射
        '服务质量': {'defects': ['起皮', '渗漏']},
        '日常维护': {'equipment': True, 'safety': ['临时用电', '消防安全']},
        '人员': {'equipment': True},
        '设备': {'equipment': True},
        '重难点': {'defects': ['空鼓', '裂缝', '渗漏']},
        '总体服务': {'equipment': True},
        '服务承诺': {'defects': []},
    }

    def render_professional_content(self, chapter_name, project_info=None):
        """
        v4.1: 根据章节名自动选择渲染工法/通病/设备/安全内容

        从ProfessionalDatabase获取专业内容并渲染到formatter。
        章节与数据库内容的映射关系由_PROFESSIONAL_CONTENT_MAP定义。

        Args:
            chapter_name: 章节名称，用于匹配渲染内容类型
            project_info: 项目信息字典（用于获取面积等参数）
        """
        # 查找匹配的映射配置
        config = None
        for key in self._PROFESSIONAL_CONTENT_MAP:
            if key in chapter_name:
                config = self._PROFESSIONAL_CONTENT_MAP[key]
                break

        if not config:
            return

        try:
            db = ProfessionalDatabase()
        except Exception:
            return

        area = 0
        if project_info:
            try:
                area = float(project_info.get('area', 0))
            except (ValueError, TypeError):
                area = 0

        detail = self.detail_level if self.detail_level >= 2 else 2

        # 渲染工法内容
        methods = config.get('methods', [])
        if methods and self.is_standard():
            self.fmt.h2("主要施工工法及技术要点")
            for method_name in methods:
                self.fmt.h3(method_name)
                db.render_method_to_formatter(self.fmt, method_name, detail_level=detail)

        # 渲染质量通病防治
        defects = config.get('defects', [])
        if defects and self.is_standard():
            self.fmt.h2("质量通病防治措施")
            for defect_type in defects:
                db.render_defect_to_formatter(self.fmt, defect_type)

        # 渲染设备清单
        if config.get('equipment') and self.is_standard():
            project_type = '装饰装修'
            if project_info:
                bid_type = project_info.get('bid_type', 'construction')
                if bid_type == 'service':
                    project_type = '装饰装修'
            self.fmt.h2("专业设备配置")
            db.render_equipment_to_formatter(self.fmt, project_type, area=area)

        # 渲染安全措施
        safety_types = config.get('safety', [])
        if safety_types and self.is_standard():
            self.fmt.h2("专项安全措施要点")
            for safety_type in safety_types:
                db.render_safety_to_formatter(self.fmt, safety_type)

    def _auto_fill_if_needed(self, project_info):
        """
        自动内容填充判断与执行 — v4.0 新增
        
        在render()方法末尾调用，根据条件自动补充扩展内容。
        触发条件：
        1. is_full() 为 True（detail_level >= 3）
        2. plan_info.target_pages > 20
        
        当以上两个条件同时满足时，依次调用：
        - render_extended_content()
        - render_professional_standards()
        - render_inspection_checklist()
        - render_responsibility_table()
        
        Args:
            project_info: 项目信息字典
        """
        target_pages = self.get_target_pages()
        if not self.is_full():
            return
        if not (target_pages > 0):
            return

        # 获取章节关键词（用于个性化内容）
        keyword = self._get_chapter_keyword()

        if target_pages > 20:
            # 完整模式：补充全部扩展内容
            self.render_extended_content(project_info, keyword)
            self.render_professional_standards(keyword)
            self.render_inspection_checklist(keyword)
            self.render_responsibility_table(keyword)
        elif target_pages > 0:
            # 轻量补充：仅补充标准引用和检查清单
            self.render_professional_standards(keyword)
            self.render_inspection_checklist(keyword)

    def _get_chapter_keyword(self):
        """
        从章节类名中提取关键词，用于匹配标准库和清单库
        
        Returns:
            匹配到的关键词字符串，默认返回"施工"
        """
        class_name = self.__class__.__name__
        keyword_map = {
            'Quality': '质量',
            'Safety': '安全',
            'Security': '安全',
            'Environment': '环保',
            'Civilization': '环保',
            'Install': '安装',
            'Steel': '钢结构',
            'Decor': '装饰',
            'Water': '给排水',
            'Electric': '电气',
            'Plumbing': '给排水',
            'HVAC': '安装',
            'Foundation': '施工',
            'Structure': '施工',
            'Progress': '施工',
            'Cost': '施工',
            'Bid': '施工',
        }
        for eng_key, cn_key in keyword_map.items():
            if eng_key.lower() in class_name.lower():
                return cn_key
        return '施工'
