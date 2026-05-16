#include "img.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"

Tensor *img_load(const char *path, int target_h, int target_w, int channels) {
    if (!path || target_h <= 0 || target_w <= 0 || channels <= 0) {
        fprintf(stderr, "img_load: invalid arguments\n");
        exit(1);
    }

    int width = 0;
    int height = 0;
    int file_channels = 0;
    int load_channels = channels == 3 ? 4 : channels;
    unsigned char *pixels = stbi_load(path, &width, &height, &file_channels, load_channels);
    if (!pixels) {
        fprintf(stderr, "img_load: failed to load '%s': %s\n", path, stbi_failure_reason());
        exit(1);
    }

    int src_w = width, src_h = height;
    unsigned char *buf = pixels;
    int buf_from_stbi = 1;

    if (src_h != target_h || src_w != target_w) {
        unsigned char *resized = malloc((size_t)target_h * target_w * load_channels);
        if (!resized) {
            fprintf(stderr, "img_load: out of memory resizing '%s'\n", path);
            stbi_image_free(pixels);
            exit(1);
        }
        float x_ratio = (target_w > 1) ? (float)(src_w - 1) / (float)(target_w - 1) : 0.0f;
        float y_ratio = (target_h > 1) ? (float)(src_h - 1) / (float)(target_h - 1) : 0.0f;
        for (int oy = 0; oy < target_h; oy++) {
            float fy = oy * y_ratio;
            int y0 = (int)fy;
            int y1 = y0 + 1 < src_h ? y0 + 1 : src_h - 1;
            float ty = fy - y0;
            for (int ox = 0; ox < target_w; ox++) {
                float fx = ox * x_ratio;
                int x0 = (int)fx;
                int x1 = x0 + 1 < src_w ? x0 + 1 : src_w - 1;
                float tx = fx - x0;
                for (int c = 0; c < load_channels; c++) {
                    float q00 = pixels[(y0 * src_w + x0) * load_channels + c];
                    float q10 = pixels[(y0 * src_w + x1) * load_channels + c];
                    float q01 = pixels[(y1 * src_w + x0) * load_channels + c];
                    float q11 = pixels[(y1 * src_w + x1) * load_channels + c];
                    float v = (1-tx)*(1-ty)*q00 + tx*(1-ty)*q10
                            + (1-tx)*   ty *q01 +    tx*ty *q11;
                    resized[(oy * target_w + ox) * load_channels + c] = (unsigned char)(v + 0.5f);
                }
            }
        }
        stbi_image_free(pixels);
        buf = resized;
        buf_from_stbi = 0;
    }

    int n = target_h * target_w * channels;
    Tensor *out = tg_new(1, n);

    if (channels == 3) {
        for (int i = 0; i < target_h * target_w; i++) {
            float alpha = buf[i * 4 + 3] / 255.0f;
            for (int c = 0; c < 3; c++) {
                float src = buf[i * 4 + c] / 255.0f;
                out->data[i * 3 + c] = src * alpha + (1.0f - alpha);
            }
        }
    } else {
        for (int i = 0; i < n; i++)
            out->data[i] = buf[i] / 255.0f;
    }

    if (buf_from_stbi) stbi_image_free(buf); else free(buf);
    return out;
}

Tensor *img_flip_h(const Tensor *img, int H, int W, int C) {
    Tensor *out = tg_new(1, H * W * C);
    for (int y = 0; y < H; y++) {
        for (int x = 0; x < W; x++) {
            int src_x = W - 1 - x;
            for (int c = 0; c < C; c++) {
                out->data[(y * W + x) * C + c] =
                    img->data[(y * W + src_x) * C + c];
            }
        }
    }
    return out;
}

Tensor *img_jitter(const Tensor *img, int H, int W, int C, float lo, float hi) {
    if (C > 4) {
        fprintf(stderr, "img_jitter: C=%d exceeds max supported channels (4)\n", C);
        exit(1);
    }
    Tensor *out = tg_new(1, H * W * C);
    /* Independent scale per channel */
    float scale[4];
    for (int c = 0; c < C; c++) {
        float t = (float)rand() / ((float)RAND_MAX + 1.0f);
        scale[c] = lo + t * (hi - lo);
    }
    for (int i = 0; i < H * W; i++) {
        for (int c = 0; c < C; c++) {
            float v = img->data[i * C + c] * scale[c];
            if (v < 0.0f) v = 0.0f;
            if (v > 1.0f) v = 1.0f;
            out->data[i * C + c] = v;
        }
    }
    return out;
}

Tensor *img_translate(const Tensor *img, int H, int W, int C, int dx, int dy) {
    Tensor *out = tg_new(1, H * W * C);
    for (int y = 0; y < H; y++) {
        for (int x = 0; x < W; x++) {
            int src_x = x - dx;
            int src_y = y - dy;
            for (int c = 0; c < C; c++) {
                float v = 1.0f; /* white fill for out-of-bounds */
                if (src_x >= 0 && src_x < W && src_y >= 0 && src_y < H)
                    v = img->data[(src_y * W + src_x) * C + c];
                out->data[(y * W + x) * C + c] = v;
            }
        }
    }
    return out;
}

Tensor *img_rotate(const Tensor *img, int H, int W, int C, float angle_rad) {
    Tensor *out = tg_new(1, H * W * C);
    float cx = (W - 1) * 0.5f;
    float cy = (H - 1) * 0.5f;
    float cos_a = cosf(-angle_rad);
    float sin_a = sinf(-angle_rad);
    for (int oy = 0; oy < H; oy++) {
        for (int ox = 0; ox < W; ox++) {
            float dx = ox - cx;
            float dy = oy - cy;
            float sx = cos_a * dx - sin_a * dy + cx;
            float sy = sin_a * dx + cos_a * dy + cy;
            for (int c = 0; c < C; c++) {
                float v = 1.0f;
                if (sx >= 0.0f && sx <= W - 1.0f && sy >= 0.0f && sy <= H - 1.0f) {
                    int x0 = (int)sx;
                    int y0 = (int)sy;
                    int x1 = x0 + 1 < W ? x0 + 1 : x0;
                    int y1 = y0 + 1 < H ? y0 + 1 : y0;
                    float tx = sx - x0;
                    float ty = sy - y0;
                    float q00 = img->data[(y0 * W + x0) * C + c];
                    float q10 = img->data[(y0 * W + x1) * C + c];
                    float q01 = img->data[(y1 * W + x0) * C + c];
                    float q11 = img->data[(y1 * W + x1) * C + c];
                    v = (1-tx)*(1-ty)*q00 + tx*(1-ty)*q10
                      + (1-tx)*   ty *q01 +    tx*ty *q11;
                }
                out->data[(oy * W + ox) * C + c] = v;
            }
        }
    }
    return out;
}

Tensor *img_augment(const Tensor *img, int H, int W, int C) {
    Tensor *cur = tg_new(1, H * W * C);
    int n = H * W * C;
    for (int i = 0; i < n; i++) cur->data[i] = img->data[i];

    /* Random horizontal flip (50%) */
    if (rand() & 1) {
        Tensor *tmp = img_flip_h(cur, H, W, C);
        tg_free(cur);
        cur = tmp;
    }

    /* Color jitter ×[0.85, 1.15] per channel */
    {
        Tensor *tmp = img_jitter(cur, H, W, C, 0.85f, 1.15f);
        tg_free(cur);
        cur = tmp;
    }

    /* Random translation ±4px */
    {
        int max_shift = 4;
        int dx = (rand() % (2 * max_shift + 1)) - max_shift;
        int dy = (rand() % (2 * max_shift + 1)) - max_shift;
        Tensor *tmp = img_translate(cur, H, W, C, dx, dy);
        tg_free(cur);
        cur = tmp;
    }

    /* Random rotation ±15° */
    {
        float max_angle = 15.0f * 3.14159265f / 180.0f;
        float t = (float)rand() / ((float)RAND_MAX + 1.0f);
        float angle = (t * 2.0f - 1.0f) * max_angle;
        Tensor *tmp = img_rotate(cur, H, W, C, angle);
        tg_free(cur);
        cur = tmp;
    }

    return cur;
}

Tensor *img_patchify(Tensor *img, int image_h, int image_w, int channels,
                     int patch_h, int patch_w) {
    if (!img || image_h <= 0 || image_w <= 0 || channels <= 0 ||
        patch_h <= 0 || patch_w <= 0) {
        fprintf(stderr, "img_patchify: invalid arguments\n");
        exit(1);
    }
    if (img->rows != 1 || img->cols != image_h * image_w * channels) {
        fprintf(stderr, "img_patchify: expected image [1x%d], got [%dx%d]\n",
                image_h * image_w * channels, img->rows, img->cols);
        exit(1);
    }
    if (image_h % patch_h != 0 || image_w % patch_w != 0) {
        fprintf(stderr, "img_patchify: image %dx%d not divisible by patch %dx%d\n",
                image_w, image_h, patch_w, patch_h);
        exit(1);
    }

    int patches_y = image_h / patch_h;
    int patches_x = image_w / patch_w;
    int n_patches = patches_y * patches_x;
    int patch_size = patch_h * patch_w * channels;
    Tensor *patches = tg_new(n_patches, patch_size);

    for (int py = 0; py < patches_y; py++) {
        for (int px = 0; px < patches_x; px++) {
            int patch_id = py * patches_x + px;
            int out_col = 0;
            for (int y = 0; y < patch_h; y++) {
                for (int x = 0; x < patch_w; x++) {
                    int img_y = py * patch_h + y;
                    int img_x = px * patch_w + x;
                    int img_base = (img_y * image_w + img_x) * channels;
                    for (int c = 0; c < channels; c++) {
                        patches->data[patch_id * patch_size + out_col] =
                            img->data[img_base + c];
                        out_col++;
                    }
                }
            }
        }
    }

    return patches;
}
