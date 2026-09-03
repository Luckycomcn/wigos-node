from django.urls import include, path

from . import views
from .views import Wmdrv2View

urlpatterns = [
    path("health/", views.health, name="health"),
    path("hello/", views.hello, name="hello"),
    path("geojson/", views.geojson, name="geojson"),
    path("codelists/<str:scheme>.csv", views.codelist, name="codelist"),
    path("my_stations/", views.my_stations, name="my_stations"),
    path("wmdrv2/",  Wmdrv2View.as_view() , name="wmdrv2"), # POST
    path("wmdrv2/<int:station_id>",  Wmdrv2View.as_view() , name="wmdrv2"), # GET and PUT
    path("my_issuer_of_identifiers/", views.my_issuer_of_identifiers, name="my_issuer_of_identifiers"),
    path("auth/", include("rest_framework.urls", namespace="rest_framework")),
]
