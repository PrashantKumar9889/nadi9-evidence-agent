"""Shared paths for the synthetic Nadi-9 pack."""

from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic"


@pytest.fixture
def data_dir() -> Path:
    return DATA_DIR
