"""
Train a YOLOv8n vehicle detector on BDD100K (cleaned from my Kaggle notebook).

Two configurations were trained, both YOLOv8n, 10 epochs, 640 px:
  --classes four     car / bus / truck / motor              (run "v1")
  --classes vehicle  one class: car, truck, bus, train,
                     motorcycle and bicycle merged           (run "v2")

    python train_bdd_yolo.py --bdd-root /path/to/bdd100k --classes vehicle

--bdd-root must contain images/100k/{train,val}/ and
labels/bdd100k_labels_images_{train,val}.json (the Kaggle "solesensei_bdd100k"
dataset has this layout). Use --max-train to train on a subset.
"""

import argparse
import json
import os
import shutil
from pathlib import Path

import yaml
from tqdm import tqdm
from ultralytics import YOLO

CLASS_SETS = {
    "four": {"car": 0, "bus": 1, "truck": 2, "motor": 3},
    "vehicle": {c: 0 for c in ["car", "truck", "bus", "train", "motor", "motorcycle", "bike", "bicycle"]},
}
NAMES = {"four": ["car", "bus", "truck", "motor"], "vehicle": ["vehicle"]}
IMG_W, IMG_H = 1280, 720          # all BDD100K images


def convert_split(json_path, img_src, img_dst, lbl_dst, class_map, max_images=None):
    """BDD100K JSON boxes -> YOLO txt labels; links (or copies) the images."""
    img_dst.mkdir(parents=True, exist_ok=True)
    lbl_dst.mkdir(parents=True, exist_ok=True)
    data = json.loads(Path(json_path).read_text())
    if max_images:
        data = data[:max_images]
    kept = 0
    for item in tqdm(data, desc=Path(json_path).stem):
        src = img_src / item["name"]
        if not src.exists():
            continue
        lines = []
        for lab in item.get("labels", []):
            cat, box = lab.get("category"), lab.get("box2d")
            if cat not in class_map or box is None:
                continue
            cx = (box["x1"] + box["x2"]) / 2 / IMG_W
            cy = (box["y1"] + box["y2"]) / 2 / IMG_H
            w = (box["x2"] - box["x1"]) / IMG_W
            h = (box["y2"] - box["y1"]) / IMG_H
            lines.append(f"{class_map[cat]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
        dst = img_dst / item["name"]
        if not dst.exists():
            try:
                os.symlink(src, dst)
            except OSError:            # e.g. Windows without symlink rights
                shutil.copy(src, dst)
        (lbl_dst / (Path(item["name"]).stem + ".txt")).write_text("\n".join(lines))
        kept += 1
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bdd-root", required=True, type=Path)
    ap.add_argument("--work-dir", default="bdd_yolo", type=Path)
    ap.add_argument("--classes", choices=CLASS_SETS, default="vehicle")
    ap.add_argument("--max-train", type=int, default=None)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default=None, help="e.g. 0 for the first GPU, or cpu")
    args = ap.parse_args()

    cmap = CLASS_SETS[args.classes]
    n_train = convert_split(args.bdd_root / "labels/bdd100k_labels_images_train.json",
                            args.bdd_root / "images/100k/train",
                            args.work_dir / "images/train", args.work_dir / "labels/train",
                            cmap, args.max_train)
    n_val = convert_split(args.bdd_root / "labels/bdd100k_labels_images_val.json",
                          args.bdd_root / "images/100k/val",
                          args.work_dir / "images/val", args.work_dir / "labels/val", cmap)
    print(f"train images: {n_train}, val images: {n_val}")

    data_yaml = args.work_dir / "bdd.yaml"
    data_yaml.write_text(yaml.dump({"path": str(args.work_dir.resolve()), "train": "images/train",
                                    "val": "images/val", "names": NAMES[args.classes]}))
    model = YOLO("yolov8n.pt")
    model.train(data=str(data_yaml), epochs=args.epochs, imgsz=640, batch=args.batch,
                device=args.device, project=str(args.work_dir / "runs"), name=f"bdd_{args.classes}")


if __name__ == "__main__":
    main()
