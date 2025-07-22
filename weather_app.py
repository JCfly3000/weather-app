import pandas as pd
import streamlit as st
from great_tables import GT, loc, style
import plotly.express as px

st.set_page_config(layout="wide")

# Load the data
@st.cache_data
def load_data():
    return pd.read_csv("weather_data.csv")

weather_df = load_data()

weather_df=weather_df.drop(columns=["lat", "lon","forecast_flag","weather_code"])

# City selection
cities = weather_df["City"].unique()
selected_city = st.selectbox("Select a city", cities)

# Filter data for the selected city
city_df = weather_df[weather_df["City"] == selected_city].reset_index(drop=True)

@st.cache_data
def convert_df_to_csv(df):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_csv(index=False).encode("utf-8")


csv = convert_df_to_csv(city_df)

st.download_button(
    label="Download Weather Data (CSV)",
    data=csv,
    file_name=f"{selected_city}_weather_data.csv",
    mime="text/csv",
)


# Display the Plotly chart
st.header("Temperature Trend")
fig = px.line(city_df, x="date", y=["temperature_max", "temperature_min"], 
              labels={"value": "Temperature (°C)", "variable": "Temperature Type"},
              title="Max and Min Daily Temperatures")
st.plotly_chart(fig, use_container_width=True)



# Display the Great Table
st.header(f"Weather Forecast for {selected_city}")

gt = GT(city_df)

gt = gt.tab_header(
    title=f"{selected_city}",
    subtitle=f"Weather from {pd.to_datetime(city_df['date'].min()).strftime('%B %d')} to {pd.to_datetime(city_df['date'].max()).strftime('%B %d, %Y')}"
)

# Color AQI status
aqi_colors = {
    "Good": "#90EE90",
    "Moderate": "#FFFF00",
    "Unhealthy for Sensitive Groups": "#FFA500",
    "Unhealthy": "#FF0000",
    "Very Unhealthy": "#800080",
    "Hazardous": "#808080"
}

for status, color in aqi_colors.items():
    gt = gt.tab_style(
        style=style.fill(color=color),
        locations=loc.body(
            columns="us_aqi_status",
            rows=lambda df: df["us_aqi_status"] == status
        )
    )


gt = gt.data_color(
    columns=["rain_prob"],
    domain=[50, 100],
    palette=["#ffcdd2", "#f44336"],
    na_color="#FFFFFF00"
)

gt = gt.fmt_number(columns=["temperature_max", "temperature_min", "pm2_5", "us_aqi"], decimals=1)
gt = gt.fmt_percent(columns=["rain_prob"], scale_values=False, decimals=0)

gt = gt.cols_label(
    date="Date",
    day="Day",
    temperature_max="Max Temp (°C)",
    temperature_min="Min Temp (°C)",
    weather="Weather",
    rain_prob="Rain Probability",
    pm2_5="PM2.5",
    us_aqi="US AQI",
    us_aqi_status="AQI Status"
).cols_hide(columns="City")


st.html(gt._repr_html_())

