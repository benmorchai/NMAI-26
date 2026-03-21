"""
NorgesGruppen Object Detection - Submission run.py
NM i AI 2026

Usage: python run.py --input /data/images --output /output/predictions.json

Uses ONNX model + onnxruntime for sandbox compatibility.
No ultralytics dependency - avoids version mismatch.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import cv2
import onnxruntime as ort


def xywh2xyxy(x):
    """Convert [cx, cy, w, h] to [x1, y1, x2, y2]."""
    y = np.copy(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y


def nms(boxes, scores, iou_threshold=0.45):
    """Non-maximum suppression."""
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]
    return np.array(keep)


def preprocess(img, imgsz=640):
    """Resize and normalize image for YOLO ONNX input."""
    h, w = img.shape[:2]
    scale = min(imgsz / h, imgsz / w)
    new_h, new_w = int(h * scale), int(w * scale)
    resized = cv2.resize(img, (new_w, new_h))

    # Pad to square
    canvas = np.full((imgsz, imgsz, 3), 114, dtype=np.uint8)
    pad_h = (imgsz - new_h) // 2
    pad_w = (imgsz - new_w) // 2
    canvas[pad_h:pad_h + new_h, pad_w:pad_w + new_w] = resized

    # HWC -> CHW, BGR -> RGB, normalize
    blob = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    blob = np.expand_dims(blob, 0)
    return blob, scale, pad_w, pad_h


def postprocess(output, scale, pad_w, pad_h, conf_threshold=0.25, iou_threshold=0.45):
    """Process YOLO ONNX output to detections."""
    # YOLOv8 output shape: (1, 5, N) for 1-class -> transpose to (N, 5)
    preds = output[0].squeeze(0).T  # (N, 5) = [cx, cy, w, h, conf]

    # Filter by confidence
    scores = preds[:, 4]
    mask = scores > conf_threshold
    preds = preds[mask]
    scores = scores[mask]

    if len(preds) == 0:
        return []

    # Convert to xyxy
    boxes = xywh2xyxy(preds[:, :4])

    # NMS
    keep = nms(boxes, scores, iou_threshold)
    boxes = boxes[keep]
    scores = scores[keep]

    # Scale back to original image coordinates
    boxes[:, 0] = (boxes[:, 0] - pad_w) / scale
    boxes[:, 1] = (boxes[:, 1] - pad_h) / scale
    boxes[:, 2] = (boxes[:, 2] - pad_w) / scale
    boxes[:, 3] = (boxes[:, 3] - pad_h) / scale

    # Convert xyxy to COCO [x, y, w, h]
    results = []
    for i in range(len(boxes)):
        x1, y1, x2, y2 = boxes[i]
        results.append({
            "bbox": [round(float(x1), 2), round(float(y1), 2),
                     round(float(x2 - x1), 2), round(float(y2 - y1), 2)],
            "category_id": 0,
            "score": round(float(scores[i]), 4),
        })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_path = Path(args.output)

    # Load ONNX model
    model_path = Path(__file__).parent / "best.onnx"
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    session = ort.InferenceSession(str(model_path), providers=providers)
    input_name = session.get_inputs()[0].name

    print(f"Model loaded: {model_path}")
    print(f"Provider: {session.get_providers()}")

    # Find images
    image_extensions = {".jpg", ".jpeg", ".png"}
    image_files = sorted([
        f for f in input_dir.iterdir()
        if f.suffix.lower() in image_extensions
    ])
    print(f"Found {len(image_files)} images")

    predictions = []

    for img_path in image_files:
        # Extract image_id
        stem = img_path.stem
        try:
            image_id = int(stem.split("_")[-1])
        except ValueError:
            image_id = hash(stem) % 100000

        # Read and preprocess
        img = cv2.imread(str(img_path))
        if img is None:
            continue

        blob, scale, pad_w, pad_h = preprocess(img, imgsz=640)

        # Inference
        output = session.run(None, {input_name: blob})

        # Postprocess
        dets = postprocess(output, scale, pad_w, pad_h, conf_threshold=0.25, iou_threshold=0.45)

        for det in dets:
            det["image_id"] = image_id
            predictions.append(det)

    print(f"Generated {len(predictions)} predictions")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(predictions, f)

    print(f"Predictions written to {output_path}")


if __name__ == "__main__":
    main()
