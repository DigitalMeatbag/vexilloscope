# vexilloscope v3 Phase 6 — Engine & Architecture Improvements

> **Purpose:** Ordered work items to strengthen the ViT and underlying autograd engine before expanding
> the training set with pride flags, military flags, additional historicals, and other new categories.
> Work through these sequentially; later steps depend on earlier ones being stable.

---

## Step 1 — Affine LayerNorm (γ/β) [otto-von-grad + vexilloscope]

**Status:** done

**Problem:** `tg_layer_norm_rows_affine` exists in OVG and is tested, but `TgBlock` uses the non-affine
variant. γ and β are never allocated, collected, saved, or trained. Standard ViT implementations include
affine LN; this is a free accuracy improvement that costs nothing at inference.

**Changes:**
- `otto-von-grad/src/tg_block.h`: Add `Tensor *gamma1, *beta1, *gamma2, *beta2` fields to `TgBlock`.
- `otto-von-grad/src/tg_block.c`:
  - `tg_block_create` / `tg_block_create_encoder`: allocate `[1 × embed_dim]`, fill gamma=1.0, beta=0.0, `persistent=1`.
  - `tg_block_free`: free all four tensors.
  - `tg_block_forward`: replace `tg_layer_norm_rows(X, eps)` with `tg_layer_norm_rows_affine(X, gamma1, beta1, eps)` and likewise for the FFN LN.
- `src/vit.c` (`vx_vit_collect_params`): append `gamma1, beta1, gamma2, beta2` to each block's params after `W2/B2`.
- `params[512]` in `vx_vit_save` / `vx_vit_load` / Adam loop in `main.c` have enough headroom (75 params with 6 blocks).
- Save/load version stays 1; n_params in the file header handles forward-compat detection automatically.

**Breaks checkpoint compat** — retrain required after this change.

---

## Step 2 — Warm-start Wout on label-set expansion [vexilloscope]

**Status:** done

**Problem:** `vx_vit_load` in `src/vit.c` exits with a fatal error when Wout column count mismatches the
file. Every label-set expansion forces from-scratch training, throwing away learned representations.

**Fix:** Detect the n_labels mismatch before fatal-exit. When the new n_labels > old n_labels:
- Create Wout as `[embed_dim × new_n_labels]` and Xavier-init it.
- Copy the old columns from the file into the first `old_n_labels` columns.
- Log the warm-start to stderr.

When new n_labels < old n_labels: still fatal-exit (truncating classes is ambiguous).

**Expected benefit:** Label expansions (e.g. adding 50 pride flags) converge in ~30% of the steps a
cold start would need.

---

## Step 3 — Augmentation additions [src/img.c]

**Status:** done

**Problem:** The current augmentation pipeline (flip_h → jitter → crop_resize → translate → rotate) is
missing two augmentations that matter for real-world Discord screenshots and small/distorted flags.

**a) Cutout / random erase**
- Pick a random rectangle (15–35% of image width, 15–35% of height), fill with random grey noise.
- Forces the model to recognize flags from partial information; improves subnational seal robustness.

**b) Blur / resolution degradation**
- Downsample to 25–50% then upsample back to 256×256.
- Simulates low-resolution or heavily compressed source images.

**c) Aspect-preserving letterbox (pre-resize)**
- Pad short axis with white before bilinear resize instead of stretching.
- Reduces distortion artifacts on flags with fixed aspect ratios (e.g. Switzerland 1:1, Nepal).

**NOTE on pride flags:** When pride classes are added, reduce per-channel jitter from ±15% to ±8%
(`VX_JITTER` constant in img.c). Pride flags are hue-defined; aggressive jitter makes color-stripe
flags ambiguous. Do not add grayscale augmentation while pride classes are in training.

---

## Step 4 — Retrain 322-class baseline to confirm no regression

**Status:** done (top-1 92.04%, top-3 97.52%; -0.58 pp from baseline, within noise; Steps 5+ retrain anyway)

After Steps 1–3, retrain from scratch on the current 322-class set and run eval. Target: match or
beat the exp-historical-16 baseline (top-1 exact flag 92.62%). If Step 1 (affine LN) is working
correctly, expect a small improvement (0.5–2 pp) on the confusable national flags.

```powershell
python scripts/export_training.py
.\build\vexilloscope.exe data/generated/train/labels.csv data/generated/train/images/ --eval-dump data/generated/train/eval_dump.csv
python scripts/eval_report.py data/generated/train/eval_dump.csv data/generated/train/class_map.json
```

---

## Step 5 — Capacity bump [src/main.c enum only]

**Status:** done (top-1 92.93%, top-3 97.86%; beats baseline on both metrics)

**Problem:** ~1M params (embed_dim=128, hidden_dim=256, 6 blocks, 4 heads) is light for 500+ classes
with heterogeneous visual structure (stripes, seals, geometric patterns, color-block pride flags).

**Changes to the enum at the top of `main.c` only:**
| Param | Current | Target |
|---|---|---|
| `VX_EMBED_DIM` | 128 | 192 |
| `VX_HIDDEN_DIM` | 256 | 512 |
| `VX_N_HEADS` | 4 | 6 |
| `VX_VIT_STEPS` | 50000 | scale with n_classes (see Step 8) |

192 must be divisible by n_heads=6 (192/6=32 ✓). This bumps param count to ~3M — still GPU-friendly.

**Breaks checkpoint compat** — retrain required.

---

## Step 6 — Patch resolution experiment [main.c enum + img.c]

**Status:** pending (run after Step 4 baseline confirms no regression from Steps 1–3)

**Current:** 16×16 patches at 256px input → 256 tokens. Corner seals land at ~5px effective detail.

**Options to benchmark:**
- **8×8 patches at 256px** → 1024 tokens (4× more compute per forward pass; same input image)
- **16×16 patches at 384px** → 576 tokens (~2× input pixels; letterbox at 384)

Run both as separate experiments. Report top-1 by category (especially subnational and historical
where seal/emblem detail matters).

---

## Step 7 — Enable balanced sampling [src/main.c enum]

**Status:** reverted — branch implemented but VX_BALANCED_SAMPLING reset to 0.
Balanced sampling caused NaN divergence around step 22–27k on two independent runs
(warm-start and cold-start) despite different RNG seeds. Root cause: rand() calls
in the sampling branch shift the augmentation sequence, exposing the model to
combinations of extreme transforms that survive the gradient clip and accumulate
into NaN. Round-robin at 402 classes trains stably. Revisit with tighter gradient
clip (0.5) or lower base LR before re-enabling.

**Problem:** `VX_BALANCED_SAMPLING=0` means round-robin over all flags. When heterogeneous categories
(e.g. 50 pride + 80 military + 322 current) are combined, rare categories get proportionally fewer
training examples per epoch.

**Change:** Set `VX_BALANCED_SAMPLING=1` in the enum. Verify the sampling branch in the training loop
is exercised before expanding the class list.

---

## Step 8 — Steps formula for growing label sets

**Status:** pending

**Rule:** `VX_VIT_STEPS ≈ 150 × n_classes`, `VX_WARMUP_STEPS ≈ 4% × VX_VIT_STEPS`.

| n_classes | VX_VIT_STEPS | VX_WARMUP_STEPS |
|---|---|---|
| 322 (current) | 48300 → 50000 | 2000 |
| ~500 | 75000 | 3000 |
| ~750 | 112500 | 4500 |
| ~1000 | 150000 | 6000 |

Update the enum when the class count changes materially. Do not retrain without updating these.

---

## Notes

- Steps 1–3 are engine/pipeline improvements and should be done before any new classes are added.
- Step 4 validates Steps 1–3 don't regress the existing 322-class model.
- Steps 5–8 are capacity and training-budget changes that make sense once the pipeline is confirmed stable.
- The negative-eval HC-FP rate (15.0% at threshold_x10=35) is an open problem; threshold tuning alone
  will not fix it. See FOUNDATION_V3.md §Open Problems. Do not advertise threshold as the fix.
