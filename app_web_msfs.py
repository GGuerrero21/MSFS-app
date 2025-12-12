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

MODELOS_AVION = [
    "Avro RJ/BAe 146", "ATR 42-600", "ATR 72-600", "Airbus A319", "Airbus A320", "Airbus A320 Neo", "Airbus A321 Neo", 
    "Airbus A330-900", "Airbus A340-600", "Airbus A350-900", "Airbus A350-1000", "Airbus A380-800", 
    "Boeing 737-600", "Boeing 737-700", "Boeing 737-800", "Boeing 737-900", "Boeing 747-8", 
    "Boeing 777-200", "Boeing 777-200LR", "Boeing 777-300ER", "Boeing 777F", "Boeing 787-8", 
    "Boeing 787-9", "Boeing 787-10", "Embraer E170", "Embraer E190", "Embraer E195"
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
    # Asegura que el ICAO esté limpio y en mayúsculas
    if isinstance(icao, str):
        return AIRPORT_COORDS.get(icao.strip().upper(), None)
    return None

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
    # crear_archivo_csv() <-- YA NO ES NECESARIO

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
                h_out = st.text_input("Hora OUT (UTC)", max_chars=4)
                h_in = st.text_input("Hora IN (UTC)", max_chars=4)
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
                    row = [fecha, origen, destino, ruta, aero, num, modelo, h_out, h_in, f"{tiempo:.2f}", 0, p_out, p_in, l_rate, notas]
                    
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

    # 3. MAPA
    elif menu == "🗺️ Mapa":
        st.header("🗺️ Historial de Rutas")
        df = leer_vuelos()
        if not df.empty:
            start_loc = [20, 0] # Coordenada default
            m = folium.Map(location=start_loc, zoom_start=2, tiles="CartoDB dark_matter")
            
            rutas_dibujadas = 0
            for _, r in df.iterrows():
                try:
                    # Limpieza de datos (upper() y strip() para quitar espacios)
                    origen_limpio = str(r['Origen']).strip().upper()
                    destino_limpio = str(r['Destino']).strip().upper()
                    
                    c1 = obtener_coords(origen_limpio)
                    c2 = obtener_coords(destino_limpio)
                    
                    if c1 and c2:
                        # Línea de ruta
                        folium.PolyLine([c1, c2], color="#39ff14", weight=3, opacity=0.8, tooltip=f"{origen_limpio}-{destino_limpio}").add_to(m)
                        # Puntos
                        folium.CircleMarker(c1, radius=3, color="white", fill=True, fill_opacity=1).add_to(m)
                        folium.CircleMarker(c2, radius=3, color="#ff3914", fill=True, fill_opacity=1).add_to(m)
                        rutas_dibujadas += 1
                except: pass
            
            st_folium(m, width=1000, height=500)
            
            if rutas_dibujadas == 0:
                st.warning("⚠️ No se dibujaron rutas. Verifica que los códigos ICAO de origen/destino (ej: KJFK, SCEL) estén en la base de datos de coordenadas en el código.")
        else: st.info("Sin vuelos registrados.")

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
            st.title("🎓 Guía de Lectura METAR")
            st.markdown("Aquí iría la guía completa...") # Abreviado para no alargar más

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

    # 6. ESTADÍSTICAS
    elif menu == "📊 Estadísticas":
        st.header("📊 Estadísticas de Piloto")
        df = leer_vuelos()
        if not df.empty:
            # Landing rate seguro
            if 'Landing_Rate_FPM' in df.columns:
                df['Landing_Rate_FPM'] = pd.to_numeric(df['Landing_Rate_FPM'], errors='coerce')
                avg_l = df['Landing_Rate_FPM'].mean()
                st.metric("Promedio de Toque (Landing Rate)", f"{avg_l:.0f} fpm" if not pd.isna(avg_l) else "N/A")
            
            st.markdown("---")
            
            c1, c2 = st.columns(2)
            
            # Gráfico Barras Corregido
            if 'Modelo_Avion' in df.columns:
                data_aviones = df['Modelo_Avion'].value_counts().reset_index()
                data_aviones.columns = ['Modelo', 'Cantidad']
                fig_bar = px.bar(data_aviones, x='Cantidad', y='Modelo', orientation='h', title="Vuelos por Avión", text='Cantidad')
                c1.plotly_chart(fig_bar, use_container_width=True)
            
            # Gráfico Pastel Corregido
            if 'Aerolinea' in df.columns:
                data_aero = df['Aerolinea'].value_counts().reset_index()
                data_aero.columns = ['Aerolinea', 'Vuelos']
                fig_pie = px.pie(data_aero, values='Vuelos', names='Aerolinea', title="Aerolíneas Preferidas", hole=0.3)
                c2.plotly_chart(fig_pie, use_container_width=True)
            
            st.dataframe(df)
        else: st.info("Registra vuelos para ver datos.")

if __name__ == "__main__":
    main_app()
