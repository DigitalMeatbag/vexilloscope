"""
Download Wikimedia-sourced flag images from flagcdn.com (rendered from the
same SVGs as Wikipedia) and resize to 128x128 for use as a second training
source alongside data/flags/.

Usage:
    python scripts/fetch_wiki_flags.py

Output: data/flags_wiki/<code>.png  (skips existing files)

Dependencies: requests, Pillow
"""

import csv
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

LABELS_CSV  = Path(__file__).parent.parent / "data" / "labels.csv"
OUTPUT_DIR  = Path(__file__).parent.parent / "data" / "flags_wiki"
FLAGCDN_URL = "https://flagcdn.com/w1280/{code}.png"
TARGET_SIZE = (128, 128)
DELAY_S     = 0.15


def fetch(code: str) -> bytes | None:
    url = FLAGCDN_URL.format(code=code.lower())
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.content
        print(f"  [{code}] HTTP {r.status_code} — skipped")
        return None
    except Exception as e:
        print(f"  [{code}] network error: {e} — skipped")
        return None


def to_128x128_png(data: bytes) -> bytes:
    img = Image.open(BytesIO(data)).convert("RGBA")
    bg  = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    out = bg.convert("RGB").resize(TARGET_SIZE, Image.LANCZOS)
    buf = BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(LABELS_CSV, newline="", encoding="utf-8") as f:
        codes = [row["code"] for row in csv.DictReader(f)]

    print(f"fetching {len(codes)} flags → {OUTPUT_DIR}\n")
    ok = skipped = failed = 0

    for code in codes:
        out_path = OUTPUT_DIR / f"{code.lower()}.png"

        if out_path.exists():
            skipped += 1
            continue

        data = fetch(code)
        if data is None:
            failed += 1
            continue

        try:
            png = to_128x128_png(data)
        except Exception as e:
            print(f"  [{code}] decode error: {e} — skipped")
            failed += 1
            continue

        out_path.write_bytes(png)
        print(f"  [{code}] ok")
        ok += 1
        time.sleep(DELAY_S)

    print(f"\ndone: {ok} fetched, {skipped} already existed, {failed} failed")


if __name__ == "__main__":
    main()
