"""PersistenceMixin — 文档保存与获取。

拆分自原 formatter.py v7.0 NormalFormatter。
"""


class PersistenceMixin:
    """文档持久化方法。"""

    def save(self, path: str) -> None:
        """保存文档。"""
        self.doc.save(path)

    def get_document(self):
        """获取文档对象（用于合并）。"""
        return self.doc
