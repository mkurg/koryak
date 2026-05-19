#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
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


def fmt_label(sentence_type: str) -> str:
    return "Active" if sentence_type == "act" else "Passive"


def group_key(row: dict[str, object], thresholds: dict[str, float]) -> str | None:
    sentence_type = str(row["type"])
    onset = float(row["speech_onset_ms"])
    threshold = thresholds[sentence_type]
    if onset < threshold:
        return "less_than_mean"
    if onset > threshold:
        return "more_than_mean"
    return None


def summarize_groups(trial_bin_rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[tuple[str, str], dict[str, object]]]:
    trial_onsets: dict[tuple[str, str, str], float] = {}
    for row in trial_bin_rows:
        trial_onsets[(str(row["participant"]), str(row["item"]), str(row["type"]))] = float(row["speech_onset_ms"])

    by_type: dict[str, list[float]] = defaultdict(list)
    for (_participant, _item, sentence_type), onset in trial_onsets.items():
        by_type[sentence_type].append(onset)
    thresholds = {sentence_type: mean(values) for sentence_type, values in by_type.items()}

    group_onsets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (_participant, _item, sentence_type), onset in trial_onsets.items():
        threshold = thresholds[sentence_type]
        if onset < threshold:
            group_onsets[(sentence_type, "less_than_mean")].append(onset)
        elif onset > threshold:
            group_onsets[(sentence_type, "more_than_mean")].append(onset)

    group_rows: list[dict[str, object]] = []
    group_meta: dict[tuple[str, str], dict[str, object]] = {}
    for sentence_type in ["act", "pass"]:
        for split in ["less_than_mean", "more_than_mean"]:
            values = group_onsets[(sentence_type, split)]
            group_mean = mean(values)
            graph_end = group_mean + 1500
            label = "SOL < type mean" if split == "less_than_mean" else "SOL > type mean"
            row = {
                "type": sentence_type,
                "split": split,
                "label": label,
                "n_trials": len(values),
                "type_mean_speech_onset_ms": thresholds[sentence_type],
                "group_mean_speech_onset_ms": group_mean,
                "graph_end_ms": graph_end,
                "min_speech_onset_ms": min(values),
                "max_speech_onset_ms": max(values),
            }
            group_rows.append(row)
            group_meta[(sentence_type, split)] = row

    return group_rows, group_meta


def summarize_plot_rows(
    trial_bin_rows: list[dict[str, object]],
    group_meta: dict[tuple[str, str], dict[str, object]],
) -> list[dict[str, object]]:
    thresholds = {
        str(meta["type"]): float(meta["type_mean_speech_onset_ms"])
        for meta in group_meta.values()
    }
    grouped: dict[tuple[str, str, str, int], list[float]] = defaultdict(list)

    for row in trial_bin_rows:
        split = group_key(row, thresholds)
        if split is None:
            continue
        meta = group_meta[(str(row["type"]), split)]
        if int(row["time_bin_start_ms"]) > float(meta["graph_end_ms"]):
            continue
        for referent, col in [("agent", "agent_prop"), ("patient", "patient_prop")]:
            grouped[
                (
                    str(row["type"]),
                    split,
                    referent,
                    int(row["time_bin_start_ms"]),
                )
            ].append(float(row[col]))

    plot_rows: list[dict[str, object]] = []
    for (sentence_type, split, referent, time_ms), values in sorted(grouped.items()):
        prop_mean = mean(values)
        prop_sd = sd(values)
        n_trial_bins = len(values)
        se2 = 2 * prop_sd / math.sqrt(n_trial_bins) if n_trial_bins else 0.0
        plot_rows.append(
            {
                "type": sentence_type,
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


def render_graph_svg(
    path: Path,
    rows: list[dict[str, object]],
    meta: dict[str, object],
) -> None:
    width = 900
    height = 560
    left = 86
    right = 820
    top = 72
    bottom = 470
    x_max = float(meta["graph_end_ms"])
    mean_onset_ms = float(meta["group_mean_speech_onset_ms"])

    def sx(x: float) -> float:
        return left + (x / x_max) * (right - left)

    def sy(y: float) -> float:
        return bottom - y * (bottom - top)

    by_ref: dict[str, list[dict[str, object]]] = {"agent": [], "patient": []}
    for row in rows:
        by_ref[str(row["referent"])].append(row)
    for referent_rows in by_ref.values():
        referent_rows.sort(key=lambda row: float(row["time_bin_start_ms"]))

    split_text = "SOL less than type mean" if meta["split"] == "less_than_mean" else "SOL greater than type mean"
    title = f"{fmt_label(str(meta['type']))} Trials: {split_text}"
    subtitle = (
        f"n = {meta['n_trials']}; type mean SOL = {float(meta['type_mean_speech_onset_ms']):.0f} ms; "
        f"dashed line = group mean SOL; plotted to +1500 ms"
    )
    onset_label = f"{mean_onset_ms:.0f} ms"

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
    if not tick_values or tick_values[-1] < x_max - 50:
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

    onset_x = sx(mean_onset_ms)
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
        description="Create Khanty active/passive graphs split by SOL below/above type mean."
    )
    parser.add_argument("--behavior-csv", default="osfstorage-archive/for_r_1.csv")
    parser.add_argument("--asc-dir", default="osfstorage-archive/ascs")
    parser.add_argument("--output-dir", default="output/khanty_sol_split_speech_planning_graphs")
    parser.add_argument("--bin-ms", type=int, default=50)
    parser.add_argument("--post-mean-ms", type=int, default=1500)
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    behavior_trials = load_behavior(Path(args.behavior_csv))

    behavior_by_type: dict[str, list[float]] = defaultdict(list)
    for trial in behavior_trials.values():
        behavior_by_type[trial.sentence_type].append(trial.sol)
    type_means = {sentence_type: mean(values) for sentence_type, values in behavior_by_type.items()}
    temporary_group_means: list[float] = []
    for trial_type, values in behavior_by_type.items():
        temporary_group_means.append(mean([value for value in values if value < type_means[trial_type]]))
        temporary_group_means.append(mean([value for value in values if value > type_means[trial_type]]))

    max_ms = int(math.ceil((max(temporary_group_means) + args.post_mean_ms) / args.bin_ms) * args.bin_ms)
    trial_bin_rows, merge_rows, missing_rows = accumulate_trial_bins(
        asc_dir=Path(args.asc_dir),
        behavior_trials=behavior_trials,
        max_ms=max_ms,
        bin_ms=args.bin_ms,
    )
    group_rows, group_meta = summarize_groups(trial_bin_rows)
    plot_rows = summarize_plot_rows(trial_bin_rows, group_meta)

    write_pretty_csv(output_dir / "khanty_sol_split_group_summary.csv", group_rows)
    write_pretty_csv(output_dir / "khanty_sol_split_plot_data.csv", plot_rows)
    write_pretty_csv(output_dir / "khanty_sol_split_trial_bins_50ms.csv", trial_bin_rows)
    write_pretty_csv(output_dir / "khanty_sol_split_merge_notes.csv", merge_rows)
    write_pretty_csv(output_dir / "khanty_sol_split_missing_clean_trials.csv", missing_rows)

    graph_paths: list[Path] = []
    for sentence_type in ["act", "pass"]:
        for split in ["less_than_mean", "more_than_mean"]:
            rows = [
                row
                for row in plot_rows
                if row["type"] == sentence_type and row["split"] == split
            ]
            suffix = "sol_less_than_mean" if split == "less_than_mean" else "sol_more_than_mean"
            graph_path = output_dir / f"khanty_{sentence_type}_{suffix}_plus_1500ms.svg"
            render_graph_svg(graph_path, rows, group_meta[(sentence_type, split)])
            graph_paths.append(graph_path)

    if not args.no_pdf:
        for graph_path in graph_paths:
            convert_svg_to_pdf(graph_path)

    print(f"Clean behavior trials: {len(behavior_trials)}")
    print(f"Merged clean ASC trials: {len({(row['participant'], row['item']) for row in trial_bin_rows})}")
    for row in group_rows:
        print(
            f"{row['type']} {row['split']}: n={row['n_trials']}, "
            f"type_mean={float(row['type_mean_speech_onset_ms']):.0f} ms, "
            f"group_mean={float(row['group_mean_speech_onset_ms']):.0f} ms, "
            f"xmax={float(row['graph_end_ms']):.0f} ms"
        )
    print(f"Missing clean behavior trials: {len(missing_rows)}")
    output_kinds = "SVG graphs" if args.no_pdf else "SVG graphs and PDF copies"
    print(f"Wrote {len(graph_paths)} {output_kinds} to {output_dir}")


if __name__ == "__main__":
    main()
