"""方案 5.6 编辑工作流：草稿 → 提交 → 校验 → 发布。

需要 PostGIS（要建用户、建站点、发请求）。在 164 上跑：

    python manage.py test api.tests_draft -v 2

这里刻意自建超管而不是用预置的 test_user1：后者只属于 nfps_Switzerland /
nfps_Brazil（issuer 756 / 76），而演示记录用的是 issuer 20000，用它会被
check_issuers 拦在 403 —— 那就测不到工作流本身了。
"""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from . import stations
from .models import AuditLog, Station, WIGOSNodeUser
from .testing_utils import load_test_json


def _grant(client, url, issuer=20000, low=0, high=999999):
    client.post(url, {"issuer": issuer, "series": 0, "numberFrom": low, "numberTo": high})


class DraftLifecycleTests(APITestCase):
    def setUp(self):
        self.user = WIGOSNodeUser.objects.create_superuser(
            username="wf_admin", email="wf_admin@example.com", password="pw12345!"
        )
        self.client.force_login(self.user)
        self.record = load_test_json("test_wmdrv2.json")
        # 默认政策维持旧行为：建了就是 submitted，接着就能发
        self.station = stations.create_station(self.user, self.record)
        self.assertEqual(self.station.status, Station.SUBMITTED)
        self.submit_url = reverse("wmdrv2-submit", args=[self.station.id])
        self.publish_url = reverse("wmdrv2-publish", args=[self.station.id])
        self.registry_url = reverse("wsi-allocations")

    def _to_draft(self):
        self.station.status = Station.DRAFT
        self.station.save(update_fields=["status"])

    def test_record_can_be_created_as_draft(self):
        other = dict(self.record, id="0-20000-0-654321")
        station = stations.create_station(self.user, other, status=Station.DRAFT)
        self.assertTrue(station.is_draft)

    def test_publishing_a_draft_is_locally_rejected(self):
        """草稿内容可能不完整，绝不能放出去。"""
        _grant(self.client, self.registry_url)
        self._to_draft()
        response = self.client.post(self.publish_url, {"operation": "canonical"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["reason"], "draft")
        self.assertTrue(
            AuditLog.objects.filter(action="publish_rejected", detail__icontains="draft").exists()
            or AuditLog.objects.filter(action="publish_rejected").exists()
        )

    def test_submit_then_publish(self):
        _grant(self.client, self.registry_url)
        self._to_draft()

        rejected = self.client.post(self.publish_url, {"operation": "canonical"}, format="json")
        self.assertEqual(rejected.status_code, status.HTTP_403_FORBIDDEN)

        submitted = self.client.post(self.submit_url)
        self.assertEqual(submitted.status_code, status.HTTP_200_OK, submitted.content)
        self.station.refresh_from_db()
        self.assertEqual(self.station.status, Station.SUBMITTED)
        self.assertTrue(AuditLog.objects.filter(action="submit").exists())

        published = self.client.post(self.publish_url, {"operation": "canonical"}, format="json")
        self.assertEqual(published.status_code, status.HTTP_201_CREATED, published.content)

    def test_submitting_an_already_submitted_record_is_a_noop(self):
        """重复提交不该报错，也不该重复写版本历史以外的东西。"""
        response = self.client.post(self.submit_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["already_submitted"])
        self.station.refresh_from_db()
        self.assertEqual(self.station.status, Station.SUBMITTED)

    def test_submit_rejects_records_that_fail_business_rules(self):
        """把关在提交这一步，就是为了让"发了才被退回"变成"提交就被退回"。"""
        broken = dict(self.record)
        broken["properties"] = dict(self.record["properties"], latitude=999)
        self.station.wmdrv2 = broken
        self.station.save()
        self._to_draft()

        response = self.client.post(self.submit_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["reason"], "business_rules")
        self.station.refresh_from_db()
        self.assertEqual(self.station.status, Station.DRAFT, "被拒的提交不该离开草稿态")


class DraftVisibilityTests(APITestCase):
    """草稿是未完成的工作，只有能改它的人看得见。"""

    def setUp(self):
        self.owner = WIGOSNodeUser.objects.create_superuser(
            username="draft_owner", email="draft_owner@example.com", password="pw12345!"
        )
        self.other = WIGOSNodeUser.objects.create_superuser(
            username="draft_other", email="draft_other@example.com", password="pw12345!"
        )
        self.client.force_login(self.owner)
        record = load_test_json("test_wmdrv2.json")
        self.station = stations.create_station(self.owner, record, status=Station.DRAFT)
        self.list_url = reverse("my_stations")

    def _wsis(self, payload):
        return [row["wsi"] for row in payload]

    def test_owner_sees_own_draft(self):
        rows = self.client.get(self.list_url).json()
        self.assertIn(self.station.wigos_identifier, self._wsis(rows))
        draft_row = next(r for r in rows if r["wsi"] == self.station.wigos_identifier)
        self.assertEqual(draft_row["status"], Station.DRAFT)

    def test_draft_hidden_from_anonymous(self):
        self.client.logout()
        rows = self.client.get(self.list_url).json()
        self.assertNotIn(self.station.wigos_identifier, self._wsis(rows))

    def test_submitted_records_stay_public(self):
        self.station.status = Station.SUBMITTED
        self.station.save(update_fields=["status"])
        self.client.logout()
        rows = self.client.get(self.list_url).json()
        self.assertIn(self.station.wigos_identifier, self._wsis(rows))
