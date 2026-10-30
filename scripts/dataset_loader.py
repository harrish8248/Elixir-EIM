"""
Dataset Loader for Elixir EIM Benchmark Datasets.
Supports loading directly from docs/ocr-benchmark/benchmark_data.tar.gz or extracted cache.
Configurable via ELIXIR_DATA_DIR environment variable.
"""

import os
import tarfile
from pathlib import Path

BENCHMARK_DIR = Path(os.getenv("ELIXIR_DATA_DIR", "docs/ocr-benchmark"))
ARCHIVE_PATH = BENCHMARK_DIR / "benchmark_data.tar.gz"


def ensure_dataset(dataset_name: str) -> Path:
    """Ensure a specific dataset directory exists; extracts from archive if needed."""
    target_dir = BENCHMARK_DIR / dataset_name
    if target_dir.exists() and any(target_dir.iterdir()):
        return target_dir

    if not ARCHIVE_PATH.exists():
        raise FileNotFoundError(f"Neither dataset directory {target_dir} nor archive {ARCHIVE_PATH} exists.")

    print(f"Extracting dataset {dataset_name} from {ARCHIVE_PATH}...")
    with tarfile.open(ARCHIVE_PATH, "r:gz") as tar:
        members = [m for m in tar.getmembers() if m.name.startswith(dataset_name)]
        tar.extractall(path=BENCHMARK_DIR, members=members)

    return target_dir
