"""Interoperability endpoints: export (F-16), ingest (F-15), WMDR1 import (F-21)
and record providers (F-13).

Everything that writes goes through ``api.stations`` so the WMDR2 schema and the
per-issuer permission rules are the same as for the web form; nothing here
bypasses validation.
"""
import logging

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import SAFE_METHODS, AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from . import exporters, importers, stations
from .models import RecordProvider, Station
from .stations import StationError

logger = logging.getLogger(__name__)

MAX_IMPORT_RECORDS = 500
FORMAT_META = {
    "csv": ("text/csv; charset=utf-8", "csv"),
    "json": ("application/geo+json", "json"),
    "xml": ("application/xml; charset=utf-8", "xml"),
}


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


def _selected_stations(request):
    raw_ids = request.query_params.getlist("station_id")
    include_archived = request.query_params.get("include_archived") in ("1", "true", "yes")
    queryset = Station.objects.filter(wmdrv2__isnull=False)
    if not include_archived:
        queryset = queryset.filter(archived=False)
    if raw_ids:
        ids = []
        for raw in raw_ids:
            if not raw.isdigit():
                raise ValueError(f"station_id 必须是数字，收到 '{raw}'")
            ids.append(int(raw))
        queryset = queryset.filter(id__in=ids)
    return queryset.order_by("id")


def _render(records, fmt, download_name):
    """Records -> HttpResponse in the requested format."""
    fmt = (fmt or "json").lower()
    if fmt not in FORMAT_META:
        raise ValueError(f"不支持的格式 '{fmt}'，可选 {sorted(FORMAT_META)}")
    content_type, extension = FORMAT_META[fmt]
    if fmt == "csv":
        body = exporters.records_to_csv(records)
    elif fmt == "xml":
        body = exporters.records_to_xml(records)
    else:
        body = exporters.records_to_geojson(records)
    response = HttpResponse(body, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{download_name}.{extension}"'
    return response


class ExportView(APIView):
    """GET /api/export/?format=csv|json|xml&station_id=1&station_id=2

    F-16: bulk export of the node's records in CSV, JSON or XML. Read-only and
    unauthenticated, like the single-record GET it is derived from.
    """

    permission_classes = [ReadOnly]

    def get(self, request):
        fmt = request.query_params.get("format", "json").lower()
        try:
            records = [station.wmdrv2 for station in _selected_stations(request)]
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        if not records:
            return Response({"detail": "没有匹配的记录可导出"}, status=404)
        stamp = timezone.now().strftime("%Y%m%d")
        try:
            return _render(records, fmt, f"wigos-wmdr2-{stamp}")
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)


class StationExportView(APIView):
    """GET /api/wmdrv2/<id>/export?format=csv|json|xml — one record."""

    permission_classes = [ReadOnly]

    def get(self, request, station_id):
        try:
            station = Station.objects.get(id=station_id)
        except Station.DoesNotExist:
            return Response({"detail": f"Station {station_id} not found"}, status=404)
        fmt = request.query_params.get("format", "json").lower()
        try:
            return _render([station.wmdrv2], fmt, f"wmdr2-{station.wigos_identifier}")
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)


# --------------------------------------------------------------------------- #
# F-15: ingest a payload (JSON / CSV / XML)
# --------------------------------------------------------------------------- #
def _payload_from_request(request):
    """(text, explicit_format, dry_run) from a multipart upload, a JSON body or raw text."""
    explicit = request.query_params.get("format")
    dry_run = request.query_params.get("dry_run") in ("1", "true", "yes")
    upload = request.FILES.get("file")
    if upload is not None:
        text = upload.read().decode("utf-8-sig")
        explicit = explicit or (upload.name.rsplit(".", 1)[-1].lower() if "." in upload.name else None)
        return text, explicit, dry_run
    if (request.content_type or "").startswith("multipart/") and upload is None:
        raise ValueError("multipart 请求需要 file 字段")
    body = request.data if isinstance(request.data, dict) else None
    if body is not None:
        dry_run = bool(body.get("dry_run", dry_run))
        explicit = explicit or body.get("format")
        if isinstance(body.get("records"), list):
            import json as _json
            return _json.dumps(body["records"]), "json", dry_run
        if "data" in body or "text" in body:
            return str(body.get("data") or body.get("text") or ""), explicit, dry_run
    raw = request.body.decode("utf-8-sig") if request.body else ""
    return raw, explicit, dry_run


def _create_many(user, records, dry_run):
    results = []
    with transaction.atomic():
        for index, record in enumerate(records):
            entry = {"index": index, "wsi": None}
            try:
                with transaction.atomic():
                    station = stations.create_station(user, record)
                entry.update(status="ok", station_id=station.id, wsi=station.wigos_identifier)
            except StationError as exc:
                entry.update(status="error", message=exc.message, wsi=(record or {}).get("id")
                             if isinstance(record, dict) else None)
                if exc.errors:
                    entry["errors"] = exc.errors[:10]
            results.append(entry)
        if dry_run:
            transaction.set_rollback(True)
    ok = sum(1 for r in results if r["status"] == "ok")
    return {"dry_run": dry_run, "summary": {"ok": ok, "error": len(results) - ok, "total": len(results)},
            "results": results}


class ImportView(APIView):
    """POST /api/import/ — F-15 batch ingest.

    Accepts ``multipart/form-data`` with a ``file`` field, or a JSON body
    ``{"format": "csv|json|xml", "data": "<text>", "dry_run": bool}``, or
    ``{"records": [...]}``. Every record is validated exactly like a form
    submission and one bad record does not abort the rest.
    """

    # Not ReadOnly: that would reject the POST before the view can answer 401.
    permission_classes = [AllowAny]
    http_method_names = ["post", "options"]

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)
        try:
            text, fmt, dry_run = _payload_from_request(request)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        if not (text or "").strip():
            return Response({"detail": "请求体为空：请上传 file 或提供 data 字段"}, status=400)
        try:
            records, fmt = importers.payload_to_records(text, fmt, now=timezone.now().isoformat())
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        if not records:
            return Response({"detail": "载荷中没有记录"}, status=400)
        if len(records) > MAX_IMPORT_RECORDS:
            return Response({"detail": f"单次最多 {MAX_IMPORT_RECORDS} 条记录"}, status=400)
        result = _create_many(request.user, records, dry_run)
        result["format"] = fmt
        return Response(result, status=200)


class Wmdr1ImportView(APIView):
    """POST /api/import/wmdr1/ — F-21: WMDR V1 import (V1 -> V2 mapping).

    Body: a V1 record, a list of V1 records, or ``{"records": [...]}``;
    optional ``dry_run``. Each converted record reports the fields that were
    filled with codelist placeholders (see ``importers.wmdr1_to_wmdr2``).
    """

    permission_classes = [AllowAny]
    http_method_names = ["post", "options"]

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)
        payload = request.data
        dry_run = bool(payload.get("dry_run")) if isinstance(payload, dict) else False
        try:
            converted = importers.wmdr1_payload_to_records(payload, now=timezone.now().isoformat())
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        if not converted:
            return Response({"detail": "载荷中没有记录"}, status=400)
        if len(converted) > MAX_IMPORT_RECORDS:
            return Response({"detail": f"单次最多 {MAX_IMPORT_RECORDS} 条记录"}, status=400)

        records = []
        mapping = []
        for index, item in enumerate(converted):
            mapping.append({
                "index": index,
                "placeholders": item["placeholders"],
                "ignored": item["ignored"],
                "error": item["error"],
            })
            records.append(item["record"])

        # Records that failed to map are reported without hitting the database.
        usable = [(index, record) for index, record in enumerate(records) if record is not None]
        results = []
        with transaction.atomic():
            for index, record in usable:
                entry = {"index": index, "wsi": record.get("id")}
                try:
                    with transaction.atomic():
                        station = stations.create_station(request.user, record)
                    entry.update(status="ok", station_id=station.id)
                except StationError as exc:
                    entry.update(status="error", message=exc.message)
                    if exc.errors:
                        entry["errors"] = exc.errors[:10]
                entry["placeholders"] = mapping[index]["placeholders"]
                results.append(entry)
            if dry_run:
                transaction.set_rollback(True)

        by_index = {item["index"]: item for item in results}
        for item in mapping:
            if item["error"]:
                by_index[item["index"]] = {"index": item["index"], "status": "error",
                                           "message": item["error"], "placeholders": []}
        ordered = [by_index[index] for index in sorted(by_index)]
        ok = sum(1 for r in ordered if r.get("status") == "ok")
        return Response({"dry_run": dry_run,
                         "summary": {"ok": ok, "error": len(ordered) - ok, "total": len(ordered)},
                         "results": ordered,
                         "converted": records}, status=200)


# --------------------------------------------------------------------------- #
# F-13: record providers
# --------------------------------------------------------------------------- #
PROVIDER_ROLES = ("owner", "operator", "dataProvider", "publisher", "funder", "other")


def _provider_payload(provider, implicit=False):
    return {
        "id": None if implicit else provider.id,
        "organization": provider.organization,
        "role": provider.role,
        "contact": provider.contact or {},
        "implicit": implicit,
        "created": None if implicit else provider.created,
    }


class StationProviderView(APIView):
    """GET/POST /api/wmdr2/<id>/providers/ — F-13, several providers per record.

    The record's owner is always reported (``implicit: true``) so a record never
    looks unowned, on top of any provider rows registered here.
    """

    permission_classes = [AllowAny]  # GET is public, POST authenticates itself

    def _station(self, station_id):
        try:
            return Station.objects.get(id=station_id), None
        except Station.DoesNotExist:
            return None, Response({"detail": f"Station {station_id} not found"}, status=404)

    def get(self, request, station_id):
        station, error = self._station(station_id)
        if error:
            return error
        owner = station.owner
        providers = [
            {"id": None, "organization": owner.get_username(), "role": "owner",
             "contact": {"emails": [{"value": owner.email}]} if owner.email else {},
             "implicit": True, "created": None}
        ]
        providers += [_provider_payload(p) for p in station.providers.all()]
        return Response({"station_id": station.id, "wsi": station.wigos_identifier,
                         "providers": providers})

    def post(self, request, station_id):
        if not request.user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)
        station, error = self._station(station_id)
        if error:
            return error
        if not (request.user.is_superuser
                or request.user.has_perm("change_station", station)
                or station.owner_id == request.user.id):
            return Response({"detail": "You do not have permission to change this station."}, status=403)
        data = request.data if isinstance(request.data, dict) else {}
        organization = (data.get("organization") or "").strip()
        role = (data.get("role") or "dataProvider").strip()
        if not organization:
            return Response({"detail": "organization is required"}, status=400)
        if role not in PROVIDER_ROLES:
            return Response({"detail": f"role 必须是 {list(PROVIDER_ROLES)} 之一"}, status=400)
        provider, created = RecordProvider.objects.get_or_create(
            station=station, organization=organization, role=role,
            defaults={"contact": data.get("contact") or {}, "created_by": request.user},
        )
        if not created:
            return Response({"detail": "该提供者（组织 + 角色）已登记"}, status=409)
        return Response(_provider_payload(provider), status=201)


class ProviderDetailView(APIView):
    """DELETE /api/providers/<id>/ — remove one registered provider."""

    permission_classes = [AllowAny]
    http_method_names = ["delete", "options"]

    def delete(self, request, provider_id):
        if not request.user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)
        try:
            provider = RecordProvider.objects.select_related("station").get(id=provider_id)
        except RecordProvider.DoesNotExist:
            return Response({"detail": "Provider not found"}, status=404)
        station = provider.station
        if not (request.user.is_superuser
                or request.user.has_perm("change_station", station)
                or station.owner_id == request.user.id):
            return Response({"detail": "You do not have permission to change this station."}, status=403)
        provider.delete()
        return Response(status=204)
