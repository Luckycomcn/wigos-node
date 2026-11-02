from django.urls import path

from . import views

urlpatterns = [
    path("", views.PublicationListView.as_view(), name="publications"),
    path("latest/", views.PublicationLatestView.as_view(), name="publications-latest"),
    path("<int:event_id>/retry/", views.PublicationRetryView.as_view(), name="publication-retry"),
]
