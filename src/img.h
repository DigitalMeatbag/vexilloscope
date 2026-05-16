#ifndef VEXILLOSCOPE_IMG_H
#define VEXILLOSCOPE_IMG_H

#include "tg_tensor.h"

Tensor *img_load(const char *path, int target_h, int target_w, int channels);
Tensor *img_patchify(Tensor *img, int image_h, int image_w, int channels,
                     int patch_h, int patch_w);

/* Augmentation — each returns a new [1 × H*W*C] tensor; caller must tg_free it. */
Tensor *img_flip_h(const Tensor *img, int H, int W, int C);
Tensor *img_jitter(const Tensor *img, int H, int W, int C, float lo, float hi);
Tensor *img_translate(const Tensor *img, int H, int W, int C, int dx, int dy);
Tensor *img_rotate(const Tensor *img, int H, int W, int C, float angle_rad);

/* Combines flip + jitter + translate + rotate randomly using stdlib rand(). */
Tensor *img_augment(const Tensor *img, int H, int W, int C);

#endif
