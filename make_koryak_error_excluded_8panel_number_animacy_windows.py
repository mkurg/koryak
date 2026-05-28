#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import re
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
ANNOTATION_DETAIL_COLUMNS = [
    "translation",
    "transcription",
    "verb_number",
    "patient_number",
    "word order",
    "comments",
]


def normalize_participant_key(value: object) -> str:
    text = str(value).strip().upper().replace("К", "K")
    match = re.search(r"K\s*0*(\d+)", text)
    if not match:
        return str(value).strip()
    return f"К{int(match.group(1)):02d}"


def verb_from_image(image: str) -> str:
    stem = Path(image).stem
    match = re.match(r"^(.*)-[12]-[12]-[a-z]+$", stem)
    if match:
        return match.group(1)
    return stem


def load_annotation_details(path: Path | None) -> dict[tuple[str, str], dict[str, str]]:
    if path is None or not path.exists():
        return {}

    details: dict[tuple[str, str], dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            participant = normalize_participant_key(row.get("id", ""))
            image = str(row.get("image", "")).strip()
            if not participant or not image:
                continue
            details[(participant, image)] = {column: row.get(column, "") for column in ANNOTATION_DETAIL_COLUMNS}
    return details


def unique_join(values: list[str]) -> str:
    return "; ".join(sorted({value for value in values if value}))


def summarize_error_rows(rows: list[dict[str, str]], all_combos: list[str]) -> dict[str, object]:
    combo_counter = Counter(row["error_fields"] for row in rows if row["error_fields"])
    record: dict[str, object] = {
        "any_error_form_trials": len(rows),
        "vf_acc_inverse_marking_errors": sum(1 for row in rows if row["vf_acc"] == "0"),
        "vn_acc_verb_number_errors": sum(1 for row in rows if row["vn_acc"] == "0"),
        "pn_acc_patient_number_errors": sum(1 for row in rows if row["pn_acc"] == "0"),
        "participant_count": len({row["participant"] for row in rows}),
        "participants": unique_join([row["participant"] for row in rows]),
        "image_count": len({row["image"] for row in rows}),
        "images": unique_join([row["image"] for row in rows]),
    }
    for combo in all_combos:
        record[combo] = combo_counter[combo]
    return record


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


def write_error_verb_outputs(
    rows: list[dict[str, str]],
    output_dir: Path,
    annotations_csv: Path | None,
    all_combos: list[str],
) -> None:
    annotation_details = load_annotation_details(annotations_csv)
    error_rows = [row for row in rows if row["is_error_form"] == "yes"]

    trial_rows: list[dict[str, object]] = []
    for row in error_rows:
        detail = annotation_details.get((normalize_participant_key(row["participant"]), row["image"]), {})
        trial_rows.append(
            {
                "verb": verb_from_image(row["image"]),
                "participant": row["participant"],
                "image": row["image"],
                "sentence_type": row["sentence_type"],
                "condition_key": row["condition_key"],
                "condition": row["condition"],
                "agent_num": row["agent_num"],
                "patient_num": row["patient_num"],
                "patient_animacy": row["patient_animacy"],
                "vf_acc": row["vf_acc"],
                "vn_acc": row["vn_acc"],
                "pn_acc": row["pn_acc"],
                "error_fields": row["error_fields"],
                "translation": detail.get("translation", ""),
                "transcription": detail.get("transcription", ""),
                "verb_number": detail.get("verb_number", ""),
                "patient_number": detail.get("patient_number", ""),
                "word_order": detail.get("word order", ""),
                "comments": detail.get("comments", ""),
            }
        )

    by_verb: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_cell_verb: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in error_rows:
        verb = verb_from_image(row["image"])
        by_verb[verb].append(row)
        by_cell_verb[(row["sentence_type"], row["condition_key"], verb)].append(row)

    verb_rows: list[dict[str, object]] = []
    for verb, verb_errors in by_verb.items():
        condition_labels = [f"{row['sentence_type']}: {row['condition']}" for row in verb_errors]
        verb_rows.append(
            {
                "verb": verb,
                **summarize_error_rows(verb_errors, all_combos),
                "condition_count": len(set(condition_labels)),
                "conditions": unique_join(condition_labels),
            }
        )
    verb_rows.sort(key=lambda row: (-int(row["any_error_form_trials"]), str(row["verb"])))

    cell_verb_rows: list[dict[str, object]] = []
    for (sentence_type, condition_key, verb), cell_verb_errors in by_cell_verb.items():
        first = cell_verb_errors[0]
        cell_verb_rows.append(
            {
                "sentence_type": sentence_type,
                "condition_key": condition_key,
                "condition": first["condition"],
                "verb": verb,
                **summarize_error_rows(cell_verb_errors, all_combos),
            }
        )
    cell_verb_rows.sort(
        key=lambda row: (
            PANEL_ORDER.get((str(row["sentence_type"]), str(row["condition_key"])), 999),
            -int(row["any_error_form_trials"]),
            str(row["verb"]),
        )
    )

    write_csv(output_dir / "koryak_error_trials_with_verbs.csv", trial_rows)
    write_csv(output_dir / "koryak_error_verb_summary.csv", verb_rows)
    write_csv(output_dir / "koryak_error_verb_by_8cell.csv", cell_verb_rows)
    write_error_verb_markdown(output_dir / "koryak_error_verb_summary.md", verb_rows)


def write_error_verb_markdown(path: Path, rows: list[dict[str, object]]) -> None:
    lines = [
        "# Koryak Error-Form Verbs",
        "",
        "Counts are error-form trial counts in the eight sentence type x patient animacy x argument-number cells.",
        "`vn_acc`, `pn_acc`, and `vn_acc+pn_acc` are exact error combinations; marginal totals are in the CSV.",
        "",
        "| verb | any | vn only | pn only | vn+pn |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['verb']} | {row['any_error_form_trials']} | "
            f"{row.get('vn_acc', 0)} | {row.get('pn_acc', 0)} | {row.get('vn_acc+pn_acc', 0)} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_error_count_outputs(input_dir: Path, output_dir: Path, annotations_csv: Path | None = None) -> None:
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
    write_error_verb_outputs(rows, output_dir, annotations_csv, all_combos)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create one 8-panel Koryak graph for sentence type x patient animacy x argument numbers."
    )
    parser.add_argument("--input-dir", default="output/koryak_number_animacy_sentence_graphs_error_excluded")
    parser.add_argument("--output-dir", default="output/koryak_error_excluded_8panel_number_animacy_windows")
    parser.add_argument("--annotations-csv", default="Koryak_thesis.xlsx - v_2.csv")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    svg_path = output_dir / "koryak_error_excluded_8panel_number_animacy_windows.svg"
    count_rows = render_page(svg_path, input_dir)
    write_csv(output_dir / "koryak_error_excluded_8panel_number_animacy_windows_counts.csv", count_rows)
    write_error_count_outputs(input_dir, output_dir, Path(args.annotations_csv) if args.annotations_csv else None)
    convert_svg_to_pdf(svg_path)
    print(svg_path.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
