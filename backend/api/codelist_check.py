"""F-9 第三部分：受控词表校验。

schema 只校验"这是一个带 id 的对象"，不校验 id 是否真是 WMDS 里的概念。
上面 ETS 的 ``codelisted-values`` 测试就是干这个的，但 ETS 是可选依赖
（见 api/ets.py）；这一模块用仓库自带的 18 个码表快照做同一件事，让校验在
任何环境下都成立。

口径与 ETS 一致：WMDR2 记录里的概念用 ``{"id": "<notation>"}`` 表达，所以
只比 notation。码表缺文件时该项跳过（不报错），因为本地快照可能没同步全。
"""
import csv
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

__all__ = ["CODELIST_FILES", "ids_for", "unknown_concepts", "cached_codelists"]

CODELIST_DIR = Path(__file__).resolve().parent / "codelists"

# 记录里的字段 -> 码表。ObservedVariable / ObservingMethod 按介质分成多个文件，
# 需要合并后再判断。
CODELIST_FILES: Dict[str, List[str]] = {
    "FacilityType": ["FacilityType.csv"],
    "WMORegion": ["WMORegion.csv"],
    "TerritoryName": ["ISO3166.csv"],
    "ReportingStatus": ["ReportingStatus.csv"],
    "ProgramAffiliation": ["ProgramAffiliation.csv"],
    "SourceOfObservation": ["SourceOfObservation.csv"],
    "InstrumentOperatingStatus": ["InstrumentOperatingStatus.csv"],
    "ReferenceSurfaceType": ["ReferenceSurfaceType.csv"],
    "ObservedVariable": [
        "ObservedVariableAtmosphere.csv",
        "ObservedVariableEarth.csv",
        "ObservedVariableOcean.csv",
        "ObservedVariableOuterSpace.csv",
    ],
    "ObservingMethod": [
        "ObservingMethodAtmosphere.csv",
        "ObservingMethodTerrestrial.csv",
        "ObservingMethodOcean.csv",
    ],
}

# 记录路径 -> 码表。路径是给人看的，所以直接写成可读形式而不是 JSON Pointer；
# ``[]`` 后缀表示"展开这一层数组"，例如 ``properties.territories[]`` 指
# territories 数组里的每个概念对象。
CONCEPT_LOCATIONS = [
    ("properties.facilityType", "FacilityType"),
    ("properties.wmoRegion", "WMORegion"),
    ("properties.reportingStatus", "ReportingStatus"),
    ("properties.territories[]", "TerritoryName"),
    ("properties.observations[].observedProperty", "ObservedVariable"),
    ("properties.observations[].programAffiliations[].programAffiliation", "ProgramAffiliation"),
    ("properties.observations[].programAffiliations[].reportingStatus", "ReportingStatus"),
    ("properties.observations[].configurations[].sourceOfObservation", "SourceOfObservation"),
    ("properties.observations[].configurations[].instrument.operatingStatus", "InstrumentOperatingStatus"),
    ("properties.observations[].configurations[].referenceSurface", "ReferenceSurfaceType"),
    ("properties.observations[].configurations[].geometry", "Geometry"),
]


@lru_cache(maxsize=None)
def ids_for(scheme) -> frozenset:
    """该码表全部 notation；文件缺失时返回空 frozenset（调用方据此跳过）。"""
    files = CODELIST_FILES.get(scheme)
    if not files:
        return frozenset()
    found = set()
    for name in files:
        path = CODELIST_DIR / name
        if not path.exists():
            logger.warning("codelist %s missing from the local snapshot (%s)", scheme, name)
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                notation = (row.get("skos:notation") or "").strip()
                if notation:
                    found.add(notation)
    return frozenset(found)


def cached_codelists() -> List[str]:
    return sorted(CODELIST_FILES)


def _concepts_at(record, path_parts):
    """按路径取到所有概念对象（dict）。``key[]`` 表示展开这一层数组。"""
    nodes = [record]
    for token in path_parts:
        expand = token.endswith("[]")
        key = token[:-2] if expand else token
        nxt = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            value = node.get(key)
            if value is None:
                continue
            if expand and isinstance(value, list):
                nxt.extend(value)
            else:
                nxt.append(value)
        nodes = nxt
    return [n for n in nodes if isinstance(n, dict)]


def unknown_concepts(record) -> List[str]:
    """返回记录里所有不在本地码表中的概念，形如
    ``programAffiliation 'GOS' is not in the ProgramAffiliation codelist``。

    码表快照缺失的项直接跳过：本地没这个文件，就没资格判定人家不合法。
    """
    problems: List[str] = []
    props = record.get("properties") if isinstance(record, dict) else None
    if not isinstance(props, dict):
        return problems

    for label, scheme in CONCEPT_LOCATIONS:
        known = ids_for(scheme)
        if not known:
            continue
        path = label.split(".")
        for node in _concepts_at(record, path):
            value = node.get("id")
            if value in (None, ""):
                continue  # 空概念由 schema 管，不是词表问题
            if value not in known:
                problems.append(f"{label}: '{value}' is not in the {scheme} codelist")
    return problems
