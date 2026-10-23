"""F-9 自检端点的测试（不碰数据库）。

    python manage.py test api.tests_checks
"""
import copy
from unittest import mock

from django.test import SimpleTestCase
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory

from .checks import ValidateView, check_one
from .testing_utils import load_test_json


class CheckOneTests(SimpleTestCase):
    def setUp(self):
        self.good = load_test_json("test_wmdrv2.json")

    def test_clean_record(self):
        result = check_one(self.good)
        self.assertTrue(result["ok"])
        self.assertEqual(result["errors"], [])
        self.assertIsNone(result.get("ets"))  # 默认不跑 ETS

    def test_bad_record_reports_errors(self):
        record = copy.deepcopy(self.good)
        record["properties"]["latitude"] = 999
        result = check_one(record)
        self.assertFalse(result["ok"])
        self.assertIn("lat-lon-range", [e["code"] for e in result["errors"]])

    def test_ets_request_falls_back_when_unavailable(self):
        """本机 Python 3.11 装不了 pywmdr，正好验证降级路径不会炸。"""
        result = check_one(self.good, run_ets=True)
        self.assertTrue(result["ok"])
        self.assertIn("ets", result)
        if not result["ets"].get("available"):
            self.assertIn("reason", result["ets"])


class ValidateViewTests(SimpleTestCase):
    def setUp(self):
        self.good = load_test_json("test_wmdrv2.json")
        self.factory = APIRequestFactory()

    def post(self, payload):
        """直接打视图。用 mock 临时放开鉴权——这些用例关注的是校验逻辑本身，
        认证由 tests_api.py 里带数据库的那批用例覆盖。"""
        request = self.factory.post("/api/validate/", payload, format="json")
        with mock.patch.object(ValidateView, "permission_classes", [AllowAny]):
            return ValidateView.as_view()(request)

    def test_single_record(self):
        response = self.post({"record": self.good})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["ok"])
        self.assertEqual(response.data["checked"], 1)

    def test_multiple_records(self):
        bad = copy.deepcopy(self.good)
        bad["properties"]["latitude"] = 999
        response = self.post({"records": [self.good, bad]})
        self.assertFalse(response.data["ok"])
        self.assertEqual(response.data["checked"], 2)
        self.assertTrue(response.data["results"][0]["ok"])
        self.assertFalse(response.data["results"][1]["ok"])
        self.assertEqual(response.data["results"][1]["index"], 1)

    def test_missing_payload_is_400(self):
        response = self.post({})
        self.assertEqual(response.status_code, 400)

    def test_non_dict_records_are_400(self):
        response = self.post({"records": ["nope"]})
        self.assertEqual(response.status_code, 400)

    def test_too_many_records_is_400(self):
        response = self.post({"records": [self.good] * 201})
        self.assertEqual(response.status_code, 400)

    def test_ets_flag_is_reported(self):
        response = self.post({"record": self.good, "ets": True})
        self.assertTrue(response.data["ets_requested"])
        # 本机没有 pywmdr，所以 available 是 False——这正是要固化的行为
        self.assertFalse(response.data["ets_available"])
