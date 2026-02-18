import streamlit as st
import pydeck as pdk
import pandas as pd
import requests
import json
import plotly.express as px
import os
import concurrent.futures
from datetime import datetime
from dotenv import load_dotenv
import time

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
st.set_page_config(
    layout="wide", page_title="Red Nimbus - Weather Dashboard", page_icon="nimbu.ico"
)
load_dotenv()


# ---------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------
def parse_time(time_str):
    """Parse time string with multiple possible formats."""
    formats = ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"]
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse time: {time_str}")


# ---------------------------------------------------
# LOAD GEOJSON
# ---------------------------------------------------
@st.cache_data
def load_map_data():
    with open("lima_districtsv2.geojson") as f:
        return json.load(f)


geojson = load_map_data()


## NUEVA FUNCION PARA OBTENER DATOS DE CADA DISTRITO
def get_single_district_weather(feature):
    """Funcion que sera ejecutada en paralelo para cada distrito"""
    time.sleep(0.3)
    props = feature["properties"]
    lat, lon = props["lat"], props["lon"]
    name = props["DISTRITO"]

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["temperature_2m", "precipitation", "relative_humidity_2m"],
        "current": ["temperature_2m", "wind_speed_10m", "relative_humidity_2m"],
        "timezone": "America/Lima",
        "wind_speed_unit": "ms",
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        return {
            "name": name,
            "temperature": data["current"]["temperature_2m"],
            "humidity": data["current"]["relative_humidity_2m"],
            "wind": data["current"]["wind_speed_10m"],
            "time": data["current"]["time"],
            "pronostico": data["hourly"],
            # "pronostico_tiempo": data["hourly"]["time"],
            # agregar para humedad y precipitacion luego
        }
    except Exception as e:
        print(f"Error al obtener datos para {name}: {e}")
        return {
            "name": name,
            "temperature": 20,
            "humidity": 70,
            "wind": 5,
            "time": datetime.now().isoformat(),
            "pronostico": {
                "time": [],
                "temperature_2m": [],
                "precipitation": [],
            },
        }


# Usamos session_state para que una ves cargado no se repita al interactuar con el mapa
if "master_df" not in st.session_state:
    with st.status(
        "📡 Sincronizando datos de distritos en tiempo real...", expanded=True
    ) as status:
        st.write("Iniciando peticiones paralelas a la API...")

        # Se ejecuta las peticiones en paralelo (15 hilos a la vez)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            weahter_results = list(
                executor.map(get_single_district_weather, geojson["features"])
            )
        st.write("Procesando geometrias y capas 3D...")
        weather_map = {res["name"]: res for res in weahter_results}
        district_data = []
        text_data = []
        pronosticos_data = []

        for feature in geojson["features"]:
            props = feature["properties"]
            w = weather_map.get(props["DISTRITO"])

            props["temperature"] = w["temperature"]
            props["humidity"] = w["humidity"]
            props["wind"] = w["wind"]
            fecha_obj = datetime.fromisoformat(w["time"])
            props["fecha"] = fecha_obj.strftime("%d-%m-%Y %H:%M")
            props["elevation"] = w["temperature"] * 150

            district_data.append(
                {
                    "District": props["DISTRITO"],
                    "Fecha": parse_time(w["time"]),
                    "Temperature": w["temperature"],
                    "Humidity": w["humidity"],
                    "Wind": w["wind"],
                }
            )
            text_data.append(
                {
                    "position": [props["lon"], props["lat"], props["elevation"] + 100],
                    "text": props["DISTRITO"],
                }
            )
            for t, temp, pp in zip(
                w["pronostico"]["time"],
                w["pronostico"]["temperature_2m"],
                w["pronostico"]["precipitation"],
            ):
                pronosticos_data.append(
                    {
                        "District": props["DISTRITO"],
                        "lat": props["lat"],
                        "lon": props["lon"],
                        "Fechas": parse_time(t),
                        "Temperature": temp,
                        "Precipitation": pp,
                    }
                )

        st.session_state.master_df = pd.DataFrame(district_data)
        st.session_state.enriched_geojson = geojson
        st.session_state.text_layer_data = text_data
        st.session_state.pronosticos_df = pd.DataFrame(pronosticos_data)
        status.update(
            label="✅ Datos cargados correctamente", state="complete", expanded=False
        )

# Recuperamos datos de la sesión
df = st.session_state.master_df
geojson = st.session_state.enriched_geojson
text_data = st.session_state.text_layer_data
pronosticos = st.session_state.pronosticos_df

# COMIENZO DE LA APLICACION
if "zoom" not in st.session_state:
    st.session_state.zoom = 9

fecha = df["Fecha"].iloc[0]
col1, col2 = st.columns([1, 2])
with col1:
    st.title("LIMA")
    st.subheader("Mapa de Temperatura 3D")
with col2:
    st.title("Última actualización:")
    st.subheader(
        f"FECHA: {fecha.strftime('%d-%m-%Y')} | HORA: {fecha.strftime('%H:%M')}"
    )
    # st.subheader(f"HORA: {fecha.strftime('%H:%M')}")
# ---------------------------------------------------
# 3D MAP
# ---------------------------------------------------
view_state = pdk.ViewState(
    latitude=-12.0464,
    longitude=-77.0428,
    zoom=st.session_state.zoom,
    pitch=45,
)

layer_geo = pdk.Layer(
    "GeoJsonLayer",
    geojson,
    pickable=True,
    filled=True,
    get_fill_color="[properties.temperature * 10, 120 - properties.temperature, 255 - properties.temperature * 8]",
    getLineColor="[0, 0, 0]",
    lineWidthMinPixels=3,
    # 3D
    extruded=True,
    get_elevation="properties.elevation",
    wireframe=True,
    transitions={"get_elevation": 1000},
)


# Ajusta el tamaño según el

text_layer = pdk.Layer(
    "TextLayer",
    text_data,
    pickable=False,
    get_position="position",
    get_text="text",
    sizeMaxPixels=10,
    get_color="[255, 255, 255]",  # Ajusta la opacidad según el zoom
    background=True,
    get_background_color="[0, 0, 0, 180]",
    backgroundBorderRadius=3,
    backgroundPadding=[2, 2],
    get_alignment_baseline="'bottom'",
    get_text_anchor="'middle'",
    billboard=True,
    get_size=16,
    size_min_pixels=6,
)

deck = pdk.Deck(
    layers=[layer_geo, text_layer],
    initial_view_state=view_state,
    # map_style="mapbox://styles/mapbox/dark-v10",
    tooltip={
        "html": "<b>{DISTRITO}</b><br/>"
        "Fecha: {fecha}<br/>"
        "Temp: {temperature}°C<br/>"
        "Humedad: {humidity}%<br/>"
        "Viento: {wind} m/s",
        "style": {
            "backgroundColor": "black",
            "color": "white",
            "borderRadius": "5px",
            "padding": "10px",
        },
    },
)

st.pydeck_chart(deck)

st.markdown("### 📊 Análisis Comparativo")
col_sel, col_graph = st.columns([1, 2])

with col_sel:
    target_districts = st.multiselect(
        "Selecciona distritos para comparar:",
        df["District"].unique(),
        default=df["District"].iloc[:3],
    )

    filtered_df = df[df["District"].isin(target_districts)]

# fecha = df["Fecha"].iloc[0]
with col_graph:
    if not filtered_df.empty:
        fig = px.bar(
            filtered_df,
            x="District",
            y="Temperature",
            color="Temperature",
            labels={"Temperature": "Temperatura (°C)", "District": "Distritos"},
            # layout={
            #     "title": {
            #         "text": f"TEMPERATURA POR DISTRITOS SELECCIONADOS",
            #         "subtitle": f"FECHA: {fecha}",
            #     }
            # },
            title=f"TEMPERATURA POR DISTRITOS SELECCIONADOS",
            subtitle=f"FECHA: {fecha}",
            color_continuous_scale="Viridis",
        )
        # fig.update_layout(title_x=0.3)
        fig.update_layout(hovermode="x unified", height=500)
        st.plotly_chart(fig, width="stretch")


st.markdown("### 🚨 Monitor de Alertas")
hot_districts = (
    df[df["Temperature"] > 24]["District"].sort_values(ascending=False).tolist()
)
windy_districts = df[df["Wind"] > 7]["District"].tolist()

c1, c2 = st.columns(2)
with c1:
    if hot_districts:
        st.warning(f"🌡️ **Temperatura elevada (> 24°C):** {', '.join(hot_districts)}")
with c2:
    if windy_districts:
        st.error(f"🌬️ **Vientos fuertes (> 7 m/s):** {', '.join(windy_districts)}")


# ---------------------------------------------------
# DATA PRONOSTICADA TEMPERATURA, AGREGAR LUEGO HUMEDAD
st.markdown("### PRONOSTICOS")
st.subheader("📈 Próximos 7 días")
col_sel_forecast, col_graph_forecast = st.columns([1, 2])

with col_sel_forecast:
    selected_districts_forecast = st.multiselect(
        "Selecciona distritos para pronóstico:",
        pronosticos["District"].unique(),
        default=pronosticos["District"].unique()[:3],
        key="forecast_selector",
    )
    filtered_forecast = pronosticos[
        pronosticos["District"].isin(selected_districts_forecast)
    ]

tab1, tab2 = st.tabs(["📈 Temperatura", "☔ Precipitación"])


with col_graph_forecast:
    with tab1:
        if not filtered_forecast.empty:
            fig_temp = px.line(
                filtered_forecast,
                x="Fechas",
                y="Temperature",
                color="District",
                title=f"Pronóstico de Temperatura",
                labels={
                    "Temperature": "Temperatura (°C)",
                    "Fechas": "Fecha y Hora",
                    "District": "Distrito",
                },
            )
            fig_temp.update_layout(hovermode="x unified", height=500)
            st.plotly_chart(fig_temp, width="stretch")
        else:
            st.info("Selecciona al menos un distrito para mostrar el pronóstico.")
    with tab2:
        if not filtered_forecast.empty:
            fig_precip = px.bar(
                filtered_forecast,
                x="Fechas",
                y="Precipitation",
                color="District",
                title=f"Pronóstico de Precipitación",
                labels={
                    "Precipitation": "Precipitación (mm)",
                    "Fechas": "Fecha y Hora",
                    "District": "Distrito",
                },
                color_continuous_scale="Blues",
            )
            fig_precip.update_layout(hovermode="x unified", height=500)
            st.plotly_chart(fig_precip, width="stretch")
        else:
            st.info("Selecciona al menos un distrito para mostrar el pronóstico.")

# ---------------------------------------------------
# FOOTER
# ---------------------------------------------------

st.markdown("---")
st.caption(
    "Datos obtenidos de la API Open-meteo | Actualizado cada 15 minutos | Hecho por Red Nimbus"
)
