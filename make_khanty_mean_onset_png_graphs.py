#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
import subprocess
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
from svg_to_pdf import DEFAULT_CACHE_DIR, find_rsvg_convert


TrialKey = tuple[str, int]


def title_type(sentence_type: str) -> str:
    return "Active" if sentence_type == "act" else "Passive"


def title_type_lower(sentence_type: str) -> str:
    return "active" if sentence_type == "act" else "passive"


def sentence_type_filename(sentence_type: str) -> str:
    return "active" if sentence_type == "act" else "passive"


def unique_trial_onsets(trial_bin_rows: list[dict[str, object]]) -> dict[TrialKey, dict[str, object]]:
    trials: dict[TrialKey, dict[str, object]] = {}
    for row in trial_bin_rows:
        key = (str(row["participant"]), int(row["item"]))
        trials[key] = {
            "participant": row["participant"],
            "item": int(row["item"]),
            "type": str(row["type"]),
            "speech_onset_ms": float(row["speech_onset_ms"]),
            "condition": row["condition"],
            "word_order": row["word_order"],
        }
    return trials


def behavior_end_ms(behavior_trials: dict[TrialKey, object], post_mean_ms: int, bin_ms: int) -> int:
    by_type: dict[str, list[float]] = defaultdict(list)
    for trial in behavior_trials.values():
        by_type[trial.sentence_type].append(float(trial.sol))

    candidates: list[float] = []
    for sentence_type in ["act", "pass"]:
        type_values = by_type[sentence_type]
        type_mean = mean(type_values)
        candidates.append(type_mean + post_mean_ms)
        less = [value for value in type_values if value < type_mean]
        greater = [value for value in type_values if value > type_mean]
        if less:
            candidates.append(mean(less) + post_mean_ms)
        if greater:
            candidates.append(mean(greater) + post_mean_ms)

    return int(math.ceil(max(candidates) / bin_ms) * bin_ms)


def build_group_meta(
    trial_onsets: dict[TrialKey, dict[str, object]],
    post_mean_ms: int,
) -> list[dict[str, object]]:
    by_type: dict[str, list[tuple[TrialKey, float]]] = defaultdict(list)
    for key, trial in trial_onsets.items():
        by_type[str(trial["type"])].append((key, float(trial["speech_onset_ms"])))

    group_meta: list[dict[str, object]] = []
    for sentence_type in ["act", "pass"]:
        type_trials = by_type[sentence_type]
        type_mean = mean([onset for _key, onset in type_trials])

        definitions = [
            ("all", "all", type_trials),
            ("less_than_mean", "less than mean", [(key, onset) for key, onset in type_trials if onset < type_mean]),
            ("greater_than_mean", "greater than mean", [(key, onset) for key, onset in type_trials if onset > type_mean]),
        ]
        for split, split_label, trials in definitions:
            if not trials:
                continue
            group_mean = mean([onset for _key, onset in trials])
            n_trials = len(trials)
            trial_keys = {key for key, _onset in trials}
            if split == "all" and sentence_type == "act":
                title = f"All active sentences (N = {n_trials})"
            elif split == "all":
                title = f"All passive sentences (N={n_trials})"
            else:
                title = (
                    f"{title_type(sentence_type)} sentences with SOL {split_label} "
                    f"(N = {n_trials})"
                )

            group_meta.append(
                {
                    "graph_id": f"{sentence_type}_{split}",
                    "type": sentence_type,
                    "split": split,
                    "title": title,
                    "n_trials": n_trials,
                    "n_participants": len({key[0] for key in trial_keys}),
                    "type_mean_speech_onset_ms": type_mean,
                    "group_mean_speech_onset_ms": group_mean,
                    "graph_end_ms": group_mean + post_mean_ms,
                    "min_speech_onset_ms": min(onset for _key, onset in trials),
                    "max_speech_onset_ms": max(onset for _key, onset in trials),
                    "trial_keys": trial_keys,
                    "filename_stem": (
                        f"all_{sentence_type_filename(sentence_type)}_sentences_mean_onset_plus_{post_mean_ms}ms"
                        if split == "all"
                        else f"{sentence_type_filename(sentence_type)}_sentences_sol_{split}_plus_{post_mean_ms}ms"
                    ),
                }
            )

    return group_meta


def summarize_group_plot_rows(
    trial_bin_rows: list[dict[str, object]],
    group_meta: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, int], list[float]] = defaultdict(list)

    groups_by_trial: dict[TrialKey, list[dict[str, object]]] = defaultdict(list)
    for meta in group_meta:
        for key in meta["trial_keys"]:
            groups_by_trial[key].append(meta)

    for row in trial_bin_rows:
        key = (str(row["participant"]), int(row["item"]))
        row_groups = groups_by_trial.get(key)
        if not row_groups:
            continue
        time_ms = int(row["time_bin_start_ms"])
        for meta in row_groups:
            if time_ms > float(meta["graph_end_ms"]):
                continue
            for referent, col in [("agent", "agent_prop"), ("patient", "patient_prop")]:
                grouped[(str(meta["graph_id"]), referent, time_ms)].append(float(row[col]))

    plot_rows: list[dict[str, object]] = []
    for (graph_id, referent, time_ms), values in sorted(grouped.items()):
        prop_mean = mean(values)
        prop_sd = sd(values)
        n_trial_bins = len(values)
        se2 = 2 * prop_sd / math.sqrt(n_trial_bins) if n_trial_bins else 0.0
        plot_rows.append(
            {
                "graph_id": graph_id,
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


def strip_trial_keys(meta_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for meta in meta_rows:
        row = {key: value for key, value in meta.items() if key != "trial_keys"}
        out.append(row)
    return out


def render_graph_svg(
    path: Path,
    rows: list[dict[str, object]],
    meta: dict[str, object],
) -> None:
    width = 1200
    height = 760
    left = 106
    right = 1090
    top = 96
    bottom = 640
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
        referent_rows.sort(key=lambda item: float(item["time_bin_start_ms"]))

    title = str(meta["title"])
    onset_label = f"{mean_onset_ms:.0f} ms"
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>',
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".title { font-size: 28px; font-weight: 700; }",
        ".axis { stroke: #222; stroke-width: 1.25; }",
        ".grid { stroke: #dddddd; stroke-width: 1; }",
        ".tick { font-size: 14px; fill: #333; }",
        ".label { font-size: 17px; fill: #222; }",
        ".legend { font-size: 15px; fill: #222; }",
        ".onset { font-size: 15px; font-weight: 700; fill: #222; }",
        "</style>",
        f'<text class="title" x="{(left + right) / 2:.1f}" y="42" text-anchor="middle">{html.escape(title)}</text>',
    ]

    for y_tick in [i / 10 for i in range(0, 11)]:
        y = sy(y_tick)
        parts.append(f'<line class="grid" x1="{left}" x2="{right}" y1="{y:.2f}" y2="{y:.2f}"/>')
        parts.append(f'<text class="tick" x="{left - 13}" y="{y + 5:.2f}" text-anchor="end">{y_tick:.1f}</text>')

    for x_tick in range(0, int(x_max // 500) * 500 + 1, 500):
        x = sx(float(x_tick))
        parts.append(f'<line class="grid" x1="{x:.2f}" x2="{x:.2f}" y1="{top}" y2="{bottom}"/>')
        parts.append(f'<text class="tick" x="{x:.2f}" y="{bottom + 28}" text-anchor="middle">{x_tick}</text>')

    parts.extend(
        [
            f'<line class="axis" x1="{left}" x2="{right}" y1="{bottom}" y2="{bottom}"/>',
            f'<line class="axis" x1="{left}" x2="{left}" y1="{top}" y2="{bottom}"/>',
            f'<text class="label" x="{(left + right) / 2:.1f}" y="{height - 34}" text-anchor="middle">Time from sentence display (ms)</text>',
            f'<text class="label" x="30" y="{(top + bottom) / 2:.1f}" text-anchor="middle" transform="rotate(-90 30 {(top + bottom) / 2:.1f})">Proportion of looks</text>',
        ]
    )

    onset_x = sx(mean_onset_ms)
    parts.append(
        f'<line x1="{onset_x:.2f}" x2="{onset_x:.2f}" y1="{top}" y2="{bottom}" '
        f'stroke="{MEAN_ONSET_COLOR}" stroke-width="2.25" stroke-dasharray="8 7"/>'
    )
    label_x = min(onset_x + 14, right - 94)
    parts.append(f'<rect x="{label_x - 7:.2f}" y="{top + 7}" width="92" height="26" fill="white" opacity="0.92"/>')
    parts.append(f'<text class="onset" x="{label_x:.2f}" y="{top + 26}">{html.escape(onset_label)}</text>')

    for referent, color in [("agent", AGENT_COLOR), ("patient", PATIENT_COLOR)]:
        referent_rows = by_ref[referent]
        if not referent_rows:
            continue

        upper = [(sx(float(row["time_bin_start_ms"])), sy(float(row["upper"]))) for row in referent_rows]
        lower_forward = [(sx(float(row["time_bin_start_ms"])), sy(float(row["lower"]))) for row in referent_rows]
        lower_reversed = list(reversed(lower_forward))
        polygon_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in upper + lower_reversed)
        mean_points = [(sx(float(row["time_bin_start_ms"])), sy(float(row["mean_prop"]))) for row in referent_rows]
        parts.append(f'<polygon points="{polygon_points}" fill="{color}" opacity="0.10"/>')
        parts.append(
            f'<path d="{svg_path(upper)}" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linejoin="round" stroke-linecap="round" stroke-dasharray="8 6"/>'
        )
        parts.append(
            f'<path d="{svg_path(lower_forward)}" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linejoin="round" stroke-linecap="round" stroke-dasharray="8 6"/>'
        )
        parts.append(
            f'<path d="{svg_path(mean_points)}" fill="none" stroke="{color}" stroke-width="3.8" '
            'stroke-linejoin="round" stroke-linecap="round"/>'
        )

    legend_x = right - 210
    legend_y = top + 40
    parts.extend(
        [
            f'<line x1="{legend_x}" x2="{legend_x + 38}" y1="{legend_y}" y2="{legend_y}" stroke="{AGENT_COLOR}" stroke-width="4"/>',
            f'<text class="legend" x="{legend_x + 50}" y="{legend_y + 5}">Agent</text>',
            f'<line x1="{legend_x}" x2="{legend_x + 38}" y1="{legend_y + 28}" y2="{legend_y + 28}" stroke="{PATIENT_COLOR}" stroke-width="4"/>',
            f'<text class="legend" x="{legend_x + 50}" y="{legend_y + 33}">Patient</text>',
            f'<line x1="{legend_x}" x2="{legend_x + 38}" y1="{legend_y + 56}" y2="{legend_y + 56}" stroke="{MEAN_ONSET_COLOR}" stroke-width="2.25" stroke-dasharray="8 7"/>',
            f'<text class="legend" x="{legend_x + 50}" y="{legend_y + 61}">Mean SOL</text>',
            "</svg>",
        ]
    )

    path.write_text("\n".join(parts), encoding="utf-8")


def convert_svg_to_png(svg_path: Path, png_path: Path, width: int) -> None:
    executable = find_rsvg_convert()
    if executable is None:
        raise RuntimeError("rsvg-convert is required to write PNG files from SVG graphs.")
    DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [executable, "-f", "png", "-w", str(width), "-o", str(png_path), str(svg_path)],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Khanty active/passive PNG graphs ending at mean SOL + 1500 ms."
    )
    parser.add_argument("--behavior-csv", default="osfstorage-archive/for_r_1.csv")
    parser.add_argument("--asc-dir", default="osfstorage-archive/ascs")
    parser.add_argument("--output-dir", default="output/khanty_mean_onset_png_graphs")
    parser.add_argument("--bin-ms", type=int, default=50)
    parser.add_argument("--post-mean-ms", type=int, default=1500)
    parser.add_argument("--png-width", type=int, default=1800)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    behavior_trials = load_behavior(Path(args.behavior_csv))
    max_ms = behavior_end_ms(behavior_trials, post_mean_ms=args.post_mean_ms, bin_ms=args.bin_ms)
    trial_bin_rows, merge_rows, missing_rows = accumulate_trial_bins(
        asc_dir=Path(args.asc_dir),
        behavior_trials=behavior_trials,
        max_ms=max_ms,
        bin_ms=args.bin_ms,
    )
    trial_onsets = unique_trial_onsets(trial_bin_rows)
    group_meta = build_group_meta(trial_onsets, post_mean_ms=args.post_mean_ms)
    plot_rows = summarize_group_plot_rows(trial_bin_rows, group_meta)

    write_pretty_csv(output_dir / "khanty_mean_onset_png_trial_bins_50ms.csv", trial_bin_rows)
    write_pretty_csv(output_dir / "khanty_mean_onset_png_plot_data.csv", plot_rows)
    write_pretty_csv(output_dir / "khanty_mean_onset_png_group_summary.csv", strip_trial_keys(group_meta))
    write_pretty_csv(output_dir / "khanty_mean_onset_png_merge_notes.csv", merge_rows)
    write_pretty_csv(output_dir / "khanty_mean_onset_png_missing_clean_trials.csv", missing_rows)

    graph_paths: list[Path] = []
    for meta in group_meta:
        rows = [row for row in plot_rows if row["graph_id"] == meta["graph_id"]]
        svg = output_dir / f"{meta['filename_stem']}.svg"
        png = output_dir / f"{meta['filename_stem']}.png"
        render_graph_svg(svg, rows, meta)
        convert_svg_to_png(svg, png, width=args.png_width)
        graph_paths.append(png)

    print(f"Clean behavior trials: {len(behavior_trials)}")
    print(f"Merged clean ASC trials: {len(trial_onsets)}")
    for meta in group_meta:
        print(
            f"{meta['graph_id']}: n={meta['n_trials']}, "
            f"mean SOL={float(meta['group_mean_speech_onset_ms']):.0f} ms, "
            f"xmax={float(meta['graph_end_ms']):.0f} ms"
        )
    print(f"Missing clean behavior trials: {len(missing_rows)}")
    print(f"Wrote {len(graph_paths)} PNG graphs to {output_dir}")


if __name__ == "__main__":
    main()
