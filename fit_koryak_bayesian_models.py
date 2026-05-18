#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


WINDOWS = [
    ("speech_planning", "Speech planning"),
    ("linguistic_encoding_1", "Linguistic encoding I"),
    ("linguistic_encoding_2", "Linguistic encoding II"),
    ("linguistic_encoding_3", "Linguistic encoding III"),
    ("post_onset_1000_2500", "1000-2500 ms after speech onset"),
]

CORE_TERMS = [
    "Intercept",
    "time",
    "time2",
    "time3",
    "contrast",
    "time:contrast",
    "time2:contrast",
    "time3:contrast",
]


@dataclass(frozen=True)
class Comparison:
    key: str
    label: str
    positive_label: str
    negative_label: str
    source: str


COMPARISONS = [
    Comparison(
        key="all_direct_vs_all_inverse",
        label="All direct vs all inverse",
        positive_label="direct",
        negative_label="inverse",
        source="animacy",
    ),
    Comparison(
        key="direct_1_1_vs_direct_1_2",
        label="Direct 1 agent/1 patient vs direct 1 agent/2 patients",
        positive_label="direct 1-1",
        negative_label="direct 1-2",
        source="number",
    ),
    Comparison(
        key="inverse_2_1_vs_inverse_2_2",
        label="Inverse 2 agents/1 patient vs inverse 2 agents/2 patients",
        positive_label="inverse 2-1",
        negative_label="inverse 2-2",
        source="number",
    ),
    Comparison(
        key="direct_animate_vs_inanimate",
        label="Direct animate patient vs direct inanimate patient",
        positive_label="direct animate",
        negative_label="direct inanimate",
        source="animacy",
    ),
    Comparison(
        key="inverse_animate_vs_inanimate",
        label="Inverse animate patient vs inverse inanimate patient",
        positive_label="inverse animate",
        negative_label="inverse inanimate",
        source="animacy",
    ),
]


def load_trial_bins(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in ["time_rel", "agent_prop", "patient_prop", "n_samples", "rt"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "agent_num" in df.columns:
        df["agent_num"] = pd.to_numeric(df["agent_num"], errors="coerce")
    if "patient_num" in df.columns:
        df["patient_num"] = pd.to_numeric(df["patient_num"], errors="coerce")
    return df


def add_comparison_code(df: pd.DataFrame, comparison: Comparison) -> pd.DataFrame:
    out = df.copy()
    out["contrast_code"] = np.nan

    if comparison.key == "all_direct_vs_all_inverse":
        out.loc[out["sentence_type"] == "direct", "contrast_code"] = 1
        out.loc[out["sentence_type"] == "inverse", "contrast_code"] = -1

    elif comparison.key == "direct_1_1_vs_direct_1_2":
        mask = out["sentence_type"] == "direct"
        out.loc[mask & (out["agent_num"] == 1) & (out["patient_num"] == 1), "contrast_code"] = 1
        out.loc[mask & (out["agent_num"] == 1) & (out["patient_num"] == 2), "contrast_code"] = -1

    elif comparison.key == "inverse_2_1_vs_inverse_2_2":
        mask = out["sentence_type"] == "inverse"
        out.loc[mask & (out["agent_num"] == 2) & (out["patient_num"] == 1), "contrast_code"] = 1
        out.loc[mask & (out["agent_num"] == 2) & (out["patient_num"] == 2), "contrast_code"] = -1

    elif comparison.key == "direct_animate_vs_inanimate":
        mask = out["sentence_type"] == "direct"
        out.loc[mask & (out["patient_animacy"] == "animate"), "contrast_code"] = 1
        out.loc[mask & (out["patient_animacy"] == "inanimate"), "contrast_code"] = -1

    elif comparison.key == "inverse_animate_vs_inanimate":
        mask = out["sentence_type"] == "inverse"
        out.loc[mask & (out["patient_animacy"] == "animate"), "contrast_code"] = 1
        out.loc[mask & (out["patient_animacy"] == "inanimate"), "contrast_code"] = -1

    else:
        raise ValueError(f"Unknown comparison: {comparison.key}")

    return out.loc[out["contrast_code"].isin([-1, 1])].copy()


def build_response(df: pd.DataFrame, referent: str) -> pd.DataFrame:
    out = df.copy()
    prop_col = f"{referent}_prop"
    successes = np.rint(out[prop_col].to_numpy(float) * out["n_samples"].to_numpy(float))
    total = out["n_samples"].to_numpy(float)
    successes = np.clip(successes, 0, total)
    failures = total - successes

    out["successes"] = successes
    out["failures"] = failures
    out["log_odds"] = np.log((successes + 0.5) / (failures + 0.5))
    out["wts"] = 1 / (successes + 0.5) + 1 / (failures + 0.5)
    out["weight"] = 1 / out["wts"]
    return out


def build_design(df: pd.DataFrame) -> tuple[np.ndarray, list[str], np.ndarray, np.ndarray]:
    df = df.reset_index(drop=True)
    time = df["time_rel"].to_numpy(float) - 0.5
    contrast = df["contrast_code"].to_numpy(float)

    core = pd.DataFrame(
        {
            "Intercept": np.ones(len(df)),
            "time": time,
            "time2": time**2,
            "time3": time**3,
            "contrast": contrast,
            "time:contrast": time * contrast,
            "time2:contrast": (time**2) * contrast,
            "time3:contrast": (time**3) * contrast,
        }
    )

    participant = pd.get_dummies(df["participant"].astype(str), prefix="participant", drop_first=True)
    item = pd.get_dummies(df["image"].astype(str), prefix="item", drop_first=True)
    design = pd.concat([core, participant, item], axis=1)

    names = list(design.columns)
    x = design.to_numpy(dtype=float)
    y = df["log_odds"].to_numpy(dtype=float)
    weights = df["weight"].to_numpy(dtype=float)
    return x, names, y, weights


def fit_conjugate_weighted_lm(
    x: np.ndarray,
    names: list[str],
    y: np.ndarray,
    weights: np.ndarray,
    draws: int,
    seed: int,
) -> dict[str, tuple[float, float, float, float]]:
    keep = np.isfinite(y) & np.isfinite(weights) & (weights > 0) & np.isfinite(x).all(axis=1)
    x = x[keep]
    y = y[keep]
    weights = weights[keep]

    sqrt_w = np.sqrt(weights)
    xw = x * sqrt_w[:, None]
    yw = y * sqrt_w

    prior_sd = np.full(x.shape[1], 10.0)
    for i, name in enumerate(names):
        if name.startswith("participant_") or name.startswith("item_"):
            prior_sd[i] = 2.5

    prior_prec = np.diag(1 / (prior_sd**2))
    precision = xw.T @ xw + prior_prec
    rhs = xw.T @ yw
    mean = np.linalg.solve(precision, rhs)
    cov_base = np.linalg.inv(precision)

    a0 = 1e-3
    b0 = 1e-3
    alpha = a0 + len(y) / 2
    resid_part = float(yw @ yw - mean @ precision @ mean)
    beta = max(b0 + 0.5 * resid_part, 1e-12)

    rng = np.random.default_rng(seed)
    gamma_draws = rng.gamma(shape=alpha, scale=1 / beta, size=draws)
    sigma2_draws = 1 / gamma_draws

    out: dict[str, tuple[float, float, float, float]] = {}
    for term in CORE_TERMS:
        idx = names.index(term)
        term_draws = mean[idx] + rng.normal(size=draws) * np.sqrt(sigma2_draws * cov_base[idx, idx])
        out[term] = (
            float(np.mean(term_draws)),
            float(np.quantile(term_draws, 0.025)),
            float(np.quantile(term_draws, 0.975)),
            float(np.mean(term_draws > 0)),
        )
    return out


def fit_all_models(
    animacy_df: pd.DataFrame,
    number_df: pd.DataFrame,
    draws: int,
    seed: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    source_map = {"animacy": animacy_df, "number": number_df}
    seed_i = seed

    for window_key, window_title in WINDOWS:
        for comparison in COMPARISONS:
            base = source_map[comparison.source]
            df = base.loc[base["window_key"] == window_key].copy()
            df = add_comparison_code(df, comparison)

            for referent in ["agent", "patient"]:
                model_df = build_response(df, referent)
                x, names, y, weights = build_design(model_df)
                posterior = fit_conjugate_weighted_lm(x, names, y, weights, draws=draws, seed=seed_i)
                seed_i += 1

                n_trials = model_df[["participant", "image"]].drop_duplicates().shape[0]
                positive_trials = model_df.loc[
                    model_df["contrast_code"] == 1, ["participant", "image"]
                ].drop_duplicates().shape[0]
                negative_trials = model_df.loc[
                    model_df["contrast_code"] == -1, ["participant", "image"]
                ].drop_duplicates().shape[0]

                for term, (estimate, lower, upper, p_gt0) in posterior.items():
                    rows.append(
                        {
                            "window_key": window_key,
                            "window": window_title,
                            "referent": referent,
                            "comparison_key": comparison.key,
                            "comparison": comparison.label,
                            "contrast_coding": f"+1 {comparison.positive_label}; -1 {comparison.negative_label}",
                            "term": term,
                            "estimate": estimate,
                            "ci_95_lower": lower,
                            "ci_95_upper": upper,
                            "p_beta_gt_0": p_gt0,
                            "n_bin_rows": len(model_df),
                            "n_trials_with_gaze": n_trials,
                            "n_positive_trials": positive_trials,
                            "n_negative_trials": negative_trials,
                        }
                    )

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fit Bayesian weighted log-odds models for Koryak gaze bins."
    )
    parser.add_argument(
        "--animacy-trial-bins",
        default="output/koryak_speech_planning_graphs/speech_planning_trial_bins.csv",
    )
    parser.add_argument(
        "--number-trial-bins",
        default="output/koryak_number_sentence_graphs/speech_planning_trial_bins.csv",
    )
    parser.add_argument("--output-dir", default="output/koryak_bayesian_models")
    parser.add_argument("--draws", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260513)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    animacy = load_trial_bins(Path(args.animacy_trial_bins))
    number = load_trial_bins(Path(args.number_trial_bins))
    results = fit_all_models(animacy, number, draws=args.draws, seed=args.seed)

    all_path = out_dir / "koryak_bayesian_model_results.csv"
    results.to_csv(all_path, index=False)

    contrast_terms = results.loc[
        results["term"].isin(["contrast", "time:contrast", "time2:contrast", "time3:contrast"])
    ].copy()
    contrast_terms.to_csv(out_dir / "koryak_bayesian_model_contrast_terms.csv", index=False)

    print(f"Wrote {len(results)} coefficient rows to {all_path}")
    print(f"Wrote contrast/interactions to {out_dir / 'koryak_bayesian_model_contrast_terms.csv'}")
    print("Model: weighted Bayesian Gaussian regression on Khanty-style log-odds bins.")
    print("Core formula: log_odds ~ cubic time * contrast + participant fixed intercepts + item fixed intercepts.")
    print("Contrast coding: +1 first condition, -1 second condition, matching the Khanty contrast style.")


if __name__ == "__main__":
    main()
