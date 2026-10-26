"""方案 5.3：WSI 注册表与发布权威性。

节点是记录的唯一权威写入口，因此必须能回答一个问题：**这个 centre-id 有没有
权利发布这个 WSI？** 注册表就是这份授权的本地副本；发布时逐条比对，超范围
的在本地拒绝并留痕，注册表本身可导出给目录侧同步校验。

对外端点（全部挂在 /api/ 下）：

    GET    /wsi-allocations/                列表（登录可读）
    POST   /wsi-allocations/                新建区间
    PATCH  /wsi-allocations/<id>/           改区间 / 备注
    DELETE /wsi-allocations/<id>/           删除区间
    GET    /wsi-allocations/export?format=json|csv   供目录侧同步
    POST   /wsi-allocations/import          批量导入（json 或 csv 文本）
    GET    /audit/                          NF-6 操作审计（仅 staff）
"""
import csv
import io
import json
import logging

from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditLog, WsiAllocation
from .wsi import parse_wsi

logger = logging.getLogger(__name__)

ALLOCATION_REQUIRED_DEFAULT = True


def allocation_enforced() -> bool:
    return str(getattr(settings, "WNM_REQUIRE_ALLOCATION", ALLOCATION_REQUIRED_DEFAULT)).lower() == "true"


def _can_manage(user, issuer_identifier) -> bool:
    """写注册表：staff，或属于该 issuer 的用户组。"""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    from .models import WIGOSNodeGroup
    return WIGOSNodeGroup.objects.filter(
        issuer_identifier=issuer_identifier, group__user=user
    ).exists()


def _actor_name(user):
    return user.get_username() if getattr(user, "is_authenticated", False) else "anonymous"


def audit(action, station=None, user=None, **detail):
    """NF-6：落一条审计。任何情况下都不允许因为审计失败而中断主流程。"""
    try:
        AuditLog.objects.create(
            actor=user if getattr(user, "is_authenticated", False) else None,
            action=action,
            station=station,
            detail=detail,
        )
    except Exception:  # pragma: no cover - 审计失败不能阻断业务
        logger.exception("failed to write audit entry for %s", action)


def check_wsi_allocation(station):
    """校验一条记录的全部 WSI 是否都在注册表授权范围内。

    返回 ``(ok, reason, offenders)``。三种拒绝原因分开返回，调用方可以据此
    给出不同的提示：格式不合法是数据问题，未登记/超范围是授权问题。
    """
    offenders = []
    malformed = []
    for wsi in station.get_wigos_identifiers():
        parsed = parse_wsi(wsi)
        if parsed is None:
            malformed.append(wsi)
            continue
        issuer, series, number, _local = parsed
        covered = WsiAllocation.objects.filter(
            issuer_identifier=issuer,
            series=series,
            number_low__lte=number,
            number_high__gte=number,
        ).exists()
        if not covered:
            offenders.append(wsi)

    if malformed:
        return False, "malformed", malformed
    if offenders:
        return False, "out_of_range", offenders
    return True, None, []


# --------------------------------------------------------------------------- #
# 注册表 CRUD
# --------------------------------------------------------------------------- #
class WsiAllocationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        issuer = request.query_params.get("issuer")
        rows = WsiAllocation.objects.all()
        if issuer:
            try:
                rows = rows.filter(issuer_identifier=int(issuer))
            except ValueError:
                return Response({"detail": "'issuer' must be an integer."}, status=400)
        # 列表要带主键，否则前端拿不到 PATCH/DELETE 需要的 id；
        # 导出（给目录侧）不带，保持文件干净。
        return Response([row.as_export_dict(include_id=True) for row in rows])

    def post(self, request):
        payload = _allocation_payload(request.data)
        if "error" in payload:
            return Response(payload, status=400)
        if not _can_manage(request.user, payload["issuer"]):
            return Response({"detail": "You may not manage allocations for this centre-id."}, status=403)
        row = WsiAllocation.objects.create(
            issuer_identifier=payload["issuer"],
            series=payload["series"],
            number_low=payload["numberFrom"],
            number_high=payload["numberTo"],
            note=payload.get("note", ""),
        )
        audit("wsi_allocation_create", user=request.user, allocation=row.as_export_dict())
        return Response(row.as_export_dict(), status=201)


class WsiAllocationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, allocation_id):
        try:
            row = WsiAllocation.objects.get(pk=allocation_id)
        except WsiAllocation.DoesNotExist:
            return Response({"detail": f"Allocation {allocation_id} not found"}, status=404)
        if not _can_manage(request.user, row.issuer_identifier):
            return Response({"detail": "You may not manage allocations for this centre-id."}, status=403)

        # QueryDict 要先摊平，否则每个值都是列表（见 _scalar 的说明）。
        data = {key: _scalar(value) for key, value in request.data.items()}
        payload = _allocation_payload({**row.as_export_dict(), **data}, partial=True)
        if "error" in payload:
            return Response(payload, status=400)
        row.series = payload["series"]
        row.number_low = payload["numberFrom"]
        row.number_high = payload["numberTo"]
        row.note = payload.get("note", "")
        row.save()
        audit("wsi_allocation_update", user=request.user, allocation=row.as_export_dict())
        return Response(row.as_export_dict())

    def delete(self, request, allocation_id):
        try:
            row = WsiAllocation.objects.get(pk=allocation_id)
        except WsiAllocation.DoesNotExist:
            return Response({"detail": f"Allocation {allocation_id} not found"}, status=404)
        if not _can_manage(request.user, row.issuer_identifier):
            return Response({"detail": "You may not manage allocations for this centre-id."}, status=403)
        snapshot = row.as_export_dict()
        row.delete()
        audit("wsi_allocation_delete", user=request.user, allocation=snapshot)
        return Response(status=204)


def _scalar(value):
    """把 QueryDict 里的单元素列表还原成标量。

    DRF 的 request.data 在表单编码（multipart / urlencoded，也就是 PATCH 不带
    JSON content-type 时的默认形态）下是 QueryDict，`dict()` 之后每个值都变成
    列表 —— `int(["30"])` 必然抛异常，于是合法的 PATCH 被当成"值不是整数"退回
    400。这里统一收口，两种编码走同一条路径。
    """
    if isinstance(value, (list, tuple)):
        return value[-1] if value else None
    return value


def _allocation_payload(data, partial=False):
    """把请求体规整成 {issuer, series, numberFrom, numberTo, note}。

    PATCH 时允许只给部分字段，缺的沿用旧值；POST 时四个字段都必需。
    """
    required = () if partial else ("issuer", "numberFrom", "numberTo")
    out = {"issuer": None, "series": 0, "numberFrom": None, "numberTo": None, "note": ""}

    for key in ("issuer", "series", "numberFrom", "numberTo"):
        raw = _scalar(data.get(key))
        if raw in (None, ""):
            if key in required:
                return {"error": f"'{key}' is required."}
            continue
        try:
            out[key] = int(raw)
        except (TypeError, ValueError):
            return {"error": f"'{key}' must be an integer."}
    out["note"] = str(_scalar(data.get("note")) or "")

    if out["numberFrom"] is not None and out["numberTo"] is not None:
        if out["numberFrom"] < 0 or out["numberTo"] < 0:
            return {"error": "numberFrom/numberTo must not be negative."}
        if out["numberFrom"] > out["numberTo"]:
            return {"error": "numberFrom must not be greater than numberTo."}
    if out["issuer"] is not None and out["issuer"] < 0:
        return {"error": "'issuer' must not be negative."}
    return out


# --------------------------------------------------------------------------- #
# 导入 / 导出
# --------------------------------------------------------------------------- #
ALLOCATION_COLUMNS = ("issuer", "series", "numberFrom", "numberTo", "note")


class WsiAllocationExportView(APIView):
    """把注册表导出成标准文件，供目录侧同步校验。

    CSV 是目录侧最省事的形态（无需 JSON 解析），JSON 保留完整字段。两种格式
    的表头/键名一致，便于互相转换。
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = [row.as_export_dict() for row in WsiAllocation.objects.all()]
        fmt = (request.query_params.get("format") or "json").lower()
        if fmt == "csv":
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=list(ALLOCATION_COLUMNS))
            writer.writeheader()
            writer.writerows(rows)
            body = buffer.getvalue()
            response = Response(body, content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="wsi-allocations.csv"'
        else:
            body = json.dumps(
                {
                    "schema": "wigos-node/wsi-allocations/v1",
                    "count": len(rows),
                    "allocations": rows,
                },
                ensure_ascii=False,
                indent=2,
            )
            response = Response(json.loads(body), content_type="application/json")
            response["Content-Disposition"] = 'attachment; filename="wsi-allocations.json"'
        audit("wsi_allocation_export", user=request.user, count=len(rows), format=fmt)
        return response


class WsiAllocationImportView(APIView):
    """批量导入注册表。body 为 {"format": "json|csv", "data": <文本或数组>}。

    与 F-15 的摄取一样走 dry-run 语义：``dry_run: true`` 只校验不落库。
    逐行报告，一行坏不影响其余行。
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        fmt = (data.get("format") or "json").lower()
        raw = data.get("data")
        dry_run = bool(data.get("dry_run", False))

        try:
            items = _load_import_items(fmt, raw)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        results = []
        created = 0
        for index, item in enumerate(items):
            payload = _allocation_payload(item)
            if "error" in payload:
                results.append({"index": index, "status": "error", "message": payload["error"]})
                continue
            if not _can_manage(request.user, payload["issuer"]):
                results.append({"index": index, "status": "error",
                                "message": "You may not manage allocations for this centre-id."})
                continue
            if not dry_run:
                WsiAllocation.objects.create(
                    issuer_identifier=payload["issuer"],
                    series=payload["series"],
                    number_low=payload["numberFrom"],
                    number_high=payload["numberTo"],
                    note=payload.get("note", ""),
                )
            created += 1
            results.append({"index": index, "status": "ok", "allocation": payload})

        audit("wsi_allocation_import", user=request.user, accepted=created,
              rejected=len(results) - created, dry_run=dry_run)
        return Response({"dry_run": dry_run, "accepted": created,
                         "rejected": len(results) - created, "results": results})


def _load_import_items(fmt, raw):
    if fmt == "csv":
        if not isinstance(raw, str):
            raise ValueError("CSV import expects 'data' to be a string.")
        return list(csv.DictReader(io.StringIO(raw)))
    if fmt == "json":
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"data is not valid JSON: {exc}")
        if isinstance(raw, dict):
            raw = raw.get("allocations", [])
        if not isinstance(raw, list):
            raise ValueError("JSON import expects a list of allocations (or {allocations: [...]}).")
        return raw
    raise ValueError(f"Unsupported format '{fmt}'. Use json or csv.")


# --------------------------------------------------------------------------- #
# 审计查询
# --------------------------------------------------------------------------- #
class AuditLogListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"detail": "Audit log is restricted to node administrators."}, status=403)
        action = request.query_params.get("action")
        station_id = request.query_params.get("station")
        rows = AuditLog.objects.select_related("actor", "station").all()
        if action:
            rows = rows.filter(action=action)
        if station_id:
            try:
                rows = rows.filter(station_id=int(station_id))
            except ValueError:
                return Response({"detail": "'station' must be an integer."}, status=400)
        try:
            limit = int(request.query_params.get("limit", 200))
        except ValueError:
            limit = 200
        return Response([
            {
                "id": row.id,
                "action": row.action,
                "actor": _actor_name(row.actor) if row.actor else None,
                "station": row.station_id,
                "wsi": row.station.wigos_identifier if row.station_id else None,
                "detail": row.detail,
                "created": row.created,
            }
            for row in rows[: min(max(limit, 1), 1000)]
        ])
