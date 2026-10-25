"""方案 5.6 工作流的状态解析与校验口径。

刻意不加数据库依赖：这套逻辑决定了「什么算草稿、草稿能不能带着问题落库」，
是纯函数。落库后的生命周期（提交/发布互拒）在 tests_draft.py 里，需要 PostGIS。
"""
import copy

from django.test import SimpleTestCase, override_settings

from . import stations
from .models import Station
from .testing_utils import load_test_json


class ResolveStatusTests(SimpleTestCase):
    @override_settings(STATION_DEFAULT_STATUS="submitted")
    def test_explicit_status_wins(self):
        self.assertEqual(stations.resolve_status(Station.DRAFT), Station.DRAFT)
        self.assertEqual(stations.resolve_status(Station.SUBMITTED), Station.SUBMITTED)

    def test_defaults_to_submitted_so_existing_flows_are_unchanged(self):
        self.assertEqual(stations.resolve_status(None), Station.SUBMITTED)
        self.assertEqual(stations.resolve_status(), Station.SUBMITTED)

    @override_settings(STATION_DEFAULT_STATUS="draft")
    def test_deployment_can_force_draft_first(self):
        """同一份代码跑「提交才可发布」的生产形态，靠配置而不是改代码。"""
        self.assertEqual(stations.resolve_status(None), Station.DRAFT)

    @override_settings(STATION_DEFAULT_STATUS="wat")
    def test_bogus_config_falls_back_rather_than_persisting_junk(self):
        with self.assertLogs("api.stations", level="WARNING"):
            self.assertEqual(stations.resolve_status(None), Station.SUBMITTED)

    def test_unknown_requested_value_falls_back(self):
        with self.assertLogs("api.stations", level="WARNING"):
            self.assertEqual(stations.resolve_status("pending"), Station.SUBMITTED)


class ValidateStrictnessTests(SimpleTestCase):
    def setUp(self):
        self.record = load_test_json("test_wmdrv2.json")

    def test_valid_record_has_no_problems(self):
        self.assertEqual(stations.validate(self.record, strict=False), [])

    def test_non_strict_returns_problems_instead_of_raising(self):
        """草稿的立身之本：能存，同时把缺什么告诉用户。

        properties.title 是 WMDR2 schema 的必填项，拿它做样本正好体现
        「必填缺失 → 草稿可存、提交不可」这套分工。
        """
        broken = copy.deepcopy(self.record)
        del broken["properties"]["title"]
        problems = stations.validate(broken, strict=False)
        self.assertTrue(problems)
        self.assertTrue(any("title" in p for p in problems))

    def test_strict_still_raises(self):
        broken = copy.deepcopy(self.record)
        del broken["properties"]["title"]
        with self.assertRaises(stations.StationError):
            stations.validate(broken)

    def test_strict_raises_matches_legacy_default_call(self):
        """不带参数调用必须保持原有严格行为，否则老调用点会静默放过坏数据。"""
        self.assertEqual(stations.validate(self.record), [])

    def test_non_object_record(self):
        self.assertTrue(stations.validate([1, 2], strict=False))
        with self.assertRaises(stations.StationError):
            stations.validate([1, 2])
