"""F-9 业务规则校验。

WMDR2 的 schema 只管"字段类型和必填项是否齐全"，管不了业务上的自相矛盾。
这里放一组不依赖数据库的规则，用于发布前的自检，避免"结构合法但业务说不通"
的记录被发到目录侧。

与目录侧的口径差异：方案 5.4 要求本地自检与目录同一套 pywmdr ETS。ETS 是
可选的（见 api/ets.py），装不上时以本模块的规则集 + schema 校验兜底；ETS
装得上时两者都跑，结果合并。

规则分两档：

* ``error``   —— 一定不成立（日期倒挂、坐标互相矛盾），默认阻断发布；
* ``warning`` —— 大概率有问题但可能存在合法例外（没有观测变量、缺联系人），
                 只提示不阻断。

新增规则只需往 RULES 里加一项，check 签名统一为 ``record -> list[str]``。
"""
import logging
from typing import Callable, List, NamedTuple

from . import codelist_check

logger = logging.getLogger(__name__)

__all__ = ["RULES", "check_record", "rule_codes"]


class Rule(NamedTuple):
    code: str
    severity: str  # error | warning
    title: str
    check: Callable[[dict], List[str]]


def _observations(record):
    props = record.get("properties") or {}
    return props.get("observations") or []


def _first_observation_time(record):
    for observation in _observations(record):
        for config in (observation.get("configurations") or []):
            time = config.get("time") or {}
            interval = time.get("interval") or []
            if interval:
                return interval[0]
    return None


def check_has_observation(record):
    """WMDR2 记录存在的意义是描述"观测什么"，没有 observation 基本是废记录。"""
    return [] if _observations(record) else ["properties.observations is empty"]


def check_observed_variables(record):
    """有观测时段但没有观测变量，目录侧无法判断这条记录覆盖什么。

    WMDR2 的字段名是 ``observedProperty``（单数，一个概念对象），不是
    ``observedVariables``——写错字段名会让这条规则永远报警。
    """
    if not _observations(record):
        return []
    missing = [
        f"observations[{index}]"
        for index, observation in enumerate(_observations(record))
        if not (observation.get("observedProperty") or {})
    ]
    return [f"{item} has no observedProperty" for item in missing]


def check_has_contact(record):
    props = record.get("properties") or {}
    return [] if (props.get("contacts") or []) else ["properties.contacts is empty"]


def check_dates_in_order(record):
    """dateEstablished 晚于 created/updated 是时间倒挂，一定是错的。"""
    props = record.get("properties") or {}
    established = props.get("dateEstablished")
    if not established:
        return []
    problems = []
    for key in ("created", "updated"):
        later = props.get(key)
        if later and str(established) > str(later):
            problems.append(f"dateEstablished ({established}) is after {key} ({later})")
    return problems


def check_geometry_matches_coordinates(record):
    """geometry 与 properties 里的 latitude/longitude 必须指向同一个点。

    两处都填且不一致时，下游不知道该信哪个；只有一处时不算问题。
    """
    props = record.get("properties") or {}
    geometry = record.get("geometry") or {}
    lat, lon = props.get("latitude"), props.get("longitude")
    if lat is None or lon is None:
        return []
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        return []
    coordinates = geometry.get("coordinates") or []
    if len(coordinates) < 2:
        return []
    gx, gy = coordinates[0], coordinates[1]
    try:
        same = abs(float(gx) - float(lon)) < 1e-6 and abs(float(gy) - float(lat)) < 1e-6
    except (TypeError, ValueError):
        return ["geometry coordinates are not numeric"]
    return [] if same else [f"geometry {coordinates} disagrees with latitude/longitude {lat}/{lon}"]


def check_latitude_range(record):
    props = record.get("properties") or {}
    problems = []
    lat = props.get("latitude")
    if lat is not None:
        try:
            value = float(lat)
        except (TypeError, ValueError):
            problems.append(f"latitude '{lat}' is not numeric")
        else:
            if not -90 <= value <= 90:
                problems.append(f"latitude {value} is outside -90..90")
    lon = props.get("longitude")
    if lon is not None:
        try:
            value = float(lon)
        except (TypeError, ValueError):
            problems.append(f"longitude '{lon}' is not numeric")
        else:
            if not -180 <= value <= 180:
                problems.append(f"longitude {value} is outside -180..180")
    return problems


def check_wsi_present(record):
    return [] if record.get("id") else ["record has no id (WIGOS identifier)"]


def check_codelisted_values(record):
    """受控词表校验（F-9 第三部分）。

    schema 只查"是不是带 id 的对象"，这里查 id 是否真是 WMDS 里的概念。
    与目录侧 ETS 的 codelisted-values 测试同口径——本地码表快照缺文件时
    该项自动跳过，不会因为没同步码表就误判。
    """
    try:
        return codelist_check.unknown_concepts(record)
    except Exception as exc:  # pragma: no cover - 码表读取异常
        logger.exception("codelist check failed")
        return [f"codelist check failed to run: {exc}"]


RULES = [
    Rule("wsi-present", "error", "Record carries a WIGOS identifier", check_wsi_present),
    Rule("has-observation", "warning", "At least one observation block", check_has_observation),
    Rule("observed-variables", "warning", "Every observation lists observed variables", check_observed_variables),
    Rule("has-contact", "warning", "At least one contact", check_has_contact),
    Rule("dates-in-order", "error", "dateEstablished is not after created/updated", check_dates_in_order),
    Rule("geometry-matches-coordinates", "error", "geometry and latitude/longitude agree",
         check_geometry_matches_coordinates),
    Rule("lat-lon-range", "error", "latitude/longitude within valid ranges", check_latitude_range),
    Rule("codelisted-values", "error", "concept ids exist in the WMDS codelists",
         check_codelisted_values),
]


def rule_codes():
    return [rule.code for rule in RULES]


def check_record(record):
    """跑完整套规则，返回按 severity 分组的问题列表。

    任何单条规则抛异常都不应让整个校验失败——一条坏规则不该堵死发布流程，
    记日志后按"跳过该规则"处理。
    """
    errors: List[dict] = []
    warnings: List[dict] = []
    record = record if isinstance(record, dict) else {}
    for rule in RULES:
        try:
            messages = rule.check(record) or []
        except Exception as exc:  # pragma: no cover - 规则自身出错
            logger.exception("business rule %s crashed", rule.code)
            messages = [f"rule {rule.code} failed to run: {exc}"]
            # 规则崩溃本身是缺陷，按 warning 报出来而不是静默吞掉
            warnings.append({"code": rule.code, "rule": rule.title, "severity": "warning", "messages": messages})
            continue
        if not messages:
            continue
        entry = {"code": rule.code, "rule": rule.title, "severity": rule.severity, "messages": messages}
        (errors if rule.severity == "error" else warnings).append(entry)
    return {"ok": not errors, "errors": errors, "warnings": warnings}
