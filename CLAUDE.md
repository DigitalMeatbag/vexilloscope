This is **vexilloscope** — a ViT flag classifier in C, intended as a Discord bot backend.
See `AGENTS.md` for full architecture, API reference, and constraints.

## Key rules

- No external ML or image processing libraries — stb (`vendor/`) is the only approved image dep
- Encoder uses **non-causal** attention (`causal=0`) — do not change this
- All 255 flags train; there is no held-out class split — eval uses augmented passes per flag
- Hyperparameter changes go in the `enum` at the top of `main.c` — no scattered magic numbers
- `persistent = 1` on any tensor that must survive `tg_free_graph` (params, patches reused across steps)
- Image dimensions are always passed explicitly — no global state
- Do not commit `vit_weights.bin`

## Build

```powershell
# CPU only
cmake -B build
cmake --build build --config Release
.\build\Release\vexilloscope.exe --identify data/flags/de.png

# CUDA (recommended for training)
cmake -B build -DOVG_CUDA=ON -G Ninja "-DCMAKE_CUDA_FLAGS=-allow-unsupported-compiler"
cmake --build build
.\build\vexilloscope.exe --identify data/flags/de.png
```

The `-allow-unsupported-compiler` flag is set in the otto-von-grad CMakeLists.txt — do not remove it.

## Verification

After code changes, build and run identify mode on any flag:

```powershell
.\build\Release\vexilloscope.exe --identify data/flags/de.png
```

Expected output format:

```
identify_flag: data/flags/de.png
  #1  DE    Germany                                   logit: <score>
  #2  ...
  #3  ...
```

No separate test runner. If training is needed to verify changes, `.\build\Release\vexilloscope.exe` runs the full loop and reports train accuracy and augmented eval on completion.
