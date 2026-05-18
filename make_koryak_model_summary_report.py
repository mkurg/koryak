#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import math
from collections import defaultdict
from pathlib import Path


OUT_DIR = Path("output/koryak_model_summary_report")
HTML_PATH = OUT_DIR / "koryak_model_summary_report.html"


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_float(value: object) -> float | None:
    text = str(value).strip()
    if text in {"", "NA", "NaN", "nan", "None"}:
        return None
    try:
        value_float = float(text)
    except ValueError:
        return None
    if math.isnan(value_float):
        return None
    return value_float


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


def term_label(term: str, contrast_label: str) -> str:
    labels = {
        "Intercept": "Intercept",
        "(Intercept)": "Intercept",
        "polytimedegreeEQ31": "Time polynomial 1",
        "polytimedegreeEQ32": "Time polynomial 2",
        "polytimedegreeEQ33": "Time polynomial 3",
        "direct_vs_inverse": contrast_label,
        "contrast_code": contrast_label,
        "polytimedegreeEQ31:direct_vs_inverse": f"Time polynomial 1 x {contrast_label}",
        "polytimedegreeEQ32:direct_vs_inverse": f"Time polynomial 2 x {contrast_label}",
        "polytimedegreeEQ33:direct_vs_inverse": f"Time polynomial 3 x {contrast_label}",
        "polytimedegreeEQ31:contrast_code": f"Time polynomial 1 x {contrast_label}",
        "polytimedegreeEQ32:contrast_code": f"Time polynomial 2 x {contrast_label}",
        "polytimedegreeEQ33:contrast_code": f"Time polynomial 3 x {contrast_label}",
    }
    return labels.get(term, term)


def html_table(headers: list[str], rows: list[list[object]], cls: str = "") -> str:
    out = [f'<table class="{cls}">', "<thead><tr>"]
    out.extend(f"<th>{esc(header)}</th>" for header in headers)
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        out.extend(f"<td>{cell}</td>" for cell in row)
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def section(title: str) -> str:
    return f"<h2>{esc(title)}</h2>"


def subsection(title: str) -> str:
    return f"<h3>{esc(title)}</h3>"


def rt_sections() -> list[str]:
    parts: list[str] = [section("1. Reaction Time Models")]
    parts.append(
        "<p>Reaction-time models use log speech-onset latency as the outcome. The tables below use Bayesian "
        "brms models with the same random-effect structure as the earlier RT analyses. Tables report "
        "posterior beta estimates on the log-ms scale, 95% credible intervals, P(beta &gt; 0), and exponentiated ratios.</p>"
    )

    desc = read_csv("output/koryak_behavioral_latency/koryak_latency_descriptives.csv")
    parts.append(subsection("1.1 All Direct vs All Inverse: Data Summary"))
    parts.append(
        html_table(
            ["Sentence type", "n", "Mean RT (ms)", "SD", "Median", "Min", "Max"],
            [
                [
                    esc(row["sentence_type"]),
                    fmt_int(row["n"]),
                    fmt(row["mean_rt_ms"], 1),
                    fmt(row["sd_rt_ms"], 1),
                    fmt(row["median_rt_ms"], 1),
                    fmt(row["min_rt_ms"], 0),
                    fmt(row["max_rt_ms"], 0),
                ]
                for row in desc
            ],
        )
    )

    fixed = read_csv("output/koryak_behavioral_latency_bayes/bayes_latency_direct_inverse_fixed_effects.csv")
    direct_rows = [row for row in fixed if row["term"] == "direct"]
    parts.append(subsection("1.2 All Direct vs All Inverse: Bayesian Contrast"))
    parts.append(
        html_table(
            ["Contrast", "Beta log(ms)", "95% CI", "P(beta > 0)", "Ratio", "% change", "Interpretation"],
            [
                [
                    "Direct - inverse",
                    fmt(row["estimate_log_ms"]),
                    ci(row["ci_95_lower_log_ms"], row["ci_95_upper_log_ms"]),
                    fmt(row["p_beta_gt_0"], 3),
                    fmt(row["ratio"]),
                    fmt(row["percent_change"], 1),
                    esc(row["interpretation"]),
                ]
                for row in direct_rows
            ],
        )
    )
    parts.append(
        "<p class=\"diagnostic\">Interpretation: the direct-minus-inverse beta is negative, so direct sentences are "
        "estimated to be faster. The 95% credible interval still includes zero. P(beta &gt; 0) = 0.108, "
        "equivalently P(beta &lt; 0) = 0.892.</p>"
    )

    desc4 = read_csv("output/koryak_behavioral_latency_4way/koryak_latency_4way_descriptives.csv")
    parts.append(subsection("1.3 Four-Way RT Model: Data Summary"))
    parts.append(
        html_table(
            ["Condition", "n", "Mean RT (ms)", "SD", "Median", "Min", "Max"],
            [
                [
                    esc(row["condition4"]),
                    fmt_int(row["n"]),
                    fmt(row["mean_rt_ms"], 1),
                    fmt(row["sd_rt_ms"], 1),
                    fmt(row["median_rt_ms"], 1),
                    fmt(row["min_rt_ms"], 0),
                    fmt(row["max_rt_ms"], 0),
                ]
                for row in desc4
            ],
        )
    )

    cond_est = read_csv("output/koryak_behavioral_latency_bayes/bayes_latency_4way_condition_estimates.csv")
    parts.append(subsection("1.4 Four-Way RT Model: Bayesian Condition Estimates"))
    parts.append(
        html_table(
            ["Condition", "Estimated RT (ms)", "95% credible interval"],
            [
                [
                    esc(row["condition4"]),
                    fmt(row["estimated_rt_ms"], 0),
                    ci(row["ci_95_lower_rt_ms"], row["ci_95_upper_rt_ms"], 0),
                ]
                for row in cond_est
            ],
        )
    )

    fixed4 = read_csv("output/koryak_behavioral_latency_bayes/bayes_latency_4way_fixed_effects.csv")
    fixed4_contrasts = [row for row in fixed4 if row["term"] != "Intercept"]
    fixed4_labels = {
        "condition4direct_1_2": "Direct 1-2 - direct 1-1",
        "condition4inverse_2_2": "Inverse 2-2 - direct 1-1",
        "condition4inverse_2_1": "Inverse 2-1 - direct 1-1",
    }
    parts.append(subsection("1.5 Four-Way RT Model: Bayesian Fixed Effects"))
    parts.append(
        html_table(
            ["Contrast", "Beta log(ms)", "95% CI", "P(beta > 0)", "Ratio", "% change", "Interpretation"],
            [
                [
                    esc(fixed4_labels.get(row["term"], row["term"])),
                    fmt(row["estimate_log_ms"]),
                    ci(row["ci_95_lower_log_ms"], row["ci_95_upper_log_ms"]),
                    fmt(row["p_beta_gt_0"], 3),
                    fmt(row["ratio"]),
                    fmt(row["percent_change"], 1),
                    esc(row["interpretation"]),
                ]
                for row in fixed4_contrasts
            ],
        )
    )

    pairwise = read_csv("output/koryak_behavioral_latency_bayes/bayes_latency_4way_pairwise.csv")
    parts.append(subsection("1.6 Four-Way RT Model: Bayesian Pairwise Comparisons"))
    parts.append(
        html_table(
            ["Comparison", "Beta log(ms)", "95% CI", "P(beta > 0)", "Ratio A/B", "% change"],
            [
                [
                    esc(row["comparison"]),
                    fmt(row["estimate_log_ms"]),
                    ci(row["ci_95_lower_log_ms"], row["ci_95_upper_log_ms"]),
                    fmt(row["p_beta_gt_0"], 3),
                    fmt(row["ratio"]),
                    fmt(row["percent_change"], 1),
                ]
                for row in pairwise
            ],
            cls="small",
        )
    )

    run_config = read_csv("output/koryak_behavioral_latency_bayes/run_config.csv")[0]
    fixed_diag = read_csv("output/koryak_behavioral_latency_bayes/bayes_latency_fixed_effect_diagnostics.csv")
    all_diag = read_csv("output/koryak_behavioral_latency_bayes/bayes_latency_all_parameter_diagnostics.csv")
    parts.append(subsection("1.7 Bayesian RT Model Diagnostics"))
    parts.append(
        html_table(
            ["Chains", "Iter", "Warmup", "adapt_delta", "max_treedepth"],
            [[
                fmt_int(run_config["chains"]),
                fmt_int(run_config["iter"]),
                fmt_int(run_config["warmup"]),
                fmt(run_config["adapt_delta"], 2),
                fmt_int(run_config["max_treedepth"]),
            ]],
        )
    )
    parts.append(
        html_table(
            ["Model", "Term", "Rhat", "Bulk ESS", "Tail ESS"],
            [
                [
                    esc(row["model"]),
                    esc(row["term"]),
                    fmt(row["rhat"], 4),
                    fmt(row["bulk_ess"], 0),
                    fmt(row["tail_ess"], 0),
                ]
                for row in fixed_diag
            ],
            cls="small",
        )
    )
    parts.append(
        html_table(
            ["Model", "Max Rhat", "Min bulk ESS", "Min tail ESS", "Worst bulk variable", "Worst tail variable"],
            [
                [
                    esc(row["model"]),
                    fmt(row["max_rhat"], 4),
                    fmt(row["min_bulk_ess"], 0),
                    fmt(row["min_tail_ess"], 0),
                    esc(row["worst_bulk_variable"]),
                    esc(row["worst_tail_variable"]),
                ]
                for row in all_diag
            ],
            cls="small",
        )
    )
    parts.append(
        "<p class=\"diagnostic\">Diagnostics: both Bayesian RT models had no divergent transitions and no max-treedepth hits. "
        "Fixed-effect diagnostics were good, with Rhat approximately 1.00 and fixed-effect bulk ESS at least 791. "
        "Stan warned about low bulk ESS for nuisance random-effect SD parameters; this is reported in the all-parameter table.</p>"
    )
    return parts


def brms_direct_rows(path: str, window: str) -> list[dict[str, object]]:
    rows = read_csv(path)
    out: list[dict[str, object]] = []
    for row in rows:
        term = row["term"]
        full_est = full_low = full_high = ""
        if "direct_vs_inverse" in term:
            full_est = 2 * float(row["estimate"])
            full_low = 2 * float(row["ci_95_lower"])
            full_high = 2 * float(row["ci_95_upper"])
        out.append(
            {
                "window": window,
                "comparison": "all direct vs all inverse",
                "looks": row["model"].replace("_", " "),
                "term": term_label(term, "direct(+1) vs inverse(-1)"),
                "beta": row["estimate"],
                "ci": ci(row["ci_95_lower"], row["ci_95_upper"]),
                "p_gt_0": row["p_beta_gt_0"],
                "full": "" if full_est == "" else f"{fmt(full_est)} [{fmt(full_low)}, {fmt(full_high)}]",
            }
        )
    return out


def brms_pairwise_rows(path: str, window: str) -> list[dict[str, object]]:
    rows = read_csv(path)
    out: list[dict[str, object]] = []
    for row in rows:
        term = row["term"]
        full = ""
        if parse_float(row.get("full_difference_estimate")) is not None:
            full = (
                f"{fmt(row['full_difference_estimate'])} "
                f"[{fmt(row['full_difference_ci_95_lower'])}, {fmt(row['full_difference_ci_95_upper'])}]"
            )
        out.append(
            {
                "window": window,
                "comparison": row["comparison"],
                "looks": row["model"].replace("_", " "),
                "term": term_label(term, "condition contrast(+1/-1)"),
                "beta": row["estimate"],
                "ci": ci(row["ci_95_lower"], row["ci_95_upper"]),
                "p_gt_0": row["p_beta_gt_0"],
                "full": full,
            }
        )
    return out


def brms_fixed_diag_rows() -> list[list[str]]:
    specs = [
        ("LE1", "all direct vs all inverse", "output/koryak_brms_le1_direct_inverse_full/brms_le1_direct_inverse_diagnostics.csv"),
        ("LE1", "number pairwise", "output/koryak_brms_le1_number_pairwise_full/brms_le1_number_pairwise_diagnostics.csv"),
        ("LE3", "all direct vs all inverse", "output/koryak_brms_le3_direct_inverse_full/brms_le3_direct_inverse_diagnostics.csv"),
        ("LE3", "number pairwise", "output/koryak_brms_le3_number_pairwise_full/brms_le3_number_pairwise_diagnostics.csv"),
    ]
    out: list[list[str]] = []
    for window, model_set, path in specs:
        rows = read_csv(path)
        max_rhat = max(float(row["rhat"]) for row in rows)
        min_bulk = min(float(row["bulk_ess"]) for row in rows)
        min_tail = min(float(row["tail_ess"]) for row in rows)
        out.append([window, model_set, fmt(max_rhat, 4), fmt(min_bulk, 0), fmt(min_tail, 0)])
    return out


def brms_all_param_diag_rows() -> list[list[str]]:
    rows = read_csv("output/koryak_model_report_brms_all_parameter_diagnostics.csv")
    out: list[list[str]] = []
    for row in rows:
        out.append(
            [
                esc(row["window"]),
                esc(row["model_set"]),
                esc(row["comparison"]),
                esc(row["looks"]),
                fmt(row["max_rhat"], 4),
                fmt(row["min_bulk_ess"], 0),
                fmt(row["min_tail_ess"], 0),
                esc(row["worst_bulk_variable"]),
                esc(row["worst_tail_variable"]),
            ]
        )
    return out


def brms_sections() -> list[str]:
    parts: list[str] = [section("2. Bayesian Eye-Movement Models")]
    parts.append(
        "<p>Bayesian models are brms Gaussian models over empirical logit-transformed fixation proportions, "
        "fit separately for agent looks and patient looks. Time is modeled with orthogonal polynomial terms up to cubic. "
        "All contrast-coded condition terms use +1/-1 coding, so the model beta is half of the full condition difference; "
        "the report also gives 2*beta for contrast and contrast-by-time terms.</p>"
    )
    parts.append(subsection("2.1 brms Run Settings"))
    run_settings = [
        ["LE1 all direct vs inverse", "4 chains, 2000 iter, 1000 warmup, adapt_delta .99, max_treedepth 12"],
        ["LE1 pairwise", "4 chains, 2000 iter, 1000 warmup, adapt_delta .99, max_treedepth 12"],
        ["LE3 all direct vs inverse", "4 chains, 2000 iter, 1000 warmup, adapt_delta .99, max_treedepth 12"],
        ["LE3 pairwise", "4 chains, 2000 iter, 1000 warmup, adapt_delta .99, max_treedepth 12"],
    ]
    parts.append(html_table(["Model set", "Settings"], run_settings))

    parts.append(subsection("2.2 Fixed-Effect Convergence Diagnostics"))
    parts.append(html_table(["Window", "Model set", "Max Rhat", "Min bulk ESS", "Min tail ESS"], brms_fixed_diag_rows()))

    parts.append(subsection("2.3 All-Parameter Convergence Diagnostics"))
    parts.append(
        html_table(
            ["Window", "Model set", "Comparison", "Looks", "Max Rhat", "Min bulk ESS", "Min tail ESS", "Worst bulk variable", "Worst tail variable"],
            brms_all_param_diag_rows(),
            cls="small",
        )
    )
    parts.append(
        '<p class="diagnostic">Log check: no divergence or treedepth warnings were found. The LE3 all-direct-vs-all-inverse run reported one low tail-ESS warning; this is reflected in the all-parameter diagnostics above.</p>'
    )

    fixed_rows = {
        "LE1 all direct vs all inverse": brms_direct_rows(
            "output/koryak_brms_le1_direct_inverse_full/brms_le1_direct_inverse_fixed_effects.csv", "LE1"
        ),
        "LE1 pairwise contrasts": brms_pairwise_rows(
            "output/koryak_brms_le1_number_pairwise_full/brms_le1_number_pairwise_fixed_effects.csv", "LE1"
        ),
        "LE3 all direct vs all inverse": brms_direct_rows(
            "output/koryak_brms_le3_direct_inverse_full/brms_le3_direct_inverse_fixed_effects.csv", "LE3"
        ),
        "LE3 pairwise contrasts": brms_pairwise_rows(
            "output/koryak_brms_le3_number_pairwise_full/brms_le3_number_pairwise_fixed_effects.csv", "LE3"
        ),
    }

    for title, rows in fixed_rows.items():
        parts.append(subsection(f"2.4 {title}: Fixed Effects"))
        table_rows = [
            [
                esc(row["comparison"]),
                esc(row["looks"]),
                esc(row["term"]),
                fmt(row["beta"]),
                row["ci"],
                fmt(row["p_gt_0"], 3),
                esc(row["full"]),
            ]
            for row in rows
        ]
        parts.append(
            html_table(
                ["Comparison", "Looks", "Term", "Beta", "95% CI", "P(beta > 0)", "Full difference 2*beta"],
                table_rows,
                cls="small fixed",
            )
        )

    return parts


def build_html() -> str:
    parts: list[str] = [
        "<!doctype html>",
        "<html>",
        "<head>",
        '<meta charset="utf-8">',
        "<title>Koryak model summary report</title>",
        "<style>",
        "@page { size: A4 landscape; margin: 12mm; }",
        "body { font-family: Arial, Helvetica, sans-serif; color: #222; font-size: 10.2px; line-height: 1.28; }",
        "h1 { font-size: 23px; margin: 0 0 8px; }",
        "h2 { font-size: 18px; margin: 18px 0 6px; border-top: 1px solid #999; padding-top: 10px; }",
        "h3 { font-size: 14px; margin: 13px 0 5px; }",
        "p { margin: 5px 0 8px; max-width: 1050px; }",
        "table { border-collapse: collapse; width: 100%; margin: 4px 0 10px; page-break-inside: auto; }",
        "th, td { border: 1px solid #bbb; padding: 3px 4px; vertical-align: top; }",
        "th { background: #eee; font-weight: 700; }",
        "tr { page-break-inside: avoid; }",
        ".small { font-size: 8.6px; }",
        ".fixed td:nth-child(1) { width: 20%; }",
        ".fixed td:nth-child(2) { width: 7%; }",
        ".fixed td:nth-child(3) { width: 21%; }",
        ".diagnostic { background: #f7f7f7; border-left: 4px solid #777; padding: 6px 8px; }",
        ".note { color: #555; }",
        "</style>",
        "</head><body>",
        "<h1>Koryak Model Summary Report</h1>",
        '<p class="note">Prepared from saved model outputs in the project folder. Reaction-time models are listed first, followed by the real brms eye-movement models for LE1 and LE3.</p>',
    ]
    parts.extend(rt_sections())
    parts.extend(brms_sections())
    parts.append("</body></html>")
    return "\n".join(parts)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(build_html(), encoding="utf-8")
    print(HTML_PATH)


if __name__ == "__main__":
    main()
