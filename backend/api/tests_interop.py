"""Tests for the interoperability endpoints: export (F-16), ingest (F-15),
WMDR1 import (F-21), OGC API conformance (F-14) and providers (F-13).

Run on a PostGIS instance:

    docker compose exec backend python manage.py test api.tests_interop -v 2
"""
import copy
import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from . import exporters
from .models import RecordProvider, Station, WIGOSNodeGroup, WIGOSNodeUser

ISSUER_A = 756
COLLECTION = "wigos-observing-facility-metadata"

BASE_RECORD = {
    "id": "0-756-0-10001",
    "conformsTo": ["http://wigos.wmo.int/spec/wmdr/2/conf/core"],
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [8.2, 46.8, 450]},
    "properties": {
        "type": "facility",
        "title": "Interop station",
        "created": "2026-01-01T00:00:00Z",
        "updated": "2026-01-02T00:00:00Z",
        "contacts": [{"organization": "WMO"}],
        "facilityType": {"id": "landFixed"},
        "wmoRegion": {"id": "europe"},
        "observations": [
            {
                "observedProperty": {"id": "224"},
                "programAffiliations": [{"programAffiliation": {"id": "unknown"}}],
                "configurations": [{"id": "default", "time": {"interval": ["2026-01-01", ".."]}}],
            }
        ],
    },
    "links": [{"href": "urn:wigos:wsi:0-756-0-10001", "rel": "about"}],
}


def record(wsi, title="Interop station"):
    data = copy.deepcopy(BASE_RECORD)
    data["id"] = wsi
    data["properties"]["title"] = title
    return data


WMDR1_RECORD = {
    "wigos_station_identifier": "0-756-0-20001",
    "station_name": "V1 station",
    "latitude": 30.62,
    "longitude": 114.13,
    "elevation": 23.0,
    "facility_type": "Land (fixed)",
    "wmo_region": "Region II",
    "territory_name": "China",
    "observed_variables": ["Air temperature"],
    "program_affiliation": "IAGOS",
    "contacts": [{"organization": "CMA", "name": "Operator", "email": "op@example.com"}],
    "start_date": "1951-01-01",
    "last_updated": "2026-09-30",
    "status": "Operational",
}


class InteropTestCase(APITestCase):

    def setUp(self):
        group = WIGOSNodeGroup.objects.get(issuer_identifier=ISSUER_A).group
        self.user = WIGOSNodeUser.objects.create_user(
            username="interop_user", email="interop@example.com", password="pw")
        self.user.groups.add(group)
        self.outsider = WIGOSNodeUser.objects.create_user(
            username="interop_outsider", email="outsider@example.com", password="pw")
        self.station = Station(wmdrv2=record("0-756-0-10001"), owner=self.user)
        self.station.save()
        assign_perm("change_station", self.user, self.station)
        assign_perm("change_station", group, self.station)
        self.client.force_authenticate(self.user)

    # ------------------------------------------------------------------ #
    # F-16 export
    # ------------------------------------------------------------------ #
    def test_export_json_is_a_feature_collection(self):
        response = self.client.get(reverse("export"), {"format": "json"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = json.loads(response.content)
        self.assertEqual(body["type"], "FeatureCollection")
        self.assertEqual([f["id"] for f in body["features"]], ["0-756-0-10001"])
        self.assertIn("wigos-wmdr2-", response["Content-Disposition"])

    def test_export_csv_has_the_documented_header(self):
        response = self.client.get(reverse("export"), {"format": "csv"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", response["Content-Type"])
        header = response.content.decode().splitlines()[0]
        self.assertEqual(header.split(","), exporters.CSV_COLUMNS)

    def test_export_xml_round_trips_to_the_same_record(self):
        response = self.client.get(reverse("export"), {"format": "xml"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("xml", response["Content-Type"])
        self.assertEqual(exporters.xml_to_records(response.content.decode()), [self.station.wmdrv2])

    def test_single_record_export(self):
        response = self.client.get(reverse("wmdrv2-export", args=[self.station.id]), {"format": "json"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.content)["features"][0]["id"], "0-756-0-10001")

    def test_export_rejects_unknown_format(self):
        response = self.client.get(reverse("export"), {"format": "xlsx"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_selected_ids_only(self):
        Station(wmdrv2=record("0-756-0-10002"), owner=self.user).save()
        response = self.client.get(reverse("export"), {"format": "json", "station_id": self.station.id})
        body = json.loads(response.content)
        self.assertEqual(len(body["features"]), 1)

    def test_export_skips_archived_unless_asked(self):
        self.station.archived = True
        self.station.save(update_fields=["archived"])
        self.assertEqual(self.client.get(reverse("export")).status_code, status.HTTP_404_NOT_FOUND)
        response = self.client.get(reverse("export"), {"include_archived": "1"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ------------------------------------------------------------------ #
    # F-14 OGC API
    # ------------------------------------------------------------------ #
    def test_conformance_declares_records_core(self):
        response = self.client.get(reverse("ogc-conformance"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(any("ogcapi-records-1" in uri for uri in response.json()["conformsTo"]))

    def test_collection_metadata_and_unknown_collection(self):
        self.assertEqual(self.client.get(reverse("ogc-collection", args=[COLLECTION])).status_code, 200)
        self.assertEqual(self.client.get(reverse("ogc-collection", args=["nope"])).status_code, 404)

    def test_items_bad_limit_is_400_not_500(self):
        response = self.client.get(reverse("ogc-items", args=[COLLECTION]), {"limit": "abc"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_items_bbox_and_datetime_filters(self):
        url = reverse("ogc-items", args=[COLLECTION])
        inside = self.client.get(url, {"bbox": "7,46,9,47"}).json()
        self.assertEqual(inside["numberMatched"], 1)
        outside = self.client.get(url, {"bbox": "0,0,1,1"}).json()
        self.assertEqual(outside["numberMatched"], 0)
        bad = self.client.get(url, {"bbox": "1,2,3"})
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        future = self.client.get(url, {"datetime": "2030-01-01T00:00:00Z/.."}).json()
        self.assertEqual(future["numberMatched"], 0)
        past = self.client.get(url, {"datetime": "2020-01-01T00:00:00Z/.."}).json()
        self.assertEqual(past["numberMatched"], 1)

    def test_items_pagination_links(self):
        for index in range(3):
            Station(wmdrv2=record(f"0-756-0-3000{index}"), owner=self.user).save()
        url = reverse("ogc-items", args=[COLLECTION])
        page = self.client.get(url, {"limit": 2}).json()
        self.assertEqual(page["numberReturned"], 2)
        self.assertEqual(page["numberMatched"], 4)
        self.assertTrue(any(link["rel"] == "next" for link in page["links"]))

    # ------------------------------------------------------------------ #
    # F-15 ingest
    # ------------------------------------------------------------------ #
    def test_import_json_creates_records(self):
        payload = {"format": "json", "data": json.dumps([record("0-756-0-40001"), record("0-756-0-40002")])}
        response = self.client.post(reverse("import"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["summary"]["ok"], 2)
        self.assertEqual(Station.objects.filter(wigos_identifier__startswith="0-756-0-4000").count(), 2)

    def test_import_csv_creates_records(self):
        text = exporters.records_to_csv([record("0-756-0-41001")])
        response = self.client.post(reverse("import"),
                                    {"format": "csv", "data": text}, format="json")
        self.assertEqual(response.json()["summary"]["ok"], 1, response.content)

    def test_import_xml_creates_records(self):
        text = exporters.records_to_xml([record("0-756-0-42001")])
        response = self.client.post(reverse("import"),
                                    {"format": "xml", "data": text}, format="json")
        self.assertEqual(response.json()["summary"]["ok"], 1, response.content)

    def test_import_file_upload_detects_format(self):
        upload = SimpleUploadedFile(
            "records.xml", exporters.records_to_xml([record("0-756-0-43001")]).encode(),
            content_type="application/xml")
        response = self.client.post(reverse("import"), {"file": upload}, format="multipart")
        self.assertEqual(response.json()["summary"]["ok"], 1, response.content)

    def test_import_dry_run_creates_nothing(self):
        before = Station.objects.count()
        response = self.client.post(reverse("import"),
                                    {"format": "json", "dry_run": True,
                                     "data": json.dumps([record("0-756-0-44001")])}, format="json")
        self.assertTrue(response.json()["dry_run"])
        self.assertEqual(Station.objects.count(), before)

    def test_import_reports_per_row_errors(self):
        bad = record("0-756-0-45001")
        del bad["properties"]["contacts"]
        response = self.client.post(reverse("import"),
                                    {"format": "json", "data": json.dumps([bad, record("0-756-0-45002")])},
                                    format="json")
        summary = response.json()["summary"]
        self.assertEqual((summary["ok"], summary["error"]), (1, 1))
        self.assertIn("errors", response.json()["results"][0])

    def test_import_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.post(reverse("import"), {"format": "json", "data": "[]"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_import_rejects_foreign_issuer(self):
        response = self.client.post(reverse("import"),
                                    {"format": "json", "data": json.dumps([record("0-76-0-46001")])},
                                    format="json")
        self.assertEqual(response.json()["summary"]["ok"], 0)
        self.assertEqual(Station.objects.filter(wigos_identifier="0-76-0-46001").exists(), False)

    # ------------------------------------------------------------------ #
    # F-21 WMDR1 import
    # ------------------------------------------------------------------ #
    def test_wmdr1_import_maps_fields(self):
        response = self.client.post(reverse("import-wmdr1"), {"records": [WMDR1_RECORD]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.json()["summary"]["ok"], 1, response.content)
        station = Station.objects.get(wigos_identifier="0-756-0-20001")
        self.assertEqual(station.wmdrv2["geometry"]["coordinates"], [114.13, 30.62, 23.0])
        self.assertEqual(station.wmdrv2["properties"]["facilityType"]["id"], "landFixed")
        self.assertEqual(station.wmdrv2["properties"]["wmoRegion"]["id"], "asia")
        self.assertEqual(station.wmdrv2["properties"]["created"], "1951-01-01T00:00:00Z")

    def test_wmdr1_import_reports_placeholders(self):
        minimal = {"wigos_station_identifier": "0-756-0-21001", "station_name": "minimal",
                   "latitude": 1, "longitude": 2}
        response = self.client.post(reverse("import-wmdr1"), {"records": [minimal]}, format="json")
        self.assertEqual(response.json()["summary"]["ok"], 1, response.content)
        placeholders = response.json()["results"][0]["placeholders"]
        self.assertIn("properties.observations", placeholders)

    def test_wmdr1_import_without_wsi_is_rejected(self):
        response = self.client.post(reverse("import-wmdr1"),
                                    {"records": [{"station_name": "no wsi", "latitude": 1, "longitude": 2}]},
                                    format="json")
        self.assertEqual(response.json()["summary"]["ok"], 0)
        self.assertIn("WIGOS", response.json()["results"][0]["message"])

    # ------------------------------------------------------------------ #
    # F-13 providers
    # ------------------------------------------------------------------ #
    def test_providers_report_implicit_owner(self):
        response = self.client.get(reverse("wmdrv2-providers", args=[self.station.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        providers = response.json()["providers"]
        self.assertEqual(providers[0]["role"], "owner")
        self.assertTrue(providers[0]["implicit"])

    def test_provider_can_be_added_and_removed(self):
        url = reverse("wmdrv2-providers", args=[self.station.id])
        created = self.client.post(url, {"organization": "CMA", "role": "dataProvider"}, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.content)
        self.assertEqual(created.json()["organization"], "CMA")
        self.assertEqual(len(self.client.get(url).json()["providers"]), 2)

        duplicate = self.client.post(url, {"organization": "CMA", "role": "dataProvider"}, format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_409_CONFLICT)

        removed = self.client.delete(reverse("provider-detail", args=[created.json()["id"]]))
        self.assertEqual(removed.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(RecordProvider.objects.count(), 0)

    def test_provider_rejects_unknown_role(self):
        response = self.client.post(reverse("wmdrv2-providers", args=[self.station.id]),
                                    {"organization": "CMA", "role": "overlord"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_outsider_cannot_add_provider(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.post(reverse("wmdrv2-providers", args=[self.station.id]),
                                    {"organization": "CMA"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
