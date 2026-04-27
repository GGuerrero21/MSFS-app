import streamlit as st
import airportsdata
import numpy as np
import requests
import pandas as pd
import plotly.express as px
import folium
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from streamlit_folium import st_folium
from datetime import datetime, time

AIRPORTS_DB = airportsdata.load('ICAO')

# --- 1. DATOS ---

AIRPORT_COORDS = {
    "KJFK": [40.6413, -73.7781], "EGLL": [51.4700, -0.4543], "SCEL": [-33.3930, -70.7858],
    "SAEZ": [-34.8222, -58.5358], "LEMD": [40.4722, -3.5609], "SKBO": [4.7016, -74.1469],
    "MMMX": [19.4363, -99.0721], "KMIA": [25.7959, -80.2870], "KLAX": [33.9416, -118.4085],
    "EHAM": [52.3105, 4.7683], "LFPG": [49.0097, 2.5479], "OMDB": [25.2532, 55.3657],
    "RJAA": [35.7719, 140.3928], "YSSY": [-33.9399, 151.1753], "SBGR": [-23.4356, -46.4731],
    "SPJC": [-12.0219, -77.1143], "MPTO": [9.0714, -79.3835], "FACT": [-33.9715, 18.6021],
    "NZAA": [-37.0082, 174.7950], "NTAA": [-17.5536, -149.6070]
}

AEROLINEAS_BASE = sorted([
    "Aer Lingus", "Aeroflot", "Aerolíneas Argentinas", "Aeroméxico", "Air Canada", "Air China",
    "Air Corsica", "Air Europa", "Air France", "Air India", "Air Mauritius", "Air New Zealand",
    "Air Transat", "Alaska Airlines", "Air Cairo", "Alitalia (ITA Airways)", "All Nippon Airways (ANA)",
    "American Airlines", "Asiana Airlines", "Atlas Air (Cargo)", "Austrian Airlines", "Avianca",
    "Azul Brazilian Airlines", "Boliviana de Aviación", "British Airways", "Brussels Airlines",
    "Cathay Pacific", "Cebu Pacific", "China Airlines", "China Eastern Airlines",
    "China Southern Airlines", "Copa Airlines", "Delta Air Lines", "Delta Connection",
    "DHL Aviation", "EasyJet", "EasyJet Europe", "EgyptAir", "El Al", "Emirates",
    "Ethiopian Airlines", "Etihad Airways", "Eurowings", "EVA Air", "FedEx Express", "Finnair",
    "Flydubai", "Frontier Airlines", "Garuda Indonesia", "GOL Linhas Aéreas", "Gulf Air",
    "Hainan Airlines", "Hawaiian Airlines", "Iberia", "Icelandair", "IndiGo",
    "Japan Airlines (JAL)", "JetBlue", "Jetstar", "JetSmart", "Juneyao Air", "Kenya Airways",
    "KLM", "Korean Air", "LATAM Airlines", "LATAM Airlines Brasil", "Lion Air",
    "LOT Polish Airlines", "Lufthansa", "Malaysia Airlines", "Norwegian Air Shuttle", "Oman Air",
    "Philippine Airlines", "Qantas", "Qatar Airways", "Rossiya Airlines", "Royal Air Maroc",
    "Royal Jordanian", "Ryanair", "SAS (Scandinavian Airlines)", "Saudia", "Scoot",
    "Singapore Airlines", "Sky Airline", "South African Airways", "Southwest Airlines",
    "SpiceJet", "Spirit Airlines", "SriLankan Airlines", "Starlux Airlines",
    "Swiss International Air Lines", "TAP Air Portugal", "Thai Airways", "Turkish Airlines",
    "Uganda Airlines", "United Airlines", "UPS Airlines", "VietJet Air", "Vietnam Airlines",
    "Virgin Atlantic", "Virgin Australia", "Volaris", "Vueling", "WestJet", "Wizz Air",
    "XiamenAir", "Peach Aviation"
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
    },
    "Regional / GA (ATR/Embraer/Cessna)": {
        "Pre-Start": ["Pre-flight Inspection: COMPLETED", "Seats/Belts: ADJUSTED/LOCKED", "Fuel Selector: BOTH/AUTO"],
        "Start": ["Master Switch/Bat: ON", "Beacon: ON", "Pumps: ON", "Ignition/Start: START"],
        "Before Takeoff": ["Flaps: SET", "Trim: SET FOR T/O", "Flight Controls: FREE & CORRECT", "Transponder: ALT"]
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
        # Auto-crear headers si el sheet está vacío
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
    """Lee desde Google Sheets con caché de 30 segundos."""
    sheet = conectar_google_sheets()
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            if df.empty:
                return pd.DataFrame()
            cols_num = ['Tiempo_Vuelo_Horas', 'Distancia_NM', 'Landing_Rate_FPM']
            for col in cols_num:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception as e:
            st.error(f"Error leyendo datos: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

def guardar_vuelo_gs(row_data):
    sheet = conectar_google_sheets()
    if sheet:
        try:
            row_str = [str(x) for x in row_data]
            sheet.append_row(row_str)
            leer_vuelos.clear()  # Limpiar caché después de guardar
            return True
        except Exception as e:
            st.error(f"Error guardando: {e}")
            return False
    return False

def eliminar_vuelo_gs(row_index):
    """Elimina una fila por índice (1-based, incluyendo header)."""
    sheet = conectar_google_sheets()
    if sheet:
        try:
            sheet.delete_rows(row_index + 2)  # +2 porque row 1 es header y gspread es 1-based
            leer_vuelos.clear()
            return True
        except Exception as e:
            st.error(f"Error eliminando: {e}")
            return False
    return False

def actualizar_vuelo_gs(row_index, row_data):
    """Actualiza una fila completa por índice."""
    sheet = conectar_google_sheets()
    if sheet:
        try:
            row_str = [str(x) for x in row_data]
            # Fila en el sheet = index + 2 (1 de header + 1 de base 1)
            sheet.update(f"A{row_index + 2}", [row_str])
            leer_vuelos.clear()
            return True
        except Exception as e:
            st.error(f"Error actualizando: {e}")
            return False
    return False

# --- 3. FUNCIONES LÓGICAS ---

def get_geodesic_path(lat1, lon1, lat2, lon2, n_points=100):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    if c == 0:
        return [[np.degrees(lat1), np.degrees(lon1)], [np.degrees(lat2), np.degrees(lon2)]]
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
    """Calcula distancia en millas náuticas entre dos coordenadas."""
    R = 3440.065  # Radio de la Tierra en NM
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def calcular_rango_xp(df):
    horas = 0
    if not df.empty and 'Tiempo_Vuelo_Horas' in df.columns:
        df['Tiempo_Vuelo_Horas'] = pd.to_numeric(df['Tiempo_Vuelo_Horas'], errors='coerce').fillna(0)
        horas = df['Tiempo_Vuelo_Horas'].sum()
    if horas < 10: return "Cadete", "🎓", horas, 10
    elif horas < 50: return "Primer Oficial", "👨‍✈️", horas, 50
    elif horas < 150: return "Capitán", "⭐⭐", horas, 150
    elif horas < 500: return "Comandante Senior", "⭐⭐⭐⭐", horas, 500
    else: return "Leyenda del Aire", "👑", horas, 1000

def obtener_datos_simbrief(username):
    if not username:
        return None, "Ingresa un usuario."
    url = f"https://www.simbrief.com/api/xml.fetcher.php?username={username}&json=1"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            general = data.get('general', {})
            origin_data = data.get('origin', {})
            dest_data = data.get('destination', {})
            times = data.get('times', {})
            est_time = int(times.get('est_block', 0)) / 3600
            dep_time = datetime.utcfromtimestamp(int(times.get('sched_out', 0))).strftime('%H:%M') if times.get('sched_out') else "12:00"
            return {
                "origen": origin_data.get('icao_code', ''),
                "destino": dest_data.get('icao_code', ''),
                "no_vuelo": f"{general.get('icao_airline', '')}{general.get('flight_number', '')}",
                "ruta": general.get('route', ''),
                "tiempo_est": est_time,
                "puerta_salida": origin_data.get('gate', 'TBD'),
                "puerta_llegada": dest_data.get('gate', 'TBD'),
                "hora_salida": dep_time,
                "fecha": datetime.now().strftime("%d %b %Y").upper()
            }, None
        else:
            return None, "Error al conectar con SimBrief."
    except Exception as e:
        return None, f"Excepción: {e}"

def obtener_aerolineas_inteligente():
    """
    Combina la lista base con aerolíneas guardadas en el sheet,
    incluyendo las agregadas manualmente por el usuario.
    """
    lista = set(AEROLINEAS_BASE)
    df = leer_vuelos()
    if not df.empty and 'Aerolinea' in df.columns:
        for a in df['Aerolinea'].dropna().unique():
            a_clean = a.strip()
            if a_clean:
                lista.add(a_clean)
    return sorted(list(lista))

def obtener_coords(icao):
    if not isinstance(icao, str):
        return None
    codigo = icao.strip().upper()
    aeropuerto = AIRPORTS_DB.get(codigo)
    if aeropuerto:
        return [aeropuerto['lat'], aeropuerto['lon']]
    return AIRPORT_COORDS.get(codigo, None)

def obtener_clima(icao_code):
    if not icao_code or len(icao_code) != 4:
        return None, "❌ ICAO inválido."
    base_url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations"
    taf_url = "https://tgftp.nws.noaa.gov/data/forecasts/taf/stations"
    headers = {'User-Agent': 'MSFS2020-App/1.0'}
    try:
        r_metar = requests.get(f"{base_url}/{icao_code.upper()}.TXT", headers=headers, timeout=5)
        raw_metar = r_metar.text.strip().split('\n')[1] if r_metar.status_code == 200 else "No disponible"
    except:
        raw_metar = "Error conexión"
    try:
        r_taf = requests.get(f"{taf_url}/{icao_code.upper()}.TXT", headers=headers, timeout=5)
        raw_taf = "\n".join(r_taf.text.strip().split('\n')[1:]) if r_taf.status_code == 200 else "No disponible"
    except:
        raw_taf = "Error conexión"
    if raw_metar == "No disponible" and raw_taf == "No disponible":
        return None, "❌ No se encontraron datos."
    return (raw_metar, raw_taf), None

def calcular_viento_cruzado(wind_dir, wind_spd, rwy_heading):
    diff = abs(wind_dir - rwy_heading)
    theta = math.radians(diff)
    return abs(math.sin(theta) * wind_spd), math.cos(theta) * wind_spd

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
            h3 { font-size: 2rem !important; }
            .stTextInput > div > div > input { font-size: 18px !important; }
            .stSelectbox > div > div > div { font-size: 18px !important; }
            .stNumberInput > div > div > input { font-size: 18px !important; }
            textarea { font-size: 18px !important; }
            .stButton > button { font-size: 20px !important; padding: 10px 24px !important; font-weight: bold !important; }
            button[data-baseweb="tab"] { font-size: 18px !important; }
            [data-testid="stSidebar"] { font-size: 18px !important; }
            </style>
        """, unsafe_allow_html=True)

    # SIDEBAR
    st.sidebar.title("👨‍✈️ Perfil")
    df_log = leer_vuelos()
    rango, icono, horas_act, horas_next = calcular_rango_xp(df_log)

    # Detectar subida de rango
    rango_prev = st.session_state.get("rango_anterior", rango)
    if rango_prev != rango:
        st.balloons()
        st.success(f"🎉 ¡Subiste de rango! Ahora eres **{rango}** {icono}")
        st.session_state["rango_anterior"] = rango
    else:
        st.session_state["rango_anterior"] = rango

    st.sidebar.markdown(f"### {icono} {rango}")
    st.sidebar.metric("Horas Totales", f"{horas_act:.1f} h")
    if horas_next != 1000:
        st.sidebar.progress(min(horas_act / horas_next, 1.0))
        st.sidebar.caption(f"Próximo rango en {horas_next - horas_act:.1f} h")

    # Resumen del último vuelo
    if not df_log.empty:
        st.sidebar.markdown("---")
        st.sidebar.markdown("**✈️ Último vuelo**")
        ultimo = df_log.iloc[-1]
        orig = ultimo.get('Origen', '???')
        dest = ultimo.get('Destino', '???')
        horas_v = float(ultimo.get('Tiempo_Vuelo_Horas', 0))
        lrate = int(float(ultimo.get('Landing_Rate_FPM', 0)))
        modelo_v = ultimo.get('Modelo_Avion', '')
        st.sidebar.caption(f"🛫 {orig} → {dest}")
        st.sidebar.caption(f"⏱️ {horas_v:.1f} h  |  🛬 {lrate} fpm")
        if modelo_v:
            st.sidebar.caption(f"✈️ {modelo_v}")

    st.sidebar.markdown("---")
    menu = st.sidebar.radio("EFB Menu", [
        "📋 Registro de Vuelo", "✅ Checklists", "🗺️ Mapa",
        "☁️ Clima (METAR/TAF)", "🧰 Herramientas", "📊 Estadísticas"
    ])

    # =========================================================
    # 1. REGISTRO DE VUELO
    # =========================================================
    if menu == "📋 Registro de Vuelo":
        st.header("📋 Registrar Vuelo / SimBrief")

        if 'form_data' not in st.session_state:
            st.session_state.form_data = {
                "origen": "", "destino": "", "ruta": "", "no_vuelo": "",
                "tiempo": 0.0, "puerta_salida": "", "puerta_llegada": ""
            }

        # --- SimBrief ---
        with st.expander("📥 Importar desde SimBrief", expanded=True):
            c1, c2 = st.columns([3, 1])
            sb_user = c1.text_input("Usuario SimBrief")
            if c2.button("Importar OFP"):
                datos, err = obtener_datos_simbrief(sb_user)
                if datos:
                    st.session_state.form_data.update(datos)
                    st.session_state.form_data["tiempo"] = datos["tiempo_est"]
                    st.success("¡Datos del plan de vuelo cargados!")
                else:
                    st.error(err)

        # --- SELECTOR DE AEROLÍNEA (FUERA del form para que funcione el checkbox) ---
        st.markdown("#### Aerolínea")

        # Inicializar estado si no existe
        if "nueva_aerolinea_modo" not in st.session_state:
            st.session_state["nueva_aerolinea_modo"] = False
        if "aerolinea_seleccionada" not in st.session_state:
            st.session_state["aerolinea_seleccionada"] = AEROLINEAS_BASE[0]

        col_aero1, col_aero2 = st.columns([3, 1])
        with col_aero2:
            nueva_modo = st.toggle("➕ Nueva aerolínea", value=st.session_state["nueva_aerolinea_modo"])
            st.session_state["nueva_aerolinea_modo"] = nueva_modo

        with col_aero1:
            if st.session_state["nueva_aerolinea_modo"]:
                nueva_aero_input = st.text_input(
                    "Nombre de la nueva aerolínea",
                    placeholder="Ej: Air Patagonia",
                    key="nueva_aero_input"
                )
                if nueva_aero_input.strip():
                    st.session_state["aerolinea_seleccionada"] = nueva_aero_input.strip()
                    st.caption(f"✅ Se guardará como: **{nueva_aero_input.strip()}**")
                else:
                    st.caption("⚠️ Escribí el nombre para continuar")
            else:
                lista_aero = obtener_aerolineas_inteligente()
                idx_default = 0
                if st.session_state["aerolinea_seleccionada"] in lista_aero:
                    idx_default = lista_aero.index(st.session_state["aerolinea_seleccionada"])
                aero_sel = st.selectbox("Seleccionar aerolínea", lista_aero, index=idx_default)
                st.session_state["aerolinea_seleccionada"] = aero_sel

        st.markdown("---")

        # --- FORMULARIO PRINCIPAL ---
        with st.form("vuelo"):
            c1, c2, c3 = st.columns(3)
            with c1:
                fecha = st.date_input("Fecha", value=datetime.now())
                origen = st.text_input("Origen (ICAO)", value=st.session_state.form_data["origen"]).upper()
                destino = st.text_input("Destino (ICAO)", value=st.session_state.form_data["destino"]).upper()
                modelo = st.selectbox("Avión", MODELOS_AVION)
            with c2:
                h_out = st.time_input("Hora OUT (UTC)", value=time(12, 0), step=60)
                h_in = st.time_input("Hora IN (UTC)", value=time(14, 0), step=60)
                tiempo = st.number_input("Horas de vuelo", step=0.1, min_value=0.0, value=st.session_state.form_data["tiempo"])
            with c3:
                num = st.text_input("N° Vuelo", value=st.session_state.form_data["no_vuelo"])
                g1, g2 = st.columns(2)
                p_out = g1.text_input("Gate Salida", value=st.session_state.form_data["puerta_salida"])
                p_in = g2.text_input("Gate Llegada", value=st.session_state.form_data["puerta_llegada"])
                l_rate = st.number_input("Landing Rate (fpm)", value=0, step=10)

            st.markdown("---")
            ruta = st.text_area("Ruta", value=st.session_state.form_data["ruta"], height=80)
            notas = st.text_area("Notas", height=80)

            submitted = st.form_submit_button("💾 Guardar Vuelo")

        # Procesar fuera del form para evitar reruns problemáticos
        if submitted:
            aero_final = st.session_state["aerolinea_seleccionada"]

            if tiempo <= 0:
                st.error("❌ Las horas de vuelo deben ser mayores a 0.")
            elif not origen or len(origen) < 3:
                st.error("❌ Ingresá un código ICAO de origen válido.")
            elif not destino or len(destino) < 3:
                st.error("❌ Ingresá un código ICAO de destino válido.")
            elif st.session_state["nueva_aerolinea_modo"] and not aero_final:
                st.error("❌ Escribí el nombre de la nueva aerolínea.")
            else:
                # Calcular distancia real
                c_orig = obtener_coords(origen)
                c_dest = obtener_coords(destino)
                distancia = 0
                if c_orig and c_dest:
                    distancia = round(haversine_nm(c_orig[0], c_orig[1], c_dest[0], c_dest[1]))

                row = [
                    str(fecha), origen, destino, ruta, aero_final, num, modelo,
                    h_out.strftime("%H:%M"), h_in.strftime("%H:%M"),
                    f"{tiempo:.2f}", distancia, p_out, p_in, l_rate, notas
                ]
                with st.spinner("Guardando en la nube..."):
                    exito = guardar_vuelo_gs(row)
                if exito:
                    dist_txt = f" ({distancia} NM)" if distancia > 0 else ""
                    st.success(f"✅ Vuelo {origen}→{destino}{dist_txt} registrado correctamente.")
                    # Resetear modo nueva aerolínea
                    st.session_state["nueva_aerolinea_modo"] = False
                else:
                    st.error("Error al guardar en la nube.")

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
                for i in v:
                    st.checkbox(i, key=f"{avion}{k}{i}")
        for k, v in items[half:]:
            with c2.expander(k, True):
                for i in v:
                    st.checkbox(i, key=f"{avion}{k}{i}")
        if st.button("Reset"):
            st.rerun()

    # =========================================================
    # 3. MAPA
    # =========================================================
    elif menu == "🗺️ Mapa":
        st.header("🗺️ Historial de Rutas")
        df = leer_vuelos()
        if not df.empty:
            col_map1, col_map2, col_map3 = st.columns([1, 1, 2])
            with col_map1:
                mostrar_iconos = st.toggle("Mostrar Iconos 📍", value=True)
            # Filtro por aerolínea
            aeros_disp = ["Todas"] + sorted(df['Aerolinea'].dropna().unique().tolist()) if 'Aerolinea' in df.columns else ["Todas"]
            with col_map2:
                filtro_aero = st.selectbox("Aerolínea", aeros_disp)

            df_mapa = df if filtro_aero == "Todas" else df[df['Aerolinea'] == filtro_aero]

            m = folium.Map(location=[20, 0], zoom_start=2, tiles="CartoDB dark_matter")
            rutas_dibujadas = 0
            aeropuertos_faltantes = set()

            for i, r in df_mapa.iterrows():
                origen = str(r['Origen']).strip().upper()
                destino = str(r['Destino']).strip().upper()
                c1 = obtener_coords(origen)
                c2 = obtener_coords(destino)
                if c1 and c2:
                    ruta_curva = get_geodesic_path(c1[0], c1[1], c2[0], c2[1])
                    folium.PolyLine(ruta_curva, color="#39ff14", weight=3, opacity=0.7,
                                   tooltip=f"✈️ {origen} → {destino}").add_to(m)
                    if mostrar_iconos:
                        folium.Marker(c1, popup=folium.Popup(f"🛫 {origen}", max_width=200),
                                      icon=folium.Icon(color="green", icon="plane", prefix="fa"),
                                      tooltip=origen).add_to(m)
                        folium.Marker(c2, popup=folium.Popup(f"🛬 {destino}", max_width=200),
                                      icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"),
                                      tooltip=destino).add_to(m)
                    rutas_dibujadas += 1
                else:
                    if not c1: aeropuertos_faltantes.add(origen)
                    if not c2: aeropuertos_faltantes.add(destino)

            st_folium(m, width=1100, height=600)
            if aeropuertos_faltantes:
                st.warning(f"⚠️ Faltan coordenadas para: {', '.join(aeropuertos_faltantes)}")
            st.caption(f"✅ Mostrando {rutas_dibujadas} rutas.")
        else:
            st.info("No hay vuelos registrados.")

    # =========================================================
    # 4. CLIMA
    # =========================================================
    elif menu == "☁️ Clima (METAR/TAF)":
        st.header("🌤️ Centro Meteorológico")
        tab1, tab2 = st.tabs(["🔍 Buscar Clima", "🎓 Escuela Meteorológica"])
        with tab1:
            with st.form("metar_search"):
                col_s1, col_s2 = st.columns([3, 1])
                icao = col_s1.text_input("Código ICAO", max_chars=4).upper()
                if col_s2.form_submit_button("Buscar 🔎") and icao:
                    datos, err = obtener_clima(icao)
                    if datos:
                        metar, taf = datos
                        st.success(f"Reporte encontrado para **{icao}**")
                        st.info(f"**METAR:**\n`{metar}`")
                        st.warning(f"**TAF:**\n`{taf}`")
                    else:
                        st.error(err)
        with tab2:
            st.title("🎓 Guía Definitiva de Lectura METAR/TAF")
            with st.expander("1. Estructura Básica (Ejemplo)", expanded=True):
                st.markdown("""
                **Ejemplo:** `SCEL 091400Z 18010KT 9999 SCT030 18/12 Q1016`
                1. **Lugar:** `SCEL` (Santiago, Chile).
                2. **Fecha/Hora:** `091400Z` → Día 09, 14:00 Hora Zulú (UTC).
                3. **Viento:** `18010KT` → Dirección 180° a 10 Nudos.
                4. **Visibilidad:** `9999` → Más de 10 km.
                5. **Nubes:** `SCT030` → Nubes dispersas a 3000 pies.
                6. **Temp:** `18/12` → 18°C temperatura, 12°C punto de rocío.
                7. **Presión:** `Q1016` → 1016 hPa.
                """)
            with st.expander("2. Fenómenos Meteorológicos"):
                cols = st.columns(3)
                with cols[0]:
                    st.markdown("**Precipitación**\n* `RA`: Lluvia\n* `SN`: Nieve\n* `GR`: Granizo\n* `DZ`: Llovizna")
                with cols[1]:
                    st.markdown("**Oscurecimiento**\n* `FG`: Niebla <1km\n* `BR`: Neblina 1-5km\n* `HZ`: Bruma\n* `FU`: Humo")
                with cols[2]:
                    st.markdown("**Intensidad**\n* `-`: Ligero\n* `+`: Fuerte\n* `TS`: Tormenta\n* `VC`: En vecindad")
            with st.expander("3. Cobertura de Nubes"):
                st.markdown("""
                | Código | Significado | Cobertura |
                |:---|:---|:---|
                | **FEW** | Escasas | 1/8 a 2/8 |
                | **SCT** | Dispersas | 3/8 a 4/8 |
                | **BKN** | Fragmentadas (Ceiling) | 5/8 a 7/8 |
                | **OVC** | Cubierto | 8/8 |
                | **NSC/SKC** | Sin nubes | Despejado |
                """)
            with st.expander("4. TAF: BECMG, TEMPO, FM"):
                st.markdown("""
                * **BECMG:** Cambio gradual y permanente.
                * **TEMPO:** Cambio temporal, luego vuelve a normal.
                * **FM:** Cambio rápido y total desde una hora exacta.
                * **PROB30/40:** Probabilidad del 30% o 40%.
                """)
            with st.expander("5. Especiales: CAVOK, VRB, G"):
                st.markdown("""
                * **CAVOK:** Condiciones ideales. Visibilidad >10km, sin nubes bajo 5000ft.
                * **VRB:** Viento variable (generalmente <5kt).
                * **G (Gusts):** Ráfagas. Ej: `24015G25KT`.
                * **NSW:** El mal tiempo terminó.
                """)

    # =========================================================
    # 5. HERRAMIENTAS
    # =========================================================
    elif menu == "🧰 Herramientas":
        st.header("🧰 Herramientas de Vuelo")
        t1, t2, t3, t4 = st.tabs(["🌬️ Viento Cruzado", "📉 Calc. Descenso", "🔄 Conversor", "⛽ Combustible"])
        with t1:
            st.subheader("Calculadora de Viento Cruzado")
            wc1, wc2, wc3 = st.columns(3)
            wd = wc1.number_input("Dirección Viento (°)", 0, 360, 0)
            ws = wc2.number_input("Velocidad Viento (kt)", 0, 100, 0)
            rwy = wc3.number_input("Rumbo de Pista (°)", 0, 360, 0)
            if ws > 0:
                cw, hw = calcular_viento_cruzado(wd, ws, rwy)
                col_r1, col_r2 = st.columns(2)
                col_r1.metric("Viento Cruzado", f"{cw:.1f} kt")
                col_r2.metric("Viento Cara/Cola", f"{hw:.1f} kt", delta="Favorável" if hw > 0 else "En cola")
        with t2:
            st.subheader("Calculadora TOD (Top of Descent)")
            c_alt, c_tgt = st.columns(2)
            alt_act = c_alt.number_input("Altitud Actual (ft)", value=35000, step=1000)
            alt_tgt = c_tgt.number_input("Altitud Objetivo (ft)", value=3000, step=1000)
            if alt_act > alt_tgt:
                dist = (alt_act - alt_tgt) * 3 / 1000
                st.success(f"📍 Iniciar descenso a **{dist:.0f} NM** del destino.")
                st.caption("Regla de los 3: 3 NM por cada 1000 ft a descender.")
        with t3:
            st.subheader("Conversor Rápido")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                kg = st.number_input("Kg → Lbs", value=0.0, step=0.1)
                st.caption(f"= **{kg * 2.20462:.1f} lbs**")
                ft = st.number_input("Pies → Metros", value=0.0, step=100.0)
                st.caption(f"= **{ft * 0.3048:.1f} m**")
            with col_c2:
                kt = st.number_input("Nudos → km/h", value=0.0, step=1.0)
                st.caption(f"= **{kt * 1.852:.1f} km/h**")
                nm = st.number_input("NM → km", value=0.0, step=1.0)
                st.caption(f"= **{nm * 1.852:.1f} km**")
        with t4:
            st.subheader("⛽ Calculadora de Combustible")
            st.caption("Planificación básica de combustible para simulación.")
            fc1, fc2, fc3 = st.columns(3)
            trip_fuel = fc1.number_input("Trip Fuel (kg)", value=5000, step=100)
            cont_pct = fc2.slider("Contingencia (%)", 0, 10, 5)
            altn_fuel = fc3.number_input("Alternado (kg)", value=1500, step=100)
            final_rsv = st.number_input("Reserva Final (kg)", value=1500, step=100)
            taxi_fuel = st.number_input("Taxi / Rodaje (kg)", value=200, step=50)

            cont_fuel = trip_fuel * cont_pct / 100
            min_fuel = trip_fuel + cont_fuel + altn_fuel + final_rsv
            block_fuel = min_fuel + taxi_fuel

            st.markdown("---")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Contingencia", f"{cont_fuel:.0f} kg")
            r2.metric("Mínimo Embarque", f"{min_fuel:.0f} kg")
            r3.metric("Block Fuel", f"{block_fuel:.0f} kg")
            r4.metric("Block Fuel (lbs)", f"{block_fuel * 2.205:.0f} lbs")

    # =========================================================
    # 6. ESTADÍSTICAS
    # =========================================================
    elif menu == "📊 Estadísticas":
        st.header("📊 Dashboard de Rendimiento")
        df = leer_vuelos()
        if not df.empty:
            if 'Landing_Rate_FPM' in df.columns:
                df['Landing_Rate_FPM'] = pd.to_numeric(df['Landing_Rate_FPM'], errors='coerce')
            if 'Tiempo_Vuelo_Horas' in df.columns:
                df['Tiempo_Vuelo_Horas'] = pd.to_numeric(df['Tiempo_Vuelo_Horas'], errors='coerce')
            if 'Distancia_NM' in df.columns:
                df['Distancia_NM'] = pd.to_numeric(df['Distancia_NM'], errors='coerce').fillna(0)

            # KPIs
            kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
            total_vuelos = len(df)
            total_horas = df['Tiempo_Vuelo_Horas'].sum()
            promedio_landing = df['Landing_Rate_FPM'].mean()
            total_nm = df['Distancia_NM'].sum()
            avion_fav = df['Modelo_Avion'].mode()[0] if 'Modelo_Avion' in df.columns and not df['Modelo_Avion'].mode().empty else "N/A"

            kpi1.metric("📦 Vuelos", f"{total_vuelos}")
            kpi2.metric("⏱️ Horas", f"{total_horas:.1f} h")
            kpi3.metric("🌍 Distancia", f"{total_nm:,.0f} NM")
            kpi4.metric("🛬 Toque Prom.", f"{promedio_landing:.0f} fpm")
            kpi5.metric("✈️ Avión Fav.", avion_fav)

            st.markdown("---")

            # Gráfico temporal de horas por mes
            if 'Fecha' in df.columns:
                try:
                    df['Fecha_dt'] = pd.to_datetime(df['Fecha'], errors='coerce')
                    df_tiempo = df.dropna(subset=['Fecha_dt']).copy()
                    df_tiempo['Mes'] = df_tiempo['Fecha_dt'].dt.to_period('M').astype(str)
                    df_mensual = df_tiempo.groupby('Mes').agg(
                        Horas=('Tiempo_Vuelo_Horas', 'sum'),
                        Vuelos=('Fecha', 'count')
                    ).reset_index()
                    if not df_mensual.empty:
                        st.subheader("📈 Actividad por Mes")
                        fig_line = px.bar(df_mensual, x='Mes', y='Horas', text='Vuelos',
                                          title="Horas voladas por mes (número = cantidad de vuelos)")
                        fig_line.update_traces(textposition='outside')
                        st.plotly_chart(fig_line, use_container_width=True)
                except Exception:
                    pass

            c1, c2 = st.columns(2)
            with c1:
                if 'Modelo_Avion' in df.columns:
                    st.subheader("✈️ Flota Utilizada")
                    data_aviones = df['Modelo_Avion'].value_counts().reset_index()
                    data_aviones.columns = ['Modelo', 'Vuelos']
                    fig_bar = px.bar(data_aviones, x='Vuelos', y='Modelo', orientation='h',
                                     text='Vuelos', color='Vuelos', title="Vuelos por Modelo")
                    st.plotly_chart(fig_bar, use_container_width=True)
            with c2:
                if 'Aerolinea' in df.columns:
                    st.subheader("🌍 Aerolíneas")
                    data_aero = df['Aerolinea'].value_counts().reset_index()
                    data_aero.columns = ['Aerolinea', 'Vuelos']
                    fig_pie = px.pie(data_aero, values='Vuelos', names='Aerolinea',
                                     title="Distribución por Aerolínea", hole=0.4)
                    st.plotly_chart(fig_pie, use_container_width=True)

            # Historial con edición/eliminación
            st.markdown("---")
            st.subheader("📋 Historial Completo")

            col_exp1, col_exp2 = st.columns([3, 1])
            with col_exp2:
                if st.button("📥 Exportar CSV"):
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button("Descargar CSV", csv, "vuelos.csv", "text/csv")

            # Tabla con opción de eliminar
            with st.expander("Ver / Editar historial", expanded=True):
                df_display = df.copy()
                for i, row in df_display.iterrows():
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
                            st.warning(f"¿Eliminar vuelo {row.get('Origen','?')}→{row.get('Destino','?')} del {row.get('Fecha','')}?")
                            c_yes, c_no = st.columns(2)
                            if c_yes.button("✅ Sí, eliminar", key=f"yes_{i}"):
                                with st.spinner("Eliminando..."):
                                    ok = eliminar_vuelo_gs(i)
                                if ok:
                                    st.success("Vuelo eliminado.")
                                    st.session_state.pop(f"confirm_del_{i}", None)
                                    st.rerun()
                            if c_no.button("❌ Cancelar", key=f"no_{i}"):
                                st.session_state.pop(f"confirm_del_{i}", None)
                                st.rerun()
                    st.divider()
        else:
            st.info("Registra tu primer vuelo para ver las estadísticas.")


if __name__ == "__main__":
    main_app()
