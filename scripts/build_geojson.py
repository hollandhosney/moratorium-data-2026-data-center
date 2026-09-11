#!/usr/bin/env python3
"""Regenerate site/moratoria.geojson from the inventory CSV.

This customized version only includes records where the sectors column
contains "data_center".

Rows without coordinates are skipped because they cannot be displayed
as geographic points.

Run from repo root:
    python3 scripts/build_geojson.py
    python3 scripts/build_geojson.py --check
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
INV = REPO / "data" / "moratorium_inventory.csv"
OUT = REPO / "site" / "moratoria.geojson"


# Property order is preserved from the published file.
STRING_PROPS = [
    ("jurisdiction", "jurisdiction"),
    ("state", "state"),
    ("state_abbrev", "state_abbrev"),
    ("jurisdiction_type", "jurisdiction_type"),
    ("enacted_status", "enacted_status"),
    ("date_enacted_iso", "date_enacted_iso"),
    ("current_end_date_iso", "current_end_date_iso"),
    ("date_enacted_uncertainty", "date_enacted_uncertainty"),
]


TRAILING_STRING_PROPS = [
    ("date_enacted", "date_enacted"),
    ("duration", "duration"),
    ("trigger", "trigger"),
]


def parse_json_array(raw: str) -> list:
    """Convert a JSON-formatted CSV value into a Python list."""

    raw = (raw or "").strip()

    if not raw:
        return []

    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []

    return value if isinstance(value, list) else []


def build() -> dict:
    """Build a GeoJSON collection containing data-center records only."""

    with open(INV, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    features = []

    for row in rows:
        # Read the sectors JSON array.
        sectors = parse_json_array(row["sectors"])

        # Only keep records that cover data centers.
        # Multi-sector records containing "data_center" are also included.
        if "data_center" not in sectors:
            continue

        lat = row["latitude"].strip()
        lon = row["longitude"].strip()

        # Skip records without geographic coordinates.
        if not lat or not lon:
            continue

        props: dict = {
            "id": row["moratorium_id"]
        }

        for key, column in STRING_PROPS:
            props[key] = row[column]

        days = row["duration_days"].strip()

        props["duration_days"] = int(float(days)) if days else None
        props["duration_kind"] = row["duration_kind"]
        props["sectors"] = sectors
        props["trigger_categories"] = parse_json_array(
            row["trigger_categories"]
        )

        for key, column in TRAILING_STRING_PROPS:
            props[key] = row[column]

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        float(lon),
                        float(lat),
                    ],
                },
                "properties": props,
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the file is out of date",
    )

    args = parser.parse_args()

    fresh = build()
    rendered = json.dumps(
        fresh,
        separators=(",", ":"),
    )

    if args.check:
        current = (
            OUT.read_text(encoding="utf-8")
            if OUT.exists()
            else ""
        )

        if current.strip() != rendered:
            print(
                "site/moratoria.geojson is OUT OF DATE "
                "- run scripts/build_geojson.py"
            )
            return 1

        print("site/moratoria.geojson is current")
        return 0

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUT.write_text(
        rendered,
        encoding="utf-8",
    )

    total_rows = (
        sum(1 for _ in open(INV, encoding="utf-8")) - 1
    )

    data_center_rows = 0

    with open(INV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sectors = parse_json_array(row["sectors"])

            if "data_center" in sectors:
                data_center_rows += 1

    skipped = data_center_rows - len(fresh["features"])

    print(f"Wrote {OUT.relative_to(REPO)}")
    print(f"  Original inventory: {total_rows} records")
    print(f"  Data center records: {data_center_rows}")
    print(f"  Map features: {len(fresh['features'])}")
    print(
        f"  Data center row(s) without coordinates skipped: {skipped}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())