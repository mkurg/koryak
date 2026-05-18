install.packages("plyr")
install.packages("tidyverse")
install.packages("lme4")
install.packages("sjPlot")
install.packages("dplyr")
install.packages("tidybayes")
install.packages("brms")
install.packages("rstan", repos = "https://cloud.r-project.org/", dependencies = TRUE)
library(plyr)
library(tidyverse)
library(lme4)
library(sjPlot)
library(dplyr)
library(ggplot2)
library(tidybayes)
library("brms")

#data before speech onset
data_all <- read.csv("data_all.csv")

#EARLY EVENT APPREHENSION------------------------

#defining time window
window1 <- data_all[(data_all$time_bin50 >= 2 & data_all$time_bin50 <=12),]
window1$time_bin50 <- window1$time_bin50 - 2
window1$time_rel <- window1$time_bin50/10


#first fixation
window1 <- window1 %>%
  group_by(ppt.no, item) %>% 
  arrange(ms) %>%               
  mutate(first_fix = who[first(which.min(ms))]) %>% 
  ungroup()  

#preparation for regressions
data.new.w1 <- ddply(window1, .(time_bin50, ppt.no, type, cond, item, wo, first_fix),  
                     summarise, 
                     agent.sum = sum(agent), 
                     pat.sum = sum(patient), 
                     N = length(ms))

data.new.w1$agg.id <- data.new.w1$ppt.no*1000
data.new.w1$agg.id <- ifelse(data.new.w1$type == "act",
                             data.new.w1$agg.id + 10,
                             data.new.w1$agg.id + 20)

data.new.w1$log.pat <- log((data.new.w1$pat.sum + .5) / 
                             (data.new.w1$N - data.new.w1$pat.sum + .5))
data.new.w1$wts.pat <- 1/(data.new.w1$pat.sum + .5) + 
  1/(data.new.w1$N - data.new.w1$pat.sum + .5)

data.new.w1$log.agent <- log((data.new.w1$agent.sum + .5) / 
                               (data.new.w1$N - data.new.w1$agent.sum + .5))
data.new.w1$wts.agent <- 1/(data.new.w1$agent.sum + .5) +
  1/(data.new.w1$N - data.new.w1$agent.sum + .5)

data.new.w1$passive_voice <- ifelse(data.new.w1$type == "pass", 1, -1)   
data.new.w1$active_voice <- ifelse(data.new.w1$type == "pass", -1, 1)    
data.new.w1$ff_patient <- ifelse(data.new.w1$first_fix == "p", 1, -1)   
data.new.w1$ff_agent <- ifelse(data.new.w1$first_fix == "p", -1, 1)      
data.new.w1$time <- (50*data.new.w1$time_bin50)/500
data.new.w1$time <- scale(data.new.w1$time, center = FALSE, scale = TRUE)


##MODELS FOR ALL ACTIVES AND ALL PASSIVES


window1.brm.ag <- brm(log.agent | weights(1/wts.agent) ~ (poly(time, degree = 3) * active_voice ) * ff_agent +
                        (1 + time ||agg.id:ppt.no) + 
                        (1 + time || ppt.no) +
                        (1 | item), 
                      data = data.new.w1, control=list(adapt_delta=0.99, max_treedepth=12))
summary(window1.brm.ag)
tab_model(window1.brm.ag)

window1.brm.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_active_voice,
               b_ff_agent,
               `b_polytimedegreeEQ31:active_voice`,
               `b_polytimedegreeEQ32:active_voice`,
               `b_polytimedegreeEQ33:active_voice`,
               `b_polytimedegreeEQ31:ff_agent`,
               `b_polytimedegreeEQ32:ff_agent`,
               `b_polytimedegreeEQ33:ff_agent`,
               `b_active_voice:ff_agent`,
               `b_polytimedegreeEQ31:active_voice:ff_agent`,
               `b_polytimedegreeEQ32:active_voice:ff_agent`,
               `b_polytimedegreeEQ33:active_voice:ff_agent`,
               
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_active_voice > 0),
    mean(b_ff_agent > 0),
    mean(`b_polytimedegreeEQ31:active_voice`>0),
    mean(`b_polytimedegreeEQ32:active_voice`>0),
    mean(`b_polytimedegreeEQ33:active_voice`>0),
    mean(`b_polytimedegreeEQ31:ff_agent`>0),
    mean(`b_polytimedegreeEQ32:ff_agent`>0),
    mean(`b_polytimedegreeEQ33:ff_agent`>0),
    mean(`b_active_voice:ff_agent`>0),
    mean(`b_polytimedegreeEQ31:active_voice:ff_agent`>0),
    mean(`b_polytimedegreeEQ32:active_voice:ff_agent`>0),
    mean(`b_polytimedegreeEQ33:active_voice:ff_agent`>0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

window1.brm.pat <- brm(log.pat|weights(1/wts.pat) ~ (poly(time, degree = 3) * passive_voice ) * ff_patient +
                         (1 + time ||agg.id:ppt.no) + 
                         (1 + time || ppt.no) +
                         (1 | item), 
                       data = data.new.w1,control=list(adapt_delta=0.99, max_treedepth=12))

summary(window1.brm.pat)
tab_model(window1.brm.pat)

window1.brm.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_passive_voice,
               b_ff_patient,
               `b_polytimedegreeEQ31:passive_voice`,
               `b_polytimedegreeEQ32:passive_voice`,
               `b_polytimedegreeEQ33:passive_voice`,
               `b_polytimedegreeEQ31:ff_patient`,
               `b_polytimedegreeEQ32:ff_patient`,
               `b_polytimedegreeEQ33:ff_patient`,
               `b_passive_voice:ff_patient`,
               `b_polytimedegreeEQ31:passive_voice:ff_patient`,
               `b_polytimedegreeEQ32:passive_voice:ff_patient`,
               `b_polytimedegreeEQ33:passive_voice:ff_patient`,
               
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_passive_voice > 0),
    mean(b_ff_patient > 0),
    mean(`b_polytimedegreeEQ31:passive_voice`>0),
    mean(`b_polytimedegreeEQ32:passive_voice`>0),
    mean(`b_polytimedegreeEQ33:passive_voice`>0),
    mean(`b_polytimedegreeEQ31:ff_patient`>0),
    mean(`b_polytimedegreeEQ32:ff_patient`>0),
    mean(`b_polytimedegreeEQ33:ff_patient`>0),
    mean(`b_passive_voice:ff_patient`>0),
    mean(`b_polytimedegreeEQ31:passive_voice:ff_patient`>0),
    mean(`b_polytimedegreeEQ32:passive_voice:ff_patient`>0),
    mean(`b_polytimedegreeEQ33:passive_voice:ff_patient`>0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)



##GRAPHS FOR ALL ACTIVES AND ALL PASSIVES


window1 <- window1 %>% mutate(time_bin = cut(time_rel, 
                                             breaks = seq(-0.05, 1, by = 0.05),
                                             labels = seq(0, 1, by = 0.05)
)
)

agent_w1 <- window1 %>%
  group_by(type, Referent = "agent", time_bin) %>%
  dplyr::summarise(
    mean_prop = mean(a_prop_50, na.rm = TRUE),
    sd_prop = sd(a_prop_50, na.rm = TRUE),
    n = n()
  ) %>%
  mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )


patient_w1 <- window1 %>%
  group_by(type, Referent = "patient", time_bin) %>%
  dplyr::summarise(mean_prop = mean(p_prop_50, na.rm = TRUE),
                   sd_prop = sd(p_prop_50, na.rm = TRUE),
                   n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

all_w1 <- bind_rows(agent_w1, patient_w1) %>%
  mutate(
    time_bin = as.numeric(as.character(time_bin)), 
    Referent = factor(Referent)
  )

# actives 
all_act_w1 <- filter(all_w1, type == "act")
act_w1 <- ggplot(all_act_w1, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth = 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.25, 0.75) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "Actives Window 1") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )



#passives
all_pass_w1 <- filter(all_w1, type == "pass")
pass_w1 <- ggplot(all_pass_w1, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth = 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend=FALSE,alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.2, 0.75) +
  labs(x = "Relative Time", y = "Proportion of Looks",title = "Passives Window 1") +
  theme_minimal() +
  theme(
    plot.title = element_text(hjust = 0.5),
    legend.key = element_blank(),
    text = element_text(size = 12),
    axis.text = element_text(size = 12),
    axis.title = element_text(size = 12),
    legend.text = element_text(size = 12)
  )

##MODELS FOR APV ACTIVES IN TOPICAL AGENT VS. CONTROL CONDITIONS

ct_w1<- subset(data.new.w1, data.new.w1$cond=="A"&data.new.w1$type=="act" | data.new.w1$cond=="none"&data.new.w1$type=="act" | data.new.w1$cond=="P"&data.new.w1$type=="pass")
ct_w1$cond_type <- ifelse(ct_w1$cond == "A" & ct_w1$type == "act", "A_act", 
                          ifelse(ct_w1$cond == "none" & ct_w1$type == "act", "N_act", "P_pass"))
ct_w1$cond_type <- as.factor(ct_w1$cond_type)
w1.apv <- subset(ct_w1, ct_w1$wo == "APV" & (ct_w1$cond_type == "N_act" | ct_w1$cond_type == "A_act"))
w1.apv$cond_type <- ifelse(w1.apv$cond_type  == "N_act", 1, -1)


window1.apv.ag <- brm(log.agent|weights(1/wts.agent) ~ (poly(time, degree = 3) * cond_type ) * ff_agent +
                        (1 + time || agg.id:ppt.no) + 
                        (1 + time || ppt.no) +
                        (1|item),
                      data = w1.apv, control=list(adapt_delta=0.99, max_treedepth=12))
summary(window1.apv.ag)
tab_model(window1.apv.ag)


window1.apv.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_cond_type,
               b_ff_agent,
               `b_polytimedegreeEQ31:cond_type`,
               `b_polytimedegreeEQ32:cond_type`,
               `b_polytimedegreeEQ33:cond_type`,
               `b_polytimedegreeEQ31:ff_agent`,
               `b_polytimedegreeEQ32:ff_agent`,
               `b_polytimedegreeEQ33:ff_agent`,
               `b_cond_type:ff_agent`,
               `b_polytimedegreeEQ31:cond_type:ff_agent`,
               `b_polytimedegreeEQ32:cond_type:ff_agent`,
               `b_polytimedegreeEQ33:cond_type:ff_agent`,
               
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_cond_type > 0),
    mean(b_ff_agent > 0),
    mean(`b_polytimedegreeEQ31:cond_type`>0),
    mean(`b_polytimedegreeEQ32:cond_type`>0),
    mean(`b_polytimedegreeEQ33:cond_type`>0),
    mean(`b_polytimedegreeEQ31:ff_agent`>0),
    mean(`b_polytimedegreeEQ32:ff_agent`>0),
    mean(`b_polytimedegreeEQ33:ff_agent`>0),
    mean(`b_cond_type:ff_agent`>0),
    mean(`b_polytimedegreeEQ31:cond_type:ff_agent`>0),
    mean(`b_polytimedegreeEQ32:cond_type:ff_agent`>0),
    mean(`b_polytimedegreeEQ33:cond_type:ff_agent`>0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

window1.apv.pat <- brm(log.pat|weights(1/wts.pat) ~ (poly(time, degree = 3) * cond_type ) * ff_patient +
                         (1 + time || agg.id:ppt.no) + 
                         (1 + time || ppt.no) +
                         (1|item),
                       data = w1.apv, control=list(adapt_delta=0.99, max_treedepth=12))
summary(window1.apv.pat)
tab_model(window1.apv.pat)

window1.apv.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_cond_type,
               b_ff_patient,
               `b_polytimedegreeEQ31:cond_type`,
               `b_polytimedegreeEQ32:cond_type`,
               `b_polytimedegreeEQ33:cond_type`,
               `b_polytimedegreeEQ31:ff_patient`,
               `b_polytimedegreeEQ32:ff_patient`,
               `b_polytimedegreeEQ33:ff_patient`,
               `b_cond_type:ff_patient`,
               `b_polytimedegreeEQ31:cond_type:ff_patient`,
               `b_polytimedegreeEQ32:cond_type:ff_patient`,
               `b_polytimedegreeEQ33:cond_type:ff_patient`,
               
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_cond_type > 0),
    mean(b_ff_patient > 0),
    mean(`b_polytimedegreeEQ31:cond_type`>0),
    mean(`b_polytimedegreeEQ32:cond_type`>0),
    mean(`b_polytimedegreeEQ33:cond_type`>0),
    mean(`b_polytimedegreeEQ31:ff_patient`>0),
    mean(`b_polytimedegreeEQ32:ff_patient`>0),
    mean(`b_polytimedegreeEQ33:ff_patient`>0),
    mean(`b_cond_type:ff_patient`>0),
    mean(`b_polytimedegreeEQ31:cond_type:ff_patient`>0),
    mean(`b_polytimedegreeEQ32:cond_type:ff_patient`>0),
    mean(`b_polytimedegreeEQ33:cond_type:ff_patient`>0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)


##GRAPHS FOR APV ACTIVES IN TOPICAL AGENT VS. CONTROL CONDITIONS

window1.apv <- subset(window1, window1$cond=="A"&window1$type=="act" | window1$cond=="none"&window1$type=="act")
window1.apv <- subset(window1, window1$wo == "APV")
window1.apv <- window1.apv %>% mutate(time_bin = cut(time_rel, 
                                                     breaks = seq(-0.05, 1, by = 0.05),
                                                     labels = seq(0, 1, by = 0.05)
)
)

agent_apv_w1 <- window1.apv %>%
  group_by(cond, Referent = "agent", time_bin) %>%
  dplyr::summarise(
    mean_prop = mean(a_prop_50, na.rm = TRUE),
    sd_prop = sd(a_prop_50, na.rm = TRUE),
    n = n()
  ) %>%
  mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

patient_apv_w1 <- window1.apv %>%
  group_by(cond, Referent = "patient", time_bin) %>%
  dplyr::summarise(mean_prop = mean(p_prop_50, na.rm = TRUE),
                   sd_prop = sd(p_prop_50, na.rm = TRUE),
                   n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

all_apv_w1 <- bind_rows(agent_apv_w1, patient_apv_w1) %>%
  mutate(
    time_bin = as.numeric(as.character(time_bin)), 
    Referent = factor(Referent)
  )


all_aapv_w1 <- filter(all_apv_w1, cond == "A")
aapv_w1 <- ggplot(all_aapv_w1, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "Topical Agent APV Actives Window 1") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_napv_w1 <- filter(all_apv_w1, cond == "none")
napv_w1 <- ggplot(all_napv_w1, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "No Topic APV Actives Window 1") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )

##MODELS FOR PRODROPPED VS. NON-PRODROPPED ACTIVES AND PASSIVES

actives <- subset(data.new.w1, data.new.w1$type == "act"& data.new.w1$cond=="A" & (data.new.w1$wo == "APV"|data.new.w1$wo == "PV"))
passives <- subset(data.new.w1, data.new.w1$type == "pass"& data.new.w1$cond=="P"& (data.new.w1$wo == "PAV"|data.new.w1$wo == "AV"))
actives$wo <- as.factor(actives$wo)
passives$wo <- as.factor(passives$wo)
actives$wo <- ifelse(actives$wo == "APV", 1, -1)
passives$wo <- ifelse(passives$wo == "PAV", 1, -1)


window1.actives.ag <- brm(log.agent | weights(1/wts.agent) ~ (poly(time, degree=3) * wo) * ff_agent  +
                            (1 + time || agg.id:ppt.no) + 
                            (1 + time || ppt.no) +
                            (1 |item),
                          data = actives, control=list(adapt_delta=0.99, max_treedepth=12))
summary(window1.actives.ag)
tab_model(window1.actives.ag)

window1.actives.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               b_ff_agent,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`,
               `b_polytimedegreeEQ31:ff_agent`,
               `b_polytimedegreeEQ32:ff_agent`,
               `b_polytimedegreeEQ33:ff_agent`,
               `b_wo:ff_agent`,
               `b_polytimedegreeEQ31:wo:ff_agent`,
               `b_polytimedegreeEQ32:wo:ff_agent`,
               `b_polytimedegreeEQ33:wo:ff_agent`,
               
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo > 0),
    mean(b_ff_agent > 0),
    mean(`b_polytimedegreeEQ31:wo`>0),
    mean(`b_polytimedegreeEQ32:wo`>0),
    mean(`b_polytimedegreeEQ33:wo`>0),
    mean(`b_polytimedegreeEQ31:ff_agent`>0),
    mean(`b_polytimedegreeEQ32:ff_agent`>0),
    mean(`b_polytimedegreeEQ33:ff_agent`>0),
    mean(`b_wo:ff_agent`>0),
    mean(`b_polytimedegreeEQ31:wo:ff_agent`>0),
    mean(`b_polytimedegreeEQ32:wo:ff_agent`>0),
    mean(`b_polytimedegreeEQ33:wo:ff_agent`>0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)


window1.actives.pat <- brm(log.pat | weights(1/wts.pat) ~ (poly(time, degree = 3) * wo ) * ff_patient +
                             (1 + time || agg.id:ppt.no) + 
                             (1 + time || ppt.no) +
                             (1|item),
                           data = actives,control=list(adapt_delta=0.99))
summary(window1.actives.pat)
tab_model(window1.actives.pat)

window1.actives.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               b_ff_patient,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`,
               `b_polytimedegreeEQ31:ff_patient`,
               `b_polytimedegreeEQ32:ff_patient`,
               `b_polytimedegreeEQ33:ff_patient`,
               `b_wo:ff_patient`,
               `b_polytimedegreeEQ31:wo:ff_patient`,
               `b_polytimedegreeEQ32:wo:ff_patient`,
               `b_polytimedegreeEQ33:wo:ff_patient`,
               
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo > 0),
    mean(b_ff_patient > 0),
    mean(`b_polytimedegreeEQ31:wo`>0),
    mean(`b_polytimedegreeEQ32:wo`>0),
    mean(`b_polytimedegreeEQ33:wo`>0),
    mean(`b_polytimedegreeEQ31:ff_patient`>0),
    mean(`b_polytimedegreeEQ32:ff_patient`>0),
    mean(`b_polytimedegreeEQ33:ff_patient`>0),
    mean(`b_wo:ff_patient`>0),
    mean(`b_polytimedegreeEQ31:wo:ff_patient`>0),
    mean(`b_polytimedegreeEQ32:wo:ff_patient`>0),
    mean(`b_polytimedegreeEQ33:wo:ff_patient`>0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)



window1.passives.ag <- brm(log.agent|weights(1/wts.agent) ~ (poly(time, degree = 3) * wo ) * ff_agent +
                             (1 + time || agg.id:ppt.no) + 
                             (1 + time || ppt.no) +
                             (1 | item),
                           data = passives, control=list(adapt_delta=0.99))
summary(window1.passives.ag)
tab_model(window1.passives.ag)

window1.passives.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               b_ff_agent,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`,
               `b_polytimedegreeEQ31:ff_agent`,
               `b_polytimedegreeEQ32:ff_agent`,
               `b_polytimedegreeEQ33:ff_agent`,
               `b_wo:ff_agent`,
               `b_polytimedegreeEQ31:wo:ff_agent`,
               `b_polytimedegreeEQ32:wo:ff_agent`,
               `b_polytimedegreeEQ33:wo:ff_agent`,
               
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo > 0),
    mean(b_ff_agent > 0),
    mean(`b_polytimedegreeEQ31:wo`>0),
    mean(`b_polytimedegreeEQ32:wo`>0),
    mean(`b_polytimedegreeEQ33:wo`>0),
    mean(`b_polytimedegreeEQ31:ff_agent`>0),
    mean(`b_polytimedegreeEQ32:ff_agent`>0),
    mean(`b_polytimedegreeEQ33:ff_agent`>0),
    mean(`b_wo:ff_agent`>0),
    mean(`b_polytimedegreeEQ31:wo:ff_agent`>0),
    mean(`b_polytimedegreeEQ32:wo:ff_agent`>0),
    mean(`b_polytimedegreeEQ33:wo:ff_agent`>0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

window1.passives.pat <- brm(log.pat| weights(1/wts.pat) ~ (poly(time, degree = 3) * wo ) * ff_patient +
                              (1 + time || agg.id:ppt.no) + 
                              (1 + time || ppt.no) +
                              (1|item),
                            data = passives, control=list(adapt_delta=0.99))

summary(window1.passives.pat)
tab_model(window1.passives.pat)


window1.passives.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               b_ff_patient,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`,
               `b_polytimedegreeEQ31:ff_patient`,
               `b_polytimedegreeEQ32:ff_patient`,
               `b_polytimedegreeEQ33:ff_patient`,
               `b_wo:ff_patient`,
               `b_polytimedegreeEQ31:wo:ff_patient`,
               `b_polytimedegreeEQ32:wo:ff_patient`,
               `b_polytimedegreeEQ33:wo:ff_patient`,
               
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo > 0),
    mean(b_ff_patient > 0),
    mean(`b_polytimedegreeEQ31:wo`>0),
    mean(`b_polytimedegreeEQ32:wo`>0),
    mean(`b_polytimedegreeEQ33:wo`>0),
    mean(`b_polytimedegreeEQ31:ff_patient`>0),
    mean(`b_polytimedegreeEQ32:ff_patient`>0),
    mean(`b_polytimedegreeEQ33:ff_patient`>0),
    mean(`b_wo:ff_patient`>0),
    mean(`b_polytimedegreeEQ31:wo:ff_patient`>0),
    mean(`b_polytimedegreeEQ32:wo:ff_patient`>0),
    mean(`b_polytimedegreeEQ33:wo:ff_patient`>0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)


##GRAPHS FOR PRODROPPED VS. NON-PRODROPPED ACTIVES AND PASSIVES

wo_act_w1 <- subset(window1, window1$type == "act"& window1$cond=="A"&(window1$wo == "APV"|window1$wo == "PV"))
wo_pass_w1 <- subset(window1, window1$type == "pass"&window1$cond=="P"&(window1$wo == "PAV"|window1$wo == "AV"))
wo_w1 <- rbind(wo_act_w1,wo_pass_w1)

wo_w1 <- wo_w1 %>% mutate(time_bin = cut(time_rel, 
                                         breaks = seq(-0.05, 1, by = 0.05),
                                         labels = seq(0, 1, by = 0.05)
)
)

agent_wo_w1 <- wo_w1 %>%
  group_by(wo, Referent = "agent", time_bin) %>%
  dplyr::summarise(
    mean_prop = mean(a_prop_50, na.rm = TRUE),
    sd_prop = sd(a_prop_50, na.rm = TRUE),
    n = n()
  ) %>%
  mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

patient_wo_w1 <- wo_w1 %>%
  group_by(wo, Referent = "patient", time_bin) %>%
  dplyr::summarise(mean_prop = mean(p_prop_50, na.rm = TRUE),
                   sd_prop = sd(p_prop_50, na.rm = TRUE),
                   n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

all_wo_w1 <- bind_rows(agent_wo_w1, patient_wo_w1) %>%
  mutate(
    time_bin = as.numeric(as.character(time_bin)), 
    Referent = factor(Referent)
  )


all_pav_w1 <- filter(all_wo_w1, wo == "PAV")
pav_w1 <- ggplot(all_pav_w1, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "PAV Passives Window 1") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_av_w1 <- filter(all_wo_w1, wo == "AV")
av_w1 <- ggplot(all_av_w1, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "AV Passives Window 1") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_apv_w1 <- filter(all_wo_w1, wo == "APV")
apv_w1 <- ggplot(all_apv_w1, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "APV Actives Window 1") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_pv_w1 <- filter(all_wo_w1, wo == "PV")
pv_w1 <- ggplot(all_pv_w1, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "PV Actives Window 1") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )

##MODELS FOR FULL ACTIVES VS. FULL PASSIVES

full_w1 <- subset(data.new.w1, (data.new.w1$type == "pass"& data.new.w1$cond=="P"& data.new.w1$wo == "PAV"| data.new.w1$type == "act"& data.new.w1$cond=="none"& data.new.w1$wo == "APV"))

window1.full.ag <- brm(log.agent | weights(1/wts.agent) ~ (poly(time, degree=3) * active_voice) * ff_agent  +
                         (1 + time || agg.id:ppt.no) + 
                         (1 + time || ppt.no) +
                         (1 |item),
                       data = full_w1, control=list(adapt_delta=0.99))

summary(window1.full.ag)
tab_model(window1.full.ag)

window1.full.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_active_voice,
               b_ff_agent,
               `b_polytimedegreeEQ31:active_voice`,
               `b_polytimedegreeEQ32:active_voice`,
               `b_polytimedegreeEQ33:active_voice`,
               `b_polytimedegreeEQ31:ff_agent`,
               `b_polytimedegreeEQ32:ff_agent`,
               `b_polytimedegreeEQ33:ff_agent`,
               `b_active_voice:ff_agent`,
               `b_polytimedegreeEQ31:active_voice:ff_agent`,
               `b_polytimedegreeEQ32:active_voice:ff_agent`,
               `b_polytimedegreeEQ33:active_voice:ff_agent`,
               
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_active_voice > 0),
    mean(b_ff_agent > 0),
    mean(`b_polytimedegreeEQ31:active_voice`>0),
    mean(`b_polytimedegreeEQ32:active_voice`>0),
    mean(`b_polytimedegreeEQ33:active_voice`>0),
    mean(`b_polytimedegreeEQ31:ff_agent`>0),
    mean(`b_polytimedegreeEQ32:ff_agent`>0),
    mean(`b_polytimedegreeEQ33:ff_agent`>0),
    mean(`b_active_voice:ff_agent`>0),
    mean(`b_polytimedegreeEQ31:active_voice:ff_agent`>0),
    mean(`b_polytimedegreeEQ32:active_voice:ff_agent`>0),
    mean(`b_polytimedegreeEQ33:active_voice:ff_agent`>0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)


window1.full.pat <- brm(log.pat | weights(1/wts.pat) ~ (poly(time, degree=3) * passive_voice) * ff_patient  +
                          (1 + time || agg.id:ppt.no) + 
                          (1 + time || ppt.no) +
                          (1 |item),
                        data = full_w1, control=list(adapt_delta=0.99))
summary(window1.full.pat)
tab_model(window1.full.pat)

window1.full.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_passive_voice,
               b_ff_patient,
               `b_polytimedegreeEQ31:passive_voice`,
               `b_polytimedegreeEQ32:passive_voice`,
               `b_polytimedegreeEQ33:passive_voice`,
               `b_polytimedegreeEQ31:ff_patient`,
               `b_polytimedegreeEQ32:ff_patient`,
               `b_polytimedegreeEQ33:ff_patient`,
               `b_passive_voice:ff_patient`,
               `b_polytimedegreeEQ31:passive_voice:ff_patient`,
               `b_polytimedegreeEQ32:passive_voice:ff_patient`,
               `b_polytimedegreeEQ33:passive_voice:ff_patient`,
               
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_passive_voice > 0),
    mean(b_ff_patient > 0),
    mean(`b_polytimedegreeEQ31:passive_voice`>0),
    mean(`b_polytimedegreeEQ32:passive_voice`>0),
    mean(`b_polytimedegreeEQ33:passive_voice`>0),
    mean(`b_polytimedegreeEQ31:ff_patient`>0),
    mean(`b_polytimedegreeEQ32:ff_patient`>0),
    mean(`b_polytimedegreeEQ33:ff_patient`>0),
    mean(`b_passive_voice:ff_patient`>0),
    mean(`b_polytimedegreeEQ31:passive_voice:ff_patient`>0),
    mean(`b_polytimedegreeEQ32:passive_voice:ff_patient`>0),
    mean(`b_polytimedegreeEQ33:passive_voice:ff_patient`>0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

#LINGUISTIC ENCODING I-----------------------------------

#defining time window
window2 <- data_all[(data_all$tw == 2),] 
window2$time_bin50 <- window2$time_bin50 - 12
window2$time_rel2 <- (50*window2$time_bin50)/(0.5*(window2$sol-600))

#preparation for regressions
data.new.w2 <- ddply(window2, .(time_bin50, ppt.no, type, cond, wo, item, sol),  
                     summarise, 
                     agent.sum = sum(agent), 
                     pat.sum = sum(patient), 
                     N = length(ms))

data.new.w2$agg.id <- data.new.w2$ppt.no*1000
data.new.w2$agg.id <- ifelse(data.new.w2$type == "act",
                             data.new.w2$agg.id + 10,
                             data.new.w2$agg.id + 20)

data.new.w2$log.pat <- log((data.new.w2$pat.sum + .5) / 
                             (data.new.w2$N - data.new.w2$pat.sum + .5))
data.new.w2$wts.pat <- 1/(data.new.w2$pat.sum + .5) + 
  1/(data.new.w2$N - data.new.w2$pat.sum + .5)

data.new.w2$log.agent <- log((data.new.w2$agent.sum + .5) / 
                               (data.new.w2$N - data.new.w2$agent.sum + .5))
data.new.w2$wts.agent <- 1/(data.new.w2$agent.sum + .5) +
  1/(data.new.w2$N - data.new.w2$agent.sum + .5)

data.new.w2$passive_voice <- ifelse(data.new.w2$type == "pass", 1, -1)   
data.new.w2$active_voice <- ifelse(data.new.w2$type == "pass", -1, 1)  
data.new.w2$time <- (50*data.new.w2$time_bin50)/(0.5*(data.new.w2$sol-600))
data.new.w2$time <- scale(data.new.w2$time, center = FALSE, scale = TRUE)

##MODELS FOR ALL ACTIVES AND ALL PASSIVES

window2.brm.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * active_voice +
                        (1 + time || agg.id:ppt.no) + 
                        (1 | item) +
                        (1 + time || ppt.no), 
                      data = data.new.w2, control=list(adapt_delta=0.99))
summary(window2.brm.ag)
tab_model(window2.brm.ag)

window2.brm.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_active_voice,
               `b_polytimedegreeEQ31:active_voice`,
               `b_polytimedegreeEQ32:active_voice`,
               `b_polytimedegreeEQ33:active_voice`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_active_voice > 0),
    mean(`b_polytimedegreeEQ31:active_voice` > 0),
    mean(`b_polytimedegreeEQ32:active_voice` > 0),
    mean(`b_polytimedegreeEQ33:active_voice` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

window2.brm.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * passive_voice +
                         (1 + time || agg.id:ppt.no) + 
                         (1 + time || ppt.no) +
                         (1 | item),
                       data = data.new.w2, control=list(adapt_delta=0.99))

summary(window2.brm.pat)
tab_model(window2.brm.pat)

window2.brm.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_passive_voice,
               `b_polytimedegreeEQ31:passive_voice`,
               `b_polytimedegreeEQ32:passive_voice`,
               `b_polytimedegreeEQ33:passive_voice`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_passive_voice > 0),
    mean(`b_polytimedegreeEQ31:passive_voice` > 0),
    mean(`b_polytimedegreeEQ32:passive_voice` > 0),
    mean(`b_polytimedegreeEQ33:passive_voice` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

##GRAPHS FOR ALL ACTIVES AND ALL PASSIVES

window2 <- window2 %>% mutate(time_bin = cut(time_rel2,
                                             breaks = seq(-0.05, 1, by = 0.05),
                                             labels = seq(0, 1, by = 0.05)
)
)

agent_w2 <- window2 %>%
  group_by(type, Referent = "agent", time_bin) %>%
  dplyr::summarise(mean_prop = mean(a_prop_50, na.rm = TRUE),
                   sd_prop = sd(a_prop_50, na.rm = TRUE),
                   n = n()
  ) %>%
  mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )


patient_w2 <- window2 %>%
  group_by(type, Referent = "patient", time_bin) %>%
  dplyr::summarise(mean_prop = mean(p_prop_50, na.rm = TRUE),
                   sd_prop = sd(p_prop_50, na.rm = TRUE),
                   n = n()
  ) %>%
  mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )


all_w2 <- bind_rows(agent_w2, patient_w2) %>%
  mutate(
    time_bin = as.numeric(as.character(time_bin)), # Convert time_bin to numeric for plotting
    Referent = factor(Referent)
  )


all_act_w2 <- filter(all_w2, type == "act")
act_w2 <- ggplot(all_act_w2, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(size = 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.2, 0.75) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "Actives Window 2") +
  theme_minimal() +
  theme(
    plot.title = element_text(hjust = 0.5),
    legend.key = element_blank(),
    text = element_text(size = 12),
    axis.text = element_text(size = 12),
    axis.title = element_text(size = 12),
    legend.text = element_text(size = 12)
  )


all_pass_w2 <- filter(all_w2, type == "pass")
pass_w2 <- ggplot(all_pass_w2, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(size = 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend=FALSE,alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.8) +
  labs( x = "Relative Time", y = "Proportion of Looks",title = "Passives Window 2") +
  theme_minimal() +
  theme(
    plot.title = element_text(hjust = 0.5),
    legend.key = element_blank(),
    text = element_text(size = 12),
    axis.text = element_text(size = 12),
    axis.title = element_text(size = 12),
    legend.text = element_text(size = 12)
  )

##MODELS FOR APV ACTIVES IN TOPICAL AGENT VS. CONTROL CONDITIONS

ct_w2<- subset(data.new.w2, data.new.w2$cond=="A"&data.new.w2$type=="act" | data.new.w2$cond=="none"&data.new.w2$type=="act" | data.new.w2$cond=="P"&data.new.w2$type=="pass")
ct_w2$cond_type <- ifelse(ct_w2$cond == "A" & ct_w2$type == "act", "A_act", 
                          ifelse(ct_w2$cond == "none" & ct_w2$type == "act", "N_act", "P_pass"))
ct_w2$cond_type <- as.factor(ct_w2$cond_type)
w2.apv <- subset(ct_w2, ct_w2$wo == "APV" & (ct_w2$cond_type == "N_act" | ct_w2$cond_type == "A_act"))
w2.apv$cond_type <- ifelse(w2.apv$cond_type  == "N_act", 1, -1)


window2.apv.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * cond_type  +
                        (1 + time || agg.id:ppt.no) + 
                        (1 + time || ppt.no) +
                        (1 | item),
                      data = w2.apv, control=list(adapt_delta=0.99, max_treedepth=12))
summary(window2.apv.ag)
tab_model(window2.apv.ag)

window2.apv.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_cond_type,
               `b_polytimedegreeEQ31:cond_type`,
               `b_polytimedegreeEQ32:cond_type`,
               `b_polytimedegreeEQ33:cond_type`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_cond_type >0),
    mean(`b_polytimedegreeEQ31:cond_type` > 0),
    mean(`b_polytimedegreeEQ32:cond_type` > 0),
    mean(`b_polytimedegreeEQ33:cond_type` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)


window2.apv.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * cond_type  +
                         (1 + time || agg.id:ppt.no) + 
                         (1 + time || ppt.no) +
                         (1|item),
                       data = w2.apv, control=list(adapt_delta=0.99))
summary(window2.apv.pat)
tab_model(window2.apv.pat)

window2.apv.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_cond_type,
               `b_polytimedegreeEQ31:cond_type`,
               `b_polytimedegreeEQ32:cond_type`,
               `b_polytimedegreeEQ33:cond_type`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_cond_type >0),
    mean(`b_polytimedegreeEQ31:cond_type` > 0),
    mean(`b_polytimedegreeEQ32:cond_type` > 0),
    mean(`b_polytimedegreeEQ33:cond_type` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

##GRAPHS FOR APV ACTIVES IN TOPICAL AGENT VS. CONTROL CONDITIONS

window2.apv <- subset(window2, window2$cond=="A"&window2$type=="act" | window2$cond=="none"&window2$type=="act")
window2.apv <- subset(window2, window2$wo == "APV")
window2.apv <- window2.apv %>% mutate(time_bin = cut(time_rel2, 
                                                     breaks = seq(-0.05, 1, by = 0.05),
                                                     labels = seq(0, 1, by = 0.05)
)
)

agent_apv_w2 <- window2.apv %>%
  group_by(cond, Referent = "agent", time_bin) %>%
  dplyr::summarise(
    mean_prop = mean(a_prop_50, na.rm = TRUE),
    sd_prop = sd(a_prop_50, na.rm = TRUE),
    n = n()
  ) %>%
  mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

patient_apv_w2 <- window2.apv %>%
  group_by(cond, Referent = "patient", time_bin) %>%
  dplyr::summarise(mean_prop = mean(p_prop_50, na.rm = TRUE),
                   sd_prop = sd(p_prop_50, na.rm = TRUE),
                   n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

all_apv_w2 <- bind_rows(agent_apv_w2, patient_apv_w2) %>%
  mutate(
    time_bin = as.numeric(as.character(time_bin)), 
    Referent = factor(Referent)
  )


all_aapv_w2 <- filter(all_apv_w2, cond == "A")
aapv_w2 <- ggplot(all_aapv_w2, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "Topical Agent APV Actives Window 2") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_napv_w2 <- filter(all_apv_w2, cond == "none")
napv_w2 <- ggplot(all_napv_w2, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "No Topic APV Actives Window 2") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )

##MODELS FOR PRODROPPED VS. NON-PRODROPPED ACTIVES AND PASSIVES

actives2 <- subset(data.new.w2, data.new.w2$type == "act"& data.new.w2$cond == "A"&(data.new.w2$wo == "APV"|data.new.w2$wo == "PV"))
passives2 <- subset(data.new.w2, data.new.w2$type == "pass"& data.new.w2$cond == "P"& (data.new.w2$wo == "PAV"|data.new.w2$wo == "AV"))
actives2$wo <- as.factor(actives2$wo)
passives2$wo <- as.factor(passives2$wo)
actives2$wo <- ifelse(actives2$wo == "APV", 1, -1)
passives2$wo <- ifelse(passives2$wo == "PAV", 1, -1)


window2.actives.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * wo +
                            (1 + time || agg.id:ppt.no) + 
                            (1 + time || ppt.no) +
                            (1|item),
                          data = actives2, control=list(adapt_delta=0.99))
summary(window2.actives.ag)
tab_model(window2.actives.ag)


window2.actives.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo > 0),
    mean(`b_polytimedegreeEQ31:wo` > 0),
    mean(`b_polytimedegreeEQ32:wo` > 0),
    mean(`b_polytimedegreeEQ33:wo` > 0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

window2.actives.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * wo  +
                             (1 + time || agg.id:ppt.no) + 
                             (1 + time || ppt.no) +
                             (1|item),
                           data = actives2, control=list(adapt_delta=0.99))
summary(window2.actives.pat)
tab_model(window2.actives.pat)

window2.actives.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo > 0),
    mean(`b_polytimedegreeEQ31:wo` > 0),
    mean(`b_polytimedegreeEQ32:wo` > 0),
    mean(`b_polytimedegreeEQ33:wo` > 0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)


window2.passives.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * wo  +
                             (1 + time || agg.id:ppt.no) + 
                             (1 + time || ppt.no) +
                             (1|item),
                           data = passives2, control=list(adapt_delta=0.99))
summary(window2.passives.ag)
tab_model(window2.passives.ag)

window2.passives.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo > 0),
    mean(`b_polytimedegreeEQ31:wo` > 0),
    mean(`b_polytimedegreeEQ32:wo` > 0),
    mean(`b_polytimedegreeEQ33:wo` > 0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)


window2.passives.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * wo  +
                              (1 + time || agg.id:ppt.no) + 
                              (1 + time || ppt.no) +
                              (1|item),
                            data = passives2, control=list(adapt_delta=0.99))
summary(window2.passives.pat)
tab_model(window2.passives.pat)

window2.passives.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo > 0),
    mean(`b_polytimedegreeEQ31:wo` > 0),
    mean(`b_polytimedegreeEQ32:wo` > 0),
    mean(`b_polytimedegreeEQ33:wo` > 0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

###GRAPHS FOR PRODROPPED VS. NON-PRODROPPED ACTIVES AND PASSIVES

wo_act_w2 <- subset(window2, window2$type == "act"& window2$cond == "A"&(window2$wo == "APV"|window2$wo == "PV"))
wo_pass_w2 <- subset(window2, window2$type == "pass"& window2$cond == "P"&(window2$wo == "PAV"|window2$wo == "AV"))
wo_w2 <- rbind(wo_act_w2,wo_pass_w2)

wo_w2 <- wo_w2 %>% mutate(time_bin = cut(time_rel2, 
                                         breaks = seq(-0.05, 1, by = 0.05),
                                         labels = seq(0, 1, by = 0.05)
)
)


agent_wo_w2 <- wo_w2 %>%
  group_by(wo, Referent = "agent", time_bin) %>%
  dplyr::summarise(
    mean_prop = mean(a_prop_50, na.rm = TRUE),
    sd_prop = sd(a_prop_50, na.rm = TRUE),
    n = n()
  ) %>%
  mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

patient_wo_w2 <- wo_w2 %>%
  group_by(wo, Referent = "patient", time_bin) %>%
  dplyr::summarise(mean_prop = mean(p_prop_50, na.rm = TRUE),
                   sd_prop = sd(p_prop_50, na.rm = TRUE),
                   n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

all_wo_w2 <- bind_rows(agent_wo_w2, patient_wo_w2) %>%
  mutate(
    time_bin = as.numeric(as.character(time_bin)), 
    Referent = factor(Referent)
  )

all_pav_w2 <- filter(all_wo_w2, wo == "PAV")
pav_w2 <- ggplot(all_pav_w2, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0, 1) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "PAV Passives Window 2") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_av_w2 <- filter(all_wo_w2, wo == "AV")
av_w2 <- ggplot(all_av_w2, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "AV Passives Window 2") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_apv_w2 <- filter(all_wo_w2, wo == "APV")
apv_w2 <- ggplot(all_apv_w2, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "APV Actives Window 2") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_pv_w2 <- filter(all_wo_w2, wo == "PV")
pv_w2 <- ggplot(all_pv_w2, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0, 1) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "PV Actives Window 2") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )

##MODELS FOR FULL ACTIVES VS. FULL PASSIVES

full_w2 <- subset(data.new.w2, (data.new.w2$type == "pass"& data.new.w2$cond=="P"& data.new.w2$wo == "PAV"| data.new.w2$type == "act"& data.new.w2$cond=="none"& data.new.w2$wo == "APV"))

window2.full.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * active_voice  +
                         (1 + time || agg.id:ppt.no) + 
                         (1 + time || ppt.no) +
                         (1|item),
                       data = full_w2, control=list(adapt_delta=0.99))
summary(window2.full.ag)
tab_model(window2.full.ag)

window2.full.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_active_voice,
               `b_polytimedegreeEQ31:active_voice`,
               `b_polytimedegreeEQ32:active_voice`,
               `b_polytimedegreeEQ33:active_voice`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_active_voice > 0),
    mean(`b_polytimedegreeEQ31:active_voice` > 0),
    mean(`b_polytimedegreeEQ32:active_voice` > 0),
    mean(`b_polytimedegreeEQ33:active_voice` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

window2.full.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * passive_voice  +
                          (1 + time || agg.id:ppt.no) + 
                          (1 + time || ppt.no) +
                          (1|item),
                        data = full_w2, control=list(adapt_delta=0.99)) 

summary(window2.full.pat)
tab_model(window2.full.pat)

window2.full.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_passive_voice,
               `b_polytimedegreeEQ31:passive_voice`,
               `b_polytimedegreeEQ32:passive_voice`,
               `b_polytimedegreeEQ33:passive_voice`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_passive_voice > 0),
    mean(`b_polytimedegreeEQ31:passive_voice` > 0),
    mean(`b_polytimedegreeEQ32:passive_voice` > 0),
    mean(`b_polytimedegreeEQ33:passive_voice` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

#LINGUISTIC ENCODING II---------------------------------

#defining time window and removing items that cause problem
window3 <- data_all[(data_all$tw == 3),] 
to_remove <- data.frame(
  ppt.no = c(11, 3, 2, 3, 2, 14),   
  item = c(13, 16, 4, 6, 24, 5),
  cond = c("A", "A", "none", "none", "P", "P")  
)
window3 <- window3 %>%
  anti_join(to_remove, by = c("ppt.no", "item", "cond"))

window3$ms <- ifelse(window3$sol %% 2 == 0, window3$ms-(601 + 0.5*(window3$sol-600)), window3$ms-(600.5 + 0.5*(window3$sol-600)))
window3 <- window3 %>% group_by(item, ppt.no, time_bin50_new = (ms %/% 50))
window3$time_rel3 <- (50*window3$time_bin50_new)/(0.5*(window3$sol-600))

#preparing for regressions
data.new.w3 <- ddply(window3, .(time_bin50_new, ppt.no, ppt_id, type, cond, wo, item, sol),  
                     summarise, 
                     agent.sum = sum(agent), 
                     pat.sum = sum(patient), 
                     N = length(ms))
head(data.new.w3)

data.new.w3$agg.id <- data.new.w3$ppt.no*1000
data.new.w3$agg.id <- ifelse(data.new.w3$type == "act",
                             data.new.w3$agg.id + 10,
                             data.new.w3$agg.id + 20)

data.new.w3$log.pat <- log((data.new.w3$pat.sum + .5) / 
                             (data.new.w3$N - data.new.w3$pat.sum + .5))
data.new.w3$wts.pat <- 1/(data.new.w3$pat.sum + .5) + 
  1/(data.new.w3$N - data.new.w3$pat.sum + .5)

data.new.w3$log.agent <- log((data.new.w3$agent.sum + .5) / 
                               (data.new.w3$N - data.new.w3$agent.sum + .5))
data.new.w3$wts.agent <- 1/(data.new.w3$agent.sum + .5) +
  1/(data.new.w3$N - data.new.w3$agent.sum + .5)

data.new.w3$passive_voice <- ifelse(data.new.w3$type == "pass", 1, -1)   
data.new.w3$active_voice <- ifelse(data.new.w3$type == "pass", -1, 1)  
data.new.w3$time <- (50*data.new.w3$time_bin50_new)/(0.5*(data.new.w3$sol-600))
data.new.w3$time <- scale(data.new.w3$time, center = FALSE, scale = FALSE)

##MODELS FOR ALL ACTIVES AND ALL PASSIVES

window3.brm.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * active_voice +
                        (1 + time || agg.id:ppt.no) + 
                        (1 + time || ppt.no) +
                        (1|item),
                      data = data.new.w3, control=list(adapt_delta=0.99))
summary(window3.brm.ag)
tab_model(window3.brm.ag)

window3.brm.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_active_voice,
               `b_polytimedegreeEQ31:active_voice`,
               `b_polytimedegreeEQ32:active_voice`,
               `b_polytimedegreeEQ33:active_voice`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_active_voice > 0),
    mean(`b_polytimedegreeEQ31:active_voice` > 0),
    mean(`b_polytimedegreeEQ32:active_voice` > 0),
    mean(`b_polytimedegreeEQ33:active_voice` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

window3.brm.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * passive_voice +
                         (1 + time || agg.id:ppt.no) + 
                         (1 + time || ppt.no) +
                         (1|item),
                       data = data.new.w3, control=list(adapt_delta=0.99, max_treedepth=12))
summary(window3.brm.pat)
tab_model(window3.brm.pat)

window3.brm.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_passive_voice,
               `b_polytimedegreeEQ31:passive_voice`,
               `b_polytimedegreeEQ32:passive_voice`,
               `b_polytimedegreeEQ33:passive_voice`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_passive_voice > 0),
    mean(`b_polytimedegreeEQ31:passive_voice` > 0),
    mean(`b_polytimedegreeEQ32:passive_voice` > 0),
    mean(`b_polytimedegreeEQ33:passive_voice` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

##GRAPHS FOR ALL ACTIVES AND ALL PASSIVES

window3 <- window3 %>% mutate(time_bin = cut(time_rel3,
                                             breaks = seq(-0.05, 1, by = 0.05),
                                             labels = seq(0, 1, by = 0.05)
)
)


agent_w3 <- window3 %>%
  group_by(type, Referent = "agent", time_bin) %>%
  dplyr::summarise(mean_prop = mean(a_prop_50, na.rm = TRUE),
                   sd_prop = sd(a_prop_50, na.rm = TRUE),
                   n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )


patient_w3 <- window3 %>%
  group_by(type, Referent = "patient", time_bin) %>%
  dplyr::summarise(mean_prop = mean(p_prop_50, na.rm = TRUE),
                   sd_prop = sd(p_prop_50, na.rm = TRUE),
                   n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

all_w3 <- bind_rows(agent_w3, patient_w3) %>%
  mutate(
    time_bin = as.numeric(as.character(time_bin)), # Convert time_bin to numeric for plotting
    Referent = factor(Referent)
  )


all_act_w3 <- filter(all_w3, type == "act")
act_w3 <- ggplot(all_act_w3, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(size = 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.75) +
  labs(x = "Relative Time",y = "Proportion of Looks",title = "Actives Window 3" ) +
  theme_minimal() +
  theme(
    plot.title = element_text(hjust = 0.5),
    legend.key = element_blank(),
    text = element_text(size = 12),
    axis.text = element_text(size = 12),
    axis.title = element_text(size = 12),
    legend.text = element_text(size = 12)
  )



all_pass_w3 <- filter(all_w3, type == "pass")
pass_w3 <- ggplot(all_pass_w3, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(size = 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.75) +
  labs(x = "Relative Time",y = "Proportion of Looks",title = "Passives Window 3") +
  theme_minimal() +
  theme(
    plot.title = element_text(hjust = 0.5),
    legend.key = element_blank(),
    text = element_text(size = 12),
    axis.text = element_text(size = 12),
    axis.title = element_text(size = 12),
    legend.text = element_text(size = 12)
  )

##MODELS FOR APV ACTIVES IN TOPICAL AGENT VS. CONTROL CONDITIONS
ct_w3<- subset(data.new.w3, data.new.w3$cond=="A"&data.new.w3$type=="act" | data.new.w3$cond=="none"&data.new.w3$type=="act" | data.new.w3$cond=="P"&data.new.w3$type=="pass")
ct_w3$cond_type <- ifelse(ct_w3$cond == "A" & ct_w3$type == "act", "A_act", 
                          ifelse(ct_w3$cond == "none" & ct_w3$type == "act", "N_act", "P_pass"))
ct_w3$cond_type <- as.factor(ct_w3$cond_type)
w3.apv <- subset(ct_w3, ct_w3$wo == "APV" & (ct_w3$cond_type == "N_act" | ct_w3$cond_type == "A_act"))
w3.apv$cond_type <- ifelse(w3.apv$cond_type  == "N_act", 1, -1)


window3.apv.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * cond_type  +
                        (1 + time || agg.id:ppt.no) + 
                        (1 + time || ppt.no) +
                        (1|item),
                      data = w3.apv, control=list(adapt_delta=0.99))
tab_model(window3.apv.ag)
summary(window3.apv.ag)

window3.apv.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_cond_type,
               `b_polytimedegreeEQ31:cond_type`,
               `b_polytimedegreeEQ32:cond_type`,
               `b_polytimedegreeEQ33:cond_type`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_cond_type >0),
    mean(`b_polytimedegreeEQ31:cond_type` > 0),
    mean(`b_polytimedegreeEQ32:cond_type` > 0),
    mean(`b_polytimedegreeEQ33:cond_type` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)


window3.apv.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * cond_type  +
                         (1 + time || agg.id:ppt.no) + 
                         (1 + time || ppt.no) +
                         (1|item),
                       data = w3.apv, control=list(adapt_delta=0.99))
summary(window3.apv.pat)
tab_model(window3.apv.pat)

window3.apv.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_cond_type,
               `b_polytimedegreeEQ31:cond_type`,
               `b_polytimedegreeEQ32:cond_type`,
               `b_polytimedegreeEQ33:cond_type`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_cond_type > 0),
    mean(`b_polytimedegreeEQ31:cond_type` > 0),
    mean(`b_polytimedegreeEQ32:cond_type` > 0),
    mean(`b_polytimedegreeEQ33:cond_type` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

##GRAPHS FOR APV ACTIVES IN TOPICAL AGENT VS. CONTROL CONDITIONS

window3.apv <- subset(window3, window3$cond=="A"&window3$type=="act" | window3$cond=="none"&window3$type=="act")
window3.apv <- subset(window3, window3$wo == "APV")

window3.apv <- window3.apv %>% mutate(time_bin = cut(time_rel3, 
                                                     breaks = seq(-0.05, 1, by = 0.05),
                                                     labels = seq(0, 1, by = 0.05)
)
)

agent_apv_w3 <- window3.apv %>%
  group_by(cond, Referent = "agent", time_bin) %>%
  dplyr::summarise(
    mean_prop = mean(a_prop_50, na.rm = TRUE),
    sd_prop = sd(a_prop_50, na.rm = TRUE),
    n = n()
  ) %>%
  mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

patient_apv_w3 <- window3.apv %>%
  group_by(cond, Referent = "patient", time_bin) %>%
  dplyr::summarise(mean_prop = mean(p_prop_50, na.rm = TRUE),
                   sd_prop = sd(p_prop_50, na.rm = TRUE),
                   n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

all_apv_w3 <- bind_rows(agent_apv_w3, patient_apv_w3) %>%
  mutate(
    time_bin = as.numeric(as.character(time_bin)), 
    Referent = factor(Referent)
  )


all_aapv_w3 <- filter(all_apv_w3, cond == "A")
aapv_w3 <- ggplot(all_aapv_w3, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "Topical Agent APV Actives Window 3") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_napv_w3 <- filter(all_apv_w3, cond == "none")
napv_w3 <- ggplot(all_napv_w3, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "No Topic APV Actives Window 3") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )

##MODELS FOR PRODROPPED VS. NON-PRODROPPED ACTIVES AND PASSIVES

actives3 <- subset(data.new.w3, data.new.w3$type == "act"& data.new.w3$cond == "A"&(data.new.w3$wo == "APV"|data.new.w3$wo == "PV"))
passives3 <- subset(data.new.w3, data.new.w3$type == "pass"& data.new.w3$cond == "P"&(data.new.w3$wo == "PAV"|data.new.w3$wo == "AV"))
actives3$wo <- as.factor(actives3$wo)
passives3$wo <- as.factor(passives3$wo)
actives3$wo <- ifelse(actives3$wo == "APV", 1, -1)
passives3$wo <- ifelse(passives3$wo == "PAV", 1, -1)

window3.actives.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * wo +
                            (1 + time || agg.id:ppt.no) + 
                            (1 + time || ppt.no) +
                            (1|item),
                          data = actives3, control=list(adapt_delta=0.99))
summary(window3.actives.ag)
tab_model(window3.actives.ag)

window3.actives.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo>0),
    mean(`b_polytimedegreeEQ31:wo` > 0),
    mean(`b_polytimedegreeEQ32:wo` > 0),
    mean(`b_polytimedegreeEQ33:wo` > 0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

window3.actives.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * wo  +
                             (1 + time || agg.id:ppt.no) + 
                             (1 + time || ppt.no) +
                             (1|item),
                           data = actives3,  control=list(adapt_delta=0.99))
tab_model(window3.actives.pat)

window3.actives.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo>0),
    mean(`b_polytimedegreeEQ31:wo` > 0),
    mean(`b_polytimedegreeEQ32:wo` > 0),
    mean(`b_polytimedegreeEQ33:wo` > 0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)


window3.passives.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * wo  +
                             (1 + time || agg.id:ppt.no) + 
                             (1 + time || ppt.no) +
                             (1|item),
                           data = passives3, control=list(adapt_delta=0.99))
summary(window3.passives.ag)
tab_model(window3.passives.ag)


window3.passives.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo>0),
    mean(`b_polytimedegreeEQ31:wo` > 0),
    mean(`b_polytimedegreeEQ32:wo` > 0),
    mean(`b_polytimedegreeEQ33:wo` > 0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

window3.passives.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * wo  +
                              (1 + time || agg.id:ppt.no) + 
                              (1 + time || ppt.no) +
                              (1|item),
                            data = passives3, control=list(adapt_delta=0.99))
summary(window3.passives.pat)
tab_model(window3.passives.pat)

window3.passives.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo>0),
    mean(`b_polytimedegreeEQ31:wo` > 0),
    mean(`b_polytimedegreeEQ32:wo` > 0),
    mean(`b_polytimedegreeEQ33:wo` > 0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

##GRAPHS FOR PRODROPPED VS. NON-PRODROPPED ACTIVES AND PASSIVES

wo_act_w3 <- subset(window3, window3$type == "act"& window3$cond=="A"&(window3$wo == "APV"|window3$wo == "PV"))
wo_pass_w3 <- subset(window3, window3$type == "pass"& window3$cond=="P"&(window3$wo == "PAV"|window3$wo == "AV"))
wo_w3 <- rbind(wo_act_w3,wo_pass_w3)

wo_w3 <- wo_w3 %>% mutate(time_bin = cut(time_rel3, 
                                         breaks = seq(-0.05, 1, by = 0.05),
                                         labels = seq(0, 1, by = 0.05)
)
)

agent_wo_w3 <- wo_w3 %>%
  group_by(wo, Referent = "agent", time_bin) %>%
  dplyr::summarise(
    mean_prop = mean(a_prop_50, na.rm = TRUE),
    sd_prop = sd(a_prop_50, na.rm = TRUE),
    n = n()
  ) %>%
  mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

patient_wo_w3 <- wo_w3 %>%
  group_by(wo, Referent = "patient", time_bin) %>%
  dplyr::summarise(mean_prop = mean(p_prop_50, na.rm = TRUE),
                   sd_prop = sd(p_prop_50, na.rm = TRUE),
                   n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

all_wo_w3 <- bind_rows(agent_wo_w3, patient_wo_w3) %>%
  mutate(
    time_bin = as.numeric(as.character(time_bin)), 
    Referent = factor(Referent)
  )

all_pav_w3 <- filter(all_wo_w3, wo == "PAV")
pav_w3 <- ggplot(all_pav_w3, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "PAV Passives Window 3") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_av_w3 <- filter(all_wo_w3, wo == "AV")
av_w3 <- ggplot(all_av_w3, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "AV Passives Window 3") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_apv_w3 <- filter(all_wo_w3, wo == "APV")
apv_w3 <- ggplot(all_apv_w3, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "APV Actives Window 3") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_pv_w3 <- filter(all_wo_w3, wo == "PV")
pv_w3 <- ggplot(all_pv_w3, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "PV Actives Window 3") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )

##MODELS FOR FULL ACTIVES VS. FULL PASSIVES

full_w3 <- subset(data.new.w3, (data.new.w3$type == "pass"& data.new.w3$cond=="P"& data.new.w3$wo == "PAV"| data.new.w3$type == "act"& data.new.w3$cond=="none"& data.new.w3$wo == "APV"))

window3.full.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * active_voice +
                         (1 + time || agg.id:ppt.no) + 
                         (1 + time || ppt.no) +
                         (1|item),
                       data = full_w3, control=list(adapt_delta=0.99))
summary(window3.full.ag)
tab_model(window3.full.ag)

window3.full.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_active_voice,
               `b_polytimedegreeEQ31:active_voice`,
               `b_polytimedegreeEQ32:active_voice`,
               `b_polytimedegreeEQ33:active_voice`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_active_voice > 0),
    mean(`b_polytimedegreeEQ31:active_voice` > 0),
    mean(`b_polytimedegreeEQ32:active_voice` > 0),
    mean(`b_polytimedegreeEQ33:active_voice` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

window3.full.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * passive_voice +
                          (1 + time || agg.id:ppt.no) + 
                          (1 + time || ppt.no) +
                          (1|item),
                        data = full_w3, control=list(adapt_delta=0.99))
summary(window3.full.pat)
tab_model(window3.full.pat)

window3.full.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_passive_voice,
               `b_polytimedegreeEQ31:passive_voice`,
               `b_polytimedegreeEQ32:passive_voice`,
               `b_polytimedegreeEQ33:passive_voice`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_passive_voice > 0),
    mean(`b_polytimedegreeEQ31:passive_voice` > 0),
    mean(`b_polytimedegreeEQ32:passive_voice` > 0),
    mean(`b_polytimedegreeEQ33:passive_voice` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

#LINGUISTIC ENCODING III-------------------------------
#data after speech onset
data_all_po <- read.csv("data_all_po.csv")

#defining time window
window4 <- subset(data_all_po, data_all_po$time_bin50 >= 0 & data_all_po$time_bin50 <= 20)
window4$time_bin50 <- window4$time_bin50 
window4$time_rel4 <- window4$time_bin50 / 20

#preparing for regressions
data.new.w4 <- ddply(window4, .(time_bin50, ppt.no, wo, type, cond, item),   
                     summarise, 
                     agent.sum = sum(agent), 
                     pat.sum = sum(patient), 
                     N = length(ms))

data.new.w4$agg.id <- data.new.w4$ppt.no*1000
data.new.w4$agg.id <- ifelse(data.new.w4$type == "act",
                             data.new.w4$agg.id + 10,
                             data.new.w4$agg.id + 20)

data.new.w4$log.pat <- log((data.new.w4$pat.sum + .5) / 
                             (data.new.w4$N - data.new.w4$pat.sum + .5))
data.new.w4$wts.pat <- 1/(data.new.w4$pat.sum + .5) + 
  1/(data.new.w4$N - data.new.w4$pat.sum + .5)

data.new.w4$log.agent <- log((data.new.w4$agent.sum + .5) / 
                               (data.new.w4$N - data.new.w4$agent.sum + .5))
data.new.w4$wts.agent <- 1/(data.new.w4$agent.sum + .5) +
  1/(data.new.w4$N - data.new.w4$agent.sum + .5)

data.new.w4$passive_voice <- ifelse(data.new.w4$type == "pass", 1, -1)   # NEW
data.new.w4$active_voice <- ifelse(data.new.w4$type == "pass", -1, 1)  
data.new.w4$time <- (50*data.new.w4$time_bin50)/1000
data.new.w4$time <- scale(data.new.w4$time, center = FALSE, scale = TRUE)

##MODELS FOR ALL ACTIVES AND ALL PASSIVES

window4.brm.ag <- brm(log.agent|weights(1/wts.agent)~ poly(time, degree = 3) * active_voice +
                        (1 + time || agg.id:ppt.no) + 
                        (1 + time || ppt.no) +
                        (1|item),
                      data = data.new.w4, control=list(adapt_delta=0.99))
summary(window4.brm.ag)
tab_model(window4.brm.ag)

window4.brm.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_active_voice,
               `b_polytimedegreeEQ31:active_voice`,
               `b_polytimedegreeEQ32:active_voice`,
               `b_polytimedegreeEQ33:active_voice`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_active_voice > 0),
    mean(`b_polytimedegreeEQ31:active_voice` > 0),
    mean(`b_polytimedegreeEQ32:active_voice` > 0),
    mean(`b_polytimedegreeEQ33:active_voice` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

window4.brm.pat <- brm(log.pat|weights(1/wts.pat)  ~ poly(time, degree = 3) * passive_voice +
                         (1 + time || agg.id:ppt.no) + 
                         (1 + time || ppt.no) +
                         (1|item),
                       data = data.new.w4, control=list(adapt_delta=0.99, max_treedepth=12))

summary(window4.brm.pat)
tab_model(window4.brm.pat)

window4.brm.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_passive_voice,
               `b_polytimedegreeEQ31:passive_voice`,
               `b_polytimedegreeEQ32:passive_voice`,
               `b_polytimedegreeEQ33:passive_voice`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_passive_voice > 0),
    mean(`b_polytimedegreeEQ31:passive_voice` > 0),
    mean(`b_polytimedegreeEQ32:passive_voice` > 0),
    mean(`b_polytimedegreeEQ33:passive_voice` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

##GRAPHS FOR ALL ACTIVES AND ALL PASSIVES

window4 <- window4 %>% mutate(time_bin = cut(time_rel4,
                                             breaks = seq(-0.05, 1, by = 0.05),
                                             labels = seq(0, 1, by = 0.05)
)
)

agent_w4 <- window4 %>%
  group_by(type, Referent = "agent", time_bin) %>%
  dplyr::summarise(mean_prop = mean(a_prop_50, na.rm = TRUE),
                   sd_prop = sd(a_prop_50, na.rm = TRUE),
                   n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

patient_w4 <- window4 %>%
  group_by(type, Referent = "patient", time_bin) %>%
  dplyr::summarise(mean_prop = mean(p_prop_50, na.rm = TRUE),
                   sd_prop = sd(p_prop_50, na.rm = TRUE),
                   n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

all_w4 <- bind_rows(agent_w4, patient_w4) %>%
  mutate(
    time_bin = as.numeric(as.character(time_bin)), 
    Referent = factor(Referent)
  )


all_act_w4 <- filter(all_w4, type == "act")
act_w4 <- ggplot(all_act_w4, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth = 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.75) +
  labs(x = "Relative Time",y = "Proportion of Looks",title = "Actives Window 4") +
  theme_minimal() +
  theme(
    plot.title = element_text(hjust = 0.5),
    legend.key = element_blank(),
    text = element_text(size = 12),
    axis.text = element_text(size = 12),
    axis.title = element_text(size = 12),
    legend.text = element_text(size = 12),
  )

all_pass_w4 <- filter(all_w4, type == "pass")
pass_w4 <- ggplot(all_pass_w4, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(size = 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.75) +
  labs(x = "Relative Time",y = "Proportion of Looks", title = "Passives Window 4") +
  theme_minimal() +
  theme(
    plot.title = element_text(hjust = 0.5),
    legend.key = element_blank(),
    text = element_text(size = 12),
    axis.text = element_text(size = 12),
    axis.title = element_text(size = 12),
    legend.text = element_text(size = 12)
  )

##MODELS FOR APV ACTIVES IN TOPICAL AGENT VS. CONTROL CONDITIONS

ct_w4<- subset(data.new.w4, data.new.w4$cond=="A"&data.new.w4$type=="act" | data.new.w4$cond=="none"&data.new.w4$type=="act" | data.new.w4$cond=="P"&data.new.w4$type=="pass")
ct_w4$cond_type <- ifelse(ct_w4$cond == "A" & ct_w4$type == "act", "A_act", 
                          ifelse(ct_w4$cond == "none" & ct_w4$type == "act", "N_act", "P_pass"))
ct_w4$cond_type <- as.factor(ct_w4$cond_type)
w4.apv <- subset(ct_w4, ct_w4$wo == "APV" & (ct_w4$cond_type == "N_act" | ct_w4$cond_type == "A_act"))
w4.apv$cond_type <- ifelse(w4.apv$cond_type  == "N_act", 1, -1)


window4.apv.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * cond_type  +
                        (1 + time || agg.id:ppt.no) + 
                        (1 + time || ppt.no) +
                        (1|item),
                      data = w4.apv, control=list(adapt_delta=0.99))
summary(window4.apv.ag)
tab_model(window4.apv.ag)

window4.apv.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_cond_type,
               `b_polytimedegreeEQ31:cond_type`,
               `b_polytimedegreeEQ32:cond_type`,
               `b_polytimedegreeEQ33:cond_type`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_cond_type > 0),
    mean(`b_polytimedegreeEQ31:cond_type` > 0),
    mean(`b_polytimedegreeEQ32:cond_type` > 0),
    mean(`b_polytimedegreeEQ33:cond_type` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)


window4.apv.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * cond_type  +
                         (1 + time || agg.id:ppt.no) + 
                         (1 + time || ppt.no) +
                         (1|item),
                       data = w4.apv, control=list(adapt_delta=0.99))
summary(window4.apv.pat)
tab_model(window4.apv.pat)

window4.apv.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_cond_type,
               `b_polytimedegreeEQ31:cond_type`,
               `b_polytimedegreeEQ32:cond_type`,
               `b_polytimedegreeEQ33:cond_type`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_cond_type > 0),
    mean(`b_polytimedegreeEQ31:cond_type` > 0),
    mean(`b_polytimedegreeEQ32:cond_type` > 0),
    mean(`b_polytimedegreeEQ33:cond_type` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

##GRAPHS FOR APV ACTIVES IN TOPICAL AGENT VS. CONTROL CONDITIONS

window4.apv <- subset(window4, window4$cond=="A"&window4$type=="act" | window4$cond=="none"&window4$type=="act")
window4.apv <- subset(window4, window4$wo == "APV")

window4.apv <- window4.apv %>% mutate(time_bin = cut(time_rel4, 
                                                     breaks = seq(-0.05, 1, by = 0.05),
                                                     labels = seq(0, 1, by = 0.05)
)
)

agent_apv_w4 <- window4.apv %>%
  group_by(cond, Referent = "agent", time_bin) %>%
  dplyr::summarise(
    mean_prop = mean(a_prop_50, na.rm = TRUE),
    sd_prop = sd(a_prop_50, na.rm = TRUE),
    n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

patient_apv_w4 <- window4.apv %>%
  group_by(cond, Referent = "patient", time_bin) %>%
  dplyr::summarise(mean_prop = mean(p_prop_50, na.rm = TRUE),
                   sd_prop = sd(p_prop_50, na.rm = TRUE),
                   n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

all_apv_w4 <- bind_rows(agent_apv_w4, patient_apv_w4) %>%
  mutate(
    time_bin = as.numeric(as.character(time_bin)), 
    Referent = factor(Referent)
  )


all_aapv_w4 <- filter(all_apv_w4, cond == "A")
aapv_w4 <- ggplot(all_aapv_w4, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "Topical Agent APV Actives Window 4") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_napv_w4 <- filter(all_apv_w4, cond == "none")
napv_w4 <- ggplot(all_napv_w4, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "No Topic APV Actives Window 4") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )

##MODELS FOR PRODROPPED VS. NON-PRODROPPED ACTIVES AND PASSIVES

actives4 <- subset(data.new.w4, data.new.w4$type == "act"& data.new.w4$cond == "A"&(data.new.w4$wo == "APV"|data.new.w4$wo == "PV"))
passives4 <- subset(data.new.w4, data.new.w4$type == "pass"& data.new.w4$cond == "P"&(data.new.w4$wo == "PAV"|data.new.w4$wo == "AV"))
actives4$wo <- as.factor(actives4$wo)
passives4$wo <- as.factor(passives4$wo)
actives4$wo <- ifelse(actives4$wo == "APV", 1, -1)
passives4$wo <- ifelse(passives4$wo == "PAV", 1, -1)

window4.actives.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * wo +
                            (1 + time || agg.id:ppt.no) + 
                            (1 + time || ppt.no) +
                            (1|item),
                          data = actives4, control=list(adapt_delta=0.99))
summary(window4.actives.ag)
tab_model(window4.actives.ag)

window4.actives.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo > 0),
    mean(`b_polytimedegreeEQ31:wo` > 0),
    mean(`b_polytimedegreeEQ32:wo` > 0),
    mean(`b_polytimedegreeEQ33:wo` > 0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)


window4.actives.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * wo  +
                             (1 + time || agg.id:ppt.no) + 
                             (1 + time || ppt.no) +
                             (1|item),
                           data = actives4, control=list(adapt_delta=0.99))
summary(window4.actives.pat)
tab_model(window4.actives.pat)

window4.actives.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo > 0),
    mean(`b_polytimedegreeEQ31:wo` > 0),
    mean(`b_polytimedegreeEQ32:wo` > 0),
    mean(`b_polytimedegreeEQ33:wo` > 0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)


window4.passives.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * wo  +
                             (1 + time || agg.id:ppt.no) + 
                             (1 + time || ppt.no) +
                             (1|item),
                           data = passives4, control=list(adapt_delta=0.99))
summary(window4.passives.ag)
tab_model(window4.passives.ag)

window4.passives.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo > 0),
    mean(`b_polytimedegreeEQ31:wo` > 0),
    mean(`b_polytimedegreeEQ32:wo` > 0),
    mean(`b_polytimedegreeEQ33:wo` > 0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)


window4.passives.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * wo  +
                              (1 + time || agg.id:ppt.no) + 
                              (1 + time || ppt.no) +
                              (1|item),
                            data = passives4, control=list(adapt_delta=0.99))
summary(window4.passives.pat)
tab_model(window4.passives.pat)


window4.passives.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_wo,
               `b_polytimedegreeEQ31:wo`,
               `b_polytimedegreeEQ32:wo`,
               `b_polytimedegreeEQ33:wo`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_wo > 0),
    mean(`b_polytimedegreeEQ31:wo` > 0),
    mean(`b_polytimedegreeEQ32:wo` > 0),
    mean(`b_polytimedegreeEQ33:wo` > 0),
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

##GRAPHS FOR PRODROPPED VS. NON-PRODROPPED ACTIVES AND PASSIVES

wo_act_w4 <- subset(window4, window4$type == "act"& window4$cond == "A"& (window4$wo == "APV"|window4$wo == "PV"))
wo_pass_w4 <- subset(window4, window4$type == "pass"& window4$cond == "P"&(window4$wo == "PAV"|window4$wo == "AV"))
wo_w4 <- rbind(wo_act_w4,wo_pass_w4)

wo_w4 <- wo_w4 %>% mutate(time_bin = cut(time_rel4, 
                                         breaks = seq(-0.05, 1, by = 0.05),
                                         labels = seq(0, 1, by = 0.05)
)
)


agent_wo_w4 <- wo_w4 %>%
  group_by(wo, Referent = "agent", time_bin) %>%
  dplyr::summarise(
    mean_prop = mean(a_prop_50, na.rm = TRUE),
    sd_prop = sd(a_prop_50, na.rm = TRUE),
    n = n()
  ) %>%
  mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

patient_wo_w4 <- wo_w4 %>%
  group_by(wo, Referent = "patient", time_bin) %>%
  dplyr::summarise(mean_prop = mean(p_prop_50, na.rm = TRUE),
                   sd_prop = sd(p_prop_50, na.rm = TRUE),
                   n = n()
  ) %>% mutate(
    upper = mean_prop + 2 * sd_prop / sqrt(n/50),
    lower = mean_prop - 2 * sd_prop / sqrt(n/50)
  )

all_wo_w4 <- bind_rows(agent_wo_w4, patient_wo_w4) %>%
  mutate(
    time_bin = as.numeric(as.character(time_bin)), 
    Referent = factor(Referent)
  )

all_pav_w4 <- filter(all_wo_w4, wo == "PAV")
pav_w4 <- ggplot(all_pav_w4, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "PAV Passives Window 4") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_av_w4 <- filter(all_wo_w4, wo == "AV")
av_w4 <- ggplot(all_av_w4, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "AV Passives Window 4") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_apv_w4 <- filter(all_wo_w4, wo == "APV")
apv_w4 <- ggplot(all_apv_w4, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "APV Actives Window 4") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )


all_pv_w4 <- filter(all_wo_w4, wo == "PV")
pv_w4 <- ggplot(all_pv_w4, aes(x = time_bin, y = mean_prop, color = Referent, group = Referent)) +
  geom_line(linewidth= 1) +
  geom_ribbon(aes(ymin = lower, ymax = upper, fill = Referent), show.legend = FALSE, alpha = 0.1, linetype=2) +
  scale_color_manual("Referent", values = c("#CC3311", "#0077BB"), labels = c("Agent", "Patient")) +
  scale_fill_manual(values = c("#CC3311", "#0077BB")) +
  xlim(0, 1) + ylim(0.1, 0.9) +
  labs(x = "Relative Time", y = "Proportion of Looks", title = "PV Actives Window 4") +
  theme_minimal() + 
  theme(plot.title = element_text(hjust = 0.5),
        legend.key = element_blank(),
        text = element_text(size = 12),
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        legend.text = element_text(size = 12)
  )

##MODELS FOR FULL ACTIVES VS. FULL PASSIVES

full_w4 <- subset(data.new.w4, (data.new.w4$type == "pass"& data.new.w4$cond=="P"& data.new.w4$wo == "PAV"| data.new.w4$type == "act"& data.new.w4$cond=="none"& data.new.w4$wo == "APV"))

window4.full.ag <- brm(log.agent|weights(1/wts.agent) ~ poly(time, degree = 3) * active_voice +
                         (1 + time || agg.id:ppt.no) + 
                         (1 + time || ppt.no) +
                         (1|item),
                       data = full_w4, control=list(adapt_delta=0.99))
summary(window4.full.ag)
tab_model(window4.full.ag)

window4.full.ag %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_active_voice,
               `b_polytimedegreeEQ31:active_voice`,
               `b_polytimedegreeEQ32:active_voice`,
               `b_polytimedegreeEQ33:active_voice`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_active_voice > 0),
    mean(`b_polytimedegreeEQ31:active_voice` > 0),
    mean(`b_polytimedegreeEQ32:active_voice` > 0),
    mean(`b_polytimedegreeEQ33:active_voice` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)

window4.full.pat <- brm(log.pat|weights(1/wts.pat) ~ poly(time, degree = 3) * passive_voice +
                          (1 + time || agg.id:ppt.no) + 
                          (1 + time || ppt.no) +
                          (1|item),
                        data = full_w4, control=list(adapt_delta=0.99))


summary(window4.full.pat)
tab_model(window4.full.pat)

window4.full.pat %>%
  spread_draws(b_Intercept,
               b_polytimedegreeEQ31, 
               b_polytimedegreeEQ32,
               b_polytimedegreeEQ33,
               b_passive_voice,
               `b_polytimedegreeEQ31:passive_voice`,
               `b_polytimedegreeEQ32:passive_voice`,
               `b_polytimedegreeEQ33:passive_voice`
  ) %>% 
  summarise(
    mean(b_Intercept > 0),
    mean(b_polytimedegreeEQ31 > 0),
    mean(b_polytimedegreeEQ32 > 0),
    mean(b_polytimedegreeEQ33 > 0),
    mean(b_passive_voice > 0),
    mean(`b_polytimedegreeEQ31:passive_voice` > 0),
    mean(`b_polytimedegreeEQ32:passive_voice` > 0),
    mean(`b_polytimedegreeEQ33:passive_voice` > 0)
  ) %>% 
  gather(condition, measurement, factor_key=TRUE)



#---------------------ARRANGING GRAPHS IN PANELS
install.packages("ggpubr")
library(ggpubr)

##ALL ACTIVES AND ALL PASSIVES

#actives
act_w1 <- act_w1 + ggtitle("EEA, 100-600 ms") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

act_w2 <- act_w2 + ggtitle("Linguistic encoding I") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

act_w3 <- act_w3 + ggtitle("Linguistic encoding II") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

act_w4 <- act_w4 + ggtitle("Linguistic encoding III") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

#passives
pass_w1 <- pass_w1 + ggtitle("EEA, 100-600 ms") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

pass_w2 <- pass_w2 + ggtitle("Linguistic encoding I") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

pass_w3 <- pass_w3 + ggtitle("Linguistic encoding II") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

pass_w4 <- pass_w4 + ggtitle("Linguistic encoding III") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

first_panel <- annotate_figure(
  ggarrange(
    ggpar(act_w1), 
    ggpar(act_w2, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(act_w3, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(act_w4, ggtheme = theme(axis.title.y = element_blank())),
    ncol = 4, common.legend = TRUE, legend = "bottom"
  ),
  top = text_grob("Active sentences (n = 414)", face = "bold", size = 14)
)

second_panel <- annotate_figure(
  ggarrange(
    ggpar(pass_w1), 
    ggpar(pass_w2, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(pass_w3, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(pass_w4, ggtheme = theme(axis.title.y = element_blank())),
    ncol = 4, common.legend = TRUE, legend = "bottom"
  ),
  top = text_grob("Passive sentences (n = 168)", face = "bold", size = 14)
)


graph1 <- ggarrange(
  first_panel,
  second_panel,
  nrow = 2,
  heights = c(1, 1)  
)

#APV ACTIVES IN TOPICAL AGENT AND CONTROL CONDITIONS

#topical agent condition
aapv_w1 <- aapv_w1 + ggtitle("EEA, 100-600 ms") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

aapv_w2 <- aapv_w2 + ggtitle("Linguistic encoding I") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

aapv_w3 <- aapv_w3 + ggtitle("Linguistic encoding II") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

aapv_w4 <- aapv_w4 + ggtitle("Linguistic encoding III") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

#control condition
napv_w1 <- napv_w1 + ggtitle("EEA, 100-600 ms") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

napv_w2 <- napv_w2 + ggtitle("Linguistic encoding I") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

napv_w3 <- napv_w3 + ggtitle("Linguistic encoding II") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

napv_w4 <- napv_w4 + ggtitle("Linguistic encoding III") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

first_panel_apv <- annotate_figure(
  ggarrange(
    ggpar(aapv_w1), 
    ggpar(aapv_w2, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(aapv_w3, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(aapv_w4, ggtheme = theme(axis.title.y = element_blank())),
    ncol = 4, common.legend = TRUE, legend = "bottom"
  ),
  top = text_grob("APV actives in Topical agent condition (n = 121)", face = "bold", size = 14)
)

second_panel_apv <- annotate_figure(
  ggarrange(
    ggpar(napv_w1), 
    ggpar(napv_w2, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(napv_w3, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(napv_w4, ggtheme = theme(axis.title.y = element_blank())),
    ncol = 4, common.legend = TRUE, legend = "bottom"
  ),
  top = text_grob("APV actives in No topic (control) condition (n = 170)", face = "bold", size = 14)
)

graph2 <- ggarrange(
  first_panel_apv,
  second_panel_apv,
  nrow = 2,
  heights = c(1, 1) 
)


#APV AND PV ACTIVES

#apv actives
apv_w1 <- apv_w1 + ggtitle("EEA, 100-600 ms") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

apv_w2 <- apv_w2 + ggtitle("Linguistic encoding I") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

apv_w3 <- apv_w3 + ggtitle("Linguistic encoding II") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

apv_w4 <- apv_w4 + ggtitle("Linguistic encoding III") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

#pv actives
pv_w1 <- pv_w1 + ggtitle("EEA, 100-600 ms") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.05, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

pv_w2 <- pv_w2 + ggtitle("Linguistic encoding I") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.05, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

pv_w3 <- pv_w3 + ggtitle("Linguistic encoding II") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.05, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

pv_w4 <- pv_w4 + ggtitle("Linguistic encoding III") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.05, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

first_panel_actnodrop <- annotate_figure(
  ggarrange(
    ggpar(apv_w1), 
    ggpar(apv_w2, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(apv_w3, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(apv_w4, ggtheme = theme(axis.title.y = element_blank())),
    ncol = 4, common.legend = TRUE, legend = "bottom"
  ),
  top = text_grob("APV actives in Topical agent condition (n = 121)", face = "bold", size = 14)
)

second_panel_actdrop <- annotate_figure(
  ggarrange(
    ggpar(pv_w1), 
    ggpar(pv_w2, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(pv_w3, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(pv_w4, ggtheme = theme(axis.title.y = element_blank())),
    ncol = 4, common.legend = TRUE, legend = "bottom"
  ),
  top = text_grob("PV actives in Topical agent condition (n = 65)", face = "bold", size = 14)
)


graph3 <- ggarrange(
  first_panel_actnodrop,
  second_panel_actdrop,
  nrow = 2,
  heights = c(1, 1)  
)

#PAV AND AV PASSIVES

#pav passives
pav_w1 <- pav_w1 + ggtitle("EEA, 100-600 ms") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.05, 0.95), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

pav_w2 <- pav_w2 + ggtitle("Linguistic encoding I") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.05, 0.95), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

pav_w3 <- pav_w3 + ggtitle("Linguistic encoding II") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.05, 0.95), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

pav_w4 <- pav_w4 + ggtitle("Linguistic encoding III") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.05, 0.95), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

#av passives
av_w1 <- av_w1 + ggtitle("EEA, 100-600 ms") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

av_w2 <- av_w2 + ggtitle("Linguistic encoding I") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

av_w3 <- av_w3 + ggtitle("Linguistic encoding II") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

av_w4 <- av_w4 + ggtitle("Linguistic encoding III") + 
  theme(plot.title = element_text(size = 12)) +
  scale_y_continuous(limits = c(0.1, 0.9), breaks = seq(0.1, 0.9, 0.2)) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5))

first_panel_passnodrop <- annotate_figure(
  ggarrange(
    ggpar(pav_w1), 
    ggpar(pav_w2, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(pav_w3, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(pav_w4, ggtheme = theme(axis.title.y = element_blank())),
    ncol = 4, common.legend = TRUE, legend = "bottom"
  ),
  top = text_grob("PAV passives in Topical patient condition (n = 47)", face = "bold", size = 14)
)

second_panel_passdrop <- annotate_figure(
  ggarrange(
    ggpar(av_w1), 
    ggpar(av_w2, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(av_w3, ggtheme = theme(axis.title.y = element_blank())), 
    ggpar(av_w4, ggtheme = theme(axis.title.y = element_blank())),
    ncol = 4, common.legend = TRUE, legend = "bottom"
  ),
  top = text_grob("AV passives in Topical patient condition (n = 75)", face = "bold", size = 14)
)

graph4 <- ggarrange(
  first_panel_passnodrop,
  second_panel_passdrop,
  nrow = 2,
  heights = c(1, 1) 
)

# FULL ACTIVES AND FULL PASSIVES
graph5 <- ggarrange(
  second_panel_apv,
  first_panel_passnodrop,
  nrow = 2,
  heights = c(1, 1) 
)



