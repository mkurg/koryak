# Koryak LE1 brms Models: Reader-Friendly Summary

Window: linguistic encoding 1.  
Run settings: 4 chains, 2000 iterations, 1000 warmup, `adapt_delta = 0.99`, `max_treedepth = 12`.  
Models: separate brms models for agent looks and patient looks.  
Contrast coding: first-named condition = +1, second-named condition = -1. Therefore the reported contrast beta is half of the full condition difference.  
Evidence label: "clear" means the 95% credible interval excludes 0.

## Convergence

No warning, divergence, or treedepth messages were found in the LE1 logs.

Fixed-effect diagnostics:

| model set | max Rhat | min bulk ESS | min tail ESS | reading |
|---|---:|---:|---:|---|
| all direct vs all inverse | 1.005 | 966 | 1685 | good |
| pairwise models | 1.006 | 1014 | 1579 | good |

All-parameter diagnostics, including random effects:

| model | max Rhat | min bulk ESS | min tail ESS | reading |
|---|---:|---:|---:|---|
| direct/inverse agent | 1.005 | 735 | 667 | acceptable |
| direct/inverse patient | 1.015 | 604 | 1190 | mild random-effect issue |
| direct 1-1 vs direct 1-2 agent | 1.019 | 480 | 1567 | mild random-effect issue |
| direct 1-1 vs direct 1-2 patient | 1.016 | 449 | 824 | mild random-effect issue |
| inverse 2-1 vs inverse 2-2 agent | 1.006 | 615 | 1546 | acceptable |
| inverse 2-1 vs inverse 2-2 patient | 1.008 | 433 | 1313 | acceptable, lower ESS for random effect |
| direct 1-1 vs inverse 2-2 agent | 1.008 | 794 | 991 | acceptable |
| direct 1-1 vs inverse 2-2 patient | 1.010 | 636 | 747 | acceptable |

Overall: the fixed effects used for interpretation converged well. A few random-effect parameters are weaker, but not enough to undermine the fixed-effect summaries.

## Data Included

| comparison | condition | bins | participants |
|---|---:|---:|---:|
| all direct vs all inverse | direct | 9657 | 16 |
| all direct vs all inverse | inverse | 7708 | 16 |
| direct 1-1 vs direct 1-2 | direct 1 agent, 1 patient | 3907 | 16 |
| direct 1-1 vs direct 1-2 | direct 1 agent, 2 patients | 4126 | 16 |
| inverse 2-1 vs inverse 2-2 | inverse 2 agents, 1 patient | 4066 | 16 |
| inverse 2-1 vs inverse 2-2 | inverse 2 agents, 2 patients | 3376 | 16 |
| direct 1-1 vs inverse 2-2 | direct 1 agent, 1 patient | 3907 | 16 |
| direct 1-1 vs inverse 2-2 | inverse 2 agents, 2 patients | 3376 | 16 |

## Main Condition Contrasts

These main contrasts are not simple averages across the full LE1 window; they are the condition contrast at the model's reference point in the cubic time basis.

| comparison | looks | beta | 95% CI | P(beta > 0) | reading |
|---|---|---:|---:|---:|---|
| all direct vs all inverse | agent | 0.069 | [-0.138, 0.285] | 0.753 | no clear difference |
| all direct vs all inverse | patient | 0.002 | [-0.327, 0.343] | 0.503 | no clear difference |
| direct 1-1 vs direct 1-2 | agent | 0.089 | [-0.359, 0.530] | 0.659 | no clear difference |
| direct 1-1 vs direct 1-2 | patient | -0.242 | [-0.799, 0.308] | 0.199 | no clear difference |
| inverse 2-1 vs inverse 2-2 | agent | 0.040 | [-0.421, 0.504] | 0.575 | no clear difference |
| inverse 2-1 vs inverse 2-2 | patient | -0.028 | [-0.725, 0.669] | 0.467 | no clear difference |
| direct 1-1 vs inverse 2-2 | agent | 0.054 | [-0.339, 0.460] | 0.606 | no clear difference |
| direct 1-1 vs inverse 2-2 | patient | -0.167 | [-0.693, 0.349] | 0.259 | no clear difference |

## Clear Time-Course Effects

| comparison | looks | time interaction | beta | 95% CI | P(beta > 0) | reading |
|---|---|---|---:|---:|---:|---|
| all direct vs all inverse | agent | linear x contrast | 12.966 | [0.895, 25.891] | 0.982 | clear positive time-course difference |
| direct 1-1 vs direct 1-2 | patient | quadratic x contrast | 7.162 | [1.339, 13.232] | 0.993 | clear positive curvature difference |
| direct 1-1 vs direct 1-2 | patient | cubic x contrast | -9.030 | [-15.167, -3.081] | 0.001 | clear negative cubic difference |
| inverse 2-1 vs inverse 2-2 | agent | quadratic x contrast | 7.390 | [2.271, 12.344] | 0.999 | clear positive curvature difference |
| inverse 2-1 vs inverse 2-2 | agent | cubic x contrast | -5.820 | [-10.803, -0.576] | 0.014 | clear negative cubic difference |
| inverse 2-1 vs inverse 2-2 | patient | quadratic x contrast | -23.829 | [-30.056, -17.911] | 0.000 | clear negative curvature difference |
| direct 1-1 vs inverse 2-2 | agent | quadratic x contrast | 8.229 | [2.924, 13.631] | 0.998 | clear positive curvature difference |
| direct 1-1 vs inverse 2-2 | patient | quadratic x contrast | -12.435 | [-18.405, -6.630] | 0.000 | clear negative curvature difference |

## Short Reading

1. LE1 does not show clear main differences in overall agent or patient looks for any of the four comparisons.
2. The strongest evidence is in the shape of the fixation trajectories over time.
3. All direct vs all inverse differs clearly for agent looks in the linear time interaction.
4. The finer-grained comparisons show several clear quadratic/cubic time-course differences, especially for patient looks in direct 1-1 vs direct 1-2 and inverse 2-1 vs inverse 2-2.
