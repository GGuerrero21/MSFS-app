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
# En una app profesional, esto vendría de una base de datos real con miles de aeropuertos.
# Aquí he puesto los hubs más importantes para que el mapa funcione bien en ejemplos.
AIRPORT_COORDS = {
    "KJFK": [40.6413, -73.7781], "EGLL": [51.4700, -0.4543], "SCEL": [-33.3930, -70.7858],
    "SAEZ": [-34.8222, -58.5358], "LEMD": [40.4722, -3.5609], "SKBO": [4.7016, -74.1469],
    "MMMX": [19.4363, -99.0721], "KMIA": [25.7959, -80.2870], "KLAX": [33.9416, -118.4085],
    "EHAM": [52.3105, 4.7683], "LFPG": [49.0097, 2.5479], "OMDB": [25.2532, 55.3657],
    "RJAA": [35.7719, 140.3928], "YSSY": [-33.9399, 151.1753], "SBGR": [-23.4356, -46.4731],
    "SPJC": [-12.0219, -77.1143], "MPTO": [9.0714, -79.3835], "FACT": [-33.9715, 18.6021]
}

# Listas de Aerolíneas y Aviones (Resumidas para el ejemplo, pero completas en lógica)
AEROLINEAS_BASE = [
    "LATAM Airlines", "Iberia", "British Airways", "American Airlines", "Delta Air Lines", 
    "Lufthansa", "Air France", "Emirates", "Qatar Airways", "KLM", "Avianca", "Aeroméxico",
    "Copa Airlines", "Ryanair", "EasyJet", "Vueling", "Sky Airline", "JetSmart", "Qantas"
]

MODELOS_AVION = [
    "Airbus A320 Neo", "Airbus A321 Neo", "Airbus A330-900", "Boeing 737-800", "Boeing 747-8", 
    "Boeing 787-10", "Boeing 777-300ER", "Cessna 172 Skyhawk", "Daher TBM 930", "ATR 72-600"
]

# Base de Datos de Checklists Simplificadas
CHECKLISTS_DB = {
    "Airbus A320/A321/A330": {
        "Cockpit Prep": ["Batteries 1 & 2: ON", "Ext Pwr: ON (if avail)", "ADIRS: NAV", "Ext Lt: NAV/LOGO"],
        "Before Start": ["APU: START", "Seatbelts: ON", "Doors: CLOSED", "Beacon: ON", "Parking Brake: SET"],
        "Engine Start": ["Thrust Levers: IDLE", "Engine Mode: IGN/START", "Master 2: ON", "Master 1: ON"],
        "After Start": ["Engine Mode: NORM", "APU Bleed: OFF", "APU Master: OFF", "Flaps: SET T/O"],
        "Takeoff": ["Auto Brake: MAX", "T.O Config: TEST", "Landing Lights: ON"]
    },
    "Boeing 737/747/787": {
        "Pre-Flight": ["Battery: ON", "Standby Power: AUTO", "Hydraulics: NORM", "Pos Lights: STEADY"],
        "Before Start": ["Fuel Pumps: ON", "APU: START", "Anti-Collision Lt: ON", "Packs: OFF"],
        "Engine Start": ["Ignition: GND/CONT", "Start Switch: GRD", "Fuel Lever: IDLE DETENT"],
        "Before Taxi": ["Generators: ON", "Probe Heat: ON", "Packs: AUTO", "Flaps: SET"],
        "Takeoff": ["Auto Brake: RTO", "Transponder: TA/RA", "Landing Lights: ON"]
    },
    "General Aviation (Cessna/TBM)": {
        "Pre-Start": ["Pre-flight Inspection: COMPLETED", "Seats/Belts: ADJUSTED/LOCKED", "Fuel Selector: BOTH"],
        "Start": ["Master Switch: ON", "Beacon: ON", "Mixture: RICH", "Throttle: OPEN 1/4", "Magnetos: START"],
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
        # Asegurar numérico
        df['Tiempo_Vuelo_Horas'] = pd.to_numeric(df['Tiempo_Vuelo_Horas'], errors='coerce').fillna(0)
        horas = df['Tiempo_Vuelo_Horas'].sum()
    
    if horas < 10: return "Cadete", "🎓", horas, 10
    elif horas < 50: return "Primer Oficial", "👨‍✈️", horas, 50
    elif horas < 150: return "Capitán", "⭐⭐", horas, 150
    elif horas < 500: return "Comandante Senior", "⭐⭐⭐⭐", horas, 500
    else: return "Leyenda del Aire", "👑", horas, 1000

def obtener_datos_simbrief(username):
    """Conecta con la API de SimBrief y trae el último plan de vuelo."""
    if not username: return None, "Ingresa un usuario."
    
    url = f"https://www.simbrief.com/api/xml.fetcher.php?username={username}&json=1"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            # Extraer datos clave
            general = data.get('general', {})
            origin = data.get('origin', {}).get('icao_code', '')
            destination = data.get('destination', {}).get('icao_code', '')
            flight_no = f"{general.get('icao_airline', '')}{general.get('flight_number', '')}"
            route = general.get('route', '')
            
            # Calcular tiempos estimados (bloque a bloque)
            times = data.get('times', {})
            est_time = int(times.get('est_block', 0)) / 3600 # Segundos a Horas
            
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
    """Devuelve lat,lon del diccionario o None si no existe."""
    return AIRPORT_COORDS.get(icao, None)

# --- 3. INTERFAZ GRÁFICA (STREAMLIT) ---

def main_app():
    st.set_page_config(page_title="MSFS EFB Pro", layout="wide", page_icon="✈️")
    crear_archivo_csv()

    # --- SIDEBAR: PERFIL DE PILOTO ---
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

    # --- PESTAÑA 1: REGISTRO DE VUELO (CON SIMBRIEF) ---
    if menu == "📋 Registro de Vuelo":
        st.header("📋 Registrar Vuelo / Importar OFP")
        
        # Estado de sesión para los campos del formulario
        if 'form_data' not in st.session_state:
            st.session_state.form_data = {"origen": "", "destino": "", "ruta": "", "no_vuelo": "", "tiempo": 0.0}

        # Importador SimBrief
        with st.expander("📥 Importar desde SimBrief", expanded=True):
            col_sb1, col_sb2 = st.columns([3, 1])
            sb_user = col_sb1.text_input("Usuario SimBrief", placeholder="Ej: JSmith")
            if col_sb2.button("Importar OFP"):
                datos_sb, error = obtener_datos_simbrief(sb_user)
                if datos_sb:
                    st.session_state.form_data["origen"] = datos_sb["origen"]
                    st.session_state.form_data["destino"] = datos_sb["destino"]
                    st.session_state.form_data["ruta"] = datos_sb["ruta"]
                    st.session_state.form_data["no_vuelo"] = datos_sb["no_vuelo"]
                    st.session_state.form_data["tiempo"] = datos_sb["tiempo_est"]
                    st.success("✅ Datos de SimBrief cargados. Revisa el formulario abajo.")
                else:
                    st.error(error)

        # Formulario de Registro
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
                # Si SimBrief trajo tiempo, lo usamos como defecto
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
                # Lógica de guardado (similar a versiones anteriores)
                tiempo_final = t_manual
                # Intentar calcular por horas OUT/IN si existen
                if h_out and h_in and len(h_out)==4 and len(h_in)==4:
                    try:
                        d_out = datetime.strptime(h_out, "%H%M")
                        d_in = datetime.strptime(h_in, "%H%M")
                        if d_in < d_out: d_in += timedelta(days=1)
                        tiempo_final = (d_in - d_out).total_seconds() / 3600
                    except: pass
                
                if tiempo_final > 0 and origen and destino:
                    dist = 0 # (Aquí iría la función de distancia random o calculada)
                    nuevo_vuelo = [
                        fecha, origen, destino, ruta, aerolinea, vuelo_num, modelo, 
                        h_out, h_in, f"{tiempo_final:.2f}", dist, puerta, notas
                    ]
                    with open(NOMBRE_ARCHIVO, 'a', newline='', encoding='utf-8') as f:
                        csv.writer(f).writerow(nuevo_vuelo)
                    st.success("Vuelo registrado y XP sumada!")
                else:
                    st.error("Faltan datos obligatorios.")

    # --- PESTAÑA 2: CHECKLISTS INTERACTIVAS ---
    elif menu == "✅ Checklists":
        st.header("✅ Listas de Chequeo Interactivas")
        
        tipo_avion = st.selectbox("Selecciona la lista para tu avión:", list(CHECKLISTS_DB.keys()))
        checklist_data = CHECKLISTS_DB[tipo_avion]
        
        col_list1, col_list2 = st.columns(2)
        
        # Dividir fases de vuelo en dos columnas
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
        
        if st.button("Reiniciar Checklists"):
            st.experimental_rerun()

    # --- PESTAÑA 3: MAPA DE RUTAS (HISTORIAL) ---
    elif menu == "🗺️ Mapa de Rutas":
        st.header("🗺️ Mis Rutas Voladas")
        
        df = leer_vuelos()
        if df.empty:
            st.info("Registra vuelos para verlos en el mapa.")
        else:
            # Crear mapa base centrado en el Atlántico
            m = folium.Map(location=[20, -40], zoom_start=2, tiles="CartoDB dark_matter")
            
            rutas_dibujadas = 0
            
            for index, row in df.iterrows():
                try:
                    orig = row['Origen'].upper().strip()
                    dest = row['Destino'].upper().strip()
                    
                    c1 = obtener_coords(orig)
                    c2 = obtener_coords(dest)
                    
                    if c1 and c2:
                        # Dibujar línea
                        folium.PolyLine([c1, c2], color="#39ff14", weight=2, opacity=0.7, tooltip=f"{orig}-{dest}").add_to(m)
                        # Dibujar puntos
                        folium.CircleMarker(c1, radius=3, color="white", fill=True).add_to(m)
                        folium.CircleMarker(c2, radius=3, color="white", fill=True).add_to(m)
                        rutas_dibujadas += 1
                except: continue
            
            st_folium(m, width=1000, height=500)
            st.caption(f"Mostrando {rutas_dibujadas} rutas basadas en aeropuertos conocidos por el sistema.")
            if rutas_dibujadas < len(df):
                st.warning("⚠️ Algunas rutas no aparecen porque los aeropuertos no están en la base de datos de ejemplo (AIRPORT_COORDS). En una app real, esto se conectaría a una DB completa.")

    # --- PESTAÑA 4: METAR (Igual que antes) ---
    elif menu == "☁️ METAR":
        st.header("Consulta Meteorológica")
        icao = st.text_input("ICAO").upper()
        if st.button("Buscar"):
            url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
            try:
                r = requests.get(url, timeout=5)
                if r.status_code==200: st.info(r.text)
                else: st.error("No encontrado")
            except: st.error("Error conexión")

    # --- PESTAÑA 5: ESTADÍSTICAS (Logbook Visual) ---
    elif menu == "📊 Estadísticas":
        st.header("📊 Tu Carrera en Números")
        df = leer_vuelos()
        if not df.empty:
            df['Modelo_Avion'] = df['Modelo_Avion'].fillna('Desconocido')
            df['Aerolinea'] = df['Aerolinea'].fillna('General')
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Aviones Favoritos")
                top_aviones = df['Modelo_Avion'].value_counts().head(10)
                fig = px.bar(top_aviones, orientation='h', color=top_aviones.values)
                st.plotly_chart(fig, use_container_width=True)
            
            with c2:
                st.subheader("Aerolíneas")
                top_aero = df['Aerolinea'].value_counts().head(10)
                fig2 = px.pie(values=top_aero.values, names=top_aero.index, hole=0.4)
                st.plotly_chart(fig2, use_container_width=True)
                
            st.dataframe(df)
        else:
            st.info("Sin datos.")

if __name__ == "__main__":
    main_app()