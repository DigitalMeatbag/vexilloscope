# Accuracy Improvement Notes

## Current architecture recap

ViT: 6 blocks, embed_dim=128, hidden_dim=256, 4 heads, 256 patches (8×8) from 128×128 input.
Training: 50 000 steps, cosine LR + 2 000-step warmup, dropout=0.1, Adam.
Augmentation: horizontal flip, color jitter ±15%, translate ±4px, rotate ±15°.
Data: 255 flags, two-source training (hampusborgos + Wikimedia).

## Planned improvements (in order)

### 1. Test-time augmentation (TTA) at inference — DONE
`identify_flag` previously ran a single clean forward pass.
Now runs `VX_IDENTIFY_TTA` augmented passes and averages the logits before ranking.
No retraining required; directly mirrors the eval strategy and handles
distorted/resized Discord inputs better.

### 2. Zoom/crop augmentation — DONE
`img_crop_resize`: random crop 80–100% of image, resized back to 128×128,
applied in `img_augment` between jitter and translate.
Simulates zoomed/cropped flags common in Discord screenshots.
Requires retraining.

### 3. Label smoothing — DONE
`VX_LABEL_SMOOTH = 100` (ε=0.10): true class gets 0.90, remaining 0.10 spread
uniformly across the other 254 classes.
Reduces overconfidence and helps with visually similar pairs
(Chad/Romania, Indonesia/Monaco, Ivory Coast/Ireland, etc.).
Requires retraining.

### 4. Third training source (Twemoji emoji renders) — DONE
`scripts/fetch_twemoji_flags.py` downloads 72×72 Twemoji flag emoji PNGs
(CC-BY 4.0) to `data/flags_emoji/`. These represent how flag emoji look in
Discord, adding a visually distinct render style to the training set.
Training loop now accepts a third positional directory argument.
Run command: `.\build\vexilloscope.exe data/labels.csv data/flags data/flags_wiki data/flags_emoji`
Requires running the fetch script and retraining.

## Other levers (not yet scheduled)

- **Weight decay in Adam** (1e-4): reduces overfitting, easy to add.
- **Capacity increase**: embed_dim 128→192+, hidden_dim 256→512+, more blocks.
  More expensive to train.
- **More training steps**: straightforward.
- **CLS token**: replace mean pooling with a learned CLS token (standard ViT practice).
- **Larger input / smaller patch**: 256×256 + 16×16 patches — 4× more patches,
  much more compute.
