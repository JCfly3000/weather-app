
# create a website using python and streamlit(https://github.com/streamlit/streamlit)

## 1 using uv to set up a virtual environment  with python version 3.13 with uv init and uv add needed packages

## 2 create a python file called download_data.py 

### learning from following R code 

generate_weather_data <- function(city_name, lat, lon) {
  
  # --- 1. Define Date Range ---
  today <- Sys.Date()
  start_date <- today - days(7)
  end_date <- today + days(7)
  
  # --- 2. Fetch Weather and Rain Probability Data ---
  weather_df <- NULL
  tryCatch({
    weather_url <- "https://api.open-meteo.com/v1/forecast"
    req_weather <- request(weather_url) %>%
      req_url_query(
        latitude = lat,
        longitude = lon,
        daily = c("weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_probability_mean"),
        start_date = start_date,
        end_date = end_date,
        timezone = "auto",
        .multi = "comma"
      )
    
    resp_weather <- req_weather %>% req_perform()
    weather_data_raw <- resp_weather %>% resp_body_json()
    
    weather_df <- as_tibble(weather_data_raw$daily) %>%
      unnest(cols = c(time, weather_code, temperature_2m_max, temperature_2m_min, precipitation_probability_mean)) %>%
      rename(
        date = time,
        temperature_max = temperature_2m_max,
        temperature_min = temperature_2m_min,
        rain_prob = precipitation_probability_mean
      ) %>%
      mutate(date = as.Date(date),
             day = format(date, "%a"))
      
    weather_mapping <- c(
      `0` = "Clear", `1` = "Mainly Clear", `2` = "Partly Cloudy", `3` = "Overcast",
      `45` = "Fog", `48` = "Rime Fog", `51` = "Light Drizzle", `53` = "Drizzle", `55` = "Heavy Drizzle",
      `56` = "Light Freezing Drizzle", `57` = "Freezing Drizzle", `61` = "Light Rain", `63` = "Rain",
      `65` = "Heavy Rain", `66` = "Light Freezing Rain", `67` = "Freezing Rain", `71` = "Light Snow",
      `73` = "Snow", `75` = "Heavy Snow", `77` = "Snow Grains", `80` = "Light Showers", `81` = "Showers",
      `82` = "Heavy Showers", `85` = "Light Snow Showers", `86` = "Snow Showers", `95` = "Thunderstorm",
      `96` = "Thunderstorm with Hail", `99` = "Heavy Thunderstorm with Hail"
    )
    
    weather_df <- weather_df %>%
      mutate(weather = weather_mapping[as.character(weather_code)])

  }, error = function(e) {
    message(paste("Failed to fetch weather data for", city_name, ":", e$message))
    return(NULL)
  })
  
  if (is.null(weather_df)) {
    return(NULL)
  }
  
  # --- 3. Fetch Air Quality Data ---
  aqi_df <- NULL
  tryCatch({
    aqi_start_date <- today - days(7)
    aqi_end_date <- today
    aqi_url <- "https://air-quality-api.open-meteo.com/v1/air-quality"
    req_aqi <- request(aqi_url) %>%
      req_url_query(
        latitude = lat,
        longitude = lon,
        start_date = aqi_start_date,
        end_date = aqi_end_date,
        hourly = c("pm2_5", "us_aqi"),
        timezone = "auto",
        .multi = "comma"
      )
    
    resp_aqi <- req_aqi %>% req_perform()
    aqi_data_raw <- resp_aqi %>% resp_body_json()
    
    aqi_df <- as_tibble(aqi_data_raw$hourly) %>%
      unnest(cols = c(time, pm2_5, us_aqi)) %>%
      mutate(date = as.Date(time)) %>%
      group_by(date) %>%
      summarise(
        pm2_5 = median(pm2_5, na.rm = TRUE),
        us_aqi = median(us_aqi, na.rm = TRUE)
      )
  }, error = function(e) {
    message(paste("Failed to fetch AQI data for", city_name, ":", e$message))
  })

  # --- 4. Combine and Process Data ---
  combined_df <- weather_df
  if (!is.null(aqi_df)) {
    combined_df <- left_join(combined_df, aqi_df, by = "date")
  }

  combined_df <- combined_df %>%
    mutate(
      City = city_name,
      lat = lat,
      lon = lon,
      forcast_flag = if_else(date > today, "forecast", "current"),
      us_aqi_status = case_when(
        us_aqi <= 50 ~ "Good",
        us_aqi <= 100 ~ "Moderate",
        us_aqi <= 150 ~ "Unhealthy for Sensitive Groups",
        us_aqi <= 200 ~ "Unhealthy",
        us_aqi <= 300 ~ "Very Unhealthy",
        us_aqi > 300 ~ "Hazardous",
        TRUE ~ "N/A"
      )
    )
  
  return(combined_df)
}



display_gt <- function(combined_df) {
  #combined_df=shenzhen_data
  city_name <- combined_df$City[1]
  start_date <- min(combined_df$date)
  end_date <- max(combined_df$date)
  
  gt_table <- combined_df %>%
    select(date, day, temperature_max, temperature_min, weather, rain_prob,pm2_5, us_aqi, us_aqi_status) %>%
    gt() %>%
    tab_options(table.width = pct(100)) %>%
    tab_header(
      title = city_name,
      subtitle = md(paste("**", format(start_date, "%B %d"), "to", format(end_date, "%B %d, %Y"), "**"))
    ) %>%
    data_color(
      columns = us_aqi_status,
      fn = function(x) {
        case_when(
          x == "Good" ~ "#90EE90",
          x == "Moderate" ~ "#FFFF00",
          x == "Unhealthy for Sensitive Groups" ~ "#FFA500",
          x == "Unhealthy" ~ "#FF0000",
          x == "Very Unhealthy" ~ "#800080",
          x == "Hazardous" ~ "#808080",
          TRUE ~ "#FFFFFF"
        )
      }
    ) %>%
    data_color(
      columns = rain_prob,
      fn = function(x) {
        # Handle NA values by replacing them with 0, which won't be colored.
        x[is.na(x)] <- 0
        
        # Squish values to the 0-100 range to handle probabilities > 100% if they appear
        x_squished <- scales::squish(x, range = c(0, 100))
        
        # Create a palette function. Values outside the domain will be NA.
        color_palette <- scales::col_numeric(
          palette = c("#ffcdd2", "#f44336"),
          domain = c(50, 100),
          na.color = "#FFFFFF00" # Use transparent for values outside domain (i.e., <= 50)
        )
        
        # Apply the palette.
        color_palette(x_squished)
      }
    ) %>%
    fmt_number(columns = where(is.numeric), decimals = 1) %>%
    fmt_percent(
      columns = rain_prob,
      scale_values = FALSE,
      decimals = 0
    ) %>%
    cols_label(
      date = "Date",
      day = "Day",
      temperature_max = "Max Temp (°C)",
      temperature_min = "Min Temp (°C)",
      weather = "Weather",
      rain_prob="Rain Probability",
      pm2_5 = "PM2.5",
      us_aqi = "US AQI",
      us_aqi_status = "AQI Status"
    )
  
  gt_table
}



### download data from using https://air-quality-api.open-meteo.com 

#### include city: Shenzhen, Bangkok,Tokyo,Seoul,London,New York,Los Angeles,Paris,Beijing

#### date include past 7 days and future 7 days

#### pandas dataframe with column date,day of week,temperature,weather,pm2_5

### save the dataframe to a csv file



## 3 create a streamlit app  into weather_app.py

### have a dropdown to select city

### include a gt table(https://github.com/posit-dev/great-tables) with the data

### inlcude a plotly(https://github.com/plotly/plotly.py) temperature line chart

