# vexilloscope v3 Phase 1 Specification

> **Purpose:** Implementation specification for vexilloscope v3 Phase 1. Derived from `FOUNDATION_V3.md`. This document covers the dataset backbone only. Do not implement anything in a later phase from this document.

---

## 1. Purpose and Scope

Phase 1 establishes the v3 manifest backbone and migrates the existing v2 dataset into it. The output is a reviewable, exportable JSONL manifest plus a working training export pipeline compatible with the existing C trainer.

**Phase 1 delivers:**

- `data/manifest/results.jsonl` — result metadata records
- `data/manifest/flags.jsonl` — exact visual flag identity records
- `data/manifest/assets.jsonl` — concrete source/render asset records
- `data/manifest/confusables.jsonl` — reviewed visual similarity/identity relationships
- `scripts/migrate_v2.py` — migrates `data/labels.csv` and `data/flags/` into the manifest
- `scripts/validate_manifest.py` — validates manifest integrity and produces QA reports
- `scripts/export_training.py` — exports `data/generated/train/` from reviewed+trainable records
- `data/generated/train/labels.csv` — training labels for the C trainer
- `data/generated/train/class_map.json` — class-to-manifest mapping for inference and eval
- `data/generated/train/images/` — training images (copies or symlinks from reviewed assets)
- `reports/qa/latest.json` and `reports/qa/latest.md` — QA reports

**Phase 1 does not touch:**

- C source files (`src/`)
- The C trainer invocation or argument convention
- The `--identify` stdout format
- The Discord bot
- Model architecture or hyperparameters
- US states/DC import, historical flags, fictional/pride/cultural expansion

---

## 2. Foundation Decisions Summary

All decisions below are closed in `FOUNDATION_V3.md` and are not re-opened in this spec.

| Decision | Value |
|---|---|
| Manifest format | JSONL; CSV and JSON are generated outputs only |
| Record model | Three separate JSONL files: results, flags, assets; confusables in a fourth file |
| Identifiers | `result_id`, `flag_id`, `asset_id` — stable, human-readable, lowercase-hyphenated |
| Category values | `national`, `subnational`, `military`, `maritime`, `organization`, `cultural`, `pride`, `sports`, `other` |
| `historical` handling | `status=historical`, not a category |
| Fictionality | Separate required field: `nonfiction` or `fictional` |
| Status values | `current`, `historical`, `proposed`, `unofficial`, `disputed`, `deprecated` |
| Variant values | `standard`, `civil`, `state`, `military`, `royal`, `presidential`, `organizational`, `alternate`, `reconstruction`, `ceremonial` |
| Asset type values | `source_original`, `source_render`, `emoji_render`, `reference_only` |
| Review status values | `imported`, `needs_review`, `needs_source`, `needs_license`, `needs_disambiguation`, `reviewed`, `rejected` |
| Export gate | All three of result, flag, asset must be `reviewed`; flag and asset must be `trainable=true` |
| `trainable` default | `false` on both flags and assets unless explicitly set |
| Importers | Collectors, not trust authorities; cannot set `reviewed` or `trainable=true` except for the explicit Phase 1 `migrate_v2.py --reviewed` path for the established v2 primary set |
| Generated artifacts | Live under `data/generated/`; ignored by default |
| QA artifacts | Live under `reports/qa/` |
| Confusables registry | `data/manifest/confusables.jsonl` |
| Training resolution | `128×128` baseline; no architecture changes in Phase 1 |
| Negative examples | Not in `assets.jsonl`; not a Phase 1 concern |
| Source preference | SVG from Wikimedia Commons when available; generate PNG locally |

---

## 3. Repository Layout

Phase 1 adds the following layout. Existing files are unchanged.

```
vexilloscope/
  data/
    labels.csv                    # v2 source of truth (read-only during migration)
    flags/                        # v2 primary source images (read-only)
    flags_wiki/                   # v2 wiki renders (generated, read-only)
    flags_emoji/                  # v2 emoji renders (generated, read-only)
    manifest/
      results.jsonl               # result metadata records
      flags.jsonl                 # exact visual flag identity records
      assets.jsonl                # concrete source/render asset records
      confusables.jsonl           # reviewed visual similarity/identity relationships
    generated/                    # GITIGNORED by default
      train/
        labels.csv                # C-trainer-compatible training labels
        class_map.json            # class_id -> flag_id -> result_id -> display_name
        images/                   # one PNG per trainable flag class
        images_wiki/              # optional secondary source_render images
        images_emoji/             # optional tertiary emoji_render images
  reports/
    qa/
      latest.json                 # machine-readable QA report
      latest.md                   # human-readable QA report
      archive/                    # timestamped prior reports (optional)
  scripts/
    migrate_v2.py                 # v2 -> manifest migration
    validate_manifest.py          # manifest validation + QA report generator
    export_training.py            # manifest -> data/generated/train/
    fetch_wiki_flags.py           # existing (unchanged)
    fetch_twemoji_flags.py        # existing (unchanged)
    requirements.txt              # Python deps for scripts
```

---

## 4. JSONL Schemas

All JSONL files follow the convention: one JSON object per line, UTF-8, LF line endings. Blank lines are forbidden. Lines beginning with `//` or `#` are forbidden (no comments in JSONL).

### 4.1 `results.jsonl`

Each line defines a metadata subject returned as a ranked result by the system.

#### Required fields

| Field | Type | Description |
|---|---|---|
| `result_id` | string | Stable internal correlation ID. Lowercase-hyphenated. Examples: `ad`, `us-ca`, `lotr-gondor`. |
| `display_name` | string | Primary human-facing name. |
| `category` | enum | See allowed values. |
| `fictionality` | enum | `nonfiction` or `fictional`. Required on all result records. |
| `status` | enum | See allowed values. |
| `short_description` | string | One-sentence human-facing context. Required when `review_status=reviewed`. |
| `review_status` | enum | See allowed values. |

#### Optional fields

| Field | Type | Description |
|---|---|---|
| `parent_result_id` | string | Parent result ID (e.g., `us` for `us-ca`). |
| `territory_code` | string | ISO 3166 or local administrative code when one exists. |
| `aliases` | array of string | Alternate names and search terms. |
| `era_start` | string | Year or ISO date string (inclusive). Useful for historical results. |
| `era_end` | string | Year or ISO date string (inclusive). `null` means ongoing. |
| `trivia` | array of object | Optional typed human-interest notes. Each object must have `type` (string) and `text` (string). |
| `links` | array of object | Reference links. Each object must have `label` (string) and `url` (string). |
| `category_data` | object | Category-specific structured metadata (free-form nested object). |
| `notes` | string | Maintainer-facing caveats. Not user-facing. |

> **Conditional requirement:** `short_description` appears in the required fields table because it must be present for a result record to be accepted as reviewed, but it is conditionally required: only when `review_status=reviewed`. Records in `imported` or `needs_*` states may omit it. Validators must not fire `missing_required_field` for an absent `short_description`; they must use `reviewed_result_missing_description` (Section 7.1) when the record is reviewed.

#### Example

```json
{"result_id": "ad", "display_name": "Andorra", "category": "national", "fictionality": "nonfiction", "status": "current", "short_description": "Current national flag of Andorra.", "review_status": "reviewed"}
```

---

### 4.2 `flags.jsonl`

Each line defines one exact visual flag identity that can be trained, evaluated, and mapped to a result.

#### Required fields

| Field | Type | Description |
|---|---|---|
| `flag_id` | string | Stable ID for the exact visual identity. Lowercase-hyphenated. Must not collide within `flags.jsonl`. |
| `result_id` | string | Must match a `result_id` in `results.jsonl`. |
| `display_name` | string | Maintainer-friendly label for the visual identity. |
| `variant` | enum | See allowed values. |
| `status` | enum | See allowed values. |
| `review_status` | enum | See allowed values. |
| `trainable` | boolean | Whether this visual identity may be exported as a model class. Defaults `false`. |

#### Optional fields

| Field | Type | Description |
|---|---|---|
| `era_start` | string | Year or ISO date. Useful when a result has multiple historical visual identities. |
| `era_end` | string | Year or ISO date. `null` means ongoing. |
| `aspect_ratio` | string | Canonical ratio string (e.g., `"2:3"`, `"1:2"`). |
| `visual_notes` | string | Maintainer-facing visual description. |
| `evaluation_group` | string | Optional grouping key for category-level evaluation metrics. |
| `variant_data` | object | Structured fine-grained variant detail (e.g., `{"military_use": "naval_ensign"}`). |
| `notes` | string | Maintainer-facing caveats. |

#### Example

```json
{"flag_id": "ad-current", "result_id": "ad", "display_name": "Andorra current flag", "variant": "standard", "status": "current", "review_status": "reviewed", "trainable": true}
```

---

### 4.3 `assets.jsonl`

Each line defines a concrete image asset associated with a flag. `assets.jsonl` tracks only positive flag assets tied to a `flag_id`. Generated augmentation samples and negative examples are outside this manifest.

#### Required fields

| Field | Type | Description |
|---|---|---|
| `asset_id` | string | Stable ID for this concrete image. Lowercase-hyphenated. Must not collide within `assets.jsonl`. |
| `flag_id` | string | Must match a `flag_id` in `flags.jsonl`. |
| `asset_type` | enum | See allowed values. |
| `path` | string | Local path to the image file, relative to repo root. |
| `source_name` | string | Human-readable source name (e.g., `"hampusborgos/country-flags"`, `"Wikimedia Commons"`, `"Twemoji"`). |
| `source_url` | string | Provenance URL. Where the asset came from; not necessarily a direct download URL. Required for all `reviewed` assets. |
| `license` | string | License identifier (e.g., `"public-domain"`, `"cc-by-4.0"`, `"cc0"`). Required for all `trainable=true` assets. |
| `review_status` | enum | See allowed values. |
| `trainable` | boolean | Whether this asset may contribute training samples. Defaults `false`. |

> **Conditional requirements:** `source_url` and `license` appear in the required fields table because they must be present for a record to be accepted for use, but they are conditionally required: `source_url` is required when `review_status=reviewed`; `license` is required when `trainable=true`. Records in `imported` or `needs_*` states may omit these fields until resolved. Validators must not report generic `missing_required_field` for omitted conditional fields; they must use the specific conditional blocker codes in Section 7.1.

#### Optional fields

| Field | Type | Description |
|---|---|---|
| `width` | integer | Source image width in pixels. |
| `height` | integer | Source image height in pixels. |
| `sha256` | string | Hex SHA-256 of the image file. Used for duplicate detection. |
| `render_style` | string | Free-form render style descriptor (e.g., `"flat-svg"`, `"emoji"`, `"photo"`). |
| `generated_from_asset_id` | string | Lineage reference when this asset was generated from another. |
| `generator` | string | Script or policy name that produced this asset. |
| `notes` | string | Maintainer-facing caveats. |

#### Example

```json
{"asset_id": "ad-current-primary", "flag_id": "ad-current", "asset_type": "source_original", "path": "data/flags/ad.png", "source_name": "hampusborgos/country-flags", "source_url": "https://github.com/hampusborgos/country-flags", "license": "public-domain", "review_status": "reviewed", "trainable": true}
```

---

### 4.4 `confusables.jsonl`

Each line defines a reviewed visual similarity or identity relationship between flags or results.

#### Required fields

| Field | Type | Description |
|---|---|---|
| `confusable_id` | string | Stable ID for this confusable group. Lowercase-hyphenated. |
| `level` | enum | `"flag"` or `"result"`. Whether members are `flag_id`s or `result_id`s. |
| `members` | array of string | Two or more IDs (matching `level`). Must reference existing records. |
| `reason` | string | Human-readable explanation (e.g., `"near-identical vertical tricolor"`). |
| `source` | enum | `"manual"`, `"qa_similarity"`, `"model_confusion"`, or `"user_report"`. |
| `review_status` | enum | See allowed values. Only `reviewed` entries affect official eval reports. |

#### Optional fields

| Field | Type | Description |
|---|---|---|
| `relationship` | string | Structured relationship type when needed. Use `"identical_design"` for flags that are visually identical but represent distinct meanings/results. |
| `notes` | string | Maintainer-facing caveats. |

#### Example

```json
{"confusable_id": "ro-td", "level": "result", "members": ["ro", "td"], "reason": "near-identical vertical tricolor", "source": "manual", "review_status": "reviewed"}
```

Phase 1 ships with a minimal seed confusables file containing the known v2-era lookalikes. It may be empty (zero lines) at the start if no manual entries are ready.

---

## 5. Allowed Enum Values

### `category` (results only)

| Value | Meaning |
|---|---|
| `national` | Sovereign states or country-level results. |
| `subnational` | Dependencies, territories, states, provinces, autonomous regions, municipalities, and other non-sovereign place-based units. |
| `military` | Military branches, units, commands, or war flags where the subject is military. |
| `maritime` | Maritime flags, ensigns, signal flags, and sea-use flags. |
| `organization` | Political parties, international organizations, companies, movements, clubs, and institutions. |
| `cultural` | Ethnic, religious, linguistic, diaspora, indigenous, or cultural-community flags. |
| `pride` | LGBTQ+, gender, sexuality, and adjacent identity flags. |
| `sports` | Sports teams, leagues, supporter flags, and sports organizations. |
| `other` | Reviewed result that does not fit the current taxonomy. |

### `fictionality` (results only)

| Value | Meaning |
|---|---|
| `nonfiction` | Real-world flag, design, proposal, unofficial usage, disputed usage, or historical usage. |
| `fictional` | Flag from a fictional universe, alternate-history setting, game, novel, film, show, or other invented context. |

### `status` (results and flags)

| Value | Meaning |
|---|---|
| `current` | Currently adopted, recognized, or in active use. |
| `historical` | Formerly used, obsolete, or time-bounded. |
| `proposed` | Proposed but not known to be adopted. |
| `unofficial` | Used informally or culturally but not officially adopted. |
| `disputed` | Adoption, authority, identity, or attribution is contested. |
| `deprecated` | Retained for compatibility but not preferred for new presentation or training. |

There is no `unknown` status. Uncertainty belongs in `review_status`.

### `variant` (flags only)

| Value | Meaning |
|---|---|
| `standard` | Default or general-use visual identity. |
| `civil` | Civilian-use identity, only when visually distinct from standard/state forms. |
| `state` | Government or official-institution identity, only when visually distinct. |
| `military` | Military-use identity. Fine-grained details (naval ensign, war flag, etc.) go in `variant_data`. |
| `royal` | Monarch, royal house, or royal standard. |
| `presidential` | President or head-of-state office-specific identity. |
| `organizational` | Organization-specific variant under a broader result. |
| `alternate` | Meaningful alternate visual identity not fitting another variant. |
| `reconstruction` | Reconstructed design where the exact historical design is uncertain. |
| `ceremonial` | Ceremonial-use identity. |

Unknown or unclear variants must not use a placeholder value. Use `review_status=needs_disambiguation`.

### `asset_type` (assets only)

| Value | Meaning |
|---|---|
| `source_original` | Original downloaded or collected source file, preserved as closely as practical. |
| `source_render` | Rendered, rasterized, or converted version of a source (e.g., SVG→PNG). |
| `emoji_render` | Platform or emoji-style render (e.g., Twemoji). |
| `reference_only` | Useful for review or comparison but not eligible for training export. |

### `review_status` (all record types)

| Value | Meaning |
|---|---|
| `imported` | Mechanically imported and structurally valid; not yet accepted. |
| `needs_review` | Requires general human attention. |
| `needs_source` | Missing acceptable provenance. |
| `needs_license` | Missing, unclear, or unacceptable license metadata. |
| `needs_disambiguation` | Unclear identity, duplicate, or variant mapping. |
| `reviewed` | Accepted for its intended use. |
| `rejected` | Deliberately excluded; retained to prevent repeat import or review churn. |

### `confusable.level`

| Value | Meaning |
|---|---|
| `flag` | Members are `flag_id`s. |
| `result` | Members are `result_id`s. |

### `confusable.source`

| Value | Meaning |
|---|---|
| `manual` | Human-authored. |
| `qa_similarity` | Discovered by the QA similarity check. |
| `model_confusion` | Discovered from recurring model evaluation confusion. |
| `user_report` | Future bot or user feedback (reserved). |

---

## 6. Required vs Optional Fields Summary

### Export-eligible record

The complete export gate is defined in Section 9.1. At minimum, all three manifest layers must be reviewed, flags and assets must be explicitly trainable, and the exported flag must have an eligible primary `source_original` asset.

```
result.review_status == reviewed
flag.review_status   == reviewed
asset.review_status  == reviewed
flag.trainable       == true
asset.trainable      == true
asset.asset_type     == source_original   (for the primary export asset)
```

`trainable=false` is the default for both flags and assets. It must be set explicitly.

### `short_description` rule

`short_description` is required on `result` records when `review_status=reviewed`. It may be absent on `imported` or `needs_*` records.

### `source_url` rule

`source_url` is required on all `reviewed` assets. It is provenance metadata; it is not required to be a direct download URL.

### `license` rule

`license` is required on all `trainable=true` assets. `reference_only` assets do not require `license` (they cannot be exported).

---

## 7. Validation Rules

`scripts/validate_manifest.py` produces `reports/qa/latest.json` and `reports/qa/latest.md`. Validation uses a blocker/warning severity model.

### 7.1 Blockers

Blockers prevent training export. The export script must refuse to run while any blocker exists.

| Code | Record type | Condition |
|---|---|---|
| `invalid_jsonl` | any | Any line in any manifest file is not valid JSON or is blank. |
| `duplicate_result_id` | result | Two or more results share the same `result_id`. |
| `duplicate_flag_id` | flag | Two or more flags share the same `flag_id`. |
| `duplicate_asset_id` | asset | Two or more assets share the same `asset_id`. |
| `duplicate_confusable_id` | confusable | Two or more confusables share the same `confusable_id`. |
| `missing_required_field` | any | An unconditionally required field is absent from a record. Conditional fields such as `source_url` and `license` use their specific conditional blocker codes. |
| `invalid_enum` | any | A field contains a value not in the allowed enum set. |
| `flag_missing_result` | flag | `flag.result_id` does not match any `result_id` in `results.jsonl`. |
| `asset_missing_flag` | asset | `asset.flag_id` does not match any `flag_id` in `flags.jsonl`. |
| `confusable_missing_member` | confusable | A `confusable.members` entry does not match any record at the referenced level. |
| `reviewed_result_missing_description` | result | `review_status=reviewed` but `short_description` is absent or empty. |
| `trainable_asset_missing_license` | asset | `trainable=true` but `license` is absent or empty. |
| `reviewed_asset_missing_source_url` | asset | `review_status=reviewed` but `source_url` is absent or empty. |
| `trainable_asset_file_missing` | asset | `trainable=true` and `review_status=reviewed` but `path` does not exist on disk. |
| `trainable_asset_unreadable` | asset | `trainable=true` and `review_status=reviewed` but file at `path` cannot be decoded as an image. |
| `trainable_asset_zero_dimensions` | asset | Decoded image has zero width or zero height. |
| `trainable_asset_unreviewed_flag` | asset | `trainable=true` and `review_status=reviewed` but referenced `flag.review_status != reviewed`. |
| `trainable_asset_unreviewed_result` | asset | `trainable=true` and `review_status=reviewed` but the flag's referenced `result.review_status != reviewed`. |
| `trainable_on_nonreviewed_flag` | flag | `flag.trainable=true` but `flag.review_status != reviewed`. |
| `trainable_on_nonreviewed_asset` | asset | `asset.trainable=true` but `asset.review_status != reviewed`. |
| `reference_only_trainable` | asset | `asset_type=reference_only` and `asset.trainable=true`. |
| `duplicate_class_id_in_export` | flag | Two or more flags that would be exported share the same `flag_id`. (Should not occur if duplicate_flag_id passes, but explicit check.) |

### 7.2 Warnings

Warnings are surfaced in the QA report but do not block export.

| Code | Condition |
|---|---|
| `result_no_aliases` | Reviewed result has no `aliases`. |
| `result_no_parent` | Reviewed result with `category=subnational` or `category=military` has no `parent_result_id`. |
| `result_no_links` | Reviewed result has no `links`. |
| `flag_no_aspect_ratio` | Reviewed flag has no `aspect_ratio`. |
| `flag_no_visual_notes` | Reviewed flag has no `visual_notes`. |
| `flag_one_trainable_asset` | A trainable flag has exactly one trainable asset. |
| `trainable_flag_no_source_original` | A flag has `trainable=true` and `review_status=reviewed` but no reviewed+trainable `source_original` asset. The export script will skip this flag; a primary source asset must be approved before it can train. |
| `asset_small_dimensions` | Trainable asset decoded dimensions are below 64×64. |
| `asset_has_transparency` | Trainable asset has an alpha channel with non-opaque pixels. |
| `asset_hash_duplicate` | `sha256` of this asset matches another asset's `sha256`. |
| `visual_similar_across_results` | Perceptual hash of a trainable asset is near the perceptual hash of a trainable asset from a different result (threshold: pHash distance ≤ 8). |
| `asset_aspect_ratio_drift` | Asset decoded aspect ratio differs from `flag.aspect_ratio` by more than 20%. |

---

## 8. Migration from v2

### 8.1 Source Mapping

```
data/labels.csv              -> results.jsonl entries + flags.jsonl entries
data/flags/<code>.png        -> assets.jsonl entries (source_original)
data/flags_wiki/<code>.png   -> assets.jsonl entries (source_render), if present
data/flags_emoji/<code>.png  -> assets.jsonl entries (emoji_render), if present
```

### 8.2 ID Convention for Migrated Records

| Record | ID format | Example |
|---|---|---|
| result | lowercase ISO code | `ad`, `us`, `gb` |
| flag | `<result_id>-current` | `ad-current`, `us-current` |
| asset (primary) | `<flag_id>-primary` | `ad-current-primary` |
| asset (wiki) | `<flag_id>-wiki` | `ad-current-wiki` |
| asset (emoji) | `<flag_id>-emoji` | `ad-current-emoji` |

### 8.3 Migration Default Field Values

The migration script (`scripts/migrate_v2.py`) applies these defaults to all records created from `data/labels.csv`:

**Results:**

| Field | Migrated value |
|---|---|
| `result_id` | `lowercase(code)` |
| `display_name` | `name` from `labels.csv` |
| `category` | `national` (default; reviewer reclassifies subnational entries) |
| `fictionality` | `nonfiction` |
| `status` | `current` |
| `short_description` | `"Current flag of <display_name>."` (generated placeholder) |
| `review_status` | `imported` by default; `reviewed` when `--reviewed` flag is passed |

**Flags:**

| Field | Migrated value |
|---|---|
| `flag_id` | `<result_id>-current` |
| `result_id` | `<result_id>` |
| `display_name` | `"<display_name> current flag"` |
| `variant` | `standard` |
| `status` | `current` |
| `review_status` | `imported` by default; `reviewed` when `--reviewed` flag is passed |
| `trainable` | `false` by default; `true` when `--reviewed` flag is passed |

**Primary assets (`data/flags/<code>.png`):**

| Field | Migrated value |
|---|---|
| `asset_id` | `<flag_id>-primary` |
| `flag_id` | `<flag_id>` |
| `asset_type` | `source_original` |
| `path` | `data/flags/<lowercase_code>.png` |
| `source_name` | `"hampusborgos/country-flags"` |
| `source_url` | `"https://github.com/hampusborgos/country-flags"` |
| `license` | `"public-domain"` |
| `review_status` | `imported` by default; `reviewed` when `--reviewed` flag is passed |
| `trainable` | `false` by default; `true` when `--reviewed` flag is passed |

**Wiki assets (`data/flags_wiki/<code>.png`):** Created only when the file exists.

| Field | Migrated value |
|---|---|
| `asset_id` | `<flag_id>-wiki` |
| `flag_id` | `<flag_id>` |
| `asset_type` | `source_render` |
| `path` | `data/flags_wiki/<lowercase_code>.png` |
| `source_name` | `"FlagCDN / Wikimedia Commons"` |
| `source_url` | `"https://flagcdn.com"` |
| `license` | (absent — must be reviewed) |
| `review_status` | `needs_license` |
| `trainable` | `false` |

**Emoji assets (`data/flags_emoji/<code>.png`):** Created only when the file exists.

| Field | Migrated value |
|---|---|
| `asset_id` | `<flag_id>-emoji` |
| `flag_id` | `<flag_id>` |
| `asset_type` | `emoji_render` |
| `path` | `data/flags_emoji/<lowercase_code>.png` |
| `source_name` | `"Twemoji"` |
| `source_url` | `"https://github.com/twitter/twemoji"` |
| `license` | `"cc-by-4.0"` |
| `review_status` | `imported` |
| `trainable` | `false` |

### 8.4 Migration `--reviewed` Flag

When invoked with `--reviewed`, the migration script marks results, flags, and primary assets as `review_status=reviewed` and sets `flag.trainable=true` and primary `asset.trainable=true`. Wiki and emoji assets are never auto-reviewed regardless of this flag.

**Standard Phase 1 migration invocation:**

```powershell
python scripts/migrate_v2.py --reviewed
```

This produces an export-eligible manifest for the v2 primary label set immediately.

### 8.5 Idempotency

If the manifest files already exist, the migration script applies the following rules:

- **Safe mutations:** A record may be upgraded from `imported` to `reviewed` on a second run with `--reviewed`. This is the expected path when the first run was done without `--reviewed` and the operator later decides to accept the batch.
- **Protected mutations:** A record already at `reviewed` must not be overwritten by the migration script. If a re-run would change a `reviewed` record's fields (other than upgrading `imported → reviewed`), the script must exit non-zero and report the conflict rather than silently overwriting.
- **`--force` (Phase 1: not implemented):** Force-overwriting `reviewed` records is intentionally deferred. The script must error out with a clear message rather than implementing `--force` in Phase 1.

Running `--reviewed` on a fresh manifest (no prior records) is the expected first-run behavior and always succeeds.

---

## 9. Training Export Contract

`scripts/export_training.py` reads the manifest and produces `data/generated/train/`.

### 9.1 Export Eligibility

A flag is exported if and only if all of the following hold:

```
flag.trainable == true
flag.review_status == reviewed
result.review_status == reviewed   (for the flag's result_id)
```

A flag must have at least one eligible primary asset:

```
asset.trainable == true
asset.review_status == reviewed
asset.flag_id == flag.flag_id
asset.asset_type == source_original
```

Flags with no eligible primary `source_original` asset are not exported and the export script emits a warning for each. Secondary eligible `source_render` and `emoji_render` assets may be exported to their type-specific directories only after the primary export condition is satisfied.

### 9.2 Class Ordering

Classes are sorted deterministically by `flag_id` in ascending lexicographic order. The sort must be stable across runs given an unchanged manifest. Class IDs start at `0`.

### 9.3 `data/generated/train/labels.csv`

One row per exported class. Format:

```
code,name
ad-current,Andorra
ae-current,United Arab Emirates
...
```

- Header line required: `code,name` — the column names `code` and `name` exactly match v2 convention. The `code` column holds `flag_id` values; the `name` column holds `display_name` values.
- The C trainer's `vx_dataset_load()` skips line 1 only when `strstr(line, "code")` matches. The header must contain the substring `"code"` — do not change it.
- Fields separated by comma, `name` quoted if it contains a comma.
- Encoding: UTF-8
- Line endings: LF

> **`--identify` output note:** After retraining from the Phase 1 export, the `CODE` column in `--identify` stdout will contain `flag_id` values (e.g., `ad-current`) instead of the v2 ISO alpha-2 codes (e.g., `AD`). The output format is otherwise identical. The `class_map.json` maps `flag_id` → `result_id` for any downstream tooling that needs the ISO code.

The `code` column (`flag_id` values) is the class key consumed by the C trainer. The C trainer is invoked as:

```powershell
.\build\vexilloscope.exe data/generated/train/labels.csv data/generated/train/images/
```

### 9.4 `data/generated/train/images/`

One image per exported class. Filename: `<flag_id>.png`. The C trainer derives the image path by lowercasing the value in the `code` column of `labels.csv` and appending `.png`. Since `flag_id` values are already lowercase-hyphenated, the resulting filename equals `<flag_id>.png` exactly.

Image source:

- The export script copies (or symlinks) the primary (`source_original`) eligible asset for each flag into `images/<flag_id>.png`.
- On Windows, the export script copies rather than symlinks by default.
- If multiple eligible asset types exist for the same flag, the export script copies each type into its corresponding type-specific subdirectory as described in section 9.5. Each subdirectory gets exactly one image per flag class.

Images are resized to 128×128 by the C trainer at load time. The export script does not resize.

### 9.5 Multi-Source Export

The C trainer supports up to three image directories (primary, wiki, emoji). The export script generates separate directories when eligible secondary asset types exist:

```
data/generated/train/images/            # primary (source_original)
data/generated/train/images_wiki/       # optional wiki/source renders (source_render)
data/generated/train/images_emoji/      # optional emoji renders (emoji_render)
```

`images/` is always created for exported classes. `images_wiki/` and `images_emoji/` are created only if they would contain at least one reviewed+trainable secondary asset. Empty secondary directories are not created.

The export script prints the trainer invocation using only directories that exist and contain at least one exported image.

Example with both secondary directories present:

```powershell
.\build\vexilloscope.exe data/generated/train/labels.csv data/generated/train/images/ data/generated/train/images_wiki/ data/generated/train/images_emoji/
```

Missing per-class images in secondary/tertiary directories cause the C trainer to fall back to the primary (existing behavior).

### 9.6 `data/generated/train/class_map.json`

The class map provides the full mapping for inference and evaluation tooling.

Schema:

```json
{
  "version": 1,
  "generated_at": "<ISO 8601 timestamp>",
  "n_classes": 255,
  "classes": [
    {
      "class_id": 0,
      "flag_id": "ad-current",
      "result_id": "ad",
      "display_name": "Andorra",
      "category": "national",
      "fictionality": "nonfiction",
      "status": "current",
      "variant": "standard"
    }
  ]
}
```

- `class_id` is the integer index used by the C trainer (0-based, sorted by `flag_id`).
- `flag_id` is the exact visual identity.
- `result_id` is the metadata subject the flag maps to.
- `display_name` is denormalized from the **result** record (the user-facing answer name).
- `category` and `fictionality` are denormalized from the **result** record (only results carry these fields).
- `status` is denormalized from the **flag** record (`flag.status` describes the lifecycle of the visual identity being classified; `result.status` is accessible via `result_id` when needed).
- `variant` is denormalized from the **flag** record (only flags carry `variant`).
- All fields are required.

The C trainer's top-3 stdout output can be mapped back to result objects by looking up `class_id` → `flag_id` → `result_id` in this file.

---

## 10. QA Report Contract

### 10.1 `reports/qa/latest.json`

```json
{
  "version": 1,
  "generated_at": "<ISO 8601 timestamp>",
  "summary": {
    "blockers": 0,
    "warnings": 12,
    "results_total": 255,
    "results_reviewed": 255,
    "flags_total": 255,
    "flags_reviewed": 255,
    "flags_trainable": 255,
    "assets_total": 765,
    "assets_reviewed": 255,
    "assets_trainable": 255,
    "export_eligible_classes": 255
  },
  "issues": [
    {
      "severity": "blocker",
      "code": "duplicate_result_id",
      "record_type": "result",
      "record_id": "ad",
      "message": "result_id 'ad' appears more than once in results.jsonl.",
      "suggested_fix": "Remove or rename the duplicate record."
    },
    {
      "severity": "blocker",
      "code": "trainable_asset_missing_license",
      "record_type": "asset",
      "record_id": "ad-current-wiki",
      "field": "license",
      "message": "Trainable asset is missing required license metadata.",
      "suggested_fix": "Add a reviewed license value or set trainable=false."
    },
    {
      "severity": "warning",
      "code": "result_no_aliases",
      "record_type": "result",
      "record_id": "ad",
      "field": "aliases",
      "message": "Reviewed result has no aliases.",
      "suggested_fix": "Add one or more alternate names or search terms."
    }
  ]
}
```

All fields in `summary` are required. `issues` may be an empty array. Each issue must include `severity`, `code`, `record_type`, `record_id`, `message`, and `suggested_fix`. The `field` key is optional: omit it for record-level issues (e.g., `invalid_jsonl`, `duplicate_result_id`) where no single field is responsible. Include it for field-level issues (e.g., `trainable_asset_missing_license`, `result_no_aliases`) to identify the specific field.

### 10.2 `reports/qa/latest.md`

A human-readable Markdown file derived from `latest.json`. Required sections:

```markdown
# Manifest QA Report

Generated: <timestamp>

## Summary

| Metric | Value |
|---|---|
| Blockers | 0 |
| Warnings | 12 |
| ... |

## Blockers

(none) OR list of blocker issues

## Warnings

List of warning issues

## Export

Export eligible classes: 255
```

### 10.3 Report Archive

When `validate_manifest.py` runs, it may write a timestamped copy to `reports/qa/archive/<timestamp>.json`. Archive copies are optional in Phase 1.

---

## 11. Artifact and Gitignore Policy

### 11.1 Committed artifacts

The following are committed to the repo:

```
data/manifest/results.jsonl
data/manifest/flags.jsonl
data/manifest/assets.jsonl
data/manifest/confusables.jsonl
```

QA reports are local generated artifacts and are not committed in Phase 1.

### 11.2 Ignored by default

Add the following to `.gitignore`:

```
data/generated/
data/flags_wiki/
data/flags_emoji/
reports/qa/archive/
reports/qa/latest.json
reports/qa/latest.md
vit_weights.bin
```

`data/generated/` covers all generated training exports, renders, and negative eval data. The existing `.gitignore` entries for `flags_wiki/` and `flags_emoji/` should be confirmed.

### 11.3 Never committed

```
vit_weights.bin
data/generated/train/images/
data/generated/train/images_wiki/
data/generated/train/images_emoji/
data/generated/renders/
data/generated/negative_eval/
reports/qa/latest.json
reports/qa/latest.md
```

---

## 12. Script Contracts

### `scripts/migrate_v2.py`

```
python scripts/migrate_v2.py [--reviewed] [--dry-run]
```

- Reads `data/labels.csv`.
- Creates or updates records in `data/manifest/results.jsonl`, `flags.jsonl`, `assets.jsonl`.
- Safe mutations: upgrades existing `imported` records to `reviewed` (and sets `trainable=true`) when `--reviewed` is passed. This is the expected path when the first run was done without `--reviewed`.
- Protected mutations: does not overwrite existing `reviewed` records whose fields would change. Exits non-zero and reports the conflict. `--force` is not implemented in Phase 1.
- `--reviewed`: marks results, flags, and primary assets as `reviewed` and `trainable=true`. Wiki and emoji assets are never auto-reviewed.
- `--dry-run`: prints what would be written without writing anything.
- Prints a summary of records created/upgraded/skipped to stdout.

### `scripts/validate_manifest.py`

```
python scripts/validate_manifest.py [--report-path reports/qa/latest.json]
```

- Reads all four manifest files.
- Validates schema, enum values, cross-file references, and image integrity for trainable assets.
- Writes `reports/qa/latest.json` and `reports/qa/latest.md`.
- Exits `0` if there are no blockers, `1` if there are blockers.
- Exits `2` on script-level errors (missing files, unreadable manifest, etc.).

### `scripts/export_training.py`

```
python scripts/export_training.py [--output data/generated/train]
```

- Reads the manifest.
- Calls `validate_manifest.py` first; refuses to export if blockers exist.
- Writes `data/generated/train/labels.csv`, `class_map.json`, and image directories.
- Prints the correct C trainer invocation to stdout after completion.
- Exits non-zero on any error.

---

## 13. Phase 1 Verification Checklist

All items must pass before Phase 1 is declared complete.

- [ ] `data/manifest/results.jsonl` exists with one entry per v2 label (255 entries).
- [ ] `data/manifest/flags.jsonl` exists with one entry per v2 label (255 entries).
- [ ] `data/manifest/assets.jsonl` exists with at least one entry per v2 label (primary assets).
- [ ] `data/manifest/confusables.jsonl` exists (may be empty or contain seed entries).
- [ ] `python scripts/validate_manifest.py` exits `0` (no blockers) on the migrated manifest.
- [ ] `reports/qa/latest.json` is written and parseable.
- [ ] `reports/qa/latest.md` is written.
- [ ] `python scripts/export_training.py` completes without error.
- [ ] `data/generated/train/labels.csv` exists with 255 rows (plus header).
- [ ] `data/generated/train/class_map.json` exists and is parseable; `n_classes` is 255.
- [ ] `data/generated/train/images/` exists with 255 PNGs named by `flag_id`.
- [ ] The C trainer runs successfully with the generated export:
  ```powershell
  .\build\vexilloscope.exe data/generated/train/labels.csv data/generated/train/images/
  ```
- [ ] `--identify` output format is unchanged (verified against `data/flags/de.png`).
- [ ] `data/generated/` is in `.gitignore`.
- [ ] `data/manifest/results.jsonl`, `flags.jsonl`, `assets.jsonl`, `confusables.jsonl` are committed.
- [ ] `reports/qa/latest.json` and `reports/qa/latest.md` are generated locally and are not committed.
- [ ] No `vit_weights.bin` committed.

---

## 14. Explicit Non-Goals

The following are explicitly out of scope for Phase 1. Do not implement or speculate on them here.

- **US states/DC import** — deferred to Phase 2
- **Historical flag import** — deferred to Phase 3
- **Fictional, pride, cultural, sports, military, maritime expansion** — deferred
- **Model architecture changes** — no C source changes in Phase 1
- **`--identify-json` implementation** — deferred to Phase 4
- **Negative eval generation** — deferred
- **256×256 or other resolution experiments** — deferred
- **Bot presentation changes** — deferred
- **Category-aware augmentation** — deferred
- **Hard-negative mining or oversampling by confusable group** — deferred
- **Dedicated detector model or flagness head** — deferred
- **Real-world eval set** — deferred
- **Automated review or `reviewed` assignment by scripts** — importers are collectors only; `reviewed` is set by human action or the explicit `--reviewed` migration flag for the established v2 primary set
- **No-flag class or separate `no_flag` classifier class** — deferred
- **SQLite manifest** — JSONL is the canonical format for v3
- **Direct JSONL parsing in the C binary** — C consumes generated CSV; JSONL stays in Python tooling
