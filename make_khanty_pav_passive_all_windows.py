#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
from collections import defaultdict
from pathlib import Path

from make_khanty_asc_active_passive_planning_graphs import (
    asc_experiment_item,
    classify_aoi,
    load_behavior,
    parse_asc_trials,
    participant_candidates,
)
from svg_to_pdf import convert_svg_to_pdf


AGENT_COLOR = "#CC3311"
PATIENT_COLOR = "#0077BB"

WINDOWS = [
    ("window1", "EEA, 100-600 ms"),
    ("window2", "Linguistic encoding I"),
    ("window3", "Linguistic encoding II"),
    ("window4", "Post-onset, 0-1000 ms"),
]


def parse_float(value: object) -> float | None:
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    if math.isnan(out):
        return None
    return out


def is_one(value: object) -> bool:
    return str(value).strip() in {"1", "1.0"}


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def sd(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((value - m) ** 2 for value in values) / (len(values) - 1))


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


def trial_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        row.get("ppt_id", "").strip(),
        row.get("ppt.no", "").strip(),
        row.get("item", "").strip(),
        row.get("cond", "").strip(),
        row.get("wo", "").strip(),
        row.get("sol", "").strip(),
    )


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


def add_sample(
    counts_by_trial_bin: dict[tuple[tuple[str, str, str, str, str, str], str, float], dict[str, int]],
    row: dict[str, str],
    window_key: str,
    time_rel: float,
) -> None:
    key = (trial_key(row), window_key, round(time_rel, 2))
    counts = counts_by_trial_bin[key]
    counts["samples"] += 1
    if is_one(row.get("agent", "")):
        counts["agent"] += 1
    if is_one(row.get("patient", "")):
        counts["patient"] += 1


def add_classified_sample(
    counts_by_trial_bin: dict[tuple[tuple[str, str, str, str, str, str], str, float], dict[str, int]],
    trial: tuple[str, str, str, str, str, str],
    window_key: str,
    time_rel: float,
    who: str,
) -> None:
    key = (trial, window_key, round(time_rel, 2))
    counts = counts_by_trial_bin[key]
    counts["samples"] += 1
    if who == "agent":
        counts["agent"] += 1
    if who == "patient":
        counts["patient"] += 1


def load_pre_windows(
    pre_csv: Path,
    counts_by_trial_bin: dict[tuple[tuple[str, str, str, str, str, str], str, float], dict[str, int]],
) -> set[tuple[str, str, str, str, str, str]]:
    pav_trials: set[tuple[str, str, str, str, str, str]] = set()

    with pre_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("type", "").strip() != "pass" or row.get("wo", "").strip() != "PAV":
                continue

            sol = parse_float(row.get("sol", ""))
            ms = parse_float(row.get("ms", ""))
            time_bin50 = parse_float(row.get("time_bin50", ""))
            if sol is None or ms is None or time_bin50 is None:
                continue

            pav_trials.add(trial_key(row))
            time_bin50_int = int(time_bin50)

            if 2 <= time_bin50_int <= 12:
                add_sample(counts_by_trial_bin, row, "window1", (time_bin50_int - 2) / 10)

            half_window = 0.5 * (sol - 600)
            if half_window <= 0:
                continue

            tw = str(row.get("tw", "")).strip().strip('"')
            if tw == "2":
                rel = (50 * (time_bin50_int - 12)) / half_window
                label = khanty_cut_label(rel)
                if label is not None:
                    add_sample(counts_by_trial_bin, row, "window2", label)

            if tw == "3":
                adjustment = 601 + half_window if sol % 2 == 0 else 600.5 + half_window
                shifted_ms = ms - adjustment
                time_bin50_new = math.floor(shifted_ms / 50)
                rel = (50 * time_bin50_new) / half_window
                label = khanty_cut_label(rel)
                if label is not None:
                    add_sample(counts_by_trial_bin, row, "window3", label)

    return pav_trials


def load_post_window_from_asc(
    asc_dir: Path,
    behavior_csv: Path,
    counts_by_trial_bin: dict[tuple[tuple[str, str, str, str, str, str], str, float], dict[str, int]],
) -> set[tuple[str, str, str, str, str, str]]:
    behavior_trials = load_behavior(behavior_csv)
    behavior_participants = {participant for participant, _item in behavior_trials}

    pav_trials: set[tuple[str, str, str, str, str, str]] = set()
    for asc_path in sorted(asc_dir.glob("*.asc")):
        asc_stem = asc_path.stem
        participant = next(
            (candidate for candidate in participant_candidates(asc_stem) if candidate in behavior_participants),
            asc_stem,
        )
        for asc_trial in parse_asc_trials(asc_path, max_ms=8000):
            item = asc_experiment_item(asc_trial)
            if item is None:
                continue

            behavior = behavior_trials.get((participant, item))
            if behavior is None or behavior.sentence_type != "pass" or behavior.word_order != "PAV":
                continue

            trial = (
                behavior.participant,
                behavior.participant_no,
                str(behavior.item),
                behavior.condition,
                behavior.word_order,
                fmt_num(behavior.sol).rstrip("0").rstrip("."),
            )
            pav_trials.add(trial)
            for rel_ms, x, y in asc_trial.samples:
                post_ms = rel_ms - behavior.sol
                post_bin = math.floor(post_ms / 50)
                if not (0 <= post_bin <= 20):
                    continue
                who = classify_aoi(x, y, asc_trial.vars.get("agens", ""), asc_trial.vars.get("patiens", ""))
                add_classified_sample(counts_by_trial_bin, trial, "window4", post_bin / 20, who)
    return pav_trials


def make_trial_bin_rows(
    counts_by_trial_bin: dict[tuple[tuple[str, str, str, str, str, str], str, float], dict[str, int]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for (trial, window_key, time_rel), counts in sorted(counts_by_trial_bin.items()):
        n_samples = counts["samples"]
        if n_samples == 0:
            continue
        ppt_id, ppt_no, item, cond, wo, sol = trial
        rows.append(
            {
                "participant": ppt_id,
                "ppt_no": ppt_no,
                "item": item,
                "condition": cond,
                "word_order": wo,
                "speech_onset_ms": float(sol),
                "window_key": window_key,
                "window": dict(WINDOWS)[window_key],
                "time_rel": time_rel,
                "agent_prop": counts["agent"] / n_samples,
                "patient_prop": counts["patient"] / n_samples,
                "n_samples": n_samples,
            }
        )
    return rows


def summarize_plot_rows(trial_bin_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, float], list[float]] = defaultdict(list)
    for row in trial_bin_rows:
        for referent, prop_col in [("agent", "agent_prop"), ("patient", "patient_prop")]:
            grouped[(str(row["window_key"]), referent, float(row["time_rel"]))].append(float(row[prop_col]))

    rows: list[dict[str, object]] = []
    for (window_key, referent, time_rel), values in sorted(grouped.items()):
        prop_mean = mean(values)
        prop_sd = sd(values)
        n_trial_bins = len(values)
        se2 = 2 * prop_sd / math.sqrt(n_trial_bins) if n_trial_bins else 0.0
        rows.append(
            {
                "window_key": window_key,
                "window": dict(WINDOWS)[window_key],
                "referent": referent,
                "time_rel": time_rel,
                "mean_prop": prop_mean,
                "sd_prop": prop_sd,
                "n_trial_bins": n_trial_bins,
                "lower": max(0.0, prop_mean - se2),
                "upper": min(1.0, prop_mean + se2),
            }
        )
    return rows


def svg_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    return " ".join(
        ("M" if index == 0 else "L") + f"{x:.2f},{y:.2f}"
        for index, (x, y) in enumerate(points)
    )


def render_panel_svg(
    path: Path,
    plot_rows: list[dict[str, object]],
    trial_bin_rows: list[dict[str, object]],
    n_trials: int,
) -> None:
    panel_width = 350
    panel_height = 330
    left_margin = 58
    right_margin = 18
    top_margin = 42
    bottom_margin = 58
    gap = 26
    width = panel_width * 4 + gap * 3 + 70
    height = 470
    y_min = 0.0
    y_max = 1.0

    def panel_origin(index: int) -> tuple[int, int]:
        return 58 + index * (panel_width + gap), 72

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>',
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".title { font-size: 21px; font-weight: 700; }",
        ".subtitle { font-size: 13px; fill: #555; }",
        ".panel-title { font-size: 13px; font-weight: 700; }",
        ".axis { stroke: #222; stroke-width: 1; }",
        ".grid { stroke: #dddddd; stroke-width: 1; }",
        ".tick { font-size: 10px; fill: #333; }",
        ".label { font-size: 13px; fill: #222; }",
        ".legend { font-size: 13px; fill: #222; }",
        "</style>",
        f'<text class="title" x="{width / 2:.1f}" y="28" text-anchor="middle">PAV Passive Sentences Across Four Time Windows</text>',
        f'<text class="subtitle" x="{width / 2:.1f}" y="49" text-anchor="middle">Khanty; n = {n_trials} PAV passive trials; 50-ms bins, normalized within each window</text>',
    ]

    trial_counts = {
        window_key: len(
            {
                (str(row["participant"]), str(row["item"]), str(row["speech_onset_ms"]))
                for row in trial_bin_rows
                if row["window_key"] == window_key
            }
        )
        for window_key, _title in WINDOWS
    }

    for index, (window_key, window_title) in enumerate(WINDOWS):
        x0, y0 = panel_origin(index)
        plot_left = x0 + left_margin
        plot_right = x0 + panel_width - right_margin
        plot_top = y0 + top_margin
        plot_bottom = y0 + panel_height - bottom_margin

        def sx(x: float) -> float:
            return plot_left + x * (plot_right - plot_left)

        def sy(y: float) -> float:
            return plot_bottom - (y - y_min) / (y_max - y_min) * (plot_bottom - plot_top)

        parts.append(
            f'<text class="panel-title" x="{(plot_left + plot_right) / 2:.1f}" y="{y0 + 18}" text-anchor="middle">'
            f'{html.escape(window_title)} (n={trial_counts[window_key]})</text>'
        )

        for y_tick in [0.0, 0.25, 0.5, 0.75, 1.0]:
            y = sy(y_tick)
            parts.append(f'<line class="grid" x1="{plot_left}" x2="{plot_right}" y1="{y:.2f}" y2="{y:.2f}"/>')
            if index == 0:
                parts.append(f'<text class="tick" x="{plot_left - 8}" y="{y + 3:.2f}" text-anchor="end">{y_tick:.2g}</text>')

        for x_tick in [0.0, 0.5, 1.0]:
            x = sx(x_tick)
            parts.append(f'<line class="grid" x1="{x:.2f}" x2="{x:.2f}" y1="{plot_top}" y2="{plot_bottom}"/>')
            parts.append(f'<text class="tick" x="{x:.2f}" y="{plot_bottom + 18}" text-anchor="middle">{x_tick:.1f}</text>')

        parts.extend(
            [
                f'<line class="axis" x1="{plot_left}" x2="{plot_right}" y1="{plot_bottom}" y2="{plot_bottom}"/>',
                f'<line class="axis" x1="{plot_left}" x2="{plot_left}" y1="{plot_top}" y2="{plot_bottom}"/>',
            ]
        )

        window_rows = [row for row in plot_rows if row["window_key"] == window_key]
        by_ref: dict[str, list[dict[str, object]]] = {"agent": [], "patient": []}
        for row in window_rows:
            by_ref[str(row["referent"])].append(row)
        for referent_rows in by_ref.values():
            referent_rows.sort(key=lambda row: float(row["time_rel"]))

        for referent, color in [("agent", AGENT_COLOR), ("patient", PATIENT_COLOR)]:
            referent_rows = by_ref[referent]
            upper = [(sx(float(row["time_rel"])), sy(float(row["upper"]))) for row in referent_rows]
            lower = [(sx(float(row["time_rel"])), sy(float(row["lower"]))) for row in reversed(referent_rows)]
            polygon_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in upper + lower)
            line_points = [(sx(float(row["time_rel"])), sy(float(row["mean_prop"]))) for row in referent_rows]
            if polygon_points:
                parts.append(f'<polygon points="{polygon_points}" fill="{color}" opacity="0.12"/>')
            parts.append(
                f'<path d="{svg_path(line_points)}" fill="none" stroke="{color}" '
                'stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>'
            )

    axis_label_y = height - 36
    parts.extend(
        [
            f'<text class="label" x="{width / 2:.1f}" y="{axis_label_y}" text-anchor="middle">Relative Time Within Window</text>',
            f'<text class="label" x="20" y="{height / 2:.1f}" text-anchor="middle" transform="rotate(-90 20 {height / 2:.1f})">Proportion of Looks</text>',
        ]
    )

    legend_x = width / 2 - 90
    legend_y = height - 14
    parts.extend(
        [
            f'<line x1="{legend_x:.1f}" x2="{legend_x + 28:.1f}" y1="{legend_y:.1f}" y2="{legend_y:.1f}" stroke="{AGENT_COLOR}" stroke-width="3"/>',
            f'<text class="legend" x="{legend_x + 38:.1f}" y="{legend_y + 4:.1f}">Agent</text>',
            f'<line x1="{legend_x + 112:.1f}" x2="{legend_x + 140:.1f}" y1="{legend_y:.1f}" y2="{legend_y:.1f}" stroke="{PATIENT_COLOR}" stroke-width="3"/>',
            f'<text class="legend" x="{legend_x + 150:.1f}" y="{legend_y + 4:.1f}">Patient</text>',
            "</svg>",
        ]
    )

    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a four-window Khanty PAV-passive speech-planning panel."
    )
    parser.add_argument("--pre-csv", default="osfstorage-archive/data_all.csv")
    parser.add_argument("--behavior-csv", default="osfstorage-archive/for_r_1.csv")
    parser.add_argument("--asc-dir", default="osfstorage-archive/ascs")
    parser.add_argument("--output-dir", default="output/khanty_pav_passive_all_windows")
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    counts_by_trial_bin: dict[tuple[tuple[str, str, str, str, str, str], str, float], dict[str, int]] = defaultdict(
        lambda: {"samples": 0, "agent": 0, "patient": 0}
    )
    pre_trials = load_pre_windows(Path(args.pre_csv), counts_by_trial_bin)
    post_trials = load_post_window_from_asc(Path(args.asc_dir), Path(args.behavior_csv), counts_by_trial_bin)
    pav_trials = {
        (trial[0], trial[2], trial[3], trial[4], trial[5])
        for trial in (pre_trials | post_trials)
    }

    trial_bin_rows = make_trial_bin_rows(counts_by_trial_bin)
    plot_rows = summarize_plot_rows(trial_bin_rows)

    write_pretty_csv(output_dir / "khanty_pav_passives_all_windows_trial_bins.csv", trial_bin_rows)
    write_pretty_csv(output_dir / "khanty_pav_passives_all_windows_plot_data.csv", plot_rows)

    summary_rows = []
    for window_key, window_title in WINDOWS:
        summary_rows.append(
            {
                "window_key": window_key,
                "window": window_title,
                "n_trials": len(
                    {
                        (str(row["participant"]), str(row["item"]), str(row["speech_onset_ms"]))
                        for row in trial_bin_rows
                        if row["window_key"] == window_key
                    }
                ),
                "n_trial_bins": sum(1 for row in trial_bin_rows if row["window_key"] == window_key),
            }
        )
    write_pretty_csv(output_dir / "khanty_pav_passives_all_windows_summary.csv", summary_rows)

    svg_path_out = output_dir / "khanty_pav_passives_all_windows.svg"
    render_panel_svg(svg_path_out, plot_rows, trial_bin_rows, n_trials=len(pav_trials))
    if not args.no_pdf:
        convert_svg_to_pdf(svg_path_out)

    print(f"PAV passive trials: {len(pav_trials)}")
    for row in summary_rows:
        print(f"{row['window_key']}: trials={row['n_trials']}, trial_bins={row['n_trial_bins']}")
    print(f"Wrote panel to {svg_path_out}")


if __name__ == "__main__":
    main()
