# Koryak Eye-Movement Analysis

This repository contains the Koryak EyeLink ASC files, stimulus metadata, stimulus images, analysis scripts, generated graphs, and Bayesian model outputs used for the Koryak speech-planning / gaze analyses.

The codebase is intentionally flat: current scripts live at the repository root, with generated artifacts under `output/`. The legacy Khanty-style R scripts are also kept at the root as reference material.

## Repository Layout

```text
.
├── ASC files/                 # EyeLink .asc recordings
├── osfstorage-archive/        # Khanty archive metadata/scripts; raw ASC and bulky CSV data ignored
├── stimuli/                   # stimulus images
├── docs/                      # static gaze-dot mini-site for publication/GitHub Pages
├── output/                    # generated data, plots, model outputs, reports
├── Koryak stimuli - final.csv # stimulus/behavioral coding
├── config.example.yml         # portable default config
├── config.yml                 # local config
├── *.py                       # Python extraction, graph, and report scripts
├── *.R                        # R/brms and legacy analysis scripts
└── run_fine_grained_pairwise_maximal.sh
```

`docs/` is a copied static mini-site from the gaze-dot overlay output. Leave it in place: it is the web-ready version of the overlay viewer. The source/generated overlay copy is still in `output/gaze_dots/`.

Generated Python bytecode, `.DS_Store`, and the local R/brms environment in `.tools/` are ignored.
Khanty raw ASC files, huge merged CSVs, and large derived trial-bin/sample CSVs are also ignored; the committed scripts and lightweight summary/plot artifacts document how to regenerate them locally.

PDF conversion for SVG graphs uses `rsvg-convert` from `librsvg`; this keeps PDFs vector-based and avoids Chrome. The helper script is `svg_to_pdf.py`; it writes font/cache files under `.tools/cache`.

## Setup

Python scripts use the dependencies in `requirements.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yml config.yml
```

The brms models use the local conda/micromamba R environment under `.tools/r-brms-env/`. That environment is intentionally not tracked in git. Most R model commands should be run with this environment on `PATH`:

```bash
export PATH=/Users/matveikurzukov/koryak/.tools/r-brms-env/bin:$PATH
export CONDA_PREFIX=/Users/matveikurzukov/koryak/.tools/r-brms-env
export R_MAKEVARS_USER=/private/tmp/koryak_r_makevars
```

## Core Data Pipeline

Behavioral clean-trial counts and reaction-time extraction:

```bash
python run_behavior.py --config config.example.yml
```

Sample-level gaze extraction around speech onset:

```bash
python run_gaze_prepost.py --config config.example.yml
```

Track-loss estimates by ASC file and planning window:

```bash
python estimate_track_loss.py
```

Gaze-dot overlays on stimulus images:

```bash
python make_gaze_dot_overlays.py
```

Open the overlay viewer from either location:

```text
docs/index.html
output/gaze_dots/index.html
```

## Graphs

Main early event apprehension / linguistic-encoding graphs are generated from `make_koryak_speech_planning_graphs.py`.

Patient animacy grouping:

```bash
python make_koryak_speech_planning_graphs.py
```

Agent/patient number grouping:

```bash
python make_koryak_speech_planning_graphs.py \
  --grouping number \
  --output-dir output/koryak_number_sentence_graphs
```

Number plus patient-animacy panels for all five planning windows:

```bash
python make_koryak_number_animacy_panel_pages.py
```

All-direct and all-inverse panels across all five windows:

```bash
python make_koryak_direct_inverse_all_windows_graphs.py
```

Convert any standalone SVG to PDF without Chrome:

```bash
python svg_to_pdf.py path/to/graph.svg
```

Key graph/report outputs:

```text
output/koryak_speech_planning_graphs/
output/koryak_number_sentence_graphs/
output/koryak_number_animacy_sentence_graphs/
output/koryak_number_animacy_sentence_graphs/direct_AVP_number_animacy_all_windows_panel.pdf
output/koryak_number_animacy_sentence_graphs/inverse_AVP_number_animacy_all_windows_panel.pdf
output/koryak_direct_inverse_all_windows_graphs/direct_AVP_all_windows.pdf
output/koryak_direct_inverse_all_windows_graphs/inverse_AVP_all_windows.pdf
```

## Khanty Archive Graphs

The Khanty archive lives under `osfstorage-archive/`. Tracked files include the behavioral metadata, legacy R scripts, archive CSV outputs, and generated plotting CSV outputs. The raw ASC recordings in `osfstorage-archive/ascs/` stay outside git, and individual CSV files larger than 100 MB are ignored unless Git LFS is enabled.

ASC-derived active/passive speech-planning graphs from 0-3500 ms:

```bash
python make_khanty_asc_active_passive_planning_graphs.py
```

Outputs:

```text
output/khanty_asc_active_passive_speech_planning_graphs/
```

Individual passive plots can be made either per session or by informant code. The informant-code mode combines filenames by the prefix before the first underscore, e.g. `RAI_a3`, `RAI_b1`, and `RAI_b2` become `RAI`:

```bash
python make_khanty_individual_passive_plots.py \
  --group-by-informant-code \
  --min-passive-trials 15 \
  --output-dir output/khanty_informant_passive_plots_gt15
```

Current eligible informant-code outputs are:

```text
output/khanty_informant_passive_plots_gt15/RAI_passives_0_3500ms.svg
output/khanty_informant_passive_plots_gt15/SED_passives_0_3500ms.svg
output/khanty_informant_passive_plots_gt15/PRM_passives_0_3500ms.svg
```

SOL-split graphs are generated by type and by requested word orders:

```bash
python make_khanty_sol_split_plots.py
python make_khanty_word_order_sol_split_plots.py
```

Outputs:

```text
output/khanty_sol_split_speech_planning_graphs/
output/khanty_word_order_sol_split_graphs/
```

The four-window aggregate panel for all 58 `PAV` passive trials is:

```bash
python make_khanty_pav_passive_all_windows.py
```

Output:

```text
output/khanty_pav_passive_all_windows/khanty_pav_passives_all_windows.svg
output/khanty_pav_passive_all_windows/khanty_pav_passives_all_windows.pdf
```

## Reaction-Time Models

Older frequentist RT checks are in:

```text
fit_koryak_behavioral_latency.R
fit_koryak_behavioral_latency_4way.R
```

The Bayesian RT replacement is:

```bash
.tools/r-brms-env/bin/Rscript fit_koryak_behavioral_latency_bayes.R
```

Main outputs:

```text
output/koryak_behavioral_latency_bayes/
```

## Gaze Models

All gaze models use empirical-logit fixation proportions, separate agent-look and patient-look models, cubic time terms, and time-by-contrast interactions.

General direct/inverse and number-pairwise brms scripts:

```text
fit_brms_le3_direct_inverse.R
fit_brms_le3_number_pairwise.R
fit_brms_condition_pairwise.R
fit_brms_condition_pairwise_maximal.R
fit_brms_le1_inverse_inanimate_pairwise.R
```

Existing completed model-output folders include:

```text
output/koryak_brms_le1_direct_inverse_full/
output/koryak_brms_le3_direct_inverse_full/
output/koryak_brms_le1_number_pairwise_full/
output/koryak_brms_le3_number_pairwise_full/
output/koryak_brms_le1_inverse_inanimate_pairwise/
output/koryak_brms_le3_inverse_inanimate_pairwise/
```

Summary reports:

```text
output/koryak_model_summary_report/koryak_model_summary_report.pdf
output/koryak_inverse_inanimate_pairwise_summary/koryak_inverse_inanimate_pairwise_le1_le3_summary.pdf
```

## Fine-Grained Maximal Pairwise Models

The maximal pairwise batch command is:

```bash
./run_fine_grained_pairwise_maximal.sh
```

This runs LE1 and LE3 models for:

```text
direct 1-1 animate vs direct 1-2 animate
direct 1-1 inanimate vs direct 1-2 inanimate
inverse 2-2 animate vs inverse 2-1 animate
direct 1-1 animate vs inverse 2-2 animate
direct 1-1 inanimate vs inverse 2-2 inanimate
```

The current saved state is 9 of 10 contrast folders completed. The stopped partial folder is:

```text
output/koryak_brms_fine_grained_pairwise_maximal/le3/direct_1_1_inanimate_vs_inverse_2_2_inanimate/
```

It currently contains counts, model data, run config, and log files, but no completed agent/patient brms summaries.

The progress summary generator is:

```bash
python make_koryak_fine_grained_maximal_progress_summary.py
```

Current progress-report outputs:

```text
output/koryak_brms_fine_grained_pairwise_maximal_progress_summary/koryak_fine_grained_pairwise_maximal_progress_summary.html
output/koryak_brms_fine_grained_pairwise_maximal_progress_summary/koryak_fine_grained_pairwise_maximal_progress_summary.pdf
```

## Notes

- `output/` is the canonical location for generated analysis artifacts.
- `docs/` is intentionally duplicated from the gaze overlay output for a static mini-site.
- `ASC files/` and `stimuli/` retain their original names so existing scripts and file references keep working.
- AOIs use the `agens` and `patiens` screen coordinates embedded in each ASC trial and the 850 x 850 px image regions used by the existing analysis.
