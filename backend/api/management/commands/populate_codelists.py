from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

# Codelist URLs referenced via $comment in wmdrRecordGeoJSON.yaml.
# The registry returns SKOS concepts as CSV by default (no Accept header
# needed).
#
# codes.wmo.int's bulk CSV export is broken for the WMORegion collection
# specifically (200 OK, 0 bytes, for every content type) even though
# individual concept URLs (e.g. .../WMORegion/africa) work fine.
# member_codes is used as a fallback: when the bulk fetch comes back empty,
# the CSV is assembled by fetching each known member concept individually.
CODELISTS = {
    "FacilityType": {
        "url": "https://codes.wmo.int/wmdr/FacilityType",
        "member_codes": None,
    },
    "WMORegion": {
        "url": "https://codes.wmo.int/wmdr/WMORegion",
        "member_codes": [
            "africa",
            "antarctica",
            "asia",
            "europe",
            "northCentralAmericaCaribbean",
            "southAmerica",
            "southWestPacific",
            "inapplicable",
            "unknown",
        ],
    },
}


class Command(BaseCommand):
    help = (
        "Best-effort update of the locally cached WMDR codelist CSVs from "
        "codes.wmo.int. Committed seed files under api/codelists/ are kept "
        "in place whenever the live update fails, so a network or upstream "
        "issue never breaks the app."
    )

    def handle(self, *args, **options):
        codelists_dir = Path(settings.BASE_DIR) / "api" / "codelists"
        codelists_dir.mkdir(parents=True, exist_ok=True)

        for scheme, config in CODELISTS.items():
            dest = codelists_dir / f"{scheme}.csv"
            self.stdout.write(f"Updating {scheme} from {config['url']}...")

            url, member_codes = config["url"], config["member_codes"]
            text = self._fetch_bulk(url)
            if not text and member_codes:
                text = self._fetch_by_member(url, member_codes)

            if not text:
                msg = f"  update failed, keeping existing {dest.name}"
                self.stderr.write(self.style.WARNING(msg))
                continue

            dest.write_text(text, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"  wrote {dest}"))

    def _fetch_bulk(self, url):
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
        except requests.RequestException as exc:
            msg = f"  bulk fetch failed: {exc}"
            self.stderr.write(self.style.WARNING(msg))
            return None
        if not response.text.strip():
            msg = "  bulk fetch returned empty body; trying fallback"
            self.stderr.write(self.style.WARNING(msg))
            return None
        return response.text

    def _fetch_by_member(self, base_url, codes):
        header = None
        rows = []
        for code in codes:
            try:
                response = requests.get(f"{base_url}/{code}", timeout=15)
                response.raise_for_status()
                lines = response.text.strip().splitlines()
                if len(lines) < 2:
                    raise ValueError("no data row returned")
            except (requests.RequestException, ValueError) as exc:
                msg = f"  concept {code!r} failed: {exc}"
                self.stderr.write(self.style.WARNING(msg))
                continue
            header = header or lines[0]
            rows.append(lines[1])

        if not header or not rows:
            return None
        return "\n".join([header] + rows) + "\n"
