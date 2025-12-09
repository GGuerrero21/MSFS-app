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

AIRPORT_COORDS = {
    "KJFK": [40.6413, -73.7781], "EGLL": [51.4700, -0.4543], "SCEL": [-33.3930, -70.7858],
    "SAEZ": [-34.8222, -58.5358], "LEMD": [40.4722, -3.5609], "SKBO": [4.7016, -74.1469],
    "MMMX": [19.4363, -99.0721], "KMIA": [25.7959, -80.2870], "KLAX": [33.9416, -118.4085],
    "EHAM": [52.3105, 4.7683], "LFPG": [49.0097, 2.5479], "OMDB": [25.2532, 55.3657],
    "RJAA": [35.7719, 140.3928], "YSSY": [-33.9399, 151.1753], "SBGR": [-23.4356, -46.4731],
    "SPJC": [-12.0219, -77.1143], "MPTO": [9.0714, -79.3835], "FACT": [-33.9715, 18.6021]
}

# --- LISTAS DEFINITIVAS ---

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
    "ATR 42-600", "ATR 72-600", "Airbus A319", "Airbus A320", "Airbus A320 Neo", "Airbus A321 Neo", 
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

NOMBRE_ARCHIVO = 'mis_vuelos_msfs2020.csv'
ENCABEZADOS_CSV = [
    "Fecha", "Origen", "Destino", "Ruta", "Aerolinea", "No_Vuelo", "Modelo_Avion", 
    "Hora_OUT_UTC", "Hora_IN_UTC", "Tiempo_Vuelo_Horas", "Distancia_NM", "Puerta_Salida", "Puerta_Llegada", "Notas"
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
            origin_data = data.get('origin', {})
            dest_data = data.get('destination', {})
            
            origin = origin_data.get('icao_code', '')
            destination = dest_data.get('icao_code', '')
            flight_no = f"{general.get('icao_airline', '')}{general.get('flight_number', '')}"
            route = general.get('route', '')
            gate_out = origin_data.get('gate', '')
            gate_in = dest_data.get('gate', '')
            times = data.get('times', {})
            est_time = int(times.get('est_block', 0)) / 3600
            
            return {
                "origen": origin, "destino": destination, "no_vuelo": flight_no,
                "ruta": route, "tiempo_est": est_time, "aerolinea_icao": general.get('icao_airline', ''),
                "puerta_salida": gate_out, "puerta_llegada": gate_in
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
        return None, "❌ No se encontraron datos para esa estación."
    return (raw_metar, raw_taf), None

# --- 3. INTERFAZ GRÁFICA ---

def main_app():
    st.set_page_config(page_title="MSFS EFB Ultimate", layout="wide", page_icon="✈️")
    crear_archivo_csv()

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

        with st.expander("📥 Importar SimBrief", expanded=True):
            c1, c2 = st.columns([3, 1])
            sb_user = c1.text_input("Usuario SimBrief")
            if c2.button("Importar"):
                datos, err = obtener_datos_simbrief(sb_user)
                if datos:
                    st.session_state.form_data.update(datos)
                    st.session_state.form_data["tiempo"] = datos["tiempo_est"]
                    st.success("Cargado.")
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
            
            ruta = st.text_area("Ruta", value=st.session_state.form_data["ruta"])
            notas = st.text_area("Notas")
            
            if st.form_submit_button("Guardar Vuelo 💾"):
                if tiempo > 0 and origen and destino:
                    row = [fecha, origen, destino, ruta, aero, num, modelo, h_out, h_in, f"{tiempo:.2f}", 0, p_out, p_in, notas]
                    with open(NOMBRE_ARCHIVO, 'a', newline='', encoding='utf-8') as f: csv.writer(f).writerow(row)
                    st.success("Registrado!")
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
            m = folium.Map(location=[20, 0], zoom_start=2, tiles="CartoDB dark_matter")
            for _, r in df.iterrows():
                try:
                    c1, c2 = obtener_coords(r['Origen']), obtener_coords(r['Destino'])
                    if c1 and c2:
                        folium.PolyLine([c1, c2], color="#39ff14", weight=2, opacity=0.7).add_to(m)
                        folium.CircleMarker(c1, radius=2, color="white").add_to(m)
                        folium.CircleMarker(c2, radius=2, color="white").add_to(m)
                except: pass
            st_folium(m, width=1000, height=500)
        else: st.info("Sin vuelos registrados.")

    # 4. CLIMA (CON GUÍA INTEGRADA)
    elif menu == "☁️ Clima (METAR/TAF)":
        st.header("🌤️ Centro Meteorológico")
        
        # PESTAÑAS PARA ORDENAR
        tab1, tab2 = st.tabs(["🔍 Buscar Clima", "📖 Escuela Meteorológica (Guía Completa)"])
        
        with tab1:
            st.subheader("Búsqueda Rápida")
            # Usamos form para que al apretar ENTER se ejecute
            with st.form("metar_search"):
                col_s1, col_s2 = st.columns([3,1])
                icao = col_s1.text_input("Código ICAO (ej: KJFK)", max_chars=4).upper()
                btn_buscar = col_s2.form_submit_button("Buscar 🔎")
                
                if btn_buscar and icao:
                    datos, err = obtener_clima(icao)
                    if datos:
                        metar, taf = datos
                        st.success(f"Reporte encontrado para **{icao}**")
                        st.info(f"**METAR (Actual):**\n`{metar}`")
                        st.warning(f"**TAF (Pronóstico):**\n`{taf}`")
                    else: st.error(err)

        with tab2:
            st.subheader("🎓 Cómo leer un reporte como un profesional")
            
            st.markdown("""
            ### 1. Ejemplo Desglosado: `SCEL 091400Z 18010KT 9999 SCT030 18/12 Q1016`
            
            * **SCEL:** Lugar (Santiago).
            * **091400Z:** Día 09, Hora 14:00 **Zulu** (UTC).
            * **18010KT:** Viento viene de **180°** (Sur) a **10 Nudos**. (`VRB` = Variable, `G` = Ráfagas).
            * **9999:** Visibilidad de 10 km o más (Perfecta).
            * **SCT030:** Nubes Dispersas (Scattered) a **3.000 pies** (030 x 100).
            * **18/12:** Temperatura 18°C, Punto de Rocío 12°C.
            * **Q1016:** Presión Barométrica (QNH) 1016 hPa.
            """)
            
            st.divider()
            
            c_g1, c_g2 = st.columns(2)
            with c_g1:
                st.markdown("**☁️ COBERTURA DE NUBES**")
                st.markdown("""
                | Código | Significado | Cobertura |
                | :--- | :--- | :--- |
                | **FEW** | Escasas | 1-2 octavas |
                | **SCT** | Dispersas | 3-4 octavas |
                | **BKN** | Fragmentadas | 5-7 octavas (Techo) |
                | **OVC** | Cubierto | 8 octavas (Techo) |
                | **NSC** | Sin Nubes | Despejado |
                """)
                
                st.markdown("**🌡️ TIEMPO PRESENTE**")
                st.markdown("""
                * **RA:** Lluvia (Rain)
                * **SN:** Nieve (Snow)
                * **TS:** Tormenta (Thunderstorm)
                * **FG:** Niebla (Fog)
                * **HZ:** Bruma (Haze)
                * **- / +:** Ligero / Fuerte (ej: `+RA`)
                """)

            with c_g2:
                st.markdown("**🔮 PRONÓSTICO (TAF)**")
                st.markdown("""
                El TAF te dice qué pasará en el futuro. Busca estas claves:
                
                * **BECMG (Becoming):** Cambio gradual y permanente.
                    * *Ej: `BECMG 1012/1014` (Cambia entre las 12 y 14Z).*
                * **TEMPO:** Cambio temporal, luego vuelve a la normalidad.
                    * *Ej: `TEMPO 3000 RA` (Lloverá por ratos).*
                * **FM (From):** Cambio rápido a partir de una hora exacta.
                * **PROB30/40:** Probabilidad de que ocurra (30% o 40%).
                """)
                
                st.info("💡 **Tip:** Si Temp y Rocío son iguales (ej: `10/10`), ¡habrá niebla!")

    # 5. HERRAMIENTAS
    elif menu == "🧰 Herramientas":
        st.header("🧰 Herramientas de Vuelo")
        t1, t2 = st.tabs(["📉 Calc. Descenso (TOD)", "🔄 Conversor Unidades"])
        
        with t1:
            st.subheader("Calculadora Top of Descent")
            st.write("Regla del 3: (Altitud Actual - Altitud Objetivo) * 3 / 1000")
            c_alt, c_tgt = st.columns(2)
            alt_act = c_alt.number_input("Altitud Actual (pies)", value=35000, step=1000)
            alt_tgt = c_tgt.number_input("Altitud Objetivo (pies)", value=3000, step=1000)
            
            if alt_act > alt_tgt:
                distancia = (alt_act - alt_tgt) * 3 / 1000
                st.success(f"📍 Comienza a descender a **{distancia:.0f} Millas Náuticas (NM)** del destino.")
                st.info(f"Régimen estimado (Velocidad Terrestre x 5): Si vas a 400kts GS, desciende a **{400*5} fpm**.")
            
        with t2:
            st.subheader("Conversor Rápido")
            cc1, cc2 = st.columns(2)
            kg = cc1.number_input("Kilogramos (kg)", value=0)
            lbs = cc1.number_input("Libras (lbs)", value=kg * 2.20462)
            st.caption(f"{kg} kg = {kg*2.20462:.1f} lbs")
            st.markdown("---")
            hpa = cc2.number_input("Hectopascales (hPa/mb)", value=1013)
            inhg = cc2.number_input("Pulgadas Hg (inHg)", value=hpa * 0.02953)
            st.caption(f"{hpa} hPa = {hpa*0.02953:.2f} inHg")

    # 6. ESTADÍSTICAS
    elif menu == "📊 Estadísticas":
        st.header("📊 Estadísticas")
        df = leer_vuelos()
        if not df.empty:
            c1, c2 = st.columns(2)
            top_av = df['Modelo_Avion'].value_counts().head(10)
            c1.plotly_chart(px.bar(top_av, orientation='h', title="Aviones Top"), use_container_width=True)
            top_ae = df['Aerolinea'].value_counts().head(10)
            c2.plotly_chart(px.pie(values=top_ae.values, names=top_ae.index, title="Aerolíneas"), use_container_width=True)
            st.dataframe(df)
        else: st.info("Registra vuelos para ver datos.")

if __name__ == "__main__":
    main_app()