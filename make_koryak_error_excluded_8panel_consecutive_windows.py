#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
from collections import defaultdict
from pathlib import Path

from svg_to_pdf import convert_svg_to_pdf


AGENT_COLOR = "#CC3311"
PATIENT_COLOR = "#0077BB"

WINDOWS = [
    ("speech_planning", "Planning"),
    ("linguistic_encoding_1", "LE I"),
    ("linguistic_encoding_2", "LE II"),
    ("linguistic_encoding_3", "LE III"),
    ("post_onset_1000_2500", "Post 1-2.5s"),
]

NUMBER_PANELS = [
    ("number", "direct", "direct_1_agent_1_patient", "Direct 1-1"),
    ("number", "direct", "direct_1_agent_2_patients", "Direct 1-2"),
    ("number", "inverse", "inverse_2_agents_1_patient", "Inverse 2-1"),
    ("number", "inverse", "inverse_2_agents_2_patients", "Inverse 2-2"),
]

ANIMACY_PANELS = [
    ("animacy", "direct", "animate", "Direct, animate patient"),
    ("animacy", "direct", "inanimate", "Direct, inanimate patient"),
    ("animacy", "inverse", "animate", "Inverse, animate patient"),
    ("animacy", "inverse", "inanimate", "Inverse, inanimate patient"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: fmt(value) for key, value in row.items()})


def load_plot_rows(path: Path) -> dict[tuple[str, str, str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(path):
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


def load_counts(path: Path) -> dict[tuple[str, str, str], dict[str, int]]:
    counts: dict[tuple[str, str, str], dict[str, int]] = {}
    for row in read_csv(path):
        counts[(row["sentence_type"], row["condition_key"], row["window_key"])] = {
            "sentences": int(float(row["clean_behavior_trials"])),
            "gaze": int(float(row["plotted_trials"])),
        }
    return counts


def svg_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    return " ".join(
        ("M" if index == 0 else "L") + f"{x:.2f},{y:.2f}"
        for index, (x, y) in enumerate(points)
    )


def render_panel(
    parts: list[str],
    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]],
    counts: dict[tuple[str, str, str], dict[str, int]],
    group_label: str,
    sentence_type: str,
    condition_key: str,
    panel_title: str,
    x0: float,
    y0: float,
    width: float,
    height: float,
    show_y_axis: bool,
) -> list[dict[str, object]]:
    left_pad = 58 if show_y_axis else 34
    right_pad = 18
    top_pad = 54
    bottom_pad = 50
    plot_left = x0 + left_pad
    plot_right = x0 + width - right_pad
    plot_top = y0 + top_pad
    plot_bottom = y0 + height - bottom_pad
    window_width = (plot_right - plot_left) / len(WINDOWS)

    def sx(window_index: int, rel: float) -> float:
        return plot_left + window_width * (window_index + rel)

    def sy(value: float) -> float:
        return plot_bottom - value * (plot_bottom - plot_top)

    panel_counts = [
        counts.get((sentence_type, condition_key, window_key), {"sentences": 0, "gaze": 0})
        for window_key, _window_label in WINDOWS
    ]
    sentence_ns = [item["sentences"] for item in panel_counts if item["sentences"]]
    sentence_n = sentence_ns[0] if sentence_ns else 0
    gaze_text = "/".join(str(item["gaze"]) for item in panel_counts)
    subtitle = f"sent n={sentence_n}; gaze n by window={gaze_text}"

    parts.append(f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{width:.2f}" height="{height:.2f}" fill="white"/>')
    parts.append(
        f'<text class="panel-title" x="{x0 + width / 2:.2f}" y="{y0 + 21:.2f}" text-anchor="middle">'
        f"{html.escape(panel_title)}</text>"
    )
    parts.append(
        f'<text class="panel-subtitle" x="{x0 + width / 2:.2f}" y="{y0 + 41:.2f}" text-anchor="middle">'
        f"{html.escape(subtitle)}</text>"
    )

    for y_tick in [0, 0.25, 0.5, 0.75, 1.0]:
        y = sy(y_tick)
        parts.append(f'<line class="grid" x1="{plot_left:.2f}" x2="{plot_right:.2f}" y1="{y:.2f}" y2="{y:.2f}"/>')
        if show_y_axis:
            parts.append(f'<text class="tick" x="{plot_left - 8:.2f}" y="{y + 4:.2f}" text-anchor="end">{y_tick:g}</text>')

    count_rows: list[dict[str, object]] = []
    for window_index, (window_key, window_label) in enumerate(WINDOWS):
        win_left = plot_left + window_index * window_width
        win_right = win_left + window_width
        if window_index > 0:
            parts.append(
                f'<line class="window-sep" x1="{win_left:.2f}" x2="{win_left:.2f}" '
                f'y1="{plot_top:.2f}" y2="{plot_bottom:.2f}"/>'
            )
        parts.append(
            f'<text class="window-label" x="{(win_left + win_right) / 2:.2f}" y="{plot_bottom + 22:.2f}" '
            f'text-anchor="middle">{html.escape(window_label)}</text>'
        )
        for tick_rel, tick_label in [(0.0, "0"), (0.5, ".5"), (1.0, "1")]:
            x = sx(window_index, tick_rel)
            parts.append(f'<line class="grid-v" x1="{x:.2f}" x2="{x:.2f}" y1="{plot_top:.2f}" y2="{plot_bottom:.2f}"/>')
            if tick_rel in {0.0, 1.0}:
                parts.append(f'<text class="mini-tick" x="{x:.2f}" y="{plot_bottom + 8:.2f}" text-anchor="middle">{tick_label}</text>')

        window_counts = counts.get((sentence_type, condition_key, window_key), {"sentences": 0, "gaze": 0})
        parts.append(
            f'<text class="nlabel" x="{win_right - 4:.2f}" y="{plot_top + 13:.2f}" text-anchor="end">'
            f"n={window_counts['gaze']}</text>"
        )
        count_rows.append(
            {
                "panel_group": group_label,
                "panel": panel_title,
                "sentence_type": sentence_type,
                "condition_key": condition_key,
                "window_key": window_key,
                "window": window_label,
                "sentence_count": window_counts["sentences"],
                "usable_gaze_count": window_counts["gaze"],
            }
        )

    parts.append(f'<line class="axis" x1="{plot_left:.2f}" x2="{plot_right:.2f}" y1="{plot_bottom:.2f}" y2="{plot_bottom:.2f}"/>')
    parts.append(f'<line class="axis" x1="{plot_left:.2f}" x2="{plot_left:.2f}" y1="{plot_top:.2f}" y2="{plot_bottom:.2f}"/>')

    for referent, color in [("agent", AGENT_COLOR), ("patient", PATIENT_COLOR)]:
        for window_index, (window_key, _window_label) in enumerate(WINDOWS):
            rows = grouped.get((sentence_type, condition_key, window_key, referent), [])
            upper = [
                (sx(window_index, float(row["time_rel"])), sy(float(row["upper"])))
                for row in rows
            ]
            lower = [
                (sx(window_index, float(row["time_rel"])), sy(float(row["lower"])))
                for row in reversed(rows)
            ]
            if upper and lower:
                points = " ".join(f"{x:.2f},{y:.2f}" for x, y in upper + lower)
                parts.append(f'<polygon points="{points}" fill="{color}" opacity="0.10"/>')

            line = [
                (sx(window_index, float(row["time_rel"])), sy(float(row["mean_prop"])))
                for row in rows
            ]
            if line:
                parts.append(
                    f'<path d="{svg_path(line)}" fill="none" stroke="{color}" stroke-width="2.35" '
                    'stroke-linejoin="round" stroke-linecap="round"/>'
                )

    return count_rows


def render_page(
    output_path: Path,
    number_grouped: dict[tuple[str, str, str, str], list[dict[str, str]]],
    number_counts: dict[tuple[str, str, str], dict[str, int]],
    animacy_grouped: dict[tuple[str, str, str, str], list[dict[str, str]]],
    animacy_counts: dict[tuple[str, str, str], dict[str, int]],
) -> list[dict[str, object]]:
    page_width = 3200
    page_height = 2400
    margin_left = 78
    margin_right = 58
    margin_top = 160
    margin_bottom = 70
    col_gap = 48
    row_gap = 50
    panel_width = (page_width - margin_left - margin_right - col_gap) / 2
    panel_height = (page_height - margin_top - margin_bottom - row_gap * 3) / 4

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_width}" height="{page_height}" viewBox="0 0 {page_width} {page_height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>',
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".title { font-size: 34px; font-weight: 700; }",
        ".subtitle { font-size: 17px; fill: #555; }",
        ".section { font-size: 22px; font-weight: 700; }",
        ".panel-title { font-size: 20px; font-weight: 700; }",
        ".panel-subtitle { font-size: 13px; fill: #555; }",
        ".axis { stroke: #222; stroke-width: 1; }",
        ".grid { stroke: #dddddd; stroke-width: 1; }",
        ".grid-v { stroke: #eeeeee; stroke-width: 1; }",
        ".window-sep { stroke: #999999; stroke-width: 1.15; stroke-dasharray: 5 5; }",
        ".tick { font-size: 12px; fill: #444; }",
        ".mini-tick { font-size: 9px; fill: #777; }",
        ".window-label { font-size: 11px; fill: #333; font-weight: 700; }",
        ".nlabel { font-size: 11px; fill: #555; }",
        ".axis-label { font-size: 15px; fill: #222; }",
        ".legend { font-size: 17px; fill: #222; }",
        "</style>",
        f'<text class="title" x="{page_width / 2:.1f}" y="45" text-anchor="middle">Koryak error-form excluded gaze across five planning windows</text>',
        f'<text class="subtitle" x="{page_width / 2:.1f}" y="75" text-anchor="middle">Rows with vf_acc=0, vn_acc=0, or pn_acc=0 excluded; each panel shows sentence n and usable gaze n by window</text>',
        f'<text class="section" x="{margin_left + panel_width / 2:.1f}" y="122" text-anchor="middle">Number contrasts</text>',
        f'<text class="section" x="{margin_left + panel_width + col_gap + panel_width / 2:.1f}" y="122" text-anchor="middle">Sentence type x patient animacy</text>',
    ]

    legend_x = page_width - 510
    legend_y = 82
    parts.extend(
        [
            f'<line x1="{legend_x}" x2="{legend_x + 42}" y1="{legend_y}" y2="{legend_y}" stroke="{AGENT_COLOR}" stroke-width="4"/>',
            f'<text class="legend" x="{legend_x + 54}" y="{legend_y + 6}">Agent</text>',
            f'<line x1="{legend_x + 155}" x2="{legend_x + 197}" y1="{legend_y}" y2="{legend_y}" stroke="{PATIENT_COLOR}" stroke-width="4"/>',
            f'<text class="legend" x="{legend_x + 209}" y="{legend_y + 6}">Patient</text>',
        ]
    )

    count_rows: list[dict[str, object]] = []
    for row_index, panel in enumerate(NUMBER_PANELS):
        group_label, sentence_type, condition_key, title = panel
        y = margin_top + row_index * (panel_height + row_gap)
        count_rows.extend(
            render_panel(
                parts,
                number_grouped,
                number_counts,
                group_label,
                sentence_type,
                condition_key,
                title,
                x0=margin_left,
                y0=y,
                width=panel_width,
                height=panel_height,
                show_y_axis=True,
            )
        )

    for row_index, panel in enumerate(ANIMACY_PANELS):
        group_label, sentence_type, condition_key, title = panel
        y = margin_top + row_index * (panel_height + row_gap)
        count_rows.extend(
            render_panel(
                parts,
                animacy_grouped,
                animacy_counts,
                group_label,
                sentence_type,
                condition_key,
                title,
                x0=margin_left + panel_width + col_gap,
                y0=y,
                width=panel_width,
                height=panel_height,
                show_y_axis=False,
            )
        )

    parts.append(
        f'<text class="axis-label" x="32" y="{margin_top + (page_height - margin_top - margin_bottom) / 2:.1f}" '
        f'text-anchor="middle" transform="rotate(-90 32 {margin_top + (page_height - margin_top - margin_bottom) / 2:.1f})">'
        "Proportion of looks</text>"
    )
    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")
    return count_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Create one 8-panel Koryak consecutive-window graph PDF.")
    parser.add_argument("--number-dir", default="output/koryak_number_sentence_graphs_error_excluded")
    parser.add_argument("--animacy-dir", default="output/koryak_speech_planning_graphs_error_excluded")
    parser.add_argument("--output-dir", default="output/koryak_error_excluded_8panel_consecutive_windows")
    args = parser.parse_args()

    number_dir = Path(args.number_dir)
    animacy_dir = Path(args.animacy_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    number_grouped = load_plot_rows(number_dir / "speech_planning_plot_data.csv")
    number_counts = load_counts(number_dir / "speech_planning_condition_counts.csv")
    animacy_grouped = load_plot_rows(animacy_dir / "speech_planning_plot_data.csv")
    animacy_counts = load_counts(animacy_dir / "speech_planning_condition_counts.csv")

    svg_path = output_dir / "koryak_error_excluded_8panel_consecutive_windows.svg"
    count_rows = render_page(svg_path, number_grouped, number_counts, animacy_grouped, animacy_counts)
    write_csv(output_dir / "koryak_error_excluded_8panel_consecutive_windows_counts.csv", count_rows)
    convert_svg_to_pdf(svg_path)
    print(svg_path.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
