"""
Convert COCO dataset to YOLO format and set up training.
NorgesGruppen Object Detection - NM i AI 2026
"""
import json
import shutil
import random
from pathlib import Path

# Paths
BASE = Path(__file__).parent
COCO_DIR = BASE / "coco_dataset" / "train"
COCO_ANN = COCO_DIR / "annotations.json"
COCO_IMGS = COCO_DIR / "images"
YOLO_DIR = BASE / "yolo_dataset"

VAL_RATIO = 0.1
SEED = 42

def convert_coco_to_yolo():
    """Convert COCO annotations to YOLO format and create train/val split."""
    print("Loading COCO annotations...")
    with open(COCO_ANN) as f:
        coco = json.load(f)

    images = {img["id"]: img for img in coco["images"]}
    categories = {cat["id"]: cat for cat in coco["categories"]}
    num_classes = len(categories)
    print(f"  {len(images)} images, {len(coco['annotations'])} annotations, {num_classes} categories")

    # Group annotations by image
    anns_by_image = {}
    for ann in coco["annotations"]:
        img_id = ann["image_id"]
        if img_id not in anns_by_image:
            anns_by_image[img_id] = []
        anns_by_image[img_id].append(ann)

    # Train/val split
    random.seed(SEED)
    img_ids = sorted(images.keys())
    random.shuffle(img_ids)
    val_count = max(1, int(len(img_ids) * VAL_RATIO))
    val_ids = set(img_ids[:val_count])
    train_ids = set(img_ids[val_count:])
    print(f"  Split: {len(train_ids)} train, {len(val_ids)} val")

    # Create directories
    for split in ["train", "val"]:
        (YOLO_DIR / split / "images").mkdir(parents=True, exist_ok=True)
        (YOLO_DIR / split / "labels").mkdir(parents=True, exist_ok=True)

    # Convert and copy
    for img_id, img_info in images.items():
        split = "val" if img_id in val_ids else "train"
        w, h = img_info["width"], img_info["height"]
        fname = img_info["file_name"]
        stem = Path(fname).stem

        # Copy image
        src = COCO_IMGS / fname
        dst = YOLO_DIR / split / "images" / fname
        if not dst.exists():
            shutil.copy2(src, dst)

        # Write YOLO label file
        label_path = YOLO_DIR / split / "labels" / f"{stem}.txt"
        lines = []
        for ann in anns_by_image.get(img_id, []):
            cat_id = ann["category_id"]
            bx, by, bw, bh = ann["bbox"]  # COCO: [x, y, width, height] in pixels

            # Convert to YOLO: [class, cx, cy, w, h] normalized
            cx = (bx + bw / 2) / w
            cy = (by + bh / 2) / h
            nw = bw / w
            nh = bh / h

            # Clamp to [0, 1]
            cx = max(0, min(1, cx))
            cy = max(0, min(1, cy))
            nw = max(0, min(1, nw))
            nh = max(0, min(1, nh))

            lines.append(f"{cat_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

        with open(label_path, "w") as f:
            f.write("\n".join(lines))

    # Create dataset YAML
    cat_names = [categories[i]["name"] for i in sorted(categories.keys())]
    yaml_content = f"""# NorgesGruppen Object Detection Dataset
path: {YOLO_DIR.resolve().as_posix()}
train: train/images
val: val/images

nc: {num_classes}
names: {json.dumps(cat_names, ensure_ascii=False)}
"""
    yaml_path = YOLO_DIR / "dataset.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    print(f"  Dataset YAML written to {yaml_path}")
    print("Conversion complete!")
    return yaml_path, num_classes


def train(yaml_path, num_classes):
    """Train YOLOv8 model."""
    from ultralytics import YOLO

    print("\nStarting YOLOv8s training...")
    print(f"  Classes: {num_classes}")
    print(f"  Dataset: {yaml_path}")

    model = YOLO("yolov8s.pt")  # small model - faster on CPU

    results = model.train(
        data=str(yaml_path),
        epochs=30,           # reasonable for CPU
        imgsz=640,
        batch=4,             # small batch for CPU memory
        device="cpu",
        workers=2,
        patience=10,         # early stopping
        save=True,
        project=str(BASE / "runs"),
        name="ngd_yolov8s",
        exist_ok=True,
        verbose=True,
    )

    print("\nTraining complete!")
    print(f"Best weights: {BASE / 'runs' / 'ngd_yolov8s' / 'weights' / 'best.pt'}")
    return results


if __name__ == "__main__":
    yaml_path, nc = convert_coco_to_yolo()
    train(yaml_path, nc)
