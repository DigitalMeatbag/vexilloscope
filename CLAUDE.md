This is **vexilloscope** — a ViT flag classifier in C, intended as a Discord bot backend.
See `AGENTS.md` for full architecture, API reference, and constraints.

## Key rules

- No external ML or image processing libraries — stb (`vendor/`) is the only approved image dep
- Encoder uses **non-causal** attention (`causal=0`) — do not change this
- All 306 flags train (v3: 255 Phase 1 + 51 US states); there is no held-out class split — eval uses augmented passes per flag
- Hyperparameter changes go in the `enum` at the top of `main.c` — no scattered magic numbers
- `persistent = 1` on any tensor that must survive `tg_free_graph` (params, patches reused across steps)
- Image dimensions are always passed explicitly — no global state
- Do not commit `vit_weights.bin`

## Build

```powershell
# CPU only
cmake -B build
cmake --build build --config Release

# CUDA (recommended for training)
cmake -B build -DOVG_CUDA=ON -G Ninja "-DCMAKE_CUDA_FLAGS=-allow-unsupported-compiler"
cmake --build build
```

Train (v3 export — run `scripts/export_training.py` first):
```powershell
.\build\vexilloscope.exe data/generated/train/labels.csv data/generated/train/images/
```

The `-allow-unsupported-compiler` flag is set in the otto-von-grad CMakeLists.txt — do not remove it.

## Verification

After code changes, build and run identify mode on any flag. Always pass `--labels` pointing to the active training export:

```powershell
.\build\vexilloscope.exe --labels data/generated/train/labels.csv --identify data/generated/train/images/de-current.png
```

Expected output format:

```
identify_flag: data/generated/train/images/de-current.png
  #1  de-current  Germany                                   logit: <score>
  #2  ...
  #3  ...
```

No separate test runner. If training is needed to verify changes, `.\build\Release\vexilloscope.exe` runs the full loop and reports train accuracy and augmented eval on completion.
