from django.contrib import admin
from django.urls import include, path, re_path

from api.mvp import WebstorageView
from api.views import api_not_found

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    # `/api/` 下任何没匹配到路由的路径都走这里，返回 JSON 而不是 Django 默认的
    # HTML 404 页。SPA 的 fetch 会对 HTML 解析失败，抛出的错误看不出任何原因。
    # 这条必须放在 include 之后：Django 按顺序匹配，先匹配到 include 的就不走它。
    re_path(r"^api/.*$", api_not_found),
    # WIS2 风格的公开 webstorage：服务 WNM 里 links[].href 指向的 WMDR2 文件。
    # 放在根路径（而不是 /api/ 下）是为了让 WNM_STORAGE_URL 与 WIS2 惯例一致。
    path("webstorage/<str:filename>", WebstorageView.as_view(), name="webstorage"),
]