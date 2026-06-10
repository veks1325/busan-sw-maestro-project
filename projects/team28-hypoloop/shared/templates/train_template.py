"""Training template that reads project CSV files directly."""

from __future__ import annotations

import argparse
from pathlib import Path

import mlflow
import mlflow.sklearn
import pandas as pd


def parse_args() -> argparse.Namespace:
    """Parse data and tracking paths supplied by the experiment runner."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-path", type=Path, required=True)
    parser.add_argument("--test-path", type=Path)
    parser.add_argument("--mlflow-uri", required=True)
    return parser.parse_args()


def load_data(
    train_path: Path,
    test_path: Path | None,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Load train and optional test CSVs without querying backend metadata."""
    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path) if test_path and test_path.exists() else None
    return train, test


def run_training(
    train_path: Path,
    test_path: Path | None,
    mlflow_uri: str,
) -> None:
    """Provide the CSV loading and MLflow scaffold for generated training code."""
    train, test = load_data(train_path, test_path)
    mlflow.set_tracking_uri(mlflow_uri)

    with mlflow.start_run():
        mlflow.log_param("train_rows", len(train))
        mlflow.log_param("test_rows", len(test) if test is not None else 0)
        # Add feature engineering, model fitting, metrics, and artifacts here.


if __name__ == "__main__":
    arguments = parse_args()
    run_training(arguments.train_path, arguments.test_path, arguments.mlflow_uri)
