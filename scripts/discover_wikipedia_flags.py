"""
Discover candidate flag assets from Wikipedia/Commons list pages/categories.

This is intentionally a discovery tool, not a manifest importer. Wikipedia flag
list pages are broad and uneven, so the script writes a reviewable CSV and can
optionally download the original Commons files into data/sources/.

Usage:
    python scripts/discover_wikipedia_flags.py
    python scripts/discover_wikipedia_flags.py --expand-hub --limit-pages 25
    python scripts/discover_wikipedia_flags.py --page "List of naval flags" --download
    python scripts/discover_wikipedia_flags.py --page-url "https://commons.wikimedia.org/wiki/LGBT_flags" --download
    python scripts/discover_wikipedia_flags.py --commons-category "Flags of territories of the Holy Roman Empire" --download
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports" / "import" / "wikipedia"
DOWNLOAD_DIR = REPO_ROOT / "data" / "sources" / "wikimedia" / "discovered"

ENWIKI_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_FILE_PAGE = "https://commons.wikimedia.org/wiki/File:{filename}"

USER_AGENT = (
    "vexilloscope-wikipedia-flag-discovery/1.0 "
    "(https://github.com/anthonybvargo/vexilloscope); "
    "python-requests/2.x"
)
DEFAULT_DELAY_SECONDS = 1.0
DEFAULT_BATCH_SIZE = 50
DEFAULT_PAGE = "Lists of flags"
DEFAULT_FILE_REGEX = r"(?i)\b(flag|ensign|banner|standard|jack|roundel)\b"
VALID_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg"}

LICENSE_MAP: dict[str, str] = {
    "Public domain": "public-domain",
    "CC0": "cc0",
    "CC BY 4.0": "cc-by-4.0",
    "CC BY-SA 4.0": "cc-by-sa-4.0",
    "CC BY-SA 3.0": "cc-by-sa-3.0",
    "CC BY-SA 2.5": "cc-by-sa-2.5",
    "CC BY-SA 2.0": "cc-by-sa-2.0",
}


def _api_get(
    session: requests.Session,
    api_url: str,
    params: dict,
    delay_seconds: float,
    max_retries: int = 6,
) -> dict:
    request_params = dict(params)
    request_params.setdefault("maxlag", "5")

    for attempt in range(max_retries + 1):
        resp = session.get(api_url, params=request_params, timeout=30)
        if resp.status_code in {429, 503}:
            retry_after = resp.headers.get("Retry-After")
            wait_s = float(retry_after) if retry_after and retry_after.isdigit() else max(1.0, delay_seconds) * (2 ** attempt)
            print(f"  rate limited by API; sleeping {wait_s:.1f}s", file=sys.stderr)
            time.sleep(wait_s)
            continue

        resp.raise_for_status()
        data = resp.json()
        error = data.get("error", {})
        if error.get("code") == "maxlag":
            lag = error.get("lag")
            wait_s = max(max(1.0, delay_seconds) * (2 ** attempt), float(lag) if isinstance(lag, (int, float)) else 0.0)
            print(f"  Wikimedia maxlag; sleeping {wait_s:.1f}s", file=sys.stderr)
            time.sleep(wait_s)
            continue
        return data

    raise RuntimeError(f"API request failed after {max_retries + 1} attempts")


def _normalize_file_title(name: str) -> str:
    name = name.strip().replace("_", " ")
    if name.startswith("File:"):
        return name
    return f"File:{name}"


def _filename_from_title(file_title: str) -> str:
    return file_title.removeprefix("File:").replace(" ", "_")


def _file_extension(file_title: str) -> str:
    return Path(_filename_from_title(file_title)).suffix.lower()


def _safe_local_name(file_title: str) -> str:
    filename = _filename_from_title(file_title)
    return re.sub(r"[^A-Za-z0-9._-]+", "_", filename)


def _wiki_title_from_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.netloc not in {"en.wikipedia.org", "commons.wikimedia.org"}:
        raise ValueError(f"unsupported wiki host: {parsed.netloc}")
    marker = "/wiki/"
    if marker not in parsed.path:
        raise ValueError(f"URL does not look like a wiki page URL: {url}")
    title = unquote(parsed.path.split(marker, 1)[1]).replace("_", " ")
    api_url = COMMONS_API if parsed.netloc == "commons.wikimedia.org" else ENWIKI_API
    return title, api_url


def _parse_page_images(
    session: requests.Session,
    title: str,
    api_url: str,
    delay_seconds: float,
) -> list[str]:
    data = _api_get(
        session,
        api_url,
        {
            "action": "parse",
            "page": title,
            "prop": "images",
            "format": "json",
            "formatversion": 2,
        },
        delay_seconds,
    )
    images = data.get("parse", {}).get("images", [])
    return [_normalize_file_title(img) for img in images]


def _parse_page_links(
    session: requests.Session,
    title: str,
    api_url: str,
    delay_seconds: float,
) -> list[str]:
    data = _api_get(
        session,
        api_url,
        {
            "action": "parse",
            "page": title,
            "prop": "links",
            "format": "json",
            "formatversion": 2,
        },
        delay_seconds,
    )
    links = data.get("parse", {}).get("links", [])
    titles: list[str] = []
    for link in links:
        if link.get("ns") != 0:
            continue
        linked_title = link.get("title", "")
        if "flag" in linked_title.lower() and linked_title not in titles:
            titles.append(linked_title)
    return titles


def _category_file_titles(
    session: requests.Session,
    category_title: str,
    delay_seconds: float,
) -> list[str]:
    if not category_title.startswith("Category:"):
        category_title = f"Category:{category_title}"

    titles: list[str] = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category_title,
        "cmnamespace": "6",
        "cmlimit": "500",
        "format": "json",
        "formatversion": 2,
    }
    while True:
        data = _api_get(session, COMMONS_API, params, delay_seconds)
        for member in data.get("query", {}).get("categorymembers", []):
            title = member.get("title", "")
            if title.startswith("File:") and title not in titles:
                titles.append(title)
        cont = data.get("continue", {})
        if "cmcontinue" not in cont:
            break
        params["cmcontinue"] = cont["cmcontinue"]
        time.sleep(delay_seconds)
    return titles


def _commons_imageinfo_batch(
    session: requests.Session,
    file_titles: list[str],
    delay_seconds: float,
) -> dict[str, dict]:
    if not file_titles:
        return {}
    data = _api_get(
        session,
        COMMONS_API,
        {
            "action": "query",
            "titles": "|".join(file_titles),
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata",
            "iiextmetadatafilter": "LicenseShortName|Artist|Credit",
            "format": "json",
            "formatversion": 2,
        },
        delay_seconds,
    )

    infos_by_title: dict[str, dict] = {}
    pages = data.get("query", {}).get("pages", [])
    for page in pages:
        if page.get("missing"):
            continue
        infos = page.get("imageinfo") or []
        if infos:
            infos_by_title[page.get("title", "")] = infos[0]
    return infos_by_title


def _license_from_imageinfo(info: dict) -> str:
    extmeta = info.get("extmetadata", {})
    short_name = extmeta.get("LicenseShortName", {}).get("value", "")
    return LICENSE_MAP.get(short_name, short_name)


def _download(
    session: requests.Session,
    url: str,
    out_dir: Path,
    file_title: str,
    delay_seconds: float,
    max_retries: int = 6,
) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_local_name(file_title)

    parsed_name = unquote(Path(urlparse(url).path).name)
    parsed_ext = Path(parsed_name).suffix
    if parsed_ext and not Path(filename).suffix:
        filename += parsed_ext

    out_path = out_dir / filename
    if out_path.exists():
        return str(out_path.relative_to(REPO_ROOT)).replace("\\", "/")

    for attempt in range(max_retries + 1):
        resp = session.get(url, timeout=60)
        if resp.status_code in {429, 503}:
            retry_after = resp.headers.get("Retry-After")
            wait_s = float(retry_after) if retry_after and retry_after.isdigit() else max(1.0, delay_seconds) * (2 ** attempt)
            print(f"  rate limited by download host; sleeping {wait_s:.1f}s", file=sys.stderr)
            time.sleep(wait_s)
            continue
        resp.raise_for_status()
        out_path.write_bytes(resp.content)
        break
    else:
        raise RuntimeError(f"download failed after {max_retries + 1} attempts")
    return str(out_path.relative_to(REPO_ROOT)).replace("\\", "/")


def _chunked(items: list[tuple[str, str]], size: int) -> list[list[tuple[str, str]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _load_existing_rows(path: Path) -> tuple[list[dict[str, str]], set[str]]:
    if not path.exists():
        return [], set()

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(row) for row in reader]

    seen = {row.get("file_title", "") for row in rows if row.get("file_title")}
    return rows, seen


def discover_candidates(
    session: requests.Session,
    page_specs: list[tuple[str, str]],
    category_titles: list[str],
    file_regex: re.Pattern,
    max_files: int | None,
    download: bool,
    delay_seconds: float,
    batch_size: int,
    existing_file_titles: set[str],
) -> list[dict[str, str]]:
    seen_files: set[str] = set(existing_file_titles)
    rows: list[dict[str, str]] = []
    pending: list[tuple[str, str]] = []

    def queue_file(source_name: str, file_title: str) -> bool:
        if max_files is not None and len(rows) + len(pending) >= max_files:
            return False
        if file_title in seen_files:
            return True
        if _file_extension(file_title) not in VALID_EXTENSIONS:
            return True
        if not file_regex.search(file_title):
            return True

        seen_files.add(file_title)
        pending.append((source_name, file_title))
        return True

    def process_batch(batch: list[tuple[str, str]]) -> bool:
        titles = [file_title for _, file_title in batch]
        try:
            infos = _commons_imageinfo_batch(session, titles, delay_seconds)
            time.sleep(delay_seconds)
        except Exception as e:
            print(f"  WARN: failed batch imageinfo: {e}", file=sys.stderr)
            return True

        for source_name, file_title in batch:
            info = infos.get(file_title)
            if not info:
                continue

            original_url = info.get("url", "")
            local_path = ""
            if download and original_url:
                try:
                    local_path = _download(session, original_url, DOWNLOAD_DIR, file_title, delay_seconds)
                    time.sleep(delay_seconds)
                except Exception as e:
                    print(f"  WARN: failed download for {file_title!r}: {e}", file=sys.stderr)

            filename = _filename_from_title(file_title)
            rows.append(
                {
                    "source_page": source_name,
                    "file_title": file_title,
                    "filename": filename,
                    "commons_page_url": COMMONS_FILE_PAGE.format(filename=filename),
                    "original_url": original_url,
                    "mime": info.get("mime", ""),
                    "width": str(info.get("width", "")),
                    "height": str(info.get("height", "")),
                    "license": _license_from_imageinfo(info),
                    "local_path": local_path,
                }
            )
            print(f"  candidate: {filename}")
            if max_files is not None and len(rows) >= max_files:
                return False
        return True

    for page_title, api_url in page_specs:
        print(f"Scanning page: {page_title}")
        try:
            image_titles = _parse_page_images(session, page_title, api_url, delay_seconds)
            time.sleep(delay_seconds)
        except Exception as e:
            print(f"  WARN: failed to parse {page_title!r}: {e}", file=sys.stderr)
            continue

        for file_title in image_titles:
            if not queue_file(page_title, file_title):
                break

    for category_title in category_titles:
        print(f"Scanning Commons category: {category_title}")
        try:
            image_titles = _category_file_titles(session, category_title, delay_seconds)
            time.sleep(delay_seconds)
        except Exception as e:
            print(f"  WARN: failed category scan for {category_title!r}: {e}", file=sys.stderr)
            continue
        for file_title in image_titles:
            if not queue_file(category_title, file_title):
                break

    for batch in _chunked(pending, batch_size):
        if not process_batch(batch):
            break

    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "source_page",
        "file_title",
        "filename",
        "commons_page_url",
        "original_url",
        "mime",
        "width",
        "height",
        "license",
        "local_path",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover candidate flag assets from Wikipedia list pages."
    )
    parser.add_argument(
        "--page",
        action="append",
        dest="pages",
        help=f"Wikipedia page title to scan. Can be repeated. Default: {DEFAULT_PAGE!r}.",
    )
    parser.add_argument(
        "--commons-page",
        action="append",
        default=[],
        help="Commons page title to scan. Can be repeated.",
    )
    parser.add_argument(
        "--commons-category",
        action="append",
        default=[],
        help="Commons category title to scan. Can be repeated; 'Category:' is optional.",
    )
    parser.add_argument(
        "--page-url",
        action="append",
        default=[],
        help="Full en.wikipedia.org or commons.wikimedia.org /wiki/ URL to scan. Can be repeated.",
    )
    parser.add_argument(
        "--expand-hub",
        action="store_true",
        help="Treat --page values as hub pages and scan linked article titles containing 'flag'.",
    )
    parser.add_argument(
        "--limit-pages",
        type=int,
        default=None,
        help="Maximum number of linked pages to scan after --expand-hub.",
    )
    parser.add_argument(
        "--limit-files",
        type=int,
        default=None,
        help="Maximum number of candidate files to emit.",
    )
    parser.add_argument(
        "--file-regex",
        default=DEFAULT_FILE_REGEX,
        help="Regex used to keep candidate file names.",
    )
    parser.add_argument(
        "--output",
        default=str(REPORTS_DIR / "wikipedia_flag_candidates.csv"),
        help="Review CSV output path.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help=f"Download original files to {DOWNLOAD_DIR.relative_to(REPO_ROOT)}.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"Polite delay between API/download requests (default: {DEFAULT_DELAY_SECONDS}).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Commons imageinfo batch size, max 50 for normal API users (default: {DEFAULT_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore an existing output CSV instead of skipping its file_title values.",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    page_specs: list[tuple[str, str]] = []
    for title in args.pages or []:
        page_specs.append((title, ENWIKI_API))
    for title in args.commons_page:
        page_specs.append((title, COMMONS_API))
    for url in args.page_url:
        try:
            page_specs.append(_wiki_title_from_url(url))
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(2)
    if not page_specs and not args.commons_category:
        page_specs.append((DEFAULT_PAGE, ENWIKI_API))
    page_specs = list(dict.fromkeys(page_specs))

    if args.expand_hub:
        expanded: list[tuple[str, str]] = []
        for title, api_url in page_specs:
            print(f"Expanding hub page: {title}")
            try:
                expanded.extend((linked_title, api_url) for linked_title in _parse_page_links(session, title, api_url, args.delay_seconds))
                time.sleep(args.delay_seconds)
            except Exception as e:
                print(f"ERROR: failed to expand hub {title!r}: {e}", file=sys.stderr)
                sys.exit(2)
        page_specs = list(dict.fromkeys(expanded))
        if args.limit_pages is not None:
            page_specs = page_specs[: args.limit_pages]

    try:
        file_regex = re.compile(args.file_regex)
    except re.error as e:
        print(f"ERROR: invalid --file-regex: {e}", file=sys.stderr)
        sys.exit(2)

    output_path = Path(args.output)
    existing_rows: list[dict[str, str]] = []
    existing_file_titles: set[str] = set()
    if not args.no_resume:
        existing_rows, existing_file_titles = _load_existing_rows(output_path)
        if existing_rows:
            print(f"Resuming from {output_path}: {len(existing_rows)} existing candidates")

    batch_size = max(1, min(args.batch_size, 50))
    rows = discover_candidates(
        session=session,
        page_specs=page_specs,
        category_titles=args.commons_category,
        file_regex=file_regex,
        max_files=args.limit_files,
        download=args.download,
        delay_seconds=max(0.0, args.delay_seconds),
        batch_size=batch_size,
        existing_file_titles=existing_file_titles,
    )

    all_rows = existing_rows + rows
    write_csv(all_rows, output_path)
    print(f"\nWrote {len(all_rows)} candidates to {output_path} ({len(rows)} new)")
    if args.download:
        print(f"Downloaded files live under {DOWNLOAD_DIR}")


if __name__ == "__main__":
    main()
