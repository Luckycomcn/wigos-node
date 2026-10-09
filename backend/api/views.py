import logging
import re
from pathlib import Path
from pickle import GET

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

from .models import Station, WIGOSNodeGroup

logger = logging.getLogger(__name__)


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

# Same pattern as "id" and "additionalIds" in schemas/wmdr2-bundled.json (and WIGOS_ID_PATTERN in the frontend).
def check_wigos_identifier(wigos_identifier):
    return not (wigos_identifier is None or not re.match(r'^(0|1|2|3)-([1-9][0-9]*)-([0-9]+)-([A-Za-z0-9._-]+)$', wigos_identifier))

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

@api_view(["GET"])
def check_wigosidentifiers(request):
    wigos_identifiers = request.query_params.getlist("wigos_identifier")
    if len(wigos_identifiers) == 0:
        return Response({"detail": "No WIGOS identifiers provided"}, status=400)
    results = {wigos_identifier: Station.objects.check_wigos_identifier(wigos_identifier) for wigos_identifier in wigos_identifiers}
    return Response(results)

@api_view(["GET"])
def my_issuer_of_identifiers(request):
    groups = WIGOSNodeGroup.objects.filter(group__user=request.user)
    issuer_identifiers = [group.issuer_identifier for group in groups]
    return Response({"issuer_of_identifiers": issuer_identifiers})    


class Wmdrv2View(APIView):
    permission_classes = [IsAuthenticated | ReadOnly]

 
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

        # superusers bypass the per-issuer group check (Django convention)
        if not request.user.is_superuser:
            issuer_of_identifiers = [wsi.split('-')[1] for wsi in station.get_wigos_identifiers()]
            # check that the user is in a group for every issuer of identifier on this station
            for issuer_id in issuer_of_identifiers:
                if not WIGOSNodeGroup.objects.filter(issuer_identifier=issuer_id, group__user=request.user).exists():
                    return Response({"error": f"You do not have permission to update a station for the issuer of identifier {issuer_id}."}, status=status.HTTP_403_FORBIDDEN)

        
        station.wmdrv2 = request.data # we only need to set the wmdrv2 field, the save method will handle updating index fields

        station.save() # owner is unchanged on update; Station.save() forwards **kwargs to Model.save(), which rejects `owner`

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

        issuer_of_identifiers = [wsi.split('-')[1] for wsi in station.get_wigos_identifiers()]

        # superusers bypass the per-issuer group check (Django convention)
        if not request.user.is_superuser:
            # check that the user is in a group for every issuer of identifier on this station
            for issuer_id in issuer_of_identifiers:
                if not WIGOSNodeGroup.objects.filter(issuer_identifier=issuer_id, group__user=request.user).exists():
                    return Response({"error": f"You do not have permission to create a station for the issuer of identifier {issuer_id}."}, status=status.HTTP_403_FORBIDDEN)

        try:
            station.save()  # This will also update the name and location based on the WMDv2 data
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        # assign permissions (after save so the station has a pk to attach object permissions to)
        assign_perm('change_station', owner, station)

        for issuer_id in issuer_of_identifiers:
            node_groups = WIGOSNodeGroup.objects.filter(issuer_identifier=issuer_id)
            if node_groups.exists():
                for node_group in node_groups:
                    assign_perm('change_station', node_group.group, station)
            else:
                logger.warning(f"No group found for issuer_identifier {issuer_id}. Station {station.id} will not be assigned to any group for this WSI.")

        return Response({"message": f"Station {station.id} created successfully.", "station_id": station.id}, status=201)
