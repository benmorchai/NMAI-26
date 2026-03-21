"""
NorgesGruppen Object Detection - Submission run.py
NM i AI 2026

Usage: python run.py --input /data/images --output /output/predictions.json

Sandbox constraints:
- No os, sys, subprocess, socket, pickle, yaml, shutil imports
- Use pathlib instead of os
- Use json instead of yaml
- NVIDIA L4 GPU (24GB VRAM), Python 3.11, PyTorch 2.6, ultralytics 8.1.0
"""
import argparse
import json
from pathlib import Path
from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="Path to input images directory")
    parser.add_argument("--output", type=str, required=True, help="Path to output predictions.json")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_path = Path(args.output)

    # Load model - best.pt should be in same directory as run.py
    model_path = Path(__file__).parent / "best.pt"
    model = YOLO(str(model_path))

    # Find all images
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
    image_files = sorted([
        f for f in input_dir.iterdir()
        if f.suffix.lower() in image_extensions
    ])

    print(f"Found {len(image_files)} images in {input_dir}")

    predictions = []

    # Run inference
    for img_path in image_files:
        # Extract image_id from filename (img_00042.jpg -> 42)
        stem = img_path.stem
        try:
            image_id = int(stem.replace("img_", "").lstrip("0") or "0")
        except ValueError:
            image_id = hash(stem) % 100000

        # Run prediction
        results = model.predict(
            source=str(img_path),
            conf=0.25,
            iou=0.45,
            imgsz=640,
            device="0",  # GPU in sandbox
            verbose=False,
        )

        for result in results:
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                continue

            for i in range(len(boxes)):
                # Get box in xyxy format, convert to COCO [x, y, w, h]
                xyxy = boxes.xyxy[i].tolist()
                x1, y1, x2, y2 = xyxy
                bbox = [
                    round(x1, 2),
                    round(y1, 2),
                    round(x2 - x1, 2),
                    round(y2 - y1, 2),
                ]

                category_id = int(boxes.cls[i].item())
                score = round(float(boxes.conf[i].item()), 4)

                predictions.append({
                    "image_id": image_id,
                    "category_id": category_id,
                    "bbox": bbox,
                    "score": score,
                })

    print(f"Generated {len(predictions)} predictions")

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(predictions, f)

    print(f"Predictions written to {output_path}")


if __name__ == "__main__":
    main()
