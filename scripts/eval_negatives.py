"""
Threshold sweep over synthetic negative images using --identify-batch.

Usage:
    python scripts/eval_negatives.py
        --binary .\\build\\vexilloscope.exe
        --labels data/generated/train/labels.csv
        --threshold-x10-base <int>
        [--negative-dir data/generated/negative_eval]
        [--fn-image-dir data/generated/train/images]
        [--eval-report reports/eval/v3-baseline/eval.json]
        [--run-id v3-baseline]
        [--output reports/eval/v3-baseline]
        [--sweep-step 5]
        [--sweep-range 20]
        [--limit N]
"""

import argparse
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NEGATIVE_DIR = REPO_ROOT / "data" / "generated" / "negative_eval"
DEFAULT_LABELS       = REPO_ROOT / "data" / "generated" / "train" / "labels.csv"

FP_RATE_CEILING    = 0.05
HC_FP_RATE_CEILING = 0.01
FN_RATE_CEILING    = 0.02


def collect_images(directory, limit=None):
    """Recursively find *.png files, optionally limited per subdirectory."""
    d = Path(directory)
    if not d.exists():
        return []
    if limit is None:
        return sorted(d.rglob("*.png"))
    subdirs = sorted(p for p in d.iterdir() if p.is_dir())
    if not subdirs:
        return sorted(d.glob("*.png"))[:limit]
    images = []
    for sub in subdirs:
        images.extend(sorted(sub.glob("*.png"))[:limit])
    return images


def run_identify_batch(binary, labels, image_paths):
    """Run --identify-batch and return dict: str(path) -> (flag_id, pre_tta_logit, post_tta_logit).
    On image-load error: str(path) -> ('ERROR', None, None)."""
    results = {}
    if not image_paths:
        return results

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        for p in image_paths:
            f.write(str(p) + "\n")
        tmp_path = f.name

    try:
        cmd = [str(binary), "--labels", str(labels), "--identify-batch", tmp_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("loaded weights"):
                continue
            parts = line.split("\t")
            if len(parts) == 3 and parts[1] == "ERROR":
                results[parts[0]] = ("ERROR", None, None)
            elif len(parts) == 4:
                try:
                    results[parts[0]] = (parts[1], float(parts[2]), float(parts[3]))
                except ValueError:
                    results[parts[0]] = ("ERROR", None, None)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return results


def recipe_of(image_path, negative_dir):
    rel = Path(image_path).relative_to(Path(negative_dir))
    parts = rel.parts
    return parts[0] if len(parts) > 1 else "unknown"


def main():
    parser = argparse.ArgumentParser(description="Negative eval threshold sweep.")
    parser.add_argument("--binary",              required=True)
    parser.add_argument("--labels",              default=str(DEFAULT_LABELS))
    parser.add_argument("--threshold-x10-base",  required=True, type=int)
    parser.add_argument("--negative-dir",        default=str(DEFAULT_NEGATIVE_DIR))
    parser.add_argument("--fn-image-dir",        default=None)
    parser.add_argument("--eval-report",         default=None)
    parser.add_argument("--run-id",              default="unnamed")
    parser.add_argument("--output",              default=None)
    parser.add_argument("--sweep-step",          type=int, default=5)
    parser.add_argument("--sweep-range",         type=int, default=20)
    parser.add_argument("--limit",               type=int, default=None)
    args = parser.parse_args()

    run_id  = args.run_id
    out_dir = Path(args.output) if args.output else REPO_ROOT / "reports" / "eval" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    binary  = Path(args.binary)
    labels  = Path(args.labels)
    base_t  = args.threshold_x10_base
    neg_dir = Path(args.negative_dir)
    fn_dir  = Path(args.fn_image_dir) if args.fn_image_dir else None

    # Determine high-confidence threshold
    hc_threshold = 2.0
    hc_source    = "default_2.0"
    if args.eval_report:
        try:
            with open(args.eval_report, encoding="utf-8") as f:
                er = json.load(f)
            hc_threshold = er["p25_correct_top1_logit"]
            hc_source    = "p25_correct_top1_logit_from_eval_report"
        except Exception as e:
            print(f"WARNING: could not read eval report: {e}", file=sys.stderr)
    else:
        print("WARNING: --eval-report not provided; using default high-confidence threshold 2.0",
              file=sys.stderr)

    # Build class_map index
    cmap_path = REPO_ROOT / "data" / "generated" / "train" / "class_map.json"
    flag_index = {}
    if cmap_path.exists():
        with open(cmap_path, encoding="utf-8") as f:
            cmap = json.load(f)
        for entry in cmap["classes"]:
            flag_index[entry["flag_id"]] = {
                "result_id":    entry["result_id"],
                "display_name": entry["display_name"],
            }

    neg_images = collect_images(neg_dir, args.limit)
    fn_images  = collect_images(fn_dir, None) if fn_dir else []

    if args.limit:
        print(f"WARNING: --limit {args.limit} applied; results not representative", file=sys.stderr)

    n_negatives = len(neg_images)
    n_fn_images = len(fn_images) if fn_dir else None

    # Build sweep thresholds
    sweep_thresholds = []
    t = base_t - args.sweep_range
    while t <= base_t + args.sweep_range:
        sweep_thresholds.append(max(5, t))
        t += args.sweep_step
    sweep_thresholds = sorted(set(sweep_thresholds))

    # Run batch inference once for all images
    all_images = neg_images + fn_images
    print(f"Running batch inference on {len(all_images)} images...", flush=True)
    batch_results = run_identify_batch(binary, labels, all_images)
    n_errors = sum(1 for v in batch_results.values() if v[0] == "ERROR")
    print(f"  done. {len(batch_results)} results, {n_errors} load errors.")

    # Sweep thresholds using cached results
    sweep_results = []
    for thr in sweep_thresholds:
        fp_count    = 0
        hc_fp_count = 0
        fn_count    = None if not fn_dir else 0

        for img in neg_images:
            r = batch_results.get(str(img))
            if r and r[0] != "ERROR":
                _, pre_tta, post_tta = r
                if pre_tta >= thr / 10.0:
                    fp_count += 1
                    if post_tta is not None and post_tta >= hc_threshold:
                        hc_fp_count += 1

        if fn_dir:
            for img in fn_images:
                r = batch_results.get(str(img))
                detected = r and r[0] != "ERROR" and r[1] >= thr / 10.0
                if not detected:
                    fn_count += 1

        sweep_results.append({
            "threshold_x10":            thr,
            "fp_count":                 fp_count,
            "fp_rate":                  round(fp_count / n_negatives, 6) if n_negatives else 0.0,
            "high_confidence_fp_count": hc_fp_count,
            "high_confidence_fp_rate":  round(hc_fp_count / n_negatives, 6) if n_negatives else 0.0,
            "fn_count":                 fn_count,
            "fn_rate":                  round(fn_count / n_fn_images, 6) if (fn_dir and n_fn_images) else None,
        })

    # Base-threshold detailed pass from cached results
    base_entry = next((s for s in sweep_results if s["threshold_x10"] == base_t), None)
    if base_entry is None:
        base_entry = min(sweep_results, key=lambda s: abs(s["threshold_x10"] - base_t))

    recipe_fp_counts = defaultdict(int)
    recipe_totals    = defaultdict(int)
    false_positives  = []

    for img in neg_images:
        recipe = recipe_of(img, neg_dir)
        recipe_totals[recipe] += 1
        r = batch_results.get(str(img))
        if r and r[0] != "ERROR":
            flag_id, pre_tta, post_tta = r
            if pre_tta >= base_t / 10.0:
                recipe_fp_counts[recipe] += 1
                info = flag_index.get(flag_id, {})
                false_positives.append({
                    "image_path":             str(img.relative_to(REPO_ROOT)).replace("\\", "/"),
                    "recipe":                 recipe,
                    "predicted_flag_id":      flag_id,
                    "predicted_result_id":    info.get("result_id"),
                    "predicted_display_name": info.get("display_name"),
                    "top1_logit":             post_tta,
                    "is_high_confidence":     (post_tta is not None and post_tta >= hc_threshold),
                })

    per_recipe = {}
    for recipe in sorted(recipe_totals):
        n_r  = recipe_totals[recipe]
        fp_r = recipe_fp_counts[recipe]
        per_recipe[recipe] = {
            "n":                n_r,
            "fp_count_at_base": fp_r,
            "fp_rate_at_base":  round(fp_r / n_r, 6) if n_r else 0.0,
        }

    # Recommendation
    base_fp_rate    = base_entry["fp_rate"]
    base_hc_fp_rate = base_entry["high_confidence_fp_rate"]
    base_fn_rate    = base_entry["fn_rate"]

    def meets_targets(entry):
        if entry["fp_rate"] > FP_RATE_CEILING:
            return False
        if entry["high_confidence_fp_rate"] > HC_FP_RATE_CEILING:
            return False
        fn = entry["fn_rate"]
        if fn is not None and fn > FN_RATE_CEILING:
            return False
        return True

    qualifying = [s["threshold_x10"] for s in sweep_results if meets_targets(s)]
    if qualifying:
        rec_thr   = min(qualifying)
        rec_basis = "no_change_needed" if rec_thr == base_t else "lowest_threshold_meeting_targets"
        rec_note  = (
            "Current threshold already meets both targets. "
            "Recommended value is the most lenient threshold that still meets both targets, "
            "preserving maximum flag detection sensitivity."
        ) if rec_thr <= base_t else (
            f"Threshold {rec_thr} is the most lenient value meeting both targets "
            f"(fp_rate <= {FP_RATE_CEILING}, hc_fp_rate <= {HC_FP_RATE_CEILING})."
        )
    else:
        min_hc = min(s["high_confidence_fp_rate"] for s in sweep_results)
        rec_thr   = min(s["threshold_x10"] for s in sweep_results if s["high_confidence_fp_rate"] == min_hc)
        rec_basis = "highest_swept_value_best_tradeoff"
        rec_note  = (
            f"No swept threshold meets both FP rate targets. "
            f"Recommending threshold {rec_thr} to minimize high-confidence false positives."
        )

    recommendation = {
        "base_threshold_x10":           base_t,
        "base_fp_rate":                 base_fp_rate,
        "base_high_confidence_fp_rate": base_hc_fp_rate,
        "base_fn_rate":                 base_fn_rate,
        "recommended_threshold_x10":    rec_thr,
        "recommendation_basis":         rec_basis,
        "targets": {
            "fp_rate_ceiling":                FP_RATE_CEILING,
            "high_confidence_fp_rate_ceiling": HC_FP_RATE_CEILING,
        },
        "note": rec_note,
    }

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = {
        "version":                          1,
        "generated_at":                     ts,
        "run_id":                           run_id,
        "binary_path":                      str(binary).replace("\\", "/"),
        "labels_path":                      str(Path(args.labels).resolve().relative_to(REPO_ROOT)).replace("\\", "/"),
        "negative_dir":                     str(neg_dir.resolve().relative_to(REPO_ROOT)).replace("\\", "/"),
        "fn_image_dir":                     str(fn_dir.resolve().relative_to(REPO_ROOT)).replace("\\", "/") if fn_dir else None,
        "high_confidence_logit_threshold":  hc_threshold,
        "high_confidence_threshold_source": hc_source,
        "n_negatives":                      n_negatives,
        "n_fn_images":                      n_fn_images,
        "threshold_sweep":                  sweep_results,
        "per_recipe":                       per_recipe,
        "false_positives_at_base":          false_positives,
        "recommendation":                   recommendation,
    }

    json_path = out_dir / "negatives.json"
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")

    md_path = out_dir / "negatives.md"
    with open(md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(build_markdown(report))

    fn_at_base = f"{base_fn_rate*100:.1f}%" if base_fn_rate is not None else "N/A"
    print(
        f"Negatives: {n_negatives}  FP@base={base_fp_rate*100:.1f}%  "
        f"HC-FP@base={base_hc_fp_rate*100:.1f}%  FN@base={fn_at_base}  "
        f"Recommended threshold_x10={rec_thr}"
    )


def build_markdown(report):
    lines = []
    rid = report["run_id"]
    fn_label = str(report["n_fn_images"]) if report["n_fn_images"] is not None else "not measured"
    hc_src   = report["high_confidence_threshold_source"]

    lines += [
        f"# Negative Eval Report: {rid}",
        "",
        f"Generated: {report['generated_at']}",
        f"Negatives: {report['n_negatives']}   FN images: {fn_label}",
        f"High-confidence threshold: {report['high_confidence_logit_threshold']} ({hc_src})",
        "",
        "## Threshold Sweep",
        "",
        "| threshold_x10 | FP rate | HC-FP rate | FN rate |",
        "|---|---|---|---|",
    ]
    base_t = report["recommendation"]["base_threshold_x10"]
    for entry in report["threshold_sweep"]:
        t    = entry["threshold_x10"]
        fp   = f"{entry['fp_rate']*100:.2f}%"
        hcfp = f"{entry['high_confidence_fp_rate']*100:.2f}%"
        fn_v = entry["fn_rate"]
        fn_s = f"{fn_v*100:.2f}%" if fn_v is not None else "N/A"
        mark = " <- base" if t == base_t else ""
        lines.append(f"| {t} | {fp} | {hcfp} | {fn_s} |{mark}")
    lines.append("")

    lines += [
        "## Per-Recipe (at base threshold)",
        "",
        "| Recipe | N | FP count | FP rate |",
        "|---|---|---|---|",
    ]
    for recipe, stats in report["per_recipe"].items():
        lines.append(f"| {recipe} | {stats['n']} | {stats['fp_count_at_base']} | {stats['fp_rate_at_base']*100:.2f}% |")
    lines.append("")

    lines += ["## False Positives at Base Threshold", ""]
    fps = report["false_positives_at_base"]
    if fps:
        for fp in fps:
            hc = " [high-confidence]" if fp["is_high_confidence"] else ""
            lines.append(
                f"- {fp['image_path']}: {fp['predicted_flag_id']} "
                f"({fp['predicted_display_name']}) logit={fp['top1_logit']}{hc}"
            )
    else:
        lines.append("(none)")
    lines.append("")

    rec = report["recommendation"]
    lines += [
        "## Recommendation",
        "",
        f"Recommended threshold_x10: {rec['recommended_threshold_x10']} (basis: {rec['recommendation_basis']})",
        f"Note: {rec['note']}",
        "",
    ]

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
