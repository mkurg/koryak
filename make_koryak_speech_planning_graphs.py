#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


AGENT_COLOR = "#CC3311"
PATIENT_COLOR = "#0077BB"

DEFAULT_INCLUDED_PARTICIPANTS = {
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

SAMPLE_RE = re.compile(r"^\s*(\d+)\s+([-\d.]+|\.)\s+([-\d.]+|\.)\s+([-\d.]+|\.)")
TRIAL_VAR_RE = re.compile(r"!V\s+TRIAL_VAR\s+(\S+)\s*(.*)$")

WINDOWS = [
    ("speech_planning", "Early event apprehension"),
    ("linguistic_encoding_1", "Linguistic encoding I"),
    ("linguistic_encoding_2", "Linguistic encoding II"),
    ("linguistic_encoding_3", "Linguistic encoding III"),
    ("post_onset_1000_2500", "1000-2500 ms after speech onset"),
]
WINDOW_TITLE_BY_KEY = dict(WINDOWS)


@dataclass(frozen=True)
class BehaviorTrial:
    participant: str
    image: str
    sentence_type: str
    patient_animacy: str
    agent_num: int
    patient_num: int
    condition_key: str
    condition_label: str
    filename_suffix: str
    rt: float


@dataclass
class AscTrial:
    block: int
    display_time: int | None = None
    vars: dict[str, str] | None = None
    samples: list[tuple[int, float | None, float | None]] | None = None

    def __post_init__(self) -> None:
        if self.vars is None:
            self.vars = {}
        if self.samples is None:
            self.samples = []


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
    if math.isnan(out):
        return None
    return out


def parse_sample_float(value: str) -> float | None:
    if value == ".":
        return None
    return parse_float(value)


def parse_coord_pair(value: object) -> tuple[float | None, float | None]:
    nums = re.findall(r"-?\d+(?:\.\d+)?", str(value))
    if len(nums) < 2:
        return None, None
    return float(nums[0]), float(nums[1])


def animacy_label(value: object) -> str | None:
    text = str(value).strip().lower()
    if text in {"1", "animate"}:
        return "animate"
    if text in {"0", "inanimate"}:
        return "inanimate"
    return None


def parse_int(value: object) -> int | None:
    number = parse_float(value)
    if number is None:
        return None
    return int(number)


def behavior_condition(
    sentence_type: str,
    patient_animacy: str,
    agent_num: int,
    patient_num: int,
    grouping: str,
) -> tuple[str, str, str] | None:
    if grouping == "animacy":
        return (
            patient_animacy,
            f"{patient_animacy} patient",
            f"{patient_animacy}_patient",
        )

    if grouping not in {"number", "number_animacy"}:
        raise ValueError("grouping must be 'animacy', 'number', or 'number_animacy'.")

    requested = {
        ("direct", 1, 1): ("direct_1_agent_1_patient", "1 agent, 1 patient", "1_agent_1_patient"),
        ("direct", 1, 2): ("direct_1_agent_2_patients", "1 agent, 2 patients", "1_agent_2_patients"),
        ("inverse", 2, 1): ("inverse_2_agents_1_patient", "2 agents, 1 patient", "2_agents_1_patient"),
        ("inverse", 2, 2): ("inverse_2_agents_2_patients", "2 agents, 2 patients", "2_agents_2_patients"),
    }
    condition = requested.get((sentence_type, agent_num, patient_num))
    if condition is None or grouping == "number":
        return condition

    condition_key, condition_label, filename_suffix = condition
    return (
        f"{condition_key}_{patient_animacy}_patient",
        f"{condition_label}, {patient_animacy} patient",
        f"{filename_suffix}_{patient_animacy}_patient",
    )


def load_clean_behavior(
    behavior_csv: Path,
    include_all_participants: bool,
    grouping: str,
) -> dict[tuple[str, str], BehaviorTrial]:
    trials: dict[tuple[str, str], BehaviorTrial] = {}

    with behavior_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            participant = normalize_participant_id(row.get("participant's id", ""))
            if not include_all_participants and participant not in DEFAULT_INCLUDED_PARTICIPANTS:
                continue

            rt = parse_float(row.get("reaction time", ""))
            sentence_type = str(row.get("sentence type", "")).strip().lower()
            word_order = str(row.get("word order", "")).strip()
            fluency = str(row.get("fluency", "")).strip().lower()
            patient_animacy = animacy_label(row.get("patiens_animacy", ""))
            agent_num = parse_int(row.get("agens_num", ""))
            patient_num = parse_int(row.get("patiens_num", ""))
            image = str(row.get("image", "")).strip()

            if (
                rt is None
                or rt >= 6000
                or fluency != "yes"
                or word_order != "AVP"
                or sentence_type not in {"direct", "inverse"}
                or patient_animacy is None
                or agent_num is None
                or patient_num is None
                or not image
            ):
                continue

            condition = behavior_condition(sentence_type, patient_animacy, agent_num, patient_num, grouping)
            if condition is None:
                continue
            condition_key, condition_label, filename_suffix = condition

            trials[(participant, image)] = BehaviorTrial(
                participant=participant,
                image=image,
                sentence_type=sentence_type,
                patient_animacy=patient_animacy,
                agent_num=agent_num,
                patient_num=patient_num,
                condition_key=condition_key,
                condition_label=condition_label,
                filename_suffix=filename_suffix,
                rt=rt,
            )

    return trials


def parse_asc_planning_samples(asc_path: Path, max_samples_after_display: int = 9000) -> list[AscTrial]:
    trials: list[AscTrial] = []
    current: AscTrial | None = None

    with asc_path.open("r", encoding="utf-8", errors="replace") as f:
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
                        key = var_match.group(1)
                        value = var_match.group(2).strip()
                        current.vars[key] = value
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
                    parse_sample_float(sample_match.group(2)),
                    parse_sample_float(sample_match.group(3)),
                )
            )

    return trials


def classify_aoi(
    x: float | None,
    y: float | None,
    agent_coord: object,
    patient_coord: object,
    width: float,
    height: float,
) -> str:
    if x is None or y is None:
        return "other"

    ax, ay = parse_coord_pair(agent_coord)
    px, py = parse_coord_pair(patient_coord)

    in_agent = ax is not None and ay is not None and ax <= x <= ax + width and ay <= y <= ay + height
    in_patient = px is not None and py is not None and px <= x <= px + width and py <= y <= py + height

    if in_agent and not in_patient:
        return "agent"
    if in_patient and not in_agent:
        return "patient"
    return "other"


def khanty_cut_label(value: float) -> float | None:
    """
    Match R's cut(..., breaks = seq(-.05, 1, .05), labels = seq(0, 1, .05)).
    """
    if value < -0.05 or value > 1:
        return None
    label_index = math.ceil((value / 0.05) - 1e-12)
    if label_index < 0 or label_index > 20:
        return None
    return round(label_index * 0.05, 2)


def window_bucket(sample_index: int, rt: float, window_key: str) -> tuple[int, float] | None:
    """
    Return the physical/normalized 50 ms bin and the plotted relative-time value.

    sample_index follows the Khanty R scripts: row_number() inside the trial
    window, starting at 1 for the first sample at DISPLAY_SENTENCE.
    """
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
            if rel is None:
                return None
            return time_bin50, rel

        first_second_half_sample = math.floor(600 + half_window) + 1
        if not (sample_index >= first_second_half_sample and sample_index <= rt):
            return None
        time_bin50 = (sample_index - first_second_half_sample) // 50
        rel = khanty_cut_label((50 * time_bin50) / half_window)
        if rel is None:
            return None
        return time_bin50, rel

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


def accumulate_trial_bins(
    asc_dir: Path,
    behavior_trials: dict[tuple[str, str], BehaviorTrial],
    aoi_width: float,
    aoi_height: float,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    candidate_rows_by_trial: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    merge_rows: list[dict[str, object]] = []

    for file_index, asc_path in enumerate(sorted(asc_dir.glob("*.asc"))):
        participant = normalize_participant_id(asc_path.stem)
        parsed_trials = parse_asc_planning_samples(asc_path)
        clean_trials = 0
        clean_candidate_bins = 0

        for block_index, asc_trial in enumerate(parsed_trials):
            image = asc_trial.vars.get("image", "").strip()
            behavior = behavior_trials.get((participant, image))
            if behavior is None:
                continue

            clean_trials += 1
            per_bin: dict[tuple[str, int, float], Counter[str]] = defaultdict(Counter)

            for index, (_sample_time, x, y) in enumerate(asc_trial.samples, start=1):
                who = classify_aoi(
                    x,
                    y,
                    asc_trial.vars.get("agens", ""),
                    asc_trial.vars.get("patiens", ""),
                    aoi_width,
                    aoi_height,
                )
                for window_key, _window_title in WINDOWS:
                    bucket = window_bucket(index, behavior.rt, window_key)
                    if bucket is None:
                        continue
                    time_bin50, time_rel = bucket
                    per_bin[(window_key, time_bin50, time_rel)][who] += 1
                    per_bin[(window_key, time_bin50, time_rel)]["all"] += 1

            candidate_rows: list[dict[str, object]] = []
            for (window_key, time_bin50, time_rel), counts in sorted(per_bin.items()):
                if counts["all"] == 0:
                    continue

                n = counts["all"]
                candidate_rows.append(
                    {
                        "window_key": window_key,
                        "window": WINDOW_TITLE_BY_KEY[window_key],
                        "participant": participant,
                        "asc_file": asc_path.name,
                        "block": asc_trial.block,
                        "image": image,
                        "sentence_type": behavior.sentence_type,
                        "patient_animacy": behavior.patient_animacy,
                        "agent_num": behavior.agent_num,
                        "patient_num": behavior.patient_num,
                        "condition_key": behavior.condition_key,
                        "condition": behavior.condition_label,
                        "filename_suffix": behavior.filename_suffix,
                        "rt": behavior.rt,
                        "time_bin50": time_bin50,
                        "time_rel": time_rel,
                        "agent_prop": counts["agent"] / n,
                        "patient_prop": counts["patient"] / n,
                        "n_samples": n,
                    }
                )

            if candidate_rows:
                clean_candidate_bins += len(candidate_rows)
                candidate_rows_by_trial[(participant, image)].append(
                    {
                        "file_index": file_index,
                        "block_index": block_index,
                        "asc_file": asc_path.name,
                        "block": asc_trial.block,
                        "n_bins": len(candidate_rows),
                        "n_samples": sum(int(row["n_samples"]) for row in candidate_rows),
                        "rows": candidate_rows,
                    }
                )

        merge_rows.append(
            {
                "asc_file": asc_path.name,
                "participant": participant,
                "asc_trials": len(parsed_trials),
                "clean_merged_trials": clean_trials,
                "clean_candidate_bins": clean_candidate_bins,
            }
        )

    trial_bin_rows: list[dict[str, object]] = []
    duplicate_rows: list[dict[str, object]] = []

    for (participant, image), candidates in sorted(candidate_rows_by_trial.items()):
        chosen = max(
            candidates,
            key=lambda candidate: (
                int(candidate["n_bins"]),
                int(candidate["n_samples"]),
                int(candidate["file_index"]),
                int(candidate["block_index"]),
            ),
        )
        trial_bin_rows.extend(chosen["rows"])

        if len(candidates) > 1:
            duplicate_rows.append(
                {
                    "participant": participant,
                    "image": image,
                    "n_candidates": len(candidates),
                    "chosen_asc_file": chosen["asc_file"],
                    "chosen_block": chosen["block"],
                    "candidate_asc_files": "; ".join(str(candidate["asc_file"]) for candidate in candidates),
                    "candidate_blocks": "; ".join(str(candidate["block"]) for candidate in candidates),
                }
            )

    return trial_bin_rows, merge_rows, duplicate_rows


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def sd(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((value - m) ** 2 for value in values) / (len(values) - 1))


def summarize_plot_rows(trial_bin_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str, str, str, str, str, str, str, float], list[float]] = defaultdict(list)

    for row in trial_bin_rows:
        for referent, prop_col in [("agent", "agent_prop"), ("patient", "patient_prop")]:
            grouped[
                (
                    str(row["window_key"]),
                    str(row["window"]),
                    str(row["sentence_type"]),
                    str(row["condition_key"]),
                    str(row["condition"]),
                    str(row["filename_suffix"]),
                    str(row["agent_num"]),
                    str(row["patient_num"]),
                    str(row["patient_animacy"]),
                    referent,
                    float(row["time_rel"]),
                )
            ].append(float(row[prop_col]))

    summary_rows: list[dict[str, object]] = []
    for (
        window_key,
        window,
        sentence_type,
        condition_key,
        condition,
        filename_suffix,
        agent_num,
        patient_num,
        patient_animacy,
        referent,
        time_rel,
    ), values in sorted(grouped.items()):
        prop_mean = mean(values)
        prop_sd = sd(values)
        n_bins = len(values)
        se2 = 2 * prop_sd / math.sqrt(n_bins) if n_bins else 0.0
        summary_rows.append(
            {
                "window_key": window_key,
                "window": window,
                "sentence_type": sentence_type,
                "condition_key": condition_key,
                "condition": condition,
                "filename_suffix": filename_suffix,
                "agent_num": agent_num,
                "patient_num": patient_num,
                "patient_animacy": patient_animacy,
                "referent": referent,
                "time_rel": time_rel,
                "mean_prop": prop_mean,
                "sd_prop": prop_sd,
                "n_bins": n_bins,
                "lower": max(0.0, prop_mean - se2),
                "upper": min(1.0, prop_mean + se2),
            }
        )

    return summary_rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def fmt_num(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def write_pretty_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: fmt_num(value) for key, value in row.items()})


def svg_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    return " ".join(
        ("M" if index == 0 else "L") + f"{x:.2f},{y:.2f}"
        for index, (x, y) in enumerate(points)
    )


def render_graph_svg(
    path: Path,
    rows: list[dict[str, object]],
    window_title: str,
    sentence_type: str,
    condition_label: str,
    trial_count: int,
) -> None:
    width = 820
    height = 560
    left = 82
    right = 760
    top = 58
    bottom = 470
    y_min = 0.0
    y_max = 1.0

    def sx(x: float) -> float:
        return left + x * (right - left)

    def sy(y: float) -> float:
        return bottom - (y - y_min) / (y_max - y_min) * (bottom - top)

    by_ref: dict[str, list[dict[str, object]]] = {"agent": [], "patient": []}
    for row in rows:
        by_ref[str(row["referent"])].append(row)

    for referent_rows in by_ref.values():
        referent_rows.sort(key=lambda item: float(item["time_rel"]))

    title_type = sentence_type.capitalize()
    title = f"{title_type} AVP, {condition_label}"
    subtitle = f"{window_title}, RT < 6000 ms, fluent trials; n = {trial_count} trials"

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>',
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".title { font-size: 20px; font-weight: 700; }",
        ".subtitle { font-size: 13px; fill: #555; }",
        ".axis { stroke: #222; stroke-width: 1; }",
        ".grid { stroke: #dddddd; stroke-width: 1; }",
        ".tick { font-size: 12px; fill: #333; }",
        ".label { font-size: 14px; fill: #222; }",
        ".legend { font-size: 13px; fill: #222; }",
        "</style>",
        f'<text class="title" x="{(left + right) / 2:.1f}" y="28" text-anchor="middle">{html.escape(title)}</text>',
        f'<text class="subtitle" x="{(left + right) / 2:.1f}" y="47" text-anchor="middle">{html.escape(subtitle)}</text>',
    ]

    for y_tick in [i / 10 for i in range(0, 11)]:
        y = sy(y_tick)
        parts.append(f'<line class="grid" x1="{left}" x2="{right}" y1="{y:.2f}" y2="{y:.2f}"/>')
        parts.append(f'<text class="tick" x="{left - 10}" y="{y + 4:.2f}" text-anchor="end">{y_tick:.1f}</text>')

    for x_tick in [i / 10 for i in range(0, 11)]:
        x = sx(x_tick)
        parts.append(f'<line class="grid" x1="{x:.2f}" x2="{x:.2f}" y1="{top}" y2="{bottom}"/>')
        parts.append(f'<text class="tick" x="{x:.2f}" y="{bottom + 22}" text-anchor="middle">{x_tick:.1f}</text>')

    parts.extend(
        [
            f'<line class="axis" x1="{left}" x2="{right}" y1="{bottom}" y2="{bottom}"/>',
            f'<line class="axis" x1="{left}" x2="{left}" y1="{top}" y2="{bottom}"/>',
            f'<text class="label" x="{(left + right) / 2:.1f}" y="{height - 28}" text-anchor="middle">Relative Time</text>',
            f'<text class="label" x="20" y="{(top + bottom) / 2:.1f}" text-anchor="middle" transform="rotate(-90 20 {(top + bottom) / 2:.1f})">Proportion of Looks</text>',
        ]
    )

    for referent, color in [("agent", AGENT_COLOR), ("patient", PATIENT_COLOR)]:
        referent_rows = by_ref[referent]
        upper = [(sx(float(row["time_rel"])), sy(float(row["upper"]))) for row in referent_rows]
        lower = [(sx(float(row["time_rel"])), sy(float(row["lower"]))) for row in reversed(referent_rows)]
        polygon_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in upper + lower)
        line_points = [(sx(float(row["time_rel"])), sy(float(row["mean_prop"]))) for row in referent_rows]
        parts.append(f'<polygon points="{polygon_points}" fill="{color}" opacity="0.12"/>')
        parts.append(f'<path d="{svg_path(line_points)}" fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>')

    legend_x = right - 155
    legend_y = top + 18
    parts.extend(
        [
            f'<line x1="{legend_x}" x2="{legend_x + 28}" y1="{legend_y}" y2="{legend_y}" stroke="{AGENT_COLOR}" stroke-width="3"/>',
            f'<text class="legend" x="{legend_x + 38}" y="{legend_y + 4}">Agent</text>',
            f'<line x1="{legend_x}" x2="{legend_x + 28}" y1="{legend_y + 22}" y2="{legend_y + 22}" stroke="{PATIENT_COLOR}" stroke-width="3"/>',
            f'<text class="legend" x="{legend_x + 38}" y="{legend_y + 26}">Patient</text>',
            "</svg>",
        ]
    )

    path.write_text("\n".join(parts), encoding="utf-8")


def write_graphs(
    output_dir: Path,
    summary_rows: list[dict[str, object]],
    trial_bin_rows: list[dict[str, object]],
) -> list[Path]:
    written: list[Path] = []
    trial_counts = Counter(
        (
            str(row["window_key"]),
            str(row["sentence_type"]),
            str(row["condition_key"]),
            str(row["participant"]),
            str(row["image"]),
        )
        for row in trial_bin_rows
    )
    by_condition_trials = Counter((key[0], key[1], key[2]) for key in trial_counts)

    conditions = sorted(
        {
            (
                str(row["sentence_type"]),
                str(row["condition_key"]),
                str(row["condition"]),
                str(row["filename_suffix"]),
            )
            for row in summary_rows
        }
    )

    for window_key, window_title in WINDOWS:
        for sentence_type in ["direct", "inverse"]:
            for cond_sentence_type, condition_key, condition_label, filename_suffix in conditions:
                if cond_sentence_type != sentence_type:
                    continue
                rows = [
                    row
                    for row in summary_rows
                    if row["window_key"] == window_key
                    and row["sentence_type"] == sentence_type
                    and row["condition_key"] == condition_key
                ]
                if not rows:
                    continue

                filename = f"{window_key}_{sentence_type}_AVP_{filename_suffix}.svg"
                out_path = output_dir / filename
                render_graph_svg(
                    out_path,
                    rows,
                    window_title=window_title,
                    sentence_type=sentence_type,
                    condition_label=condition_label,
                    trial_count=by_condition_trials[(window_key, sentence_type, condition_key)],
                )
                written.append(out_path)

    return written


def write_condition_counts(
    path: Path,
    behavior_trials: dict[tuple[str, str], BehaviorTrial],
    trial_bin_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    behavior_counts = Counter((trial.sentence_type, trial.condition_key) for trial in behavior_trials.values())
    plotted_trials = {
        (
            str(row["window_key"]),
            str(row["sentence_type"]),
            str(row["condition_key"]),
            str(row["participant"]),
            str(row["image"]),
        )
        for row in trial_bin_rows
    }
    plotted_counts = Counter((key[0], key[1], key[2]) for key in plotted_trials)
    plotted_bins = Counter(
        (str(row["window_key"]), str(row["sentence_type"]), str(row["condition_key"]))
        for row in trial_bin_rows
    )
    condition_meta: dict[tuple[str, str], dict[str, object]] = {}
    for trial in behavior_trials.values():
        key = (trial.sentence_type, trial.condition_key)
        if key not in condition_meta:
            condition_meta[key] = {
                "condition": trial.condition_label,
                "agent_num": trial.agent_num,
                "patient_num": trial.patient_num,
                "patient_animacy": trial.patient_animacy,
            }
            continue
        if (
            condition_meta[key]["agent_num"] != trial.agent_num
            or condition_meta[key]["patient_num"] != trial.patient_num
        ):
            condition_meta[key]["agent_num"] = "mixed"
            condition_meta[key]["patient_num"] = "mixed"
        if condition_meta[key]["patient_animacy"] != trial.patient_animacy:
            condition_meta[key]["patient_animacy"] = "mixed"
    conditions = sorted(
        (
            sentence_type,
            condition_key,
            str(meta["condition"]),
            meta["agent_num"],
            meta["patient_num"],
            meta["patient_animacy"],
        )
        for (sentence_type, condition_key), meta in condition_meta.items()
    )

    rows: list[dict[str, object]] = []
    for window_key, window_title in WINDOWS:
        for sentence_type in ["direct", "inverse"]:
            for cond_sentence_type, condition_key, condition_label, agent_num, patient_num, patient_animacy in conditions:
                if cond_sentence_type != sentence_type:
                    continue
                rows.append(
                    {
                        "window_key": window_key,
                        "window": window_title,
                        "sentence_type": sentence_type,
                        "condition_key": condition_key,
                        "condition": condition_label,
                        "agent_num": agent_num,
                        "patient_num": patient_num,
                        "patient_animacy": patient_animacy,
                        "clean_behavior_trials": behavior_counts[(sentence_type, condition_key)],
                        "plotted_trials": plotted_counts[(window_key, sentence_type, condition_key)],
                        "plotted_50ms_bins": plotted_bins[(window_key, sentence_type, condition_key)],
                    }
                )

    write_csv(path, rows)
    return rows


def write_missing_trials(
    path: Path,
    behavior_trials: dict[tuple[str, str], BehaviorTrial],
    trial_bin_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    plotted_keys = {(str(row["window_key"]), str(row["participant"]), str(row["image"])) for row in trial_bin_rows}
    missing_rows: list[dict[str, object]] = []

    for window_key, window_title in WINDOWS:
        for key, trial in sorted(behavior_trials.items()):
            if (window_key, key[0], key[1]) in plotted_keys:
                continue
            missing_rows.append(
                {
                    "window_key": window_key,
                    "window": window_title,
                    "participant": trial.participant,
                    "image": trial.image,
                    "sentence_type": trial.sentence_type,
                    "condition_key": trial.condition_key,
                    "condition": trial.condition_label,
                    "agent_num": trial.agent_num,
                    "patient_num": trial.patient_num,
                    "patient_animacy": trial.patient_animacy,
                    "rt": trial.rt,
                }
            )

    write_pretty_csv(path, missing_rows)
    return missing_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Khanty-style Koryak speech-planning eye-movement graphs."
    )
    parser.add_argument("--behavior-csv", default="Koryak stimuli - final.csv")
    parser.add_argument("--asc-dir", default="ASC files")
    parser.add_argument("--output-dir", default="output/koryak_speech_planning_graphs")
    parser.add_argument("--aoi-width", type=float, default=850)
    parser.add_argument("--aoi-height", type=float, default=850)
    parser.add_argument(
        "--grouping",
        choices=["animacy", "number", "number_animacy"],
        default="animacy",
        help="Split graphs by patient animacy, by agent/patient number, or by number crossed with patient animacy.",
    )
    parser.add_argument(
        "--include-all-participants",
        action="store_true",
        help="Use every participant instead of the 16-participant clean set in the Koryak codebase.",
    )
    args = parser.parse_args()

    behavior_csv = Path(args.behavior_csv)
    asc_dir = Path(args.asc_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    behavior_trials = load_clean_behavior(
        behavior_csv=behavior_csv,
        include_all_participants=args.include_all_participants,
        grouping=args.grouping,
    )
    trial_bin_rows, merge_rows, duplicate_rows = accumulate_trial_bins(
        asc_dir=asc_dir,
        behavior_trials=behavior_trials,
        aoi_width=args.aoi_width,
        aoi_height=args.aoi_height,
    )
    summary_rows = summarize_plot_rows(trial_bin_rows)

    write_pretty_csv(output_dir / "speech_planning_trial_bins.csv", trial_bin_rows)
    write_pretty_csv(output_dir / "speech_planning_plot_data.csv", summary_rows)
    write_csv(output_dir / "speech_planning_merge_notes.csv", merge_rows)
    write_csv(output_dir / "speech_planning_duplicate_trials.csv", duplicate_rows)
    condition_count_rows = write_condition_counts(
        output_dir / "speech_planning_condition_counts.csv",
        behavior_trials,
        trial_bin_rows,
    )
    missing_rows = write_missing_trials(
        output_dir / "speech_planning_missing_trials.csv",
        behavior_trials,
        trial_bin_rows,
    )
    graph_paths = write_graphs(output_dir, summary_rows, trial_bin_rows)

    print(f"Clean behavior trials: {len(behavior_trials)}")
    for row in condition_count_rows:
        print(
            f"  {row['window_key']:22s} {row['sentence_type']:7s} {row['condition']:20s}: "
            f"behavior={row['clean_behavior_trials']}, plotted={row['plotted_trials']}"
        )
    print(f"Duplicate usable ASC trials resolved: {len(duplicate_rows)}")
    print(f"Clean behavior trials without usable ASC planning samples: {len(missing_rows)}")
    print(f"Wrote {len(graph_paths)} graphs to {output_dir}")


if __name__ == "__main__":
    main()
