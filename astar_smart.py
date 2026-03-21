#!/usr/bin/env python3
"""
Astar Island SMART prediction script for NM i AI 2026.

Strategy:
1. Use simulate endpoint to observe final states across the map
2. Aggregate multiple stochastic observations per cell
3. Learn transition probabilities from completed rounds (ground truth)
4. Build empirical probability distributions for predictions
"""

import requests
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# --- Config ---
BASE_URL = "https://api.ainm.no"
SCRIPT_DIR = Path(__file__).parent
STATS_FILE = SCRIPT_DIR / "transition_stats.json"
ENV_FILE = SCRIPT_DIR / ".env"

FLOOR = 0.01
NUM_CLASSES = 6
CLASS_LABELS = ["Empty", "Settlement", "Port", "Ruin", "Forest", "Mountain"]

# Grid codes in initial state
# 10=Ocean, 11=Plains, 4=Forest, 5=Mountain, 1=Settlement, 2=Port

# Grid codes in simulate response
# 10=Ocean, 11=Plains, 4=Forest, 5=Mountain, 1=Settlement, 2=Port, 3=Ruin

# Map simulate grid values to prediction classes (0-5)
GRID_TO_CLASS = {
    10: 0,   # Ocean -> Empty
    11: 0,   # Plains -> Empty
    0: 0,    # Empty -> Empty
    1: 1,    # Settlement
    2: 2,    # Port
    3: 3,    # Ruin
    4: 4,    # Forest
    5: 5,    # Mountain
}


def load_token():
    """Load token from .env file."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().strip().split("\n"):
            if line.startswith("AINM_TOKEN="):
                return line.split("=", 1)[1].strip()
    # Fallback to environment variable
    token = os.environ.get("AINM_TOKEN")
    if token:
        return token
    print("ERROR: No token found. Create .env file with AINM_TOKEN=your_token")
    sys.exit(1)


TOKEN = load_token()
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}


def normalize_with_floor(probs):
    """Apply minimum floor and renormalize to sum to 1, ensuring floor is maintained."""
    n = len(probs)
    total_floor = FLOOR * n
    # Ensure each prob is at least FLOOR, then renormalize remaining mass
    result = [0.0] * n
    remaining_mass = 1.0 - total_floor  # mass to distribute proportionally

    raw_sum = sum(max(p - FLOOR, 0) for p in probs)
    if raw_sum > 0:
        for i in range(n):
            result[i] = FLOOR + max(p - FLOOR, 0) / raw_sum * remaining_mass if (p := probs[i]) > FLOOR else FLOOR
    else:
        # All probs are at or below floor - uniform
        result = [1.0 / n] * n

    # Final safety check
    total = sum(result)
    result = [p / total for p in result]
    # One more pass to ensure floor
    result = [max(p, FLOOR) for p in result]
    total = sum(result)
    result = [p / total for p in result]
    return result


def get_active_round():
    """Get active round info."""
    resp = requests.get(f"{BASE_URL}/astar-island/rounds", headers=HEADERS)
    resp.raise_for_status()
    rounds = resp.json()
    active = next((r for r in rounds if r["status"] == "active"), None)
    if not active:
        print("No active round found!")
        print("Available:", [(r["round_number"], r["status"]) for r in rounds])
        sys.exit(1)
    return active


def get_round_details(round_id):
    """Get round details with initial states."""
    resp = requests.get(f"{BASE_URL}/astar-island/rounds/{round_id}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def get_my_rounds():
    """Get all my round submissions."""
    resp = requests.get(f"{BASE_URL}/astar-island/my-rounds", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def simulate(round_id, seed_index, x, y, width, height):
    """Run a simulation query and get the result viewport."""
    payload = {
        "round_id": round_id,
        "seed_index": seed_index,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }
    resp = requests.post(
        f"{BASE_URL}/astar-island/simulate",
        headers=HEADERS,
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()


def get_analysis(round_id, seed_index):
    """Get analysis/ground truth for a completed round."""
    resp = requests.get(
        f"{BASE_URL}/astar-island/analysis/{round_id}/{seed_index}",
        headers=HEADERS,
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def plan_viewports(map_w, map_h, max_vp=15, num_queries=9):
    """
    Plan viewport positions to cover the entire map.
    Uses a 3x3 grid of 15x15 viewports with overlap for a 40x40 map.
    """
    viewports = []

    if num_queries >= 4:
        # 3x3 grid covers 40x40 well with 15x15 viewports
        positions = []
        for gy in range(3):
            for gx in range(3):
                vx = min(gx * 13, map_w - max_vp)  # 0, 13, 25
                vy = min(gy * 13, map_h - max_vp)  # 0, 13, 25
                positions.append((vx, vy))
        viewports = [(x, y, max_vp, max_vp) for x, y in positions]
        # Trim to query budget
        viewports = viewports[:num_queries]
    elif num_queries >= 2:
        # 2x2 grid
        for gy in range(2):
            for gx in range(2):
                vx = gx * (map_w - max_vp)
                vy = gy * (map_h - max_vp)
                viewports.append((vx, vy, max_vp, max_vp))
    else:
        # Single center viewport
        cx = (map_w - max_vp) // 2
        cy = (map_h - max_vp) // 2
        viewports.append((cx, cy, max_vp, max_vp))

    return viewports


def learn_from_completed_rounds():
    """
    Learn transition probabilities from completed rounds' ground truth.
    Returns dict: {terrain_code: [avg_prob_class_0, ..., avg_prob_class_5]}
    """
    # Load existing stats
    existing_stats = {}
    learned_rounds = set()
    if STATS_FILE.exists():
        data = json.loads(STATS_FILE.read_text())
        existing_stats = data.get("distributions", {})
        learned_rounds = set(data.get("learned_rounds", []))
        print(f"  Loaded existing stats from {len(learned_rounds)} rounds")

    # Find completed rounds we haven't learned from yet
    print("  Fetching completed rounds...")
    resp = requests.get(f"{BASE_URL}/astar-island/rounds", headers=HEADERS)
    resp.raise_for_status()
    all_rounds = resp.json()
    completed = [r for r in all_rounds if r["status"] == "completed"]

    new_rounds = [r for r in completed if r["id"] not in learned_rounds]
    if not new_rounds:
        print("  No new completed rounds to learn from")
        return existing_stats

    print(f"  Learning from {len(new_rounds)} new completed rounds...")

    # Accumulate distributions
    terrain_dist = defaultdict(lambda: [0.0] * NUM_CLASSES)
    terrain_count = defaultdict(int)

    # Start from existing data
    for terrain_str, dist in existing_stats.items():
        terrain = int(terrain_str)
        # Weight by number of previous rounds
        weight = len(learned_rounds) * 5 * 1600  # rough estimate per terrain
        # Actually, just re-learn from scratch with all available data
        pass

    # Re-learn from ALL completed rounds (including previously learned)
    all_learned = list(learned_rounds)
    for r in new_rounds:
        all_learned.append(r["id"])

    for round_info in completed:
        rid = round_info["id"]
        rnum = round_info["round_number"]
        for seed in range(5):
            analysis = get_analysis(rid, seed)
            if analysis is None:
                continue
            ini = analysis["initial_grid"]
            gt = analysis["ground_truth"]
            for y in range(len(ini)):
                for x in range(len(ini[0])):
                    cell_type = ini[y][x]
                    gt_probs = gt[y][x]
                    for c in range(NUM_CLASSES):
                        terrain_dist[cell_type][c] += gt_probs[c]
                    terrain_count[cell_type] += 1
        print(f"    Round {rnum} processed")

    # Compute averages
    result = {}
    print("\n  === Learned distributions ===")
    for terrain in sorted(terrain_dist.keys()):
        n = terrain_count[terrain]
        avg = [terrain_dist[terrain][c] / n for c in range(NUM_CLASSES)]
        result[str(terrain)] = avg
        nonzero = [(CLASS_LABELS[i], f"{avg[i]:.4f}") for i in range(NUM_CLASSES) if avg[i] > 0.005]
        print(f"    Terrain {terrain} (n={n}): {nonzero}")

    # Save
    save_data = {
        "distributions": result,
        "learned_rounds": list(set(all_learned)),
        "terrain_counts": {str(k): v for k, v in terrain_count.items()},
    }
    STATS_FILE.write_text(json.dumps(save_data, indent=2))
    print(f"  Saved stats to {STATS_FILE}")

    return result


def build_prediction_from_observations(
    initial_state, observations, learned_dists, map_w, map_h
):
    """
    Build prediction combining observations and learned distributions.

    observations: dict of (x, y) -> list of class counts from simulate queries
    learned_dists: dict of terrain_code -> [prob_0, ..., prob_5]
    """
    grid = initial_state["grid"]
    prediction = []

    for y in range(map_h):
        row = []
        for x in range(map_w):
            cell_key = (x, y)

            if cell_key in observations and sum(observations[cell_key]) > 0:
                # We have observations for this cell - use empirical distribution
                counts = observations[cell_key]
                total = sum(counts)
                probs = [c / total for c in counts]
            else:
                # No observations - use learned distributions from ground truth
                cell_type = grid[y][x]
                cell_str = str(cell_type)

                if cell_str in learned_dists:
                    probs = list(learned_dists[cell_str])
                else:
                    # Fallback: baseline heuristics
                    probs = get_baseline_probs(cell_type, initial_state, x, y)

            # Apply floor and normalize
            probs = normalize_with_floor(probs)
            row.append(probs)
        prediction.append(row)

    return prediction


def get_baseline_probs(cell_type, initial_state, x, y):
    """Fallback baseline probabilities when no data available."""
    if cell_type == 10:
        return [0.94, 0.01, 0.01, 0.01, 0.01, 0.02]
    elif cell_type == 11:
        return [0.82, 0.08, 0.01, 0.01, 0.06, 0.02]
    elif cell_type == 5:
        return [0.01, 0.01, 0.01, 0.01, 0.01, 0.95]
    elif cell_type == 4:
        return [0.05, 0.10, 0.01, 0.01, 0.81, 0.02]
    elif cell_type == 1:
        return [0.40, 0.37, 0.01, 0.02, 0.19, 0.01]
    elif cell_type == 2:
        return [0.45, 0.10, 0.21, 0.02, 0.21, 0.01]
    else:
        return [1.0 / NUM_CLASSES] * NUM_CLASSES


def submit_prediction(round_id, seed_index, prediction):
    """Submit prediction for a seed."""
    payload = {
        "round_id": round_id,
        "seed_index": seed_index,
        "prediction": prediction,
    }
    resp = requests.post(
        f"{BASE_URL}/astar-island/submit",
        headers=HEADERS,
        json=payload,
    )
    return resp


def main():
    print("=" * 60)
    print("ASTAR ISLAND SMART PREDICTOR")
    print("=" * 60)

    # Step 1: Learn from completed rounds
    print("\n[STEP 1] Learning from completed rounds...")
    learned_dists = learn_from_completed_rounds()

    # Step 2: Get active round
    print("\n[STEP 2] Fetching active round...")
    active = get_active_round()
    round_id = active["id"]
    print(f"  Round #{active['round_number']} (id: {round_id})")
    print(f"  Closes at: {active['closes_at']}")
    print(f"  Weight: {active['round_weight']}")

    # Step 3: Get round details
    print("\n[STEP 3] Fetching round details...")
    details = get_round_details(round_id)
    initial_states = details["initial_states"]
    seeds_count = details["seeds_count"]
    map_w = details["map_width"]
    map_h = details["map_height"]
    print(f"  Map: {map_w}x{map_h}, Seeds: {seeds_count}")

    # Check query budget
    my_rounds = get_my_rounds()
    active_info = next((r for r in my_rounds if r["id"] == round_id), None)
    queries_used = active_info["queries_used"] if active_info else 0
    queries_max = active_info["queries_max"] if active_info else 50
    queries_remaining = queries_max - queries_used
    print(f"  Queries: {queries_used}/{queries_max} used, {queries_remaining} remaining")

    # Plan query budget: 9 per seed ideally, but respect limits
    queries_per_seed = min(9, queries_remaining // seeds_count)
    if queries_per_seed < 1:
        print("  WARNING: Not enough queries for observations! Using learned distributions only.")
        queries_per_seed = 0

    print(f"  Using {queries_per_seed} queries per seed ({queries_per_seed * seeds_count} total)")

    # Step 4: For each seed, observe and predict
    for seed_idx in range(seeds_count):
        print(f"\n{'='*40}")
        print(f"[SEED {seed_idx}]")
        print(f"{'='*40}")

        state = initial_states[seed_idx]

        # Count terrain types
        from collections import Counter
        flat = [c for row in state["grid"] for c in row]
        counts = Counter(flat)
        print(f"  Terrain: {dict(counts)}")
        print(f"  Settlements: {len(state.get('settlements', []))}")

        # Observe with simulate queries
        observations = defaultdict(lambda: [0] * NUM_CLASSES)

        if queries_per_seed > 0:
            viewports = plan_viewports(map_w, map_h, max_vp=15, num_queries=queries_per_seed)
            viewports = viewports[:queries_per_seed]  # Limit to budget

            for vp_idx, (vx, vy, vw, vh) in enumerate(viewports):
                print(f"  Query {vp_idx + 1}/{len(viewports)}: viewport ({vx},{vy}) {vw}x{vh}...", end=" ")
                try:
                    result = simulate(round_id, seed_idx, vx, vy, vw, vh)
                    sim_grid = result["grid"]

                    # Count observations
                    cells_observed = 0
                    for row_idx, row in enumerate(sim_grid):
                        for col_idx, cell_val in enumerate(row):
                            abs_x = vx + col_idx
                            abs_y = vy + row_idx
                            if abs_x < map_w and abs_y < map_h:
                                cls = GRID_TO_CLASS.get(cell_val, 0)
                                observations[(abs_x, abs_y)][cls] += 1
                                cells_observed += 1

                    print(f"OK ({cells_observed} cells)")
                except Exception as e:
                    print(f"ERROR: {e}")

            print(f"  Total observed cells: {len(observations)} unique positions")
            # Show observation coverage
            total_cells = map_w * map_h
            coverage = len(observations) / total_cells * 100
            print(f"  Coverage: {coverage:.1f}% of map")

        # Build prediction
        print("  Building prediction...")
        prediction = build_prediction_from_observations(
            state, observations, learned_dists, map_w, map_h
        )

        # Verify
        for y in range(len(prediction)):
            for x in range(len(prediction[0])):
                s = sum(prediction[y][x])
                assert abs(s - 1.0) < 1e-6, f"Prob sum at ({x},{y}) = {s}"
                for p in prediction[y][x]:
                    assert p >= FLOOR - 1e-6, f"Prob below floor at ({x},{y}): {p}"

        # Submit
        print(f"  Submitting prediction...")
        resp = submit_prediction(round_id, seed_idx, prediction)
        if resp.status_code == 200:
            result = resp.json()
            score = result.get("score", "N/A")
            print(f"  SUCCESS! Score: {score}")
        else:
            print(f"  ERROR {resp.status_code}: {resp.text}")

    # Step 5: Final scores
    print(f"\n{'='*60}")
    print("[FINAL SCORES]")
    print(f"{'='*60}")
    my_rounds = get_my_rounds()
    active_info = next((r for r in my_rounds if r["id"] == round_id), None)
    if active_info:
        print(f"  Round #{active_info['round_number']}:")
        print(f"    Round score: {active_info.get('round_score', 'N/A')}")
        print(f"    Seed scores: {active_info.get('seed_scores', 'N/A')}")
        print(f"    Queries used: {active_info.get('queries_used', 'N/A')}/{active_info.get('queries_max', 'N/A')}")
        print(f"    Rank: {active_info.get('rank', 'N/A')}/{active_info.get('total_teams', 'N/A')}")
    else:
        print("  Could not find active round in my-rounds")
        print(json.dumps(my_rounds, indent=2))


if __name__ == "__main__":
    main()
