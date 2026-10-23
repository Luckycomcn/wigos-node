"""diffing 的单元测试。

纯函数、不碰数据库，任何装了 Django 的机器都能跑：
    python manage.py test api.tests_diffing
"""
from django.test import SimpleTestCase

from .diffing import diff_records, flatten


class FlattenTests(SimpleTestCase):
    def test_nested_paths(self):
        flat = flatten({"a": {"b": {"c": 1}}, "d": [10, 20]})
        self.assertEqual(flat, {"a.b.c": 1, "d[0]": 10, "d[1]": 20})

    def test_empty_containers_are_leaves(self):
        """空 dict/list 是叶子，否则"字段被清空"会被误判成"字段消失"。"""
        flat = flatten({"a": {}, "b": []})
        self.assertEqual(flat, {"a": {}, "b": []})

    def test_scalar_values_pass_through(self):
        flat = flatten({"n": None, "t": True, "f": False, "z": 0, "s": ""})
        self.assertEqual(flat, {"n": None, "t": True, "f": False, "z": 0, "s": ""})


class DiffTests(SimpleTestCase):
    def test_added_removed_changed(self):
        old = {"id": "0-1-2-3", "properties": {"name": "旧名", "extra": "要删的"}}
        new = {"id": "0-1-2-3", "properties": {"name": "新名", "added": "新的"}}

        result = diff_records(old, new)

        self.assertEqual([item["path"] for item in result["changed"]], ["properties.name"])
        self.assertEqual(result["changed"][0]["from"], "旧名")
        self.assertEqual(result["changed"][0]["to"], "新名")
        self.assertEqual([item["path"] for item in result["added"]], ["properties.added"])
        self.assertEqual([item["path"] for item in result["removed"]], ["properties.extra"])
        self.assertEqual(result["summary"], {"added": 1, "removed": 1, "changed": 1, "unchanged": 1})

    def test_identical_records_have_no_differences(self):
        record = {"id": "0-1-2-3", "properties": {"name": "same"}}
        result = diff_records(record, dict(record))
        self.assertEqual(result["summary"], {"added": 0, "removed": 0, "changed": 0, "unchanged": 2})

    def test_array_append_and_shrink(self):
        old = {"items": [1, 2, 3]}
        new = {"items": [1, 2]}

        result = diff_records(old, new)
        self.assertEqual([i["path"] for i in result["removed"]], ["items[2]"])
        self.assertEqual(result["summary"]["removed"], 1)

        result = diff_records(new, old)
        self.assertEqual([i["path"] for i in result["added"]], ["items[2]"])

    def test_array_element_change_is_positional(self):
        old = {"items": [{"n": "a"}, {"n": "b"}]}
        new = {"items": [{"n": "b"}, {"n": "a"}]}

        result = diff_records(old, new)
        # 重排在"按位置对齐"下表现为两处修改，而不是整段增删
        self.assertEqual(sorted(i["path"] for i in result["changed"]), ["items[0].n", "items[1].n"])

    def test_bool_is_not_zero(self):
        """bool 是 int 子类，直接 == 会把 False 和 0 判成相等。"""
        result = diff_records({"a": False}, {"a": 0})
        self.assertEqual(len(result["changed"]), 1)
        result = diff_records({"a": 0}, {"a": False})
        self.assertEqual(len(result["changed"]), 1)
        result = diff_records({"a": True}, {"a": True})
        self.assertEqual(len(result["changed"]), 0)

    def test_cleared_container_shows_as_removed_plus_empty(self):
        """{"a": {"b": 1}} -> {"a": {}}：a.b 消失，同时 a 变成空容器叶子。

        这不是 changed，因为扁平化之后两个路径本来就不同；保留两条记录比
        "只报 removed"信息更全（能看出 a 还在，只是内容被清空了）。
        """
        result = diff_records({"a": {"b": 1}}, {"a": {}})
        self.assertEqual([i["path"] for i in result["removed"]], ["a.b"])
        self.assertEqual([i["path"] for i in result["added"]], ["a"])
        self.assertEqual(result["added"][0]["value"], {})

    def test_empty_to_none_is_changed(self):
        result = diff_records({"a": []}, {"a": None})
        self.assertEqual(len(result["changed"]), 1)
