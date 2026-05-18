from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd


_NUMERIC_SAMPLE_RE = re.compile(r"^\s*(\d+)\s+([-\d.]+|\.)\s+([-\d.]+|\.)\s+([-\d.]+|\.)")


def _to_float(x: str) -> float:
    if x == ".":
        return np.nan
    try:
        return float(x)
    except Exception:
        return np.nan


def parse_asc(path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Lightweight EyeLink ASC parser for this project.

    Returns:
      samples_df: rows with block, time, xp, yp, pupil
      msgs_df: all MSG lines with block, time, text
      trials_df: one row per START/END block, plus DISPLAY_SENTENCE and TRIAL_VAR fields

    This avoids requiring the R eyelinker package.
    """
    path = Path(path)

    samples: list[dict[str, Any]] = []
    msgs: list[dict[str, Any]] = []
    trial_records: dict[int, dict[str, Any]] = {}

    block = 0
    current_block: int | None = None

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            raw = line.rstrip("\n")

            if raw.startswith("START"):
                block += 1
                current_block = block
                parts = raw.split()
                start_time = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                trial_records[current_block] = {
                    "block": current_block,
                    "start_time": start_time,
                    "end_time": None,
                    "display_time": None,
                }
                continue

            if raw.startswith("END"):
                parts = raw.split()
                if current_block is not None and len(parts) > 1 and parts[1].isdigit():
                    trial_records.setdefault(current_block, {"block": current_block})["end_time"] = int(parts[1])
                continue

            if raw.startswith("MSG"):
                parts = raw.split(maxsplit=2)
                if len(parts) >= 3:
                    try:
                        t = int(parts[1])
                    except ValueError:
                        t = None
                    text = parts[2]
                    msgs.append({"block": current_block, "time": t, "text": text})

                    if current_block is not None:
                        rec = trial_records.setdefault(current_block, {"block": current_block})

                        if "DISPLAY_SENTENCE" in text:
                            rec["display_time"] = t

                        # Example:
                        # !V TRIAL_VAR agens (970.0,100.0)
                        m = re.search(r"!V\s+TRIAL_VAR\s+(\S+)\s*(.*)$", text)
                        if m:
                            key = m.group(1)
                            val = m.group(2).strip()
                            rec[key] = val
                continue

            m = _NUMERIC_SAMPLE_RE.match(raw)
            if m and current_block is not None:
                samples.append({
                    "block": current_block,
                    "time": int(m.group(1)),
                    "xp": _to_float(m.group(2)),
                    "yp": _to_float(m.group(3)),
                    "pupil": _to_float(m.group(4)),
                })

    samples_df = pd.DataFrame(samples)
    msgs_df = pd.DataFrame(msgs)
    trials_df = pd.DataFrame(list(trial_records.values()))

    # Helpful numeric conversions for trial variables.
    for col in ["trial_num", "practice", "cond", "number", "Trial_Index_", "patiens_animacy"]:
        if col in trials_df.columns:
            trials_df[col] = pd.to_numeric(trials_df[col], errors="coerce")

    return samples_df, msgs_df, trials_df
