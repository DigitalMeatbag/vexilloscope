# vexilloscope

ViT flag classifier — identify country and regional flags from images using a Vision Transformer
trained from scratch in C with no external ML libraries. This is vexilloscope **v3**.

Built on top of [`otto-von-grad`](https://github.com/DigitalMeatbag/otto-von-grad) (the autograd engine).

Intended as a backend for a Discord bot: the bot handles image retrieval;
vexilloscope handles detection, cropping, and classification via `--identify-json`.

---

## What it does

Given a flag image, vexilloscope returns the top-3 most likely results with confidence scores:

```
identify_flag: data/generated/train/images/de-current.png
  #1  de-current  Germany                                   logit: 4.2341
  #2  at-current  Austria                                   logit: 2.1034
  #3  be-current  Belgium                                   logit: 1.8821
```

---

## Architecture

```
image [256×256×3]
→ letterbox + img_patchify → [256 patches × 768 pixels]
→ PatchEmb [768 → 192] + PosEmb → [256 × 192]    (embed_dim = 192)
→ encoder transformer (6 blocks, non-causal, 6 heads)
  each block: affine LayerNorm → MultiHeadAttention → residual → affine LayerNorm → FFN → residual
→ CLS token extract: tg_row_slice(enc, 0, 1) → [1 × 192]
→ Wout [192 × n_labels] → logits [1 × n_labels]
→ cross_entropy / identify
```

**Hyperparameters** (in `main.c` enum):

| Parameter | Value |
|-----------|-------|
| Image size | 256 × 256 × 3 |
| Patch size | 16 × 16 |
| n_patches | 256 |
| embed_dim | 192 |
| hidden_dim | 512 |
| n_blocks | 6 |
| n_heads | 6 |
| steps | 60 000 |
| warmup_steps | 2 400 |
| label_smooth | 0.10 |
| Optimizer | Adam (β1=0.9, β2=0.999, base LR 3e-4) |
| LR schedule | Cosine decay with linear warmup |

~2.35M parameters, ~9.4 MB weights file.

---

## Classes

402 classes across five categories:

- **255** national and territory flags (Phase 1)
- **51** US states + DC (Phase 2)
- **16** historical national flags (Phase 5)
- **pride flags** and **HRE historical flags** (Phase 6)

All classes train together — there is no held-out class split. Eval measures robustness via augmented passes per flag.

---

## Data

Training data is generated from the manifest at `data/manifest/`:

```
data/
  manifest/
    results.jsonl    # result definitions (country/category metadata)
    flags.jsonl      # flag definitions (flag_id, result_id, variant)
    assets.jsonl     # asset records (source URL, local path)
  generated/         # derived from manifest — do not commit
    train/
      labels.csv     # code,name  (one row per class)
      images/        # one PNG per class, named by flag_id
      class_map.json # class_id → result metadata
```

Populate `data/generated/` before training:

```powershell
python scripts/export_training.py
```

---

## Augmentation

Applied per training step before patchification:

1. Letterbox: pad short axis with white to make square canvas (preserves aspect ratio)
2. 50% random horizontal flip
3. Per-channel color jitter × uniform(0.92, 1.08) — reduced for hue-defined pride flags
4. Random crop 80–100% of image, resized back to 256×256
5. Random translation ±4px (vacated edges filled white)
6. Random rotation ±15° (bilinear, white fill)
7. 50% cutout: random 15–35% × 15–35% rectangle filled with grey noise
8. 50% blur: downsample to 25–50% then upsample back (simulates low-res sources)

Inference (`--identify-json`) runs a sliding window detector, scores candidates with a single
unaugmented forward pass, then re-extracts the best crop and averages `VX_IDENTIFY_TTA` augmented
passes to produce the final result.

---

## Build

### CPU only

```powershell
cmake -B build
cmake --build build --config Release
```

### CUDA (recommended for training)

```powershell
cmake -B build -DOVG_CUDA=ON -G Ninja "-DCMAKE_CUDA_FLAGS=-allow-unsupported-compiler"
cmake --build build
```

---

## Usage

### Train

```powershell
# Generate training data first
python scripts/export_training.py

# Train (saves vit_weights.bin on completion)
.\build\vexilloscope.exe data/generated/train/labels.csv data/generated/train/images/ --eval-dump data/generated/train/eval_dump.csv

# Warm-start from existing weights (e.g. after adding new classes)
.\build\vexilloscope.exe data/generated/train/labels.csv data/generated/train/images/ --warmstart vit_weights.bin
```

### Identify a flag

```powershell
# Human-readable top-3
.\build\vexilloscope.exe --labels data/generated/train/labels.csv --identify path/to/flag.png

# JSON output (bot interface)
.\build\vexilloscope.exe --labels data/generated/train/labels.csv --identify-json path/to/flag.png
```

---

## Discord Bot Integration

The bot uses `--identify-json` and parses stdout as a single JSON object:

```powershell
vexilloscope.exe --labels <labels_path> --identify-json <image_path>
```

**Output schema** (`detected=true`):

```json
{
  "detected": true,
  "results": [
    {
      "rank": 1,
      "result_id": "de",
      "display_name": "Germany",
      "category": "national",
      "confidence": 4.2341,
      "margin": 2.1307
    }
  ],
  "detection": { "crop": [...], "score": 4.2341 }
}
```

**Output schema** (`detected=false`):

```json
{ "detected": false, "no_flag_reason": "below_threshold" }
```

`no_flag_reason` is one of `load_error`, `no_detection`, `below_threshold`. Check `detected`
before reading `results`.

> **Note:** `stb_image` does not support WebP. The bot converts WebP attachments to PNG
> in-memory with PIL before passing to the binary.

---

## Weight format

Binary file with a self-describing header:

```
magic:      "VXWT"  (4 bytes)
version:    int32 = 1
n_patches:  int32
patch_size: int32
embed_dim:  int32
hidden_dim: int32
n_blocks:   int32
n_heads:    int32
n_labels:   int32
n_params:   int32
per param:  rows int32, cols int32, rows×cols float32
```

`vx_vit_load` reconstructs the full model from the file alone — no architecture params needed.
Do not commit `vit_weights.bin`.

---

## API (`vit.h`)

```c
VxViT   vx_vit_create(int n_patches, int patch_size, int embed_dim,
                      int hidden_dim, int n_blocks, int n_heads, int n_labels);
void    vx_vit_free(VxViT *v);
Tensor *vx_vit_forward(VxViT *v, Tensor *patches);   // [n_patches × patch_size] → [1 × n_labels]
int     vx_vit_collect_params(VxViT *v, Tensor **params);
void    vx_vit_save(const VxViT *v, const char *path);
VxViT   vx_vit_load(const char *path);
VxViT   vx_vit_load_warmstart(const char *path, int new_n_labels);  // expand Wout for new classes
```
