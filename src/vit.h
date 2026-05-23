#ifndef VEXILLOSCOPE_VIT_H
#define VEXILLOSCOPE_VIT_H

#include "patch_embedding.h"
#include "tg_transformer.h"

typedef struct {
    VxPatchEmbedding patch_emb;  // PatchEmb [patch_size x C] + PosEmb [n_patches x C]
    TgTransformer    encoder;    // non-causal transformer stack
    Tensor          *Wout;       // [embed_dim x n_labels]
    int              n_labels;
    int              embed_dim;
} VxViT;

VxViT   vx_vit_create(int n_patches, int patch_size, int embed_dim,
                      int hidden_dim, int n_blocks, int n_heads, int n_labels,
                      float max_drop_path_rate);
void    vx_vit_free(VxViT *v);

// patches: [n_patches x patch_size] → logits: [1 x n_labels]
Tensor *vx_vit_forward(VxViT *v, Tensor *patches);

// Fills params[] with all trainable tensors; returns count.
int     vx_vit_collect_params(VxViT *v, Tensor **params);

// Serialization: save/load all weights to/from a binary file.
// File format: 4-byte magic "VXWT" + version int32 + 8 architecture int32s +
// per-param (rows int32, cols int32, rows*cols float32 data).
// vx_vit_load creates a fresh VxViT from the file header, then overwrites weights.
void    vx_vit_save(const VxViT *v, const char *path);
VxViT   vx_vit_load(const char *path);
// vx_vit_load_warmstart: load weights and expand Wout to new_n_labels.
// Old class columns are copied verbatim; new columns keep Xavier init from vx_vit_create.
// Fatals if new_n_labels < file's n_labels (truncation is ambiguous).
VxViT   vx_vit_load_warmstart(const char *path, int new_n_labels);

#endif
