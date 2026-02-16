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
st.set_page_config(layout="wide", page_title="Red Nimbus - Weather Dashboard")
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

    for feature in geojson["features"]:
        props = feature["properties"]
        name = props["DISTRITO"]
        lat = props["lat"]
        lon = props["lon"]

        weather = get_weather(lat, lon)

        props["temperature"] = weather["temp"]
        props["humidity"] = weather["humidity"]
        props["wind"] = weather["wind"]

        district_data.append(
            {
                "District": name,
                "Temperature": weather["temp"],
                "Humidity": weather["humidity"],
                "Wind": weather["wind"],
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
        # stroked=True,
        filled=True,
        get_fill_color="[255 - properties.temperature*5, 120, 50]",
        getLineColor="[0, 0, 0]",
        lineWidthMinPixels=1,
        # 3D
        extruded=True,
        get_elevation="properties.temperature * 100",
        wireframe=True,
        transitions={"get_elevation": 800},
    )

    # Preparar datos para TextLayer

    text_data = []
    for feature in geojson["features"]:
        elevation = feature["properties"]["temperature"] * 100
        text_data.append(
            {
                "position": [
                    feature["properties"]["lon"],
                    feature["properties"]["lat"],
                    elevation + 400,
                ],
                "text": feature["properties"]["DISTRITO"],
                # "temperature": feature["properties"]["temperature"],
            }
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
        # get_angle=90,
        # sizeScale=10,
        sizeMinPixels=6,
        sizeMaxPixels=10,
        get_color="[255, 255, 255, opactity]",  # Ajusta la opacidad según el zoom
        # getPixelOffset="[0, -5]",  # Mover el texto hacia arriba
        background=True,
        get_background_color="[0, 0, 0, 180]",
        backgroundBorderRadius=3,
        backgroundPadding=[4, 4],
        get_alignment_baseline="'center'",
        get_text_anchor="'middle'",
        billboard=True,
        sizeUnits="meters",  # 👈 clave
        get_size=200,  # tamaño base
        sizeScale=size_scale,  # 👈 dinámico
    )

    layers = [layer_geo]
    if st.session_state.zoom >= 9:
        layers.append(text_layer)

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
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

# ---------------------------------------------------
# SNAPSHOT SECTION
# ---------------------------------------------------

st.markdown("## 🌤️ Hoy")

cols = st.columns(5)
for col, (_, row) in zip(cols, df.iterrows()):
    col.metric(
        row["District"], f"{row['Temperature']}°C", f"Humedad: {row['Humidity']}%"
    )

# ---------------------------------------------------
# COMPARE DISTRICTS
# ---------------------------------------------------

st.markdown("## 📊 Comparar Distritos")

districts = df["District"].tolist()

col1, col2 = st.columns(2)
d1 = col1.selectbox("Distrito A", districts, index=1)
d2 = col2.selectbox("Distrito B", districts)

compare_df = df[df["District"].isin([d1, d2])]

fig = px.bar(
    compare_df, x="District", y=["Temperature", "Humidity", "Wind"], barmode="group"
)

fig.update_layout(transition_duration=500)

st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------
# ALERTS SECTION
# ---------------------------------------------------

st.markdown("## 🚨 Alertas Climáticas")

for _, row in df.iterrows():
    if row["Temperature"] > 25:
        st.warning(f"🌡️ Alta temperatura en {row['District']}")
    elif row["Wind"] > 8:
        st.error(f"🌬️ Vientos fuertes en {row['District']}")
    else:
        st.success(f"✅ Condiciones estables en {row['District']}")

# ---------------------------------------------------
# FOOTER
# ---------------------------------------------------

st.markdown("---")
st.caption("Datos obtenidos de OpenWeather | Actualizado cada 15 minutos")
