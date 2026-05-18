#!/usr/bin/env zsh
set -euo pipefail

cd /Users/matveikurzukov/koryak

export PATH=/Users/matveikurzukov/koryak/.tools/r-brms-env/bin:$PATH
export CONDA_PREFIX=/Users/matveikurzukov/koryak/.tools/r-brms-env
export R_MAKEVARS_USER=/private/tmp/koryak_r_makevars
export KORYAK_BRMS_CHAINS=${KORYAK_BRMS_CHAINS:-4}
export KORYAK_BRMS_CORES=${KORYAK_BRMS_CORES:-4}
export KORYAK_BRMS_ITER=${KORYAK_BRMS_ITER:-2000}
export KORYAK_BRMS_WARMUP=${KORYAK_BRMS_WARMUP:-1000}
export KORYAK_BRMS_REFRESH=${KORYAK_BRMS_REFRESH:-100}
export KORYAK_BRMS_ADAPT_DELTA=${KORYAK_BRMS_ADAPT_DELTA:-0.99}
export KORYAK_BRMS_MAX_TREEDEPTH=${KORYAK_BRMS_MAX_TREEDEPTH:-12}
export KORYAK_BRMS_FILE_REFIT=${KORYAK_BRMS_FILE_REFIT:-on_change}

DATA=output/koryak_number_animacy_sentence_graphs/speech_planning_trial_bins.csv
BASE_OUT=output/koryak_brms_fine_grained_pairwise_maximal

run_pair () {
  local window_key="$1"
  local window_label="$2"
  local contrast_id="$3"
  local condition_a="$4"
  local label_a="$5"
  local condition_b="$6"
  local label_b="$7"
  local out="$BASE_OUT/$window_label/$contrast_id"

  mkdir -p "$out"
  .tools/r-brms-env/bin/Rscript fit_brms_condition_pairwise_maximal.R \
    "$DATA" "$out" "$window_key" "$window_label" \
    "$contrast_id" "$condition_a" "$label_a" "$condition_b" "$label_b" \
    2>&1 | tee "$out/${window_label}_${contrast_id}_maximal_full_run.log"
}

for window in le1:linguistic_encoding_1 le3:linguistic_encoding_3; do
  window_label="${window%%:*}"
  window_key="${window#*:}"

  run_pair "$window_key" "$window_label" direct_1_1_animate_vs_direct_1_2_animate \
    direct_1_agent_1_patient_animate_patient "direct 1-1 animate patient" \
    direct_1_agent_2_patients_animate_patient "direct 1-2 animate patient"

  run_pair "$window_key" "$window_label" direct_1_1_inanimate_vs_direct_1_2_inanimate \
    direct_1_agent_1_patient_inanimate_patient "direct 1-1 inanimate patient" \
    direct_1_agent_2_patients_inanimate_patient "direct 1-2 inanimate patient"

  run_pair "$window_key" "$window_label" inverse_2_2_animate_vs_inverse_2_1_animate \
    inverse_2_agents_2_patients_animate_patient "inverse 2-2 animate patient" \
    inverse_2_agents_1_patient_animate_patient "inverse 2-1 animate patient"

  run_pair "$window_key" "$window_label" direct_1_1_animate_vs_inverse_2_2_animate \
    direct_1_agent_1_patient_animate_patient "direct 1-1 animate patient" \
    inverse_2_agents_2_patients_animate_patient "inverse 2-2 animate patient"

  run_pair "$window_key" "$window_label" direct_1_1_inanimate_vs_inverse_2_2_inanimate \
    direct_1_agent_1_patient_inanimate_patient "direct 1-1 inanimate patient" \
    inverse_2_agents_2_patients_inanimate_patient "inverse 2-2 inanimate patient"
done
