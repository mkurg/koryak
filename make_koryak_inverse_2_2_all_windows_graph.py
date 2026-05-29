#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
from pathlib import Path

from make_koryak_error_excluded_8panel_consecutive_windows import (
    AGENT_COLOR,
    PATIENT_COLOR,
    load_counts,
    load_plot_rows,
    render_panel,
    write_csv,
)
from svg_to_pdf import convert_svg_to_pdf


SENTENCE_TYPE = "inverse"
CONDITION_KEY = "inverse_2_agents_2_patients"
PANEL_TITLE = "All inverse 2-2"


def render_page(output_path: Path, input_dir: Path) -> list[dict[str, object]]:
    grouped = load_plot_rows(input_dir / "speech_planning_plot_data.csv")
    counts = load_counts(input_dir / "speech_planning_condition_counts.csv")

    page_width = 1300
    page_height = 760
    margin_left = 76
    margin_right = 54
    margin_top = 142
    margin_bottom = 58
    panel_width = page_width - margin_left - margin_right
    panel_height = page_height - margin_top - margin_bottom

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_width}" height="{page_height}" viewBox="0 0 {page_width} {page_height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>',
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".title { font-size: 31px; font-weight: 700; }",
        ".subtitle { font-size: 16px; fill: #555; }",
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
        f'<text class="title" x="{page_width / 2:.1f}" y="42" text-anchor="middle">{html.escape(PANEL_TITLE)} gaze across planning windows</text>',
        f'<text class="subtitle" x="{page_width / 2:.1f}" y="70" text-anchor="middle">Clean AVP trials from the standard number-condition output; no error-form exclusion</text>',
    ]

    legend_x = page_width - 430
    legend_y = 92
    parts.extend(
        [
            f'<line x1="{legend_x}" x2="{legend_x + 42}" y1="{legend_y}" y2="{legend_y}" stroke="{AGENT_COLOR}" stroke-width="4"/>',
            f'<text class="legend" x="{legend_x + 54}" y="{legend_y + 6}">Agent</text>',
            f'<line x1="{legend_x + 155}" x2="{legend_x + 197}" y1="{legend_y}" y2="{legend_y}" stroke="{PATIENT_COLOR}" stroke-width="4"/>',
            f'<text class="legend" x="{legend_x + 209}" y="{legend_y + 6}">Patient</text>',
        ]
    )

    count_rows = render_panel(
        parts,
        grouped,
        counts,
        "inverse_2_2",
        SENTENCE_TYPE,
        CONDITION_KEY,
        PANEL_TITLE,
        x0=margin_left,
        y0=margin_top,
        width=panel_width,
        height=panel_height,
        show_y_axis=True,
    )

    y_mid = margin_top + panel_height / 2
    parts.append(
        f'<text class="axis-label" x="31" y="{y_mid:.1f}" text-anchor="middle" '
        f'transform="rotate(-90 31 {y_mid:.1f})">Proportion of looks</text>'
    )
    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")
    return count_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a single all-window PDF for all inverse 2-2 Koryak trials.")
    parser.add_argument("--input-dir", default="output/koryak_number_sentence_graphs")
    parser.add_argument("--output-dir", default="output/koryak_inverse_2_2_all_windows_graph")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    svg_path = output_dir / "koryak_inverse_2_2_all_windows.svg"
    count_rows = render_page(svg_path, input_dir)
    write_csv(output_dir / "koryak_inverse_2_2_all_windows_counts.csv", count_rows)
    convert_svg_to_pdf(svg_path)
    print(svg_path.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
