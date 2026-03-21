"""
NorgesGruppen Training Monitor — NM i AI 2026
Serves a dashboard at http://localhost:8888
Tracks BOTH trainings: 356-class and 1-class detection.
"""
import http.server
import json
import csv
import time
from pathlib import Path
from datetime import datetime, timedelta

PORT = 8888
BASE = Path(__file__).parent

TRAINING_RUNS = {
    "multiclass": {
        "name": "Multiclass 30ep (ferdig)",
        "dir": BASE / "runs" / "ngd_yolov8s",
        "total_epochs": 30,
    },
    "detection": {
        "name": "Detection 50ep (ferdig)",
        "dir": BASE / "runs" / "ngd_1class",
        "total_epochs": 50,
    },
    "multiclass_100ep": {
        "name": "Multiclass 100ep (natt)",
        "dir": BASE / "runs" / "ngd_multiclass_100ep",
        "total_epochs": 100,
    },
    "detection_100ep": {
        "name": "Detection 100ep (natt)",
        "dir": BASE / "runs" / "ngd_detection_100ep",
        "total_epochs": 100,
    },
}


def parse_run(run_dir, total_epochs):
    """Parse a single training run's results."""
    results_csv = run_dir / "results.csv"
    weights_dir = run_dir / "weights"

    info = {
        "status": "waiting",
        "current_epoch": 0,
        "total_epochs": total_epochs,
        "epochs": [],
        "best_metrics": {},
        "training_finished": False,
        "eta": None,
        "weights_exist": {
            "best": (weights_dir / "best.pt").exists(),
            "last": (weights_dir / "last.pt").exists(),
        },
    }

    if not results_csv.exists():
        return info

    rows = []
    try:
        with open(results_csv, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cleaned = {}
                for k, v in row.items():
                    k = k.strip()
                    try:
                        cleaned[k] = float(v.strip())
                    except (ValueError, AttributeError):
                        cleaned[k] = v.strip() if isinstance(v, str) else v
                rows.append(cleaned)
    except Exception:
        return info

    if not rows:
        info["status"] = "started"
        return info

    info["current_epoch"] = len(rows)
    info["epochs"] = rows

    if len(rows) >= total_epochs:
        info["training_finished"] = True
        info["status"] = "FINISHED"
    else:
        info["status"] = "training"

    latest = rows[-1]

    # Find metric keys
    map50_key = map5095_key = precision_key = recall_key = None
    for k in latest:
        kl = k.lower()
        if "map50-95" in kl or "map50_95" in kl:
            map5095_key = k
        elif "map50" in kl:
            map50_key = k
        elif "precision" in kl:
            precision_key = k
        elif "recall" in kl:
            recall_key = k

    best_map50 = best_map5095 = 0
    for row in rows:
        if map50_key and isinstance(row.get(map50_key), (int, float)):
            best_map50 = max(best_map50, row[map50_key])
        if map5095_key and isinstance(row.get(map5095_key), (int, float)):
            best_map5095 = max(best_map5095, row[map5095_key])

    safe = lambda v: round(v, 4) if isinstance(v, (int, float)) else 0
    info["best_metrics"] = {
        "best_mAP50": safe(best_map50),
        "best_mAP50_95": safe(best_map5095),
        "current_mAP50": safe(latest.get(map50_key, 0)) if map50_key else 0,
        "current_mAP50_95": safe(latest.get(map5095_key, 0)) if map5095_key else 0,
        "current_precision": safe(latest.get(precision_key, 0)) if precision_key else 0,
        "current_recall": safe(latest.get(recall_key, 0)) if recall_key else 0,
    }

    # ETA
    if len(rows) >= 2 and not info["training_finished"]:
        try:
            args_yaml = run_dir / "args.yaml"
            create_time = args_yaml.stat().st_mtime if args_yaml.exists() else results_csv.stat().st_mtime - 300
            total_elapsed = time.time() - create_time
            avg_epoch_time = total_elapsed / len(rows)
            remaining = total_epochs - len(rows)
            eta_sec = remaining * avg_epoch_time
            info["eta"] = {
                "remaining_epochs": remaining,
                "avg_epoch_seconds": round(avg_epoch_time, 1),
                "eta_seconds": round(eta_sec),
                "eta_human": str(timedelta(seconds=int(eta_sec))),
                "estimated_finish": (datetime.now() + timedelta(seconds=eta_sec)).strftime("%H:%M:%S"),
            }
        except Exception:
            pass

    return info


def get_all_status():
    """Get status for all training runs + combined score estimate."""
    result = {"runs": {}, "timestamp": datetime.now().isoformat()}

    for key, cfg in TRAINING_RUNS.items():
        run_info = parse_run(cfg["dir"], cfg["total_epochs"])
        run_info["display_name"] = cfg["name"]
        result["runs"][key] = run_info

    # Score estimation
    mc = result["runs"].get("multiclass", {})
    det = result["runs"].get("detection", {})

    mc_map50 = mc.get("best_metrics", {}).get("best_mAP50", 0)
    det_map50 = det.get("best_metrics", {}).get("best_mAP50", 0)

    # Strategy A: multiclass model (does both detection + classification)
    if mc_map50 > 0:
        est_det_a = min(1.0, mc_map50 * 1.5)
        est_cls_a = mc_map50
        score_a = (0.70 * est_det_a + 0.30 * est_cls_a) * 100
    else:
        score_a = 0

    # Strategy B: 1-class detection only (category_id=0, max 70 pts)
    score_b = det_map50 * 0.70 * 100 if det_map50 > 0 else 0

    # Strategy C: hybrid (1-class for detection + multiclass for classification)
    if det_map50 > 0 and mc_map50 > 0:
        score_c = (0.70 * det_map50 + 0.30 * mc_map50) * 100
    else:
        score_c = 0

    result["score_estimates"] = {
        "strategy_a": {
            "name": "Multiclass Only",
            "desc": "356-class model for both detection + classification",
            "score": round(score_a, 1),
            "det": round(min(1.0, mc_map50 * 1.5), 4) if mc_map50 > 0 else 0,
            "cls": round(mc_map50, 4),
        },
        "strategy_b": {
            "name": "Detection Only",
            "desc": "1-class model, category_id=0 (max 70 pts)",
            "score": round(score_b, 1),
            "det": round(det_map50, 4),
            "cls": 0,
        },
        "strategy_c": {
            "name": "Hybrid (Best)",
            "desc": "1-class detection + multiclass classification",
            "score": round(score_c, 1),
            "det": round(det_map50, 4),
            "cls": round(mc_map50, 4),
        },
        "recommended": "strategy_c" if score_c >= score_a and score_c >= score_b else (
            "strategy_a" if score_a >= score_b else "strategy_b"
        ),
    }

    return result


class MonitorHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            data = get_all_status()
            self.wfile.write(json.dumps(data, indent=2).encode())
        elif self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_path = Path(__file__).parent / "dashboard.html"
            with open(html_path, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    print(f"Training Monitor at http://localhost:{PORT}")
    print(f"Tracking: {list(TRAINING_RUNS.keys())}")
    server = http.server.HTTPServer(("", PORT), MonitorHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
