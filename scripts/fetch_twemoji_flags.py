"""
Download Twemoji flag emoji PNGs as a third training source.

Twemoji (CC-BY 4.0) renders represent flag emoji as displayed in Discord
and similar apps — a visually distinct style from the hampusborgos and
Wikimedia sources.

Usage:
    python scripts/fetch_twemoji_flags.py

Output: data/flags_emoji/<code>.png  (skips existing files)

Dependencies: requests, Pillow
"""

import csv
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

LABELS_CSV  = Path(__file__).parent.parent / "data" / "labels.csv"
OUTPUT_DIR  = Path(__file__).parent.parent / "data" / "flags_emoji"
TARGET_SIZE = (128, 128)
DELAY_S     = 0.5   # GitHub raw rate-limits on quick bursts; keep this ≥ 0.5

# Twemoji 72x72 PNG CDN (CC-BY 4.0, Twitter/X open-source emoji project)
TWEMOJI_URL = "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/{codepoint}.png"

_RI_BASE = 0x1F1E6  # Unicode Regional Indicator Symbol Letter A


def iso_to_codepoint(code: str) -> str:
    """'US' → '1f1fa-1f1f8'  (Twemoji filename convention)."""
    a, b = code.upper()
    return f"{_RI_BASE + ord(a) - 65:x}-{_RI_BASE + ord(b) - 65:x}"


def fetch(url: str, code: str, retries: int = 4) -> bytes | None:
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=(10, 30))
            if r.status_code == 200:
                return r.content
            if r.status_code == 404:
                print(f"  [{code}] HTTP 404 — skipped")
                return None
            print(f"  [{code}] HTTP {r.status_code} (attempt {attempt + 1}) — retrying")
        except requests.exceptions.Timeout:
            print(f"  [{code}] timeout (attempt {attempt + 1}) — retrying")
        except Exception as e:
            print(f"  [{code}] error: {e} — skipped")
            return None
        time.sleep(5.0 * (attempt + 1))
    print(f"  [{code}] failed after {retries} attempts — skipped")
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
        if len(code) != 2:
            print(f"  [{code}] non-2-letter code — skipped")
            failed += 1
            continue

        out_path = OUTPUT_DIR / f"{code.lower()}.png"
        if out_path.exists():
            skipped += 1
            continue

        cp  = iso_to_codepoint(code)
        url = TWEMOJI_URL.format(codepoint=cp)
        data = fetch(url, code)

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
