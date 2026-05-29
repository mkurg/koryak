#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import re
from pathlib import Path

from make_koryak_error_excluded_8panel_consecutive_windows import (
    AGENT_COLOR,
    PATIENT_COLOR,
    load_counts,
    load_plot_rows,
    render_panel,
    write_csv,
)
from make_koryak_speech_planning_graphs import (
    DEFAULT_INCLUDED_PARTICIPANTS,
    BehaviorTrial,
    accumulate_trial_bins,
    animacy_label,
    parse_float,
    parse_int,
    normalize_participant_id,
    summarize_plot_rows,
    write_missing_trials,
    write_pretty_csv,
    write_condition_counts,
)
from svg_to_pdf import convert_svg_to_pdf


CONDITIONS = [
    ("direct", "direct_2_agents_2_patients", "Direct used for 2-2", "direct_2_2", 2, 2),
    ("inverse", "inverse_1_agent_1_patient", "Inverse used for 1-1", "inverse_1_1", 1, 1),
]


def target_numbers_from_image(image: str) -> tuple[int, int] | None:
    match = re.match(r"^.*-([12])-([12])-[a-z]+\.png$", image)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def load_selected_behavior(
    behavior_csv: Path,
    include_all_participants: bool,
    number_source: str,
) -> tuple[dict[tuple[str, str], BehaviorTrial], list[dict[str, object]]]:
    trials: dict[tuple[str, str], BehaviorTrial] = {}
    selected_rows: list[dict[str, object]] = []
    condition_by_key = {
        (sentence_type, agent_num, patient_num): (condition_key, condition_label, filename_suffix)
        for sentence_type, condition_key, condition_label, filename_suffix, agent_num, patient_num in CONDITIONS
    }

    with behavior_csv.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            participant = normalize_participant_id(row.get("participant's id", ""))
            if not include_all_participants and participant not in DEFAULT_INCLUDED_PARTICIPANTS:
                continue

            rt = parse_float(row.get("reaction time", ""))
            sentence_type = str(row.get("sentence type", "")).strip().lower()
            word_order = str(row.get("word order", "")).strip()
            fluency = str(row.get("fluency", "")).strip().lower()
            patient_animacy = animacy_label(row.get("patiens_animacy", ""))
            image = str(row.get("image", "")).strip()

            if number_source == "target_filename":
                numbers = target_numbers_from_image(image)
                if numbers is None:
                    continue
                agent_num, patient_num = numbers
            else:
                agent_num = parse_int(row.get("agens_num", ""))
                patient_num = parse_int(row.get("patiens_num", ""))

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

            condition = condition_by_key.get((sentence_type, agent_num, patient_num))
            if condition is None:
                continue

            condition_key, condition_label, filename_suffix = condition
            trial = BehaviorTrial(
                participant=participant,
                image=image,
                rt=rt,
                sentence_type=sentence_type,
                patient_animacy=patient_animacy,
                agent_num=agent_num,
                patient_num=patient_num,
                condition_key=condition_key,
                condition_label=condition_label,
                filename_suffix=filename_suffix,
            )
            trials[(participant, image)] = trial
            selected_rows.append(
                {
                    "participant": participant,
                    "image": image,
                    "sentence_type": sentence_type,
                    "condition_key": condition_key,
                    "condition": condition_label,
                    "number_source": number_source,
                    "agent_num": agent_num,
                    "patient_num": patient_num,
                    "patient_animacy": patient_animacy,
                    "rt": rt,
                    "translation": row.get("translation", ""),
                    "transcription": row.get("transcription", ""),
                    "comments": row.get("comments", ""),
                }
            )

    return trials, selected_rows


def render_page(output_path: Path, input_dir: Path, number_source: str) -> None:
    grouped = load_plot_rows(input_dir / "speech_planning_plot_data.csv")
    counts = load_counts(input_dir / "speech_planning_condition_counts.csv")

    page_width = 2300
    page_height = 760
    margin_left = 76
    margin_right = 54
    margin_top = 142
    margin_bottom = 58
    col_gap = 50
    panel_width = (page_width - margin_left - margin_right - col_gap) / 2
    panel_height = page_height - margin_top - margin_bottom

    source_label = "agens_num/patiens_num columns" if number_source == "produced_columns" else "stimulus filename"
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
        f'<text class="title" x="{page_width / 2:.1f}" y="42" text-anchor="middle">Koryak gaze for unexpected direct/inverse number pairings</text>',
        f'<text class="subtitle" x="{page_width / 2:.1f}" y="70" text-anchor="middle">Clean AVP trials; numbers from {html.escape(source_label)}; no error-form exclusion</text>',
    ]

    legend_x = page_width - 505
    legend_y = 92
    parts.extend(
        [
            f'<line x1="{legend_x}" x2="{legend_x + 42}" y1="{legend_y}" y2="{legend_y}" stroke="{AGENT_COLOR}" stroke-width="4"/>',
            f'<text class="legend" x="{legend_x + 54}" y="{legend_y + 6}">Agent</text>',
            f'<line x1="{legend_x + 155}" x2="{legend_x + 197}" y1="{legend_y}" y2="{legend_y}" stroke="{PATIENT_COLOR}" stroke-width="4"/>',
            f'<text class="legend" x="{legend_x + 209}" y="{legend_y + 6}">Patient</text>',
        ]
    )

    for index, (sentence_type, condition_key, title, _suffix, _agent_num, _patient_num) in enumerate(CONDITIONS):
        x = margin_left + index * (panel_width + col_gap)
        render_panel(
            parts,
            grouped,
            counts,
            "unexpected_number_sentence_type",
            sentence_type,
            condition_key,
            title,
            x0=x,
            y0=margin_top,
            width=panel_width,
            height=panel_height,
            show_y_axis=index == 0,
        )

    y_mid = margin_top + panel_height / 2
    parts.append(
        f'<text class="axis-label" x="31" y="{y_mid:.1f}" text-anchor="middle" '
        f'transform="rotate(-90 31 {y_mid:.1f})">Proportion of looks</text>'
    )
    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot Koryak direct 2-2 and inverse 1-1 gaze windows.")
    parser.add_argument("--behavior-csv", default="Koryak stimuli - final.csv")
    parser.add_argument("--asc-dir", default="ASC files")
    parser.add_argument("--output-dir", default="output/koryak_unexpected_direct_inverse_number_graphs")
    parser.add_argument(
        "--number-source",
        choices=["produced_columns", "target_filename"],
        default="produced_columns",
        help="Use produced/annotated agens_num+patiens_num columns or parse target numbers from the stimulus filename.",
    )
    parser.add_argument("--include-all-participants", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    behavior_trials, selected_rows = load_selected_behavior(
        Path(args.behavior_csv),
        include_all_participants=args.include_all_participants,
        number_source=args.number_source,
    )
    write_pretty_csv(output_dir / "selected_behavior_trials.csv", selected_rows)

    trial_bin_rows, merge_rows, duplicate_rows = accumulate_trial_bins(
        Path(args.asc_dir),
        behavior_trials,
        aoi_width=850,
        aoi_height=850,
    )
    write_pretty_csv(output_dir / "speech_planning_trial_bins.csv", trial_bin_rows)
    write_csv(output_dir / "speech_planning_plot_data.csv", summarize_plot_rows(trial_bin_rows))
    write_csv(output_dir / "speech_planning_asc_merge_summary.csv", merge_rows)
    write_pretty_csv(output_dir / "speech_planning_duplicate_asc_trials.csv", duplicate_rows)
    write_condition_counts(output_dir / "speech_planning_condition_counts.csv", behavior_trials, trial_bin_rows)
    write_missing_trials(output_dir / "speech_planning_missing_trials.csv", behavior_trials, trial_bin_rows)

    svg_path = output_dir / "koryak_unexpected_direct_inverse_number_graphs.svg"
    render_page(svg_path, output_dir, args.number_source)
    convert_svg_to_pdf(svg_path)
    print(svg_path.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
