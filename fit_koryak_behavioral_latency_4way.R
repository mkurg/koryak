suppressPackageStartupMessages({
  library(dplyr)
  library(lmerTest)
  library(readr)
  library(tibble)
})

input_path <- "Koryak stimuli - final.csv"
output_dir <- "output/koryak_behavioral_latency_4way"
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

cyr_k <- "\u041a"
included_participants <- paste0(
  cyr_k,
  sprintf("%02d", c(1, 3, 4, 5, 6, 7, 10, 13, 14, 15, 16, 17, 20, 22, 24, 25))
)

condition_levels <- c(
  "direct_1_1",
  "direct_1_2",
  "inverse_2_2",
  "inverse_2_1"
)

condition_label <- function(sentence_type, agent_num, patient_num) {
  case_when(
    sentence_type == "direct" & agent_num == 1 & patient_num == 1 ~ "direct_1_1",
    sentence_type == "direct" & agent_num == 1 & patient_num == 2 ~ "direct_1_2",
    sentence_type == "inverse" & agent_num == 2 & patient_num == 2 ~ "inverse_2_2",
    sentence_type == "inverse" & agent_num == 2 & patient_num == 1 ~ "inverse_2_1",
    TRUE ~ NA_character_
  )
}

raw <- read_csv(input_path, show_col_types = FALSE)

model_df <- raw |>
  transmute(
    participant = as.character(`participant's id`),
    item = as.character(image),
    rt = suppressWarnings(parse_number(as.character(`reaction time`))),
    fluency = tolower(trimws(as.character(fluency))),
    sentence_type = tolower(trimws(as.character(`sentence type`))),
    word_order = trimws(as.character(`word order`)),
    agent_num = suppressWarnings(as.integer(parse_number(as.character(agens_num)))),
    patient_num = suppressWarnings(as.integer(parse_number(as.character(patiens_num))))
  ) |>
  mutate(condition4 = condition_label(sentence_type, agent_num, patient_num)) |>
  filter(
    participant %in% included_participants,
    !is.na(rt),
    rt < 6000,
    fluency == "yes",
    word_order == "AVP",
    condition4 %in% condition_levels,
    !is.na(item),
    item != ""
  ) |>
  mutate(
    condition4 = factor(condition4, levels = condition_levels),
    participant = factor(participant),
    item = factor(item)
  )

if (nrow(model_df) != 783) {
  stop("Expected the clean 783-trial four-way dataset, got ", nrow(model_df), " rows.")
}

write_csv(model_df, file.path(output_dir, "koryak_latency_4way_model_data.csv"))

descriptives <- model_df |>
  group_by(condition4) |>
  summarise(
    n = n(),
    mean_rt_ms = mean(rt),
    sd_rt_ms = sd(rt),
    median_rt_ms = median(rt),
    min_rt_ms = min(rt),
    max_rt_ms = max(rt),
    khanty_style_2se_ms = 2 * sd(rt) / sqrt(n()),
    .groups = "drop"
  )

write_csv(descriptives, file.path(output_dir, "koryak_latency_4way_descriptives.csv"))

lmer_ctrl <- lmerControl(
  optimizer = "bobyqa",
  optCtrl = list(maxfun = 100000)
)

full_model <- lmer(
  log(rt) ~ condition4 + (1 + condition4 | item) + (1 + condition4 | participant),
  data = model_df,
  control = lmer_ctrl
)

full_fixed <- coef(summary(full_model)) |>
  as.data.frame() |>
  rownames_to_column("term") |>
  as_tibble()

names(full_fixed) <- c("term", "estimate_log_ms", "std_error", "df", "t_value", "p_value")

full_ci <- confint(full_model, parm = "beta_", method = "Wald") |>
  as.data.frame() |>
  rownames_to_column("term") |>
  as_tibble()

names(full_ci) <- c("term", "ci_95_lower_log_ms", "ci_95_upper_log_ms")

full_fixed <- full_fixed |>
  left_join(full_ci, by = "term") |>
  mutate(
    ratio = exp(estimate_log_ms),
    percent_change = 100 * (ratio - 1),
    ci_95_lower_ratio = exp(ci_95_lower_log_ms),
    ci_95_upper_ratio = exp(ci_95_upper_log_ms)
  )

write_csv(full_fixed, file.path(output_dir, "koryak_latency_4way_fixed_effects.csv"))

overall_anova <- anova(full_model, ddf = "Satterthwaite") |>
  as.data.frame() |>
  rownames_to_column("term") |>
  as_tibble()

write_csv(overall_anova, file.path(output_dir, "koryak_latency_4way_overall_anova.csv"))

fit_pair <- function(level_a, level_b) {
  pair_df <- model_df |>
    filter(condition4 %in% c(level_a, level_b)) |>
    mutate(pair_contrast = if_else(condition4 == level_a, 1, 0))

  pair_model <- lmer(
    log(rt) ~ pair_contrast + (1 + pair_contrast | item) + (1 + pair_contrast | participant),
    data = pair_df,
    control = lmer_ctrl
  )

  fixed <- coef(summary(pair_model)) |>
    as.data.frame() |>
    rownames_to_column("term") |>
    as_tibble()
  names(fixed) <- c("term", "estimate_log_ms", "std_error", "df", "t_value", "p_value")

  ci <- confint(pair_model, parm = "beta_", method = "Wald") |>
    as.data.frame() |>
    rownames_to_column("term") |>
    as_tibble()
  names(ci) <- c("term", "ci_95_lower_log_ms", "ci_95_upper_log_ms")

  fixed |>
    filter(term == "pair_contrast") |>
    left_join(ci, by = "term") |>
    transmute(
      comparison = paste(level_a, "vs", level_b),
      estimate_log_ms,
      std_error,
      df,
      t_value,
      p_value,
      ci_95_lower_log_ms,
      ci_95_upper_log_ms,
      ratio_a_to_b = exp(estimate_log_ms),
      percent_change_a_vs_b = 100 * (ratio_a_to_b - 1),
      ci_95_lower_ratio = exp(ci_95_lower_log_ms),
      ci_95_upper_ratio = exp(ci_95_upper_log_ms),
      n_a = sum(pair_df$condition4 == level_a),
      n_b = sum(pair_df$condition4 == level_b),
      singular_fit = isSingular(pair_model),
      convergence_messages = paste(pair_model@optinfo$conv$lme4$messages, collapse = " | ")
    )
}

pair_grid <- combn(condition_levels, 2, simplify = FALSE)
pairwise <- bind_rows(lapply(pair_grid, function(x) fit_pair(x[[1]], x[[2]])))

write_csv(pairwise, file.path(output_dir, "koryak_latency_4way_pairwise.csv"))

saveRDS(full_model, file.path(output_dir, "koryak_latency_4way_lmer_model.rds"))

sink(file.path(output_dir, "koryak_latency_4way_model_summary.txt"))
cat("Koryak speech onset latency four-way model\n")
cat("==========================================\n\n")
cat("Model: lmer(log(rt) ~ condition4 + (1 + condition4 | item) + (1 + condition4 | participant))\n")
cat("Reference level in fixed-effect table: direct_1_1\n")
cat("Pairwise table estimates are level A minus level B on the log latency scale.\n\n")
cat("N trials:", nrow(model_df), "\n")
cat("Participants:", n_distinct(model_df$participant), "\n")
cat("Items:", n_distinct(model_df$item), "\n\n")
cat("Counts:\n")
print(count(model_df, condition4))
cat("\nDescriptives:\n")
print(descriptives)
cat("\nOverall condition test:\n")
print(overall_anova)
cat("\nFull model singular fit:", isSingular(full_model), "\n")
cat("\nFull model convergence messages:\n")
print(full_model@optinfo$conv$lme4$messages)
cat("\nFull model fixed effects:\n")
print(full_fixed)
cat("\nPairwise comparisons:\n")
print(pairwise)
cat("\nRandom-effects variance/correlation table:\n")
print(as.data.frame(VarCorr(full_model)))
sink()

cat("Wrote Koryak behavioral four-way latency outputs to:", output_dir, "\n")
