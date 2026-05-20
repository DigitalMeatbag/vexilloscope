"""
Import US state and DC flags from Wikimedia Commons into the v3 manifest.

Usage:
    python scripts/import_us_states.py [--dry-run] [--state <result_id>]

Exits:
    0  all processed entries succeeded (or were cleanly skipped)
    1  one or more entries had a protected conflict (skipped_existing_reviewed)
       or a fetch/write failure; or --force-download was passed
    2  script-level error (bad arguments, unwritable manifest, etc.)
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_DIR = REPO_ROOT / "data" / "manifest"
SOURCES_DIR = REPO_ROOT / "data" / "sources" / "wikimedia" / "us_states"
REPORTS_DIR = REPO_ROOT / "reports" / "import" / "wikimedia"

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
WIKIMEDIA_FILE_PAGE = "https://commons.wikimedia.org/wiki/File:{filename}"
USER_AGENT = (
    "vexilloscope-importer/1.0 "
    "(https://github.com/anthonybvargo/vexilloscope); "
    "python-requests/2.x"
)
RATE_LIMIT_SECONDS = 0.5

# Spec Section 4 — canonical lookup table
US_STATES: list[dict] = [
    {"result_id": "us-al", "display_name": "Alabama",            "territory_code": "US-AL", "wikimedia_filename": "Flag_of_Alabama.svg"},
    {"result_id": "us-ak", "display_name": "Alaska",             "territory_code": "US-AK", "wikimedia_filename": "Flag_of_Alaska.svg"},
    {"result_id": "us-az", "display_name": "Arizona",            "territory_code": "US-AZ", "wikimedia_filename": "Flag_of_Arizona.svg"},
    {"result_id": "us-ar", "display_name": "Arkansas",           "territory_code": "US-AR", "wikimedia_filename": "Flag_of_Arkansas.svg"},
    {"result_id": "us-ca", "display_name": "California",         "territory_code": "US-CA", "wikimedia_filename": "Flag_of_California.svg"},
    {"result_id": "us-co", "display_name": "Colorado",           "territory_code": "US-CO", "wikimedia_filename": "Flag_of_Colorado.svg"},
    {"result_id": "us-ct", "display_name": "Connecticut",        "territory_code": "US-CT", "wikimedia_filename": "Flag_of_Connecticut.svg"},
    {"result_id": "us-de", "display_name": "Delaware",           "territory_code": "US-DE", "wikimedia_filename": "Flag_of_Delaware.svg"},
    {"result_id": "us-fl", "display_name": "Florida",            "territory_code": "US-FL", "wikimedia_filename": "Flag_of_Florida.svg"},
    {"result_id": "us-ga", "display_name": "Georgia",            "territory_code": "US-GA", "wikimedia_filename": "Flag_of_Georgia_(U.S._state).svg"},
    {"result_id": "us-hi", "display_name": "Hawaii",             "territory_code": "US-HI", "wikimedia_filename": "Flag_of_Hawaii.svg"},
    {"result_id": "us-id", "display_name": "Idaho",              "territory_code": "US-ID", "wikimedia_filename": "Flag_of_Idaho.svg"},
    {"result_id": "us-il", "display_name": "Illinois",           "territory_code": "US-IL", "wikimedia_filename": "Flag_of_Illinois.svg"},
    {"result_id": "us-in", "display_name": "Indiana",            "territory_code": "US-IN", "wikimedia_filename": "Flag_of_Indiana.svg"},
    {"result_id": "us-ia", "display_name": "Iowa",               "territory_code": "US-IA", "wikimedia_filename": "Flag_of_Iowa.svg"},
    {"result_id": "us-ks", "display_name": "Kansas",             "territory_code": "US-KS", "wikimedia_filename": "Flag_of_Kansas.svg"},
    {"result_id": "us-ky", "display_name": "Kentucky",           "territory_code": "US-KY", "wikimedia_filename": "Flag_of_Kentucky.svg"},
    {"result_id": "us-la", "display_name": "Louisiana",          "territory_code": "US-LA", "wikimedia_filename": "Flag_of_Louisiana.svg"},
    {"result_id": "us-me", "display_name": "Maine",              "territory_code": "US-ME", "wikimedia_filename": "Flag_of_Maine.svg"},
    {"result_id": "us-md", "display_name": "Maryland",           "territory_code": "US-MD", "wikimedia_filename": "Flag_of_Maryland.svg"},
    {"result_id": "us-ma", "display_name": "Massachusetts",      "territory_code": "US-MA", "wikimedia_filename": "Flag_of_Massachusetts.svg"},
    {"result_id": "us-mi", "display_name": "Michigan",           "territory_code": "US-MI", "wikimedia_filename": "Flag_of_Michigan.svg"},
    {"result_id": "us-mn", "display_name": "Minnesota",          "territory_code": "US-MN", "wikimedia_filename": "Flag_of_Minnesota.svg"},
    {"result_id": "us-ms", "display_name": "Mississippi",        "territory_code": "US-MS", "wikimedia_filename": "Flag_of_Mississippi.svg"},
    {"result_id": "us-mo", "display_name": "Missouri",           "territory_code": "US-MO", "wikimedia_filename": "Flag_of_Missouri.svg"},
    {"result_id": "us-mt", "display_name": "Montana",            "territory_code": "US-MT", "wikimedia_filename": "Flag_of_Montana.svg"},
    {"result_id": "us-ne", "display_name": "Nebraska",           "territory_code": "US-NE", "wikimedia_filename": "Flag_of_Nebraska.svg"},
    {"result_id": "us-nv", "display_name": "Nevada",             "territory_code": "US-NV", "wikimedia_filename": "Flag_of_Nevada.svg"},
    {"result_id": "us-nh", "display_name": "New Hampshire",      "territory_code": "US-NH", "wikimedia_filename": "Flag_of_New_Hampshire.svg"},
    {"result_id": "us-nj", "display_name": "New Jersey",         "territory_code": "US-NJ", "wikimedia_filename": "Flag_of_New_Jersey.svg"},
    {"result_id": "us-nm", "display_name": "New Mexico",         "territory_code": "US-NM", "wikimedia_filename": "Flag_of_New_Mexico.svg"},
    {"result_id": "us-ny", "display_name": "New York",           "territory_code": "US-NY", "wikimedia_filename": "Flag_of_New_York.svg"},
    {"result_id": "us-nc", "display_name": "North Carolina",     "territory_code": "US-NC", "wikimedia_filename": "Flag_of_North_Carolina.svg"},
    {"result_id": "us-nd", "display_name": "North Dakota",       "territory_code": "US-ND", "wikimedia_filename": "Flag_of_North_Dakota.svg"},
    {"result_id": "us-oh", "display_name": "Ohio",               "territory_code": "US-OH", "wikimedia_filename": "Flag_of_Ohio.svg"},
    {"result_id": "us-ok", "display_name": "Oklahoma",           "territory_code": "US-OK", "wikimedia_filename": "Flag_of_Oklahoma.svg"},
    {"result_id": "us-or", "display_name": "Oregon",             "territory_code": "US-OR", "wikimedia_filename": "Flag_of_Oregon.svg"},
    {"result_id": "us-pa", "display_name": "Pennsylvania",       "territory_code": "US-PA", "wikimedia_filename": "Flag_of_Pennsylvania.svg"},
    {"result_id": "us-ri", "display_name": "Rhode Island",       "territory_code": "US-RI", "wikimedia_filename": "Flag_of_Rhode_Island.svg"},
    {"result_id": "us-sc", "display_name": "South Carolina",     "territory_code": "US-SC", "wikimedia_filename": "Flag_of_South_Carolina.svg"},
    {"result_id": "us-sd", "display_name": "South Dakota",       "territory_code": "US-SD", "wikimedia_filename": "Flag_of_South_Dakota.svg"},
    {"result_id": "us-tn", "display_name": "Tennessee",          "territory_code": "US-TN", "wikimedia_filename": "Flag_of_Tennessee.svg"},
    {"result_id": "us-tx", "display_name": "Texas",              "territory_code": "US-TX", "wikimedia_filename": "Flag_of_Texas.svg"},
    {"result_id": "us-ut", "display_name": "Utah",               "territory_code": "US-UT", "wikimedia_filename": "Flag_of_Utah.svg"},
    {"result_id": "us-vt", "display_name": "Vermont",            "territory_code": "US-VT", "wikimedia_filename": "Flag_of_Vermont.svg"},
    {"result_id": "us-va", "display_name": "Virginia",           "territory_code": "US-VA", "wikimedia_filename": "Flag_of_Virginia.svg"},
    {"result_id": "us-wa", "display_name": "Washington",         "territory_code": "US-WA", "wikimedia_filename": "Flag_of_Washington_(state).svg"},
    {"result_id": "us-wv", "display_name": "West Virginia",      "territory_code": "US-WV", "wikimedia_filename": "Flag_of_West_Virginia.svg"},
    {"result_id": "us-wi", "display_name": "Wisconsin",          "territory_code": "US-WI", "wikimedia_filename": "Flag_of_Wisconsin.svg"},
    {"result_id": "us-wy", "display_name": "Wyoming",            "territory_code": "US-WY", "wikimedia_filename": "Flag_of_Wyoming.svg"},
    {"result_id": "us-dc", "display_name": "District of Columbia", "territory_code": "US-DC", "wikimedia_filename": "Flag_of_the_District_of_Columbia.svg"},
]

# Spec Section 7.2 — Wikimedia LicenseShortName → v3 license identifier
LICENSE_MAP: dict[str, str] = {
    "Public domain": "public-domain",
    "CC0":           "cc0",
    "CC BY 4.0":     "cc-by-4.0",
    "CC BY-SA 4.0":  "cc-by-sa-4.0",
    "CC BY-SA 3.0":  "cc-by-sa-3.0",
}


def _load_jsonl(path: Path) -> dict[str, dict]:
    """Load a JSONL file keyed by its first unique string field that is named <stem>_id."""
    stem = path.stem  # e.g. "results" → "result_id", "flags" → "flag_id"
    id_field = stem.rstrip("s") + "_id"
    records: dict[str, dict] = {}
    if not path.exists():
        return records
    with open(path, encoding="utf-8", newline="") as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = obj.get(id_field)
            if key and key not in records:
                records[key] = obj
    return records


def _write_jsonl(path: Path, records: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for rec in records.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _query_wikimedia(filename: str, session: requests.Session) -> dict | None:
    """Query Wikimedia Commons imageinfo for one file. Returns parsed API response page dict or None."""
    params = {
        "action": "query",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiextmetadatafilter": "LicenseShortName|Artist|Credit",
        "format": "json",
    }
    try:
        resp = session.get(WIKIMEDIA_API, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"_error": str(e)}

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return {"_error": "Empty pages in API response"}

    page = next(iter(pages.values()))
    return page


def _extract_license(page: dict) -> str | None:
    """Extract v3 license value from imageinfo extmetadata, or None if unrecognized."""
    imageinfo = page.get("imageinfo", [{}])
    if not imageinfo:
        return None
    extmeta = imageinfo[0].get("extmetadata", {})
    short_name = extmeta.get("LicenseShortName", {}).get("value", "")
    return LICENSE_MAP.get(short_name)


def _extract_download_url(page: dict) -> str | None:
    imageinfo = page.get("imageinfo", [{}])
    if not imageinfo:
        return None
    return imageinfo[0].get("url")


def _process_entry(
    entry: dict,
    results: dict,
    flags: dict,
    assets: dict,
    session: requests.Session,
    dry_run: bool,
) -> tuple[dict | None, dict | None]:
    """Process one state entry. Returns (record_entry, failure_entry) — exactly one will be non-None."""
    result_id = entry["result_id"]
    display_name = entry["display_name"]
    territory_code = entry["territory_code"]
    wikimedia_filename = entry["wikimedia_filename"]

    flag_id = f"{result_id}-current"
    asset_id = f"{flag_id}-wikimedia-svg"
    source_url = WIKIMEDIA_FILE_PAGE.format(filename=wikimedia_filename)
    svg_path_rel = f"data/sources/wikimedia/us_states/{result_id}.svg"
    svg_path_abs = REPO_ROOT / svg_path_rel

    # Protected mutation check — if any of the three records are reviewed, skip
    existing_result = results.get(result_id)
    existing_flag = flags.get(flag_id)
    existing_asset = assets.get(asset_id)

    if (
        (existing_result and existing_result.get("review_status") == "reviewed") or
        (existing_flag and existing_flag.get("review_status") == "reviewed") or
        (existing_asset and existing_asset.get("review_status") == "reviewed")
    ):
        print(f"  SKIP (reviewed conflict): {result_id}")
        rec = {
            "result_id": result_id,
            "flag_id": flag_id,
            "asset_id": asset_id,
            "outcome": "skipped_existing_reviewed",
            "source_url": source_url,
            "svg_path": svg_path_rel,
            "notes": "One or more records already have review_status=reviewed; not overwritten.",
        }
        return rec, None

    # Query Wikimedia metadata
    print(f"  Querying Wikimedia: {wikimedia_filename}")
    page = _query_wikimedia(wikimedia_filename, session)
    time.sleep(RATE_LIMIT_SECONDS)

    if "_error" in page:
        print(f"  FAIL (fetch): {result_id}: {page['_error']}")
        fail = {
            "target_result_id": result_id,
            "wikimedia_filename": wikimedia_filename,
            "phase": "failed_fetch",
            "source_url": source_url,
            "error": page["_error"],
            "notes": "Check network or Wikimedia API availability.",
        }
        return None, fail

    if page.get("missing") == "":
        print(f"  FAIL (fetch): {result_id}: File not found on Wikimedia Commons")
        fail = {
            "target_result_id": result_id,
            "wikimedia_filename": wikimedia_filename,
            "phase": "failed_fetch",
            "source_url": source_url,
            "error": "File not found on Wikimedia Commons (page missing)",
            "notes": "Wikimedia filename may have changed; check file page manually.",
        }
        return None, fail

    download_url = _extract_download_url(page)
    if not download_url:
        print(f"  FAIL (parse): {result_id}: No download URL in API response")
        fail = {
            "target_result_id": result_id,
            "wikimedia_filename": wikimedia_filename,
            "phase": "failed_parse",
            "source_url": source_url,
            "error": "No imageinfo.url in API response",
            "notes": "Unexpected API response shape.",
        }
        return None, fail

    license_value = _extract_license(page)

    if not dry_run:
        # Download SVG if not already present
        if not svg_path_abs.exists():
            print(f"  Downloading SVG: {result_id}")
            try:
                svg_resp = session.get(download_url, timeout=60)
                svg_resp.raise_for_status()
                svg_bytes = svg_resp.content
                time.sleep(RATE_LIMIT_SECONDS)
            except Exception as e:
                print(f"  FAIL (fetch): {result_id}: SVG download failed: {e}")
                fail = {
                    "target_result_id": result_id,
                    "wikimedia_filename": wikimedia_filename,
                    "phase": "failed_fetch",
                    "source_url": download_url,
                    "error": f"SVG download failed: {e}",
                    "notes": "Check network or try again.",
                }
                return None, fail

            SOURCES_DIR.mkdir(parents=True, exist_ok=True)
            try:
                svg_path_abs.write_bytes(svg_bytes)
            except Exception as e:
                print(f"  FAIL (write): {result_id}: {e}")
                fail = {
                    "target_result_id": result_id,
                    "wikimedia_filename": wikimedia_filename,
                    "phase": "failed_write",
                    "source_url": download_url,
                    "error": f"Failed to write SVG: {e}",
                    "notes": None,
                }
                return None, fail
        else:
            print(f"  SVG exists (skipping download): {result_id}")

    # Build manifest records
    review_status_asset = "imported" if license_value else "needs_license"

    new_result: dict = {
        "result_id": result_id,
        "display_name": display_name,
        "category": "subnational",
        "fictionality": "nonfiction",
        "status": "current",
        "short_description": f"Current state flag of {display_name}, United States.",
        "parent_result_id": "us",
        "territory_code": territory_code,
        "review_status": "imported",
    }

    flag_display = (
        f"{display_name} state flag"
        if display_name != "District of Columbia"
        else "District of Columbia flag"
    )
    new_flag: dict = {
        "flag_id": flag_id,
        "result_id": result_id,
        "display_name": flag_display,
        "variant": "standard",
        "status": "current",
        "review_status": "imported",
        "trainable": False,
    }

    new_asset: dict = {
        "asset_id": asset_id,
        "flag_id": flag_id,
        "asset_type": "source_original",
        "path": svg_path_rel,
        "source_name": "Wikimedia Commons",
        "source_url": source_url,
        "review_status": review_status_asset,
        "trainable": False,
    }
    if license_value:
        new_asset["license"] = license_value

    if not dry_run:
        results[result_id] = new_result
        flags[flag_id] = new_flag
        assets[asset_id] = new_asset

    outcome = "imported" if license_value else "needs_license"
    status_label = "DRY-RUN " if dry_run else ""
    print(f"  {status_label}{outcome.upper()}: {result_id} (license: {license_value or 'none'})")

    rec = {
        "result_id": result_id,
        "flag_id": flag_id,
        "asset_id": asset_id,
        "outcome": outcome,
        "source_url": source_url,
        "svg_path": svg_path_rel,
        "notes": None,
    }
    if license_value:
        rec["license_extracted"] = license_value

    return rec, None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import US state and DC flags from Wikimedia Commons into the v3 manifest."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be written without writing anything.")
    parser.add_argument("--state", metavar="result_id",
                        help="Import only the specified state (e.g. us-ca).")
    parser.add_argument("--force-download", action="store_true",
                        help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.force_download:
        print("ERROR: --force-download is not implemented in Phase 2.", file=sys.stderr)
        sys.exit(1)

    # Determine target entries
    if args.state:
        table_by_id = {e["result_id"]: e for e in US_STATES}
        if args.state not in table_by_id:
            print(f"ERROR: unknown result_id {args.state!r}. Valid values: "
                  + ", ".join(e["result_id"] for e in US_STATES), file=sys.stderr)
            sys.exit(2)
        targets = [table_by_id[args.state]]
    else:
        targets = US_STATES

    # Load current manifest state
    results_path = MANIFEST_DIR / "results.jsonl"
    flags_path = MANIFEST_DIR / "flags.jsonl"
    assets_path = MANIFEST_DIR / "assets.jsonl"

    results = _load_jsonl(results_path)
    flags = _load_jsonl(flags_path)
    assets = _load_jsonl(assets_path)

    if args.dry_run:
        print("DRY RUN — no files will be written or downloaded.\n")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    report_records: list[dict] = []
    report_failures: list[dict] = []

    n_imported = 0
    n_needs_license = 0
    n_skipped_reviewed = 0
    n_failed = 0

    print(f"Processing {len(targets)} entries...")

    for entry in targets:
        rec, fail = _process_entry(entry, results, flags, assets, session, args.dry_run)
        if fail is not None:
            report_failures.append(fail)
            n_failed += 1
        elif rec is not None:
            report_records.append(rec)
            outcome = rec["outcome"]
            if outcome == "imported":
                n_imported += 1
            elif outcome == "needs_license":
                n_needs_license += 1
            elif outcome == "skipped_existing_reviewed":
                n_skipped_reviewed += 1

    # Write manifest files
    if not args.dry_run:
        try:
            _write_jsonl(results_path, results)
            _write_jsonl(flags_path, flags)
            _write_jsonl(assets_path, assets)
        except Exception as e:
            print(f"ERROR: failed to write manifest: {e}", file=sys.stderr)
            sys.exit(2)

    # Write import report
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report_path = REPORTS_DIR / f"{ts}.json"

    summary = {
        "total": len(targets),
        "imported": n_imported,
        "needs_license": n_needs_license,
        "needs_review": 0,
        "needs_disambiguation": 0,
        "rejected": 0,
        "skipped_existing_reviewed": n_skipped_reviewed,
        "failed_fetch": sum(1 for f in report_failures if f["phase"] == "failed_fetch"),
        "failed_parse": sum(1 for f in report_failures if f["phase"] == "failed_parse"),
        "failed_license_parse": sum(1 for f in report_failures if f["phase"] == "failed_license_parse"),
        "failed_image_decode": sum(1 for f in report_failures if f["phase"] == "failed_image_decode"),
        "failed_validation": sum(1 for f in report_failures if f["phase"] == "failed_validation"),
        "failed_write": sum(1 for f in report_failures if f["phase"] == "failed_write"),
    }

    report = {
        "version": 1,
        "generated_at": ts_iso,
        "importer": "import_us_states",
        "source_family": "wikimedia",
        "summary": summary,
        "records": report_records,
        "failures": report_failures,
    }

    if not args.dry_run:
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            with open(report_path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
                f.write("\n")
            print(f"\nImport report: {report_path}")
        except Exception as e:
            print(f"WARNING: failed to write import report: {e}", file=sys.stderr)
    else:
        print(f"\n[DRY RUN] Import report would be written to: {REPORTS_DIR}/<timestamp>.json")

    # Summary
    print(
        f"\nSummary: {n_imported} imported, {n_needs_license} needs_license, "
        f"{n_skipped_reviewed} skipped (reviewed conflict), {n_failed} failed."
    )

    if n_skipped_reviewed > 0 or n_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
