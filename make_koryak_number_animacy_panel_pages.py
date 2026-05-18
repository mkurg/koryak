#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
from collections import defaultdict
from pathlib import Path


AGENT_COLOR = "#CC3311"
PATIENT_COLOR = "#0077BB"
PAGE_WIDTH = 3600
PAGE_HEIGHT = 1780

WINDOWS = [
    ("speech_planning", "Early event apprehension"),
    ("linguistic_encoding_1", "Linguistic encoding I"),
    ("linguistic_encoding_2", "Linguistic encoding II"),
    ("linguistic_encoding_3", "Linguistic encoding III"),
    ("post_onset_1000_2500", "1000-2500 ms after speech onset"),
]

ROW_ORDER = {
    "inverse": [
        ("inverse_2_agents_1_patient_animate_patient", "2 agents, 1 patient, animate patient"),
        ("inverse_2_agents_2_patients_animate_patient", "2 agents, 2 patients, animate patient"),
        ("inverse_2_agents_1_patient_inanimate_patient", "2 agents, 1 patient, inanimate patient"),
        ("inverse_2_agents_2_patients_inanimate_patient", "2 agents, 2 patients, inanimate patient"),
    ],
    "direct": [
        ("direct_1_agent_1_patient_animate_patient", "1 agent, 1 patient, animate patient"),
        ("direct_1_agent_2_patients_animate_patient", "1 agent, 2 patients, animate patient"),
        ("direct_1_agent_1_patient_inanimate_patient", "1 agent, 1 patient, inanimate patient"),
        ("direct_1_agent_2_patients_inanimate_patient", "1 agent, 2 patients, inanimate patient"),
    ],
}


def svg_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    return " ".join(
        ("M" if index == 0 else "L") + f"{x:.2f},{y:.2f}"
        for index, (x, y) in enumerate(points)
    )


def load_plot_data(path: Path) -> dict[tuple[str, str, str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            grouped[
                (
                    row["sentence_type"],
                    row["condition_key"],
                    row["window_key"],
                    row["referent"],
                )
            ].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: float(row["time_rel"]))
    return grouped


def load_counts(path: Path) -> dict[tuple[str, str, str], int]:
    counts: dict[tuple[str, str, str], int] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            counts[(row["sentence_type"], row["condition_key"], row["window_key"])] = int(row["plotted_trials"])
    return counts


def render_cell(
    parts: list[str],
    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]],
    counts: dict[tuple[str, str, str], int],
    sentence_type: str,
    condition_key: str,
    window_key: str,
    x0: float,
    y0: float,
    width: float,
    height: float,
    show_y_axis: bool,
    show_x_axis: bool,
) -> None:
    left_pad = 42
    right_pad = 12
    top_pad = 15
    bottom_pad = 34
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
            parts.append(f'<text class="tick" x="{plot_left - 8:.2f}" y="{y + 4:.2f}" text-anchor="end">{y_tick:g}</text>')

    for x_tick in [0, 0.5, 1.0]:
        x = sx(x_tick)
        parts.append(f'<line class="grid" x1="{x:.2f}" x2="{x:.2f}" y1="{plot_top:.2f}" y2="{plot_bottom:.2f}"/>')
        if show_x_axis:
            parts.append(f'<text class="tick" x="{x:.2f}" y="{plot_bottom + 20:.2f}" text-anchor="middle">{x_tick:g}</text>')

    parts.append(f'<line class="axis" x1="{plot_left:.2f}" x2="{plot_right:.2f}" y1="{plot_bottom:.2f}" y2="{plot_bottom:.2f}"/>')
    parts.append(f'<line class="axis" x1="{plot_left:.2f}" x2="{plot_left:.2f}" y1="{plot_top:.2f}" y2="{plot_bottom:.2f}"/>')

    for referent, color in [("agent", AGENT_COLOR), ("patient", PATIENT_COLOR)]:
        rows = grouped.get((sentence_type, condition_key, window_key, referent), [])
        upper = [(sx(float(row["time_rel"])), sy(float(row["upper"]))) for row in rows]
        lower = [(sx(float(row["time_rel"])), sy(float(row["lower"]))) for row in reversed(rows)]
        if upper and lower:
            polygon_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in upper + lower)
            parts.append(f'<polygon points="{polygon_points}" fill="{color}" opacity="0.10"/>')
        line_points = [(sx(float(row["time_rel"])), sy(float(row["mean_prop"]))) for row in rows]
        if line_points:
            parts.append(
                f'<path d="{svg_path(line_points)}" fill="none" stroke="{color}" stroke-width="2.2" '
                'stroke-linejoin="round" stroke-linecap="round"/>'
            )

    n = counts.get((sentence_type, condition_key, window_key), 0)
    parts.append(f'<text class="nlabel" x="{plot_right - 4:.2f}" y="{plot_top + 13:.2f}" text-anchor="end">n={n}</text>')


def render_page(
    output_path: Path,
    sentence_type: str,
    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]],
    counts: dict[tuple[str, str, str], int],
) -> None:
    page_width = PAGE_WIDTH
    page_height = PAGE_HEIGHT
    margin_left = 520
    margin_right = 60
    margin_top = 188
    margin_bottom = 95
    col_gap = 18
    row_gap = 34
    cols = len(WINDOWS)
    rows = len(ROW_ORDER[sentence_type])
    cell_width = (page_width - margin_left - margin_right - col_gap * (cols - 1)) / cols
    cell_height = (page_height - margin_top - margin_bottom - row_gap * (rows - 1)) / rows

    page_title = f"{sentence_type.capitalize()} AVP: number by patient animacy across planning windows"

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_width}" height="{page_height}" viewBox="0 0 {page_width} {page_height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>',
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".page-title { font-size: 34px; font-weight: 700; }",
        ".subtitle { font-size: 17px; fill: #555; }",
        ".column-title { font-size: 18px; font-weight: 700; }",
        ".row-title { font-size: 18px; font-weight: 700; }",
        ".axis { stroke: #222; stroke-width: 1; }",
        ".grid { stroke: #dddddd; stroke-width: 1; }",
        ".tick { font-size: 12px; fill: #444; }",
        ".axis-label { font-size: 15px; fill: #222; }",
        ".legend { font-size: 17px; fill: #222; }",
        ".nlabel { font-size: 12px; fill: #555; }",
        "</style>",
        f'<text class="page-title" x="{page_width / 2:.1f}" y="48" text-anchor="middle">{html.escape(page_title)}</text>',
        f'<text class="subtitle" x="{page_width / 2:.1f}" y="78" text-anchor="middle">RT &lt; 6000 ms, fluent AVP trials; time windows unfold chronologically left to right</text>',
    ]

    legend_x = page_width - 445
    legend_y = 103
    parts.extend(
        [
            f'<line x1="{legend_x}" x2="{legend_x + 42}" y1="{legend_y}" y2="{legend_y}" stroke="{AGENT_COLOR}" stroke-width="4"/>',
            f'<text class="legend" x="{legend_x + 54}" y="{legend_y + 6}">Agent</text>',
            f'<line x1="{legend_x + 145}" x2="{legend_x + 187}" y1="{legend_y}" y2="{legend_y}" stroke="{PATIENT_COLOR}" stroke-width="4"/>',
            f'<text class="legend" x="{legend_x + 199}" y="{legend_y + 6}">Patient</text>',
        ]
    )

    for col, (_window_key, window_title) in enumerate(WINDOWS):
        x = margin_left + col * (cell_width + col_gap) + cell_width / 2
        parts.append(f'<text class="column-title" x="{x:.2f}" y="{margin_top - 28}" text-anchor="middle">{html.escape(window_title)}</text>')

    for row_i, (condition_key, condition_label) in enumerate(ROW_ORDER[sentence_type]):
        y = margin_top + row_i * (cell_height + row_gap)
        row_label_y = y + cell_height / 2
        row_ns = [
            counts.get((sentence_type, condition_key, window_key), 0)
            for window_key, _window_title in WINDOWS
        ]
        nonzero_row_ns = [n for n in row_ns if n > 0]
        row_n = nonzero_row_ns[0] if nonzero_row_ns else 0
        row_label = f"{condition_label} (n={row_n})"
        parts.append(
            f'<text class="row-title" x="{margin_left - 34}" y="{row_label_y:.2f}" text-anchor="end" dominant-baseline="middle">{html.escape(row_label)}</text>'
        )
        for col_i, (window_key, _window_title) in enumerate(WINDOWS):
            x = margin_left + col_i * (cell_width + col_gap)
            render_cell(
                parts,
                grouped=grouped,
                counts=counts,
                sentence_type=sentence_type,
                condition_key=condition_key,
                window_key=window_key,
                x0=x,
                y0=y,
                width=cell_width,
                height=cell_height,
                show_y_axis=col_i == 0,
                show_x_axis=row_i == rows - 1,
            )

    parts.append(
        f'<text class="axis-label" x="{margin_left + (page_width - margin_left - margin_right) / 2:.1f}" y="{page_height - 35}" text-anchor="middle">Relative time within each window</text>'
    )
    parts.append(
        f'<text class="axis-label" x="44" y="{margin_top + (page_height - margin_top - margin_bottom) / 2:.1f}" text-anchor="middle" transform="rotate(-90 44 {margin_top + (page_height - margin_top - margin_bottom) / 2:.1f})">Proportion of looks</text>'
    )
    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")


def write_print_wrapper(output_path: Path, svg_filename: str, title: str) -> None:
    output_path.write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html>",
                "<head>",
                '  <meta charset="utf-8">',
                "  <style>",
                "    @page {",
                f"      size: {PAGE_WIDTH}px {PAGE_HEIGHT}px;",
                "      margin: 0;",
                "    }",
                "    html,",
                "    body {",
                "      margin: 0;",
                f"      width: {PAGE_WIDTH}px;",
                f"      height: {PAGE_HEIGHT}px;",
                "      overflow: hidden;",
                "      background: white;",
                "    }",
                "    img {",
                "      display: block;",
                f"      width: {PAGE_WIDTH}px;",
                f"      height: {PAGE_HEIGHT}px;",
                "    }",
                "  </style>",
                "</head>",
                "<body>",
                f'  <img src="{html.escape(svg_filename)}" alt="{html.escape(title)}">',
                "</body>",
                "</html>",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create direct/inverse Koryak number-by-animacy panel pages.")
    parser.add_argument("--input-dir", default="output/koryak_number_animacy_sentence_graphs")
    parser.add_argument("--output-dir", default="output/koryak_number_animacy_sentence_graphs")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    grouped = load_plot_data(input_dir / "speech_planning_plot_data.csv")
    counts = load_counts(input_dir / "speech_planning_condition_counts.csv")

    for sentence_type in ["inverse", "direct"]:
        svg_filename = f"{sentence_type}_AVP_number_animacy_all_windows_panel.svg"
        html_filename = f"{sentence_type}_AVP_number_animacy_all_windows_panel_print.html"
        title = f"{sentence_type.capitalize()} AVP panel"
        render_page(output_dir / svg_filename, sentence_type, grouped, counts)
        write_print_wrapper(output_dir / html_filename, svg_filename, title)


if __name__ == "__main__":
    main()
