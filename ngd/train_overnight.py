"""
Nattrenings-script: Kjører to treninger sekvensielt.
Start: python train_overnight.py
Estimert tid: 7-10 timer på CPU.
Sjekk progress: se training_log.txt
"""
from ultralytics import YOLO
from pathlib import Path
import datetime

LOG = Path(__file__).parent / "training_log.txt"

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

if __name__ == "__main__":
    log("=== NATTRENINGS-SCRIPT STARTET ===")

    # --- Trening 1: Multiclass (356 klasser, 100 epochs) ---
    log("TRENING 1: Multiclass YOLOv8s - 356 klasser, 100 epochs")
    log("Starter...")
    try:
        model1 = YOLO("yolov8s.pt")
        model1.train(
            data="yolo_dataset/dataset.yaml",
            epochs=100,
            imgsz=640,
            batch=4,
            device="cpu",
            project="runs",
            name="ngd_multiclass_100ep",
            patience=20,
            augment=True,
            mosaic=1.0,
            mixup=0.1,
            copy_paste=0.1,
            lr0=0.01,
            lrf=0.01,
            warmup_epochs=5,
            workers=0,
        )
        log("TRENING 1 FERDIG!")
    except Exception as e:
        log(f"TRENING 1 FEILET: {e}")

    # --- Trening 2: Detection (1 klasse, 100 epochs) ---
    log("TRENING 2: Detection YOLOv8s - 1 klasse, 100 epochs")
    log("Starter...")
    try:
        model2 = YOLO("yolov8s.pt")
        model2.train(
            data="yolo_dataset_1class/dataset.yaml",
            epochs=100,
            imgsz=640,
            batch=8,
            device="cpu",
            project="runs",
            name="ngd_detection_100ep",
            patience=20,
            augment=True,
            mosaic=1.0,
            lr0=0.01,
            lrf=0.01,
            warmup_epochs=5,
            workers=0,
        )
        log("TRENING 2 FERDIG!")
    except Exception as e:
        log(f"TRENING 2 FEILET: {e}")

    log("=== ALT FERDIG ===")
