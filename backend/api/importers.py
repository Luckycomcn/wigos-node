"""Parsing/ingesting WMDR2 payloads (F-15) and WMDR V1 records (F-21).

Two conversions live here:

``payload_to_records``
    Turns an uploaded payload (JSON / CSV / XML, as produced by
    ``api.exporters`` or by hand) into a list of WMDR2 record dicts. The
    records are *candidates*: they still go through
    ``api.stations.create_station`` so the WMDR2 schema and the per-issuer
    permission rules apply exactly as they do for the web form.

``wmdr1_to_wmdr2``
    Maps a WMDR V1 record (OSCAR/Surface V1 JSON export) onto WMDR2. V1 has
    no equivalent for some schema-required blocks, so those are filled with
    explicit *placeholders* from the WMO codelists and reported back per
    record -- nothing is invented silently.

Field mapping (V1 -> V2), see ``WMDR1_FIELD_MAP``:

    wigos_station_identifier / wigos_id / wsi  ->  id
    station_name / name                        ->  properties.title
    comments / description                     ->  properties.description
    latitude / longitude / elevation           ->  geometry.coordinates
    facility_type                              ->  properties.facilityType
    wmo_region                                 ->  properties.wmoRegion
    territory_name / territory / country       ->  properties.territories[].territory
    observed_variables / observed_variable      ->  properties.observations[].observedProperty
    program_affiliation / programme            ->  observations[].programAffiliations[].programAffiliation
    contacts / station_contacts                ->  properties.contacts
    start_date                                 ->  properties.created
    last_updated / updated                     ->  properties.updated
    url / station_url / wmo_url                ->  links[].href

Only the standard library is used; the codelist lookups read the cached CSVs
under ``api/codelists``.
"""
import csv
import re
from functools import lru_cache
from pathlib import Path

from . import exporters

CODELIST_DIR = Path(__file__).resolve().parent / "codelists"
DEFAULT_CONFORMS_TO = "http://wigos.wmo.int/spec/wmdr/2/conf/core"
PLACEHOLDER = "unknown"

WMDR1_FIELD_MAP = {
    "id": ("wigos_station_identifier", "wigos_id", "wsi", "wigosStationIdentifier", "id"),
    "title": ("station_name", "name", "title"),
    "description": ("comments", "description"),
    "latitude": ("latitude", "lat"),
    "longitude": ("longitude", "lon", "long"),
    "elevation": ("elevation", "height", "altitude"),
    "facility_type": ("facility_type", "facilityType", "facility"),
    "wmo_region": ("wmo_region", "wmoRegion", "region"),
    "territory": ("territory_name", "territory", "country", "territoryName"),
    "observed_variables": ("observed_variables", "observed_variable", "observedVariables", "variables"),
    "program_affiliation": ("program_affiliation", "programme", "program", "programAffiliation"),
    "contacts": ("contacts", "station_contacts", "contact"),
    "created": ("start_date", "created", "startDate"),
    "updated": ("last_updated", "updated", "lastUpdated"),
    "url": ("url", "station_url", "wmo_url", "link"),
}

# WMDR2 contacts allow exactly these keys (additionalProperties: false).
CONTACT_KEYS = (
    "identifier", "name", "position", "organization", "logo", "phones",
    "emails", "addresses", "links", "hoursOfService", "contactInstructions", "roles",
)

# Fields we knowingly drop because WMDR2 has no slot for them.
WMDR1_IGNORED_FIELDS = (
    "status",
    "oscar_id",
    "climate_zone",
    "wmo_programme",
    "station_type",
    "surface_type",
)


# --------------------------------------------------------------------------- #
# codelists
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=None)
def _codelist_index(scheme):
    """notation/label/url -> concept dict, for one cached codelist CSV."""
    path = CODELIST_DIR / f"{scheme}.csv"
    index = {}
    if not path.exists():
        return index
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            url = (row.get("@id") or "").strip().strip("<>")
            label = (row.get("rdfs:label") or "").strip()
            notation = (row.get("skos:notation") or "").strip()
            if not (url or notation):
                continue
            concept = {
                "id": notation or url.rstrip("/").rsplit("/", 1)[-1],
                "title": label,
                "url": url,
            }
            for key in (notation, label, label.lower(), url, url.rstrip("/").rsplit("/", 1)[-1]):
                if key:
                    index[key] = concept
    return index


# WMDR1 stores the WMO region as "Region I".."Region VI"; the codelist uses
# the region's name. Both spellings must resolve (Region II = Asia, etc.).
SCHEME_ALIASES = {
    "wmoregion": {
        "region i": "africa",
        "region ii": "asia",
        "region iii": "southAmerica",
        "region iv": "northCentralAmericaCaribbean",
        "region v": "southWestPacific",
        "region vi": "europe",
        "region 1": "africa",
        "region 2": "asia",
        "region 3": "southAmerica",
        "region 4": "northCentralAmericaCaribbean",
        "region 5": "southWestPacific",
        "region 6": "europe",
    },
}


def concept(scheme, value):
    """Resolve a code, label or URL against a codelist; None when unknown."""
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("id") or value.get("title") or value.get("url")
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    index = _codelist_index(scheme)
    found = index.get(value) or index.get(value.lower()) or index.get(
        value.rstrip("/").rsplit("/", 1)[-1]
    )
    if found:
        return found
    alias = SCHEME_ALIASES.get(scheme.lower(), {}).get(value.lower())
    return index.get(alias) if alias else None


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
normalise_datetime = exporters.normalise_datetime


def _first(record, keys):
    for key in keys:
        if key in record and record[key] not in (None, "", []):
            return record[key]
    return None


def _observation_time(stamp):
    """Configurations[].time is required: use the record's start date, open-ended."""
    day = (stamp or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        day = "1970-01-01"
    return {"interval": [day, ".."]}


def _number(value):
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _as_list(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[;|]", value) if part.strip()]
    return [value]


# --------------------------------------------------------------------------- #
# WMDR V1 -> V2
# --------------------------------------------------------------------------- #
def wmdr1_to_wmdr2(record, now=None):
    """Map one WMDR V1 record onto WMDR2.

    Returns ``{"record": ..., "placeholders": [...], "ignored": [...],
    "error": None | "..."}``. A placeholder entry names the JSON path that was
    filled automatically, so a curator can complete it afterwards.
    """
    placeholders = []
    ignored = []
    if not isinstance(record, dict):
        return {"error": "记录必须是 JSON 对象", "record": None,
                "placeholders": [], "ignored": []}

    flat = {key.lower(): value for key, value in record.items()}
    lookup = {name: _first(flat, keys) for name, keys in WMDR1_FIELD_MAP.items()}

    wsi = (lookup.get("id") or "").strip() if isinstance(lookup.get("id"), str) else lookup.get("id")
    if not wsi:
        return {"error": "缺少 WIGOS identifier（wigos_station_identifier），无法迁移", "record": None,
                "placeholders": [], "ignored": []}

    latitude = _number(lookup.get("latitude"))
    longitude = _number(lookup.get("longitude"))
    if latitude is None or longitude is None:
        return {"error": "缺少 latitude/longitude，无法迁移", "record": None,
                "placeholders": [], "ignored": []}

    coordinates = [longitude, latitude]
    elevation = _number(lookup.get("elevation"))
    if elevation is not None:
        coordinates.append(elevation)

    territory = concept("ISO3166", lookup.get("territory")) or concept(
        "TerritoryName", lookup.get("territory")
    )
    organization = (territory or {}).get("title") or "UNKNOWN"

    contacts = []
    for entry in _as_list(lookup.get("contacts")):
        if isinstance(entry, dict):
            contact = {k: v for k, v in entry.items() if k in CONTACT_KEYS}
            # V1 spells them singular; WMDR2 nests them as [{value: ...}]
            for singular, plural in (("email", "emails"), ("phone", "phones")):
                value = entry.get(singular)
                if value and plural not in contact:
                    contact[plural] = [{"value": str(value)}]
            contact.setdefault("organization", organization)
            contacts.append(contact)
        elif isinstance(entry, str) and entry.strip():
            contacts.append({"organization": entry.strip()})
    if not contacts:
        contacts = [{"organization": organization}]
        placeholders.append("properties.contacts")

    created = normalise_datetime(lookup.get("created"), now)
    if not created:
        return {"error": "无法确定 created 时间（V1 的 start_date 缺失且未提供 now）",
                "record": None, "placeholders": [], "ignored": []}
    updated = normalise_datetime(lookup.get("updated"), created)

    program = concept("ProgramAffiliation", lookup.get("program_affiliation"))
    observations = []
    variables = _as_list(lookup.get("observed_variables"))
    if variables:
        for variable in variables:
            observed = concept("ObservedVariableAtmosphere", variable) or concept(
                "ObservedVariableTerrestrial", variable
            ) or concept("ObservedVariableOcean", variable) or concept(
                "ObservedVariableEarth", variable
            )
            if observed is None:
                observed = {"id": str(variable), "title": str(variable)}
                placeholders.append(f"observations[{len(observations)}].observedProperty")
            observations.append(
                {
                    "observedProperty": observed,
                    "programAffiliations": [
                        {"programAffiliation": program or {"id": PLACEHOLDER}}
                    ],
                    "configurations": [{"id": "default", "time": _observation_time(created)}],
                }
            )
    else:
        observations = [
            {
                "observedProperty": {"id": PLACEHOLDER},
                "programAffiliations": [{"programAffiliation": program or {"id": PLACEHOLDER}}],
                "configurations": [{"id": "default", "time": _observation_time(created)}],
            }
        ]
        placeholders.append("properties.observations")
    if program is None and variables:
        placeholders.append("observations[].programAffiliations")

    properties = {
        "type": "facility",
        "title": lookup.get("title") or wsi,
        "created": created,
        "updated": updated,
        "contacts": contacts,
        "observations": observations,
    }
    if lookup.get("description"):
        properties["description"] = str(lookup["description"])
    facility_type = concept("FacilityType", lookup.get("facility_type"))
    if facility_type:
        properties["facilityType"] = facility_type
    else:
        placeholders.append("properties.facilityType")
    wmo_region = concept("WMORegion", lookup.get("wmo_region"))
    if wmo_region:
        properties["wmoRegion"] = wmo_region
    else:
        placeholders.append("properties.wmoRegion")
    if territory:
        properties["territories"] = [{"territory": territory}]
    else:
        placeholders.append("properties.territories")

    href = lookup.get("url") or f"urn:wigos:wsi:{wsi}"
    record_v2 = {
        "id": wsi,
        "conformsTo": [DEFAULT_CONFORMS_TO],
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": coordinates},
        "properties": properties,
        "links": [{"href": str(href), "rel": "about"}],
    }

    lowered_keys = {key.lower() for key in record}
    known = {key for keys in WMDR1_FIELD_MAP.values() for key in keys}
    ignored = sorted(
        key for key in lowered_keys
        if key in WMDR1_IGNORED_FIELDS and key not in known
    )
    return {"error": None, "record": record_v2, "placeholders": placeholders, "ignored": ignored}


# --------------------------------------------------------------------------- #
# payload dispatch (F-15)
# --------------------------------------------------------------------------- #
def detect_format(text):
    stripped = (text or "").lstrip("\ufeff").lstrip()
    if stripped.startswith("<"):
        return "xml"
    if stripped.startswith("{") or stripped.startswith("["):
        return "json"
    return "csv"


def payload_to_records(text, fmt=None, now=None):
    """Text payload -> (records, format). Raises ValueError with a readable message."""
    fmt = (fmt or detect_format(text)).lower()
    if fmt == "json":
        import json as _json
        try:
            payload = _json.loads(text)
        except _json.JSONDecodeError as exc:
            raise ValueError(f"JSON 解析失败: {exc}") from exc
        return exporters.records_from_json(payload), "json"
    if fmt == "xml":
        return exporters.xml_to_records(text), "xml"
    if fmt == "csv":
        records = []
        errors = []
        for index, row in enumerate(exporters.csv_to_rows(text)):
            try:
                records.append(exporters.csv_row_to_record(row, concept_lookup=concept, now=now))
            except ValueError as exc:
                errors.append({"index": index, "error": str(exc)})
        if not records and errors:
            raise ValueError(f"CSV 中没有可用行：{errors[:3]}")
        return records, "csv"
    raise ValueError(f"不支持的格式 {fmt}，可选 json / csv / xml")


def wmdr1_payload_to_records(payload, now=None):
    """Accept a V1 record, a list of V1 records, or {"records": [...]}."""
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        items = payload["records"]
    elif isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = [payload]
    else:
        raise ValueError("WMDR1 载荷需为对象、数组或 {\"records\": [...]}")
    return [wmdr1_to_wmdr2(item, now=now) for item in items]
