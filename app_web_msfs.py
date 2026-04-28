import streamlit as st
import airportsdata
import numpy as np
import requests
import pandas as pd
import plotly.express as px
import folium
import math
import gspread
import random
from oauth2client.service_account import ServiceAccountCredentials
from streamlit_folium import st_folium
from datetime import datetime, time, timedelta

AIRPORTS_DB = airportsdata.load('ICAO')

# --- 1. DATOS ---

AIRPORT_COORDS_FALLBACK = {
    "NTAA": [-17.5536, -149.6070]
}

AEROLINEAS_BASE = sorted([
    "Aer Lingus", "Aeroflot", "Aerolíneas Argentinas", "Aeroméxico", "Air Canada", "Air China",
    "Air Europa", "Air France", "Air India", "Air New Zealand", "Alaska Airlines", 
    "Alitalia (ITA Airways)", "All Nippon Airways (ANA)", "American Airlines", "British Airways", 
    "Cathay Pacific", "Copa Airlines", "Delta Air Lines", "Emirates", "Iberia", "Japan Airlines (JAL)", 
    "KLM", "Korean Air", "LATAM Airlines", "Lufthansa", "Qantas", "Qatar Airways", "Ryanair", 
    "Singapore Airlines", "Southwest Airlines", "Turkish Airlines", "United Airlines", "Vueling"
])

MODELOS_AVION = [
    "Avro RJ/BAe 146", "ATR 42-600", "ATR 72-600", "Airbus A319", "Airbus A320",
    "Airbus A320 Neo", "Airbus A321", "Airbus A321 Neo", "Airbus A330-900", "Airbus A340-600",
    "Airbus A350-900", "Airbus A350-1000", "Airbus A380-800", "Boeing 737-600", "Boeing 737-700",
    "Boeing 737-800", "Boeing 737 MAX 8", "Boeing 737-900", "Boeing 747-8", "Boeing 777-200",
    "Boeing 777-200LR", "Boeing 777-300ER", "Boeing 777F", "Boeing 787-8", "Boeing 787-9",
    "Boeing 787-10", "Embraer E170", "Embraer E175", "Embraer E190", "Embraer E195",
    "Sukhoi SuperJet 100"
]

CHECKLISTS_DB = {
    "Airbus (Familia A320/A330)": {
        "Cockpit Prep": ["Batteries 1 & 2: ON", "Ext Pwr: ON (if avail)", "ADIRS: NAV", "Ext Lt: NAV/LOGO"],
        "Before Start": ["APU: START", "Seatbelts: ON", "Doors: CLOSED", "Beacon: ON", "Parking Brake: SET"],
        "Engine Start": ["Thrust Levers: IDLE", "Engine Mode: IGN/START", "Master 2: ON", "Master 1: ON"],
        "After Start": ["Engine Mode: NORM", "APU Bleed: OFF", "APU Master: OFF", "Flaps: SET T/O"],
        "Takeoff": ["Auto Brake: MAX", "T.O Config: TEST", "Landing Lights: ON"]
    },
    "Boeing (737/747/777/787)": {
        "Pre-Flight": ["Battery: ON", "Standby Power: AUTO", "Hydraulics: NORM", "Pos Lights: STEADY"],
        "Before Start": ["Fuel Pumps: ON", "APU: START", "Anti-Collision Lt: ON", "Packs: OFF"],
        "Engine Start": ["Ignition: GND/CONT", "Start Switch: GRD", "Fuel Lever: IDLE DETENT"],
        "Before Taxi": ["Generators: ON", "Probe Heat: ON", "Packs: AUTO", "Flaps: SET"],
        "Takeoff": ["Auto Brake: RTO", "Transponder: TA/RA", "Landing Lights: ON"]
    }
}

SHEET_HEADERS = [
    "Fecha", "Origen", "Destino", "Ruta", "Aerolinea", "Num_Vuelo", "Modelo_Avion",
    "Hora_OUT", "Hora_IN", "Tiempo_Vuelo_Horas", "Distancia_NM", "Gate_Salida",
    "Gate_Llegada", "Landing_Rate_FPM", "Notas"
]

# --- 2. GOOGLE SHEETS ---
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def conectar_google_sheets():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("⚠️ No se encontraron los secretos de Google Cloud.")
            return None
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open("FlightLogbook").sheet1
        existing = sheet.get_all_values()
        if not existing:
            sheet.append_row(SHEET_HEADERS)
        elif existing[0] != SHEET_HEADERS:
            sheet.insert_row(SHEET_HEADERS, 1)
        return sheet
    except Exception as e:
        st.error(f"Error conectando a Google Sheets: {e}")
        return None

@st.cache_data(ttl=30)
def leer_vuelos():
    sheet = conectar_google_sheets()
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            if df.empty: return pd.DataFrame()
            cols_num = ['Tiempo_Vuelo_Horas', 'Distancia_NM', 'Landing_Rate_FPM']
            for col in cols_num:
                if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception as e:
            st.error(f"Error leyendo datos: {e}")
    return pd.DataFrame()

def guardar_vuelo_gs(row_data):
    sheet = conectar_google_sheets()
    if sheet:
        try:
            row_str = [str(x) for x in row_data]
            sheet.append_row(row_str)
            leer_vuelos.clear()
            return True
        except Exception: return False
    return False

def eliminar_vuelo_gs(row_index):
    sheet = conectar_google_sheets()
    if sheet:
        try:
            sheet.delete_rows(row_index + 2)
            leer_vuelos.clear()
            return True
        except Exception: return False
    return False

# --- 3. FUNCIONES LÓGICAS ---
def get_geodesic_path(lat1, lon1, lat2, lon2, n_points=100):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    if c == 0: return [[np.degrees(lat1), np.degrees(lon1)], [np.degrees(lat2), np.degrees(lon2)]]
    f = np.linspace(0, 1, n_points)
    A = np.sin((1 - f) * c) / np.sin(c)
    B = np.sin(f * c) / np.sin(c)
    x = A * np.cos(lat1) * np.cos(lon1) + B * np.cos(lat2) * np.cos(lon2)
    y = A * np.cos(lat1) * np.sin(lon1) + B * np.cos(lat2) * np.sin(lon2)
    z = A * np.sin(lat1) + B * np.sin(lat2)
    lat_i = np.arctan2(z, np.sqrt(x**2 + y**2))
    lon_i = np.unwrap(np.arctan2(y, x))
    return np.stack([np.degrees(lat_i), np.degrees(lon_i)], axis=1).tolist()

def haversine_nm(lat1, lon1, lat2, lon2):
    R = 3440.065
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    a = math.sin((lat2 - lat1)/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1)/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def calcular_rango_xp(df):
    horas = df['Tiempo_Vuelo_Horas'].sum() if not df.empty else 0
    if horas < 10: return "Cadete", "🎓", horas, 10
    elif horas < 50: return "Primer Oficial", "👨‍✈️", horas, 50
    elif horas < 150: return "Capitán", "⭐⭐", horas, 150
    elif horas < 500: return "Comandante Senior", "⭐⭐⭐⭐", horas, 500
    else: return "Leyenda del Aire", "👑", horas, 1000

def obtener_datos_simbrief(username):
    if not username: return None, "Ingresa un usuario."
    url = f"https://www.simbrief.com/api/xml.fetcher.php?username={username}&json=1"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            gen, orig, dest, times = data.get('general',{}), data.get('origin',{}), data.get('destination',{}), data.get('times',{})
            dep_time = datetime.utcfromtimestamp(int(times.get('sched_out', 0))).strftime('%H:%M') if times.get('sched_out') else "12:00"
            return {
                "origen": orig.get('icao_code', ''), "destino": dest.get('icao_code', ''),
                "no_vuelo": f"{gen.get('icao_airline', '')}{gen.get('flight_number', '')}",
                "ruta": gen.get('route', ''), "tiempo_est": int(times.get('est_block', 0)) / 3600,
                "puerta_salida": orig.get('gate', 'TBD'), "puerta_llegada": dest.get('gate', 'TBD'),
                "hora_salida": dep_time, "fecha": datetime.now().strftime("%d %b %Y").upper()
            }, None
        return None, "Error al conectar con SimBrief."
    except Exception as e: return None, f"Excepción: {e}"

def obtener_vuelo_real_api(api_key):
    """Obtiene un vuelo real saliendo desde un hub global usando AeroDataBox con reintentos."""
    AEROPUERTOS_HUB = ["KJFK", "EGLL", "SAEZ", "SCEL", "OMDB", "YSSY", "RJAA", "LEMD", "LFPG", "EHAM", "KLAX", "SBGR", "KMIA", "SPJC"]
    
    # Intentamos hasta 3 veces con aeropuertos distintos si la API devuelve una lista vacía
    for intento in range(3):
        origen_icao = random.choice(AEROPUERTOS_HUB)

        # Usamos 11 horas para mantenernos seguros dentro del límite estricto de 12h de la API
        now_utc = datetime.utcnow()
        to_utc = now_utc + timedelta(hours=11) 
        from_str = now_utc.strftime("%Y-%m-%dT%H:%M")
        to_str = to_utc.strftime("%Y-%m-%dT%H:%M")

        url = f"https://aerodatabox.p.rapidapi.com/flights/airports/icao/{origen_icao}/{from_str}/{to_str}"
        headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": "aerodatabox.p.rapidapi.com"}
        querystring = {"withLeg": "true", "direction": "Departure", "withCancelled": "false", "withPrivate": "false"}

        try:
            response = requests.get(url, headers=headers, params=querystring, timeout=10)
            
            # Si la respuesta es exitosa, procesamos los datos
            if response.status_code == 200:
                data = response.json()
                departures = data.get("departures", [])
                vuelos_validos = []

                for d in departures:
                    if "movement" in d and "arrival" in d:
                        dest = d["arrival"].get("airport", {}).get("icao")
                        airline = d.get("airline", {}).get("name") or d.get("airline", {}).get("iata") or "Aerolínea Desconocida"
                        flt_num = d.get("number")
                        aircraft = d.get("aircraft", {}).get("model", "Avión genérico")

                        if dest and flt_num:
                            vuelos_validos.append({
                                "origen": origen_icao,
                                "destino": dest,
                                "aerolinea": airline,
                                "num": flt_num,
                                "avion": aircraft,
                                "duracion": "TBD",
                                "info": f"Vuelo real programado (Hora local: {d['movement'].get('scheduledTimeLocal', 'Desconocida')[:16]})"
                            })

                # Si encontró vuelos válidos, devuelve uno y corta el bucle
                if vuelos_validos:
                    return random.choice(vuelos_validos), None
                
                # Si la lista vuelve vacía, el bucle sigue e intenta con otro aeropuerto...

        except Exception as e:
            # Si hay un error de conexión, lo ignoramos temporalmente y probamos de nuevo
            pass 

    # Si después de 3 intentos distintos no encontró nada, recién ahí avisa
    return None, "Los radares están tranquilos. No se encontraron vuelos comerciales en los aeropuertos escaneados. Intentá de nuevo."
    
def obtener_coords(icao):
    if not isinstance(icao, str):
        return None
    codigo = icao.strip().upper()
    aeropuerto = AIRPORTS_DB.get(codigo)
    if aeropuerto:
        return [aeropuerto['lat'], aeropuerto['lon']]
    return AIRPORT_COORDS_FALLBACK.get(codigo, None)
# --- 4. INTERFAZ ---

def main_app():
    st.set_page_config(page_title="MSFS EFB Ultimate", layout="wide", page_icon="✈️")

    modo_grande = st.sidebar.toggle("👁️ Modo Texto Grande", value=False)
    if modo_grande:
        st.markdown("""
            <style>
            html, body, [class*="css"] { font-size: 20px !important; }
            h1 { font-size: 3rem !important; }
            h2 { font-size: 2.5rem !important; }
            .stTextInput > div > div > input, .stSelectbox > div > div > div, .stNumberInput > div > div > input, textarea { font-size: 18px !important; }
            .stButton > button { font-size: 20px !important; padding: 10px 24px !important; font-weight: bold !important; }
            [data-testid="stSidebar"] { font-size: 18px !important; }
            </style>
        """, unsafe_allow_html=True)

    # SIDEBAR
    st.sidebar.title("👨‍✈️ Perfil")
    df_log = leer_vuelos()
    rango, icono, horas_act, horas_next = calcular_rango_xp(df_log)

    rango_prev = st.session_state.get("rango_anterior", rango)
    if rango_prev != rango:
        st.balloons()
        st.success(f"🎉 ¡Subiste de rango! Ahora eres **{rango}** {icono}")
    st.session_state["rango_anterior"] = rango

    st.sidebar.markdown(f"### {icono} {rango}")
    st.sidebar.metric("Horas Totales", f"{horas_act:.1f} h")
    if horas_next != 1000:
        st.sidebar.progress(min(horas_act / horas_next, 1.0))
        st.sidebar.caption(f"Próximo rango en {horas_next - horas_act:.1f} h")

    st.sidebar.markdown("---")
    menu = st.sidebar.radio("EFB Menu", [
        "📋 Registro de Vuelo", "✅ Checklists", "🗺️ Mapa",
        "🎲 Vuelos Aleatorios", "📊 Estadísticas"
    ])

    # =========================================================
    # 1. REGISTRO DE VUELO
    # =========================================================
    if menu == "📋 Registro de Vuelo":
        st.header("📋 Registrar Vuelo / SimBrief")
        if 'form_data' not in st.session_state:
            st.session_state.form_data = {"origen": "", "destino": "", "ruta": "", "no_vuelo": "", "tiempo": 0.0, "puerta_salida": "", "puerta_llegada": ""}

        with st.expander("📥 Importar desde SimBrief", expanded=True):
            c1, c2 = st.columns([3, 1])
            sb_user = c1.text_input("Usuario SimBrief")
            if c2.button("Importar OFP"):
                datos, err = obtener_datos_simbrief(sb_user)
                if datos:
                    st.session_state.form_data.update(datos)
                    st.session_state.form_data["tiempo"] = datos["tiempo_est"]
                    st.success("¡Datos cargados!")
                else: st.error(err)

        st.markdown("#### Aerolínea")
        if "nueva_aerolinea_modo" not in st.session_state: st.session_state["nueva_aerolinea_modo"] = False
        if "aerolinea_seleccionada" not in st.session_state: st.session_state["aerolinea_seleccionada"] = AEROLINEAS_BASE[0]

        col_aero1, col_aero2 = st.columns([3, 1])
        with col_aero2:
            st.session_state["nueva_aerolinea_modo"] = st.toggle("➕ Nueva aerolínea", value=st.session_state["nueva_aerolinea_modo"])
        with col_aero1:
            if st.session_state["nueva_aerolinea_modo"]:
                nueva_aero_input = st.text_input("Nombre de la nueva aerolínea", key="nueva_aero_input")
                if nueva_aero_input.strip():
                    st.session_state["aerolinea_seleccionada"] = nueva_aero_input.strip()
            else:
                lista_aero = obtener_aerolineas_inteligente()
                idx_default = lista_aero.index(st.session_state["aerolinea_seleccionada"]) if st.session_state["aerolinea_seleccionada"] in lista_aero else 0
                st.session_state["aerolinea_seleccionada"] = st.selectbox("Seleccionar aerolínea", lista_aero, index=idx_default)

        st.markdown("---")
        with st.form("vuelo"):
            c1, c2, c3 = st.columns(3)
            with c1:
                fecha = st.date_input("Fecha", value=datetime.now())
                origen = st.text_input("Origen (ICAO)", value=st.session_state.form_data["origen"]).upper()
                destino = st.text_input("Destino (ICAO)", value=st.session_state.form_data["destino"]).upper()
                modelo = st.selectbox("Avión", MODELOS_AVION)
            with c2:
                h_out = st.time_input("Hora OUT", value=time(12, 0), step=60)
                h_in = st.time_input("Hora IN", value=time(14, 0), step=60)
                tiempo = st.number_input("Horas de vuelo", step=0.1, min_value=0.0, value=st.session_state.form_data["tiempo"])
            with c3:
                num = st.text_input("N° Vuelo", value=st.session_state.form_data["no_vuelo"])
                g1, g2 = st.columns(2)
                p_out = g1.text_input("Gate Sal.", value=st.session_state.form_data["puerta_salida"])
                p_in = g2.text_input("Gate Lleg.", value=st.session_state.form_data["puerta_llegada"])
                l_rate = st.number_input("Landing Rate (fpm)", value=0, step=10)

            ruta = st.text_area("Ruta", value=st.session_state.form_data["ruta"], height=80)
            notas = st.text_area("Notas", height=80)
            submitted = st.form_submit_button("💾 Guardar Vuelo")

        if submitted:
            c_orig = obtener_coords(origen)
            c_dest = obtener_coords(destino)
            distancia = round(haversine_nm(c_orig[0], c_orig[1], c_dest[0], c_dest[1])) if c_orig and c_dest else 0
            row = [str(fecha), origen, destino, ruta, st.session_state["aerolinea_seleccionada"], num, modelo, 
                   h_out.strftime("%H:%M"), h_in.strftime("%H:%M"), f"{tiempo:.2f}", distancia, p_out, p_in, l_rate, notas]
            with st.spinner("Guardando en la nube..."):
                if guardar_vuelo_gs(row):
                    st.success(f"✅ Vuelo {origen}→{destino} registrado correctamente.")
                else: st.error("Error al guardar.")

    # =========================================================
    # 2. CHECKLISTS
    # =========================================================
    elif menu == "✅ Checklists":
        st.header("✅ Listas de Chequeo")
        avion = st.selectbox("Avión:", list(CHECKLISTS_DB.keys()))
        data = CHECKLISTS_DB[avion]
        c1, c2 = st.columns(2)
        items = list(data.items())
        half = len(items) // 2
        for k, v in items[:half]:
            with c1.expander(k, True):
                for i in v: st.checkbox(i, key=f"{avion}{k}{i}")
        for k, v in items[half:]:
            with c2.expander(k, True):
                for i in v: st.checkbox(i, key=f"{avion}{k}{i}")

    # =========================================================
    # 3. MAPA
    # =========================================================
    elif menu == "🗺️ Mapa":
        st.header("🗺️ Historial de Rutas")
        df = leer_vuelos()
        if not df.empty:
            m = folium.Map(location=[20, 0], zoom_start=2, tiles="CartoDB dark_matter")
            for i, r in df.iterrows():
                o_c, d_c = obtener_coords(str(r['Origen']).strip()), obtener_coords(str(r['Destino']).strip())
                if o_c and d_c:
                    folium.PolyLine(get_geodesic_path(o_c[0], o_c[1], d_c[0], d_c[1]), color="#39ff14", weight=3, opacity=0.7).add_to(m)
            st_folium(m, width=1100, height=600)
        else: st.info("No hay vuelos registrados.")

    # =========================================================
    # 4. VUELOS ALEATORIOS (CONECTADO A LA API EN VIVO)
    # =========================================================
    elif menu == "🎲 Vuelos Aleatorios":
        st.header("📡 Generador de Vuelos en Vivo (AeroDataBox)")
        st.caption("Obteniendo vuelos comerciales programados en este exacto momento desde hubs internacionales.")

        # Campo para ingresar la API Key
        api_key_input = st.text_input(
            "🔑 RapidAPI Key", 
            type="password", 
            help="Ingresá tu API Key de RapidAPI (AeroDataBox). Puedes registrarte gratis en RapidAPI para obtenerla."
        )

        if st.button("🎲 Buscar Vuelo Real", use_container_width=True):
            if not api_key_input:
                st.warning("⚠️ Ingresá tu API Key para buscar tráfico en vivo.")
            else:
                with st.spinner("Escaneando radares para buscar un vuelo comercial aleatorio..."):
                    v, error = obtener_vuelo_real_api(api_key_input)
                    if error:
                        st.error(error)
                    else:
                        st.session_state["vuelo_random"] = v

        v = st.session_state.get("vuelo_random")
        if v:
            st.divider()
            c_card1, c_card2 = st.columns([3, 2])
            with c_card1:
                st.markdown(f"## 🛫 {v['origen']}  →  🛬 {v['destino']}")
                st.markdown(f"**{v['aerolinea']}** — Vuelo `{v['num']}`")
                st.markdown(f"_{v['info']}_")

            with c_card2:
                st.metric("✈️ Equipo Registrado", v["avion"])

            # Mapa del vuelo generado
            c_orig, c_dest = obtener_coords(v["origen"]), obtener_coords(v["destino"])
            if c_orig and c_dest:
                st.divider()
                m_rand = folium.Map(location=[(c_orig[0]+c_dest[0])/2, (c_orig[1]+c_dest[1])/2], zoom_start=3, tiles="CartoDB dark_matter")
                folium.PolyLine(get_geodesic_path(c_orig[0], c_orig[1], c_dest[0], c_dest[1]), color="#39ff14", weight=3).add_to(m_rand)
                folium.Marker(c_orig, icon=folium.Icon(color="green", icon="plane", prefix="fa")).add_to(m_rand)
                folium.Marker(c_dest, icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa")).add_to(m_rand)
                dist_nm = round(haversine_nm(c_orig[0], c_orig[1], c_dest[0], c_dest[1]))
                st_folium(m_rand, width=900, height=380)
                st.caption(f"📏 Distancia gran círculo: **{dist_nm} NM**")

            st.divider()
            if st.button("📋 Cargar en el Registro", use_container_width=True):
                st.session_state.form_data = {
                    "origen": v["origen"], "destino": v["destino"], "ruta": "", 
                    "no_vuelo": v["num"], "tiempo": 0.0, "puerta_salida": "", "puerta_llegada": ""
                }
                st.session_state["aerolinea_seleccionada"] = v["aerolinea"]
                st.success(f"✅ Vuelo {v['num']} cargado. Andá al Registro de Vuelo para completarlo.")

    # =========================================================
    # 5. ESTADÍSTICAS (Actualizado)
    # =========================================================
    elif menu == "📊 Estadísticas":
        st.header("📊 Dashboard de Rendimiento")
        df = leer_vuelos()
        
        if not df.empty:
            if 'Modelo_Avion' in df.columns:
                st.subheader("✈️ Histograma de Flota Utilizada")
                data_aviones = df['Modelo_Avion'].value_counts().reset_index()
                data_aviones.columns = ['Modelo', 'Vuelos']
                
                # Gráfico de barras simple (Histograma de Aviones)
                fig_bar = px.bar(
                    data_aviones, 
                    x='Modelo', 
                    y='Vuelos', 
                    text='Vuelos', 
                    color='Vuelos', 
                    title="Distribución de uso por modelo de aeronave"
                )
                fig_bar.update_traces(textposition='outside')
                st.plotly_chart(fig_bar, use_container_width=True)

            st.markdown("---")
            st.subheader("📋 Historial Completo")

            col_exp1, col_exp2 = st.columns([3, 1])
            with col_exp2:
                if st.button("📥 Exportar CSV"):
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button("Descargar CSV", csv, "vuelos.csv", "text/csv")

            with st.expander("Ver / Editar historial", expanded=True):
                for i, row in df.iterrows():
                    with st.container():
                        cols = st.columns([2, 2, 2, 2, 1, 1])
                        cols[0].write(f"**{row.get('Origen','?')} → {row.get('Destino','?')}**")
                        cols[1].write(f"{row.get('Fecha','')}")
                        cols[2].write(f"{row.get('Aerolinea','')}")
                        cols[3].write(f"{row.get('Modelo_Avion','')}")
                        cols[4].write(f"{float(row.get('Tiempo_Vuelo_Horas',0)):.1f}h")
                        
                        if cols[5].button("🗑️", key=f"del_{i}", help="Eliminar este vuelo"):
                            st.session_state[f"confirm_del_{i}"] = True

                        if st.session_state.get(f"confirm_del_{i}", False):
                            st.warning(f"¿Eliminar vuelo {row.get('Origen','?')}→{row.get('Destino','?')}?")
                            c_yes, c_no = st.columns(2)
                            if c_yes.button("✅ Sí, eliminar", key=f"yes_{i}"):
                                if eliminar_vuelo_gs(i):
                                    st.success("Vuelo eliminado.")
                                    st.session_state.pop(f"confirm_del_{i}", None)
                                    st.rerun()
                            if c_no.button("❌ Cancelar", key=f"no_{i}"):
                                st.session_state.pop(f"confirm_del_{i}", None)
                                st.rerun()
                    st.divider()
        else:
            st.info("Aún no registraste vuelos.")

if __name__ == "__main__":
    main_app()
