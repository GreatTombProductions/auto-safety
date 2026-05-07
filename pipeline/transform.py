"""
Transform NHTSA complaints flat file into searchable JSON.

Input: raw_data/FLAT_CMPL.txt (tab-delimited, 51 fields, no header, ~2.2M rows)

NHTSA FLAT_CMPL field mapping (positions 1-indexed):
  1  CMPL_ID          Row identifier
  2  ODESSION_NUMBER   ODI case number
  3  MFR_NAME         Manufacturer name
  4  MAKETXT          Make (uppercase)
  5  MODELTXT         Model (uppercase)
  6  YEARTXT          Model year
  7  CRASH            Crash? (Y/N)
  8  FAILDATE         Failure date (YYYYMMDD)
  9  FIRE             Fire? (Y/N)
  10 INJURED          Number injured
  11 DEATHS           Number killed
  12 COMPDESC         Component (colon-separated hierarchy)
  13 CITY             City
  14 STATE            State
  15 VIN              Partial VIN
  16 DATEA            Date added (YYYYMMDD)
  17 DATECL           Date complaint (YYYYMMDD)
  46 TYPE             V=vehicle, T=tire, E=equipment, C=child seat

Output:
  data/vehicles.json   — Pre-aggregated by make/model/year (~8-12MB)
  data/stats.json      — National summary statistics
  data/meta.json       — Data vintage and methodology
  data/recalls.json    — Active recall counts by make/model/year
"""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RAW_DIR = PROJECT_ROOT / "raw_data"
DATA_DIR = PROJECT_ROOT / "data"

COMPLAINTS_FILE = RAW_DIR / "FLAT_CMPL.txt"
RECALLS_FILE = RAW_DIR / "FLAT_RCL.txt"


def parse_date(s: str) -> str | None:
    """Parse YYYYMMDD to YYYY-MM-DD, return None if invalid."""
    s = s.strip()
    if not s or len(s) != 8 or not s.isdigit():
        return None
    y, m, d = s[:4], s[4:6], s[6:]
    if int(y) < 1950 or int(y) > 2030:
        return None
    return f"{y}-{m}-{d}"


def parse_year(s: str) -> int | None:
    """Parse YYYYMMDD or YYYY to year."""
    s = s.strip()
    if not s:
        return None
    try:
        y = int(s[:4])
        return y if 1950 <= y <= 2030 else None
    except (ValueError, IndexError):
        return None


def top_component(comp: str) -> str:
    """Extract top-level component from colon-separated hierarchy."""
    if not comp or not comp.strip():
        return "UNKNOWN"
    return comp.split(":")[0].strip()


def load_recalls() -> dict[tuple[str, str, int], int]:
    """Load recall counts by (make, model, year) from FLAT_RCL.txt.

    FLAT_RCL fields (tab-delimited):
      1  RECORD_ID
      2  CAMPNO (campaign number)
      3  MAKETXT
      4  MODELTXT
      5  YEARTXT
      ...more fields
    """
    recalls: dict[tuple[str, str, int], int] = defaultdict(int)

    rcl_path = RECALLS_FILE
    if not rcl_path.exists():
        print("  No recalls file found, skipping recall cross-reference.")
        return {}

    print("  Loading recalls...")
    with open(rcl_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 5:
                continue
            make = row[2].strip().upper()
            model = row[3].strip().upper()
            try:
                year = int(row[4].strip())
            except (ValueError, IndexError):
                continue
            if make and model and 1950 <= year <= 2030:
                recalls[(make, model, year)] += 1

    print(f"    {len(recalls):,} unique make/model/year combos with recalls")
    return dict(recalls)


def transform():
    """Transform raw complaints into pre-aggregated JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Load recalls first
    recalls = load_recalls()

    # Phase 1: Read complaints and aggregate
    print("  Reading complaints...")

    # Per make/model/year aggregation
    vehicle_data: dict[tuple[str, str, int], dict] = {}

    # Global counters
    total_complaints = 0
    total_crashes = 0
    total_fires = 0
    total_injuries = 0
    total_deaths = 0
    by_component = Counter()
    by_make = Counter()
    by_year_filed = Counter()
    by_state = Counter()
    complaints_by_model_year = Counter()

    with open(COMPLAINTS_FILE, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 20:
                continue

            total_complaints += 1
            if total_complaints % 500000 == 0:
                print(f"    Processed {total_complaints:,} complaints...")

            make = row[3].strip().upper()
            model = row[4].strip().upper()
            try:
                year = int(row[5].strip())
            except (ValueError, IndexError):
                continue

            if not make or not model or year < 1950 or year > 2030:
                continue

            crash = row[6].strip() == "Y"
            fire = row[8].strip() == "Y"
            try:
                injured = int(row[9].strip()) if row[9].strip() else 0
            except ValueError:
                injured = 0
            try:
                deaths = int(row[10].strip()) if row[10].strip() else 0
            except ValueError:
                deaths = 0

            comp = top_component(row[11])
            state = row[13].strip()
            year_filed = parse_year(row[16])

            # Global stats
            total_crashes += crash
            total_fires += fire
            total_injuries += injured
            total_deaths += deaths
            by_component[comp] += 1
            by_make[make] += 1
            if year_filed:
                by_year_filed[year_filed] += 1
            if state:
                by_state[state] += 1

            # Per-vehicle aggregation
            key = (make, model, year)
            complaints_by_model_year[key] += 1

            if key not in vehicle_data:
                vehicle_data[key] = {
                    "complaints": 0,
                    "crashes": 0,
                    "fires": 0,
                    "injuries": 0,
                    "deaths": 0,
                    "components": Counter(),
                    "by_year": Counter(),
                    "mfr_name": row[2].strip(),
                }

            v = vehicle_data[key]
            v["complaints"] += 1
            v["crashes"] += crash
            v["fires"] += fire
            v["injuries"] += injured
            v["deaths"] += deaths
            v["components"][comp] += 1
            if year_filed:
                v["by_year"][year_filed] += 1

    print(f"    Total: {total_complaints:,} complaints")
    print(f"    Unique vehicles: {len(vehicle_data):,}")

    # Phase 2: Build output JSON

    # vehicles.json: keyed by "MAKE|MODEL|YEAR"
    # Compact format with abbreviated keys
    print("  Building vehicles index...")

    vehicles = {}
    for (make, model, year), v in sorted(vehicle_data.items(), key=lambda x: -x[1]["complaints"]):
        key = f"{make}|{model}|{year}"

        # Top 8 components by count
        top_comps = v["components"].most_common(8)
        comp_dict = {c: n for c, n in top_comps}

        # Complaint timeline (by year filed)
        timeline = {}
        for yr, cnt in sorted(v["by_year"].items()):
            timeline[str(yr)] = cnt

        entry = {
            "n": v["complaints"],          # complaint count
            "mfr": v["mfr_name"],          # manufacturer display name
        }

        # Only include non-zero severity counts
        if v["crashes"]:
            entry["cr"] = v["crashes"]
        if v["fires"]:
            entry["fi"] = v["fires"]
        if v["injuries"]:
            entry["in"] = v["injuries"]
        if v["deaths"]:
            entry["de"] = v["deaths"]

        # Components (abbreviated)
        if comp_dict:
            entry["co"] = comp_dict

        # Timeline
        if timeline:
            entry["tl"] = timeline

        # Recall count
        rcl_key = (make, model, year)
        if rcl_key in recalls:
            entry["rc"] = recalls[rcl_key]

        vehicles[key] = entry

    # Write vehicles.json
    vehicles_path = DATA_DIR / "vehicles.json"
    with open(vehicles_path, "w") as f:
        json.dump(vehicles, f, separators=(",", ":"))

    size_mb = vehicles_path.stat().st_size / (1024 * 1024)
    print(f"    vehicles.json: {size_mb:.1f} MB ({len(vehicles):,} entries)")

    # Phase 3: Stats
    print("  Building statistics...")

    # Top models by complaints
    top_vehicles = []
    for (make, model, year), v in sorted(
        vehicle_data.items(), key=lambda x: -x[1]["complaints"]
    )[:50]:
        entry = {"m": make, "mo": model, "y": year, "n": v["complaints"]}
        if v["crashes"]:
            entry["cr"] = v["crashes"]
        if v["deaths"]:
            entry["de"] = v["deaths"]
        top_vehicles.append(entry)

    # Component breakdown
    comp_stats = [
        {"name": comp, "count": cnt}
        for comp, cnt in by_component.most_common(25)
    ]

    # By year filed
    year_stats = {str(yr): cnt for yr, cnt in sorted(by_year_filed.items())}

    # Top makes
    make_stats = [
        {"name": make, "count": cnt}
        for make, cnt in by_make.most_common(30)
    ]

    # State stats
    state_stats = {st: cnt for st, cnt in sorted(by_state.items())}

    stats = {
        "total_complaints": total_complaints,
        "total_crashes": total_crashes,
        "total_fires": total_fires,
        "total_injuries": total_injuries,
        "total_deaths": total_deaths,
        "unique_vehicles": len(vehicle_data),
        "unique_makes": len(by_make),
        "top_vehicles": top_vehicles,
        "components": comp_stats,
        "by_year": year_stats,
        "makes": make_stats,
        "states": state_stats,
    }

    stats_path = DATA_DIR / "stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, separators=(",", ":"))

    print(f"    stats.json: {stats_path.stat().st_size / 1024:.0f} KB")

    # Phase 4: Makes index — for autocomplete
    print("  Building makes index...")

    makes_index: dict[str, list] = {}
    # Group models by make
    make_models: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for (make, model, year) in vehicle_data.keys():
        make_models[make][model].append(year)

    for make in sorted(make_models.keys()):
        models = []
        for model in sorted(make_models[make].keys()):
            years = sorted(make_models[make][model])
            count = sum(
                vehicle_data[(make, model, y)]["complaints"]
                for y in years
            )
            models.append({
                "m": model,
                "y": [years[0], years[-1]],  # year range
                "n": count,
            })
        # Sort models by complaint count descending
        models.sort(key=lambda x: -x["n"])
        makes_index[make] = models

    makes_path = DATA_DIR / "makes.json"
    with open(makes_path, "w") as f:
        json.dump(makes_index, f, separators=(",", ":"))

    print(f"    makes.json: {makes_path.stat().st_size / 1024:.0f} KB")

    # Phase 5: Metadata
    meta = {
        "title": "Auto Safety Complaints",
        "description": "NHTSA consumer complaints about vehicle safety defects",
        "data_source": "U.S. Department of Transportation, National Highway Traffic Safety Administration",
        "source_url": "https://www.nhtsa.gov/recalls-complaints/complaints",
        "download_url": "https://static.nhtsa.gov/odi/ffdd/cmpl/FLAT_CMPL.zip",
        "total_complaints": total_complaints,
        "unique_vehicles": len(vehicle_data),
        "total_crashes": total_crashes,
        "total_injuries": total_injuries,
        "total_deaths": total_deaths,
        "update_frequency": "Updated regularly",
        "disclaimer": (
            "Consumer complaints submitted to NHTSA. Not verified by NHTSA. "
            "Complaint counts alone do not indicate a safety defect. "
            "Higher-selling vehicles naturally receive more complaints. "
            "Not legal advice."
        ),
        "data_freshness": {
            "vintage": "May 2026",
            "source_update_frequency": "regularly",
            "staleness_threshold_months": 6,
            "staleness_action": "refresh_or_warn",
        },
        "methodology": (
            "Complaints pre-aggregated by make/model/year. "
            "Component categories extracted from NHTSA's colon-separated hierarchy. "
            "Crash, fire, injury, and death flags are consumer-reported, not verified. "
            "Recall counts cross-referenced from NHTSA recall database."
        ),
    }

    meta_path = DATA_DIR / "meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    # Summary
    print("\n=== OUTPUT SUMMARY ===")
    print(f"  vehicles.json: {vehicles_path.stat().st_size / (1024*1024):.1f} MB ({len(vehicles):,} entries)")
    print(f"  makes.json:    {makes_path.stat().st_size / 1024:.0f} KB ({len(makes_index)} makes)")
    print(f"  stats.json:    {stats_path.stat().st_size / 1024:.0f} KB")
    print(f"  meta.json:     {meta_path.stat().st_size / 1024:.0f} KB")
    print(f"\n  Total complaints: {total_complaints:,}")
    print(f"  Crashes: {total_crashes:,}  Fires: {total_fires:,}")
    print(f"  Injuries: {total_injuries:,}  Deaths: {total_deaths:,}")


if __name__ == "__main__":
    transform()
