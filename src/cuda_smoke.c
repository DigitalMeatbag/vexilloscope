/* cuda_smoke.c — verify GPU ops produce same results as CPU ops */
#include "tg_ops.h"
#include "tg_train.h"
#include "attention.h"

#ifdef OVG_CUDA_ENABLED
#include "tg_cuda.h"
#endif

#include <stdio.h>
#include <math.h>
#include <stdlib.h>

static int n_fail = 0;

static void check(const char *name, float cpu, float gpu, float tol) {
    float err = fabsf(cpu - gpu);
    if (err > tol) {
        printf("  FAIL %s: cpu=%.6f  gpu=%.6f  err=%.2e\n", name, cpu, gpu, err);
        n_fail++;
    } else {
        printf("  PASS %s: cpu=%.6f  gpu=%.6f  err=%.2e\n", name, cpu, gpu, err);
    }
}

static float max_err_array(const float *a, const float *b, int n) {
    float e = 0.0f;
    for (int i = 0; i < n; i++) e = fmaxf(e, fabsf(a[i] - b[i]));
    return e;
}

int main(void) {
#ifndef OVG_CUDA_ENABLED
    printf("cuda_smoke: built without OVG_CUDA_ENABLED — nothing to test\n");
    return 0;
#else
    printf("cuda_smoke: testing GPU ops vs CPU ops\n");

    // Test 1: 4×3 @ 3×2 = 4×2, known values
    printf("\n[matmul tests]\n");
    {
        Tensor *A = tg_new(4, 3);
        Tensor *B = tg_new(3, 2);
        float a_data[] = {1,2,3,  4,5,6,  7,8,9,  10,11,12};
        float b_data[] = {1,2,  3,4,  5,6};
        for (int i = 0; i < 12; i++) A->data[i] = a_data[i];
        for (int i = 0; i < 6;  i++) B->data[i] = b_data[i];

        // CPU
        Tensor *C_cpu = tg_matmul(A, B);

        // GPU: upload, run, download
        Tensor *A2 = tg_new(4, 3);
        Tensor *B2 = tg_new(3, 2);
        for (int i = 0; i < 12; i++) A2->data[i] = a_data[i];
        for (int i = 0; i < 6;  i++) B2->data[i] = b_data[i];
        tg_to_cuda(A2);
        tg_to_cuda(B2);
        Tensor *C_gpu = tg_matmul(A2, B2);
        tg_from_cuda(C_gpu);

        float me = max_err_array(C_cpu->data, C_gpu->data, 8);
        printf("  test1 (4x3 @ 3x2): max_err=%.2e  %s\n", me, me < 1e-3f ? "PASS" : "FAIL");
        if (me >= 1e-3f) n_fail++;

        tg_free_graph(C_cpu);
        tg_cuda_free(A2); tg_cuda_free(B2); tg_cuda_free(C_gpu);
        tg_free(A2); tg_free(B2); tg_free(C_gpu);
    }

    // Test 2: larger random matmul
    {
        int M = 64, K = 128, N = 64;
        Tensor *A = tg_new(M, K);
        Tensor *B = tg_new(K, N);
        for (int i = 0; i < M*K; i++) A->data[i] = (float)(i % 7) * 0.1f - 0.3f;
        for (int i = 0; i < K*N; i++) B->data[i] = (float)(i % 5) * 0.1f - 0.2f;

        Tensor *C_cpu = tg_matmul(A, B);

        Tensor *A2 = tg_new(M, K);
        Tensor *B2 = tg_new(K, N);
        for (int i = 0; i < M*K; i++) A2->data[i] = A->data[i];
        for (int i = 0; i < K*N; i++) B2->data[i] = B->data[i];
        tg_to_cuda(A2);
        tg_to_cuda(B2);
        Tensor *C_gpu = tg_matmul(A2, B2);
        tg_from_cuda(C_gpu);

        float me = max_err_array(C_cpu->data, C_gpu->data, M*N);
        printf("  test2 (%dx%d @ %dx%d): max_err=%.2e  %s\n",
               M, K, K, N, me, me < 1e-3f ? "PASS" : "FAIL");
        if (me >= 1e-3f) n_fail++;

        tg_free_graph(C_cpu);
        tg_cuda_free(A2); tg_cuda_free(B2); tg_cuda_free(C_gpu);
        tg_free(A2); tg_free(B2); tg_free(C_gpu);
    }

    // ── Layer norm ───────────────────────────────────────────────────────────
    printf("\n[layer_norm_rows tests]\n");
    {
        int R = 4, C = 8;
        Tensor *X = tg_new(R, C);
        for (int i = 0; i < R*C; i++) X->data[i] = (float)(i % 5) * 0.3f - 0.6f;

        Tensor *Y_cpu = tg_layer_norm_rows(X, 1e-5f);

        Tensor *X2 = tg_new(R, C);
        for (int i = 0; i < R*C; i++) X2->data[i] = X->data[i];
        tg_to_cuda(X2);
        Tensor *Y_gpu = tg_layer_norm_rows(X2, 1e-5f);
        tg_from_cuda(Y_gpu);

        float me = max_err_array(Y_cpu->data, Y_gpu->data, R*C);
        printf("  layer_norm [%dx%d]: max_err=%.2e  cpu[0]=%.6f  gpu[0]=%.6f  %s\n",
               R, C, me, Y_cpu->data[0], Y_gpu->data[0], me < 1e-4f ? "PASS" : "FAIL");
        if (me >= 1e-4f) n_fail++;

        tg_free_graph(Y_cpu);
        tg_cuda_free(X2); tg_cuda_free(Y_gpu);
        tg_free(X2); tg_free(Y_gpu);
    }

    // ── Softmax rows ─────────────────────────────────────────────────────────
    printf("\n[softmax_rows tests]\n");
    {
        int R = 2, C = 8;
        Tensor *X = tg_new(R, C);
        for (int i = 0; i < R*C; i++) X->data[i] = (float)(i % 5) * 0.5f - 1.0f;

        Tensor *Y_cpu = tg_softmax_rows(X);

        Tensor *X2 = tg_new(R, C);
        for (int i = 0; i < R*C; i++) X2->data[i] = X->data[i];
        tg_to_cuda(X2);
        Tensor *Y_gpu = tg_softmax_rows(X2);
        tg_from_cuda(Y_gpu);

        float me = max_err_array(Y_cpu->data, Y_gpu->data, R*C);
        printf("  softmax_rows [%dx%d]: max_err=%.2e  cpu[0]=%.6f  gpu[0]=%.6f  %s\n",
               R, C, me, Y_cpu->data[0], Y_gpu->data[0], me < 1e-4f ? "PASS" : "FAIL");
        if (me >= 1e-4f) n_fail++;

        tg_free_graph(Y_cpu);
        tg_cuda_free(X2); tg_cuda_free(Y_gpu);
        tg_free(X2); tg_free(Y_gpu);
    }

    // ── Cross entropy ────────────────────────────────────────────────────────
    printf("\n[cross_entropy tests]\n");
    {
        // 1×4 logits, one-hot class 2
        int R = 1, C = 4;
        Tensor *logits = tg_new(R, C);
        Tensor *targets = tg_new(R, C);
        float lg[] = {1.0f, 2.0f, 3.0f, 4.0f};
        float tg_data[] = {0.0f, 0.0f, 1.0f, 0.0f};
        for (int i = 0; i < C; i++) { logits->data[i] = lg[i]; targets->data[i] = tg_data[i]; }

        Tensor *loss_cpu = tg_cross_entropy(logits, targets);

        Tensor *lg2 = tg_new(R, C);
        Tensor *tg2 = tg_new(R, C);
        for (int i = 0; i < C; i++) { lg2->data[i] = lg[i]; tg2->data[i] = tg_data[i]; }
        tg_to_cuda(lg2); tg_to_cuda(tg2);
        Tensor *loss_gpu = tg_cross_entropy(lg2, tg2);
        // tg_cross_entropy already calls tg_from_cuda for the GPU path

        check("ce_1x4_class2", loss_cpu->data[0], loss_gpu->data[0], 1e-4f);

        tg_free_graph(loss_cpu);
        tg_cuda_free(lg2); tg_cuda_free(tg2); tg_cuda_free(loss_gpu);
        tg_free(lg2); tg_free(tg2); tg_free(loss_gpu);
    }

    {
        // 1×255 all-zero logits, one-hot class 0 → CE = log(255) ≈ 5.5413
        int R = 1, C = 255;
        Tensor *logits = tg_new(R, C);
        Tensor *targets = tg_new(R, C);
        targets->data[0] = 1.0f;  // class 0

        Tensor *loss_cpu = tg_cross_entropy(logits, targets);

        Tensor *lg2 = tg_new(R, C);
        Tensor *tg2 = tg_new(R, C);
        tg2->data[0] = 1.0f;
        tg_to_cuda(lg2); tg_to_cuda(tg2);
        Tensor *loss_gpu = tg_cross_entropy(lg2, tg2);

        float expected = logf(255.0f);
        printf("  ce_1x255_uniform: expected=%.6f  cpu=%.6f  gpu=%.6f  %s\n",
               expected, loss_cpu->data[0], loss_gpu->data[0],
               fabsf(loss_cpu->data[0] - loss_gpu->data[0]) < 1e-3f ? "PASS" : "FAIL");
        if (fabsf(loss_cpu->data[0] - loss_gpu->data[0]) >= 1e-3f) n_fail++;

        tg_free_graph(loss_cpu);
        tg_cuda_free(lg2); tg_cuda_free(tg2); tg_cuda_free(loss_gpu);
        tg_free(lg2); tg_free(tg2); tg_free(loss_gpu);
    }

    // ── mean_rows ────────────────────────────────────────────────────────────
    printf("\n[mean_rows tests]\n");
    {
        int R = 8, C = 16;
        Tensor *X = tg_new(R, C);
        for (int i = 0; i < R*C; i++) X->data[i] = (float)(i % 7) * 0.1f - 0.3f;

        Tensor *Y_cpu = tg_mean_rows(X);

        Tensor *X2 = tg_new(R, C);
        for (int i = 0; i < R*C; i++) X2->data[i] = X->data[i];
        tg_to_cuda(X2);
        Tensor *Y_gpu = tg_mean_rows(X2);
        tg_from_cuda(Y_gpu);

        float me = max_err_array(Y_cpu->data, Y_gpu->data, C);
        printf("  mean_rows [%dx%d]: max_err=%.2e  cpu[0]=%.6f  gpu[0]=%.6f  %s\n",
               R, C, me, Y_cpu->data[0], Y_gpu->data[0], me < 1e-4f ? "PASS" : "FAIL");
        if (me >= 1e-4f) n_fail++;

        tg_free_graph(Y_cpu);
        tg_cuda_free(X2); tg_cuda_free(Y_gpu);
        tg_free(X2); tg_free(Y_gpu);
    }

    // ── Mini forward+backward: patches@PatchEmb + PosEmb → mean_rows → @Wout → CE ──
    printf("\n[mini forward+backward: patches@PE + Pos → mean_rows → @Wout → CE]\n");
    {
        int T = 4, P = 6, C2 = 8, L = 4;
        // Create matching CPU and GPU models
        float *pe_data = malloc(P * C2 * sizeof(float));
        float *pos_data = malloc(T * C2 * sizeof(float));
        float *wo_data = malloc(C2 * L * sizeof(float));
        float *patch_data = malloc(T * P * sizeof(float));
        for (int i = 0; i < P*C2; i++) pe_data[i]   = (float)(i % 7) * 0.05f - 0.15f;
        for (int i = 0; i < T*C2; i++) pos_data[i]  = (float)(i % 5) * 0.04f - 0.08f;
        for (int i = 0; i < C2*L; i++) wo_data[i]   = (float)(i % 6) * 0.06f - 0.15f;
        for (int i = 0; i < T*P; i++)  patch_data[i] = (float)(i % 9) * 0.1f - 0.4f;

        // CPU forward
        Tensor *patches_c = tg_new(T, P);
        Tensor *PE_c = tg_new(P, C2);
        Tensor *Pos_c = tg_new(T, C2);
        Tensor *Wo_c = tg_new(C2, L);
        Tensor *tgt_c = tg_new(1, L);
        for (int i = 0; i < T*P; i++)  patches_c->data[i] = patch_data[i];
        for (int i = 0; i < P*C2; i++) PE_c->data[i]  = pe_data[i];
        for (int i = 0; i < T*C2; i++) Pos_c->data[i] = pos_data[i];
        for (int i = 0; i < C2*L; i++) Wo_c->data[i]  = wo_data[i];
        tgt_c->data[1] = 1.0f;  // one-hot class 1
        patches_c->persistent = PE_c->persistent = Pos_c->persistent = Wo_c->persistent = tgt_c->persistent = 1;

        Tensor *emb_c = tg_matmul(patches_c, PE_c);
        Tensor *X_c   = tg_add(emb_c, Pos_c);
        Tensor *pool_c = tg_mean_rows(X_c);
        Tensor *logits_c = tg_matmul(pool_c, Wo_c);
        Tensor *loss_c = tg_cross_entropy(logits_c, tgt_c);
        tg_backward(loss_c);

        // GPU forward
        Tensor *patches_g = tg_new(T, P);
        Tensor *PE_g = tg_new(P, C2);
        Tensor *Pos_g = tg_new(T, C2);
        Tensor *Wo_g = tg_new(C2, L);
        Tensor *tgt_g = tg_new(1, L);
        for (int i = 0; i < T*P; i++)  patches_g->data[i] = patch_data[i];
        for (int i = 0; i < P*C2; i++) PE_g->data[i]  = pe_data[i];
        for (int i = 0; i < T*C2; i++) Pos_g->data[i] = pos_data[i];
        for (int i = 0; i < C2*L; i++) Wo_g->data[i]  = wo_data[i];
        tgt_g->data[1] = 1.0f;
        patches_g->persistent = PE_g->persistent = Pos_g->persistent = Wo_g->persistent = tgt_g->persistent = 1;
        tg_to_cuda(patches_g); tg_to_cuda(PE_g); tg_to_cuda(Pos_g); tg_to_cuda(Wo_g); tg_to_cuda(tgt_g);

        Tensor *emb_g = tg_matmul(patches_g, PE_g);
        Tensor *X_g   = tg_add(emb_g, Pos_g);
        Tensor *pool_g = tg_mean_rows(X_g);
        Tensor *logits_g = tg_matmul(pool_g, Wo_g);
        Tensor *loss_g = tg_cross_entropy(logits_g, tgt_g);
        tg_backward(loss_g);

        // Compare loss
        check("mini_fwd_loss", loss_c->data[0], loss_g->data[0], 1e-4f);

        // Compare logits
        tg_from_cuda(logits_g);
        float logits_err = max_err_array(logits_c->data, logits_g->data, L);
        printf("  mini_fwd logits max_err=%.2e  %s\n", logits_err,
               logits_err < 1e-4f ? "PASS" : "FAIL");
        if (logits_err >= 1e-4f) n_fail++;

        // Compare gradients of Wout (Wo)
        tg_from_cuda(Wo_g);
        float grad_err = max_err_array(Wo_c->grad, Wo_g->grad, C2*L);
        printf("  mini_bwd Wout grad max_err=%.2e  cpu[0]=%.6f  gpu[0]=%.6f  %s\n",
               grad_err, Wo_c->grad[0], Wo_g->grad[0],
               grad_err < 1e-4f ? "PASS" : "FAIL");
        if (grad_err >= 1e-4f) n_fail++;

        // Compare gradients of PE
        tg_from_cuda(PE_g);
        float pe_grad_err = max_err_array(PE_c->grad, PE_g->grad, P*C2);
        printf("  mini_bwd PatchEmb grad max_err=%.2e  cpu[0]=%.6f  gpu[0]=%.6f  %s\n",
               pe_grad_err, PE_c->grad[0], PE_g->grad[0],
               pe_grad_err < 1e-4f ? "PASS" : "FAIL");
        if (pe_grad_err >= 1e-4f) n_fail++;

        free(pe_data); free(pos_data); free(wo_data); free(patch_data);
        tg_free_graph(loss_c);
        tg_free(patches_c); tg_free(PE_c); tg_free(Pos_c); tg_free(Wo_c); tg_free(tgt_c);
        tg_cuda_free(patches_g); tg_cuda_free(PE_g); tg_cuda_free(Pos_g);
        tg_cuda_free(Wo_g); tg_cuda_free(tgt_g);
        tg_free_graph(loss_g);
        tg_free(patches_g); tg_free(PE_g); tg_free(Pos_g); tg_free(Wo_g); tg_free(tgt_g);
    }

    // ── Mini forward with layer_norm + attention ─────────────────────────────
    printf("\n[mini transformer block: LN + self-attn + add + LN + FFN + add → mean_rows → CE]\n");
    {
        int T = 4, C2 = 8, H = 16, L = 4, n_heads = 2;
        int head_dim = C2 / n_heads;

        float *x_data = malloc(T * C2 * sizeof(float));
        float *wq_data = malloc(C2 * C2 * sizeof(float));
        float *wk_data = malloc(C2 * C2 * sizeof(float));
        float *wv_data = malloc(C2 * C2 * sizeof(float));
        float *wo_data = malloc(C2 * C2 * sizeof(float));
        float *w1_data = malloc(C2 * H * sizeof(float));
        float *b1_data = malloc(T * H * sizeof(float));
        float *w2_data = malloc(H * C2 * sizeof(float));
        float *b2_data = malloc(T * C2 * sizeof(float));
        float *wout_data = malloc(C2 * L * sizeof(float));

        for (int i = 0; i < T*C2; i++)  x_data[i]    = (float)(i%7)*0.05f - 0.15f;
        for (int i = 0; i < C2*C2; i++) wq_data[i]   = (float)(i%5)*0.04f - 0.08f;
        for (int i = 0; i < C2*C2; i++) wk_data[i]   = (float)(i%6)*0.03f - 0.07f;
        for (int i = 0; i < C2*C2; i++) wv_data[i]   = (float)(i%7)*0.04f - 0.09f;
        for (int i = 0; i < C2*C2; i++) wo_data[i]   = (float)(i%5)*0.05f - 0.10f;
        for (int i = 0; i < C2*H; i++)  w1_data[i]   = (float)(i%8)*0.03f - 0.10f;
        for (int i = 0; i < T*H; i++)   b1_data[i]   = 0.0f;
        for (int i = 0; i < H*C2; i++)  w2_data[i]   = (float)(i%6)*0.03f - 0.08f;
        for (int i = 0; i < T*C2; i++)  b2_data[i]   = 0.0f;
        for (int i = 0; i < C2*L; i++)  wout_data[i] = (float)(i%5)*0.06f - 0.12f;

        // ─── CPU ───
        Tensor *X_c   = tg_new(T, C2);
        Tensor *Wq_c  = tg_new(C2, C2), *Wk_c = tg_new(C2, C2), *Wv_c = tg_new(C2, C2), *Wao_c = tg_new(C2, C2);
        Tensor *W1_c  = tg_new(C2, H),  *B1_c = tg_new(T, H);
        Tensor *W2_c  = tg_new(H, C2),  *B2_c = tg_new(T, C2);
        Tensor *Wout_c = tg_new(C2, L);
        Tensor *tgt_c = tg_new(1, L);
        tgt_c->data[2] = 1.0f;

        for (int i = 0; i < T*C2; i++) X_c->data[i] = x_data[i];
        for (int i = 0; i < C2*C2; i++) { Wq_c->data[i]=wq_data[i]; Wk_c->data[i]=wk_data[i]; Wv_c->data[i]=wv_data[i]; Wao_c->data[i]=wo_data[i]; }
        for (int i = 0; i < C2*H; i++) W1_c->data[i] = w1_data[i];
        for (int i = 0; i < T*H; i++) B1_c->data[i] = b1_data[i];
        for (int i = 0; i < H*C2; i++) W2_c->data[i] = w2_data[i];
        for (int i = 0; i < T*C2; i++) B2_c->data[i] = b2_data[i];
        for (int i = 0; i < C2*L; i++) Wout_c->data[i] = wout_data[i];

        X_c->persistent = Wq_c->persistent = Wk_c->persistent = Wv_c->persistent = Wao_c->persistent = 1;
        W1_c->persistent = B1_c->persistent = W2_c->persistent = B2_c->persistent = Wout_c->persistent = tgt_c->persistent = 1;

        // pre-norm block (encoder, no causal mask)
        Tensor *LN1_c = tg_layer_norm_rows(X_c, 1e-5f);
        Tensor *Q_c = tg_matmul(LN1_c, Wq_c);
        Tensor *K_c = tg_matmul(LN1_c, Wk_c);
        Tensor *V_c = tg_matmul(LN1_c, Wv_c);
        // single head (n_heads=2, head_dim=4): just use full Q,K,V for simplicity
        Tensor *KT_c = tg_transpose(K_c);
        Tensor *scores_c = tg_matmul(Q_c, KT_c);
        float scale = 1.0f / sqrtf((float)C2);
        Tensor *scores_s_c = tg_scale(scores_c, scale);
        Tensor *weights_c = tg_softmax_rows(scores_s_c);
        Tensor *attn_c = tg_matmul(weights_c, V_c);
        Tensor *proj_c = tg_matmul(attn_c, Wao_c);
        Tensor *Y1_c = tg_add(X_c, proj_c);
        Tensor *LN2_c = tg_layer_norm_rows(Y1_c, 1e-5f);
        Tensor *F1_c = tg_matmul(LN2_c, W1_c);
        Tensor *F1b_c = tg_add(F1_c, B1_c);
        Tensor *F1t_c = tg_tanh(F1b_c);
        Tensor *F2_c = tg_matmul(F1t_c, W2_c);
        Tensor *F2b_c = tg_add(F2_c, B2_c);
        Tensor *Y2_c = tg_add(Y1_c, F2b_c);
        Tensor *pool_c = tg_mean_rows(Y2_c);
        Tensor *logits_c = tg_matmul(pool_c, Wout_c);
        Tensor *loss_c = tg_cross_entropy(logits_c, tgt_c);
        tg_backward(loss_c);

        // ─── GPU ───
        Tensor *X_g   = tg_new(T, C2);
        Tensor *Wq_g  = tg_new(C2, C2), *Wk_g = tg_new(C2, C2), *Wv_g = tg_new(C2, C2), *Wao_g = tg_new(C2, C2);
        Tensor *W1_g  = tg_new(C2, H),  *B1_g = tg_new(T, H);
        Tensor *W2_g  = tg_new(H, C2),  *B2_g = tg_new(T, C2);
        Tensor *Wout_g = tg_new(C2, L);
        Tensor *tgt_g = tg_new(1, L);
        tgt_g->data[2] = 1.0f;

        for (int i = 0; i < T*C2; i++) X_g->data[i] = x_data[i];
        for (int i = 0; i < C2*C2; i++) { Wq_g->data[i]=wq_data[i]; Wk_g->data[i]=wk_data[i]; Wv_g->data[i]=wv_data[i]; Wao_g->data[i]=wo_data[i]; }
        for (int i = 0; i < C2*H; i++) W1_g->data[i] = w1_data[i];
        for (int i = 0; i < T*H; i++) B1_g->data[i] = b1_data[i];
        for (int i = 0; i < H*C2; i++) W2_g->data[i] = w2_data[i];
        for (int i = 0; i < T*C2; i++) B2_g->data[i] = b2_data[i];
        for (int i = 0; i < C2*L; i++) Wout_g->data[i] = wout_data[i];

        X_g->persistent = Wq_g->persistent = Wk_g->persistent = Wv_g->persistent = Wao_g->persistent = 1;
        W1_g->persistent = B1_g->persistent = W2_g->persistent = B2_g->persistent = Wout_g->persistent = tgt_g->persistent = 1;
        tg_to_cuda(X_g); tg_to_cuda(Wq_g); tg_to_cuda(Wk_g); tg_to_cuda(Wv_g); tg_to_cuda(Wao_g);
        tg_to_cuda(W1_g); tg_to_cuda(B1_g); tg_to_cuda(W2_g); tg_to_cuda(B2_g);
        tg_to_cuda(Wout_g); tg_to_cuda(tgt_g);

        Tensor *LN1_g = tg_layer_norm_rows(X_g, 1e-5f);
        Tensor *Q_g = tg_matmul(LN1_g, Wq_g);
        Tensor *K_g = tg_matmul(LN1_g, Wk_g);
        Tensor *V_g = tg_matmul(LN1_g, Wv_g);
        Tensor *KT_g = tg_transpose(K_g);
        Tensor *scores_g = tg_matmul(Q_g, KT_g);
        Tensor *scores_s_g = tg_scale(scores_g, scale);
        Tensor *weights_g = tg_softmax_rows(scores_s_g);
        Tensor *attn_g = tg_matmul(weights_g, V_g);
        Tensor *proj_g = tg_matmul(attn_g, Wao_g);
        Tensor *Y1_g = tg_add(X_g, proj_g);
        Tensor *LN2_g = tg_layer_norm_rows(Y1_g, 1e-5f);
        Tensor *F1_g = tg_matmul(LN2_g, W1_g);
        Tensor *F1b_g = tg_add(F1_g, B1_g);
        Tensor *F1t_g = tg_tanh(F1b_g);
        Tensor *F2_g = tg_matmul(F1t_g, W2_g);
        Tensor *F2b_g = tg_add(F2_g, B2_g);
        Tensor *Y2_g = tg_add(Y1_g, F2b_g);
        Tensor *pool_g = tg_mean_rows(Y2_g);
        Tensor *logits_g = tg_matmul(pool_g, Wout_g);
        Tensor *loss_g = tg_cross_entropy(logits_g, tgt_g);
        tg_backward(loss_g);

        // Compare
        check("block_fwd_loss", loss_c->data[0], loss_g->data[0], 1e-3f);

        tg_from_cuda(logits_g);
        float logits_err = max_err_array(logits_c->data, logits_g->data, L);
        printf("  block_fwd logits max_err=%.2e  cpu=%.4f,%.4f  gpu=%.4f,%.4f  %s\n",
               logits_err, logits_c->data[0], logits_c->data[1],
               logits_g->data[0], logits_g->data[1],
               logits_err < 1e-3f ? "PASS" : "FAIL");
        if (logits_err >= 1e-3f) n_fail++;

        tg_from_cuda(Wout_g);
        float wout_grad_err = max_err_array(Wout_c->grad, Wout_g->grad, C2*L);
        printf("  block_bwd Wout grad max_err=%.2e  %s\n", wout_grad_err,
               wout_grad_err < 1e-3f ? "PASS" : "FAIL");
        if (wout_grad_err >= 1e-3f) n_fail++;

        tg_from_cuda(Wq_g);
        float wq_grad_err = max_err_array(Wq_c->grad, Wq_g->grad, C2*C2);
        printf("  block_bwd Wq grad max_err=%.2e  %s\n", wq_grad_err,
               wq_grad_err < 1e-3f ? "PASS" : "FAIL");
        if (wq_grad_err >= 1e-3f) n_fail++;

        free(x_data); free(wq_data); free(wk_data); free(wv_data); free(wo_data);
        free(w1_data); free(b1_data); free(w2_data); free(b2_data); free(wout_data);

        tg_free_graph(loss_c);
        tg_free(X_c); tg_free(Wq_c); tg_free(Wk_c); tg_free(Wv_c); tg_free(Wao_c);
        tg_free(W1_c); tg_free(B1_c); tg_free(W2_c); tg_free(B2_c);
        tg_free(Wout_c); tg_free(tgt_c);

        tg_cuda_free(X_g); tg_cuda_free(Wq_g); tg_cuda_free(Wk_g); tg_cuda_free(Wv_g); tg_cuda_free(Wao_g);
        tg_cuda_free(W1_g); tg_cuda_free(B1_g); tg_cuda_free(W2_g); tg_cuda_free(B2_g);
        tg_cuda_free(Wout_g); tg_cuda_free(tgt_g);
        tg_free_graph(loss_g);
        tg_free(X_g); tg_free(Wq_g); tg_free(Wk_g); tg_free(Wv_g); tg_free(Wao_g);
        tg_free(W1_g); tg_free(B1_g); tg_free(W2_g); tg_free(B2_g);
        tg_free(Wout_g); tg_free(tgt_g);
    }

    // ── Multi-head attention forward+backward (n_heads=4) ────────────────────
    // Tests the actual slice_cols + per-head QKV + concat_cols path.
    // The mini block test above bypasses this by using a single-head shortcut.
    for (int test = 0; test < 3; test++) {
        int T   = (test == 0) ?  8 : (test == 1) ? 16 : 256;
        int C2  = (test == 0) ?  8 : 128;
        int nh  = 4;
        int hd  = C2 / nh;

        printf("\n[multi-head attn fwd+bwd: T=%d C=%d n_heads=%d head_dim=%d encoder]\n",
               T, C2, nh, hd);

        int wsize = C2 * C2;
        float *wq_d = malloc(wsize * sizeof(float));
        float *wk_d = malloc(wsize * sizeof(float));
        float *wv_d = malloc(wsize * sizeof(float));
        float *wo_d = malloc(wsize * sizeof(float));
        float *x_d  = malloc(T * C2 * sizeof(float));
        float *wout_d = malloc(C2 * 4 * sizeof(float));

        for (int i = 0; i < wsize; i++) {
            wq_d[i] = (float)(i % 7) * 0.02f - 0.06f;
            wk_d[i] = (float)(i % 5) * 0.02f - 0.04f;
            wv_d[i] = (float)(i % 9) * 0.02f - 0.08f;
            wo_d[i] = (float)(i % 6) * 0.02f - 0.05f;
        }
        for (int i = 0; i < T * C2; i++) x_d[i] = (float)(i % 11) * 0.03f - 0.15f;
        for (int i = 0; i < C2 * 4; i++) wout_d[i] = (float)(i % 5) * 0.04f - 0.08f;

        // ─── CPU path ───
        TgSelfAttention attn_c = tg_attention_create_encoder(C2, nh);
        for (int i = 0; i < wsize; i++) {
            attn_c.Wq->data[i] = wq_d[i];
            attn_c.Wk->data[i] = wk_d[i];
            attn_c.Wv->data[i] = wv_d[i];
            attn_c.Wo->data[i] = wo_d[i];
        }
        Tensor *X_c    = tg_new(T, C2);
        Tensor *Wout_c = tg_new(C2, 4);
        Tensor *tgt_c  = tg_new(1, 4);
        for (int i = 0; i < T*C2; i++) X_c->data[i] = x_d[i];
        for (int i = 0; i < C2*4; i++) Wout_c->data[i] = wout_d[i];
        tgt_c->data[1] = 1.0f;
        X_c->persistent = attn_c.Wq->persistent = attn_c.Wk->persistent = 1;
        attn_c.Wv->persistent = attn_c.Wo->persistent = 1;
        Wout_c->persistent = tgt_c->persistent = 1;

        Tensor *proj_c  = tg_attention_forward(&attn_c, X_c);
        Tensor *pool_c  = tg_mean_rows(proj_c);
        Tensor *logits_c = tg_matmul(pool_c, Wout_c);
        Tensor *loss_c  = tg_cross_entropy(logits_c, tgt_c);
        tg_backward(loss_c);

        // ─── GPU path ───
        TgSelfAttention attn_g = tg_attention_create_encoder(C2, nh);
        for (int i = 0; i < wsize; i++) {
            attn_g.Wq->data[i] = wq_d[i];
            attn_g.Wk->data[i] = wk_d[i];
            attn_g.Wv->data[i] = wv_d[i];
            attn_g.Wo->data[i] = wo_d[i];
        }
        Tensor *X_g    = tg_new(T, C2);
        Tensor *Wout_g = tg_new(C2, 4);
        Tensor *tgt_g  = tg_new(1, 4);
        for (int i = 0; i < T*C2; i++) X_g->data[i] = x_d[i];
        for (int i = 0; i < C2*4; i++) Wout_g->data[i] = wout_d[i];
        tgt_g->data[1] = 1.0f;
        X_g->persistent = attn_g.Wq->persistent = attn_g.Wk->persistent = 1;
        attn_g.Wv->persistent = attn_g.Wo->persistent = 1;
        Wout_g->persistent = tgt_g->persistent = 1;

        tg_to_cuda(attn_g.Wq); tg_to_cuda(attn_g.Wk);
        tg_to_cuda(attn_g.Wv); tg_to_cuda(attn_g.Wo);
        tg_to_cuda(X_g); tg_to_cuda(Wout_g); tg_to_cuda(tgt_g);

        Tensor *proj_g  = tg_attention_forward(&attn_g, X_g);
        Tensor *pool_g  = tg_mean_rows(proj_g);
        Tensor *logits_g = tg_matmul(pool_g, Wout_g);
        Tensor *loss_g  = tg_cross_entropy(logits_g, tgt_g);
        tg_backward(loss_g);

        // Compare loss
        check("mha_loss", loss_c->data[0], loss_g->data[0], 1e-3f);

        // Compare proj output
        tg_from_cuda(proj_g);
        float proj_err = max_err_array(proj_c->data, proj_g->data, T * C2);
        printf("  mha_proj max_err=%.2e  cpu[0]=%.4f  gpu[0]=%.4f  %s\n",
               proj_err, proj_c->data[0], proj_g->data[0],
               proj_err < 1e-3f ? "PASS" : "FAIL");
        if (proj_err >= 1e-3f) n_fail++;

        // Compare Wq gradient
        tg_from_cuda(attn_g.Wq);
        float wq_grad_err = max_err_array(attn_c.Wq->grad, attn_g.Wq->grad, wsize);
        printf("  mha_bwd Wq grad max_err=%.2e  %s\n", wq_grad_err,
               wq_grad_err < 1e-3f ? "PASS" : "FAIL");
        if (wq_grad_err >= 1e-3f) n_fail++;

        // Compare Wo gradient
        tg_from_cuda(attn_g.Wo);
        float wo_grad_err = max_err_array(attn_c.Wo->grad, attn_g.Wo->grad, wsize);
        printf("  mha_bwd Wo grad max_err=%.2e  %s\n", wo_grad_err,
               wo_grad_err < 1e-3f ? "PASS" : "FAIL");
        if (wo_grad_err >= 1e-3f) n_fail++;

        free(wq_d); free(wk_d); free(wv_d); free(wo_d); free(x_d); free(wout_d);

        tg_free_graph(loss_c);
        tg_free(X_c); tg_free(Wout_c); tg_free(tgt_c);
        tg_attention_free(&attn_c);

        tg_cuda_free(attn_g.Wq); tg_cuda_free(attn_g.Wk);
        tg_cuda_free(attn_g.Wv); tg_cuda_free(attn_g.Wo);
        tg_cuda_free(X_g); tg_cuda_free(Wout_g); tg_cuda_free(tgt_g);
        tg_free_graph(loss_g);
        tg_free(X_g); tg_free(Wout_g); tg_free(tgt_g);
        tg_attention_free(&attn_g);
    }


    printf("\ncuda_smoke: %s (%d failures)\n",
           n_fail == 0 ? "ALL TESTS PASSED" : "SOME TESTS FAILED", n_fail);
    return n_fail == 0 ? 0 : 1;
#endif
}
