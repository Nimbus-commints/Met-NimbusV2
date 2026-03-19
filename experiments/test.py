import streamlit as st
import pydeck as pdk
import pandas as pd
import requests
import json
import plotly.express as px
import os
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

st.title("🏙️ Lima en Capas")
st.subheader("Mapa de Temperatura")


# ---------------------------------------------------
# LOAD GEOJSON
# ---------------------------------------------------
@st.cache_data
def load_map_data():
    with open("lima_districtsv2.geojson") as f:
        return json.load(f)


geojson = load_map_data()
# ---------------------------------------------------
# WEATHER FUNCTION
# ---------------------------------------------------


# USANDO API DE OPENWEATHER EN TIEMPO REAL (CON CACHE DE 15 MINUTOS)
@st.cache_data(ttl=900)
def get_weather(lat, lon):
    if not API_KEY:
        # Fallback para desarrollo sin API Key
        import random

        return {
            "temp": random.uniform(18, 26),
            "humidity": random.randint(60, 90),
            "wind": random.uniform(2, 7),
        }
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    )
    try:
        r = requests.get(url).json()
        return {
            "temp": r["main"]["temp"],
            "humidity": r["main"]["humidity"],
            "wind": r["wind"]["speed"],
        }
    except:
        return {"temp": 20, "humidity": 70, "wind": 5}


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

        weather = get_weather(lat, lon)

        props["temperature"] = weather["temp"]
        props["humidity"] = weather["humidity"]
        props["wind"] = weather["wind"]
        # elevacion
        props["elevation"] = weather["temp"] * 150
        district_data.append(
            {
                "District": name,
                "Temperature": weather["temp"],
                "Humidity": weather["humidity"],
                "Wind": weather["wind"],
            }
        )
        text_data.append(
            {"position": [lon, lat, props["elevation"] + 100], "text": name}
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
    getLineColor="[255, 255, 255]",
    lineWidthMinPixels=1,
    # 3D
    extruded=True,
    get_elevation="properties.elevation",
    wireframe=True,
    transitions={"get_elevation": 1000},
)


zoom = view_state.zoom
size_scale = 10 * (2**zoom)
opactity = 255 if st.session_state.zoom >= 9 else 0  # Ajusta el tamaño según el
text_layer = pdk.Layer(
    "TextLayer",
    text_data,
    pickable=False,
    get_position="position",
    get_text="text",
    sizeMinPixels=6,
    sizeMaxPixels=10,
    get_color="[255, 255, 255, opactity]",  # Ajusta la opacidad según el zoom
    # getPixelOffset="[0, -5]",  # Mover el texto hacia arriba
    background=True,
    get_background_color="[0, 0, 0, 180]",
    backgroundBorderRadius=3,
    backgroundPadding=[2, 2],
    get_alignment_baseline="'bottom'",
    # get_text_anchor="'middle'",
    billboard=True,
    # sizeUnits="meters",  # 👈 clave
    get_size=16,
    size_min_pixels=6,
    # sizeScale=size_scale,  # 👈 dinámico
)


deck = pdk.Deck(
    layers=[layer_geo, text_layer],
    initial_view_state=view_state,
    map_style="mapbox://styles/mapbox/dark-v10",
    tooltip={
        "html": "<b>{DISTRITO}</b><br/>"
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

# # ---------------------------------------------------
# # SNAPSHOT SECTION
# # ---------------------------------------------------

# st.markdown("## 🌤️ Hoy")

# cols = st.columns(5)
# for col, (_, row) in zip(cols, df.iterrows()):
#     col.metric(
#         row["District"], f"{row['Temperature']}°C", f"Humedad: {row['Humidity']}%"
#     )

# ---------------------------------------------------
# COMPARE DISTRICTS
# ---------------------------------------------------

st.markdown("### 📊 Análisis Comparativo")
col_sel, col_graph = st.columns([1, 2])

with col_sel:
    target_districts = st.multiselect(
        "Selecciona distritos para comparar:",
        df["District"].unique(),
        default=df["District"].iloc[:3],
    )

    filtered_df = df[df["District"].isin(target_districts)]

with col_graph:
    if not filtered_df.empty:
        fig = px.bar(
            filtered_df,
            x="District",
            y="Temperature",
            color="Temperature",
            title="Temperatura por Distrito Seleccionado",
            color_continuous_scale="Viridis",
        )
        st.plotly_chart(fig, width="stretch")
# st.markdown("## 📊 Analisis Comparativo")

# districts = df["District"].tolist()

# col1, col2 = st.columns(2)
# d1 = col1.selectbox("Distrito A", districts, index=1)
# d2 = col2.selectbox("Distrito B", districts)

# compare_df = df[df["District"].isin([d1, d2])]

# fig = px.bar(
#     compare_df, x="District", y=["Temperature", "Humidity", "Wind"], barmode="group"
# )

# fig.update_layout(transition_duration=500)

# st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------
# ALERTS SECTION
# ---------------------------------------------------

st.markdown("### 🚨 Monitor de Alertas")
hot_districts = (
    df[df["Temperature"] > 24]["District"].sort_values(ascending=False).tolist()
)
windy_districts = df[df["Wind"] > 7]["District"].tolist()

c1, c2 = st.columns(2)
with c1:
    if hot_districts:
        st.warning(f"🌡️ **Temperatura elevada:** {', '.join(hot_districts)}")
with c2:
    if windy_districts:
        st.error(f"🌬️ **Vientos fuertes:** {', '.join(windy_districts)}")

# ---------------------------------------------------
# FOOTER
# ---------------------------------------------------

st.markdown("---")
st.caption(
    "Datos obtenidos de OpenWeather | Actualizado cada 15 minutos | Hecho por Red Nimbus"
)
