# Khanty Passive LE1 Agent-Over-Patient Per-Person Estimates

Model: binomial agent looks out of agent-or-patient looks in passive sentences during LE1 (`tw == 2`).

Interpretation: `average_agent_share > 0.5` means a preference for the agent over the patient, conditional on looking at either argument.

Passive trials: 168.

Main output files:

- `khanty_le1_passive_agent_patient_person_absolute_estimates.csv`: per-person average LE1 agent-over-patient estimates.
- `khanty_le1_passive_agent_patient_group_estimate.csv`: group-level average LE1 estimate.
- `khanty_le1_passive_agent_patient_average_share_forest.png`: forest plot on probability scale.
- `khanty_le1_passive_agent_patient_average_log_odds_forest.png`: forest plot on log-odds scale.
