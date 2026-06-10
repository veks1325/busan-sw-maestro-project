"""EDA template that reads project CSV files directly."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    """Parse data paths supplied by the experiment runner."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-path", type=Path, required=True)
    parser.add_argument("--test-path", type=Path)
    return parser.parse_args()


def run_eda(train_path: Path, test_path: Path | None) -> None:
    """Load project CSVs and create experiment-local EDA artifacts."""
    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path) if test_path and test_path.exists() else None
    image_dir = Path(__file__).resolve().parent / "img"
    image_dir.mkdir(parents=True, exist_ok=True)

    # Replace this placeholder with hypothesis-specific EDA and visualizations.
    train.select_dtypes(include="number").hist(figsize=(10, 6))
    plt.tight_layout()
    plt.savefig(image_dir / "numeric_distributions.png")
    plt.close("all")

    print(f"train shape: {train.shape}")
    if test is not None:
        print(f"test shape: {test.shape}")


if __name__ == "__main__":
    arguments = parse_args()
    run_eda(arguments.train_path, arguments.test_path)
