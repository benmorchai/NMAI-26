#!/usr/bin/env python3
"""Astar Island baseline prediction script for NM i AI 2026."""

import requests
import json
import sys

BASE_URL = "https://api.ainm.no"
TOKEN = "SETT_INN_TOKEN_HER"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# 6 classes: Empty(0), Settlement(1), Port(2), Ruin(3), Forest(4), Mountain(5)
# Initial state terrain codes: 10=Ocean, 11=Plains, 4=Forest, 5=Mountain, 1=Settlement, 2=Port

FLOOR = 0.01


def normalize_with_floor(probs):
    """Apply minimum floor and renormalize to sum to 1."""
    probs = [max(p, FLOOR) for p in probs]
    total = sum(probs)
    return [p / total for p in probs]


def build_prediction(initial_state):
    """Build a 40x40x6 prediction tensor from initial state grid."""
    grid = initial_state["grid"]
    settlements = initial_state.get("settlements", [])

    # Build a lookup of settlement positions
    settlement_map = {}
    for s in settlements:
        settlement_map[(s["x"], s["y"])] = s

    H = len(grid)
    W = len(grid[0])
    prediction = []

    for y in range(H):
        row = []
        for x in range(W):
            cell = grid[y][x]

            if cell == 10:
                # Ocean -> stays Empty with very high probability
                probs = [0.94, 0.01, 0.01, 0.01, 0.01, 0.02]
            elif cell == 11:
                # Plains -> mostly Empty, small chance of settlement/forest growth
                probs = [0.70, 0.06, 0.02, 0.04, 0.15, 0.03]
            elif cell == 5:
                # Mountain -> stays Mountain
                probs = [0.02, 0.01, 0.01, 0.01, 0.02, 0.93]
            elif cell == 4:
                # Forest -> likely stays Forest, can be cleared
                probs = [0.12, 0.03, 0.01, 0.02, 0.80, 0.02]
            elif cell == 1:
                # Settlement -> can become Settlement, Port, Ruin, or Empty
                s = settlement_map.get((x, y))
                if s and s.get("has_port"):
                    # Port settlement -> higher chance of staying Port
                    probs = [0.05, 0.20, 0.45, 0.20, 0.05, 0.05]
                else:
                    # Regular settlement -> mix of Settlement, Ruin, Empty
                    probs = [0.08, 0.40, 0.10, 0.30, 0.07, 0.05]
            elif cell == 2:
                # Port -> can stay Port or become Ruin/Settlement
                probs = [0.05, 0.15, 0.45, 0.25, 0.05, 0.05]
            else:
                # Unknown -> uniform-ish
                probs = [0.30, 0.10, 0.05, 0.10, 0.30, 0.15]

            probs = normalize_with_floor(probs)
            row.append(probs)
        prediction.append(row)

    return prediction


def main():
    # 1. Get active round
    print("Fetching rounds...")
    resp = requests.get(f"{BASE_URL}/astar-island/rounds", headers=HEADERS)
    resp.raise_for_status()
    rounds = resp.json()

    active = next((r for r in rounds if r["status"] == "active"), None)
    if not active:
        print("No active round found!")
        print("Available rounds:", [(r["round_number"], r["status"]) for r in rounds])
        sys.exit(1)

    round_id = active["id"]
    print(f"Active round: #{active['round_number']} (id: {round_id})")
    print(f"  Closes at: {active['closes_at']}")
    print(f"  Weight: {active['round_weight']}")

    # 2. Get round details with initial states
    print("\nFetching round details...")
    resp = requests.get(f"{BASE_URL}/astar-island/rounds/{round_id}", headers=HEADERS)
    resp.raise_for_status()
    details = resp.json()

    initial_states = details["initial_states"]
    seeds_count = details["seeds_count"]
    print(f"  Map: {details['map_width']}x{details['map_height']}")
    print(f"  Seeds: {seeds_count}")

    # 3. Build and submit predictions for all seeds
    for seed_idx in range(seeds_count):
        print(f"\n--- Seed {seed_idx} ---")
        state = initial_states[seed_idx]

        # Count terrain types
        from collections import Counter
        flat = [c for row in state["grid"] for c in row]
        counts = Counter(flat)
        print(f"  Terrain: {dict(counts)}")
        print(f"  Settlements: {len(state.get('settlements', []))}")

        # Build prediction
        prediction = build_prediction(state)
        print(f"  Prediction shape: {len(prediction)}x{len(prediction[0])}x{len(prediction[0][0])}")

        # Verify all probs sum to ~1
        for y in range(len(prediction)):
            for x in range(len(prediction[0])):
                s = sum(prediction[y][x])
                assert abs(s - 1.0) < 1e-6, f"Prob sum at ({x},{y}) = {s}"
                for p in prediction[y][x]:
                    assert p >= FLOOR, f"Prob below floor at ({x},{y}): {p}"

        # Submit
        payload = {
            "round_id": round_id,
            "seed_index": seed_idx,
            "prediction": prediction,
        }

        print(f"  Submitting seed {seed_idx}...")
        resp = requests.post(
            f"{BASE_URL}/astar-island/submit",
            headers=HEADERS,
            json=payload,
        )

        if resp.status_code == 200:
            result = resp.json()
            print(f"  SUCCESS: {json.dumps(result, indent=2)}")
        else:
            print(f"  ERROR {resp.status_code}: {resp.text}")

    # 4. Check scores
    print("\n=== Checking scores ===")
    resp = requests.get(f"{BASE_URL}/astar-island/my-rounds", headers=HEADERS)
    if resp.status_code == 200:
        my_rounds = resp.json()
        print(json.dumps(my_rounds, indent=2))
    else:
        print(f"Could not fetch scores: {resp.status_code} {resp.text}")


if __name__ == "__main__":
    main()
