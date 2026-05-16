# vexilloscope

ViT-lite flag classifier — identify country flags from images using a Vision Transformer
trained from scratch in C with no external ML libraries.

Built on top of `otto_von_grad` (the autograd engine). This is vexilloscope **v1**.

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

- 255 country flags at 64 × 64 PNG
- Source: [hampusborgos/country-flags](https://github.com/hampusborgos/country-flags) (public domain)
- Resize: `magick mogrify -resize 64x64! *.png`
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

Eval and inference use clean images (no augmentation).
`img_load` bilinearly resizes any source image to the target dimensions.

---

## Build

```powershell
cd vexilloscope
cmake -B build
cmake --build build
```

---

## Usage

### Train (saves weights)

```powershell
.\build\Debug\vexilloscope.exe [labels.csv [flags_dir]]
# defaults: data/labels.csv  data/flags
# saves: vit_weights.bin after training completes
```

### Identify a flag (no training)

```powershell
.\build\Debug\vexilloscope.exe --identify path/to/flag.png
.\build\Debug\vexilloscope.exe --identify path/to/flag.png --weights my_weights.bin
```

`--weights` defaults to `vit_weights.bin` in the current directory.

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

---

## Results (v1 training run)

```
steps: 10 000  augmentation: on  cosine LR: on
train accuracy: ~42%  (218 flags seen during training)
eval accuracy:  ~0%   (37 held-out classes never seen — hard generalization task)
```

The eval 0% is expected: the train/eval split holds out entire flag classes. With one image per
class, the model has never seen those flags at all. Train accuracy of 42% confirms the model is
learning visual features from augmented single-image data.
