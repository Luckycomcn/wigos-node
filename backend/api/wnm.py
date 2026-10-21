"""
Build WIS2 Notification Messages (WNM) announcing WMDR2 records.

Spec: https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-STABLE.html
"""
import base64
import hashlib
import uuid
from datetime import datetime, timezone

from django.conf import settings
from django.urls import reverse

from .models import Station
from .renderers import render_wmdrv2

WNM_CONFORMANCE_CLASS = 'http://wis.wmo.int/spec/wnm/1/conf/core'
WMDR2_MEDIA_TYPE = 'application/geo+json'

# Link relations for a new, updated or removed record (Req 12E-12G). Exactly
# one of them appears in a notification (Req 12I).
CREATE = 'canonical'
UPDATE = 'update'
DELETE = 'deletion'
OPERATIONS = (CREATE, UPDATE, DELETE)

# Data larger than this must not be embedded via properties.content (Req 11A)
MAX_INLINE_CONTENT_SIZE = 4096


def _rfc3339_utc(value):
    """Format a datetime or an RFC3339 string as RFC3339 in UTC (Req 7B, 10B)."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _wnm_geometry(wmdrv2):
    """Point or Polygon from the record, else null (Req 6B)."""
    geometry = wmdrv2.get('geometry')
    if isinstance(geometry, dict) and geometry.get('type') in ('Point', 'Polygon'):
        return {'type': geometry['type'], 'coordinates': geometry.get('coordinates')}
    return None


def create_wnm(wmdrv2, href, operation=CREATE, pubtime=None):
    """
    Return a WNM (as a dict) announcing the WMDR2 record `wmdrv2`, published
    at `href`. `operation` is CREATE, UPDATE or DELETE.

    data_id is the record's WIGOS identifier, so updates and deletions refer to
    the same data granule as the original notification. The data shared is the
    metadata record itself, so metadata_id is the WIGOS identifier too. integrity and content
    are computed over render_wmdrv2(record), which matches the bytes the API
    serves at `href` only if `wmdrv2` was read back from the database (jsonb
    reorders keys on storage).
    """
    if operation not in OPERATIONS:
        raise ValueError(f"Unknown WNM operation '{operation}', expected one of {OPERATIONS}")

    wigos_identifier = wmdrv2.get('id')
    if not wigos_identifier:
        raise ValueError("Missing required field 'id' in wmdrv2 JSON data")

    record_properties = wmdrv2.get('properties') or {}
    record_updated = record_properties.get('updated') or record_properties.get('created')

    properties = {
        'pubtime': _rfc3339_utc(pubtime or datetime.now(timezone.utc)),
        'data_id': f"wmdr2/{wigos_identifier}",
        'metadata_id': wigos_identifier,
        # Req 10D: null only when no temporal description can be derived
        'datetime': _rfc3339_utc(record_updated) if record_updated else None,
    }
    link = {'href': href, 'rel': operation, 'type': WMDR2_MEDIA_TYPE}

    if operation != DELETE:
        data = render_wmdrv2(wmdrv2)
        properties['integrity'] = {
            'method': 'sha512',
            'value': base64.b64encode(hashlib.sha512(data).digest()).decode('ascii'),
        }
        if len(data) <= MAX_INLINE_CONTENT_SIZE:
            properties['content'] = {
                'encoding': 'utf-8',
                'value': data.decode('utf-8'),
                'size': len(data),
            }
        link['length'] = len(data)

    return {
        'id': str(uuid.uuid4()),
        'conformsTo': [WNM_CONFORMANCE_CLASS],
        'type': 'Feature',
        'geometry': _wnm_geometry(wmdrv2),
        'properties': properties,
        'links': [link],
    }


def create_station_wnm(station, operation=CREATE, pubtime=None):
    """WNM for a saved Station, linking to its record on this node's wmdrv2 endpoint."""
    href = settings.WNM_BASE_URL.rstrip('/') + reverse('wmdrv2', kwargs={'station_id': station.pk})
    wmdrv2 = station.wmdrv2
    if operation != DELETE:
        # The stored copy, in the key order the API will serve it in. A deleted
        # row is gone, and a deletion carries no integrity anyway.
        wmdrv2 = Station.objects.values_list('wmdrv2', flat=True).get(pk=station.pk)
    return create_wnm(
        wmdrv2,
        href,
        operation=operation,
        pubtime=pubtime,
    )
