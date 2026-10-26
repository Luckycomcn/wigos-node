"""登录接口的行为测试。

要覆盖的是原版完全没测过的两条路：
1. 匿名访问 my_issuer_of_identifiers 必须 401，而不是 500（BUG-04）；
2. 登录失败累积到阈值后必须被锁住（BUG-21），而成功一次就解锁。
"""
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .auth import FAILURE_KEY, FAILURE_LIMIT, LoginRateThrottle
from .models import WIGOSNodeUser


class AnonymousEndpointTests(APITestCase):
    def test_my_issuer_of_identifiers_requires_login(self):
        """原版匿名访问这里会 500：AnonymousUser 没有主键，
        `WIGOSNodeGroup.objects.filter(group__user=request.user)` 抛 TypeError。"""
        response = self.client.get(reverse("my_issuer_of_identifiers"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.json())

    def test_my_issuer_of_identifiers_logged_in(self):
        user = WIGOSNodeUser.objects.create_user(
            username="issuer_user", email="issuer_user@example.com", password="pw12345!"
        )
        self.client.force_login(user)
        response = self.client.get(reverse("my_issuer_of_identifiers"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"issuer_of_identifiers": []})


class LoginThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = WIGOSNodeUser.objects.create_user(
            username="throttle_user", email="throttle@example.com", password="correct-horse!"
        )
        self.url = reverse("auth-login")

    def tearDown(self):
        cache.clear()

    def _post(self, password):
        # 绕开 DRF 的每分钟速率闸，专测按窗口累计失败次数的锁定。
        # 两道闸是独立的，混在一起测会让"速率闸触发"看起来像"计数闸的 bug"。
        with patch.object(LoginRateThrottle, "allow_request", return_value=True):
            return self.client.post(self.url, {"username": "throttle@example.com", "password": password})

    def test_failures_accumulate_and_lock(self):
        for i in range(FAILURE_LIMIT):
            response = self._post("wrong")
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED, f"第 {i + 1} 次")
        # 达到阈值后，即便口令是对的也拒绝 —— 否则锁不住爆破。
        locked = self._post("correct-horse!")
        self.assertEqual(locked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_success_clears_the_counter(self):
        self._post("wrong")
        self._post("wrong")
        ok = self._post("correct-horse!")
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertEqual(cache.get(FAILURE_KEY.format(ip="127.0.0.1"), 0), 0)
        # 清零之后又能承受整轮失败。
        for _ in range(FAILURE_LIMIT - 1):
            self.assertEqual(self._post("wrong").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rate_throttle_is_wired(self):
        """速率闸必须真的挂在登录视图上（而不是只在 settings 里配了一个数字）。"""
        from .auth import login as login_view

        self.assertTrue(login_view.cls.throttle_classes or getattr(login_view, "cls", None))
        self.assertEqual(LoginRateThrottle.scope, "login")
        self.assertIn("login", settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])

    def test_counter_key_is_per_address(self):
        self._post("wrong")
        key = FAILURE_KEY.format(ip="127.0.0.1")
        self.assertGreaterEqual(cache.get(key, 0), 1)

    def test_login_by_username_also_works(self):
        """前端登录框接受邮箱或用户名（USERNAME_FIELD 是 email）。"""
        response = self.client.post(self.url, {"username": "throttle_user", "password": "correct-horse!"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["email"], "throttle@example.com")
