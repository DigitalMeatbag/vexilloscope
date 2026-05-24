# vexilloscope v3 Foundation Document v2

> **Purpose:** This document captures the intent, constraints, proposed direction, open questions, and planning checklist for vexilloscope v3. It is a living foundation document, not yet an implementation specification.

---

## Intent

vexilloscope v3 expands from a current-country flag classifier into a broad flag recognition system. The goal is to identify as many useful flag classes as practical, including current national flags, dependent territories, subnational flags, historical flags, variants, organizations, cultural flags, fictional flags, and other vexillological categories.

v3 should improve real-world accuracy while expanding coverage. The project should avoid treating label expansion as a simple append-only CSV exercise. A larger flag universe requires stronger dataset metadata, source tracking, quality checks, evaluation tooling, and inference semantics.

---

## Motivating Driver

The current system is useful for current national and territory flags, especially when the flag is the dominant subject of the image. The long-term use case is broader: a user should be able to post a Discord screenshot, cropped image, emoji render, or distorted flag and receive a useful answer even when the flag is historical, regional, alternate, fictional, or visually confusable with common national flags.

v3 is the planning step that turns vexilloscope from "255 labels and a model" into a maintainable flag knowledge and recognition pipeline.

---

## v2 State (Brownfield Baseline)

- Classifier: ViT trained on current label set with up to three render sources.
- Detection: `--identify` owns the sliding-window detection path and can return `no flag detected`.
- Bot: transport layer that passes image bytes to the binary and parses stdout.
- Dataset: `labels.csv` maps one display label to one primary image filename.
- Training: all labels are training labels; eval measures augmented robustness rather than a held-out class split.
- Inference: top-3 exact labels are printed from classifier logits.

The primary v3 limitation is not only model capacity. The current dataset representation cannot safely scale to thousands of heterogeneous flag identities with source provenance, aliases, variants, hierarchy, and ambiguity.

---

## v3 North Star

v3 should optimize for:

- **Coverage:** many more flags across national, regional, historical, fictional, and other categories.
- **Accuracy:** higher real-world correctness, especially on Discord-style screenshots and visually similar flags.
- **Honesty:** better handling of no-flag, ambiguous, low-confidence, and near-duplicate cases.
- **Maintainability:** dataset imports are reproducible, metadata-rich, and reviewable.
- **Evaluation:** improvements are measured by category, hierarchy, confusable group, and no-flag behavior.

---

## Proposed Architecture Direction

```text
source importers
  -> raw image cache + source metadata
  -> reviewed manifest
  -> dataset QA reports
  -> train/eval splits and generated variants
  -> detector / classifier training
  -> identify output with exact match, entity grouping, and ambiguity handling
```

The model remains important, but v3 treats the dataset and evaluation harness as first-class architecture.

---

## Planning Method

Each planning topic should be resolved in the same shape:

- **Overview:** what the topic covers.
- **Why it matters:** what ambiguity or risk this decision removes.
- **Constraints:** what the decision must respect.
- **Non-goals:** what the decision deliberately does not solve.
- **Options:** viable approaches and their tradeoffs.
- **Follow-ups:** questions or experiments needed before closing the decision.
- **Decision:** the chosen direction once settled.

The foundation document should preserve the reasoning behind decisions, not only the decisions themselves. The later specification should be able to derive implementation requirements from this document with minimal interpretation.

---

## Specification Strategy

v3 should be specified in phases rather than as one monolithic specification.

The foundation intentionally covers the full v3 direction: dataset model, imports, QA, training export, negatives, evaluation, confusables, model direction, inference, and artifact layout. A single full v3 specification would be too large and too speculative. Later phases depend on the dataset backbone working against real data.

### First Spec Target

The first v3 specification should be:

```text
SPEC_V3_PHASE1.md
```

Scope:

- `data/manifest/results.jsonl`
- `data/manifest/flags.jsonl`
- `data/manifest/assets.jsonl`
- `data/manifest/confusables.jsonl`
- schema validation rules
- migration from `data/labels.csv`
- initial source asset mapping from existing `data/flags`
- QA report contract
- export to `data/generated/train/labels.csv`
- generated `data/generated/train/class_map.json`
- gitignore/artifact expectations

### Phase 1 Non-Goals

The first spec should not attempt to implement:

- US states/DC import
- historical flags
- fictional/pride/cultural expansion
- model architecture changes
- `--identify-json`
- negative eval generation
- 256x256 experiments
- bot presentation changes

### Later Specs

Later v3 specs should be generated after Phase 1 is implemented and validated against the current dataset.

Likely follow-up specs:

```text
SPEC_V3_PHASE2_SOURCES.md      # controlled source expansion, starting with US states + DC
SPEC_V3_PHASE3_EVAL.md         # category-aware eval, negatives, confusables
SPEC_V3_PHASE4_MODEL_OUTPUT.md # model experiments and --identify-json
```

The exact names and boundaries may change, but the principle should not: spec only the next implementable slice with enough detail to build and verify it.

---

## Decision Log

| Topic | Status | Decision |
|---|---|---|
| Manifest format | Closed | Canonical v3 manifest data is JSONL; simple CSV files may be generated for compatibility. |
| Required manifest metadata | Closed | Results, flags, and assets have moderate required cores; reviewed/trainable export requires reviewed records and explicit trainability gates. |
| Result/flag/asset semantics | Closed | v3 uses separate result, flag, and asset records rather than one mashed-together manifest row. |
| First expansion category | Closed | Migrate current v2 labels first; first true expansion is a bounded subnational set, preferably US states + DC; historical national flags follow. |
| Source import strategy | Closed | Importers are collectors, not trust authorities; reports must trace failures to likely root cause. |
| No-flag strategy | Closed | Use locally generated negative evaluation data for threshold calibration first; balance false positives and false negatives with mild preference against confident false positives. |
| Evaluation strategy | Closed | Result-level accuracy is the primary user-value metric; exact flag accuracy remains a model/debug metric with required breakdowns and no-flag/confusable reporting. |
| Production resolution | Closed | 256×256 input with 16×16 patches (adopted 2026-05-21 from exp-256-p16: top-1 94.32%, HC-FP 15.0% at threshold_x10=35). Pending clean retraining from scratch. |

---

## Dataset Manifest

v3 should replace or extend `data/labels.csv` with richer manifest data.

### Overview

The manifest is the canonical index of what vexilloscope knows about flags. It defines result objects, visual flag identities, and concrete source/training assets. It records what a flag is, where its images came from, how it should be grouped for output, whether it is current or historical, and whether it is approved for training.

The current `labels.csv` is a useful v1/v2 shape:

```text
code,name,filename
```

v3 needs a shape that can represent a much larger and messier world:

- one entity with multiple visual variants
- one visual flag shared by multiple entities
- current and historical versions of the same entity
- official, unofficial, fictional, proposed, disputed, and reconstructed flags
- multiple render/source assets per flag
- source provenance and licensing
- review state

### Why It Matters

The manifest is upstream of almost every v3 system:

- importers create manifest entries
- QA validates manifest entries
- training consumes accepted manifest entries
- eval groups results by type, status, and hierarchy
- inference maps model classes back to user-facing answers
- the bot decides what to show based on manifest metadata

If the manifest is underspecified, the ambiguity leaks everywhere else. For example, the model might correctly predict an emoji render of Scotland, but the bot needs to know whether to display "Scotland", "Flag of Scotland", "United Kingdom / Scotland", or a render-specific label.

### Constraints

- The format must be easy to generate and validate from scripts.
- It must preserve source provenance and license metadata.
- It must distinguish trainable class identity from user-facing answer identity.
- It must support generated assets without requiring generated assets to be committed.
- It must allow review and rejection without deleting source records.
- It must be practical to inspect and edit during early v3 development.
- It should not force a database dependency into the C binary.

### Non-Goals

- The manifest does not need to be a full vexillology encyclopedia.
- The manifest does not need to solve visual similarity by itself.
- The first version does not need to encode every possible historical nuance.
- The C training path does not need to consume the rich manifest directly if a generated compatibility file is simpler.
- The manifest should not become a dumping ground for unverified internet images.

Early planning treated the manifest as a possible single record shape with fields such as:

```text
flag_id
result_id
display_name
type
parent_id
territory_code
era_start
era_end
variant
status
source_name
source_url
license
path
aliases
notes
review_status
```

The v3 direction is now to keep these concepts separated rather than mashing them into one row.

### Format Options

#### Option A: CSV

Use a single `data/manifest.csv`.

Pros:

- simple and familiar
- easy to diff in Git
- easy to generate from the current `labels.csv`
- easy to inspect in a spreadsheet
- straightforward for C and Python to parse

Cons:

- awkward for nested fields like multiple aliases, sources, render assets, or notes
- escaping becomes annoying as metadata grows
- harder to represent multiple source images under one flag identity
- schema evolution can become brittle

Best fit:

- early migration from v2
- simple one-row-per-trainable-class design
- compatibility export for C training

#### Option B: JSONL

Use JSONL files for canonical manifest records.

Pros:

- still diffable and line-oriented
- supports nested fields without inventing delimiter rules
- easier to represent aliases, sources, assets, and review metadata
- excellent fit for Python import/QA scripts
- easier to evolve during v3 planning

Cons:

- less convenient for manual spreadsheet editing
- C should probably not parse it directly
- requires a generated CSV or binary/index format for the current C loader

Best fit:

- canonical rich v3 manifest
- importer and QA workflow
- generated compatibility outputs for training

#### Option C: SQLite

Use a local SQLite database as the canonical manifest.

Pros:

- strong querying and constraints
- natural fit for many-to-many relationships
- good for review tools and larger datasets
- can enforce schema more rigorously

Cons:

- binary-ish artifact is less friendly in Git
- harder to review changes
- adds tooling weight early
- overkill before the data model is stable

Best fit:

- later review UI or large dataset management
- not ideal as the first v3 foundation format

#### Option D: Layered JSONL Manifest Files

Keep result, flag, and asset records in separate JSONL files.

Example:

```text
data/manifest/results.jsonl
data/manifest/flags.jsonl
data/manifest/assets.jsonl
data/generated/labels.csv
```

Pros:

- each file has one clear record type
- avoids forcing result metadata, visual identity, and asset provenance into one row
- keeps JSONL records easy to inspect and validate
- supports multiple flags per result and multiple assets per flag
- generated compatibility files can stay simple

Cons:

- more moving parts
- requires validation across files
- requires stable IDs and references from the beginning
- requires export scripts before the C trainer can consume v3 data

Best fit:

- canonical v3 manifest data
- exact separation of output metadata, trainable visual identity, and source assets

### Suggested Direction

Use **layered JSONL manifest files** as the canonical rich manifest data, with generated compatibility outputs for C training and inference.

Suggested initial layout:

```text
data/
  manifest/
    results.jsonl             # result objects and human-meaningful metadata
    flags.jsonl               # exact visual flag identities
    assets.jsonl              # source/render/training assets
    confusables.jsonl         # reviewed visual similarity/identity relationships
  generated/
    labels.csv                # generated v2-compatible training labels
scripts/
  migrate_labels_to_manifest.py
  validate_manifest.py
  export_training_labels.py
```

This keeps the philosophical center clean: v3's truth lives in metadata-rich, reviewable JSONL records, while the existing C code can keep consuming simple generated files until the richer loader is worth building.

### Resolved Follow-ups

- Closed: schemas for `results.jsonl`, `flags.jsonl`, and `assets.jsonl` are defined in the required metadata section.
- Closed: required fields for reviewed/exportable records are defined in the required metadata section.
- Closed: v3 training uses generated compatibility exports; `data/labels.csv` remains the v2 source until migration replaces or supersedes it deliberately.
- Closed: generated compatibility files are artifacts under `data/generated/` and are ignored by default unless intentionally snapshotted.

### Field Intent

- `flag_id`: exact visual identity used as a classifier class.
- `result_id`: stable internal correlation ID for the metadata object returned by the system.
- `display_name`: human-readable label.
- `category`: national, subnational, military, maritime, organization, cultural, pride, sports, or other.
- `fictionality`: nonfiction or fictional.
- `parent_result_id`: hierarchy, such as California -> United States.
- `territory_code`: ISO or local administrative code when one exists.
- `era_start` / `era_end`: date range for historical flags.
- `variant`: standard, civil, state, military, royal, presidential, organizational, alternate, reconstruction, or ceremonial.
- `status`: current, historical, proposed, unofficial, disputed, or deprecated.
- `source_name` / `source_url` / `license`: provenance and reuse tracking.
- `path`: local image asset.
- `aliases`: alternate names and search terms.
- `notes`: human-readable caveats.
- `review_status`: imported, needs_review, needs_source, needs_license, needs_disambiguation, reviewed, or rejected.

### Decision

Closed: v3 uses layered JSONL manifest data as the canonical source of truth. Result objects, exact visual flag identities, and concrete source/training assets are separate records. The C training path may consume generated compatibility files until a richer loader is justified. CSV remains acceptable as an export or compatibility format, not the source of truth.

---

## Result Object

### Overview

The primary interaction is:

```text
user uploads image -> vexilloscope identifies likely flag -> system returns one or more result objects
```

A v3 result object is a JSON-compatible metadata blob describing the flag identity vexilloscope believes the image most likely represents. The result object is the first-class object returned by the system and consumed by integrations.

The result object has a stable internal ID for correlation, caching, evaluation, debugging, and API use. That ID is not a meaningful part of the human-facing answer. Users care about the flag name, who uses or used it, the relevant category, historical or fictional context, and other interesting facts.

The classifier may internally predict a training class, crop, or visual identity, but the machine-readable output is a structured result:

```json
{
  "result_id": "us-ca",
  "display_name": "California",
  "category": "subnational",
  "fictionality": "nonfiction",
  "status": "current",
  "parent": {
    "result_id": "us",
    "display_name": "United States"
  },
  "confidence": 0.92
}
```

Different result categories may expose different metadata. A fictional flag does not need the same fields as a historical national flag, and a current subnational flag does not need the same fields as an obsolete military variant.

### Why It Matters

The user's intent is usually not "what tensor class had the highest logit?" The user's intent is "what flag is this, who uses it, and what context should I know?"

Making the result object first-class prevents v3 from leaking internal classifier mechanics into the product model. It also gives the bot, CLI, and any future integrations one stable contract: they consume ranked result objects with metadata, regardless of how the model produced them.

The internal ID exists so the system can correlate the result reliably. It should not be treated as user-facing copy.

### Constraints

- Every result object must have a stable internal `result_id`.
- Result IDs should be stable across retraining.
- Result objects must be JSON-compatible.
- Result metadata must be category-aware.
- Multiple plausible results must be representable.
- Result objects should be derivable from the manifest plus model output.
- Internal training labels may be more granular than result IDs.
- Human-facing output should prioritize useful facts over internal identifiers.

### Non-Goals

- The result object does not need to expose every training/render asset.
- The result object does not need to encode the full source/import history.
- The result object does not need to settle all naming disputes by itself.
- The result object should not require the user to understand `flag_id`, logits, or training classes.
- The internal result ID is not meant to be displayed as an interesting fact.

### Options

#### Option A: Result ID Equals Exact Visual Class

The result `id` is the exact classifier class.

Pros:

- simple mapping from model output to result
- easy to evaluate exact visual prediction
- good for variants that users care about

Cons:

- can overexpose render or variant distinctions
- multiple top results may all be the same real-world answer
- awkward for identical or near-identical flags

#### Option B: Result ID Equals Metadata Subject

The result `id` correlates to the metadata subject the answer is about, such as a country, region, group, historical regime, fictional polity, or symbol family.

Pros:

- matches the core user intent
- avoids duplicate render/source variants in output
- cleaner bot and JSON response semantics

Cons:

- may hide meaningful variant differences
- exact visual evaluation needs a separate internal ID
- historical and alternate flags need careful modeling

#### Option C: Result Object Contains Internal Correlation ID and Matched Visual ID

The result has a stable internal correlation `id`, plus optional exact visual identity fields. Human-facing presentation is generated from the descriptive metadata, not from the ID.

Example:

```json
{
  "result_id": "de-1935",
  "display_name": "Germany, 1935-1945",
  "category": "national",
  "fictionality": "nonfiction",
  "status": "historical",
  "matched_flag_id": "de-1935-state",
  "variant": "state",
  "confidence": 0.88
}
```

Pros:

- preserves exact model evidence
- keeps the human-facing answer clean
- supports category-specific metadata
- works with grouped variants and exact visual classes

Cons:

- requires clearer manifest semantics
- slightly more complex output contract

### Suggested Direction

Use Option C.

The first-class result should be a metadata object with a stable internal `result_id`. Human-facing output should be generated from descriptive fields, not the ID. When useful, the result can include the more granular matched visual identity, variant, source, or render information. This keeps the user's question central while preserving enough detail for correlation, debugging, evaluation, and advanced output modes.

### Follow-ups

- Closed: the stable internal result identifier is `result_id`.
- Closed: common and category-specific metadata are defined by the required metadata and category sections.
- Closed: `--identify-json` returns ranked result objects by default.
- Closed: existing text stdout remains compatibility-oriented while JSON output becomes result-object based.

### Decision

Closed: the first-class machine output is a ranked result object with stable internal `result_id` and human-meaningful metadata. Human-facing output is generated from descriptive fields, not internal IDs. When useful, result objects include matched flag details, variant/source context, confidence, margin, and ambiguity metadata.

---

## Result, Flag, and Asset Semantics

v3 should separate exact visual classification from user-facing meaning.

```text
result_id = internal correlation ID for the returned metadata object
flag_id   = exact visual flag identity the classifier may predict
asset_id  = concrete source, render, or generated image
```

Example:

```text
flag_id: us-ca-current
result_id: us-ca
asset_id: us-ca-current-wikimedia-svg
display_name: California
category: subnational
parent_result_id: us
status: current
```

This allows the system to distinguish exact matches while still reporting a useful grouped answer.

### Overview

v3 has three distinct concepts:

- `result`: the metadata object returned by the system and transformed into a human answer.
- `flag`: an exact visual symbol that can be trained, evaluated, and mapped to a result.
- `asset`: a concrete image, source render, generated variant, or training sample associated with a flag.

These concepts should not be collapsed into one manifest row. A result can have multiple flag identities, and a flag can have multiple assets.

### Why It Matters

This separation prevents source/render details from becoming fake user-facing answers. It also prevents broad metadata subjects from being forced to behave like exact visual classifier classes.

For example, "California" is a result. The current California flag is a visual flag identity. A Wikimedia SVG render, an emoji-style render, and generated distorted training crops are assets.

### Constraints

- Every `result`, `flag`, and `asset` must have a stable ID.
- A `flag` must reference a `result_id`.
- An `asset` must reference a `flag_id`.
- The model may train on assets and predict flag identities.
- Inference must map predicted flags back to ranked result objects.
- Human-facing output must be generated from result metadata, not internal IDs.

### Non-Goals

- Assets are not user-facing answers.
- Source render variants should not become separate results unless they represent meaningful flag identities.
- The first v3 pass does not need a database to enforce these relationships.

### Options

#### Option A: One Combined Manifest Row

Put result metadata, flag identity, and asset source details in one JSON object.

Pros:

- fewer files
- easy to inspect a single row
- quick to prototype

Cons:

- mixes three different concepts
- duplicates result metadata across variants/assets
- makes validation and updates clumsy
- encourages accidental user-facing exposure of asset/source distinctions

#### Option B: Separate Result, Flag, and Asset Records

Use separate JSONL files with references between them.

Pros:

- each record type has one job
- matches the conceptual model
- handles one-to-many relationships cleanly
- keeps future importers and QA tools simpler

Cons:

- requires cross-file validation
- requires export scripts from the beginning
- slightly more ceremony than one file

### Decision

Closed: v3 uses separate result, flag, and asset records. Result records define the metadata objects returned by the system. Flag records define exact visual identities that can be trained and evaluated. Asset records define concrete source, render, or generated images. Inference maps predicted flags to ranked result objects.

### Resolved Questions

- Closed: required fields are defined in the required metadata section.
- Closed: the bot presents result metadata from `--identify-json`, including status/category context and ambiguity notes when warranted.
- Closed: default JSON output merges multiple top `flag_id`s that map to the same `result_id` into one ranked result object while preserving matched flag details.

---

## Required Manifest Metadata

### Overview

v3 manifest data is split into three record types:

```text
results.jsonl -> metadata subjects returned by the system
flags.jsonl   -> exact visual flag identities
assets.jsonl  -> concrete source/render/generated images
```

This section defines the minimum metadata each record type should carry so importers, QA, training export, inference, and human-facing presentation can all make reliable decisions.

The goal is not to model every possible fact about every flag. The goal is to capture enough structure that v3 can scale without ambiguity.

### Why It Matters

The required fields determine what the rest of v3 can trust.

If `results` lack category and status, the bot cannot explain whether a flag is current, historical, fictional, unofficial, or subnational. If `flags` lack stable result references, model predictions cannot be reliably mapped back to answer objects. If `assets` lack provenance and review state, training can silently ingest questionable images.

Required metadata is the line between a curated recognition system and a directory full of interesting PNGs.

### Constraints

- Required fields should be minimal enough to populate for current v2 labels.
- Required fields should be strong enough to block unreviewed or sourceless data from training.
- IDs must be stable and human-readable enough for maintainers, but not treated as user-facing copy.
- Record types must be independently validateable.
- Category-specific metadata should be allowed without forcing every category into the same fields.
- The C trainer should be able to consume generated exports without understanding the full schema.

### Non-Goals

- Do not require complete historical scholarship before a result can exist.
- Do not require all categories to share the same rich metadata.
- Do not make generated augmentation samples first-class curated source records unless needed.
- Do not expose internal IDs as human-facing answer text.
- Do not turn the manifest into a general encyclopedia.

### Proposed Core Schemas

#### `results.jsonl`

Each line describes a metadata subject that can be returned as a ranked result.

Required fields:

```json
{
  "result_id": "us-ca",
  "display_name": "California",
  "category": "subnational",
  "fictionality": "nonfiction",
  "status": "current",
  "short_description": "Current state flag of California, United States.",
  "review_status": "reviewed"
}
```

Recommended optional fields:

```json
{
  "parent_result_id": "us",
  "territory_code": "US-CA",
  "aliases": ["California state flag"],
  "era_start": "1911",
  "era_end": null,
  "trivia": [
    {
      "type": "visual_detail",
      "text": "Features the California grizzly bear and a red star."
    }
  ],
  "links": [
    {
      "label": "Wikimedia Commons",
      "url": "https://commons.wikimedia.org/..."
    }
  ],
  "notes": "Use result metadata for human-facing presentation; do not display result_id."
}
```

Field intent:

- `result_id`: stable internal correlation ID.
- `display_name`: primary human-facing name.
- `category`: broad type of result.
- `fictionality`: whether the result belongs to the real world or a fictional setting.
- `status`: current, historical, proposed, unofficial, disputed, deprecated.
- `short_description`: short human-facing context sentence; required for reviewed results.
- `review_status`: whether the result metadata has been accepted for use.
- `parent_result_id`: hierarchy such as California -> United States.
- `territory_code`: ISO or local administrative code when one exists.
- `aliases`: alternate names and search terms.
- `era_start` / `era_end`: meaningful for historical or time-bounded results.
- `trivia`: optional typed human-interest notes; useful context, not required to carry the same weight as core identity metadata.
- `links`: optional reference links.
- `notes`: maintainer-facing caveats.

#### `flags.jsonl`

Each line describes one exact visual flag identity that can be trained, evaluated, and mapped to a result.

Required fields:

```json
{
  "flag_id": "us-ca-current",
  "result_id": "us-ca",
  "display_name": "California current flag",
  "variant": "standard",
  "status": "current",
  "review_status": "reviewed",
  "trainable": false
}
```

Recommended optional fields:

```json
{
  "era_start": "1911",
  "era_end": null,
  "aspect_ratio": "2:3",
  "visual_notes": "White field with bear, red star, and red stripe.",
  "trainable": true,
  "evaluation_group": "subnational-current"
}
```

Field intent:

- `flag_id`: stable ID for the exact visual identity.
- `result_id`: result object this flag maps to.
- `display_name`: maintainer-friendly label for the visual identity.
- `variant`: standard, civil, state, military, royal, presidential, organizational, alternate, reconstruction, ceremonial.
- `status`: current, historical, proposed, unofficial, disputed, deprecated.
- `review_status`: whether this visual identity is accepted.
- `trainable`: whether this visual identity may be exported as a model class; defaults false.
- `era_start` / `era_end`: useful when a result has multiple historical visual identities.
- `aspect_ratio`: canonical ratio if known.
- `visual_notes`: maintainer-facing visual description.
- `evaluation_group`: optional grouping for metrics.

#### `assets.jsonl`

Each line describes a concrete image asset associated with a flag.

Required fields:

```json
{
  "asset_id": "us-ca-current-wikimedia-svg",
  "flag_id": "us-ca-current",
  "asset_type": "source_original",
  "path": "data/sources/wikimedia/us_states/us-ca.svg",
  "source_name": "Wikimedia Commons",
  "source_url": "https://commons.wikimedia.org/...",
  "license": "public-domain",
  "review_status": "reviewed",
  "trainable": false
}
```

Recommended optional fields:

```json
{
  "width": 1280,
  "height": 853,
  "sha256": "...",
  "render_style": "flat-svg",
  "generated_from_asset_id": null,
  "generator": null,
  "trainable": true,
  "notes": "Rasterized from SVG at import time."
}
```

Field intent:

- `asset_id`: stable ID for this concrete image asset.
- `flag_id`: exact visual identity this asset represents.
- `asset_type`: source_original, source_render, emoji_render, or reference_only.
- `path`: local path to the asset or generated output.
- `source_name` / `source_url` / `license`: provenance and reuse metadata. `source_url` records where the asset came from; it is not necessarily the URL used to retrieve the local file.
- `review_status`: whether this asset is accepted for use.
- `trainable`: whether this concrete asset may contribute training samples; defaults false.
- `width` / `height`: source dimensions when known.
- `sha256`: duplicate detection and reproducibility.
- `render_style`: flat-svg, emoji, photo, screenshot, generated-augmentation, etc.
- `generated_from_asset_id`: lineage for generated variants.
- `generator`: script or policy that produced the asset.
- `notes`: maintainer-facing caveats.

### Category-Specific Metadata

All result records share a small common core, but category-specific fields should live in a nested object rather than bloating every record.

Example:

```json
{
  "result_id": "lotr-gondor",
  "display_name": "Gondor",
  "category": "national",
  "fictionality": "fictional",
  "status": "current",
  "short_description": "Fictional flag associated with Gondor in The Lord of the Rings.",
  "category_data": {
    "fictional_universe": "The Lord of the Rings",
    "creator": "J. R. R. Tolkien"
  },
  "review_status": "reviewed"
}
```

This keeps the common schema small while allowing historical, fictional, organizational, pride, military, and subnational results to carry different metadata.

### Options

#### Option A: Very Small Required Core

Require only IDs, display names, references, and review status.

Pros:

- fastest to populate
- easiest migration from v2
- fewer import blockers

Cons:

- weak human-facing answers
- category-aware eval is limited
- bad data can enter unless QA grows stricter elsewhere

#### Option B: Moderate Required Core

Require IDs, names, category/status, references, provenance, review status, and trainability gates.

Pros:

- enough structure for inference, eval, QA, and presentation
- still practical for v2 migration
- catches most ambiguity early

Cons:

- more work for imported data
- some categories need placeholder or unknown values until reviewed

#### Option C: Rich Required Core

Require historical dates, hierarchy, aliases, facts, dimensions, hashes, source links, and category-specific metadata for every reviewed record.

Pros:

- best metadata quality
- strongest presentation and QA

Cons:

- slows expansion dramatically
- overfits the schema before real data teaches us what matters
- makes fictional/unofficial/historical imports painful

### Suggested Direction

Use Option B: a moderate required core.

Required fields should be strong enough to ensure every trainable/exportable item has a known identity, mapping, provenance, status, and review state. Richer facts should be encouraged but not required for the first v3 pass.

### Follow-ups

- Closed: allowed values for `category`, `status`, `variant`, `asset_type`, and `review_status` are defined in their respective sections.
- Closed: `short_description` is required for reviewed results and may be shown directly to users.
- Closed: `license` is required for every trainable asset.
- Closed: `source_url` is provenance metadata, not a guaranteed download URL.
- Closed: generated augmentation samples are produced outside the curated `assets.jsonl` manifest unless a future use case requires tracking them.
- Closed: `trainable` defaults to false unless explicitly true.
- Closed: `trainable` lives on both flags and assets. `flag.trainable` controls whether the visual identity may become a model class; `asset.trainable` controls whether the concrete image may contribute training samples.
- Closed: training export requires explicit trainability and reviewed records at all three layers: result, flag, and asset.

### Decision

Closed: v3 uses a moderate required metadata core. Required fields are strong enough to ensure every trainable/exportable item has known identity, mapping, provenance, license, status, and review state. Richer metadata is encouraged but not required for the first v3 pass.

---

## Result Category Values

### Overview

`category` classifies what kind of metadata subject a `result` represents. It is primarily a result-level field, not a flag-level or asset-level field.

Example:

```json
{
  "result_id": "us-ca",
  "display_name": "California",
  "category": "subnational",
  "fictionality": "nonfiction",
  "status": "current",
  "short_description": "Current state flag of California, United States."
}
```

Category answers the broad question: "What kind of thing is this flag associated with?"

### Why It Matters

Category drives:

- human-facing presentation
- category-specific metadata requirements
- evaluation grouping
- expansion planning
- import/review policy
- result filtering

A fictional military flag, a historical national flag, a maritime signal flag, and a municipal flag should not all be treated as the same kind of answer just because they are all images of flags.

### Constraints

- Categories should be broad and stable.
- Categories should describe the subject of the result, not the image source.
- Categories should avoid encoding currentness; `status` handles current, historical, proposed, disputed, etc.
- Categories should not multiply just because a flag has a variant; `variant` handles exact visual subtype.
- The starting set should be small enough to use consistently.
- Unknown or messy imports should have a safe holding category rather than forcing premature precision.

### Non-Goals

- Category does not need to encode every jurisdiction type.
- Category does not replace hierarchy such as parent regions.
- Category does not settle whether a flag is official, current, disputed, or fictional; those are status and metadata questions.
- Category does not describe the asset source or render style.

### Options

#### Option A: Coarse Taxonomy

Use a small set of broad categories:

```text
national
territory
subnational
municipal
organization
cultural
fictional
other
```

Pros:

- easy to classify
- stable
- avoids taxonomy bikeshedding
- works well for early v3

Cons:

- hides important distinctions such as military or maritime flags
- may push too much meaning into category-specific metadata

#### Option B: Medium Taxonomy

Use broad categories plus common flag-domain categories:

```text
national
subnational
military
maritime
organization
cultural
pride
sports
other
```

Pros:

- still manageable
- useful for evaluation and presentation
- covers likely expansion families
- avoids making every special case its own category

Cons:

- some results can plausibly fit multiple categories
- requires clearer precedence rules

#### Option C: Fine Taxonomy

Use many specific categories:

```text
national
dependent_territory
first_level_subdivision
second_level_subdivision
city
military_branch
naval_ensign
civil_ensign
political_party
intergovernmental_organization
ethnic_group
religious_group
pride_identity
fictional_country
fictional_organization
...
```

Pros:

- very expressive
- strong category-specific presentation

Cons:

- likely premature
- harder to apply consistently
- many edge cases
- can duplicate hierarchy, status, and variant fields

### Suggested Direction

Use Option B: a medium taxonomy.

Suggested initial allowed values:

```text
national
subnational
military
maritime
organization
cultural
pride
sports
other
```

### Field Boundaries

- `category=national`: sovereign states or country-level results.
- `category=subnational`: dependencies, territories, states, provinces, constituent countries, autonomous regions, cities, counties, municipalities, and other non-sovereign place-based political/geographic units. More specific distinctions can live in `category_data.subnational_type`.
- `category=military`: military branches, units, ranks, commands, or war flags where the subject is military.
- `category=maritime`: maritime flags, ensigns, signal flags, yacht clubs, and sea-use flags where the subject is maritime.
- `category=organization`: political parties, international organizations, companies, movements, clubs, and institutions.
- `category=cultural`: ethnic, religious, linguistic, diaspora, indigenous, or cultural-community flags.
- `category=pride`: LGBTQ+, gender, sexuality, and related identity flags.
- `category=sports`: sports teams, leagues, supporter flags, and sports organizations.
- `category=other`: reviewed result that does not fit the current taxonomy.

### Fictionality

Fictional vs non-fictional should be represented as its own axis rather than as a category.

Proposed field:

```json
{
  "fictionality": "nonfiction"
}
```

Suggested allowed values:

```text
nonfiction
fictional
```

This allows results such as:

```text
fictional military flag     -> category=military, fictionality=fictional
fictional country flag      -> category=national, fictionality=fictional
fictional city flag         -> category=subnational, fictionality=fictional
historical in-universe flag -> status=historical, fictionality=fictional
```

This is cleaner than forcing all fictional results into `category=fictional`, because fictional flags can still belong to recognizable subject types.

Alternate-history, parody, or real-world-inspired fictional flags should generally use `fictionality=fictional`. Their relationship to real-world subjects can be captured in category-specific metadata or `trivia`, not as a third top-level fictionality value.

### Cultural vs Pride

`pride` can be treated either as its own category or as a specialized part of `cultural`.

The distinction, if kept, is:

- `category=cultural`: ethnic, religious, linguistic, indigenous, diaspora, heritage, or broad cultural-community flags.
- `category=pride`: LGBTQ+, gender, sexuality, and adjacent identity flags, because they are a large, recognizable flag family with distinctive discovery, metadata, and user expectations.

Decision: keep `pride` separate from `cultural`.

Rationale: the distinction is practical rather than philosophical. Pride flags and cultural/community flags carry distinct enough user expectations, likely metadata, and expansion/review needs that separate categories are useful.

### Maritime

Decision: keep `maritime` as a category.

Rationale: maritime flags can be their own subject family, not only a variant of national or military flags. Naval/civil ensign details may still appear in `variant_data` when appropriate, but maritime remains available as a result category when the subject itself is maritime.

### Precedence Questions

Some flags can plausibly fit multiple categories. v3 needs precedence rules.

Examples:

- A historical national flag should be `national` with `status=historical`, rather than `category=historical`.
- A naval ensign for a current country could be `maritime` or `national` plus `variant=military` and `variant_data.military_use=naval_ensign`.
- A pride organization flag could be `pride` or `organization`.
- A fictional military flag should likely be `category=military` with `fictionality=fictional`.

### Follow-ups

- Closed: `historical` is not a category; it is a `status`.
- Closed: `fictionality` is required for all reviewed results.
- Closed: `maritime` remains a category.
- Closed: `pride` remains separate from `cultural`.
- Closed: `subnational` includes territories and dependencies; more specific distinctions can live in category-specific metadata.

### Decision

Closed: the initial result category set is `national`, `subnational`, `military`, `maritime`, `organization`, `cultural`, `pride`, `sports`, and `other`. `historical` is a status, not a category. Fictional vs non-fictional is represented by a required `fictionality` field for reviewed results.

---

## Fictionality Values

### Overview

`fictionality` describes whether a result belongs to the real world or to a fictional setting. It is required for reviewed results and is separate from `category` and `status`.

### Why It Matters

Fictionality affects provenance, licensing caution, human-facing presentation, and category interpretation. A fictional military flag and a real-world military flag can share `category=military`, but the system should not present them as the same kind of real-world object.

### Allowed Values

```text
nonfiction
fictional
```

### Field Boundaries

- `nonfiction`: real-world flag, symbol, design, proposal, unofficial usage, disputed usage, or historical usage.
- `fictional`: flag or symbol from a fictional universe, alternate-history setting, game, novel, film, show, roleplay setting, parody setting, or other invented context.

### Non-Goals

- `fictionality` does not encode currentness; `status` does that.
- `fictionality` does not encode category; fictional results still use categories such as `national`, `military`, or `organization`.
- `fictionality` does not attempt to distinguish "fully fictional" from "real-world-inspired fictional." That nuance belongs in category-specific metadata or `trivia`.

### Trivia Caution

`trivia` is intentionally flexible, but it should not become a hidden replacement for core metadata. If a piece of information is required for filtering, evaluation, training export, licensing review, or consistent presentation, it should become an explicit schema field rather than living only in `trivia`.

### Decision

Closed: reviewed results use binary `fictionality`: `nonfiction` or `fictional`. There is no `unknown` or `fictionalized` value. Uncertainty belongs in `review_status`; real-world-inspired fictional nuance belongs in category-specific metadata or `trivia`.

---

## Review Status Values

### Overview

`review_status` describes whether a record is accepted, blocked, pending review, or rejected. It exists on result, flag, and asset records.

Review status is the pipeline gatekeeper. Category, status, and fictionality should not use `unknown` as a holding value; uncertainty and blockers belong here.

### Why It Matters

v3 will ingest data from generated scripts, public sources, manual curation, and probably messy future sources. Review status prevents imported data from silently becoming training data or user-facing output.

It also makes partial import runs useful. An importer can create valid records for successfully imported items while marking incomplete or risky items with specific blockers.

### Allowed Values

```text
imported
needs_review
needs_source
needs_license
needs_disambiguation
reviewed
rejected
```

### Field Boundaries

- `imported`: mechanically imported and structurally valid enough to exist, but not yet accepted by human or QA review.
- `needs_review`: requires general human attention and does not fit a more specific blocker.
- `needs_source`: missing acceptable provenance or source reference.
- `needs_license`: missing, unclear, unsafe, or unacceptable license metadata.
- `needs_disambiguation`: unclear identity, duplicate, variant mapping, naming, or result/flag relationship.
- `reviewed`: accepted for its intended use.
- `rejected`: deliberately excluded; retained to prevent repeat importer churn or repeated review work.

### Export Rule

Only `reviewed` records are eligible for training export or user-facing result output.

For a trainable asset to export, all three layers must be accepted:

```text
result.review_status == reviewed
flag.review_status   == reviewed
asset.review_status  == reviewed
asset.trainable      == true
```

### Partial Import Example

```text
Importer finds 500 source images.
- 420 import cleanly with source and license metadata -> imported
- 50 import but license parsing fails              -> needs_license
- 20 import but identity is ambiguous              -> needs_disambiguation
- 10 fail before a useful record can be created    -> import error log only
```

### Non-Goals

- `review_status` does not describe whether a flag is current or historical.
- `review_status` does not describe whether a flag is fictional.
- `review_status` does not replace source/license fields.

### Decision

Closed: allowed review statuses are `imported`, `needs_review`, `needs_source`, `needs_license`, `needs_disambiguation`, `reviewed`, and `rejected`. `imported` is the raw successful importer landing state. Only `reviewed` records may export.

---

## Status Values

### Overview

`status` describes the adoption, usage, or lifecycle state of a result or flag identity. It is separate from `category` and `fictionality`.

Example:

```json
{
  "result_id": "us-1777",
  "display_name": "United States, 1777-1795",
  "category": "national",
  "fictionality": "nonfiction",
  "status": "historical",
  "short_description": "Historical national flag of the United States with thirteen stars and thirteen stripes."
}
```

### Why It Matters

Status tells the system how to present and evaluate a result:

- current flags can be presented as current usage
- historical flags need time/context language
- proposed flags should not be described as adopted
- unofficial flags need softer wording
- disputed flags need caution
- deprecated records can remain for compatibility without being preferred

### Constraints

- `status` must not duplicate `category`.
- `status` must not duplicate `fictionality`.
- Reviewed results should not use an unknown status.
- Unsettled records should use `review_status`, such as `needs_review` or `needs_disambiguation`, rather than `status=unknown`.

### Allowed Values

```text
current
historical
proposed
unofficial
disputed
deprecated
```

### Field Boundaries

- `current`: currently adopted, recognized, or in active use by the result subject.
- `historical`: formerly used, obsolete, or time-bounded in context.
- `proposed`: proposed but not adopted or not known to be adopted.
- `unofficial`: used informally or culturally but not officially adopted.
- `disputed`: adoption, authority, identity, or correct attribution is contested.
- `deprecated`: retained for compatibility, old model mapping, or historical data hygiene, but not preferred for new presentation or training.

### Trivia Metadata Boundary

Some flags develop a cultural afterlife that does not change their primary category or status.

Example: the Laser Kiwi flag is best modeled as `category=national`, `fictionality=nonfiction`, and `status=proposed`. Its later life as a meme, cultural reference, or recognizable internet symbol should live in `trivia` rather than changing the primary category or status.

Example:

```json
{
  "result_id": "nz-laser-kiwi",
  "display_name": "Laser Kiwi",
  "category": "national",
  "fictionality": "nonfiction",
  "status": "proposed",
  "short_description": "Unofficial proposed alternative flag of New Zealand from the 2015-2016 flag referendum era.",
  "trivia": [
    {
      "type": "cultural_afterlife",
      "text": "The design later became a widely recognized meme and cultural reference."
    }
  ]
}
```

### Non-Goals

- `status` does not encode fictional vs non-fictional.
- `status` does not encode visual variants such as naval or civil.
- `status` does not encode source trust or review state.

### Decision

Closed: allowed status values are `current`, `historical`, `proposed`, `unofficial`, `disputed`, and `deprecated`. There is no `unknown` status; uncertainty belongs in `review_status`.

---

## Flag Variant Values

### Overview

`variant` describes the role or subtype of an exact visual flag identity in `flags.jsonl`. It is a flag-level field, not a result-level field and not an asset render-style field.

Example:

```json
{
  "flag_id": "es-state",
  "result_id": "es",
  "display_name": "Spain state flag",
  "variant": "state",
  "status": "current",
  "review_status": "reviewed"
}
```

### Why It Matters

Many result objects can have multiple exact visual identities. Variant metadata explains why those visual identities are distinct without forcing every special case into its own category.

For example, a country may have a standard flag, a civilian-use version, a government-use version, a military-use version, and a royal standard. These may map to the same result object while still being different classifier targets.

### Constraints

- `variant` should stay coarse.
- Fine-grained role details should use `variant_data`.
- Render/source style such as emoji or Wikimedia render belongs on assets, not variants.
- Unknown variant is not an allowed value; unclear cases should use `review_status=needs_disambiguation`.
- Civil/state variants should only be split when they are visually distinct and meaningful.

### Allowed Values

```text
standard
civil
state
military
royal
presidential
organizational
alternate
reconstruction
ceremonial
```

### Field Boundaries

- `standard`: default or general-use visual identity for the result.
- `civil`: civilian-use visual identity, used only when visually distinct from standard/state forms.
- `state`: government or official-institution visual identity, used only when visually distinct from standard/civil forms.
- `military`: military-use visual identity. More specific details such as naval ensign, war flag, air force ensign, roundel, jack, pennant, rank flag, or unit flag should live in `variant_data`.
- `royal`: monarch, royal house, royal standard, or related visual identity.
- `presidential`: president, head of state, or similar office-specific visual identity.
- `organizational`: organization-specific variant under a broader result where useful.
- `alternate`: meaningful alternate visual identity that does not fit another variant.
- `reconstruction`: reconstructed design where the exact historical design is uncertain or reconstructed from sources.
- `ceremonial`: ceremonial-use visual identity.

### Variant Data

`variant_data` carries structured detail when the coarse variant needs precision.

Example:

```json
{
  "flag_id": "nz-naval-ensign",
  "result_id": "nz",
  "variant": "military",
  "variant_data": {
    "military_use": "naval_ensign"
  }
}
```

This keeps top-level variants stable while allowing precise metadata where it matters for filtering, evaluation, or presentation.

### Civil vs State

`civil` means a civilian-use visual identity. `state` means a government or official-institution visual identity.

Many flags use the same design for both roles. In that case, v3 should use one `standard` flag record rather than creating duplicate `civil` and `state` records.

Only split `civil` and `state` when the visual identities are meaningfully different.

### Non-Goals

- `variant` does not describe whether a result is current, historical, proposed, or unofficial.
- `variant` does not describe whether a result is fictional.
- `variant` does not describe source/render style.
- `variant` does not need to model every specialized flag-use term as a top-level value.

### Decision

Closed: initial flag variants are `standard`, `civil`, `state`, `military`, `royal`, `presidential`, `organizational`, `alternate`, `reconstruction`, and `ceremonial`. Fine-grained use details belong in `variant_data`.

---

## Asset Type Values

### Overview

`asset_type` describes what kind of positive flag asset a record in `assets.jsonl` represents. Assets are concrete images tied to a `flag_id`.

Example:

```json
{
  "asset_id": "us-ca-current-wikimedia-svg",
  "flag_id": "us-ca-current",
  "asset_type": "source_original",
  "path": "data/sources/wikimedia/us_states/us-ca.svg",
  "source_name": "Wikimedia Commons",
  "source_url": "https://commons.wikimedia.org/...",
  "license": "public-domain",
  "review_status": "reviewed"
}
```

### Why It Matters

Asset type separates source provenance and render style from flag identity. The model may train on several assets for the same exact flag identity, but those assets should not become separate result objects or flag identities unless the visual design itself is meaningfully different.

### Constraints

- `assets.jsonl` is for positive flag assets tied to a `flag_id`.
- Generated augmentation samples do not live in `assets.jsonl`.
- Negative/no-flag examples do not live in `assets.jsonl`.
- Asset render style should not become a flag variant unless it represents a meaningful visual identity.
- Every trainable asset must have source/license metadata and explicit `trainable=true`.

### Allowed Values

```text
source_original
source_render
emoji_render
reference_only
```

### Field Boundaries

- `source_original`: original downloaded or collected source file, preserved as closely as practical.
- `source_render`: rendered, rasterized, normalized, or converted version of a source asset, such as an SVG rendered to PNG.
- `emoji_render`: platform or emoji-style render, such as Twemoji.
- `reference_only`: useful for review, documentation, or comparison but not eligible for training export.

### Non-Goals

- `asset_type` does not encode no-flag negatives.
- `asset_type` does not encode generated augmentation samples.
- `asset_type` does not describe result category or flag variant.

### Negative Dataset Boundary

Negative examples are a separate dataset concept. They are used for detector calibration and no-flag behavior, not for identifying a known flag. They should be handled by a future negative/no-flag dataset path rather than by `assets.jsonl`.

### Decision

Closed: initial asset types are `source_original`, `source_render`, `emoji_render`, and `reference_only`. `assets.jsonl` tracks positive flag assets tied to `flag_id`s. Generated augmentations and negative/no-flag examples are outside the curated asset manifest.

---

## First Expansion Strategy

### Overview

The first v3 expansion should test the manifest, QA, export, and evaluation pipeline without immediately taking on the hardest ambiguity classes.

Expansion should proceed in controlled layers:

```text
1. migrate current v2 labels into layered manifest records
2. add one bounded subnational expansion set
3. add historical national flags after the pipeline has been tested
```

### Why It Matters

The first expansion is not only about adding more labels. It is the first real test of whether the v3 data model works.

If the first expansion is too broad, errors become hard to diagnose: failures could come from source import, schema weakness, category/status ambiguity, model capacity, licensing gaps, or evaluation weakness. A bounded expansion gives the project a clean shakeout phase.

### Phase 1: Migrate Current v2 Labels

The current label set should be migrated before adding new families.

Expected mapping:

```text
data/labels.csv      -> results.jsonl + flags.jsonl
data/flags/*.png     -> assets.jsonl
data/flags_wiki/*    -> assets.jsonl where present
data/flags_emoji/*   -> assets.jsonl where present
```

Default metadata for migrated current flags:

```text
fictionality=nonfiction
status=current
variant=standard
review_status=reviewed or imported, depending on migration policy
trainable=false by default until explicitly enabled
```

Categories should be assigned during migration:

```text
national
subnational
```

Most current v2 labels are national or territory-like entries. Under the v3 taxonomy, dependencies, territories, constituent countries, and similar non-sovereign place-based entries are `subnational`.

### Phase 2: Bounded Subnational Expansion

The first true expansion should be a controlled subnational set.

Recommended first set:

```text
United States states + District of Columbia
```

Rationale:

- finite and familiar
- useful to users
- tests `category=subnational`
- lower conceptual ambiguity than historical or fictional flags
- easier to validate manually
- good source/provenance candidates exist

Source policy:

- Prefer Wikimedia Commons source pages with explicit license metadata.
- Use official state or DC government references for identity verification where helpful.
- Do not assume state government origin means public domain. The US federal public-domain rule does not automatically apply to state governments, territories, counties, municipalities, or other subdivisions.
- Require reviewed `source_url`, reviewed `license`, and explicit `asset.trainable=true` before training export.

### Phase 3: Historical National Flags

Historical national flags should come after the migration and first subnational expansion.

Rationale:

- high user interest
- tests `status=historical`
- likely sourceable from Wikimedia Commons and similar references

Risks:

- date ranges can be ambiguous
- reconstructed designs need careful handling
- variants can proliferate quickly
- disputed historical attribution is common

### Deferred Expansion Families

These are not rejected, but should wait until the backbone is proven:

- fictional flags
- pride flags
- broad cultural flags
- military and maritime families
- municipal/city-scale bulk imports
- arbitrary internet-sourced flag collections

### Decision

Closed: v3 expansion starts by migrating the current v2 labels into layered manifest records. The first true expansion family is a bounded subnational set, preferably United States states plus District of Columbia. Historical national flags follow after the pipeline has been tested.

---

## Source Import Strategy

v3 should use reproducible importers instead of manual image drops.

### Overview

Importers collect candidate manifest records and source assets. They do not decide that a record is trusted, trainable, or ready for user-facing output.

Importer output should populate or propose records for:

```text
data/manifest/results.jsonl
data/manifest/flags.jsonl
data/manifest/assets.jsonl
```

Importer failures should produce traceable reports that help identify the root cause.

Likely source families:

- Existing `data/flags/` current labels.
- Existing generated `data/flags_wiki/` Wikimedia/FlagCDN render source.
- Existing generated `data/flags_emoji/` Twemoji render source.
- Wikimedia Commons categories for historical flags, subnational flags, dependent territories, and organization flags.
- Curated local manifests for fictional, cultural, proposed, and unofficial flags.

### Importer Requirements

- Download or render assets reproducibly.
- Save source URL and license metadata.
- Preserve original image where possible.
- Generate normalized training images separately from source originals.
- Mark imported rows as unreviewed until accepted.
- Avoid silently overwriting existing reviewed assets.
- Never set `trainable=true` by default.
- Treat importers as collectors, not trust authorities.
- Produce reports for successes, warnings, skipped records, and failures.
- Make failures traceable to likely root cause.

### Importer Landing Statuses

Importers should use review status consistently:

```text
successful candidate import     -> imported
missing acceptable source        -> needs_source
missing or unsafe license        -> needs_license
ambiguous identity or mapping    -> needs_disambiguation
generic human attention needed   -> needs_review
deliberately excluded candidate  -> rejected
download/render/parse failure    -> report only, unless a useful partial record exists
```

### Failure Reporting

Any import failure should facilitate tracing to the error source or root cause.

Reports should capture enough context to answer:

- Which importer ran?
- Which source record, URL, or category was being processed?
- Which manifest record ID was being created or updated?
- Which phase failed: fetch, parse, license extraction, image decode, render, file write, validation, dedupe, or mapping?
- What was the concrete error message?
- Was the failure transient, source-data-related, schema-related, or policy-related?
- What local files or partial artifacts were produced, if any?

Suggested report location:

```text
reports/import/<source>/<timestamp>.json
```

Suggested report categories:

```text
imported
needs_source
needs_license
needs_disambiguation
needs_review
rejected
skipped_existing_reviewed
failed_fetch
failed_parse
failed_license_parse
failed_render
failed_image_decode
failed_validation
failed_write
```

### No Silent Overwrite

If an imported record ID already exists and is reviewed, the importer should not overwrite it unless running in an explicit update mode.

If a reviewed record conflicts with newly imported data, the importer should report the conflict rather than choosing silently.

### Source Priority

For early v3 expansion, source preference is:

```text
1. Wikimedia Commons pages with explicit license metadata
2. official entity/government references for identity verification
3. manually curated sources with clear provenance and license
```

Official references may help confirm identity, names, dates, or adoption status. They do not automatically satisfy license requirements unless the license is explicit and acceptable.

### Resolved Questions

- Closed: prefer importing SVG source assets where available and generating PNG training/render outputs locally.

### Decision

Closed: importers are collectors, not trust authorities. They may create candidate records and source assets, but only reviewed records with explicit trainability may export. Import reports must make successes, partial successes, skips, conflicts, and failures traceable to likely source or root cause. When SVG sources are available, v3 prefers storing/importing those SVGs and generating PNG outputs locally rather than treating remote rendered PNGs as the canonical source.

---

## Dataset QA

v3 should add dataset quality tooling before large-scale label expansion.

### Overview

Dataset QA validates manifest records, source assets, generated outputs, and relationships between results, flags, and assets. It is the safety layer between importers and export.

Importers collect candidates. Review status records human/automation acceptance. Dataset QA answers:

```text
Is this data structurally valid?
Is it safe to export?
Is it likely to confuse training or evaluation?
Is there enough information for a maintainer to fix problems?
```

QA should produce actionable reports rather than merely failing with a count of errors.

### Why It Matters

v3 is going to expand into messier data: subnational flags, historical variants, fictional flags, cultural flags, proposed designs, duplicate designs, and multiple source/render styles.

Without QA, mistakes will quietly become model behavior:

- unlicensed assets enter training
- duplicate flags inflate accuracy
- wrong result/flag mappings produce confident wrong answers
- corrupt images create bad training samples
- missing metadata breaks presentation
- visually identical flags get treated inconsistently

QA is how v3 keeps growth from turning into entropy with PNGs.

### Constraints

- QA must validate the layered manifest relationships.
- QA must respect the closed export gate: reviewed result, reviewed flag, reviewed trainable asset.
- QA must make failures traceable to the record, field, file, phase, and likely fix.
- QA should distinguish blockers from warnings.
- QA should be runnable locally from scripts.
- QA should not require training the model.
- QA should not require generated augmentation samples to be present.

QA reports should detect:

- duplicate and near-duplicate images
- identical flags mapped to multiple labels
- visually similar confusable clusters
- missing source or license metadata
- missing aliases or parent hierarchy
- invalid or extreme aspect ratios
- tiny or low-quality source assets
- transparent backgrounds
- excessive whitespace or borders
- classes with too few render variants
- classes whose generated training images are blank or corrupt

### Proposed QA Levels

#### Blockers

Blockers prevent export.

Suggested blockers:

- invalid JSONL
- duplicate IDs within a record type
- broken references, such as `flag.result_id` missing or `asset.flag_id` missing
- invalid enum values for category, fictionality, status, review status, variant, or asset type
- reviewed result missing required fields
- reviewed flag missing required fields
- reviewed asset missing required fields
- trainable asset missing license
- trainable asset missing source URL
- trainable asset path missing on disk
- trainable asset file unreadable or unsupported
- trainable asset has invalid or zero dimensions
- trainable asset references unreviewed result or flag
- `trainable=true` on non-reviewed flag or asset
- `reference_only` asset marked trainable
- generated training export would produce duplicate class IDs

#### Warnings

Warnings do not automatically block export, but should be visible.

Suggested warnings:

- result has no aliases
- result has no parent when category suggests one may exist
- result has no trivia or external reference links
- flag has no aspect ratio
- flag has no visual notes
- flag has only one trainable asset
- multiple flags under one result have very similar names
- asset dimensions are unusually small
- asset aspect ratio differs sharply from known/canonical flag aspect ratio
- asset has transparency
- asset has large whitespace/border region
- asset hash matches another asset
- perceptual hash is near another asset
- two trainable flags appear visually identical but map to different results
- source URL domain is unexpected for the importer/source family

### Report Shape

QA should produce both human-readable and machine-readable output.

Suggested locations:

```text
reports/qa/latest.json
reports/qa/latest.md
```

Suggested JSON report shape:

```json
{
  "summary": {
    "blockers": 0,
    "warnings": 12,
    "results": 306,
    "flags": 312,
    "assets": 948
  },
  "issues": [
    {
      "severity": "blocker",
      "code": "asset_missing_license",
      "record_type": "asset",
      "record_id": "us-ca-wikimedia-svg",
      "field": "license",
      "message": "Trainable asset is missing required license metadata.",
      "suggested_fix": "Add a reviewed license value or set trainable=false."
    }
  ]
}
```

### QA vs Review Status

QA can recommend or assign review statuses in generated reports, but should be careful about mutating reviewed records automatically.

Safe automation:

- imported asset missing license -> suggest `needs_license`
- imported asset missing source URL -> suggest `needs_source`
- imported flag with missing result reference -> suggest `needs_disambiguation`

Unsafe automation:

- marking records `reviewed`
- setting `trainable=true`
- overwriting reviewed records
- resolving duplicate/near-duplicate identity questions without human input

### Duplicate and Similarity Checks

QA should distinguish deterministic duplicates from visual similarity.

```text
duplicate      -> deterministic same asset/content
visual_match   -> appears identical or effectively identical after normalization
visual_similar -> likely confusable but not identical
```

The distinction matters because many flags are legitimately similar. Romania/Chad, Indonesia/Monaco, Poland/Monaco, Ireland/Côte d'Ivoire, Australia/New Zealand, and many tricolor or emblem variants are not necessarily bad data. They are often exactly the hard cases the model needs to learn.

Implementation levels:

```text
exact file hash              -> duplicate
decoded normalized hash      -> duplicate or visual_match
perceptual hash threshold    -> visual_similar
future model confusion data  -> visual_similar / confusable candidate
```

Deterministic duplicates may block when they violate IDs, relationships, or export rules. Visual similarity should warn by default and may feed the confusables registry.

### Image Integrity Checks

For trainable assets, QA should verify:

- file exists
- file can be decoded or rendered
- dimensions are nonzero
- dimensions meet minimum threshold
- image is not blank
- alpha/transparency behavior is known
- generated PNG output can be produced if source is SVG

### Non-Goals

- QA does not decide subjective historical interpretation.
- QA does not certify legal correctness; it enforces project metadata requirements.
- QA does not replace human review.
- QA does not require model inference or training.
- QA does not attempt to solve all visual confusability in v3 foundation.

### Resolved Questions

- Closed: blockers prevent export by definition; warnings do not.
- Closed: do not collapse visual similarity into duplicates. Use `duplicate`, `visual_match`, and `visual_similar` distinctions.
- Closed: QA artifacts live under `reports/qa/`.

### Suggested Direction

Use a blocker/warning model.

QA should block export on structural validity, missing reviewed/trainable gates, missing provenance/license for trainable assets, unreadable assets, invalid relationships, invalid enum values, and invalid generated exports.

QA should warn on likely quality or ambiguity issues such as duplicates, near-duplicates, low resolution, transparency, aspect-ratio drift, missing aliases, and sparse assets.

### Decision

Closed: v3 QA uses blocker/warning severity. Blockers prevent export by definition. Duplicate checks distinguish deterministic duplicates from visual matches and visual similarities. Deterministic duplicates may block when they violate IDs, relationships, or export rules; visual similarities warn by default and may feed the confusables registry. QA artifacts live under `reports/qa/`.

---

## Training Data and Augmentation

v3 should train from multiple render styles and synthetic distortions.

### Overview

Training data is derived from reviewed, trainable manifest records.

The core distinction:

```text
curated assets      -> source truth
generated renders   -> reproducible artifacts
runtime augmentation -> training-time distortion
```

Source SVGs, original images, and reviewed emoji/source renders are curated assets. Locally rendered PNGs, normalized training images, and generated exports are reproducible artifacts derived from those assets.

### Why It Matters

v3 will often have multiple assets per flag. Some flags may have a source SVG, a Wikimedia render, an emoji render, and official reference imagery; others may have only one source. Training should not accidentally oversample a flag simply because it has more assets.

The model should learn balanced flag identities, not the shape of the dataset collection process.

### Constraints

- Only reviewed/trainable results, flags, and assets may enter training export.
- Source assets are curated; generated renders and training files are reproducible outputs.
- Generated augmentation samples do not live in `assets.jsonl`.
- The initial v3 training export should remain compatible with the existing C pipeline where practical.
- Runtime augmentation remains the main distortion mechanism.
- v3 baseline should avoid architecture/resolution changes until the data pipeline is validated.

Recommended training variants:

- canonical clean render
- Wikimedia or source render
- emoji or platform render where relevant
- aspect-preserving resize with padding
- mild crop and zoom
- rotation, translation, perspective, blur
- JPEG and screenshot compression artifacts
- dark/light UI backgrounds
- partial occlusion
- low-resolution downsample then upsample
- white-flag and transparent-background stress cases

### Generated Render Policy

When source SVGs are available, v3 stores/reviews the SVG as the curated asset and generates PNGs locally.

Suggested paths:

```text
data/generated/renders/
data/generated/train/
```

Rendered PNGs are generated artifacts, not curated source assets, unless a future use case requires tracking a specific generated render as a source-like asset.

### Training Export Shape

Initial v3 export should produce simple compatibility files for the C trainer:

```text
data/generated/train/labels.csv
data/generated/train/images/
```

The export script maps:

```text
asset -> flag_id -> class_id
```

and preserves mapping metadata for inference/evaluation:

```text
data/generated/train/class_map.json
```

The current C path may keep consuming a CSV plus image directory while v3 metadata remains in JSONL.

### Sampling Policy

Training should be balanced by `flag_id`.

Recommended sampling:

```text
1. sample a trainable flag_id
2. sample one trainable asset for that flag_id
3. render/normalize if needed
4. apply runtime augmentation
```

This prevents flags with more assets from dominating training.

### Resolution Policy

v3 baseline keeps the existing `128x128` training target until the data pipeline is validated.

Source renders should be generated at a higher resolution where practical so future experiments can downsample to `160`, `192`, `256`, or other sizes without re-fetching sources.

**Update (2026-05-21):** After Phase 4 eval infrastructure was in place, the `exp-256-p16` experiment (256×256 input, 16×16 patches, same 256 tokens) was run and adopted as the production default. Results: top-1 94.32%, top-3 97.96%, HC-FP rate 15.0% at threshold_x10=35. Both accuracy and false-positive metrics improved meaningfully over the 128×128 / 8×8 baseline. The enum constants in `main.c` now reflect these values. Pending retraining from scratch; current weights (`vit_weights_256p16.bin`) were produced from the experiment run.

### Category-Aware Augmentation

Category-aware augmentation is deferred.

The first v3 pass should use a common augmentation policy. Category-specific policies may become useful later for seal-heavy subnational flags, pride flags with fine stripe patterns, or historical reconstructions, but they should follow evidence from evaluation.

### Non-Goals

- Do not commit generated training images by default until artifact policy is settled.
- Do not make generated augmentation samples first-class curated assets.
- Do not change model architecture solely because the manifest has changed.
- Do not allow asset count to determine class sampling frequency.

### Resolved Questions and Evidence Gaps

- Closed: generated augmentation samples are created on the fly unless debugging/evaluation creates a specific reason to materialize them.
- Closed: category-aware augmentation is deferred until evaluation shows a need.
- Evidence gap: how much distortion is useful before the model starts learning unrealistic samples.

### Decision

Closed: curated assets are source truth; generated renders and training files are reproducible artifacts. The initial v3 export remains compatible with the existing C pipeline, balances sampling by `flag_id`, keeps runtime augmentation as the primary distortion source, and retains `128x128` as the initial baseline training target while rendering sources at higher resolution where practical. **Updated 2026-05-21:** production default is now `256x256` with `16x16` patches (adopted from exp-256-p16).

---

## Negatives and Flagness

v3 should add explicit negative examples or a dedicated flagness signal.

### Overview

Negatives are no-flag or should-not-identify examples used to evaluate and calibrate the detector. They are not positive flag assets and do not belong in `assets.jsonl`.

The initial v3 posture is:

```text
generate negatives locally -> run no-flag eval -> calibrate thresholds
```

not:

```text
import negatives as assets -> train no_flag class immediately
```

### Why It Matters

The current v2 detector can return `no flag detected` using confidence thresholds. As the label set grows, false positives may become more likely because there are more classes for arbitrary crops to resemble.

Before adding architecture complexity, v3 should measure no-flag behavior with a generated negative evaluation set and calibrate thresholds against it.

### Constraints

- Negative examples are separate from curated positive flag assets.
- Negative examples should be generated locally where practical.
- Negative examples are used for evaluation and threshold calibration first.
- Negative examples should not require source/licensing review in the same way as positive imported assets if generated from approved local processes.
- Training on negatives, adding a `no_flag` class, or adding a flagness head are deferred until evaluation shows the need.

Negative categories:

- no-flag screenshots
- maps
- coats of arms
- logos
- countryball or emoji-like art
- UI icons
- colored rectangles and tricolor-like graphics
- flags too small or occluded to identify honestly

Possible approaches:

- Add a `no_flag` classifier class.
- Add a separate flag/non-flag head.
- Train a dedicated detector model.
- Keep sliding-window detection but calibrate thresholds using negative datasets.

### Initial Negative Generation

The first negative set can be generated locally from deterministic or scripted recipes.

Candidate recipe families:

- random solid colors and gradients
- random stripe patterns that are not known flags
- noisy rectangles
- UI-like screenshots or synthetic panels
- maps or coat-of-arms-like layouts if locally generated
- low-information crops
- tiny or heavily occluded flag-like shapes that should return no result

The exact recipe should be evidence-driven. The foundation does not need to choose the final negative distribution before real no-flag evaluation exists.

### Evaluation-First Policy

For v3, "negative use" means no-flag evaluation and threshold calibration unless explicitly revisited.

Other possible uses are deferred:

- training a `no_flag` class
- training a separate detector model
- adding a flag/non-flag head
- hard-negative mining from production failures

### Generated Negative Artifacts

Generated negatives may live under a generated/evaluation path such as:

```text
data/generated/negative_eval/
```

They should be reproducible from scripts. The generated images themselves do not need to be committed by default.

### Non-Goals

- Do not import negatives into `assets.jsonl`.
- Do not add a `no_flag` class as the first v3 step.
- Do not train a separate detector before threshold calibration evidence exists.
- Do not decide the final negative distribution without evaluation data.

### Resolved Questions

- Closed: v3 starts with threshold calibration using a generated negative evaluation set, not a separate detector.
- Closed: negative examples are generated locally and kept outside `assets.jsonl`.
- Closed: no-flag behavior should balance false positives and false negatives where feasible, with a mild preference against confident false positives.

### Decision

Closed: v3 negative handling starts as locally generated no-flag evaluation data used for threshold calibration. Negatives are not curated positive assets, are not imported into `assets.jsonl`, and do not imply a `no_flag` class or separate detector in the first v3 pass. Calibration should balance false positives and false negatives where feasible, with a mild preference against confident false positives.

---

## Evaluation

v3 needs category-aware evaluation.

### Overview

v3 evaluation must measure both model behavior and user-value behavior.

The model may predict exact `flag_id`s, but users care primarily about whether vexilloscope returns the correct result object and useful context. Therefore v3 evaluation separates:

```text
exact flag accuracy  -> model/debug metric
result accuracy      -> primary user-value metric
```

### Why It Matters

As v3 adds variants and multiple assets per result, exact visual correctness and answer correctness can diverge.

For example, predicting the state variant of a flag when the civil variant was shown may be an exact flag error, but if both map to the same result, the user may still get the answer they wanted. Conversely, predicting a visually similar flag from a different result is a more serious user-facing error.

Evaluation should make those differences visible.

Metrics should include:

- exact flag top-1 and top-3
- result top-1 and top-3
- current-only accuracy
- historical-only accuracy
- subnational-only accuracy
- fictional/unofficial accuracy if included
- no-flag false positive rate
- no-flag false negative rate
- confusable-pair accuracy
- calibration / margin between top results
- detector crop correctness where applicable

### Primary Metric

The primary v3 success metric is result-level accuracy.

```text
top-1 result accuracy
top-3 result accuracy
```

Exact flag accuracy remains important for model debugging:

```text
top-1 exact flag accuracy
top-3 exact flag accuracy
```

### Required Breakdowns

Evaluation should report metrics by:

```text
category
status
fictionality
variant
```

Examples:

```text
category=subnational
status=historical
fictionality=fictional
variant=military
```

This makes it clear whether regressions are broad or isolated to specific expansion families.

### No-Flag Metrics

Evaluation must include no-flag behavior:

```text
false positive rate
false negative rate
high-confidence false positives
threshold curves
```

High-confidence false positives should be tracked separately because they are the most harmful no-flag failure mode.

### Confusable Metrics

Known confusable groups should receive dedicated reporting.

Examples:

```text
ro,td
id,mc
pl,mc
ie,ci
au,nz
```

Confusable reporting should include both exact flag confusion and result-level confusion.

### Evaluation Sets

Initial v3 evaluation should use:

```text
eval_clean
  derived from reviewed trainable assets with minimal distortion

eval_augmented
  generated with expected Discord/screenshot-like distortion

eval_negative
  locally generated no-flag examples for threshold calibration
```

Later v3 should add:

```text
eval_realworld
  manually curated Discord-like images, screenshots, crops, and hard cases
```

### Detector/Crop Evaluation

For arbitrary images, evaluation should distinguish:

```text
correct result
reasonable crop
wrong crop but right result
right crop but wrong result
no flag detected correctly
missed flag
false positive on no-flag image
```

Manual review may be needed for crop correctness in early v3.

### Non-Goals

- Evaluation does not require a held-out class split.
- Evaluation does not replace QA.
- Evaluation does not need real-world Discord data before the first v3 baseline.
- Evaluation does not require architecture changes before metrics expose the need.

### Resolved Questions and Future Evaluation Questions

- Closed: result-level accuracy is the primary user-value metric; exact flag accuracy is a model/debug metric.
- Future evaluation question: what image set best represents real Discord usage.
- Future evaluation question: when to introduce a manually curated real-world validation set.
- Future evaluation question: what minimum metric improvement is required before accepting an architecture change.

### Decision

Closed: v3 evaluation reports exact flag metrics and result-level metrics separately. Result-level accuracy is the primary success metric for user value. Exact flag accuracy remains a model/debug metric. Evaluation must include category/status/fictionality/variant breakdowns, no-flag calibration metrics, confusable reporting, and separate clean, augmented, and negative evaluation sets.

---

## Confusables

v3 should maintain an explicit confusables registry.

### Overview

Confusables are flags or result objects that are visually similar enough to deserve special evaluation, review, or presentation handling.

They are not bad data. Many confusable flags are legitimate and important. The registry exists so v3 can treat them deliberately instead of discovering the same mistakes repeatedly.

Examples:

```text
ro,td
id,mc
pl,mc
ie,ci
lu,nl
au,nz
sl,si
ru,sk,si
```

Uses:

- focused evaluation
- oversampling
- targeted augmentation
- ambiguity-aware inference
- user-facing "visually similar to" notes

### Why It Matters

Flag recognition is unusually confusable:

- many flags share simple stripe layouts
- many flags differ only by small seals or emblems
- colonial, historical, and subnational flags often reuse templates
- variants can differ by tiny details
- screenshots and Discord compression destroy fine visual cues

As the label set expands, top-1 accuracy alone will hide important failures. A model that confuses Romania and Chad is making a different kind of mistake than one that confuses California and a fictional naval ensign.

### Constraints

- Confusables should not imply one record is wrong.
- Confusables should work at both `flag_id` and `result_id` levels.
- Confusables should feed evaluation before they feed training changes.
- Confusable groups should be reviewable and editable by humans.
- Automatically discovered confusables should be candidates until reviewed.

### Registry Shape

Suggested file:

```text
data/manifest/confusables.jsonl
```

Suggested record:

```json
{
  "confusable_id": "ro-td",
  "level": "result",
  "members": ["ro", "td"],
  "reason": "near-identical vertical tricolor",
  "source": "manual",
  "review_status": "reviewed"
}
```

Identical design example:

```json
{
  "confusable_id": "identical-x-y",
  "level": "flag",
  "relationship": "identical_design",
  "members": ["x-current", "y-historical"],
  "reason": "Same visual design associated with different results.",
  "source": "manual",
  "review_status": "reviewed"
}
```

Flag-level example:

```json
{
  "confusable_id": "au-nz-standard",
  "level": "flag",
  "members": ["au-current", "nz-current"],
  "reason": "blue ensigns with Union Jack and star fields",
  "source": "manual",
  "review_status": "reviewed"
}
```

### Source Types

Confusable candidates can come from:

```text
manual        -> human-authored known lookalikes
qa_similarity -> visual_similar output from dataset QA
model_confusion -> recurring evaluation confusion
user_report   -> future bot/user feedback
```

Only reviewed confusable groups should affect official eval reports or inference wording.

### Evaluation Use

Confusables should produce dedicated metrics:

```text
confusable top-1 accuracy
confusable top-3 accuracy
within-group confusion matrix
margin between correct result and nearest confusable
```

Evaluation should report whether an error stayed within a known confusable group or jumped to an unrelated result.

### Training Use

Confusables may later drive:

- oversampling
- targeted augmentation
- hard-negative-style pair mining
- resolution/patch-size experiments
- focused eval sets

Training use should follow evaluation evidence. The first v3 step is to track and report confusables, not to automatically rebalance training around them.

### Inference Use

Confusables may help explain ambiguity when top candidates are close.

Example:

```text
This looks most like Chad, but Romania is visually very similar and the confidence margin is small.
```

Inference should not always mention confusables. It should do so only when the model's ranked outputs and confidence/margin suggest a genuine ambiguity.

### Identical Flags

Some flags are not merely similar; they may be visually identical or effectively identical.

These require deliberate modeling:

- Identical visual designs are retained when they represent distinct meanings/results.
- v3 starts with separate `flag_id`s plus explicit `identical_design` relationships in the confusables registry.
- Duplicate assets with the same meaning are QA cleanup.
- QA should warn on visual matches across different results.

v3 does not start with one `flag_id` mapped to multiple results. That can be revisited later if inference needs justify it.

### Non-Goals

- Confusables do not replace category/status/fictionality metadata.
- Confusables do not mean one of the records should be removed.
- Confusables do not automatically change training weights.
- Confusables do not require user-facing ambiguity notes unless inference confidence warrants it.

### Resolved Questions

- Closed: confusables can be both hand-authored and discovered, but discovered groups are candidates until reviewed.
- Closed: identical designs with distinct meanings/results are retained as separate `flag_id`s with explicit `identical_design` relationships.
- Closed: the confusables registry lives under `data/manifest/confusables.jsonl`.

### Decision

Closed: v3 maintains an explicit reviewed confusables registry at `data/manifest/confusables.jsonl`. Confusables can be manual, QA-discovered, model-discovered, or future user-reported candidates. Reviewed confusables feed dedicated evaluation first and may later inform training or ambiguity-aware output. Similarity is not treated as bad data or automatic deletion. Identical visual designs are retained when they represent distinct meanings/results, using separate `flag_id`s plus explicit `identical_design` relationships.

---

## Model Direction

The current from-scratch ViT remains a good baseline. Model changes should follow dataset and evaluation improvements, not precede them.

### Overview

v3 should not start by replacing the model. The first priority is to build the manifest, import, QA, export, and evaluation backbone so model changes can be measured clearly.

The current ViT remains the baseline:

```text
128x128 input
8x8 patches
mean pooling
non-causal transformer encoder
single classifier head
```

Model experiments should be evidence-gated by v3 evaluation results.

### Why It Matters

Expanding the label set will introduce new failure modes:

- more visually similar classes
- more seal-heavy subnational flags
- more historical variants
- more uneven source coverage
- more false-positive opportunities

If architecture changes happen before the data/eval pipeline is stable, it will be hard to tell whether improvements or regressions came from the model, the data, the export, the detector, or the evaluation set.

### Constraints

- No external ML frameworks.
- Keep the model in C on top of otto-von-grad.
- Preserve non-causal attention.
- Do not reintroduce a class-split holdout as the main strategy.
- Keep the first v3 baseline compatible with current training/inference where practical.
- Architecture changes should have measurable eval justification.

Candidate experiments:

- stronger weight decay
- increased capacity
- longer training
- smaller patches or larger input resolution
- learned CLS token
- convolutional stem
- mixup or cutmix-style training
- class-balanced sampling
- hard-negative mining
- separate detector or flagness head

### Baseline-First Policy

The first v3 model baseline should use the existing architecture and the new v3 export.

Initial goal:

```text
same model family + v3 manifest/export/eval
```

This isolates the effect of the data pipeline and expanded labels before changing architecture.

### Evidence-Gated Experiments

Potential experiments and what would motivate them:

- **More training steps:** baseline underfits or improves steadily at end of training.
- **Class-balanced sampling:** uneven class/source coverage hurts expanded label performance.
- **Weight decay tuning:** overconfidence or overfitting appears in eval.
- **Higher input resolution:** seal-heavy or detail-heavy flags fail disproportionately.
- **Smaller patches:** fine detail matters and higher resolution alone is not enough.
- **Increased capacity:** broad underfitting across categories after data issues are controlled.
- **CLS token:** mean pooling appears weaker on fine-detail or localized-symbol flags.
- **Convolutional stem:** early patch embedding struggles with small emblems or local visual patterns.
- **Mixup/cutmix-style training:** robustness/confusables need improvement after simpler augmentation.
- **Flagness head or detector model:** no-flag threshold calibration is insufficient.

### Resolution Experiments

The v3 data-pipeline baseline may keep `128x128` for compatibility, but the v3 model target should seriously evaluate `256x256`. Seal-heavy, emblem-heavy, and near-confusable flags may need that resolution for meaningful discernment.

Current expected training machine:

```text
CPU: AMD Ryzen 9 7950X3D
RAM: 64 GB
GPU: NVIDIA GeForce RTX 4070 SUPER
VRAM: 12 GB dedicated GDDR6X
CUDA cores: 7168
```

This machine is strong enough to justify larger-input experiments, but 12 GB VRAM still makes token count important.

Patch-size implications:

```text
128x128 with 8x8 patches  -> 256 tokens
256x256 with 16x16 patches -> 256 tokens
256x256 with 8x8 patches  -> 1024 tokens
```

`256x256` with `8x8` patches greatly increases attention cost. `256x256` with `16x16` patches preserves the current token count while giving the patch projection access to higher-resolution image detail. Both should be evaluated rather than assumed.

Candidate future sizes:

```text
160
192
256
```

Resolution changes should be evaluated against detail-heavy categories, especially subnational, military, maritime, historical, and seal-heavy flags. The working hypothesis is that `256x256` is likely the minimum meaningful target for many seal/detail confusables, but this remains an evaluation question.

### Detector/Flagness Experiments

A `no_flag` class, flagness head, or dedicated detector should not be part of the first v3 model change.

Those become justified if:

- generated negative eval shows threshold calibration is insufficient
- high-confidence false positives remain common
- sliding-window crop selection frequently chooses wrong non-flag regions
- result accuracy is dominated by detector failures rather than classifier failures

### Non-Goals

- Do not replace the C/otto-von-grad model with an external framework.
- Do not change architecture before v3 baseline metrics exist.
- Do not optimize only exact flag accuracy at the expense of result-level accuracy.
- Do not train a no-flag model before negative eval demonstrates the need.
- Do not assume bigger model or higher resolution is automatically better.

### Evidence Questions

- **Closed (2026-05-21):** `256x256` with `16x16` patches was sufficient as a first meaningful improvement (top-1 +0.7 pp, HC-FP −4.7 pp vs 128×128 / 8×8 baseline). Smaller patches at 256×256 remain an open question for future confusable-heavy cases.
- What GPU memory and training time budget is acceptable on the RTX 4070 SUPER 12GB machine?
- Closed: v3 preserves the single-model classifier path initially.

### Suggested Direction

Use the existing ViT as the first v3 baseline. Let evaluation decide which model experiment comes next.

### Decision

Closed: v3 keeps the current ViT family as the first baseline and uses v3 data/export/evaluation before architecture changes. The working resolution hypothesis is that `256x256` may be needed for seal/detail confusables, with `256x256` + `16x16` patches as a practical first experiment on the RTX 4070 SUPER 12GB machine.

---

## Inference and Output

v3 output should remain scriptable while exposing richer meaning.

### Overview

v3 inference maps model predictions to ranked result objects.

Internal path:

```text
image -> detector/crop -> classifier logits -> flag_id ranking -> result_id ranking -> output
```

The user-facing answer should be generated from result metadata, not internal IDs. Machine-readable output should expose enough structure for the bot, CLI, eval tools, and future integrations.

Potential output concepts:

- exact match
- result match
- type and status
- parent hierarchy
- historical era
- source or variant note
- confidence / margin
- ambiguity warning
- no-flag result

The existing stdout contract should not be casually broken. If richer output is needed, prefer adding an optional machine-readable mode such as `--identify-json` while preserving current top-3 text output for the bot until the bot is updated deliberately.

### Why It Matters

The v2 text output is simple and useful, but v3 needs to communicate more:

- result metadata
- exact matched visual identity
- category/status/fictionality
- variant details
- confidence and margin
- ambiguity or identical-design relationships
- no-flag decisions

JSON output gives integrations a stable contract without forcing all of that into fragile text parsing.

### Compatibility Policy

Preserve existing text output until the bot is deliberately migrated.

Add a new JSON mode rather than changing the existing stdout format:

```text
--identify path\to\image.png       -> existing text contract
--identify-json path\to\image.png  -> structured JSON contract
```

The existing `no flag detected` text case remains intact for compatibility.

### JSON Output Shape

Suggested successful output:

```json
{
  "input_path": "path/to/image.png",
  "detected": true,
  "results": [
    {
      "rank": 1,
      "result_id": "us-ca",
      "display_name": "California",
      "category": "subnational",
      "fictionality": "nonfiction",
      "status": "current",
      "short_description": "Current state flag of California, United States.",
      "matched_flag_id": "us-ca-current",
      "matched_variant": "standard",
      "confidence": 0.92,
      "margin": 0.18
    }
  ],
  "detection": {
    "crop": {
      "x": 0,
      "y": 0,
      "width": 512,
      "height": 341
    },
    "score": 4.2
  }
}
```

Suggested no-flag output:

```json
{
  "input_path": "path/to/image.png",
  "detected": false,
  "results": [],
  "no_flag_reason": "below_threshold"
}
```

Allowed `no_flag_reason` values:

```text
below_threshold
no_detection
low_confidence
```

Field boundaries:

- `below_threshold`: the best candidate score did not clear the calibrated detection threshold.
- `no_detection`: no usable detection candidate was produced.
- `low_confidence`: a flag-like candidate existed, but final result confidence or margin was too weak to return a result.

### Result Ranking

JSON output should rank result objects, not raw assets.

If multiple top `flag_id`s map to the same `result_id`, the output should merge them into one result entry and preserve the best or relevant matched flag details.

Exact flag rankings may be included later for debug modes, but the default JSON contract should prioritize result objects.

### Ambiguity Handling

Ambiguity should be explicit when confidence/margin and confusable relationships warrant it.

Possible JSON field:

```json
{
  "ambiguity": {
    "type": "known_confusable",
    "message": "Top results are visually similar and confidence margin is small.",
    "related_result_ids": ["td", "ro"]
  }
}
```

Human-facing bot output might say:

```text
This looks most like Chad, but Romania is visually very similar and the margin is small.
```

Ambiguity should not be shown every time a flag has known confusables. It should require the model outputs to indicate uncertainty.

### Identical Design Handling

If the best match belongs to an `identical_design` relationship, output may include an explicit note.

Example:

```json
{
  "ambiguity": {
    "type": "identical_design",
    "message": "This visual design is associated with multiple results.",
    "related_result_ids": ["x", "y"]
  }
}
```

This is not a model failure; it is honest metadata.

### Bot Presentation

The bot should eventually consume `--identify-json` and generate concise human answers from result metadata.

Human-facing output should prioritize:

```text
display_name
short_description
status/category context
ambiguity note when warranted
limited trivia when useful
```

The bot should not display internal IDs unless explicitly in a debug/admin mode.

### Non-Goals

- Do not break existing text output without a compatibility path.
- Do not force all metadata into the text output.
- Do not expose source/license/debug fields to ordinary users by default.
- Do not always mention confusables; only mention ambiguity when warranted.
- Do not make the user interpret logits or internal IDs.

### Resolved Questions

- Closed: v3 adds `--identify-json` rather than changing the existing text contract.
- Closed: default JSON output ranks result objects and includes matched flag details.
- Closed: the bot should eventually consume JSON and present human-facing metadata, not internal IDs.
- Closed: ambiguity notes should appear only when model outputs and known relationships warrant them.

### Decision

Closed: v3 preserves the existing text identification contract and adds `--identify-json` for structured output. Default JSON output returns ranked result objects with matched flag details, detection metadata, confidence/margin information, and optional ambiguity notes. Human-facing presentation is generated from result metadata and should not display internal IDs by default.

---

## Repository and Artifact Layout

Potential v3 additions:

```text
data/
  manifest/
    results.jsonl
    flags.jsonl
    assets.jsonl
    confusables.jsonl
  sources/
    ...
  generated/
    renders/
    train/
    negative_eval/
scripts/
  import_*.py
  render_assets.py
  qa_dataset.py
  eval_report.py
reports/
  import/
  qa/
  eval/
```

### Overview

v3 needs a clear boundary between:

```text
canonical reviewed data
source assets
generated artifacts
reports
scripts
```

This keeps the repo understandable and prevents generated files from becoming accidental source truth.

### Layout Policy

#### Canonical Manifest Data

```text
data/manifest/
  results.jsonl
  flags.jsonl
  assets.jsonl
  confusables.jsonl
```

These files are canonical v3 metadata and should be committed.

#### Source Assets

```text
data/sources/
  <source_family>/
    ...
```

Source assets are curated inputs referenced by `assets.jsonl`.

Examples:

```text
data/sources/wikimedia/
data/sources/twemoji/
data/sources/current_flags/
```

Whether source assets are committed depends on size, license, and artifact policy. For early v3, small reviewed source SVGs are good candidates to commit; large generated or downloaded caches should not be committed by default.

#### Generated Artifacts

```text
data/generated/
  renders/
  train/
  negative_eval/
```

Generated artifacts are reproducible outputs.

Examples:

```text
data/generated/renders/          # local PNG renders from SVG/source assets
data/generated/train/labels.csv  # C-compatible training export
data/generated/train/images/     # normalized training images
data/generated/train/class_map.json
data/generated/negative_eval/    # generated no-flag calibration set
```

Generated artifacts should be ignored by git by default unless a specific snapshot is intentionally committed.

#### Reports

```text
reports/
  import/
  qa/
  eval/
```

Reports are outputs from import, QA, and evaluation runs.

Latest reports may be overwritten locally:

```text
reports/qa/latest.json
reports/qa/latest.md
```

Timestamped reports can be useful for debugging and comparison:

```text
reports/import/wikimedia/2026-05-18T120000.json
reports/eval/v3-baseline/...
```

Reports should generally be local artifacts unless a report snapshot is intentionally committed for a milestone.

#### Scripts

```text
scripts/
  migrate_labels_to_manifest.py
  import_*.py
  validate_manifest.py
  render_assets.py
  export_training_labels.py
  qa_dataset.py
  eval_report.py
```

Scripts should be committed and should make their input/output paths explicit.

### Commit Policy

Commit by default:

- manifest JSONL files
- source/import/render/export/eval scripts
- small hand-authored configuration files
- small curated source assets when license and size are acceptable

Ignore by default:

- generated renders
- generated training images
- generated negative eval images
- downloaded caches
- large raw source drops
- local reports
- model weights

Commit intentionally:

- milestone QA/eval reports
- small reproducibility fixtures
- curated source SVG snapshots if license and size are acceptable

### Artifact Ownership

Canonical files should be edited or reviewed deliberately:

```text
data/manifest/*.jsonl
data/sources/... curated assets
```

Generated files should be overwritten by scripts:

```text
data/generated/**
reports/**
```

No generated file should be required as the only source of truth.

### Non-Goals

- Do not commit generated training image trees by default.
- Do not treat reports as canonical metadata.
- Do not use generated PNGs as the source of truth when SVG/source assets exist.
- Do not require a database for v3 foundation.

### Resolved Questions

- Closed: generated renders, training images, negative eval images, downloaded caches, local reports, and model weights are ignored by default.
- Closed: manifest JSONL files and scripts are committed.
- Closed: small reviewed source SVGs may be committed when license and size are acceptable; larger source drops/caches are local or regenerated.
- Closed: reports are local artifacts by default, with intentional milestone snapshots allowed.

### Decision

Closed: v3 separates canonical manifest data, curated source assets, generated artifacts, reports, and scripts. Manifest JSONL and scripts are committed. Generated artifacts and local reports are ignored by default. Small reviewed source SVGs may be committed when license and size permit; generated PNGs are reproducible artifacts, not source truth.

---

## Planning Checklist

### Phase 0: Foundation Decisions

- [x] Choose manifest format.
- [x] Define required metadata fields.
- [x] Define result/flag/asset semantics.
- [x] Decide first expansion category.
- [x] Decide no-flag strategy for v3.
- [x] Decide evaluation strategy and validation data shape.

### Phase 1: Dataset Backbone

- [ ] Add v3 manifest schema.
- [ ] Add migration from current `labels.csv`.
- [ ] Add confusables registry.
- [ ] Add dataset QA report.
- [ ] Add source provenance validation.

### Phase 2: Source Expansion

- [ ] Import current national/territory flags into v3 manifest.
- [ ] Import one controlled expansion family.
- [ ] Review duplicate and provenance reports.
- [ ] Generate normalized training assets.

### Phase 3: Training and Evaluation

- [ ] Update dataset loader to consume v3 manifest or generated labels.
- [ ] Add category-aware eval reporting.
- [ ] Add confusable eval reporting.
- [ ] Add negative/no-flag eval.
- [ ] Establish v3 baseline metrics.

### Phase 4: Model and Inference Experiments

- [x] Calibrate detection thresholds with negatives. (threshold raised 20→35; deeper calibration deferred — threshold alone cannot solve HC-FP problem)
- [ ] Try class-balanced sampling. (deferred to Phase 5+; low expected value with single-source-dominated dataset)
- [x] Try resolution/patch/capacity experiments. (exp-256-p16 adopted 2026-05-21)
- [ ] Evaluate flagness head or separate detector. (deferred; separate spec required)
- [x] Add `--identify-json` structured output mode. (implemented 2026-05-21)

### Phase 5: Historical Flags and Bot Migration

- [x] Add `scripts/import_historical.py` and `scripts/historical_seed.csv` for Wikimedia-sourced historical national flags.
- [x] Import 16 initial historical flag records; promote all to `review_status=reviewed`, `trainable=true`; retrain to 322 classes.
- [x] Migrate `bot/bot.py` from `--identify` text parsing (RESULT_RE) to `--identify-json` structured output.
- [x] Add `--identify-json-batch <file>` for NDJSON batch inference.
- [x] Fix `VX_CODE_MAX` 16→64 to support flag IDs longer than 15 chars (e.g., `ca-red-ensign-1957`, `es-second-republic`).

---

## Non-Goals

- Expanding to arbitrary internet-sourced flags without provenance.
- Replacing the from-scratch C/otto-von-grad model with an external ML framework.
- Breaking existing `--identify` stdout without a compatibility path.
- Treating fictional, unofficial, or proposed flags as equivalent to current official flags without metadata.

---

## Document Revision History

### v2 — Phase 2 spec closure (2026-05-19)

**Trigger:** Phase 2 spec review (`SPEC_V3_PHASE2_SOURCES.md`) surfaced two problems in the v1 Foundation: a field-naming inconsistency that existed within v1 itself, and asset examples that used pre-decision placeholder values that were superseded by decisions Phase 2 closed. Both are corrected here so the Foundation remains the upstream source of truth rather than drifting behind the spec it governs.

**Changes:**

1. **`parent_id` → `parent_result_id` (Field Intent list and result object example block)**

   The v1 Field Intent prose and one illustrative example block used `parent_id`. The rest of v1 — including the `results.jsonl` schema block and all other examples — consistently used `parent_result_id`. Both Phase 1 and Phase 2 specs correctly inferred `parent_result_id` from the schema examples and never used `parent_id`. This is an internal v1 inconsistency; the correct field name was never in dispute. The Field Intent list and the affected example block now match the rest of the Foundation.

2. **Asset type, path, and ID in the `assets.jsonl` example (Dataset Manifest section) and the Asset Type Values section example**

   The v1 examples showed a Wikimedia asset as `asset_type: "source_render"` with a `.png` path and `asset_id: "us-ca-wikimedia-svg-render"`. These were pre-decision placeholders written before the Wikimedia source strategy was settled. Phase 2 (`SPEC_V3_PHASE2_SOURCES.md`, Source Policy and Importer Contract sections) closed the following decisions:

   - **SVG files downloaded from Wikimedia Commons are `source_original`.** The SVG is the authored original. PNG renders are reproducible generated artifacts placed under `data/generated/renders/` and are not manifest records. This is semantically consistent with the `source_render` definition in this document ("rasterized, normalized, or converted version of a source asset"): the render of an SVG is not the SVG itself.
   - **Asset ID convention for Wikimedia SVG assets:** `<flag_id>-wikimedia-svg` (e.g., `us-ca-current-wikimedia-svg`).
   - **Directory structure:** `data/sources/wikimedia/<import_family>/` (e.g., `data/sources/wikimedia/us_states/`), with the filename matching the flag ISO/admin code.

   The v1 examples have been updated to reflect these closed decisions. The rationale is recorded here rather than being embedded silently in the example values.

### v3 — Phase 5 completion (2026-05-22)

**Trigger:** v3 Phase 5 implemented per `SPEC_V3_PHASE5.md`. Three threads:

**Thread A — Historical flag import pipeline**

`scripts/import_historical.py` added following the `import_us_states.py` pattern. Reads a curated `scripts/historical_seed.csv`; never writes `results.jsonl`; downloads SVGs to `data/sources/wikimedia/historical/{flag_id}.svg`; `--force` unlocks overwriting reviewed records. 16 initial historical flags imported and promoted to `trainable=true`.

**Thread B — Bot migration to structured output**

`bot/bot.py` migrated from `--identify` text parsing (RESULT_RE regex) to `--identify-json` JSON parsing. Removes the fragile regex dependency; bot now consumes the structured `results[]` array directly.

**Thread C — Batch inference**

`--identify-json-batch <file>` added to `src/main.c`. `identify_flag_json_one` extracted as a static void helper (compact NDJSON, one line per image); `identify_flag_json` is a thin wrapper. Batch mode loads `class_meta.tsv` and `confusable_pairs.tsv` once, then loops over paths from the file.

**Breaking fix — `VX_CODE_MAX` 16→64**

`VxCountry.code[16]` held only 15 usable characters. `ca-red-ensign-1957` (18 chars) and `es-second-republic` (18 chars) were silently truncated, causing "missing flag image" errors at training time. `VX_CODE_MAX` bumped to 64 in `src/dataset.h`. All AGENTS.md references updated.

**Eval — exp-historical-16**

Retrained from scratch on 322 classes (255 Phase 1 + 51 US states + DC + 16 historical). Results:

| Metric | exp-historical-16 (322 classes) | exp-256-p16 baseline (306 classes) |
|---|---|---|
| Top-1 exact | 92.62% | 94.32% |
| Top-1 result-level | 93.13% | — |
| Top-3 | 97.55% | 97.96% |
| Historical flags top-1 | 98.44% | (not in baseline) |
| Current flags top-1 | 92.85% | 94.32% |

Regression on current flags (−1.47 pp exact) is consistent with the larger softmax head and some pre-existing weak classes. Historical flags performed better than current average (98.44%), expected given their visual distinctiveness. Known weak classes (bq-current, gb-nir-current, sh-current) were weak pre-Phase-5 and are not regressions introduced by the historical expansion.
