suppressPackageStartupMessages({
  library(brms)
  library(dplyr)
  library(posterior)
  library(readr)
  library(tibble)
})

args <- commandArgs(trailingOnly = TRUE)
direct_inverse_path <- ifelse(
  length(args) >= 1,
  args[[1]],
  "output/koryak_behavioral_latency/koryak_latency_model_data.csv"
)
fourway_path <- ifelse(
  length(args) >= 2,
  args[[2]],
  "output/koryak_behavioral_latency_4way/koryak_latency_4way_model_data.csv"
)
output_dir <- ifelse(length(args) >= 3, args[[3]], "output/koryak_behavioral_latency_bayes")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

env_int <- function(name, default) {
  value <- Sys.getenv(name, unset = "")
  if (nzchar(value)) as.integer(value) else default
}

env_num <- function(name, default) {
  value <- Sys.getenv(name, unset = "")
  if (nzchar(value)) as.numeric(value) else default
}

chains <- env_int("KORYAK_BRMS_CHAINS", 4)
cores <- env_int("KORYAK_BRMS_CORES", chains)
iter <- env_int("KORYAK_BRMS_ITER", 2000)
warmup <- env_int("KORYAK_BRMS_WARMUP", 1000)
refresh <- env_int("KORYAK_BRMS_REFRESH", 100)
adapt_delta <- env_num("KORYAK_BRMS_ADAPT_DELTA", 0.99)
max_treedepth <- env_int("KORYAK_BRMS_MAX_TREEDEPTH", 12)
file_refit <- Sys.getenv("KORYAK_BRMS_FILE_REFIT", unset = "on_change")

options(mc.cores = cores)
rstan::rstan_options(auto_write = TRUE)

summarise_values <- function(values) {
  tibble(
    estimate_log_ms = mean(values),
    ci_95_lower_log_ms = unname(quantile(values, 0.025)),
    ci_95_upper_log_ms = unname(quantile(values, 0.975)),
    p_beta_gt_0 = mean(values > 0),
    ratio = exp(mean(values)),
    ci_95_lower_ratio = exp(unname(quantile(values, 0.025))),
    ci_95_upper_ratio = exp(unname(quantile(values, 0.975))),
    percent_change = 100 * (ratio - 1)
  )
}

fixed_summary <- function(model, model_name) {
  fixed_draws <- as.data.frame(fixef(model, summary = FALSE))
  bind_rows(lapply(names(fixed_draws), function(term) {
    summarise_values(fixed_draws[[term]]) |>
      mutate(model = model_name, term = term, .before = 1)
  }))
}

diagnostic_summary <- function(model, model_name) {
  fixed <- as.data.frame(summary(model)$fixed)
  fixed$term <- rownames(fixed)
  lower_col <- grep("^l-", names(fixed), value = TRUE)[1]
  upper_col <- grep("^u-", names(fixed), value = TRUE)[1]
  fixed |>
    as_tibble() |>
    transmute(
      model = model_name,
      term,
      estimate = Estimate,
      estimate_error = Est.Error,
      q2.5 = .data[[lower_col]],
      q97.5 = .data[[upper_col]],
      rhat = Rhat,
      bulk_ess = Bulk_ESS,
      tail_ess = Tail_ESS
    )
}

all_parameter_diagnostics <- function(model, model_name) {
  draws <- posterior::summarise_draws(posterior::as_draws_df(model))
  tibble(
    model = model_name,
    max_rhat = max(draws$rhat, na.rm = TRUE),
    min_bulk_ess = min(draws$ess_bulk, na.rm = TRUE),
    min_tail_ess = min(draws$ess_tail, na.rm = TRUE),
    worst_bulk_variable = draws$variable[which.min(draws$ess_bulk)],
    worst_tail_variable = draws$variable[which.min(draws$ess_tail)]
  )
}

direct_inverse_df <- read_csv(direct_inverse_path, show_col_types = FALSE) |>
  mutate(
    log_rt = log(rt),
    direct = as.numeric(direct),
    participant = factor(participant),
    item = factor(item)
  )

fourway_levels <- c("direct_1_1", "direct_1_2", "inverse_2_2", "inverse_2_1")
fourway_df <- read_csv(fourway_path, show_col_types = FALSE) |>
  mutate(
    log_rt = log(rt),
    condition4 = factor(condition4, levels = fourway_levels),
    participant = factor(participant),
    item = factor(item)
  )

priors_direct_inverse <- c(
  prior(normal(7.8, 1), class = Intercept),
  prior(normal(0, 0.5), class = b),
  prior(exponential(2), class = sd),
  prior(exponential(2), class = sigma),
  prior(lkj(2), class = cor)
)

priors_fourway <- c(
  prior(normal(7.8, 1), class = Intercept),
  prior(normal(0, 0.5), class = b),
  prior(exponential(2), class = sd),
  prior(exponential(2), class = sigma),
  prior(lkj(2), class = cor)
)

write_csv(
  tibble(
    chains = chains,
    cores = cores,
    iter = iter,
    warmup = warmup,
    refresh = refresh,
    adapt_delta = adapt_delta,
    max_treedepth = max_treedepth,
    file_refit = file_refit
  ),
  file.path(output_dir, "run_config.csv")
)

write_csv(
  direct_inverse_df |>
    count(sentence_type, name = "n_trials") |>
    mutate(model = "direct_inverse", .before = 1),
  file.path(output_dir, "bayes_latency_direct_inverse_counts.csv")
)

write_csv(
  fourway_df |>
    count(condition4, name = "n_trials") |>
    mutate(model = "fourway", .before = 1),
  file.path(output_dir, "bayes_latency_4way_counts.csv")
)

message("Fitting Bayesian direct-vs-inverse RT model")
fit_direct_inverse <- brm(
  log_rt ~ direct + (1 + direct | item) + (1 + direct | participant),
  data = direct_inverse_df,
  family = gaussian(),
  prior = priors_direct_inverse,
  chains = chains,
  cores = cores,
  iter = iter,
  warmup = warmup,
  seed = 20260521,
  backend = "rstan",
  control = list(adapt_delta = adapt_delta, max_treedepth = max_treedepth),
  refresh = refresh,
  file = file.path(output_dir, "brms_latency_direct_inverse"),
  file_refit = file_refit
)

message("Fitting Bayesian four-way RT model")
fit_fourway <- brm(
  log_rt ~ condition4 + (1 + condition4 | item) + (1 + condition4 | participant),
  data = fourway_df,
  family = gaussian(),
  prior = priors_fourway,
  chains = chains,
  cores = cores,
  iter = iter,
  warmup = warmup,
  seed = 20260522,
  backend = "rstan",
  control = list(adapt_delta = adapt_delta, max_treedepth = max_treedepth),
  refresh = refresh,
  file = file.path(output_dir, "brms_latency_4way"),
  file_refit = file_refit
)

direct_inverse_fixed <- fixed_summary(fit_direct_inverse, "direct_inverse") |>
  mutate(
    interpretation = case_when(
      term == "direct" ~ "direct minus inverse on log RT scale",
      term == "Intercept" ~ "inverse log RT intercept",
      TRUE ~ ""
    )
  )

write_csv(
  direct_inverse_fixed,
  file.path(output_dir, "bayes_latency_direct_inverse_fixed_effects.csv")
)

fourway_fixed <- fixed_summary(fit_fourway, "fourway") |>
  mutate(
    interpretation = case_when(
      term == "Intercept" ~ "direct_1_1 log RT intercept",
      term == "condition4direct_1_2" ~ "direct_1_2 minus direct_1_1",
      term == "condition4inverse_2_2" ~ "inverse_2_2 minus direct_1_1",
      term == "condition4inverse_2_1" ~ "inverse_2_1 minus direct_1_1",
      TRUE ~ ""
    )
  )

write_csv(fourway_fixed, file.path(output_dir, "bayes_latency_4way_fixed_effects.csv"))

fourway_draws <- as.data.frame(fixef(fit_fourway, summary = FALSE))
condition_draws <- tibble(
  direct_1_1 = fourway_draws$Intercept,
  direct_1_2 = fourway_draws$Intercept + fourway_draws$condition4direct_1_2,
  inverse_2_2 = fourway_draws$Intercept + fourway_draws$condition4inverse_2_2,
  inverse_2_1 = fourway_draws$Intercept + fourway_draws$condition4inverse_2_1
)

pairwise_levels <- combn(fourway_levels, 2, simplify = FALSE)
fourway_pairwise <- bind_rows(lapply(pairwise_levels, function(levels) {
  level_a <- levels[[1]]
  level_b <- levels[[2]]
  values <- condition_draws[[level_a]] - condition_draws[[level_b]]
  summarise_values(values) |>
    mutate(
      comparison = paste(level_a, "vs", level_b),
      interpretation = paste(level_a, "minus", level_b, "on log RT scale"),
      .before = 1
    )
}))

write_csv(fourway_pairwise, file.path(output_dir, "bayes_latency_4way_pairwise.csv"))

condition_summary <- bind_rows(lapply(fourway_levels, function(level) {
  values <- condition_draws[[level]]
  summarise_values(values) |>
    transmute(
      condition4 = level,
      estimated_log_rt = estimate_log_ms,
      ci_95_lower_log_rt = ci_95_lower_log_ms,
      ci_95_upper_log_rt = ci_95_upper_log_ms,
      estimated_rt_ms = exp(estimate_log_ms),
      ci_95_lower_rt_ms = exp(ci_95_lower_log_ms),
      ci_95_upper_rt_ms = exp(ci_95_upper_log_ms)
    )
}))

write_csv(condition_summary, file.path(output_dir, "bayes_latency_4way_condition_estimates.csv"))

diagnostics <- bind_rows(
  diagnostic_summary(fit_direct_inverse, "direct_inverse"),
  diagnostic_summary(fit_fourway, "fourway")
)
write_csv(diagnostics, file.path(output_dir, "bayes_latency_fixed_effect_diagnostics.csv"))

all_diagnostics <- bind_rows(
  all_parameter_diagnostics(fit_direct_inverse, "direct_inverse"),
  all_parameter_diagnostics(fit_fourway, "fourway")
)
write_csv(all_diagnostics, file.path(output_dir, "bayes_latency_all_parameter_diagnostics.csv"))

capture.output(summary(fit_direct_inverse), file = file.path(output_dir, "brms_latency_direct_inverse_summary.txt"))
capture.output(summary(fit_fourway), file = file.path(output_dir, "brms_latency_4way_summary.txt"))

sink(file.path(output_dir, "bayes_latency_reader_friendly_summary.txt"))
cat("Koryak Bayesian speech onset latency models\n")
cat("==========================================\n\n")
cat("Models:\n")
cat("1. log(rt) ~ direct + (1 + direct | item) + (1 + direct | participant)\n")
cat("2. log(rt) ~ condition4 + (1 + condition4 | item) + (1 + condition4 | participant)\n\n")
cat("Priors: normal(7.8, 1) intercept; normal(0, 0.5) fixed effects; exponential(2) SD/sigma; LKJ(2) correlations.\n\n")
cat("Direct vs inverse fixed effects:\n")
print(direct_inverse_fixed)
cat("\nFour-way fixed effects:\n")
print(fourway_fixed)
cat("\nFour-way pairwise contrasts:\n")
print(fourway_pairwise)
cat("\nFixed-effect diagnostics:\n")
print(diagnostics)
cat("\nAll-parameter diagnostics:\n")
print(all_diagnostics)
sink()

message("Wrote Bayesian latency outputs to: ", output_dir)
