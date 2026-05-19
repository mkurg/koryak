#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import math
from collections import defaultdict
from pathlib import Path

from make_khanty_asc_active_passive_planning_graphs import (
    AGENT_COLOR,
    MEAN_ONSET_COLOR,
    PATIENT_COLOR,
    accumulate_trial_bins,
    load_behavior,
    mean,
    sd,
    svg_path,
    write_pretty_csv,
)
from svg_to_pdf import convert_svg_to_pdf


TARGET_CELLS = [
    ("act", "APV"),
    ("act", "PV"),
    ("pass", "PAV"),
    ("pass", "AV"),
]


def type_label(sentence_type: str) -> str:
    return "Active" if sentence_type == "act" else "Passive"


def split_label(split: str) -> str:
    return "SOL less than cell mean" if split == "less_than_mean" else "SOL greater than cell mean"


def target_key(row: dict[str, object]) -> tuple[str, str] | None:
    key = (str(row["type"]), str(row["word_order"]))
    return key if key in TARGET_CELLS else None


def build_thresholds_from_behavior(behavior_trials: dict[tuple[str, int], object]) -> dict[tuple[str, str], float]:
    by_cell: dict[tuple[str, str], list[float]] = defaultdict(list)
    for trial in behavior_trials.values():
        key = (trial.sentence_type, trial.word_order)
        if key in TARGET_CELLS:
            by_cell[key].append(trial.sol)
    return {key: mean(values) for key, values in by_cell.items()}


def estimate_max_ms(behavior_trials: dict[tuple[str, int], object], post_mean_ms: int, bin_ms: int) -> int:
    thresholds = build_thresholds_from_behavior(behavior_trials)
    group_onsets: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for trial in behavior_trials.values():
        key = (trial.sentence_type, trial.word_order)
        if key not in TARGET_CELLS:
            continue
        threshold = thresholds[key]
        if trial.sol < threshold:
            group_onsets[(trial.sentence_type, trial.word_order, "less_than_mean")].append(trial.sol)
        elif trial.sol > threshold:
            group_onsets[(trial.sentence_type, trial.word_order, "more_than_mean")].append(trial.sol)

    max_group_mean = max(mean(values) for values in group_onsets.values() if values)
    return int(math.ceil((max_group_mean + post_mean_ms) / bin_ms) * bin_ms)


def summarize_groups(trial_bin_rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[tuple[str, str, str], dict[str, object]]]:
    trial_onsets: dict[tuple[str, str, str, str], float] = {}
    for row in trial_bin_rows:
        key = target_key(row)
        if key is None:
            continue
        trial_onsets[(str(row["participant"]), str(row["item"]), key[0], key[1])] = float(row["speech_onset_ms"])

    by_cell: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (_participant, _item, sentence_type, word_order), onset in trial_onsets.items():
        by_cell[(sentence_type, word_order)].append(onset)
    thresholds = {key: mean(values) for key, values in by_cell.items()}

    group_onsets: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for (_participant, _item, sentence_type, word_order), onset in trial_onsets.items():
        threshold = thresholds[(sentence_type, word_order)]
        if onset < threshold:
            group_onsets[(sentence_type, word_order, "less_than_mean")].append(onset)
        elif onset > threshold:
            group_onsets[(sentence_type, word_order, "more_than_mean")].append(onset)

    group_rows: list[dict[str, object]] = []
    group_meta: dict[tuple[str, str, str], dict[str, object]] = {}
    for sentence_type, word_order in TARGET_CELLS:
        for split in ["less_than_mean", "more_than_mean"]:
            values = group_onsets[(sentence_type, word_order, split)]
            group_mean = mean(values)
            row = {
                "type": sentence_type,
                "word_order": word_order,
                "split": split,
                "label": split_label(split),
                "n_trials": len(values),
                "cell_mean_speech_onset_ms": thresholds[(sentence_type, word_order)],
                "group_mean_speech_onset_ms": group_mean,
                "graph_end_ms": group_mean + 1500,
                "min_speech_onset_ms": min(values),
                "max_speech_onset_ms": max(values),
            }
            group_rows.append(row)
            group_meta[(sentence_type, word_order, split)] = row

    return group_rows, group_meta


def summarize_plot_rows(
    trial_bin_rows: list[dict[str, object]],
    group_meta: dict[tuple[str, str, str], dict[str, object]],
) -> list[dict[str, object]]:
    thresholds = {
        (str(meta["type"]), str(meta["word_order"])): float(meta["cell_mean_speech_onset_ms"])
        for meta in group_meta.values()
    }
    grouped: dict[tuple[str, str, str, str, int], list[float]] = defaultdict(list)

    for row in trial_bin_rows:
        cell = target_key(row)
        if cell is None:
            continue
        onset = float(row["speech_onset_ms"])
        threshold = thresholds[cell]
        if onset < threshold:
            split = "less_than_mean"
        elif onset > threshold:
            split = "more_than_mean"
        else:
            continue

        meta = group_meta[(cell[0], cell[1], split)]
        if int(row["time_bin_start_ms"]) > float(meta["graph_end_ms"]):
            continue

        for referent, col in [("agent", "agent_prop"), ("patient", "patient_prop")]:
            grouped[
                (
                    cell[0],
                    cell[1],
                    split,
                    referent,
                    int(row["time_bin_start_ms"]),
                )
            ].append(float(row[col]))

    plot_rows: list[dict[str, object]] = []
    for (sentence_type, word_order, split, referent, time_ms), values in sorted(grouped.items()):
        prop_mean = mean(values)
        prop_sd = sd(values)
        n_trial_bins = len(values)
        se2 = 2 * prop_sd / math.sqrt(n_trial_bins) if n_trial_bins else 0.0
        plot_rows.append(
            {
                "type": sentence_type,
                "word_order": word_order,
                "split": split,
                "referent": referent,
                "time_bin_start_ms": time_ms,
                "mean_prop": prop_mean,
                "sd_prop": prop_sd,
                "n_trial_bins": n_trial_bins,
                "lower": max(0.0, prop_mean - se2),
                "upper": min(1.0, prop_mean + se2),
            }
        )
    return plot_rows


def render_graph_svg(path: Path, rows: list[dict[str, object]], meta: dict[str, object]) -> None:
    width = 900
    height = 560
    left = 86
    right = 820
    top = 72
    bottom = 470
    x_max = float(meta["graph_end_ms"])
    group_mean_ms = float(meta["group_mean_speech_onset_ms"])

    def sx(x: float) -> float:
        return left + (x / x_max) * (right - left)

    def sy(y: float) -> float:
        return bottom - y * (bottom - top)

    by_ref: dict[str, list[dict[str, object]]] = {"agent": [], "patient": []}
    for row in rows:
        by_ref[str(row["referent"])].append(row)
    for referent_rows in by_ref.values():
        referent_rows.sort(key=lambda row: float(row["time_bin_start_ms"]))

    title = f"{type_label(str(meta['type']))} {meta['word_order']} Trials: {split_label(str(meta['split']))}"
    subtitle = (
        f"n = {meta['n_trials']}; {meta['word_order']} mean SOL = "
        f"{float(meta['cell_mean_speech_onset_ms']):.0f} ms; dashed line = group mean SOL; plotted to +1500 ms"
    )
    onset_label = f"{group_mean_ms:.0f} ms"

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>',
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".title { font-size: 21px; font-weight: 700; }",
        ".subtitle { font-size: 13px; fill: #555; }",
        ".axis { stroke: #222; stroke-width: 1; }",
        ".grid { stroke: #dddddd; stroke-width: 1; }",
        ".tick { font-size: 12px; fill: #333; }",
        ".label { font-size: 14px; fill: #222; }",
        ".legend { font-size: 13px; fill: #222; }",
        ".onset { font-size: 13px; font-weight: 700; fill: #222; }",
        "</style>",
        f'<text class="title" x="{(left + right) / 2:.1f}" y="30" text-anchor="middle">{html.escape(title)}</text>',
        f'<text class="subtitle" x="{(left + right) / 2:.1f}" y="51" text-anchor="middle">{html.escape(subtitle)}</text>',
    ]

    for y_tick in [i / 10 for i in range(0, 11)]:
        y = sy(y_tick)
        parts.append(f'<line class="grid" x1="{left}" x2="{right}" y1="{y:.2f}" y2="{y:.2f}"/>')
        parts.append(f'<text class="tick" x="{left - 10}" y="{y + 4:.2f}" text-anchor="end">{y_tick:.1f}</text>')

    tick_values = list(range(0, int(x_max // 500) * 500 + 1, 500))
    if tick_values and x_max - tick_values[-1] < 300:
        tick_values[-1] = round(x_max)
    elif not tick_values or tick_values[-1] < x_max - 50:
        tick_values.append(round(x_max))
    for x_tick in tick_values:
        x = sx(float(x_tick))
        parts.append(f'<line class="grid" x1="{x:.2f}" x2="{x:.2f}" y1="{top}" y2="{bottom}"/>')
        parts.append(f'<text class="tick" x="{x:.2f}" y="{bottom + 22}" text-anchor="middle">{x_tick}</text>')

    parts.extend(
        [
            f'<line class="axis" x1="{left}" x2="{right}" y1="{bottom}" y2="{bottom}"/>',
            f'<line class="axis" x1="{left}" x2="{left}" y1="{top}" y2="{bottom}"/>',
            f'<text class="label" x="{(left + right) / 2:.1f}" y="{height - 28}" text-anchor="middle">Time from sentence display (ms)</text>',
            f'<text class="label" x="22" y="{(top + bottom) / 2:.1f}" text-anchor="middle" transform="rotate(-90 22 {(top + bottom) / 2:.1f})">Proportion of Looks</text>',
        ]
    )

    onset_x = sx(group_mean_ms)
    parts.append(
        f'<line x1="{onset_x:.2f}" x2="{onset_x:.2f}" y1="{top}" y2="{bottom}" '
        f'stroke="{MEAN_ONSET_COLOR}" stroke-width="2" stroke-dasharray="7 6"/>'
    )
    label_x = min(onset_x + 12, right - 82)
    parts.append(f'<rect x="{label_x - 6:.2f}" y="{top + 5}" width="80" height="22" fill="white" opacity="0.92"/>')
    parts.append(f'<text class="onset" x="{label_x:.2f}" y="{top + 20}">{html.escape(onset_label)}</text>')

    for referent, color in [("agent", AGENT_COLOR), ("patient", PATIENT_COLOR)]:
        referent_rows = by_ref[referent]
        upper = [(sx(float(row["time_bin_start_ms"])), sy(float(row["upper"]))) for row in referent_rows]
        lower = [(sx(float(row["time_bin_start_ms"])), sy(float(row["lower"]))) for row in reversed(referent_rows)]
        polygon_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in upper + lower)
        line_points = [(sx(float(row["time_bin_start_ms"])), sy(float(row["mean_prop"]))) for row in referent_rows]
        parts.append(f'<polygon points="{polygon_points}" fill="{color}" opacity="0.12"/>')
        parts.append(
            f'<path d="{svg_path(line_points)}" fill="none" stroke="{color}" '
            'stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>'
        )

    legend_x = right - 165
    legend_y = top + 35
    parts.extend(
        [
            f'<line x1="{legend_x}" x2="{legend_x + 28}" y1="{legend_y}" y2="{legend_y}" stroke="{AGENT_COLOR}" stroke-width="3"/>',
            f'<text class="legend" x="{legend_x + 38}" y="{legend_y + 4}">Agent</text>',
            f'<line x1="{legend_x}" x2="{legend_x + 28}" y1="{legend_y + 22}" y2="{legend_y + 22}" stroke="{PATIENT_COLOR}" stroke-width="3"/>',
            f'<text class="legend" x="{legend_x + 38}" y="{legend_y + 26}">Patient</text>',
            f'<line x1="{legend_x}" x2="{legend_x + 28}" y1="{legend_y + 44}" y2="{legend_y + 44}" stroke="{MEAN_ONSET_COLOR}" stroke-width="2" stroke-dasharray="7 6"/>',
            f'<text class="legend" x="{legend_x + 38}" y="{legend_y + 48}">Group mean SOL</text>',
            "</svg>",
        ]
    )

    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Khanty SOL-split graphs separately by requested word orders."
    )
    parser.add_argument("--behavior-csv", default="osfstorage-archive/for_r_1.csv")
    parser.add_argument("--asc-dir", default="osfstorage-archive/ascs")
    parser.add_argument("--output-dir", default="output/khanty_word_order_sol_split_graphs")
    parser.add_argument("--bin-ms", type=int, default=50)
    parser.add_argument("--post-mean-ms", type=int, default=1500)
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    behavior_trials = load_behavior(Path(args.behavior_csv))
    max_ms = estimate_max_ms(behavior_trials, post_mean_ms=args.post_mean_ms, bin_ms=args.bin_ms)
    trial_bin_rows, merge_rows, missing_rows = accumulate_trial_bins(
        asc_dir=Path(args.asc_dir),
        behavior_trials=behavior_trials,
        max_ms=max_ms,
        bin_ms=args.bin_ms,
    )
    target_trial_bin_rows = [row for row in trial_bin_rows if target_key(row) is not None]
    group_rows, group_meta = summarize_groups(target_trial_bin_rows)
    plot_rows = summarize_plot_rows(target_trial_bin_rows, group_meta)

    write_pretty_csv(output_dir / "khanty_word_order_sol_split_group_summary.csv", group_rows)
    write_pretty_csv(output_dir / "khanty_word_order_sol_split_plot_data.csv", plot_rows)
    write_pretty_csv(output_dir / "khanty_word_order_sol_split_trial_bins_50ms.csv", target_trial_bin_rows)
    write_pretty_csv(output_dir / "khanty_word_order_sol_split_merge_notes.csv", merge_rows)
    write_pretty_csv(output_dir / "khanty_word_order_sol_split_missing_clean_trials.csv", missing_rows)

    graph_paths: list[Path] = []
    for sentence_type, word_order in TARGET_CELLS:
        for split in ["less_than_mean", "more_than_mean"]:
            rows = [
                row
                for row in plot_rows
                if row["type"] == sentence_type and row["word_order"] == word_order and row["split"] == split
            ]
            split_suffix = "sol_less_than_mean" if split == "less_than_mean" else "sol_more_than_mean"
            graph_path = output_dir / f"khanty_{sentence_type}_{word_order}_{split_suffix}_plus_1500ms.svg"
            render_graph_svg(graph_path, rows, group_meta[(sentence_type, word_order, split)])
            graph_paths.append(graph_path)

    if not args.no_pdf:
        for graph_path in graph_paths:
            convert_svg_to_pdf(graph_path)

    print(f"Clean behavior trials: {len(behavior_trials)}")
    print(f"Requested word-order trials: {len({(row['participant'], row['item']) for row in target_trial_bin_rows})}")
    for row in group_rows:
        print(
            f"{row['type']} {row['word_order']} {row['split']}: "
            f"n={row['n_trials']}, cell_mean={float(row['cell_mean_speech_onset_ms']):.0f} ms, "
            f"group_mean={float(row['group_mean_speech_onset_ms']):.0f} ms, "
            f"xmax={float(row['graph_end_ms']):.0f} ms"
        )
    print(f"Missing clean behavior trials: {len(missing_rows)}")
    output_kinds = "SVG graphs" if args.no_pdf else "SVG graphs and PDF copies"
    print(f"Wrote {len(graph_paths)} {output_kinds} to {output_dir}")


if __name__ == "__main__":
    main()
