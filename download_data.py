import pandas as pd
import requests
from datetime import date, timedelta
import concurrent.futures

def generate_weather_data(city_name, lat, lon):
    """
    Fetches weather and air quality data for a given city.
    """
    # 1. Define Date Range
    today = date.today()
    start_date = today - timedelta(days=7)
    end_date = today + timedelta(days=7)

    # 2. Fetch Weather and Rain Probability Data
    weather_df = None
    try:
        weather_url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_mean",
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "timezone": "auto"
        }
        resp_weather = requests.get(weather_url, params=params)
        resp_weather.raise_for_status()
        weather_data_raw = resp_weather.json()
        
        weather_df = pd.DataFrame(weather_data_raw['daily'])
        weather_df = weather_df.rename(columns={
            "time": "date",
            "temperature_2m_max": "temperature_max",
            "temperature_2m_min": "temperature_min",
            "precipitation_probability_mean": "rain_prob"
        })
        weather_df['date'] = pd.to_datetime(weather_df['date'])
        weather_df['day'] = weather_df['date'].dt.strftime('%a')

        weather_mapping = {
            0: "Clear", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
            45: "Fog", 48: "Rime Fog", 51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
            56: "Light Freezing Drizzle", 57: "Freezing Drizzle", 61: "Light Rain", 63: "Rain",
            65: "Heavy Rain", 66: "Light Freezing Rain", 67: "Freezing Rain", 71: "Light Snow",
            73: "Snow", 75: "Heavy Snow", 77: "Snow Grains", 80: "Light Showers", 81: "Showers",
            82: "Heavy Showers", 85: "Light Snow Showers", 86: "Snow Showers", 95: "Thunderstorm",
            96: "Thunderstorm with Hail", 99: "Heavy Thunderstorm with Hail"
        }
        weather_df['weather'] = weather_df['weather_code'].map(weather_mapping)

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch weather data for {city_name}: {e}")
        return None

    # 3. Fetch Air Quality Data
    aqi_df = None
    try:
        aqi_start_date = today - timedelta(days=7)
        aqi_end_date = today
        aqi_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": aqi_start_date.strftime("%Y-%m-%d"),
            "end_date": aqi_end_date.strftime("%Y-%m-%d"),
            "hourly": "pm2_5,us_aqi",
            "timezone": "auto"
        }
        resp_aqi = requests.get(aqi_url, params=params)
        resp_aqi.raise_for_status()
        aqi_data_raw = resp_aqi.json()
        
        if 'hourly' in aqi_data_raw:
            aqi_df = pd.DataFrame(aqi_data_raw['hourly'])
            aqi_df['date'] = pd.to_datetime(aqi_df['time']).dt.date
            aqi_df = aqi_df.groupby('date').agg(
                pm2_5=('pm2_5', 'median'),
                us_aqi=('us_aqi', 'median')
            ).reset_index()
            aqi_df['date'] = pd.to_datetime(aqi_df['date'])


    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch AQI data for {city_name}: {e}")

    # 4. Combine and Process Data
    combined_df = weather_df
    if aqi_df is not None:
        combined_df = pd.merge(combined_df, aqi_df, on="date", how="left")

    combined_df['City'] = city_name
    combined_df['lat'] = lat
    combined_df['lon'] = lon
    combined_df['forecast_flag'] = combined_df['date'].apply(lambda x: 'forecast' if x.date() > today else 'current')
    
    def get_aqi_status(us_aqi):
        if pd.isna(us_aqi):
            return "N/A"
        if us_aqi <= 50:
            return "Good"
        if us_aqi <= 100:
            return "Moderate"
        if us_aqi <= 150:
            return "Unhealthy for Sensitive Groups"
        if us_aqi <= 200:
            return "Unhealthy"
        if us_aqi <= 300:
            return "Very Unhealthy"
        return "Hazardous"

    if 'us_aqi' in combined_df.columns:
        combined_df['us_aqi_status'] = combined_df['us_aqi'].apply(get_aqi_status)
    else:
        combined_df['us_aqi_status'] = "N/A"
        combined_df['pm2_5'] = None
        combined_df['us_aqi'] = None


    return combined_df

def main():
    cities = {
        "Shenzhen": (22.5431, 114.0579),
        "Bangkok": (13.7563, 100.5018),
        "Tokyo": (35.6895, 139.6917),
        "Seoul": (37.5665, 126.9780),
        "London": (51.5074, -0.1278),
        "New York": (40.7128, -74.0060),
        "Los Angeles": (34.0522, -118.2437),
        "Paris": (48.8566, 2.3522),
        "Beijing": (39.9042, 116.4074)
    }

    all_data = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_city = {executor.submit(generate_weather_data, city, lat, lon): city for city, (lat, lon) in cities.items()}
        for future in concurrent.futures.as_completed(future_to_city):
            city = future_to_city[future]
            try:
                city_data = future.result()
                if city_data is not None:
                    all_data.append(city_data)
            except Exception as exc:
                print(f'{city} generated an exception: {exc}')

    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        final_df.to_csv("weather_data.csv", index=False)
        print("Data downloaded and saved to weather_data.csv")

main()