# -*- coding: utf-8 -*-
"""
工程标书生成器 - Skill入口 v6.0
v6.0: Pydantic 模型校验入口（P1-6 重构）；延迟导入；日志规范化
v5.0: 封面/目录/页码支持；暗标模式增强；后处理钩子；商务标/资格标框架
v4.0: detail_level 深度控制和 parse_result 评分项对齐
"""

import json
from typing import Any, Dict, Union

from bid_core.models import BidRequest, dict_to_request, request_to_dict
from bid_core.logger import get_logger
from bid_core.llm_client import load_llm_config

_log = get_logger(__name__)


def generate_bid_document(args: Union[Dict[str, Any], BidRequest]) -> Dict[str, Any]:
    """生成工程标书 v6.0

    Args:
        args: 项目信息字典或 BidRequest 模型实例，支持以下参数：
            - name: 项目名称
            - target_pages: 目标页数（>120自动完整模式）
            - detail_level: 手动指定深度(1-5)
            - parse_result: parser.py解析结果
            - user_context: 用户信息（公司/人员/业绩）
            - is_dark_bid: 是否暗标模式
            - dark_bid_filter_words: 暗标过滤词列表
            - add_cover: 是否添加封面（默认True）
            - add_toc: 是否添加目录（默认True）
            - add_page_numbers: 是否添加页码（默认True）
            - enable_deai: 是否启用去AI化（默认True）
            - enable_format: 是否启用格式修正（默认True）
            - enable_deviation_table: 是否自动生成偏离表（默认True，需 parse_result）
            - heading_font: 标题字体（默认黑体）
            - body_font: 正文字体（默认仿宋）

    Returns:
        包含生成结果的字典
    """
    try:
        # 统一转为 BidRequest 模型（兼容 dict 入参）
        if isinstance(args, dict):
            req = dict_to_request(args)
        else:
            req = args

        data = request_to_dict(req)

        # v7.2: 若配置了 LLM 扩写（环境变量或 data/llm_config.json），构造客户端；
        # 未配置时返回 None，RichChapter 自动回退模板，行为与 v7.1 一致。
        llm_client = load_llm_config()

        from bid_generator import (
            generate_bid, generate_bid_with_hooks,
        )

        # 提取参数
        target_pages = req.target_pages
        detail_level = req.detail_level
        parse_result = req.parse_result
        user_context = req.user_context

        # v7.1: 若提供了招标文件，自动解析为 parse_result（除非已显式传入）
        if req.tender_file and not parse_result:
            try:
                from bid_core.parser import parse_tender
                parsed = parse_tender(req.tender_file, bid_type=req.bid_type)
                if parsed.get('score_items') or parsed.get('star_clauses') or \
                   parsed.get('qualification_reqs') or parsed.get('red_line_clauses'):
                    req.parse_result = parsed
                    data['parse_result'] = parsed
                    _log.info('已从招标文件解析 parse_result: %s（评分项 %d / 星号 %d / 资格 %d / 红线 %d）',
                              req.tender_file, len(parsed.get('score_items', [])),
                              len(parsed.get('star_clauses', [])),
                              len(parsed.get('qualification_reqs', [])),
                              len(parsed.get('red_line_clauses', [])))
                else:
                    _log.warning('招标文件未解析出有效条款，已忽略: %s', req.tender_file)
            except Exception as exc:
                _log.warning('招标文件解析失败，已忽略: %s | %s', req.tender_file, exc)
        parse_result = req.parse_result
        is_dark_bid = req.is_dark_bid
        dark_bid_filter_words = req.dark_bid_filter_words
        reference_file = req.reference_file
        enable_risk_grading = req.enable_risk_grading
        enable_mock_review = req.enable_mock_review
        enable_knowledge_base = req.enable_knowledge_base
        knowledge_base_path = req.knowledge_base_path

        # P1: 单章节生成模式（chapter_only + chapter_title）
        if req.chapter_only and req.chapter_title:
            from bid_core.chapter_generator import generate_single_chapter
            single_req = data.copy()
            single_req['chapter_title'] = req.chapter_title
            single_req['detail_level'] = detail_level or 3
            single_req['parse_result'] = parse_result
            single_req['user_context'] = user_context
            single_req['bid_type'] = req.bid_type
            single_req['output_path'] = req.output_path or None
            single_req['llm_client'] = llm_client
            _log.info('单章节生成模式: %s', req.chapter_title)
            return generate_single_chapter(single_req)

        # 生成输出路径
        output_path = req.output_path or f"技术标书_{req.name}.docx"

        _log.info('开始生成标书: %s | 页数=%d | 暗标=%s',
                  req.name, target_pages, is_dark_bid)

        if req.enable_hooks:
            result_path_data = generate_bid_with_hooks(
                project_info=data,
                target_pages=target_pages,
                output_path=output_path,
                parse_result=parse_result,
                user_context=user_context,
                detail_level=detail_level,
                randomize=req.randomize,
                is_dark_bid=is_dark_bid,
                dark_bid_filter_words=dark_bid_filter_words,
                add_cover=req.add_cover,
                add_toc=req.add_toc,
                add_page_numbers=req.add_page_numbers,
                enable_deai=req.enable_deai,
                enable_format=req.enable_format,
                enable_deviation_table=req.enable_deviation_table,
                reference_file=reference_file,
                enable_risk_grading=enable_risk_grading,
                enable_mock_review=enable_mock_review,
                enable_knowledge_base=enable_knowledge_base,
                knowledge_base_path=knowledge_base_path,
                heading_font=req.heading_font,
                body_font=req.body_font,
                llm_client=llm_client,
            )
            result_path = result_path_data.get('doc_path', output_path)
            hooks_result = result_path_data.get('hooks', {})
        else:
            result_path = generate_bid(
                project_info=data,
                target_pages=target_pages,
                output_path=output_path,
                parse_result=parse_result,
                detail_level=detail_level,
                user_context=user_context,
                bid_type=req.bid_type,
                randomize=req.randomize,
                is_dark_bid=is_dark_bid,
                dark_bid_filter_words=dark_bid_filter_words,
                add_cover=req.add_cover,
                add_toc=req.add_toc,
                add_page_numbers=req.add_page_numbers,
                enable_deviation_table=req.enable_deviation_table,
                reference_file=reference_file,
                enable_risk_grading=enable_risk_grading,
                enable_mock_review=enable_mock_review,
                enable_knowledge_base=enable_knowledge_base,
                knowledge_base_path=knowledge_base_path,
                heading_font=req.heading_font,
                body_font=req.body_font,
                llm_client=llm_client,
            )
            hooks_result = None

        _log.info('标书生成完成: %s', result_path)

        return {
            "success": True,
            "message": "标书生成成功",
            "output_file": result_path,
            "project": req.name,
            "duration": req.duration,
            "area": req.area,
            "detail_level": detail_level or (3 if target_pages > 120 else 2 if target_pages > 50 else 1),
            "is_dark_bid": is_dark_bid,
            "hooks_applied": hooks_result is not None,
        }
    except Exception as e:
        _log.error('标书生成失败: %s', e, exc_info=True)
        return {
            "success": False,
            "message": f"生成失败：{str(e)}"
        }


def check_and_repair_bid(args: Dict[str, Any]) -> Dict[str, Any]:
    """合规检查+修复

    Args:
        args: 包含检查参数的字典：
            - bid_doc_path: 标书文件路径
            - parse_result: 解析结果
            - doc_info: 文档信息
            - max_rounds: 最大修复轮数（默认3）

    Returns:
        包含检查结果的字典
    """
    try:
        from bid_generator import check_and_repair
        result = check_and_repair(
            project_info=args,
            parse_result=args.get('parse_result'),
            bid_doc_path=args.get('bid_doc_path'),
            doc_info=args.get('doc_info'),
            max_rounds=args.get('max_rounds', 3),
        )
        return {
            "success": True,
            "passed": result.get('passed', False),
            "rounds": result.get('rounds', []),
            "message": result.get('message', ''),
        }
    except Exception as e:
        _log.error('检查失败: %s', e, exc_info=True)
        return {
            "success": False,
            "message": f"检查失败：{str(e)}"
        }


def check_duplicate_documents(args: Dict[str, Any]) -> Dict[str, Any]:
    """文档查重

    Args:
        args: 包含查重参数的字典：
            - file_paths: 待查重文件路径列表
            - mode: 查重模式（标书/论文/通用）

    Returns:
        包含查重结果的字典
    """
    try:
        from bid_generator import check_duplicates
        file_paths = args.get('file_paths', [])
        mode = args.get('mode', '标书')
        if not file_paths or len(file_paths) < 2:
            return {
                "success": False,
                "message": "至少需要2个文件进行查重",
            }
        result = check_duplicates(file_paths, mode=mode)
        return {
            "success": True,
            "result": result,
        }
    except Exception as e:
        _log.error('查重失败: %s', e, exc_info=True)
        return {
            "success": False,
            "message": f"查重失败：{str(e)}"
        }


if __name__ == "__main__":
    # 测试完整模式（200+页）
    test_project = {
        "name": "测试项目-v6.0完整标书",
        "duration": 90,
        "area": 3600,
        "structure_type": "3层装修",
        "work_content": "室内装修、给排水、电气",
        "quality_target": "合格",
        "divisions": ["装饰装修工程", "给排水工程", "电气工程"],
        "target_pages": 250,
    }
    result = generate_bid_document(test_project)
    print(json.dumps(result, ensure_ascii=False, indent=2))
