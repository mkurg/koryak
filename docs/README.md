# Koryak GitHub Pages site

Open `index.html` for the `/docs` landing page. It links to:

- `output-library.html`: searchable library of downloadable analysis outputs.
- `gaze-dot-overlays.html`: Koryak gaze dot overlay browser.

The gaze-dot overlay assets are:

- `participant_trials/`: one SVG per participant/run/trial.
- `aggregate_by_stimulus/`: one SVG per stimulus, pooling all plotted fixations.
- `fixations_plotted.csv`: every fixation dot with coordinates and metadata.
- `trial_overlay_summary.csv`: one row per generated trial overlay.
- `missing_stimuli.csv`: ASC trials whose PNG was not found in `stimuli/`.

Blue dots are fixations before speech onset. Orange dots are fixations in the first 2000 ms after speech onset. Dot size follows fixation duration. Numbered dots in participant-trial overlays show fixation order.
