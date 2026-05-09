"""
Compare the two trained detectors on the same images, class-agnostically,
and pick the confidence threshold that gives the most accurate vehicle COUNTS.

    python evaluate_detectors.py --data /path/to/sample   # folder with images/val and labels/val

The labels are the single-class "vehicle" labels of the v2 run (BDD100K
validation split). Images are split in two halves: the threshold is chosen on
the first half (calibration) and all reported numbers come from the second
half (test), so the threshold is not tuned on the data it is scored on.

Outputs: results/detector_comparison.csv, results/count_pairs.csv and
../assets/graphs/detector_threshold_sweep.png, detector_counts_scatter.png
"""

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from ultralytics import YOLO

HERE = Path(__file__).resolve().parent
MODELS = {"v1 (4 classes, 69k train images)": HERE / "weights/yolov8n_bdd_v1_4class.pt",
          "v2 (1 class, 1.2k train images)": HERE / "weights/yolov8n_bdd_v2_vehicle.pt"}
THRESHOLDS = np.round(np.arange(0.05, 0.81, 0.05), 2)


def load_labels(path):
    rows = [l.split() for l in Path(path).read_text().splitlines() if l.strip()]
    if not rows:
        return np.zeros((0, 4))
    b = np.array(rows, dtype=float)[:, 1:5]          # cx cy w h, normalised
    return np.stack([b[:, 0] - b[:, 2] / 2, b[:, 1] - b[:, 3] / 2,
                     b[:, 0] + b[:, 2] / 2, b[:, 1] + b[:, 3] / 2], 1)


def iou(a, b):
    x1 = np.maximum(a[:, None, 0], b[None, :, 0]); y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2]); y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area = lambda r: (r[:, 2] - r[:, 0]) * (r[:, 3] - r[:, 1])
    return inter / (area(a)[:, None] + area(b)[None, :] - inter + 1e-12)


def match(pred, gt, thr=0.5):
    """Greedy one-to-one matching by IoU (predictions sorted by confidence). Returns TP."""
    if len(pred) == 0 or len(gt) == 0:
        return 0
    m = iou(pred, gt)
    used, tp = set(), 0
    for i in range(len(pred)):
        j = int(np.argmax(np.where([k in used for k in range(len(gt))], -1, m[i])))
        if m[i, j] >= thr and j not in used:
            used.add(j); tp += 1
    return tp


def scores(preds, gts, t):
    tp = fp = fn = 0
    errs = []
    for (boxes, conf), gt in zip(preds, gts):
        p = boxes[conf >= t]
        k = match(p, gt)
        tp += k; fp += len(p) - k; fn += len(gt) - k
        errs.append(len(p) - len(gt))
    errs = np.array(errs)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": prec, "recall": rec, "f1": 2 * prec * rec / (prec + rec + 1e-12),
            "count_mae": float(np.abs(errs).mean()), "count_bias": float(errs.mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    args = ap.parse_args()
    images = sorted((args.data / "images/val").glob("*.jpg"))
    gts = [load_labels(args.data / "labels/val" / (p.stem + ".txt")) for p in images]
    half = len(images) // 2
    print(f"{len(images)} images, {sum(len(g) for g in gts)} labelled vehicles "
          f"(calibration {half}, test {len(images) - half})")

    rows, sweeps, pairs = [], {}, []
    for name, wpath in MODELS.items():
        model = YOLO(str(wpath))
        preds = []
        for i in range(0, len(images), 16):
            for r in model.predict([str(p) for p in images[i:i + 16]], conf=0.05, iou=0.7, imgsz=640,
                                   agnostic_nms=True, device="cpu", verbose=False):
                preds.append((r.boxes.xyxyn.cpu().numpy(), r.boxes.conf.cpu().numpy()))
        cal = [scores(preds[:half], gts[:half], t) for t in THRESHOLDS]
        best_t = float(THRESHOLDS[int(np.argmin([c["count_mae"] for c in cal]))])
        test = {t: scores(preds[half:], gts[half:], t) for t in THRESHOLDS}
        sweeps[name] = test
        for label, t in [("default 0.25", 0.25), ("tuned for counting", best_t)]:
            rows.append({"model": name, "threshold": label, "conf": t, **test[t]})
        for (b, c), g, img in zip(preds[half:], gts[half:], images[half:]):
            pairs.append({"model": name, "image": img.name, "true": len(g),
                          "pred_default": int((c >= 0.25).sum()), "pred_tuned": int((c >= best_t).sum())})
        print(f"{name}: count-optimal threshold on calibration half = {best_t}")

    os.makedirs(HERE / "results", exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(HERE / "results/detector_comparison.csv", index=False, float_format="%.4f")
    pd.DataFrame(pairs).to_csv(HERE / "results/count_pairs.csv", index=False)
    print(df.round(3).to_string(index=False))

    graphs = HERE.parent / "assets/graphs"
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    for name, test in sweeps.items():
        axes[0].plot(THRESHOLDS, [test[t]["count_mae"] for t in THRESHOLDS], marker="o", label=name)
        axes[1].plot(THRESHOLDS, [test[t]["precision"] for t in THRESHOLDS], ls="--", label=f"{name}: precision")
        axes[1].plot(THRESHOLDS, [test[t]["recall"] for t in THRESHOLDS], label=f"{name}: recall")
    axes[0].axvline(0.25, color="grey", ls=":", label="Ultralytics default (0.25)")
    axes[0].set(xlabel="Confidence threshold", ylabel="Mean absolute count error (vehicles per image)",
                title="Counting error vs threshold (test half)")
    axes[1].set(xlabel="Confidence threshold", ylabel="Box-level precision / recall (IoU 0.5)",
                title="Precision and recall vs threshold (test half)")
    axes[0].legend(fontsize=8); axes[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(graphs / "detector_threshold_sweep.png", dpi=130)

    pdf = pd.DataFrame(pairs)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, name in zip(axes, MODELS):
        d = pdf[pdf.model == name]
        ax.scatter(d.true, d.pred_tuned, s=10, alpha=0.4)
        lim = max(d.true.max(), d.pred_tuned.max()) + 2
        ax.plot([0, lim], [0, lim], color="black", lw=1, ls="--", label="perfect count")
        ax.set(xlabel="Labelled vehicles in image", title=f"{name}\n(count-tuned threshold)")
        ax.legend()
    axes[0].set_ylabel("Detected vehicles")
    fig.tight_layout(); fig.savefig(graphs / "detector_counts_scatter.png", dpi=130)


if __name__ == "__main__":
    main()
