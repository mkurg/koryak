from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from asc_parser import parse_asc
from behavior import clean_behavior_trials
from utils import ensure_dir, normalize_participant_id, parse_coord_pair


def classify_aoi(
    x: float,
    y: float,
    agent_coord: object,
    patient_coord: object,
    width: float,
    height: float,
) -> str:
    """
    Return 'a', 'p', or 'other' for one gaze sample.
    """
    if pd.isna(x) or pd.isna(y):
        return "other"

    ax, ay = parse_coord_pair(agent_coord)
    px, py = parse_coord_pair(patient_coord)

    in_agent = False
    in_patient = False

    if ax is not None and ay is not None:
        in_agent = (ax <= x <= ax + width) and (ay <= y <= ay + height)
    if px is not None and py is not None:
        in_patient = (px <= x <= px + width) and (py <= y <= py + height)

    if in_agent and not in_patient:
        return "a"
    if in_patient and not in_agent:
        return "p"
    return "other"


def first_existing_value(row: pd.Series, candidates: list[str]) -> object:
    for candidate in candidates:
        if candidate in row.index:
            return row[candidate]
    return None


def prepare_trial_merge_for_participant(
    asc_path: Path,
    clean_behavior: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    participant = normalize_participant_id(asc_path.stem)

    samples, _msgs, trials = parse_asc(asc_path)

    if samples.empty or trials.empty:
        return pd.DataFrame(), pd.DataFrame()

    trials["participant_norm"] = participant

    # Merge clean behavioral rows to ASC trial rows using participant + trial_num.
    beh = clean_behavior.loc[clean_behavior["participant_norm"] == participant].copy()
    if beh.empty:
        return pd.DataFrame(), pd.DataFrame()

    trials["trial_num_norm"] = pd.to_numeric(trials.get("trial_num"), errors="coerce")

    # Merge ASC trials to behavioral rows.
    # Important for this dataset: trial_num repeats within participant, so image is safer.
    merge_keys = list(config.get("gaze", {}).get("merge_keys", ["image"]))
    available_keys = ["participant_norm"]
    for key in merge_keys:
        if key in trials.columns and key in beh.columns:
            available_keys.append(key)

    if len(available_keys) == 1:
        # Fallback only if image/ans are unavailable.
        available_keys.append("trial_num_norm")

    merged_trials = trials.merge(
        beh,
        on=available_keys,
        how="inner",
        suffixes=("_asc", "_beh"),
    )

    # Only trials with a display timestamp and RT can be sliced.
    merged_trials = merged_trials.dropna(subset=["display_time", "rt", "block"])

    if merged_trials.empty:
        return pd.DataFrame(), pd.DataFrame()

    return samples, merged_trials


def extract_phase_samples(
    samples: pd.DataFrame,
    trials: pd.DataFrame,
    config: dict,
    phase: str,
) -> pd.DataFrame:
    width = float(config["gaze"]["aoi_width_px"])
    height = float(config["gaze"]["aoi_height_px"])
    post_ms = float(config["gaze"].get("post_window_ms", 2000))

    rows: list[pd.DataFrame] = []

    for _, tr in trials.iterrows():
        display = float(tr["display_time"])
        rt = float(tr["rt"])
        onset = display + rt

        if phase == "pre":
            start = display
            end = onset
        elif phase == "post":
            start = onset
            end = onset + post_ms
        else:
            raise ValueError("phase must be 'pre' or 'post'.")

        chunk = samples.loc[
            (samples["block"] == tr["block"])
            & (samples["time"] >= start)
            & (samples["time"] <= end)
        ].copy()

        if chunk.empty:
            continue

        # Add trial metadata. After merging, some columns can get _asc/_beh suffixes.
        metadata_candidates = {
            "participant_norm": ["participant_norm"],
            "trial_num_norm": ["trial_num_norm", "trial_num_norm_asc", "trial_num_norm_beh"],
            "block": ["block"],
            "rt": ["rt"],
            "sentence_type_norm": ["sentence_type_norm"],
            "type_binary": ["type_binary"],
            "is_direct": ["is_direct"],
            "is_inverse": ["is_inverse"],
            "word_order_norm": ["word_order_norm"],
            "fluency_norm": ["fluency_norm"],
            "patient_animacy_norm": ["patient_animacy_norm"],
            "agens": ["agens", "agens_asc", "agens_beh"],
            "patiens": ["patiens", "patiens_asc", "patiens_beh"],
            "image": ["image", "image_asc", "image_beh"],
            "ans": ["ans", "ans_asc", "ans_beh"],
            "cond": ["cond", "cond_asc", "cond_beh"],
            "number": ["number", "number_asc", "number_beh"],
        }
        for out_col, candidates in metadata_candidates.items():
            for candidate in candidates:
                if candidate in tr.index:
                    chunk[out_col] = tr[candidate]
                    break

        chunk["phase"] = phase
        chunk["speech_onset_time"] = onset
        chunk["display_time"] = display

        agent_coord = first_existing_value(tr, ["agens", "agens_asc", "agens_beh"])
        patient_coord = first_existing_value(tr, ["patiens", "patiens_asc", "patiens_beh"])

        chunk["who"] = [
            classify_aoi(x, y, agent_coord, patient_coord, width, height)
            for x, y in zip(chunk["xp"], chunk["yp"])
        ]
        chunk["agent"] = (chunk["who"] == "a").astype(int)
        chunk["patient"] = (chunk["who"] == "p").astype(int)
        chunk["valid_ap"] = ((chunk["agent"] == 1) | (chunk["patient"] == 1)).astype(int)

        rows.append(chunk)

    if not rows:
        return pd.DataFrame()

    out = pd.concat(rows, ignore_index=True)
    out = add_bins_and_props(out, config, phase=phase)
    return out


def add_bins_and_props(df: pd.DataFrame, config: dict, phase: str) -> pd.DataFrame:
    out = df.sort_values(["participant_norm", "trial_num_norm", "time"]).copy()

    group_cols = ["participant_norm", "trial_num_norm"]
    out["ms"] = out.groupby(group_cols).cumcount() + 1
    out["rev_ms"] = out.groupby(group_cols)["ms"].transform(lambda s: len(s) - s + 1)

    for bin_size in config["gaze"].get("bin_sizes", [20, 50]):
        # R-style: ms %/% bin_size, with ms starting at 1.
        bin_col = f"time_bin{bin_size}"
        out[bin_col] = (out["ms"] // int(bin_size)).astype(int)

        denom = out.groupby(group_cols + [bin_col])["valid_ap"].transform("sum").replace({0: np.nan})
        out[f"a_prop_{bin_size}"] = out.groupby(group_cols + [bin_col])["agent"].transform("sum") / denom
        out[f"p_prop_{bin_size}"] = out.groupby(group_cols + [bin_col])["patient"].transform("sum") / denom

        if phase == "pre":
            nbin_col = f"time_bin{bin_size}_neg"
            out[nbin_col] = (out["rev_ms"] // int(bin_size)).astype(int)
            denom_n = out.groupby(group_cols + [nbin_col])["valid_ap"].transform("sum").replace({0: np.nan})
            out[f"a_prop_{bin_size}n"] = out.groupby(group_cols + [nbin_col])["agent"].transform("sum") / denom_n
            out[f"p_prop_{bin_size}n"] = out.groupby(group_cols + [nbin_col])["patient"].transform("sum") / denom_n

    if config["gaze"].get("make_tw", True) and phase == "pre":
        sol = out["rt"].astype(float)
        out["tw"] = np.where(
            out["ms"] <= 100, "0",
            np.where(
                out["ms"] <= 600, "1",
                np.where(out["ms"] <= 600 + 0.5 * (sol - 600), "2", "3")
            )
        )
    else:
        out["tw"] = np.nan

    return out


def summarize_gaze(pre: pd.DataFrame, post: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_samples = pd.concat([pre, post], ignore_index=True)

    if all_samples.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Ensure optional metadata columns exist.
    for optional_col in ["patient_animacy_norm", "image"]:
        if optional_col not in all_samples.columns:
            all_samples[optional_col] = np.nan

    # Trial-level summary
    trial_summary = (
        all_samples
        .groupby(["participant_norm", "trial_num_norm", "phase", "type_binary"], dropna=False)
        .agg(
            n_samples=("time", "size"),
            agent_samples=("agent", "sum"),
            patient_samples=("patient", "sum"),
            valid_ap_samples=("valid_ap", "sum"),
            rt_ms=("rt", "first"),
            patient_animacy=("patient_animacy_norm", "first"),
            image=("image", "first"),
        )
        .reset_index()
    )
    trial_summary["agent_share_ap"] = trial_summary["agent_samples"] / trial_summary["valid_ap_samples"].replace({0: np.nan})
    trial_summary["patient_share_ap"] = trial_summary["patient_samples"] / trial_summary["valid_ap_samples"].replace({0: np.nan})

    # First A/P look per trial, if any.
    firsts = (
        all_samples.loc[all_samples["who"].isin(["a", "p"])]
        .sort_values(["participant_norm", "trial_num_norm", "phase", "time"])
        .groupby(["participant_norm", "trial_num_norm", "phase"], as_index=False)
        .first()[["participant_norm", "trial_num_norm", "phase", "who"]]
        .rename(columns={"who": "first_ap_look"})
    )
    trial_summary = trial_summary.merge(firsts, on=["participant_norm", "trial_num_norm", "phase"], how="left")

    overall = (
        trial_summary
        .groupby(["phase", "type_binary"], dropna=False)
        .agg(
            n_trials=("trial_num_norm", "size"),
            agent_samples=("agent_samples", "sum"),
            patient_samples=("patient_samples", "sum"),
            valid_ap_samples=("valid_ap_samples", "sum"),
            mean_agent_share_ap=("agent_share_ap", "mean"),
            mean_patient_share_ap=("patient_share_ap", "mean"),
            first_agent=("first_ap_look", lambda s: (s == "a").sum()),
            first_patient=("first_ap_look", lambda s: (s == "p").sum()),
        )
        .reset_index()
    )

    return trial_summary, overall


def write_gaze_outputs(config: dict) -> None:
    out_dir = ensure_dir(config["paths"]["output_dir"])
    asc_dir = Path(config["paths"]["asc_dir"])

    clean = clean_behavior_trials(config)

    all_pre: list[pd.DataFrame] = []
    all_post: list[pd.DataFrame] = []
    merge_notes: list[dict[str, object]] = []

    asc_files = sorted(asc_dir.glob("*.asc"))
    if not asc_files:
        raise FileNotFoundError(f"No .asc files found in {asc_dir}")

    for asc_path in asc_files:
        participant = normalize_participant_id(asc_path.stem)
        print(f"Parsing {asc_path.name} -> {participant}")

        samples, trials = prepare_trial_merge_for_participant(asc_path, clean, config)

        merge_notes.append({
            "asc_file": asc_path.name,
            "participant": participant,
            "n_samples_raw": len(samples),
            "n_clean_merged_trials": len(trials),
        })

        if samples.empty or trials.empty:
            continue

        pre = extract_phase_samples(samples, trials, config, phase="pre")
        post = extract_phase_samples(samples, trials, config, phase="post")

        if not pre.empty:
            all_pre.append(pre)
        if not post.empty:
            all_post.append(post)

    pre_all = pd.concat(all_pre, ignore_index=True) if all_pre else pd.DataFrame()
    post_all = pd.concat(all_post, ignore_index=True) if all_post else pd.DataFrame()

    pre_all.to_csv(out_dir / "gaze_preonset_samples.csv", index=False)
    post_all.to_csv(out_dir / "gaze_postonset_samples.csv", index=False)

    trial_summary, overall = summarize_gaze(pre_all, post_all)
    trial_summary.to_csv(out_dir / "gaze_trial_pre_post_summary.csv", index=False)
    overall.to_csv(out_dir / "gaze_overall_summary.csv", index=False)
    pd.DataFrame(merge_notes).to_csv(out_dir / "gaze_merge_notes.csv", index=False)

    print(f"\nWrote gaze outputs to: {out_dir}")
    print("\nMerge notes:")
    print(pd.DataFrame(merge_notes).to_string(index=False))
    if not overall.empty:
        print("\nOverall summary:")
        print(overall.to_string(index=False))
