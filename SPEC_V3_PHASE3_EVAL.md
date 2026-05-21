# vexilloscope v3 Phase 3 Specification: Evaluation

> **Purpose:** Implementation specification for vexilloscope v3 Phase 3. Derived from `FOUNDATION_V3.md` and building on `SPEC_V3_PHASE1.md` and `SPEC_V3_PHASE2_SOURCES.md`. This document covers evaluation infrastructure only: category-aware reporting, confusable reporting, negative eval, and baseline establishment. Do not implement anything in a later phase from this document.

---

## 1. Purpose and Scope

Phase 3 adds the evaluation harness that makes v3 metrics meaningful. It replaces the flat aggregate accuracy printed by the C trainer with category-aware, confusable-aware, and no-flag-aware reports derived from manifest metadata. It produces the v3 baseline — the committed record of current model behavior that Phase 4 experiments must demonstrably improve upon.

**Phase 3 delivers:**

- Two small additions to `src/main.c`:
  - `--eval-dump <path>` flag: writes per-example prediction CSV after the existing `vit_eval()` loop
  - `--detect-threshold-x10 <int>` flag: overrides `VX_DETECT_THRESHOLD_X10` for a single `--identify` run
- `scripts/generate_negatives.py` — generates the local synthetic negative eval dataset
- `scripts/eval_report.py` — reads eval dump + class map + confusables and produces category-aware eval reports
- `scripts/eval_negatives.py` — sweeps detection thresholds over the negative dataset and produces a calibration report
- Updated `scripts/export_training.py` — augments the printed C trainer invocation with `--eval-dump`
- `data/generated/negative_eval/` — generated negative images (gitignored, reproducible from script)
- `reports/eval/<run_id>/eval.json` and `eval.md` — category-aware eval report (local artifact)
- `reports/eval/<run_id>/negatives.json` and `negatives.md` — negative eval and calibration report (local artifact)
- **Committed baseline snapshot:** `reports/eval/v3-baseline/` — all four report files committed as the Phase 3 milestone

**Phase 3 touches `src/main.c` for eval tooling only.** The two additions — `--eval-dump` and `--detect-threshold-x10` — are output and override flags that do not alter the model architecture, training loop, augmentation policy, optimizer, learning rate schedule, or any model hyperparameter. Phase 3's non-goal list explicitly excludes all such changes.

**Phase 3 does not touch:**

- Model architecture, patch size, input resolution, attention configuration, or capacity
- Training loop, optimizer, learning rate schedule, or augmentation policy
- `VX_DETECT_THRESHOLD_X10` constant value (analysis only; change is Phase 4)
- `--identify` stdout format (the existing top-3 text output is unchanged)
- The `--identify-json` output mode (deferred to Phase 4)
- The Discord bot
- `data/manifest/` records or `scripts/validate_manifest.py`
- `scripts/export_training.py` other than the printed C trainer invocation line
- Training on a `no_flag` class (deferred)

---

## 2. Foundation Decisions Summary

All decisions below are closed in `FOUNDATION_V3.md` and are not re-opened in this spec.

| Decision | Value |
|---|---|
| Primary eval metric | Result-level top-1 and top-3 accuracy |
| Secondary eval metric | Exact flag top-1 and top-3 accuracy (model/debug metric) |
| Required breakdowns | category, status, fictionality, variant from the manifest |
| Confusable eval | Within-group confusion matrices, top-1/top-3 per group, logit margin between correct answer and nearest confusable member |
| Only reviewed records participate | Yes; the eval dump covers exactly the classes in `class_map.json`, which only contains reviewed+trainable flags |
| No-flag strategy | Evaluation-first: generate locally, measure FP/FN rates, recommend threshold; do not change the threshold in Phase 3 |
| Negatives not in `assets.jsonl` | Generated negatives are reproducible local artifacts, not curated positive flag assets |
| Negative categories | Solid colors, gradients, stripes, noise, geometric shapes — no real photographs |
| Threshold calibration direction | Mild preference against confident false positives (Foundation §Negatives and Flagness) |
| Report location | `reports/eval/` |
| Baseline commit policy | `reports/eval/v3-baseline/` (all four report files) committed as Phase 3 milestone snapshot |

---

## 3. Repository Layout Changes

Phase 3 adds the following. Phase 1 and 2 files are unchanged unless noted.

```
vexilloscope/
  src/
    main.c                           # UPDATED: --eval-dump and --detect-threshold-x10
  data/
    generated/                       # GITIGNORED (unchanged)
      negative_eval/                 # NEW: gitignored generated negative images
        solid_color/
          0000.png ... 0099.png
        gradient/
          0000.png ... 0099.png
        stripes/
          0000.png ... 0149.png
        noise/
          0000.png ... 0099.png
        geometric/
          0000.png ... 0149.png
      train/
        eval_dump.csv                # NEW: gitignored eval prediction dump
  reports/
    eval/                            # NEW
      v3-baseline/                   # COMMITTED (milestone snapshot)
        eval.json
        eval.md
        negatives.json
        negatives.md
      <other-run-id>/                # LOCAL ONLY (gitignored by default)
        eval.json
        eval.md
        negatives.json
        negatives.md
  scripts/
    generate_negatives.py            # NEW
    eval_report.py                   # NEW
    eval_negatives.py                # NEW
    export_training.py               # UPDATED (printed invocation only)
```

---

## 4. C Binary: Eval Tooling Extensions

Phase 3 adds two optional flags to the C binary. Both are strictly output/override flags. Neither modifies the training loop, model weights, augmentation behavior, or any hyperparameter. The existing behavior when these flags are absent is unchanged.

### 4.1 `--eval-dump <path>`

**Mode:** Training mode (positional invocation, not `--identify` mode).

**Behavior:** After `vit_eval()` completes and prints its aggregate summary to stdout, the binary opens `<path>` for writing, writes the eval dump (see §5), and closes the file. The aggregate accuracy line already printed to stdout is unchanged.

**Argument position:** `--eval-dump <path>` may appear anywhere after the required positional arguments:

```powershell
.\build\vexilloscope.exe data/generated/train/labels.csv data/generated/train/images/ --eval-dump data/generated/train/eval_dump.csv
```

If the path's parent directory does not exist, the binary exits non-zero with a message naming the missing directory. It does not create intermediate directories.

If `--eval-dump` is provided without a following non-flag argument, the binary exits non-zero with a usage error.

**Scope:** The dump covers exactly the same augmented eval passes that `vit_eval()` already performs — one row per (class, augmented pass) pair. No additional inference is performed.

### 4.2 `--detect-threshold-x10 <int>`

**Mode:** Identify mode only (`--identify` is present).

**Behavior:** Overrides the compiled `VX_DETECT_THRESHOLD_X10` constant for this single binary invocation. The argument value must be a positive integer. If the value is not a valid positive integer, the binary exits non-zero with a usage error.

**Argument position:**

```powershell
.\build\vexilloscope.exe --labels data/generated/train/labels.csv --identify image.png --detect-threshold-x10 35
```

**Scope:** Applies only to the detection threshold comparison in the sliding-window scan. Does not affect classifier logits, top-3 output format, or any training behavior.

**Rationale:** `eval_negatives.py` needs to run `--identify` at multiple threshold values to produce a calibration curve. Recompiling for each threshold value is not practical. This flag provides an eval-only override without touching the constant used during training.

---

## 5. Eval Dump Format

`data/generated/train/eval_dump.csv` is a CSV file written by the C binary when `--eval-dump` is given.

### 5.1 File Format

- UTF-8 encoding, LF line endings.
- First line is a header: `aug_pass,true_class_id,pred1_class_id,pred1_logit,pred2_class_id,pred2_logit,pred3_class_id,pred3_logit`
- One row per (class, augmented pass) combination.
- Row count (excluding header): `n_classes × n_aug_passes`. At baseline: `306 × 8 = 2448`.
- Rows are written in training-eval order: outer loop over class index (0 to n_classes−1), inner loop over aug passes (0 to n_aug_passes−1).

### 5.2 Column Definitions

| Column | Type | Description |
|---|---|---|
| `aug_pass` | integer | Augmented pass index, 0-based. Range: `[0, n_aug_passes)`. |
| `true_class_id` | integer | Ground-truth class index as used by the C trainer. Indexes into `class_map.json`. |
| `pred1_class_id` | integer | Top-1 predicted class index. |
| `pred1_logit` | float | Raw logit score for `pred1_class_id`. Written with `%.6f` format. |
| `pred2_class_id` | integer | Top-2 predicted class index. |
| `pred2_logit` | float | Raw logit score for `pred2_class_id`. Written with `%.6f` format. |
| `pred3_class_id` | integer | Top-3 predicted class index. |
| `pred3_logit` | float | Raw logit score for `pred3_class_id`. Written with `%.6f` format. |

### 5.3 Notes

Class IDs in the dump are the same 0-based integer indices used by the C trainer. They map to `flag_id`, `result_id`, `category`, and all other manifest metadata via `class_map.json`.

CSV is used rather than JSONL because it is trivially writable from C without any JSON library, and Python's `csv` module parses it cleanly. The asymmetry with the manifest's JSONL format is intentional: the dump is generated by C; all analysis is performed by Python.

---

## 6. Negative Dataset: Recipe Families and Counts

`scripts/generate_negatives.py` produces 600 PNG images in `data/generated/negative_eval/`. All images are 512×512, reproducible with `--seed` (default: `42`). The 512×512 size matches the training export render resolution and is large enough for the sliding-window detector to operate.

### 6.1 Recipe Families

| Subdirectory | Count | Recipe description |
|---|---|---|
| `solid_color` | 100 | Flat single-color fills. Cover white, black, mid-gray, 16 named web colors (red, green, blue, yellow, cyan, magenta, orange, purple, navy, teal, olive, maroon, lime, aqua, silver, fuchsia), and the remainder as random RGB triples seeded from `--seed`. |
| `gradient` | 100 | Linear gradients between two randomly chosen hues. Orientations: horizontal (left-to-right), vertical (top-to-bottom), and diagonal (top-left to bottom-right). Hues are drawn from a uniform distribution over the color wheel, seeded from `--seed`. |
| `stripes` | 150 | Random stripe patterns of 2–8 stripes in horizontal, vertical, or diagonal orientations. Stripe widths are randomly proportioned. Colors are drawn from a uniform RGB distribution. These are not constrained to avoid known flag patterns; collision with real flags is negligible given the random colors and widths. |
| `noise` | 100 | Gaussian noise with σ ∈ {30, 60, 90} applied to solid color backgrounds (white, gray, black), salt-and-pepper noise at density ∈ {0.05, 0.15, 0.30}, and fully random per-pixel RGB noise. |
| `geometric` | 150 | Simple geometric shapes (filled circles, crosses, five-pointed stars, equilateral triangles, rectangles) centered on solid or gradient backgrounds. Shapes use a contrasting color from the background. Each image contains one or two shapes. |

### 6.2 File Naming

Images are named `NNNN.png` (zero-padded to 4 digits), starting from `0000.png` within each subdirectory. The sequence is deterministic given `--seed`. Existing files in the output directory are overwritten on each generation run.

### 6.3 Rationale

These recipe families cover the most common failure modes for sliding-window detectors on non-flag content: solid fills and gradients test whether uniform regions trigger detection; stripes test whether simple geometric regularity triggers false classification as a tricolor; noise tests detector robustness; geometric shapes test shape-based false triggering. None of these families include real photographs, real flags, maps, coats of arms, or screenshots, per the Foundation's scope constraint for Phase 3.

---

## 7. Eval Report: Metric Definitions

`scripts/eval_report.py` computes the following metrics from the eval dump, cross-referenced with `class_map.json` and `data/manifest/confusables.jsonl`.

### 7.1 Loading and Cross-Reference

1. Load `eval_dump.csv`. Each row is `(aug_pass, true_class_id, pred1_class_id, pred1_logit, pred2_class_id, pred2_logit, pred3_class_id, pred3_logit)`.
2. Load `class_map.json`. Build an index `class_map[class_id]` → `{flag_id, result_id, display_name, category, fictionality, status, variant}`.
3. Load `data/manifest/confusables.jsonl`. Only `review_status=reviewed` entries participate in confusable group metrics.

### 7.2 Per-Example Classification

For each row in the dump, compute:

| Quantity | Definition |
|---|---|
| `exact_top1` | `pred1_class_id == true_class_id` |
| `exact_top3` | `true_class_id ∈ {pred1_class_id, pred2_class_id, pred3_class_id}` |
| `result_top1` | `class_map[pred1_class_id].result_id == class_map[true_class_id].result_id` |
| `result_top3` | `class_map[true_class_id].result_id ∈ {class_map[pred[1,2,3]_class_id].result_id}` |

### 7.3 Aggregate Metrics

Top-1 and top-3 rates are computed as `count / n_examples` where `n_examples = n_classes × n_aug_passes`.

> **Note:** At the current 306-class Phase 1+2 dataset, every result has exactly one flag identity — `exact_top1 ≈ result_top1` and `exact_top3 ≈ result_top3`. The dual metrics are infrastructure for Phase 4+ expansion (historical variants, multiple flags per result), not a divergence signal at Phase 3 baseline.

### 7.4 Category, Status, Fictionality, and Variant Breakdowns

For each breakdown field (category, status, fictionality, variant), group eval rows by `class_map[true_class_id].<field>` and compute `exact_top1`, `exact_top3`, `result_top1`, `result_top3`, `n_classes`, and `n_examples` per group. Groups with zero classes are omitted from the report.

### 7.5 Confusable Group Metrics

For each `reviewed` confusable group in `confusables.jsonl`:

**Group membership:** Determined by `level`:
- `level=result`: a class belongs to the group if `class_map[class_id].result_id ∈ members`
- `level=flag`: a class belongs to the group if `class_map[class_id].flag_id ∈ members`

**Member classes:** Build `member_classes` — the list of `(id, class_id)` pairs for all classes in the group. Any member ID from `confusables.jsonl` that has no matching class in `class_map.json` is noted in the report as `unresolved_members` (this can happen legitimately if the referenced flag/result has `trainable=false` at the time of the eval run).

**Group examples:** All eval rows where `true_class_id` belongs to the group.

**Group metrics:**
- `result_top1` and `result_top3`: standard result-level top-1 and top-3 accuracy over group examples.
- `exact_top1` and `exact_top3`: standard exact-flag top-1 and top-3 accuracy over group examples.

**Within-group confusion matrix:**
- For each eval row where the true answer is in the group AND the top-1 prediction maps to a group member (possibly the same as the true answer): record a `(true_id, pred_id)` pair. For `level=result`, IDs are `result_id` values; for `level=flag`, IDs are `flag_id` values.
- The confusion matrix captures within-group confusion only. Errors that land outside the group are counted as correct-or-wrong at the group level but are not broken out in the within-group matrix.

**Logit margin to nearest confusable member:**
- Computed only for rows where the top-1 prediction is correct (same result or flag as true answer).
- `margin = pred1_logit − max(logit_of_pred[2,3] where that prediction maps to a different group member)`
- If no other group member appears in {pred2, pred3}: margin is `null`; the example is counted in `n_margin_not_in_top3`.
- For rows with wrong top-1 predictions: confusion is recorded in the confusion matrix; no margin is computed.

### 7.6 Per-Class Summary

A per-class summary is included for debugging. For each class_id, compute `exact_top1`, `exact_top3`, `result_top1`, `result_top3`, and `n_examples`. Sorted by `class_id` ascending.

### 7.7 High-Confidence Threshold

The eval report also computes `p25_correct_top1_logit`: the 25th percentile of `pred1_logit` among rows where `exact_top1=true`. This value is stored in the report and consumed by `eval_negatives.py` as the high-confidence FP threshold. It is self-calibrating — it tracks the model's actual score distribution across retraining and prevents stale hard-coded values from misclassifying model-confidence bands.

---

## 8. Eval Report: JSON Schema

### 8.1 `reports/eval/<run_id>/eval.json`

```json
{
  "version": 1,
  "generated_at": "<ISO 8601 timestamp>",
  "run_id": "v3-baseline",
  "class_map_path": "data/generated/train/class_map.json",
  "eval_dump_path": "data/generated/train/eval_dump.csv",
  "n_classes": 306,
  "n_aug_passes": 8,
  "n_examples": 2448,
  "p25_correct_top1_logit": 3.41,
  "metrics": {
    "exact_flag": {
      "top1": 0.9400,
      "top1_count": 2301,
      "top3": 0.9775,
      "top3_count": 2392
    },
    "result_level": {
      "top1": 0.9400,
      "top1_count": 2301,
      "top3": 0.9775,
      "top3_count": 2392
    }
  },
  "by_category": {
    "national": {
      "n_classes": 255,
      "n_examples": 2040,
      "exact_flag_top1": 0.9000,
      "exact_flag_top1_count": 1836,
      "exact_flag_top3": 0.9500,
      "exact_flag_top3_count": 1938,
      "result_top1": 0.9000,
      "result_top1_count": 1836,
      "result_top3": 0.9500,
      "result_top3_count": 1938
    },
    "subnational": {
      "n_classes": 51,
      "n_examples": 408,
      "exact_flag_top1": 0.0,
      "exact_flag_top1_count": 0,
      "exact_flag_top3": 0.0,
      "exact_flag_top3_count": 0,
      "result_top1": 0.0,
      "result_top1_count": 0,
      "result_top3": 0.0,
      "result_top3_count": 0
    }
  },
  "by_status": {
    "current": { "n_classes": 306, "n_examples": 2448, "exact_flag_top1": 0.94, "exact_flag_top1_count": 0, "exact_flag_top3": 0.0, "exact_flag_top3_count": 0, "result_top1": 0.94, "result_top1_count": 0, "result_top3": 0.0, "result_top3_count": 0 }
  },
  "by_fictionality": {
    "nonfiction": { "n_classes": 306, "n_examples": 2448, "exact_flag_top1": 0.94, "exact_flag_top1_count": 0, "exact_flag_top3": 0.0, "exact_flag_top3_count": 0, "result_top1": 0.94, "result_top1_count": 0, "result_top3": 0.0, "result_top3_count": 0 }
  },
  "by_variant": {
    "standard": { "n_classes": 306, "n_examples": 2448, "exact_flag_top1": 0.94, "exact_flag_top1_count": 0, "exact_flag_top3": 0.0, "exact_flag_top3_count": 0, "result_top1": 0.94, "result_top1_count": 0, "result_top3": 0.0, "result_top3_count": 0 }
  },
  "confusable_groups": [
    {
      "confusable_id": "ro-td",
      "level": "result",
      "members": ["ro", "td"],
      "member_classes": [
        {"id": "ro", "class_id": 183},
        {"id": "td", "class_id": 240}
      ],
      "unresolved_members": [],
      "n_examples": 16,
      "exact_top1": 0.875,
      "exact_top1_count": 14,
      "exact_top3": 1.0,
      "exact_top3_count": 16,
      "result_top1": 0.875,
      "result_top1_count": 14,
      "result_top3": 1.0,
      "result_top3_count": 16,
      "within_group_confusion": [
        {"true_id": "ro", "pred_id": "ro", "count": 7},
        {"true_id": "ro", "pred_id": "td", "count": 1},
        {"true_id": "td", "pred_id": "td", "count": 7},
        {"true_id": "td", "pred_id": "ro", "count": 1}
      ],
      "margin_stats": {
        "n_correct_top1": 14,
        "n_margin_computable": 10,
        "n_margin_not_in_top3": 4,
        "min_margin": 0.12,
        "mean_margin": 1.43,
        "max_margin": 3.87
      }
    }
  ],
  "per_class": [
    {
      "class_id": 0,
      "flag_id": "ad-current",
      "result_id": "ad",
      "category": "national",
      "fictionality": "nonfiction",
      "status": "current",
      "variant": "standard",
      "n_examples": 8,
      "exact_top1": 1.0,
      "exact_top1_count": 8,
      "exact_top3": 1.0,
      "exact_top3_count": 8,
      "result_top1": 1.0,
      "result_top1_count": 8,
      "result_top3": 1.0,
      "result_top3_count": 8
    }
  ]
}
```

#### Required top-level fields

| Field | Description |
|---|---|
| `version` | Schema version; currently `1`. |
| `generated_at` | ISO 8601 UTC timestamp. |
| `run_id` | String identifier for this eval run (e.g., `"v3-baseline"`). |
| `class_map_path` | Path to the class map used for this report, relative to repo root. |
| `eval_dump_path` | Path to the eval dump CSV used for this report, relative to repo root. |
| `n_classes` | Number of classes in the eval dump. |
| `n_aug_passes` | Number of augmented passes per class. |
| `n_examples` | Total row count in the eval dump: `n_classes × n_aug_passes`. |
| `p25_correct_top1_logit` | 25th percentile of `pred1_logit` for correctly-predicted top-1 examples. Used by `eval_negatives.py` as the high-confidence FP logit threshold. |
| `metrics` | Aggregate exact-flag and result-level metrics. |
| `by_category` | Per-category breakdown; keys are category values present in the class map. |
| `by_status` | Per-status breakdown. |
| `by_fictionality` | Per-fictionality breakdown. |
| `by_variant` | Per-variant breakdown. |
| `confusable_groups` | List of per-confusable-group metric objects (one per reviewed confusable entry). |
| `per_class` | List of per-class metric objects, sorted by `class_id` ascending. |

#### Breakdown entry fields

Each entry in `by_category`, `by_status`, `by_fictionality`, and `by_variant`:

| Field | Type | Description |
|---|---|---|
| `n_classes` | integer | Number of classes in this group. |
| `n_examples` | integer | Total eval rows for this group. |
| `exact_flag_top1` | float | Exact flag top-1 accuracy rate. |
| `exact_flag_top1_count` | integer | Number of exact flag top-1 hits. |
| `exact_flag_top3` | float | Exact flag top-3 accuracy rate. |
| `exact_flag_top3_count` | integer | Number of exact flag top-3 hits. |
| `result_top1` | float | Result-level top-1 accuracy rate. |
| `result_top1_count` | integer | Number of result-level top-1 hits. |
| `result_top3` | float | Result-level top-3 accuracy rate. |
| `result_top3_count` | integer | Number of result-level top-3 hits. |

#### Confusable group entry fields

| Field | Type | Description |
|---|---|---|
| `confusable_id` | string | From `confusables.jsonl`. |
| `level` | string | `"result"` or `"flag"`. |
| `members` | array | Member IDs from `confusables.jsonl`. |
| `member_classes` | array | List of `{id, class_id}` objects for each member found in `class_map.json`. |
| `unresolved_members` | array | Member IDs from `confusables.jsonl` not found in `class_map.json`. |
| `n_examples` | integer | Eval rows where the true class belongs to this group. |
| `exact_top1` | float | Exact flag top-1 accuracy over group examples. |
| `exact_top1_count` | integer | Count. |
| `exact_top3` | float | Exact flag top-3 accuracy over group examples. |
| `exact_top3_count` | integer | Count. |
| `result_top1` | float | Result top-1 accuracy over group examples. |
| `result_top1_count` | integer | Count. |
| `result_top3` | float | Result top-3 accuracy over group examples. |
| `result_top3_count` | integer | Count. |
| `within_group_confusion` | array | List of `{true_id, pred_id, count}` objects. IDs are `result_id` for `level=result`, `flag_id` for `level=flag`. Only rows where the top-1 prediction maps to a group member are included; errors outside the group are not shown here. |
| `margin_stats` | object | See field table above. |

#### `margin_stats` fields

| Field | Type | Description |
|---|---|---|
| `n_correct_top1` | integer | Rows where top-1 is correct (used as denominator for margin stats). |
| `n_margin_computable` | integer | Correct top-1 rows where a different group member appears in top-2 or top-3. |
| `n_margin_not_in_top3` | integer | Correct top-1 rows where no other group member appears in top-2 or top-3. |
| `min_margin` | float or null | Minimum `pred1_logit − nearest_confusable_logit` over computable rows; `null` if `n_margin_computable=0`. |
| `mean_margin` | float or null | Mean margin; `null` if `n_margin_computable=0`. |
| `max_margin` | float or null | Maximum margin; `null` if `n_margin_computable=0`. |

### 8.2 `reports/eval/<run_id>/eval.md`

A human-readable Markdown report derived from `eval.json`. Required sections:

```markdown
# Eval Report: <run_id>

Generated: <timestamp>
Classes: <n_classes>  Aug passes: <n_aug_passes>  Examples: <n_examples>

## Aggregate Metrics

| Metric | Top-1 | Top-3 |
|---|---|---|
| Exact flag | 94.00% (2301/2448) | 97.75% (2392/2448) |
| Result level | 94.00% (2301/2448) | 97.75% (2392/2448) |

## By Category

| Category | Classes | Top-1 Result | Top-3 Result |
|---|---|---|---|
| national | 255 | 94.32% | 97.80% |
| subnational | 51 | 90.20% | 96.32% |

## By Status

...

## By Fictionality

...

## By Variant

...

## Confusable Groups

### ro-td (result-level, 2 members)

Top-1: 87.5% (14/16)   Top-3: 100.0% (16/16)
Margin stats: min=0.12  mean=1.43  max=3.87  (10/14 computable, 4 not in top-3)

Within-group confusion (top-1):
| True \ Pred | ro | td |
|---|---|---|
| ro | 7 | 1 |
| td | 1 | 7 |

...

## Per-Class Summary

(Full table: class_id, flag_id, result_id, category, exact_top1, result_top1)
```

The `by_status`, `by_fictionality`, and `by_variant` sections follow the same table format as `by_category`. Sections with only one populated group value (e.g., all classes have `status=current` at baseline) are included but note the single value.

---

## 9. Negative Eval Report: JSON Schema

### 9.1 `reports/eval/<run_id>/negatives.json`

```json
{
  "version": 1,
  "generated_at": "<ISO 8601 timestamp>",
  "run_id": "v3-baseline",
  "binary_path": ".\\build\\Release\\vexilloscope.exe",
  "labels_path": "data/generated/train/labels.csv",
  "negative_dir": "data/generated/negative_eval",
  "fn_image_dir": "data/generated/train/images",
  "high_confidence_logit_threshold": 3.41,
  "high_confidence_threshold_source": "p25_correct_top1_logit_from_eval_report",
  "n_negatives": 600,
  "n_fn_images": 306,
  "threshold_sweep": [
    {
      "threshold_x10": 20,
      "fp_count": 87,
      "fp_rate": 0.1450,
      "high_confidence_fp_count": 12,
      "high_confidence_fp_rate": 0.0200,
      "fn_count": 0,
      "fn_rate": 0.0000
    },
    {
      "threshold_x10": 25,
      "fp_count": 52,
      "fp_rate": 0.0867,
      "high_confidence_fp_count": 6,
      "high_confidence_fp_rate": 0.0100,
      "fn_count": 0,
      "fn_rate": 0.0000
    },
    {
      "threshold_x10": 30,
      "fp_count": 21,
      "fp_rate": 0.0350,
      "high_confidence_fp_count": 2,
      "high_confidence_fp_rate": 0.0033,
      "fn_count": 0,
      "fn_rate": 0.0000
    },
    {
      "threshold_x10": 35,
      "fp_count": 8,
      "fp_rate": 0.0133,
      "high_confidence_fp_count": 0,
      "high_confidence_fp_rate": 0.0000,
      "fn_count": 0,
      "fn_rate": 0.0000
    },
    {
      "threshold_x10": 40,
      "fp_count": 3,
      "fp_rate": 0.0050,
      "high_confidence_fp_count": 0,
      "high_confidence_fp_rate": 0.0000,
      "fn_count": 0,
      "fn_rate": 0.0000
    },
    {
      "threshold_x10": 45,
      "fp_count": 1,
      "fp_rate": 0.0017,
      "high_confidence_fp_count": 0,
      "high_confidence_fp_rate": 0.0000,
      "fn_count": 2,
      "fn_rate": 0.0065
    }
  ],
  "per_recipe": {
    "solid_color": {"n": 100, "fp_count_at_base": 0, "fp_rate_at_base": 0.0},
    "gradient": {"n": 100, "fp_count_at_base": 1, "fp_rate_at_base": 0.01},
    "stripes": {"n": 150, "fp_count_at_base": 2, "fp_rate_at_base": 0.0133},
    "noise": {"n": 100, "fp_count_at_base": 0, "fp_rate_at_base": 0.0},
    "geometric": {"n": 150, "fp_count_at_base": 0, "fp_rate_at_base": 0.0}
  },
  "false_positives_at_base": [
    {
      "image_path": "data/generated/negative_eval/stripes/0042.png",
      "recipe": "stripes",
      "predicted_flag_id": "nl-current",
      "predicted_result_id": "nl",
      "predicted_display_name": "Netherlands",
      "top1_logit": 2.14,
      "is_high_confidence": false
    }
  ],
  "recommendation": {
    "base_threshold_x10": 40,
    "base_fp_rate": 0.0050,
    "base_high_confidence_fp_rate": 0.0000,
    "base_fn_rate": 0.0000,
    "recommended_threshold_x10": 30,
    "recommendation_basis": "lowest_threshold_meeting_targets",
    "targets": {
      "fp_rate_ceiling": 0.05,
      "high_confidence_fp_rate_ceiling": 0.01
    },
    "note": "Current threshold already meets both targets. Recommended value is the most lenient threshold that still meets both targets, preserving maximum flag detection sensitivity."
  }
}
```

#### Top-level required fields

| Field | Type | Description |
|---|---|---|
| `version` | integer | Schema version; currently `1`. |
| `generated_at` | string | ISO 8601 UTC timestamp. |
| `run_id` | string | Eval run identifier. |
| `binary_path` | string | Path to the C binary used. |
| `labels_path` | string | Path to the labels CSV used for `--identify`. |
| `negative_dir` | string | Path to the negative dataset root. |
| `fn_image_dir` | string or null | Path to positive flag images used for FN measurement; `null` if not provided. |
| `high_confidence_logit_threshold` | float | Logit threshold above which a false positive is classified as high-confidence. Set from `p25_correct_top1_logit` in the eval report when `--eval-report` is provided; otherwise falls back to `2.0`. |
| `high_confidence_threshold_source` | string | `"p25_correct_top1_logit_from_eval_report"` or `"default_2.0"`. |
| `n_negatives` | integer | Total number of negative images evaluated. |
| `n_fn_images` | integer or null | Number of positive flag images evaluated for FN; `null` if not measured. |
| `threshold_sweep` | array | One entry per threshold value tested; see below. |
| `per_recipe` | object | Per-recipe FP counts and rates **at the base threshold only**. |
| `false_positives_at_base` | array | Full record for each false positive at the base threshold. |
| `recommendation` | object | Calibration recommendation. |

#### Threshold sweep entry fields

| Field | Type | Description |
|---|---|---|
| `threshold_x10` | integer | The `--detect-threshold-x10` value used. |
| `fp_count` | integer | Number of negative images that produced a flag detection. |
| `fp_rate` | float | `fp_count / n_negatives`. |
| `high_confidence_fp_count` | integer | FP images where top-1 logit ≥ `high_confidence_logit_threshold`. |
| `high_confidence_fp_rate` | float | `high_confidence_fp_count / n_negatives`. |
| `fn_count` | integer or null | Number of positive images that returned "no flag detected"; `null` if `fn_image_dir` not provided. |
| `fn_rate` | float or null | `fn_count / n_fn_images`; `null` if not measured. |

#### `per_recipe` entry fields

| Field | Type | Description |
|---|---|---|
| `n` | integer | Count of images in this recipe family. |
| `fp_count_at_base` | integer | FP count at the base (current compiled) threshold. |
| `fp_rate_at_base` | float | FP rate at the base threshold. |

#### `false_positives_at_base` entry fields

| Field | Type | Description |
|---|---|---|
| `image_path` | string | Path to the negative image, relative to repo root. |
| `recipe` | string | Recipe family subdirectory name. |
| `predicted_flag_id` | string | `flag_id` from the `--identify` output (first token of `#1` line). |
| `predicted_result_id` | string or null | `result_id` from `class_map.json`; `null` if the predicted `flag_id` is not in the class map. |
| `predicted_display_name` | string or null | `display_name` from `class_map.json`; `null` if not found. |
| `top1_logit` | float | Logit value from the `--identify` output `#1` line. |
| `is_high_confidence` | boolean | `top1_logit ≥ high_confidence_logit_threshold`. |

#### `recommendation` fields

| Field | Type | Description |
|---|---|---|
| `base_threshold_x10` | integer | The compiled `VX_DETECT_THRESHOLD_X10` value at the time of the run. Passed via `--threshold-x10-base`. |
| `base_fp_rate` | float | FP rate at the base threshold. |
| `base_high_confidence_fp_rate` | float | High-confidence FP rate at the base threshold. |
| `base_fn_rate` | float or null | FN rate at the base threshold; `null` if not measured. |
| `recommended_threshold_x10` | integer | Recommended new value. See §9.2. |
| `recommendation_basis` | string | One of: `"lowest_threshold_meeting_targets"`, `"highest_swept_value_best_tradeoff"`, `"no_change_needed"`. |
| `targets` | object | The FP and high-confidence FP rate ceilings used for the recommendation. |
| `note` | string | Human-readable explanation. |

### 9.2 Recommendation Logic

The recommendation is computed as follows:

**Targets:** `fp_rate ≤ 0.05` AND `high_confidence_fp_rate ≤ 0.01`.

**Algorithm:**
1. Collect all threshold values in the sweep where both targets are met AND (fn_rate is null OR fn_rate ≤ 0.02).
2. If such values exist: `recommended_threshold_x10 = min(qualifying_values)`. Basis: `"lowest_threshold_meeting_targets"` (most lenient threshold that still meets both targets — preserves maximum flag detection sensitivity). If `recommended_threshold_x10 == base_threshold_x10`, basis is `"no_change_needed"`.
3. If no swept value meets both targets: `recommended_threshold_x10 = min(values where high_confidence_fp_rate is minimized)`. Basis: `"highest_swept_value_best_tradeoff"`. Foundation preference is for low confident false positives; when targets cannot be met, minimize high-confidence FP rate.

### 9.3 `reports/eval/<run_id>/negatives.md`

A human-readable Markdown report. Required sections:

```markdown
# Negative Eval Report: <run_id>

Generated: <timestamp>
Negatives: <n_negatives>   FN images: <n_fn_images or "not measured">
High-confidence threshold: <value> (<source>)

## Threshold Sweep

| threshold_x10 | FP rate | HC-FP rate | FN rate |
|---|---|---|---|
| 20 | 14.50% | 2.00% | 0.00% |
| ...                                      |
| 40 | 0.50% | 0.00% | 0.00% | ← base |

## Per-Recipe (at base threshold)

| Recipe | N | FP count | FP rate |
|---|---|---|---|
| solid_color | 100 | 0 | 0.00% |
| ...                    |

## False Positives at Base Threshold

(list or "(none)")

## Recommendation

Recommended threshold_x10: <value> (basis: <basis>)
Note: <note>
```

---

## 10. Baseline Metrics Policy and Phase 4 Gate

### 10.1 What Constitutes the v3 Baseline

The v3 baseline is a complete, committed eval snapshot taken from a fully trained 306-class model. It is valid when all of the following hold:

1. The model was trained to completion on `data/generated/train/labels.csv` with all 306 reviewed+trainable classes (Phase 1 + Phase 2).
2. The eval dump (`data/generated/train/eval_dump.csv`) was generated by the same binary/weights that produced the training run's final aggregate accuracy output. Do not mix dumps from different model checkpoints.
3. `eval_report.py` was run on that dump with the current `class_map.json` and `data/manifest/confusables.jsonl`. All 8 reviewed confusable entries from `confusables.jsonl` must appear in `confusable_groups`.
4. `generate_negatives.py` was run with `--seed 42` (the default) to produce `data/generated/negative_eval/` with exactly 600 images.
5. `eval_negatives.py` was run with `--eval-report reports/eval/v3-baseline/eval.json` so that `high_confidence_logit_threshold` is derived from `p25_correct_top1_logit` rather than the default fallback.
6. All four report files (`eval.json`, `eval.md`, `negatives.json`, `negatives.md`) are present in `reports/eval/v3-baseline/`.

### 10.2 Committed Baseline Files

The following files are **committed** as the Phase 3 milestone:

```
reports/eval/v3-baseline/eval.json
reports/eval/v3-baseline/eval.md
reports/eval/v3-baseline/negatives.json
reports/eval/v3-baseline/negatives.md
```

All other eval run directories under `reports/eval/` are local artifacts and are gitignored by default.

### 10.3 Phase 4 Gate

Phase 4 model experiments are justified when all of the following are true:

1. `reports/eval/v3-baseline/` is committed and the four baseline report files are present and parseable.
2. The following headline metrics from `eval.json` are documented (the actual values come from the baseline run): aggregate result-level top-1 and top-3, aggregate exact-flag top-1 and top-3, subnational breakdown result-level top-1, and the weakest confusable group (lowest `result_top1` across all groups).
3. The following headline metrics from `negatives.json` are documented: FP rate and high-confidence FP rate at the base threshold, recommended `threshold_x10` value.
4. At least one specific measurable weakness is identified as the target of the next Phase 4 experiment. "Overall accuracy is lower than v2" or "subnational accuracy is below 80%" are valid targets. "General improvement" is not.

### 10.4 Eval Report Versioning

When subsequent Phase 4 experiments produce new model checkpoints, re-running `eval_report.py` and `eval_negatives.py` with `--run-id <experiment-name>` creates new local report directories. These are not committed unless they represent a new milestone. The v3-baseline reports are never overwritten.

---

## 11. Script Contracts

### `scripts/generate_negatives.py`

```
python scripts/generate_negatives.py [--output data/generated/negative_eval] [--seed 42] [--count-stripes 150] [--count-geometric 150] [--count-other 100]
```

- Generates exactly `n` images per recipe family in subdirectories of `--output`. Default counts: `solid_color=100`, `gradient=100`, `stripes=150`, `noise=100`, `geometric=150` (600 total). The `--count-stripes` and `--count-geometric` flags override the two higher-count families; `--count-other` overrides the remaining three families uniformly.
- All images are 512×512 PNGs with white background where applicable.
- Uses Pillow for image generation. No other non-standard library dependencies.
- Overwrites existing files in the output directory without prompting.
- `--seed <int>`: global random seed for reproducibility (default: `42`). Applies to all recipe families.
- Prints per-recipe count and output path on completion.
- Exits non-zero if Pillow is unavailable or any image write fails.

### `scripts/eval_report.py`

```
python scripts/eval_report.py
    --eval-dump data/generated/train/eval_dump.csv
    --class-map data/generated/train/class_map.json
    [--confusables data/manifest/confusables.jsonl]
    [--run-id v3-baseline]
    [--output reports/eval/v3-baseline]
```

- `--eval-dump`: required. Path to the eval dump CSV produced by the C binary.
- `--class-map`: required. Path to `class_map.json`.
- `--confusables`: optional; defaults to `data/manifest/confusables.jsonl` relative to repo root. Only `review_status=reviewed` entries are used.
- `--run-id`: optional; defaults to `"unnamed"`. Used in report metadata and as the default output directory name.
- `--output`: optional; defaults to `reports/eval/<run_id>` relative to repo root. Created if it does not exist.
- Validates that `n_classes` from the eval dump matches `class_map.n_classes`. Exits non-zero if they differ.
- Writes `<output>/eval.json` and `<output>/eval.md`.
- Prints a one-line summary to stdout: `"Run <run_id>: result_top1=X.XX% exact_top1=X.XX% n_classes=306 n_confusable_groups=8"`.
- Exits `0` on success, non-zero on any error.
- Dependencies: `json`, `csv`, `pathlib`, `argparse`, `collections`, `statistics` (all standard library). No new entries needed in `requirements.txt`.

### `scripts/eval_negatives.py`

```
python scripts/eval_negatives.py
    --binary .\build\Release\vexilloscope.exe
    --labels data/generated/train/labels.csv
    --threshold-x10-base <int>
    [--negative-dir data/generated/negative_eval]
    [--fn-image-dir data/generated/train/images]
    [--eval-report reports/eval/v3-baseline/eval.json]
    [--run-id v3-baseline]
    [--output reports/eval/v3-baseline]
    [--sweep-step 5]
    [--sweep-range 20]
    [--limit N]
```

- `--binary`: required. Path to the C binary. On Windows, must be a path to the built `.exe`.
- `--labels`: required. Path to the labels CSV, passed to each `--identify` invocation.
- `--threshold-x10-base`: required. The current compiled `VX_DETECT_THRESHOLD_X10` value. There is no default; this must be supplied explicitly by reading the constant from `src/main.c` to prevent stale hardcoding.
- `--negative-dir`: optional; defaults to `data/generated/negative_eval` relative to repo root. Recursively finds all `*.png` files.
- `--fn-image-dir`: optional. When provided, also runs `--identify` on all `*.png` files in this directory to measure FN rate across the threshold sweep. If omitted, `fn_count` and `fn_rate` are `null` throughout the report.
- `--eval-report`: optional. When provided, reads `p25_correct_top1_logit` from this JSON file to set `high_confidence_logit_threshold`. When omitted, falls back to `2.0` with `high_confidence_threshold_source="default_2.0"` and a warning printed to stderr.
- `--run-id` and `--output`: same semantics as `eval_report.py`.
- `--sweep-step`: threshold step size in `threshold_x10` units; default `5`.
- `--sweep-range`: sweep from `base - sweep_range` to `base + sweep_range`; default `20`. Any computed threshold_x10 value below 5 is clamped to 5 (the binary rejects non-positive values).
- `--limit N`: process only the first N negative images per recipe family (for smoke testing). When provided, notes the limit in the report and prints a warning that results are not representative.
- Invokes the C binary as a subprocess for each image and threshold value: `<binary> --labels <labels> --identify <image> --detect-threshold-x10 <value>`. Parses stdout.
- **Stdout parsing:** A detection is a flag identification if and only if the first non-blank line of stdout does NOT start with `"no flag detected"`. If a detection occurs, parse the `#1` line to extract `flag_id` (second whitespace-separated token on the line) and `logit` (float following `"logit: "`).
- Sweeps are run in order from lowest to highest `threshold_x10`. For each threshold, all negatives (and fn-image-dir images, if provided) are re-evaluated.
- Writes `<output>/negatives.json` and `<output>/negatives.md`.
- Prints a one-line summary: `"Negatives: N  FP@base=X.X%  HC-FP@base=X.X%  FN@base=X.X%  Recommended threshold_x10=N"`.
- Exits `0` on success, non-zero on any error.
- Dependencies: `subprocess`, `json`, `pathlib`, `argparse`, `re`, `collections` (all standard library). No new entries needed in `requirements.txt`.

### Updated `scripts/export_training.py`

The only change from Phase 2: the printed C trainer invocation now appends `--eval-dump data/generated/train/eval_dump.csv`:

```
C trainer invocation:
.\build\vexilloscope.exe data/generated/train/labels.csv data/generated/train/images/ --eval-dump data/generated/train/eval_dump.csv
```

No other changes to export logic, file structure, or report format. If secondary asset directories are also present, they appear before `--eval-dump`:

```
.\build\vexilloscope.exe data/generated/train/labels.csv data/generated/train/images/ data/generated/train/images_wiki/ --eval-dump data/generated/train/eval_dump.csv
```

The `--eval-dump` argument is always appended last.

---

## 12. Gitignore Updates

Add the following entries to `.gitignore`:

```
data/generated/negative_eval/
data/generated/train/eval_dump.csv
reports/eval/
```

**Exception for the baseline:** `reports/eval/v3-baseline/` is committed intentionally by adding a `.gitkeep`-style overriding allowlist in `.gitignore`:

```
# Allow the committed baseline snapshot
!reports/eval/v3-baseline/
!reports/eval/v3-baseline/eval.json
!reports/eval/v3-baseline/eval.md
!reports/eval/v3-baseline/negatives.json
!reports/eval/v3-baseline/negatives.md
```

`data/generated/` is already in `.gitignore` (added in Phase 1), which covers `data/generated/negative_eval/` and `data/generated/train/eval_dump.csv`. The explicit entries above are redundant but clarifying; the `reports/eval/` entry is new.

---

## 13. Phase 3 Verification Checklist

All items must pass before Phase 3 is declared complete.

### C Changes

- [ ] `src/main.c` compiles cleanly with `cmake --build build --config Release` after the `--eval-dump` addition.
- [ ] `src/main.c` compiles cleanly with `cmake -B build -DOVG_CUDA=ON -G Ninja && cmake --build build` after both additions.
- [ ] Running the C trainer with `--eval-dump` produces `data/generated/train/eval_dump.csv`:
  ```powershell
  .\build\Release\vexilloscope.exe data/generated/train/labels.csv data/generated/train/images/ --eval-dump data/generated/train/eval_dump.csv
  ```
- [ ] `eval_dump.csv` has a header line followed by exactly `n_classes × n_aug_passes` data rows (at least 2448 rows for 306 classes × 8 passes).
- [ ] The aggregate accuracy line printed to stdout by the C trainer is unchanged from before the `--eval-dump` addition.
- [ ] Running `--identify` with `--detect-threshold-x10 99999` on a known flag image produces `no flag detected` (verifies the override is applied):
  ```powershell
  .\build\Release\vexilloscope.exe --labels data/generated/train/labels.csv --identify data/generated/train/images/de-current.png --detect-threshold-x10 99999
  ```
- [ ] Running `--identify` without `--detect-threshold-x10` produces the standard `#1 / #2 / #3` output (verifies the override is additive and the default behavior is preserved):
  ```powershell
  .\build\Release\vexilloscope.exe --labels data/generated/train/labels.csv --identify data/generated/train/images/de-current.png
  ```

### Negative Dataset

- [ ] `python scripts/generate_negatives.py` completes without error.
- [ ] `data/generated/negative_eval/` contains exactly 5 subdirectories: `solid_color`, `gradient`, `stripes`, `noise`, `geometric`.
- [ ] Total PNG count: `solid_color=100`, `gradient=100`, `stripes=150`, `noise=100`, `geometric=150` (600 total).
- [ ] Re-running `generate_negatives.py` with the same `--seed` produces identical files (reproducibility check: SHA-256 of one sample file matches between runs).
- [ ] All generated images open as valid 512×512 PNGs in Pillow.

### Eval Report (positive eval)

- [ ] `python scripts/eval_report.py --eval-dump data/generated/train/eval_dump.csv --class-map data/generated/train/class_map.json --run-id v3-baseline --output reports/eval/v3-baseline` completes without error.
- [ ] `reports/eval/v3-baseline/eval.json` is written and parseable.
- [ ] `eval.json` field `n_classes` matches `class_map.json` field `n_classes`.
- [ ] `eval.json` field `n_examples` equals `n_classes × n_aug_passes`.
- [ ] `eval.json` `by_category` contains entries for both `national` and `subnational`.
- [ ] `eval.json` `confusable_groups` contains exactly 8 entries (matching the 8 reviewed entries in `data/manifest/confusables.jsonl`).
- [ ] Each confusable group entry has `unresolved_members = []` (all confusable members are present in `class_map.json`).
- [ ] `eval.json` `p25_correct_top1_logit` is a positive finite float.
- [ ] `reports/eval/v3-baseline/eval.md` is written and contains all required sections (Aggregate Metrics, By Category, By Status, By Fictionality, By Variant, Confusable Groups, Per-Class Summary).
- [ ] The aggregate `result_top1` in `eval.json` matches (within 0.01%) the top-1 figure printed by the C trainer during the training run that produced the eval dump.

### Negative Eval

- [ ] Read `VX_DETECT_THRESHOLD_X10` from `src/main.c`. Record the integer value; it will be passed as `--threshold-x10-base`.
- [ ] `python scripts/eval_negatives.py --binary .\build\Release\vexilloscope.exe --labels data/generated/train/labels.csv --threshold-x10-base <value> --fn-image-dir data/generated/train/images --eval-report reports/eval/v3-baseline/eval.json --run-id v3-baseline --output reports/eval/v3-baseline` completes without error.
- [ ] `reports/eval/v3-baseline/negatives.json` is written and parseable.
- [ ] `negatives.json` field `n_negatives` is 600.
- [ ] `negatives.json` field `n_fn_images` is 306.
- [ ] `negatives.json` field `high_confidence_threshold_source` is `"p25_correct_top1_logit_from_eval_report"` (not the fallback).
- [ ] `negatives.json` `threshold_sweep` contains at least 9 entries (from `base-20` to `base+20` in steps of 5).
- [ ] `negatives.json` `base_threshold_x10` matches the value passed as `--threshold-x10-base`.
- [ ] `negatives.json` `recommendation.recommended_threshold_x10` is present and is a positive integer.
- [ ] `reports/eval/v3-baseline/negatives.md` is written and contains all required sections.
- [ ] Smoke test with `--limit 10` to verify the binary invocation and stdout parsing work before the full sweep:
  ```powershell
  python scripts/eval_negatives.py --binary .\build\Release\vexilloscope.exe --labels data/generated/train/labels.csv --threshold-x10-base <value> --eval-report reports/eval/v3-baseline/eval.json --run-id smoke --output reports/eval/smoke --limit 10
  ```

### Baseline Commit

- [ ] All four report files exist in `reports/eval/v3-baseline/`: `eval.json`, `eval.md`, `negatives.json`, `negatives.md`.
- [ ] `.gitignore` contains `reports/eval/` with the `!reports/eval/v3-baseline/` override pattern.
- [ ] `git status` shows the four v3-baseline files as new tracked files (not gitignored).
- [ ] The Phase 4 Gate checklist from §10.3 is satisfied: headline metrics from both reports are recorded in the commit message or a short note.

### Updated Export Invocation

- [ ] `python scripts/export_training.py` prints a C trainer invocation that ends with `--eval-dump data/generated/train/eval_dump.csv`.

### Gitignore

- [ ] `data/generated/negative_eval/` is not tracked by git.
- [ ] `data/generated/train/eval_dump.csv` is not tracked by git.
- [ ] `reports/eval/v3-baseline/` IS tracked by git after the explicit allowlist is added.
- [ ] `reports/eval/<other-run-id>/` is gitignored for any run ID other than `v3-baseline`.

### No Regressions

- [ ] `python scripts/validate_manifest.py` exits 0 (no blockers) after Phase 3 changes.
- [ ] `python scripts/export_training.py` exits 0 and produces 306 classes.
- [ ] `.\build\Release\vexilloscope.exe --labels data/generated/train/labels.csv --identify data/generated/train/images/de-current.png` produces `#1 de-current Germany logit: <score>` with the expected format (unchanged from pre-Phase-3).

---

## 14. Explicit Non-Goals

The following are explicitly out of scope for Phase 3. Do not implement or speculate on them here.

- **`VX_DETECT_THRESHOLD_X10` constant change** — Phase 3 produces a recommendation; Phase 4 applies it
- **`no_flag` training class** — deferred; evaluation-first policy means negatives inform training only after the eval shows what threshold calibration alone cannot solve
- **Model architecture changes** — no ViT structure, patch size, resolution, attention, or capacity changes in Phase 3
- **`--identify-json` structured output** — deferred to Phase 4
- **Real-world Discord/screenshot eval set** — deferred; Phase 3 uses only generated synthetic negatives
- **Augmented or distorted positive eval set** — Phase 3 eval uses the same augmented passes as the C trainer's existing `vit_eval()` loop; a separate distorted eval set is a future addition
- **Hard-negative mining, oversampling by confusable group, or class-balanced sampling** — deferred; these follow from evaluation evidence produced in Phase 3
- **Category-aware augmentation** — deferred
- **Historical flag import** — deferred
- **Fictional, pride, cultural, military, or maritime expansion** — deferred
- **`--force` overwrite of committed baseline reports** — the v3-baseline reports are immutable once committed; any new model checkpoint produces a new run-id
- **A dedicated detector model or flagness head** — evaluation-first; the sliding-window threshold approach is retained until negative eval evidence justifies a different architecture
- **Bot presentation changes** — deferred
- **256×256 or other resolution experiments** — deferred to Phase 4
- **SQLite manifest** — JSONL remains canonical
- **Direct JSONL parsing in the C binary** — C consumes generated CSV; JSONL stays in Python tooling
