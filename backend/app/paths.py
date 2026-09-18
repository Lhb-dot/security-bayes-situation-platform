"""Shared filesystem locations used by application services."""

from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
DATA_ROOT = PROJECT_ROOT / "data"
MODEL_STORAGE_ROOT = BACKEND_ROOT / "storage" / "models"
OUTPUT_ROOT = BACKEND_ROOT / "storage" / "output"
