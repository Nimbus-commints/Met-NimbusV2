import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium


# --- CONFIGURATION & PERU DATA ---
st.set_page_config(
    page_title="RedNimbus Perú", layout="wide", initial_sidebar_state="collapsed"
)

# Curated list of high-impact Peruvian locations with descriptions
REGIONS = {
    "Lima (Costa Central)": {
        "lat": -12.0464,
        "lon": -77.0428,
        "description": "Capital - Clima Templado",
    },
    "Puno (Altiplano - Riesgo Heladas)": {
        "lat": -15.8402,
        "lon": -70.0219,
        "description": "Altiplano - Riesgo de Heladas",
    },
    "Piura (Norte - Riesgo El Niño)": {
        "lat": -5.1945,
        "lon": -80.6328,
        "description": "Norte - Riesgo Niño",
    },
    "Cusco (Sierra Sur)": {
        "lat": -13.5320,
        "lon": -71.9675,
        "description": "Sierra - Turismo",
    },
    "Iquitos (Selva)": {
        "lat": -3.7437,
        "lon": -73.2516,
        "description": "Selva Amazónica",
    },
}
# ===== GESTION DE ESTADO (Sincronizacion Mapa <---> Menu) ====

if "selected_city" not in st.session_state:
    st.session_state.selected_city = list(REGIONS.keys())[0]


@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    """
    Fetches 7-day hourly forecast from Open-Meteo API.
    Includes: temperature, precipitation, cloud cover, humidity.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,cloudcover,relative_humidity_2m",
        "timezone": "America/Lima",
        "forecast_days": 7,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
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


# === TITULO Y ENCABEZADO ===
st.title("🇵🇪 MONITOR CLIMÁTICO INTERACTIVO")
st.markdown("**RedNimbus** - Pronóstico de 7 días para ciudades estratégicas del Perú")

# === LAYOUT SUPERIOR: MAPA Y SELECTOR ===

col_map, col_controls = st.columns([2, 1])
with col_map:
    # Crear mapa base centrado en Perú
    m = folium.Map(
        location=[-9.19, -75.01],
        zoom_start=5,
        tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        attr="Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap (CC-BY-SA)",
    )

    # Agregar marcadores para cada región
    for city, data in REGIONS.items():
        color = "red" if city == st.session_state.selected_city else "blue"
        icon = "star" if city == st.session_state.selected_city else "info-sign"

        folium.Marker(
            [data["lat"], data["lon"]],
            popup=city,
            tooltip=f"Ver Clima en {city}",
            icon=folium.Icon(color=color, icon=icon),
        ).add_to(m)

    # Renderizar mapa y capturar interacción
    map_output = st_folium(
        m,
        height=400,
        use_container_width=True,
        key="mapa_peru",
        returned_objects=["last_object_clicked_tooltip"],
    )

# === LÓGICA DE ACTUALIZACIÓN POR CLICK EN EL MAPA ===
if map_output and map_output.get("last_object_clicked_tooltip"):
    raw_text = map_output["last_object_clicked_tooltip"]
    clicked_city = raw_text.replace("Ver Clima en ", "").strip()
    if clicked_city in REGIONS and clicked_city != st.session_state.selected_city:
        st.session_state.selected_city = clicked_city
        st.rerun()

with col_controls:
    st.subheader("⚙️ Configuración")
    selected_city = st.selectbox(
        "Región Activa:",
        options=list(REGIONS.keys()),
        key="selected_city",
        format_func=lambda x: x.split("(")[0].strip(),
    )

    coords = REGIONS[selected_city]
    st.info(
        f"📍 **Analizando:** {selected_city}\n\n"
        f"**Coordenadas:** {coords['lat']:.4f}, {coords['lon']:.4f}"
    )
    st.caption(f"ℹ️ {coords['description']}")


# === PROCESO Y VISUALIZACION DE DATOS ===
st.divider()

with st.spinner("⏳ Actualizando información meteorológica..."):
    data = get_weather_data(coords["lat"], coords["lon"])

if data and "hourly" in data:
    # DataFrame
    df = pd.DataFrame(
        {
            "Tiempo": pd.to_datetime(data["hourly"]["time"]),
            "Temp (°C)": data["hourly"]["temperature_2m"],
            "Lluvia (mm)": data["hourly"]["precipitation"],
            "Humedad (%)": data["hourly"]["relative_humidity_2m"],
            "Nubosidad (%)": data["hourly"]["cloudcover"],
        }
    )

    # Agregaciones útiles
    current_temp = df["Temp (°C)"].iloc[0]
    max_temp = df["Temp (°C)"].max()
    min_temp = df["Temp (°C)"].min()
    total_rain = df["Lluvia (mm)"].sum()
    current_humidity = df["Humedad (%)"].iloc[0]
    current_cloud = df["Nubosidad (%)"].iloc[0]

    # === MÉTRICAS KPI ===
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    kpi1.metric(
        "🌡️ Temperatura Actual", f"{current_temp:.1f}°C", f"Máx: {max_temp:.1f}°C"
    )
    kpi2.metric(
        "☔ Lluvia Acumulada (7 días)", f"{total_rain:.1f} mm", delta_color="inverse"
    )
    kpi3.metric("💨 Humedad Actual", f"{current_humidity:.0f}%", delta_color="off")
    kpi4.metric(
        "☁️ Nubosidad",
        f"{current_cloud:.0f}%",
        (
            "Despejado"
            if current_cloud < 30
            else "Parcial nuboso" if current_cloud < 70 else "Nublado"
        ),
    )

    # === LÓGICA DE ALERTAS ===
    st.subheader("⚠️ Alertas y Condiciones")

    alerts_triggered = False

    if min_temp <= 2:
        st.error(
            f"❄️ **ALERTA DE HELADA:** Mínima de {min_temp:.1f}°C detectada. Riesgo crítico para cultivos andinos."
        )
        alerts_triggered = True

    if total_rain > 50:
        st.warning(
            f"🌊 **ALERTA DE LLUVIA INTENSA:** {total_rain:.1f}mm acumulados en 7 días. Riesgo de desborde."
        )
        alerts_triggered = True

    if df["Lluvia (mm)"].max() > 10:
        st.warning(
            f"🌧️ **LLUVIA PUNTUAL:** Máximo horario de {df['Lluvia (mm)'].max():.1f}mm/hora"
        )
        alerts_triggered = True

    if not alerts_triggered:
        st.success(
            "✅ **Condiciones Estables:** Sin alertas meteorológicas críticas para los próximos 7 días."
        )

    # === GRÁFICOS INTERACTIVOS ===
    st.subheader("📊 Análisis de Pronóstico")
    tab1, tab2, tab3 = st.tabs(
        ["📈 Temperatura", "☔ Precipitaciones", "💨 Humedad y Nubosidad"]
    )

    with tab1:
        fig_temp = px.line(
            df,
            x="Tiempo",
            y="Temp (°C)",
            markers=True,
            title=f"Pronóstico de Temperatura - {selected_city}",
            labels={"Temp (°C)": "Temperatura (°C)", "Tiempo": "Fecha y Hora"},
        )
        fig_temp.add_hline(
            y=2,
            line_dash="dash",
            line_color="red",
            annotation_text="⚠️ Umbral de Helada",
            annotation_position="right",
        )
        fig_temp.update_layout(hovermode="x unified", height=500)
        st.plotly_chart(fig_temp, use_container_width=True)

    with tab2:
        fig_rain = px.bar(
            df,
            x="Tiempo",
            y="Lluvia (mm)",
            title=f"Precipitación Horaria - {selected_city}",
            labels={"Lluvia (mm)": "Lluvia (mm)", "Tiempo": "Fecha y Hora"},
            color="Lluvia (mm)",
            color_continuous_scale="Blues",
        )
        fig_rain.update_layout(hovermode="x unified", height=500)
        st.plotly_chart(fig_rain, use_container_width=True)

    with tab3:
        fig_humidity = px.line(
            df,
            x="Tiempo",
            y=["Humedad (%)", "Nubosidad (%)"],
            title=f"Humedad y Nubosidad - {selected_city}",
            labels={"value": "Porcentaje (%)", "Tiempo": "Fecha y Hora"},
            color_discrete_map={"Humedad (%)": "#1C83E1", "Nubosidad (%)": "#A9A9A9"},
        )
        fig_humidity.update_layout(hovermode="x unified", height=500)
        st.plotly_chart(fig_humidity, use_container_width=True)

    # === EXPORTAR DATOS ===
    st.divider()
    col_download, col_info = st.columns([1, 3])

    with col_download:
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Reporte (CSV)",
            data=csv_data,
            file_name=f"clima_{selected_city.lower().split('(')[0].strip().replace(' ', '_')}_7dias.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col_info:
        st.caption(
            f"📅 Datos actualizados automáticamente cada hora. Próximos 7 días a partir de {df['Tiempo'].iloc[0].strftime('%d/%m/%Y %H:%M')}"
        )

else:
    st.error(
        "❌ No se pudieron cargar los datos. Por favor verifica tu conexión a internet e intenta nuevamente."
    )
