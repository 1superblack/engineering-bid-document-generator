#!/usr/bin/env python3
"""
ScoringStrategy - 评分项→高分内容策略映射 v1.0

根据评分细则智能分配内容深度，为每个章节生成高分内容策略：
- 分析评分项权重，输出内容深度分配建议
- 根据章节+评分项+权重返回差异化内容策略
- 内置施工类15章/服务类7章的高分内容要素数据库
- 支持必须包含、加分项、常见遗漏三维度要素识别

与现有架构集成点：
- planner.py: plan_chapters() 可调用 analyze_score_items() 增强 detail_level 分配
- chapter_interface.py: ChapterInterface 可调用 get_content_strategy() 指导内容生成
- generator.py: render_chapter() 可调用 get_must_have_content() 确保内容完整性
"""


import json
from pathlib import Path

from bid_core.data_loader import DataLoader

# ══════════════════════════════════════════════════════════════════
# 评分策略数据库 — 从 data/scoring_strategy.json 加载（v1.1 重构）
#
# 原硬编码于本文件 L21-569，共 550 行。现迁移至外部 JSON 配置，
# 修改策略无需改动代码，便于运营人员独立维护。
# JSON 路径：data/scoring_strategy.json（相对于项目根目录）
# v1.2: 通过统一 DataLoader 加载（P1-1 重构）
# ══════════════════════════════════════════════════════════════════


def _load_strategy_data() -> dict:
    """从 JSON 加载评分策略数据。

    Returns:
        包含 construction_strategy_db / service_strategy_db /
        chapter_match_keywords 三个键的字典。
    """
    return DataLoader().load_scoring_strategy()


_strategy_data = _load_strategy_data()
CONSTRUCTION_STRATEGY_DB: dict = _strategy_data['construction_strategy_db']
SERVICE_STRATEGY_DB: dict = _strategy_data['service_strategy_db']
CHAPTER_MATCH_KEYWORDS: dict = _strategy_data['chapter_match_keywords']


class ScoringStrategy:
    """
    评分项→高分内容策略映射

    核心功能：
    - analyze_score_items(): 分析评分项权重，输出内容深度分配建议
    - get_content_strategy(): 根据章节+评分项+权重返回内容策略
    - get_detail_level(): 根据权重占比返回 detail_level（1-5）
    - get_must_have_content(): 返回该章节必须包含的内容要素列表

    与现有架构兼容：
    - detail_level 1-5 向下兼容原有 1-3 体系（5→3, 4→3, 3→3, 2→2, 1→1）
    - 章节名匹配复用 planner.py 的 CHAPTER_KEYWORD_MAP 逻辑
    - 策略输出可直接注入 ChapterInterface.plan_info
    """

    def __init__(self, project_type="construction"):
        """
        初始化评分策略

        Args:
            project_type: 工程类型，'construction' 或 'service'
        """
        self.project_type = project_type
        if project_type == "service":
            self._db = SERVICE_STRATEGY_DB
        else:
            self._db = CONSTRUCTION_STRATEGY_DB

    # ── 核心方法 ──────────────────────────────────────────────

    def analyze_score_items(self, score_items):
        """
        分析评分项权重，输出内容深度分配建议

        Args:
            score_items: 评分项列表，每项包含 name/title, score 等字段
                         例: [{"title": "施工方案", "score": 25}, ...]

        Returns:
            dict: {
                "total_weight": 总分,
                "items_analysis": [
                    {
                        "name": 评分项名称,
                        "weight": 分值,
                        "weight_ratio": 权重占比(0-1),
                        "detail_level": 建议内容深度(1-5),
                        "max_pages": 页数上限,
                        "chapter_match": 匹配到的章节名,
                        "strategy": 内容策略字典,
                    },
                    ...
                ],
                "priority_order": 按权重排序的评分项索引列表,
                "high_priority_count": 高优先级(权重≥10%)评分项数量,
            }
        """
        if not score_items:
            return {
                "total_weight": 0,
                "items_analysis": [],
                "priority_order": [],
                "high_priority_count": 0,
            }

        total_weight = sum(item.get("score", 0) for item in score_items)
        items_analysis = []

        for item in score_items:
            name = item.get("name") or item.get("title", "")
            weight = item.get("score", 0)
            weight_ratio = weight / total_weight if total_weight > 0 else 0

            detail_level = self.get_detail_level(weight, total_weight)
            max_pages = self._get_max_pages(detail_level)
            chapter_match = self._match_chapter(name)
            strategy = self.get_content_strategy(chapter_match or name, item, weight)

            items_analysis.append({
                "name": name,
                "weight": weight,
                "weight_ratio": round(weight_ratio, 4),
                "detail_level": detail_level,
                "max_pages": max_pages,
                "chapter_match": chapter_match,
                "strategy": strategy,
            })

        # 按权重降序排列的索引
        priority_order = sorted(
            range(len(items_analysis)),
            key=lambda i: items_analysis[i]["weight"],
            reverse=True,
        )

        high_priority_count = sum(
            1 for a in items_analysis if a["weight_ratio"] >= 0.10
        )

        return {
            "total_weight": total_weight,
            "items_analysis": items_analysis,
            "priority_order": priority_order,
            "high_priority_count": high_priority_count,
        }

    def get_content_strategy(self, chapter_name, score_item, weight):
        """
        根据章节+评分项+权重返回内容策略

        Args:
            chapter_name: 章节名称
            score_item: 评分项字典（含 name/title, score, sub_items 等）
            weight: 评分项分值/权重

        Returns:
            dict: {
                "must_have": 必须包含要素列表,
                "bonus": 加分项要素列表,
                "common_omissions": 常见遗漏要素列表,
                "structure_template": 高分内容结构模板,
                "detail_level": 建议内容深度,
                "max_pages": 页数上限,
                "focus_areas": 重点聚焦领域,
            }
        """
        # 从数据库匹配章节策略
        strategy = self._find_chapter_strategy(chapter_name)

        # 根据权重计算 detail_level 和页数上限
        total_weight = weight  # 单项权重作为参考
        # 如果 score_item 中有 total 信息，使用之；否则用自身权重估算
        detail_level = self.get_detail_level(weight, max(weight, 100))
        max_pages = self._get_max_pages(detail_level)

        # 根据评分项子项调整聚焦领域
        focus_areas = self._derive_focus_areas(score_item, strategy)

        return {
            "must_have": strategy.get("must_have", []),
            "bonus": strategy.get("bonus", []),
            "common_omissions": strategy.get("common_omissions", []),
            "structure_template": strategy.get("structure_template", ""),
            "detail_level": detail_level,
            "max_pages": max_pages,
            "focus_areas": focus_areas,
        }

    def get_detail_level(self, score_item_weight, total_weight):
        """
        根据权重占比返回 detail_level（1-5）

        规则：
        - 权重≥15%: detail_level=5, 页数上限35页
        - 权重10-15%: detail_level=4, 页数上限30页
        - 权重5-10%: detail_level=3, 页数上限25页
        - 权重＜5%: detail_level=2, 页数上限15页
        - 无评分项: detail_level=1, 页数上限10页

        Args:
            score_item_weight: 单个评分项的分值
            total_weight: 所有评分项的总分值

        Returns:
            int: detail_level (1-5)
        """
        if total_weight <= 0 or score_item_weight <= 0:
            return 1

        ratio = score_item_weight / total_weight

        if ratio >= 0.15:
            return 5
        elif ratio >= 0.10:
            return 4
        elif ratio >= 0.05:
            return 3
        else:
            return 2

    def get_must_have_content(self, chapter_name, project_type=None):
        """
        返回该章节必须包含的内容要素列表

        Args:
            chapter_name: 章节名称
            project_type: 工程类型（'construction' 或 'service'），
                          为 None 时使用初始化时的类型

        Returns:
            dict: {
                "must_have": 必须包含要素列表,
                "bonus": 加分项要素列表,
                "common_omissions": 常见遗漏要素列表,
                "structure_template": 高分内容结构模板,
                "structure_layers": 结构层次说明,
            }
        """
        db = self._db
        if project_type and project_type != self.project_type:
            db = (
                SERVICE_STRATEGY_DB
                if project_type == "service"
                else CONSTRUCTION_STRATEGY_DB
            )

        strategy = self._find_chapter_strategy_in_db(chapter_name, db)

        return {
            "must_have": strategy.get("must_have", []),
            "bonus": strategy.get("bonus", []),
            "common_omissions": strategy.get("common_omissions", []),
            "structure_template": strategy.get("structure_template", ""),
            "structure_layers": strategy.get("structure_layers", []),
        }

    # ── 兼容性方法 ────────────────────────────────────────────

    @staticmethod
    def detail_level_to_legacy(level):
        """
        将 5 级 detail_level 转换为原有 3 级体系

        映射规则：
        - 5 → 3 (完整版)
        - 4 → 3 (完整版)
        - 3 → 3 (完整版)
        - 2 → 2 (标准版)
        - 1 → 1 (精简版)

        Args:
            level: 5 级 detail_level (1-5)

        Returns:
            int: 3 级 detail_level (1-3)
        """
        mapping = {5: 3, 4: 3, 3: 3, 2: 2, 1: 1}
        return mapping.get(level, 2)

    def get_plan_info_for_chapter(self, chapter_name, score_item, total_weight):
        """
        生成可直接注入 ChapterInterface.plan_info 的策略信息

        此方法是集成的便捷入口，输出格式与 plan_chapters() 中
        plan_info 字段完全兼容。

        Args:
            chapter_name: 章节名称
            score_item: 评分项字典
            total_weight: 总权重/总分

        Returns:
            dict: 可直接作为 plan_info 传入章节实例的策略信息
        """
        weight = score_item.get("score", 0)
        weight_ratio = weight / total_weight if total_weight > 0 else 0
        detail_level = self.get_detail_level(weight, total_weight)
        max_pages = self._get_max_pages(detail_level)
        must_have_content = self.get_must_have_content(chapter_name)
        strategy = self.get_content_strategy(chapter_name, score_item, weight)

        return {
            "detail_level": detail_level,
            "detail_level_legacy": self.detail_level_to_legacy(detail_level),
            "max_pages": max_pages,
            "weight_ratio": round(weight_ratio, 4),
            "must_have": must_have_content["must_have"],
            "bonus": must_have_content["bonus"],
            "common_omissions": must_have_content["common_omissions"],
            "structure_template": must_have_content["structure_template"],
            "structure_layers": must_have_content["structure_layers"],
            "focus_areas": strategy.get("focus_areas", []),
        }

    # ── 内部方法 ──────────────────────────────────────────────

    def _find_chapter_strategy(self, chapter_name):
        """在当前类型的策略数据库中查找章节策略"""
        return self._find_chapter_strategy_in_db(chapter_name, self._db)

    @staticmethod
    def _find_chapter_strategy_in_db(chapter_name, db):
        """
        在指定策略数据库中查找章节策略

        匹配优先级：
        1. 精确匹配
        2. 章节名包含数据库key
        3. 数据库key包含章节名
        4. 关键词模糊匹配
        """
        if not chapter_name:
            return {}

        # 1. 精确匹配
        if chapter_name in db:
            return db[chapter_name]

        # 2. 章节名包含数据库key
        for key in db:
            if key in chapter_name:
                return db[key]

        # 3. 数据库key包含章节名核心词
        for key in db:
            if chapter_name[:4] in key:
                return db[key]

        # 4. 关键词模糊匹配
        best_match = None
        best_score = 0
        for key, keywords in CHAPTER_MATCH_KEYWORDS.items():
            if key not in db:
                continue
            for kw in keywords:
                if kw in chapter_name or chapter_name[:3] in kw:
                    score = len(kw)
                    if score > best_score:
                        best_score = score
                        best_match = key
                    break

        if best_match and best_match in db:
            return db[best_match]

        # 无匹配，返回空策略
        return {
            "must_have": [],
            "bonus": [],
            "common_omissions": [],
            "structure_template": "",
            "structure_layers": [],
        }

    def _match_chapter(self, score_item_name):
        """
        将评分项名称匹配到最相关的章节名

        匹配优先级：
        1. 章节名完全包含评分项名
        2. 评分项名完全包含章节名
        3. 关键词模糊匹配（优先匹配最具体的关键词）

        Args:
            score_item_name: 评分项名称

        Returns:
            str or None: 匹配到的章节名，未匹配返回 None
        """
        if not score_item_name:
            return None

        # 1. 章节名完全包含评分项名
        for chapter in self._db:
            if score_item_name in chapter or chapter in score_item_name:
                return chapter

        # 2. 关键词模糊匹配——多关键词匹配+覆盖率优先
        best_match = None
        best_score = 0

        for chapter, keywords in CHAPTER_MATCH_KEYWORDS.items():
            if chapter not in self._db:
                continue
            matched_count = 0
            max_kw_len = 0
            for kw in keywords:
                if kw in score_item_name:
                    matched_count += 1
                    max_kw_len = max(max_kw_len, len(kw))
            if matched_count > 0:
                # 评分：匹配关键词数量*10 + 最长关键词长度
                # 多关键词匹配优先，其次看关键词长度
                score = matched_count * 10 + max_kw_len
                if score > best_score:
                    best_score = score
                    best_match = chapter

        return best_match

    @staticmethod
    def _get_max_pages(detail_level):
        """
        根据 detail_level 返回页数上限

        Args:
            detail_level: 内容深度等级 (1-5)

        Returns:
            int: 页数上限
        """
        page_limits = {
            5: 35,
            4: 30,
            3: 25,
            2: 15,
            1: 10,
        }
        return page_limits.get(detail_level, 15)

    @staticmethod
    def _derive_focus_areas(score_item, strategy):
        """
        根据评分项子项和章节策略推导重点聚焦领域

        当评分项包含 sub_items/includes 时，将子项与策略中的
        must_have/bonus 进行匹配，输出最相关的聚焦领域。

        Args:
            score_item: 评分项字典
            strategy: 章节策略字典

        Returns:
            list: 聚焦领域列表
        """
        focus_areas = []

        # 从评分项子项中提取聚焦领域
        sub_items = score_item.get("sub_items", score_item.get("includes", []))
        if sub_items:
            for si in sub_items:
                if isinstance(si, str):
                    focus_areas.append(si)
                elif isinstance(si, dict):
                    content = si.get("content", si.get("name", ""))
                    if content:
                        focus_areas.append(content)

        # 如果没有子项，从策略的 must_have 中提取前3项作为聚焦领域
        if not focus_areas and strategy:
            must_have = strategy.get("must_have", [])
            focus_areas = must_have[:3]

        return focus_areas


# ══════════════════════════════════════════════════════════════════
# 便捷函数（可直接从模块导入使用）
# ══════════════════════════════════════════════════════════════════

def create_strategy(project_type="construction"):
    """
    创建评分策略实例的便捷函数

    Args:
        project_type: 'construction' 或 'service'

    Returns:
        ScoringStrategy 实例
    """
    return ScoringStrategy(project_type=project_type)


def analyze_and_plan(score_items, project_type="construction"):
    """
    一站式分析评分项并生成完整策略建议

    Args:
        score_items: 评分项列表
        project_type: 工程类型

    Returns:
        dict: analyze_score_items() 的完整输出
    """
    strategy = ScoringStrategy(project_type=project_type)
    return strategy.analyze_score_items(score_items)


# ══════════════════════════════════════════════════════════════════
# 自测
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("ScoringStrategy 自测")
    print("=" * 60)

    # 测试1：施工类评分项分析
    print("\n--- 测试1：施工类评分项分析 ---")
    construction_items = [
        {"title": "主要分项工程施工方案和技术措施", "score": 25},
        {"title": "施工安全措施", "score": 15},
        {"title": "质量保证措施和创优计划", "score": 15},
        {"title": "施工总进度计划及保障措施", "score": 10},
        {"title": "现场文明施工、消防以及环保方案", "score": 8},
        {"title": "现场组织管理机构", "score": 7},
        {"title": "施工现场总平面布置", "score": 5},
        {"title": "冬季和雨季施工方案", "score": 5},
        {"title": "成品保护和工程保修", "score": 4},
        {"title": "紧急情况的处理措施", "score": 3},
        {"title": "定位和测量放线", "score": 2},
        {"title": "总承包管理", "score": 1},
    ]

    cs = ScoringStrategy(project_type="construction")
    result = cs.analyze_score_items(construction_items)

    print(f"总分: {result['total_weight']}")
    print(f"高优先级(≥10%)评分项: {result['high_priority_count']}个")
    print(f"优先级排序: {result['priority_order']}")
    print()
    for item in result["items_analysis"]:
        print(
            f"  {item['name'][:20]:20s} | "
            f"权重{item['weight']:5.1f} | "
            f"占比{item['weight_ratio']*100:5.1f}% | "
            f"深度L{item['detail_level']} | "
            f"上限{item['max_pages']:2d}页 | "
            f"匹配→{item['chapter_match'] or '未匹配'}"
        )

    # 测试2：服务类评分项分析
    print("\n--- 测试2：服务类评分项分析 ---")
    service_items = [
        {"title": "总体服务方案", "score": 30},
        {"title": "重难点分析及解决方案", "score": 20},
        {"title": "服务质量保证方案", "score": 15},
        {"title": "设施日常维护方案", "score": 15},
        {"title": "人员、设备安排计划", "score": 10},
        {"title": "应急预案", "score": 6},
        {"title": "服务承诺", "score": 4},
    ]

    ss = ScoringStrategy(project_type="service")
    result2 = ss.analyze_score_items(service_items)

    print(f"总分: {result2['total_weight']}")
    print(f"高优先级(≥10%)评分项: {result2['high_priority_count']}个")
    print()
    for item in result2["items_analysis"]:
        print(
            f"  {item['name'][:20]:20s} | "
            f"权重{item['weight']:5.1f} | "
            f"占比{item['weight_ratio']*100:5.1f}% | "
            f"深度L{item['detail_level']} | "
            f"上限{item['max_pages']:2d}页"
        )

    # 测试3：内容策略获取
    print("\n--- 测试3：施工方案内容策略 ---")
    strategy = cs.get_content_strategy(
        "主要分项工程施工方案和技术措施",
        {"title": "施工方案", "score": 25},
        25,
    )
    print(f"结构模板: {strategy['structure_template']}")
    print(f"必须包含: {strategy['must_have']}")
    print(f"加分项: {strategy['bonus'][:3]}...")
    print(f"常见遗漏: {strategy['common_omissions'][:2]}...")

    # 测试4：必须内容要素
    print("\n--- 测试4：质量保证必须内容 ---")
    must_have = cs.get_must_have_content("质量保证措施和创优计划")
    print(f"必须包含({len(must_have['must_have'])}项):")
    for i, item in enumerate(must_have["must_have"], 1):
        print(f"  {i}. {item}")
    print(f"结构: {must_have['structure_layers']}")

    # 测试5：detail_level兼容性
    print("\n--- 测试5：detail_level 5级→3级兼容映射 ---")
    for level in range(1, 6):
        legacy = ScoringStrategy.detail_level_to_legacy(level)
        print(f"  L{level} → L{legacy}")

    # 测试6：plan_info生成（与现有架构集成）
    print("\n--- 测试6：plan_info生成 ---")
    plan_info = cs.get_plan_info_for_chapter(
        "施工安全措施",
        {"title": "施工安全措施", "score": 15},
        100,
    )
    print(f"  detail_level: {plan_info['detail_level']} (legacy: {plan_info['detail_level_legacy']})")
    print(f"  max_pages: {plan_info['max_pages']}")
    print(f"  weight_ratio: {plan_info['weight_ratio']}")
    print(f"  must_have: {plan_info['must_have'][:2]}...")
    print(f"  focus_areas: {plan_info['focus_areas'][:3]}...")

    print("\n" + "=" * 60)
    print("自测完成 ✓")
    print("=" * 60)
