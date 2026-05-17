# AGENTS.md

# vexilloscope

A Vision Transformer (ViT) flag identifier written in C.

Classifies world flags from PNG images using a from-scratch ViT built on top of
the otto-von-grad autograd engine. Intended for identifying flags in Discord
screenshots and similar small/distorted images.

No external ML frameworks. CUDA-accelerated training via otto-von-grad.

---

## Repository Structure

```text
vexilloscope/
  src/
    main.c               — training loop, eval, identify_flag entry point
    dataset.c / .h       — CSV label loading, VxDataset, VxCountry structs
    img.c / .h           — image load/resize/crop, patchify, augmentation pipeline
    patch_embedding.c / .h — VxPatchEmbedding (linear projection + positional embedding)
    vit.c / .h           — VxViT model: patch_emb + encoder + Wout
    mlp_classifier.c / .h — legacy MLP classifier (unused in current ViT pipeline)
    cuda_smoke.c         — CUDA sanity tests
  data/
    flags/               — PNG flag images (one per country, 128×128, hampusborgos source)
    flags_wiki/          — PNG flag images (Wikimedia-sourced, generated — not committed)
    flags_emoji/         — PNG flag images (Twemoji emoji renders, generated — not committed)
    labels.csv           — ISO code, country name per row
  scripts/
    fetch_wiki_flags.py   — downloads flags_wiki/ from flagcdn.com (Wikimedia SVG renders)
    fetch_twemoji_flags.py — downloads flags_emoji/ from Twemoji CDN (emoji-style renders, CC-BY 4.0)
    requirements.txt     — Python deps for scripts (requests, Pillow)
  bot/
    bot.py               — Discord bot: right-click context menu → identify flag
    requirements.txt     — Python deps for bot (discord.py, Pillow)
  vendor/
    stb_image.h          — single-header PNG/JPEG loader (stb)
  CMakeLists.txt
```

---

## Model Architecture

```text
Input: PNG flag image → resize to [128 × 128 × 3]
         ↓
Patchify: 8×8 patches → [256 × 192]  (n_patches=256, patch_size=8*8*3=192)
         ↓
PatchEmbedding: linear projection [192 → embed_dim] + positional embedding
  → [256 × embed_dim]
         ↓
Encoder: non-causal transformer (TgTransformer, causal=0)
  N blocks of: LayerNorm → MultiHeadAttention → residual → LayerNorm → FFN → residual
         ↓
Pool: tg_mean_rows → [1 × embed_dim]
         ↓
Wout: [embed_dim × n_labels] → logits [1 × n_labels]
         ↓
Loss: tg_cross_entropy (softmax CE, one-hot targets)
```

Default hyperparameters (in `main.c` enum):

| Param | Value |
|---|---|
| Image size | 128×128×3 |
| Patch size | 8×8 |
| n_patches | 256 |
| embed_dim | 128 |
| hidden_dim | 256 |
| n_blocks | 6 |
| n_heads | 4 |
| steps | 50000 |
| warmup_steps | 2000 |
| lr_base | 3e-4 (cosine decay) |

---

## Key Structs

```c
// dataset.h
typedef struct { char code[16]; char name[128]; char flag_path[512]; int class_id; } VxCountry;
typedef struct { VxCountry *countries; int count; } VxDataset;

// vit.h
typedef struct {
    VxPatchEmbedding patch_emb;  // PatchEmb [patch_size × embed_dim] + PosEmb [n_patches × embed_dim]
    TgTransformer    encoder;    // non-causal transformer stack
    Tensor          *Wout;       // [embed_dim × n_labels]
    int              n_labels, embed_dim;
} VxViT;

// patch_embedding.h
typedef struct {
    Tensor *PatchEmb;  // [patch_size × embed_dim]
    Tensor *PosEmb;    // [n_patches × embed_dim]
    int n_patches, patch_size, embed_dim;
} VxPatchEmbedding;
```

---

## Data Format

**labels.csv** — one row per country:
```
AD,Andorra,ad.png
AE,United Arab Emirates,ae.png
...
```

**flags/** — PNG images named by ISO 3166-1 alpha-2 code (lowercase), e.g. `ad.png`, `us.png`.

Images are loaded, resized to 128×128, and normalized to [0,1] float.

---

## Image Pipeline

```c
Tensor *img_load(path, H, W, C);                         // load + resize to fixed H×W → [1 × H*W*C]
Tensor *img_load_native(path, max_dim, C, *out_h, *out_w); // load at native res, cap longer edge to max_dim
Tensor *img_crop_and_resize(img, src_h, src_w, C,        // extract rect + bilinear resize
                             y0, x0, crop_h, crop_w,     //   → [1 × target_h*target_w*C]
                             target_h, target_w);
Tensor *img_patchify(img, H, W, C, patch_h, patch_w);    // → [n_patches × patch_size]
Tensor *img_augment(img, H, W, C);                       // flip + jitter + translate + rotate + crop
```

`img_load` is used for training. `img_load_native` + `img_crop_and_resize` drive the
sliding window detector at inference. Augmentation is applied fresh each training step
and during TTA in `identify_flag`. Eval uses augmented samples (N passes per flag) to
measure robustness to distortion.

---

## Training Loop (GPU path)

```
startup: load all images → patchify (CPU) → upload params + targets to GPU

per step:
  sample = images[(step-1) % n_flags]  (all 255 flags, cycling)
  aug    = img_augment(sample)          (CPU, fresh each step)
  p      = img_patchify(aug)
  tg_to_cuda(p)
  logits = vx_vit_forward(&vit, p)
  loss   = tg_cross_entropy(logits, targets[idx])
  tg_backward_accum(loss)
  tg_adam_step_gpu(...)
  tg_free_graph(loss)
  tg_cuda_free(p)

after all steps:
  tg_from_cuda(params)   // sync back to CPU
  save weights
  eval (CPU, augmented)
```

Training runs on **all flags** — there is no held-out class split. Eval measures
robustness to augmentation across all 255 flags.

When `flags_dir2` is provided (positional arg 3), `n_images = n_flags * 2`. When `flags_dir3`
is provided (positional arg 4), `n_images = n_flags * 3`. The training loop cycles over all
sources; `class_idx = idx % n_flags` maps each image to its label. Secondary/tertiary images
that are missing fall back to NULL and the loop substitutes the primary.

---

## Weights Serialization

```c
vx_vit_save(const VxViT *v, const char *path);  // saves to binary .bin file
VxViT vx_vit_load(const char *path);            // reconstructs model from file
```

File format: `"VXWT"` magic + version int32 + 8 architecture int32s + per-param data.

---

## Build Commands

```powershell
# Configure (first time or after clean)
cmake -B build -DOVG_CUDA=ON -G Ninja "-DCMAKE_CUDA_FLAGS=-allow-unsupported-compiler"

# Build
cmake --build build

# Train — single source
.\build\vexilloscope.exe

# Train — two sources
.\build\vexilloscope.exe data/labels.csv data/flags data/flags_wiki

# Train — three sources (recommended; populate flags_wiki/ and flags_emoji/ first)
.\build\vexilloscope.exe data/labels.csv data/flags data/flags_wiki data/flags_emoji

# Identify a flag
.\build\vexilloscope.exe --identify path\to\flag.png
```

Requires `data/flags/` and `data/labels.csv` to be present relative to the working directory.

Trained weights are saved to `vit_weights.bin` in the working directory.

---

## Dependency: otto-von-grad

`vexilloscope` links against `ottovongrad` (static library from
[otto-von-grad](https://github.com/anthvargo/otto-von-grad)).

For local development both repos are expected side-by-side:
```
~/Code/otto-von-grad/
~/Code/vexilloscope/
```

To switch to a remote URL, replace the `add_subdirectory` block in `CMakeLists.txt`
with a `FetchContent_Declare` block (template already in the comment there).

---

## Coding Style

* C11. No external ML libraries, no OOP patterns.
* Image dimensions always passed explicitly — no global state.
* `persistent = 1` on any tensor that must survive `tg_free_graph` (params, patches used across steps).
* Augmentation stays on CPU; only the patch tensor is uploaded to GPU per step.
* Shape mismatches should fail loudly.

---

## Important Guidance For Agents

* Do not introduce external ML or image processing libraries (stb is the approved vendor).
* The encoder uses **non-causal** attention — do not replace with causal blocks.
* Eval strategy: all 255 flags in training, eval via augmented passes. Do not reintroduce a class-split holdout.
* When changing hyperparameters, update the enum constants in `main.c` — do not scatter magic numbers.
* The `-allow-unsupported-compiler` flag is required for VS 2026 + CUDA 12.8 and is set in the otto-von-grad CMakeLists.txt — do not remove it.
* Weights file (`vit_weights.bin`) should not be committed to the repo.
* `data/flags_wiki/` is generated — do not commit it. Regenerate with `scripts/fetch_wiki_flags.py`.
* `data/flags_emoji/` is generated — do not commit it. Regenerate with `scripts/fetch_twemoji_flags.py`.
* The bot (`bot/bot.py`) uses a Discord message context menu command ("Identify flag") and passes raw attachment bytes to the exe. Exception: WebP attachments are converted to PNG in-memory with PIL first (`stb_image` does not support WebP). The binary handles all sizing via the sliding window detector.
* `identify_flag` stdout has two cases: top-3 lines (`#N  CODE  Name  logit: score`) on success, or `no flag detected` on its own line when the best window logit is below `VX_DETECT_THRESHOLD_X10 / 10.0`. Check for the latter before attempting regex parsing.
* The detector scores scale-1 (full image) first. If `scale1_logit >= VX_DETECT_SKIP_SUBWINDOWS_X10 / 10.0`, sub-windows are skipped entirely. This prevents a high-confidence sub-crop of a complex flag from overriding the correct full-image answer.
