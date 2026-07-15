"""
ChapterRegistry - 章节注册表
支持动态加载章节类和路由
"""
import json
import os
from importlib import import_module


class ChapterRegistry:
    """章节注册表"""
    
    def __init__(self, registry_path=None):
        """
        初始化注册表
        
        Args:
            registry_path: 注册表JSON文件路径
        """
        self.registry = {}
        self.route_priority = []
        self.routes = {}
        
        if registry_path and os.path.exists(registry_path):
            self.load(registry_path)
    
    def load(self, registry_path):
        """从JSON文件加载注册表"""
        with open(registry_path, 'r', encoding='utf-8') as f:
            self.registry = json.load(f)
        
        # 构建路由表和优先级
        self._build_routes()
    
    def _build_routes(self):
        """构建路由表"""
        self.routes = {}
        self.route_priority = []
        
        # 递归遍历注册表
        def traverse(data, path=''):
            for key, value in data.items():
                if isinstance(value, dict):
                    if 'module' in value and 'class' in value:
                        # 章节注册项
                        self.routes[key] = {
                            'module': value['module'],
                            'class': value['class'],
                            'l3_titles': value.get('l3_titles', []),
                            'priority': value.get('priority', 5),
                        }
                    else:
                        # 继续递归
                        traverse(value, f"{path}.{key}" if path else key)
        
        traverse(self.registry)
        
        # 按优先级排序
        self.route_priority = sorted(
            self.routes.keys(),
            key=lambda k: self.routes[k].get('priority', 5),
            reverse=True
        )
    
    def get_route(self, keyword):
        """
        根据关键词获取路由信息
        
        Args:
            keyword: 章节关键词
            
        Returns:
            路由信息字典或None
        """
        # 按优先级匹配
        for k in self.route_priority:
            if k in keyword:
                return self.routes[k]
        return None
    
    def dispatch(self, keyword):
        """
        根据关键词分发到对应章节类
        
        Args:
            keyword: 章节关键词
            
        Returns:
            ChapterInterface子类实例或None
        """
        route = self.get_route(keyword)
        if not route:
            return None
        
        try:
            module = import_module(route['module'])
            cls = getattr(module, route['class'])
            return cls
        except (ImportError, AttributeError):
            return None
    
    def get_l3_titles(self, keyword):
        """获取三级标题列表"""
        route = self.get_route(keyword)
        if route:
            return route.get('l3_titles', [])
        return []
    
    def get_all_chapters(self, bid_type='technical', bid_section='construction'):
        """获取指定类型的所有章节"""
        chapters = []
        
        # 递归获取章节
        def traverse(data):
            for key, value in data.items():
                if isinstance(value, dict):
                    if 'module' in value and 'class' in value:
                        chapters.append({
                            'name': key,
                            'module': value['module'],
                            'class': value['class'],
                            'l3_titles': value.get('l3_titles', []),
                            'priority': value.get('priority', 5),
                        })
                    else:
                        traverse(value)
        
        if bid_type in self.registry:
            traverse(self.registry[bid_type].get(bid_section, {}))
        
        return sorted(chapters, key=lambda x: x['priority'], reverse=True)
