This is **vexilloscope** — a Vision Transformer flag identifier in C (C11).
See `AGENTS.md` for full architecture, data format, training loop, and constraints.

Key rules:
- Depends on otto-von-grad (`ottovongrad` static lib) — no other ML dependencies
- Encoder uses **non-causal** attention — do not use causal/GPT-style blocks
- All 255 flags are used for training; eval uses augmented passes — no class-split holdout
- Image pipeline: load → resize → patchify → augment (all CPU); only the patch tensor goes to GPU
- Hyperparameters live in the enum in `main.c` — no scattered magic numbers
- `vit_weights.bin` must not be committed
- stb (vendor/) is the only approved image library
