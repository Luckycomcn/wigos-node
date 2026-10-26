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
        """默认来源应当由 ALLOWED_HOSTS 推导，而不是写死某个主机名。

        ``ALLOWED_HOSTS='*'`` 是合法配置（测试脚本就用它），但通配无法枚举，
        此时设置模块会回落到 loopback —— 这里只断言「非通配主机名都被覆盖」。
        """
        # Django 的测试运行器会在配置加载完之后往 ALLOWED_HOSTS 里追加
        # 'testserver'，而信任列表是在设置模块求值时生成的，自然不含它。
        hosts = [
            h.strip()
            for h in settings.ALLOWED_HOSTS
            if h and h.strip() not in {"*", "testserver"}
        ]
        joined = " ".join(settings.CSRF_TRUSTED_ORIGINS)
        for host in hosts:
            self.assertIn(host, joined, f"{host} 出现在 ALLOWED_HOSTS 但不在信任来源里")

    def test_wildcard_allowed_hosts_still_yields_a_usable_list(self):
        """ALLOWED_HOSTS='*' 时不能推导出空列表 —— 空列表等于所有写操作 403。"""
        self.assertTrue(
            settings.CSRF_TRUSTED_ORIGINS,
            "信任来源为空，浏览器发起的写请求会全部被 CSRF 拦掉",
        )
        self.assertTrue(settings.CORS_ALLOWED_ORIGINS, "CORS 来源为空")

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

class SecurityDefaultTests(SimpleTestCase):
    """默认值必须是安全的 —— "照文档部署"不该拿到一个能被利用的实例。

    这组断言对应 BUG-05（DEBUG 与固定密钥）和 BUG-24（数据库端口暴露）。
    """

    def test_debug_defaults_to_off(self):
        """源码里的默认值（没有环境变量时）必须是 False。

        原版是 ``os.environ.get("DJANGO_DEBUG", "true")``，而 .env.example 又把
        true 抄了进去 —— 照文档部署的实例会把完整堆栈、绝对路径、DATABASES
        结构返回给浏览器。这里直接读源码，而不是读已经求值的 settings：测试
        运行器本身可能设了 DJANGO_DEBUG。
        """
        from pathlib import Path

        source = (Path(settings.BASE_DIR) / "config" / "settings.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("DJANGO_DEBUG", "false")', source,
                      "DEBUG 的默认值又变成 true 了")

    def test_insecure_secret_key_refuses_to_start(self):
        """非 DEBUG 下用模板里的占位密钥必须直接起不来。

        那个密钥在仓库里公开，拿它签出来的 session cookie 谁都能伪造。
        """
        import os

        import config.settings as s

        os.environ.pop("DJANGO_DEBUG", None)
        os.environ["DJANGO_SECRET_KEY"] = "change-me-in-dev"
        try:
            with self.assertRaises(Exception):
                importlib.reload(s)
        finally:
            os.environ.pop("DJANGO_SECRET_KEY", None)
            importlib.reload(s)

    def test_env_example_has_no_insecure_defaults(self):
        """模板里不能出现 DEBUG=true、弱口令、缺 CSRF 来源。"""
        from pathlib import Path

        template = (Path(settings.BASE_DIR).parent / ".env.example").read_text(encoding="utf-8")
        self.assertNotIn("DJANGO_DEBUG=true", template, ".env.example 又把 DEBUG 打开了")
        self.assertNotIn("POSTGRES_PASSWORD=app_password", template,
                         ".env.example 里还是模板弱口令")
        self.assertIn("CSRF_TRUSTED_ORIGINS", template,
                      ".env.example 缺 CSRF_TRUSTED_ORIGINS（BUG-23 的根因之一）")

    def test_cookie_hardening(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY, "session cookie 必须 HttpOnly")
        self.assertIn(settings.SESSION_COOKIE_SAMESITE, ("Lax", "Strict"))
        # SPA 要读 csrftoken 放进 X-CSRFToken 头，所以它不能是 HttpOnly。
        self.assertFalse(settings.CSRF_COOKIE_HTTPONLY)

    def test_login_throttle_rate_configured(self):
        self.assertIn("login", settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}))


class CacheBackendTests(SimpleTestCase):
    """登录失败计数必须跨进程可见。

    真机上暴露过一次：默认缓存是 LocMemCache，而 gunicorn 是 3 worker，
    每个 worker 各数各的失败次数，等于把 10 次/15 分钟的锁定放宽成 30 次。
    实测连发 40 次错误口令，有 8 次漏过（401 而非 429）。

    开发态与测试态都是单进程，这个缺陷在那里**完全看不出来** —— 所以要靠
    对配置本身的断言来守，而不是靠行为测试。
    """

    def test_default_cache_is_not_process_local(self):
        """非测试、未配 DJANGO_CACHE_URL 时不能落到 locmem。"""
        from pathlib import Path

        source = (Path(settings.BASE_DIR) / "config" / "settings.py").read_text(encoding="utf-8")
        # 生产分支（else:）里必须是 DatabaseCache，locmem 只能出现在测试分支。
        self.assertIn("django.core.cache.backends.db.DatabaseCache", source,
                      "默认缓存不是 DatabaseCache —— 多 worker 下限流会被放宽 N 倍")
        # locmem 只允许在 RUNNING_TESTS 分支出现一次。
        self.assertEqual(
            source.count("locmem.LocMemCache"), 1,
            "locmem 不应出现在生产分支里",
        )

    def test_test_run_uses_locmem(self):
        """测试态用 locmem 是对的：不建表、行为足够。"""
        self.assertIn("LocMemCache", settings.CACHES["default"]["BACKEND"])

    def test_cache_table_named_and_referenced(self):
        """缓存表名必须在 settings 与 entrypoint 里一致。"""
        from pathlib import Path

        self.assertTrue(getattr(settings, "CACHE_TABLE", ""), "CACHE_TABLE 未定义")
        entrypoint = (Path(settings.BASE_DIR) / "entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("createcachetable", entrypoint,
                      "entrypoint 没建缓存表 —— 登录会因表不存在直接 500")
