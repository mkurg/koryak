# Khanty LE1 Agent-Look Per-Person Estimates

Model: empirical-logit agent-look proportions in Linguistic Encoding I (`tw == 2`).

Contrast coding: active = +1, passive = -1, so `active_voice` is half of the active-passive difference.

Trials: active = 414; passive = 168.

Main output files:

- `khanty_le1_agent_active_passive_person_random_effects.csv`: person-level random effects relative to the grand mean.
- `khanty_le1_agent_active_passive_person_absolute_estimates.csv`: fixed + person random effects; includes full active-passive contrast.
- `khanty_le1_agent_person_random_active_voice_slope_forest.png`: random slope forest plot.
- `khanty_le1_agent_person_absolute_active_minus_passive_forest.png`: absolute active-passive forest plot.
