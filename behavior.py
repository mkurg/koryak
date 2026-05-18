from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from utils import clean_string_series, ensure_dir, normalize_participant_id, parse_number


def load_behavior(config: dict) -> pd.DataFrame:
    c = config["columns"]
    path = config["paths"]["behavior_csv"]
    df = pd.read_csv(path)

    df["participant_norm"] = df[c["participant_id"]].apply(normalize_participant_id)
    df["rt"] = df[c["reaction_time"]].apply(parse_number)
    df["fluency_norm"] = clean_string_series(df[c["fluency"]]).str.lower()
    df["sentence_type_norm"] = clean_string_series(df[c["sentence_type"]]).str.lower()
    df["word_order_norm"] = clean_string_series(df[c["word_order"]])
    df["trial_num_norm"] = pd.to_numeric(df[c["trial_num"]], errors="coerce")

    if c.get("patient_animacy") in df.columns:
        df["patient_animacy_norm"] = pd.to_numeric(df[c["patient_animacy"]], errors="coerce").map(
            {0: "inanimate", 1: "animate"}
        )
    else:
        df["patient_animacy_norm"] = np.nan

    return df


def add_sentence_binary(df: pd.DataFrame, match_mode: str = "contains") -> pd.DataFrame:
    out = df.copy()
    st = out["sentence_type_norm"].fillna("")

    if match_mode == "exact":
        is_direct = st == "direct"
        is_inverse = st == "inverse"
    elif match_mode == "contains":
        is_direct = st.str.contains("direct", na=False)
        is_inverse = st.str.contains("inverse", na=False)
    else:
        raise ValueError("sentence_type_match must be 'contains' or 'exact'.")

    out["is_direct"] = is_direct
    out["is_inverse"] = is_inverse

    # Keep unambiguous labels for the main direct-vs-inverse tests.
    out["type_binary"] = pd.Series(pd.NA, index=out.index, dtype="object")
    out.loc[is_direct & ~is_inverse, "type_binary"] = "direct"
    out.loc[is_inverse & ~is_direct, "type_binary"] = "inverse"

    # Also keep broad flags, because earlier descriptive counts used contains().
    return out


def clean_behavior_trials(config: dict) -> pd.DataFrame:
    df = load_behavior(config)
    cl = config["cleaning"]

    included = {normalize_participant_id(x) for x in cl["included_participants"]}
    match_mode = cl.get("sentence_type_match", "contains")
    df = add_sentence_binary(df, match_mode=match_mode)

    mask = (
        df["participant_norm"].isin(included)
        & (df["rt"] < float(cl["rt_max_ms"]))
        & (df["fluency_norm"] == str(cl["fluency_ok_value"]).strip().lower())
        & (df["word_order_norm"] == cl["word_order"])
        & (df["is_direct"] | df["is_inverse"])
    )

    clean = df.loc[mask].copy()
    return clean


def summarize_behavior(clean: pd.DataFrame, config: dict) -> dict[str, pd.DataFrame | str]:
    out: dict[str, pd.DataFrame | str] = {}

    direct = clean[clean["is_direct"]]
    inverse = clean[clean["is_inverse"]]

    out["participant_clean_counts"] = (
        pd.DataFrame(index=sorted(clean["participant_norm"].unique()))
        .assign(
            clean_direct_AVP=direct.groupby("participant_norm").size(),
            clean_inverse_AVP=inverse.groupby("participant_norm").size(),
        )
        .fillna(0)
        .astype(int)
        .assign(total_clean_AVP=lambda d: d["clean_direct_AVP"] + d["clean_inverse_AVP"])
        .reset_index(names="participant")
    )

    out["rt_summary_by_sentence_type"] = (
        pd.concat([
            direct.assign(type_for_summary="direct"),
            inverse.assign(type_for_summary="inverse")
        ])
        .groupby("type_for_summary")
        .agg(
            n=("rt", "size"),
            mean_rt_ms=("rt", "mean"),
            sd_rt_ms=("rt", "std"),
            median_rt_ms=("rt", "median"),
            min_rt_ms=("rt", "min"),
            max_rt_ms=("rt", "max"),
        )
        .reset_index()
    )

    out["patient_animacy_breakdown"] = (
        pd.concat([
            direct.assign(type_for_summary="direct"),
            inverse.assign(type_for_summary="inverse")
        ])
        .pivot_table(
            index="type_for_summary",
            columns="patient_animacy_norm",
            values="rt",
            aggfunc="size",
            fill_value=0,
        )
        .reset_index()
    )

    # Age table if participant info exists.
    info_path = config["paths"].get("participant_info_csv")
    if info_path and Path(info_path).exists():
        ic = config["columns"]
        info = pd.read_csv(info_path)
        info["participant_norm"] = info[ic["info_id"]].apply(normalize_participant_id)
        info["age"] = pd.to_numeric(info[ic["info_age"]], errors="coerce")

        counts = out["participant_clean_counts"]
        age_counts = counts.merge(
            info[["participant_norm", "age"]],
            left_on="participant",
            right_on="participant_norm",
            how="left",
        ).drop(columns=["participant_norm"])
        out["included_participant_age_counts"] = age_counts

    return out


def fit_rt_models(clean: pd.DataFrame) -> str:
    """
    Fit:
    1. Logistic GLM: inverse vs direct ~ RT + participant fixed effects.
    2. Mixed model: RT ~ inverse + random intercept by participant.

    Ambiguous rows containing both direct and inverse are excluded.
    """
    model_df = clean.loc[clean["type_binary"].isin(["direct", "inverse"])].copy()
    model_df["inverse"] = (model_df["type_binary"] == "inverse").astype(int)
    model_df["rt_sec"] = model_df["rt"] / 1000.0
    model_df["participant"] = model_df["participant_norm"].astype(str)

    lines: list[str] = []
    lines.append("RT / sentence-type models")
    lines.append("=" * 60)
    lines.append(f"N model trials: {len(model_df)}")
    lines.append(f"Direct: {(model_df['inverse'] == 0).sum()}")
    lines.append(f"Inverse: {(model_df['inverse'] == 1).sum()}")
    lines.append("")

    if len(model_df) == 0:
        lines.append("No direct/inverse trials available for modeling.")
        return "\n".join(lines)

    # Logistic regression
    try:
        logit = smf.glm(
            "inverse ~ rt_sec + C(participant)",
            data=model_df,
            family=sm.families.Binomial(),
        ).fit()

        coef = logit.params["rt_sec"]
        p = logit.pvalues["rt_sec"]
        ci = logit.conf_int().loc["rt_sec"]
        lines.append("Logistic regression: inverse ~ rt_sec + C(participant)")
        lines.append(f"  beta RT/sec: {coef:.6f}")
        lines.append(f"  OR per +1000 ms: {np.exp(coef):.4f}")
        lines.append(f"  95% CI OR: [{np.exp(ci[0]):.4f}, {np.exp(ci[1]):.4f}]")
        lines.append(f"  p-value: {p:.6g}")
        lines.append("")
    except Exception as e:
        lines.append(f"Logistic regression failed: {e}")
        lines.append("")

    # Mixed model RT outcome
    try:
        mixed = smf.mixedlm(
            "rt ~ inverse",
            data=model_df,
            groups=model_df["participant"],
        ).fit(reml=False)

        coef = mixed.params["inverse"]
        p = mixed.pvalues["inverse"]
        ci = mixed.conf_int().loc["inverse"]
        lines.append("Mixed model: rt ~ inverse + (1 | participant)")
        lines.append(f"  inverse-vs-direct estimate: {coef:.3f} ms")
        lines.append(f"  95% CI: [{ci[0]:.3f}, {ci[1]:.3f}]")
        lines.append(f"  p-value: {p:.6g}")
        lines.append("")
    except Exception as e:
        lines.append(f"Mixed model failed: {e}")
        lines.append("")

    lines.append("Note: RT is continuous, so the mixed RT model is the more natural primary model.")
    return "\n".join(lines)


def write_behavior_outputs(config: dict) -> None:
    out_dir = ensure_dir(config["paths"]["output_dir"])
    clean = clean_behavior_trials(config)
    summaries = summarize_behavior(clean, config)

    clean.to_csv(out_dir / "clean_behavior_trials.csv", index=False)

    for name, obj in summaries.items():
        if isinstance(obj, pd.DataFrame):
            obj.to_csv(out_dir / f"{name}.csv", index=False)

    model_text = fit_rt_models(clean)
    (out_dir / "rt_models_summary.txt").write_text(model_text, encoding="utf-8")

    print(model_text)
    print(f"\nWrote behavior outputs to: {out_dir}")
