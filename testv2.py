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
API_KEY = os.getenv("OPENWEATHER_API_KEY")


if "zoom" not in st.session_state:
    st.session_state.zoom = 10

st.title("LIMA")
st.subheader("Mapa de Temperatura")


# ---------------------------------------------------
# LOAD GEOJSON
# ---------------------------------------------------
@st.cache_data
def load_map_data():
    with open("lima_districtsv2.geojson") as f:
        return json.load(f)


geojson = load_map_data()


# USANDO API DE OPEN
@st.cache_data(ttl=900)
def get_weather_datav2(lat, lon):
    ulr = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m",
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


# ---------------------------------------------------
# ENRICH GEOJSON WITH WEATHER
# ---------------------------------------------------
with st.spinner("Cargando datos meteorologicos por distrito..."):
    district_data = []
    text_data = []

    for feature in geojson["features"]:
        props = feature["properties"]
        name = props["DISTRITO"]
        lat = props["lat"]
        lon = props["lon"]

        weather = get_weather_datav2(lat, lon)

        props["temperature"] = weather["current"]["temperature_2m"]
        iso_date = weather["current"]["time"]
        # props["fecha"] = datetime.strptime(iso_date, "%Y-%m-%dT%H:%M")
        props["fecha"] = weather["current"]["time"]
        props["humidity"] = weather["current"]["relative_humidity_2m"]
        props["wind"] = weather["current"]["wind_speed_10m"]
        # elevacion
        props["elevation"] = weather["current"]["temperature_2m"] * 150

        district_data.append(
            {
                "District": name,
                "Fecha": datetime.strptime(iso_date, "%Y-%m-%dT%H:%M"),
                "Temperature": weather["current"]["temperature_2m"],
                "Humidity": weather["current"]["relative_humidity_2m"],
                "Wind": weather["current"]["wind_speed_10m"],
            }
        )
        text_data.append(
            {
                "position": [lon, lat, props["elevation"] + 100],
                "text": name,
                # "Fecha": weather["current"]["time"],
            }
        )

    df = pd.DataFrame(district_data)

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
