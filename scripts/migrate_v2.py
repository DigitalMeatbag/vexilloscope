"""
Migrate v2 dataset (data/labels.csv + data/flags/) into v3 JSONL manifests.

Usage:
    python scripts/migrate_v2.py [--reviewed] [--dry-run]

--reviewed  Mark results, flags, and primary assets as reviewed + trainable=true.
            Wiki and emoji assets are never auto-reviewed.
--dry-run   Print what would be written without touching disk.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
LABELS_CSV = DATA_DIR / "labels.csv"
FLAGS_DIR = DATA_DIR / "flags"
FLAGS_WIKI_DIR = DATA_DIR / "flags_wiki"
FLAGS_EMOJI_DIR = DATA_DIR / "flags_emoji"
MANIFEST_DIR = DATA_DIR / "manifest"
RESULTS_JSONL = MANIFEST_DIR / "results.jsonl"
FLAGS_JSONL = MANIFEST_DIR / "flags.jsonl"
ASSETS_JSONL = MANIFEST_DIR / "assets.jsonl"

SOURCE_NAME_PRIMARY = "hampusborgos/country-flags"
SOURCE_URL_PRIMARY = "https://github.com/hampusborgos/country-flags"
LICENSE_PRIMARY = "public-domain"
SOURCE_NAME_WIKI = "FlagCDN / Wikimedia Commons"
SOURCE_URL_WIKI = "https://flagcdn.com"
SOURCE_NAME_EMOJI = "Twemoji"
SOURCE_URL_EMOJI = "https://github.com/twitter/twemoji"
LICENSE_EMOJI = "cc-by-4.0"


def posix_path(p: Path) -> str:
    return str(p.relative_to(REPO_ROOT)).replace("\\", "/")


def read_jsonl(path: Path, key: str) -> dict:
    """Read a JSONL file, return dict keyed by the given field name."""
    records = {}
    if not path.exists():
        return records
    with open(path, encoding="utf-8", newline="") as f:
        for lineno, line in enumerate(f, 1):
            line = line.rstrip("\n").rstrip("\r")
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"ERROR: {path.name} line {lineno}: {e}", file=sys.stderr)
                sys.exit(2)
            if key in obj:
                records[obj[key]] = obj
    return records


def write_jsonl(path: Path, records: dict, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for record in records.values():
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_result(code: str, name: str, reviewed: bool) -> dict:
    review_status = "reviewed" if reviewed else "imported"
    return {
        "result_id": code,
        "display_name": name,
        "category": "national",
        "fictionality": "nonfiction",
        "status": "current",
        "short_description": f"Current flag of {name}.",
        "review_status": review_status,
    }


def build_flag(result_id: str, display_name: str, reviewed: bool) -> dict:
    flag_id = f"{result_id}-current"
    review_status = "reviewed" if reviewed else "imported"
    return {
        "flag_id": flag_id,
        "result_id": result_id,
        "display_name": f"{display_name} current flag",
        "variant": "standard",
        "status": "current",
        "review_status": review_status,
        "trainable": reviewed,
    }


def build_primary_asset(flag_id: str, code: str, reviewed: bool) -> dict:
    asset_id = f"{flag_id}-primary"
    review_status = "reviewed" if reviewed else "imported"
    path = posix_path(FLAGS_DIR / f"{code}.png")
    record = {
        "asset_id": asset_id,
        "flag_id": flag_id,
        "asset_type": "source_original",
        "path": path,
        "source_name": SOURCE_NAME_PRIMARY,
        "source_url": SOURCE_URL_PRIMARY,
        "license": LICENSE_PRIMARY,
        "review_status": review_status,
        "trainable": reviewed,
    }
    return record


def build_wiki_asset(flag_id: str, code: str) -> dict:
    asset_id = f"{flag_id}-wiki"
    path = posix_path(FLAGS_WIKI_DIR / f"{code}.png")
    return {
        "asset_id": asset_id,
        "flag_id": flag_id,
        "asset_type": "source_render",
        "path": path,
        "source_name": SOURCE_NAME_WIKI,
        "source_url": SOURCE_URL_WIKI,
        "review_status": "needs_license",
        "trainable": False,
    }


def build_emoji_asset(flag_id: str, code: str) -> dict:
    asset_id = f"{flag_id}-emoji"
    path = posix_path(FLAGS_EMOJI_DIR / f"{code}.png")
    return {
        "asset_id": asset_id,
        "flag_id": flag_id,
        "asset_type": "emoji_render",
        "path": path,
        "source_name": SOURCE_NAME_EMOJI,
        "source_url": SOURCE_URL_EMOJI,
        "license": LICENSE_EMOJI,
        "review_status": "imported",
        "trainable": False,
    }


def check_conflict(existing: dict, new_record: dict, id_field: str) -> list[str]:
    """
    Return list of conflict messages for fields that would change on a reviewed record.
    Allowed: imported -> reviewed (review_status upgrade + trainable flip).
    Protected: any other field change on an already-reviewed record.
    """
    rec_id = existing.get(id_field, "?")
    if existing.get("review_status") != "reviewed":
        return []

    conflicts = []
    skip_fields = {"review_status", "trainable"}
    for key, new_val in new_record.items():
        if key in skip_fields:
            continue
        if key in existing and existing[key] != new_val:
            conflicts.append(
                f"  {id_field}={rec_id!r}: field {key!r} would change "
                f"{existing[key]!r} -> {new_val!r}"
            )
    return conflicts


def merge_record(existing: dict, new_record: dict, reviewed: bool) -> tuple[dict, str]:
    """
    Merge new_record into existing. Returns (merged, action) where action is
    'created', 'upgraded', or 'skipped'.
    """
    if not existing:
        return new_record, "created"

    if existing.get("review_status") == "imported" and reviewed:
        merged = dict(existing)
        merged["review_status"] = new_record["review_status"]
        if "trainable" in new_record:
            merged["trainable"] = new_record["trainable"]
        return merged, "upgraded"

    return existing, "skipped"


def main():
    parser = argparse.ArgumentParser(description="Migrate v2 dataset to v3 manifest.")
    parser.add_argument("--reviewed", action="store_true",
                        help="Mark results, flags, and primary assets as reviewed + trainable=true.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print planned changes without writing.")
    args = parser.parse_args()

    if not LABELS_CSV.exists():
        print(f"ERROR: {LABELS_CSV} not found.", file=sys.stderr)
        sys.exit(2)

    existing_results = read_jsonl(RESULTS_JSONL, "result_id")
    existing_flags = read_jsonl(FLAGS_JSONL, "flag_id")
    existing_assets = read_jsonl(ASSETS_JSONL, "asset_id")

    rows = []
    with open(LABELS_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    all_conflicts = []
    results_out = dict(existing_results)
    flags_out = dict(existing_flags)
    assets_out = dict(existing_assets)

    counts = {"results": {"created": 0, "upgraded": 0, "skipped": 0},
              "flags": {"created": 0, "upgraded": 0, "skipped": 0},
              "assets": {"created": 0, "upgraded": 0, "skipped": 0}}

    for row in rows:
        code = row["code"].lower()
        name = row["name"]
        result_id = code
        flag_id = f"{result_id}-current"

        new_result = build_result(result_id, name, args.reviewed)
        existing_r = existing_results.get(result_id, {})
        conflicts = check_conflict(existing_r, new_result, "result_id")
        all_conflicts.extend(conflicts)
        merged_r, action_r = merge_record(existing_r, new_result, args.reviewed)
        results_out[result_id] = merged_r
        counts["results"][action_r] += 1

        new_flag = build_flag(result_id, name, args.reviewed)
        existing_f = existing_flags.get(flag_id, {})
        conflicts = check_conflict(existing_f, new_flag, "flag_id")
        all_conflicts.extend(conflicts)
        merged_f, action_f = merge_record(existing_f, new_flag, args.reviewed)
        flags_out[flag_id] = merged_f
        counts["flags"][action_f] += 1

        primary_asset_id = f"{flag_id}-primary"
        new_primary = build_primary_asset(flag_id, code, args.reviewed)
        existing_a = existing_assets.get(primary_asset_id, {})
        conflicts = check_conflict(existing_a, new_primary, "asset_id")
        all_conflicts.extend(conflicts)
        merged_a, action_a = merge_record(existing_a, new_primary, args.reviewed)
        assets_out[primary_asset_id] = merged_a
        counts["assets"][action_a] += 1

        wiki_path = FLAGS_WIKI_DIR / f"{code}.png"
        if wiki_path.exists():
            wiki_asset_id = f"{flag_id}-wiki"
            if wiki_asset_id not in existing_assets:
                new_wiki = build_wiki_asset(flag_id, code)
                assets_out[wiki_asset_id] = new_wiki
                counts["assets"]["created"] += 1

        emoji_path = FLAGS_EMOJI_DIR / f"{code}.png"
        if emoji_path.exists():
            emoji_asset_id = f"{flag_id}-emoji"
            if emoji_asset_id not in existing_assets:
                new_emoji = build_emoji_asset(flag_id, code)
                assets_out[emoji_asset_id] = new_emoji
                counts["assets"]["created"] += 1

    if all_conflicts:
        print("ERROR: Protected field conflicts detected on reviewed records:", file=sys.stderr)
        for c in all_conflicts:
            print(c, file=sys.stderr)
        print("Re-run without conflicting changes. --force is not implemented in Phase 1.", file=sys.stderr)
        sys.exit(1)

    label = "[DRY RUN] " if args.dry_run else ""
    print(f"{label}Results:  created={counts['results']['created']}  upgraded={counts['results']['upgraded']}  skipped={counts['results']['skipped']}")
    print(f"{label}Flags:    created={counts['flags']['created']}  upgraded={counts['flags']['upgraded']}  skipped={counts['flags']['skipped']}")
    print(f"{label}Assets:   created={counts['assets']['created']}  upgraded={counts['assets']['upgraded']}  skipped={counts['assets']['skipped']}")

    if args.dry_run:
        print("[DRY RUN] No files written.")
        return

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(RESULTS_JSONL, results_out, dry_run=False)
    write_jsonl(FLAGS_JSONL, flags_out, dry_run=False)
    write_jsonl(ASSETS_JSONL, assets_out, dry_run=False)
    print(f"Wrote {RESULTS_JSONL.name}, {FLAGS_JSONL.name}, {ASSETS_JSONL.name}")


if __name__ == "__main__":
    main()
