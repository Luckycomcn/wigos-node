import re
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Station


def check_wigos_identifier(wigos_identifier):
    return not (wigos_identifier is None or not re.match(r'^(0|1|2|3)-([1-9][0-9]*)-([0-9]+)-([A-Za-z0-9]+)$', wigos_identifier))

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
    return Response([{"wsi": station.wigos_identifier, "name": station.name} for station in my_stations])


class Wmdrv2View(APIView):
    # DRF automatically runs this before get() or post()
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        wigos_identifier = kwargs.get('wigos_identifier')
        if not check_wigos_identifier(wigos_identifier):
            from rest_framework.exceptions import ValidationError
            raise ValidationError(f"Invalid WIGOS identifier: '{wigos_identifier}'")

    def get(self, request, wigos_identifier):
        try:
            station = Station.objects.get(wigos_identifier=wigos_identifier)
        except Station.DoesNotExist:
            return Response({"detail": f"Station {wigos_identifier} not found"}, status=404)

        return Response(station.wmdrv2)
        

    def post(self, request, wigos_identifier):
        try:
            station = Station.objects.get(wigos_identifier=wigos_identifier)
        except Station.DoesNotExist:
            station = Station(wigos_identifier=wigos_identifier)
        
        station.wmdrv2 = request.data # we only need to set the wmdrv2 field, the save method will handle updating index fields
    
        station.save()
        
        return Response({"message": f"WMDv2 data for station {wigos_identifier} updated successfully."}, status=200)
