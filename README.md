# vexilloscope

ViT-lite flag classifier — identify country flags from images using a Vision Transformer
trained from scratch in C with no external ML libraries.

Built on top of `otto-von-grad` (the autograd engine). This is vexilloscope **v1**.

Intended as a backend for a Discord bot: the bot handles image retrieval and sizing;
vexilloscope handles classification via `--identify`.

---

## What it does

Given a flag image, vexilloscope returns the top-3 most likely countries with confidence scores:

```
identify_flag: data/flags/de.png
  #1  DE    Germany                                   logit: 4.2341
  #2  AT    Austria                                   logit: 2.1034
  #3  BE    Belgium                                   logit: 1.8821
```

---

## Architecture

```
image [128×128×3]
→ img_patchify → [256 patches × 192 pixels]
→ PatchEmb + PosEmb → [256 × 128]    (C = 128)
→ encoder transformer (6 blocks, non-causal, 4 heads, dropout=0.1)
→ tg_mean_rows → [1 × 128]
→ Wout → [1 × n_labels]
→ cross_entropy / identify
```

**Hyperparameters (v1):**

| Parameter | Value |
|-----------|-------|
| Image size | 128 × 128 × 3 |
| Patch size | 8 × 8 |
| Patches | 256 |
| Embed dim (C) | 128 |
| Hidden dim | 256 |
| Encoder blocks | 6 |
| Attention heads | 4 |
| Dropout | 0.1 |
| Optimizer | Adam (β1=0.9, β2=0.999) |
| LR schedule | Cosine decay (base 3e-4) |
| Training steps | 50 000 |

---

## Data

- 255 country flags at 128 × 128 PNG
- Source: [hampusborgos/country-flags](https://github.com/hampusborgos/country-flags) (public domain)
- Resize: `magick mogrify -resize 128x128! *.png`
- `data/labels.csv`: `<code>,<country name>` (one row per flag)

```
data/
  labels.csv       # code, name  (255 rows)
  flags/           # aa.png … zw.png
```

---

## Augmentation

Applied per training step to the raw image before patchification:

1. 50% random horizontal flip
2. Per-channel color jitter × uniform(0.85, 1.15)
3. Random translation ±4px (vacated edges filled white)
4. Random rotation ±15° (bilinear, white fill)

Inference (`--identify`) uses the raw image with no augmentation.
Eval uses multiple augmented passes per flag to measure robustness to distortion.
`img_load` bilinearly resizes any source image to 128×128 before patchification.

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

### Train (saves weights)

```powershell
# MSVC multi-config (Debug/Release subfolder):
.\build\Release\vexilloscope.exe [labels.csv [flags_dir]]

# Ninja (no config subfolder):
.\build\vexilloscope.exe [labels.csv [flags_dir]]

# defaults: data/labels.csv  data/flags
# saves: vit_weights.bin after training completes
```

### Identify a flag

```powershell
.\build\Release\vexilloscope.exe --identify path/to/flag.png
.\build\Release\vexilloscope.exe --identify path/to/flag.png --weights my_weights.bin
```

`--weights` defaults to `vit_weights.bin` in the current directory.

---

## Discord Bot Integration

The bot calls `--identify` with a pre-sized image and parses stdout:

```
vexilloscope.exe --identify <image_path> [--weights <weights_path>]
```

**Output (stdout):**

```
identify_flag: path/to/flag.png
  #1  DE    Germany                                   logit: 4.2341
  #2  AT    Austria                                   logit: 2.1034
  #3  BE    Belgium                                   logit: 1.8821
```

Parse lines matching `#N  CODE  Name  logit: score`. The bot is responsible for
sizing; `img_load` bilinearly rescales any input to 128×128 as a fallback.
Inference is deterministic — dropout is disabled in identify mode.

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

`vx_vit_load` reconstructs the full model from the file alone — no need to pass architecture params.

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
```

