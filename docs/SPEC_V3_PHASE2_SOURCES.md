# vexilloscope v3 Phase 2 Specification: Source Expansion

> **Purpose:** Implementation specification for vexilloscope v3 Phase 2. Derived from `FOUNDATION_V3.md` and building on `SPEC_V3_PHASE1.md`. This document covers the first controlled source expansion only: US states + District of Columbia. Do not implement anything in a later phase from this document.

---

## 1. Purpose and Scope

Phase 2 is the first real test of the importer pipeline. It adds 51 new subnational results (50 US states + DC) to the manifest, sourcing SVG assets from Wikimedia Commons, and produces a working end-to-end path from import through QA to training export.

**Phase 2 delivers:**

- `scripts/import_us_states.py` — importer that queries Wikimedia Commons, downloads SVGs, and writes manifest records
- `scripts/render_assets.py` — renders reviewed SVG source assets to PNG for visual inspection and export
- `data/sources/wikimedia/us_states/` — committed SVG source assets (after reviewer accepts them)
- `reports/import/wikimedia/<timestamp>.json` — import report per run
- 51 new records in `data/manifest/results.jsonl`
- 51 new records in `data/manifest/flags.jsonl`
- 51 new records in `data/manifest/assets.jsonl` (SVG source_original per entry)
- New confusable entries in `data/manifest/confusables.jsonl` for the blue-seal flag group
- Updated `scripts/export_training.py` to handle SVG source originals at export time
- Updated `scripts/validate_manifest.py` to handle SVG integrity checks on trainable assets
- Updated `scripts/requirements.txt` with SVG rendering dependency
- Updated `.gitignore`

**Phase 2 does not touch:**

- C source files (`src/`)
- The C trainer invocation or argument convention
- The `--identify` stdout format
- The Discord bot
- Model architecture or hyperparameters
- Existing reviewed v2 records in the manifest
- Reclassification of existing v2 US territory entries (`pr`, `gu`, `vi`, `mp`, `as`, `um`) — those remain as migrated; reclassification is a separate curation pass

---

## 2. Foundation Decisions Summary

All decisions below are closed in `FOUNDATION_V3.md` and are not re-opened in this spec.

| Decision | Value |
|---|---|
| First expansion category | US states + DC; subnational; `parent_result_id=us` |
| Category value for expansion | `subnational` |
| Importers | Collectors only; cannot set `reviewed` or `trainable=true`; Phase 2 has no `--reviewed` shortcut |
| License handling | Do not assume state-government origin means public domain; extract from Wikimedia metadata; set `needs_license` if unclear |
| Source preference | SVG from Wikimedia Commons when available; generate PNG locally from SVG |
| SVG assets | Committed under `data/sources/` when reviewed; generated PNGs are reproducible artifacts under `data/generated/` |
| Import reports | `reports/import/<source>/<timestamp>.json`; local artifact, not committed |
| No silent overwrite | If a reviewed record already exists, importer must report conflict and exit non-zero rather than overwriting |
| Export gate | Unchanged from Phase 1: result+flag+asset all reviewed; flag+asset trainable=true; asset.asset_type=source_original |
| `trainable` default | `false` on all imported records |
| Training resolution | `128×128` baseline; no architecture changes in Phase 2 |

---

## 3. Repository Layout Changes

Phase 2 adds the following layout. Phase 1 files are unchanged unless noted.

```
vexilloscope/
  data/
    sources/                        # NEW: committed curated source assets
      wikimedia/
        us_states/
          us-al.svg                 # committed after review
          us-ak.svg
          ...                       # one SVG per state/DC
    generated/                      # GITIGNORED (unchanged)
      renders/
        wikimedia/
          us_states/                # NEW: gitignored PNG renders for review
            us-al.png
            ...
  reports/
    import/                         # NEW: gitignored import run reports
      wikimedia/
        <timestamp>.json
  scripts/
    import_us_states.py             # NEW
    render_assets.py                # NEW
    export_training.py              # UPDATED (SVG handling)
    requirements.txt                # UPDATED (cairosvg)
```

---

## 4. Class Scope: The 51 Entries

Phase 2 imports exactly the following 51 entries. No other entries are added in Phase 2.

| `result_id` | `display_name` | `territory_code` | Wikimedia Commons filename |
|---|---|---|---|
| `us-al` | Alabama | US-AL | `Flag_of_Alabama.svg` |
| `us-ak` | Alaska | US-AK | `Flag_of_Alaska.svg` |
| `us-az` | Arizona | US-AZ | `Flag_of_Arizona.svg` |
| `us-ar` | Arkansas | US-AR | `Flag_of_Arkansas.svg` |
| `us-ca` | California | US-CA | `Flag_of_California.svg` |
| `us-co` | Colorado | US-CO | `Flag_of_Colorado.svg` |
| `us-ct` | Connecticut | US-CT | `Flag_of_Connecticut.svg` |
| `us-de` | Delaware | US-DE | `Flag_of_Delaware.svg` |
| `us-fl` | Florida | US-FL | `Flag_of_Florida.svg` |
| `us-ga` | Georgia | US-GA | `Flag_of_Georgia_(U.S._state).svg` |
| `us-hi` | Hawaii | US-HI | `Flag_of_Hawaii.svg` |
| `us-id` | Idaho | US-ID | `Flag_of_Idaho.svg` |
| `us-il` | Illinois | US-IL | `Flag_of_Illinois.svg` |
| `us-in` | Indiana | US-IN | `Flag_of_Indiana.svg` |
| `us-ia` | Iowa | US-IA | `Flag_of_Iowa.svg` |
| `us-ks` | Kansas | US-KS | `Flag_of_Kansas.svg` |
| `us-ky` | Kentucky | US-KY | `Flag_of_Kentucky.svg` |
| `us-la` | Louisiana | US-LA | `Flag_of_Louisiana.svg` |
| `us-me` | Maine | US-ME | `Flag_of_Maine.svg` |
| `us-md` | Maryland | US-MD | `Flag_of_Maryland.svg` |
| `us-ma` | Massachusetts | US-MA | `Flag_of_Massachusetts.svg` |
| `us-mi` | Michigan | US-MI | `Flag_of_Michigan.svg` |
| `us-mn` | Minnesota | US-MN | `Flag_of_Minnesota.svg` |
| `us-ms` | Mississippi | US-MS | `Flag_of_Mississippi.svg` |
| `us-mo` | Missouri | US-MO | `Flag_of_Missouri.svg` |
| `us-mt` | Montana | US-MT | `Flag_of_Montana.svg` |
| `us-ne` | Nebraska | US-NE | `Flag_of_Nebraska.svg` |
| `us-nv` | Nevada | US-NV | `Flag_of_Nevada.svg` |
| `us-nh` | New Hampshire | US-NH | `Flag_of_New_Hampshire.svg` |
| `us-nj` | New Jersey | US-NJ | `Flag_of_New_Jersey.svg` |
| `us-nm` | New Mexico | US-NM | `Flag_of_New_Mexico.svg` |
| `us-ny` | New York | US-NY | `Flag_of_New_York.svg` |
| `us-nc` | North Carolina | US-NC | `Flag_of_North_Carolina.svg` |
| `us-nd` | North Dakota | US-ND | `Flag_of_North_Dakota.svg` |
| `us-oh` | Ohio | US-OH | `Flag_of_Ohio.svg` |
| `us-ok` | Oklahoma | US-OK | `Flag_of_Oklahoma.svg` |
| `us-or` | Oregon | US-OR | `Flag_of_Oregon.svg` |
| `us-pa` | Pennsylvania | US-PA | `Flag_of_Pennsylvania.svg` |
| `us-ri` | Rhode Island | US-RI | `Flag_of_Rhode_Island.svg` |
| `us-sc` | South Carolina | US-SC | `Flag_of_South_Carolina.svg` |
| `us-sd` | South Dakota | US-SD | `Flag_of_South_Dakota.svg` |
| `us-tn` | Tennessee | US-TN | `Flag_of_Tennessee.svg` |
| `us-tx` | Texas | US-TX | `Flag_of_Texas.svg` |
| `us-ut` | Utah | US-UT | `Flag_of_Utah.svg` |
| `us-vt` | Vermont | US-VT | `Flag_of_Vermont.svg` |
| `us-va` | Virginia | US-VA | `Flag_of_Virginia.svg` |
| `us-wa` | Washington | US-WA | `Flag_of_Washington_(state).svg` |
| `us-wv` | West Virginia | US-WV | `Flag_of_West_Virginia.svg` |
| `us-wi` | Wisconsin | US-WI | `Flag_of_Wisconsin.svg` |
| `us-wy` | Wyoming | US-WY | `Flag_of_Wyoming.svg` |
| `us-dc` | District of Columbia | US-DC | `Flag_of_the_District_of_Columbia.svg` |

The `us` result already exists in the manifest from Phase 1 migration. All 51 new entries have `parent_result_id=us`.

The Wikimedia Commons file titles in the rightmost column are the canonical filenames as they appear on Wikimedia Commons. These are the input to the `titles` parameter of the Wikimedia API query (prefixed with `File:`). If the canonical filename no longer resolves on Wikimedia (e.g., the file was renamed), the importer records the entry as `failed_fetch` in the import report; the maintainer resolves the discrepancy by updating the hardcoded table and re-running.

---

## 5. ID Conventions

| Record | ID format | Example |
|---|---|---|
| result | `us-<lc-2letter-code>` | `us-ca`, `us-dc` |
| flag | `<result_id>-current` | `us-ca-current`, `us-dc-current` |
| asset (SVG) | `<flag_id>-wikimedia-svg` | `us-ca-current-wikimedia-svg` |

No other asset ID patterns are created by the Phase 2 importer. Rendered PNG files produced by `render_assets.py` are not tracked as manifest assets and have no asset_id.

---

## 6. Manifest Record Defaults from Importer

The import script (`scripts/import_us_states.py`) applies the following defaults to all records it creates.

### `results.jsonl` defaults

| Field | Imported value |
|---|---|
| `result_id` | `us-<lc-code>` (from table in Section 4) |
| `display_name` | State or DC name (from table in Section 4) |
| `category` | `subnational` |
| `fictionality` | `nonfiction` |
| `status` | `current` |
| `short_description` | `"Current state flag of <display_name>, United States."` (generated placeholder) |
| `parent_result_id` | `us` |
| `territory_code` | ISO 3166-2 code (from table in Section 4) |
| `review_status` | `imported` |

### `flags.jsonl` defaults

| Field | Imported value |
|---|---|
| `flag_id` | `<result_id>-current` |
| `result_id` | `<result_id>` |
| `display_name` | `"<display_name> state flag"` (e.g., `"California state flag"`; DC: `"District of Columbia flag"`) |
| `variant` | `standard` |
| `status` | `current` |
| `review_status` | `imported` |
| `trainable` | `false` |

### `assets.jsonl` defaults (SVG source_original)

| Field | Imported value |
|---|---|
| `asset_id` | `<flag_id>-wikimedia-svg` |
| `flag_id` | `<flag_id>` |
| `asset_type` | `source_original` |
| `path` | `data/sources/wikimedia/us_states/<result_id>.svg` |
| `source_name` | `"Wikimedia Commons"` |
| `source_url` | Wikimedia Commons file page URL (e.g., `"https://commons.wikimedia.org/wiki/File:Flag_of_California.svg"`) |
| `license` | Extracted from Wikimedia metadata if recognized (see Section 7); omitted if unclear |
| `review_status` | `imported` if license extracted; `needs_license` if license absent or unrecognized |
| `trainable` | `false` |

The `source_url` is always the Wikimedia Commons file page URL, not the direct download URL. This is the provenance record. The importer logs the direct download URL in the import report but does not store it in the manifest.

---

## 7. Source Policy

### 7.1 Wikimedia Commons SVG Sourcing

The importer queries the Wikimedia Commons API to resolve file URLs and license metadata.

**API endpoint:**

```
https://commons.wikimedia.org/w/api.php
  ?action=query
  &titles=File:<wikimedia_filename>
  &prop=imageinfo
  &iiprop=url|extmetadata
  &iiextmetadatafilter=LicenseShortName|Artist|Credit
  &format=json
```

The importer uses the `imageinfo.url` field as the direct SVG download URL. The `source_url` stored in the manifest is always the file page URL (`https://commons.wikimedia.org/wiki/File:<wikimedia_filename>`), not the direct download URL. The `Artist` and `Credit` fields are included in the query for future import report provenance use; Phase 2 does not store them in the manifest.

**Rate limiting:** The importer pauses 0.5 seconds between requests to Wikimedia Commons (more conservative than `fetch_wiki_flags.py`'s 0.15s, since SVG files are larger and Wikimedia Commons enforces rate limits on the API endpoint).

**User-Agent:** The importer must set a descriptive `User-Agent` header as required by Wikimedia Commons API policy (e.g., `"vexilloscope-importer/1.0 (https://github.com/...); python-requests/2.x"`).

### 7.2 License Extraction Policy

The importer extracts license metadata from `extmetadata.LicenseShortName.value` and maps it to a v3 license identifier using the following table. `LicenseShortName` is Wikimedia's normalized human-readable string (not the raw template key); empirically, all PD-variant templates (`PD-ineligible`, `PD-USGov`, `PD-art`, etc.) resolve to the literal `"Public domain"` via this field.

| Wikimedia `LicenseShortName` | v3 `license` value |
|---|---|
| `Public domain` | `"public-domain"` |
| `CC0` | `"cc0"` |
| `CC BY 4.0` | `"cc-by-4.0"` |
| `CC BY-SA 4.0` | `"cc-by-sa-4.0"` |
| `CC BY-SA 3.0` | `"cc-by-sa-3.0"` |
| Anything else or absent | Omit `license`; set `review_status=needs_license` |

**The US federal public-domain rule does not apply to state governments.** Do not assume `public-domain` for any state flag unless Wikimedia's extmetadata explicitly identifies it as such. If Wikimedia's `LicenseShortName` is `Public domain`, accept it; if absent or unrecognized, always land as `needs_license`.

The reviewer is responsible for confirming each license value is accurate before approving a record. A license extracted from Wikimedia metadata is still a human-review item, not a guarantee.

### 7.3 SVG Source Asset Commit Policy

Downloaded SVGs are saved to `data/sources/wikimedia/us_states/<result_id>.svg` at import time. These files are tracked in git once a reviewer accepts the record (`review_status=reviewed`).

SVG source files for US state flags are typically small (10–300 KB). Committing them is acceptable under the foundation's policy for small reviewed source assets.

The gitignore update for Phase 2 does not add `data/sources/` to the ignore list. Files under `data/sources/` that arrive via import but are not yet reviewed should not be committed until reviewed; this is a workflow expectation, not enforced by gitignore.

---

## 8. SVG Rendering Policy

### 8.1 Purpose

Rendering SVG source assets to PNG serves two distinct purposes in Phase 2:

1. **Review preview:** Allow the reviewer to visually inspect each flag before approving it.
2. **Training export:** Produce a PNG for the C trainer when exporting.

### 8.2 Toolchain

Phase 2 adds `cairosvg>=2.5` to `scripts/requirements.txt` for SVG-to-PNG rendering.

`cairosvg` requires the Cairo library to be installed on the system. On Windows, this is available via the GTK3 runtime (`gtk3-runtime-<version>-win64.exe`). On Linux/macOS, Cairo is available via the system package manager.

There is no fallback SVG renderer specified in Phase 2. If `cairosvg` is unavailable, the scripts that depend on it (`render_assets.py` and the updated `export_training.py`) will fail with an ImportError and a clear message.

Updated `scripts/requirements.txt`:

```
requests>=2.28.0
Pillow>=9.0
imagehash>=4.3
cairosvg>=2.5
```

### 8.3 Render Paths and Resolution

`render_assets.py` renders SVGs to `data/generated/renders/wikimedia/us_states/<result_id>.png`. These files are gitignored.

Render resolution: **512×512** pixels with white background compositing. This is higher than the current 128×128 training target so future resolution experiments (160, 192, 256) can use the same rendered source without re-fetching.

Aspect ratio handling: render with aspect-preserving resize within a 512×512 canvas; pad with white to fill. The flag is centered within the canvas.

### 8.4 Source/Render File Pattern

Phase 2 creates one manifest asset record per flag (the SVG source_original) alongside one untracked render file:

| Step | Asset type | Path | Created by | Tracked in manifest |
|---|---|---|---|---|
| Import | `source_original` (SVG) | `data/sources/wikimedia/us_states/<result_id>.svg` | `import_us_states.py` | Yes |
| Render | — | `data/generated/renders/wikimedia/us_states/<result_id>.png` | `render_assets.py` | No |

The rendered PNG is a preview artifact. It is not tracked as a manifest asset record. The export script renders SVGs on the fly at export time (see Section 9) and does not depend on the `data/generated/renders/` tree being present.

The `source_render` asset type is reserved for a future pass where PNG renders from multiple source families need independent tracking (e.g., if a second PNG source is imported alongside the Wikimedia SVG for the same flag). Phase 2 does not use `source_render` asset records.

---

## 9. Export Contract Update

### 9.1 SVG Handling in `export_training.py`

The Phase 1 export script assumed all `source_original` assets are PNGs and copied them directly into `data/generated/train/images/`. Phase 2 extends this to handle SVG source originals.

**Updated export behavior for primary asset copy:**

```
if asset.path ends with ".svg":
    render to PNG using cairosvg at 512x512 (aspect-preserving resize within 512×512 canvas,
        white padding, centered — identical to render_assets.py behavior)
    resize to 128x128 using Pillow (LANCZOS, white background)
    write to data/generated/train/images/<flag_id>.png
else:
    copy as before
```

This logic is confined to the export copy step. No other export contract changes.

> **Note on Phase 1 compatibility:** Phase 1 Section 9.4 states "the export script does not resize" — that rule applies to PNG `source_original` assets, which the C trainer resizes at load time. SVG assets cannot be passed directly to the C trainer; they must be rasterized first. The 512×512 → 128×128 resize in the SVG branch is the necessary rasterization step, not a change to the PNG-asset behavior. The C trainer will still resize the resulting 128×128 PNG to its fixed target size at load (a no-op at matching resolution).

The export script must import `cairosvg` at the top of the file and exit with a clear error message if Cairo is unavailable.

### 9.2 Backward Compatibility

All Phase 1 records use PNG `source_original` assets. The updated export script must continue to handle these identically. The SVG branch is additive.

### 9.3 Validator Contract Updates

#### `flag_one_trainable_asset` warning refinement

The Phase 1 validator emits `flag_one_trainable_asset` whenever a trainable flag has exactly one trainable asset. This fires for all 255 Phase 1 flags (secondary wiki/emoji assets exist but are `trainable=false`) and would fire for all 51 Phase 2 flags (no secondary sources exist at all). The two cases are meaningfully different: Phase 1 flags have promotable secondaries; Phase 2 flags do not.

**Updated behaviour:** `flag_one_trainable_asset` fires only when the flag has exactly one trainable asset AND at least one non-trainable asset in the manifest. This makes the warning actionable — it means "you have sources you could promote" — and suppresses it for Phase 2 flags that simply have no secondary sources yet.

#### SVG integrity checks

The Phase 1 validator checks image integrity on all trainable assets using Pillow (`trainable_asset_unreadable`, `trainable_asset_zero_dimensions`). Pillow cannot decode SVG files. Without this update, promoting a Phase 2 SVG asset to `trainable=true` would cause the validator to emit `trainable_asset_unreadable`.

**Updated integrity check behavior in `validate_manifest.py`:**

```
if asset.path ends with ".svg" and asset.trainable is true:
    render to PNG using cairosvg in-memory (no file written)
    check dimensions using Pillow on the in-memory bytes
    if render fails → trainable_asset_unreadable (blocker)
    if dimensions are 0×0 → trainable_asset_zero_dimensions (blocker)
else:
    apply existing Pillow-based integrity check as before
```

The validator imports `cairosvg` lazily — only when an SVG trainable asset is encountered — so that installations without Cairo are not broken by the presence of SVGs with `trainable=false`.

If `cairosvg` is unavailable when an SVG trainable asset is encountered, the validator emits `trainable_asset_unreadable` with a message directing the user to install `cairosvg>=2.5`.

---

## 10. Script Contracts

### `scripts/import_us_states.py`

```
python scripts/import_us_states.py [--dry-run] [--state <result_id>]
```

- Contains a hardcoded lookup table mapping each `result_id` to the record in Section 4 (display name, territory code, Wikimedia filename).
- For each entry, queries the Wikimedia Commons API for the SVG URL and license metadata.
- Downloads the SVG to `data/sources/wikimedia/us_states/<result_id>.svg`.
- Creates or updates records in `data/manifest/results.jsonl`, `flags.jsonl`, `assets.jsonl` using the defaults from Section 6.
- **Protected mutation:** If a record already exists at `reviewed`, does not overwrite it. Reports the conflict to stdout and records it in the import report as `skipped_existing_reviewed`. The script continues processing the remaining entries rather than aborting; it exits non-zero after all entries have been processed if any protected conflict occurred during the run.
- **Idempotent import:** If a record already exists at `imported`, or if the corresponding asset record is at `needs_license`, the script re-fetches metadata and updates the record if no conflict exists (e.g., license can now be resolved). Does not re-download the SVG if it already exists on disk. `--force-download` is not implemented in Phase 2; if the user passes it, the script must recognize it as a known-but-unsupported argument and exit non-zero with a clear message (e.g., `"--force-download is not implemented in Phase 2"`), not a generic argparse error.
- `--dry-run`: prints what would be written and fetched without writing anything or downloading files.
- `--state <result_id>`: imports only the specified state (e.g., `--state us-ca`). Useful for testing and per-state review cycles.
- Writes an import report to `reports/import/wikimedia/<ISO8601-timestamp>.json` (see Section 11).
- Prints a summary to stdout: records created, updated, skipped, and failed.
- Sets `review_status=imported` on all created records. Never sets `reviewed`.
- Sets `trainable=false` on all created records.

### `scripts/render_assets.py`

```
python scripts/render_assets.py [--source-dir data/sources/wikimedia/us_states] [--output-dir data/generated/renders/wikimedia/us_states] [--all]
```

- Reads `data/sources/wikimedia/us_states/*.svg` by default.
- Renders each SVG to PNG at 512×512 (white background, aspect-preserving with padding) using `cairosvg`.
- Writes rendered PNGs to `--output-dir`.
- By default, skips SVGs whose corresponding asset record in `assets.jsonl` is not `review_status=imported` or `reviewed` (i.e., skips `needs_*`, `rejected`). Pass `--all` to render regardless of review status.
- Does not modify the manifest.
- Prints per-file status (rendered, skipped, failed).
- Exits non-zero if any render fails.

### Updated `scripts/export_training.py`

Changes from Phase 1:

- Imports `cairosvg` at top. If import fails, exits with: `"ERROR: cairosvg is required for SVG export. Install it with: pip install cairosvg>=2.5"`.
- In the primary asset copy step: if `asset.path` ends with `.svg`, renders to PNG in-memory using cairosvg, resizes to 128×128 with Pillow (LANCZOS, white background), writes as PNG. Otherwise, copies as before.
- No other changes to export logic, file structure, or report format.

---

## 11. Import Report Contract

Phase 2 introduces the first import report, filling in the contract described in the foundation's Source Import Strategy section.

### Location

```
reports/import/wikimedia/<ISO8601-timestamp>.json
```

Example: `reports/import/wikimedia/2026-05-19T143000.json`

Reports are not committed (added to gitignore).

### JSON Schema

```json
{
  "version": 1,
  "generated_at": "<ISO 8601 timestamp>",
  "importer": "import_us_states",
  "source_family": "wikimedia",
  "summary": {
    "total": 51,
    "imported": 0,
    "needs_license": 0,
    "needs_review": 0,
    "needs_disambiguation": 0,
    "rejected": 0,
    "skipped_existing_reviewed": 0,
    "failed_fetch": 0,
    "failed_parse": 0,
    "failed_license_parse": 0,
    "failed_image_decode": 0,
    "failed_validation": 0,
    "failed_write": 0
  },
  "records": [
    {
      "result_id": "us-ca",
      "flag_id": "us-ca-current",
      "asset_id": "us-ca-current-wikimedia-svg",
      "outcome": "imported",
      "license_extracted": "public-domain",
      "source_url": "https://commons.wikimedia.org/wiki/File:Flag_of_California.svg",
      "svg_path": "data/sources/wikimedia/us_states/us-ca.svg",
      "notes": null
    }
  ],
  "failures": [
    {
      "target_result_id": "us-xx",
      "wikimedia_filename": "Flag_of_X.svg",
      "phase": "failed_fetch",
      "source_url": "https://commons.wikimedia.org/wiki/File:Flag_of_X.svg",
      "error": "HTTP 404: Not Found",
      "notes": "Wikimedia filename may have changed; check file page manually."
    }
  ]
}
```

#### `summary` fields

All counts are required. A count of zero is valid. `total` is the number of states targeted by the current invocation: 51 for a full run, 1 when `--state` is passed. `summary` counts apply to the current run, not to prior runs. `needs_review`, `needs_disambiguation`, and `rejected` are included for schema consistency with the general import framework; the US states importer is not expected to produce non-zero counts for these in normal operation.

#### `records` fields

| Field | Required | Description |
|---|---|---|
| `result_id` | yes | The result_id for this entry. |
| `flag_id` | yes | The flag_id created or updated. |
| `asset_id` | yes | The SVG asset_id created or updated. |
| `outcome` | yes | One of: `imported`, `needs_license`, `needs_review`, `needs_disambiguation`, `rejected`, `skipped_existing_reviewed`. |
| `license_extracted` | no | The v3 license value extracted from Wikimedia metadata, if any. |
| `source_url` | yes | The Wikimedia file page URL. |
| `svg_path` | yes | The local path where the SVG was saved. |
| `notes` | no | Maintainer-facing note for this record. |

#### `failures` fields

| Field | Required | Description |
|---|---|---|
| `target_result_id` | yes | The result_id that was being processed. |
| `wikimedia_filename` | yes | The Wikimedia Commons filename that was queried. |
| `phase` | yes | Which phase failed: `failed_fetch`, `failed_parse`, `failed_license_parse`, `failed_image_decode`, `failed_validation`, `failed_write`. |
| `source_url` | yes | The URL being accessed when the failure occurred. |
| `error` | yes | Concrete error message. |
| `notes` | no | Suggested fix or investigation hint. |

---

## 12. Confusables Additions

Many US state flags share a common design template: dark blue background with the state seal centered. At 128×128, the seal text and fine detail are unreadable, making these flags difficult to distinguish by visual features alone.

Phase 2 adds two confusable records to `data/manifest/confusables.jsonl`: one for the blue-seal group and one for a cross-category pair that are nonetheless visually similar at training resolution.

### Blue-Seal Group

```jsonl
{"confusable_id": "us-states-blue-seal", "level": "flag", "members": ["us-id-current", "us-ks-current", "us-ky-current", "us-me-current", "us-ma-current", "us-mi-current", "us-mt-current", "us-ne-current", "us-nh-current", "us-ny-current", "us-nd-current", "us-or-current", "us-pa-current", "us-sd-current", "us-ut-current", "us-vt-current", "us-va-current", "us-wi-current"], "reason": "Dark blue background with centered dark state seal; seal colors blend into the field making flags indistinguishable at 128px training resolution.", "source": "manual", "review_status": "reviewed"}
```

> **Note:** Minnesota (`us-mn`) is excluded. Minnesota's 2024 redesign replaced the blue-seal design with a gold North Star and loon motif on a half-blue, half-green field — it is not a blue-seal flag.
>
> **Note:** Connecticut (`us-ct`) is excluded. Connecticut's seal is predominantly white/light on a white shield, creating a high-contrast light center element on the blue field. At 128px this reads as a distinct visual archetype (light blob on dark) rather than blending into the field like the dark-seal members of this group.

These entries are added manually as part of the Phase 2 review work, after the importer has created the flag records (so the referenced `flag_id`s exist). They follow the same pattern as the Phase 1 seed confusables: human-authored, pre-approved vexillological knowledge committed alongside the manifest updates. They are not written by `import_us_states.py`. See Section 13 for the review workflow step that adds them.

### Oregon/Indiana Near-Match

Oregon (blue field with state seal) and Indiana (blue field with torch) share a blue background with prominent gold lettering and are among the more visually similar pairs across different emblem styles:

```jsonl
{"confusable_id": "us-or-in", "level": "flag", "members": ["us-or-current", "us-in-current"], "reason": "Similar dark blue background with state name in gold/yellow lettering.", "source": "manual", "review_status": "reviewed"}
```

Additional confusable groups may be added during the review phase as the reviewer inspects the imported flags. These two entries define the minimum Phase 2 confusables contribution.

Both entries carry `"review_status": "reviewed"` and `"source": "manual"` — they are pre-approved vexillological knowledge, not imported records, and do not go through the `imported → reviewed` promotion cycle. They must be added after the importer has run (so the referenced `flag_id`s exist in `flags.jsonl`) but before the first training export. See Section 13, step 5.

---

## 13. Review Workflow

Phase 2 has no `--reviewed` shortcut. All 51 records land as `imported`. Promotion to `reviewed + trainable=true` requires human action on each record.

**Expected review steps after a successful import run:**

1. Run the importer:
   ```powershell
   python scripts/import_us_states.py
   ```

2. Check the import report in `reports/import/wikimedia/<timestamp>.json`. Verify counts, note any `needs_license` or failed entries.

3. Run the validator. Expect 0 blockers (imported records are not subject to export-gate blockers unless structurally invalid):
   ```powershell
   python scripts/validate_manifest.py
   ```

4. Run the renderer to produce visual previews:
   ```powershell
   python scripts/render_assets.py
   ```
   Preview PNGs appear in `data/generated/renders/wikimedia/us_states/`. Pass `--all` to also render `needs_license` entries (skipped by default); recommended if any states landed as `needs_license`.

5. Add the Phase 2 seed confusable entries to `data/manifest/confusables.jsonl`. Copy the two `jsonl` lines verbatim from Section 12 and append them to the file. These are pre-approved (`review_status=reviewed`) and require no further review. Can be done any time after the importer has run and before the first training export. Run the validator immediately after to confirm no `confusable_missing_member` errors:
   ```powershell
   python scripts/validate_manifest.py
   ```

6. For each flag the reviewer accepts:
   - Edit `data/manifest/results.jsonl`: set `review_status=reviewed`; update `short_description` with a meaningful one-sentence description (the placeholder is acceptable for training but not preferred for reviewed records).
   - Edit `data/manifest/flags.jsonl`: set `review_status=reviewed` and `trainable=true`.
   - Edit `data/manifest/assets.jsonl` (SVG asset): set `review_status=reviewed` and `trainable=true`; confirm `license` is correct.
   - For `needs_license` entries: confirm the correct license value (typically by visiting the Wikimedia Commons file page), add the `license` field, then set `review_status=reviewed`.

7. Re-run the validator. Expect 0 blockers for accepted records:
   ```powershell
   python scripts/validate_manifest.py
   ```

8. Run the export to confirm Phase 2 classes are included:
   ```powershell
   python scripts/export_training.py
   ```
   The export count should be 255 (Phase 1 classes) plus the number of Phase 2 states the reviewer accepted.

9. Commit accepted SVG source files and manifest updates:
   ```
   data/sources/wikimedia/us_states/us-ca.svg   (and others accepted)
   data/manifest/results.jsonl
   data/manifest/flags.jsonl
   data/manifest/assets.jsonl
   data/manifest/confusables.jsonl
   ```

**Batch review is acceptable.** A reviewer may accept all 51 entries in one pass if the import succeeded cleanly and the rendered PNGs look correct. Each record must still be explicitly set to `reviewed`; there is no batch acceptance command.

**Partial review is acceptable.** The manifest is valid and exportable as long as reviewed records satisfy all export-gate conditions. States with `needs_license` or unreviewed status simply do not appear in the export until reviewed.

---

## 14. Gitignore Updates

Add the following to `.gitignore`:

```
reports/import/
```

`data/generated/renders/` is already covered by the `data/generated/` entry added in Phase 1 and does not need a separate entry.

`data/sources/` is intentionally NOT gitignored. Reviewed SVG source assets under this path should be committed.

---

## 15. Phase 2 Verification Checklist

All items must pass before Phase 2 is declared complete.

**Import:**

- [ ] `python scripts/import_us_states.py` completes without exit code 1 on a clean run.
- [ ] `reports/import/wikimedia/<timestamp>.json` is written and parseable.
- [ ] The import report `summary.total` is 51.
- [ ] `data/sources/wikimedia/us_states/` exists with SVG files for all successfully imported states.
- [ ] 51 new entries in `data/manifest/results.jsonl`, all with `category=subnational`, `parent_result_id=us`, `review_status=imported`.
- [ ] 51 new entries in `data/manifest/flags.jsonl`, all with `trainable=false`, `review_status=imported`.
- [ ] 51 new `source_original` SVG entries in `data/manifest/assets.jsonl`, all with `trainable=false`.

**QA:**

- [ ] `python scripts/validate_manifest.py` exits 0 (no blockers) after import.
- [ ] `reports/qa/latest.json` is updated and parseable.
- [ ] `reports/qa/latest.json summary.results_total` is 306 (255 Phase 1 + 51 Phase 2).

**Rendering:**

- [ ] `python scripts/render_assets.py` runs without error.
- [ ] `data/generated/renders/wikimedia/us_states/` contains at least one rendered PNG.
- [ ] A reviewer visually inspects at least one rendered flag and confirms it is correct.

**End-to-end review smoke test (≥ 1 state):**

- [ ] At least one Phase 2 state is manually promoted to `review_status=reviewed` + `trainable=true` across all three manifest layers (result, flag, asset).
- [ ] `python scripts/validate_manifest.py` exits 0 after this review step.
- [ ] `python scripts/export_training.py` exits 0.
- [ ] `data/generated/train/labels.csv` contains at least 256 rows (255 + 1 accepted state + header).
- [ ] `data/generated/train/class_map.json` has `n_classes` ≥ 256.
- [ ] `data/generated/train/images/<state-flag-id>.png` exists and is a valid 128×128 PNG.
- [ ] `.\build\Release\vexilloscope.exe --identify data/generated/train/images/<state-flag-id>.png` completes without error (confirms the SVG→PNG export produces a file the C binary can decode).

**Confusables:**

- [ ] `data/manifest/confusables.jsonl` contains the `us-states-blue-seal` and `us-or-in` entries from Section 12.
- [ ] `python scripts/validate_manifest.py` shows no `confusable_missing_member` warnings for these entries.

**Gitignore:**

- [ ] `reports/import/` is in `.gitignore`.
- [ ] `data/generated/` is in `.gitignore` (covers `data/generated/renders/`; added in Phase 1).
- [ ] `data/sources/` is NOT in `.gitignore`.

**No regressions:**

- [ ] `python scripts/validate_manifest.py` reports the same number of blockers and warnings for Phase 1 records as before (0 blockers).
- [ ] The Phase 1 export produces at least 255 classes from the Phase 1 records.

---

## 16. Explicit Non-Goals

The following are explicitly out of scope for Phase 2.

- **Historical flag import** — deferred to Phase 3
- **Fictional, pride, cultural, sports, military, maritime expansion** — deferred
- **Model architecture changes** — no C source changes in Phase 2
- **`--identify-json` implementation** — deferred to Phase 4
- **Negative eval generation** — deferred
- **256×256 or other resolution experiments** — deferred
- **Bot presentation changes** — deferred
- **Category-aware augmentation** — deferred
- **Reclassification of existing v2 US territory entries** (`pr`, `gu`, `vi`, `mp`, `as`, `um`) to `subnational` — separate curation pass, not Phase 2
- **Import of DC statehood flag, historical DC flags, or alternate designs** — Phase 2 imports exactly one flag per entry per Section 4
- **Non-Wikimedia sources for US state flags** — Wikimedia Commons SVGs are the sole source in Phase 2; secondary source imports (e.g., official state SVGs) are a future curation pass
- **`--reviewed` shortcut for the Phase 2 importer** — importers are collectors; all promotion to `reviewed` is a manual reviewer step
- **Automated license approval** — license values extracted from Wikimedia metadata are still subject to human review
- **`--force` overwrite of reviewed records** — not implemented; importer exits non-zero on protected conflict
- **SQLite manifest** — JSONL remains canonical
- **Direct JSONL parsing in the C binary** — C consumes generated CSV; JSONL stays in Python tooling
- **US state civil/military/alternate flag variants** — Phase 2 imports only the standard flag per state; variant imports are a future expansion
- **Municipal or county flag imports** — deferred
- **Canadian provinces, Mexican states, or other subnational families** — US states/DC is the complete Phase 2 scope
