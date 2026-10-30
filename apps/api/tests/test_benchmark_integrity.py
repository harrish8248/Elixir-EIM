"""
Benchmark integrity verification test.
Fails if any file in the frozen benchmarks (data/ and data_gst/) has been modified, deleted, or corrupted.
"""

import hashlib
import os
from pathlib import Path

MANIFEST_PATH = Path(os.environ.get("ELIXIR_DATA_DIR", "docs/ocr-benchmark")) / "benchmark_manifest.sha256"


def test_benchmark_frozen_manifest_integrity():
    assert MANIFEST_PATH.exists(), f"Benchmark manifest {MANIFEST_PATH} not found"

    lines = MANIFEST_PATH.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1100, f"Expected >= 1100 files in manifest, got {len(lines)}"

    mismatches = []
    missing = []

    for line in lines:
        if not line.strip() or line.startswith("#"):
            continue
        expected_hash, rel_path = line.strip().split(maxsplit=1)
        target_path = Path(rel_path.replace("/", "\\"))

        if not target_path.exists():
            missing.append(rel_path)
            continue

        actual_hash = hashlib.sha256(target_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            mismatches.append((rel_path, expected_hash, actual_hash))

    assert not missing, f"Missing {len(missing)} benchmark files: {missing[:5]}"
    assert not mismatches, f"Mismatched SHA-256 in {len(mismatches)} benchmark files: {mismatches[:5]}"

