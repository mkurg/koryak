# Koryak Eye-Movement Analysis

This folder contains the Koryak behavioral data, EyeLink ASC files, stimulus images, legacy R scripts, and the newer Python analysis/visualization scripts.

The project has been flattened so the working scripts are at the repository root instead of inside a nested codebase folder.

## Folder Layout

```text
.
├── ASC files/                         # EyeLink .asc recordings
├── stimuli/                           # stimulus PNGs
├── output/                            # generated files
│   ├── analysis/                      # behavior/gaze CSV outputs
│   ├── gaze_dots/                     # stimulus gaze-dot overlays
│   ├── koryak_speech_planning_graphs/ # animacy grouping graphs
│   └── koryak_number_sentence_graphs/ # number grouping graphs
├── Koryak stimuli - final.csv         # behavioral/stimulus coding
├── run_behavior.py                    # clean-trial counts and RT models
├── run_gaze_prepost.py                # sample-level pre/post speech-onset gaze extraction
├── make_gaze_dot_overlays.py          # visual gaze-dot overlays on stimuli
├── make_koryak_speech_planning_graphs.py
├── raw_extraction.R                   # legacy R code, kept for reference/reuse
└── eye_movement_analysis.R            # legacy R code, kept for reference/reuse
```

The helper modules used by the Python scripts are also at the root:

```text
asc_parser.py
behavior.py
gaze.py
utils.py
```

## Setup

Create a virtual environment and install the Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The default paths are in `config.example.yml`. You can either run scripts against that file directly or copy it to `config.yml`.

```bash
cp config.example.yml config.yml
```

## Main Commands

Behavioral summaries and RT models:

```bash
python run_behavior.py --config config.example.yml
```

Pre/post speech-onset gaze sample extraction:

```bash
python run_gaze_prepost.py --config config.example.yml
```

Gaze-dot overlays on the stimulus images:

```bash
python make_gaze_dot_overlays.py
```

Open the overlay index here:

```text
output/gaze_dots/index.html
```

Speech-planning graphs by patient animacy:

```bash
python make_koryak_speech_planning_graphs.py
```

Speech-planning graphs by agent/patient number condition:

```bash
python make_koryak_speech_planning_graphs.py \
  --grouping number \
  --output-dir output/koryak_number_sentence_graphs
```

## Notes

- The R scripts were not removed. They stay at the root as the legacy analysis/reference code.
- `ASC files/` and `stimuli/` keep their original names so existing references still work.
- `output/` is the single place for generated results. The old top-level `outputs/` folder was folded into it.
- The gaze AOIs use the `agens` and `patiens` screen coordinates embedded in each ASC trial and the 850 x 850 px image regions used by the existing analysis.