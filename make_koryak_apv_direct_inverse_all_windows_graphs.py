#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
from collections import Counter
from pathlib import Path

from make_koryak_direct_inverse_all_windows_graphs import (
    AGENT_COLOR,
    PATIENT_COLOR,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    WINDOWS,
    count_gaze_trials,
    render_cell,
    summarize_bins,
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
    write_missing_trials,
    write_pretty_csv,
)
from svg_to_pdf import convert_svg_to_pdf


WORD_ORDER = "APV"


def load_apv_behavior(
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
                or word_order != WORD_ORDER
                or sentence_type not in {"direct", "inverse"}
                or patient_animacy is None
                or agent_num is None
                or patient_num is None
                or not image
            ):
                continue

            condition_key = f"{sentence_type}_{WORD_ORDER.lower()}"
            condition_label = f"{sentence_type.capitalize()} {WORD_ORDER}"
            trials[(participant, image)] = BehaviorTrial(
                participant=participant,
                image=image,
                rt=rt,
                sentence_type=sentence_type,
                patient_animacy=patient_animacy,
                agent_num=agent_num,
                patient_num=patient_num,
                condition_key=condition_key,
                condition_label=condition_label,
                filename_suffix=WORD_ORDER.lower(),
            )
            selected_rows.append(
                {
                    "participant": participant,
                    "image": image,
                    "sentence_type": sentence_type,
                    "word_order": word_order,
                    "condition_key": condition_key,
                    "condition": condition_label,
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


def render_page(
    path: Path,
    sentence_type: str,
    summary_rows: list[dict[str, object]],
    gaze_counts: dict[tuple[str, str], int],
    behavior_counts: dict[str, int],
    participant_scope: str,
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

    title = f"All {sentence_type} {WORD_ORDER} sentences across planning windows"
    behavior_n = behavior_counts.get(sentence_type, 0)
    gaze_ns = [gaze_counts.get((sentence_type, window_key), 0) for window_key, _ in WINDOWS]
    gaze_n = max(gaze_ns) if gaze_ns else 0
    subtitle = (
        f"APV trials including erroneous verb forms: n={behavior_n}; usable gaze trials plotted: n={gaze_n}. "
        f"{participant_scope}; RT < 6000 ms; fluent {WORD_ORDER} trials; no _acc/error-form exclusion."
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
    parser = argparse.ArgumentParser(description="Create APV direct/inverse all-window Koryak gaze graphs.")
    parser.add_argument("--behavior-csv", default="Koryak stimuli - final.csv")
    parser.add_argument("--asc-dir", default="ASC files")
    parser.add_argument("--output-dir", default="output/koryak_apv_direct_inverse_all_windows_graphs")
    parser.add_argument("--include-all-participants", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    behavior_trials, selected_rows = load_apv_behavior(
        Path(args.behavior_csv),
        include_all_participants=args.include_all_participants,
    )
    participant_scope = "all participants" if args.include_all_participants else "default 16-participant set"
    write_pretty_csv(output_dir / "selected_behavior_trials.csv", selected_rows)

    trial_bin_rows, merge_rows, duplicate_rows = accumulate_trial_bins(
        Path(args.asc_dir),
        behavior_trials,
        aoi_width=850,
        aoi_height=850,
    )
    summary_rows = summarize_bins(trial_bin_rows)
    gaze_counts = count_gaze_trials(trial_bin_rows)
    behavior_counts = Counter(trial.sentence_type for trial in behavior_trials.values())

    write_pretty_csv(output_dir / "speech_planning_trial_bins.csv", trial_bin_rows)
    write_csv(output_dir / "apv_direct_inverse_all_windows_plot_data.csv", summary_rows)
    write_csv(output_dir / "speech_planning_asc_merge_summary.csv", merge_rows)
    write_pretty_csv(output_dir / "speech_planning_duplicate_asc_trials.csv", duplicate_rows)
    write_missing_trials(output_dir / "speech_planning_missing_trials.csv", behavior_trials, trial_bin_rows)

    count_rows = []
    for sentence_type in ["direct", "inverse"]:
        for window_key, window_title in WINDOWS:
            count_rows.append(
                {
                    "sentence_type": sentence_type,
                    "word_order": WORD_ORDER,
                    "window_key": window_key,
                    "window": window_title,
                    "participant_scope": participant_scope,
                    "behavior_apv_trials_including_error_forms": behavior_counts.get(sentence_type, 0),
                    "usable_gaze_trials": gaze_counts.get((sentence_type, window_key), 0),
                }
            )
    write_csv(output_dir / "apv_direct_inverse_all_windows_counts.csv", count_rows)

    for sentence_type in ["direct", "inverse"]:
        svg_path = output_dir / f"{sentence_type}_{WORD_ORDER}_all_windows.svg"
        render_page(svg_path, sentence_type, summary_rows, gaze_counts, behavior_counts, participant_scope)
        convert_svg_to_pdf(svg_path)

    print(output_dir)


if __name__ == "__main__":
    main()
