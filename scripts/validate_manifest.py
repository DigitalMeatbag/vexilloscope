"""
Validate v3 manifest and produce QA reports.

Usage:
    python scripts/validate_manifest.py [--report-path reports/qa/latest.json]

Exits:
    0  no blockers
    1  one or more blockers
    2  script-level error (missing files, unreadable manifest, etc.)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_DIR = REPO_ROOT / "data" / "manifest"
RESULTS_JSONL = MANIFEST_DIR / "results.jsonl"
FLAGS_JSONL = MANIFEST_DIR / "flags.jsonl"
ASSETS_JSONL = MANIFEST_DIR / "assets.jsonl"
CONFUSABLES_JSONL = MANIFEST_DIR / "confusables.jsonl"

VALID_CATEGORY = {"national", "subnational", "military", "maritime", "organization",
                  "cultural", "pride", "sports", "other"}
VALID_FICTIONALITY = {"nonfiction", "fictional"}
VALID_STATUS = {"current", "historical", "proposed", "unofficial", "disputed", "deprecated"}
VALID_VARIANT = {"standard", "civil", "state", "military", "royal", "presidential",
                 "organizational", "alternate", "reconstruction", "ceremonial"}
VALID_ASSET_TYPE = {"source_original", "source_render", "emoji_render", "reference_only"}
VALID_REVIEW_STATUS = {"imported", "needs_review", "needs_source", "needs_license",
                       "needs_disambiguation", "reviewed", "rejected"}
VALID_CONFUSABLE_LEVEL = {"flag", "result"}
VALID_CONFUSABLE_SOURCE = {"manual", "qa_similarity", "model_confusion", "user_report"}

RESULT_REQUIRED = {"result_id", "display_name", "category", "fictionality", "status", "review_status"}
FLAG_REQUIRED = {"flag_id", "result_id", "display_name", "variant", "status", "review_status", "trainable"}
ASSET_REQUIRED = {"asset_id", "flag_id", "asset_type", "path", "source_name",
                  "source_url", "license", "review_status", "trainable"}
ASSET_CONDITIONAL_REQUIRED = {"source_url", "license"}
CONFUSABLE_REQUIRED = {"confusable_id", "level", "members", "reason", "source", "review_status"}


def _issue(severity, code, record_type, record_id, message, suggested_fix, field=None):
    obj = {
        "severity": severity,
        "code": code,
        "record_type": record_type,
        "record_id": record_id,
        "message": message,
        "suggested_fix": suggested_fix,
    }
    if field is not None:
        obj["field"] = field
    return obj


def blocker(code, record_type, record_id, message, suggested_fix, field=None):
    return _issue("blocker", code, record_type, record_id, message, suggested_fix, field)


def warning(code, record_type, record_id, message, suggested_fix, field=None):
    return _issue("warning", code, record_type, record_id, message, suggested_fix, field)


def load_jsonl(path: Path, id_field: str, issues: list) -> tuple[dict, bool]:
    """Load a JSONL file into a dict keyed by id_field. Returns (records, ok).
    Raises RuntimeError (-> exit 2) if the file does not exist.
    """
    records = {}
    if not path.exists():
        raise RuntimeError(f"Manifest file not found: {path}. Run migrate_v2.py to generate it.")

    ok = True
    with open(path, encoding="utf-8", newline="") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip("\n").rstrip("\r")
            if not line:
                issues.append(blocker(
                    "invalid_jsonl", path.stem, f"{path.name}:{lineno}",
                    f"Blank line at {path.name}:{lineno}.",
                    "Remove blank lines from JSONL files."
                ))
                ok = False
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                issues.append(blocker(
                    "invalid_jsonl", path.stem, f"{path.name}:{lineno}",
                    f"Invalid JSON at {path.name}:{lineno}: {e}",
                    "Fix the malformed JSON."
                ))
                ok = False
                continue

            if id_field not in obj:
                issues.append(blocker(
                    "missing_required_field", path.stem, f"{path.name}:{lineno}",
                    f"Record at line {lineno} is missing required field {id_field!r}.",
                    f"Add {id_field!r} to the record."
                ))
                ok = False
                continue

            rec_id = obj[id_field]
            if rec_id in records:
                dup_code = f"duplicate_{id_field}"
                issues.append(blocker(
                    dup_code, path.stem, rec_id,
                    f"{id_field} {rec_id!r} appears more than once in {path.name}.",
                    "Remove or rename the duplicate record."
                ))
                ok = False
            else:
                records[rec_id] = obj

    return records, ok


def check_missing_required(record: dict, required: set, conditional: set,
                            record_type: str, rec_id: str, issues: list) -> None:
    unconditional = required - conditional
    for field in sorted(unconditional):
        if field not in record:
            issues.append(blocker(
                "missing_required_field", record_type, rec_id,
                f"Record {rec_id!r} is missing required field {field!r}.",
                f"Add {field!r} to the record.",
                field=field
            ))


def check_enum(record: dict, field: str, valid: set,
               record_type: str, rec_id: str, issues: list) -> None:
    val = record.get(field)
    if val is not None and val not in valid:
        issues.append(blocker(
            "invalid_enum", record_type, rec_id,
            f"Field {field!r} has invalid value {val!r}.",
            f"Use one of: {sorted(valid)}.",
            field=field
        ))


def validate(manifest_dir: Path = MANIFEST_DIR) -> tuple[list, dict, dict]:
    issues = []

    results_jsonl = manifest_dir / "results.jsonl"
    flags_jsonl = manifest_dir / "flags.jsonl"
    assets_jsonl = manifest_dir / "assets.jsonl"
    confusables_jsonl = manifest_dir / "confusables.jsonl"

    results, results_ok = load_jsonl(results_jsonl, "result_id", issues)
    flags, flags_ok = load_jsonl(flags_jsonl, "flag_id", issues)
    assets, assets_ok = load_jsonl(assets_jsonl, "asset_id", issues)
    confusables, _ = load_jsonl(confusables_jsonl, "confusable_id", issues)

    # --- Results ---
    for rid, rec in results.items():
        check_missing_required(rec, RESULT_REQUIRED, set(), "result", rid, issues)
        check_enum(rec, "category", VALID_CATEGORY, "result", rid, issues)
        check_enum(rec, "fictionality", VALID_FICTIONALITY, "result", rid, issues)
        check_enum(rec, "status", VALID_STATUS, "result", rid, issues)
        check_enum(rec, "review_status", VALID_REVIEW_STATUS, "result", rid, issues)

        if rec.get("review_status") == "reviewed":
            if not rec.get("short_description"):
                issues.append(blocker(
                    "reviewed_result_missing_description", "result", rid,
                    f"Reviewed result {rid!r} is missing short_description.",
                    "Add a one-sentence short_description.",
                    field="short_description"
                ))
            if not rec.get("aliases"):
                issues.append(warning(
                    "result_no_aliases", "result", rid,
                    f"Reviewed result {rid!r} has no aliases.",
                    "Add one or more alternate names or search terms.",
                    field="aliases"
                ))
            if not rec.get("links"):
                issues.append(warning(
                    "result_no_links", "result", rid,
                    f"Reviewed result {rid!r} has no links.",
                    "Add at least one reference link.",
                    field="links"
                ))
            cat = rec.get("category")
            if cat in ("subnational", "military") and not rec.get("parent_result_id"):
                issues.append(warning(
                    "result_no_parent", "result", rid,
                    f"Reviewed result {rid!r} with category={cat!r} has no parent_result_id.",
                    "Add a parent_result_id.",
                    field="parent_result_id"
                ))

    # --- Flags ---
    for fid, rec in flags.items():
        check_missing_required(rec, FLAG_REQUIRED, set(), "flag", fid, issues)
        check_enum(rec, "variant", VALID_VARIANT, "flag", fid, issues)
        check_enum(rec, "status", VALID_STATUS, "flag", fid, issues)
        check_enum(rec, "review_status", VALID_REVIEW_STATUS, "flag", fid, issues)

        result_id = rec.get("result_id")
        if result_id and result_id not in results:
            issues.append(blocker(
                "flag_missing_result", "flag", fid,
                f"flag {fid!r} references result_id {result_id!r} which does not exist.",
                "Add the missing result record or correct the result_id.",
                field="result_id"
            ))

        if rec.get("trainable") is True and rec.get("review_status") != "reviewed":
            issues.append(blocker(
                "trainable_on_nonreviewed_flag", "flag", fid,
                f"Flag {fid!r} has trainable=true but review_status is not 'reviewed'.",
                "Set review_status=reviewed or set trainable=false.",
                field="trainable"
            ))

        if rec.get("review_status") == "reviewed":
            if not rec.get("aspect_ratio"):
                issues.append(warning(
                    "flag_no_aspect_ratio", "flag", fid,
                    f"Reviewed flag {fid!r} has no aspect_ratio.",
                    "Add the canonical aspect ratio (e.g., '2:3').",
                    field="aspect_ratio"
                ))
            if not rec.get("visual_notes"):
                issues.append(warning(
                    "flag_no_visual_notes", "flag", fid,
                    f"Reviewed flag {fid!r} has no visual_notes.",
                    "Add a brief visual description.",
                    field="visual_notes"
                ))

    # --- Per-flag trainable-asset counts ---
    flag_trainable_asset_counts: dict[str, int] = {}
    flag_has_trainable_source_original: dict[str, bool] = {}
    for fid in flags:
        flag_trainable_asset_counts[fid] = 0
        flag_has_trainable_source_original[fid] = False

    # --- Assets ---
    # Deferred image checks — collect (asset_id, path) pairs
    image_check_queue: list[tuple[str, str]] = []
    # For perceptual hash: {asset_id: (result_id, hash)}
    phash_map: dict[str, tuple[str, object]] = {}
    # For sha256 duplicate detection
    sha256_map: dict[str, str] = {}

    for aid, rec in assets.items():
        check_missing_required(rec, ASSET_REQUIRED, ASSET_CONDITIONAL_REQUIRED, "asset", aid, issues)
        check_enum(rec, "asset_type", VALID_ASSET_TYPE, "asset", aid, issues)
        check_enum(rec, "review_status", VALID_REVIEW_STATUS, "asset", aid, issues)

        flag_id = rec.get("flag_id")
        if flag_id and flag_id not in flags:
            issues.append(blocker(
                "asset_missing_flag", "asset", aid,
                f"Asset {aid!r} references flag_id {flag_id!r} which does not exist.",
                "Add the missing flag record or correct the flag_id.",
                field="flag_id"
            ))

        asset_type = rec.get("asset_type")
        review_status = rec.get("review_status")
        trainable = rec.get("trainable", False)

        if trainable is True and review_status != "reviewed":
            issues.append(blocker(
                "trainable_on_nonreviewed_asset", "asset", aid,
                f"Asset {aid!r} has trainable=true but review_status is not 'reviewed'.",
                "Set review_status=reviewed or set trainable=false.",
                field="trainable"
            ))

        if asset_type == "reference_only" and trainable is True:
            issues.append(blocker(
                "reference_only_trainable", "asset", aid,
                f"Asset {aid!r} has asset_type=reference_only and trainable=true.",
                "Set trainable=false for reference_only assets.",
                field="trainable"
            ))

        if trainable is True and not rec.get("license"):
            issues.append(blocker(
                "trainable_asset_missing_license", "asset", aid,
                f"Trainable asset {aid!r} is missing required license metadata.",
                "Add a reviewed license value or set trainable=false.",
                field="license"
            ))

        if review_status == "reviewed" and not rec.get("source_url"):
            issues.append(blocker(
                "reviewed_asset_missing_source_url", "asset", aid,
                f"Reviewed asset {aid!r} is missing source_url.",
                "Add a provenance URL.",
                field="source_url"
            ))

        if trainable and review_status == "reviewed":
            flag_rec = flags.get(flag_id, {})
            result_id = flag_rec.get("result_id") if flag_rec else None

            if flag_rec.get("review_status") != "reviewed":
                issues.append(blocker(
                    "trainable_asset_unreviewed_flag", "asset", aid,
                    f"Trainable asset {aid!r} is reviewed+trainable but flag {flag_id!r} is not reviewed.",
                    "Review the flag record or set trainable=false on the asset.",
                    field="flag_id"
                ))
            elif result_id and results.get(result_id, {}).get("review_status") != "reviewed":
                issues.append(blocker(
                    "trainable_asset_unreviewed_result", "asset", aid,
                    f"Trainable asset {aid!r}: flag's result {result_id!r} is not reviewed.",
                    "Review the result record or set trainable=false on the asset.",
                    field="flag_id"
                ))

            path_str = rec.get("path", "")
            abs_path = REPO_ROOT / path_str
            if not abs_path.exists():
                issues.append(blocker(
                    "trainable_asset_file_missing", "asset", aid,
                    f"Trainable asset {aid!r}: file not found at {path_str!r}.",
                    "Restore the file or set trainable=false.",
                    field="path"
                ))
            else:
                image_check_queue.append((aid, path_str))

            if flag_id in flag_trainable_asset_counts:
                flag_trainable_asset_counts[flag_id] += 1
            if asset_type == "source_original" and flag_id in flag_has_trainable_source_original:
                flag_has_trainable_source_original[flag_id] = True

        sha256 = rec.get("sha256")
        if sha256:
            if sha256 in sha256_map:
                issues.append(warning(
                    "asset_hash_duplicate", "asset", aid,
                    f"Asset {aid!r} sha256 matches asset {sha256_map[sha256]!r}.",
                    "Check for duplicate source files.",
                    field="sha256"
                ))
            else:
                sha256_map[sha256] = aid

    # --- Image integrity checks ---
    try:
        from PIL import Image
        pil_available = True
    except ImportError:
        pil_available = False
        print("WARNING: Pillow not installed — skipping image integrity checks.", file=sys.stderr)

    try:
        import imagehash
        imagehash_available = True
    except ImportError:
        imagehash_available = False

    if pil_available:
        for aid, path_str in image_check_queue:
            abs_path = REPO_ROOT / path_str
            try:
                img = Image.open(abs_path)
                img.load()
            except Exception as e:
                issues.append(blocker(
                    "trainable_asset_unreadable", "asset", aid,
                    f"Trainable asset {aid!r}: cannot decode image at {path_str!r}: {e}",
                    "Replace the file with a valid image.",
                    field="path"
                ))
                continue

            w, h = img.size
            if w == 0 or h == 0:
                issues.append(blocker(
                    "trainable_asset_zero_dimensions", "asset", aid,
                    f"Trainable asset {aid!r}: decoded image has zero dimensions ({w}x{h}).",
                    "Replace with a valid image.",
                    field="path"
                ))
                continue

            if w < 64 or h < 64:
                issues.append(warning(
                    "asset_small_dimensions", "asset", aid,
                    f"Trainable asset {aid!r}: image dimensions {w}x{h} are below 64x64.",
                    "Consider using a higher-resolution source.",
                    field="path"
                ))

            mode = img.mode
            if mode in ("RGBA", "LA") or (mode == "P" and "transparency" in img.info):
                rgba = img.convert("RGBA")
                extrema = rgba.getextrema()
                alpha_min = extrema[3][0] if len(extrema) > 3 else 255
                if alpha_min < 255:
                    issues.append(warning(
                        "asset_has_transparency", "asset", aid,
                        f"Trainable asset {aid!r}: image has non-opaque alpha pixels.",
                        "Composite onto a background or convert to RGB.",
                        field="path"
                    ))

            asset_rec = assets[aid]
            flag_id = asset_rec.get("flag_id", "")
            aspect_ratio_str = flags.get(flag_id, {}).get("aspect_ratio")
            if aspect_ratio_str:
                try:
                    ar_parts = [int(x) for x in aspect_ratio_str.split(":")]
                    if len(ar_parts) == 2 and ar_parts[1] != 0:
                        expected_ratio = ar_parts[0] / ar_parts[1]
                        actual_ratio = w / h if h != 0 else 0
                        if expected_ratio != 0 and abs(actual_ratio - expected_ratio) / expected_ratio > 0.20:
                            issues.append(warning(
                                "asset_aspect_ratio_drift", "asset", aid,
                                f"Trainable asset {aid!r}: actual ratio {w}:{h} differs from "
                                f"flag.aspect_ratio {aspect_ratio_str!r} by more than 20%.",
                                "Check the aspect_ratio field or the source image.",
                                field="path"
                            ))
                except (ValueError, ZeroDivisionError):
                    pass

            if imagehash_available:
                try:
                    ph = imagehash.phash(img)
                    result_id = flags.get(flag_id, {}).get("result_id", "")
                    phash_map[aid] = (result_id, ph)
                except Exception:
                    pass

    # --- Perceptual hash cross-result similarity ---
    if imagehash_available and phash_map:
        aid_list = list(phash_map.keys())
        for i in range(len(aid_list)):
            for j in range(i + 1, len(aid_list)):
                a1, a2 = aid_list[i], aid_list[j]
                r1, h1 = phash_map[a1]
                r2, h2 = phash_map[a2]
                if r1 != r2 and (h1 - h2) <= 8:
                    issues.append(warning(
                        "visual_similar_across_results", "asset", a1,
                        f"Asset {a1!r} (result {r1!r}) is perceptually similar to "
                        f"{a2!r} (result {r2!r}), pHash distance {h1 - h2}.",
                        "Add a confusables entry if this is expected.",
                        field="path"
                    ))

    # --- Confusables ---
    for cid, rec in confusables.items():
        check_missing_required(rec, CONFUSABLE_REQUIRED, set(), "confusable", cid, issues)
        check_enum(rec, "level", VALID_CONFUSABLE_LEVEL, "confusable", cid, issues)
        check_enum(rec, "source", VALID_CONFUSABLE_SOURCE, "confusable", cid, issues)
        check_enum(rec, "review_status", VALID_REVIEW_STATUS, "confusable", cid, issues)

        level = rec.get("level")
        members = rec.get("members", [])
        if isinstance(members, list) and len(members) < 2:
            issues.append(blocker(
                "missing_required_field", "confusable", cid,
                f"Confusable {cid!r} has fewer than 2 members (got {len(members)}).",
                "Add at least two member IDs.",
                field="members"
            ))
        ref_map = results if level == "result" else flags
        for member in members:
            if member not in ref_map:
                issues.append(blocker(
                    "confusable_missing_member", "confusable", cid,
                    f"Confusable {cid!r}: member {member!r} not found in {level}s.",
                    f"Add the missing {level} record or remove the member.",
                    field="members"
                ))

    # --- Per-flag warnings ---
    for fid, rec in flags.items():
        if rec.get("trainable") is True and rec.get("review_status") == "reviewed":
            count = flag_trainable_asset_counts.get(fid, 0)
            has_primary = flag_has_trainable_source_original.get(fid, False)

            if count == 1:
                issues.append(warning(
                    "flag_one_trainable_asset", "flag", fid,
                    f"Trainable flag {fid!r} has exactly one trainable asset.",
                    "Consider adding a secondary source for augmentation diversity.",
                    field="trainable"
                ))

            if not has_primary:
                issues.append(warning(
                    "trainable_flag_no_source_original", "flag", fid,
                    f"Trainable flag {fid!r} has no reviewed+trainable source_original asset. "
                    "The export script will skip this flag.",
                    "Approve a primary source_original asset.",
                    field="trainable"
                ))

    # --- Duplicate class ID in export ---
    # (Should not occur if duplicate_flag_id passes, but explicit check per spec)
    export_flag_ids = set()
    for fid, rec in flags.items():
        if rec.get("trainable") is True and rec.get("review_status") == "reviewed":
            result_id = rec.get("result_id")
            result_rec = results.get(result_id, {})
            if result_rec.get("review_status") == "reviewed":
                if fid in export_flag_ids:
                    issues.append(blocker(
                        "duplicate_class_id_in_export", "flag", fid,
                        f"Flag {fid!r} would be exported more than once.",
                        "Remove or rename the duplicate flag.",
                        field="flag_id"
                    ))
                export_flag_ids.add(fid)

    # --- Summary ---
    n_results = len(results)
    n_results_reviewed = sum(1 for r in results.values() if r.get("review_status") == "reviewed")
    n_flags = len(flags)
    n_flags_reviewed = sum(1 for f in flags.values() if f.get("review_status") == "reviewed")
    n_flags_trainable = sum(1 for f in flags.values() if f.get("trainable") is True)
    n_assets = len(assets)
    n_assets_reviewed = sum(1 for a in assets.values() if a.get("review_status") == "reviewed")
    n_assets_trainable = sum(1 for a in assets.values() if a.get("trainable") is True)
    n_export_eligible = len(export_flag_ids)

    summary = {
        "blockers": sum(1 for i in issues if i["severity"] == "blocker"),
        "warnings": sum(1 for i in issues if i["severity"] == "warning"),
        "results_total": n_results,
        "results_reviewed": n_results_reviewed,
        "flags_total": n_flags,
        "flags_reviewed": n_flags_reviewed,
        "flags_trainable": n_flags_trainable,
        "assets_total": n_assets,
        "assets_reviewed": n_assets_reviewed,
        "assets_trainable": n_assets_trainable,
        "export_eligible_classes": n_export_eligible,
    }

    loaded = {"results": results, "flags": flags, "assets": assets, "confusables": confusables}
    return issues, summary, loaded


def write_reports(issues: list, summary: dict, report_path: Path) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = {
        "version": 1,
        "generated_at": ts,
        "summary": summary,
        "issues": issues,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")

    md_path = report_path.parent / "latest.md"
    blockers = [i for i in issues if i["severity"] == "blocker"]
    warnings = [i for i in issues if i["severity"] == "warning"]

    lines = [
        "# Manifest QA Report",
        "",
        f"Generated: {ts}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, val in summary.items():
        label = key.replace("_", " ").title()
        lines.append(f"| {label} | {val} |")

    lines += ["", "## Blockers", ""]
    if blockers:
        for issue in blockers:
            field_note = f" (field: `{issue['field']}`)" if "field" in issue else ""
            lines.append(f"- **{issue['code']}** [{issue['record_type']} `{issue['record_id']}`]{field_note}: {issue['message']}")
    else:
        lines.append("(none)")

    lines += ["", "## Warnings", ""]
    if warnings:
        for issue in warnings:
            field_note = f" (field: `{issue['field']}`)" if "field" in issue else ""
            lines.append(f"- **{issue['code']}** [{issue['record_type']} `{issue['record_id']}`]{field_note}: {issue['message']}")
    else:
        lines.append("(none)")

    lines += [
        "",
        "## Export",
        "",
        f"Export eligible classes: {summary['export_eligible_classes']}",
        "",
    ]

    with open(md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    print(f"Wrote {report_path}")
    print(f"Wrote {md_path}")


def main():
    parser = argparse.ArgumentParser(description="Validate v3 manifest and produce QA reports.")
    parser.add_argument("--report-path", default=str(REPO_ROOT / "reports" / "qa" / "latest.json"),
                        help="Path to write the JSON QA report.")
    args = parser.parse_args()

    report_path = Path(args.report_path)

    try:
        issues, summary, _ = validate()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    write_reports(issues, summary, report_path)

    n_blockers = summary["blockers"]
    n_warnings = summary["warnings"]
    print(f"Blockers: {n_blockers}  Warnings: {n_warnings}  Export eligible: {summary['export_eligible_classes']}")

    sys.exit(0 if n_blockers == 0 else 1)


if __name__ == "__main__":
    main()
