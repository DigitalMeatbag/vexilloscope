#include "dataset.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void copy_field(char *dst, size_t dst_size, const char *src) {
    if (dst_size == 0) return;
    if (!src) src = "";
    snprintf(dst, dst_size, "%s", src);
}

static void lower_code(char *out, size_t out_size, const char *in) {
    size_t i = 0;
    if (out_size == 0) return;

    while (in[i] != '\0' && i + 1 < out_size) {
        out[i] = (char)tolower((unsigned char)in[i]);
        i++;
    }
    out[i] = '\0';
}

static int file_exists(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    fclose(f);
    return 1;
}

static void trim_newline(char *s) {
    size_t n = strlen(s);
    while (n > 0 && (s[n - 1] == '\n' || s[n - 1] == '\r')) {
        s[n - 1] = '\0';
        n--;
    }
}

static const char *parse_csv_field(const char *p, char *out, size_t out_size) {
    size_t n = 0;
    int quoted = 0;

    if (*p == '"') {
        quoted = 1;
        p++;
    }

    while (*p != '\0') {
        if (quoted) {
            if (*p == '"' && p[1] == '"') {
                if (n + 1 < out_size) out[n++] = '"';
                p += 2;
                continue;
            }
            if (*p == '"') {
                p++;
                break;
            }
        } else if (*p == ',') {
            break;
        }

        if (n + 1 < out_size) out[n++] = *p;
        p++;
    }

    out[n] = '\0';
    if (*p == ',') p++;
    return p;
}

static int parse_label_row(const char *line, char *code, size_t code_size,
                           char *name, size_t name_size) {
    const char *p = parse_csv_field(line, code, code_size);
    parse_csv_field(p, name, name_size);
    return code[0] != '\0' && name[0] != '\0';
}

VxDataset vx_dataset_load(const char *labels_csv_path, const char *flags_dir) {
    FILE *f = fopen(labels_csv_path, "r");
    if (!f) {
        fprintf(stderr, "vx_dataset_load: failed to open '%s'\n", labels_csv_path);
        exit(1);
    }

    int capacity = 256;
    VxDataset dataset;
    dataset.count = 0;
    dataset.countries = calloc((size_t)capacity, sizeof(VxCountry));
    if (!dataset.countries) {
        fprintf(stderr, "vx_dataset_load: out of memory\n");
        fclose(f);
        exit(1);
    }

    char line[1024];
    int line_no = 0;
    while (fgets(line, sizeof(line), f)) {
        line_no++;
        trim_newline(line);
        if (line[0] == '\0') continue;
        if (line_no == 1 && strstr(line, "code")) continue;

        char code[VX_CODE_MAX];
        char name[VX_NAME_MAX];
        if (!parse_label_row(line, code, sizeof(code), name, sizeof(name))) {
            fprintf(stderr, "vx_dataset_load: malformed CSV row %d\n", line_no);
            exit(1);
        }

        if (dataset.count == capacity) {
            capacity *= 2;
            VxCountry *grown = realloc(dataset.countries, (size_t)capacity * sizeof(VxCountry));
            if (!grown) {
                fprintf(stderr, "vx_dataset_load: out of memory\n");
                exit(1);
            }
            dataset.countries = grown;
        }

        VxCountry *country = &dataset.countries[dataset.count];
        memset(country, 0, sizeof(*country));
        copy_field(country->code, sizeof(country->code), code);
        copy_field(country->name, sizeof(country->name), name);
        country->class_id = dataset.count;

        char flag_name[VX_CODE_MAX];
        lower_code(flag_name, sizeof(flag_name), country->code);
        snprintf(country->flag_path, sizeof(country->flag_path), "%s/%s.png", flags_dir, flag_name);
        country->has_image = file_exists(country->flag_path);

        dataset.count++;
    }

    fclose(f);
    return dataset;
}

void vx_dataset_free(VxDataset *dataset) {
    if (!dataset) return;
    free(dataset->countries);
    dataset->countries = NULL;
    dataset->count = 0;
}

void vx_dataset_print_summary(const VxDataset *dataset) {
    int available = 0;
    for (int i = 0; i < dataset->count; i++) {
        if (dataset->countries[i].has_image) available++;
    }

    printf("dataset: %d labels, %d flag images present\n", dataset->count, available);
    if (dataset->count > 0) {
        const VxCountry *first = &dataset->countries[0];
        printf("class %d: %s %s (%s)\n",
               first->class_id, first->code, first->name, first->flag_path);
    }
}
