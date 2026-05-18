#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


SAMPLE_RE = re.compile(r"^\s*(\d+)\s+([-\d.]+|\.)\s+([-\d.]+|\.)\s+([-\d.]+|\.)")
TRIAL_VAR_RE = re.compile(r"!V\s+TRIAL_VAR\s+(\S+)\s*(.*)$")
EBLINK_RE = re.compile(r"^EBLINK\s+\S+\s+(\d+)\s+(\d+)\s+\d+")

WINDOWS = [
    ("speech_planning", "Speech planning", "100-600 ms after display"),
    ("linguistic_encoding_1", "Linguistic encoding I", "1st half of 600 ms to speech onset"),
    ("linguistic_encoding_2", "Linguistic encoding II", "2nd half of 600 ms to speech onset"),
    ("linguistic_encoding_3", "Linguistic encoding III", "0-1000 ms after speech onset"),
    ("post_onset_1000_2500", "Post-onset 1000-2500", "1000-2500 ms after speech onset"),
]
WINDOW_TITLE = {key: title for key, title, _desc in WINDOWS}
WINDOW_DESC = {key: desc for key, _title, desc in WINDOWS}

INCLUDED_PARTICIPANTS = {
    "К01",
    "К03",
    "К04",
    "К05",
    "К06",
    "К07",
    "К10",
    "К13",
    "К14",
    "К15",
    "К16",
    "К17",
    "К20",
    "К22",
    "К24",
    "К25",
}


@dataclass(frozen=True)
class BehaviorTrial:
    participant: str
    image: str
    rt: float
    sentence_type: str
    word_order: str
    fluency: str
    included_participant: bool


@dataclass
class AscTrial:
    block: int
    display_time: int | None = None
    vars: dict[str, str] = field(default_factory=dict)
    samples: list[tuple[int, str, str, str]] = field(default_factory=list)
    blinks: list[tuple[int, int]] = field(default_factory=list)


def normalize_participant_id(value: object) -> str:
    text = str(value).strip().upper().replace("К", "K")
    match = re.search(r"K\s*0*(\d+)", text)
    if not match:
        return str(value).strip()
    return f"К{int(match.group(1)):02d}"


def parse_float(value: object) -> float | None:
    text = str(value).strip().replace(",", ".")
    if not text or text == "-":
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    return None if math.isnan(out) else out


def load_clean_behavior(
    path: Path,
    analysis_participants_only: bool,
) -> dict[tuple[str, str], BehaviorTrial]:
    out: dict[tuple[str, str], BehaviorTrial] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            participant = normalize_participant_id(row.get("participant's id", ""))
            included = participant in INCLUDED_PARTICIPANTS
            if analysis_participants_only and not included:
                continue

            rt = parse_float(row.get("reaction time", ""))
            sentence_type = str(row.get("sentence type", "")).strip().lower()
            word_order = str(row.get("word order", "")).strip()
            fluency = str(row.get("fluency", "")).strip().lower()
            image = str(row.get("image", "")).strip()

            if (
                rt is None
                or rt >= 6000
                or fluency != "yes"
                or word_order != "AVP"
                or sentence_type not in {"direct", "inverse"}
                or not image
            ):
                continue

            out[(participant, image)] = BehaviorTrial(
                participant=participant,
                image=image,
                rt=rt,
                sentence_type=sentence_type,
                word_order=word_order,
                fluency=fluency,
                included_participant=included,
            )
    return out


def parse_asc(path: Path, max_samples_after_display: int = 9000) -> list[AscTrial]:
    trials: list[AscTrial] = []
    current: AscTrial | None = None

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            raw = line.rstrip("\n")

            if raw.startswith("START"):
                current = AscTrial(block=len(trials) + 1)
                trials.append(current)
                continue

            if current is None:
                continue

            if raw.startswith("MSG"):
                parts = raw.split(maxsplit=2)
                if len(parts) >= 3:
                    try:
                        msg_time = int(parts[1])
                    except ValueError:
                        msg_time = None
                    text = parts[2]

                    if msg_time is not None and "DISPLAY_SENTENCE" in text:
                        current.display_time = msg_time

                    var_match = TRIAL_VAR_RE.search(text)
                    if var_match:
                        current.vars[var_match.group(1)] = var_match.group(2).strip()
                continue

            blink_match = EBLINK_RE.match(raw)
            if blink_match:
                current.blinks.append((int(blink_match.group(1)), int(blink_match.group(2))))
                continue

            if current.display_time is None or len(current.samples) >= max_samples_after_display:
                continue

            sample_match = SAMPLE_RE.match(raw)
            if not sample_match:
                continue

            sample_time = int(sample_match.group(1))
            if sample_time < current.display_time:
                continue
            current.samples.append(
                (
                    sample_time,
                    sample_match.group(2),
                    sample_match.group(3),
                    sample_match.group(4),
                )
            )

    return trials


def khanty_cut_label(value: float) -> float | None:
    if value < -0.05 or value > 1:
        return None
    index = math.ceil((value / 0.05) - 1e-12)
    if index < 0 or index > 20:
        return None
    return round(index * 0.05, 2)


def window_bucket(sample_index: int, rt: float, window_key: str) -> tuple[int, float] | None:
    if window_key == "speech_planning":
        time_bin50 = sample_index // 50
        if 2 <= time_bin50 <= 12:
            return time_bin50, (time_bin50 - 2) / 10
        return None

    if window_key in {"linguistic_encoding_1", "linguistic_encoding_2"}:
        half_window = 0.5 * (rt - 600)
        if half_window <= 0:
            return None

        if window_key == "linguistic_encoding_1":
            if not (sample_index > 600 and sample_index <= 600 + half_window):
                return None
            time_bin50 = sample_index // 50
            rel = khanty_cut_label((50 * (time_bin50 - 12)) / half_window)
            return None if rel is None else (time_bin50, rel)

        first_second_half_sample = math.floor(600 + half_window) + 1
        if not (sample_index >= first_second_half_sample and sample_index <= rt):
            return None
        time_bin50 = (sample_index - first_second_half_sample) // 50
        rel = khanty_cut_label((50 * time_bin50) / half_window)
        return None if rel is None else (time_bin50, rel)

    if window_key == "linguistic_encoding_3":
        post_index = sample_index - math.floor(rt)
        time_bin50 = post_index // 50
        if post_index >= 1 and 0 <= time_bin50 <= 20:
            return time_bin50, time_bin50 / 20
        return None

    if window_key == "post_onset_1000_2500":
        post_index = sample_index - math.floor(rt)
        post_time_bin50 = post_index // 50
        if post_index >= 1 and 20 <= post_time_bin50 <= 50:
            time_bin50 = post_time_bin50 - 20
            return time_bin50, time_bin50 / 30
        return None

    raise ValueError(f"Unknown window: {window_key}")


def in_full_timecourse(sample_index: int, rt: float) -> bool:
    return 100 <= sample_index <= math.floor(rt) + 2500


def is_blink_sample(sample_time: int, intervals: list[tuple[int, int]], pointer: int) -> tuple[bool, int]:
    while pointer < len(intervals) and intervals[pointer][1] < sample_time:
        pointer += 1
    if pointer < len(intervals):
        start, end = intervals[pointer]
        if start <= sample_time <= end:
            return True, pointer
    return False, pointer


def is_track_loss(x: str, y: str, pupil: str) -> bool:
    return x == "." or y == "." or pupil == "."


def pct(loss: int, denom: int) -> float | None:
    if denom == 0:
        return None
    return 100 * loss / denom


def fmt(value: object) -> object:
    if isinstance(value, float):
        return f"{value:.6f}"
    if value is None:
        return ""
    return value


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: fmt(value) for key, value in row.items()})


def add_counts(counter: Counter[str], is_blink: bool, loss: bool) -> None:
    counter["raw_samples"] += 1
    if is_blink:
        counter["blink_samples_excluded"] += 1
        return
    counter["nonblink_samples"] += 1
    if loss:
        counter["track_loss_samples"] += 1


def analyze(
    asc_dir: Path,
    behavior: dict[tuple[str, str], BehaviorTrial],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    file_counts: dict[str, Counter[str]] = defaultdict(Counter)
    window_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    bin_counts: dict[tuple[str, str, float], Counter[str]] = defaultdict(Counter)
    overall_bin_counts: dict[tuple[str, float], Counter[str]] = defaultdict(Counter)
    file_trial_counts: Counter[str] = Counter()
    file_matched_blocks: Counter[str] = Counter()
    file_included: dict[str, str] = {}

    asc_files = sorted(asc_dir.glob("*.asc"))
    for asc_path in asc_files:
        participant = normalize_participant_id(asc_path.stem)
        file_counts[asc_path.name]["asc_trials"] = 0
        file_included[asc_path.name] = "yes" if participant in INCLUDED_PARTICIPANTS else "no"

        for trial in parse_asc(asc_path):
            file_counts[asc_path.name]["asc_trials"] += 1
            image = trial.vars.get("image", "").strip()
            beh = behavior.get((participant, image))
            if beh is None:
                continue

            file_matched_blocks[asc_path.name] += 1
            file_trial_counts[asc_path.name] += 1
            intervals = sorted(trial.blinks)
            blink_pointer = 0

            for sample_index, (sample_time, x, y, pupil) in enumerate(trial.samples, start=1):
                blink, blink_pointer = is_blink_sample(sample_time, intervals, blink_pointer)
                loss = is_track_loss(x, y, pupil)

                if in_full_timecourse(sample_index, beh.rt):
                    add_counts(file_counts[asc_path.name], blink, loss)

                for window_key, _title, _desc in WINDOWS:
                    bucket = window_bucket(sample_index, beh.rt, window_key)
                    if bucket is None:
                        continue
                    _time_bin50, time_rel = bucket
                    add_counts(window_counts[(asc_path.name, window_key)], blink, loss)
                    add_counts(bin_counts[(asc_path.name, window_key, time_rel)], blink, loss)
                    add_counts(overall_bin_counts[(window_key, time_rel)], blink, loss)

    file_rows: list[dict[str, object]] = []
    for asc_path in asc_files:
        name = asc_path.name
        counts = file_counts[name]
        file_rows.append(
            {
                "asc_file": name,
                "included_participant": file_included.get(name, "no"),
                "asc_trials": counts["asc_trials"],
                "matched_clean_trials": file_trial_counts[name],
                "raw_timecourse_samples": counts["raw_samples"],
                "blink_samples_excluded": counts["blink_samples_excluded"],
                "nonblink_samples": counts["nonblink_samples"],
                "track_loss_samples": counts["track_loss_samples"],
                "track_loss_percent_excluding_blinks": pct(
                    counts["track_loss_samples"], counts["nonblink_samples"]
                ),
            }
        )

    window_rows: list[dict[str, object]] = []
    for asc_path in asc_files:
        for window_key, title, desc in WINDOWS:
            counts = window_counts[(asc_path.name, window_key)]
            window_rows.append(
                {
                    "asc_file": asc_path.name,
                    "included_participant": file_included.get(asc_path.name, "no"),
                    "window_key": window_key,
                    "window": title,
                    "window_description": desc,
                    "matched_clean_trials": file_trial_counts[asc_path.name],
                    "raw_samples": counts["raw_samples"],
                    "blink_samples_excluded": counts["blink_samples_excluded"],
                    "nonblink_samples": counts["nonblink_samples"],
                    "track_loss_samples": counts["track_loss_samples"],
                    "track_loss_percent_excluding_blinks": pct(
                        counts["track_loss_samples"], counts["nonblink_samples"]
                    ),
                }
            )

    bin_rows: list[dict[str, object]] = []
    for (asc_file, window_key, time_rel), counts in sorted(bin_counts.items()):
        bin_rows.append(
            {
                "asc_file": asc_file,
                "included_participant": file_included.get(asc_file, "no"),
                "window_key": window_key,
                "window": WINDOW_TITLE[window_key],
                "time_rel": time_rel,
                "raw_samples": counts["raw_samples"],
                "blink_samples_excluded": counts["blink_samples_excluded"],
                "nonblink_samples": counts["nonblink_samples"],
                "track_loss_samples": counts["track_loss_samples"],
                "track_loss_percent_excluding_blinks": pct(
                    counts["track_loss_samples"], counts["nonblink_samples"]
                ),
            }
        )

    overall_rows: list[dict[str, object]] = []
    for (window_key, time_rel), counts in sorted(overall_bin_counts.items()):
        overall_rows.append(
            {
                "window_key": window_key,
                "window": WINDOW_TITLE[window_key],
                "time_rel": time_rel,
                "raw_samples": counts["raw_samples"],
                "blink_samples_excluded": counts["blink_samples_excluded"],
                "nonblink_samples": counts["nonblink_samples"],
                "track_loss_samples": counts["track_loss_samples"],
                "track_loss_percent_excluding_blinks": pct(
                    counts["track_loss_samples"], counts["nonblink_samples"]
                ),
            }
        )

    return file_rows, window_rows, bin_rows, overall_rows


def color_for_pct(value: float | None, vmax: float) -> str:
    if value is None or vmax <= 0:
        return "#f5f5f5"
    t = max(0.0, min(1.0, value / vmax))
    r = int(255 - 40 * t)
    g = int(245 - 170 * t)
    b = int(235 - 205 * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def write_file_window_heatmap(path: Path, window_rows: list[dict[str, object]]) -> None:
    files = sorted({str(row["asc_file"]) for row in window_rows})
    window_keys = [key for key, _title, _desc in WINDOWS]
    values: dict[tuple[str, str], float | None] = {
        (str(row["asc_file"]), str(row["window_key"])): row["track_loss_percent_excluding_blinks"]
        for row in window_rows
    }
    numeric_values = [value for value in values.values() if isinstance(value, float)]
    vmax = max(numeric_values) if numeric_values else 1

    left = 145
    top = 58
    cell_w = 138
    cell_h = 18
    width = left + cell_w * len(window_keys) + 30
    height = top + cell_h * len(files) + 45
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.small{font-size:11px}.head{font-size:12px;font-weight:700}.title{font-size:18px;font-weight:700}</style>',
        '<text class="title" x="20" y="28">Track loss by ASC file and planning window</text>',
        '<text class="small" x="20" y="45">Percent excludes blink intervals from the denominator.</text>',
    ]
    for col, window_key in enumerate(window_keys):
        x = left + col * cell_w + cell_w / 2
        parts.append(
            f'<text class="head" x="{x:.1f}" y="{top - 8}" text-anchor="middle">{html.escape(WINDOW_TITLE[window_key])}</text>'
        )
    for row_i, asc_file in enumerate(files):
        y = top + row_i * cell_h
        parts.append(f'<text class="small" x="{left - 8}" y="{y + 13}" text-anchor="end">{html.escape(asc_file)}</text>')
        for col, window_key in enumerate(window_keys):
            x = left + col * cell_w
            value = values.get((asc_file, window_key))
            fill = color_for_pct(value, vmax)
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w - 2}" height="{cell_h - 1}" fill="{fill}" stroke="#ddd"/>')
            label = "" if value is None else f"{value:.1f}%"
            parts.append(f'<text class="small" x="{x + cell_w / 2:.1f}" y="{y + 13}" text-anchor="middle">{label}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_overall_timecourse_svg(path: Path, overall_rows: list[dict[str, object]]) -> None:
    by_window: dict[str, list[tuple[float, float]]] = defaultdict(list)
    max_pct = 0.0
    for row in overall_rows:
        value = row["track_loss_percent_excluding_blinks"]
        if not isinstance(value, float):
            continue
        by_window[str(row["window_key"])].append((float(row["time_rel"]), value))
        max_pct = max(max_pct, value)
    y_max = max(1.0, math.ceil(max_pct))

    width = 860
    panel_h = 120
    left = 65
    right = 825
    top0 = 52
    height = top0 + panel_h * len(WINDOWS) + 35

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:18px;font-weight:700}.small{font-size:11px}.panel{font-size:13px;font-weight:700}.axis{stroke:#333}.grid{stroke:#e2e2e2}</style>',
        '<text class="title" x="20" y="28">Overall non-blink track loss over planning time course</text>',
        '<text class="small" x="20" y="45">Aggregated across matched clean trials in all ASC files.</text>',
    ]

    for panel_i, (window_key, title, _desc) in enumerate(WINDOWS):
        top = top0 + panel_i * panel_h
        bottom = top + 85
        points = sorted(by_window.get(window_key, []))

        def sx(x: float) -> float:
            return left + x * (right - left)

        def sy(y: float) -> float:
            return bottom - (y / y_max) * (bottom - top)

        parts.append(f'<text class="panel" x="20" y="{top + 4}">{html.escape(title)}</text>')
        for tick in [0, y_max / 2, y_max]:
            y = sy(tick)
            parts.append(f'<line class="grid" x1="{left}" x2="{right}" y1="{y:.1f}" y2="{y:.1f}"/>')
            parts.append(f'<text class="small" x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">{tick:.1f}%</text>')
        parts.append(f'<line class="axis" x1="{left}" x2="{right}" y1="{bottom}" y2="{bottom}"/>')
        parts.append(f'<line class="axis" x1="{left}" x2="{left}" y1="{top}" y2="{bottom}"/>')
        if points:
            path_d = " ".join(
                ("M" if i == 0 else "L") + f"{sx(x):.1f},{sy(y):.1f}"
                for i, (x, y) in enumerate(points)
            )
            parts.append(f'<path d="{path_d}" fill="none" stroke="#8f2d1f" stroke-width="2.4"/>')
        for x_tick in [0, 0.5, 1]:
            parts.append(f'<text class="small" x="{sx(x_tick):.1f}" y="{bottom + 16}" text-anchor="middle">{x_tick:g}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate non-blink track loss in Koryak ASC files.")
    parser.add_argument("--behavior-csv", default="Koryak stimuli - final.csv")
    parser.add_argument("--asc-dir", default="ASC files")
    parser.add_argument("--output-dir", default="output/track_loss")
    parser.add_argument(
        "--analysis-participants-only",
        action="store_true",
        help="Restrict to the 16 included participants used in the main gaze plots.",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    behavior = load_clean_behavior(Path(args.behavior_csv), args.analysis_participants_only)
    file_rows, window_rows, bin_rows, overall_rows = analyze(Path(args.asc_dir), behavior)

    write_csv(out_dir / "track_loss_by_asc_file.csv", file_rows)
    write_csv(out_dir / "track_loss_by_asc_file_window.csv", window_rows)
    write_csv(out_dir / "track_loss_timecourse_by_asc_file.csv", bin_rows)
    write_csv(out_dir / "track_loss_timecourse_overall.csv", overall_rows)
    write_file_window_heatmap(out_dir / "track_loss_file_window_heatmap.svg", window_rows)
    write_overall_timecourse_svg(out_dir / "track_loss_timecourse_overall.svg", overall_rows)

    print(f"Wrote track-loss outputs to {out_dir}")
    print("Highest per-file non-blink track loss:")
    ranked = sorted(
        [row for row in file_rows if isinstance(row["track_loss_percent_excluding_blinks"], float)],
        key=lambda row: row["track_loss_percent_excluding_blinks"],
        reverse=True,
    )
    for row in ranked[:10]:
        print(
            f"  {row['asc_file']}: {row['track_loss_percent_excluding_blinks']:.2f}% "
            f"({row['track_loss_samples']}/{row['nonblink_samples']} samples, "
            f"{row['matched_clean_trials']} matched trials)"
        )


if __name__ == "__main__":
    main()
