#ifndef VEXILLOSCOPE_DATASET_H
#define VEXILLOSCOPE_DATASET_H

#include <stddef.h>

#define VX_CODE_MAX 16
#define VX_NAME_MAX 128
#define VX_PATH_MAX 512

typedef struct {
    char code[VX_CODE_MAX];
    char name[VX_NAME_MAX];
    char flag_path[VX_PATH_MAX];
    int class_id;
    int has_image;
} VxCountry;

typedef struct {
    VxCountry *countries;
    int count;
} VxDataset;

VxDataset vx_dataset_load(const char *labels_csv_path, const char *flags_dir);
void      vx_dataset_free(VxDataset *dataset);
void      vx_dataset_print_summary(const VxDataset *dataset);

#endif
