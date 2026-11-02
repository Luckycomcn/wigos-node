from django.apps import apps
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
]

# Publishing is an extra service: removing the app from INSTALLED_APPS switches it off
if apps.is_installed("outbox"):
    urlpatterns.append(path("api/publications/", include("outbox.urls")))
