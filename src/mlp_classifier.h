#ifndef VEXILLOSCOPE_MLP_CLASSIFIER_H
#define VEXILLOSCOPE_MLP_CLASSIFIER_H

#include "tg_mlp.h"

typedef struct {
    TgLinear hidden;   // [1 x 12288] -> [1 x hidden_dim]
    TgLinear output;   // [1 x hidden_dim] -> [1 x n_labels]
    int input_dim;
    int hidden_dim;
    int n_labels;
} VxMlpClassifier;

typedef struct {
    Tensor *xw1;
    Tensor *z1;
    Tensor *h;
    Tensor *xw2;
    Tensor *logits;
} VxMlpForward;

VxMlpClassifier vx_mlp_create(int input_dim, int hidden_dim, int n_labels);
void            vx_mlp_free(VxMlpClassifier *m);

VxMlpForward    vx_mlp_forward_full(VxMlpClassifier *m, Tensor *image);
Tensor         *vx_mlp_forward(VxMlpClassifier *m, Tensor *image);
void            vx_mlp_forward_free(VxMlpForward *f);

int             vx_mlp_collect_params(VxMlpClassifier *m, Tensor **params);

#endif
