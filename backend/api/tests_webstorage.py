"""webstorage 只读视图的测试。

不需要数据库（SimpleTestCase），因此可以在没有 PostGIS 的机器上跑：
    DJANGO_SETTINGS_MODULE=config.settings python manage.py test api.tests_webstorage
"""
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from .mvp import WebstorageView


class WebstorageViewTests(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        (self.dir / "wmdr2_io-test_0-20000-0-123456_2026-08-07T11_13_00_000.json").write_bytes(
            b'{"id":"0-20000-0-123456"}'
        )
        (self.dir / "readme.txt").write_text("hello")
        self._override = override_settings(WNM_STORAGE_DIR=str(self.dir))
        self._override.enable()
        self.factory = APIRequestFactory()

    def tearDown(self):
        self._override.disable()
        self._tmp.cleanup()

    def call(self, filename):
        request = self.factory.get(f"/webstorage/{filename}")
        return WebstorageView.as_view()(request, filename=filename)

    # --- 正向 ---------------------------------------------------------
    def test_serves_published_record(self):
        response = self.call("wmdr2_io-test_0-20000-0-123456_2026-08-07T11_13_00_000.json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'{"id":"0-20000-0-123456"}')
        self.assertEqual(response["Content-Type"], "application/geo+json")
        self.assertEqual(response["Cache-Control"], "public, max-age=60")
        self.assertEqual(response["Content-Length"], str(len(response.content)))

    def test_head_allowed(self):
        request = self.factory.head("/webstorage/readme.txt")
        response = WebstorageView.as_view()(request, filename="readme.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        # HEAD 必须保留 Content-Length，否则目录侧无法预判大小
        self.assertEqual(response["Content-Length"], "5")

    def test_anonymous_access(self):
        """WIS2 消息文件是公开的，不带任何凭据也应能下载。"""
        request = self.factory.get("/webstorage/readme.txt")
        request.user = None
        response = WebstorageView.as_view()(request, filename="readme.txt")
        self.assertEqual(response.status_code, 200)

    # --- 负向 ---------------------------------------------------------
    def test_missing_file_returns_404(self):
        response = self.call("does-not-exist.json")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", str(response.data))

    def test_hidden_file_rejected(self):
        (self.dir / ".env").write_text("SECRET=1")
        response = self.call(".env")
        self.assertEqual(response.status_code, 400)

    def test_path_traversal_rejected(self):
        # 路由的 <str:filename> 本来就排除 "/"，这里直接打视图，验证二层防护
        for evil in ("../settings.py", "a/b.json", "..", "../.."):
            response = self.call(evil)
            self.assertEqual(response.status_code, 400, msg=f"{evil} 应被拒绝")

    def test_write_methods_not_allowed(self):
        request = self.factory.post("/webstorage/readme.txt")
        response = WebstorageView.as_view()(request, filename="readme.txt")
        self.assertEqual(response.status_code, 405)
