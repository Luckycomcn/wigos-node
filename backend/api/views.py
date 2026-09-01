from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Station


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


@api_view(["GET"])
def my_stations(request):
    my_stations = Station.objects.filter(wmdrv2__isnull=False) # return all stations in the meantime
    return Response([
        {
            "id": station.id,
            "wsi": station.wigos_identifier,
            "name": station.name,
            "latitude": station.location.y,
            "longitude": station.location.x,
        }
        for station in my_stations
    ])


class Wmdrv2View(APIView):
    def get(self, request, pk=None):
        if pk is None:
            return Response({"detail": "A station id is required"}, status=400)
        try:
            station = Station.objects.get(pk=pk)
        except Station.DoesNotExist:
            return Response({"detail": f"Station {pk} not found"}, status=404)

        return Response(station.wmdrv2)

    def post(self, request, pk=None):
        if pk is None:
            station = Station(wmdrv2=request.data)
        else:
            try:
                station = Station.objects.get(pk=pk)
            except Station.DoesNotExist:
                return Response({"detail": f"Station {pk} not found"}, status=404)
            station.wmdrv2 = request.data # we only need to set the wmdrv2 field, the save method will handle updating index fields

        try:
            station.save()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(
            {"id": station.id, "message": f"WMDR data for station {station.id} saved successfully."},
            status=201 if pk is None else 200,
        )
