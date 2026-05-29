#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
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
from make_koryak_speech_planning_graphs import (
    DEFAULT_INCLUDED_PARTICIPANTS,
    BehaviorTrial,
    accumulate_trial_bins,
    animacy_label,
    normalize_participant_id,
    parse_float,
    parse_int,
    summarize_plot_rows,
    write_condition_counts,
    write_missing_trials,
    write_pretty_csv,
)
from svg_to_pdf import convert_svg_to_pdf


SENTENCE_TYPE = "direct"
CONDITION_KEY = "direct_2_agents_1_patient"
PANEL_TITLE = "All direct 2-1"


def load_direct_2_1_behavior(
    behavior_csv: Path,
    include_all_participants: bool,
) -> tuple[dict[tuple[str, str], BehaviorTrial], list[dict[str, object]]]:
    trials: dict[tuple[str, str], BehaviorTrial] = {}
    selected_rows: list[dict[str, object]] = []

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
            agent_num = parse_int(row.get("agens_num", ""))
            patient_num = parse_int(row.get("patiens_num", ""))
            image = str(row.get("image", "")).strip()

            if (
                rt is None
                or rt >= 6000
                or fluency != "yes"
                or word_order != "AVP"
                or sentence_type != SENTENCE_TYPE
                or patient_animacy is None
                or agent_num != 2
                or patient_num != 1
                or not image
            ):
                continue

            trial = BehaviorTrial(
                participant=participant,
                image=image,
                rt=rt,
                sentence_type=sentence_type,
                patient_animacy=patient_animacy,
                agent_num=agent_num,
                patient_num=patient_num,
                condition_key=CONDITION_KEY,
                condition_label=PANEL_TITLE,
                filename_suffix="2_agents_1_patient",
            )
            trials[(participant, image)] = trial
            selected_rows.append(
                {
                    "participant": participant,
                    "image": image,
                    "sentence_type": sentence_type,
                    "condition_key": CONDITION_KEY,
                    "condition": PANEL_TITLE,
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
        f'<text class="subtitle" x="{page_width / 2:.1f}" y="70" text-anchor="middle">Clean AVP trials selected by agens_num=2, patiens_num=1; no error-form exclusion</text>',
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
        "direct_2_1",
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
    parser = argparse.ArgumentParser(description="Create a single all-window PDF for direct 2-1 Koryak trials.")
    parser.add_argument("--behavior-csv", default="Koryak stimuli - final.csv")
    parser.add_argument("--asc-dir", default="ASC files")
    parser.add_argument("--output-dir", default="output/koryak_direct_2_1_all_windows_graph")
    parser.add_argument("--include-all-participants", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    behavior_trials, selected_rows = load_direct_2_1_behavior(
        Path(args.behavior_csv),
        include_all_participants=args.include_all_participants,
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

    svg_path = output_dir / "koryak_direct_2_1_all_windows.svg"
    count_rows = render_page(svg_path, output_dir)
    write_csv(output_dir / "koryak_direct_2_1_all_windows_counts.csv", count_rows)
    convert_svg_to_pdf(svg_path)
    print(svg_path.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
