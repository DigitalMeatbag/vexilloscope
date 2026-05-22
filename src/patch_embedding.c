#include "patch_embedding.h"

#include "tg_ops.h"

#include <stdio.h>
#include <stdlib.h>

VxPatchEmbedding vx_patch_embedding_create(int n_patches, int patch_size, int embed_dim) {
    if (n_patches <= 0 || patch_size <= 0 || embed_dim <= 0) {
        fprintf(stderr, "vx_patch_embedding_create: invalid dimensions\n");
        exit(1);
    }

    VxPatchEmbedding p;
    p.n_patches = n_patches;
    p.patch_size = patch_size;
    p.embed_dim = embed_dim;
    p.PatchEmb = tg_new(patch_size, embed_dim);
    p.PosEmb = tg_new(n_patches, embed_dim);
    tg_fill_xavier_uniform(p.PatchEmb);
    tg_fill(p.PosEmb, 0.0f);

    p.PatchEmb->persistent = 1;
    p.PosEmb->persistent   = 1;
    return p;
}

void vx_patch_embedding_free(VxPatchEmbedding *p) {
    if (!p) return;
    tg_free(p->PatchEmb);
    tg_free(p->PosEmb);
    p->PatchEmb = NULL;
    p->PosEmb = NULL;
}

VxPatchEmbeddingForward vx_patch_embedding_forward_full(VxPatchEmbedding *p, Tensor *patches) {
    if (!p || !patches) {
        fprintf(stderr, "vx_patch_embedding_forward_full: null argument\n");
        exit(1);
    }
    if (patches->rows != p->n_patches || patches->cols != p->patch_size) {
        fprintf(stderr, "vx_patch_embedding_forward_full: expected patches [%dx%d], got [%dx%d]\n",
                p->n_patches, p->patch_size, patches->rows, patches->cols);
        exit(1);
    }

    VxPatchEmbeddingForward f;
    f.projected = tg_matmul(patches, p->PatchEmb);
    f.encoded = tg_add(f.projected, p->PosEmb);
    return f;
}

Tensor *vx_patch_embedding_forward(VxPatchEmbedding *p, Tensor *patches) {
    VxPatchEmbeddingForward f = vx_patch_embedding_forward_full(p, patches);
    return f.encoded;
}

void vx_patch_embedding_forward_free(VxPatchEmbeddingForward *f) {
    if (!f) return;
    tg_free(f->encoded);
    tg_free(f->projected);
    f->encoded = NULL;
    f->projected = NULL;
}

int vx_patch_embedding_collect_params(VxPatchEmbedding *p, Tensor **params) {
    if (!p || !params) {
        fprintf(stderr, "vx_patch_embedding_collect_params: null argument\n");
        exit(1);
    }
    params[0] = p->PatchEmb;
    params[1] = p->PosEmb;
    return 2;
}
