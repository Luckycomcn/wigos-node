"""业务规则与受控词表的单元测试（不碰数据库）。

    python manage.py test api.tests_rules
"""
import copy
import json
from pathlib import Path

from django.test import SimpleTestCase

from . import rules
from .testing_utils import load_test_json

BASE = Path(__file__).resolve().parent.parent


class RuleSetTests(SimpleTestCase):
    def setUp(self):
        self.good = load_test_json("test_wmdrv2.json")

    def test_clean_record_passes(self):
        result = rules.check_record(self.good)
        self.assertTrue(result["ok"], msg=result["errors"])
        self.assertEqual(result["errors"], [])

    def test_missing_id_is_error(self):
        record = copy.deepcopy(self.good)
        del record["id"]
        result = rules.check_record(record)
        self.assertFalse(result["ok"])
        self.assertEqual([e["code"] for e in result["errors"]], ["wsi-present"])

    def test_date_established_after_created_is_error(self):
        record = copy.deepcopy(self.good)
        record["properties"]["dateEstablished"] = "2099-01-01"
        result = rules.check_record(record)
        self.assertFalse(result["ok"])
        self.assertIn("dates-in-order", [e["code"] for e in result["errors"]])

    def test_geometry_disagreeing_with_latlon_is_error(self):
        record = copy.deepcopy(self.good)
        record["properties"]["latitude"] = -23.0
        record["properties"]["longitude"] = 22.0
        record["geometry"] = {"type": "Point", "coordinates": [100.0, 50.0]}
        result = rules.check_record(record)
        self.assertIn("geometry-matches-coordinates", [e["code"] for e in result["errors"]])

    def test_latitude_out_of_range_is_error(self):
        record = copy.deepcopy(self.good)
        record["properties"]["latitude"] = 999
        result = rules.check_record(record)
        self.assertIn("lat-lon-range", [e["code"] for e in result["errors"]])

    def test_unknown_codelist_concept_is_error(self):
        """GOS 不是 WMDS 里的概念（正式写法是 GOSGeneral）——正是 ETS 抓到过的。"""
        record = copy.deepcopy(self.good)
        record["properties"]["observations"][0]["programAffiliations"][0]["programAffiliation"]["id"] = "GOS"
        result = rules.check_record(record)
        self.assertIn("codelisted-values", [e["code"] for e in result["errors"]])
        messages = " ".join(
            m for e in result["errors"] if e["code"] == "codelisted-values" for m in e["messages"]
        )
        self.assertIn("GOS", messages)

    def test_known_codelist_concepts_pass(self):
        """把 GOS 换成正式概念后，同一条规则应当放行。"""
        record = copy.deepcopy(self.good)
        record["properties"]["observations"][0]["programAffiliations"][0]["programAffiliation"]["id"] = "GOSGeneral"
        result = rules.check_record(record)
        self.assertNotIn("codelisted-values", [e["code"] for e in result["errors"]])

    def test_missing_observation_is_warning_not_error(self):
        record = copy.deepcopy(self.good)
        record["properties"]["observations"] = []
        result = rules.check_record(record)
        self.assertTrue(result["ok"])
        self.assertIn("has-observation", [w["code"] for w in result["warnings"]])

    def test_missing_contact_is_warning(self):
        record = copy.deepcopy(self.good)
        record["properties"]["contacts"] = []
        result = rules.check_record(record)
        self.assertIn("has-contact", [w["code"] for w in result["warnings"]])

    def test_non_dict_record_does_not_crash(self):
        result = rules.check_record("not a record")
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["code"], "wsi-present")

    def test_every_rule_has_a_code_and_severity(self):
        for rule in rules.RULES:
            self.assertTrue(rule.code)
            self.assertIn(rule.severity, ("error", "warning"))
            self.assertTrue(rule.title)

    def test_rule_codes_are_unique(self):
        codes = rules.rule_codes()
        self.assertEqual(len(codes), len(set(codes)))
