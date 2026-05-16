#include "mlp_classifier.h"

#include "tg_ops.h"
#include "tg_tensor.h"

#include <stdio.h>
#include <stdlib.h>

VxMlpClassifier vx_mlp_create(int input_dim, int hidden_dim, int n_labels) {
    if (input_dim <= 0 || hidden_dim <= 0 || n_labels <= 0) {
        fprintf(stderr, "vx_mlp_create: invalid dimensions\n");
        exit(1);
    }

    VxMlpClassifier m;
    m.input_dim = input_dim;
    m.hidden_dim = hidden_dim;
    m.n_labels = n_labels;
    m.hidden = tg_linear_create(input_dim, hidden_dim, 1, 0.01f);
    m.output = tg_linear_create(hidden_dim, n_labels, 1, 0.01f);
    return m;
}

void vx_mlp_free(VxMlpClassifier *m) {
    if (!m) return;
    tg_linear_free(&m->hidden);
    tg_linear_free(&m->output);
}

VxMlpForward vx_mlp_forward_full(VxMlpClassifier *m, Tensor *image) {
    if (!m || !image) {
        fprintf(stderr, "vx_mlp_forward_full: null argument\n");
        exit(1);
    }
    if (image->rows != 1 || image->cols != m->input_dim) {
        fprintf(stderr, "vx_mlp_forward_full: expected image [1x%d], got [%dx%d]\n",
                m->input_dim, image->rows, image->cols);
        exit(1);
    }

    VxMlpForward f;
    f.xw1 = NULL;
    f.z1 = tg_linear_forward(&m->hidden, image, &f.xw1);
    f.h = tg_tanh(f.z1);
    f.xw2 = NULL;
    f.logits = tg_linear_forward(&m->output, f.h, &f.xw2);
    return f;
}

Tensor *vx_mlp_forward(VxMlpClassifier *m, Tensor *image) {
    VxMlpForward f = vx_mlp_forward_full(m, image);
    return f.logits;
}

void vx_mlp_forward_free(VxMlpForward *f) {
    if (!f) return;
    tg_free(f->logits);
    tg_free(f->xw2);
    tg_free(f->h);
    tg_free(f->z1);
    tg_free(f->xw1);
    f->logits = NULL;
    f->xw2 = NULL;
    f->h = NULL;
    f->z1 = NULL;
    f->xw1 = NULL;
}

int vx_mlp_collect_params(VxMlpClassifier *m, Tensor **params) {
    if (!m || !params) {
        fprintf(stderr, "vx_mlp_collect_params: null argument\n");
        exit(1);
    }

    params[0] = m->hidden.W;
    params[1] = m->hidden.B;
    params[2] = m->output.W;
    params[3] = m->output.B;
    return 4;
}
