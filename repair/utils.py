"""
修复工具模块
包含表格构建、标题检测等通用工具函数
"""
import re
from typing import Optional

from log_helper import get_logger
log = get_logger(__name__)


def _build_concrete_table(tbl_name: str) -> str:
    """为补表生成终版内容（杜绝"按实际填写"占位符）

    根据表名语义给出 3 行具体、可直接交付的表格内容。
    """
    if '责任人表' in tbl_name or '管理措施' in tbl_name:
        rows = [
            ('组织保障', '成立专项小组，项目经理牵头、技术负责人落实'),
            ('过程管控', '执行三检制，关键工序旁站监督'),
            ('责任到人', '签订质量责任书，落实到岗到人'),
        ]
    elif '标准表' in tbl_name or '检查项目' in tbl_name:
        rows = [
            ('原材料进场', '合格证齐全，复试合格后方可使用'),
            ('隐蔽工程', '验收合格并记录完整方可进入下道工序'),
            ('实测实量', '偏差满足规范及设计要求'),
        ]
    elif '时间表' in tbl_name or '实施计划' in tbl_name:
        rows = [
            ('准备阶段', '完成技术交底与资源配置'),
            ('实施阶段', '按进度计划组织施工'),
            ('验收阶段', '自检合格报监理验收'),
        ]
    else:
        rows = [
            ('资源配置', '人员、机械、材料按计划到位'),
            ('过程控制', '严格执行方案与规范'),
            ('结果验收', '符合设计及验收标准'),
        ]

    lines = [f'表：{tbl_name}', '| 序号 | 项目 | 内容/标准 | 备注 |',
             '|------|------|-----------|------|']
    for i, (item, std) in enumerate(rows, 1):
        lines.append(f'| {i} | {item} | {std} | |')

    return '\n'.join(lines)


def _re_match_heading(text: str) -> bool:
    """检测文本是否为标题格式"""
    heading_patterns = [
        r'^第[一二三四五六七八九十]+[章节部分]',
        r'^[\d\.]+[\s、]',
        r'^[一二三四五六七八九十]+[、\.]',
        r'^（[一二三四五六七八九十]+）',
    ]
    return any(re.match(p, text.strip()) for p in heading_patterns)


def _re_detect_heading_level(text: str) -> int:
    """检测标题级别

    Returns:
        1: 一级标题（章）
        2: 二级标题（节）
        3: 三级标题（小节）
        0: 非标题
    """
    text = text.strip()

    # 一级标题模式
    if re.match(r'^第[一二三四五六七八九十]+[章]', text):
        return 1
    if re.match(r'^[\d]+\.', text) and not re.match(r'^[\d]+\.[\d]+', text):
        return 1

    # 二级标题模式
    if re.match(r'^[\d]+\.[\d]+[\s、]', text):
        return 2
    if re.match(r'^[一二三四五六七八九十]+[、．]', text):
        return 2

    # 三级标题模式
    if re.match(r'^[\d]+\.[\d]+\.[\d]+', text):
        return 3
    if re.match(r'^（[一二三四五六七八九十]+）', text):
        return 3

    return 0


# 常见问题修复模板库 v2.0
REPAIR_TEMPLATES = {
    'DQ001': {  # 工期超标
        'name': '工期超标',
        'template': '我方承诺本工程总工期为{duration}日历天，不超过招标文件要求的{tender_duration}日历天。'
                    '我方将通过科学组织、合理安排、加大资源投入等措施，确保在合同工期内完成全部施工任务。',
    },
    'DQ002': {  # 质量目标缺失
        'name': '质量目标缺失',
        'template': '我方承诺本工程质量目标为{quality_target}，符合国家现行工程施工质量验收规范标准。'
                    '工程竣工验收时，所有分部分项工程均达到合格标准，观感质量评分不低于80%。',
    },
    'DQ003': {  # 安全生产许可证
        'name': '安全生产许可证未提及',
        'template': '我方持有有效的安全生产许可证，证书在有效期内。'
                    '施工全过程严格遵守《安全生产许可证条例》和《建筑施工企业安全生产管理机构设置及专职安全生产管理人员配备办法》的规定，'
                    '确保安全生产合法合规。安全生产许可证复印件随投标文件一并递交。',
    },
    'DQ004': {  # 项目经理资格
        'name': '项目经理资格未说明',
        'template': '我方拟派项目经理持有{cert_type}，证书在有效期内。'
                    '项目经理具有{years}年以上同类工程施工管理经验，曾主持过{project_example}等类似项目，'
                    '具备全面的项目管理能力和专业技术水平。',
    },
    'DQ005': {  # 投标人名称不一致
        'name': '投标人名称不一致',
        'template': '我方确认投标文件中所有涉及投标人名称的表述均保持一致。',
    },
    # 更多模板...
}
