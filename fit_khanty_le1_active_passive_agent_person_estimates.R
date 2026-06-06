suppressPackageStartupMessages({
  library(brms)
  library(dplyr)
  library(forcats)
  library(ggplot2)
  library(posterior)
  library(readr)
  library(tibble)
  library(tidyr)
  library(tidybayes)
})

args <- commandArgs(trailingOnly = TRUE)
data_all_path <- ifelse(length(args) >= 1, args[[1]], "osfstorage-archive/data_all.csv")
output_dir <- ifelse(length(args) >= 2, args[[2]], "output/khanty_brms_le1_active_passive_agent_person_estimates")
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

options(mc.cores = cores)
rstan::rstan_options(auto_write = TRUE)

raw <- read_csv(data_all_path, show_col_types = FALSE)

model_df <- raw |>
  filter(
    tw == 2,
    rep == "ok",
    type %in% c("act", "pass")
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
    agent.sum = sum(agent, na.rm = TRUE),
    pat.sum = sum(patient, na.rm = TRUE),
    N = n(),
    .groups = "drop"
  ) |>
  mutate(
    person = factor(ppt.no),
    item = factor(item),
    sentence_type = factor(type, levels = c("pass", "act")),
    active_voice = if_else(type == "act", 1, -1),
    time_rel = (50 * time_bin50) / (0.5 * (sol - 600)),
    time = as.numeric(scale(time_rel, center = FALSE, scale = TRUE)),
    agent.sum = pmin(pmax(agent.sum, 0), N),
    pat.sum = pmin(pmax(pat.sum, 0), N),
    log.agent = log((agent.sum + 0.5) / (N - agent.sum + 0.5)),
    wts.agent = 1 / (agent.sum + 0.5) + 1 / (N - agent.sum + 0.5)
  )

if (nrow(model_df) == 0) {
  stop("No LE1 active/passive agent-look model rows found.")
}

person_trial_rows <- model_df |>
  distinct(person, ppt_ids, type, item, cond, wo, sol)

person_counts <- person_trial_rows |>
  group_by(person) |>
  summarise(
    ppt_ids = paste(sort(unique(unlist(strsplit(paste(ppt_ids, collapse = ";"), ";")))), collapse = ";"),
    n_trials_act = sum(type == "act"),
    n_trials_pass = sum(type == "pass"),
    n_trials_total = n(),
    .groups = "drop"
  )

write_csv(
  model_df |>
    group_by(type) |>
    summarise(
      participants = n_distinct(person),
      trials = n_distinct(paste(person, item, cond, wo, sol, sep = "||")),
      total_bins = n(),
      total_samples = sum(N),
      .groups = "drop"
    ),
  file.path(output_dir, "khanty_le1_agent_active_passive_model_counts.csv")
)

write_csv(model_df, file.path(output_dir, "khanty_le1_agent_active_passive_model_data.csv"))
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
    outcome = "agent looks",
    contrast_coding = "active_voice: active = +1, passive = -1"
  ),
  file.path(output_dir, "run_config.csv")
)

agent_formula <- bf(
  log.agent | weights(1 / wts.agent) ~ poly(time, degree = 3) * active_voice +
    (1 + active_voice + time || person) +
    (1 | item)
)

fit_agent <- brm(
  formula = agent_formula,
  data = model_df,
  family = gaussian(),
  chains = chains,
  cores = cores,
  iter = iter,
  warmup = warmup,
  seed = seed,
  backend = "rstan",
  control = list(adapt_delta = adapt_delta, max_treedepth = max_treedepth),
  refresh = refresh,
  file = file.path(output_dir, "brms_khanty_le1_active_passive_agent_person"),
  file_refit = file_refit
)

fixed_draws <- as.data.frame(fixef(fit_agent, summary = FALSE))
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
write_csv(fixed_summary, file.path(output_dir, "khanty_le1_agent_active_passive_fixed_effects.csv"))

person_ranef <- ranef(fit_agent, summary = FALSE)$person
person_terms <- dimnames(person_ranef)[[3]]

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
  median_qi(r_person, .width = 0.95) |>
  ungroup() |>
  left_join(person_counts, by = "person") |>
  arrange(as.numeric(person), term)

write_csv(
  person_random_summary,
  file.path(output_dir, "khanty_le1_agent_active_passive_person_random_effects.csv")
)

fixed_for_join <- tibble(
  .draw = seq_len(nrow(fixed_draws)),
  b_Intercept = fixed_draws$Intercept,
  b_active_voice = fixed_draws$active_voice
)

person_wide <- person_draws |>
  filter(term %in% c("Intercept", "active_voice")) |>
  select(.draw, person, term, r_person) |>
  pivot_wider(names_from = term, values_from = r_person)

person_abs_draws <- person_wide |>
  left_join(fixed_for_join, by = ".draw") |>
  mutate(
    absolute_intercept = b_Intercept + Intercept,
    absolute_active_voice_half_difference = b_active_voice + active_voice,
    active_minus_passive_logit = 2 * absolute_active_voice_half_difference
  )

person_abs_summary <- person_abs_draws |>
  group_by(person) |>
  summarise(
    absolute_intercept_median = median(absolute_intercept),
    absolute_intercept_lower = quantile(absolute_intercept, 0.025),
    absolute_intercept_upper = quantile(absolute_intercept, 0.975),
    absolute_active_voice_half_difference_median = median(absolute_active_voice_half_difference),
    half_difference_lower = quantile(absolute_active_voice_half_difference, 0.025),
    half_difference_upper = quantile(absolute_active_voice_half_difference, 0.975),
    active_minus_passive_logit_median = median(active_minus_passive_logit),
    active_minus_passive_lower = quantile(active_minus_passive_logit, 0.025),
    active_minus_passive_upper = quantile(active_minus_passive_logit, 0.975),
    p_active_minus_passive_gt_0 = mean(active_minus_passive_logit > 0),
    .groups = "drop"
  ) |>
  left_join(person_counts, by = "person") |>
  arrange(as.numeric(person))

write_csv(
  person_abs_summary,
  file.path(output_dir, "khanty_le1_agent_active_passive_person_absolute_estimates.csv")
)

random_slope_plot_data <- person_random_summary |>
  filter(term == "active_voice") |>
  mutate(person_ordered = fct_reorder(factor(person), r_person))

random_slope_plot <- ggplot(
  random_slope_plot_data,
  aes(x = r_person, xmin = .lower, xmax = .upper, y = person_ordered)
) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "grey35") +
  geom_pointrange(color = "#CC3311") +
  labs(
    x = "Random active-voice slope relative to grand mean",
    y = "Person",
    title = "Khanty LE1 agent looks: by-person active/passive slope deviations"
  ) +
  theme_minimal(base_size = 12)

ggsave(
  file.path(output_dir, "khanty_le1_agent_person_random_active_voice_slope_forest.png"),
  random_slope_plot,
  width = 9,
  height = 8,
  dpi = 300,
  bg = "white"
)

absolute_plot_data <- person_abs_summary |>
  mutate(person_ordered = fct_reorder(factor(person), active_minus_passive_logit_median))

absolute_plot <- ggplot(
  absolute_plot_data,
  aes(
    x = active_minus_passive_logit_median,
    xmin = active_minus_passive_lower,
    xmax = active_minus_passive_upper,
    y = person_ordered
  )
) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "grey35") +
  geom_pointrange(color = "#CC3311") +
  labs(
    x = "Person-specific active - passive contrast for agent looks",
    y = "Person",
    title = "Khanty LE1 agent looks: by-person active-passive estimates"
  ) +
  theme_minimal(base_size = 12)

ggsave(
  file.path(output_dir, "khanty_le1_agent_person_absolute_active_minus_passive_forest.png"),
  absolute_plot,
  width = 9,
  height = 8,
  dpi = 300,
  bg = "white"
)

draw_diagnostics <- summarise_draws(as_draws_df(fit_agent))
write_csv(
  draw_diagnostics,
  file.path(output_dir, "khanty_le1_agent_active_passive_all_parameter_diagnostics.csv")
)

sampler <- rstan::get_sampler_params(fit_agent$fit, inc_warmup = FALSE)
sampler_diag <- tibble(
  divergent_transitions = sum(vapply(sampler, function(x) sum(x[, "divergent__"]), numeric(1))),
  max_treedepth_hits = sum(vapply(sampler, function(x) sum(x[, "treedepth__"] >= max_treedepth), numeric(1)))
)
write_csv(sampler_diag, file.path(output_dir, "khanty_le1_agent_active_passive_sampler_diagnostics.csv"))

capture.output(
  summary(fit_agent),
  file = file.path(output_dir, "brms_khanty_le1_active_passive_agent_person_summary.txt")
)

sink(file.path(output_dir, "reader_friendly_summary.md"))
cat("# Khanty LE1 Agent-Look Per-Person Estimates\n\n")
cat("Model: empirical-logit agent-look proportions in Linguistic Encoding I (`tw == 2`).\n\n")
cat("Contrast coding: active = +1, passive = -1, so `active_voice` is half of the active-passive difference.\n\n")
cat("Trials: active = ", sum(person_counts$n_trials_act), "; passive = ", sum(person_counts$n_trials_pass), ".\n\n", sep = "")
cat("Main output files:\n\n")
cat("- `khanty_le1_agent_active_passive_person_random_effects.csv`: person-level random effects relative to the grand mean.\n")
cat("- `khanty_le1_agent_active_passive_person_absolute_estimates.csv`: fixed + person random effects; includes full active-passive contrast.\n")
cat("- `khanty_le1_agent_person_random_active_voice_slope_forest.png`: random slope forest plot.\n")
cat("- `khanty_le1_agent_person_absolute_active_minus_passive_forest.png`: absolute active-passive forest plot.\n")
sink()

message("Wrote Khanty LE1 active/passive agent-look per-person estimates to: ", output_dir)
