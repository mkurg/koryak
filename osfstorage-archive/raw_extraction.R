install.packages("dplyr")
install.packages("tidyr")
install.packages("intervals")
install.packages("stringr")
devtools::install_github("a-hurst/eyelinker")
library(eyelinker)
library(dplyr)

#BEFORE INDIVIDUAL SPEECH ONSET

#the following part (until "merging files") is repeated for each individual raw experimental file

dat <- read.asc("ATL_a3.asc")
letter <- "a"
raw <- dat$raw
msg <- dat$msg

pics <- subset(msg, grepl("DISPLAY_SENTENCE", msg$text)==TRUE)
pics_exp <- pics[c(7,9,12,14,17,19,22,24,27,29,32,34,38,40,43,45,48,50,53,55,58,60,63,65), ]


print(n=25, pics_exp)
nrow(pics)

behav_all <- read.csv("for_r.csv",header = TRUE,sep=",")
behav <- subset(behav_all, ppt_id == "ATL_a3")
behav$time_start <- pics_exp$time
behav$time_end <- behav$time_start + behav$sol


df = data.frame()
for (i in seq_len(nrow(behav))){
  output <- subset(raw, time >= behav[i,8] & time <= behav[i,9])
  df = rbind(df, output)
}
df$item<-as.numeric(as.factor(df$block))


behav <- subset(behav, sol <= 6500)
behav <- subset(behav, rep == "ok")
behav <- subset(behav, type != "NA")
behav$item

df_clean <- subset(df, df$item %in% behav$item == TRUE)
df_clean$item <- as.numeric(df_clean$item)
df_clean$xp <- as.numeric(df_clean$xp)
df_clean$yp <- as.numeric(df_clean$yp)
df_clean [,"who"]= "0"


for (i in seq_len(nrow(df_clean))){
  if (letter == "a"){
    if(is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 960 & df_clean[i,3] <= 1773 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 == 0){
      df_clean$who[i] <- "p"
    } else if (is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 960 & df_clean[i,3] <= 1773 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 != 0) {
      df_clean$who[i] <- "a"
    } else if (is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 147 & df_clean[i,3] <= 960 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 == 0) {
      df_clean$who[i] <- "a"
    } else if (is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 147 & df_clean[i,3] <= 960 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 != 0) {
      df_clean$who[i] <- "p"
    }
    else {
      df_clean$who[i] <- "NA"
    }
  } else {
    if(is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 960 & df_clean[i,3] <= 1773 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 == 0){
      df_clean$who[i] <- "a"
    } else if (is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 960 & df_clean[i,3] <= 1773 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 != 0) {
      df_clean$who[i] <- "p"
    } else if (is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 147 & df_clean[i,3] <= 960 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 == 0) {
      df_clean$who[i] <- "p"
    } else if (is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 147 & df_clean[i,3] <= 960 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 != 0) {
      df_clean$who[i] <- "a"
    }
    else {
      df_clean$who[i] <- "NA"
    }
  }
}

df_clean <- subset(df_clean, select = - c(input, cr.info))


df_clean [,"agent"]= "0"
df_clean[,"patient"] = "0"
for (i in seq_len(nrow(df_clean))){
  if(df_clean$who[i] == "a"){
    df_clean$agent[i] <- 1
    df_clean$patient[i] <- 0
  } else if (df_clean$who[i] == "p") {
    df_clean$agent[i] <- 0
    df_clean$patient[i] <- 1
  } else {
    df_clean$agent[i] <- 0
    df_clean$patient[i] <- 0
  }
}

df_clean[,"cond"] = "0"
for (i in seq_len(nrow(df_clean))){
  val <- df_clean$item[i]
  df_clean$cond[i] <- behav$cond[behav$item == val]
}

df_clean[,"type"] = "0"
for (i in seq_len(nrow(df_clean))){
  val1 <- df_clean$item[i]
  df_clean$type[i] <- behav$type[behav$item == val1]
}

df_clean <- df_clean %>% group_by(item) %>% mutate(ms = row_number())
df_clean <- df_clean %>% group_by(item) %>% mutate(rev_ms = rev(row_number()))
df_clean <- df_clean %>% group_by(item,time_bin50 = (ms %/% 50)) %>% mutate(a_prop_50 = sum(agent == "1")/sum(agent=="1"|agent == "0"))
df_clean <- df_clean %>% group_by(item,time_bin50 = (ms %/% 50)) %>% mutate(p_prop_50 = sum(patient == "1")/sum(patient=="1"|patient == "0"))
df_clean <- df_clean %>% group_by(item,time_bin20 = (ms %/% 20)) %>% mutate(a_prop_20 = sum(agent == "1")/sum(agent=="1"|agent == "0"))
df_clean <- df_clean %>% group_by(item,time_bin20 = (ms %/% 20)) %>% mutate(p_prop_20 = sum(patient == "1")/sum(patient=="1"|patient == "0"))
df_clean <- df_clean %>% group_by(item,time_bin50_neg = (rev_ms %/% 50)) %>% mutate(a_prop_50n = sum(agent == "1")/sum(agent=="1"|agent == "0"))
df_clean <- df_clean %>% group_by(item,time_bin50_neg = (rev_ms %/% 50)) %>% mutate(p_prop_50n = sum(patient == "1")/sum(patient=="1"|patient == "0"))
df_clean <- df_clean %>% group_by(item,time_bin20_neg = (rev_ms %/% 20)) %>% mutate(a_prop_20n = sum(agent == "1")/sum(agent=="1"|agent == "0"))
df_clean <- df_clean %>% group_by(item,time_bin20_neg = (rev_ms %/% 20)) %>% mutate(p_prop_20n = sum(patient == "1")/sum(patient=="1"|patient == "0"))
merged <- merge(df_clean,behav,by = c("item","type","cond"))
merged[,"tw"]= "i"
merged$ms <- as.numeric(merged$ms)
merged$sol <- as.numeric(merged$sol)
for (i in seq_len(nrow(merged))){
  if(merged$ms[i] <= 100){
    merged$tw[i] <- "0"
  }
  else if (merged$ms[i] > 100 & merged$ms[i] <= 600){
    merged$tw[i] <- "1"
  }
  else if (merged$ms[i] <= 600 + 0.5*(merged$sol[i]-600)){
    merged$tw[i] <- "2"
  }
  else {
    merged$tw[i] <- "3"
  }
}
merged <- merged %>% arrange(item)

#change for every new participant
merged[,"ppt.no"]= "1"

write.csv(merged, "C:/Users/guppy/Documents/preonset/ATL_a3_pre.csv", row.names=FALSE)


#merging files

setwd("C:/Users/guppy/Documents/preonset/")
all_files <- list.files("C:/Users/guppy/Documents/preonset/", pattern="*pre.csv")
data_all <- NULL  
for (i in seq(all_files)) {
  temp <- read.csv(all_files[i], header = TRUE,sep=",")
  data_all <- rbind(data_all, temp) 
}
data_all <- write.csv(data_all,"C:/Users/guppy/Documents/preonset/data_all.csv", row.names = FALSE)


#AFTER INDIVIDUAL SPEECH ONSET
#the following part (until "merging files") is repeated for each individual raw experimental file

dat <- read.asc("ATL_b2.asc")
letter <- "b"
raw <- dat$raw
msg <- dat$msg

pics <- subset(msg, grepl("DISPLAY_SENTENCE", msg$text)==TRUE)
pics_exp <- pics[c(7,9,12,14,17,19,22,24,27,29,32,34,38,40,43,45,48,50,53,55,58,60,63,65), ]

print(n=25, pics_exp)
nrow(pics)

behav_all <- read.csv("for_r.csv",header = TRUE,sep=",")
behav <- subset(behav_all, ppt_id == "ATL_b2")
behav$time_start <- pics_exp$time
behav$time_end <- behav$time_start + behav$sol
class(behav$time_end)

df = data.frame()
for (i in seq_len(nrow(behav))){
  output <- subset(raw, time >= behav[i,9] & time <= (behav[i,9]+2000))
  df = rbind(df, output)
}
df$item<-as.numeric(as.factor(df$block))


behav <- subset(behav, sol <= 6500)
behav <- subset(behav, rep == "ok")
behav <- subset(behav, type != "NA")
behav$item

df_clean <- subset(df, df$item %in% behav$item == TRUE)
df_clean$item <- as.numeric(df_clean$item)
df_clean$xp <- as.numeric(df_clean$xp)
df_clean$yp <- as.numeric(df_clean$yp)
df_clean [,"who"]= "0"


for (i in seq_len(nrow(df_clean))){
  if (letter == "a"){
    if(is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 960 & df_clean[i,3] <= 1773 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 == 0){
      df_clean$who[i] <- "p"
    } else if (is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 960 & df_clean[i,3] <= 1773 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 != 0) {
      df_clean$who[i] <- "a"
    } else if (is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 147 & df_clean[i,3] <= 960 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 == 0) {
      df_clean$who[i] <- "a"
    } else if (is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 147 & df_clean[i,3] <= 960 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 != 0) {
      df_clean$who[i] <- "p"
    }
    else {
      df_clean$who[i] <- "NA"
    }
  } else {
    if(is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 960 & df_clean[i,3] <= 1773 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 == 0){
      df_clean$who[i] <- "a"
    } else if (is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 960 & df_clean[i,3] <= 1773 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 != 0) {
      df_clean$who[i] <- "p"
    } else if (is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 147 & df_clean[i,3] <= 960 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 == 0) {
      df_clean$who[i] <- "p"
    } else if (is.na(df_clean[i,3]) == FALSE & is.na(df_clean[i,4]) == FALSE & df_clean[i,3] >= 147 & df_clean[i,3] <= 960 & df_clean[i,4] >= 122 & df_clean[i,4] <= 1039 & df_clean[i,8] %% 2 != 0) {
      df_clean$who[i] <- "a"
    }
    else {
      df_clean$who[i] <- "NA"
    }
  }
}
print(df_clean, n=100)

df_clean <- subset(df_clean, select = - c(input, cr.info))


df_clean [,"agent"]= "0"
df_clean[,"patient"] = "0"
for (i in seq_len(nrow(df_clean))){
  if(df_clean$who[i] == "a"){
    df_clean$agent[i] <- 1
    df_clean$patient[i] <- 0
  } else if (df_clean$who[i] == "p") {
    df_clean$agent[i] <- 0
    df_clean$patient[i] <- 1
  } else {
    df_clean$agent[i] <- 0
    df_clean$patient[i] <- 0
  }
}

df_clean[,"cond"] = "0"
for (i in seq_len(nrow(df_clean))){
  val <- df_clean$item[i]
  df_clean$cond[i] <- behav$cond[behav$item == val]
}

df_clean[,"type"] = "0"
for (i in seq_len(nrow(df_clean))){
  val1 <- df_clean$item[i]
  df_clean$type[i] <- behav$type[behav$item == val1]
}

df_clean <- df_clean %>% group_by(item) %>% mutate(ms = row_number())
df_clean <- df_clean %>% group_by(item,time_bin50 = (ms %/% 50)) %>% mutate(a_prop_50 = sum(agent == "1")/sum(agent=="1"|agent == "0"))
df_clean <- df_clean %>% group_by(item,time_bin50 = (ms %/% 50)) %>% mutate(p_prop_50 = sum(patient == "1")/sum(patient=="1"|patient == "0"))
df_clean <- df_clean %>% group_by(item,time_bin20 = (ms %/% 20)) %>% mutate(a_prop_20 = sum(agent == "1")/sum(agent=="1"|agent == "0"))
df_clean <- df_clean %>% group_by(item,time_bin20 = (ms %/% 20)) %>% mutate(p_prop_20 = sum(patient == "1")/sum(patient=="1"|patient == "0"))
merged <- merge(df_clean,behav,by = c("item","type","cond"))


merged[,"ppt.no"]= "1"

write.csv(merged, "C:/Users/guppy/Documents/postonset/ATL_b2_po.csv", row.names=FALSE)


#merging files 

setwd("C:/Users/guppy/Documents/postonset/")
all_files_po <- list.files("C:/Users/guppy/Documents/postonset/", pattern="*po.csv")

data_all_po <- NULL  
for (i in seq(all_files_po)) {
  temp <- read.csv(all_files_po[i], header = TRUE,sep=",")
  data_all_po <- rbind(data_all_po, temp) 
}

data_all_po <- write.csv(data_all_po,"C:/Users/guppy/Documents/postonset/data_all_po.csv", row.names = FALSE)



