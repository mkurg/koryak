suppressPackageStartupMessages({
  library(brms)
  library(dplyr)
  library(posterior)
  library(readr)
  library(tibble)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 9) {
  stop(
    "Usage: Rscript fit_brms_condition_pairwise.R ",
    "<trial_bins.csv> <output_dir> <window_key> <window_label> ",
    "<contrast_id> <condition_a> <label_a> <condition_b> <label_b>"
  )
}

trial_bins_path <- args[[1]]
output_dir <- args[[2]]
target_window_key <- args[[3]]
window_label <- args[[4]]
contrast_id <- args[[5]]
condition_a <- args[[6]]
label_a <- args[[7]]
condition_b <- args[[8]]
label_b <- args[[9]]

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

draw_summary <- function(model, model_name) {
  fixed_draws <- as.data.frame(fixef(model, summary = FALSE))
  bind_rows(lapply(names(fixed_draws), function(term) {
    values <- fixed_draws[[term]]
    tibble(
      contrast_id = contrast_id,
      comparison = paste(label_a, "vs", label_b),
      model = model_name,
      term = term,
      estimate = mean(values),
      ci_95_lower = unname(quantile(values, 0.025)),
      ci_95_upper = unname(quantile(values, 0.975)),
      p_beta_gt_0 = mean(values > 0),
      full_difference_estimate = if_else(grepl("contrast_code", term), 2 * mean(values), NA_real_),
      full_difference_ci_95_lower = if_else(grepl("contrast_code", term), 2 * unname(quantile(values, 0.025)), NA_real_),
      full_difference_ci_95_upper = if_else(grepl("contrast_code", term), 2 * unname(quantile(values, 0.975)), NA_real_)
    )
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
      contrast_id = contrast_id,
      comparison = paste(label_a, "vs", label_b),
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
    contrast_id = contrast_id,
    comparison = paste(label_a, "vs", label_b),
    model = model_name,
    max_rhat = max(draws$rhat, na.rm = TRUE),
    min_bulk_ess = min(draws$ess_bulk, na.rm = TRUE),
    min_tail_ess = min(draws$ess_tail, na.rm = TRUE),
    worst_bulk_variable = draws$variable[which.min(draws$ess_bulk)],
    worst_tail_variable = draws$variable[which.min(draws$ess_tail)]
  )
}

sampler_diagnostics <- function(model, model_name) {
  sampler <- rstan::get_sampler_params(model$fit, inc_warmup = FALSE)
  tibble(
    contrast_id = contrast_id,
    comparison = paste(label_a, "vs", label_b),
    model = model_name,
    divergent_transitions = sum(vapply(sampler, function(x) sum(x[, "divergent__"]), numeric(1))),
    max_treedepth_hits = sum(vapply(sampler, function(x) sum(x[, "treedepth__"] >= max_treedepth), numeric(1)))
  )
}

raw <- read_csv(trial_bins_path, show_col_types = FALSE)

model_df <- raw |>
  filter(
    window_key == target_window_key,
    condition_key %in% c(condition_a, condition_b)
  ) |>
  mutate(
    participant = factor(participant),
    item = factor(image),
    condition_key = as.character(condition_key),
    contrast_code = if_else(condition_key == condition_a, 1, -1),
    participant_condition = interaction(participant, condition_key, drop = TRUE),
    time = as.numeric(time_rel),
    N = as.numeric(n_samples),
    agent.sum = round(as.numeric(agent_prop) * N),
    pat.sum = round(as.numeric(patient_prop) * N),
    agent.sum = pmin(pmax(agent.sum, 0), N),
    pat.sum = pmin(pmax(pat.sum, 0), N),
    log.agent = log((agent.sum + 0.5) / (N - agent.sum + 0.5)),
    wts.agent = 1 / (agent.sum + 0.5) + 1 / (N - agent.sum + 0.5),
    log.pat = log((pat.sum + 0.5) / (N - pat.sum + 0.5)),
    wts.pat = 1 / (pat.sum + 0.5) + 1 / (N - pat.sum + 0.5)
  )

if (nrow(model_df) == 0) {
  stop("No model rows found for requested window and conditions.")
}

output_prefix <- paste0("brms_", window_label, "_", contrast_id)

write_csv(
  tibble(
    chains = chains,
    cores = cores,
    iter = iter,
    warmup = warmup,
    refresh = refresh,
    adapt_delta = adapt_delta,
    max_treedepth = max_treedepth,
    file_refit = file_refit,
    window_key = target_window_key,
    window_label = window_label,
    contrast_id = contrast_id,
    positive_condition = condition_a,
    negative_condition = condition_b,
    positive_label = label_a,
    negative_label = label_b
  ),
  file.path(output_dir, "run_config.csv")
)

counts <- model_df |>
  group_by(condition_key) |>
  summarise(
    contrast_id = contrast_id,
    comparison = paste(label_a, "vs", label_b),
    participants = n_distinct(participant),
    total_bins = n(),
    trials = n_distinct(paste(participant, block, image, sep = "||")),
    .groups = "drop"
  )

write_csv(counts, file.path(output_dir, paste0(output_prefix, "_counts.csv")))
write_csv(model_df, file.path(output_dir, paste0(window_label, "_", contrast_id, "_model_data.csv")))

agent_formula <- bf(
  log.agent | weights(1 / wts.agent) ~ poly(time, degree = 3) * contrast_code +
    (1 + time || participant_condition) +
    (1 + time || participant) +
    (1 | item)
)

patient_formula <- bf(
  log.pat | weights(1 / wts.pat) ~ poly(time, degree = 3) * contrast_code +
    (1 + time || participant_condition) +
    (1 + time || participant) +
    (1 | item)
)

message("Fitting ", contrast_id, " agent looks")
fit_agent <- brm(
  formula = agent_formula,
  data = model_df,
  family = gaussian(),
  chains = chains,
  cores = cores,
  iter = iter,
  warmup = warmup,
  seed = 20260523,
  backend = "rstan",
  control = list(adapt_delta = adapt_delta, max_treedepth = max_treedepth),
  refresh = refresh,
  file = file.path(output_dir, paste0(output_prefix, "_agent")),
  file_refit = file_refit
)

message("Fitting ", contrast_id, " patient looks")
fit_patient <- brm(
  formula = patient_formula,
  data = model_df,
  family = gaussian(),
  chains = chains,
  cores = cores,
  iter = iter,
  warmup = warmup,
  seed = 20260524,
  backend = "rstan",
  control = list(adapt_delta = adapt_delta, max_treedepth = max_treedepth),
  refresh = refresh,
  file = file.path(output_dir, paste0(output_prefix, "_patient")),
  file_refit = file_refit
)

summaries <- bind_rows(
  draw_summary(fit_agent, "agent_looks"),
  draw_summary(fit_patient, "patient_looks")
)

diagnostics <- bind_rows(
  diagnostic_summary(fit_agent, "agent_looks"),
  diagnostic_summary(fit_patient, "patient_looks")
)

all_diagnostics <- bind_rows(
  all_parameter_diagnostics(fit_agent, "agent_looks"),
  all_parameter_diagnostics(fit_patient, "patient_looks")
)

sampler_diag <- bind_rows(
  sampler_diagnostics(fit_agent, "agent_looks"),
  sampler_diagnostics(fit_patient, "patient_looks")
)

write_csv(summaries, file.path(output_dir, paste0(output_prefix, "_fixed_effects.csv")))
write_csv(diagnostics, file.path(output_dir, paste0(output_prefix, "_diagnostics.csv")))
write_csv(all_diagnostics, file.path(output_dir, paste0(output_prefix, "_all_parameter_diagnostics.csv")))
write_csv(sampler_diag, file.path(output_dir, paste0(output_prefix, "_sampler_diagnostics.csv")))

capture.output(summary(fit_agent), file = file.path(output_dir, paste0(output_prefix, "_agent_summary.txt")))
capture.output(summary(fit_patient), file = file.path(output_dir, paste0(output_prefix, "_patient_summary.txt")))

sink(file.path(output_dir, "reader_friendly_summary.txt"))
cat("Koryak Bayesian pairwise model\n")
cat("==============================\n\n")
cat("Window:", window_label, "(", target_window_key, ")\n")
cat("Comparison:", label_a, "vs", label_b, "\n")
cat("Coding: +1 =", label_a, "; -1 =", label_b, "\n")
cat("Model: empirical-logit fixation proportions ~ cubic time * contrast + random effects by participant condition, participant, and item.\n\n")
cat("Counts:\n")
print(counts)
cat("\nFixed effects:\n")
print(summaries)
cat("\nFixed-effect diagnostics:\n")
print(diagnostics)
cat("\nAll-parameter diagnostics:\n")
print(all_diagnostics)
cat("\nSampler diagnostics:\n")
print(sampler_diag)
sink()

message("Wrote brms ", window_label, " ", contrast_id, " outputs to: ", output_dir)
