#define _USE_MATH_DEFINES
#include "dataset.h"
#include "img.h"
#include "vit.h"
#include "tg_ops.h"
#include "tg_tensor.h"
#include "tg_train.h"

#ifdef OVG_CUDA_ENABLED
#include "tg_cuda.h"
#endif

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    VX_IMAGE_H       = 128,
    VX_IMAGE_W       = 128,
    VX_IMAGE_C       = 3,
    VX_PATCH_H       = 8,
    VX_PATCH_W       = 8,
    VX_PATCH_SIZE    = VX_PATCH_H * VX_PATCH_W * VX_IMAGE_C,
    VX_N_PATCHES     = (VX_IMAGE_H / VX_PATCH_H) * (VX_IMAGE_W / VX_PATCH_W),
    VX_EMBED_DIM     = 128,
    VX_HIDDEN_DIM    = 256,
    VX_N_BLOCKS      = 6,
    VX_N_HEADS       = 4,
    VX_VIT_STEPS     = 50000,
    VX_EVAL_AUGS     = 8,     // augmented versions per flag for robustness eval
    VX_BATCH_SIZE    = 1,     // gradient accumulation batch size (1 = single sample per step)
    VX_WARMUP_STEPS  = 2000   // linear LR ramp; prevents early divergence in deep transformers
};

static Tensor *make_one_hot(int id, int n_classes) {
    Tensor *out = tg_new(1, n_classes);
    tg_fill(out, 0.0f);
    if (id < 0 || id >= n_classes) {
        fprintf(stderr, "make_one_hot: id %d out of range [0,%d)\n", id, n_classes);
        exit(1);
    }
    out->data[id]  = 1.0f;
    out->persistent = 1;
    return out;
}

static int argmax_row(const Tensor *t, int row) {
    int best = 0;
    float best_val = t->data[row * t->cols];
    for (int j = 1; j < t->cols; j++) {
        float v = t->data[row * t->cols + j];
        if (v > best_val) { best = j; best_val = v; }
    }
    return best;
}

static void require_all_images_present(const VxDataset *dataset) {
    int missing = 0;
    for (int i = 0; i < dataset->count; i++) {
        if (!dataset->countries[i].has_image) {
            fprintf(stderr, "missing flag image for %s at %s\n",
                    dataset->countries[i].code, dataset->countries[i].flag_path);
            missing++;
        }
    }
    if (missing > 0) {
        fprintf(stderr, "cannot train: %d flag images missing\n", missing);
        exit(1);
    }
}

static Tensor **load_images(const VxDataset *dataset) {
    Tensor **images = calloc((size_t)dataset->count, sizeof(Tensor *));
    if (!images) { fprintf(stderr, "load_images: out of memory\n"); exit(1); }
    for (int i = 0; i < dataset->count; i++)
        images[i] = img_load(dataset->countries[i].flag_path,
                             VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C);
    return images;
}

static Tensor **make_targets(int n_labels) {
    Tensor **targets = calloc((size_t)n_labels, sizeof(Tensor *));
    if (!targets) { fprintf(stderr, "make_targets: out of memory\n"); exit(1); }
    for (int i = 0; i < n_labels; i++)
        targets[i] = make_one_hot(i, n_labels);
    return targets;
}

static Tensor **make_patches(Tensor **images, int n) {
    Tensor **patches = calloc((size_t)n, sizeof(Tensor *));
    if (!patches) { fprintf(stderr, "make_patches: out of memory\n"); exit(1); }
    for (int i = 0; i < n; i++) {
        patches[i] = img_patchify(images[i], VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C,
                                  VX_PATCH_H, VX_PATCH_W);
        patches[i]->persistent = 1;
    }
    return patches;
}

static void free_tensor_array(Tensor **items, int n) {
    if (!items) return;
    for (int i = 0; i < n; i++) tg_free(items[i]);
    free(items);
}

/* Top-k: fills out[k] with indices of the k largest values in scores[n], sorted descending. */
static void topk_indices(const float *scores, int n, int k, int *out) {
    for (int i = 0; i < k; i++) out[i] = -1;

    for (int r = 0; r < k; r++) {
        float best = -1e38f;
        int   best_idx = -1;
        for (int j = 0; j < n; j++) {
            int already = 0;
            for (int p = 0; p < r; p++) if (out[p] == j) { already = 1; break; }
            if (!already && scores[j] > best) { best = scores[j]; best_idx = j; }
        }
        out[r] = best_idx;
    }
}

/* Eval: run VX_EVAL_AUGS augmented passes per flag, report aggregate top-1/top-3.
   Tests robustness to the kinds of distortions seen in Discord-resized images. */
static void vit_eval(VxViT *vit, Tensor **images, int n_flags,
                     const VxDataset *dataset) {
    int top1 = 0, top3 = 0;
    int k = dataset->count < 3 ? dataset->count : 3;
    int top_indices[3];
    int total = n_flags * VX_EVAL_AUGS;

    for (int i = 0; i < n_flags; i++) {
        for (int a = 0; a < VX_EVAL_AUGS; a++) {
            Tensor *aug = img_augment(images[i], VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C);
            Tensor *p   = img_patchify(aug, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C,
                                       VX_PATCH_H, VX_PATCH_W);
            p->persistent = 1;
            tg_free(aug);

            Tensor *logits = vx_vit_forward(vit, p);
            topk_indices(logits->data, dataset->count, k, top_indices);

            if (top_indices[0] == i) top1++;
            for (int r = 0; r < k; r++)
                if (top_indices[r] == i) { top3++; break; }

            tg_free_graph(logits);
            tg_free(p);
        }
    }

    printf("eval (augmented, %d augs × %d flags):\n", VX_EVAL_AUGS, n_flags);
    printf("  top-1: %.2f%%  (%d/%d)\n", 100.0f * top1 / total, top1, total);
    printf("  top-3: %.2f%%  (%d/%d)\n", 100.0f * top3 / total, top3, total);
}

static void identify_flag(const char *path, VxViT *vit, const VxDataset *dataset) {
    printf("\nidentify_flag: %s\n", path);

    Tensor *image   = img_load(path, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C);
    Tensor *patches = img_patchify(image, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C,
                                   VX_PATCH_H, VX_PATCH_W);
    patches->persistent = 1;

    Tensor *logits  = vx_vit_forward(vit, patches);

    int k = dataset->count < 3 ? dataset->count : 3;
    int top_indices[3];
    topk_indices(logits->data, dataset->count, k, top_indices);

    for (int r = 0; r < k; r++) {
        int idx = top_indices[r];
        printf("  #%d  %-4s  %-40s  logit: %.4f\n",
               r + 1,
               dataset->countries[idx].code,
               dataset->countries[idx].name,
               logits->data[idx]);
    }

    tg_free_graph(logits);
    tg_free(patches);
    tg_free(image);
}

int main(int argc, char **argv) {
    srand(42);

    /* Parse flags and positional args */
    const char *identify_path = NULL;
    const char *weights_path  = "vit_weights.bin";
    const char *labels_path   = "data/labels.csv";
    const char *flags_dir     = "data/flags";

    int pos = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--identify") == 0 && i + 1 < argc) {
            identify_path = argv[++i];
        } else if (strcmp(argv[i], "--weights") == 0 && i + 1 < argc) {
            weights_path = argv[++i];
        } else if (pos == 0) { labels_path = argv[i]; pos++; }
          else if (pos == 1) { flags_dir   = argv[i]; pos++; }
    }

    /* ── Identify mode: load weights and classify a single image ── */
    if (identify_path) {
        printf("vexilloscope identify mode\n");
        tg_training = 0;
        VxDataset dataset = vx_dataset_load(labels_path, flags_dir);
        VxViT vit = vx_vit_load(weights_path);
        identify_flag(identify_path, &vit, &dataset);
        vx_vit_free(&vit);
        vx_dataset_free(&dataset);
        return 0;
    }

    /* ── Train mode (default) ── */
    printf("vexilloscope v1\n");

    VxDataset dataset = vx_dataset_load(labels_path, flags_dir);
    vx_dataset_print_summary(&dataset);
    require_all_images_present(&dataset);

    Tensor **images  = load_images(&dataset);
    Tensor **targets = make_targets(dataset.count);
    Tensor **patches = make_patches(images, dataset.count);

    int n_flags = dataset.count;
    printf("training on all %d flags\n", n_flags);
    printf("baseline ln(%d) ~= %.6f\n", n_flags, logf((float)n_flags));

    printf("\nViT training  (augmentation + cosine LR)\n");
    printf("embed_dim=%d  hidden=%d  n_blocks=%d  n_heads=%d  steps=%d\n",
           VX_EMBED_DIM, VX_HIDDEN_DIM, VX_N_BLOCKS, VX_N_HEADS, VX_VIT_STEPS);

    VxViT vit = vx_vit_create(VX_N_PATCHES, VX_PATCH_SIZE, VX_EMBED_DIM,
                               VX_HIDDEN_DIM, VX_N_BLOCKS, VX_N_HEADS, dataset.count);

    for (int i = 0; i < vit.encoder.n_blocks; i++)
        vit.encoder.blocks[i].dropout = 0.1f;

    Tensor *vit_params[2 + VX_N_BLOCKS * 8 + 1];
    int n_vit_params = vx_vit_collect_params(&vit, vit_params);

    float **adam_m = calloc((size_t)n_vit_params, sizeof(float *));
    float **adam_v = calloc((size_t)n_vit_params, sizeof(float *));
    if (!adam_m || !adam_v) { fprintf(stderr, "out of memory\n"); exit(1); }

#ifdef OVG_CUDA_ENABLED
    /* ── GPU path: upload all params and targets to GPU ── */
    printf("GPU training enabled (uploading params + targets)\n");
    for (int i = 0; i < n_vit_params; i++)
        tg_to_cuda(vit_params[i]);
    for (int i = 0; i < dataset.count; i++)
        tg_to_cuda(targets[i]);

    float **adam_m_gpu = calloc((size_t)n_vit_params, sizeof(float *));
    float **adam_v_gpu = calloc((size_t)n_vit_params, sizeof(float *));
    if (!adam_m_gpu || !adam_v_gpu) { fprintf(stderr, "out of memory\n"); exit(1); }
    for (int i = 0; i < n_vit_params; i++) {
        int n = vit_params[i]->rows * vit_params[i]->cols;
        adam_m_gpu[i] = tg_cuda_malloc_floats(n);
        adam_v_gpu[i] = tg_cuda_malloc_floats(n);
    }
#else
    for (int i = 0; i < n_vit_params; i++) {
        size_t sz = (size_t)vit_params[i]->rows * vit_params[i]->cols;
        adam_m[i] = calloc((size_t)sz, sizeof(float));
        adam_v[i] = calloc((size_t)sz, sizeof(float));
        if (!adam_m[i] || !adam_v[i]) { fprintf(stderr, "out of memory\n"); exit(1); }
    }
#endif

    float lr_base = 3e-4f;
    for (int step = 1; step <= VX_VIT_STEPS; step++) {
        float cosine_lr = lr_base * 0.5f * (1.0f + cosf((float)M_PI * (step - 1) / VX_VIT_STEPS));
        float warmup    = step < VX_WARMUP_STEPS ? (float)step / VX_WARMUP_STEPS : 1.0f;
        float lr        = cosine_lr * warmup;
        float inv_batch = 1.0f / VX_BATCH_SIZE;

        /* Zero param grads once; tg_backward_accum will accumulate across the batch. */
        tg_zero_grads(vit_params, n_vit_params);

        float batch_loss = 0.0f;
        for (int b = 0; b < VX_BATCH_SIZE; b++) {
            int idx = ((step - 1) * VX_BATCH_SIZE + b) % n_flags;

            Tensor *aug = img_augment(images[idx], VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C);
            Tensor *p   = img_patchify(aug, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C,
                                       VX_PATCH_H, VX_PATCH_W);
            p->persistent = 1;
            tg_free(aug);

#ifdef OVG_CUDA_ENABLED
            tg_to_cuda(p);
#endif
            Tensor *logits      = vx_vit_forward(&vit, p);
            Tensor *loss        = tg_cross_entropy(logits, targets[idx]);
            Tensor *scaled_loss = tg_scale(loss, inv_batch);

            batch_loss += loss->data[0];   /* loss->data[0] is synced by tg_cross_entropy */

            tg_backward_accum(scaled_loss);
            tg_free_graph(scaled_loss);
#ifdef OVG_CUDA_ENABLED
            tg_cuda_free(p);
#endif
            tg_free(p);
        }

        batch_loss *= inv_batch;

#ifdef OVG_CUDA_ENABLED
        tg_adam_step_gpu(vit_params, adam_m_gpu, adam_v_gpu, n_vit_params, lr, step, 0.9f, 0.999f, 1e-8f);
#else
        tg_adam_step(vit_params, adam_m, adam_v, n_vit_params, lr, step, 0.9f, 0.999f, 1e-8f);
#endif

        if (step == 1 || step % 500 == 0) {
            if (step > 1) printf("\n");
            printf("step %5d/%d  loss: %.6f  lr: %.6f\n",
                   step, VX_VIT_STEPS, batch_loss, lr);
        } else if (step % 10 == 0) {
            printf(".");
            fflush(stdout);
        }
    }

#ifdef OVG_CUDA_ENABLED
    /* Pull GPU params back to CPU for eval and serialization */
    for (int i = 0; i < n_vit_params; i++) {
        tg_from_cuda(vit_params[i]);
        vit_params[i]->on_cuda = 0;
    }
    /* Pull targets off GPU too so eval's cross_entropy path is CPU */
    for (int i = 0; i < dataset.count; i++) {
        tg_cuda_free(targets[i]);
    }
    /* Free GPU optimizer moments */
    for (int i = 0; i < n_vit_params; i++) {
        tg_cuda_free_floats(adam_m_gpu[i]);
        tg_cuda_free_floats(adam_v_gpu[i]);
    }
    free(adam_m_gpu);
    free(adam_v_gpu);
#else
    for (int i = 0; i < n_vit_params; i++) { free(adam_m[i]); free(adam_v[i]); }
#endif
    free(adam_m);
    free(adam_v);

    /* Save trained weights (after GPU→CPU sync so params are up-to-date) */
    vx_vit_save(&vit, weights_path);

    tg_training = 0;

    /* Accuracy on clean (non-augmented) patches for all flags */
    int train_correct = 0;
    for (int i = 0; i < n_flags; i++) {
        Tensor *logits = vx_vit_forward(&vit, patches[i]);
        if (argmax_row(logits, 0) == i) train_correct++;
        tg_free_graph(logits);
    }
    printf("train accuracy (clean): %.2f%% (%d/%d)\n",
           100.0f * train_correct / n_flags, train_correct, n_flags);

    /* Augmented eval: robustness to distortion across all flags */
    printf("\naugmented eval (%d augs per flag):\n", VX_EVAL_AUGS);
    vit_eval(&vit, images, n_flags, &dataset);

    /* Identify demo on 3 spread-out flags */
    int demo_indices[3] = { 0, n_flags / 2, n_flags - 1 };
    for (int d = 0; d < 3; d++)
        identify_flag(dataset.countries[demo_indices[d]].flag_path, &vit, &dataset);

    vx_vit_free(&vit);
    free_tensor_array(patches, dataset.count);
    free_tensor_array(targets, dataset.count);
    free_tensor_array(images, dataset.count);
    vx_dataset_free(&dataset);
    return 0;
}
