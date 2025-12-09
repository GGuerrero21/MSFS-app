import streamlit as st
import csv
import random
import requests
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# --- 1. BASES DE DATOS Y CONFIGURACIÓN ---

# Coordenadas de Aeropuertos Principales (Para el mapa)
AIRPORT_COORDS = {
    "KJFK": [40.6413, -73.7781], "EGLL": [51.4700, -0.4543], "SCEL": [-33.3930, -70.7858],
    "SAEZ": [-34.8222, -58.5358], "LEMD": [40.4722, -3.5609], "SKBO": [4.7016, -74.1469],
    "MMMX": [19.4363, -99.0721], "KMIA": [25.7959, -80.2870], "KLAX": [33.9416, -118.4085],
    "EHAM": [52.3105, 4.7683], "LFPG": [49.0097, 2.5479], "OMDB": [25.2532, 55.3657],
    "RJAA": [35.7719, 140.3928], "YSSY": [-33.9399, 151.1753], "SBGR": [-23.4356, -46.4731],
    "SPJC": [-12.0219, -77.1143], "MPTO": [9.0714, -79.3835], "FACT": [-33.9715, 18.6021]
}

# --- LISTAS DEFINITIVAS (NO TOCAR) ---

# Lista Masiva de Aerolíneas
AEROLINEAS_BASE = [
    "Aer Lingus", "Aeroflot", "Aerolíneas Argentinas", "Aeroméxico", "Air Canada", "Air China", 
    "Air Europa", "Air France", "Air India", "Air New Zealand", "Air Transat", "Alaska Airlines", 
    "Alitalia (ITA Airways)", "All Nippon Airways (ANA)", "American Airlines", "Asiana Airlines", 
    "Atlas Air (Cargo)", "Austrian Airlines", "Avianca", "Azul Brazilian Airlines", "British Airways", 
    "Brussels Airlines", "Cathay Pacific", "Cebu Pacific", "China Airlines", "China Eastern Airlines", 
    "China Southern Airlines", "Copa Airlines", "Delta Air Lines", "DHL Aviation", "EasyJet", 
    "EgyptAir", "El Al", "Emirates", "Ethiopian Airlines", "Etihad Airways", "Eurowings", 
    "EVA Air", "FedEx Express", "Finnair", "Flydubai", "Frontier Airlines", "Garuda Indonesia", 
    "GOL Linhas Aéreas", "Gulf Air", "Hainan Airlines", "Hawaiian Airlines", "Iberia", "Icelandair", 
    "IndiGo", "Japan Airlines (JAL)", "JetBlue", "Jetstar", "JetSmart", "Kenya Airways", "KLM", 
    "Korean Air", "LATAM Airlines", "Lion Air", "LOT Polish Airlines", "Lufthansa", "Malaysia Airlines", 
    "Norwegian Air Shuttle", "Oman Air", "Philippine Airlines", "Qantas", "Qatar Airways", 
    "Royal Air Maroc", "Royal Jordanian", "Ryanair", "SAS (Scandinavian Airlines)", "Saudia", 
    "Scoot", "Singapore Airlines", "Sky Airline", "South African Airways", "Southwest Airlines", 
    "SpiceJet", "Spirit Airlines", "SriLankan Airlines", "Swiss International Air Lines", 
    "TAP Air Portugal", "Thai Airways", "Turkish Airlines", "United Airlines", "UPS Airlines", 
    "VietJet Air", "Vietnam Airlines", "Virgin Atlantic", "Virgin Australia", "Volaris", 
    "Vueling", "WestJet", "Wizz Air", "XiamenAir"
]

# Lista Específica de Modelos de Avión
MODELOS_AVION = [
    "ATR 42-600",
    "ATR 72-600",
    "Airbus A319",
    "Airbus A320",
    "Airbus A320 Neo",
    "Airbus A321 Neo",
    "Airbus A330-900",
    "Airbus A340-600",
    "Airbus A350-900",
    "Airbus A350-1000",
    "Airbus A380-800",
    "Boeing 737-600",
    "Boeing 737-700",
    "Boeing 737-800",
    "Boeing 737-900",
    "Boeing 747-8",
    "Boeing 777-200",
    "Boeing 777-200LR",
    "Boeing 777-300ER",
    "Boeing 777F",
    "Boeing 787-8",
    "Boeing 787-9",
    "Boeing 787-10",
    "Embraer E170",
    "Embraer E190",
    "Embraer E195"
]

# Base de Datos de Checklists
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

NOMBRE_ARCHIVO = 'mis_vuelos_msfs2020.csv'
ENCABEZADOS_CSV = [
    "Fecha", "Origen", "Destino", "Ruta", "Aerolinea", "No_Vuelo", "Modelo_Avion", 
    "Hora_OUT_UTC", "Hora_IN_UTC", "Tiempo_Vuelo_Horas", "Distancia_NM", "Puerta", "Notas"
]

# --- 2. FUNCIONES DE LÓGICA ---

def crear_archivo_csv():
    try:
        with open(NOMBRE_ARCHIVO, mode='x', newline='', encoding='utf-8') as archivo:
            csv.writer(archivo).writerow(ENCABEZADOS_CSV)
    except FileExistsError: pass

def leer_vuelos():
    try: return pd.read_csv(NOMBRE_ARCHIVO)
    except: return pd.DataFrame()

def calcular_rango_xp(df):
    """Calcula el rango basado en horas totales."""
    if df.empty: horas = 0
    else: 
        df['Tiempo_Vuelo_Horas'] = pd.to_numeric(df['Tiempo_Vuelo_Horas'], errors='coerce').fillna(0)
        horas = df['Tiempo_Vuelo_Horas'].sum()
    
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
            origin = data.get('origin', {}).get('icao_code', '')
            destination = data.get('destination', {}).get('icao_code', '')
            flight_no = f"{general.get('icao_airline', '')}{general.get('flight_number', '')}"
            route = general.get('route', '')
            times = data.get('times', {})
            est_time = int(times.get('est_block', 0)) / 3600
            
            return {
                "origen": origin, "destino": destination, "no_vuelo": flight_no,
                "ruta": route, "tiempo_est": est_time, "aerolinea_icao": general.get('icao_airline', '')
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
    return AIRPORT_COORDS.get(icao, None)

def obtener_metar(icao_code):
    """Función METAR robusta."""
    if not icao_code or len(icao_code) != 4:
        return "❌ Código ICAO no válido. Debe tener 4 letras."
        
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao_code.upper()}.TXT"
    
    try:
        headers = {'User-Agent': 'MSFS2020-Companion-App/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            
            fecha_obs = "Fecha desconocida"
            raw_metar = "METAR no encontrado."
            
            for line in lines:
                line = line.strip()
                if line.startswith('20'):
                    fecha_obs = line
                elif line.startswith(icao_code.upper()) or "KT" in line:
                    raw_metar = line

            if raw_metar == "METAR no encontrado." and len(lines) > 0:
                 raw_metar = " ".join(lines)

            resultado = (
                f"--- ☁️ METAR de **{icao_code.upper()}** ---\n"
                f"**Hora de Obs:** {fecha_obs}\n\n"
                f"**Raw:** `{raw_metar}`"
            )
            return resultado
        elif response.status_code == 404:
            return f"❌ No se encontró METAR para {icao_code.upper()}. (Código 404)"
        else:
            return f"❌ Error al obtener datos. Código de estado: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return f"❌ Error de conexión al obtener METAR: {e}"

# --- 3. INTERFAZ GRÁFICA (STREAMLIT) ---

def main_app():
    st.set_page_config(page_title="MSFS EFB Pro", layout="wide", page_icon="✈️")
    crear_archivo_csv()

    # --- SIDEBAR ---
    st.sidebar.title("👨‍✈️ Perfil de Piloto")
    df_log = leer_vuelos()
    rango, icono, horas_act, horas_next = calcular_rango_xp(df_log)
    
    st.sidebar.markdown(f"### {icono} {rango}")
    st.sidebar.metric("Horas Totales", f"{horas_act:.1f} h")
    if horas_next != 1000:
        progreso = min(horas_act / horas_next, 1.0)
        st.sidebar.progress(progreso)
        st.sidebar.caption(f"Próximo rango en {horas_next - horas_act:.1f} horas")
    
    st.sidebar.markdown("---")
    menu = st.sidebar.radio("EFB Menu", ["📋 Registro de Vuelo", "✅ Checklists", "🗺️ Mapa de Rutas", "☁️ METAR", "📊 Estadísticas"])

    # --- PESTAÑA 1: REGISTRO ---
    if menu == "📋 Registro de Vuelo":
        st.header("📋 Registrar Vuelo / Importar OFP")
        
        if 'form_data' not in st.session_state:
            st.session_state.form_data = {"origen": "", "destino": "", "ruta": "", "no_vuelo": "", "tiempo": 0.0}

        with st.expander("📥 Importar desde SimBrief", expanded=True):
            col_sb1, col_sb2 = st.columns([3, 1])
            sb_user = col_sb1.text_input("Usuario SimBrief", placeholder="Ej: JSmith")
            if col_sb2.button("Importar OFP"):
                datos_sb, error = obtener_datos_simbrief(sb_user)
                if datos_sb:
                    st.session_state.form_data.update(datos_sb)
                    st.session_state.form_data["tiempo"] = datos_sb["tiempo_est"]
                    st.success("✅ Datos cargados.")
                else:
                    st.error(error)

        with st.form("flight_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                fecha = st.date_input("Fecha", value=datetime.now())
                origen = st.text_input("Origen (ICAO)", value=st.session_state.form_data["origen"]).upper()
                destino = st.text_input("Destino (ICAO)", value=st.session_state.form_data["destino"]).upper()
                modelo = st.selectbox("Avión", MODELOS_AVION)
            
            with col2:
                h_out = st.text_input("Hora OUT (UTC HHMM)", max_chars=4)
                h_in = st.text_input("Hora IN (UTC HHMM)", max_chars=4)
                t_manual = st.number_input("Tiempo (Horas)", min_value=0.0, step=0.1, value=st.session_state.form_data["tiempo"])
            
            with col3:
                lista_aero = obtener_aerolineas_inteligente()
                manual_aero = st.checkbox("¿Aerolínea nueva?")
                if manual_aero: aerolinea = st.text_input("Nombre Aerolínea")
                else: aerolinea = st.selectbox("Aerolínea", lista_aero)
                vuelo_num = st.text_input("N° Vuelo", value=st.session_state.form_data["no_vuelo"])
                puerta = st.text_input("Puerta")

            ruta = st.text_area("Ruta", value=st.session_state.form_data["ruta"])
            notas = st.text_area("Notas")
            
            if st.form_submit_button("Guardar en Logbook 💾"):
                tiempo_final = t_manual
                if h_out and h_in and len(h_out)==4 and len(h_in)==4:
                    try:
                        d_out = datetime.strptime(h_out, "%H%M")
                        d_in = datetime.strptime(h_in, "%H%M")
                        if d_in < d_out: d_in += timedelta(days=1)
                        tiempo_final = (d_in - d_out).total_seconds() / 3600
                    except: pass
                
                if tiempo_final > 0 and origen and destino:
                    nuevo_vuelo = [
                        fecha, origen, destino, ruta, aerolinea, vuelo_num, modelo, 
                        h_out, h_in, f"{tiempo_final:.2f}", 0, puerta, notas
                    ]
                    with open(NOMBRE_ARCHIVO, 'a', newline='', encoding='utf-8') as f:
                        csv.writer(f).writerow(nuevo_vuelo)
                    st.success("Vuelo registrado y XP sumada!")
                else:
                    st.error("Faltan datos obligatorios.")

    # --- PESTAÑA 2: CHECKLISTS ---
    elif menu == "✅ Checklists":
        st.header("✅ Listas de Chequeo Interactivas")
        tipo_avion = st.selectbox("Selecciona la lista:", list(CHECKLISTS_DB.keys()))
        checklist_data = CHECKLISTS_DB[tipo_avion]
        col_list1, col_list2 = st.columns(2)
        fases = list(checklist_data.keys())
        mitad = len(fases) // 2
        
        with col_list1:
            for fase in fases[:mitad]:
                with st.expander(fase, expanded=True):
                    for item in checklist_data[fase]:
                        st.checkbox(item, key=f"{tipo_avion}_{fase}_{item}")
        with col_list2:
            for fase in fases[mitad:]:
                with st.expander(fase, expanded=True):
                    for item in checklist_data[fase]:
                        st.checkbox(item, key=f"{tipo_avion}_{fase}_{item}")
        
        if st.button("Reiniciar"):
            st.rerun()

    # --- PESTAÑA 3: MAPA ---
    elif menu == "🗺️ Mapa de Rutas":
        st.header("🗺️ Mis Rutas Voladas")
        df = leer_vuelos()
        if df.empty:
            st.info("Registra vuelos para verlos en el mapa.")
        else:
            m = folium.Map(location=[20, -40], zoom_start=2, tiles="CartoDB dark_matter")
            rutas_dibujadas = 0
            for index, row in df.iterrows():
                try:
                    orig = row['Origen'].upper().strip()
                    dest = row['Destino'].upper().strip()
                    c1 = obtener_coords(orig)
                    c2 = obtener_coords(dest)
                    if c1 and c2:
                        folium.PolyLine([c1, c2], color="#39ff14", weight=2, opacity=0.7).add_to(m)
                        folium.CircleMarker(c1, radius=3, color="white", fill=True).add_to(m)
                        folium.CircleMarker(c2, radius=3, color="white", fill=True).add_to(m)
                        rutas_dibujadas += 1
                except: continue
            st_folium(m, width=1000, height=500)
            if rutas_dibujadas < len(df):
                st.caption("Nota: Solo se muestran rutas entre aeropuertos que el sistema conoce por coordenadas.")

    # --- PESTAÑA 4: METAR ---
    elif menu == "☁️ METAR":
        st.header("Consulta Meteorológica")
        icao = st.text_input("ICAO (4 letras)", max_chars=4).upper()
        if st.button("Buscar"):
            st.markdown(obtener_metar(icao))

    # --- PESTAÑA 5: ESTADÍSTICAS ---
    elif menu == "📊 Estadísticas":
        st.header("📊 Tu Carrera en Números")
        df = leer_vuelos()
        if not df.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Aviones Favoritos")
                if 'Modelo_Avion' in df.columns:
                    top_aviones = df['Modelo_Avion'].value_counts().head(10)
                    fig = px.bar(top_aviones, orientation='h', color=top_aviones.values)
                    st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.subheader("Aerolíneas")
                if 'Aerolinea' in df.columns:
                    top_aero = df['Aerolinea'].value_counts().head(10)
                    fig2 = px.pie(values=top_aero.values, names=top_aero.index, hole=0.4)
                    st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(df)
        else:
            st.info("Sin datos.")

if __name__ == "__main__":
    main_app()