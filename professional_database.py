"""
ProfessionalDatabase - 施工行业专业数据库 v1.0
为标书生成提供专业深度内容，与 bid_technical 章节代码兼容。

数据库包含：
1. CONSTRUCTION_METHODS - 施工工法库（装饰装修7大类+外立面排危）
2. QUALITY_STANDARDS    - 质量标准库（GB国标分类索引）
3. EQUIPMENT_DATABASE   - 设备配置库（按工程类型/规模推荐）
4. SAFETY_MEASURES      - 安全措施库（脚手架/高处作业/临时用电/消防）
5. COMMON_DEFECTS       - 质量通病库（8大类通病防治）

生成方法：
- get_method_content(method_name, detail_level) → 返回指定深度的工法内容
- get_quality_standard(standard_id) → 返回标准详情
- get_equipment_list(project_type, area) → 返回设备配置
- get_defect_content(defect_type) → 返回通病防治内容
"""


# v8.0: 静态数据已拆分至 db_data.py
from db_data import (
    CONSTRUCTION_METHODS,
    QUALITY_STANDARDS,
    EQUIPMENT_DATABASE,
    SAFETY_MEASURES,
    COMMON_DEFECTS,
)

class ProfessionalDatabase:
    """施工行业专业数据库"""

    # v8.0: 数据定义已移至 db_data.py，此处通过类属性引用保持接口兼容
    CONSTRUCTION_METHODS = CONSTRUCTION_METHODS
    QUALITY_STANDARDS = QUALITY_STANDARDS
    EQUIPMENT_DATABASE = EQUIPMENT_DATABASE
    SAFETY_MEASURES = SAFETY_MEASURES
    COMMON_DEFECTS = COMMON_DEFECTS

    # ══════════════════════════════════════════════════════════════
    # 生成方法
    # ══════════════════════════════════════════════════════════════

    def get_method_content(self, method_name, detail_level=2):
        """
        返回指定深度的工法内容

        Args:
            method_name: 工法名称，如"抹灰工程"、"涂料工程"等
            detail_level: 内容深度等级
                1 = 精简版（仅工序流程概要）
                2 = 标准版（工序流程+质量控制点+验收标准）
                3 = 完整版（全部内容含通病防治详表）

        Returns:
            dict: 工法内容字典，包含 process_flow / quality_control_points /
                  acceptance_standards / common_defects_prevention（按detail_level）
        """
        method = self.CONSTRUCTION_METHODS.get(method_name)
        if not method:
            return {"error": f"未找到工法：{method_name}", "available": list(self.CONSTRUCTION_METHODS.keys())}

        result = {
            "method_name": method_name,
            "category": method.get("category", ""),
            "process_flow": method.get("process_flow", [])
        }

        if detail_level >= 2:
            result["quality_control_points"] = method.get("quality_control_points", [])
            result["acceptance_standards"] = method.get("acceptance_standards", [])

        if detail_level >= 3:
            result["common_defects_prevention"] = method.get("common_defects_prevention", [])

        return result

    def get_quality_standard(self, standard_id):
        """
        返回标准详情

        Args:
            standard_id: 标准编号，如"GB50210-2018"、"GB50300-2013"等

        Returns:
            dict: 标准详情字典，包含 full_name / scope / key_indicators /
                  inspection_methods / acceptance_criteria
        """
        # 支持多种写法：GB50210-2018 / GB 50210-2018 / gb50210
        normalized = standard_id.upper().replace(" ", "").replace("－", "-")
        standard = self.QUALITY_STANDARDS.get(normalized)
        if not standard:
            # 尝试模糊匹配
            for key, val in self.QUALITY_STANDARDS.items():
                if normalized in key.upper().replace(" ", ""):
                    standard = val
                    break
        if not standard:
            return {"error": f"未找到标准：{standard_id}", "available": list(self.QUALITY_STANDARDS.keys())}
        return standard

    def get_equipment_list(self, project_type, area=0):
        """
        返回设备配置清单

        Args:
            project_type: 工程类型，如"装饰装修"、"外立面排危"
            area: 工程面积（m²），用于按规模选择设备清单和计算数量

        Returns:
            dict: 设备配置字典，包含 area_range / equipment 列表（数量已计算）
        """
        type_data = self.EQUIPMENT_DATABASE.get(project_type)
        if not type_data:
            return {"error": f"未找到工程类型：{project_type}", "available": list(self.EQUIPMENT_DATABASE.keys())}

        # 按面积选择规模等级
        area_num = float(area) if area else 0
        if area_num <= 5000:
            scale = "small"
        elif area_num <= 20000:
            scale = "medium"
        else:
            scale = "large"

        # 外立面排危面积阈值不同
        if project_type == "外立面排危":
            if area_num <= 3000:
                scale = "small"
            elif area_num <= 10000:
                scale = "medium"
            else:
                scale = "large"

        scale_data = type_data.get(scale, {})
        equipment_list = []

        for eq in scale_data.get("equipment", []):
            # 计算数量（使用安全求值替代eval）
            qty_formula = eq.get("qty_formula", "1")
            try:
                from safe_eval import safe_eval
                qty = safe_eval(qty_formula, {"area": area_num, "max": max, "min": min})
                qty = max(1, int(round(qty)))
            except Exception:
                qty = 1

            equipment_list.append({
                "name": eq.get("name", ""),
                "model": eq.get("model", ""),
                "quantity": qty,
                "unit": eq.get("unit", "台"),
                "power": eq.get("power", ""),
                "note": eq.get("note", "")
            })

        return {
            "project_type": project_type,
            "area": area_num,
            "scale": scale,
            "area_range": scale_data.get("area_range", ""),
            "equipment": equipment_list
        }

    def get_defect_content(self, defect_type):
        """
        返回通病防治内容

        Args:
            defect_type: 通病类型，如"墙面空鼓"、"裂缝"、"色差"等
                         也支持模糊匹配，如"空鼓"匹配"墙面空鼓"

        Returns:
            dict: 通病防治内容字典，包含 defect_type / category / description /
                  causes / prevention_measures / inspection_method / standard_reference
        """
        # 精确匹配
        defect = self.COMMON_DEFECTS.get(defect_type)
        if defect:
            return defect

        # 模糊匹配
        for key, val in self.COMMON_DEFECTS.items():
            if defect_type in key or key in defect_type:
                return val

        return {"error": f"未找到通病类型：{defect_type}", "available": list(self.COMMON_DEFECTS.keys())}

    # ══════════════════════════════════════════════════════════════
    # 格式化输出方法（与 self.fmt.body() 等调用兼容）
    # ══════════════════════════════════════════════════════════════

    def render_method_to_formatter(self, fmt, method_name, detail_level=2):
        """
        将工法内容直接渲染到 formatter，与现有章节代码 self.fmt 调用兼容

        Args:
            fmt: 格式化引擎（NormalFormatter 实例）
            method_name: 工法名称
            detail_level: 内容深度等级 1/2/3
        """
        content = self.get_method_content(method_name, detail_level)
        if "error" in content:
            fmt.body(content["error"])
            return

        # 工序流程
        if content.get("process_flow"):
            fmt.h3("施工工艺流程")
            flow = content["process_flow"]
            fmt.body("→".join([f.split("：")[0] if "：" in f else f.split(":")[0] if ":" in f else f for f in flow]))
            if detail_level >= 2:
                for i, step in enumerate(flow, 1):
                    fmt.body(f"（{i}）{step}")

        # 质量控制点
        if detail_level >= 2 and content.get("quality_control_points"):
            fmt.h3("施工质量控制要点")
            for i, pt in enumerate(content["quality_control_points"], 1):
                fmt.body(f"{i}、{pt}")

        # 验收标准表
        if detail_level >= 2 and content.get("acceptance_standards"):
            fmt.h3("质量验收标准")
            headers = ["检查项目", "质量要求", "检验方法", "执行标准"]
            rows = []
            for std in content["acceptance_standards"]:
                rows.append([
                    std.get("item", ""),
                    std.get("requirement", ""),
                    std.get("method", ""),
                    std.get("standard_id", "")
                ])
            fmt.table(headers, rows)

        # 通病防治表
        if detail_level >= 3 and content.get("common_defects_prevention"):
            fmt.h3("质量通病防治")
            headers = ["通病类型", "产生原因", "防治措施"]
            rows = []
            for d in content["common_defects_prevention"]:
                rows.append([
                    d.get("defect", ""),
                    d.get("cause", ""),
                    d.get("prevention", "")
                ])
            fmt.table(headers, rows)

    def render_defect_to_formatter(self, fmt, defect_type):
        """
        将通病防治内容渲染到 formatter

        Args:
            fmt: 格式化引擎（NormalFormatter 实例）
            defect_type: 通病类型
        """
        content = self.get_defect_content(defect_type)
        if "error" in content:
            fmt.body(content["error"])
            return

        fmt.h3(f"{content.get('defect_type', defect_type)}防治")

        # 原因分析
        if content.get("causes"):
            fmt.h4("原因分析")
            for i, cause in enumerate(content["causes"], 1):
                fmt.body(f"{i}、{cause}")

        # 防治措施
        if content.get("prevention_measures"):
            fmt.h4("防治措施")
            for i, measure in enumerate(content["prevention_measures"], 1):
                fmt.body(f"{i}、{measure}")

        # 检查方法
        if content.get("inspection_method"):
            fmt.h4("检查方法")
            fmt.body(content["inspection_method"])

        # 标准依据
        if content.get("standard_reference"):
            fmt.h4("标准依据")
            fmt.body(content["standard_reference"])

    def render_equipment_to_formatter(self, fmt, project_type, area=0):
        """
        将设备配置清单渲染到 formatter

        Args:
            fmt: 格式化引擎（NormalFormatter 实例）
            project_type: 工程类型
            area: 工程面积（m²）
        """
        result = self.get_equipment_list(project_type, area)
        if "error" in result:
            fmt.body(result["error"])
            return

        fmt.h3(f"拟投入的主要施工机械设备表（{result.get('area_range', '')}）")
        headers = ["序号", "机械或设备名称", "型号规格", "数量", "单位", "额定功率", "备注"]
        rows = []
        for i, eq in enumerate(result.get("equipment", []), 1):
            rows.append([
                str(i),
                eq.get("name", ""),
                eq.get("model", ""),
                str(eq.get("quantity", 1)),
                eq.get("unit", "台"),
                eq.get("power", ""),
                eq.get("note", "")
            ])
        fmt.table(headers, rows)

    def render_safety_to_formatter(self, fmt, safety_type, sub_type=None):
        """
        将安全措施内容渲染到 formatter

        Args:
            fmt: 格式化引擎（NormalFormatter 实例）
            safety_type: 安全措施类型，如"脚手架安全"、"高处作业"、"临时用电"、"消防安全"
            sub_type: 子类型（如脚手架类型），为None则输出全部子类型
        """
        data = self.SAFETY_MEASURES.get(safety_type)
        if not data:
            fmt.body(f"未找到安全措施类型：{safety_type}")
            return

        if safety_type == "脚手架安全":
            items = {sub_type: data[sub_type]} if sub_type and sub_type in data else data
            for scaffold_type, scaffold_data in items.items():
                fmt.h3(f"{scaffold_type}安全要点")
                fmt.body(f"适用范围：{scaffold_data.get('applicable', '')}")
                if scaffold_data.get("key_points"):
                    for i, pt in enumerate(scaffold_data["key_points"], 1):
                        fmt.body(f"{i}、{pt}")
                if scaffold_data.get("acceptance_items"):
                    fmt.body(f"验收要点：{'、'.join(scaffold_data['acceptance_items'])}")

        elif safety_type == "高处作业":
            fmt.h3("高处作业分级防护标准")
            if data.get("分级标准"):
                headers = ["作业级别", "作业高度", "防护标准"]
                rows = [[lv["level"], lv["height"], lv["protection"]] for lv in data["分级标准"]]
                fmt.table(headers, rows)
            if data.get("基本要求"):
                fmt.h4("基本要求")
                for i, req in enumerate(data["基本要求"], 1):
                    fmt.body(f"{i}、{req}")

        elif safety_type == "临时用电":
            fmt.h3("临时用电安全技术要点")
            if data.get("三级配电二级保护"):
                headers = ["配电级别", "名称", "配置要求"]
                rows = [[lv["level"], lv["name"], lv["requirement"]] for lv in data["三级配电二级保护"]]
                fmt.table(headers, rows)
            if data.get("基本要求"):
                fmt.h4("基本要求")
                for i, req in enumerate(data["基本要求"], 1):
                    fmt.body(f"{i}、{req}")

        elif safety_type == "消防安全":
            fmt.h3("消防安全管理要点")
            if data.get("动火审批"):
                fmt.h4("动火审批分级")
                headers = ["动火级别", "适用范围", "审批权限", "防护措施"]
                rows = [[lv["level"], lv["scope"], lv["approver"], lv["measures"]] for lv in data["动火审批"]]
                fmt.table(headers, rows)
            if data.get("灭火器配置"):
                fmt.h4("灭火器配置标准")
                headers = ["灭火器类型", "适用范围", "规格", "配置数量", "备注"]
                rows = [[fp["type"], fp["applicable"], fp["spec"], fp["qty"], fp["note"]] for fp in data["灭火器配置"]]
                fmt.table(headers, rows)


# ══════════════════════════════════════════════════════════════
# 模块级便捷实例
# ══════════════════════════════════════════════════════════════
_db_instance = None


def get_database():
    """获取数据库单例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = ProfessionalDatabase()
    return _db_instance


def get_method_content(method_name, detail_level=2):
    """便捷方法：获取工法内容"""
    return get_database().get_method_content(method_name, detail_level)


def get_quality_standard(standard_id):
    """便捷方法：获取标准详情"""
    return get_database().get_quality_standard(standard_id)


def get_equipment_list(project_type, area=0):
    """便捷方法：获取设备配置"""
    return get_database().get_equipment_list(project_type, area)


def get_defect_content(defect_type):
    """便捷方法：获取通病防治内容"""
    return get_database().get_defect_content(defect_type)
