from django.urls import path

from . import views
from .views import Wmdrv2View

urlpatterns = [
    path("health/", views.health, name="health"),
    path("hello/", views.hello, name="hello"),
    path("geojson/", views.geojson, name="geojson"),
    path("codelists/<str:scheme>.csv", views.codelist, name="codelist"),
    path("my_stations/", views.my_stations, name="my_stations"),
    path("wmdrv2/", Wmdrv2View.as_view(), name="wmdrv2-create"),
    path("wmdrv2/<int:pk>", Wmdrv2View.as_view(), name="wmdrv2"),
]
