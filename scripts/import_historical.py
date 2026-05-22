"""
Import historical national flags from Wikimedia Commons into the v3 manifest.

Usage:
    python scripts/import_historical.py [--seed PATH] [--dry-run] [--force]

Exits:
    0  all entries succeeded or were cleanly skipped
    1  one or more entries had a failed_fetch or failed_write outcome
    2  script-level error (bad arguments, unwritable manifest, etc.)
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_DIR = REPO_ROOT / "data" / "manifest"
SOURCES_DIR = REPO_ROOT / "data" / "sources" / "wikimedia" / "historical"
REPORTS_DIR = REPO_ROOT / "reports" / "import" / "wikimedia"

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
WIKIMEDIA_FILE_PAGE = "https://commons.wikimedia.org/wiki/File:{filename}"
USER_AGENT = (
    "vexilloscope-importer/1.0 "
    "(https://github.com/anthonybvargo/vexilloscope); "
    "python-requests/2.x"
)
RATE_LIMIT_SECONDS = 0.5

DEFAULT_SEED = Path(__file__).resolve().parent / "historical_seed.csv"

LICENSE_MAP: dict[str, str] = {
    "Public domain": "public-domain",
    "CC0":           "cc0",
    "CC BY 4.0":     "cc-by-4.0",
    "CC BY-SA 4.0":  "cc-by-sa-4.0",
    "CC BY-SA 3.0":  "cc-by-sa-3.0",
}


def _load_seed(seed_path: Path) -> list[dict]:
    """Load historical_seed.csv; skip blank lines and # comments."""
    entries = []
    with open(seed_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(row for row in f if not row.startswith("#") and row.strip())
        for row in reader:
            entries.append(dict(row))
    return entries


def _load_jsonl(path: Path) -> dict[str, dict]:
    stem = path.stem
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
    force: bool,
) -> tuple[dict | None, dict | None]:
    """Process one seed row. Returns (record_entry, failure_entry) — exactly one non-None."""
    result_id        = entry["result_id"].strip()
    era_descriptor   = entry["era_descriptor"].strip()
    era_start        = entry.get("era_start", "").strip()
    era_end          = entry.get("era_end", "").strip()
    display_name     = entry["display_name"].strip()
    wikimedia_filename = entry["wikimedia_filename"].strip()

    flag_id  = f"{result_id}-{era_descriptor}"
    asset_id = f"{flag_id}-wikimedia-svg"
    source_url = WIKIMEDIA_FILE_PAGE.format(filename=wikimedia_filename)
    svg_path_rel = f"data/sources/wikimedia/historical/{flag_id}.svg"
    svg_path_abs = REPO_ROOT / svg_path_rel

    # Protected mutation: skip if flag record is already reviewed (unless --force)
    existing_flag = flags.get(flag_id)
    if existing_flag and existing_flag.get("review_status") == "reviewed" and not force:
        print(f"  SKIP (reviewed): {flag_id}")
        rec = {
            "flag_id": flag_id,
            "outcome": "skipped_existing_reviewed",
            "flag_review_status": "reviewed",
            "asset_review_status": assets.get(asset_id, {}).get("review_status"),
        }
        return rec, None

    # result_id must already exist in results.jsonl — never create result records
    if result_id not in results:
        print(f"  SKIP (unknown result_id): {flag_id}")
        rec = {
            "flag_id": flag_id,
            "outcome": "unknown_result_id",
            "flag_review_status": None,
            "asset_review_status": None,
        }
        return rec, None

    # Query Wikimedia metadata
    print(f"  Querying Wikimedia: {wikimedia_filename}")
    page = _query_wikimedia(wikimedia_filename, session)
    time.sleep(RATE_LIMIT_SECONDS)

    if "_error" in page:
        print(f"  FAIL (fetch): {flag_id}: {page['_error']}")
        fail = {
            "flag_id": flag_id,
            "outcome": "failed_fetch",
            "error": page["_error"],
        }
        return None, fail

    # Missing page → needs_source: create flag record only, no asset
    if page.get("missing") == "":
        print(f"  NEEDS_SOURCE: {flag_id}: File not found on Wikimedia Commons")
        flag_rec: dict = {
            "flag_id": flag_id,
            "result_id": result_id,
            "display_name": display_name,
            "variant": "standard",
            "status": "historical",
            "review_status": "needs_source",
            "trainable": False,
        }
        if era_start:
            flag_rec["era_start"] = era_start
        if era_end:
            flag_rec["era_end"] = era_end
        if not dry_run:
            flags[flag_id] = flag_rec
        rec = {
            "flag_id": flag_id,
            "outcome": "needs_source",
            "flag_review_status": "needs_source",
            "asset_review_status": None,
        }
        return rec, None

    download_url = _extract_download_url(page)
    if not download_url:
        print(f"  FAIL (parse): {flag_id}: No download URL in API response")
        fail = {
            "flag_id": flag_id,
            "outcome": "failed_fetch",
            "error": "No imageinfo.url in API response",
        }
        return None, fail

    license_value = _extract_license(page)

    if not dry_run:
        # Download SVG if not already present (or --force)
        if not svg_path_abs.exists() or force:
            print(f"  Downloading SVG: {flag_id}")
            try:
                svg_resp = session.get(download_url, timeout=60)
                svg_resp.raise_for_status()
                svg_bytes = svg_resp.content
                time.sleep(RATE_LIMIT_SECONDS)
            except Exception as e:
                print(f"  FAIL (fetch): {flag_id}: SVG download failed: {e}")
                fail = {
                    "flag_id": flag_id,
                    "outcome": "failed_fetch",
                    "error": f"SVG download failed: {e}",
                }
                return None, fail

            SOURCES_DIR.mkdir(parents=True, exist_ok=True)
            try:
                svg_path_abs.write_bytes(svg_bytes)
            except Exception as e:
                print(f"  FAIL (write): {flag_id}: {e}")
                fail = {
                    "flag_id": flag_id,
                    "outcome": "failed_write",
                    "error": f"Failed to write SVG: {e}",
                }
                return None, fail
        else:
            print(f"  SVG exists (skipping download): {flag_id}")

    # Build flag record
    review_status_asset = "imported" if license_value else "needs_license"

    new_flag: dict = {
        "flag_id": flag_id,
        "result_id": result_id,
        "display_name": display_name,
        "variant": "standard",
        "status": "historical",
        "review_status": "imported",
        "trainable": False,
    }
    if era_start:
        new_flag["era_start"] = era_start
    if era_end:
        new_flag["era_end"] = era_end

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
        flags[flag_id] = new_flag
        assets[asset_id] = new_asset

    outcome = "imported" if license_value else "needs_license"
    status_label = "DRY-RUN " if dry_run else ""
    print(f"  {status_label}{outcome.upper()}: {flag_id} (license: {license_value or 'none'})")

    rec = {
        "flag_id": flag_id,
        "outcome": outcome,
        "flag_review_status": "imported",
        "asset_review_status": review_status_asset,
    }
    return rec, None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import historical national flags from Wikimedia Commons into the v3 manifest."
    )
    parser.add_argument("--seed", metavar="PATH", default=str(DEFAULT_SEED),
                        help="Path to historical_seed.csv (default: scripts/historical_seed.csv).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch metadata but do not download SVGs or write manifest files; print report to stdout.")
    parser.add_argument("--force", action="store_true",
                        help="Allow overwriting records that already have review_status=reviewed.")

    args = parser.parse_args()

    seed_path = Path(args.seed)
    if not seed_path.exists():
        print(f"ERROR: seed file not found: {seed_path}", file=sys.stderr)
        sys.exit(2)

    try:
        targets = _load_seed(seed_path)
    except Exception as e:
        print(f"ERROR: failed to load seed file: {e}", file=sys.stderr)
        sys.exit(2)

    results_path = MANIFEST_DIR / "results.jsonl"
    flags_path   = MANIFEST_DIR / "flags.jsonl"
    assets_path  = MANIFEST_DIR / "assets.jsonl"

    results = _load_jsonl(results_path)
    flags   = _load_jsonl(flags_path)
    assets  = _load_jsonl(assets_path)

    if args.dry_run:
        print("DRY RUN — no files will be written or downloaded.\n")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    report_records: list[dict] = []
    report_failures: list[dict] = []

    n_imported            = 0
    n_needs_license       = 0
    n_needs_source        = 0
    n_skipped_reviewed    = 0
    n_unknown_result_id   = 0
    n_failed_fetch        = 0
    n_failed_write        = 0

    print(f"Processing {len(targets)} entries...")

    for entry in targets:
        rec, fail = _process_entry(entry, results, flags, assets, session, args.dry_run, args.force)
        if fail is not None:
            report_failures.append(fail)
            outcome = fail["outcome"]
            if outcome == "failed_fetch":
                n_failed_fetch += 1
            elif outcome == "failed_write":
                n_failed_write += 1
        elif rec is not None:
            report_records.append(rec)
            outcome = rec["outcome"]
            if outcome == "imported":
                n_imported += 1
            elif outcome == "needs_license":
                n_needs_license += 1
            elif outcome == "needs_source":
                n_needs_source += 1
            elif outcome == "skipped_existing_reviewed":
                n_skipped_reviewed += 1
            elif outcome == "unknown_result_id":
                n_unknown_result_id += 1

    # Write manifest files (flags + assets only; results is never written)
    if not args.dry_run:
        try:
            _write_jsonl(flags_path, flags)
            _write_jsonl(assets_path, assets)
        except Exception as e:
            print(f"ERROR: failed to write manifest: {e}", file=sys.stderr)
            sys.exit(2)

    ts     = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report_path = REPORTS_DIR / f"{ts}.json"

    summary = {
        "total":                    len(targets),
        "imported":                 n_imported,
        "needs_license":            n_needs_license,
        "needs_source":             n_needs_source,
        "skipped_existing_reviewed": n_skipped_reviewed,
        "unknown_result_id":        n_unknown_result_id,
        "failed_fetch":             n_failed_fetch,
        "failed_write":             n_failed_write,
    }

    report = {
        "version":       1,
        "generated_at":  ts_iso,
        "importer":      "import_historical",
        "source_family": "wikimedia",
        "summary":       summary,
        "records":       report_records,
        "failures":      report_failures,
    }

    if args.dry_run:
        import io
        buf = io.StringIO()
        json.dump(report, buf, ensure_ascii=False, indent=2)
        print("\n" + buf.getvalue())
    else:
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            with open(report_path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
                f.write("\n")
            print(f"\nImport report: {report_path}")
        except Exception as e:
            print(f"WARNING: failed to write import report: {e}", file=sys.stderr)

    print(
        f"\nSummary: {n_imported} imported, {n_needs_license} needs_license, "
        f"{n_needs_source} needs_source, {n_skipped_reviewed} skipped (reviewed), "
        f"{n_unknown_result_id} unknown_result_id, "
        f"{n_failed_fetch} failed_fetch, {n_failed_write} failed_write."
    )

    if n_failed_fetch > 0 or n_failed_write > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
