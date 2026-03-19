import streamlit as st
import pydeck as pdk
import pandas as pd
import requests
import json
import plotly.express as px
import time as _time
from datetime import datetime

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
st.set_page_config(
    layout="wide", page_title="Red Nimbus - Weather Dashboard", page_icon="nimbu.ico"
)

# Constantes
TEMP_ALERT_THRESHOLD = 24  # °C
WIND_ALERT_THRESHOLD = 7  # m/s
ELEVATION_SCALE = 150
API_TIMEOUT = 30
DATA_TTL_SECONDS = 15 * 60  # 15 minutos
LIMA_CENTER = (-12.0464, -77.0428)
PRECIPITATION_SCALE = 800


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


def data_is_stale():
    """Verifica si los datos cargados ya expiraron."""
    loaded_at = st.session_state.get("data_loaded_at", 0)
    return (_time.time() - loaded_at) > DATA_TTL_SECONDS


# ---------------------------------------------------
# LOAD GEOJSON
# ---------------------------------------------------
@st.cache_data
def load_map_data():
    with open("lima_districtsv2.geojson") as f:
        return json.load(f)


geojson = load_map_data()


# ---------------------------------------------------
# BATCH WEATHER FETCH (1 sola request para todos los distritos)
# ---------------------------------------------------
def fetch_all_districts_weather(features, max_retries=3):
    """Obtiene datos meteorológicos de todos los distritos en una sola petición batch."""
    latitudes = [f["properties"]["lat"] for f in features]
    longitudes = [f["properties"]["lon"] for f in features]
    names = [f["properties"]["DISTRITO"] for f in features]

    params = {
        "latitude": latitudes,
        "longitude": longitudes,
        "hourly": ["temperature_2m", "precipitation", "relative_humidity_2m"],
        "current": ["temperature_2m", "wind_speed_10m", "relative_humidity_2m"],
        "timezone": "America/Lima",
        "wind_speed_unit": "ms",
    }

    for attempt in range(max_retries):
        try:
            response = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params=params,
                timeout=API_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list) or len(data) != len(names):
                raise ValueError(f"Respuesta inesperada: se esperaban {len(names)} resultados")

            results = []
            for i, item in enumerate(data):
                results.append({
                    "name": names[i],
                    "temperature": item["current"]["temperature_2m"],
                    "humidity": item["current"]["relative_humidity_2m"],
                    "wind": item["current"]["wind_speed_10m"],
                    "time": item["current"]["time"],
                    "pronostico": item["hourly"],
                })
            return results

        except Exception as e:
            if attempt < max_retries - 1:
                _time.sleep(2 ** attempt)
                continue
            st.error(f"Error al obtener datos después de {max_retries} intentos: {e}")
            # Fallback con datos por defecto
            return [
                {
                    "name": name,
                    "temperature": 20,
                    "humidity": 70,
                    "wind": 5,
                    "time": datetime.now().isoformat(),
                    "pronostico": {
                        "time": [],
                        "temperature_2m": [],
                        "precipitation": [],
                        "relative_humidity_2m": [],
                    },
                }
                for name in names
            ]


# ---------------------------------------------------
# SIDEBAR
# ---------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div style="text-align:center; padding: 10px 0 5px 0;">
            <span style="font-size:2rem;">🌩️</span>
            <h2 style="margin:0; padding:0;">Red Nimbus</h2>
            <p style="margin:0; color:#888; font-size:0.85rem;">Monitoreo Climático de Lima</p>
        </div>
        <hr style="margin:10px 0; border-color:#333;">
        """,
        unsafe_allow_html=True,
    )

    if st.button("🔄 Actualizar datos", use_container_width=True):
        for key in ["master_df", "enriched_geojson", "text_layer_data", "pronosticos_df", "data_loaded_at"]:
            st.session_state.pop(key, None)
        st.rerun()

    if "data_loaded_at" in st.session_state:
        elapsed = _time.time() - st.session_state.data_loaded_at
        mins = int(elapsed // 60)
        if mins > 0:
            st.caption(f"⏱️ Datos cargados hace {mins} min")
        else:
            st.caption("⏱️ Datos recién cargados")

    # Placeholder para resumen — se llena después de cargar datos
    sidebar_stats = st.empty()


# ---------------------------------------------------
# LOAD & PROCESS DATA
# ---------------------------------------------------
if "master_df" not in st.session_state or data_is_stale():
    with st.status(
        "📡 Sincronizando datos de distritos en tiempo real...", expanded=True
    ) as status:
        st.write("Descargando datos meteorológicos (1 petición batch)...")

        weather_results = fetch_all_districts_weather(geojson["features"])

        st.write("Procesando geometrías y capas 3D...")
        weather_map = {res["name"]: res for res in weather_results}
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
            props["elevation"] = w["temperature"] * ELEVATION_SCALE

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
            for t, temp, pp, hum in zip(
                w["pronostico"]["time"],
                w["pronostico"]["temperature_2m"],
                w["pronostico"]["precipitation"],
                w["pronostico"].get("relative_humidity_2m", [None] * len(w["pronostico"]["time"])),
            ):
                pronosticos_data.append(
                    {
                        "District": props["DISTRITO"],
                        "lat": props["lat"],
                        "lon": props["lon"],
                        "Fechas": parse_time(t),
                        "Temperature": temp,
                        "Precipitation": pp,
                        "Humidity": hum,
                    }
                )

        st.session_state.master_df = pd.DataFrame(district_data)
        st.session_state.enriched_geojson = geojson
        st.session_state.text_layer_data = text_data
        st.session_state.pronosticos_df = pd.DataFrame(pronosticos_data)
        st.session_state.data_loaded_at = _time.time()
        status.update(
            label="✅ Datos cargados correctamente", state="complete", expanded=False
        )

# Recuperamos datos de la sesión
df = st.session_state.master_df
geojson = st.session_state.enriched_geojson
text_data = st.session_state.text_layer_data
pronosticos = st.session_state.pronosticos_df

# Rellenar sidebar con estadísticas
with sidebar_stats.container():
    st.markdown("<hr style='margin:10px 0; border-color:#333;'>", unsafe_allow_html=True)
    st.markdown("##### 📊 Resumen actual")

    _col1, _col2 = st.columns(2)
    _col1.metric("🌡️ Máx", f"{df['Temperature'].max():.1f}°C")
    _col2.metric("❄️ Mín", f"{df['Temperature'].min():.1f}°C")

    _col3, _col4 = st.columns(2)
    _col3.metric("💨 Viento máx", f"{df['Wind'].max():.1f} m/s")
    _col4.metric("💧 Hum. prom", f"{df['Humidity'].mean():.0f}%")

    hottest = df.loc[df["Temperature"].idxmax()]
    coldest = df.loc[df["Temperature"].idxmin()]
    st.markdown("<hr style='margin:10px 0; border-color:#333;'>", unsafe_allow_html=True)
    st.markdown("##### 🏆 Extremos")
    st.markdown(f"🔴 **Más caliente:** {hottest['District']} ({hottest['Temperature']:.1f}°C)")
    st.markdown(f"🔵 **Más frío:** {coldest['District']} ({coldest['Temperature']:.1f}°C)")

    st.markdown("<hr style='margin:10px 0; border-color:#333;'>", unsafe_allow_html=True)
    st.markdown("##### ℹ️ Datos")
    st.caption(f"📍 {len(df)} distritos monitoreados")
    st.caption("📅 Pronóstico: 7 días (168 horas)")
    st.caption("🌐 Fuente: Open-Meteo API")

# ---------------------------------------------------
# HEADER
# ---------------------------------------------------
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

# ---------------------------------------------------
# LEYENDA DE COLORES
# ---------------------------------------------------
st.markdown(
    """
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:10px;">
        <span style="font-weight:bold; font-size:14px;">Temperatura:</span>
        <span style="background:rgb(150,110,200); padding:2px 10px; border-radius:4px; color:white;">≤15°C</span>
        <span style="background:rgb(180,100,135); padding:2px 10px; border-radius:4px; color:white;">18°C</span>
        <span style="background:rgb(200,90,95); padding:2px 10px; border-radius:4px; color:white;">20°C</span>
        <span style="background:rgb(220,80,55); padding:2px 10px; border-radius:4px; color:white;">22°C</span>
        <span style="background:rgb(250,60,15); padding:2px 10px; border-radius:4px; color:white;">≥25°C</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------
# 3D MAP
# ---------------------------------------------------
view_state = pdk.ViewState(
    latitude=LIMA_CENTER[0],
    longitude=LIMA_CENTER[1],
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
    extruded=True,
    get_elevation="properties.elevation",
    wireframe=True,
    transitions={"get_elevation": 1000},
)

text_layer = pdk.Layer(
    "TextLayer",
    text_data,
    pickable=False,
    get_position="position",
    get_text="text",
    sizeMaxPixels=10,
    get_color="[255, 255, 255]",
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

# ---------------------------------------------------
# ANÁLISIS COMPARATIVO
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
            labels={"Temperature": "Temperatura (°C)", "District": "Distritos"},
            title="TEMPERATURA POR DISTRITOS SELECCIONADOS",
            subtitle=f"FECHA: {fecha}",
            color_continuous_scale="Viridis",
        )
        fig.update_layout(hovermode="x unified", height=500)
        st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------
# ALERTAS
# ---------------------------------------------------
st.markdown("### 🚨 Monitor de Alertas")
hot_districts = (
    df[df["Temperature"] > TEMP_ALERT_THRESHOLD]["District"]
    .sort_values(ascending=False)
    .tolist()
)
windy_districts = df[df["Wind"] > WIND_ALERT_THRESHOLD]["District"].tolist()

c1, c2 = st.columns(2)
with c1:
    if hot_districts:
        st.warning(
            f"🌡️ **Temperatura elevada (> {TEMP_ALERT_THRESHOLD}°C):** {', '.join(hot_districts)}"
        )
    else:
        st.success("🌡️ Temperaturas normales en todos los distritos")
with c2:
    if windy_districts:
        st.error(
            f"🌬️ **Vientos fuertes (> {WIND_ALERT_THRESHOLD} m/s):** {', '.join(windy_districts)}"
        )
    else:
        st.success("🌬️ Vientos normales en todos los distritos")

# ---------------------------------------------------
# PRONÓSTICOS
# ---------------------------------------------------
st.markdown("### 📈 Pronósticos - Próximos 7 días")
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

tab1, tab2, tab3 = st.tabs(["📈 Temperatura", "☔ Precipitación", "💧 Humedad"])

with col_graph_forecast:
    with tab1:
        if not filtered_forecast.empty:
            fig_temp = px.line(
                filtered_forecast,
                x="Fechas",
                y="Temperature",
                color="District",
                title="Pronóstico de Temperatura",
                labels={
                    "Temperature": "Temperatura (°C)",
                    "Fechas": "Fecha y Hora",
                    "District": "Distrito",
                },
            )
            fig_temp.update_traces(hovertemplate="%{y:.1f}°C")
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
                title="Pronóstico de Precipitación",
                labels={
                    "Precipitation": "Precipitación (mm)",
                    "Fechas": "Fecha y Hora",
                    "District": "Distrito",
                },
            )
            fig_precip.update_traces(hovertemplate="%{y:.2f} mm")
            fig_precip.update_layout(hovermode="x unified", height=500)
            st.plotly_chart(fig_precip, width="stretch")
        else:
            st.info("Selecciona al menos un distrito para mostrar el pronóstico.")
    with tab3:
        if not filtered_forecast.empty:
            fig_hum = px.line(
                filtered_forecast,
                x="Fechas",
                y="Humidity",
                color="District",
                title="Pronóstico de Humedad Relativa",
                labels={
                    "Humidity": "Humedad (%)",
                    "Fechas": "Fecha y Hora",
                    "District": "Distrito",
                },
            )
            fig_hum.update_traces(hovertemplate="%{y:.0f}%")
            fig_hum.update_layout(hovermode="x unified", height=500)
            st.plotly_chart(fig_hum, width="stretch")
        else:
            st.info("Selecciona al menos un distrito para mostrar el pronóstico.")

# ---------------------------------------------------
# ANIMACIÓN TEMPORAL DE PRECIPITACIÓN
# ---------------------------------------------------
st.markdown("### 🌧️ Precipitación por hora")
unique_times = sorted(pronosticos["Fechas"].unique())
selected_time = st.select_slider(
    "Selecciona fecha y hora:",
    options=unique_times,
    format_func=lambda x: x.strftime("%d-%m %H:%M"),
)

time_filtered = pronosticos[pronosticos["Fechas"] == selected_time].copy()
time_filtered["elevation"] = time_filtered["Precipitation"] * PRECIPITATION_SCALE

max_prec = pronosticos["Precipitation"].max()
time_filtered["color_r"] = 0
time_filtered["color_g"] = (
    (time_filtered["Precipitation"] / (max_prec + 1e-6)) * 150
).astype(int)
time_filtered["color_b"] = 255

precipitation_layer = pdk.Layer(
    "ColumnLayer",
    data=time_filtered,
    get_position="[lon, lat]",
    get_elevation="elevation",
    elevationScale=1,
    radius=500,
    get_fill_color="[color_r, color_g, color_b]",
    pickable=True,
    extruded=True,
)

deck_temporal = pdk.Deck(
    layers=[precipitation_layer],
    initial_view_state=view_state,
    tooltip={
        "html": "<b>{District}</b><br/>Precip: {Precipitation} mm",
        "style": {
            "backgroundColor": "black",
            "color": "white",
        },
    },
)

st.pydeck_chart(deck_temporal)

st.dataframe(
    time_filtered[["District", "Precipitation", "Temperature", "Humidity"]]
    .sort_values("Precipitation", ascending=False)
    .reset_index(drop=True),
    use_container_width=True,
)

# ---------------------------------------------------
# EXPORTAR DATOS
# ---------------------------------------------------
st.markdown("### 📥 Exportar datos")
col_exp1, col_exp2 = st.columns(2)
with col_exp1:
    csv_actual = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Descargar datos actuales (CSV)",
        csv_actual,
        "lima_weather_actual.csv",
        "text/csv",
    )
with col_exp2:
    csv_forecast = pronosticos.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Descargar pronóstico 7 días (CSV)",
        csv_forecast,
        "lima_weather_pronostico.csv",
        "text/csv",
    )

# ---------------------------------------------------
# FOOTER
# ---------------------------------------------------
st.markdown("---")
st.caption(
    "Datos obtenidos de la API Open-Meteo | Auto-actualización cada 15 minutos | Hecho por Red Nimbus"
)
