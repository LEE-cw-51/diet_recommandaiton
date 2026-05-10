# Pareto front decoder and summary analyzer.
# Run with: python experiment/results/analyze_pareto.py  (from project root)

import sys
import os
import io

# Force UTF-8 output on Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure project root is on the path (script lives at experiment/results/, so go up 3 levels)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import numpy as np

# --- 1. Load food data from Supabase ---

print("=" * 70)
print("Loading food data from Supabase...")
print("=" * 70)

from db.client import get_client

sb = get_client()

SELECT_COLS = "id,product_name,brand_name,category_type,calories,protein,carbs,fat,sugar,sodium,price,allergens"
CAL_MIN = 10.0

all_rows = []
PAGE = 1000
offset = 0
while True:
    resp = sb.table("food_master") \
             .select(SELECT_COLS) \
             .gt("calories", CAL_MIN) \
             .range(offset, offset + PAGE - 1) \
             .execute()
    batch = resp.data
    if not batch:
        break
    all_rows.extend(batch)
    if len(batch) < PAGE:
        break
    offset += PAGE

food_df = pd.DataFrame(all_rows)
print(f"  Total rows loaded: {len(food_df)}")
print(f"  Columns: {list(food_df.columns)}")
print(f"  Category distribution:")
print(food_df["category_type"].value_counts().to_string())
print()

# --- 2. Split into pools (in Supabase-return order, no sort) ---

main_df  = food_df[food_df["category_type"] == "MAIN"].reset_index(drop=True)
side_df  = food_df[food_df["category_type"].isin(["SIDE", "SOUP"])].reset_index(drop=True)
drink_df = food_df[food_df["category_type"] == "DRINK"].reset_index(drop=True)

print(f"  MAIN pool      : {len(main_df)}")
print(f"  SIDE+SOUP pool : {len(side_df)}")
print(f"  DRINK pool     : {len(drink_df)}")
print()

# --- 3. Helper: decode one row ---

def safe_float(val):
    """Return float, treating None/NaN as 0."""
    if val is None:
        return 0.0
    try:
        f = float(val)
        return 0.0 if pd.isna(f) else f
    except (TypeError, ValueError):
        return 0.0

def safe_idx(df, raw_val):
    """Round float index and clamp to valid range."""
    idx = int(round(float(raw_val))) % len(df)
    return df.iloc[idx]

def decode_solution(row):
    """Decode x0-x3 into food items and compute totals."""
    main  = safe_idx(main_df,  row["x0"])
    side1 = safe_idx(side_df,  row["x1"])
    side2 = safe_idx(side_df,  row["x2"])
    drink = safe_idx(drink_df, row["x3"])

    items = [main, side1, side2, drink]

    total_cal   = sum(safe_float(it["calories"]) for it in items)
    total_prot  = sum(safe_float(it["protein"])  for it in items)
    total_carbs = sum(safe_float(it["carbs"])    for it in items)
    total_fat   = sum(safe_float(it["fat"])      for it in items)
    total_price = sum(safe_float(it["price"])    for it in items)

    # Mark price as N/A if all items have no price
    prices = [safe_float(it["price"]) for it in items]
    has_price = any(p > 0 for p in prices)

    return {
        "main":        main["product_name"],
        "side1":       side1["product_name"],
        "side2":       side2["product_name"],
        "drink":       drink["product_name"],
        "total_cal":   total_cal,
        "total_prot":  total_prot,
        "total_carbs": total_carbs,
        "total_fat":   total_fat,
        "total_price": total_price if has_price else None,
    }

# --- 4. Load pareto CSVs and pick 5 representative solutions ---

EXP_DIRS = {
    "exp1": os.path.join(PROJECT_ROOT, "experiment", "results", "output", "exp1_nsga2_base_20260318_000401"),
    "exp2": os.path.join(PROJECT_ROOT, "experiment", "results", "output", "exp2_nsga2_base_20260318_000359"),
}

def load_all_pareto(exp_dir):
    """Concatenate all run_XX_pareto.csv files."""
    frames = []
    for fname in sorted(os.listdir(exp_dir)):
        if fname.startswith("run_") and fname.endswith("_pareto.csv"):
            path = os.path.join(exp_dir, fname)
            df = pd.read_csv(path)
            df["run"] = fname.replace("_pareto.csv", "")
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

def pick_representatives(df, n=5):
    """Pick n evenly spaced solutions from combined Pareto front, sorted by f1."""
    f_cols = [c for c in df.columns if c.startswith("f")]
    df_sorted = df.sort_values(f_cols[0]).reset_index(drop=True)
    if len(df_sorted) <= n:
        return df_sorted
    indices = np.linspace(0, len(df_sorted) - 1, n, dtype=int)
    return df_sorted.iloc[indices].reset_index(drop=True)

# --- 5. Print results for each experiment ---

for exp_name, exp_dir in EXP_DIRS.items():
    print("=" * 70)
    config_file = os.path.join(exp_dir, "config_snapshot.yaml")
    with open(config_file, "r", encoding="utf-8") as f:
        first_comments = [l.strip() for l in f if l.startswith("#")][:2]
    for c in first_comments:
        print(c)

    pareto_df = load_all_pareto(exp_dir)
    f_cols = [c for c in pareto_df.columns if c.startswith("f")]
    x_cols = [c for c in pareto_df.columns if c.startswith("x")]

    print(f"\n  Pareto solutions loaded: {len(pareto_df)} (across all runs)")
    print(f"  Objective columns: {f_cols}")
    print(f"  Variable columns:  {x_cols}")

    reps = pick_representatives(pareto_df, n=5)

    print(f"\n  --- 5 Representative Pareto Solutions ({exp_name}) ---")
    for i, (_, sol) in enumerate(reps.iterrows()):
        decoded = decode_solution(sol)
        print(f"\n  [Solution {i+1}]")
        fvals_str = "  ".join(f"f{j+1}={sol[fc]:.6f}" for j, fc in enumerate(f_cols))
        print(f"    f-values  : {fvals_str}")
        print(f"    Main      : {decoded['main']}")
        print(f"    Side 1    : {decoded['side1']}")
        print(f"    Side 2    : {decoded['side2']}")
        print(f"    Drink     : {decoded['drink']}")
        price_str = f"{decoded['total_price']:.0f} KRW" if decoded["total_price"] is not None else "N/A (NULL in DB)"
        print(f"    Totals    : Cal={decoded['total_cal']:.1f} kcal | "
              f"Protein={decoded['total_prot']:.1f}g | "
              f"Carbs={decoded['total_carbs']:.1f}g | "
              f"Fat={decoded['total_fat']:.1f}g | "
              f"Price={price_str}")
    print()

# --- 6. runs_summary statistics ---

print("=" * 70)
print("RUNS SUMMARY STATISTICS")
print("=" * 70)

METRICS = ["GD", "IGD", "HV", "Spread"]

for exp_name, exp_dir in EXP_DIRS.items():
    summary_path = os.path.join(exp_dir, "runs_summary.csv")
    summary_df = pd.read_csv(summary_path)
    print(f"\n  [{exp_name}] {os.path.basename(exp_dir)}")
    print(f"  Runs: {len(summary_df)}")
    for metric in METRICS:
        if metric in summary_df.columns:
            mean_val = summary_df[metric].mean()
            std_val  = summary_df[metric].std()
            min_val  = summary_df[metric].min()
            max_val  = summary_df[metric].max()
            print(f"    {metric:<8}: mean={mean_val:.6f}  std={std_val:.6f}  "
                  f"min={min_val:.6f}  max={max_val:.6f}")
        else:
            print(f"    {metric:<8}: NOT FOUND in summary")

print()
print("=" * 70)
print("Done.")
print("=" * 70)
