# vexilloscope v2 Specification

> **Purpose:** Implementation specification for vexilloscope v2. Derived from `FOUNDATION_V2.md` plus decisions resolved during planning. This document is the authoritative reference for the v2 build.

---

## Pipeline

```
bot → raw image (any size, any content) → vexilloscope --identify → detector → crop → classifier → top-3 (stdout)
                                                                                                  └─ no flag detected (stdout)
```

The bot is a pure transport layer: download attachment bytes, write to temp file, call binary, parse stdout.

---

## Phase 1: img Layer Primitives

Two new functions added to `src/img.c` and `src/img.h`.

### `img_load_native`

```c
Tensor *img_load_native(const char *path, int max_dim, int channels,
                        int *out_h, int *out_w);
```

Loads the image at native resolution. If the longer edge exceeds `max_dim`, downscales proportionally (bilinear) so the longer edge equals `max_dim`; otherwise the image is loaded at its native dimensions unchanged. Returns actual loaded dimensions via `out_h` and `out_w`. Alpha compositing against white for 3-channel output — same as `img_load`.

### `img_crop_and_resize`

```c
Tensor *img_crop_and_resize(const Tensor *img, int src_h, int src_w, int channels,
                             int y0, int x0, int crop_h, int crop_w,
                             int target_h, int target_w);
```

Extracts the rectangle `[y0, y0+crop_h) × [x0, x0+crop_w)` from `img` (a `[1 × src_h*src_w*channels]` tensor) and bilinearly resizes to `target_h × target_w`. Returns a new `[1 × target_h*target_w*channels]` tensor. Caller frees.

---

## Phase 2: Sliding Window Detector

### New enum constants

Added to the `enum` at the top of `src/main.c`:

```c
VX_DETECT_MAX_DIM       = 1024,  // longer edge cap when loading for detection
VX_DETECT_THRESHOLD_X10 =   20,  // confidence threshold × 10 (e.g. 20 → 2.0 logit)
VX_DETECT_STRIDE_PCT    =   50,  // window stride as % of window size
VX_DETECT_MIN_CROP      =   64,  // minimum window dimension (px) in working image
```

### Candidate generation

1. Load the input image with `img_load_native(..., VX_DETECT_MAX_DIM, VX_IMAGE_C, &H, &W)`.
2. Compute three window sizes based on `min(H, W)`:
   - Scale 1 (100%): window = `H × W` — the full image, always exactly one candidate.
   - Scale 2 (75%): square window of side `floor(0.75 × min(H, W))`.
   - Scale 3 (50%): square window of side `floor(0.50 × min(H, W))`.
3. For scales 2 and 3, discard any scale whose window side falls below `VX_DETECT_MIN_CROP`. Scale 1 (full image) is always retained regardless of image dimensions.
4. For scales 2 and 3, stride = `max(1, floor(side × VX_DETECT_STRIDE_PCT / 100))`.
5. Enumerate all `(y0, x0)` positions where the window fits within `[0, H) × [0, W)` at the given stride.
6. The full-image candidate (scale 1) is always included and is never subject to stride enumeration.

### Scoring

For each candidate:

1. Extract with `img_crop_and_resize(..., VX_IMAGE_H, VX_IMAGE_W)`.
2. Patchify with `img_patchify`.
3. Set `patches->persistent = 1` so `tg_free_graph` does not free the patches tensor.
4. Run a **single unaugmented forward pass**: `vx_vit_forward(vit, patches)`.
5. Record `max_logit = max over all class logits`, the corresponding class index, and the candidate's geometry `(y0, x0, crop_h, crop_w)`.
6. Free crop, patches, and logit graph (`tg_free(crop)`, `tg_free_graph(logits)`, `tg_free(patches)`).

### Selection and final identification

- The detection winner is the candidate with the highest `max_logit`.
- If `winner_max_logit < VX_DETECT_THRESHOLD_X10 / 10.0f`:
  - Print the `identify_flag:` header line, then output `no flag detected` to stdout.
  - Return.
- Otherwise:
  - Re-extract the winning crop with `img_crop_and_resize`.
  - Run `VX_IDENTIFY_TTA` augmented passes (identical to current TTA logic in `identify_flag`), averaging logits across passes.
  - Compute top-3 and output using the existing format (unchanged).

### stdout contract

**Successful identification** — format unchanged:

```
identify_flag: <path>
  #1  <CODE>  <Name>                                    logit: <score>
  #2  ...
  #3  ...
```

**No flag detected:**

```
identify_flag: <path>
no flag detected
```

`no flag detected` is the exact string on its own line. The bot checks for this string in stdout before attempting RESULT_RE parsing.

---

## Phase 3: Bot (`bot/bot.py`)

### PIL removed

`_preprocess()` is removed entirely. `PIL` / `Pillow` is no longer imported. `stbi` in the C binary handles JPEG, PNG, WebP, and other formats Discord delivers — format detection is by file content, not extension.

### Raw byte pass-through

`identify_attachment()` writes raw attachment bytes directly to the temp file. The existing `.png` suffix is retained (stbi ignores it).

### Output case handling

`_run_identify()` checks for `no flag detected` in stdout before the existing `RESULT_RE` parse:

```python
if any("no flag detected" in line for line in result.stdout.splitlines()):
    return "No flag found in that image.", result.stdout, result.stderr
```

The existing `RESULT_RE` path is unchanged for successful identifications. The bot surfaces the no-flag result as an explicit reply to the user rather than silently returning empty.

---

## Deferred

- Non-square windows matching flag aspect ratios (2:3, 3:5) — deferred pending accuracy evidence
- Multi-flag detection — out of scope for v2
- Label set expansion — deferred pending real-world accuracy validation
- Dedicated detector model — deferred pending sliding window evaluation

---

## Non-goals (carried from foundation)

- Changes to training, augmentation, or classifier architecture
- New binary entry points
- Changes to the existing top-3 stdout format for successful identifications
