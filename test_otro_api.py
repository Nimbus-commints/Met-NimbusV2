import streamlit as st
import pydeck as pdk
import pandas as pd
import requests
import json
import plotly.express as px
import os
from dotenv import load_dotenv
from datetime import datetime


def get_weather_datav2(lat, lon):
    ulr = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["temperature_2m", "precipitation", "relative_humidity_2m"],
        "current": ["temperature_2m", "wind_speed_10m", "relative_humidity_2m"],
        "timezone": "America/Lima",
        "wind_speed_unit": "ms",
    }
    try:
        response = requests.get(ulr, params=params)
        # response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error("⚠️ Error: La API tardó demasiado en responder. Intenta nuevamente.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error de conexión: {str(e)}")
        return None
    except ValueError:
        st.error("❌ Error: Respuesta inválida de la API")
        return None


data = get_weather_datav2(-12.090113234999933, -76.92269610276367)
# print(data)
# print(
#     datetime.strptime(data["current"]["time"], "%Y-%m-%dT%H:%M"),
# )

pronosticos = pd.DataFrame(
    {
        "fecha": data["hourly"]["time"],
        "temp": data["hourly"]["temperature_2m"],
    }
)
fig_temp = px.line(
    pronosticos,
    x="fecha",
    y="temp",
    markers=True,
    # title=f"Pronóstico de Temperatura - {selected_city}",
    # labels={"Temp (°C)": "Temperatura (°C)", "Tiempo": "Fecha y Hora"},
)

st.plotly_chart(fig_temp, use_container_width=True)
# print(pronosticos)
# print(pd.DataFrame([{"hora": "hora1", "temp": 20}]))
