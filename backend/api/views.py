import re
from pathlib import Path

import django.http
from django.conf import settings
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.decorators import (
    api_view,
)
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Station


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

def check_wigos_identifier(wigos_identifier):
    return not (wigos_identifier is None or not re.match(r'^(0|1|2|3)-([1-9][0-9]*)-([0-9]+)-([A-Za-z0-9]+)$', wigos_identifier))

@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


def codelist(request, scheme):
    path = Path(settings.BASE_DIR) / "api" / "codelists" / f"{scheme}.csv"
    if not path.exists():
        return django.http.HttpResponseNotFound(f"No cached codelist for '{scheme}'")
    return django.http.HttpResponse(path.read_text(encoding="utf-8"), content_type="text/csv")


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
            "station_id": station.id,
            "wsi": station.wigos_identifier,
            "name": station.name,
            "latitude": station.location.y,
            "longitude": station.location.x,
        }
        for station in my_stations
    ])


class Wmdrv2View(APIView):
    permission_classes = [IsAuthenticated | ReadOnly]

    # DRF automatically runs this before get() or post()
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        wigos_identifier = kwargs.get('wigos_identifier')
        if not check_wigos_identifier(wigos_identifier):
            from rest_framework.exceptions import ValidationError
            raise ValidationError(f"Invalid WIGOS identifier: '{wigos_identifier}'")

    def get(self, request, station_id=None):

        if station_id is None:
            return Response(
                {"error": "Station ID is required for retrieval."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            station = Station.objects.get(id=station_id)
        except Station.DoesNotExist:
            return Response({"detail": f"Station {station_id} not found"}, status=404)

        return Response(station.wmdrv2)
        

    def put(self, request, station_id=None):

        if station_id is None:
            return Response(
                {"error": "Station ID is required for updating."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            station = Station.objects.get(id=station_id)
        except Station.DoesNotExist:
            return Response({"detail": f"Station {station_id} not found"}, status=404)

        if not request.user.has_perm('change_station', station):
            return Response({"error": "You do not have permission to change this station."}, status=status.HTTP_403_FORBIDDEN)
        
        station.wmdrv2 = request.data # we only need to set the wmdrv2 field, the save method will handle updating index fields
    
        station.save(owner=request.user) # pass the owner to the save method to set the owner field
        #station.save() # pass the owner to the save method to set the owner field
        
        return Response({"message": f"WMDv2 data for station {station_id} updated successfully."}, status=200)

    def post(self, request, station_id=None):
        if station_id is not None:
            return Response(
                {"error": "Station ID should not be provided for creation."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        wmdrv2_data = request.data
        owner = request.user  # Get the authenticated user making the request

        # Create a new Station instance
        station = Station(wmdrv2=wmdrv2_data, owner=owner)

        # assign permissions
        assign_perm('change_station', owner, station)
        
        
        try:
            station.save()  # This will also update the name and location based on the WMDv2 data
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        return Response({"message": f"Station {station.id} created successfully.", "station_id": station.id}, status=201)