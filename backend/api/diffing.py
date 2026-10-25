"""WMDR2 记录的扁平化与差异对比（F-8 "变更对比"）。

纯函数、不依赖 Django 模型，因此可以在没有数据库的机器上直接单测：

    from api.diffing import diff_records
    diff_records(old_record, new_record)
"""
from typing import Any, Dict, List

__all__ = ["flatten", "diff_records", "summarise"]


def flatten(record: Any, prefix: str = "") -> Dict[str, Any]:
    """把嵌套 dict/list 拍平成 `path -> 叶子值`。

    路径约定与前端表单一致：``a.b``、``items[0].name``。
    空 dict / 空 list 也作为叶子，否则"字段被清空"会表现为"字段消失"。
    """
    out: Dict[str, Any] = {}
    _flatten_into(record, prefix, out)
    return out


def _flatten_into(value: Any, path: str, out: Dict[str, Any]) -> None:
    if isinstance(value, dict):
        if not value:
            out[path] = {}
            return
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            _flatten_into(item, child, out)
        return
    if isinstance(value, (list, tuple)):
        if not value:
            out[path] = []
            return
        for index, item in enumerate(value):
            _flatten_into(item, f"{path}[{index}]", out)
        return
    out[path] = value


def diff_records(old: Any, new: Any) -> Dict[str, Any]:
    """对比两个记录，返回新增 / 删除 / 修改三类路径级差异。

    数组按索引对齐：位置 i 的内容变了算 changed，数组变长算 added，
    变短算 removed。这比"按内容匹配"更贴近"这条记录的第三位联系人换了电话"
    这类真实改动，也不会把重排误判成大面积修改。
    """
    before = flatten(old)
    after = flatten(new)

    added: List[Dict[str, Any]] = [
        {"path": path, "value": after[path]} for path in after if path not in before
    ]
    removed: List[Dict[str, Any]] = [
        {"path": path, "value": before[path]} for path in before if path not in after
    ]
    changed: List[Dict[str, Any]] = [
        {"path": path, "from": before[path], "to": after[path]}
        for path in after
        if path in before and not _same(before[path], after[path])
    ]

    result = {
        "added": added,
        "removed": removed,
        "changed": changed,
        "summary": summarise(before, after, added, removed, changed),
    }
    return result


def summarise(
    before: Dict[str, Any],
    after: Dict[str, Any],
    added: List[Dict[str, Any]],
    removed: List[Dict[str, Any]],
    changed: List[Dict[str, Any]],
) -> Dict[str, int]:
    total = len(set(before) | set(after))
    touched = len({item["path"] for item in added} | {item["path"] for item in removed} | {item["path"] for item in changed})
    return {
        "added": len(added),
        "removed": len(removed),
        "changed": len(changed),
        "unchanged": max(total - touched, 0),
    }


def _same(left: Any, right: Any) -> bool:
    """叶子相等判断。

    `bool` 是 `int` 的子类，直接 `==` 会把 `False` 和 `0` 判成相等，
    在元数据里这是两个完全不同的值，必须显式区分。
    """
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    return left == right
