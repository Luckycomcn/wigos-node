"""WSI 解析与授权区间覆盖的单元测试（不碰数据库）。

    python manage.py test api.tests_wsi
"""
from django.test import SimpleTestCase

from .models import WsiAllocation
from .wsi import format_wsi, is_well_formed, normalise_wsi, parse_wsi


class ParseWsiTests(SimpleTestCase):
    def test_four_segment_identifier(self):
        self.assertEqual(parse_wsi("0-20000-0-123456"), (20000, 0, 123456, None))

    def test_local_extension_is_kept(self):
        self.assertEqual(parse_wsi("0-20000-0-123456-localA"), (20000, 0, 123456, "localA"))

    def test_surrounding_whitespace_tolerated(self):
        self.assertEqual(parse_wsi("  0-20000-0-123456  "), (20000, 0, 123456, None))

    def test_empty_local_segment_is_dropped(self):
        """末尾一个空的 '-' 不该产生空字符串 local。"""
        self.assertEqual(parse_wsi("0-20000-0-123456-"), (20000, 0, 123456, None))

    def test_rejects_non_wigos_scheme(self):
        self.assertIsNone(parse_wsi("1-20000-0-123456"))

    def test_rejects_wrong_segment_count(self):
        self.assertIsNone(parse_wsi("20000-0-123456"))
        self.assertIsNone(parse_wsi("0-20000-0-123456-a-b"))

    def test_rejects_non_numeric_segments(self):
        self.assertIsNone(parse_wsi("0-20x00-0-123456"))
        self.assertIsNone(parse_wsi("0-20000-x-123456"))

    def test_rejects_negative_segments(self):
        self.assertIsNone(parse_wsi("0--1-0-123456"))

    def test_rejects_non_string_input(self):
        self.assertIsNone(parse_wsi(20000))
        self.assertIsNone(parse_wsi(None))
        self.assertIsNone(parse_wsi(["0-20000-0-123456"]))

    def test_well_formed_helper(self):
        self.assertTrue(is_well_formed("0-20000-0-1"))
        self.assertFalse(is_well_formed("not-a-wsi"))

    def test_normalise_round_trip(self):
        self.assertEqual(normalise_wsi("0-20000-0-123456"), "0-20000-0-123456")
        self.assertEqual(normalise_wsi(" 0-20000-0-123456 "), "0-20000-0-123456")
        self.assertEqual(normalise_wsi("0-20000-0-123456-"), "0-20000-0-123456")
        self.assertIsNone(normalise_wsi("bad"))

    def test_format_wsi(self):
        self.assertEqual(format_wsi(20000, 0, 5), "0-20000-0-5")
        self.assertEqual(format_wsi(20000, 0, 5, "L1"), "0-20000-0-5-L1")


class AllocationCoversTests(SimpleTestCase):
    def setUp(self):
        # 20000 号段 0..999999，2026 系列单开一个窄区间
        self.wide = WsiAllocation(issuer_identifier=20000, series=0, number_low=0, number_high=999999)
        self.narrow = WsiAllocation(issuer_identifier=20000, series=1, number_low=10, number_high=20)

    def test_inside_range(self):
        self.assertTrue(self.wide.covers("0-20000-0-123456"))
        self.assertTrue(self.narrow.covers("0-20000-1-15"))

    def test_boundaries_are_inclusive(self):
        self.assertTrue(self.narrow.covers("0-20000-1-10"))
        self.assertTrue(self.narrow.covers("0-20000-1-20"))

    def test_outside_range(self):
        self.assertFalse(self.narrow.covers("0-20000-1-9"))
        self.assertFalse(self.narrow.covers("0-20000-1-21"))

    def test_wrong_issuer(self):
        self.assertFalse(self.wide.covers("0-20001-0-123456"))

    def test_wrong_series(self):
        self.assertFalse(self.narrow.covers("0-20000-0-15"))

    def test_local_extension_does_not_affect_range(self):
        self.assertTrue(self.narrow.covers("0-20000-1-15-anything"))

    def test_malformed_wsi_never_covers(self):
        self.assertFalse(self.wide.covers("garbage"))
        self.assertFalse(self.wide.covers("0-20000-0"))

    def test_export_dict_shape(self):
        self.assertEqual(
            self.narrow.as_export_dict(),
            {"issuer": 20000, "series": 1, "numberFrom": 10, "numberTo": 20, "note": ""},
        )
