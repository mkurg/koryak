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


def parse_float(value: object) -> float | None:
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    if math.isnan(out):
        return None
    return out


def parse_int(value: object) -> int | None:
    number = parse_float(value)
    if number is None:
        return None
    return int(number)


def is_one(value: object) -> bool:
    return str(value).strip() in {"1", "1.0"}


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


def trial_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        row.get("ppt_id", "").strip(),
        row.get("item", "").strip(),
        row.get("type", "").strip(),
        row.get("cond", "").strip(),
        row.get("wo", "").strip(),
        row.get("ppt.no", "").strip(),
    )


def load_trial_bins(
    data_csv: Path,
    max_ms: int,
    bin_ms: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    sample_counts: dict[tuple[tuple[str, str, str, str, str, str], int], Counter[str]] = defaultdict(Counter)
    trial_meta: dict[tuple[str, str, str, str, str, str], dict[str, object]] = {}

    with data_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sentence_type = row.get("type", "").strip()
            if sentence_type not in {"act", "pass"}:
                continue

            sample_ms = parse_int(row.get("ms", ""))
            sol = parse_float(row.get("sol", ""))
            if sample_ms is None or sol is None or sample_ms < 1 or sample_ms > max_ms:
                continue

            key = trial_key(row)
            trial_meta.setdefault(
                key,
                {
                    "participant": key[0],
                    "item": key[1],
                    "type": sentence_type,
                    "condition": key[3],
                    "word_order": key[4],
                    "sol": sol,
                },
            )

            bin_start = ((sample_ms - 1) // bin_ms) * bin_ms
            counts = sample_counts[(key, bin_start)]
            counts["samples"] += 1
            if is_one(row.get("agent", "")):
                counts["agent"] += 1
            if is_one(row.get("patient", "")):
                counts["patient"] += 1

    trial_bin_rows: list[dict[str, object]] = []
    for (key, bin_start), counts in sorted(sample_counts.items(), key=lambda item: (item[0][0], item[0][1])):
        if counts["samples"] == 0:
            continue
        meta = trial_meta[key]
        trial_bin_rows.append(
            {
                "participant": meta["participant"],
                "item": meta["item"],
                "type": meta["type"],
                "condition": meta["condition"],
                "word_order": meta["word_order"],
                "sol": meta["sol"],
                "time_ms": bin_start,
                "agent_prop": counts["agent"] / counts["samples"],
                "patient_prop": counts["patient"] / counts["samples"],
                "n_samples": counts["samples"],
            }
        )

    trial_rows = [
        {
            "participant": meta["participant"],
            "item": meta["item"],
            "type": meta["type"],
            "condition": meta["condition"],
            "word_order": meta["word_order"],
            "sol": meta["sol"],
        }
        for _key, meta in sorted(trial_meta.items())
    ]
    return trial_bin_rows, trial_rows


def summarize_plot_rows(trial_bin_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, int], list[float]] = defaultdict(list)

    for row in trial_bin_rows:
        for referent, col in [("agent", "agent_prop"), ("patient", "patient_prop")]:
            grouped[(str(row["type"]), referent, int(row["time_ms"]))].append(float(row[col]))

    summary_rows: list[dict[str, object]] = []
    for (sentence_type, referent, time_ms), values in sorted(grouped.items()):
        prop_mean = mean(values)
        prop_sd = sd(values)
        n_trial_bins = len(values)
        se2 = 2 * prop_sd / math.sqrt(n_trial_bins) if n_trial_bins else 0.0
        summary_rows.append(
            {
                "type": sentence_type,
                "referent": referent,
                "time_ms": time_ms,
                "mean_prop": prop_mean,
                "sd_prop": prop_sd,
                "n_trial_bins": n_trial_bins,
                "lower": max(0.0, prop_mean - se2),
                "upper": min(1.0, prop_mean + se2),
            }
        )

    return summary_rows


def summarize_trials(trial_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_type: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in trial_rows:
        if row["type"] in {"act", "pass"}:
            by_type[str(row["type"])].append(row)

    out: list[dict[str, object]] = []
    for sentence_type in ["act", "pass"]:
        rows = by_type[sentence_type]
        sols = [float(row["sol"]) for row in rows]
        out.append(
            {
                "type": sentence_type,
                "n_trials": len(rows),
                "n_participants": len({str(row["participant"]) for row in rows}),
                "mean_speech_onset_ms": mean(sols),
                "median_speech_onset_ms": sorted(sols)[len(sols) // 2]
                if len(sols) % 2 == 1
                else mean(sorted(sols)[len(sols) // 2 - 1 : len(sols) // 2 + 1]),
                "min_speech_onset_ms": min(sols),
                "max_speech_onset_ms": max(sols),
            }
        )
    return out


def svg_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    return " ".join(
        ("M" if index == 0 else "L") + f"{x:.2f},{y:.2f}"
        for index, (x, y) in enumerate(points)
    )


def render_graph_svg(
    path: Path,
    rows: list[dict[str, object]],
    sentence_type: str,
    n_trials: int,
    mean_onset_ms: float,
    max_ms: int,
) -> None:
    width = 900
    height = 560
    left = 86
    right = 820
    top = 72
    bottom = 470
    y_min = 0.0
    y_max = 1.0

    def sx(x: float) -> float:
        return left + (x / max_ms) * (right - left)

    def sy(y: float) -> float:
        return bottom - (y - y_min) / (y_max - y_min) * (bottom - top)

    by_ref: dict[str, list[dict[str, object]]] = {"agent": [], "patient": []}
    for row in rows:
        by_ref[str(row["referent"])].append(row)
    for referent_rows in by_ref.values():
        referent_rows.sort(key=lambda item: float(item["time_ms"]))

    title_label = "Active sentences" if sentence_type == "act" else "Passive sentences"
    onset_label = f"{mean_onset_ms:.0f} ms"
    title = f"Khanty Speech Planning: {title_label}"
    subtitle = f"0-3500 ms from sentence display; 50-ms bins; n = {n_trials} trials"

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
    label_y = top + 20
    parts.append(
        f'<rect x="{label_x - 6:.2f}" y="{label_y - 15:.2f}" width="80" height="22" '
        'fill="white" opacity="0.92"/>'
    )
    parts.append(f'<text class="onset" x="{label_x:.2f}" y="{label_y:.2f}">{html.escape(onset_label)}</text>')

    for referent, color in [("agent", AGENT_COLOR), ("patient", PATIENT_COLOR)]:
        referent_rows = by_ref[referent]
        upper = [(sx(float(row["time_ms"])), sy(float(row["upper"]))) for row in referent_rows]
        lower = [(sx(float(row["time_ms"])), sy(float(row["lower"]))) for row in reversed(referent_rows)]
        polygon_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in upper + lower)
        line_points = [(sx(float(row["time_ms"])), sy(float(row["mean_prop"]))) for row in referent_rows]
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


def write_graphs(
    output_dir: Path,
    summary_rows: list[dict[str, object]],
    trial_summary_rows: list[dict[str, object]],
    max_ms: int,
) -> list[Path]:
    by_type = {str(row["type"]): row for row in trial_summary_rows}
    graph_paths: list[Path] = []

    for sentence_type, filename_type in [("act", "actives"), ("pass", "passives")]:
        rows = [row for row in summary_rows if row["type"] == sentence_type]
        if not rows:
            continue
        graph_path = output_dir / f"khanty_all_{filename_type}_speech_planning_0_{max_ms}ms.svg"
        meta = by_type[sentence_type]
        render_graph_svg(
            graph_path,
            rows,
            sentence_type=sentence_type,
            n_trials=int(meta["n_trials"]),
            mean_onset_ms=float(meta["mean_speech_onset_ms"]),
            max_ms=max_ms,
        )
        graph_paths.append(graph_path)

    return graph_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create all-active and all-passive Khanty speech-planning graphs from generated CSV data."
    )
    parser.add_argument("--data-csv", default="osfstorage-archive/data_all.csv")
    parser.add_argument("--output-dir", default="output/khanty_active_passive_speech_planning_graphs")
    parser.add_argument("--max-ms", type=int, default=3500)
    parser.add_argument("--bin-ms", type=int, default=50)
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()

    data_csv = Path(args.data_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    trial_bin_rows, trial_rows = load_trial_bins(data_csv=data_csv, max_ms=args.max_ms, bin_ms=args.bin_ms)
    summary_rows = summarize_plot_rows(trial_bin_rows)
    trial_summary_rows = summarize_trials(trial_rows)

    write_pretty_csv(output_dir / "khanty_active_passive_speech_planning_trial_bins.csv", trial_bin_rows)
    write_pretty_csv(output_dir / "khanty_active_passive_speech_planning_plot_data.csv", summary_rows)
    write_pretty_csv(output_dir / "khanty_active_passive_speech_planning_onsets.csv", trial_summary_rows)

    plotted_bins = Counter((str(row["type"]), int(row["time_ms"])) for row in trial_bin_rows)
    count_rows = [
        {"type": sentence_type, "time_ms": time_ms, "n_trial_bins": count}
        for (sentence_type, time_ms), count in sorted(plotted_bins.items())
    ]
    write_pretty_csv(output_dir / "khanty_active_passive_speech_planning_counts_by_bin.csv", count_rows)

    graph_paths = write_graphs(output_dir, summary_rows, trial_summary_rows, max_ms=args.max_ms)
    if not args.no_pdf:
        for graph_path in graph_paths:
            convert_svg_to_pdf(graph_path)

    print(f"Read {len(trial_rows)} clean trials from {data_csv}")
    for row in trial_summary_rows:
        label = "actives" if row["type"] == "act" else "passives"
        print(
            f"{label}: n={row['n_trials']}, "
            f"mean speech onset={float(row['mean_speech_onset_ms']):.0f} ms"
        )
    output_kinds = "SVG graphs" if args.no_pdf else "SVG graphs and PDF copies"
    print(f"Wrote {len(graph_paths)} {output_kinds} to {output_dir}")


if __name__ == "__main__":
    main()
