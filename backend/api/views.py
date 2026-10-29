import logging
import re
from pathlib import Path

import django.http
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import (
    api_view,
)
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import stations
from .models import Station, WIGOSNodeGroup
from .renderers import CompactJSONRenderer
from .stations import StationError

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


@api_view(["GET", "POST"])
def geojson(request):
    """GeoJSON 出入口。

    原版只接受 POST，GET 返回 405；而 POST 的实现只是把入参原样回显，既不
    校验也不落库 —— 对 GIS 客户端来说是个假接口。这里两边都做实：

      GET  → 已发布台站的 FeatureCollection（GIS 客户端直接可画）
      POST → 接收 Feature 或 FeatureCollection，走与 /api/wmdrv2/ 相同的
             校验与权限路径后落库
    """
    if request.method == "GET":
        include_archived = request.query_params.get("include_archived") in ("1", "true", "yes")
        queryset = Station.objects.filter(wmdrv2__isnull=False)
        if not include_archived:
            queryset = queryset.filter(archived=False)
        editable = stations.editable_station_ids(request.user)
        features = [
            {
                "type": "Feature",
                "id": station.wigos_identifier,
                "geometry": station.wmdrv2.get("geometry"),
                "properties": station.wmdrv2.get("properties", {}),
            }
            for station in queryset
            # 草稿是未完成的工作，只有能改它的人看得见（与 my_stations 一致）
            if station.status != Station.DRAFT or station.id in editable
        ]
        return Response({"type": "FeatureCollection", "features": features})

    if not request.user.is_authenticated:
        return Response(
            {"detail": "Authentication credentials were not provided."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    body = request.data if isinstance(request.data, dict) else {}
    if body.get("type") == "FeatureCollection":
        incoming = body.get("features")
        if not isinstance(incoming, list):
            return Response({"detail": "A FeatureCollection needs a 'features' array."}, status=400)
    elif body.get("type") == "Feature":
        incoming = [body]
    else:
        return Response({"detail": "Payload must be a GeoJSON Feature or FeatureCollection."}, status=400)

    created, failures = [], []
    for index, feature in enumerate(incoming):
        if not isinstance(feature, dict) or "geometry" not in feature:
            failures.append({"index": index, "detail": "Not a GeoJSON Feature."})
            continue
        try:
            station = stations.create_station(request.user, feature)
        except StationError as e:
            failures.append({"index": index, "detail": e.message})
            continue
        created.append({"index": index, "station_id": station.id, "wsi": station.wigos_identifier})

    payload = {"created": created, "failed": failures}
    if not created:
        payload["detail"] = "No feature could be stored."
        return Response(payload, status=400)
    return Response(payload, status=201)


def api_not_found(request, *args, **kwargs):
    """`/api/` 下没有匹配到任何路由时的兜底。

    原版走 Django 默认的 404，返回的是 HTML 页面（`<!doctype html>...<title>
    Not Found</title>`）。SPA 的 fetch 拿到的 `res.json()` 会直接抛解析错误，
    调用方拿不到任何可判断的信息。统一成 JSON，并把可用路径列出来。
    """
    return JsonResponse(
        {
            "detail": "Not found.",
            "path": request.path,
            "hint": "See /api/ for the available endpoints, or check the HTTP method.",
        },
        status=404,
    )


MY_STATIONS_DEFAULT_LIMIT = 50
MY_STATIONS_MAX_LIMIT = 500


def _int_param(request, name, default, maximum=None, minimum=0):
    """把查询参数解析成整数。非数字/越界一律夹到合法区间，不抛 500 ——
    `?limit=abc` 是调用方的笔误，不该让整个列表接口挂掉。"""
    raw = request.query_params.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value < minimum:
        return minimum
    if maximum is not None and value > maximum:
        return maximum
    return value


@api_view(["GET"])
def my_stations(request):
    """当前用户可见的台站列表。

    原版不判登录就直接返回全部台站（匿名可见），且无分页、无搜索 ——
    台站上千条时一次性全量返回。这里三件事都补上：

      ?q=           按 WSI 或名称模糊搜索
      ?status=      只看 draft / submitted
      ?limit=&offset=  分页，默认 50 条，上限 500；limit=0 表示不分页（导出用）
      ?include_archived=1  含已归档

    总数放在 X-Total-Count 响应头里，响应体仍是数组，既有调用方不用改。
    另外 `editable_count` 也放在头里，前端"全选可编辑"不必自己数。
    """
    if not request.user.is_authenticated:
        # "my_stations" 的语义就是"我的"。原版对匿名返回全量，既与名字相反，
        # 也是公网部署的暴露面。公开读取走 /api/wmdrv2/wsi/<wsi> 与
        # /api/records/collections/... —— 那些才是面向目录收割的接口。
        return Response(
            {"detail": "Authentication credentials were not provided."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    include_archived = request.query_params.get("include_archived") in ("1", "true", "yes")
    queryset = Station.objects.filter(wmdrv2__isnull=False)
    if not include_archived:
        queryset = queryset.filter(archived=False)

    status_filter = (request.query_params.get("status") or "").strip().lower()
    if status_filter in (Station.DRAFT, Station.SUBMITTED):
        queryset = queryset.filter(status=status_filter)

    keyword = (request.query_params.get("q") or "").strip()
    if keyword:
        queryset = queryset.filter(
            Q(wigos_identifier__icontains=keyword) | Q(name__icontains=keyword)
        )

    queryset = queryset.order_by("id")

    editable = stations.editable_station_ids(request.user)

    # 方案 5.6：草稿是未完成的工作，不该出现在别人的列表里。
    # 只有能改这条记录的人（owner / issuer 组 / 超管）看得到自己的草稿。
    visible = [
        station
        for station in queryset
        if station.status != Station.DRAFT or station.id in editable
    ]

    total = len(visible)
    limit = _int_param(request, "limit", MY_STATIONS_DEFAULT_LIMIT, MY_STATIONS_MAX_LIMIT)
    offset = _int_param(request, "offset", 0)
    if limit:
        visible = visible[offset:offset + limit]
    elif offset:
        visible = visible[offset:]

    response = Response([
        {
            "station_id": station.id,
            "wsi": station.wigos_identifier,
            "name": station.name,
            "latitude": station.location.y,
            "longitude": station.location.x,
            "can_edit": station.id in editable,
            "archived": station.archived,
            "status": station.status,
        }
        for station in visible
    ])
    response["X-Total-Count"] = str(total)
    response["X-Editable-Count"] = str(len(editable))
    # 分页参数会变，别让中间层缓存住第一页。
    response["Vary"] = "Cookie"
    return response

@api_view(["GET"])
def check_wigosidentifiers(request):
    wigos_identifiers = request.query_params.getlist("wigos_identifier")
    if len(wigos_identifiers) == 0:
        return Response({"detail": "No WIGOS identifiers provided"}, status=400)
    results = {wigos_identifier: Station.objects.check_wigos_identifier(wigos_identifier) for wigos_identifier in wigos_identifiers}
    return Response(results)

@api_view(["GET"])
def my_issuer_of_identifiers(request):
    # 未登录时必须先返回 401。原来的写法直接拿 request.user 去过滤，AnonymousUser
    # 没有主键，Django 抛 TypeError -> 500（这是全后端唯一没有测试覆盖的接口）。
    if not request.user.is_authenticated:
        return Response(
            {"detail": "Authentication credentials were not provided."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    groups = WIGOSNodeGroup.objects.filter(group__user=request.user)
    issuer_identifiers = [group.issuer_identifier for group in groups]
    return Response({"issuer_of_identifiers": issuer_identifiers})    


def _error_response(error):
    # 403s keep their historical {"error": ...} shape, everything else {"detail": ...}.
    body = {"error" if error.status == status.HTTP_403_FORBIDDEN else "detail": error.message}
    if error.errors:
        body["errors"] = error.errors
    return Response(body, status=error.status)


class Wmdrv2View(APIView):
    permission_classes = [IsAuthenticated | ReadOnly]
    # GET serves the same bytes for every client (see renderers.py)
    renderer_classes = [CompactJSONRenderer]

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

        # 草稿只对能改它的人可见；匿名/他人拿到 404 而不是 403，
        # 免得把"这个 id 有一条草稿"这个事实泄露出去。
        if station.status == Station.DRAFT and station.id not in stations.editable_station_ids(request.user):
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

        try:
            stations.update_station(request.user, station, request.data,
                                    status=request.query_params.get("status"))
        except StationError as e:
            return _error_response(e)

        return Response({
            "message": f"WMDR2 data for station {station_id} updated successfully.",
            "station_id": station.id,
            "status": station.status,
            # 草稿才可能有 schema 问题（严格模式下 validate 早抛 400 了）
            "schema_problems": getattr(station, "schema_problems", []),
        }, status=200)

    def post(self, request, station_id=None):
        if station_id is not None:
            return Response(
                {"error": "Station ID should not be provided for creation."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            station = stations.create_station(request.user, request.data,
                                              status=request.query_params.get("status"))
        except StationError as e:
            return _error_response(e)

        return Response({
            "message": f"Station {station.id} created successfully.",
            "station_id": station.id,
            "status": station.status,
            "schema_problems": getattr(station, "schema_problems", []),
        }, status=201)

    def delete(self, request, station_id=None):
        """F-19: hard delete. Archive (/archive) is the reversible option; only
        the record owner or a superuser may destroy a record."""
        if station_id is None:
            return Response({"error": "Station ID is required for deletion."}, status=400)
        try:
            station = Station.objects.get(id=station_id)
        except Station.DoesNotExist:
            return Response({"detail": f"Station {station_id} not found"}, status=404)
        if not (request.user.is_superuser or station.owner_id == request.user.id):
            return Response({"detail": "Only the record owner or a superuser may delete a station."}, status=403)
        station.delete()
        return Response(status=204)


class Wmdrv2ByWsiView(APIView):
    """A record by any of its WIGOS identifiers, primary or additional. Each
    record's `self` link points here with its primary identifier."""

    permission_classes = [ReadOnly]
    renderer_classes = [CompactJSONRenderer]

    def get(self, request, wsi):
        # 匿名可读（目录收割要用），但草稿不能从这里漏出去 ——
        # 它是未完成的工作，只在"谁能改它"的界面里出现。
        visible = Station.objects.exclude(status=Station.DRAFT)
        station = (
            visible.filter(wigos_identifier=wsi).first()
            or visible.with_additional_wigos_identifier(wsi).first()
        )
        if station is None:
            return Response({"detail": f"No station with WIGOS identifier {wsi}"}, status=404)
        return Response(station.wmdrv2)


MAX_BATCH_UPDATES = 500


def _parse_station_id(value):
    # bool is an int subclass; reject it along with anything non-integer.
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


class Wmdrv2BatchView(APIView):
    """Reads and edits many existing stations at once. Never creates stations."""

    permission_classes = [IsAuthenticated | ReadOnly]

    def get(self, request):
        """?station_id=1&station_id=2 -> { "1": <wmdrv2>, "2": <wmdrv2> }.
        Unknown IDs are left out."""
        raw_ids = request.query_params.getlist("station_id")
        ids = [_parse_station_id(raw) for raw in raw_ids]
        if not ids or None in ids:
            return Response({"detail": "Provide one or more numeric station_id parameters."}, status=400)
        if len(ids) > MAX_BATCH_UPDATES:
            return Response({"detail": f"At most {MAX_BATCH_UPDATES} stations can be read at once."}, status=400)
        return Response({str(station.id): station.wmdrv2 for station in Station.objects.filter(id__in=ids)})

    def post(self, request):
        """Body: { "dry_run": bool, "updates": [{ "station_id": int, "wmdrv2": {...} }] }.

        Every update runs in its own savepoint inside one transaction: a failing
        update is rolled back alone and later updates see the earlier ones (so
        the same WIGOS ID given to two stations in one batch is caught). A dry
        run rolls everything back at the end."""
        body = request.data if isinstance(request.data, dict) else {}
        updates = body.get("updates")
        dry_run = body.get("dry_run", False)
        if not isinstance(updates, list) or not isinstance(dry_run, bool):
            return Response({"detail": "Expected { \"dry_run\": bool, \"updates\": [...] }."}, status=400)
        if len(updates) > MAX_BATCH_UPDATES:
            return Response({"detail": f"At most {MAX_BATCH_UPDATES} updates are allowed per request."}, status=400)

        results = []
        with transaction.atomic():
            for index, update in enumerate(updates):
                results.append(self._apply(request.user, index, update))
            if dry_run:
                transaction.set_rollback(True)

        summary = {"ok": sum(r["status"] == "ok" for r in results)}
        summary["error"] = len(results) - summary["ok"]
        return Response({"dry_run": dry_run, "summary": summary, "results": results})

    def _apply(self, user, index, update):
        update = update if isinstance(update, dict) else {}
        station_id = _parse_station_id(update.get("station_id"))
        wmdrv2 = update.get("wmdrv2")
        result = {"index": index, "station_id": station_id, "wsi": None}
        try:
            if station_id is None:
                raise StationError("A numeric station_id is required. Batch operations never create stations.")
            try:
                station = Station.objects.select_for_update().get(id=station_id)
            except Station.DoesNotExist:
                raise StationError(f"Station {station_id} not found.", status=404)
            result["wsi"] = station.wigos_identifier
            with transaction.atomic():  # savepoint: a failure only undoes this update
                stations.update_station(user, station, wmdrv2)
            result["wsi"] = wmdrv2.get("id")
            result["status"] = "ok"
        except StationError as e:
            result.update(status="error", message=e.message)
            if e.errors:
                result["errors"] = e.errors
        return result
