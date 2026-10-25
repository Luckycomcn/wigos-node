from django.contrib import admin
from django.urls import include, path

from api.mvp import WebstorageView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    # WIS2 风格的公开 webstorage：服务 WNM 里 links[].href 指向的 WMDR2 文件。
    # 放在根路径（而不是 /api/ 下）是为了让 WNM_STORAGE_URL 与 WIS2 惯例一致。
    path("webstorage/<str:filename>", WebstorageView.as_view(), name="webstorage"),
]
