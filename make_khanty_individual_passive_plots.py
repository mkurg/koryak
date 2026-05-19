#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
from collections import Counter, defaultdict
from pathlib import Path

from svg_to_pdf import convert_svg_to_pdf


AGENT_COLOR = "#CC3311"
PATIENT_COLOR = "#0077BB"
MEAN_ONSET_COLOR = "#333333"


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def sd(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((value - m) ** 2 for value in values) / (len(values) - 1))


def fmt_num(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def write_pretty_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: fmt_num(value) for key, value in row.items()})


def safe_filename(value: object) -> str:
    chars = []
    for char in str(value):
        chars.append(char if char.isalnum() or char in {"_", "-"} else "_")
    return "".join(chars) or "participant"


def svg_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    return " ".join(
        ("M" if index == 0 else "L") + f"{x:.2f},{y:.2f}"
        for index, (x, y) in enumerate(points)
    )


def load_trial_bins(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["type"] != "pass":
                continue
            rows.append(
                {
                    "participant": row["participant"],
                    "item": row["item"],
                    "speech_onset_ms": float(row["speech_onset_ms"]),
                    "time_bin_start_ms": int(float(row["time_bin_start_ms"])),
                    "agent_prop": float(row["agent_prop"]),
                    "patient_prop": float(row["patient_prop"]),
                    "n_samples": int(float(row["n_samples"])),
                }
            )
    return rows


def passive_count_rows(trial_bin_rows: list[dict[str, object]], threshold: int) -> list[dict[str, object]]:
    trial_keys = {
        (str(row["participant"]), str(row["item"]))
        for row in trial_bin_rows
    }
    counts = Counter(participant for participant, _item in trial_keys)
    onsets: dict[str, list[float]] = defaultdict(list)
    for participant, item in trial_keys:
        onset_values = [
            float(row["speech_onset_ms"])
            for row in trial_bin_rows
            if row["participant"] == participant and row["item"] == item
        ]
        if onset_values:
            onsets[participant].append(onset_values[0])

    rows: list[dict[str, object]] = []
    for participant, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        rows.append(
            {
                "participant": participant,
                "n_passive_trials": count,
                "eligible_gt_threshold": "yes" if count > threshold else "no",
                "mean_speech_onset_ms": mean(onsets[participant]),
            }
        )
    return rows


def summarize_participant(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in rows:
        for referent, col in [("agent", "agent_prop"), ("patient", "patient_prop")]:
            grouped[(referent, int(row["time_bin_start_ms"]))].append(float(row[col]))

    summary_rows: list[dict[str, object]] = []
    for (referent, time_ms), values in sorted(grouped.items()):
        prop_mean = mean(values)
        prop_sd = sd(values)
        n_trial_bins = len(values)
        se2 = 2 * prop_sd / math.sqrt(n_trial_bins) if n_trial_bins else 0.0
        summary_rows.append(
            {
                "referent": referent,
                "time_bin_start_ms": time_ms,
                "mean_prop": prop_mean,
                "sd_prop": prop_sd,
                "n_trial_bins": n_trial_bins,
                "lower": max(0.0, prop_mean - se2),
                "upper": min(1.0, prop_mean + se2),
            }
        )
    return summary_rows


def render_participant_svg(
    path: Path,
    participant: str,
    rows: list[dict[str, object]],
    n_passive_trials: int,
    mean_onset_ms: float,
    max_ms: int,
) -> None:
    width = 900
    height = 560
    left = 86
    right = 820
    top = 72
    bottom = 470

    def sx(x: float) -> float:
        return left + (x / max_ms) * (right - left)

    def sy(y: float) -> float:
        return bottom - y * (bottom - top)

    by_ref: dict[str, list[dict[str, object]]] = {"agent": [], "patient": []}
    for row in rows:
        by_ref[str(row["referent"])].append(row)
    for referent_rows in by_ref.values():
        referent_rows.sort(key=lambda row: float(row["time_bin_start_ms"]))

    title = f"Khanty Passive Speech Planning: {participant}"
    subtitle = f"0-3500 ms from display; 50-ms bins; n = {n_passive_trials} passive trials"
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

    for x_tick in range(0, max_ms + 1, 500):
        x = sx(x_tick)
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
            f'<text class="legend" x="{legend_x + 38}" y="{legend_y + 48}">Mean speech onset</text>',
            "</svg>",
        ]
    )

    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create individual passive Khanty speech-planning plots above a passive-trial threshold."
    )
    parser.add_argument(
        "--trial-bins-csv",
        default="output/khanty_asc_active_passive_speech_planning_graphs/khanty_asc_speech_planning_trial_bins_50ms.csv",
    )
    parser.add_argument("--output-dir", default="output/khanty_individual_passive_plots_gt20")
    parser.add_argument("--min-passive-trials", type=int, default=20)
    parser.add_argument("--max-ms", type=int, default=3500)
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    trial_bin_rows = load_trial_bins(Path(args.trial_bins_csv))
    count_rows = passive_count_rows(trial_bin_rows, threshold=args.min_passive_trials)
    write_pretty_csv(output_dir / "khanty_passive_counts_by_participant.csv", count_rows)

    eligible = {
        str(row["participant"]): row
        for row in count_rows
        if int(row["n_passive_trials"]) > args.min_passive_trials
    }

    plot_data_rows: list[dict[str, object]] = []
    graph_paths: list[Path] = []
    for participant, count_row in eligible.items():
        participant_rows = [row for row in trial_bin_rows if row["participant"] == participant]
        summary_rows = summarize_participant(participant_rows)
        for row in summary_rows:
            plot_data_rows.append({"participant": participant, **row})

        graph_path = output_dir / f"{safe_filename(participant)}_passives_0_{args.max_ms}ms.svg"
        render_participant_svg(
            graph_path,
            participant=participant,
            rows=summary_rows,
            n_passive_trials=int(count_row["n_passive_trials"]),
            mean_onset_ms=float(count_row["mean_speech_onset_ms"]),
            max_ms=args.max_ms,
        )
        graph_paths.append(graph_path)

    write_pretty_csv(output_dir / "khanty_individual_passive_plot_data.csv", plot_data_rows)

    if not args.no_pdf:
        for graph_path in graph_paths:
            convert_svg_to_pdf(graph_path)

    print(f"Participants with passive trials: {len(count_rows)}")
    print(f"Eligible participants with > {args.min_passive_trials} passive trials: {len(eligible)}")
    if count_rows:
        print(f"Maximum passive trials for one participant: {max(int(row['n_passive_trials']) for row in count_rows)}")
    output_kinds = "SVG graphs" if args.no_pdf else "SVG graphs and PDF copies"
    print(f"Wrote {len(graph_paths)} {output_kinds} to {output_dir}")


if __name__ == "__main__":
    main()
