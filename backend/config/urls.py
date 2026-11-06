from django.apps import apps
from django.contrib import admin
from django.urls import include, path, re_path

from api.mvp import WebstorageView
from api.views import api_not_found

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    # WIS2 风格的公开 webstorage：服务 WNM 里 links[].href 指向的 WMDR2 文件。
    # 放在根路径（而不是 /api/ 下）是为了让 WNM_STORAGE_URL 与 WIS2 惯例一致。
    path("webstorage/<str:filename>", WebstorageView.as_view(), name="webstorage"),
]

# Publishing is an extra service: removing the app from INSTALLED_APPS switches it off
if apps.is_installed("outbox"):
    urlpatterns.append(path("api/publications/", include("outbox.urls")))

# `/api/` 下任何没匹配到路由的路径都走这里，返回 JSON 而不是 Django 默认的
# HTML 404 页。SPA 的 fetch 会对 HTML 解析失败，抛出的错误看不出任何原因。
#
# 它必须排在**所有** api/ 前缀路由之后，包括上面 outbox 的 publications。
# Django 按顺序匹配，这个正则一旦命中就不再往下走；早先它写在 outbox 的
# append 之前，`/api/publications/` 整组接口被它吞成 404 —— 发布列表、
# 发布状态芯片、重试按钮全部不可用，而路由本身是注册好的，只是永远匹配不到。
urlpatterns.append(re_path(r"^api/.*$", api_not_found))
