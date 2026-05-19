#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from svg_to_pdf import convert_svg_to_pdf


AGENT_COLOR = "#CC3311"
PATIENT_COLOR = "#0077BB"
MEAN_ONSET_COLOR = "#333333"

SAMPLE_RE = re.compile(r"^\s*(\d+)\s+([-\d.]+|\.)\s+([-\d.]+|\.)\s+([-\d.]+|\.)")
DISPLAY_RE = re.compile(r"^MSG\s+(\d+)\s+.*DISPLAY_SENTENCE")
TRIAL_VAR_RE = re.compile(r"!V\s+TRIAL_VAR\s+(\S+)\s*(.*)$")
EXPERIMENT_SENTENCE_RE = re.compile(r"^e(\d+)_")
COORD_RE = re.compile(r"\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)")


@dataclass
class BehaviorTrial:
    participant: str
    item: int
    sentence_type: str
    condition: str
    repetition: str
    word_order: str
    sol: float
    participant_no: str


@dataclass
class AscTrial:
    asc_file: str
    block: int
    display_time: int | None = None
    vars: dict[str, str] = field(default_factory=dict)
    samples: list[tuple[int, float | None, float | None]] = field(default_factory=list)


def parse_float(value: object) -> float | None:
    text = str(value).strip().replace(",", ".")
    if not text or text == ".":
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    if math.isnan(out):
        return None
    return out


def parse_coord(value: object) -> tuple[float | None, float | None]:
    match = COORD_RE.search(str(value))
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def sd(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((value - m) ** 2 for value in values) / (len(values) - 1))


def median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return mean(ordered[middle - 1 : middle + 1])


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


def participant_candidates(asc_stem: str) -> list[str]:
    collapsed = re.sub(r"__+", "_", asc_stem)
    if collapsed == asc_stem:
        return [asc_stem]
    return [asc_stem, collapsed]


def load_behavior(path: Path) -> dict[tuple[str, int], BehaviorTrial]:
    trials: dict[tuple[str, int], BehaviorTrial] = {}

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            participant = row.get("ppt_id", "").strip()
            item = int(float(row.get("item ", row.get("item", "0"))))
            sentence_type = row.get("type", "").strip()
            repetition = row.get("rep", "")
            sol = parse_float(row.get("sol", ""))

            if sol is None:
                continue
            if sol > 6500 or repetition != "ok" or sentence_type == "NA":
                continue
            if sentence_type not in {"act", "pass"}:
                continue

            trials[(participant, item)] = BehaviorTrial(
                participant=participant,
                item=item,
                sentence_type=sentence_type,
                condition=row.get("cond", "").strip(),
                repetition=repetition,
                word_order=row.get("wo", "").strip(),
                sol=sol,
                participant_no=row.get("ppt.no", "").strip(),
            )

    return trials


def parse_asc_trials(path: Path, max_ms: int) -> list[AscTrial]:
    trials: list[AscTrial] = []
    current: AscTrial | None = None
    last_ended: AscTrial | None = None

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("START"):
                current = AscTrial(asc_file=path.name, block=len(trials) + 1)
                trials.append(current)
                last_ended = None
                continue

            if line.startswith("END"):
                last_ended = current
                current = None
                continue

            if line.startswith("MSG"):
                display_match = DISPLAY_RE.search(line)
                if display_match and current is not None:
                    current.display_time = int(display_match.group(1))

                var_match = TRIAL_VAR_RE.search(line)
                if var_match and last_ended is not None:
                    last_ended.vars[var_match.group(1)] = var_match.group(2).strip()
                continue

            if current is None or current.display_time is None:
                continue

            sample_match = SAMPLE_RE.match(line)
            if not sample_match:
                continue

            sample_time = int(sample_match.group(1))
            rel_ms = sample_time - current.display_time
            if rel_ms < 0:
                continue
            if rel_ms >= max_ms:
                continue

            current.samples.append(
                (
                    rel_ms,
                    parse_float(sample_match.group(2)),
                    parse_float(sample_match.group(3)),
                )
            )

    return trials


def classify_aoi(
    x: float | None,
    y: float | None,
    agent_coord: object,
    patient_coord: object,
) -> str:
    if x is None or y is None:
        return "other"

    ax, ay = parse_coord(agent_coord)
    px, py = parse_coord(patient_coord)

    def in_rect(coord_x: float | None, coord_y: float | None) -> bool:
        if coord_x is None or coord_y is None:
            return False
        if coord_x == 0 and coord_y == 0:
            return False

        if coord_x >= 500:
            left, right = 960.0, 1773.0
        else:
            left, right = 147.0, 960.0
        return left <= x <= right and 122.0 <= y <= 1039.0

    in_agent = in_rect(ax, ay)
    in_patient = in_rect(px, py)

    if in_agent and not in_patient:
        return "agent"
    if in_patient and not in_agent:
        return "patient"

    # Boundary samples can land at x=960. Match the old R extraction's
    # right-side-first behavior by assigning the boundary to the right AOI.
    if in_agent and in_patient and x >= 960:
        return "agent" if ax is not None and ax >= 500 else "patient"
    if in_agent and in_patient:
        return "agent" if ax is not None and ax < 500 else "patient"

    return "other"


def asc_experiment_item(trial: AscTrial) -> int | None:
    if trial.display_time is None:
        return None
    if trial.vars.get("Trial_Recycled_", "").strip() == "True":
        return None
    match = EXPERIMENT_SENTENCE_RE.match(trial.vars.get("sentence", "").strip())
    if not match:
        return None
    return int(match.group(1))


def accumulate_trial_bins(
    asc_dir: Path,
    behavior_trials: dict[tuple[str, int], BehaviorTrial],
    max_ms: int,
    bin_ms: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    behavior_participants = {participant for participant, _item in behavior_trials}
    trial_bin_rows: list[dict[str, object]] = []
    merge_rows: list[dict[str, object]] = []
    seen_clean_trials: set[tuple[str, int]] = set()

    for asc_path in sorted(asc_dir.glob("*.asc")):
        asc_stem = asc_path.stem
        participant = next(
            (candidate for candidate in participant_candidates(asc_stem) if candidate in behavior_participants),
            asc_stem,
        )
        parsed_trials = parse_asc_trials(asc_path, max_ms=max_ms)
        experimental_trials = 0
        clean_trials = 0
        clean_complete_3500 = 0

        for asc_trial in parsed_trials:
            item = asc_experiment_item(asc_trial)
            if item is None:
                continue

            experimental_trials += 1
            behavior = behavior_trials.get((participant, item))
            if behavior is None:
                continue

            clean_trials += 1
            seen_clean_trials.add((participant, item))

            counts_by_bin: dict[int, Counter[str]] = defaultdict(Counter)
            for rel_ms, x, y in asc_trial.samples:
                bin_start_ms = (rel_ms // bin_ms) * bin_ms
                who = classify_aoi(
                    x,
                    y,
                    asc_trial.vars.get("agens", ""),
                    asc_trial.vars.get("patiens", ""),
                )
                counts = counts_by_bin[bin_start_ms]
                counts["samples"] += 1
                counts[who] += 1

            if any(int(bin_start) == max_ms - bin_ms for bin_start in counts_by_bin):
                clean_complete_3500 += 1

            for bin_start_ms, counts in sorted(counts_by_bin.items()):
                n_samples = counts["samples"]
                if n_samples == 0:
                    continue
                trial_bin_rows.append(
                    {
                        "participant": participant,
                        "ppt_no": behavior.participant_no,
                        "asc_file": asc_path.name,
                        "asc_block": asc_trial.block,
                        "item": item,
                        "type": behavior.sentence_type,
                        "condition": behavior.condition,
                        "word_order": behavior.word_order,
                        "speech_onset_ms": behavior.sol,
                        "time_bin_start_ms": bin_start_ms,
                        "time_bin_end_ms": min(bin_start_ms + bin_ms, max_ms),
                        "agent_prop": counts["agent"] / n_samples,
                        "patient_prop": counts["patient"] / n_samples,
                        "other_prop": counts["other"] / n_samples,
                        "n_samples": n_samples,
                    }
                )

        merge_rows.append(
            {
                "asc_file": asc_path.name,
                "participant": participant,
                "parsed_trials": len(parsed_trials),
                "experimental_trials_with_display": experimental_trials,
                "clean_behavior_trials_merged": clean_trials,
                "clean_trials_with_last_50ms_bin": clean_complete_3500,
            }
        )

    missing_rows: list[dict[str, object]] = []
    for (participant, item), behavior in sorted(behavior_trials.items()):
        if (participant, item) in seen_clean_trials:
            continue
        missing_rows.append(
            {
                "participant": participant,
                "item": item,
                "type": behavior.sentence_type,
                "condition": behavior.condition,
                "word_order": behavior.word_order,
                "speech_onset_ms": behavior.sol,
            }
        )

    return trial_bin_rows, merge_rows, missing_rows


def summarize_plot_rows(trial_bin_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, int], list[float]] = defaultdict(list)

    for row in trial_bin_rows:
        for referent, col in [("agent", "agent_prop"), ("patient", "patient_prop")]:
            grouped[(str(row["type"]), referent, int(row["time_bin_start_ms"]))].append(float(row[col]))

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
                "time_bin_start_ms": time_ms,
                "mean_prop": prop_mean,
                "sd_prop": prop_sd,
                "n_trial_bins": n_trial_bins,
                "lower": max(0.0, prop_mean - se2),
                "upper": min(1.0, prop_mean + se2),
            }
        )

    return summary_rows


def summarize_onsets(
    behavior_trials: dict[tuple[str, int], BehaviorTrial],
    trial_bin_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    plotted_trials = {
        (str(row["participant"]), int(row["item"]))
        for row in trial_bin_rows
    }
    by_type: dict[str, list[BehaviorTrial]] = defaultdict(list)
    for key, trial in behavior_trials.items():
        if key in plotted_trials:
            by_type[trial.sentence_type].append(trial)

    rows: list[dict[str, object]] = []
    for sentence_type in ["act", "pass"]:
        trials = by_type[sentence_type]
        onsets = [trial.sol for trial in trials]
        rows.append(
            {
                "type": sentence_type,
                "n_trials": len(trials),
                "n_participants": len({trial.participant for trial in trials}),
                "mean_speech_onset_ms": mean(onsets),
                "median_speech_onset_ms": median(onsets),
                "min_speech_onset_ms": min(onsets),
                "max_speech_onset_ms": max(onsets),
            }
        )
    return rows


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
        referent_rows.sort(key=lambda item: float(item["time_bin_start_ms"]))

    title_label = "Active sentences" if sentence_type == "act" else "Passive sentences"
    onset_label = f"{mean_onset_ms:.0f} ms"
    title = f"Khanty Speech Planning From ASCs: {title_label}"
    subtitle = f"0-3500 ms from display; 50-ms trial bins; n = {n_trials}; dashed line = mean speech onset"

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


def write_graphs(
    output_dir: Path,
    summary_rows: list[dict[str, object]],
    onset_rows: list[dict[str, object]],
    max_ms: int,
) -> list[Path]:
    onset_by_type = {str(row["type"]): row for row in onset_rows}
    graph_paths: list[Path] = []

    for sentence_type, filename_type in [("act", "actives"), ("pass", "passives")]:
        rows = [row for row in summary_rows if row["type"] == sentence_type]
        if not rows:
            continue
        onset = onset_by_type[sentence_type]
        graph_path = output_dir / f"khanty_asc_all_{filename_type}_speech_planning_0_{max_ms}ms.svg"
        render_graph_svg(
            graph_path,
            rows,
            sentence_type=sentence_type,
            n_trials=int(onset["n_trials"]),
            mean_onset_ms=float(onset["mean_speech_onset_ms"]),
            max_ms=max_ms,
        )
        graph_paths.append(graph_path)

    return graph_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create active/passive Khanty speech-planning graphs from raw ASC files."
    )
    parser.add_argument("--behavior-csv", default="osfstorage-archive/for_r_1.csv")
    parser.add_argument("--asc-dir", default="osfstorage-archive/ascs")
    parser.add_argument("--output-dir", default="output/khanty_asc_active_passive_speech_planning_graphs")
    parser.add_argument("--max-ms", type=int, default=3500)
    parser.add_argument("--bin-ms", type=int, default=50)
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()

    behavior_csv = Path(args.behavior_csv)
    asc_dir = Path(args.asc_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    behavior_trials = load_behavior(behavior_csv)
    trial_bin_rows, merge_rows, missing_rows = accumulate_trial_bins(
        asc_dir=asc_dir,
        behavior_trials=behavior_trials,
        max_ms=args.max_ms,
        bin_ms=args.bin_ms,
    )
    summary_rows = summarize_plot_rows(trial_bin_rows)
    onset_rows = summarize_onsets(behavior_trials, trial_bin_rows)

    write_pretty_csv(output_dir / "khanty_asc_speech_planning_trial_bins_50ms.csv", trial_bin_rows)
    write_pretty_csv(output_dir / "khanty_asc_speech_planning_plot_data.csv", summary_rows)
    write_pretty_csv(output_dir / "khanty_asc_speech_planning_onsets.csv", onset_rows)
    write_pretty_csv(output_dir / "khanty_asc_speech_planning_merge_notes.csv", merge_rows)
    write_pretty_csv(output_dir / "khanty_asc_speech_planning_missing_clean_trials.csv", missing_rows)

    graph_paths = write_graphs(output_dir, summary_rows, onset_rows, max_ms=args.max_ms)
    if not args.no_pdf:
        for graph_path in graph_paths:
            convert_svg_to_pdf(graph_path)

    print(f"Clean behavior trials: {len(behavior_trials)}")
    print(f"Merged clean ASC trials: {len({(row['participant'], row['item']) for row in trial_bin_rows})}")
    for row in onset_rows:
        label = "actives" if row["type"] == "act" else "passives"
        print(
            f"{label}: n={row['n_trials']}, "
            f"mean speech onset={float(row['mean_speech_onset_ms']):.0f} ms"
        )
    print(f"Missing clean behavior trials: {len(missing_rows)}")
    output_kinds = "SVG graphs" if args.no_pdf else "SVG graphs and PDF copies"
    print(f"Wrote {len(graph_paths)} {output_kinds} to {output_dir}")


if __name__ == "__main__":
    main()
