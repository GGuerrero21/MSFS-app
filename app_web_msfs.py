import streamlit as st
# ... otros imports ...
import airportsdata
import numpy as np  # <--- NUEVO IMPORT
# ...
import airportsdata
import streamlit as st
# import csv  <-- YA NO NECESITAMOS CSV
import requests
import pandas as pd
import plotly.express as px
import folium
import math
import gspread # LIBRERIA NUEVA
from oauth2client.service_account import ServiceAccountCredentials # LIBRERIA NUEVA
from streamlit_folium import st_folium
from datetime import datetime
from datetime import time
# Cargar base de datos mundial de aeropuertos (Usando códigos ICAO de 4 letras)
AIRPORTS_DB = airportsdata.load('ICAO')

# --- 1. CONFIGURACIÓN Y DATOS ---

AIRPORT_COORDS = {
    "KJFK": [40.6413, -73.7781], "EGLL": [51.4700, -0.4543], "SCEL": [-33.3930, -70.7858],
    "SAEZ": [-34.8222, -58.5358], "LEMD": [40.4722, -3.5609], "SKBO": [4.7016, -74.1469],
    "MMMX": [19.4363, -99.0721], "KMIA": [25.7959, -80.2870], "KLAX": [33.9416, -118.4085],
    "EHAM": [52.3105, 4.7683], "LFPG": [49.0097, 2.5479], "OMDB": [25.2532, 55.3657],
    "RJAA": [35.7719, 140.3928], "YSSY": [-33.9399, 151.1753], "SBGR": [-23.4356, -46.4731],
    "SPJC": [-12.0219, -77.1143], "MPTO": [9.0714, -79.3835], "FACT": [-33.9715, 18.6021],
    "NZAA": [-37.0082, 174.7950], "NTAA": [-17.5536, -149.6070] 
}

AEROLINEAS_BASE = [
    "Aer Lingus", "Aeroflot", "Aerolíneas Argentinas", "Aeroméxico", "Air Canada", "Air China", "Air Corsica", 
    "Air Europa", "Air France", "Air India", "Air Mauritius", "Air New Zealand", "Air Transat", "Alaska Airlines", "Air Cairo", 
    "Alitalia (ITA Airways)", "All Nippon Airways (ANA)", "American Airlines", "Asiana Airlines", 
    "Atlas Air (Cargo)", "Austrian Airlines", "Avianca", "Azul Brazilian Airlines", "British Airways", 
    "Brussels Airlines", "Cathay Pacific", "Cebu Pacific", "China Airlines", "China Eastern Airlines", 
    "China Southern Airlines", "Copa Airlines", "Delta Air Lines", "Delta Connection", "DHL Aviation", "EasyJet", "EasyJet Europe",  
    "EgyptAir", "El Al", "Emirates", "Ethiopian Airlines", "Etihad Airways", "Eurowings", 
    "EVA Air", "FedEx Express", "Finnair", "Flydubai", "Frontier Airlines", "Garuda Indonesia", 
    "GOL Linhas Aéreas", "Gulf Air", "Hainan Airlines", "Hawaiian Airlines", "Iberia", "Icelandair", 
    "IndiGo", "Japan Airlines (JAL)", "JetBlue", "Jetstar", "JetSmart", "Juneyao Air", "Kenya Airways", "KLM", 
    "Korean Air", "LATAM Airlines", "LATAM Airlines Brasil", "Lion Air", "LOT Polish Airlines", "Lufthansa", "Malaysia Airlines", 
    "Norwegian Air Shuttle", "Oman Air", "Philippine Airlines", "Qantas", "Qatar Airways", "Rossiya Airlines", 
    "Royal Air Maroc", "Royal Jordanian", "Ryanair", "SAS (Scandinavian Airlines)", "Saudia", 
    "Scoot", "Singapore Airlines", "Sky Airline", "South African Airways", "Southwest Airlines", 
    "SpiceJet", "Spirit Airlines", "SriLankan Airlines", "Starlux Ailines", "Swiss International Air Lines", 
    "TAP Air Portugal", "Thai Airways", "Turkish Airlines","Uganda Airlines", "United Airlines", "UPS Airlines", 
    "VietJet Air", "Vietnam Airlines", "Virgin Atlantic", "Virgin Australia", "Volaris", 
    "Vueling", "WestJet", "Wizz Air", "XiamenAir", "Peach Aviation"
]

MODELOS_AVION = [
    "Avro RJ/BAe 146", "ATR 42-600", "ATR 72-600", "Airbus A319", "Airbus A320", "Airbus A320 Neo", "Airbus A321", "Airbus A321 Neo", 
    "Airbus A330-900", "Airbus A340-600", "Airbus A350-900", "Airbus A350-1000", "Airbus A380-800", 
    "Boeing 737-600", "Boeing 737-700", "Boeing 737-800", "Boeing 737 MAX 8", "Boeing 737-900", "Boeing 747-8", 
    "Boeing 777-200", "Boeing 777-200LR", "Boeing 777-300ER", "Boeing 777F", "Boeing 787-8", 
    "Boeing 787-9", "Boeing 787-10", "Embraer E170", "Embraer E175", "Embraer E190", "Embraer E195", "Shukhoi SuperJet 100"
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

# --- 2. FUNCIONES LÓGICAS (MODIFICADO PARA GOOGLE SHEETS) ---



def get_geodesic_path(lat1, lon1, lat2, lon2, n_points=100):
    """
    Calcula la ruta curva (ortodrómica) y corrige el cruce del Pacífico.
    """
    # 1. Convertir a radianes
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

    # 2. Calcular la distancia angular (fórmula Haversine simplificada para dirección)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    
    if c == 0: return [[np.degrees(lat1), np.degrees(lon1)], [np.degrees(lat2), np.degrees(lon2)]]

    # 3. Generar puntos intermedios
    f = np.linspace(0, 1, n_points)
    A = np.sin((1 - f) * c) / np.sin(c)
    B = np.sin(f * c) / np.sin(c)
    
    x = A * np.cos(lat1) * np.cos(lon1) + B * np.cos(lat2) * np.cos(lon2)
    y = A * np.cos(lat1) * np.sin(lon1) + B * np.cos(lat2) * np.sin(lon2)
    z = A * np.sin(lat1) + B * np.sin(lat2)

    lat_i = np.arctan2(z, np.sqrt(x**2 + y**2))
    lon_i = np.arctan2(y, x)

    # 4. EL TRUCO MÁGICO: Unwrap corrige el salto de 180 a -180
    # Esto hace que la longitud sea continua (ej: 179, 180, 181...) en vez de saltar a -179
    lon_i = np.unwrap(lon_i)

    # 5. Convertir a grados y retornar lista de pares [lat, lon]
    return np.stack([np.degrees(lat_i), np.degrees(lon_i)], axis=1).tolist()
# Configuración de conexión
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def conectar_google_sheets():
    """Conecta con Google Sheets usando los secretos de Streamlit"""
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("⚠️ No se encontraron los secretos de Google Cloud. Configúralos en Streamlit Cloud.")
            return None
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], SCOPE)
        client = gspread.authorize(creds)
        # Abre la hoja llamada 'FlightLogbook'
        sheet = client.open("FlightLogbook").sheet1 
        return sheet
    except Exception as e:
        st.error(f"Error conectando a Google Sheets: {e}")
        return None

def leer_vuelos():
    """Lee los datos directamente desde Google Sheets"""
    sheet = conectar_google_sheets()
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            
            # Si el DataFrame está vacío, retornamos vacío
            if df.empty: return pd.DataFrame()

            # Asegurar que las columnas numéricas sean números (Google Sheets a veces devuelve texto)
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
    """Guarda una nueva fila en Google Sheets"""
    sheet = conectar_google_sheets()
    if sheet:
        try:
            # Convertimos todo a string para evitar errores de formato JSON
            row_str = [str(x) for x in row_data]
            sheet.append_row(row_str)
            return True
        except Exception as e:
            st.error(f"Error guardando: {e}")
            return False
    return False

def calcular_rango_xp(df):
    if df.empty: horas = 0
    else: 
        if 'Tiempo_Vuelo_Horas' in df.columns:
            df['Tiempo_Vuelo_Horas'] = pd.to_numeric(df['Tiempo_Vuelo_Horas'], errors='coerce').fillna(0)
            horas = df['Tiempo_Vuelo_Horas'].sum()
        else:
            horas = 0
    
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
            general = data.get('general', {})
            origin_data = data.get('origin', {})
            dest_data = data.get('destination', {})
            
            origin = origin_data.get('icao_code', '')
            destination = dest_data.get('icao_code', '')
            flight_no = f"{general.get('icao_airline', '')}{general.get('flight_number', '')}"
            route = general.get('route', '')
            gate_out = origin_data.get('gate', 'TBD')
            gate_in = dest_data.get('gate', 'TBD')
            times = data.get('times', {})
            est_time = int(times.get('est_block', 0)) / 3600
            
            # Hora estimada salida
            dep_time = datetime.utcfromtimestamp(int(times.get('sched_out', 0))).strftime('%H:%M') if times.get('sched_out') else "12:00"

            return {
                "origen": origin, "destino": destination, "no_vuelo": flight_no,
                "ruta": route, "tiempo_est": est_time, "aerolinea_icao": general.get('icao_airline', 'UNK'),
                "puerta_salida": gate_out, "puerta_llegada": gate_in,
                "hora_salida": dep_time,
                "fecha": datetime.now().strftime("%d %b %Y").upper()
            }, None
        else: return None, "Error al conectar con SimBrief."
    except Exception as e: return None, f"Excepción: {e}"

def obtener_aerolineas_inteligente():
    lista = set(AEROLINEAS_BASE)
    df = leer_vuelos()
    if not df.empty and 'Aerolinea' in df.columns:
        for a in df['Aerolinea'].dropna().unique(): lista.add(a.strip())
    return sorted(list(lista))

def obtener_coords(icao):
    """
    Busca las coordenadas en la base de datos mundial airportsdata.
    """
    if not isinstance(icao, str):
        return None
    
    codigo = icao.strip().upper()
    
    # 1. Buscar en la base de datos mundial
    aeropuerto = AIRPORTS_DB.get(codigo)
    
    if aeropuerto:
        # La librería devuelve lat/lon, lo convertimos a lista [lat, lon]
        return [aeropuerto['lat'], aeropuerto['lon']]
    
    # 2. (Opcional) Si no está en la base mundial, busca en tu diccionario manual
    # Esto sirve por si vas a una pista de tierra que no sale en los mapas oficiales
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
    except: raw_metar = "Error conexión"

    try:
        r_taf = requests.get(f"{taf_url}/{icao_code.upper()}.TXT", headers=headers, timeout=5)
        raw_taf = "\n".join(r_taf.text.strip().split('\n')[1:]) if r_taf.status_code == 200 else "No disponible"
    except: raw_taf = "Error conexión"
    
    if raw_metar == "No disponible" and raw_taf == "No disponible":
        return None, "❌ No se encontraron datos."
    return (raw_metar, raw_taf), None

def calcular_viento_cruzado(wind_dir, wind_spd, rwy_heading):
    diff = abs(wind_dir - rwy_heading)
    theta = math.radians(diff)
    crosswind = abs(math.sin(theta) * wind_spd)
    headwind = math.cos(theta) * wind_spd
    return crosswind, headwind

# --- 3. INTERFAZ GRÁFICA ---

def main_app():
    st.set_page_config(page_title="MSFS EFB Ultimate", layout="wide", page_icon="✈️")

    # --- INICIO DEL BLOQUE DE ESTILO ---

    # Interruptor en la barra lateral para activar el modo grande
    modo_grande = st.sidebar.toggle("👁️ Modo Texto Grande", value=False)

    if modo_grande:
        st.markdown("""
            <style>
            /* 1. Aumentar tamaño base de todo el texto */
            html, body, [class*="css"]  {
                font-size: 20px !important;
            }
            
            /* 2. Títulos más grandes */
            h1 { font-size: 3rem !important; }
            h2 { font-size: 2.5rem !important; }
            h3 { font-size: 2rem !important; }
            
            /* 3. Inputs, Cajas de texto y Selectores */
            .stTextInput > div > div > input { font-size: 18px !important; }
            .stSelectbox > div > div > div { font-size: 18px !important; }
            .stNumberInput > div > div > input { font-size: 18px !important; }
            textarea { font-size: 18px !important; }
            
            /* 4. Botones más grandes y fáciles de clicar */
            .stButton > button {
                font-size: 20px !important;
                padding: 10px 24px !important;
                font-weight: bold !important;
            }
            
            /* 5. Aumentar la fuente de las pestañas (Tabs) */
            button[data-baseweb="tab"] {
                font-size: 18px !important;
            }
            
            /* 6. Aumentar la letra de la Sidebar */
            [data-testid="stSidebar"] {
                font-size: 18px !important;
            }
            </style>
            """, unsafe_allow_html=True)
    # --- FIN DEL BLOQUE DE ESTILO ---

    # ... AQUÍ SIGUE EL RESTO DE TU CÓDIGO (SIDEBAR, MENU, ETC) ...
    # st.sidebar.title("👨‍✈️ Perfil")
    # ...

    # SIDEBAR
    st.sidebar.title("👨‍✈️ Perfil")
    df_log = leer_vuelos()
    rango, icono, horas_act, horas_next = calcular_rango_xp(df_log)
    st.sidebar.markdown(f"### {icono} {rango}")
    st.sidebar.metric("Horas Totales", f"{horas_act:.1f} h")
    if horas_next != 1000:
        st.sidebar.progress(min(horas_act / horas_next, 1.0))
        st.sidebar.caption(f"Próximo rango en {horas_next - horas_act:.1f} h")
    
    st.sidebar.markdown("---")
    menu = st.sidebar.radio("EFB Menu", ["📋 Registro de Vuelo", "✅ Checklists", "🗺️ Mapa", "☁️ Clima (METAR/TAF)", "🧰 Herramientas", "📊 Estadísticas"])

    # 1. REGISTRO
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
                    st.success("¡Datos del plan de vuelo cargados!")
                else: st.error(err)

        with st.form("vuelo"):
            c1, c2, c3 = st.columns(3)
            with c1:
                fecha = st.date_input("Fecha", value=datetime.now())
                origen = st.text_input("Origen", value=st.session_state.form_data["origen"]).upper()
                destino = st.text_input("Destino", value=st.session_state.form_data["destino"]).upper()
                modelo = st.selectbox("Avión", MODELOS_AVION)
            with c2:
                h_out = st.time_input("Hora OUT (UTC)", value=time(12, 0))
                h_in = st.time_input("Hora IN (UTC)", value=time(14, 0))
                tiempo = st.number_input("Horas", step=0.1, value=st.session_state.form_data["tiempo"])
            with c3:
                lista_aero = obtener_aerolineas_inteligente()
                if st.checkbox("¿Nueva Aerolínea?"): aero = st.text_input("Nombre")
                else: aero = st.selectbox("Aerolínea", lista_aero)
                num = st.text_input("N° Vuelo", value=st.session_state.form_data["no_vuelo"])
                g1, g2 = st.columns(2)
                p_out = g1.text_input("Gate Salida", value=st.session_state.form_data["puerta_salida"])
                p_in = g2.text_input("Gate Llegada", value=st.session_state.form_data["puerta_llegada"])
            
            st.markdown("---")
            col_lrate, col_ruta = st.columns([1, 3])
            l_rate = col_lrate.number_input("Landing Rate (fpm)", value=0, step=10)
            ruta = col_ruta.text_area("Ruta", value=st.session_state.form_data["ruta"], height=100)
            notas = st.text_area("Notas")
            
            if st.form_submit_button("Guardar Vuelo 💾"):
                if tiempo > 0 and origen and destino:
                    # Datos a guardar
                    # Convertir a formato HH:MM
                    h_out_str = h_out.strftime("%H:%M")
                    h_in_str = h_in.strftime("%H:%M")
                    
                    row = [
                        fecha, origen, destino, ruta, aero, num, modelo,
                        h_out_str, h_in_str,
                        f"{tiempo:.2f}", 0, p_out, p_in, l_rate, notas
                    ]
                    
                    # --- GUARDADO EN GOOGLE SHEETS ---
                    with st.spinner("Guardando en la nube..."):
                        exito = guardar_vuelo_gs(row)
                    
                    if exito:
                        st.success("✅ Vuelo registrado en Google Sheets (Permanente)")
                        # Limpiar formulario (opcional)
                        # st.session_state.form_data = ...
                    else:
                        st.error("Error al guardar en la nube.")
                else: st.error("Faltan datos.")

    # 2. CHECKLISTS
    elif menu == "✅ Checklists":
        st.header("✅ Listas de Chequeo")
        avion = st.selectbox("Avión:", list(CHECKLISTS_DB.keys()))
        data = CHECKLISTS_DB[avion]
        c1, c2 = st.columns(2)
        items = list(data.items())
        half = len(items)//2
        for k, v in items[:half]: 
            with c1.expander(k, True): 
                for i in v: st.checkbox(i, key=f"{avion}{k}{i}")
        for k, v in items[half:]: 
            with c2.expander(k, True): 
                for i in v: st.checkbox(i, key=f"{avion}{k}{i}")
        if st.button("Reset"): st.rerun()

  # 3. MAPA (CON INTERRUPTOR ON/OFF PARA ICONOS)
    elif menu == "🗺️ Mapa":
        st.header("🗺️ Historial de Rutas")
        df = leer_vuelos()
        
        if not df.empty:
            # --- INTERRUPTOR DE ICONOS ---
            col_map1, col_map2 = st.columns([1, 4])
            with col_map1:
                mostrar_iconos = st.toggle("Mostrar Iconos 📍", value=True)
            
            # Centrar el mapa
            m = folium.Map(location=[20, 0], zoom_start=2, tiles="CartoDB dark_matter")
            
            rutas_dibujadas = 0
            aeropuertos_faltantes = set()

            for i, r in df.iterrows():
                origen = str(r['Origen']).strip().upper()
                destino = str(r['Destino']).strip().upper()
                
                c1 = obtener_coords(origen)
                c2 = obtener_coords(destino)
                
                if c1 and c2:
                    # 1. SIEMPRE DIBUJAR LA LÍNEA (Ruta)
                    ruta_curva = get_geodesic_path(c1[0], c1[1], c2[0], c2[1])
                    folium.PolyLine(
                        ruta_curva, 
                        color="#39ff14", 
                        weight=3, 
                        opacity=0.7,
                        tooltip=f"✈️ Vuelo: {origen} -> {destino}"
                    ).add_to(m)
                    
                    # 2. DIBUJAR MARCADORES SOLO SI EL INTERRUPTOR ESTÁ ENCENDIDO
                    if mostrar_iconos:
                        # Marcador de ORIGEN (Avión Verde)
                        folium.Marker(
                            location=c1,
                            popup=folium.Popup(f"🛫 Origen: <b>{origen}</b>", max_width=200),
                            icon=folium.Icon(color="green", icon="plane", prefix="fa"),
                            tooltip=origen
                        ).add_to(m)
                        
                        # Marcador de DESTINO (Bandera Roja)
                        folium.Marker(
                            location=c2,
                            popup=folium.Popup(f"🛬 Destino: <b>{destino}</b>", max_width=200),
                            icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"),
                            tooltip=destino
                        ).add_to(m)
                    
                    rutas_dibujadas += 1
                else:
                    if not c1: aeropuertos_faltantes.add(origen)
                    if not c2: aeropuertos_faltantes.add(destino)
            
            st_folium(m, width=1100, height=600)
            
            if aeropuertos_faltantes:
                st.warning(f"⚠️ Faltan coordenadas para: {', '.join(aeropuertos_faltantes)}")
            if rutas_dibujadas > 0:
                st.caption(f"✅ Se muestran {rutas_dibujadas} rutas voladas.")
                
        else: 
            st.info("No hay vuelos registrados.")
            
    # 4. CLIMA
    elif menu == "☁️ Clima (METAR/TAF)":
        st.header("🌤️ Centro Meteorológico")
        tab1, tab2 = st.tabs(["🔍 Buscar Clima", "🎓 Escuela Meteorológica"])
        
        with tab1:
            with st.form("metar_search"):
                col_s1, col_s2 = st.columns([3,1])
                icao = col_s1.text_input("Código ICAO", max_chars=4).upper()
                if col_s2.form_submit_button("Buscar 🔎") and icao:
                    datos, err = obtener_clima(icao)
                    if datos:
                        metar, taf = datos
                        st.success(f"Reporte encontrado para **{icao}**")
                        st.info(f"**METAR:**\n`{metar}`")
                        st.warning(f"**TAF:**\n`{taf}`")
                    else: st.error(err)
        
        with tab2:
            st.title("🎓 Guía Definitiva de Lectura METAR/TAF")
            
            with st.expander("1. Estructura Básica (Ejemplo)", expanded=True):
                st.markdown("""
                **Ejemplo:** `SCEL 091400Z 18010KT 9999 SCT030 18/12 Q1016`
                
                1.  **Lugar:** `SCEL` (Santiago, Chile).
                2.  **Fecha/Hora:** `091400Z` -> Día 09, 14:00 Hora Zulú (UTC).
                3.  **Viento:** `18010KT` -> Dirección 180° a 10 Nudos.
                4.  **Visibilidad:** `9999` -> Más de 10 kilómetros (OK).
                5.  **Nubes:** `SCT030` -> Nubes dispersas a 3000 pies.
                6.  **Temp:** `18/12` -> 18°C temperatura, 12°C punto de rocío.
                7.  **Presión:** `Q1016` -> 1016 hectopascales.
                """)
            
            with st.expander("2. Fenómenos Meteorológicos (Lluvia, Niebla...)"):
                st.write("Estos códigos aparecen después de la visibilidad si hay mal tiempo.")
                cols = st.columns(3)
                with cols[0]:
                    st.markdown("**Precipitación**")
                    st.markdown("""
                    * `RA`: Lluvia (Rain)
                    * `SN`: Nieve (Snow)
                    * `GR`: Granizo
                    * `DZ`: Llovizna (Drizzle)
                    """)
                with cols[1]:
                    st.markdown("**Oscurecimiento**")
                    st.markdown("""
                    * `FG`: Niebla (Fog) < 1km
                    * `BR`: Neblina (Mist) 1-5km
                    * `HZ`: Bruma (Haze)
                    * `FU`: Humo
                    """)
                with cols[2]:
                    st.markdown("**Intensidad / Otros**")
                    st.markdown("""
                    * `-`: Ligero (ej: `-RA`)
                    * `+`: Fuerte (ej: `+RA`)
                    * `TS`: Tormenta (Thunderstorm)
                    * `VC`: En vecindad (cerca)
                    """)

            with st.expander("3. Cobertura de Nubes y Techo"):
                st.info("⚠️ **Dato Importante:** Se considera 'Techo de Nubes' (Ceiling) a partir de BKN. Si dice FEW o SCT, técnicamente no hay techo.")
                st.markdown("""
                | Código | Significado | Cantidad de Cielo Cubierto |
                | :--- | :--- | :--- |
                | **FEW** | Escasas | 1/8 a 2/8 |
                | **SCT** | Dispersas | 3/8 a 4/8 |
                | **BKN** | Fragmentadas (Ceiling) | 5/8 a 7/8 |
                | **OVC** | Cubierto (Ceiling) | 8/8 (Cielo tapado) |
                | **NSC / SKC** | Sin Nubes | Cielo despejado |
                | **VV** | Visibilidad Vertical | Indefinido (Niebla total) |
                """)
                st.caption("Los números siempre indican altura en cientos de pies. `030` = 3000 pies.")

            with st.expander("4. Pronósticos (TAF): BECMG, TEMPO, FM"):
                st.write("El TAF te dice qué va a pasar en el futuro. Estas son las palabras clave:")
                st.markdown("""
                * **BECMG (Becoming):** Cambio **gradual y permanente**.
                    * *Ej: `BECMG 1012/1014` -> Entre las 12 y las 14Z el clima cambiará y se quedará así.*
                * **TEMPO (Temporary):** Cambio **temporal**.
                    * *Ej: `TEMPO 1820 TSRA` -> Entre las 18 y 20Z habrá tormentas por momentos, pero luego volverá a lo normal.*
                * **FM (From):** Cambio **rápido y total** a partir de una hora.
                    * *Ej: `FM120000` -> A partir de las 12:00 en punto, el clima será este...*
                * **PROB30 / PROB40:** Probabilidad del 30% o 40% de que ocurra algo.
                """)

            with st.expander("5. Códigos Especiales (CAVOK, VRB)"):
                st.markdown("""
                * **CAVOK (Ceiling And Visibility OK):** Condiciones ideales. Visibilidad >10km, sin nubes por debajo de 5000ft, sin lluvias.
                * **VRB (Variable):** El viento cambia de dirección constantemente (generalmente cuando es suave, menos de 5kt).
                * **G (Gusts):** Ráfagas. Ej: `24015G25KT` (Viento 15 nudos, ráfagas de 25).
                * **NSW (No Significant Weather):** El mal tiempo ha terminado.
                """)

    # 5. HERRAMIENTAS
    elif menu == "🧰 Herramientas":
        st.header("🧰 Herramientas de Vuelo")
        t1, t2, t3 = st.tabs(["🌬️ Viento Cruzado", "📉 Calc. Descenso", "🔄 Conversor"])
        with t1:
            st.subheader("Calculadora de Viento Cruzado")
            wc1, wc2, wc3 = st.columns(3)
            wd = wc1.number_input("Dirección Viento (°)", 0, 360, 0)
            ws = wc2.number_input("Velocidad Viento (kt)", 0, 100, 0)
            rwy = wc3.number_input("Rumbo de Pista (°)", 0, 360, 0)
            if ws > 0:
                cw, hw = calcular_viento_cruzado(wd, ws, rwy)
                st.write(f"**Viento Cruzado:** {cw:.1f} kts | **Viento Cara/Cola:** {hw:.1f} kts")
        with t2:
            st.subheader("Calculadora TOD")
            c_alt, c_tgt = st.columns(2)
            alt_act = c_alt.number_input("Altitud Actual (ft)", value=35000, step=1000)
            alt_tgt = c_tgt.number_input("Altitud Objetivo (ft)", value=3000, step=1000)
            if alt_act > alt_tgt:
                dist = (alt_act - alt_tgt) * 3 / 1000
                st.success(f"📍 Iniciar descenso a **{dist:.0f} NM**.")
        with t3:
            st.subheader("Conversor Rápido")
            kg = st.number_input("Kg a Lbs", value=0)
            st.caption(f"{kg} kg = {kg*2.20462:.1f} lbs")

# 6. ESTADÍSTICAS (KPIs + GRÁFICOS CLÁSICOS)
    elif menu == "📊 Estadísticas":
        st.header("📊 Dashboard de Rendimiento")
        df = leer_vuelos()
        
        if not df.empty:
            # --- PROCESAMIENTO DE DATOS ---
            if 'Landing_Rate_FPM' in df.columns:
                df['Landing_Rate_FPM'] = pd.to_numeric(df['Landing_Rate_FPM'], errors='coerce')
            if 'Tiempo_Vuelo_Horas' in df.columns:
                df['Tiempo_Vuelo_Horas'] = pd.to_numeric(df['Tiempo_Vuelo_Horas'], errors='coerce')

            # --- FILA 1: KPIs (Dashboard de Rendimiento) ---
            # Esto es lo que te gustó: los números grandes arriba
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            
            total_vuelos = len(df)
            total_horas = df['Tiempo_Vuelo_Horas'].sum()
            promedio_landing = df['Landing_Rate_FPM'].mean()
            # Calcular avión favorito
            avion_fav = df['Modelo_Avion'].mode()[0] if 'Modelo_Avion' in df.columns and not df['Modelo_Avion'].mode().empty else "N/A"

            kpi1.metric("📦 Vuelos Totales", f"{total_vuelos}")
            kpi2.metric("⏱️ Horas Acumuladas", f"{total_horas:.1f} h")
            
            # Color dinámico simple para el landing
            delta_color = "normal"
            if promedio_landing < 180: delta_color = "inverse" # Verde si es suave
            
            kpi3.metric("🛬 Toque Promedio", f"{promedio_landing:.0f} fpm", delta_color=delta_color)
            kpi4.metric("✈️ Avión Favorito", avion_fav)

            st.markdown("---")

            # --- FILA 2: GRÁFICOS PRINCIPALES ---
            c1, c2 = st.columns(2)
            
            with c1:
                # 1. Histograma de Aviones (Barras Horizontales)
                if 'Modelo_Avion' in df.columns:
                    st.subheader("✈️ Flota Utilizada")
                    data_aviones = df['Modelo_Avion'].value_counts().reset_index()
                    data_aviones.columns = ['Modelo', 'Vuelos']
                    
                    fig_bar = px.bar(
                        data_aviones, 
                        x='Vuelos', 
                        y='Modelo', 
                        orientation='h', 
                        text='Vuelos',
                        color='Vuelos', # Le da un toque de color sin ser exagerado
                        title="Vuelos por Modelo"
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

            with c2:
                # 2. Aerolíneas (Pastel Clásico)
                if 'Aerolinea' in df.columns:
                    st.subheader("🌍 Aerolíneas")
                    data_aero = df['Aerolinea'].value_counts().reset_index()
                    data_aero.columns = ['Aerolinea', 'Vuelos']
                    
                    fig_pie = px.pie(
                        data_aero, 
                        values='Vuelos', 
                        names='Aerolinea', 
                        title="Distribución por Aerolínea", 
                        hole=0.4
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

            # --- FILA 3: TABLA DE DATOS ---
            with st.expander("📋 Ver Historial Completo"):
                st.dataframe(df, use_container_width=True)
                
        else:
            st.info("Registra tu primer vuelo para ver las estadísticas.")

if __name__ == "__main__":
    main_app()





















