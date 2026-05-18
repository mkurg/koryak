# Koryak Bayesian Speech Onset Latency Models

Bayesian analogs were fit to the same log-transformed RT outcome as the frequentist models, with random intercepts and random slopes by item and participant.

## Direct vs Inverse

Dataset: 879 clean trials. Direct: 496 trials; inverse: 383 trials.

Model: `log(rt) ~ direct + (1 + direct | item) + (1 + direct | participant)`

The direct-minus-inverse contrast was negative but uncertain:

| Contrast | Beta | 95% CI | P(beta > 0) | Ratio | Interpretation |
|---|---:|---:|---:|---:|---|
| Direct - inverse | -0.040 | [-0.106, 0.022] | 0.108 | 0.961 | Direct sentences were estimated about 4.0% faster than inverse sentences, but the CI includes no difference. |

Because the beta is coded as direct minus inverse, `P(beta > 0) = 0.108` means the posterior probability that direct sentences are slower is low. Equivalently, `P(beta < 0) = 0.892`, so there is suggestive but not decisive evidence that direct sentences are faster.

## Four-Way Model

Dataset: 783 clean trials. Direct 1-1: 208; direct 1-2: 208; inverse 2-2: 171; inverse 2-1: 196.

Model: `log(rt) ~ condition4 + (1 + condition4 | item) + (1 + condition4 | participant)`

Fixed effects are relative to direct 1-1:

| Contrast | Beta | 95% CI | P(beta > 0) | Ratio | Interpretation |
|---|---:|---:|---:|---:|---|
| Direct 1-2 - direct 1-1 | 0.030 | [-0.071, 0.132] | 0.722 | 1.030 | Direct 1-2 was estimated about 3.0% slower than direct 1-1, uncertain. |
| Inverse 2-2 - direct 1-1 | 0.038 | [-0.072, 0.145] | 0.753 | 1.038 | Inverse 2-2 was estimated about 3.8% slower than direct 1-1, uncertain. |
| Inverse 2-1 - direct 1-1 | 0.079 | [-0.027, 0.183] | 0.924 | 1.082 | Inverse 2-1 was estimated about 8.2% slower than direct 1-1; this is the strongest trend, but the CI still includes no difference. |

Model-estimated condition means:

| Condition | Estimated RT | 95% CI |
|---|---:|---:|
| Direct 1-1 | 2562 ms | [2195, 2990] |
| Direct 1-2 | 2639 ms | [2256, 3090] |
| Inverse 2-2 | 2661 ms | [2274, 3131] |
| Inverse 2-1 | 2773 ms | [2353, 3283] |

Pairwise contrasts, coded as first condition minus second condition:

| Contrast | Beta | 95% CI | P(beta > 0) |
|---|---:|---:|---:|
| Direct 1-1 - direct 1-2 | -0.030 | [-0.132, 0.071] | 0.278 |
| Direct 1-1 - inverse 2-2 | -0.038 | [-0.145, 0.072] | 0.247 |
| Direct 1-1 - inverse 2-1 | -0.079 | [-0.183, 0.027] | 0.076 |
| Direct 1-2 - inverse 2-2 | -0.008 | [-0.118, 0.103] | 0.442 |
| Direct 1-2 - inverse 2-1 | -0.049 | [-0.162, 0.058] | 0.182 |
| Inverse 2-2 - inverse 2-1 | -0.041 | [-0.160, 0.074] | 0.244 |

## Convergence

Both models completed 4 chains with 2000 iterations each, 1000 warmup, `adapt_delta = 0.99`, and `max_treedepth = 12`.

Fixed-effect diagnostics were good. Fixed-effect Rhats were approximately 1.00; the smallest fixed-effect bulk ESS was 791, and most contrast ESS values were above 2000.

There were no divergent transitions and no max-treedepth hits in either model.

Stan did warn about low bulk ESS for some nuisance random-effect SD parameters:

| Model | Max Rhat | Min bulk ESS | Parameter causing lowest bulk ESS |
|---|---:|---:|---|
| Direct vs inverse | 1.010 | 173 | `sd_item__direct` |
| Four-way | 1.012 | 372 | `sd_item__condition4inverse_2_2` |

This warning is worth reporting, but it does not undermine the main fixed-effect contrasts in the same way as the singular frequentist fits. The substantive conclusion is that the Bayesian models show weak/suggestive RT tendencies, especially slower inverse 2-1 responses, but no contrast has a 95% credible interval excluding zero.
