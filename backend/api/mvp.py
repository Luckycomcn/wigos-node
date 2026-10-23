"""MVP-completion endpoints (F-1..F-24 gaps on top of the existing API).

Everything here is additive: the existing /api/wmdrv2/ endpoints keep their
behaviour, and the rules that guard writes are the ones in api/stations.py.
"""
import logging
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import stations
from .models import (
    PublishedRecord,
    Station,
    StationGrade,
    StationGroup,
    StationTemplate,
    StationVersion,
)
from .renderers import render_wmdrv2
from .stations import StationError
from .wnm import CREATE, UPDATE, create_station_wnm, record_file_name

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #
def _can_change(user, station):
    return user.is_authenticated and user.has_perm("change_station", station)


def _station_or_error(station_id):
    try:
        return Station.objects.get(id=station_id), None
    except Station.DoesNotExist:
        return None, Response({"detail": f"Station {station_id} not found"}, status=404)


def write_version(station, operation, user=None):
    """F-8: snapshot the record after a successful save."""
    last = station.versions.order_by("-version").values_list("version", flat=True).first() or 0
    return StationVersion.objects.create(
        station=station,
        version=last + 1,
        wmdrv2=station.wmdrv2,
        operation=operation,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )


# --------------------------------------------------------------------------- #
# F-19: archive / restore / delete
# --------------------------------------------------------------------------- #
class StationArchiveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, station_id, action):
        station, error = _station_or_error(station_id)
        if error:
            return error
        if not _can_change(request.user, station):
            return Response({"detail": "You do not have permission to change this station."}, status=403)

        if action == "archive":
            station.archived = True
            station.archived_at = timezone.now()
            station.save(update_fields=["archived", "archived_at"])
            return Response({"station_id": station.id, "archived": True})
        if action == "restore":
            station.archived = False
            station.archived_at = None
            station.save(update_fields=["archived", "archived_at"])
            return Response({"station_id": station.id, "archived": False})
        return Response({"detail": f"Unknown action {action}"}, status=400)

    def delete(self, request, station_id, action=None):
        """Hard delete (F-19 '删除'). Archive is the recommended path; this is
        only allowed for the record owner or a superuser."""
        station, error = _station_or_error(station_id)
        if error:
            return error
        if not (request.user.is_superuser or station.owner_id == request.user.id):
            return Response({"detail": "Only the record owner or a superuser may delete a station."}, status=403)
        station.delete()
        return Response(status=204)


# --------------------------------------------------------------------------- #
# F-8: version history
# --------------------------------------------------------------------------- #
class StationHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, station_id, version=None):
        station, error = _station_or_error(station_id)
        if error:
            return error
        if version is None:
            rows = station.versions.order_by("-version")
            return Response([
                {
                    "version": v.version,
                    "operation": v.operation,
                    "created": v.created,
                    "created_by": v.created_by.get_username() if v.created_by else None,
                }
                for v in rows
            ])
        try:
            snapshot = station.versions.get(version=version)
        except StationVersion.DoesNotExist:
            return Response({"detail": f"Version {version} not found"}, status=404)
        return Response({"version": snapshot.version, "operation": snapshot.operation,
                         "created": snapshot.created, "wmdrv2": snapshot.wmdrv2})


# --------------------------------------------------------------------------- #
# F-6: groups / clusters
# --------------------------------------------------------------------------- #
class GroupListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        groups = StationGroup.objects.all().prefetch_related("stations")
        return Response([
            {
                "id": g.id,
                "name": g.name,
                "description": g.description,
                "station_ids": list(g.stations.values_list("id", flat=True)),
                "owner": g.owner.get_username(),
            }
            for g in groups
        ])

    def post(self, request):
        name = (request.data or {}).get("name")
        if not name:
            return Response({"detail": "name is required"}, status=400)
        group, created = StationGroup.objects.get_or_create(
            name=name,
            defaults={"description": (request.data or {}).get("description", ""), "owner": request.user},
        )
        if not created:
            return Response({"detail": f"Group '{name}' already exists"}, status=409)
        return Response({"id": group.id, "name": group.name}, status=201)


class GroupDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, group_id):
        try:
            return StationGroup.objects.prefetch_related("stations").get(id=group_id), None
        except StationGroup.DoesNotExist:
            return None, Response({"detail": "Group not found"}, status=404)

    def get(self, request, group_id):
        group, error = self._get(group_id)
        if error:
            return error
        return Response({
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "stations": list(group.stations.values("id", "wigos_identifier", "name")),
        })

    def patch(self, request, group_id):
        group, error = self._get(group_id)
        if error:
            return error
        if not (request.user.is_superuser or group.owner_id == request.user.id):
            return Response({"detail": "Only the group owner may edit it."}, status=403)
        data = request.data or {}
        if "name" in data:
            group.name = data["name"]
        if "description" in data:
            group.description = data["description"]
        group.save()
        return Response({"id": group.id, "name": group.name, "description": group.description})

    def post(self, request, group_id):
        """Body: {"add": [ids], "remove": [ids]} — F-6 membership."""
        group, error = self._get(group_id)
        if error:
            return error
        if not (request.user.is_superuser or group.owner_id == request.user.id):
            return Response({"detail": "Only the group owner may edit it."}, status=403)
        data = request.data or {}
        add = Station.objects.filter(id__in=data.get("add") or [])
        remove = Station.objects.filter(id__in=data.get("remove") or [])
        group.stations.add(*add)
        group.stations.remove(*remove)
        return Response({"id": group.id, "station_ids": list(group.stations.values_list("id", flat=True))})

    def delete(self, request, group_id):
        group, error = self._get(group_id)
        if error:
            return error
        if not (request.user.is_superuser or group.owner_id == request.user.id):
            return Response({"detail": "Only the group owner may delete it."}, status=403)
        group.delete()
        return Response(status=204)


# --------------------------------------------------------------------------- #
# F-22: templates
# --------------------------------------------------------------------------- #
class TemplateListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        rows = StationTemplate.objects.filter(Q(owner=request.user) | Q(shared=True)).order_by("name")
        return Response([
            {"id": t.id, "name": t.name, "description": t.description,
             "shared": t.shared, "payload": t.payload,
             "owner": t.owner.get_username()}
            for t in rows
        ])

    def post(self, request):
        data = request.data or {}
        name = data.get("name")
        payload = data.get("payload")
        if not name or not isinstance(payload, dict):
            return Response({"detail": "name and payload (object) are required"}, status=400)
        tpl = StationTemplate.objects.create(
            name=name,
            description=data.get("description", ""),
            payload=payload,
            shared=bool(data.get("shared", False)),
            owner=request.user,
        )
        return Response({"id": tpl.id, "name": tpl.name}, status=201)


class TemplateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return StationTemplate.objects.get(id=pk), None
        except StationTemplate.DoesNotExist:
            return None, Response({"detail": "Template not found"}, status=404)

    def get(self, request, pk):
        tpl, error = self._get(pk)
        if error:
            return error
        return Response({"id": tpl.id, "name": tpl.name, "description": tpl.description,
                         "shared": tpl.shared, "payload": tpl.payload})

    def put(self, request, pk):
        tpl, error = self._get(pk)
        if error:
            return error
        if not (request.user.is_superuser or tpl.owner_id == request.user.id):
            return Response({"detail": "Only the template owner may edit it."}, status=403)
        data = request.data or {}
        for field in ("name", "description", "payload", "shared"):
            if field in data:
                setattr(tpl, field, data[field])
        tpl.save()
        return Response({"id": tpl.id, "name": tpl.name})

    def delete(self, request, pk):
        tpl, error = self._get(pk)
        if error:
            return error
        if not (request.user.is_superuser or tpl.owner_id == request.user.id):
            return Response({"detail": "Only the template owner may delete it."}, status=403)
        tpl.delete()
        return Response(status=204)


# --------------------------------------------------------------------------- #
# F-24: station grading
# --------------------------------------------------------------------------- #
def _get_path(record, path):
    current = record
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
        if current is None:
            return None
    return current


def _criterion_matches(record, criterion):
    op = criterion.get("op", "exists")
    value = _get_path(record, criterion.get("path", ""))
    expected = criterion.get("value")
    if op == "exists":
        return value not in (None, "", [], {})
    if op == "eq":
        return value == expected
    if op == "ne":
        return value != expected
    if op == "contains":
        try:
            return expected in value
        except TypeError:
            return False
    if op == "gt":
        return value is not None and value > expected
    if op == "lt":
        return value is not None and value < expected
    if op == "in":
        return value in (expected or [])
    return False


class GradeListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = StationGrade.objects.all()
        return Response([
            {"code": g.code, "label": g.label, "description": g.description,
             "criteria": g.criteria, "order": g.order}
            for g in rows
        ])

    def post(self, request):
        if not request.user.is_superuser:
            return Response({"detail": "Only superusers may define grades."}, status=403)
        data = request.data or {}
        if not data.get("code") or not data.get("label"):
            return Response({"detail": "code and label are required"}, status=400)
        grade, created = StationGrade.objects.get_or_create(
            code=data["code"],
            defaults={
                "label": data["label"],
                "description": data.get("description", ""),
                "criteria": data.get("criteria", []),
                "order": data.get("order", 100),
            },
        )
        if not created:
            return Response({"detail": f"Grade '{data['code']}' already exists"}, status=409)
        return Response({"code": grade.code, "label": grade.label}, status=201)


class GradeEvaluateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, station_id):
        station, error = _station_or_error(station_id)
        if error:
            return error
        matched = [
            {"code": g.code, "label": g.label}
            for g in StationGrade.objects.all()
            if all(_criterion_matches(station.wmdrv2, c) for c in (g.criteria or []))
        ]
        return Response({"station_id": station.id, "grades": matched})


# --------------------------------------------------------------------------- #
# publishing (WNM + web storage)  — the node→catalogue gap
# --------------------------------------------------------------------------- #
class StationPublishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, station_id):
        station, error = _station_or_error(station_id)
        if error:
            return error
        if not _can_change(request.user, station):
            return Response({"detail": "You do not have permission to publish this station."}, status=403)

        operation = (request.data or {}).get("operation", "canonical")
        op = {"canonical": CREATE, "create": CREATE, "update": UPDATE}.get(operation)
        if op is None:
            return Response({"detail": "operation must be canonical or update"}, status=400)

        try:
            wnm = create_station_wnm(station, operation=op)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        storage_dir = Path(getattr(settings, "WNM_STORAGE_DIR", settings.BASE_DIR / "webstorage"))
        storage_dir.mkdir(parents=True, exist_ok=True)
        file_name = record_file_name(station.wmdrv2)
        (storage_dir / file_name).write_bytes(render_wmdrv2(station.wmdrv2))

        url = wnm["links"][0]["href"]
        record = PublishedRecord.objects.create(
            station=station,
            version=wnm["properties"]["datetime"],
            wnm=wnm,
            url=url,
            operation=operation,
            published_by=request.user,
        )

        # Optional fan-out to a catalogue/broker endpoint (best effort, offline-safe).
        publish_url = getattr(settings, "WNM_PUBLISH_URL", "")
        delivered = False
        if publish_url:
            try:
                import requests
                requests.post(publish_url, json=wnm, timeout=10).raise_for_status()
                delivered = True
            except Exception as exc:  # pragma: no cover - network dependent
                logger.warning("WNM delivery to %s failed: %s", publish_url, exc)

        return Response({"published": True, "url": url, "delivered": delivered,
                         "publication_id": record.id, "wnm": wnm}, status=201)


class PublicationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, station_id):
        station, error = _station_or_error(station_id)
        if error:
            return error
        return Response([
            {"id": p.id, "version": p.version, "url": p.url, "operation": p.operation,
             "published": p.published}
            for p in station.publications.all()
        ])


# --------------------------------------------------------------------------- #
# F-11: next WSI under an issuer
# --------------------------------------------------------------------------- #
class WsiNextView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        issuer = (request.query_params.get("issuer") or "").strip()
        station_no = (request.query_params.get("station") or "0").strip()
        series = (request.query_params.get("series") or "0").strip()
        if not issuer.isdigit():
            return Response({"detail": "issuer must be numeric (e.g. 756)"}, status=400)
        allowed = stations.user_issuers(request.user)
        if not request.user.is_superuser and issuer not in allowed:
            return Response({"detail": f"You are not an issuer of identifiers for {issuer}."}, status=403)

        prefix = f"{series}-{issuer}-{station_no}-"
        highest = 0
        for wsi in Station.objects.filter(wigos_identifier__startswith=prefix).values_list("wigos_identifier", flat=True):
            tail = wsi[len(prefix):]
            if tail.isdigit():
                highest = max(highest, int(tail))
        return Response({"wsi": f"{prefix}{highest + 1}", "issuer": issuer,
                         "series": series, "station": station_no})


# --------------------------------------------------------------------------- #
# F-4: batch create (the existing batch endpoint only updates)
# --------------------------------------------------------------------------- #
class BatchCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        records = body.get("records")
        dry_run = bool(body.get("dry_run", False))
        if not isinstance(records, list) or not records:
            return Response({"detail": "Expected { \"records\": [wmdrv2, ...], \"dry_run\": bool }."}, status=400)
        if len(records) > 500:
            return Response({"detail": "At most 500 records per request."}, status=400)

        results = []
        with transaction.atomic():
            for index, record in enumerate(records):
                try:
                    with transaction.atomic():
                        station = stations.create_station(request.user, record)
                    results.append({"index": index, "status": "ok", "station_id": station.id,
                                    "wsi": station.wigos_identifier})
                except StationError as exc:
                    entry = {"index": index, "status": "error", "message": exc.message}
                    if exc.errors:
                        entry["errors"] = exc.errors
                    results.append(entry)
            if dry_run:
                transaction.set_rollback(True)

        ok = sum(r["status"] == "ok" for r in results)
        return Response({"dry_run": dry_run, "summary": {"ok": ok, "error": len(results) - ok}, "results": results})


# --------------------------------------------------------------------------- #
# F-14: OGC API - Records (minimal read-only surface over the node's records)
# --------------------------------------------------------------------------- #
COLLECTION_ID = "wigos-observing-facility-metadata"


class OgcCollectionsView(APIView):
    permission_classes = []

    def get(self, request):
        return Response({
            "collections": [{
                "id": COLLECTION_ID,
                "title": "WIGOS Observing Facility Metadata",
                "description": "WMDR2 records held by this WIGOS node",
                "itemType": "feature",
                "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
                "links": [
                    {"href": f"{request.build_absolute_uri().rstrip('/')}/{COLLECTION_ID}/items",
                     "rel": "items", "type": "application/geo+json"},
                ],
            }],
            "links": [{"href": request.build_absolute_uri(), "rel": "self", "type": "application/json"}],
        })


class OgcItemsView(APIView):
    permission_classes = []

    def get(self, request):
        qs = Station.objects.filter(archived=False)
        limit = min(int(request.query_params.get("limit", 100) or 100), 1000)
        offset = int(request.query_params.get("offset", 0) or 0)
        total = qs.count()
        features = [s.wmdrv2 for s in qs.order_by("id")[offset:offset + limit]]
        base = request.build_absolute_uri().split("?")[0]
        return Response({
            "type": "FeatureCollection",
            "features": features,
            "numberMatched": total,
            "numberReturned": len(features),
            "links": [
                {"href": base, "rel": "self", "type": "application/geo+json"},
                {"href": f"{base.rsplit('/items', 1)[0]}", "rel": "collection", "type": "application/json"},
            ],
        })


class OgcItemView(APIView):
    permission_classes = []

    def get(self, request, wsi):
        station = (
            Station.objects.filter(wigos_identifier=wsi, archived=False).first()
            or Station.objects.filter(archived=False).with_additional_wigos_identifier(wsi).first()
        )
        if station is None:
            return Response({"detail": f"No station with WIGOS identifier {wsi}"}, status=404)
        return Response(station.wmdrv2)
