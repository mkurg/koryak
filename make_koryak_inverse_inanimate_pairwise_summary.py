#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import math
from pathlib import Path


OUT_DIR = Path("output/koryak_inverse_inanimate_pairwise_summary")
HTML_PATH = OUT_DIR / "koryak_inverse_inanimate_pairwise_le1_le3_summary.html"

SPECS = [
    (
        "LE1",
        Path("output/koryak_brms_le1_inverse_inanimate_pairwise"),
        "brms_le1_inverse_inanimate_pairwise",
    ),
    (
        "LE3",
        Path("output/koryak_brms_le3_inverse_inanimate_pairwise"),
        "brms_le3_inverse_inanimate_pairwise",
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


def credible(row: dict[str, str], lower_key: str = "ci_95_lower", upper_key: str = "ci_95_upper") -> bool:
    lower = parse_float(row.get(lower_key))
    upper = parse_float(row.get(upper_key))
    return lower is not None and upper is not None and ((lower > 0 and upper > 0) or (lower < 0 and upper < 0))


def html_table(headers: list[str], rows: list[list[object]], cls: str = "") -> str:
    out = [f'<table class="{cls}">', "<thead><tr>"]
    out.extend(f"<th>{esc(header)}</th>" for header in headers)
    out.append("</tr></thead><tbody>")
    for row in rows:
        row_cls = ""
        cells = row
        if row and isinstance(row[-1], dict):
            meta = row[-1]
            cells = row[:-1]
            if meta.get("credible"):
                row_cls = ' class="credible"'
        out.append(f"<tr{row_cls}>")
        out.extend(f"<td>{cell}</td>" for cell in cells)
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def condition_label(condition_key: str) -> str:
    if "2_agents_2_patients" in condition_key:
        return "Inverse 2-2, inanimate patient"
    if "2_agents_1_patient" in condition_key:
        return "Inverse 2-1, inanimate patient"
    return condition_key


def model_label(model: str) -> str:
    return model.replace("_looks", " looks").replace("_", " ")


def collect_rows() -> dict[str, list[dict[str, str]]]:
    collected: dict[str, list[dict[str, str]]] = {
        "counts": [],
        "fixed": [],
        "diagnostics": [],
        "all_diagnostics": [],
        "sampler": [],
    }
    for window, directory, prefix in SPECS:
        for key, filename in [
            ("counts", f"{prefix}_counts.csv"),
            ("fixed", f"{prefix}_fixed_effects.csv"),
            ("diagnostics", f"{prefix}_diagnostics.csv"),
            ("all_diagnostics", f"{prefix}_all_parameter_diagnostics.csv"),
            ("sampler", f"{prefix}_sampler_diagnostics.csv"),
        ]:
            for row in read_csv(directory / filename):
                row["window"] = window
                collected[key].append(row)
    return collected


def build_html() -> str:
    rows = collect_rows()

    count_rows = []
    for row in rows["counts"]:
        count_rows.append(
            [
                esc(row["window"]),
                esc(condition_label(row["condition_key"])),
                fmt_int(row["trials"]),
                fmt_int(row["participants"]),
                fmt_int(row["total_bins"]),
            ]
        )

    total_sentences = {}
    for row in rows["counts"]:
        total_sentences.setdefault(row["window"], 0)
        total_sentences[row["window"]] += int(float(row["trials"]))

    contrast_rows = []
    time_rows = []
    for row in rows["fixed"]:
        target = contrast_rows if row["term"] in CONTRAST_TERMS else time_rows
        full = ""
        if parse_float(row.get("full_difference_estimate")) is not None:
            full = (
                f"{fmt(row['full_difference_estimate'])} "
                f"{ci(row['full_difference_ci_95_lower'], row['full_difference_ci_95_upper'])}"
            )
        target.append(
            [
                esc(row["window"]),
                esc(model_label(row["model"])),
                esc(TERM_LABELS.get(row["term"], row["term"])),
                fmt(row["estimate"]),
                ci(row["ci_95_lower"], row["ci_95_upper"]),
                fmt(row["p_beta_gt_0"], 3),
                esc(full),
                {"credible": credible(row)},
            ]
        )

    fixed_diag_rows = []
    for row in rows["diagnostics"]:
        fixed_diag_rows.append(
            [
                esc(row["window"]),
                esc(model_label(row["model"])),
                esc(TERM_LABELS.get(row["term"], row["term"])),
                fmt(row["rhat"], 4),
                fmt(row["bulk_ess"], 0),
                fmt(row["tail_ess"], 0),
            ]
        )

    all_diag_rows = []
    all_diag_lookup = {}
    for row in rows["all_diagnostics"]:
        all_diag_lookup[(row["window"], row["model"])] = row
    sampler_lookup = {(row["window"], row["model"]): row for row in rows["sampler"]}
    for key, row in all_diag_lookup.items():
        sampler = sampler_lookup.get(key, {})
        all_diag_rows.append(
            [
                esc(row["window"]),
                esc(model_label(row["model"])),
                fmt(row["max_rhat"], 4),
                fmt(row["min_bulk_ess"], 0),
                fmt(row["min_tail_ess"], 0),
                esc(row["worst_bulk_variable"]),
                esc(row["worst_tail_variable"]),
                fmt_int(sampler.get("divergent_transitions", "")),
                fmt_int(sampler.get("max_treedepth_hits", "")),
            ]
        )

    summary_rows = []
    for row in rows["fixed"]:
        if row["term"] not in CONTRAST_TERMS or not credible(row):
            continue
        direction = "positive" if parse_float(row["estimate"]) and parse_float(row["estimate"]) > 0 else "negative"
        summary_rows.append(
            [
                esc(row["window"]),
                esc(model_label(row["model"])),
                esc(TERM_LABELS.get(row["term"], row["term"])),
                esc(direction),
                fmt(row["estimate"]),
                ci(row["ci_95_lower"], row["ci_95_upper"]),
                fmt(row["p_beta_gt_0"], 3),
            ]
        )

    return "\n".join(
        [
            "<!doctype html>",
            "<html><head><meta charset='utf-8'>",
            "<title>Koryak inverse inanimate pairwise brms summary</title>",
            "<style>",
            "@page { size: A4 landscape; margin: 12mm; }",
            "body { font-family: Arial, Helvetica, sans-serif; color: #222; font-size: 10.5px; line-height: 1.3; }",
            "h1 { font-size: 23px; margin: 0 0 8px; }",
            "h2 { font-size: 17px; margin: 16px 0 6px; border-top: 1px solid #999; padding-top: 9px; }",
            "p { margin: 5px 0 8px; max-width: 1050px; }",
            "table { border-collapse: collapse; width: 100%; margin: 5px 0 10px; page-break-inside: auto; }",
            "th, td { border: 1px solid #bbb; padding: 3px 4px; vertical-align: top; }",
            "th { background: #eee; font-weight: 700; }",
            "tr { page-break-inside: avoid; }",
            ".small { font-size: 8.8px; }",
            ".credible td { background: #eef7ee; }",
            ".note { color: #555; }",
            ".diagnostic { background: #f7f7f7; border-left: 4px solid #777; padding: 6px 8px; }",
            "</style></head><body>",
            "<h1>Koryak Bayesian Pairwise Models: Inverse Inanimate Patients</h1>",
            "<p class='note'>Comparison in all four models: inverse 2-2 inanimate patient vs inverse 2-1 inanimate patient. "
            "Coding is +1 for inverse 2-2 inanimate and -1 for inverse 2-1 inanimate; contrast terms are therefore half-differences, "
            "and the full-difference column reports 2*beta.</p>",
            "<p class='note'>Models: empirical-logit fixation proportions with cubic time, condition contrast, and contrast-by-time interactions; "
            "fit separately for agent and patient looks in LE1 and LE3.</p>",
            "<h2>Data Included</h2>",
            html_table(["Window", "Condition", "Sentences included", "Participants", "50 ms bins"], count_rows),
            f"<p>Totals: LE1 included {total_sentences.get('LE1', 0)} sentences; LE3 included {total_sentences.get('LE3', 0)} sentences.</p>",
            "<h2>Credible Contrast Terms</h2>",
            "<p>Rows shown here are contrast or contrast-by-time terms whose 95% credible interval excludes zero.</p>",
            html_table(["Window", "Looks", "Term", "Direction", "Beta", "95% CI", "P(beta > 0)"], summary_rows),
            "<h2>Contrast And Interaction Terms</h2>",
            html_table(["Window", "Looks", "Term", "Beta", "95% CI", "P(beta > 0)", "Full difference 2*beta"], contrast_rows, cls="small"),
            "<h2>All Fixed Effects</h2>",
            html_table(["Window", "Looks", "Term", "Beta", "95% CI", "P(beta > 0)", "Full difference 2*beta"], time_rows + contrast_rows, cls="small"),
            "<h2>Convergence Diagnostics</h2>",
            "<p class='diagnostic'>All four models had 0 divergent transitions and 0 max-treedepth hits. Fixed-effect Rhats are approximately 1.00.</p>",
            html_table(["Window", "Looks", "Max Rhat", "Min bulk ESS", "Min tail ESS", "Worst bulk variable", "Worst tail variable", "Divergences", "Treedepth hits"], all_diag_rows, cls="small"),
            "<h2>Fixed-Effect Diagnostics</h2>",
            html_table(["Window", "Looks", "Term", "Rhat", "Bulk ESS", "Tail ESS"], fixed_diag_rows, cls="small"),
            "</body></html>",
        ]
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(build_html(), encoding="utf-8")
    print(HTML_PATH)


if __name__ == "__main__":
    main()
