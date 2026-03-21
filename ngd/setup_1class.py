"""
Create a 1-class (product detection only) version of the dataset.
All categories → class 0 ("product").
This maximizes detection mAP@0.5 which is 70% of the score.
"""
import json
import shutil
from pathlib import Path

BASE = Path(__file__).parent
COCO_ANN = BASE / "coco_dataset" / "train" / "annotations.json"
SRC_YOLO = BASE / "yolo_dataset"
DST_YOLO = BASE / "yolo_dataset_1class"

def main():
    print("Setting up 1-class detection dataset...")

    # Create directories
    for split in ["train", "val"]:
        (DST_YOLO / split / "images").mkdir(parents=True, exist_ok=True)
        (DST_YOLO / split / "labels").mkdir(parents=True, exist_ok=True)

    # Copy images (symlink would be better but Windows...)
    for split in ["train", "val"]:
        src_imgs = SRC_YOLO / split / "images"
        dst_imgs = DST_YOLO / split / "images"
        for img in src_imgs.iterdir():
            dst = dst_imgs / img.name
            if not dst.exists():
                shutil.copy2(img, dst)
        print(f"  Copied {split} images")

    # Convert labels: change all class IDs to 0
    for split in ["train", "val"]:
        src_labels = SRC_YOLO / split / "labels"
        dst_labels = DST_YOLO / split / "labels"
        count = 0
        for lbl_file in src_labels.glob("*.txt"):
            lines = []
            with open(lbl_file) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        # Replace class ID with 0
                        parts[0] = "0"
                        lines.append(" ".join(parts))
            with open(dst_labels / lbl_file.name, "w") as f:
                f.write("\n".join(lines))
            count += 1
        print(f"  Converted {count} {split} label files")

    # Write dataset YAML
    yaml_content = f"""path: {DST_YOLO.resolve().as_posix()}
train: train/images
val: val/images

nc: 1
names: ["product"]
"""
    yaml_path = DST_YOLO / "dataset.yaml"
    with open(yaml_path, "w") as f:
        f.write(yaml_content)

    print(f"  Dataset YAML: {yaml_path}")
    print("Done!")
    return yaml_path


if __name__ == "__main__":
    main()
