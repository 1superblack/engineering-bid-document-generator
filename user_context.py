"""
UserContext - 用户信息注入器 v2.0
v2.0: 增加自动推断填充能力（业绩/设备/人员/资质）
v1.0: 管理用户独有信息（公司/人员/业绩/设备）
"""
import os

from bid_core.logger import get_logger

log = get_logger(__name__)


class UserContext:
    """用户信息注入器 v2.0"""
    
    # 按bid_type的设备模板
    EQUIPMENT_TEMPLATES = {
        'construction': [
            {'name': '电焊机', 'model': 'BX3-300', 'count': 4},
            {'name': '电锤', 'model': 'GBH2-26', 'count': 6},
            {'name': '空压机', 'model': 'V-0.6/8', 'count': 2},
            {'name': '切割机', 'model': 'J3G-400', 'count': 4},
            {'name': '砂浆搅拌机', 'model': 'UJZ-200', 'count': 3},
        ],
        'service': [
            {'name': '高压清洗机', 'model': 'KJR-1798A', 'count': 2},
            {'name': '消毒设备', 'model': '二氧化氯发生器', 'count': 2},
            {'name': '检测仪器', 'model': '多参数水质检测仪', 'count': 1},
            {'name': '工程车', 'model': '小型货车', 'count': 1},
            {'name': '抽水泵', 'model': 'WQD10-15-1.5', 'count': 3},
        ],
    }

    # 按bid_type的人员资质模板
    PERSONNEL_TEMPLATES = {
        'construction': [
            {'role': '项目经理', 'cert': '一级/二级建造师', 'major': '建筑工程'},
            {'role': '技术负责人', 'cert': '中级及以上职称', 'major': '相关专业'},
            {'role': '安全员', 'cert': '安全员C证', 'major': '安全工程'},
            {'role': '质检员', 'cert': '质检员证', 'major': '质量管理'},
        ],
        'service': [
            {'role': '项目负责人', 'cert': '项目经理证书', 'major': '相关专业'},
            {'role': '技术负责人', 'cert': '中级及以上职称', 'major': '相关专业'},
            {'role': '安全员', 'cert': '安全员证', 'major': '安全工程'},
            {'role': '质检员', 'cert': '质检员证', 'major': '质量管理'},
        ],
    }

    # 按bid_type的业绩模板
    PROJECT_TEMPLATES = {
        'construction': [
            {'name': '某办公楼装饰装修工程', 'amount': '约500万元', 'scale': '8000㎡'},
            {'name': '某小区外墙排危整治工程', 'amount': '约300万元', 'scale': '5000㎡'},
            {'name': '某学校旧房改造工程', 'amount': '约200万元', 'scale': '3000㎡'},
        ],
        'service': [
            {'name': '某区二次供水设施清洗消毒服务', 'amount': '约80万元/年', 'scale': '50座设施'},
            {'name': '某物业设施维护服务', 'amount': '约60万元/年', 'scale': '20个小区'},
            {'name': '某市政设施运营维护服务', 'amount': '约100万元/年', 'scale': '30处设施'},
        ],
    }
    
    def __init__(self, context_data=None):
        """
        初始化用户上下文
        
        Args:
            context_data: 用户信息字典，格式见架构规范
        """
        self.data = context_data or {}
    
    @classmethod
    def from_file(cls, file_path):
        """从JSON文件加载用户信息"""
        import json
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(data)
        return cls({})

    @classmethod
    def load_knowledge_base(cls, path: str) -> 'UserContext':
        """P3: 从企业知识库 JSON 加载用户信息。

        知识库结构同 user_context，但额外可包含 products / images / templates 等复用字段。
        """
        import json
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return cls(data)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning('知识库加载失败，降级为空上下文: %s', exc)
        return cls({})

    def merge_knowledge_base(self, path: str) -> None:
        """P3: 合并知识库 JSON 到当前上下文（仅补全缺失/空字段，不覆盖用户提供值）。"""
        import json
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                kb = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning('知识库合并失败（已忽略）: %s', exc)
            return
        self._deep_merge_kb(self.data, kb)

    @staticmethod
    def _deep_merge_kb(base: dict, incoming: dict) -> None:
        """深合并：incoming 仅补全 base 中缺失或为空的字段，不覆盖已有值。"""
        for key, value in incoming.items():
            if key.startswith('_'):  # 跳过 _meta 等元数据
                continue
            if key not in base or base[key] in (None, '', [], {}):
                base[key] = value
            elif isinstance(base[key], dict) and isinstance(value, dict):
                UserContext._deep_merge_kb(base[key], value)
            elif isinstance(base[key], list) and isinstance(value, list):
                # 列表：追加 base 中不存在的元素
                existing = {str(x) for x in base[key]}
                for item in value:
                    if str(item) not in existing:
                        base[key].append(item)
    
    def get(self, key, default=None):
        """
        获取用户信息
        支持点号分隔的路径，如 'company.name'
        """
        if '.' in key:
            keys = key.split('.')
            value = self.data
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                else:
                    return default
            return value if value is not None else default
        return self.data.get(key, default)
    
    def get_company(self):
        """获取公司信息"""
        return self.data.get('company', {})
    
    def get_key_personnel(self):
        """获取关键人员列表"""
        return self.data.get('key_personnel', [])
    
    def get_similar_projects(self):
        """获取类似项目列表"""
        return self.data.get('similar_projects', [])
    
    def get_equipment(self):
        """获取设备列表"""
        return self.data.get('equipment_owned', [])

    def get_images(self):
        """v7.3: 获取企业图片库（配图用）。格式：[{name, path, desc}, ...]"""
        return self.data.get('images', []) or []
    
    def get_special_methods(self):
        """获取特种工艺列表"""
        return self.data.get('special_methods', [])
    
    def get_project_manager(self):
        """获取项目经理信息"""
        for person in self.get_key_personnel():
            if person.get('role') == '项目经理' or '经理' in person.get('role', ''):
                return person
        return None
    
    def get_tech_leader(self):
        """获取技术负责人信息"""
        for person in self.get_key_personnel():
            if '技术' in person.get('role', ''):
                return person
        return None
    
    def has_info(self):
        """检查是否有用户信息"""
        return bool(self.data)
    
    def merge(self, additional_data):
        """合并额外数据：已有值（user_context）优先，additional_data（知识库）仅补缺。

        ADR-007：避免 demo 知识库（示例建设集团）覆盖用户注入的真实投标人信息。
        """
        if isinstance(additional_data, dict):
            for key, value in additional_data.items():
                if key in self.data and isinstance(self.data[key], dict) and isinstance(value, dict):
                    # 以 self.data[key]（用户上下文）为基准，知识库仅补充缺失键
                    merged = dict(value)
                    merged.update(self.data[key])
                    self.data[key] = merged
                else:
                    if key not in self.data:
                        self.data[key] = value
    
    def to_dict(self):
        """转为字典"""
        return self.data.copy()
    
    def get_filter_words(self):
        """获取暗标过滤词表"""
        words = []
        company = self.get_company()
        if company.get('name'):
            words.append(company['name'])
        if company.get('legal_person'):
            words.append(company['legal_person'])
        for person in self.get_key_personnel():
            if person.get('name'):
                words.append(person['name'])
        return words

    # ── v2.0 自动推断填充方法 ──

    def infer_equipment(self, project_info=None):
        """根据bid_type推断需要的设备清单
        
        如果用户已提供设备则直接返回，否则从模板推断。
        """
        existing = self.get_equipment()
        if existing:
            return existing

        bid_type = 'construction'
        if project_info:
            bid_type = project_info.get('bid_type', 'construction')

        return self.EQUIPMENT_TEMPLATES.get(bid_type, self.EQUIPMENT_TEMPLATES['construction'])

    def infer_personnel(self, project_info=None):
        """根据bid_type推断需要的人员资质
        
        如果用户已提供关键人员则直接返回，否则从模板推断。
        """
        existing = self.get_key_personnel()
        if existing:
            return existing

        bid_type = 'construction'
        if project_info:
            bid_type = project_info.get('bid_type', 'construction')

        return self.PERSONNEL_TEMPLATES.get(bid_type, self.PERSONNEL_TEMPLATES['construction'])

    def infer_projects(self, project_info=None):
        """根据bid_type推断类似业绩
        
        如果用户已提供业绩则直接返回，否则从模板推断。
        """
        existing = self.get_similar_projects()
        if existing:
            return existing

        bid_type = 'construction'
        if project_info:
            bid_type = project_info.get('bid_type', 'construction')

        return self.PROJECT_TEMPLATES.get(bid_type, self.PROJECT_TEMPLATES['construction'])

    def needs_safety_license(self, project_info=None):
        """判断是否需要安全生产许可证
        
        施工类项目一般都需要，服务类通常不需要。
        """
        bid_type = 'construction'
        if project_info:
            bid_type = project_info.get('bid_type', 'construction')
        
        # 施工类需要安全生产许可证
        if bid_type == 'construction':
            return True
        
        # 服务类涉及有限空间作业的也需要
        work = (project_info or {}).get('work_content', '')
        if any(kw in work for kw in ['有限空间', '清洗', '消毒', '水箱']):
            return True
        
        return False

    def get_qualification_requirements(self, project_info=None):
        """获取资质要求列表
        
        根据项目信息推断需要的资质。
        """
        reqs = []
        bid_type = 'construction'
        if project_info:
            bid_type = project_info.get('bid_type', 'construction')
        
        if bid_type == 'construction':
            reqs.append({'name': '安全生产许可证', 'required': True})
            reqs.append({'name': '建筑业企业资质证书', 'required': True})
            
            work = (project_info or {}).get('work_content', '')
            if '装饰' in work or '装修' in work:
                reqs.append({'name': '建筑装修装饰工程专业承包资质', 'required': True})
            if '防水' in work:
                reqs.append({'name': '防水防腐保温工程专业承包资质', 'required': False})
            if '幕墙' in work or '外立面' in work:
                reqs.append({'name': '建筑幕墙工程专业承包资质', 'required': True})
            if '消防' in work:
                reqs.append({'name': '消防设施工程专业承包资质', 'required': True})
        
        elif bid_type == 'service':
            work = (project_info or {}).get('work_content', '')
            if '清洗' in work or '消毒' in work or '二次供水' in work:
                reqs.append({'name': '涉及饮用水卫生安全产品卫生许可批件', 'required': True})
                reqs.append({'name': '有限空间作业资质', 'required': True})
            if '物业' in work:
                reqs.append({'name': '物业服务企业资质证书', 'required': False})
        
        return reqs
