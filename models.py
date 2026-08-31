"""
入口层类型模型 v1.0 — P1-6 重构

用 Pydantic BaseModel 替换 main.py 中的 args: dict 裸字典，
提供类型安全、自动校验和 IDE 自动补全。

用法:
    from bid_core.models import BidRequest

    req = BidRequest(name='测试项目', target_pages=200)
    result = generate_bid_document(req)

    # 或从字典构建（兼容旧接口）
    req = BidRequest(**raw_dict)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field, field_validator
    _HAS_PYDANTIC = True
except ImportError:
    # Pydantic 不可用时降级为 dataclass
    from dataclasses import dataclass as _dataclass, field as _field
    _HAS_PYDANTIC = False


if _HAS_PYDANTIC:
    class BidRequest(BaseModel):
        """标书生成请求模型

        替换原有的 args: dict 参数，提供类型安全和校验。
        """

        # ── 项目基本信息 ──
        name: str = Field('未命名项目', description='项目名称')
        duration: int = Field(0, ge=0, description='工期(天)')
        area: float = Field(0, ge=0, description='建筑面积(m²)')
        structure_type: str = Field('', description='结构类型')
        work_content: str = Field('', description='工程内容描述')
        quality_target: str = Field('合格', description='质量目标')
        divisions: List[str] = Field(default_factory=list, description='分部分项工程列表')
        bid_type: str = Field('construction', description='标书类型: construction/service')
        bid_section: str = Field('technical', description='标段: technical/commercial/qualification')

        # ── 生成参数 ──
        target_pages: int = Field(0, ge=0, description='目标页数(>120自动完整模式)')
        detail_level: Optional[int] = Field(None, ge=1, le=5, description='手动指定深度(1-5)')
        output_path: str = Field('', description='输出文件路径')

        # ── 解析结果 ──
        parse_result: Optional[Dict[str, Any]] = Field(None, description='parser.py解析结果')

        # ── 用户信息 ──
        user_context: Optional[Dict[str, Any]] = Field(None, description='用户信息(公司/人员/业绩)')

        # ── 暗标模式 ──
        is_dark_bid: bool = Field(False, description='是否暗标模式')
        dark_bid_filter_words: Optional[List[str]] = Field(None, description='暗标过滤词列表')

        # ── 封面/目录/页码 ──
        add_cover: bool = Field(True, description='是否添加封面')
        add_toc: bool = Field(True, description='是否添加目录')
        add_page_numbers: bool = Field(True, description='是否添加页码')

        # ── 后处理钩子 ──
        enable_hooks: bool = Field(True, description='是否启用后处理钩子')
        enable_deai: bool = Field(True, description='是否启用去AI化')
        enable_format: bool = Field(True, description='是否启用格式修正')
        enable_rewrite: bool = Field(False, description='是否启用降重')
        enable_duplicate: bool = Field(False, description='是否启用查重')

        # ── 随机化 ──
        randomize: bool = Field(False, description='是否启用随机化')

        # ── 字体 ──
        heading_font: Optional[str] = Field(None, description='标题字体(默认黑体)')
        body_font: Optional[str] = Field(None, description='正文字体(默认仿宋)')

        # ── 其他 ──
        header_text: str = Field('', description='页眉文字')
        mode: str = Field('normal', description='生成模式')

        # ── v7.0 升级开关与参数 ──
        enable_deviation_table: bool = Field(True, description='P0: 自动生成偏离表(需 parse_result)')
        enable_risk_grading: bool = Field(True, description='P2: 三级废标风险分级预警')
        enable_mock_review: bool = Field(True, description='P2: 模拟评审打分与得分表')
        enable_knowledge_base: bool = Field(True, description='P3: 启用企业知识库复用')
        enable_feasibility: bool = Field(True, description='v8.9: 投标前可行性预评估(资质匹配/废标风险/时间压力)')
        reference_file: Optional[str] = Field(None, description='P1: 以标写标-参考历史标书路径(docx)')
        chapter_only: bool = Field(False, description='P1: 仅生成单章节(配合 chapter_title)')
        chapter_title: Optional[str] = Field(None, description='P1: 单章节标题(配合 chapter_only)')
        knowledge_base_path: Optional[str] = Field(None, description='P3: 知识库 JSON 路径(默认 data/user_knowledge_base.json)')
        tender_file: Optional[str] = Field(None, description='v7.1: 招标文件路径(docx/pdf)，自动解析为 parse_result')
        previous_bids: Optional[List[str]] = Field(None, description='v8.9: 历史标书路径列表,用于跨文档防串标查重')
        enable_qualification_response: bool = Field(True, description='v9.0: 企业资质业绩库+资质业绩响应表注入成稿')
        enable_scoring_reinforce: bool = Field(False, description='v9.2: 评分响应闭环补强(PDCA-Act)，默认关闭，避免正文尾部堆积评分项描述')

        @field_validator('bid_type')
        @classmethod
        def validate_bid_type(cls, v: str) -> str:
            if v not in ('construction', 'service'):
                raise ValueError(f'bid_type 必须是 construction 或 service, got {v}')
            return v

        @field_validator('bid_section')
        @classmethod
        def validate_bid_section(cls, v: str) -> str:
            if v not in ('technical', 'commercial', 'qualification'):
                raise ValueError(f'bid_section 必须是 technical/commercial/qualification, got {v}')
            return v

        model_config = {
            'extra': 'allow',  # 允许额外字段，向后兼容
        }

    class CheckRequest(BaseModel):
        """合规检查请求模型"""
        bid_doc_path: str = Field(..., description='标书文件路径')
        parse_result: Optional[Dict[str, Any]] = Field(None, description='解析结果')
        doc_info: Optional[Dict[str, Any]] = Field(None, description='文档信息')
        max_rounds: int = Field(3, ge=1, le=10, description='最大修复轮数')

    class DuplicateCheckRequest(BaseModel):
        """查重请求模型"""
        file_paths: List[str] = Field(..., min_length=2, description='待查重文件路径列表')
        mode: str = Field('标书', description='查重模式')

else:
    # ── Pydantic 不可用时的降级实现（dataclass） ──
    @_dataclass
    class BidRequest:
        """标书生成请求模型（降级版，无校验）"""
        name: str = '未命名项目'
        duration: int = 0
        area: float = 0
        structure_type: str = ''
        work_content: str = ''
        quality_target: str = '合格'
        divisions: List[str] = _field(default_factory=list)
        bid_type: str = 'construction'
        bid_section: str = 'technical'
        target_pages: int = 0
        detail_level: Optional[int] = None
        output_path: str = ''
        parse_result: Optional[Dict[str, Any]] = None
        user_context: Optional[Dict[str, Any]] = None
        is_dark_bid: bool = False
        dark_bid_filter_words: Optional[List[str]] = None
        add_cover: bool = True
        add_toc: bool = True
        add_page_numbers: bool = True
        enable_hooks: bool = True
        enable_deai: bool = True
        enable_format: bool = True
        enable_rewrite: bool = False
        enable_duplicate: bool = False
        randomize: bool = False
        heading_font: Optional[str] = None
        body_font: Optional[str] = None
        header_text: str = ''
        mode: str = 'normal'
        # 以下 5 个字段此前只存在于 Pydantic 版，降级分支漏定义，
        # 导致 main.py 访问 req.reference_file 时抛 AttributeError。
        # 默认值与 Pydantic 版保持一致。
        enable_deviation_table: bool = True
        enable_risk_grading: bool = True
        enable_mock_review: bool = True
        enable_knowledge_base: bool = True
        reference_file: Optional[str] = None
        chapter_only: bool = False
        chapter_title: Optional[str] = None
        knowledge_base_path: Optional[str] = None
        tender_file: Optional[str] = None
        enable_feasibility: bool = True
        previous_bids: Optional[List[str]] = None
        enable_qualification_response: bool = True
        enable_scoring_reinforce: bool = False

        def model_dump(self) -> Dict[str, Any]:
            """兼容 Pydantic 的 model_dump 接口"""
            from dataclasses import asdict
            return asdict(self)

        @classmethod
        def model_validate(cls, data: Dict[str, Any]) -> 'BidRequest':
            """兼容 Pydantic 的 model_validate 接口"""
            return cls(**{k: v for k, v in data.items()
                         if k in cls.__dataclass_fields__})

    @_dataclass
    class CheckRequest:
        bid_doc_path: str = ''
        parse_result: Optional[Dict[str, Any]] = None
        doc_info: Optional[Dict[str, Any]] = None
        max_rounds: int = 3

    @_dataclass
    class DuplicateCheckRequest:
        file_paths: List[str] = _field(default_factory=list)
        mode: str = '标书'


def dict_to_request(data: Dict[str, Any]) -> BidRequest:
    """从字典创建 BidRequest（兼容旧接口）

    Args:
        data: 原始字典参数

    Returns:
        BidRequest 实例
    """
    if _HAS_PYDANTIC:
        return BidRequest(**data)
    else:
        return BidRequest.model_validate(data)


def request_to_dict(req: BidRequest) -> Dict[str, Any]:
    """将 BidRequest 转回字典（兼容旧接口）"""
    if _HAS_PYDANTIC:
        return req.model_dump()
    else:
        return req.model_dump()
