suppressPackageStartupMessages({
  library(brms)
  library(dplyr)
  library(forcats)
  library(ggplot2)
  library(posterior)
  library(readr)
  library(tibble)
  library(tidyr)
})

args <- commandArgs(trailingOnly = TRUE)
data_all_path <- ifelse(length(args) >= 1, args[[1]], "osfstorage-archive/data_all.csv")
output_dir <- ifelse(length(args) >= 2, args[[2]], "output/khanty_brms_le1_passive_agent_patient_person_estimates")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

env_int <- function(name, default) {
  value <- Sys.getenv(name, unset = "")
  if (nzchar(value)) as.integer(value) else default
}

env_num <- function(name, default) {
  value <- Sys.getenv(name, unset = "")
  if (nzchar(value)) as.numeric(value) else default
}

chains <- env_int("KHANTY_BRMS_CHAINS", 4)
cores <- env_int("KHANTY_BRMS_CORES", chains)
iter <- env_int("KHANTY_BRMS_ITER", 2000)
warmup <- env_int("KHANTY_BRMS_WARMUP", 1000)
refresh <- env_int("KHANTY_BRMS_REFRESH", 100)
adapt_delta <- env_num("KHANTY_BRMS_ADAPT_DELTA", 0.99)
max_treedepth <- env_int("KHANTY_BRMS_MAX_TREEDEPTH", 12)
file_refit <- Sys.getenv("KHANTY_BRMS_FILE_REFIT", unset = "on_change")
seed <- env_int("KHANTY_BRMS_SEED", 20260606)
prep_only <- tolower(Sys.getenv("KHANTY_BRMS_PREP_ONLY", unset = "false")) %in% c("1", "true", "yes")

options(mc.cores = cores)
rstan::rstan_options(auto_write = TRUE)

raw <- read_csv(data_all_path, show_col_types = FALSE)

prepared_df <- raw |>
  filter(
    tw == 2,
    rep == "ok",
    type == "pass"
  ) |>
  mutate(
    time_bin50 = as.numeric(time_bin50) - 12,
    sol = as.numeric(sol),
    time_rel = (50 * time_bin50) / (0.5 * (sol - 600)),
    agent = as.numeric(agent),
    patient = as.numeric(patient)
  ) |>
  filter(is.finite(time_rel), time_rel >= 0, time_rel <= 1) |>
  group_by(time_bin50, ppt.no, type, cond, wo, item, sol) |>
  summarise(
    ppt_ids = paste(sort(unique(ppt_id)), collapse = ";"),
    agent_sum = as.integer(round(sum(agent, na.rm = TRUE))),
    patient_sum = as.integer(round(sum(patient, na.rm = TRUE))),
    N = n(),
    .groups = "drop"
  ) |>
  mutate(
    agent_patient_sum = agent_sum + patient_sum,
    person = factor(ppt.no),
    item = factor(item),
    time_rel = (50 * time_bin50) / (0.5 * (sol - 600)),
    time_c = time_rel - 0.5,
    time_c2 = time_c^2,
    time_c3 = time_c^3
  )

if (nrow(prepared_df) == 0) {
  stop("No passive LE1 rows found.")
}

model_df <- prepared_df |>
  filter(agent_patient_sum > 0)

if (nrow(model_df) == 0) {
  stop("No passive LE1 rows with either agent or patient looks found.")
}

person_counts <- prepared_df |>
  group_by(person) |>
  summarise(
    ppt_ids = paste(sort(unique(unlist(strsplit(paste(ppt_ids, collapse = ";"), ";")))), collapse = ";"),
    passive_trials = n_distinct(paste(item, cond, wo, sol, sep = "||")),
    total_bins = n(),
    modeled_bins = sum(agent_patient_sum > 0),
    total_samples = sum(N),
    agent_looks = sum(agent_sum),
    patient_looks = sum(patient_sum),
    agent_or_patient_looks = sum(agent_patient_sum),
    raw_agent_share = agent_looks / agent_or_patient_looks,
    .groups = "drop"
  ) |>
  arrange(as.numeric(person))

write_csv(
  tibble(
    participants = n_distinct(prepared_df$person),
    passive_trials = n_distinct(paste(prepared_df$person, prepared_df$item, prepared_df$cond, prepared_df$wo, prepared_df$sol, sep = "||")),
    total_bins = nrow(prepared_df),
    modeled_bins = nrow(model_df),
    total_samples = sum(prepared_df$N),
    agent_looks = sum(prepared_df$agent_sum),
    patient_looks = sum(prepared_df$patient_sum),
    agent_or_patient_looks = sum(prepared_df$agent_patient_sum),
    raw_agent_share = sum(prepared_df$agent_sum) / sum(prepared_df$agent_patient_sum)
  ),
  file.path(output_dir, "khanty_le1_passive_agent_patient_model_counts.csv")
)

write_csv(person_counts, file.path(output_dir, "khanty_le1_passive_agent_patient_person_counts.csv"))
write_csv(model_df, file.path(output_dir, "khanty_le1_passive_agent_patient_model_data.csv"))
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
    seed = seed,
    source_data = data_all_path,
    window = "LE1",
    sentence_type = "passive",
    outcome = "agent looks out of agent-or-patient looks",
    interpretation = "agent_share > 0.5 means agent preference over patient"
  ),
  file.path(output_dir, "run_config.csv")
)

if (prep_only) {
  message("Prepared passive LE1 agent/patient model data only: ", output_dir)
  quit(save = "no", status = 0)
}

agent_patient_formula <- bf(
  agent_sum | trials(agent_patient_sum) ~ time_c + time_c2 + time_c3 +
    (1 + time_c || person) +
    (1 | item)
)

fit_agent_patient <- brm(
  formula = agent_patient_formula,
  data = model_df,
  family = binomial(),
  chains = chains,
  cores = cores,
  iter = iter,
  warmup = warmup,
  seed = seed,
  backend = "rstan",
  control = list(adapt_delta = adapt_delta, max_treedepth = max_treedepth),
  refresh = refresh,
  file = file.path(output_dir, "brms_khanty_le1_passive_agent_patient_person"),
  file_refit = file_refit
)

fixed_draws <- as.data.frame(fixef(fit_agent_patient, summary = FALSE))
fixed_summary <- bind_rows(lapply(names(fixed_draws), function(term) {
  values <- fixed_draws[[term]]
  tibble(
    term = term,
    estimate = mean(values),
    median = median(values),
    ci_95_lower = unname(quantile(values, 0.025)),
    ci_95_upper = unname(quantile(values, 0.975)),
    p_gt_0 = mean(values > 0)
  )
}))
write_csv(fixed_summary, file.path(output_dir, "khanty_le1_passive_agent_patient_fixed_effects.csv"))

person_ranef <- ranef(fit_agent_patient, summary = FALSE)$person
person_terms <- dimnames(person_ranef)[[3]]
person_labels <- dimnames(person_ranef)[[2]]

person_draws <- bind_rows(lapply(seq_along(person_terms), function(term_index) {
  mat <- person_ranef[, , term_index, drop = FALSE][, , 1]
  as_tibble(mat, .name_repair = "minimal") |>
    mutate(.draw = row_number()) |>
    pivot_longer(
      cols = -.draw,
      names_to = "person",
      values_to = "r_person"
    ) |>
    mutate(term = person_terms[[term_index]])
}))

person_random_summary <- person_draws |>
  group_by(person, term) |>
  summarise(
    r_person_median = median(r_person),
    r_person_lower = quantile(r_person, 0.025),
    r_person_upper = quantile(r_person, 0.975),
    p_r_person_gt_0 = mean(r_person > 0),
    .groups = "drop"
  ) |>
  left_join(person_counts, by = "person") |>
  arrange(as.numeric(person), term)

write_csv(
  person_random_summary,
  file.path(output_dir, "khanty_le1_passive_agent_patient_person_random_effects.csv")
)

time_grid <- tibble(
  time_rel = seq(0, 1, length.out = 101)
) |>
  mutate(
    time_c = time_rel - 0.5,
    time_c2 = time_c^2,
    time_c3 = time_c^3
  )

n_draws <- nrow(fixed_draws)
draw_ids <- seq_len(n_draws)

get_person_term <- function(term) {
  if (term %in% person_terms) {
    person_ranef[, , match(term, person_terms), drop = FALSE][, , 1]
  } else {
    matrix(0, nrow = n_draws, ncol = length(person_labels), dimnames = list(NULL, person_labels))
  }
}

r_intercept <- get_person_term("Intercept")
r_time_c <- get_person_term("time_c")

person_abs_draws <- bind_rows(lapply(seq_along(person_labels), function(person_index) {
  person_id <- person_labels[[person_index]]
  eta_grid <- sapply(seq_len(nrow(time_grid)), function(grid_index) {
    fixed_draws$Intercept +
      r_intercept[, person_index] +
      (fixed_draws$time_c + r_time_c[, person_index]) * time_grid$time_c[[grid_index]] +
      fixed_draws$time_c2 * time_grid$time_c2[[grid_index]] +
      fixed_draws$time_c3 * time_grid$time_c3[[grid_index]]
  })
  midpoint_eta <- fixed_draws$Intercept + r_intercept[, person_index]
  tibble(
    .draw = draw_ids,
    person = person_id,
    average_log_agent_over_patient = rowMeans(eta_grid),
    average_agent_share = rowMeans(plogis(eta_grid)),
    average_agent_minus_patient_share = 2 * average_agent_share - 1,
    midpoint_log_agent_over_patient = midpoint_eta,
    midpoint_agent_share = plogis(midpoint_eta)
  )
}))

person_abs_summary <- person_abs_draws |>
  group_by(person) |>
  summarise(
    average_agent_share_median = median(average_agent_share),
    average_agent_share_lower = quantile(average_agent_share, 0.025),
    average_agent_share_upper = quantile(average_agent_share, 0.975),
    average_agent_minus_patient_share_median = median(average_agent_minus_patient_share),
    average_agent_minus_patient_share_lower = quantile(average_agent_minus_patient_share, 0.025),
    average_agent_minus_patient_share_upper = quantile(average_agent_minus_patient_share, 0.975),
    average_log_agent_over_patient_median = median(average_log_agent_over_patient),
    average_log_agent_over_patient_lower = quantile(average_log_agent_over_patient, 0.025),
    average_log_agent_over_patient_upper = quantile(average_log_agent_over_patient, 0.975),
    p_average_agent_gt_patient = mean(average_agent_share > 0.5),
    midpoint_agent_share_median = median(midpoint_agent_share),
    midpoint_agent_share_lower = quantile(midpoint_agent_share, 0.025),
    midpoint_agent_share_upper = quantile(midpoint_agent_share, 0.975),
    p_midpoint_agent_gt_patient = mean(midpoint_agent_share > 0.5),
    .groups = "drop"
  ) |>
  left_join(person_counts, by = "person") |>
  arrange(as.numeric(person))

write_csv(
  person_abs_summary,
  file.path(output_dir, "khanty_le1_passive_agent_patient_person_absolute_estimates.csv")
)

fixed_eta_grid <- sapply(seq_len(nrow(time_grid)), function(grid_index) {
  fixed_draws$Intercept +
    fixed_draws$time_c * time_grid$time_c[[grid_index]] +
    fixed_draws$time_c2 * time_grid$time_c2[[grid_index]] +
    fixed_draws$time_c3 * time_grid$time_c3[[grid_index]]
})

group_draws <- tibble(
  .draw = draw_ids,
  average_log_agent_over_patient = rowMeans(fixed_eta_grid),
  average_agent_share = rowMeans(plogis(fixed_eta_grid)),
  average_agent_minus_patient_share = 2 * average_agent_share - 1,
  midpoint_log_agent_over_patient = fixed_draws$Intercept,
  midpoint_agent_share = plogis(fixed_draws$Intercept)
)

group_summary <- group_draws |>
  summarise(
    average_agent_share_median = median(average_agent_share),
    average_agent_share_lower = quantile(average_agent_share, 0.025),
    average_agent_share_upper = quantile(average_agent_share, 0.975),
    average_agent_minus_patient_share_median = median(average_agent_minus_patient_share),
    average_agent_minus_patient_share_lower = quantile(average_agent_minus_patient_share, 0.025),
    average_agent_minus_patient_share_upper = quantile(average_agent_minus_patient_share, 0.975),
    average_log_agent_over_patient_median = median(average_log_agent_over_patient),
    average_log_agent_over_patient_lower = quantile(average_log_agent_over_patient, 0.025),
    average_log_agent_over_patient_upper = quantile(average_log_agent_over_patient, 0.975),
    p_average_agent_gt_patient = mean(average_agent_share > 0.5),
    midpoint_agent_share_median = median(midpoint_agent_share),
    midpoint_agent_share_lower = quantile(midpoint_agent_share, 0.025),
    midpoint_agent_share_upper = quantile(midpoint_agent_share, 0.975),
    p_midpoint_agent_gt_patient = mean(midpoint_agent_share > 0.5)
  )

write_csv(group_summary, file.path(output_dir, "khanty_le1_passive_agent_patient_group_estimate.csv"))

share_plot_data <- person_abs_summary |>
  mutate(
    person_label = paste0(person, " - ", ppt_ids),
    person_ordered = fct_reorder(person_label, average_agent_share_median)
  )

share_plot <- ggplot(
  share_plot_data,
  aes(
    x = average_agent_share_median,
    xmin = average_agent_share_lower,
    xmax = average_agent_share_upper,
    y = person_ordered
  )
) +
  geom_vline(xintercept = 0.5, linetype = "dashed", color = "grey35") +
  geom_pointrange(color = "#0072B2") +
  scale_x_continuous(limits = c(0, 1)) +
  labs(
    x = "Average LE1 P(agent | agent or patient look)",
    y = "Person",
    title = "Khanty passive LE1: by-person agent-over-patient estimates"
  ) +
  theme_minimal(base_size = 12)

ggsave(
  file.path(output_dir, "khanty_le1_passive_agent_patient_average_share_forest.png"),
  share_plot,
  width = 11,
  height = 8,
  dpi = 300,
  bg = "white"
)

logit_plot_data <- person_abs_summary |>
  mutate(
    person_label = paste0(person, " - ", ppt_ids),
    person_ordered = fct_reorder(person_label, average_log_agent_over_patient_median)
  )

logit_plot <- ggplot(
  logit_plot_data,
  aes(
    x = average_log_agent_over_patient_median,
    xmin = average_log_agent_over_patient_lower,
    xmax = average_log_agent_over_patient_upper,
    y = person_ordered
  )
) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "grey35") +
  geom_pointrange(color = "#0072B2") +
  labs(
    x = "Average LE1 log-odds(agent / patient)",
    y = "Person",
    title = "Khanty passive LE1: by-person agent-over-patient log-odds"
  ) +
  theme_minimal(base_size = 12)

ggsave(
  file.path(output_dir, "khanty_le1_passive_agent_patient_average_log_odds_forest.png"),
  logit_plot,
  width = 11,
  height = 8,
  dpi = 300,
  bg = "white"
)

draw_diagnostics <- summarise_draws(as_draws_df(fit_agent_patient))
write_csv(
  draw_diagnostics,
  file.path(output_dir, "khanty_le1_passive_agent_patient_all_parameter_diagnostics.csv")
)

sampler <- rstan::get_sampler_params(fit_agent_patient$fit, inc_warmup = FALSE)
sampler_diag <- tibble(
  divergent_transitions = sum(vapply(sampler, function(x) sum(x[, "divergent__"]), numeric(1))),
  max_treedepth_hits = sum(vapply(sampler, function(x) sum(x[, "treedepth__"] >= max_treedepth), numeric(1)))
)
write_csv(sampler_diag, file.path(output_dir, "khanty_le1_passive_agent_patient_sampler_diagnostics.csv"))

capture.output(
  summary(fit_agent_patient),
  file = file.path(output_dir, "brms_khanty_le1_passive_agent_patient_person_summary.txt")
)

sink(file.path(output_dir, "reader_friendly_summary.md"))
cat("# Khanty Passive LE1 Agent-Over-Patient Per-Person Estimates\n\n")
cat("Model: binomial agent looks out of agent-or-patient looks in passive sentences during LE1 (`tw == 2`).\n\n")
cat("Interpretation: `average_agent_share > 0.5` means a preference for the agent over the patient, conditional on looking at either argument.\n\n")
cat("Passive trials: ", n_distinct(paste(prepared_df$person, prepared_df$item, prepared_df$cond, prepared_df$wo, prepared_df$sol, sep = "||")), ".\n\n", sep = "")
cat("Main output files:\n\n")
cat("- `khanty_le1_passive_agent_patient_person_absolute_estimates.csv`: per-person average LE1 agent-over-patient estimates.\n")
cat("- `khanty_le1_passive_agent_patient_group_estimate.csv`: group-level average LE1 estimate.\n")
cat("- `khanty_le1_passive_agent_patient_average_share_forest.png`: forest plot on probability scale.\n")
cat("- `khanty_le1_passive_agent_patient_average_log_odds_forest.png`: forest plot on log-odds scale.\n")
sink()

message("Wrote Khanty passive LE1 agent-over-patient per-person estimates to: ", output_dir)
