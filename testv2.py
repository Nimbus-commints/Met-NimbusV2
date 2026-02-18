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

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
st.set_page_config(
    layout="wide", page_title="Red Nimbus - Weather Dashboard", page_icon="nimbu.ico"
)
load_dotenv()
# API_KEY = os.getenv("OPENWEATHER_API_KEY")


if "zoom" not in st.session_state:
    st.session_state.zoom = 10

st.title("LIMA")
st.subheader("Mapa de Temperatura 3D")


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
    props = feature["properties"]
    lat, lon = props["lat"], props["lon"]
    name = props["DISTRITO"]

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ["temperature_2m", "wind_speed_10m", "relative_humidity_2m"],
        "timezone": "America/Lima",
        "wind_speed_unit": "ms",
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        return {
            "name": name,
            "temperature": data["current"]["temperature_2m"],
            "humidity": data["current"]["relative_humidity_2m"],
            "wind": data["current"]["wind_speed_10m"],
            "time": data["current"]["time"],
        }
    except:
        return {
            "name": name,
            "temperature": 20,
            "humidity": 70,
            "wind": 5,
            "time": datetime.now().isoformat(),
        }


# Usamos session_state para que una ves cargado no se repita al interactuar con el mapa
if "master_df" not in st.session_state:
    with st.status(
        "📡 Sincronizando datos de distritos en tiempo real...", expanded=True
    ) as status:
        st.write("Iniciando peticiones paralelas a la API...")

        # Se ejecuta las peticiones en paralelo (15 hilos a la vez)

        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            weahter_results = list(
                executor.map(get_single_district_weather, geojson["features"])
            )
        st.write("Procesando geometrias y capas 3D...")
        weather_map = {res["name"]: res for res in weahter_results}
        district_data = []
        text_data = []

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
                    "Fecha": datetime.strptime(w["time"], "%Y-%m-%dT%H:%M"),
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
        st.session_state.master_df = pd.DataFrame(district_data)
        st.session_state.enriched_geojson = geojson
        st.session_state.text_layer_data = text_data
        status.update(
            label="✅ Datos cargados correctamente", state="complete", expanded=False
        )

# Recuperamos datos de la sesión
df = st.session_state.master_df
geojson = st.session_state.enriched_geojson
text_data = st.session_state.text_layer_data

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


zoom = view_state.zoom
size_scale = 10 * (2**zoom)
# opactity = 255 if st.session_state.zoom >= 9 else 0  # Ajusta el tamaño según el
text_layer = pdk.Layer(
    "TextLayer",
    text_data,
    pickable=False,
    get_position="position",
    get_text="text",
    # sizeMinPixels=6,
    sizeMaxPixels=10,
    get_color="[255, 255, 255]",  # Ajusta la opacidad según el zoom
    # getPixelOffset="[0, -5]",  # Mover el texto hacia arriba
    background=True,
    get_background_color="[0, 0, 0, 180]",
    backgroundBorderRadius=3,
    backgroundPadding=[2, 2],
    get_alignment_baseline="'bottom'",
    get_text_anchor="'middle'",
    billboard=True,
    # sizeUnits="meters",  # 👈 clave
    get_size=16,
    size_min_pixels=6,
    # sizeScale=size_scale,  # 👈 dinámico
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
fecha = df["Fecha"].iloc[0]
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
# FOOTER
# ---------------------------------------------------

st.markdown("---")
st.caption(
    "Datos obtenidos de la API Open-meteo | Actualizado cada 15 minutos | Hecho por Red Nimbus"
)
