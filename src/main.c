#define _USE_MATH_DEFINES
#include "dataset.h"
#include "img.h"
#include "vit.h"
#include "tg_ops.h"
#include "tg_rng.h"
#include "tg_tensor.h"
#include "tg_train.h"

#ifdef OVG_CUDA_ENABLED
#include "tg_cuda.h"
#endif

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <conio.h>
#include <io.h>
#endif

enum {
    VX_IMAGE_H       = 256,
    VX_IMAGE_W       = 256,
    VX_IMAGE_C       = 3,
    VX_PATCH_H       = 8,
    VX_PATCH_W       = 8,
    VX_PATCH_SIZE    = VX_PATCH_H * VX_PATCH_W * VX_IMAGE_C,
    VX_N_PATCHES     = (VX_IMAGE_H / VX_PATCH_H) * (VX_IMAGE_W / VX_PATCH_W),
    VX_EMBED_DIM     = 192,
    VX_HIDDEN_DIM    = 512,
    VX_N_BLOCKS      = 6,
    VX_N_HEADS       = 6,
    VX_VIT_STEPS     = 60000,  // ~150 × n_classes (402 classes)
    VX_EVAL_AUGS     = 8,     // augmented versions per flag for robustness eval
    VX_IDENTIFY_TTA  = 8,     // augmented passes averaged at inference time
    VX_BATCH_SIZE    = 1,     // gradient accumulation batch size (1 = single sample per step)
    VX_WARMUP_STEPS  = 2400,  // ~4% × VX_VIT_STEPS
    VX_LABEL_SMOOTH  = 100,   // label smoothing epsilon × 1000 (e.g. 100 → ε=0.10); 0 = hard labels
    VX_DROP_PATH_RATE_X1000 = 100, // max stochastic depth drop rate × 1000 (0.10); 0 = disabled
    VX_DETECT_MAX_DIM            = 1024, // longer edge cap when loading for detection
    VX_DETECT_THRESHOLD_X10      =   35, // confidence threshold × 10; raised from 20 (see SPEC_V3_PHASE4_MODEL_OUTPUT.md §2)
    VX_DETECT_STRIDE_PCT         =   50, // window stride as % of window size
    VX_DETECT_MIN_CROP           =   64, // minimum window dimension (px) in working image
    VX_DETECT_SKIP_SUBWINDOWS_X10=   30, // skip sub-windows if scale-1 logit >= this ÷ 10
    VX_AMBIGUITY_MARGIN          =   10, // ambiguity gate: emit when margin < this / 100.0
    VX_BALANCED_SAMPLING         =    0  // 0 = round-robin (baseline default), 1 = class-balanced random
};

/* ── Phase 4 structs ── */

typedef struct {
    int   class_id;
    char  result_id[64];
    char  flag_id[64];
    char  display_name[128];
    char  category[32];
    char  fictionality[32];
    char  status[32];
    char  variant[32];
    char  short_description[256];
} VxClassMeta;

typedef struct {
    char confusable_id[64];
    int  level;        /* 0 = result-level, 1 = flag-level */
    char member_a[64];
    char member_b[64];
} VxConfusablePair;

/* Derive a sibling-file path: replaces the filename portion of base_path with filename. */
static void vx_sibling_path(const char *base_path, const char *filename, char *out, size_t out_size) {
    strncpy(out, base_path, out_size - 1);
    out[out_size - 1] = '\0';
    char *last = NULL;
    for (char *p = out; *p; p++)
        if (*p == '/' || *p == '\\') last = p;
    if (last)
        snprintf(last + 1, out_size - (size_t)(last + 1 - out), "%s", filename);
    else
        snprintf(out, out_size, "%s", filename);
}

/* Advance *p past next tab (or to end), returning the field start (NUL-terminated). */
static char *vx_tab_next(char **p) {
    if (!*p) return NULL;
    char *start = *p;
    char *tab = strchr(start, '\t');
    if (tab) { *tab = '\0'; *p = tab + 1; }
    else      { *p = NULL; }
    return start;
}

static VxClassMeta *vx_class_meta_load(const char *labels_path, int *out_n) {
    char path[512];
    vx_sibling_path(labels_path, "class_meta.tsv", path, sizeof(path));

    FILE *f = fopen(path, "r");
    if (!f) {
        fprintf(stderr, "error: cannot open class_meta.tsv at '%s'\n", path);
        exit(1);
    }

    char line[1024];
    /* discard header */
    if (!fgets(line, sizeof(line), f)) {
        fprintf(stderr, "error: class_meta.tsv is empty\n");
        fclose(f);
        exit(1);
    }

    int cap = 512;
    VxClassMeta *meta = malloc((size_t)cap * sizeof(VxClassMeta));
    if (!meta) { fprintf(stderr, "vx_class_meta_load: out of memory\n"); exit(1); }
    int n = 0;

    while (fgets(line, sizeof(line), f)) {
        int len = (int)strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) line[--len] = '\0';
        if (len == 0) continue;

        if (n >= cap) {
            cap *= 2;
            meta = realloc(meta, (size_t)cap * sizeof(VxClassMeta));
            if (!meta) { fprintf(stderr, "vx_class_meta_load: out of memory\n"); exit(1); }
        }

        VxClassMeta *m = &meta[n];
        char *rest = line;
        char *tok;

#define NEXT_META_FIELD(dst, size, name)                                          \
    tok = vx_tab_next(&rest);                                                     \
    if (!tok) { fprintf(stderr, "class_meta.tsv: missing '%s' on row %d\n", (name), n); exit(1); } \
    if (strlen(tok) >= (size)) { fprintf(stderr, "class_meta.tsv: class_id=%d field '%s' too long (%zu chars)\n", n, (name), strlen(tok)); exit(1); } \
    strncpy(dst, tok, (size) - 1); (dst)[(size)-1] = '\0'

        tok = vx_tab_next(&rest);
        if (!tok) { fprintf(stderr, "class_meta.tsv: missing class_id on row %d\n", n); exit(1); }
        int cid = atoi(tok);
        if (cid != n) {
            fprintf(stderr, "class_meta.tsv: expected class_id=%d, got %d\n", n, cid);
            exit(1);
        }
        m->class_id = cid;

        NEXT_META_FIELD(m->result_id,         sizeof(m->result_id),         "result_id");
        NEXT_META_FIELD(m->flag_id,           sizeof(m->flag_id),           "flag_id");
        NEXT_META_FIELD(m->display_name,      sizeof(m->display_name),      "display_name");
        NEXT_META_FIELD(m->category,          sizeof(m->category),          "category");
        NEXT_META_FIELD(m->fictionality,      sizeof(m->fictionality),      "fictionality");
        NEXT_META_FIELD(m->status,            sizeof(m->status),            "status");
        NEXT_META_FIELD(m->variant,           sizeof(m->variant),           "variant");
        NEXT_META_FIELD(m->short_description, sizeof(m->short_description), "short_description");
#undef NEXT_META_FIELD

        n++;
    }

    fclose(f);
    *out_n = n;
    return meta;
}

static VxConfusablePair *vx_confusable_pairs_load(const char *labels_path, int *out_n) {
    char path[512];
    vx_sibling_path(labels_path, "confusable_pairs.tsv", path, sizeof(path));

    FILE *f = fopen(path, "r");
    if (!f) {
        *out_n = 0;
        return NULL;
    }

    char line[512];
    /* discard header */
    if (!fgets(line, sizeof(line), f)) {
        fclose(f);
        *out_n = 0;
        return NULL;
    }

    int cap = 256;
    VxConfusablePair *pairs = malloc((size_t)cap * sizeof(VxConfusablePair));
    if (!pairs) { fprintf(stderr, "vx_confusable_pairs_load: out of memory\n"); exit(1); }
    int n = 0;

    while (fgets(line, sizeof(line), f)) {
        int len = (int)strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) line[--len] = '\0';
        if (len == 0) continue;

        if (n >= cap) {
            cap *= 2;
            pairs = realloc(pairs, (size_t)cap * sizeof(VxConfusablePair));
            if (!pairs) { fprintf(stderr, "vx_confusable_pairs_load: out of memory\n"); exit(1); }
        }

        VxConfusablePair *pr = &pairs[n];
        char *rest = line;
        char *tok;

#define NEXT_PAIR_FIELD(dst, size, name)                                          \
    tok = vx_tab_next(&rest);                                                     \
    if (!tok) { fprintf(stderr, "confusable_pairs.tsv: missing '%s' on row %d\n", (name), n); exit(1); } \
    strncpy(dst, tok, (size) - 1); (dst)[(size)-1] = '\0'

        NEXT_PAIR_FIELD(pr->confusable_id, sizeof(pr->confusable_id), "confusable_id");

        tok = vx_tab_next(&rest);
        if (!tok) { fprintf(stderr, "confusable_pairs.tsv: missing 'level' on row %d\n", n); exit(1); }
        if      (strcmp(tok, "result") == 0) pr->level = 0;
        else if (strcmp(tok, "flag")   == 0) pr->level = 1;
        else {
            fprintf(stderr, "confusable_pairs.tsv: unrecognized level '%s' on row %d\n", tok, n);
            exit(1);
        }

        NEXT_PAIR_FIELD(pr->member_a, sizeof(pr->member_a), "member_a");
        NEXT_PAIR_FIELD(pr->member_b, sizeof(pr->member_b), "member_b");
#undef NEXT_PAIR_FIELD

        n++;
    }

    fclose(f);
    *out_n = n;
    return pairs;
}

static void vx_softmax(const float *logits, float *probs, int n) {
    float max_l = logits[0];
    for (int i = 1; i < n; i++) if (logits[i] > max_l) max_l = logits[i];
    float sum = 0.0f;
    for (int i = 0; i < n; i++) { probs[i] = expf(logits[i] - max_l); sum += probs[i]; }
    for (int i = 0; i < n; i++) probs[i] /= sum;
}

static void vx_json_write_string(FILE *f, const char *s) {
    fputc('"', f);
    for (; *s; s++) {
        unsigned char c = (unsigned char)*s;
        if      (c == '"')  fputs("\\\"", f);
        else if (c == '\\') fputs("\\\\", f);
        else if (c < 0x20)  fprintf(f, "\\u%04x", c);
        else                fputc(c, f);
    }
    fputc('"', f);
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
    for (int i = 0; i < n; i++) if (items[i]) tg_free(items[i]);
    free(items);
}

static int path_exists(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    fclose(f);
    return 1;
}

/* Press 'p' during training or eval to pause; any key resumes. */
static void check_pause(void) {
#ifdef _WIN32
    if (!_kbhit()) return;
    int c = _getch();
    if (c != 'p' && c != 'P') return;
    printf("\n[paused -- press any key to resume]\n");
    fflush(stdout);
    _getch();
    printf("[resumed]\n");
    fflush(stdout);
#endif
}

/* Load images from dataset, optionally supplemented by up to two extra source directories.
   Layout: [0,n) primary, [n,2n) dir2, [2n,3n) dir3.
   Missing secondary/tertiary images are NULL; the training loop falls back to primary. */
static Tensor **load_images_multi(const VxDataset *dataset,
                                  const char *dir2, const char *dir3) {
    int n     = dataset->count;
    int n_src = 1 + (dir2 ? 1 : 0) + (dir3 ? 1 : 0);
    int total = n * n_src;
    Tensor **images = calloc((size_t)total, sizeof(Tensor *));
    if (!images) { fprintf(stderr, "load_images_multi: out of memory\n"); exit(1); }

    for (int i = 0; i < n; i++)
        images[i] = img_load(dataset->countries[i].flag_path,
                             VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C);

    const char *extra[2] = { dir2, dir3 };
    for (int s = 0; s < 2; s++) {
        if (!extra[s]) continue;
        int found = 0;
        for (int i = 0; i < n; i++) {
            const char *base = strrchr(dataset->countries[i].flag_path, '/');
            base = base ? base + 1 : dataset->countries[i].flag_path;
            char path2[512];
            snprintf(path2, sizeof(path2), "%s/%s", extra[s], base);
            if (path_exists(path2)) {
                images[(s + 1) * n + i] = img_load(path2, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C);
                found++;
            }
        }
        printf("source %d: %d/%d flags found in %s\n", s + 2, found, n, extra[s]);
    }

    return images;
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
   Tests robustness to the kinds of distortions seen in Discord-resized images.
   When eval_dump_path is non-NULL, writes a per-example prediction CSV to that path. */
static void vit_eval(VxViT *vit, Tensor **images, int n_flags,
                     const VxDataset *dataset, const char *eval_dump_path) {
    int top1 = 0, top3 = 0;
    int k = dataset->count < 3 ? dataset->count : 3;
    int top_indices[3];
    int total = n_flags * VX_EVAL_AUGS;

    FILE *dump_fp = NULL;
    if (eval_dump_path) {
        dump_fp = fopen(eval_dump_path, "w");
        if (!dump_fp) {
            char parent[512];
            strncpy(parent, eval_dump_path, sizeof(parent) - 1);
            parent[sizeof(parent) - 1] = '\0';
            char *last = NULL;
            for (char *p = parent; *p; p++)
                if (*p == '/' || *p == '\\') last = p;
            if (last) { *last = '\0'; fprintf(stderr, "eval-dump: directory does not exist: %s\n", parent); }
            else fprintf(stderr, "eval-dump: cannot open '%s' for writing\n", eval_dump_path);
            exit(1);
        }
        fprintf(dump_fp, "aug_pass,true_class_id,pred1_class_id,pred1_logit,"
                         "pred2_class_id,pred2_logit,pred3_class_id,pred3_logit\n");
    }

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

            if (dump_fp) {
                float l1 = logits->data[top_indices[0]];
                float l2 = (k >= 2) ? logits->data[top_indices[1]] : l1;
                float l3 = (k >= 3) ? logits->data[top_indices[2]] : l1;
                int   p2 = (k >= 2) ? top_indices[1] : top_indices[0];
                int   p3 = (k >= 3) ? top_indices[2] : top_indices[0];
                fprintf(dump_fp, "%d,%d,%d,%.6f,%d,%.6f,%d,%.6f\n",
                        a, i, top_indices[0], l1, p2, l2, p3, l3);
            }

            tg_free_graph(logits);
            tg_free(p);
        }
        if ((i + 1) % 10 == 0 || i == n_flags - 1) {
            printf("  %d/%d\r", i + 1, n_flags);
            fflush(stdout);
            check_pause();
        }
    }

    printf("\n");
    printf("eval (augmented, %d augs x %d flags):\n", VX_EVAL_AUGS, n_flags);
    printf("  top-1: %.2f%%  (%d/%d)\n", 100.0f * top1 / total, top1, total);
    printf("  top-3: %.2f%%  (%d/%d)\n", 100.0f * top3 / total, top3, total);

    if (dump_fp) fclose(dump_fp);
}

/* Run full identify pipeline (always TTA, no threshold gate) and print one TSV line:
   <path>\t<flag_id>\t<pre_tta_best_logit>\t<post_tta_avg_logit>
   On image-load failure: <path>\tERROR\tcannot load image */
static void identify_flag_batch_one(const char *path, VxViT *vit,
                                    const VxDataset *dataset) {
    int H = 0, W = 0;
    Tensor *full_img = img_load_native(path, VX_DETECT_MAX_DIM, VX_IMAGE_C, &H, &W);
    if (!full_img) {
        printf("%s\tERROR\tcannot load image\n", path);
        return;
    }
    int n = dataset->count;

    float best_logit = -1e38f;
    int best_y0 = 0, best_x0 = 0, best_crop_h = H, best_crop_w = W;

#define SCORE_CANDIDATE_B(cy0, cx0, ch, cw)                                      \
    do {                                                                          \
        Tensor *_crop = img_crop_and_resize(full_img, H, W, VX_IMAGE_C,          \
                                            (cy0), (cx0), (ch), (cw),            \
                                            VX_IMAGE_H, VX_IMAGE_W);             \
        Tensor *_p = img_patchify(_crop, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C,    \
                                  VX_PATCH_H, VX_PATCH_W);                       \
        _p->persistent = 1;                                                       \
        tg_free(_crop);                                                           \
        Tensor *_lg = vx_vit_forward(vit, _p);                                   \
        float _mx = _lg->data[0];                                                 \
        for (int _j = 1; _j < n; _j++)                                           \
            if (_lg->data[_j] > _mx) _mx = _lg->data[_j];                        \
        tg_free_graph(_lg);                                                       \
        tg_free(_p);                                                              \
        if (_mx > best_logit) {                                                   \
            best_logit = _mx;                                                     \
            best_y0 = (cy0); best_x0 = (cx0);                                    \
            best_crop_h = (ch); best_crop_w = (cw);                              \
        }                                                                         \
    } while (0)

    SCORE_CANDIDATE_B(0, 0, H, W);
    float scale1_logit = best_logit;

    if (scale1_logit < VX_DETECT_SKIP_SUBWINDOWS_X10 / 10.0f) {
        int min_side = H < W ? H : W;
        float scale_fracs[2] = { 0.75f, 0.50f };
        for (int s = 0; s < 2; s++) {
            int side = (int)(scale_fracs[s] * min_side);
            if (side < VX_DETECT_MIN_CROP) continue;
            int stride = side * VX_DETECT_STRIDE_PCT / 100;
            if (stride < 1) stride = 1;
            for (int cy0 = 0; cy0 + side <= H; cy0 += stride)
                for (int cx0 = 0; cx0 + side <= W; cx0 += stride)
                    SCORE_CANDIDATE_B(cy0, cx0, side, side);
        }
    }

#undef SCORE_CANDIDATE_B

    float pre_tta_logit = best_logit;

    /* Always run TTA — caller applies threshold in post-processing. */
    Tensor *win_crop = img_crop_and_resize(full_img, H, W, VX_IMAGE_C,
                                           best_y0, best_x0,
                                           best_crop_h, best_crop_w,
                                           VX_IMAGE_H, VX_IMAGE_W);
    tg_free(full_img);

    float *avg_logits = calloc((size_t)n, sizeof(float));
    if (!avg_logits) { fprintf(stderr, "identify_flag_batch_one: out of memory\n"); exit(1); }

    for (int a = 0; a < VX_IDENTIFY_TTA; a++) {
        Tensor *aug     = img_augment(win_crop, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C);
        Tensor *patches = img_patchify(aug, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C,
                                       VX_PATCH_H, VX_PATCH_W);
        patches->persistent = 1;
        tg_free(aug);
        Tensor *logits = vx_vit_forward(vit, patches);
        for (int j = 0; j < n; j++)
            avg_logits[j] += logits->data[j];
        tg_free_graph(logits);
        tg_free(patches);
    }
    tg_free(win_crop);

    float inv = 1.0f / VX_IDENTIFY_TTA;
    for (int j = 0; j < n; j++) avg_logits[j] *= inv;

    int best_idx = 0;
    for (int j = 1; j < n; j++)
        if (avg_logits[j] > avg_logits[best_idx]) best_idx = j;

    printf("%s\t%s\t%.6f\t%.6f\n",
           path,
           dataset->countries[best_idx].code,
           pre_tta_logit,
           avg_logits[best_idx]);

    free(avg_logits);
}

static void identify_flag(const char *path, VxViT *vit, const VxDataset *dataset,
                          int threshold_x10) {
    printf("\nidentify_flag: %s\n", path);

    int H = 0, W = 0;
    Tensor *full_img = img_load_native(path, VX_DETECT_MAX_DIM, VX_IMAGE_C, &H, &W);
    int n = dataset->count;

    float best_logit = -1e38f;
    int best_y0 = 0, best_x0 = 0, best_crop_h = H, best_crop_w = W;

    /* Score one candidate window and update running best. */
#define SCORE_CANDIDATE(cy0, cx0, ch, cw)                                        \
    do {                                                                          \
        Tensor *_crop = img_crop_and_resize(full_img, H, W, VX_IMAGE_C,          \
                                            (cy0), (cx0), (ch), (cw),            \
                                            VX_IMAGE_H, VX_IMAGE_W);             \
        Tensor *_p = img_patchify(_crop, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C,    \
                                  VX_PATCH_H, VX_PATCH_W);                       \
        _p->persistent = 1;                                                       \
        tg_free(_crop);                                                           \
        Tensor *_lg = vx_vit_forward(vit, _p);                                   \
        float _mx = _lg->data[0];                                                 \
        for (int _j = 1; _j < n; _j++)                                           \
            if (_lg->data[_j] > _mx) _mx = _lg->data[_j];                        \
        tg_free_graph(_lg);                                                       \
        tg_free(_p);                                                              \
        if (_mx > best_logit) {                                                   \
            best_logit = _mx;                                                     \
            best_y0 = (cy0); best_x0 = (cx0);                                    \
            best_crop_h = (ch); best_crop_w = (cw);                              \
        }                                                                         \
    } while (0)

    /* Scale 1: full image — always exactly one candidate. */
    SCORE_CANDIDATE(0, 0, H, W);
    float scale1_logit = best_logit;

    /* Scales 2 (75%) and 3 (50%): only run if scale-1 isn't already confident.
       Avoids sub-crops of a flag image beating the correct full-image answer. */
    if (scale1_logit < VX_DETECT_SKIP_SUBWINDOWS_X10 / 10.0f) {
        int min_side = H < W ? H : W;
        float scale_fracs[2] = { 0.75f, 0.50f };
        for (int s = 0; s < 2; s++) {
            int side = (int)(scale_fracs[s] * min_side);
            if (side < VX_DETECT_MIN_CROP) continue;
            int stride = side * VX_DETECT_STRIDE_PCT / 100;
            if (stride < 1) stride = 1;
            for (int cy0 = 0; cy0 + side <= H; cy0 += stride)
                for (int cx0 = 0; cx0 + side <= W; cx0 += stride)
                    SCORE_CANDIDATE(cy0, cx0, side, side);
        }
    }

#undef SCORE_CANDIDATE

    if (best_logit < threshold_x10 / 10.0f) {
        tg_free(full_img);
        printf("no flag detected\n");
        return;
    }

    /* Re-extract winner and run TTA. */
    Tensor *win_crop = img_crop_and_resize(full_img, H, W, VX_IMAGE_C,
                                           best_y0, best_x0,
                                           best_crop_h, best_crop_w,
                                           VX_IMAGE_H, VX_IMAGE_W);
    tg_free(full_img);

    float *avg_logits = calloc((size_t)n, sizeof(float));
    if (!avg_logits) { fprintf(stderr, "identify_flag: out of memory\n"); exit(1); }

    for (int a = 0; a < VX_IDENTIFY_TTA; a++) {
        Tensor *aug     = img_augment(win_crop, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C);
        Tensor *patches = img_patchify(aug, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C,
                                       VX_PATCH_H, VX_PATCH_W);
        patches->persistent = 1;
        tg_free(aug);

        Tensor *logits = vx_vit_forward(vit, patches);
        for (int j = 0; j < n; j++)
            avg_logits[j] += logits->data[j];

        tg_free_graph(logits);
        tg_free(patches);
    }

    tg_free(win_crop);

    float inv = 1.0f / VX_IDENTIFY_TTA;
    for (int j = 0; j < n; j++) avg_logits[j] *= inv;

    int k = n < 3 ? n : 3;
    int top_indices[3];
    topk_indices(avg_logits, n, k, top_indices);

    for (int r = 0; r < k; r++) {
        int idx = top_indices[r];
        printf("  #%d  %-4s  %-40s  logit: %.4f\n",
               r + 1,
               dataset->countries[idx].code,
               dataset->countries[idx].name,
               avg_logits[idx]);
    }

    free(avg_logits);
}

static void identify_flag_json_one(const char *path, const VxDataset *dataset,
                                    VxViT *vit,
                                    VxClassMeta *class_meta, int n_meta,
                                    VxConfusablePair *pairs, int n_pairs,
                                    int threshold_x10) {
    (void)n_meta;
    int n = dataset->count;
    int H = 0, W = 0;
    Tensor *full_img = img_load_native(path, VX_DETECT_MAX_DIM, VX_IMAGE_C, &H, &W);
    if (!full_img) {
        fprintf(stderr, "identify_flag_json: cannot load image '%s'\n", path);
        printf("{\"input_path\":");
        vx_json_write_string(stdout, path);
        printf(",\"detected\":false,\"results\":[],\"no_flag_reason\":\"load_error\"}\n");
        return;
    }

    float best_logit = -1e38f;
    int best_y0 = 0, best_x0 = 0, best_crop_h = H, best_crop_w = W;

#define SCORE_CANDIDATE_J(cy0, cx0, ch, cw)                                       \
    do {                                                                           \
        Tensor *_crop = img_crop_and_resize(full_img, H, W, VX_IMAGE_C,           \
                                            (cy0), (cx0), (ch), (cw),             \
                                            VX_IMAGE_H, VX_IMAGE_W);              \
        Tensor *_p = img_patchify(_crop, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C,     \
                                  VX_PATCH_H, VX_PATCH_W);                        \
        _p->persistent = 1;                                                        \
        tg_free(_crop);                                                            \
        Tensor *_lg = vx_vit_forward(vit, _p);                                    \
        float _mx = _lg->data[0];                                                  \
        for (int _j = 1; _j < n; _j++)                                            \
            if (_lg->data[_j] > _mx) _mx = _lg->data[_j];                         \
        tg_free_graph(_lg);                                                        \
        tg_free(_p);                                                               \
        if (_mx > best_logit) {                                                    \
            best_logit = _mx;                                                      \
            best_y0 = (cy0); best_x0 = (cx0);                                     \
            best_crop_h = (ch); best_crop_w = (cw);                               \
        }                                                                          \
    } while (0)

    SCORE_CANDIDATE_J(0, 0, H, W);
    float scale1_logit = best_logit;

    if (scale1_logit < VX_DETECT_SKIP_SUBWINDOWS_X10 / 10.0f) {
        int min_side = H < W ? H : W;
        float scale_fracs[2] = { 0.75f, 0.50f };
        for (int s = 0; s < 2; s++) {
            int side = (int)(scale_fracs[s] * min_side);
            if (side < VX_DETECT_MIN_CROP) continue;
            int stride = side * VX_DETECT_STRIDE_PCT / 100;
            if (stride < 1) stride = 1;
            for (int cy0 = 0; cy0 + side <= H; cy0 += stride)
                for (int cx0 = 0; cx0 + side <= W; cx0 += stride)
                    SCORE_CANDIDATE_J(cy0, cx0, side, side);
        }
    }

#undef SCORE_CANDIDATE_J

    /* No-detection: no window was scored (only possible if H==0 || W==0 somehow). */
    if (best_logit <= -1e37f) {
        tg_free(full_img);
        printf("{\"input_path\":");
        vx_json_write_string(stdout, path);
        printf(",\"detected\":false,\"results\":[],\"no_flag_reason\":\"no_detection\"}\n");
        return;
    }

    /* Below threshold: no flag. */
    if (best_logit < threshold_x10 / 10.0f) {
        tg_free(full_img);
        printf("{\"input_path\":");
        vx_json_write_string(stdout, path);
        printf(",\"detected\":false,\"results\":[],\"no_flag_reason\":\"below_threshold\"}\n");
        return;
    }

    /* Re-extract best window and run TTA. */
    Tensor *win_crop = img_crop_and_resize(full_img, H, W, VX_IMAGE_C,
                                           best_y0, best_x0,
                                           best_crop_h, best_crop_w,
                                           VX_IMAGE_H, VX_IMAGE_W);
    tg_free(full_img);

    float *avg_logits = calloc((size_t)n, sizeof(float));
    float *probs      = calloc((size_t)n, sizeof(float));
    if (!avg_logits || !probs) { fprintf(stderr, "identify_flag_json: out of memory\n"); exit(1); }

    for (int a = 0; a < VX_IDENTIFY_TTA; a++) {
        Tensor *aug     = img_augment(win_crop, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C);
        Tensor *patches = img_patchify(aug, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C,
                                       VX_PATCH_H, VX_PATCH_W);
        patches->persistent = 1;
        tg_free(aug);
        Tensor *logits = vx_vit_forward(vit, patches);
        for (int j = 0; j < n; j++) avg_logits[j] += logits->data[j];
        tg_free_graph(logits);
        tg_free(patches);
    }
    tg_free(win_crop);

    float inv = 1.0f / VX_IDENTIFY_TTA;
    for (int j = 0; j < n; j++) avg_logits[j] *= inv;

    int k = n < 3 ? n : 3;
    int top_indices[3] = { -1, -1, -1 };
    topk_indices(avg_logits, n, k, top_indices);

    vx_softmax(avg_logits, probs, n);

    float confidence[3], margin[3];
    for (int r = 0; r < k; r++)
        confidence[r] = probs[top_indices[r]];
    margin[0] = (k >= 2) ? confidence[0] - confidence[1] : 0.0f;
    margin[1] = (k >= 3) ? confidence[1] - confidence[2] : 0.0f;
    /* margin[2] is null per spec — do not compute or use. */

    /* Ambiguity check. */
    int has_ambiguity = 0;
    char ambig_cid[64] = "";
    if (n_pairs > 0 && k >= 2) {
        const char *rid1 = class_meta[top_indices[0]].result_id;
        const char *rid2 = class_meta[top_indices[1]].result_id;
        const char *fid1 = class_meta[top_indices[0]].flag_id;
        const char *fid2 = class_meta[top_indices[1]].flag_id;

        if (margin[0] < VX_AMBIGUITY_MARGIN / 100.0f) {
            for (int i = 0; i < n_pairs && !has_ambiguity; i++) {
                VxConfusablePair *cp = &pairs[i];
                if (cp->level == 0) {
                    if ((strcmp(cp->member_a, rid1) == 0 && strcmp(cp->member_b, rid2) == 0) ||
                        (strcmp(cp->member_a, rid2) == 0 && strcmp(cp->member_b, rid1) == 0)) {
                        has_ambiguity = 1;
                        strncpy(ambig_cid, cp->confusable_id, sizeof(ambig_cid) - 1);
                    }
                } else {
                    if ((strcmp(cp->member_a, fid1) == 0 && strcmp(cp->member_b, fid2) == 0) ||
                        (strcmp(cp->member_a, fid2) == 0 && strcmp(cp->member_b, fid1) == 0)) {
                        has_ambiguity = 1;
                        strncpy(ambig_cid, cp->confusable_id, sizeof(ambig_cid) - 1);
                    }
                }
            }
        }
    }

    /* Serialize compact NDJSON to stdout (one line, no internal newlines). */
    printf("{\"input_path\":");
    vx_json_write_string(stdout, path);
    printf(",\"detected\":true,\"results\":[");

    for (int r = 0; r < k; r++) {
        int idx = top_indices[r];
        VxClassMeta *m = &class_meta[idx];
        if (r > 0) printf(",");
        printf("{\"rank\":%d,", r + 1);
        printf("\"result_id\":"); vx_json_write_string(stdout, m->result_id); printf(",");
        printf("\"display_name\":"); vx_json_write_string(stdout, m->display_name); printf(",");
        printf("\"category\":"); vx_json_write_string(stdout, m->category); printf(",");
        printf("\"fictionality\":"); vx_json_write_string(stdout, m->fictionality); printf(",");
        printf("\"status\":"); vx_json_write_string(stdout, m->status); printf(",");
        printf("\"short_description\":"); vx_json_write_string(stdout, m->short_description); printf(",");
        printf("\"matched_flag_id\":"); vx_json_write_string(stdout, m->flag_id); printf(",");
        printf("\"matched_variant\":"); vx_json_write_string(stdout, m->variant); printf(",");
        printf("\"confidence\":%.4f,", confidence[r]);
        if (r == 2)
            printf("\"margin\":null}");
        else
            printf("\"margin\":%.4f}", margin[r]);
    }

    printf("],\"detection\":{\"crop\":{\"x\":%d,\"y\":%d,\"width\":%d,\"height\":%d},"
           "\"score\":%.4f,\"scaled_image_size\":{\"width\":%d,\"height\":%d}}",
           best_x0, best_y0, best_crop_w, best_crop_h, best_logit, W, H);

    if (has_ambiguity) {
        printf(",\"ambiguity\":{\"type\":\"known_confusable\","
               "\"message\":\"Top results are visually similar and confidence margin is small.\","
               "\"related_result_ids\":[");
        vx_json_write_string(stdout, class_meta[top_indices[0]].result_id);
        printf(",");
        vx_json_write_string(stdout, class_meta[top_indices[1]].result_id);
        printf("]}");
    } else {
        printf(",\"ambiguity\":null");
    }
    printf("}\n");

    free(avg_logits);
    free(probs);
}

static int identify_flag_json(const char *path, VxViT *vit, const VxDataset *dataset,
                               int threshold_x10,
                               VxClassMeta *class_meta, int n_meta,
                               VxConfusablePair *pairs, int n_pairs) {
    identify_flag_json_one(path, dataset, vit, class_meta, n_meta, pairs, n_pairs, threshold_x10);
    return 0;
}

int main(int argc, char **argv) {
    /* In JSON output modes, redirect the rng seed log to stderr so stdout stays clean JSON. */
    int json_stdout = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--identify-json") == 0 ||
            strcmp(argv[i], "--identify-json-batch") == 0) {
            json_stdout = 1;
            break;
        }
    }
    if (json_stdout) {
#ifdef _WIN32
        int saved_fd = _dup(_fileno(stdout));
        _dup2(_fileno(stderr), _fileno(stdout));
        tg_seed_from_entropy();
        fflush(stdout);
        _dup2(saved_fd, _fileno(stdout));
        _close(saved_fd);
#else
        int saved_fd = dup(fileno(stdout));
        dup2(fileno(stderr), fileno(stdout));
        tg_seed_from_entropy();
        fflush(stdout);
        dup2(saved_fd, fileno(stdout));
        close(saved_fd);
#endif
    } else {
        tg_seed_from_entropy();
    }

    /* Parse flags and positional args */
    const char *identify_path            = NULL;
    const char *identify_json_path       = NULL;
    const char *identify_batch_path      = NULL;
    const char *identify_json_batch_path = NULL;
    const char *weights_path        = "vit_weights.bin";
    const char *labels_path         = "data/labels.csv";
    const char *flags_dir           = "data/flags";
    const char *flags_dir2          = NULL;
    const char *flags_dir3          = NULL;
    const char *eval_dump_path      = NULL;
    const char *warmstart_path      = NULL;
    int detect_threshold_x10        = VX_DETECT_THRESHOLD_X10;

    int pos = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--identify") == 0 && i + 1 < argc) {
            identify_path = argv[++i];
        } else if (strcmp(argv[i], "--identify-json") == 0 && i + 1 < argc) {
            identify_json_path = argv[++i];
        } else if (strcmp(argv[i], "--identify-batch") == 0 && i + 1 < argc) {
            identify_batch_path = argv[++i];
        } else if (strcmp(argv[i], "--identify-json-batch") == 0 && i + 1 < argc) {
            identify_json_batch_path = argv[++i];
        } else if (strcmp(argv[i], "--weights") == 0 && i + 1 < argc) {
            weights_path = argv[++i];
        } else if (strcmp(argv[i], "--labels") == 0 && i + 1 < argc) {
            labels_path = argv[++i];
        } else if (strcmp(argv[i], "--eval-dump") == 0) {
            if (i + 1 >= argc || strncmp(argv[i + 1], "--", 2) == 0) {
                fprintf(stderr, "error: --eval-dump requires a path argument\n");
                exit(1);
            }
            eval_dump_path = argv[++i];
        } else if (strcmp(argv[i], "--detect-threshold-x10") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "error: --detect-threshold-x10 requires a positive integer argument\n");
                exit(1);
            }
            detect_threshold_x10 = atoi(argv[++i]);
            if (detect_threshold_x10 <= 0) {
                fprintf(stderr, "error: --detect-threshold-x10 value must be a positive integer\n");
                exit(1);
            }
        } else if (strcmp(argv[i], "--warmstart") == 0 && i + 1 < argc) {
            warmstart_path = argv[++i];
        } else if (pos == 0) { labels_path = argv[i]; pos++; }
          else if (pos == 1) { flags_dir   = argv[i]; pos++; }
          else if (pos == 2) { flags_dir2  = argv[i]; pos++; }
          else if (pos == 3) { flags_dir3  = argv[i]; pos++; }
    }

    /* Mutual exclusion: --identify and --identify-json cannot both be set. */
    if (identify_path && identify_json_path) {
        fprintf(stderr, "error: --identify and --identify-json are mutually exclusive\n");
        return 1;
    }
    /* --identify-json is not compatible with training positional dirs or --eval-dump. */
    if (identify_json_path && pos > 1) {
        fprintf(stderr, "error: --identify-json cannot be combined with training directory args\n");
        return 1;
    }
    if (identify_json_path && eval_dump_path) {
        fprintf(stderr, "error: --identify-json is not compatible with --eval-dump\n");
        return 1;
    }
    /* --identify-json-batch is mutually exclusive with other identify modes. */
    if (identify_json_batch_path && (identify_path || identify_json_path || identify_batch_path)) {
        fprintf(stderr, "error: --identify-json-batch cannot be combined with other identify modes\n");
        return 1;
    }
    if (identify_json_batch_path && pos > 1) {
        fprintf(stderr, "error: --identify-json-batch cannot be combined with training directory args\n");
        return 1;
    }
    if (identify_json_batch_path && eval_dump_path) {
        fprintf(stderr, "error: --identify-json-batch is not compatible with --eval-dump\n");
        return 1;
    }

    /* ── Identify JSON mode: structured output to stdout ── */
    if (identify_json_path) {
        tg_training = 0;
        VxDataset dataset = vx_dataset_load(labels_path, flags_dir);
        VxViT vit = vx_vit_load(weights_path);

        int n_meta = 0, n_pairs = 0;
        VxClassMeta *class_meta = vx_class_meta_load(labels_path, &n_meta);
        VxConfusablePair *conf_pairs = vx_confusable_pairs_load(labels_path, &n_pairs);

        if (n_meta != vit.n_labels) {
            fprintf(stderr, "error: class_meta has %d entries but model has %d labels\n",
                    n_meta, vit.n_labels);
            return 1;
        }

        int rc = identify_flag_json(identify_json_path, &vit, &dataset,
                                    detect_threshold_x10,
                                    class_meta, n_meta, conf_pairs, n_pairs);
        free(class_meta);
        if (conf_pairs) free(conf_pairs);
        vx_vit_free(&vit);
        vx_dataset_free(&dataset);
        return rc;
    }

    /* ── Identify JSON batch mode: NDJSON output, one object per image ── */
    if (identify_json_batch_path) {
        tg_training = 0;
        VxDataset dataset = vx_dataset_load(labels_path, flags_dir);
        VxViT vit = vx_vit_load(weights_path);

        int n_meta = 0, n_pairs = 0;
        VxClassMeta *class_meta = vx_class_meta_load(labels_path, &n_meta);
        VxConfusablePair *conf_pairs = vx_confusable_pairs_load(labels_path, &n_pairs);

        if (n_meta != vit.n_labels) {
            fprintf(stderr, "error: class_meta has %d entries but model has %d labels\n",
                    n_meta, vit.n_labels);
            return 1;
        }

        FILE *batch_f = fopen(identify_json_batch_path, "r");
        if (!batch_f) {
            fprintf(stderr, "error: cannot open batch list '%s'\n", identify_json_batch_path);
            return 1;
        }
        char line[4096];
        while (fgets(line, sizeof(line), batch_f)) {
            int len = (int)strlen(line);
            while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) line[--len] = '\0';
            if (len == 0) continue;
            identify_flag_json_one(line, &dataset, &vit, class_meta, n_meta, conf_pairs, n_pairs,
                                   VX_DETECT_THRESHOLD_X10);
            fflush(stdout);
        }
        fclose(batch_f);
        free(class_meta);
        if (conf_pairs) free(conf_pairs);
        vx_vit_free(&vit);
        vx_dataset_free(&dataset);
        return 0;
    }

    /* ── Identify mode: load weights and classify a single image ── */
    if (identify_path) {
        printf("vexilloscope identify mode\n");
        tg_training = 0;
        VxDataset dataset = vx_dataset_load(labels_path, flags_dir);
        VxViT vit = vx_vit_load(weights_path);
        identify_flag(identify_path, &vit, &dataset, detect_threshold_x10);
        vx_vit_free(&vit);
        vx_dataset_free(&dataset);
        return 0;
    }

    /* ── Batch identify mode: classify many images, one TSV line per image ── */
    if (identify_batch_path) {
        tg_training = 0;
        VxDataset dataset = vx_dataset_load(labels_path, flags_dir);
        VxViT vit = vx_vit_load(weights_path);
        FILE *list = fopen(identify_batch_path, "r");
        if (!list) {
            fprintf(stderr, "error: cannot open batch list '%s'\n", identify_batch_path);
            exit(1);
        }
        char line[4096];
        while (fgets(line, sizeof(line), list)) {
            /* strip trailing newline/carriage-return */
            int len = (int)strlen(line);
            while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) line[--len] = '\0';
            if (len == 0) continue;
            identify_flag_batch_one(line, &vit, &dataset);
            fflush(stdout);
        }
        fclose(list);
        vx_vit_free(&vit);
        vx_dataset_free(&dataset);
        return 0;
    }

    /* ── Train mode (default) ── */
    printf("vexilloscope v1\n");

    VxDataset dataset = vx_dataset_load(labels_path, flags_dir);
    vx_dataset_print_summary(&dataset);
    require_all_images_present(&dataset);

    Tensor **images  = load_images_multi(&dataset, flags_dir2, flags_dir3);
    Tensor **patches = make_patches(images, dataset.count);

    int n_flags  = dataset.count;
    int n_src    = 1 + (flags_dir2 ? 1 : 0) + (flags_dir3 ? 1 : 0);
    int n_images = n_flags * n_src;
    if (n_src > 1)
        printf("training on %d flags × %d sources = %d images\n", n_flags, n_src, n_images);
    else
        printf("training on all %d flags\n", n_flags);
    printf("baseline ln(%d) ~= %.6f\n", n_flags, logf((float)n_flags));

    printf("\nViT training  (augmentation + cosine LR)\n");
    printf("embed_dim=%d  hidden=%d  n_blocks=%d  n_heads=%d  steps=%d\n",
           VX_EMBED_DIM, VX_HIDDEN_DIM, VX_N_BLOCKS, VX_N_HEADS, VX_VIT_STEPS);

    VxViT vit = warmstart_path
        ? vx_vit_load_warmstart(warmstart_path, dataset.count)
        : vx_vit_create(VX_N_PATCHES, VX_PATCH_SIZE, VX_EMBED_DIM,
                        VX_HIDDEN_DIM, VX_N_BLOCKS, VX_N_HEADS, dataset.count,
                        VX_DROP_PATH_RATE_X1000 / 1000.0f);

    for (int i = 0; i < vit.encoder.n_blocks; i++)
        vit.encoder.blocks[i].dropout = 0.1f;

    Tensor *vit_params[3 + VX_N_BLOCKS * 12 + 1];
    int n_vit_params = vx_vit_collect_params(&vit, vit_params);

    float **adam_m = calloc((size_t)n_vit_params, sizeof(float *));
    float **adam_v = calloc((size_t)n_vit_params, sizeof(float *));
    if (!adam_m || !adam_v) { fprintf(stderr, "out of memory\n"); exit(1); }

#ifdef OVG_CUDA_ENABLED
    /* ── GPU path: upload all params and targets to GPU ── */
    printf("GPU training enabled (uploading params + targets)\n");
    for (int i = 0; i < n_vit_params; i++)
        tg_to_cuda(vit_params[i]);

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
            int idx, class_idx;
            if (VX_BALANCED_SAMPLING) {
                class_idx     = rand() % n_flags;
                int src_choice = rand() % n_src;
                idx            = src_choice * n_flags + class_idx;
            } else {
                idx       = ((step - 1) * VX_BATCH_SIZE + b) % n_images;
                class_idx = idx % n_flags;
            }

            Tensor *src = images[idx] ? images[idx] : images[class_idx];
            Tensor *aug = img_augment(src, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C);
            Tensor *p   = img_patchify(aug, VX_IMAGE_H, VX_IMAGE_W, VX_IMAGE_C,
                                       VX_PATCH_H, VX_PATCH_W);
            p->persistent = 1;
            tg_free(aug);

#ifdef OVG_CUDA_ENABLED
            tg_to_cuda(p);
#endif
            Tensor *logits      = vx_vit_forward(&vit, p);
            int class_ids[1] = { class_idx };
            Tensor *loss        = tg_cross_entropy_sparse(logits, class_ids, 1,
                                                          VX_LABEL_SMOOTH / 1000.0f);
            Tensor *scaled_loss = tg_scale(loss, inv_batch);

            batch_loss += tg_scalar_value(loss);

            tg_backward_accum(scaled_loss);
            tg_free_graph(scaled_loss);
#ifdef OVG_CUDA_ENABLED
            tg_cuda_free(p);
#endif
            tg_free(p);
        }

        batch_loss *= inv_batch;

        tg_clip_grad_norm(vit_params, n_vit_params, 1.0f, 1e-6f);

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
            check_pause();
        }
    }

#ifdef OVG_CUDA_ENABLED
    /* Pull GPU params back to CPU for eval and serialization */
    for (int i = 0; i < n_vit_params; i++) {
        tg_from_cuda(vit_params[i]);
        vit_params[i]->on_cuda = 0;
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
    vit_eval(&vit, images, n_flags, &dataset, eval_dump_path);

    /* Identify demo on 3 spread-out flags */
    int demo_indices[3] = { 0, n_flags / 2, n_flags - 1 };
    for (int d = 0; d < 3; d++)
        identify_flag(dataset.countries[demo_indices[d]].flag_path, &vit, &dataset,
                      VX_DETECT_THRESHOLD_X10);

    vx_vit_free(&vit);
    free_tensor_array(patches, dataset.count);
    free_tensor_array(images, n_images);
    vx_dataset_free(&dataset);
    return 0;
}
