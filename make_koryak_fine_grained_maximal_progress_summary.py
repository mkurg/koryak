#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import math
from datetime import datetime
from pathlib import Path


BASE_DIR = Path("output/koryak_brms_fine_grained_pairwise_maximal")
OUT_DIR = Path("output/koryak_brms_fine_grained_pairwise_maximal_progress_summary")
HTML_PATH = OUT_DIR / "koryak_fine_grained_pairwise_maximal_progress_summary.html"

WINDOWS = [
    ("le1", "Linguistic encoding 1"),
    ("le3", "Linguistic encoding 3"),
]

CONTRASTS = [
    (
        "direct_1_1_animate_vs_direct_1_2_animate",
        "Direct 1-1 animate patient vs direct 1-2 animate patient",
    ),
    (
        "direct_1_1_inanimate_vs_direct_1_2_inanimate",
        "Direct 1-1 inanimate patient vs direct 1-2 inanimate patient",
    ),
    (
        "inverse_2_2_animate_vs_inverse_2_1_animate",
        "Inverse 2-2 animate patient vs inverse 2-1 animate patient",
    ),
    (
        "direct_1_1_animate_vs_inverse_2_2_animate",
        "Direct 1-1 animate patient vs inverse 2-2 animate patient",
    ),
    (
        "direct_1_1_inanimate_vs_inverse_2_2_inanimate",
        "Direct 1-1 inanimate patient vs inverse 2-2 inanimate patient",
    ),
]

TERM_LABELS = {
    "Intercept": "Intercept",
    "polytimedegreeEQ31": "Time 1",
    "polytimedegreeEQ32": "Time 2",
    "polytimedegreeEQ33": "Time 3",
    "contrast_code": "Main contrast",
    "polytimedegreeEQ31:contrast_code": "Time 1 x contrast",
    "polytimedegreeEQ32:contrast_code": "Time 2 x contrast",
    "polytimedegreeEQ33:contrast_code": "Time 3 x contrast",
}

CONTRAST_TERMS = {
    "contrast_code",
    "polytimedegreeEQ31:contrast_code",
    "polytimedegreeEQ32:contrast_code",
    "polytimedegreeEQ33:contrast_code",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_float(value: object) -> float | None:
    text = str(value).strip()
    if text in {"", "NA", "NaN", "nan", "None"}:
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    if math.isnan(out):
        return None
    return out


def fmt(value: object, digits: int = 3) -> str:
    value_float = parse_float(value)
    if value_float is None:
        return ""
    if abs(value_float) < 0.0005 and value_float != 0:
        return f"{value_float:.2e}"
    return f"{value_float:.{digits}f}"


def fmt_int(value: object) -> str:
    value_float = parse_float(value)
    if value_float is None:
        return ""
    return str(int(round(value_float)))


def ci(lower: object, upper: object, digits: int = 3) -> str:
    if parse_float(lower) is None or parse_float(upper) is None:
        return ""
    return f"[{fmt(lower, digits)}, {fmt(upper, digits)}]"


def esc(value: object) -> str:
    return html.escape(str(value))


def credible(row: dict[str, str], low_key: str = "ci_95_lower", high_key: str = "ci_95_upper") -> bool:
    lower = parse_float(row.get(low_key))
    upper = parse_float(row.get(high_key))
    return lower is not None and upper is not None and ((lower > 0 and upper > 0) or (lower < 0 and upper < 0))


def html_table(headers: list[str], rows: list[list[object]], cls: str = "") -> str:
    out = [f'<table class="{cls}">', "<thead><tr>"]
    out.extend(f"<th>{esc(header)}</th>" for header in headers)
    out.append("</tr></thead><tbody>")
    for row in rows:
        row_class = ""
        cells = row
        if row and isinstance(row[-1], dict):
            meta = row[-1]
            cells = row[:-1]
            if meta.get("credible"):
                row_class = ' class="credible"'
            elif meta.get("warning"):
                row_class = ' class="warning"'
            elif meta.get("partial"):
                row_class = ' class="partial"'
        out.append(f"<tr{row_class}>")
        out.extend(f"<td>{cell}</td>" for cell in cells)
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def prefix(window: str, contrast_id: str) -> str:
    return f"brms_{window}_{contrast_id}_maximal"


def files_for(window: str, contrast_id: str) -> dict[str, Path]:
    directory = BASE_DIR / window / contrast_id
    base = prefix(window, contrast_id)
    return {
        "dir": directory,
        "fixed": directory / f"{base}_fixed_effects.csv",
        "diagnostics": directory / f"{base}_diagnostics.csv",
        "all_diagnostics": directory / f"{base}_all_parameter_diagnostics.csv",
        "sampler": directory / f"{base}_sampler_diagnostics.csv",
        "counts": directory / f"{base}_counts.csv",
        "run_config": directory / "run_config.csv",
        "agent_rds": directory / f"{base}_agent.rds",
        "patient_rds": directory / f"{base}_patient.rds",
        "log": directory / f"{window}_{contrast_id}_maximal_full_run.log",
    }


def status_for(window: str, contrast_id: str) -> tuple[str, str]:
    paths = files_for(window, contrast_id)
    if not paths["dir"].exists():
        return "not started", "No output folder yet"

    complete_files = ["fixed", "diagnostics", "all_diagnostics", "sampler", "counts", "run_config"]
    missing = [name for name in complete_files if not paths[name].exists()]
    if missing:
        present = []
        if paths["agent_rds"].exists():
            present.append("agent .rds")
        if paths["patient_rds"].exists():
            present.append("patient .rds")
        detail = f"Missing {', '.join(missing)}"
        if present:
            detail += f"; present: {', '.join(present)}"
        return "partial/running", detail

    fixed_rows = read_csv(paths["fixed"])
    models = {row.get("model", "") for row in fixed_rows}
    if {"agent_looks", "patient_looks"}.issubset(models):
        return "complete", "Agent and patient summaries present"
    return "partial/running", f"Fixed-effects file has models: {', '.join(sorted(models))}"


def completed_specs() -> list[tuple[str, str, str, Path]]:
    out = []
    for window, window_label in WINDOWS:
        for contrast_id, label in CONTRASTS:
            status, _ = status_for(window, contrast_id)
            if status == "complete":
                out.append((window, window_label, contrast_id, label, BASE_DIR / window / contrast_id))
    return out


def model_label(value: str) -> str:
    return value.replace("_looks", " looks").replace("_", " ")


def condition_label(value: str) -> str:
    return value.replace("_", " ")


def status_section() -> str:
    rows = []
    complete = 0
    partial = 0
    not_started = 0
    for window, window_label in WINDOWS:
        for contrast_id, label in CONTRASTS:
            status, detail = status_for(window, contrast_id)
            if status == "complete":
                complete += 1
            elif status == "partial/running":
                partial += 1
            else:
                not_started += 1
            rows.append(
                [
                    esc(window_label),
                    esc(label),
                    esc(status),
                    esc(detail),
                    {"warning": status != "complete", "partial": status == "partial/running"},
                ]
            )
    return "\n".join(
        [
            "<h2>Run Status</h2>",
            (
                f"<p><b>Completed contrast folders:</b> {complete}/10. "
                f"<b>Partial/running:</b> {partial}. <b>Not started:</b> {not_started}. "
                "A contrast folder is treated as complete only when both agent and patient fixed-effect and diagnostic CSVs are present.</p>"
            ),
            html_table(["Window", "Comparison", "Status", "Detail"], rows),
        ]
    )


def counts_section() -> str:
    rows = []
    for window, window_label, contrast_id, label, directory in completed_specs():
        for row in read_csv(files_for(window, contrast_id)["counts"]):
            rows.append(
                [
                    esc(window_label),
                    esc(label),
                    esc(condition_label(row["condition_key"])),
                    fmt_int(row["trials"]),
                    fmt_int(row["participants"]),
                    fmt_int(row["lexical_items"]),
                    fmt_int(row["total_bins"]),
                ]
            )
    return "\n".join(
        [
            "<h2>Included Data</h2>",
            html_table(
                ["Window", "Comparison", "Condition", "Sentences/trials", "Participants", "Lexical items", "Time bins"],
                rows,
                cls="small",
            ),
        ]
    )


def convergence_section() -> str:
    fixed_rows = []
    all_rows = []
    sampler_rows = []
    warnings = []

    for window, window_label, contrast_id, label, directory in completed_specs():
        diag = read_csv(files_for(window, contrast_id)["diagnostics"])
        all_diag = read_csv(files_for(window, contrast_id)["all_diagnostics"])
        sampler = read_csv(files_for(window, contrast_id)["sampler"])

        by_model: dict[str, list[dict[str, str]]] = {}
        for row in diag:
            by_model.setdefault(row["model"], []).append(row)

        for model, rows in sorted(by_model.items()):
            max_rhat = max(parse_float(row["rhat"]) or 0 for row in rows)
            min_bulk = min(parse_float(row["bulk_ess"]) or 0 for row in rows)
            min_tail = min(parse_float(row["tail_ess"]) or 0 for row in rows)
            warn = max_rhat > 1.01 or min_bulk < 400 or min_tail < 400
            fixed_rows.append(
                [
                    esc(window_label),
                    esc(label),
                    esc(model_label(model)),
                    fmt(max_rhat, 4),
                    fmt(min_bulk, 0),
                    fmt(min_tail, 0),
                    {"warning": warn},
                ]
            )
            if warn:
                warnings.append(f"{window.upper()} {label}, {model_label(model)} fixed effects")

        for row in all_diag:
            warn = (
                (parse_float(row["max_rhat"]) or 0) > 1.01
                or (parse_float(row["min_bulk_ess"]) or 0) < 400
                or (parse_float(row["min_tail_ess"]) or 0) < 400
            )
            all_rows.append(
                [
                    esc(window_label),
                    esc(label),
                    esc(model_label(row["model"])),
                    fmt(row["max_rhat"], 4),
                    fmt(row["min_bulk_ess"], 0),
                    fmt(row["min_tail_ess"], 0),
                    esc(row["worst_bulk_variable"]),
                    esc(row["worst_tail_variable"]),
                    {"warning": warn},
                ]
            )

        for row in sampler:
            warn = (parse_float(row["divergent_transitions"]) or 0) > 0 or (parse_float(row["max_treedepth_hits"]) or 0) > 0
            sampler_rows.append(
                [
                    esc(window_label),
                    esc(label),
                    esc(model_label(row["model"])),
                    fmt_int(row["divergent_transitions"]),
                    fmt_int(row["max_treedepth_hits"]),
                    {"warning": warn},
                ]
            )

    if warnings:
        note = "Some fixed-effect diagnostics need caution: " + "; ".join(warnings) + "."
    else:
        note = "Fixed-effect diagnostics are broadly acceptable for completed models."

    return "\n".join(
        [
            "<h2>Convergence Diagnostics</h2>",
            f'<p class="diagnostic">{esc(note)} All-parameter diagnostics are stricter because they include nuisance random-effect SD/correlation parameters.</p>',
            "<h3>Fixed Effects</h3>",
            html_table(["Window", "Comparison", "Looks", "Max Rhat", "Min bulk ESS", "Min tail ESS"], fixed_rows, cls="small"),
            "<h3>All Parameters</h3>",
            html_table(
                [
                    "Window",
                    "Comparison",
                    "Looks",
                    "Max Rhat",
                    "Min bulk ESS",
                    "Min tail ESS",
                    "Worst bulk variable",
                    "Worst tail variable",
                ],
                all_rows,
                cls="tiny",
            ),
            "<h3>Sampler Diagnostics</h3>",
            html_table(["Window", "Comparison", "Looks", "Divergences", "Max-treedepth hits"], sampler_rows, cls="small"),
        ]
    )


def fixed_effect_sections() -> str:
    parts = ["<h2>Fixed Effects: Contrast Terms</h2>"]
    parts.append(
        "<p>Contrasts use +1/-1 coding: the reported beta is half of the full condition difference. The full-difference column is 2*beta. Green rows have a 95% credible interval excluding zero.</p>"
    )

    for window, window_label in WINDOWS:
        rows = []
        for completed in completed_specs():
            c_window, _, contrast_id, label, _ = completed
            if c_window != window:
                continue
            fixed = read_csv(files_for(window, contrast_id)["fixed"])
            for row in fixed:
                if row["term"] not in CONTRAST_TERMS:
                    continue
                full = ""
                if parse_float(row.get("full_difference_estimate")) is not None:
                    full = f"{fmt(row['full_difference_estimate'])} {ci(row['full_difference_ci_95_lower'], row['full_difference_ci_95_upper'])}"
                rows.append(
                    [
                        esc(label),
                        esc(model_label(row["model"])),
                        esc(TERM_LABELS.get(row["term"], row["term"])),
                        fmt(row["estimate"]),
                        ci(row["ci_95_lower"], row["ci_95_upper"]),
                        fmt(row["p_beta_gt_0"], 3),
                        esc(full),
                        {"credible": credible(row)},
                    ]
                )

        parts.append(f"<h3>{esc(window_label)}</h3>")
        parts.append(
            html_table(
                ["Comparison", "Looks", "Term", "Beta", "95% CI", "P(beta > 0)", "Full difference"],
                rows,
                cls="small fixed",
            )
        )

    parts.append("<h2>Fixed Effects: Intercept and Time Terms</h2>")
    for window, window_label in WINDOWS:
        rows = []
        for completed in completed_specs():
            c_window, _, contrast_id, label, _ = completed
            if c_window != window:
                continue
            for row in read_csv(files_for(window, contrast_id)["fixed"]):
                if row["term"] in CONTRAST_TERMS:
                    continue
                rows.append(
                    [
                        esc(label),
                        esc(model_label(row["model"])),
                        esc(TERM_LABELS.get(row["term"], row["term"])),
                        fmt(row["estimate"]),
                        ci(row["ci_95_lower"], row["ci_95_upper"]),
                        fmt(row["p_beta_gt_0"], 3),
                        {"credible": credible(row)},
                    ]
                )
        parts.append(f"<h3>{esc(window_label)}</h3>")
        parts.append(
            html_table(
                ["Comparison", "Looks", "Term", "Beta", "95% CI", "P(beta > 0)"],
                rows,
                cls="small fixed",
            )
        )

    return "\n".join(parts)


def credible_summary_section() -> str:
    rows = []
    for window, window_label, contrast_id, label, directory in completed_specs():
        for row in read_csv(files_for(window, contrast_id)["fixed"]):
            if row["term"] not in CONTRAST_TERMS or not credible(row):
                continue
            est = parse_float(row["estimate"]) or 0
            direction = "positive" if est > 0 else "negative"
            rows.append(
                [
                    esc(window_label),
                    esc(label),
                    esc(model_label(row["model"])),
                    esc(TERM_LABELS.get(row["term"], row["term"])),
                    esc(direction),
                    fmt(row["estimate"]),
                    ci(row["ci_95_lower"], row["ci_95_upper"]),
                    fmt(row["p_beta_gt_0"], 3),
                ]
            )
    if not rows:
        rows = [["", "No contrast terms currently have 95% credible intervals excluding zero.", "", "", "", "", "", ""]]
    return "\n".join(
        [
            "<h2>Contrast Effects with 95% CI Excluding Zero</h2>",
            html_table(["Window", "Comparison", "Looks", "Term", "Direction", "Beta", "95% CI", "P(beta > 0)"], rows, cls="small"),
        ]
    )


def run_settings_section() -> str:
    settings_rows = []
    seen = set()
    for window, window_label, contrast_id, label, directory in completed_specs():
        config_path = files_for(window, contrast_id)["run_config"]
        if not config_path.exists():
            continue
        row = read_csv(config_path)[0]
        key = (row["chains"], row["iter"], row["warmup"], row["adapt_delta"], row["max_treedepth"], row["file_refit"])
        if key in seen:
            continue
        seen.add(key)
        settings_rows.append(
            [
                fmt_int(row["chains"]),
                fmt_int(row["iter"]),
                fmt_int(row["warmup"]),
                fmt(row["adapt_delta"], 2),
                fmt_int(row["max_treedepth"]),
                esc(row["file_refit"]),
            ]
        )
    return "\n".join(
        [
            "<h2>Model Specification</h2>",
            "<p>Outcome is empirical-logit fixation proportion, fit separately for agent looks and patient looks. Time is modeled up to cubic using orthogonal polynomials. The current run uses the maximal correlated random-effect structure requested for participants and lexical items.</p>",
            "<p><b>Formula:</b> logit(looks) ~ poly(time, 3) * contrast + (1 + poly(time, 3) * contrast | participant) + (1 + poly(time, 3) | participant_condition) + (1 + poly(time, 3) * contrast | item)</p>",
            "<p><b>Priors:</b> no explicit priors are set in the script, so brms default weakly informative priors are used.</p>",
            html_table(["Chains", "Iter", "Warmup", "adapt_delta", "max_treedepth", "file_refit"], settings_rows),
        ]
    )


def build_html() -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    complete_model_count = len(completed_specs()) * 2
    return "\n".join(
        [
            "<!doctype html>",
            "<html>",
            "<head>",
            '<meta charset="utf-8">',
            "<title>Koryak fine-grained maximal pairwise progress summary</title>",
            "<style>",
            "@page { size: A4 landscape; margin: 11mm; }",
            "body { font-family: Arial, Helvetica, sans-serif; color: #222; font-size: 9.4px; line-height: 1.26; }",
            "h1 { font-size: 22px; margin: 0 0 6px; }",
            "h2 { font-size: 16px; margin: 15px 0 5px; border-top: 1px solid #999; padding-top: 8px; }",
            "h3 { font-size: 12px; margin: 10px 0 4px; }",
            "p { margin: 4px 0 7px; max-width: 1080px; }",
            "table { border-collapse: collapse; width: 100%; margin: 4px 0 8px; page-break-inside: auto; }",
            "th, td { border: 1px solid #bbb; padding: 2.5px 3.5px; vertical-align: top; }",
            "th { background: #eee; font-weight: 700; }",
            "tr { page-break-inside: avoid; }",
            ".small { font-size: 8.2px; }",
            ".tiny { font-size: 7.4px; }",
            ".fixed td:nth-child(1) { width: 24%; }",
            ".fixed td:nth-child(2) { width: 7%; }",
            ".fixed td:nth-child(3) { width: 12%; }",
            ".credible td { background: #eef7ee; }",
            ".warning td { background: #fff3df; }",
            ".partial td { background: #fff8d8; }",
            ".diagnostic { background: #f7f7f7; border-left: 4px solid #777; padding: 6px 8px; }",
            ".note { color: #555; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Koryak Fine-Grained Maximal Pairwise brms Models: Progress Summary</h1>",
            f'<p class="note">Generated {esc(generated)} from saved outputs in <code>{esc(BASE_DIR)}</code>. Completed model count summarized here: {complete_model_count} gaze models.</p>',
            status_section(),
            run_settings_section(),
            counts_section(),
            credible_summary_section(),
            fixed_effect_sections(),
            convergence_section(),
            "</body></html>",
        ]
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(build_html(), encoding="utf-8")
    print(HTML_PATH)


if __name__ == "__main__":
    main()
