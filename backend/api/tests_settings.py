"""CSRF / CORS 信任来源的配置测试。

真机上暴露过一次：full 轨跑在 :5175，而 ``CSRF_TRUSTED_ORIGINS`` 的默认值写死
成 :5173，于是浏览器发起的每个写请求都被 Django 的 Origin 校验挡成 403。用
curl 直连测接口看不到这个问题 —— curl 根本不发 Origin 头。

这里守住两件事：
1. 默认值必须跟着 ``DJANGO_ALLOWED_HOSTS`` 走，而不是某一个写死的端口；
2. 三条轨道（5173/5174/5175）在默认配置下都必须被信任，否则"换条轨就用不了"。
"""
import importlib

from django.conf import settings
from django.test import SimpleTestCase


class TrustedOriginTests(SimpleTestCase):
    def test_default_covers_every_track_port(self):
        """默认配置下 5173/5174/5175 三个前端端口都要被信任。"""
        joined = " ".join(settings.CSRF_TRUSTED_ORIGINS)
        for port in (5173, 5174, 5175):
            self.assertIn(f":{port}", joined, f"端口 {port} 不在 CSRF 信任列表里：{joined}")

    def test_origins_follow_allowed_hosts(self):
        """默认来源应当由 ALLOWED_HOSTS 推导，而不是写死某个主机名。"""
        # Django 的测试运行器会在配置加载完之后往 ALLOWED_HOSTS 里追加
        # 'testserver'，而信任列表是在设置模块求值时生成的，自然不含它。
        hosts = [
            h.strip()
            for h in settings.ALLOWED_HOSTS
            if h and h != "*" and h.strip() != "testserver"
        ]
        self.assertTrue(hosts, "ALLOWED_HOSTS 不应为空")
        joined = " ".join(settings.CSRF_TRUSTED_ORIGINS)
        for host in hosts:
            self.assertIn(host, joined, f"{host} 出现在 ALLOWED_HOSTS 但不在信任来源里")

    def test_origins_are_absolute_http_urls(self):
        """Origin 必须是带 scheme 的绝对地址，否则 Django 匹配不上。"""
        for origin in settings.CSRF_TRUSTED_ORIGINS:
            self.assertTrue(
                origin.startswith("http://") or origin.startswith("https://"),
                f"不是合法 Origin：{origin!r}",
            )

    def test_cors_and_csrf_defaults_agree(self):
        """两边默认值一致，避免只在一个列表里加了新端口。"""
        self.assertEqual(
            sorted(settings.CSRF_TRUSTED_ORIGINS),
            sorted(settings.CORS_ALLOWED_ORIGINS),
        )

    def test_env_override_still_wins(self):
        """显式给了环境变量时，应该完全按环境变量来。"""
        import os

        os.environ["CSRF_TRUSTED_ORIGINS"] = "https://node.example.org"
        try:
            import config.settings as s

            importlib.reload(s)
            self.assertEqual(s.CSRF_TRUSTED_ORIGINS, ["https://node.example.org"])
        finally:
            del os.environ["CSRF_TRUSTED_ORIGINS"]
            import config.settings as s

            importlib.reload(s)