suppressPackageStartupMessages({
  library(brms)
  library(dplyr)
  library(posterior)
  library(readr)
  library(tibble)
})

args <- commandArgs(trailingOnly = TRUE)
trial_bins_path <- ifelse(length(args) >= 1, args[[1]], "output/koryak_speech_planning_graphs/speech_planning_trial_bins.csv")
output_dir <- ifelse(length(args) >= 2, args[[2]], "output/koryak_brms_le3_direct_inverse")
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

draw_summary <- function(model, model_name) {
  fixed_draws <- as.data.frame(fixef(model, summary = FALSE))
  fixed_names <- names(fixed_draws)
  rows <- lapply(fixed_names, function(term) {
    values <- fixed_draws[[term]]
    tibble(
      model = model_name,
      term = term,
      estimate = mean(values),
      ci_95_lower = unname(quantile(values, 0.025)),
      ci_95_upper = unname(quantile(values, 0.975)),
      p_beta_gt_0 = mean(values > 0)
    )
  })
  bind_rows(rows)
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

raw <- read_csv(trial_bins_path, show_col_types = FALSE)

le3 <- raw |>
  filter(
    window_key == target_window_key,
    sentence_type %in% c("direct", "inverse")
  ) |>
  mutate(
    participant = factor(participant),
    item = factor(image),
    sentence_type = factor(sentence_type, levels = c("inverse", "direct")),
    direct_vs_inverse = if_else(sentence_type == "direct", 1, -1),
    participant_condition = interaction(participant, sentence_type, drop = TRUE),
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
  le3 |>
    count(sentence_type, participant, name = "n_bins") |>
    group_by(sentence_type) |>
    summarise(
      participants = n_distinct(participant),
      total_bins = sum(n_bins),
      .groups = "drop"
    ),
  file.path(output_dir, paste0(window_label, "_model_data_counts.csv"))
)

write_csv(le3, file.path(output_dir, paste0(window_label, "_direct_inverse_model_data.csv")))

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

common_formula_rhs <- bf(
  y | weights(w) ~ poly(time, degree = 3) * direct_vs_inverse +
    (1 + time || participant_condition) +
    (1 + time || participant) +
    (1 | item)
)

agent_formula <- bf(
  log.agent | weights(1 / wts.agent) ~ poly(time, degree = 3) * direct_vs_inverse +
    (1 + time || participant_condition) +
    (1 + time || participant) +
    (1 | item)
)

patient_formula <- bf(
  log.pat | weights(1 / wts.pat) ~ poly(time, degree = 3) * direct_vs_inverse +
    (1 + time || participant_condition) +
    (1 + time || participant) +
    (1 | item)
)

fit_agent <- brm(
  formula = agent_formula,
  data = le3,
  family = gaussian(),
  chains = chains,
  cores = cores,
  iter = iter,
  warmup = warmup,
  seed = 20260513,
  backend = "rstan",
  control = list(adapt_delta = adapt_delta, max_treedepth = max_treedepth),
  refresh = refresh,
  file = file.path(output_dir, paste0("brms_", window_label, "_direct_inverse_agent")),
  file_refit = file_refit
)

fit_patient <- brm(
  formula = patient_formula,
  data = le3,
  family = gaussian(),
  chains = chains,
  cores = cores,
  iter = iter,
  warmup = warmup,
  seed = 20260514,
  backend = "rstan",
  control = list(adapt_delta = adapt_delta, max_treedepth = max_treedepth),
  refresh = refresh,
  file = file.path(output_dir, paste0("brms_", window_label, "_direct_inverse_patient")),
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

write_csv(summaries, file.path(output_dir, paste0("brms_", window_label, "_direct_inverse_fixed_effects.csv")))
write_csv(diagnostics, file.path(output_dir, paste0("brms_", window_label, "_direct_inverse_diagnostics.csv")))

capture.output(summary(fit_agent), file = file.path(output_dir, paste0("brms_", window_label, "_direct_inverse_agent_summary.txt")))
capture.output(summary(fit_patient), file = file.path(output_dir, paste0("brms_", window_label, "_direct_inverse_patient_summary.txt")))

message("Wrote brms ", window_label, " direct-vs-inverse outputs to: ", output_dir)
