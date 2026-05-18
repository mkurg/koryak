# Reader-friendly summary of Koryak Bayesian gaze models

Significance criterion: a term is marked significant when its 95% credible interval does not include 0.
`P(beta > 0)` is the posterior probability that the coefficient is positive.

Contrast coding: `+1` is the first condition and `-1` is the second condition. So a positive main contrast means more looks to that referent in the first condition; a negative main contrast means more looks in the second condition.

## Significant main contrast effects

| Window | Looks to | Comparison | Direction | Estimate | 95% CI | P(beta > 0) | Trials |
|---|---:|---|---|---:|---:|---:|---:|
| Speech planning | agent | All direct vs all inverse | direct > inverse | 0.256 | [0.082, 0.431] | 0.998 | 830 |
| Speech planning | patient | All direct vs all inverse | inverse > direct | -0.218 | [-0.400, -0.037] | 0.009 | 830 |
| Speech planning | patient | Inverse 2 agents/1 patient vs inverse 2 agents/2 patients | inverse 2-2 > inverse 2-1 | -1.322 | [-2.580, -0.074] | 0.019 | 347 |
| Linguistic encoding II | patient | All direct vs all inverse | direct > inverse | 0.283 | [0.157, 0.410] | 1.000 | 830 |
| Linguistic encoding III | agent | All direct vs all inverse | inverse > direct | -0.261 | [-0.418, -0.105] | 0.000 | 830 |
| Linguistic encoding III | patient | All direct vs all inverse | direct > inverse | 0.226 | [0.087, 0.367] | 0.999 | 830 |
| Linguistic encoding III | agent | Direct animate patient vs direct inanimate patient | direct animate > direct inanimate | 1.229 | [0.093, 2.392] | 0.982 | 470 |
| 1000-2500 ms after speech onset | agent | All direct vs all inverse | inverse > direct | -0.225 | [-0.341, -0.108] | 0.000 | 830 |

## Plain-language takeaways

- The clearest direct-vs-inverse contrast is early and then reverses later: during speech planning, direct sentences show more agent looks and fewer patient looks than inverse sentences; by Linguistic encoding III and the later post-onset window, inverse sentences show more agent looks than direct sentences.
- Patient looks show the complementary pattern for direct-vs-inverse in Linguistic encoding II and III: direct sentences have more patient looks than inverse sentences.
- Number contrasts have very few stable main effects. The only main-effect signal is in speech planning for inverse 2-agent/1-patient vs inverse 2-agent/2-patient sentences: patient looks are higher for inverse 2-agent/2-patient sentences.
- Animacy contrasts mostly appear as time-course differences rather than stable average differences. The one stable main animacy effect is in Linguistic encoding III: direct animate-patient sentences have more agent looks than direct inanimate-patient sentences.

## Significant time-course interactions

These indicate that the shape of the gaze curve differs between the two conditions. They are not simple average differences; they say the contrast changes over relative time within the window.

| Window | Looks to | Comparison | Significant interaction terms |
|---|---:|---|---|
| Speech planning | agent | All direct vs all inverse | time:contrast + (0.49, P>0=0.985); time2:contrast + (1.04, P>0=0.999); time3:contrast - (-2.93, P>0=0.009) |
| Speech planning | agent | Direct 1 agent/1 patient vs direct 1 agent/2 patients | time:contrast + (1.24, P>0=1.000); time2:contrast + (5.46, P>0=1.000); time3:contrast - (-9.99, P>0=0.000) |
| Speech planning | patient | Direct 1 agent/1 patient vs direct 1 agent/2 patients | time:contrast - (-0.89, P>0=0.003); time2:contrast - (-5.29, P>0=0.000); time3:contrast + (10.68, P>0=1.000) |
| Speech planning | agent | Inverse 2 agents/1 patient vs inverse 2 agents/2 patients | time2:contrast - (-6.30, P>0=0.000); time3:contrast + (5.02, P>0=0.997) |
| Speech planning | patient | Inverse 2 agents/1 patient vs inverse 2 agents/2 patients | time2:contrast + (6.73, P>0=1.000); time3:contrast - (-6.89, P>0=0.000) |
| Speech planning | agent | Direct animate patient vs direct inanimate patient | time:contrast + (1.55, P>0=1.000); time2:contrast + (3.43, P>0=1.000); time3:contrast - (-6.25, P>0=0.000) |
| Speech planning | patient | Direct animate patient vs direct inanimate patient | time:contrast - (-0.89, P>0=0.002); time2:contrast - (-3.26, P>0=0.000) |
| Speech planning | agent | Inverse animate patient vs inverse inanimate patient | time:contrast + (1.29, P>0=1.000); time2:contrast + (3.76, P>0=1.000); time3:contrast - (-5.89, P>0=0.001) |
| Speech planning | patient | Inverse animate patient vs inverse inanimate patient | time:contrast - (-0.90, P>0=0.005); time2:contrast - (-4.05, P>0=0.000); time3:contrast + (3.75, P>0=0.979) |
| Linguistic encoding I | patient | Direct 1 agent/1 patient vs direct 1 agent/2 patients | time2:contrast + (1.33, P>0=1.000); time3:contrast - (-4.49, P>0=0.002) |
| Linguistic encoding I | agent | Inverse 2 agents/1 patient vs inverse 2 agents/2 patients | time2:contrast + (0.89, P>0=0.984) |
| Linguistic encoding I | patient | Inverse 2 agents/1 patient vs inverse 2 agents/2 patients | time2:contrast - (-3.21, P>0=0.000) |
| Linguistic encoding I | agent | Direct animate patient vs direct inanimate patient | time:contrast - (-0.91, P>0=0.000); time3:contrast + (2.87, P>0=0.983) |
| Linguistic encoding I | agent | Inverse animate patient vs inverse inanimate patient | time:contrast - (-2.03, P>0=0.000); time3:contrast + (7.28, P>0=1.000) |
| Linguistic encoding I | patient | Inverse animate patient vs inverse inanimate patient | time:contrast + (2.32, P>0=1.000); time2:contrast + (2.17, P>0=1.000); time3:contrast - (-8.29, P>0=0.000) |
| Linguistic encoding II | agent | All direct vs all inverse | time:contrast - (-0.43, P>0=0.006) |
| Linguistic encoding II | patient | All direct vs all inverse | time:contrast + (0.58, P>0=1.000); time2:contrast - (-0.98, P>0=0.000); time3:contrast - (-2.45, P>0=0.008) |
| Linguistic encoding II | patient | Direct 1 agent/1 patient vs direct 1 agent/2 patients | time3:contrast + (3.84, P>0=0.996) |
| Linguistic encoding II | agent | Direct animate patient vs direct inanimate patient | time:contrast + (0.47, P>0=0.978) |
| Linguistic encoding II | patient | Direct animate patient vs direct inanimate patient | time:contrast - (-0.98, P>0=0.000) |
| Linguistic encoding II | agent | Inverse animate patient vs inverse inanimate patient | time3:contrast + (3.05, P>0=0.981) |
| Linguistic encoding II | patient | Inverse animate patient vs inverse inanimate patient | time:contrast + (0.65, P>0=0.995); time3:contrast - (-4.44, P>0=0.001) |
| Linguistic encoding III | patient | Direct 1 agent/1 patient vs direct 1 agent/2 patients | time:contrast - (-0.59, P>0=0.012); time2:contrast - (-0.98, P>0=0.007) |
| Linguistic encoding III | agent | Inverse 2 agents/1 patient vs inverse 2 agents/2 patients | time2:contrast - (-0.98, P>0=0.009) |
| Linguistic encoding III | patient | Direct animate patient vs direct inanimate patient | time:contrast + (0.81, P>0=1.000); time3:contrast - (-4.66, P>0=0.000) |
| 1000-2500 ms after speech onset | agent | Direct 1 agent/1 patient vs direct 1 agent/2 patients | time:contrast + (0.54, P>0=0.992) |
| 1000-2500 ms after speech onset | agent | Direct animate patient vs direct inanimate patient | time3:contrast - (-2.72, P>0=0.011) |
| 1000-2500 ms after speech onset | agent | Inverse animate patient vs inverse inanimate patient | time2:contrast - (-0.93, P>0=0.004) |

## Where there was no significant main contrast

Most tested main contrasts were not credible average differences: 42 of 50 main contrast coefficients had intervals crossing 0. This is why the interaction table matters: many effects are time-local or curve-shape differences rather than stable whole-window differences.

## Files

- Full coefficients: `koryak_bayesian_model_results.csv`
- Contrast and interaction terms only: `koryak_bayesian_model_contrast_terms.csv`
- Method note: `model_method_notes.txt`