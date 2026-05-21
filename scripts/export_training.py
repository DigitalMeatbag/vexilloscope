"""
Export v3 manifest to data/generated/train/ for the C trainer.

Usage:
    python scripts/export_training.py [--output data/generated/train]

Refuses to export if validate_manifest.py reports any blockers.
Exits non-zero on any error.
"""

import argparse
import io
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import cairosvg as _cairosvg
except ImportError:
    print(
        "ERROR: cairosvg is required for SVG export. "
        "Install it with: pip install cairosvg>=2.5",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from PIL import Image as _Image
except ImportError:
    print("ERROR: Pillow is required. Install it with: pip install Pillow>=9.0", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "data" / "generated" / "train"
SVG_RENDER_SIZE = 512

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_manifest as vm


def _render_svg_for_export(svg_path: Path) -> bytes:
    """Render SVG to SVG_RENDER_SIZE×SVG_RENDER_SIZE PNG bytes for training export.

    Renders aspect-preserving with white background and padding, then saves at
    SVG_RENDER_SIZE without downsampling. The C trainer's img_load resizes to
    128×128 using the same algorithm as --identify, keeping training and
    inference on the same resize pipeline.
    """
    # Render at export canvas width; height scales naturally
    png_bytes = _cairosvg.svg2png(url=str(svg_path), output_width=SVG_RENDER_SIZE)
    img = _Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    w, h = img.size

    # If natural height exceeds canvas, re-render constrained by height
    if h > SVG_RENDER_SIZE:
        png_bytes = _cairosvg.svg2png(url=str(svg_path), output_height=SVG_RENDER_SIZE)
        img = _Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        w, h = img.size

    # Composite centered onto white canvas at SVG_RENDER_SIZE
    canvas = _Image.new("RGB", (SVG_RENDER_SIZE, SVG_RENDER_SIZE), "white")
    x = (SVG_RENDER_SIZE - w) // 2
    y = (SVG_RENDER_SIZE - h) // 2
    canvas.paste(img, (x, y), mask=img.split()[3])

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def _rel(p: Path) -> str:
    """Return POSIX-style path relative to repo root, falling back to absolute."""
    try:
        return str(p.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def main():
    parser = argparse.ArgumentParser(description="Export v3 manifest to training dataset.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help="Output directory (default: data/generated/train).")
    args = parser.parse_args()

    output_dir = Path(args.output)

    # --- Run validation first (returns loaded records, avoiding a second disk read) ---
    print("Running manifest validation...")
    try:
        issues, summary, loaded = vm.validate()
    except Exception as e:
        print(f"ERROR: validation failed: {e}", file=sys.stderr)
        sys.exit(2)

    n_blockers = summary["blockers"]
    if n_blockers > 0:
        print(f"ERROR: {n_blockers} blocker(s) found. Fix blockers before exporting.", file=sys.stderr)
        for issue in issues:
            if issue["severity"] == "blocker":
                print(f"  [{issue['code']}] {issue['record_type']} {issue['record_id']}: {issue['message']}",
                      file=sys.stderr)
        sys.exit(1)

    print(f"Validation passed (0 blockers, {summary['warnings']} warnings).")

    results = loaded["results"]
    flags = loaded["flags"]
    assets_raw = loaded["assets"]

    # Index assets by flag_id and asset_type for efficient lookup
    # assets_by_flag[flag_id][asset_type] = list of eligible assets
    assets_by_flag: dict[str, dict[str, list[dict]]] = {}
    for aid, asset in assets_raw.items():
        if asset.get("trainable") is True and asset.get("review_status") == "reviewed":
            fid = asset.get("flag_id", "")
            atype = asset.get("asset_type", "")
            assets_by_flag.setdefault(fid, {}).setdefault(atype, []).append(asset)

    # --- Determine export-eligible flags (sorted by flag_id) ---
    eligible_flags = []
    for fid, flag in sorted(flags.items()):
        if flag.get("trainable") is not True:
            continue
        if flag.get("review_status") != "reviewed":
            continue
        result_id = flag.get("result_id", "")
        result = results.get(result_id, {})
        if result.get("review_status") != "reviewed":
            continue
        # Must have at least one eligible source_original asset
        primary_assets = assets_by_flag.get(fid, {}).get("source_original", [])
        if not primary_assets:
            print(f"WARNING: flag {fid!r} has no eligible source_original asset — skipping.",
                  file=sys.stderr)
            continue
        eligible_flags.append((fid, flag, result, primary_assets,
                                assets_by_flag.get(fid, {}).get("source_render", []),
                                assets_by_flag.get(fid, {}).get("emoji_render", [])))

    if not eligible_flags:
        print("ERROR: No export-eligible flags found.", file=sys.stderr)
        sys.exit(1)

    # --- Set up output directories ---
    images_dir = output_dir / "images"
    images_wiki_dir = output_dir / "images_wiki"
    images_emoji_dir = output_dir / "images_emoji"

    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    has_wiki = any(wiki_assets for _, _, _, _, wiki_assets, _ in eligible_flags)
    has_emoji = any(emoji_assets for _, _, _, _, _, emoji_assets in eligible_flags)

    if has_wiki:
        images_wiki_dir.mkdir(parents=True, exist_ok=True)
    if has_emoji:
        images_emoji_dir.mkdir(parents=True, exist_ok=True)

    # --- Copy images and build labels + class map ---
    labels_rows = []
    class_entries = []

    for class_id, (fid, flag, result, primary_assets, wiki_assets, emoji_assets) in enumerate(eligible_flags):
        display_name = result.get("display_name", "")

        # Primary image — use the first eligible source_original
        primary_asset = primary_assets[0]
        src_path = REPO_ROOT / primary_asset["path"]
        dest_path = images_dir / f"{fid}.png"
        if primary_asset["path"].endswith(".svg"):
            png_bytes = _render_svg_for_export(src_path)
            dest_path.write_bytes(png_bytes)
        else:
            shutil.copy2(str(src_path), str(dest_path))

        # Wiki image — first eligible source_render
        if has_wiki and wiki_assets:
            wiki_asset = wiki_assets[0]
            wiki_src = REPO_ROOT / wiki_asset["path"]
            wiki_dest = images_wiki_dir / f"{fid}.png"
            shutil.copy2(str(wiki_src), str(wiki_dest))

        # Emoji image — first eligible emoji_render
        if has_emoji and emoji_assets:
            emoji_asset = emoji_assets[0]
            emoji_src = REPO_ROOT / emoji_asset["path"]
            emoji_dest = images_emoji_dir / f"{fid}.png"
            shutil.copy2(str(emoji_src), str(emoji_dest))

        # Quote name if it contains a comma
        name_field = f'"{display_name}"' if "," in display_name else display_name
        labels_rows.append(f"{fid},{name_field}")

        class_entries.append({
            "class_id": class_id,
            "flag_id": fid,
            "result_id": result.get("result_id", ""),
            "display_name": display_name,
            "category": result.get("category", ""),
            "fictionality": result.get("fictionality", ""),
            "status": flag.get("status", ""),
            "variant": flag.get("variant", ""),
        })

    # --- Write labels.csv ---
    labels_path = output_dir / "labels.csv"
    with open(labels_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("code,name\n")
        for row in labels_rows:
            f.write(row + "\n")

    # --- Write class_map.json ---
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    class_map = {
        "version": 1,
        "generated_at": ts,
        "n_classes": len(class_entries),
        "classes": class_entries,
    }
    class_map_path = output_dir / "class_map.json"
    with open(class_map_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(class_map, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # --- Report ---
    n_classes = len(class_entries)
    print(f"Exported {n_classes} classes.")
    print(f"  labels.csv:    {labels_path}")
    print(f"  class_map.json: {class_map_path}")
    print(f"  images/:       {images_dir}  ({n_classes} PNGs)")
    if has_wiki:
        n_wiki = sum(1 for _, _, _, _, w, _ in eligible_flags if w)
        print(f"  images_wiki/:  {images_wiki_dir}  ({n_wiki} PNGs)")
    if has_emoji:
        n_emoji = sum(1 for _, _, _, _, _, e in eligible_flags if e)
        print(f"  images_emoji/: {images_emoji_dir}  ({n_emoji} PNGs)")

    # --- Print C trainer invocation ---
    invocation_parts = [
        r".\build\vexilloscope.exe",
        _rel(labels_path),
        _rel(images_dir) + "/",
    ]
    if has_wiki:
        invocation_parts.append(_rel(images_wiki_dir) + "/")
    if has_emoji:
        invocation_parts.append(_rel(images_emoji_dir) + "/")

    invocation_parts.append("--eval-dump data/generated/train/eval_dump.csv")

    print("\nC trainer invocation:")
    print(" ".join(invocation_parts))


if __name__ == "__main__":
    main()
