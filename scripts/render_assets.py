"""
Render reviewed SVG source assets to PNG for visual inspection.

Usage:
    python scripts/render_assets.py
        [--source-dir data/sources/wikimedia/us_states]
        [--output-dir data/generated/renders/wikimedia/us_states]
        [--all]

By default, skips assets whose review_status in assets.jsonl is not
'imported' or 'reviewed'. Pass --all to render regardless of status.

Exits non-zero if any render fails.
"""

import argparse
import io
import json
import sys
from pathlib import Path

try:
    import cairosvg
except ImportError:
    cairosvg = None  # type: ignore[assignment]

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_DIR = REPO_ROOT / "data" / "manifest"
ASSETS_JSONL = MANIFEST_DIR / "assets.jsonl"

DEFAULT_SOURCE_DIR = REPO_ROOT / "data" / "sources" / "wikimedia" / "us_states"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "generated" / "renders" / "wikimedia" / "us_states"

RENDER_CANVAS = 512
ALLOWED_REVIEW_STATUSES = {"imported", "reviewed"}


def _load_asset_review_statuses(assets_path: Path) -> dict[str, str]:
    """Return a mapping of asset path → review_status from assets.jsonl."""
    status_by_path: dict[str, str] = {}
    if not assets_path.exists():
        return status_by_path
    with open(assets_path, encoding="utf-8", newline="") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            path = obj.get("path", "")
            status = obj.get("review_status", "")
            if path:
                status_by_path[path] = status
    return status_by_path


def render_svg_to_png(svg_path: Path, canvas_size: int = RENDER_CANVAS) -> bytes:
    """Render an SVG file to PNG bytes at canvas_size×canvas_size with white background.

    Uses aspect-preserving resize: render at the given width, then height-constrain if
    the natural height exceeds the canvas. Center the result on a white canvas.
    """
    if cairosvg is None:
        raise RuntimeError(
            "cairosvg is required. Install it with: pip install 'cairosvg>=2.5'. "
            "On Windows, also install the GTK3 runtime."
        )
    if Image is None:
        raise RuntimeError("Pillow is required. Install it with: pip install Pillow>=9.0")

    # Render at canvas width; height scales proportionally
    png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=canvas_size)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    w, h = img.size

    # If natural height exceeds canvas, re-render constrained by height
    if h > canvas_size:
        png_bytes = cairosvg.svg2png(url=str(svg_path), output_height=canvas_size)
        img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        w, h = img.size

    # Composite centered onto white canvas
    canvas = Image.new("RGB", (canvas_size, canvas_size), "white")
    x = (canvas_size - w) // 2
    y = (canvas_size - h) // 2
    canvas.paste(img, (x, y), mask=img.split()[3])

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render SVG source assets to PNG for visual inspection."
    )
    parser.add_argument(
        "--source-dir",
        default=str(DEFAULT_SOURCE_DIR),
        help="Directory containing SVG source assets (default: data/sources/wikimedia/us_states).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for rendered PNGs (default: data/generated/renders/wikimedia/us_states).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="render_all",
        help="Render all SVGs regardless of review_status.",
    )
    args = parser.parse_args()

    if cairosvg is None:
        print(
            "ERROR: cairosvg is required for rendering. "
            "Install it with: pip install 'cairosvg>=2.5'. "
            "On Windows, also install the GTK3 runtime.",
            file=sys.stderr,
        )
        sys.exit(1)

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)

    if not source_dir.exists():
        print(f"ERROR: source directory does not exist: {source_dir}", file=sys.stderr)
        sys.exit(1)

    svg_files = sorted(source_dir.glob("*.svg"))
    if not svg_files:
        print(f"No SVG files found in {source_dir}")
        sys.exit(0)

    # Load asset review statuses for filtering
    status_by_path = _load_asset_review_statuses(ASSETS_JSONL)

    output_dir.mkdir(parents=True, exist_ok=True)

    n_rendered = 0
    n_skipped = 0
    n_failed = 0

    for svg_path in svg_files:
        # Build the relative path key as stored in assets.jsonl
        try:
            rel_path = str(svg_path.relative_to(REPO_ROOT)).replace("\\", "/")
        except ValueError:
            rel_path = str(svg_path).replace("\\", "/")

        if not args.render_all:
            review_status = status_by_path.get(rel_path)
            if review_status not in ALLOWED_REVIEW_STATUSES:
                print(f"  SKIP (review_status={review_status!r}): {svg_path.name}")
                n_skipped += 1
                continue

        png_path = output_dir / (svg_path.stem + ".png")
        try:
            png_bytes = render_svg_to_png(svg_path, canvas_size=RENDER_CANVAS)
            png_path.write_bytes(png_bytes)
            print(f"  rendered: {svg_path.name} -> {png_path.name}")
            n_rendered += 1
        except Exception as e:
            print(f"  FAIL: {svg_path.name}: {e}", file=sys.stderr)
            n_failed += 1

    print(f"\nDone: {n_rendered} rendered, {n_skipped} skipped, {n_failed} failed.")

    if n_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
