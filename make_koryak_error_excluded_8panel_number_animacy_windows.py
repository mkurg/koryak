#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
from collections import Counter, defaultdict
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


PANELS = [
    ("direct", "direct_1_agent_1_patient_animate_patient", "Direct 1-1, animate patient"),
    ("direct", "direct_1_agent_1_patient_inanimate_patient", "Direct 1-1, inanimate patient"),
    ("direct", "direct_1_agent_2_patients_animate_patient", "Direct 1-2, animate patient"),
    ("direct", "direct_1_agent_2_patients_inanimate_patient", "Direct 1-2, inanimate patient"),
    ("inverse", "inverse_2_agents_1_patient_animate_patient", "Inverse 2-1, animate patient"),
    ("inverse", "inverse_2_agents_1_patient_inanimate_patient", "Inverse 2-1, inanimate patient"),
    ("inverse", "inverse_2_agents_2_patients_animate_patient", "Inverse 2-2, animate patient"),
    ("inverse", "inverse_2_agents_2_patients_inanimate_patient", "Inverse 2-2, inanimate patient"),
]
PANEL_ORDER = {(sentence_type, condition_key): index for index, (sentence_type, condition_key, _title) in enumerate(PANELS)}


def render_page(output_path: Path, input_dir: Path) -> list[dict[str, object]]:
    grouped = load_plot_rows(input_dir / "speech_planning_plot_data.csv")
    counts = load_counts(input_dir / "speech_planning_condition_counts.csv")

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
        f'<text class="title" x="{page_width / 2:.1f}" y="45" text-anchor="middle">Koryak error-form excluded gaze by sentence type, animacy, and argument number</text>',
        f'<text class="subtitle" x="{page_width / 2:.1f}" y="75" text-anchor="middle">Rows with vf_acc=0, vn_acc=0, or pn_acc=0 excluded; each panel shows sentence n and usable gaze n by window</text>',
        f'<text class="section" x="{margin_left + panel_width / 2:.1f}" y="122" text-anchor="middle">Animate patient</text>',
        f'<text class="section" x="{margin_left + panel_width + col_gap + panel_width / 2:.1f}" y="122" text-anchor="middle">Inanimate patient</text>',
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
    for index, (sentence_type, condition_key, title) in enumerate(PANELS):
        row_index = index // 2
        col_index = index % 2
        x = margin_left + col_index * (panel_width + col_gap)
        y = margin_top + row_index * (panel_height + row_gap)
        count_rows.extend(
            render_panel(
                parts,
                grouped,
                counts,
                "sentence_type_patient_animacy_argument_numbers",
                sentence_type,
                condition_key,
                html.unescape(title),
                x0=x,
                y0=y,
                width=panel_width,
                height=panel_height,
                show_y_axis=col_index == 0,
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


def read_error_form_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_error_count_outputs(input_dir: Path, output_dir: Path) -> None:
    rows = read_error_form_rows(input_dir / "speech_planning_error_form_trials.csv")
    by_cell: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (row["sentence_type"], row["condition_key"])
        if key in PANEL_ORDER:
            by_cell[key].append(row)

    all_combos = sorted({row["error_fields"] for row in rows if row["error_fields"]})
    summary_rows: list[dict[str, object]] = []
    combo_rows: list[dict[str, object]] = []
    for sentence_type, condition_key, _title in PANELS:
        cell_rows = by_cell[(sentence_type, condition_key)]
        first = cell_rows[0]
        annotated = [row for row in cell_rows if row["matched_accuracy"] == "yes"]
        missing = [row for row in cell_rows if row["matched_accuracy"] != "yes"]
        error_rows = [row for row in cell_rows if row["is_error_form"] == "yes"]
        combo_counter = Counter(row["error_fields"] if row["error_fields"] else "no_error" for row in cell_rows)

        summary_rows.append(
            {
                "sentence_type": first["sentence_type"],
                "condition_key": first["condition_key"],
                "condition": first["condition"],
                "clean_behavior_trials": len(cell_rows),
                "accuracy_annotated_trials": len(annotated),
                "missing_accuracy_annotation_trials": len(missing),
                "any_error_form_trials": len(error_rows),
                "vf_acc_inverse_marking_errors": sum(1 for row in cell_rows if row["vf_acc"] == "0"),
                "vn_acc_verb_number_errors": sum(1 for row in cell_rows if row["vn_acc"] == "0"),
                "pn_acc_patient_number_errors": sum(1 for row in cell_rows if row["pn_acc"] == "0"),
                "retained_no_error_or_unannotated": sum(1 for row in cell_rows if row["excluded_from_graphs"] == "no"),
            }
        )

        combo_record: dict[str, object] = {
            "sentence_type": first["sentence_type"],
            "condition_key": first["condition_key"],
            "condition": first["condition"],
            "clean_behavior_trials": len(cell_rows),
            "missing_accuracy_annotation_trials": len(missing),
            "no_error_or_unannotated": combo_counter["no_error"],
        }
        for combo in all_combos:
            combo_record[combo] = combo_counter[combo]
        combo_rows.append(combo_record)

    write_csv(output_dir / "koryak_error_counts_by_8cell_accuracy_column.csv", summary_rows)
    write_csv(output_dir / "koryak_error_counts_by_8cell_combinations.csv", combo_rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create one 8-panel Koryak graph for sentence type x patient animacy x argument numbers."
    )
    parser.add_argument("--input-dir", default="output/koryak_number_animacy_sentence_graphs_error_excluded")
    parser.add_argument("--output-dir", default="output/koryak_error_excluded_8panel_number_animacy_windows")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    svg_path = output_dir / "koryak_error_excluded_8panel_number_animacy_windows.svg"
    count_rows = render_page(svg_path, input_dir)
    write_csv(output_dir / "koryak_error_excluded_8panel_number_animacy_windows_counts.csv", count_rows)
    write_error_count_outputs(input_dir, output_dir)
    convert_svg_to_pdf(svg_path)
    print(svg_path.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
