suppressPackageStartupMessages({
  library(dplyr)
  library(lmerTest)
  library(readr)
  library(tibble)
})

input_path <- "Koryak stimuli - final.csv"
output_dir <- "output/koryak_behavioral_latency"
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

cyr_k <- "\u041a"
included_participants <- paste0(
  cyr_k,
  sprintf("%02d", c(1, 3, 4, 5, 6, 7, 10, 13, 14, 15, 16, 17, 20, 22, 24, 25))
)

raw <- read_csv(input_path, show_col_types = FALSE)

model_df <- raw |>
  transmute(
    participant = as.character(`participant's id`),
    item = as.character(image),
    rt = suppressWarnings(parse_number(as.character(`reaction time`))),
    fluency = tolower(trimws(as.character(fluency))),
    sentence_type = tolower(trimws(as.character(`sentence type`))),
    word_order = trimws(as.character(`word order`))
  ) |>
  filter(
    participant %in% included_participants,
    !is.na(rt),
    rt < 6000,
    fluency == "yes",
    word_order == "AVP",
    sentence_type %in% c("direct", "inverse"),
    !is.na(item),
    item != ""
  ) |>
  mutate(
    direct = if_else(sentence_type == "direct", 1, 0),
    participant = factor(participant),
    item = factor(item)
  )

if (nrow(model_df) != 879) {
  stop("Expected the clean 879-trial dataset, got ", nrow(model_df), " rows.")
}

write_csv(model_df, file.path(output_dir, "koryak_latency_model_data.csv"))

descriptives <- model_df |>
  group_by(sentence_type) |>
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

write_csv(descriptives, file.path(output_dir, "koryak_latency_descriptives.csv"))

model <- lmer(
  log(rt) ~ direct + (1 + direct | item) + (1 + direct | participant),
  data = model_df
)

fixed <- coef(summary(model)) |>
  as.data.frame() |>
  rownames_to_column("term") |>
  as_tibble()

names(fixed) <- c("term", "estimate_log_ms", "std_error", "df", "t_value", "p_value")

wald_ci <- confint(model, parm = "beta_", method = "Wald") |>
  as.data.frame() |>
  rownames_to_column("term") |>
  as_tibble()

names(wald_ci) <- c("term", "ci_95_lower_log_ms", "ci_95_upper_log_ms")

fixed <- fixed |>
  left_join(wald_ci, by = "term") |>
  mutate(
    ratio_direct_to_inverse = exp(estimate_log_ms),
    percent_change_direct_vs_inverse = 100 * (ratio_direct_to_inverse - 1),
    ci_95_lower_ratio = exp(ci_95_lower_log_ms),
    ci_95_upper_ratio = exp(ci_95_upper_log_ms)
  )

write_csv(fixed, file.path(output_dir, "koryak_latency_fixed_effects.csv"))

saveRDS(model, file.path(output_dir, "koryak_latency_lmer_model.rds"))

sink(file.path(output_dir, "koryak_latency_model_summary.txt"))
cat("Koryak speech onset latency model\n")
cat("=================================\n\n")
cat("Khanty source model: lmer(log(sol) ~ type + (1 + type | item) + (1 + type | ppt.no))\n")
cat("Koryak model: lmer(log(rt) ~ direct + (1 + direct | item) + (1 + direct | participant))\n")
cat("Coding: direct = 1, inverse = 0. Positive direct coefficient means longer direct latencies.\n\n")
cat("N trials:", nrow(model_df), "\n")
cat("Participants:", n_distinct(model_df$participant), "\n")
cat("Items:", n_distinct(model_df$item), "\n\n")
cat("Counts by sentence type:\n")
print(count(model_df, sentence_type))
cat("\nDescriptives:\n")
print(descriptives)
cat("\nSingular fit:", isSingular(model), "\n")
cat("\nConvergence messages:\n")
print(model@optinfo$conv$lme4$messages)
cat("\nFixed effects table:\n")
print(fixed)
cat("\nRandom-effects variance/correlation table:\n")
print(as.data.frame(VarCorr(model)))
sink()

cat("Wrote Koryak behavioral latency outputs to:", output_dir, "\n")
