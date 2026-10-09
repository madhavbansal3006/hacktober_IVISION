"""
Generate a stratified training sample table from the aligned feature stack
and label raster, and produce a spatially-blocked train/test split to
reduce leakage from spatially autocorrelated neighboring pixels.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def stratified_sample(
    feature_array: np.ndarray,
    label_array: np.ndarray,
    transform,
    samples_per_class: int,
    target_classes: dict,
    random_state: int = 42,
    mode: str = "equal_count",
    max_total_samples: int = 20000,
) -> pd.DataFrame:
    """Sample valid pixels per class for training.

    mode="equal_count" (default, Experiments A/B): up to
      `samples_per_class` pixels per class regardless of true prevalence.

    mode="natural_prior" (Experiment C): sample proportionally to each
      class's true prevalence among valid labeled pixels, capped at
      `max_total_samples` total, with a small floor per class
      (max(50, ...)) so rare classes are not entirely absent from training.
      This deliberately keeps the class imbalance from the reference
      labels intact, unlike equal_count sampling.

    Returns a DataFrame with feature columns, LULC_Label, and pixel
    row/col/x/y so a spatial block split can be computed downstream.
    """
    rng = np.random.default_rng(random_state)
    rows_out = []

    if mode == "natural_prior":
        counts_available = {
            c: int((label_array == c).sum()) for c in target_classes.keys()
        }
        total_available = sum(counts_available.values())
        min_floor = 50
        target_n = {}
        for c, n_avail in counts_available.items():
            if total_available == 0:
                target_n[c] = 0
                continue
            proportional = int(round(max_total_samples * n_avail / total_available))
            target_n[c] = max(min_floor, proportional) if n_avail > 0 else 0
    elif mode == "equal_count":
        target_n = {c: samples_per_class for c in target_classes.keys()}
    else:
        raise ValueError(f"Unknown sampling mode: {mode}")

    for class_id in sorted(target_classes.keys()):
        rr, cc = np.where(label_array == class_id)
        n_available = len(rr)
        if n_available == 0:
            print(f"  WARNING: class {class_id} ({target_classes[class_id]}) has 0 valid pixels. Skipped.")
            continue
        n_take = min(target_n[class_id], n_available)
        idx = rng.choice(n_available, size=n_take, replace=False)
        sel_rr, sel_cc = rr[idx], cc[idx]

        xs, ys = rasterio_xy_batch(transform, sel_rr, sel_cc)

        for i in range(n_take):
            r, c = sel_rr[i], sel_cc[i]
            feat_vals = feature_array[r, c, :]
            rows_out.append({
                **{f"__feat_{j}": v for j, v in enumerate(feat_vals)},
                "row": int(r), "col": int(c),
                "x": xs[i], "y": ys[i],
                "LULC_Label": int(class_id),
            })
        print(f"  Class {class_id} ({target_classes[class_id]}): sampled {n_take} / {n_available} "
              f"available valid pixels (mode={mode})")

    df = pd.DataFrame(rows_out)
    return df


def rasterio_xy_batch(transform, rows: np.ndarray, cols: np.ndarray):
    """Vectorized pixel (row, col) -> (x, y) center-of-pixel coordinates
    using an affine transform, without importing rasterio.transform.xy in
    a per-pixel Python loop (which is slow for thousands of samples).
    """
    xs = transform.c + (cols + 0.5) * transform.a + (rows + 0.5) * transform.b
    ys = transform.f + (cols + 0.5) * transform.d + (rows + 0.5) * transform.e
    return xs, ys


def hybrid_sqrt_sample(
    feature_array: np.ndarray,
    label_array: np.ndarray,
    transform,
    target_classes: dict,
    total_budget: int = 18000,
    min_floor: int = 300,
    block_size_m: float = 300.0,
    block_spread_factor: float = 3.0,
    random_state: int = 42,
) -> pd.DataFrame:
    """Model 1.1 hybrid sampling strategy.

    Allocation: samples per class proportional to sqrt(available valid
    pixels), not linear proportion (Experiment C) and not equal-count
    (Experiment B). Sqrt-proportional allocation is a standard compromise
    for class imbalance (used e.g. for balancing corpora across languages
    in multilingual NLP training) — it keeps the majority class dominant
    without letting it swamp the training set, and lifts rare classes well
    above their true prevalence without giving them full parity with
    common classes. Enforced with a floor (min_floor) so no class is
    starved, and capped at what's actually available.

    Spatial diversity safeguard: within each class, candidate pixels are
    grouped into `block_size_m` spatial blocks (same grid as the
    train/test split), and no single block may contribute more than
    `block_spread_factor` times its "fair share" (target_n / n_blocks)
    of that class's samples — preventing one cluster (e.g. a single farm
    pond) from dominating a class's training signal, while still allowing
    naturally concentrated classes (e.g. Water) to be sampled where they
    actually occur.
    """
    rng = np.random.default_rng(random_state)
    class_ids = sorted(target_classes.keys())

    avail = {c: int((label_array == c).sum()) for c in class_ids}
    sqrt_w = {c: np.sqrt(avail[c]) if avail[c] > 0 else 0.0 for c in class_ids}
    total_sqrt = sum(sqrt_w.values())
    target_n = {}
    for c in class_ids:
        if avail[c] == 0:
            target_n[c] = 0
            continue
        raw = int(round(total_budget * sqrt_w[c] / total_sqrt)) if total_sqrt > 0 else 0
        target_n[c] = min(max(raw, min_floor), avail[c])

    print(f"  Hybrid sqrt allocation (budget={total_budget}, floor={min_floor}):")
    for c in class_ids:
        print(f"    Class {c} ({target_classes[c]}): available={avail[c]}, target={target_n[c]} "
              f"({100*target_n[c]/avail[c]:.2f}% of available)" if avail[c] else
              f"    Class {c} ({target_classes[c]}): available=0, skipped")

    rows_out = []
    for c in class_ids:
        if target_n[c] == 0:
            continue
        rr, cc = np.where(label_array == c)
        xs_all, ys_all = rasterio_xy_batch(transform, rr, cc)
        block_ids = list(zip((xs_all // block_size_m).astype(int), (ys_all // block_size_m).astype(int)))

        block_to_indices = {}
        for i, b in enumerate(block_ids):
            block_to_indices.setdefault(b, []).append(i)

        n_blocks = len(block_to_indices)
        fair_share = max(1, target_n[c] / n_blocks)
        max_per_block = max(1, int(np.ceil(fair_share * block_spread_factor)))

        block_keys = list(block_to_indices.keys())
        rng.shuffle(block_keys)

        selected_local_idx = []
        for b in block_keys:
            if len(selected_local_idx) >= target_n[c]:
                break
            candidates = block_to_indices[b]
            take = min(max_per_block, len(candidates), target_n[c] - len(selected_local_idx))
            chosen = rng.choice(candidates, size=take, replace=False) if take < len(candidates) else np.array(candidates)
            selected_local_idx.extend(chosen.tolist())

        selected_local_idx = np.array(selected_local_idx[:target_n[c]])
        sel_rr, sel_cc = rr[selected_local_idx], cc[selected_local_idx]
        xs, ys = rasterio_xy_batch(transform, sel_rr, sel_cc)

        n_blocks_used = len(set(zip((xs // block_size_m).astype(int), (ys // block_size_m).astype(int))))
        print(f"    Class {c}: sampled {len(sel_rr)} from {n_blocks_used}/{n_blocks} blocks "
              f"(max_per_block cap={max_per_block})")

        for i in range(len(sel_rr)):
            r, cidx = sel_rr[i], sel_cc[i]
            feat_vals = feature_array[r, cidx, :]
            rows_out.append({
                **{f"__feat_{j}": v for j, v in enumerate(feat_vals)},
                "row": int(r), "col": int(cidx), "x": xs[i], "y": ys[i], "LULC_Label": int(c),
            })

    return pd.DataFrame(rows_out)


def finalize_columns(df: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
    """Rename the internal __feat_N columns to their real names, in order,
    and drop helper row/col/x/y columns that aren't part of the saved CSV
    schema (kept available upstream for the spatial split only).
    """
    rename = {f"__feat_{j}": name for j, name in enumerate(feature_names)}
    df = df.rename(columns=rename)
    ordered_cols = feature_names + ["LULC_Label"]
    return df[["row", "col", "x", "y"] + ordered_cols]


def spatial_block_split(
    df: pd.DataFrame,
    block_size_m: float,
    test_fraction: float,
    random_state: int = 42,
) -> pd.DataFrame:
    """Assign each sample to a spatial block (grid cell of block_size_m),
    then randomly assign ENTIRE BLOCKS (not individual pixels) to
    train/test. This prevents nearby, spatially-correlated pixels from
    leaking between train and test sets. Adds a 'split' column
    ('train'/'test') to the returned DataFrame.
    """
    rng = np.random.default_rng(random_state)

    block_x = (df["x"] // block_size_m).astype(int)
    block_y = (df["y"] // block_size_m).astype(int)
    df = df.copy()
    df["_block_id"] = list(zip(block_x, block_y))

    unique_blocks = df["_block_id"].unique()
    rng.shuffle(unique_blocks)
    n_test_blocks = max(1, int(len(unique_blocks) * test_fraction))
    test_blocks = set(map(tuple, unique_blocks[:n_test_blocks]))

    df["split"] = df["_block_id"].apply(lambda b: "test" if b in test_blocks else "train")
    df = df.drop(columns=["_block_id"])

    n_train = (df["split"] == "train").sum()
    n_test = (df["split"] == "test").sum()
    print(f"  Spatial block split ({block_size_m}m blocks): "
          f"{len(unique_blocks)} total blocks, {n_test_blocks} assigned to test "
          f"-> {n_train} train samples, {n_test} test samples")

    return df
