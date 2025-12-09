import streamlit as st
import csv
import random
import requests
import pandas as pd
import plotly.express as px
import folium
import math
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y DATOS ---

# Mapeo de Estilos de Aerolíneas (Colores Reales y Código IATA para Logos)
AIRLINE_STYLES = {
    "LAN": {"color": "#181373", "iata": "LA", "name": "LATAM Airlines"},
    "LPE": {"color": "#181373", "iata": "LA", "name": "LATAM Perú"},
    "AVA": {"color": "#DA291C", "iata": "AV", "name": "Avianca"},
    "AMX": {"color": "#002A54", "iata": "AM", "name": "Aeroméxico"},
    "IBE": {"color": "#D7192D", "iata": "IB", "name": "Iberia"},
    "AAL": {"color": "#0078D2", "iata": "AA", "name": "American Airlines"},
    "DAL": {"color": "#E31837", "iata": "DL", "name": "Delta"},
    "UAL": {"color": "#005DAA", "iata": "UA", "name": "United"},
    "BAW": {"color": "#00247D", "iata": "BA", "name": "British Airways"},
    "AFR": {"color": "#002157", "iata": "AF", "name": "Air France"},
    "KLM": {"color": "#00A1DE", "iata": "KL", "name": "KLM"},
    "Lufthansa": {"color": "#05164D", "iata": "LH", "name": "Lufthansa"}, # A veces SimBrief da nombres
    "DLH": {"color": "#05164D", "iata": "LH", "name": "Lufthansa"},
    "CMP": {"color": "#003263", "iata": "CM", "name": "Copa Airlines"},
    "UAE": {"color": "#D71921", "iata": "EK", "name": "Emirates"},
    "QFA": {"color": "#E40000", "iata": "QF", "name": "Qantas"},
    "JAL": {"color": "#CC0000", "iata": "JL", "name": "Japan Airlines"},
    "ARG": {"color": "#00A3E0", "iata": "AR", "name": "Aerolíneas Arg."},
    "VLG": {"color": "#FFCC00", "iata": "VY", "name": "Vueling", "text_color": "black"},
    "RYR": {"color": "#0D1E50", "iata": "FR", "name": "Ryanair"},
    "EZY": {"color": "#FF6600", "iata": "U2", "name": "easyJet"},
    "SKU": {"color": "#8800CC", "iata": "H2", "name": "Sky Airline"},
    "JAT": {"color": "#363636", "iata": "JA", "name": "JetSmart"},
}

AIRPORT_COORDS = {
    "KJFK": [40.6413, -73.7781], "EGLL": [51.4700, -0.4543], "SCEL": [-33.3930, -70.7858],
    "SAEZ": [-34.8222, -58.5358], "LEMD": [40.4722, -3.5609], "SKBO": [4.7016, -74.1469],
    "MMMX": [19.4363, -99.0721], "KMIA": [25.7959, -80.2870], "KLAX": [33.9416, -118.4085],
    "EHAM": [52.3105, 4.7683], "LFPG": [49.0097, 2.5479], "OMDB": [25.2532, 55.3657],
    "RJAA": [35.7719, 140.3928], "YSSY": [-33.9399, 151.1753], "SBGR": [-23.4356, -46.4731],
    "SPJC": [-12.0219, -77.1143], "MPTO": [9.0714, -79.3835], "FACT": [-33.9715, 18.6021]
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
    "Hora_OUT_UTC", "Hora_IN_UTC", "Tiempo_Vuelo_Horas", "Distancia_NM", "Puerta_Salida", "Puerta_Llegada", "Landing_Rate_FPM", "Notas"
]

# --- 2. FUNCIONES LÓGICAS ---

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
            gate_out = origin_data.get('gate', 'TBD')
            gate_in = dest_data.get('gate', 'TBD')
            times = data.get('times', {})
            est_time = int(times.get('est_block', 0)) / 3600
            
            # Hora estimada salida (simulada o real si el OFP la tiene)
            dep_time = datetime.utcfromtimestamp(int(times.get('sched_out', 0))).strftime('%H:%M') if times.get('sched_out') else "12:00"

            return {
                "origen": origin, "destino": destination, "no_vuelo": flight_no,
                "ruta": route, "tiempo_est": est_time, "aerolinea_icao": general.get('icao_airline', ''),
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
        return None, "❌ No se encontraron datos."
    return (raw_metar, raw_taf), None

def calcular_viento_cruzado(wind_dir, wind_spd, rwy_heading):
    diff = abs(wind_dir - rwy_heading)
    theta = math.radians(diff)
    crosswind = abs(math.sin(theta) * wind_spd)
    headwind = math.cos(theta) * wind_spd
    return crosswind, headwind

# --- GENERADOR DE BOARDING PASS ---
def generar_boarding_pass_img(data):
    # Dimensiones
    W, H = 600, 250
    
    # Obtener estilo aerolínea
    icao = data.get('aerolinea_icao', 'UNK')
    estilo = AIRLINE_STYLES.get(icao, {"color": "#333333", "iata": "", "name": "AEROLÍNEA"})
    
    bg_color = "white"
    primary_color = estilo["color"]
    text_color_header = estilo.get("text_color", "white")

    # Crear Imagen Base
    img = Image.new('RGB', (W, H), color=bg_color)
    draw = ImageDraw.Draw(img)

    # 1. Cabecera (Color Aerolínea)
    draw.rectangle([(0, 0), (W, 60)], fill=primary_color)
    
    # Fuente (Usamos por defecto si no hay ttf)
    try:
        font_lg = ImageFont.truetype("arial.ttf", 36)
        font_md = ImageFont.truetype("arial.ttf", 24)
        font_sm = ImageFont.truetype("arial.ttf", 16)
        font_xs = ImageFont.truetype("arial.ttf", 12)
    except:
        font_lg = ImageFont.load_default()
        font_md = ImageFont.load_default()
        font_sm = ImageFont.load_default()
        font_xs = ImageFont.load_default()

    # 2. Logo / Nombre
    # Intentar descargar logo pequeño si tenemos IATA
    logo_exito = False
    if estilo["iata"]:
        try:
            url_logo = f"https://www.gstatic.com/flights/airline_logos/70px/{estilo['iata']}.png"
            response = requests.get(url_logo)
            if response.status_code == 200:
                logo_img = Image.open(BytesIO(response.content)).convert("RGBA")
                # Redimensionar manteniendo aspecto
                logo_img.thumbnail((50, 50))
                img.paste(logo_img, (15, 5), logo_img)
                draw.text((80, 15), estilo["name"], font=font_md, fill=text_color_header)
                logo_exito = True
        except: pass
    
    if not logo_exito:
        draw.text((20, 15), estilo["name"], font=font_md, fill=text_color_header)
    
    draw.text((W - 150, 20), "BOARDING PASS", font=font_sm, fill=text_color_header)

    # 3. Cuerpo del Pase
    # Fila 1: Origen -> Destino
    draw.text((30, 80), data['origen'], font=font_lg, fill="black")
    draw.text((150, 95), "✈", font=font_md, fill=primary_color)
    draw.text((200, 80), data['destino'], font=font_lg, fill="black")
    
    # Datos Derecha (Vuelo)
    draw.text((400, 80), "VUELO", font=font_xs, fill="gray")
    draw.text((400, 95), data['no_vuelo'], font=font_md, fill="black")
    
    # Fila 2: Detalles
    y_row2 = 150
    
    # Hora
    draw.text((30, y_row2), "HORA", font=font_xs, fill="gray")
    draw.text((30, y_row2+15), data.get('hora_salida', '12:00'), font=font_md, fill="black")
    
    # Puerta
    draw.text((150, y_row2), "PUERTA", font=font_xs, fill="gray")
    gate = data.get('puerta_salida', 'TBD')
    draw.text((150, y_row2+15), gate if gate else "---", font=font_md, fill=primary_color)
    
    # Asiento (Random si no existe)
    asiento = f"{random.randint(1,30)}{random.choice(['A','B','C','D','E','F'])}"
    draw.text((250, y_row2), "ASIENTO", font=font_xs, fill="gray")
    draw.text((250, y_row2+15), asiento, font=font_md, fill="black")
    
    # Fecha
    draw.text((400, y_row2), "FECHA", font=font_xs, fill="gray")
    draw.text((400, y_row2+15), data.get('fecha', 'HOY'), font=font_sm, fill="black")

    # 4. Footer (Barcode Falso)
    draw.rectangle([(0, 210), (W, 250)], fill="#eeeeee")
    draw.rectangle([(20, 220), (W-20, 240)], fill="black") # Simula código de barras

    return img

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
        
        # VARIABLE PARA MOSTRAR BOARDING PASS
        if 'boarding_pass_img' not in st.session_state:
            st.session_state.boarding_pass_img = None

        with st.expander("📥 Importar SimBrief (Generar Boarding Pass)", expanded=True):
            c1, c2 = st.columns([3, 1])
            sb_user = c1.text_input("Usuario SimBrief")
            if c2.button("Importar y Generar"):
                datos, err = obtener_datos_simbrief(sb_user)
                if datos:
                    st.session_state.form_data.update(datos)
                    st.session_state.form_data["tiempo"] = datos["tiempo_est"]
                    # GENERAR TARJETA
                    img = generar_boarding_pass_img(datos)
                    st.session_state.boarding_pass_img = img
                    st.success("¡Datos cargados y Tarjeta Generada!")
                else: st.error(err)

        # MOSTRAR TARJETA SI EXISTE
        if st.session_state.boarding_pass_img:
            st.image(st.session_state.boarding_pass_img, caption="Tarjeta de Embarque Digital", use_column_width=False, width=600)

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
                    row = [fecha, origen, destino, ruta, aero, num, modelo, h_out, h_in, f"{tiempo:.2f}", 0, p_out, p_in, l_rate, notas]
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

    # 4. CLIMA
    elif menu == "☁️ Clima (METAR/TAF)":
        st.header("🌤️ Centro Meteorológico")
        tab1, tab2 = st.tabs(["🔍 Buscar Clima", "📖 Escuela Meteorológica"])
        with tab1:
            with st.form("metar_search"):
                col_s1, col_s2 = st.columns([3,1])
                icao = col_s1.text_input("Código ICAO", max_chars=4).upper()
                btn_buscar = col_s2.form_submit_button("Buscar 🔎")
                if btn_buscar and icao:
                    datos, err = obtener_clima(icao)
                    if datos:
                        metar, taf = datos
                        st.success(f"Reporte encontrado para **{icao}**")
                        st.info(f"**METAR:**\n`{metar}`")
                        st.warning(f"**TAF:**\n`{taf}`")
                    else: st.error(err)
        with tab2:
            st.markdown("### Guía Rápida METAR")
            st.write("Consulta la guía de códigos para interpretar el METAR.")

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
                color_cw = "red" if cw > 20 else ("orange" if cw > 15 else "green")
                st.write(f"**Viento Cruzado:** :{color_cw}[{cw:.1f} kts]")
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
            cc1, cc2 = st.columns(2)
            kg = cc1.number_input("Kg", value=0)
            st.caption(f"{kg} kg = {kg*2.20462:.1f} lbs")

    # 6. ESTADÍSTICAS
    elif menu == "📊 Estadísticas":
        st.header("📊 Estadísticas")
        df = leer_vuelos()
        if not df.empty:
            if 'Landing_Rate_FPM' in df.columns:
                avg_l = pd.to_numeric(df['Landing_Rate_FPM'], errors='coerce').mean()
                st.metric("Promedio de Toque (Landing Rate)", f"{avg_l:.0f} fpm")
            c1, c2 = st.columns(2)
            top_av = df['Modelo_Avion'].value_counts().head(10)
            c1.plotly_chart(px.bar(top_av, orientation='h', title="Aviones Top"), use_container_width=True)
            top_ae = df['Aerolinea'].value_counts().head(10)
            c2.plotly_chart(px.pie(values=top_ae.values, names=top_ae.index, title="Aerolíneas"), use_container_width=True)
            st.dataframe(df)
        else: st.info("Registra vuelos para ver datos.")

if __name__ == "__main__":
    main_app()