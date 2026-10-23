from django.urls import include, path

from . import auth, interop, mvp, views
from .views import Wmdrv2BatchView, Wmdrv2ByWsiView, Wmdrv2View

urlpatterns = [
    path("health/", views.health, name="health"),
    path("hello/", views.hello, name="hello"),
    path("geojson/", views.geojson, name="geojson"),
    path("codelists/<str:scheme>.csv", views.codelist, name="codelist"),
    path("my_stations/", views.my_stations, name="my_stations"),
    path("wmdrv2/batch/", Wmdrv2BatchView.as_view(), name="wmdrv2-batch"), # GET and POST, before wmdrv2/<int:station_id>
    path("wmdrv2/batch-create/", mvp.BatchCreateView.as_view(), name="wmdrv2-batch-create"), # F-4 create
    path("wmdrv2/wsi/<str:wsi>", Wmdrv2ByWsiView.as_view(), name="wmdrv2-wsi"), # GET
    # F-19 archive/restore + hard delete, F-8 history, publishing
    path("wmdrv2/<int:station_id>/archive", mvp.StationArchiveView.as_view(), {"action": "archive"}, name="wmdrv2-archive"),
    path("wmdrv2/<int:station_id>/restore", mvp.StationArchiveView.as_view(), {"action": "restore"}, name="wmdrv2-restore"),
    path("wmdrv2/<int:station_id>/history/", mvp.StationHistoryView.as_view(), name="wmdrv2-history"),
    path("wmdrv2/<int:station_id>/history/<int:version>", mvp.StationHistoryView.as_view(), name="wmdrv2-history-version"),
    path("wmdrv2/<int:station_id>/publish", mvp.StationPublishView.as_view(), name="wmdrv2-publish"),
    path("wmdrv2/<int:station_id>/publications/", mvp.PublicationListView.as_view(), name="wmdrv2-publications"),
    path("wmdrv2/",  Wmdrv2View.as_view() , name="wmdrv2"), # POST
    path("wmdrv2/<int:station_id>",  Wmdrv2View.as_view() , name="wmdrv2"), # GET and PUT, DELETE
    path("my_issuer_of_identifiers/", views.my_issuer_of_identifiers, name="my_issuer_of_identifiers"),
    path('check_wigosidentifiers/', views.check_wigosidentifiers, name='check_wigosidentifiers'),
    # MVP completion: groups (F-6), templates (F-22), grades (F-24), WSI (F-11), OGC API (F-14)
    path("groups/", mvp.GroupListCreateView.as_view(), name="groups"),
    path("groups/<int:group_id>/", mvp.GroupDetailView.as_view(), name="group-detail"),
    path("templates/", mvp.TemplateListCreateView.as_view(), name="templates"),
    path("templates/<int:pk>/", mvp.TemplateDetailView.as_view(), name="template-detail"),
    path("grades/", mvp.GradeListCreateView.as_view(), name="grades"),
    path("stations/<int:station_id>/grades/", mvp.GradeEvaluateView.as_view(), name="station-grades"),
    path("wsi/next/", mvp.WsiNextView.as_view(), name="wsi-next"),
    # F-14: conformance, one collection, items (literal path before the <str> one)
    path("records/conformance", mvp.OgcConformanceView.as_view(), name="ogc-conformance"),
    path("records/collections/", mvp.OgcCollectionsView.as_view(), name="ogc-collections"),
    path("records/collections/<str:collection_id>/items", mvp.OgcItemsView.as_view(), name="ogc-items"),
    path("records/collections/<str:collection_id>/items/<str:wsi>", mvp.OgcItemView.as_view(), name="ogc-item"),
    path("records/collections/<str:collection_id>", mvp.OgcCollectionView.as_view(), name="ogc-collection"),
    # F-16 export: bulk and single record
    path("export/", interop.ExportView.as_view(), name="export"),
    path("wmdrv2/<int:station_id>/export", interop.StationExportView.as_view(), name="wmdrv2-export"),
    # F-15 ingest / F-21 WMDR1 import
    path("import/", interop.ImportView.as_view(), name="import"),
    path("import/wmdr1/", interop.Wmdr1ImportView.as_view(), name="import-wmdr1"),
    # F-13 providers: several organisations per record
    path("wmdrv2/<int:station_id>/providers/", interop.StationProviderView.as_view(), name="wmdrv2-providers"),
    path("providers/<int:provider_id>/", interop.ProviderDetailView.as_view(), name="provider-detail"),
    # JSON auth endpoints for the SPA (the DRF HTML login stays at auth/ below)
    path("csrf/", auth.csrf, name="auth-csrf"),
    path("login/", auth.login, name="auth-login"),
    path("logout/", auth.logout, name="auth-logout"),
    path("whoami/", auth.me, name="auth-me"),
    path("auth/", include("rest_framework.urls", namespace="rest_framework")),
]
