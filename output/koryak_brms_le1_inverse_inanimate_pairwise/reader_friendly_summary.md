# Koryak LE1 Pairwise Bayesian Model: Inverse Inanimate Patients

Comparison: inverse 2 agents, 2 patients, inanimate patient vs inverse 2 agents, 1 patient, inanimate patient.

Coding: `+1 = inverse 2-2 inanimate`, `-1 = inverse 2-1 inanimate`. Therefore, contrast terms are half-differences; the `full difference` columns are `2 * beta`.

## Data Included

| Condition | Sentences included | Participants | 50 ms bins |
|---|---:|---:|---:|
| Inverse 2-1, inanimate patient | 93 | 16 | 1964 |
| Inverse 2-2, inanimate patient | 74 | 14 | 1357 |
| Total | 167 | 16 | 3321 |

## Agent Looks

| Term | Beta | 95% CI | P(beta > 0) | Full difference |
|---|---:|---:|---:|---:|
| Main contrast | -0.140 | [-0.832, 0.540] | 0.336 | -0.280 [-1.665, 1.080] |
| Time 1 x contrast | 22.122 | [7.231, 37.128] | 0.998 | 44.244 [14.463, 74.255] |
| Time 2 x contrast | -2.087 | [-7.485, 3.276] | 0.223 | -4.175 [-14.971, 6.553] |
| Time 3 x contrast | 5.408 | [0.316, 10.554] | 0.981 | 10.815 [0.632, 21.109] |

Reader-friendly interpretation: there is no clear main contrast at the model reference point. The agent-looking trajectory differs over LE1, with credible positive Time 1 and Time 3 interactions.

## Patient Looks

| Term | Beta | 95% CI | P(beta > 0) | Full difference |
|---|---:|---:|---:|---:|
| Main contrast | 0.168 | [-0.730, 1.023] | 0.653 | 0.335 [-1.459, 2.047] |
| Time 1 x contrast | -17.872 | [-33.216, -2.920] | 0.011 | -35.744 [-66.432, -5.840] |
| Time 2 x contrast | 11.512 | [5.255, 17.793] | 1.000 | 23.023 [10.510, 35.587] |
| Time 3 x contrast | -6.538 | [-12.938, -0.322] | 0.020 | -13.076 [-25.876, -0.645] |

Reader-friendly interpretation: there is no clear main contrast at the model reference point. The patient-looking trajectory differs over LE1, with credible Time 1, Time 2, and Time 3 interactions.

## Convergence

Both models used 4 chains, 2000 iterations, 1000 warmup, `adapt_delta = 0.99`, and `max_treedepth = 12`.

| Model | Max Rhat | Min bulk ESS | Min tail ESS | Divergences | Max treedepth hits |
|---|---:|---:|---:|---:|---:|
| Agent looks | 1.0106 | 612 | 1661 | 0 | 0 |
| Patient looks | 1.0076 | 611 | 910 | 0 | 0 |

Fixed-effect diagnostics were also good: all fixed-effect Rhats were approximately 1.00, and fixed-effect bulk ESS values were at least 1297 for agent looks and 1510 for patient looks.
