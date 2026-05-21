"""
Produce category-aware eval report from eval_dump.csv and class_map.json.

Usage:
    python scripts/eval_report.py
        --eval-dump data/generated/train/eval_dump.csv
        --class-map data/generated/train/class_map.json
        [--confusables data/manifest/confusables.jsonl]
        [--run-id v3-baseline]
        [--output reports/eval/v3-baseline]
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import quantiles

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFUSABLES = REPO_ROOT / "data" / "manifest" / "confusables.jsonl"


def load_eval_dump(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "aug_pass":       int(row["aug_pass"]),
                "true_class_id":  int(row["true_class_id"]),
                "pred1_class_id": int(row["pred1_class_id"]),
                "pred1_logit":    float(row["pred1_logit"]),
                "pred2_class_id": int(row["pred2_class_id"]),
                "pred2_logit":    float(row["pred2_logit"]),
                "pred3_class_id": int(row["pred3_class_id"]),
                "pred3_logit":    float(row["pred3_logit"]),
            })
    return rows


def load_class_map(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cm = {entry["class_id"]: entry for entry in data["classes"]}
    return data["n_classes"], cm


def load_confusables(path):
    entries = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    if entry.get("review_status") == "reviewed":
                        entries.append(entry)
    except FileNotFoundError:
        pass
    return entries


def annotate_rows(rows, class_map):
    for r in rows:
        true_result  = class_map[r["true_class_id"]]["result_id"]
        pred1_result = class_map[r["pred1_class_id"]]["result_id"]
        pred2_result = class_map[r["pred2_class_id"]]["result_id"]
        pred3_result = class_map[r["pred3_class_id"]]["result_id"]
        r["exact_top1"]  = r["pred1_class_id"] == r["true_class_id"]
        r["exact_top3"]  = r["true_class_id"] in (r["pred1_class_id"], r["pred2_class_id"], r["pred3_class_id"])
        r["result_top1"] = pred1_result == true_result
        r["result_top3"] = true_result in (pred1_result, pred2_result, pred3_result)


def _group_stats(group_rows):
    n = len(group_rows)
    if n == 0:
        return {"n_classes": 0, "n_examples": 0,
                "exact_flag_top1": 0.0, "exact_flag_top1_count": 0,
                "exact_flag_top3": 0.0, "exact_flag_top3_count": 0,
                "result_top1": 0.0, "result_top1_count": 0,
                "result_top3": 0.0, "result_top3_count": 0}
    ef1 = sum(1 for r in group_rows if r["exact_top1"])
    ef3 = sum(1 for r in group_rows if r["exact_top3"])
    rl1 = sum(1 for r in group_rows if r["result_top1"])
    rl3 = sum(1 for r in group_rows if r["result_top3"])
    return {
        "n_classes":            len(set(r["true_class_id"] for r in group_rows)),
        "n_examples":           n,
        "exact_flag_top1":      round(ef1 / n, 6),
        "exact_flag_top1_count": ef1,
        "exact_flag_top3":      round(ef3 / n, 6),
        "exact_flag_top3_count": ef3,
        "result_top1":          round(rl1 / n, 6),
        "result_top1_count":    rl1,
        "result_top3":          round(rl3 / n, 6),
        "result_top3_count":    rl3,
    }


def compute_breakdown(rows, field, class_map):
    buckets = defaultdict(list)
    for r in rows:
        buckets[class_map[r["true_class_id"]][field]].append(r)
    return {k: _group_stats(buckets[k]) for k in sorted(buckets)}


def compute_confusable_group(entry, rows, class_map):
    level   = entry["level"]
    members = entry["members"]
    mset    = set(members)

    def get_id(cid):
        return class_map[cid]["result_id"] if level == "result" else class_map[cid]["flag_id"]

    member_classes, resolved = [], set()
    for cid, cm in class_map.items():
        key = cm["result_id"] if level == "result" else cm["flag_id"]
        if key in mset:
            member_classes.append({"id": key, "class_id": cid})
            resolved.add(key)

    member_cids = set(mc["class_id"] for mc in member_classes)
    unresolved  = [m for m in members if m not in resolved]
    group_rows  = [r for r in rows if r["true_class_id"] in member_cids]
    n           = len(group_rows)

    empty_margin = {"n_correct_top1": 0, "n_margin_computable": 0, "n_margin_not_in_top3": 0,
                    "min_margin": None, "mean_margin": None, "max_margin": None}
    if n == 0:
        return {"confusable_id": entry["confusable_id"], "level": level, "members": members,
                "member_classes": sorted(member_classes, key=lambda x: x["class_id"]),
                "unresolved_members": unresolved, "n_examples": 0,
                "exact_top1": 0.0, "exact_top1_count": 0,
                "exact_top3": 0.0, "exact_top3_count": 0,
                "result_top1": 0.0, "result_top1_count": 0,
                "result_top3": 0.0, "result_top3_count": 0,
                "within_group_confusion": [], "margin_stats": empty_margin}

    ef1 = sum(1 for r in group_rows if r["exact_top1"])
    ef3 = sum(1 for r in group_rows if r["exact_top3"])
    rl1 = sum(1 for r in group_rows if r["result_top1"])
    rl3 = sum(1 for r in group_rows if r["result_top3"])

    # Within-group confusion matrix (top-1 prediction maps to a group member)
    conf_counts = defaultdict(int)
    for r in group_rows:
        if r["pred1_class_id"] in member_cids:
            conf_counts[(get_id(r["true_class_id"]), get_id(r["pred1_class_id"]))] += 1
    within_group_confusion = [
        {"true_id": k[0], "pred_id": k[1], "count": v}
        for k, v in sorted(conf_counts.items())
    ]

    # Margin stats
    def is_correct(r):
        return r["result_top1"] if level == "result" else r["exact_top1"]

    correct_rows    = [r for r in group_rows if is_correct(r)]
    n_correct_top1  = len(correct_rows)
    margins         = []
    n_not_in_top3   = 0

    for r in correct_rows:
        true_id = get_id(r["true_class_id"])
        conf_logits = [
            logit
            for pred_cid, logit in [(r["pred2_class_id"], r["pred2_logit"]),
                                     (r["pred3_class_id"], r["pred3_logit"])]
            if pred_cid in member_cids and get_id(pred_cid) != true_id
        ]
        if conf_logits:
            margins.append(r["pred1_logit"] - max(conf_logits))
        else:
            n_not_in_top3 += 1

    n_comp = len(margins)
    margin_stats = {
        "n_correct_top1":      n_correct_top1,
        "n_margin_computable": n_comp,
        "n_margin_not_in_top3": n_not_in_top3,
        "min_margin":  round(min(margins),           6) if margins else None,
        "mean_margin": round(sum(margins) / n_comp,  6) if margins else None,
        "max_margin":  round(max(margins),           6) if margins else None,
    }

    return {
        "confusable_id":   entry["confusable_id"],
        "level":           level,
        "members":         members,
        "member_classes":  sorted(member_classes, key=lambda x: x["class_id"]),
        "unresolved_members": unresolved,
        "n_examples":      n,
        "exact_top1":      round(ef1 / n, 6),
        "exact_top1_count": ef1,
        "exact_top3":      round(ef3 / n, 6),
        "exact_top3_count": ef3,
        "result_top1":     round(rl1 / n, 6),
        "result_top1_count": rl1,
        "result_top3":     round(rl3 / n, 6),
        "result_top3_count": rl3,
        "within_group_confusion": within_group_confusion,
        "margin_stats":    margin_stats,
    }


def build_markdown(report):
    lines = []
    rid = report["run_id"]
    N   = report["n_examples"]

    lines += [
        f"# Eval Report: {rid}",
        "",
        f"Generated: {report['generated_at']}",
        f"Classes: {report['n_classes']}  Aug passes: {report['n_aug_passes']}  Examples: {N}",
        "",
        "## Aggregate Metrics",
        "",
        "| Metric | Top-1 | Top-3 |",
        "|---|---|---|",
    ]
    ef = report["metrics"]["exact_flag"]
    rl = report["metrics"]["result_level"]
    lines.append(f"| Exact flag | {ef['top1']*100:.2f}% ({ef['top1_count']}/{N}) | {ef['top3']*100:.2f}% ({ef['top3_count']}/{N}) |")
    lines.append(f"| Result level | {rl['top1']*100:.2f}% ({rl['top1_count']}/{N}) | {rl['top3']*100:.2f}% ({rl['top3_count']}/{N}) |")
    lines.append("")

    for field_key, title in [
        ("by_category",    "By Category"),
        ("by_status",      "By Status"),
        ("by_fictionality","By Fictionality"),
        ("by_variant",     "By Variant"),
    ]:
        col = title.split()[-1]
        lines += [f"## {title}", "", f"| {col} | Classes | Top-1 Result | Top-3 Result |", "|---|---|---|---|"]
        for key, stats in report[field_key].items():
            lines.append(f"| {key} | {stats['n_classes']} | {stats['result_top1']*100:.2f}% | {stats['result_top3']*100:.2f}% |")
        lines.append("")

    lines += ["## Confusable Groups", ""]
    for g in report["confusable_groups"]:
        n_mem = len(g["member_classes"])
        lines.append(f"### {g['confusable_id']} ({g['level']}-level, {n_mem} members)")
        lines.append("")
        n_g = g["n_examples"]
        if n_g > 0:
            lines.append(
                f"Top-1: {g['result_top1']*100:.1f}% ({g['result_top1_count']}/{n_g})   "
                f"Top-3: {g['result_top3']*100:.1f}% ({g['result_top3_count']}/{n_g})"
            )
            ms = g["margin_stats"]
            if ms["n_margin_computable"] > 0:
                lines.append(
                    f"Margin stats: min={ms['min_margin']:.2f}  mean={ms['mean_margin']:.2f}  "
                    f"max={ms['max_margin']:.2f}  "
                    f"({ms['n_margin_computable']}/{ms['n_correct_top1']} computable, "
                    f"{ms['n_margin_not_in_top3']} not in top-3)"
                )
            else:
                lines.append(
                    f"Margin stats: no computable margins ({ms['n_correct_top1']} correct top-1, "
                    f"no confusable members in top-3)"
                )
        else:
            lines.append("(no examples in this group)")

        if g["within_group_confusion"]:
            all_ids = sorted(
                set(e["true_id"] for e in g["within_group_confusion"])
                | set(e["pred_id"] for e in g["within_group_confusion"])
            )
            lines.append("")
            lines.append("Within-group confusion (top-1):")
            lines.append("| True \\ Pred | " + " | ".join(all_ids) + " |")
            lines.append("|---|" + "---|" * len(all_ids))
            conf_dict = {(e["true_id"], e["pred_id"]): e["count"] for e in g["within_group_confusion"]}
            for tid in all_ids:
                vals = [str(conf_dict.get((tid, pid), 0)) for pid in all_ids]
                lines.append(f"| {tid} | " + " | ".join(vals) + " |")

        if g["unresolved_members"]:
            lines.append(f"Unresolved members: {', '.join(g['unresolved_members'])}")
        lines.append("")

    lines += [
        "## Per-Class Summary",
        "",
        "| class_id | flag_id | result_id | category | exact_top1 | result_top1 |",
        "|---|---|---|---|---|---|",
    ]
    for pc in report["per_class"]:
        lines.append(
            f"| {pc['class_id']} | {pc['flag_id']} | {pc['result_id']} | {pc['category']} | "
            f"{pc['exact_top1']*100:.1f}% | {pc['result_top1']*100:.1f}% |"
        )

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Generate eval report from eval dump.")
    parser.add_argument("--eval-dump",    required=True)
    parser.add_argument("--class-map",    required=True)
    parser.add_argument("--confusables",  default=str(DEFAULT_CONFUSABLES))
    parser.add_argument("--run-id",       default="unnamed")
    parser.add_argument("--output")
    args = parser.parse_args()

    run_id  = args.run_id
    out_dir = Path(args.output) if args.output else REPO_ROOT / "reports" / "eval" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    rows                     = load_eval_dump(args.eval_dump)
    n_classes_from_map, cmap = load_class_map(args.class_map)
    confusables              = load_confusables(args.confusables)

    # Validate class count consistency
    n_classes_from_dump = len(set(r["true_class_id"] for r in rows))
    if n_classes_from_dump != n_classes_from_map:
        print(f"ERROR: eval dump has {n_classes_from_dump} unique classes but class_map declares {n_classes_from_map}",
              file=sys.stderr)
        sys.exit(1)

    n_aug_passes = max(r["aug_pass"] for r in rows) + 1
    n_examples   = len(rows)

    annotate_rows(rows, cmap)

    # Aggregate
    N   = n_examples
    ef1 = sum(1 for r in rows if r["exact_top1"])
    ef3 = sum(1 for r in rows if r["exact_top3"])
    rl1 = sum(1 for r in rows if r["result_top1"])
    rl3 = sum(1 for r in rows if r["result_top3"])

    # p25 of correct top-1 logits
    correct_logits = sorted(r["pred1_logit"] for r in rows if r["exact_top1"])
    p25 = quantiles(correct_logits, n=4)[0] if len(correct_logits) >= 2 else 0.0

    by_category    = compute_breakdown(rows, "category",    cmap)
    by_status      = compute_breakdown(rows, "status",      cmap)
    by_fictionality= compute_breakdown(rows, "fictionality", cmap)
    by_variant     = compute_breakdown(rows, "variant",     cmap)

    confusable_groups = [compute_confusable_group(e, rows, cmap) for e in confusables]

    # Per-class summary
    rows_by_class = defaultdict(list)
    for r in rows:
        rows_by_class[r["true_class_id"]].append(r)

    per_class = []
    for cid in sorted(cmap):
        cm  = cmap[cid]
        cr  = rows_by_class[cid]
        n_c = len(cr)
        ef1_c = sum(1 for r in cr if r["exact_top1"])
        ef3_c = sum(1 for r in cr if r["exact_top3"])
        rl1_c = sum(1 for r in cr if r["result_top1"])
        rl3_c = sum(1 for r in cr if r["result_top3"])
        per_class.append({
            "class_id":          cid,
            "flag_id":           cm["flag_id"],
            "result_id":         cm["result_id"],
            "category":          cm["category"],
            "fictionality":      cm["fictionality"],
            "status":            cm["status"],
            "variant":           cm["variant"],
            "n_examples":        n_c,
            "exact_top1":        round(ef1_c / n_c, 6) if n_c else 0.0,
            "exact_top1_count":  ef1_c,
            "exact_top3":        round(ef3_c / n_c, 6) if n_c else 0.0,
            "exact_top3_count":  ef3_c,
            "result_top1":       round(rl1_c / n_c, 6) if n_c else 0.0,
            "result_top1_count": rl1_c,
            "result_top3":       round(rl3_c / n_c, 6) if n_c else 0.0,
            "result_top3_count": rl3_c,
        })

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    report = {
        "version":               1,
        "generated_at":          ts,
        "run_id":                run_id,
        "class_map_path":        str(Path(args.class_map).resolve().relative_to(REPO_ROOT)).replace("\\", "/"),
        "eval_dump_path":        str(Path(args.eval_dump).resolve().relative_to(REPO_ROOT)).replace("\\", "/"),
        "n_classes":             n_classes_from_map,
        "n_aug_passes":          n_aug_passes,
        "n_examples":            n_examples,
        "p25_correct_top1_logit": round(p25, 6),
        "metrics": {
            "exact_flag":    {"top1": round(ef1/N, 6), "top1_count": ef1, "top3": round(ef3/N, 6), "top3_count": ef3},
            "result_level":  {"top1": round(rl1/N, 6), "top1_count": rl1, "top3": round(rl3/N, 6), "top3_count": rl3},
        },
        "by_category":     by_category,
        "by_status":       by_status,
        "by_fictionality": by_fictionality,
        "by_variant":      by_variant,
        "confusable_groups": confusable_groups,
        "per_class":       per_class,
    }

    json_path = out_dir / "eval.json"
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")

    md_path = out_dir / "eval.md"
    with open(md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(build_markdown(report))

    print(f"Run {run_id}: result_top1={rl1/N*100:.2f}% exact_top1={ef1/N*100:.2f}% "
          f"n_classes={n_classes_from_map} n_confusable_groups={len(confusable_groups)}")


if __name__ == "__main__":
    main()
