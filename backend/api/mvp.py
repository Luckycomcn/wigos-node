"""MVP-completion endpoints (F-1..F-24 gaps on top of the existing API).

Everything here is additive: the existing /api/wmdrv2/ endpoints keep their
behaviour, and the rules that guard writes are the ones in api/stations.py.
"""
import logging
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import publishers, registry, rules, stations
from .diffing import diff_records
from .models import (
    PublishedRecord,
    Station,
    StationGrade,
    StationGroup,
    StationTemplate,
    StationVersion,
)
from publishing.base import Operation
from publishing.generators.wnm import create_wnm as _create_wnm
from publishing.wmdr2 import render_record as _render_record
from publishing.wmdr2 import record_file_name as _record_file_name
from .stations import StationError


# --------------------------------------------------------------------------- #
# WNM 生成（上游 194dbb1 把 api/wnm.py 整体搬进 publishing/）
#
# 上游删掉了 backend/api/wnm.py，同一套逻辑现在在 publishing/generators/wnm.py。
# 这里的发布流程（POST /api/wmdrv2/<id>/publish）早于上游重构就存在，所以保持
# 自己的入口不变，只把实现指向 publishing —— 两份 WNM 不再各写一遍。
#
# 与上游函数的差异只有一处：上游 create_wnm 要求显式传 href / centre_id，因为
# 它的调用方是"先存文件、拿到真链接再发通知"的 outbox 流程；本模块自己写
# webstorage 并自己拼链接，所以在这里把这两个参数从 settings 补上。
# --------------------------------------------------------------------------- #
CREATE = "canonical"
UPDATE = "update"
DELETE = "deletion"

# 上面三个是本模块对外沿用的取值（它们同时是 WNM 里的 link rel: canonical /
# update / deletion）；上游 publishing 的 Operation 是另一套词表（create /
# update / delete），两者不能混着传 —— 这里显式翻译一次。
_OPERATIONS = {
    CREATE: Operation.CREATE,
    UPDATE: Operation.UPDATE,
    DELETE: Operation.DELETE,
}


def _wnm_href(wmdrv2):
    """本模块约定的公开链接：WNM_STORAGE_URL + 记录文件名。"""
    name = _record_file_name(wmdrv2, settings.WNM_CENTRE_ID)
    return f"{settings.WNM_STORAGE_URL.rstrip('/')}/{quote(name)}"


def create_station_wnm(station, operation=CREATE, pubtime=None):
    """为已保存的 Station 生成 WNM。不删除时以库里的存储副本为准——WNM 的
    integrity 必须描述真正写进 webstorage 的那份字节，而不是内存里又渲染一遍。"""
    try:
        upstream_operation = _OPERATIONS[operation]
    except KeyError:
        raise ValueError(
            f"Unknown WNM operation '{operation}', expected one of {tuple(_OPERATIONS)}"
        ) from None

    wmdrv2 = station.wmdrv2
    if upstream_operation is not Operation.DELETE:
        # 读回库里的副本，与 API 输出同一种键序；已被删除的行取不到，而删除
        # 类通知本来也不带 integrity。
        wmdrv2 = Station.objects.values_list("wmdrv2", flat=True).get(pk=station.pk)
    content = None if upstream_operation is Operation.DELETE else _render_record(wmdrv2)
    return _create_wnm(
        wmdrv2,
        upstream_operation,
        href=_wnm_href(wmdrv2),
        centre_id=settings.WNM_CENTRE_ID,
        content=content,
        pubtime=pubtime,
    )


def record_file_name(wmdrv2):
    """webstorage 里的文件名（centre_id 由配置提供，与上游同名函数一致）。"""
    return _record_file_name(wmdrv2, settings.WNM_CENTRE_ID)


def render_wmdrv2(wmdrv2):
    """写进 webstorage 的字节；WNM 的 integrity 与 length 都按它计算。"""
    return _render_record(wmdrv2)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #
def _can_change(user, station):
    return user.is_authenticated and user.has_perm("change_station", station)


def _can_view(user, station):
    """只读权限：能改的人当然能看，另外显式拿到 view_station 的只读角色也能看。

    上游只 assign 了 change_station，所以这里不能只查 view_station，否则连
    站点所有者都读不到自己的历史。
    """
    if not user.is_authenticated:
        return False
    return user.has_perm("change_station", station) or user.has_perm("view_station", station)


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
        if not _can_view(request.user, station):
            return Response({"detail": "You do not have permission to read this station."}, status=403)
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


class StationHistoryDiffView(APIView):
    """F-8 变更对比：`?from=<旧版本>&to=<新版本>`，返回路径级差异。

    两个参数都可省略：都不给时对比「上一版 → 最新版」；只给 to 时从最早版本
    开始；只给 from 时对比到最新版。
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, station_id):
        station, error = _station_or_error(station_id)
        if error:
            return error
        if not _can_view(request.user, station):
            return Response({"detail": "You do not have permission to read this station."}, status=403)

        versions = list(station.versions.order_by("version"))
        if not versions:
            return Response({"detail": "This station has no versions yet."}, status=404)

        selected = {}
        for name in ("from", "to"):
            raw = request.query_params.get(name)
            if raw is None:
                selected[name] = None
                continue
            try:
                selected[name] = int(raw)
            except (TypeError, ValueError):
                return Response({"detail": f"'{name}' must be an integer version number."}, status=400)

        known = {v.version: v for v in versions}
        for name in ("from", "to"):
            if selected[name] is not None and selected[name] not in known:
                return Response(
                    {"detail": f"Version {selected[name]} not found. Available: "
                               f"{min(known)}-{max(known)}."},
                    status=404,
                )

        if selected["from"] is None and selected["to"] is None:
            if len(versions) < 2:
                return Response({"detail": "Need at least two versions to compare. "
                                          "Pass ?from= and ?to= explicitly."}, status=400)
            old, new = versions[-2], versions[-1]
        else:
            old = known[selected["from"] if selected["from"] is not None else versions[0].version]
            new = known[selected["to"] if selected["to"] is not None else versions[-1].version]
            if old.version == new.version:
                return Response({"detail": "from and to are the same version; nothing to compare."}, status=400)
            if old.version > new.version:
                return Response({"detail": "from must be older than to."}, status=400)

        body = diff_records(old.wmdrv2, new.wmdrv2)
        body.update({
            "station_id": station.id,
            "wsi": station.wigos_identifier,
            "from": old.version,
            "to": new.version,
        })
        return Response(body)


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
class StationSubmitView(APIView):
    """方案 5.6 工作流：草稿 → 提交 → 校验 → 发布。

    提交是把草稿交出去的那一步，所以在这里把关：schema 有问题就退回去改，
    业务规则不通过也退回去。通过之后记录才进入 submitted，此后才可发布。
    允许醒目的 README 式提示 —— 取消/退回由编辑者自己决定是否编辑内容。
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, station_id):
        station, error = _station_or_error(station_id)
        if error:
            return error
        if not _can_change(request.user, station):
            return Response(
                {"detail": "You do not have permission to submit this station."}, status=403
            )

        if station.status != Station.DRAFT:
            return Response(
                {"status": station.status, "already_submitted": station.status == Station.SUBMITTED},
                status=200,
            )

        # 1) WMDR2 schema —— 草稿容忍的问题，在这里必须已经修好
        schema_problems = stations.validate(station.wmdrv2, strict=False)
        if schema_problems:
            registry.audit(
                "submit_rejected", station=station, user=request.user,
                reason="schema", errors=schema_problems[:10],
            )
            return Response(
                {"detail": "The record does not yet satisfy the WMDR2 schema.",
                 "reason": "schema", "errors": schema_problems},
                status=400,
            )

        # 2) 业务规则 —— 与发布用同一套口径，避免"提交了才发现发不出去"
        rule_result = rules.check_record(station.wmdrv2)
        if not rule_result["ok"]:
            registry.audit(
                "submit_rejected", station=station, user=request.user,
                reason="business_rules",
                errors=[item["code"] for item in rule_result["errors"]],
            )
            return Response(
                {"detail": "This record does not pass the WMDR2 business rules.",
                 "reason": "business_rules", "errors": rule_result["errors"],
                 "warnings": rule_result["warnings"]},
                status=400,
            )

        station.status = Station.SUBMITTED
        station.save(update_fields=["status"])
        registry.audit(
            "submit", station=station, user=request.user,
            wsi=station.wigos_identifier,
            warnings=[item["code"] for item in rule_result["warnings"]],
        )
        return Response(
            {"status": station.status, "submitted": True,
             "warnings": rule_result["warnings"]},
            status=200,
        )


class StationPublishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, station_id):
        station, error = _station_or_error(station_id)
        if error:
            return error
        if not _can_change(request.user, station):
            return Response({"detail": "You do not have permission to publish this station."}, status=403)

        # 方案 5.6：只有提交过的记录可以发布。草稿允许内容不完整，放出去就
        # 会把不合格的数据灌进目录，所以在本地就挡住。
        if station.status == Station.DRAFT:
            registry.audit(
                "publish_rejected", station=station, user=request.user,
                reason="draft", wsi=station.wigos_identifier,
            )
            return Response(
                {"detail": "Draft records cannot be published. Submit them first "
                           "(POST /api/wmdrv2/<id>/submit).",
                 "reason": "draft", "status": station.status},
                status=403,
            )

        # 方案 5.3：发布权威性。目标 WSI 必须落在本 centre-id 的授权范围内，
        # 否则本地直接拒绝——超范围发布在本地即被拒绝并留痕（NF-6）。
        # WNM_REQUIRE_ALLOCATION=false 时跳过，仅用于把未登记的历史数据先跑起来。
        if registry.allocation_enforced():
            allowed, reason, offenders = registry.check_wsi_allocation(station)
            if not allowed:
                registry.audit(
                    "publish_rejected", station=station, user=request.user,
                    reason=reason, offenders=offenders,
                )
                if reason == "malformed":
                    detail = ("These WIGOS identifiers are not well formed and cannot be "
                              f"checked against the registry: {offenders}")
                else:
                    detail = ("These WIGOS identifiers are outside the allocation granted to "
                              f"this node: {offenders}. Import the WSI registry first "
                              "(POST /api/wsi-allocations/import).")
                return Response({"detail": detail, "reason": reason, "offenders": offenders}, status=403)

        operation = (request.data or {}).get("operation", "canonical")
        op = {"canonical": CREATE, "create": CREATE, "update": UPDATE}.get(operation)
        if op is None:
            return Response({"detail": "operation must be canonical or update"}, status=400)

        # F-9：业务规则 + 受控词表。schema 合法不等于业务上说得通，所以在真正
        # 生成 WNM 之前先自检；WNM_ENFORCE_RULES=false 可降级为只警告。
        rule_result = rules.check_record(station.wmdrv2)
        if not rule_result["ok"] and str(
            getattr(settings, "WNM_ENFORCE_RULES", "true")
        ).lower() == "true":
            registry.audit(
                "publish_rejected", station=station, user=request.user,
                reason="business_rules",
                errors=[item["code"] for item in rule_result["errors"]],
            )
            return Response(
                {
                    "detail": "This record does not pass the WMDR2 business rules.",
                    "reason": "business_rules",
                    "errors": rule_result["errors"],
                    "warnings": rule_result["warnings"],
                },
                status=400,
            )

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

        # 方案 5.5：按 WNM_PUBLISH_STRATEGY 投递到本地代理/全局代理/本国 WIS2
        # 节点/直连目录。每条通道独立成败，本地发布本身不受影响。
        delivery = publishers.deliver(wnm)
        delivered_channels = publishers.delivered_channels(delivery)

        registry.audit(
            "publish", station=station, user=request.user,
            operation=operation, url=url, delivered=bool(delivered_channels),
            channels=delivered_channels, wsi=station.wigos_identifier,
        )

        return Response(
            {
                "published": True,
                "url": url,
                "delivered": bool(delivered_channels),
                "publication_id": record.id,
                "wnm": wnm,
                # 逐通道明细，便于运维判断是代理不通还是 WIS2 节点拒收
                "delivery": [item.as_dict() for item in delivery],
            },
            status=201,
        )


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

# F-14: what this node actually implements, declared instead of implied.
OGC_CONFORMANCE = [
    "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
    "http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/sorting",
]

MAX_LIMIT = 1000
CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"


def _int_param(request, name, default):
    """Query params must not turn into 500s (F-14 conformance: 400 on bad input)."""
    raw = request.query_params.get(name)
    if raw in (None, ""):
        return default, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, Response({"detail": f"{name} must be an integer, got '{raw}'"}, status=400)
    if value < 0:
        return None, Response({"detail": f"{name} must be >= 0"}, status=400)
    return value, None


def _bbox_param(request):
    """bbox=minLon,minLat[,minZ],maxLon,maxLat[,maxZ] -> (geometry, error)."""
    raw = request.query_params.get("bbox")
    if not raw:
        return None, None
    try:
        values = [float(part) for part in raw.split(",")]
    except ValueError:
        return None, Response({"detail": f"bbox 必须是数字，收到 '{raw}'"}, status=400)
    if len(values) == 4:
        min_lon, min_lat, max_lon, max_lat = values
    elif len(values) == 6:
        min_lon, min_lat, _, max_lon, max_lat, _ = values
    else:
        return None, Response(
            {"detail": "bbox 必须是 4 或 6 个数字（minLon,minLat[,minZ],maxLon,maxLat[,maxZ]）"},
            status=400,
        )
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180
            and -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        return None, Response({"detail": "bbox 超出经纬度范围（CRS84）"}, status=400)
    if min_lon > max_lon or min_lat > max_lat:
        return None, Response({"detail": "bbox 的最小值必须小于等于最大值"}, status=400)
    return Polygon.from_bbox((min_lon, min_lat, max_lon, max_lat)), None


def _datetime_filter(value):
    """datetime=RFC3339 | start/.. | ../end | start/end -> Q object."""
    if not value:
        return None
    parts = value.split("/")
    if len(parts) > 2:
        raise ValueError("datetime 只支持 'instant'、'start/..'、'../end' 或 'start/end'")
    start = parts[0] if parts and parts[0] not in ("", "..") else None
    end = parts[1] if len(parts) == 2 and parts[1] not in ("", "..") else None
    if start is None and end is None:
        return None
    filters = Q()
    for field in ("updated", "created"):
        key = f"wmdrv2__properties__{field}"
        if start:
            filters |= Q(**{f"{key}__gte": start})
        if end:
            filters |= Q(**{f"{key}__lte": end})
    return filters


class OgcConformanceView(APIView):
    """GET /records/conformance — declared conformance classes (F-14)."""

    permission_classes = []

    def get(self, request):
        return Response({"conformsTo": OGC_CONFORMANCE})


class OgcCollectionsView(APIView):
    permission_classes = []

    def get(self, request):
        base = request.build_absolute_uri().rstrip("/").rsplit("/", 1)[0]
        return Response({
            "collections": [{
                "id": COLLECTION_ID,
                "title": "WIGOS Observing Facility Metadata",
                "description": "WMDR2 records held by this WIGOS node",
                "itemType": "feature",
                "crs": [CRS84],
                "bbox": None,
                "links": [
                    {"href": f"{base}/{COLLECTION_ID}/items",
                     "rel": "items", "type": "application/geo+json"},
                ],
            }],
            "links": [{"href": request.build_absolute_uri(), "rel": "self", "type": "application/json"}],
        })


class OgcCollectionView(APIView):
    """GET /records/collections/<id> — one collection's metadata."""

    permission_classes = []

    def get(self, request, collection_id):
        if collection_id != COLLECTION_ID:
            return Response({"detail": f"Unknown collection '{collection_id}'"}, status=404)
        base = request.build_absolute_uri().rstrip("/")
        return Response({
            "id": COLLECTION_ID,
            "title": "WIGOS Observing Facility Metadata",
            "description": "WMDR2 records held by this WIGOS node",
            "itemType": "feature",
            "crs": [CRS84],
            "links": [
                {"href": f"{base}/items", "rel": "items", "type": "application/geo+json"},
                {"href": request.build_absolute_uri(), "rel": "self",
                 "type": "application/json"},
            ],
        })


class OgcItemsView(APIView):
    permission_classes = []

    def get(self, request, collection_id):
        if collection_id != COLLECTION_ID:
            return Response({"detail": f"Unknown collection '{collection_id}'"}, status=404)

        limit, error = _int_param(request, "limit", 100)
        if error:
            return error
        offset, error = _int_param(request, "offset", 0)
        if error:
            return error
        limit = max(1, min(limit or 100, MAX_LIMIT))

        geometry, error = _bbox_param(request)
        if error:
            return error

        qs = Station.objects.filter(archived=False)
        # 草稿是未完成的工作，只在"谁能改它"的界面里出现（my_stations）。
        # OGC API 是给目录收割用的公开接口，匿名可达 —— 不过滤的话草稿会从这里
        # 漏出去，绕过 my_stations 的可见性规则。
        qs = qs.exclude(status=Station.DRAFT)
        if geometry is not None:
            qs = qs.filter(location__within=geometry)
        try:
            filters = _datetime_filter(request.query_params.get("datetime"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        if filters is not None:
            qs = qs.filter(filters)

        total = qs.count()
        features = [s.wmdrv2 for s in qs.order_by("id")[offset:offset + limit]]
        base = request.build_absolute_uri().split("?")[0]
        links = [
            {"href": request.build_absolute_uri(), "rel": "self", "type": "application/geo+json"},
            {"href": base.rsplit("/items", 1)[0], "rel": "collection", "type": "application/json"},
        ]
        if offset + len(features) < total:
            links.append({"href": f"{base}?limit={limit}&offset={offset + limit}",
                          "rel": "next", "type": "application/geo+json"})
        if offset > 0:
            links.append({"href": f"{base}?limit={limit}&offset={max(0, offset - limit)}",
                          "rel": "prev", "type": "application/geo+json"})
        return Response({
            "type": "FeatureCollection",
            "features": features,
            "numberMatched": total,
            "numberReturned": len(features),
            "timeStamp": timezone.now().isoformat(),
            "links": links,
        })


class OgcItemView(APIView):
    permission_classes = []

    def get(self, request, collection_id, wsi):
        if collection_id != COLLECTION_ID:
            return Response({"detail": f"Unknown collection '{collection_id}'"}, status=404)
        station = (
            Station.objects.filter(wigos_identifier=wsi, archived=False)
            .exclude(status=Station.DRAFT).first()
            or Station.objects.filter(archived=False)
            .exclude(status=Station.DRAFT)
            .with_additional_wigos_identifier(wsi).first()
        )
        if station is None:
            return Response({"detail": f"No station with WIGOS identifier {wsi}"}, status=404)
        return Response(station.wmdrv2)


class WebstorageView(APIView):
    """公开只读的 WIS2 风格 webstorage。

    `POST /api/wmdrv2/<id>/publish` 把 WMDR2 字节写到 ``WNM_STORAGE_DIR``，并把
    ``WNM_STORAGE_URL + filename`` 作为消息里的 ``links[].href`` 发出去。如果没
    有这个视图，那条链接就是 404 —— 节点→目录 的发布链路在演示里是断的。

    语义按 WIS2 惯例：消息文件本就是公开可下载的，所以匿名可读、只允许 GET/HEAD。
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ["get", "head"]

    def get(self, request, filename):
        # <str:filename> 已排除 "/"，这里再挡掉 ".." 与隐藏文件
        if filename.startswith(".") or Path(filename).name != filename:
            return Response({"detail": "invalid filename"}, status=400)

        storage_dir = Path(getattr(settings, "WNM_STORAGE_DIR", settings.BASE_DIR / "webstorage"))
        target = storage_dir / filename
        if not target.is_file():
            return Response({"detail": f"not found: {filename}"}, status=404)

        payload = target.read_bytes()
        response = HttpResponse(payload, content_type="application/geo+json")
        response["Content-Length"] = str(len(payload))
        response["Cache-Control"] = "public, max-age=60"
        return response

    def head(self, request, filename):
        """HEAD 保留响应头（含 Content-Length），但不返回 body。"""
        response = self.get(request, filename)
        if isinstance(response, HttpResponse):
            length = response.get("Content-Length", "")
            response.content = b""
            if length:
                response["Content-Length"] = length
        return response
