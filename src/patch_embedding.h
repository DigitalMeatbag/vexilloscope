#ifndef VEXILLOSCOPE_PATCH_EMBEDDING_H
#define VEXILLOSCOPE_PATCH_EMBEDDING_H

#include "tg_tensor.h"

typedef struct {
    Tensor *PatchEmb;  // [patch_size x embed_dim]
    Tensor *PosEmb;    // [n_patches x embed_dim]
    int n_patches;
    int patch_size;
    int embed_dim;
} VxPatchEmbedding;

typedef struct {
    Tensor *projected;
    Tensor *encoded;
} VxPatchEmbeddingForward;

VxPatchEmbedding        vx_patch_embedding_create(int n_patches, int patch_size, int embed_dim);
void                    vx_patch_embedding_free(VxPatchEmbedding *p);
VxPatchEmbeddingForward vx_patch_embedding_forward_full(VxPatchEmbedding *p, Tensor *patches);
Tensor                 *vx_patch_embedding_forward(VxPatchEmbedding *p, Tensor *patches);
void                    vx_patch_embedding_forward_free(VxPatchEmbeddingForward *f);
int                     vx_patch_embedding_collect_params(VxPatchEmbedding *p, Tensor **params);

#endif
