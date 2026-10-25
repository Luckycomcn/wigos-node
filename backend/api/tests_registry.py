"""WSI 注册表 / 发布权威性 / 审计的接口测试。

需要 PostGIS（这些用例会建用户、建站点、发请求）。在 164 上跑：

    python manage.py test api.tests_registry -v 2

预置用户来自 migration 0007：test_user1 / test_password1，属于
nfps_Switzerland 与 nfps_Brazil 两个 issuer 组。
"""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from . import stations
from .models import AuditLog, Station, WIGOSNodeUser, WsiAllocation
from .testing_utils import load_test_json


class RegistryAuthTests(APITestCase):
    def setUp(self):
        self.url = reverse("wsi-allocations")

    def test_list_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_requires_login(self):
        response = self.client.post(self.url, {"issuer": 20000, "numberFrom": 1, "numberTo": 9})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_audit_requires_staff(self):
        self.client.login(username="test_user1", password="test_password1")
        response = self.client.get(reverse("audit-log"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AllocationCrudTests(APITestCase):
    def setUp(self):
        self.client.login(username="test_user1", password="test_password1")
        self.url = reverse("wsi-allocations")

    def test_create_and_list(self):
        response = self.client.post(self.url, {
            "issuer": 20000, "series": 0, "numberFrom": 0, "numberTo": 999999, "note": "test block",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["issuer"], 20000)

        listing = self.client.get(self.url).json()
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0]["numberTo"], 999999)

    def test_create_rejects_inverted_range(self):
        response = self.client.post(self.url, {"issuer": 20000, "numberFrom": 10, "numberTo": 1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("numberFrom", response.json()["error"])

    def test_create_rejects_non_integer(self):
        response = self.client.post(self.url, {"issuer": "abc", "numberFrom": 1, "numberTo": 2})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_and_delete(self):
        created = self.client.post(self.url, {
            "issuer": 20000, "series": 1, "numberFrom": 10, "numberTo": 20,
        }).json()
        detail = reverse("wsi-allocation-detail", args=[WsiAllocation.objects.get(
            issuer_identifier=20000, series=1).id])

        patched = self.client.patch(detail, {"numberTo": 30, "note": "widened"})
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.json()["numberTo"], 30)
        self.assertEqual(patched.json()["note"], "widened")

        self.assertEqual(self.client.delete(detail).status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(WsiAllocation.objects.filter(issuer_identifier=20000, series=1).exists())

    def test_issuer_filter(self):
        self.client.post(self.url, {"issuer": 20000, "numberFrom": 0, "numberTo": 10})
        self.client.post(self.url, {"issuer": 20001, "numberFrom": 0, "numberTo": 10})
        self.assertEqual(len(self.client.get(self.url).json()), 2)
        self.assertEqual(len(self.client.get(self.url, {"issuer": 20001}).json()), 1)


class AllocationIoTests(APITestCase):
    def setUp(self):
        self.client.login(username="test_user1", password="test_password1")
        self.url = reverse("wsi-allocations")

    def test_export_json(self):
        self.client.post(self.url, {"issuer": 20000, "numberFrom": 5, "numberTo": 6})
        response = self.client.get(reverse("wsi-allocations-export"), {"format": "json"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["allocations"][0]["numberFrom"], 5)

    def test_export_csv(self):
        self.client.post(self.url, {"issuer": 20000, "numberFrom": 5, "numberTo": 6})
        response = self.client.get(reverse("wsi-allocations-export"), {"format": "csv"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("issuer,series,numberFrom,numberTo,note", response.content.decode())

    def test_import_json_dry_run_then_apply(self):
        payload = {"format": "json", "dry_run": True, "data": [
            {"issuer": 20000, "series": 0, "numberFrom": 0, "numberTo": 99},
            {"issuer": 20000, "series": 0, "numberFrom": 100, "numberTo": 199},
            {"issuer": "oops", "series": 0, "numberFrom": 1, "numberTo": 2},
        ]}
        response = self.client.post(reverse("wsi-allocations-import"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertTrue(body["dry_run"])
        self.assertEqual(body["accepted"], 2)
        self.assertEqual(body["rejected"], 1)
        self.assertEqual(WsiAllocation.objects.count(), 0, "dry_run 不应落库")

        payload["dry_run"] = False
        applied = self.client.post(reverse("wsi-allocations-import"), payload, format="json").json()
        self.assertEqual(applied["accepted"], 2)
        self.assertEqual(WsiAllocation.objects.count(), 2)

    def test_import_csv(self):
        csv_text = "issuer,series,numberFrom,numberTo,note\n20000,0,0,50,first\n20001,0,0,50,second\n"
        response = self.client.post(
            reverse("wsi-allocations-import"),
            {"format": "csv", "data": csv_text},
            format="json",
        )
        self.assertEqual(response.json()["accepted"], 2)
        self.assertEqual(WsiAllocation.objects.count(), 2)

    def test_import_rejects_unknown_format(self):
        response = self.client.post(
            reverse("wsi-allocations-import"), {"format": "yaml", "data": "x"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PublishAuthorityTests(APITestCase):
    """发布权威性：WSI 不在授权范围内就地在本地拒绝，并留痕。"""

    def setUp(self):
        # 迁移只预置了 test_user1（属 nfps_Switzerland/nfps_Brazil，即 issuer
        # 756/76），演示记录用的是 issuer 20000 —— 用它必然被 check_issuers 403，
        # 我们这里要测的是"WSI 授权范围"这道独立的闸，不该被别的门槛挡住。
        # 所以自建超管 + 自建站点，把 issuer 组这套前置条件绕开。
        self.user = WIGOSNodeUser.objects.create_superuser(
            username="authority_admin", email="authority_admin@example.com", password="pw12345!"
        )
        self.client.force_login(self.user)
        self.registry_url = reverse("wsi-allocations")
        self.station = stations.create_station(self.user, load_test_json("test_wmdrv2.json"))
        self.assertEqual(self.station.wigos_identifier, "0-20000-0-123456")
        self.publish_url = reverse("wmdrv2-publish", args=[self.station.id])

    def _grant(self, low=0, high=999999, issuer=20000):
        self.client.post(self.registry_url, {
            "issuer": issuer, "series": 0, "numberFrom": low, "numberTo": high,
        })

    def test_publish_rejected_without_allocation(self):
        response = self.client.post(self.publish_url, {"operation": "canonical"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["reason"], "out_of_range")
        # 留痕（NF-6）
        self.assertTrue(AuditLog.objects.filter(action="publish_rejected").exists())

    def test_publish_allowed_within_allocation(self):
        self._grant()
        response = self.client.post(self.publish_url, {"operation": "canonical"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(AuditLog.objects.filter(action="publish").exists())

    def test_publish_rejected_when_number_outside_range(self):
        self._grant(low=0, high=100)
        response = self.client.post(self.publish_url, {"operation": "canonical"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("0-20000-0-123456", response.json()["offenders"])

    def test_publish_rejected_for_other_issuer(self):
        self._grant(issuer=20001)
        response = self.client.post(self.publish_url, {"operation": "canonical"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_publish_allowed_when_enforcement_disabled(self):
        with self.settings(WNM_REQUIRE_ALLOCATION=False):
            response = self.client.post(self.publish_url, {"operation": "canonical"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
