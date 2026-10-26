"""Rules shared by every endpoint that creates or changes a station: schema
validation, the per-issuer group check and object permissions. The single
station endpoints (views.Wmdrv2View) and the batch endpoint
(views.Wmdrv2BatchView) both go through here, so they can't drift apart."""

import json
import logging
from functools import cache
from pathlib import Path

from django.conf import settings
from django.db import IntegrityError
from guardian.shortcuts import assign_perm, get_objects_for_user
from jsonschema import Draft202012Validator

from .models import ADDITIONAL_WSI_SEPARATOR, Station, StationVersion, WIGOSNodeGroup

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "wmdr2-bundled.json"


class StationError(Exception):
    """A station couldn't be created or changed. `status` is the HTTP status the
    single-station endpoints answer with; `errors` lists schema failures."""

    def __init__(self, message, status=400, errors=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.errors = errors or []


@cache
def _validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    # Format checking matches ajv-formats on the frontend.
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def _error_path(error):
    return "/" + "/".join(str(part) for part in error.absolute_path)


def validation_errors(wmdrv2):
    """JSON Schema errors for a WMDR2 record, e.g.
    "/properties/observations/0: 'configurations' is a required property".
    Empty when the record is valid."""
    errors = sorted(_validator().iter_errors(wmdrv2), key=lambda e: list(map(str, e.absolute_path)))
    return [f"{_error_path(error)}: {error.message}" for error in errors]


def validate(wmdrv2, strict=True):
    """Check a record against the WMDR2 schema.

    Returns the list of problems (empty when valid). `strict=True` (the default,
    and the behaviour every caller relied on) raises StationError instead; set
    `strict=False` for drafts, where saving half-finished work is the whole
    point — the caller is expected to hand the problems back to the user.
    """
    if not isinstance(wmdrv2, dict):
        problem = "The record must be a JSON object."
        if strict:
            raise StationError(problem)
        return [problem]
    errors = validation_errors(wmdrv2)
    if errors and strict:
        raise StationError("The record is not valid against the WMDR2 schema.", errors=errors)
    return errors


def resolve_status(requested=None):
    """方案 5.6：新记录的初始状态。

    迁移里写死默认值会锁死部署策略，所以默认值由 STATION_DEFAULT_STATUS 决定：
    "submitted" 保持「建了就能发」的旧行为（演示、迁移存量数据），"draft" 则是
    强制走完 草稿 → 提交 → 校验 → 发布 的生产形态。
    """
    if requested in (Station.DRAFT, Station.SUBMITTED):
        return requested
    if requested:
        logger.warning("Ignoring unknown station status %r, falling back to the default", requested)
    configured = str(getattr(settings, "STATION_DEFAULT_STATUS", Station.SUBMITTED)).lower()
    if configured not in (Station.DRAFT, Station.SUBMITTED):
        # 拼错的配置如果静默吞掉，运维会以为策略生效了，实际没有。
        logger.warning(
            "STATION_DEFAULT_STATUS=%r is not one of draft/submitted, using %r",
            configured, Station.SUBMITTED,
        )
        return Station.SUBMITTED
    return configured


def issuer_of(wsi):
    parts = wsi.split("-")
    return parts[1] if len(parts) > 1 else wsi


def wsis_of(wmdrv2):
    """Primary and additional WIGOS identifiers of a record."""
    return Station(wmdrv2=wmdrv2).get_wigos_identifiers()


def user_issuers(user):
    """Issuers of identifiers the user may manage, as strings (e.g. {"756"})."""
    if not user.is_authenticated:
        return set()
    return {str(i) for i in WIGOSNodeGroup.objects.filter(group__user=user).values_list("issuer_identifier", flat=True)}


def check_issuers(user, wsis, action, issuers=None):
    """The user must be in a group for every issuer of identifier in `wsis`.
    Superusers bypass the check (Django convention)."""
    if user.is_superuser:
        return
    issuers = user_issuers(user) if issuers is None else issuers
    for issuer_id in dict.fromkeys(issuer_of(wsi) for wsi in wsis):
        if issuer_id not in issuers:
            raise StationError(
                f"You do not have permission to {action} a station for the issuer of identifier {issuer_id}.",
                status=403,
            )


def editable_station_ids(user):
    """IDs of the stations the user may change, by the same rules as
    update_station (object permission plus the issuer check on the stored
    identifiers).

    性能：原版 `for station in stations.only("id", "wmdrv2")` 会把**每一台**站的
    完整 WMDR2 JSON（含全部观测、联系人、标识符数组）从库里读出来再解析，
    只是为了拿里面的 WSI。台站上千条时，列表接口光这一项就要拉几十 MB。

    两次查询搞定，且第二次只取两个小的生成列：
      1. guardian 的 get_objects_for_user —— 拿到有对象权限的站；
      2. 按 id 取 (wigos_identifier, additional_wigos_identifiers)。
    这两个字段是 db_persist 的生成列，由数据库从 wmdrv2 里抽出来，值与
    get_wigos_identifiers() 一致，但不需要传大 JSON。
    """
    if not user.is_authenticated:
        return set()
    # Object permissions only, like user.has_perm('change_station', station):
    # issuer groups also hold the global change_station permission.
    permitted = get_objects_for_user(
        user, "api.change_station", klass=Station, accept_global_perms=False
    )
    if user.is_superuser:
        # 超管绕开 issuer 检查，也就没必要把标识符读出来了。
        return set(permitted.values_list("id", flat=True))

    issuers = user_issuers(user)
    rows = permitted.values_list("id", "wigos_identifier", "additional_wigos_identifiers")
    editable = set()
    for station_id, primary, additional in rows:
        # 生成列里附加标识符是 ",wsi1,wsi2," 这种形态（逗号不可能出现在 WSI 里）。
        wsis = [primary] if primary else []
        if additional:
            wsis.extend(w for w in additional.split(ADDITIONAL_WSI_SEPARATOR) if w)
        # 每台站都允许吗？等价于 check_issuers 的逐条判断，但不起异常、不重复算集合。
        if all(issuer_of(wsi) in issuers for wsi in wsis):
            editable.add(station_id)
    return editable


def assign_issuer_groups(station, wsis):
    """Lets the groups of every issuer in `wsis` change the station."""
    for issuer_id in dict.fromkeys(issuer_of(wsi) for wsi in wsis):
        node_groups = WIGOSNodeGroup.objects.filter(issuer_identifier=issuer_id) if issuer_id.isdigit() else []
        if not node_groups:
            logger.warning(f"No group found for issuer_identifier {issuer_id}. Station {station.id} will not be assigned to any group for this WSI.")
        for node_group in node_groups:
            assign_perm("change_station", node_group.group, station)


def _save(station):
    try:
        station.save()
    except ValueError as e:
        raise StationError(str(e)) from e
    except IntegrityError as e:
        raise StationError(f"The station could not be saved: {e}") from e


def _snapshot(station, operation, user):
    """F-8: keep an immutable copy of the record after every save."""
    last = station.versions.order_by("-version").values_list("version", flat=True).first() or 0
    StationVersion.objects.create(
        station=station,
        version=last + 1,
        wmdrv2=station.wmdrv2,
        operation=operation,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )


def create_station(user, wmdrv2, status=None):
    status = resolve_status(status)
    # 草稿允许带着 schema 问题落库（这就是"草稿保存"的意义），但把问题挂回
    # 实例上让调用方回给用户；提交状态的记录照旧严格校验。
    problems = validate(wmdrv2, strict=status != Station.DRAFT)
    wsis = wsis_of(wmdrv2)
    check_issuers(user, wsis, "create")
    station = Station(wmdrv2=wmdrv2, owner=user, status=status)
    _save(station)
    # after save so the station has a pk to attach object permissions to
    assign_perm("change_station", user, station)
    assign_issuer_groups(station, wsis)
    _snapshot(station, "create", user)
    station.schema_problems = problems
    return station


def update_station(user, station, wmdrv2, status=None):
    if not user.has_perm("change_station", station):
        raise StationError("You do not have permission to change this station.", status=403)
    # status 未给出时保持原状 —— 编辑一条已提交的记录不该把它退回草稿。
    new_status = resolve_status(status) if status is not None else station.status
    problems = validate(wmdrv2, strict=new_status != Station.DRAFT)
    old_wsis = station.get_wigos_identifiers()
    new_wsis = wsis_of(wmdrv2)
    # Old and new: the primary and additional IDs may both change.
    check_issuers(user, old_wsis + new_wsis, "update")
    station.wmdrv2 = wmdrv2  # save() updates the index fields
    station.status = new_status
    _save(station)  # owner is unchanged on update
    added = [wsi for wsi in new_wsis if issuer_of(wsi) not in {issuer_of(old) for old in old_wsis}]
    assign_issuer_groups(station, added)
    _snapshot(station, "update", user)
    station.schema_problems = problems
    return station
