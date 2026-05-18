# Koryak LE3 Pairwise brms Models: Reader-Friendly Summary

Window: linguistic encoding 3.  
Models: separate brms models for agent looks and patient looks.  
Contrast coding: first-named condition = +1, second-named condition = -1. The reported beta is therefore half of the full condition difference; the full difference is 2 * beta.  
Evidence label: "clear" means the 95% credible interval excludes 0. "Directional" means posterior probability is mostly on one side, but the 95% credible interval still touches/crosses 0.

## Model Diagnostics

The run completed without divergent-transition or treedepth warnings in the log.

Fixed-effect diagnostics:

| diagnostic | range |
|---|---:|
| Rhat | 0.9996 to 1.0097 |
| bulk ESS | 807 to 8993 |
| tail ESS | 1301 to 3427 |

## Data Included

| comparison | condition | bins | participants |
|---|---:|---:|---:|
| direct 1-1 vs direct 1-2 | direct 1 agent, 1 patient | 4074 | 16 |
| direct 1-1 vs direct 1-2 | direct 1 agent, 2 patients | 4158 | 16 |
| inverse 2-1 vs inverse 2-2 | inverse 2 agents, 1 patient | 3864 | 16 |
| inverse 2-1 vs inverse 2-2 | inverse 2 agents, 2 patients | 3423 | 16 |
| direct 1-1 vs inverse 2-2 | direct 1 agent, 1 patient | 4074 | 16 |
| direct 1-1 vs inverse 2-2 | inverse 2 agents, 2 patients | 3423 | 16 |

## Main Pairwise Contrasts

These are the main condition contrasts from each model. They should be read as the condition difference at the model's reference point in the cubic time basis, not as a simple average across the whole window.

| comparison | looks | beta | 95% CI | P(beta > 0) | full difference | interpretation |
|---|---|---:|---:|---:|---:|---|
| direct 1-1 vs direct 1-2 | agent | -0.098 | [-0.640, 0.431] | 0.366 | -0.197 | no clear difference |
| direct 1-1 vs direct 1-2 | patient | -0.019 | [-0.563, 0.553] | 0.471 | -0.039 | no clear difference |
| inverse 2-1 vs inverse 2-2 | agent | 0.209 | [-0.256, 0.688] | 0.805 | 0.418 | no clear difference |
| inverse 2-1 vs inverse 2-2 | patient | -0.264 | [-0.853, 0.365] | 0.192 | -0.527 | no clear difference |
| direct 1-1 vs inverse 2-2 | agent | -0.421 | [-0.936, 0.104] | 0.056 | -0.842 | directional: direct 1-1 fewer agent looks |
| direct 1-1 vs inverse 2-2 | patient | 0.379 | [-0.224, 0.977] | 0.899 | 0.758 | directional: direct 1-1 more patient looks |

## Time-Course Effects

The cubic time interactions ask whether the difference between the two conditions changes over the LE3 window.

| comparison | looks | time term | beta | 95% CI | P(beta > 0) | interpretation |
|---|---|---|---:|---:|---:|---|
| direct 1-1 vs direct 1-2 | agent | linear x contrast | 3.163 | [-12.767, 18.857] | 0.664 | no clear trajectory difference |
| direct 1-1 vs direct 1-2 | agent | quadratic x contrast | 1.344 | [-4.471, 6.933] | 0.675 | no clear trajectory difference |
| direct 1-1 vs direct 1-2 | agent | cubic x contrast | -4.395 | [-10.199, 1.582] | 0.069 | directional negative cubic difference |
| direct 1-1 vs direct 1-2 | patient | linear x contrast | -5.945 | [-20.638, 8.536] | 0.205 | no clear trajectory difference |
| direct 1-1 vs direct 1-2 | patient | quadratic x contrast | -5.624 | [-11.004, -0.184] | 0.021 | clear negative quadratic difference |
| direct 1-1 vs direct 1-2 | patient | cubic x contrast | 5.481 | [0.251, 10.621] | 0.980 | clear positive cubic difference |
| inverse 2-1 vs inverse 2-2 | agent | linear x contrast | -0.669 | [-15.326, 15.013] | 0.462 | no clear trajectory difference |
| inverse 2-1 vs inverse 2-2 | agent | quadratic x contrast | -5.997 | [-11.411, -0.508] | 0.015 | clear negative quadratic difference |
| inverse 2-1 vs inverse 2-2 | agent | cubic x contrast | -0.693 | [-5.810, 4.471] | 0.398 | no clear trajectory difference |
| inverse 2-1 vs inverse 2-2 | patient | linear x contrast | -3.552 | [-22.510, 14.568] | 0.359 | no clear trajectory difference |
| inverse 2-1 vs inverse 2-2 | patient | quadratic x contrast | -3.094 | [-8.700, 2.758] | 0.142 | no clear trajectory difference |
| inverse 2-1 vs inverse 2-2 | patient | cubic x contrast | 1.200 | [-4.693, 6.885] | 0.659 | no clear trajectory difference |
| direct 1-1 vs inverse 2-2 | agent | linear x contrast | -0.970 | [-14.422, 13.181] | 0.440 | no clear trajectory difference |
| direct 1-1 vs inverse 2-2 | agent | quadratic x contrast | 2.333 | [-3.115, 7.864] | 0.803 | no clear trajectory difference |
| direct 1-1 vs inverse 2-2 | agent | cubic x contrast | -5.327 | [-10.759, 0.247] | 0.031 | directional negative cubic difference |
| direct 1-1 vs inverse 2-2 | patient | linear x contrast | -6.720 | [-22.205, 8.348] | 0.192 | no clear trajectory difference |
| direct 1-1 vs inverse 2-2 | patient | quadratic x contrast | -3.588 | [-8.861, 1.483] | 0.085 | directional negative quadratic difference |
| direct 1-1 vs inverse 2-2 | patient | cubic x contrast | 2.580 | [-2.719, 7.786] | 0.840 | no clear trajectory difference |

## Short Reading

1. Direct 1-1 vs direct 1-2: there is no clear overall difference in agent or patient looks. The patient-look trajectory differs, with clear quadratic and cubic contrast-by-time effects.
2. Inverse 2-1 vs inverse 2-2: there is no clear overall difference in agent or patient looks. The agent-look trajectory differs in the quadratic time component.
3. Direct 1-1 vs inverse 2-2: the main effects go in the expected direction, with fewer agent looks and more patient looks for direct 1-1, but the 95% credible intervals cross 0. This comparison is directional rather than clear in this narrower subset.
