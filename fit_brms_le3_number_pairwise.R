suppressPackageStartupMessages({
  library(brms)
  library(dplyr)
  library(readr)
  library(tibble)
})

args <- commandArgs(trailingOnly = TRUE)
trial_bins_path <- ifelse(length(args) >= 1, args[[1]], "output/koryak_number_sentence_graphs/speech_planning_trial_bins.csv")
output_dir <- ifelse(length(args) >= 2, args[[2]], "output/koryak_brms_le3_number_pairwise")
target_window_key <- ifelse(length(args) >= 3, args[[3]], Sys.getenv("KORYAK_BRMS_WINDOW_KEY", unset = "linguistic_encoding_3"))
window_label <- ifelse(length(args) >= 4, args[[4]], Sys.getenv("KORYAK_BRMS_WINDOW_LABEL", unset = "le3"))
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

contrasts <- tribble(
  ~contrast_id, ~label_a, ~condition_a, ~label_b, ~condition_b,
  "direct_1_1_vs_direct_1_2",
  "direct 1 agent, 1 patient", "direct_1_agent_1_patient",
  "direct 1 agent, 2 patients", "direct_1_agent_2_patients",
  "inverse_2_1_vs_inverse_2_2",
  "inverse 2 agents, 1 patient", "inverse_2_agents_1_patient",
  "inverse 2 agents, 2 patients", "inverse_2_agents_2_patients",
  "direct_1_1_vs_inverse_2_2",
  "direct 1 agent, 1 patient", "direct_1_agent_1_patient",
  "inverse 2 agents, 2 patients", "inverse_2_agents_2_patients"
)

draw_summary <- function(model, model_name, contrast_id, label_a, label_b) {
  fixed_draws <- as.data.frame(fixef(model, summary = FALSE))
  fixed_names <- names(fixed_draws)
  bind_rows(lapply(fixed_names, function(term) {
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

diagnostic_summary <- function(model, model_name, contrast_id, label_a, label_b) {
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

raw <- read_csv(trial_bins_path, show_col_types = FALSE)

le3 <- raw |>
  filter(window_key == target_window_key) |>
  mutate(
    participant = factor(participant),
    item = factor(image),
    condition_key = as.character(condition_key),
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
    window_label = window_label
  ),
  file.path(output_dir, "run_config.csv")
)

all_summaries <- list()
all_diagnostics <- list()
all_counts <- list()

for (i in seq_len(nrow(contrasts))) {
  row <- contrasts[i, ]
  contrast_id <- row$contrast_id
  condition_a <- row$condition_a
  condition_b <- row$condition_b
  label_a <- row$label_a
  label_b <- row$label_b

  model_df <- le3 |>
    filter(condition_key %in% c(condition_a, condition_b)) |>
    mutate(
      contrast_code = if_else(condition_key == condition_a, 1, -1),
      participant_condition = interaction(participant, condition_key, drop = TRUE)
    )

  all_counts[[contrast_id]] <- model_df |>
    count(condition_key, participant, name = "n_bins") |>
    group_by(condition_key) |>
    summarise(
      contrast_id = contrast_id,
      comparison = paste(label_a, "vs", label_b),
      participants = n_distinct(participant),
      total_bins = sum(n_bins),
      .groups = "drop"
    )

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
    seed = 20260520 + i,
    backend = "rstan",
    control = list(adapt_delta = adapt_delta, max_treedepth = max_treedepth),
    refresh = refresh,
    file = file.path(output_dir, paste0("brms_", window_label, "_", contrast_id, "_agent")),
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
    seed = 20260530 + i,
    backend = "rstan",
    control = list(adapt_delta = adapt_delta, max_treedepth = max_treedepth),
    refresh = refresh,
    file = file.path(output_dir, paste0("brms_", window_label, "_", contrast_id, "_patient")),
    file_refit = file_refit
  )

  all_summaries[[paste0(contrast_id, "_agent")]] <- draw_summary(fit_agent, "agent_looks", contrast_id, label_a, label_b)
  all_summaries[[paste0(contrast_id, "_patient")]] <- draw_summary(fit_patient, "patient_looks", contrast_id, label_a, label_b)
  all_diagnostics[[paste0(contrast_id, "_agent")]] <- diagnostic_summary(fit_agent, "agent_looks", contrast_id, label_a, label_b)
  all_diagnostics[[paste0(contrast_id, "_patient")]] <- diagnostic_summary(fit_patient, "patient_looks", contrast_id, label_a, label_b)

  capture.output(summary(fit_agent), file = file.path(output_dir, paste0("brms_", window_label, "_", contrast_id, "_agent_summary.txt")))
  capture.output(summary(fit_patient), file = file.path(output_dir, paste0("brms_", window_label, "_", contrast_id, "_patient_summary.txt")))
}

write_csv(bind_rows(all_counts), file.path(output_dir, paste0("brms_", window_label, "_number_pairwise_counts.csv")))
write_csv(bind_rows(all_summaries), file.path(output_dir, paste0("brms_", window_label, "_number_pairwise_fixed_effects.csv")))
write_csv(bind_rows(all_diagnostics), file.path(output_dir, paste0("brms_", window_label, "_number_pairwise_diagnostics.csv")))

message("Wrote brms ", window_label, " number pairwise outputs to: ", output_dir)
