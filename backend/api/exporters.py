"""Serialisation of WMDR2 records: CSV / JSON / XML (F-16 export, F-15 import).

Formats
-------
JSON
    The record exactly as stored (one object, or a FeatureCollection for many).
    Lossless.
XML
    WMDR2 has no official XML encoding yet, so this module defines a
    *deterministic, lossless* JSON<->XML mapping and documents it here. Until
    WMO publishes an XML profile this is the node's own convention:

    * the root element is ``<wmdr2>`` (``<wmdr2Collection><wmdr2>...`` for many);
    * every object key becomes a child element; keys that are not valid XML
      names are escaped as ``__k_<hex of the utf-8 bytes>``;
    * arrays are elements carrying ``l="1"`` with one ``<item>`` per entry
      (an empty array is ``<key l="1"/>``), so ``[]`` and a missing key stay
      distinguishable;
    * scalars carry their JSON type in ``t`` (``int``, ``float``, ``bool``,
      ``null``) and are typed back on import; plain strings carry no ``t``.

    ``xmlish -> XML -> record`` therefore round-trips byte-for-byte on values,
    which matters because a WNM's integrity hash is computed over the JSON.
CSV
    Flat, one row per record, first observation only: lossy by design, meant
    for spreadsheets. The column set below is what ``csv_to_records`` accepts,
    and the two functions are exact inverses for the fields they carry.

Only the standard library is used, so these helpers run without Django or a
database (see ``tests/test_interop_local.py``).
"""
import csv
import io
import json
import re

CSV_COLUMNS = [
    "id",
    "title",
    "latitude",
    "longitude",
    "elevation",
    "facility_type",
    "wmo_region",
    "territory",
    "additional_ids",
    "created",
    "updated",
    "observed_property",
    "program_affiliation",
    "contact_organization",
    "contact_email",
]

MULTI_SEPARATOR = "|"

# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #
def record_id(record):
    return (record or {}).get("id")


def _concept_id(value):
    """A concept field may be {"id": ...}, a bare code, or a URL."""
    if isinstance(value, dict):
        return value.get("id") or ""
    if isinstance(value, str):
        return value.rstrip("/").rsplit("/", 1)[-1]
    return ""


def _first_observation(record):
    observations = (record.get("properties") or {}).get("observations") or []
    return observations[0] if observations else {}


def _coords(record):
    geometry = record.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    return coords


def _join(values):
    return MULTI_SEPARATOR.join(str(v) for v in values if v not in (None, ""))


def _split(value):
    return [part for part in (value or "").split(MULTI_SEPARATOR) if part != ""]


def normalise_datetime(value, fallback=None):
    """'1990-01-01' / '1990-01-01T00:00:00' / ISO with +00:00 -> RFC3339 UTC.

    WMDR2 declares ``properties.created``/``updated`` as ``date-time``, so a
    date-only value from a spreadsheet or WMDR1 must be widened, otherwise the
    record fails schema validation."""
    if isinstance(value, dict):
        value = value.get("value") or value.get("date")
    if not value:
        return fallback
    text = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return f"{text}T00:00:00Z"
    text = text.replace(" ", "T")
    if text.endswith("+00:00"):
        text = text[:-6] + "Z"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?", text):
        text += "Z"
    return text


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #
def record_to_csv_row(record):
    properties = record.get("properties") or {}
    coords = _coords(record)
    observation = _first_observation(record)
    affiliations = (observation.get("programAffiliations") or [{}])[0]
    contacts = properties.get("contacts") or [{}]
    return {
        "id": record.get("id", ""),
        "title": properties.get("title", ""),
        "latitude": coords[1] if len(coords) > 1 else "",
        "longitude": coords[0] if len(coords) > 0 else "",
        "elevation": coords[2] if len(coords) > 2 else "",
        "facility_type": _concept_id(properties.get("facilityType")),
        "wmo_region": _concept_id(properties.get("wmoRegion")),
        "territory": _concept_id(((properties.get("territories") or [{}])[0]).get("territory")),
        "additional_ids": _join(properties.get("additionalIds") or []),
        "created": properties.get("created", ""),
        "updated": properties.get("updated", ""),
        "observed_property": _concept_id(observation.get("observedProperty")),
        "program_affiliation": _concept_id(affiliations.get("programAffiliation")),
        "contact_organization": (contacts[0] or {}).get("organization", ""),
        "contact_email": (contacts[0] or {}).get("email", ""),
    }


def records_to_csv(records):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow(record_to_csv_row(record))
    return buffer.getvalue()


def csv_to_rows(text):
    """CSV text -> list of dicts keyed by CSV_COLUMNS (unknown columns ignored)."""
    stream = io.StringIO(text.lstrip("\ufeff"))
    reader = csv.DictReader(stream)
    if reader.fieldnames is None:
        raise ValueError("CSV 文件为空或缺少表头")
    missing = [c for c in ("id",) if c not in reader.fieldnames]
    if missing:
        raise ValueError(
            f"CSV 表头缺少必需列 {missing}；可用列见 /api/export/?format=csv 的导出样例"
        )
    rows = []
    for row in reader:
        rows.append({k: (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k})
    return rows


def _number(value):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() and "." not in str(value) else number


def csv_row_to_record(row, concept_lookup=None, now=None):
    """One CSV row -> a WMDR2 record skeleton.

    ``concept_lookup(scheme, value)`` resolves a code/label/URL to a concept
    dict; when it returns None the raw value is kept as the concept id so the
    schema error names the offending column. Raises ValueError when the row
    cannot be turned into a record at all (no id / no coordinates).
    """
    lookup = concept_lookup or (lambda scheme, value: None)
    wsi = (row.get("id") or "").strip()
    if not wsi:
        raise ValueError("缺少 id 列（WIGOS identifier）")
    latitude = _number(row.get("latitude"))
    longitude = _number(row.get("longitude"))
    if latitude is None or longitude is None:
        raise ValueError("缺少 latitude/longitude")

    coordinates = [longitude, latitude]
    elevation = _number(row.get("elevation"))
    if elevation is not None:
        coordinates.append(elevation)

    stamp = normalise_datetime(row.get("updated") or row.get("created") or now)
    day = (stamp or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        day = "1970-01-01"
    contacts = [{"organization": (row.get("contact_organization") or "UNKNOWN").strip() or "UNKNOWN"}]
    # WMDR2 restricts contacts to a fixed key set (additionalProperties: false):
    # an address goes under emails[].value, never under a bare "email" key.
    email = (row.get("contact_email") or "").strip()
    if email:
        contacts[0]["emails"] = [{"value": email}]

    properties = {
        "type": "facility",
        "title": (row.get("title") or wsi).strip() or wsi,
        "created": normalise_datetime(row.get("created"), stamp),
        "updated": normalise_datetime(row.get("updated"), stamp),
        "contacts": contacts,
        "observations": [
            {
                "observedProperty": lookup("ObservedVariableAtmosphere", row.get("observed_property"))
                or {"id": (row.get("observed_property") or "").strip() or "unknown"},
                "programAffiliations": [
                    {
                        "programAffiliation": lookup("ProgramAffiliation", row.get("program_affiliation"))
                        or {"id": (row.get("program_affiliation") or "").strip() or "unknown"}
                    }
                ],
                "configurations": [{"id": "default", "time": {"interval": [day, ".."]}}],
            }
        ],
    }

    additional_ids = _split(row.get("additional_ids"))
    if additional_ids:
        properties["additionalIds"] = additional_ids
    facility_type = (row.get("facility_type") or "").strip()
    if facility_type:
        properties["facilityType"] = lookup("FacilityType", facility_type) or {"id": facility_type}
    wmo_region = (row.get("wmo_region") or "").strip()
    if wmo_region:
        properties["wmoRegion"] = lookup("WMORegion", wmo_region) or {"id": wmo_region}
    territory = (row.get("territory") or "").strip()
    if territory:
        properties["territories"] = [
            {"territory": lookup("ISO3166", territory) or {"id": territory}}
        ]

    return {
        "id": wsi,
        "conformsTo": ["http://wigos.wmo.int/spec/wmdr/2/conf/core"],
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": coordinates},
        "properties": properties,
        "links": [{"href": f"urn:wigos:wsi:{wsi}", "rel": "about"}],
    }


# --------------------------------------------------------------------------- #
# XML (deterministic mapping, see module docstring)
# --------------------------------------------------------------------------- #
import xml.etree.ElementTree as ET

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_ESCAPED_PREFIX = "__k_"


def _element_name(key):
    key = str(key)
    if _NAME_RE.match(key):
        return key
    return _ESCAPED_PREFIX + key.encode("utf-8").hex()


def _key_from_element(name):
    if name.startswith(_ESCAPED_PREFIX):
        try:
            return bytes.fromhex(name[len(_ESCAPED_PREFIX):]).decode("utf-8")
        except ValueError:
            return name
    return name


def _set_scalar(element, value):
    if value is None:
        element.set("t", "null")
    elif isinstance(value, bool):
        element.set("t", "bool")
        element.text = "true" if value else "false"
    elif isinstance(value, int):
        element.set("t", "int")
        element.text = str(value)
    elif isinstance(value, float):
        element.set("t", "float")
        element.text = repr(value)
    else:
        element.text = str(value)


def _read_scalar(element):
    kind = element.get("t")
    text = element.text or ""
    if kind == "null":
        return None
    if kind == "bool":
        return text.strip() == "true"
    if kind == "int":
        return int(text)
    if kind == "float":
        return float(text)
    return text


def _append_value(parent, key, value):
    element = ET.SubElement(parent, _element_name(key))
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            _append_value(element, child_key, child_value)
    elif isinstance(value, list):
        element.set("l", "1")
        for item in value:
            _append_value(element, "item", item)
    else:
        _set_scalar(element, value)
    return element


def _element_to_value(element):
    if element.get("l") == "1":
        return [_element_to_value(child) for child in list(element)]
    children = list(element)
    if children:
        return {_key_from_element(child.tag): _element_to_value(child) for child in children}
    return _read_scalar(element)


def record_to_xml(record, root="wmdr2"):
    element = ET.Element(root)
    for key, value in record.items():
        _append_value(element, key, value)
    return ET.tostring(element, encoding="unicode")


def records_to_xml(records):
    root = ET.Element("wmdr2Collection")
    for record in records:
        root.append(ET.fromstring(record_to_xml(record)))
    return ET.tostring(root, encoding="unicode")


def xml_to_records(text):
    """XML -> list of records. Accepts <wmdr2>, <wmdr2Collection> or <record>."""
    try:
        root = ET.fromstring(text.strip())
    except ET.ParseError as exc:
        raise ValueError(f"XML 解析失败: {exc}") from exc

    if root.tag == "wmdr2Collection":
        records = [_element_to_value(child) for child in list(root)]
    elif root.tag in ("records", "collection"):
        records = [_element_to_value(child) for child in list(root)]
    else:
        records = [_element_to_value(root)]
    for record in records:
        if not isinstance(record, dict) or "id" not in record:
            raise ValueError("XML 中每个记录都必须含 <id> 元素")
    return records


# --------------------------------------------------------------------------- #
# JSON
# --------------------------------------------------------------------------- #
def records_from_json(payload):
    """Accept a single record, a list of records, or a GeoJSON FeatureCollection."""
    if isinstance(payload, dict) and payload.get("type") == "FeatureCollection":
        return list(payload.get("features") or [])
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        return list(payload["records"])
    if isinstance(payload, list):
        return list(payload)
    if isinstance(payload, dict) and "id" in payload:
        return [payload]
    raise ValueError("JSON 载荷需为记录、记录数组或 FeatureCollection")


def records_to_json(records):
    return json.dumps(list(records), ensure_ascii=False, indent=2)


def records_to_geojson(records):
    return json.dumps(
        {"type": "FeatureCollection", "features": list(records)}, ensure_ascii=False
    )
