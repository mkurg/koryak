# Koryak LE3 Brms Model Summary

Model set: linguistic encoding III, all clean direct vs all clean inverse AVP sentences.

Data:
- Direct bins: 9,870
- Inverse bins: 7,560
- Participants: 16
- Chains: 4
- Iterations: 2,000 per chain, 1,000 warmup
- Coding: `direct_vs_inverse = +1` for direct and `-1` for inverse

## Main Direct-Inverse Contrast

Because the contrast is coded `+1 / -1`, the model coefficient is half of the full direct-minus-inverse difference on the log-odds scale.

| Outcome | Beta | 95% CI | P(beta > 0) | Reader-Friendly Interpretation |
|---|---:|---:|---:|---|
| Agent looks | -0.313 | [-0.559, -0.071] | 0.009 | Direct sentences had fewer agent looks than inverse sentences. |
| Patient looks | 0.327 | [0.042, 0.613] | 0.986 | Direct sentences had more patient looks than inverse sentences. |

As full direct-minus-inverse log-odds differences:

| Outcome | Full Direct-Inverse Difference | 95% CI | Odds Ratio |
|---|---:|---:|---:|
| Agent looks | -0.627 | [-1.118, -0.141] | 0.53 |
| Patient looks | 0.654 | [0.085, 1.226] | 1.92 |

## Time-Course Terms

| Outcome | Term | Beta | 95% CI | P(beta > 0) | Interpretation |
|---|---|---:|---:|---:|---|
| Agent looks | Linear time | -50.957 | [-73.662, -28.770] | 0.000 | Agent looks decreased over time overall. |
| Agent looks | Quadratic time | -3.950 | [-9.582, 1.679] | 0.084 | No clear quadratic trend. |
| Agent looks | Cubic time | -2.447 | [-8.035, 3.293] | 0.191 | No clear cubic trend. |
| Patient looks | Linear time | 47.548 | [31.501, 64.704] | 1.000 | Patient looks increased over time overall. |
| Patient looks | Quadratic time | -5.493 | [-11.282, 0.541] | 0.037 | Weak/uncertain negative quadratic trend. |
| Patient looks | Cubic time | 15.052 | [9.641, 20.500] | 1.000 | Clear cubic component in the patient-look trajectory. |

## Direct-Inverse Time-Course Differences

| Outcome | Interaction Term | Beta | 95% CI | P(beta > 0) | Interpretation |
|---|---|---:|---:|---:|---|
| Agent looks | Linear time x direct-inverse | -13.756 | [-24.039, -4.424] | 0.003 | Direct and inverse agent-look trajectories differed clearly in the linear component. |
| Agent looks | Quadratic time x direct-inverse | 5.305 | [-0.217, 10.637] | 0.972 | Suggestive but CI still crosses zero. |
| Agent looks | Cubic time x direct-inverse | -4.401 | [-9.848, 1.003] | 0.062 | Suggestive but not decisive. |
| Patient looks | Linear time x direct-inverse | 1.394 | [-11.770, 15.022] | 0.583 | No clear trajectory difference. |
| Patient looks | Quadratic time x direct-inverse | 1.054 | [-4.666, 6.849] | 0.647 | No clear trajectory difference. |
| Patient looks | Cubic time x direct-inverse | -1.096 | [-6.804, 4.669] | 0.350 | No clear trajectory difference. |

## Convergence

Fixed-effect diagnostics look good:
- Rhat range for fixed effects: about 1.000 to 1.005
- Bulk ESS for fixed effects: all above 1,100
- Tail ESS for fixed effects: all above 1,800

The run log reported a low tail-ESS warning, likely for a non-fixed-effect parameter. Fixed-effect estimates above are stable enough to discuss.
