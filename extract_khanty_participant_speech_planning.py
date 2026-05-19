#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path


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


def trial_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        row.get("ppt_id", "").strip(),
        row.get("item", "").strip(),
        row.get("type", "").strip(),
        row.get("cond", "").strip(),
        row.get("wo", "").strip(),
        row.get("ppt.no", "").strip(),
    )


def safe_filename(value: object) -> str:
    keep = []
    for char in str(value).strip():
        if char.isalnum() or char in {"-", "_"}:
            keep.append(char)
        else:
            keep.append("_")
    return "".join(keep) or "unknown_participant"


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        fieldnames = list(rows[0].keys())

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: fmt_num(row.get(key, "")) for key in fieldnames})


def load_extracted_rows(data_csv: Path, max_ms: int) -> tuple[list[dict[str, object]], list[str]]:
    extracted_rows: list[dict[str, object]] = []

    with data_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return [], []
        source_fieldnames = reader.fieldnames

        for row in reader:
            sentence_type = row.get("type", "").strip()
            sample_ms = parse_int(row.get("ms", ""))
            if sentence_type not in {"act", "pass"} or sample_ms is None:
                continue
            if not (1 <= sample_ms <= max_ms):
                continue

            out_row: dict[str, object] = dict(row)
            out_row["time_from_display_ms"] = sample_ms - 1
            out_row["sample_ms_1based"] = sample_ms
            extracted_rows.append(out_row)

    fieldnames = [
        "time_from_display_ms",
        "sample_ms_1based",
        *source_fieldnames,
    ]
    return extracted_rows, fieldnames


def summarize_trials(extracted_rows: list[dict[str, object]], max_ms: int) -> list[dict[str, object]]:
    trial_meta: dict[tuple[str, str, str, str, str, str], dict[str, object]] = {}
    max_sample_by_trial: dict[tuple[str, str, str, str, str, str], int] = defaultdict(int)
    samples_by_trial: Counter[tuple[str, str, str, str, str, str]] = Counter()

    for row in extracted_rows:
        key = trial_key(row)  # type: ignore[arg-type]
        sample_ms = int(row["sample_ms_1based"])
        sol = parse_float(row.get("sol", "")) or 0.0
        trial_meta.setdefault(
            key,
            {
                "participant": key[0],
                "item": key[1],
                "type": key[2],
                "condition": key[3],
                "word_order": key[4],
                "sol": sol,
            },
        )
        max_sample_by_trial[key] = max(max_sample_by_trial[key], sample_ms)
        samples_by_trial[key] += 1

    rows: list[dict[str, object]] = []
    for key, meta in sorted(trial_meta.items()):
        rows.append(
            {
                "participant": meta["participant"],
                "item": meta["item"],
                "type": meta["type"],
                "condition": meta["condition"],
                "word_order": meta["word_order"],
                "sol": meta["sol"],
                "reaches_3500ms": "yes" if max_sample_by_trial[key] >= max_ms else "no",
                "last_available_sample_ms_1based": max_sample_by_trial[key],
                "n_extracted_samples": samples_by_trial[key],
            }
        )

    return rows


def coverage_summary(trial_rows: list[dict[str, object]], extracted_rows: list[dict[str, object]], max_ms: int) -> list[dict[str, object]]:
    trial_rows_by_participant: dict[str, list[dict[str, object]]] = defaultdict(list)
    extracted_samples_by_participant: Counter[str] = Counter()

    for row in trial_rows:
        trial_rows_by_participant[str(row["participant"])].append(row)
    for row in extracted_rows:
        extracted_samples_by_participant[str(row.get("ppt_id", ""))] += 1

    summary_rows: list[dict[str, object]] = []
    for participant, rows in sorted(trial_rows_by_participant.items()):
        sols = [float(row["sol"]) for row in rows]
        last_samples = [int(row["last_available_sample_ms_1based"]) for row in rows]
        reaches = [row for row in rows if row["reaches_3500ms"] == "yes"]
        type_counts = Counter(str(row["type"]) for row in rows)
        summary_rows.append(
            {
                "participant": participant,
                "n_trials": len(rows),
                "n_active_trials": type_counts["act"],
                "n_passive_trials": type_counts["pass"],
                "n_trials_reaching_3500ms": len(reaches),
                "percent_trials_reaching_3500ms": 100 * len(reaches) / len(rows) if rows else 0.0,
                "mean_speech_onset_ms": mean(sols),
                "min_speech_onset_ms": min(sols),
                "max_speech_onset_ms": max(sols),
                "max_available_sample_ms_1based": max(last_samples),
                "n_extracted_samples": extracted_samples_by_participant[participant],
            }
        )

    total_trials = len(trial_rows)
    total_reaching = sum(1 for row in trial_rows if row["reaches_3500ms"] == "yes")
    all_sols = [float(row["sol"]) for row in trial_rows]
    summary_rows.append(
        {
            "participant": "ALL",
            "n_trials": total_trials,
            "n_active_trials": sum(1 for row in trial_rows if row["type"] == "act"),
            "n_passive_trials": sum(1 for row in trial_rows if row["type"] == "pass"),
            "n_trials_reaching_3500ms": total_reaching,
            "percent_trials_reaching_3500ms": 100 * total_reaching / total_trials if total_trials else 0.0,
            "mean_speech_onset_ms": mean(all_sols),
            "min_speech_onset_ms": min(all_sols),
            "max_speech_onset_ms": max(all_sols),
            "max_available_sample_ms_1based": max(int(row["last_available_sample_ms_1based"]) for row in trial_rows),
            "n_extracted_samples": len(extracted_rows),
        }
    )
    return summary_rows


def trial_bin_summary(
    extracted_rows: list[dict[str, object]],
    max_ms: int,
    bin_ms: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    counts_by_trial_bin: dict[tuple[tuple[str, str, str, str, str, str], int], Counter[str]] = defaultdict(Counter)
    meta_by_trial: dict[tuple[str, str, str, str, str, str], dict[str, object]] = {}

    for row in extracted_rows:
        key = trial_key(row)  # type: ignore[arg-type]
        sample_ms = int(row["sample_ms_1based"])
        bin_start_ms = ((sample_ms - 1) // bin_ms) * bin_ms
        if bin_start_ms >= max_ms:
            continue

        meta_by_trial.setdefault(
            key,
            {
                "participant": key[0],
                "item": key[1],
                "type": key[2],
                "condition": key[3],
                "word_order": key[4],
                "sol": parse_float(row.get("sol", "")) or 0.0,
            },
        )
        counts = counts_by_trial_bin[(key, bin_start_ms)]
        counts["samples"] += 1
        if is_one(row.get("agent", "")):
            counts["agent"] += 1
        if is_one(row.get("patient", "")):
            counts["patient"] += 1

    trial_bin_rows: list[dict[str, object]] = []
    for (key, bin_start_ms), counts in sorted(counts_by_trial_bin.items(), key=lambda item: (item[0][0], item[0][1])):
        meta = meta_by_trial[key]
        n_samples = counts["samples"]
        trial_bin_rows.append(
            {
                "participant": meta["participant"],
                "item": meta["item"],
                "type": meta["type"],
                "condition": meta["condition"],
                "word_order": meta["word_order"],
                "sol": meta["sol"],
                "time_bin_start_ms": bin_start_ms,
                "time_bin_end_ms": min(bin_start_ms + bin_ms, max_ms),
                "agent_prop": counts["agent"] / n_samples if n_samples else 0.0,
                "patient_prop": counts["patient"] / n_samples if n_samples else 0.0,
                "n_samples": n_samples,
            }
        )

    participant_grouped: dict[tuple[str, str, str, int], list[float]] = defaultdict(list)
    for row in trial_bin_rows:
        for referent, col in [("agent", "agent_prop"), ("patient", "patient_prop")]:
            participant_grouped[
                (str(row["participant"]), str(row["type"]), referent, int(row["time_bin_start_ms"]))
            ].append(float(row[col]))

    participant_summary_rows: list[dict[str, object]] = []
    for (participant, sentence_type, referent, bin_start_ms), values in sorted(participant_grouped.items()):
        prop_mean = mean(values)
        prop_sd = sd(values)
        n_trial_bins = len(values)
        se2 = 2 * prop_sd / math.sqrt(n_trial_bins) if n_trial_bins else 0.0
        participant_summary_rows.append(
            {
                "participant": participant,
                "type": sentence_type,
                "referent": referent,
                "time_bin_start_ms": bin_start_ms,
                "time_bin_end_ms": min(bin_start_ms + bin_ms, max_ms),
                "mean_prop": prop_mean,
                "sd_prop": prop_sd,
                "n_trial_bins": n_trial_bins,
                "lower": max(0.0, prop_mean - se2),
                "upper": min(1.0, prop_mean + se2),
            }
        )

    return trial_bin_rows, participant_summary_rows


def write_participant_files(
    participant_dir: Path,
    extracted_rows: list[dict[str, object]],
    fieldnames: list[str],
) -> int:
    participant_dir.mkdir(parents=True, exist_ok=True)
    rows_by_participant: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in extracted_rows:
        rows_by_participant[str(row.get("ppt_id", ""))].append(row)

    for participant, rows in sorted(rows_by_participant.items()):
        participant_path = participant_dir / f"{safe_filename(participant)}_speech_planning_0_3500ms.csv"
        write_csv(participant_path, rows, fieldnames)

    return len(rows_by_participant)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract the first 3500 ms of Khanty speech-planning data for each participant."
    )
    parser.add_argument("--data-csv", default="osfstorage-archive/data_all.csv")
    parser.add_argument("--output-dir", default="output/khanty_participant_speech_planning_0_3500ms")
    parser.add_argument("--max-ms", type=int, default=3500)
    parser.add_argument("--bin-ms", type=int, default=50)
    args = parser.parse_args()

    data_csv = Path(args.data_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted_rows, extracted_fieldnames = load_extracted_rows(data_csv, max_ms=args.max_ms)
    trial_rows = summarize_trials(extracted_rows, max_ms=args.max_ms)
    coverage_rows = coverage_summary(trial_rows, extracted_rows, max_ms=args.max_ms)
    trial_bin_rows, participant_summary_rows = trial_bin_summary(
        extracted_rows,
        max_ms=args.max_ms,
        bin_ms=args.bin_ms,
    )

    write_csv(
        output_dir / "khanty_speech_planning_0_3500ms_all_participants.csv",
        extracted_rows,
        extracted_fieldnames,
    )
    n_participants = write_participant_files(
        output_dir / "participants",
        extracted_rows,
        extracted_fieldnames,
    )
    write_csv(output_dir / "khanty_speech_planning_0_3500ms_trials.csv", trial_rows)
    write_csv(output_dir / "khanty_speech_planning_0_3500ms_coverage_by_participant.csv", coverage_rows)
    write_csv(output_dir / "khanty_speech_planning_0_3500ms_trial_bins_50ms.csv", trial_bin_rows)
    write_csv(output_dir / "khanty_speech_planning_0_3500ms_participant_bin_means_50ms.csv", participant_summary_rows)

    overall = coverage_rows[-1]
    print(f"Extracted {len(extracted_rows)} samples from {len(trial_rows)} trials and {n_participants} participants.")
    print(
        f"Trials reaching {args.max_ms} ms before speech onset: "
        f"{overall['n_trials_reaching_3500ms']}/{overall['n_trials']} "
        f"({float(overall['percent_trials_reaching_3500ms']):.1f}%)."
    )
    print(f"Wrote outputs to {output_dir}")


if __name__ == "__main__":
    main()
