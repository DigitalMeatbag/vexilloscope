#include "vit.h"

#include "tg_ops.h"
#include "tg_train.h"

#include <stdio.h>
#include <stdlib.h>

VxViT vx_vit_create(int n_patches, int patch_size, int embed_dim,
                    int hidden_dim, int n_blocks, int n_heads, int n_labels) {
    VxViT v;

    v.patch_emb = vx_patch_embedding_create(n_patches, patch_size, embed_dim);
    v.encoder   = tg_transformer_create_encoder(n_blocks, embed_dim, hidden_dim,
                                                n_patches, n_heads);
    v.Wout      = tg_new(embed_dim, n_labels);
    v.n_labels  = n_labels;
    v.embed_dim = embed_dim;

    tg_fill_xavier_uniform(v.Wout);
    v.Wout->persistent = 1;

    return v;
}

void vx_vit_free(VxViT *v) {
    if (!v) return;

    vx_patch_embedding_free(&v->patch_emb);
    tg_transformer_free(&v->encoder);
    tg_free(v->Wout);

    v->Wout     = NULL;
    v->n_labels = 0;
    v->embed_dim = 0;
}

Tensor *vx_vit_forward(VxViT *v, Tensor *patches) {
    if (!v || !patches) {
        fprintf(stderr, "vx_vit_forward: NULL argument\n");
        exit(1);
    }

    /*
        patches: [n_patches x patch_size]
        X:       [n_patches x C]           patch + positional embeddings
        enc:     [n_patches x C]           encoder transformer output
        pool:    [1 x C]                   mean over patch tokens
        logits:  [1 x n_labels]            classification scores
    */
    Tensor *X   = vx_patch_embedding_forward(&v->patch_emb, patches);
    Tensor *enc = tg_transformer_forward(&v->encoder, X);
    Tensor *pool   = tg_mean_rows(enc);
    Tensor *logits = tg_matmul(pool, v->Wout);

    return logits;
}

int vx_vit_collect_params(VxViT *v, Tensor **params) {
    int n = 0;

    n += vx_patch_embedding_collect_params(&v->patch_emb, params + n);

    for (int i = 0; i < v->encoder.n_blocks; i++) {
        TgBlock *b = &v->encoder.blocks[i];

        params[n++] = b->gamma1;
        params[n++] = b->beta1;
        params[n++] = b->attn.Wq;
        params[n++] = b->attn.Wk;
        params[n++] = b->attn.Wv;
        params[n++] = b->attn.Wo;

        params[n++] = b->gamma2;
        params[n++] = b->beta2;
        params[n++] = b->W1;
        params[n++] = b->B1;
        params[n++] = b->W2;
        params[n++] = b->B2;
    }

    params[n++] = v->Wout;

    return n;
}

void vx_vit_save(const VxViT *v, const char *path) {
    if (!v || !path) {
        fprintf(stderr, "vx_vit_save: NULL argument\n");
        exit(1);
    }

    int n_patches  = v->patch_emb.n_patches;
    int patch_size = v->patch_emb.patch_size;
    int embed_dim  = v->embed_dim;
    int hidden_dim = v->encoder.hidden_dim;
    int n_blocks   = v->encoder.n_blocks;
    int n_heads    = (n_blocks > 0) ? v->encoder.blocks[0].attn.n_heads : 1;
    int n_labels   = v->n_labels;

    Tensor *params[512];
    int n_params = vx_vit_collect_params((VxViT *)v, params);

    FILE *f = fopen(path, "wb");
    if (!f) {
        fprintf(stderr, "vx_vit_save: cannot open '%s' for writing\n", path);
        exit(1);
    }

    const char magic[4] = {'V', 'X', 'W', 'T'};
    int version = 1;
    fwrite(magic,      1,            4, f);
    fwrite(&version,   sizeof(int),  1, f);
    fwrite(&n_patches, sizeof(int),  1, f);
    fwrite(&patch_size,sizeof(int),  1, f);
    fwrite(&embed_dim, sizeof(int),  1, f);
    fwrite(&hidden_dim,sizeof(int),  1, f);
    fwrite(&n_blocks,  sizeof(int),  1, f);
    fwrite(&n_heads,   sizeof(int),  1, f);
    fwrite(&n_labels,  sizeof(int),  1, f);
    fwrite(&n_params,  sizeof(int),  1, f);

    for (int i = 0; i < n_params; i++) {
        Tensor *t = params[i];
        size_t n_floats = (size_t)t->rows * t->cols;
        if (fwrite(&t->rows, sizeof(int),   1,        f) != 1 ||
            fwrite(&t->cols, sizeof(int),   1,        f) != 1 ||
            fwrite(t->data,  sizeof(float), n_floats, f) != n_floats) {
            fprintf(stderr, "vx_vit_save: write error on param %d\n", i);
            fclose(f);
            exit(1);
        }
    }

    fclose(f);
    printf("saved weights to '%s' (%d params)\n", path, n_params);
}

VxViT vx_vit_load(const char *path) {
    if (!path) {
        fprintf(stderr, "vx_vit_load: NULL path\n");
        exit(1);
    }

    FILE *f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "vx_vit_load: cannot open '%s' for reading\n", path);
        exit(1);
    }

    char magic[4];
    fread(magic, 1, 4, f);
    if (magic[0]!='V' || magic[1]!='X' || magic[2]!='W' || magic[3]!='T') {
        fprintf(stderr, "vx_vit_load: invalid magic bytes in '%s'\n", path);
        fclose(f);
        exit(1);
    }

    int version;
    fread(&version, sizeof(int), 1, f);
    if (version != 1) {
        fprintf(stderr, "vx_vit_load: unsupported version %d in '%s'\n", version, path);
        fclose(f);
        exit(1);
    }

    int n_patches, patch_size, embed_dim, hidden_dim, n_blocks, n_heads, n_labels, n_params;
    fread(&n_patches,  sizeof(int), 1, f);
    fread(&patch_size, sizeof(int), 1, f);
    fread(&embed_dim,  sizeof(int), 1, f);
    fread(&hidden_dim, sizeof(int), 1, f);
    fread(&n_blocks,   sizeof(int), 1, f);
    fread(&n_heads,    sizeof(int), 1, f);
    fread(&n_labels,   sizeof(int), 1, f);
    fread(&n_params,   sizeof(int), 1, f);

    VxViT v = vx_vit_create(n_patches, patch_size, embed_dim,
                             hidden_dim, n_blocks, n_heads, n_labels);

    Tensor *params[512];
    int actual_n = vx_vit_collect_params(&v, params);
    if (actual_n != n_params) {
        fprintf(stderr, "vx_vit_load: param count mismatch: file=%d expected=%d\n",
                n_params, actual_n);
        fclose(f);
        vx_vit_free(&v);
        exit(1);
    }

    for (int i = 0; i < n_params; i++) {
        int rows, cols;
        if (fread(&rows, sizeof(int), 1, f) != 1 ||
            fread(&cols, sizeof(int), 1, f) != 1) {
            fprintf(stderr, "vx_vit_load: unexpected EOF reading param %d header\n", i);
            fclose(f);
            vx_vit_free(&v);
            exit(1);
        }
        if (rows != params[i]->rows || cols != params[i]->cols) {
            fprintf(stderr,
                "vx_vit_load: param %d shape mismatch: file=[%d,%d] expected=[%d,%d]\n",
                i, rows, cols, params[i]->rows, params[i]->cols);
            fclose(f);
            vx_vit_free(&v);
            exit(1);
        }
        size_t n_floats = (size_t)rows * cols;
        if (fread(params[i]->data, sizeof(float), n_floats, f) != n_floats) {
            fprintf(stderr, "vx_vit_load: unexpected EOF reading param %d data\n", i);
            fclose(f);
            vx_vit_free(&v);
            exit(1);
        }
    }

    fclose(f);
    fprintf(stderr, "loaded weights from '%s'  (%d params  n_labels=%d)\n",
            path, n_params, n_labels);
    return v;
}

VxViT vx_vit_load_warmstart(const char *path, int new_n_labels) {
    if (!path) {
        fprintf(stderr, "vx_vit_load_warmstart: NULL path\n");
        exit(1);
    }

    FILE *f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "vx_vit_load_warmstart: cannot open '%s' for reading\n", path);
        exit(1);
    }

    char magic[4];
    fread(magic, 1, 4, f);
    if (magic[0]!='V' || magic[1]!='X' || magic[2]!='W' || magic[3]!='T') {
        fprintf(stderr, "vx_vit_load_warmstart: invalid magic bytes in '%s'\n", path);
        fclose(f);
        exit(1);
    }

    int version;
    fread(&version, sizeof(int), 1, f);
    if (version != 1) {
        fprintf(stderr, "vx_vit_load_warmstart: unsupported version %d in '%s'\n", version, path);
        fclose(f);
        exit(1);
    }

    int n_patches, patch_size, embed_dim, hidden_dim, n_blocks, n_heads, file_n_labels, n_params;
    fread(&n_patches,     sizeof(int), 1, f);
    fread(&patch_size,    sizeof(int), 1, f);
    fread(&embed_dim,     sizeof(int), 1, f);
    fread(&hidden_dim,    sizeof(int), 1, f);
    fread(&n_blocks,      sizeof(int), 1, f);
    fread(&n_heads,       sizeof(int), 1, f);
    fread(&file_n_labels, sizeof(int), 1, f);
    fread(&n_params,      sizeof(int), 1, f);

    if (new_n_labels < file_n_labels) {
        fprintf(stderr,
            "vx_vit_load_warmstart: new_n_labels=%d < file n_labels=%d; truncation is ambiguous\n",
            new_n_labels, file_n_labels);
        fclose(f);
        exit(1);
    }

    VxViT v = vx_vit_create(n_patches, patch_size, embed_dim,
                             hidden_dim, n_blocks, n_heads, new_n_labels);

    Tensor *params[512];
    int actual_n = vx_vit_collect_params(&v, params);
    if (actual_n != n_params) {
        fprintf(stderr, "vx_vit_load_warmstart: param count mismatch: file=%d expected=%d\n",
                n_params, actual_n);
        fclose(f);
        vx_vit_free(&v);
        exit(1);
    }

    /* Contract guard: Wout must be the last collected param. */
    if (params[n_params - 1] != v.Wout) {
        fprintf(stderr, "vx_vit_load_warmstart: internal error — Wout is not the last param\n");
        fclose(f);
        vx_vit_free(&v);
        exit(1);
    }

    /* Load all params except Wout with strict shape check. */
    for (int i = 0; i < n_params - 1; i++) {
        int rows, cols;
        if (fread(&rows, sizeof(int), 1, f) != 1 ||
            fread(&cols, sizeof(int), 1, f) != 1) {
            fprintf(stderr, "vx_vit_load_warmstart: unexpected EOF reading param %d header\n", i);
            fclose(f);
            vx_vit_free(&v);
            exit(1);
        }
        if (rows != params[i]->rows || cols != params[i]->cols) {
            fprintf(stderr,
                "vx_vit_load_warmstart: param %d shape mismatch: file=[%d,%d] expected=[%d,%d]\n",
                i, rows, cols, params[i]->rows, params[i]->cols);
            fclose(f);
            vx_vit_free(&v);
            exit(1);
        }
        size_t n_floats = (size_t)rows * cols;
        if (fread(params[i]->data, sizeof(float), n_floats, f) != n_floats) {
            fprintf(stderr, "vx_vit_load_warmstart: unexpected EOF reading param %d data\n", i);
            fclose(f);
            vx_vit_free(&v);
            exit(1);
        }
    }

    /* Load Wout: verify file shape, then copy row-by-row into the wider new Wout.
       Columns [file_n_labels, new_n_labels) keep their Xavier-init values. */
    {
        int rows, cols;
        if (fread(&rows, sizeof(int), 1, f) != 1 ||
            fread(&cols, sizeof(int), 1, f) != 1) {
            fprintf(stderr, "vx_vit_load_warmstart: unexpected EOF reading Wout header\n");
            fclose(f);
            vx_vit_free(&v);
            exit(1);
        }
        if (rows != embed_dim || cols != file_n_labels) {
            fprintf(stderr,
                "vx_vit_load_warmstart: Wout shape mismatch: file=[%d,%d] expected=[%d,%d]\n",
                rows, cols, embed_dim, file_n_labels);
            fclose(f);
            vx_vit_free(&v);
            exit(1);
        }
        for (int r = 0; r < embed_dim; r++) {
            if (fread(&v.Wout->data[r * new_n_labels], sizeof(float), (size_t)file_n_labels, f)
                    != (size_t)file_n_labels) {
                fprintf(stderr, "vx_vit_load_warmstart: unexpected EOF reading Wout row %d\n", r);
                fclose(f);
                vx_vit_free(&v);
                exit(1);
            }
        }
    }

    fclose(f);

    if (new_n_labels > file_n_labels) {
        fprintf(stderr,
            "warm-start: loaded '%s'  (%d params  %d → %d labels  %d new classes Xavier-inited)\n",
            path, n_params, file_n_labels, new_n_labels, new_n_labels - file_n_labels);
    } else {
        fprintf(stderr,
            "warm-start: loaded '%s'  (%d params  n_labels=%d  no expansion)\n",
            path, n_params, file_n_labels);
    }

    return v;
}
