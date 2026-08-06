from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


def codelist(request, scheme):
    path = Path(settings.BASE_DIR) / "api" / "codelists" / f"{scheme}.csv"
    if not path.exists():
        return HttpResponseNotFound(f"No cached codelist for '{scheme}'")
    return HttpResponse(path.read_text(encoding="utf-8"), content_type="text/csv")


@api_view(["GET"])
def hello(request):
    return Response({"message": "Hello from Django!"})


@api_view(["POST"])
def geojson(request):
    body = request.data
    if body.get("type") != "Feature" or "geometry" not in body:
        return Response({"detail": "Payload must be a GeoJSON Feature"}, status=400)
    return Response({"received": body}, status=201)
