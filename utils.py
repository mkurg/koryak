from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pandas as pd
import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def normalize_participant_id(value: object, use_cyrillic: bool = True) -> str:
    """
    Normalize participant IDs across common variants:
    K01, k01, К01, к01 -> К01 by default.
    """
    if pd.isna(value):
        return ""
    s = str(value).strip().upper()
    s = s.replace("К", "K")  # Cyrillic Ka to Latin K internally
    m = re.search(r"K\s*0*(\d+)", s)
    if not m:
        return str(value).strip()
    num = int(m.group(1))
    return f"К{num:02d}" if use_cyrillic else f"K{num:02d}"


def clean_string_series(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip()


def parse_number(value: object) -> float:
    if pd.isna(value):
        return float("nan")
    return pd.to_numeric(str(value).strip().replace(",", "."), errors="coerce")


def parse_coord_pair(value: object) -> tuple[float, float] | tuple[None, None]:
    """
    Parse ASC TRIAL_VAR coordinates like "(970.0,100.0)".
    """
    if value is None or pd.isna(value):
        return (None, None)
    text = str(value)
    nums = re.findall(r"-?\d+(?:\.\d+)?", text)
    if len(nums) < 2:
        return (None, None)
    return (float(nums[0]), float(nums[1]))
