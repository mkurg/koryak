#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
from collections import Counter, defaultdict
from pathlib import Path

from svg_to_pdf import convert_svg_to_pdf


AGENT_COLOR = "#CC3311"
PATIENT_COLOR = "#0077BB"

PAGE_WIDTH = 3200
PAGE_HEIGHT = 760

WINDOWS = [
    ("speech_planning", "Early event apprehension"),
    ("linguistic_encoding_1", "Linguistic encoding I"),
    ("linguistic_encoding_2", "Linguistic encoding II"),
    ("linguistic_encoding_3", "Linguistic encoding III"),
    ("post_onset_1000_2500", "1000-2500 ms after speech onset"),
]


def parse_float(value: object) -> float:
    return float(str(value).strip())


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def sd(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    center = mean(values)
    return math.sqrt(sum((value - center) ** 2 for value in values) / (len(values) - 1))


def fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def svg_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    return " ".join(
        ("M" if index == 0 else "L") + f"{x:.2f},{y:.2f}"
        for index, (x, y) in enumerate(points)
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: fmt(value) for key, value in row.items()})


def load_behavior_counts(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in read_csv(path):
        out[row["sentence_type"]] = int(float(row["n"]))
    return out


def summarize_bins(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, float], list[float]] = defaultdict(list)
    for row in rows:
        for referent, prop_col in [("agent", "agent_prop"), ("patient", "patient_prop")]:
            grouped[
                (
                    row["sentence_type"],
                    row["window_key"],
                    referent,
                    parse_float(row["time_rel"]),
                )
            ].append(parse_float(row[prop_col]))

    out: list[dict[str, object]] = []
    window_labels = dict(WINDOWS)
    for (sentence_type, window_key, referent, time_rel), values in sorted(grouped.items()):
        prop_mean = mean(values)
        prop_sd = sd(values)
        n_bins = len(values)
        se2 = 2 * prop_sd / math.sqrt(n_bins) if n_bins else 0.0
        out.append(
            {
                "sentence_type": sentence_type,
                "window_key": window_key,
                "window": window_labels.get(window_key, window_key),
                "referent": referent,
                "time_rel": time_rel,
                "mean_prop": prop_mean,
                "sd_prop": prop_sd,
                "n_bins": n_bins,
                "lower": max(0.0, prop_mean - se2),
                "upper": min(1.0, prop_mean + se2),
            }
        )
    return out


def count_gaze_trials(rows: list[dict[str, str]]) -> dict[tuple[str, str], int]:
    by_window_type: dict[tuple[str, str], set[tuple[str, str, str]]] = defaultdict(set)
    for row in rows:
        by_window_type[(row["sentence_type"], row["window_key"])].add(
            (row["participant"], row["block"], row["image"])
        )
    return {key: len(value) for key, value in by_window_type.items()}


def render_cell(
    parts: list[str],
    rows: list[dict[str, object]],
    x0: float,
    y0: float,
    width: float,
    height: float,
    gaze_n: int,
    show_y_axis: bool,
) -> None:
    left_pad = 58 if show_y_axis else 28
    right_pad = 18
    top_pad = 18
    bottom_pad = 46
    plot_left = x0 + left_pad
    plot_right = x0 + width - right_pad
    plot_top = y0 + top_pad
    plot_bottom = y0 + height - bottom_pad

    def sx(value: float) -> float:
        return plot_left + value * (plot_right - plot_left)

    def sy(value: float) -> float:
        return plot_bottom - value * (plot_bottom - plot_top)

    parts.append(
        f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{width:.2f}" height="{height:.2f}" fill="white"/>'
    )

    for y_tick in [0, 0.25, 0.5, 0.75, 1.0]:
        y = sy(y_tick)
        parts.append(f'<line class="grid" x1="{plot_left:.2f}" x2="{plot_right:.2f}" y1="{y:.2f}" y2="{y:.2f}"/>')
        if show_y_axis:
            parts.append(f'<text class="tick" x="{plot_left - 9:.2f}" y="{y + 4:.2f}" text-anchor="end">{y_tick:g}</text>')

    for x_tick in [0, 0.5, 1.0]:
        x = sx(x_tick)
        parts.append(f'<line class="grid" x1="{x:.2f}" x2="{x:.2f}" y1="{plot_top:.2f}" y2="{plot_bottom:.2f}"/>')
        parts.append(f'<text class="tick" x="{x:.2f}" y="{plot_bottom + 22:.2f}" text-anchor="middle">{x_tick:g}</text>')

    parts.append(f'<line class="axis" x1="{plot_left:.2f}" x2="{plot_right:.2f}" y1="{plot_bottom:.2f}" y2="{plot_bottom:.2f}"/>')
    parts.append(f'<line class="axis" x1="{plot_left:.2f}" x2="{plot_left:.2f}" y1="{plot_top:.2f}" y2="{plot_bottom:.2f}"/>')

    by_ref = {"agent": [], "patient": []}
    for row in rows:
        by_ref[str(row["referent"])].append(row)

    for referent, color in [("agent", AGENT_COLOR), ("patient", PATIENT_COLOR)]:
        referent_rows = sorted(by_ref[referent], key=lambda item: float(item["time_rel"]))
        upper = [(sx(float(row["time_rel"])), sy(float(row["upper"]))) for row in referent_rows]
        lower = [(sx(float(row["time_rel"])), sy(float(row["lower"]))) for row in reversed(referent_rows)]
        if upper and lower:
            polygon_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in upper + lower)
            parts.append(f'<polygon points="{polygon_points}" fill="{color}" opacity="0.11"/>')
        line_points = [(sx(float(row["time_rel"])), sy(float(row["mean_prop"]))) for row in referent_rows]
        if line_points:
            parts.append(
                f'<path d="{svg_path(line_points)}" fill="none" stroke="{color}" stroke-width="3" '
                'stroke-linejoin="round" stroke-linecap="round"/>'
            )

    parts.append(f'<text class="nlabel" x="{plot_right - 4:.2f}" y="{plot_top + 15:.2f}" text-anchor="end">gaze n={gaze_n}</text>')


def render_page(
    path: Path,
    sentence_type: str,
    summary_rows: list[dict[str, object]],
    gaze_counts: dict[tuple[str, str], int],
    behavior_counts: dict[str, int],
) -> None:
    page_width = PAGE_WIDTH
    page_height = PAGE_HEIGHT
    margin_left = 82
    margin_right = 55
    margin_top = 164
    margin_bottom = 92
    col_gap = 22
    cols = len(WINDOWS)
    cell_width = (page_width - margin_left - margin_right - col_gap * (cols - 1)) / cols
    cell_height = page_height - margin_top - margin_bottom

    title = f"All {sentence_type} AVP sentences across planning windows"
    behavior_n = behavior_counts.get(sentence_type, 0)
    gaze_ns = [gaze_counts.get((sentence_type, window_key), 0) for window_key, _ in WINDOWS]
    gaze_n = max(gaze_ns) if gaze_ns else 0
    subtitle = (
        f"Behavioral clean set: n={behavior_n} of 879; usable gaze trials plotted: n={gaze_n}. "
        "RT < 6000 ms, fluent AVP trials."
    )

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_width}" height="{page_height}" viewBox="0 0 {page_width} {page_height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>',
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".page-title { font-size: 32px; font-weight: 700; }",
        ".subtitle { font-size: 17px; fill: #555; }",
        ".column-title { font-size: 18px; font-weight: 700; }",
        ".axis { stroke: #222; stroke-width: 1; }",
        ".grid { stroke: #dddddd; stroke-width: 1; }",
        ".tick { font-size: 12px; fill: #444; }",
        ".axis-label { font-size: 15px; fill: #222; }",
        ".legend { font-size: 17px; fill: #222; }",
        ".nlabel { font-size: 12px; fill: #555; }",
        "</style>",
        f'<text class="page-title" x="{page_width / 2:.1f}" y="48" text-anchor="middle">{html.escape(title)}</text>',
        f'<text class="subtitle" x="{page_width / 2:.1f}" y="78" text-anchor="middle">{html.escape(subtitle)}</text>',
    ]

    legend_x = page_width - 440
    legend_y = 106
    parts.extend(
        [
            f'<line x1="{legend_x}" x2="{legend_x + 42}" y1="{legend_y}" y2="{legend_y}" stroke="{AGENT_COLOR}" stroke-width="4"/>',
            f'<text class="legend" x="{legend_x + 54}" y="{legend_y + 6}">Agent</text>',
            f'<line x1="{legend_x + 145}" x2="{legend_x + 187}" y1="{legend_y}" y2="{legend_y}" stroke="{PATIENT_COLOR}" stroke-width="4"/>',
            f'<text class="legend" x="{legend_x + 199}" y="{legend_y + 6}">Patient</text>',
        ]
    )

    for col, (window_key, window_title) in enumerate(WINDOWS):
        x = margin_left + col * (cell_width + col_gap)
        parts.append(
            f'<text class="column-title" x="{x + cell_width / 2:.2f}" y="{margin_top - 28}" text-anchor="middle">{html.escape(window_title)}</text>'
        )
        rows = [
            row
            for row in summary_rows
            if row["sentence_type"] == sentence_type and row["window_key"] == window_key
        ]
        render_cell(
            parts=parts,
            rows=rows,
            x0=x,
            y0=margin_top,
            width=cell_width,
            height=cell_height,
            gaze_n=gaze_counts.get((sentence_type, window_key), 0),
            show_y_axis=col == 0,
        )

    parts.append(
        f'<text class="axis-label" x="{margin_left + (page_width - margin_left - margin_right) / 2:.1f}" y="{page_height - 35}" text-anchor="middle">Relative time within each window</text>'
    )
    parts.append(
        f'<text class="axis-label" x="30" y="{margin_top + cell_height / 2:.1f}" text-anchor="middle" transform="rotate(-90 30 {margin_top + cell_height / 2:.1f})">Proportion of looks</text>'
    )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create all-direct and all-inverse all-window Koryak gaze graphs.")
    parser.add_argument(
        "--trial-bins",
        default="output/koryak_speech_planning_graphs/speech_planning_trial_bins.csv",
        help="Trial-bin CSV from the all direct/inverse clean sentence graph extraction.",
    )
    parser.add_argument(
        "--behavior-counts",
        default="output/koryak_behavioral_latency/koryak_latency_descriptives.csv",
        help="Behavioral 879-dataset direct/inverse counts.",
    )
    parser.add_argument("--output-dir", default="output/koryak_direct_inverse_all_windows_graphs")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    trial_rows = read_csv(Path(args.trial_bins))
    summary_rows = summarize_bins(trial_rows)
    gaze_counts = count_gaze_trials(trial_rows)
    behavior_counts = load_behavior_counts(Path(args.behavior_counts))

    write_csv(output_dir / "direct_inverse_all_windows_plot_data.csv", summary_rows)
    count_rows = []
    for sentence_type in ["direct", "inverse"]:
        for window_key, window_title in WINDOWS:
            count_rows.append(
                {
                    "sentence_type": sentence_type,
                    "window_key": window_key,
                    "window": window_title,
                    "behavior_clean_trials_879_dataset": behavior_counts.get(sentence_type, 0),
                    "usable_gaze_trials": gaze_counts.get((sentence_type, window_key), 0),
                }
            )
    write_csv(output_dir / "direct_inverse_all_windows_counts.csv", count_rows)

    for sentence_type in ["direct", "inverse"]:
        svg_name = f"{sentence_type}_AVP_all_windows.svg"
        svg_path = output_dir / svg_name
        render_page(svg_path, sentence_type, summary_rows, gaze_counts, behavior_counts)
        convert_svg_to_pdf(svg_path)

    print(output_dir)


if __name__ == "__main__":
    main()
