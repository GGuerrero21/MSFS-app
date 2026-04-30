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

# --- INICIALIZACIÓN DE BASES DE DATOS ESTÁTICAS ---
AIRPORTS_DB = airportsdata.load('ICAO')

AIRPORT_COORDS_FALLBACK = {
    "NTAA": [-17.5536, -149.6070]
}

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

# --- LISTAS BASE (Se usarán la primera vez para poblar Google Sheets) ---
AEROLINEAS_BASE = sorted([
    "Aer Lingus", "Aerolíneas Argentinas", "Aeroméxico", "Air Canada", "Air China",
    "Air Europa", "Air France", "Air India", "Air New Zealand", "American Airlines",
    "Avianca", "Azul Brazilian Airlines", "British Airways", "Cathay Pacific", 
    "Copa Airlines", "Delta Air Lines", "Emirates", "Iberia", "Japan Airlines (JAL)", 
    "KLM", "LATAM Airlines", "Lufthansa", "Qantas", "Qatar Airways", "Ryanair", 
    "Singapore Airlines", "Southwest Airlines", "Turkish Airlines", "United Airlines"
])

AVIONES_BASE = [
    "Airbus A319", "Airbus A320", "Airbus A320 Neo", "Airbus A321", "Airbus A330-900", 
    "Airbus A350-900", "Boeing 737-700", "Boeing 737-800", "Boeing 737 MAX 8", 
    "Boeing 747-8", "Boeing 777-300ER", "Boeing 787-9", "Embraer E190", "ATR 72-600"
]

SHEET_HEADERS = [
    "Fecha", "Origen", "Destino", "Ruta", "Aerolinea", "Num_Vuelo", "Modelo_Avion",
    "Hora_OUT", "Hora_IN", "Tiempo_Vuelo_Horas", "Distancia_NM", "Gate_Salida",
    "Gate_Llegada", "Landing_Rate_FPM", "Notas"
]

HEADERS_RUTAS = ["Origen", "Destino", "Aerolinea", "Callsign", "Avion", "Categoria", "Distancia_NM", "Duracion_Est"]

# =========================================================
# FUNCIONES DE GOOGLE SHEETS Y CONEXIÓN
# =========================================================
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def conectar_google_sheets():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("⚠️ No se encontraron los secretos de Google Cloud en st.secrets.")
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
        st.error(f"Error conectando a Bitácora principal: {e}")
        return None

@st.cache_data(ttl=30)
def leer_vuelos():
    sheet = conectar_google_sheets()
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            if df.empty: return pd.DataFrame()
            for col in ['Distancia_NM', 'Landing_Rate_FPM']:
                if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception: return pd.DataFrame()
    return pd.DataFrame()

def guardar_vuelo_gs(row_data):
    sheet = conectar_google_sheets()
    if sheet:
        try:
            sheet.append_row([str(x) for x in row_data])
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

@st.cache_resource
def conectar_gs_rutas():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], SCOPE)
        client = gspread.authorize(creds)
        doc = client.open("FlightLogbook")
        try:
            sheet = doc.worksheet("RutasAleatorias")
        except gspread.exceptions.WorksheetNotFound:
            sheet = doc.add_worksheet(title="RutasAleatorias", rows="1000", cols="10")
            sheet.append_row(HEADERS_RUTAS)
        return sheet
    except Exception: return None

@st.cache_data(ttl=10)
def leer_rutas_aleatorias():
    sheet = conectar_gs_rutas()
    if sheet:
        try:
            return pd.DataFrame(sheet.get_all_records())
        except Exception: pass
    return pd.DataFrame()

def guardar_ruta_gs(row_data):
    sheet = conectar_gs_rutas()
    if sheet:
        try:
            sheet.append_row([str(x) for x in row_data])
            leer_rutas_aleatorias.clear()
            return True
        except Exception: return False
    return False

def eliminar_ruta_gs(row_index):
    sheet = conectar_gs_rutas()
    if sheet:
        try:
            sheet.delete_rows(row_index + 2)
            leer_rutas_aleatorias.clear()
            return True
        except Exception: return False
    return False

def actualizar_ruta_gs(row_index, row_data):
    sheet = conectar_gs_rutas()
    if sheet:
        try:
            cell_list = sheet.range(f"A{row_index + 2}:H{row_index + 2}")
            for i, val in enumerate(row_data): cell_list[i].value = str(val)
            sheet.update_cells(cell_list)
            leer_rutas_aleatorias.clear()
            return True
        except Exception: return False
    return False

@st.cache_resource
def conectar_gs_config():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], SCOPE)
        client = gspread.authorize(creds)
        doc = client.open("FlightLogbook")
        try:
            sheet = doc.worksheet("Configuracion")
        except gspread.exceptions.WorksheetNotFound:
            sheet = doc.add_worksheet(title="Configuracion", rows="1000", cols="2")
            col_a = [["Aerolineas"]] + [[a] for a in AEROLINEAS_BASE]
            col_b = [["Aviones"]] + [[a] for a in AVIONES_BASE]
            try:
                sheet.update(f"A1:A{len(col_a)}", col_a)
                sheet.update(f"B1:B{len(col_b)}", col_b)
            except: pass 
        return sheet
    except Exception: return None

@st.cache_data(ttl=10)
def leer_configuracion():
    sheet = conectar_gs_config()
    aero_list, avion_list = [], []
    if sheet:
        try:
            data = sheet.get_all_records()
            for row in data:
                if row.get("Aerolineas"): aero_list.append(str(row["Aerolineas"]).strip())
                if row.get("Aviones"): avion_list.append(str(row["Aviones"]).strip())
        except Exception: pass
    
    if not aero_list: aero_list = AEROLINEAS_BASE
    if not avion_list: avion_list = AVIONES_BASE
    return sorted([x for x in set(aero_list) if x]), sorted([x for x in set(avion_list) if x])

def agregar_item_config(columna, valor):
    sheet = conectar_gs_config()
    if sheet:
        try:
            col_idx = 1 if columna == "Aerolineas" else 2
            valores = sheet.col_values(col_idx)
            sheet.update_cell(len(valores) + 1, col_idx, valor)
            leer_configuracion.clear()
            return True
        except Exception: return False
    return False

def eliminar_item_config(columna, valor):
    sheet = conectar_gs_config()
    if sheet:
        try:
            col_idx = 1 if columna == "Aerolineas" else 2
            valores = sheet.col_values(col_idx)
            if valor in valores:
                sheet.update_cell(valores.index(valor) + 1, col_idx, "")
                leer_configuracion.clear()
                return True
        except Exception: return False
    return False


# =========================================================
# FUNCIONES DE LÓGICA Y CÁLCULO
# =========================================================
def parse_tiempo_horas(val):
    val = str(val).strip()
    if ':' in val:
        try:
            h, m = val.split(':')
            return float(h) + float(m)/60.0
        except: return 0.0
    try: return float(val)
    except: return 0.0

def calcular_diferencia_hhmm(t_out, t_in):
    m_out = t_out.hour * 60 + t_out.minute
    m_in = t_in.hour * 60 + t_in.minute
    if m_in < m_out: m_in += 24 * 60 
    diff = m_in - m_out
    return f"{diff // 60:02d}:{diff % 60:02d}"

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
    horas = sum(parse_tiempo_horas(x) for x in df['Tiempo_Vuelo_Horas'].dropna()) if not df.empty and 'Tiempo_Vuelo_Horas' in df.columns else 0
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

def obtener_aerolineas_inteligente():
    lista_db, _ = leer_configuracion()
    lista = set(lista_db)
    df = leer_vuelos()
    if not df.empty and 'Aerolinea' in df.columns:
        for a in df['Aerolinea'].dropna().unique():
            if str(a).strip(): lista.add(str(a).strip())
    return sorted(list(lista))

def obtener_coords(icao):
    if not isinstance(icao, str): return None
    codigo = icao.strip().upper()
    apt = AIRPORTS_DB.get(codigo)
    return [apt['lat'], apt['lon']] if apt else AIRPORT_COORDS_FALLBACK.get(codigo, None)

def obtener_clima(icao_code):
    if not icao_code or len(icao_code) != 4: return None, "❌ ICAO inválido."
    headers = {'User-Agent': 'MSFS2020-App/1.0'}
    try:
        r_metar = requests.get(f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao_code.upper()}.TXT", headers=headers, timeout=5)
        raw_metar = r_metar.text.strip().split('\n')[1] if r_metar.status_code == 200 else "No disponible"
    except: raw_metar = "Error conexión"
    try:
        r_taf = requests.get(f"https://tgftp.nws.noaa.gov/data/forecasts/taf/stations/{icao_code.upper()}.TXT", headers=headers, timeout=5)
        raw_taf = "\n".join(r_taf.text.strip().split('\n')[1:]) if r_taf.status_code == 200 else "No disponible"
    except: raw_taf = "Error conexión"
    if raw_metar == "No disponible" and raw_taf == "No disponible": return None, "❌ No se encontraron datos."
    return (raw_metar, raw_taf), None

def decodificar_metar(metar_raw):
    import re
    resultado = {}
    tokens = metar_raw.strip().split()
    if not tokens: return resultado
    idx = 0
    if re.match(r'^[A-Z]{4}$', tokens[idx]):
        resultado['estacion'] = tokens[idx]
        idx += 1
    if idx < len(tokens) and re.match(r'^\d{6}Z$', tokens[idx]):
        resultado['fecha_hora'] = f"Día {tokens[idx][0:2]}, {tokens[idx][2:4]}:{tokens[idx][4:6]} UTC"
        idx += 1
    if idx < len(tokens) and tokens[idx] in ('AUTO', 'COR'): idx += 1
    
    if idx < len(tokens):
        m = re.match(r'^(VRB|\d{3})(\d{2,3})(G(\d{2,3}))?(KT|MPS|KMH)$', tokens[idx])
        if m:
            resultado['viento'] = f"{'Variable' if m.group(1) == 'VRB' else m.group(1)+'°'} a {m.group(2)} {m.group(5)}{', ráfagas '+m.group(4) if m.group(4) else ''}"
            idx += 1
            if idx < len(tokens) and re.match(r'^\d{3}V\d{3}$', tokens[idx]):
                resultado['viento'] += f" (var {tokens[idx][:3]}°-{tokens[idx][4:]}°)"
                idx += 1
                
    if idx < len(tokens) and tokens[idx] == 'CAVOK':
        resultado['visibilidad'] = "> 10 km"
        resultado['nubes'] = "CAVOK"
        resultado['cavok'] = True
        idx += 1
    else:
        if idx < len(tokens) and re.match(r'^(\d{4})$', tokens[idx]):
            resultado['visibilidad'] = "> 10 km" if int(tokens[idx]) >= 9999 else f"{int(tokens[idx])} m"
            idx += 1
        
        wx_codes = {'RA':'Lluvia', 'SN':'Nieve', 'GR':'Granizo', 'DZ':'Llovizna', 'FG':'Niebla', 'BR':'Neblina', 'HZ':'Bruma', 'TS':'Tormenta'}
        fenomenos = []
        while idx < len(tokens):
            desc, t_body, pfx = None, tokens[idx].lstrip('-+'), 'Ligero' if tokens[idx].startswith('-') else ('Fuerte' if tokens[idx].startswith('+') else '')
            for code, name in wx_codes.items():
                if t_body.startswith(code) or code in t_body: desc = f"{pfx} {name}".strip()
            if desc:
                fenomenos.append(desc)
                idx += 1
            else: break
        if fenomenos: resultado['fenomenos'] = ", ".join(fenomenos)

        nubes = []
        while idx < len(tokens):
            m = re.match(r'^(FEW|SCT|BKN|OVC|NSC|SKC|NCD|VV)(\d{3})?', tokens[idx])
            if m:
                cmap = {'FEW':'Escasas', 'SCT':'Dispersas', 'BKN':'Fragmentadas', 'OVC':'Cubierto', 'NSC':'Sin Nubes', 'SKC':'Despejado'}
                nubes.append(f"{cmap.get(m.group(1), m.group(1))}{' a '+str(int(m.group(2))*100)+' ft' if m.group(2) else ''}")
                idx += 1
            else: break
        if nubes: resultado['nubes'] = " | ".join(nubes)

    if idx < len(tokens):
        m = re.match(r'^(M?\d{2})/(M?\d{2})$', tokens[idx])
        if m:
            resultado['temperatura'] = f"-{m.group(1)[1:]}°C" if 'M' in m.group(1) else f"{m.group(1)}°C"
            resultado['rocio'] = f"-{m.group(2)[1:]}°C" if 'M' in m.group(2) else f"{m.group(2)}°C"
            if abs(int(m.group(1).replace('M','-')) - int(m.group(2).replace('M','-'))) <= 2: resultado['alerta_niebla'] = True
            idx += 1

    if idx < len(tokens):
        m = re.match(r'^(Q|A)(\d{4})$', tokens[idx])
        if m:
            resultado['qnh'] = f"{m.group(2)} hPa" if m.group(1)=='Q' else f"{int(m.group(2))/100:.2f} inHg"
            idx += 1
            
    resto = " ".join(tokens[idx:])
    if resto: resultado['tendencia'] = resto
    return resultado

def calcular_viento_cruzado(wind_dir, wind_spd, rwy_heading):
    diff = abs(wind_dir - rwy_heading)
    theta = math.radians(diff)
    return abs(math.sin(theta) * wind_spd), math.cos(theta) * wind_spd

def obtener_notams(icao_code, api_key):
    """Obtiene los NOTAMs reales usando AVWX API (Súper estable)."""
    if not icao_code or len(icao_code) != 4: return None, "❌ Código ICAO inválido."
    
    # 🛠️ CORRECCIÓN: La URL es avwx.rest (sin el "api." al principio)
    url = f"https://avwx.rest/api/notam/{icao_code.upper()}"
    headers = {"Authorization": f"Token {api_key}"}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            notams_list = []
            
            # AVWX devuelve una lista directa de objetos
            lista_cruda = data if isinstance(data, list) else data.get("data", [])
            
            for n in lista_cruda:
                if isinstance(n, dict) and "raw" in n:
                    notams_list.append(n["raw"])
                elif isinstance(n, str):
                    notams_list.append(n)
                    
            return notams_list, None if notams_list else f"No hay NOTAMs activos para {icao_code.upper()}."
        elif r.status_code in (401, 403): 
            return None, "❌ Token de AVWX inválido o expirado."
        else: 
            return None, f"Error del servidor (Cod: {r.status_code})."
    except Exception as e: 
        return None, f"Error de conexión: {str(e)}"

# =========================================================
# 4. INTERFAZ PRINCIPAL
# =========================================================
def main_app():
    st.set_page_config(page_title="MSFS EFB Ultimate", layout="wide", page_icon="✈️")

    st.markdown("""
        <style>
        [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {
            overflow-y: hidden !important;
        }
        </style>
    """, unsafe_allow_html=True)

    modo_grande = st.sidebar.toggle("👁️ Modo Texto Grande", value=False)
    if modo_grande:
        st.markdown("""
            <style>
            html, body, [class*="css"] { font-size: 20px !important; }
            h1 { font-size: 3rem !important; }
            h2 { font-size: 2.5rem !important; }
            .stTextInput > div > div > input, .stSelectbox > div > div > div { font-size: 18px !important; }
            </style>
        """, unsafe_allow_html=True)

    # --- SIDEBAR PERFIL ---
    st.sidebar.title("👨‍✈️ Perfil")
    df_log = leer_vuelos()
    rango, icono, horas_act, horas_next = calcular_rango_xp(df_log)

    if st.session_state.get("rango_anterior", rango) != rango:
        st.balloons()
        st.success(f"🎉 ¡Subiste de rango! Ahora eres **{rango}** {icono}")
    st.session_state["rango_anterior"] = rango

    st.sidebar.markdown(f"### {icono} {rango}")
    st.sidebar.metric("Horas Totales", f"{horas_act:.1f} h")
    if horas_next != 1000:
        st.sidebar.progress(min(horas_act / horas_next, 1.0))
        st.sidebar.caption(f"Próximo rango en {horas_next - horas_act:.1f} h")

    if not df_log.empty:
        ultimo = df_log.iloc[-1]
        st.sidebar.markdown("---")
        st.sidebar.markdown("**✈️ Último vuelo**")
        st.sidebar.caption(f"🛫 {ultimo.get('Origen', '?')} → {ultimo.get('Destino', '?')}")
        st.sidebar.caption(f"⏱️ {ultimo.get('Tiempo_Vuelo_Horas', '0')} | 🛬 {ultimo.get('Landing_Rate_FPM', 0)} fpm")

    st.sidebar.markdown("---")
    menu = st.sidebar.radio("EFB Menu", [
        "📋 Registro de Vuelo", "✅ Checklists", "🗺️ Mapa",
        "☁️ Clima (METAR/TAF)", "🎲 Vuelos Aleatorios", "🧰 Herramientas", "📊 Estadísticas", "⚙️ Configuración"
    ])

    _, AVIONES_DINAMICOS = leer_configuracion()

    # =========================================================
    # REGISTRO DE VUELO
    # =========================================================
    if menu == "📋 Registro de Vuelo":
        st.header("📋 Bitácora de Vuelo")
        st.caption("Completá los datos del despacho. El tiempo de vuelo se calculará de forma automática bloque a bloque.")

        if 'form_data' not in st.session_state:
            st.session_state.form_data = {
                "origen": "", "destino": "", "ruta": "", "no_vuelo": "",
                "puerta_salida": "", "puerta_llegada": ""
            }

        with st.expander("📥 Importar desde SimBrief", expanded=False):
            c1, c2 = st.columns([3, 1])
            sb_user = c1.text_input("Usuario SimBrief")
            if c2.button("Importar OFP"):
                datos, err = obtener_datos_simbrief(sb_user)
                if datos:
                    st.session_state.form_data.update(datos)
                    st.success("¡Plan de vuelo importado!")
                else:
                    st.error(err)

        st.markdown("#### 🏢 Operador / Aerolínea")
        if "nueva_aerolinea_modo" not in st.session_state: st.session_state["nueva_aerolinea_modo"] = False
        if "aerolinea_seleccionada" not in st.session_state: st.session_state["aerolinea_seleccionada"] = AEROLINEAS_BASE[0] 

        col_aero1, col_aero2 = st.columns([3, 1])
        with col_aero2:
            st.session_state["nueva_aerolinea_modo"] = st.toggle("➕ Aerolínea manual", value=st.session_state["nueva_aerolinea_modo"])
        with col_aero1:
            if st.session_state["nueva_aerolinea_modo"]:
                nueva_aero_input = st.text_input("Ingresar aerolínea manualmente", placeholder="Ej: Vuelo Privado", key="nueva_aero_input")
                if nueva_aero_input.strip(): st.session_state["aerolinea_seleccionada"] = nueva_aero_input.strip()
            else:
                lista_aero = obtener_aerolineas_inteligente()
                idx_default = lista_aero.index(st.session_state["aerolinea_seleccionada"]) if st.session_state["aerolinea_seleccionada"] in lista_aero else 0
                st.session_state["aerolinea_seleccionada"] = st.selectbox("Seleccionar aerolínea guardada", lista_aero, index=idx_default, label_visibility="collapsed")

        with st.form("vuelo", clear_on_submit=False):
            st.markdown("#### ✈️ Identificación del Vuelo")
            c1, c2, c3, c4 = st.columns(4)
            fecha = c1.date_input("📅 Fecha", value=datetime.now())
            num = c2.text_input("🔢 N° Vuelo / Callsign", value=st.session_state.form_data["no_vuelo"])
            modelo = c3.selectbox("🛩️ Equipo", AVIONES_DINAMICOS) 
            l_rate = c4.number_input("📉 Toque (fpm)", value=0, step=10, help="Ej: -150")

            st.markdown("#### 🗺️ Ruta y Puertas")
            r1, r2, r3, r4 = st.columns(4)
            origen = r1.text_input("🛫 Origen (ICAO)", value=st.session_state.form_data["origen"]).upper()
            p_out = r2.text_input("🚪 Gate Salida", value=st.session_state.form_data["puerta_salida"])
            destino = r3.text_input("🛬 Destino (ICAO)", value=st.session_state.form_data["destino"]).upper()
            p_in = r4.text_input("🚪 Gate Llegada", value=st.session_state.form_data["puerta_llegada"])

            st.markdown("#### ⏱️ Tiempos de Calzos (ZULU)")
            t1, t2, t3 = st.columns([1, 1, 2])
            
            def_out = time(12, 0)
            if st.session_state.form_data.get("hora_salida") and ":" in st.session_state.form_data["hora_salida"]:
                try:
                    ho, mi = st.session_state.form_data["hora_salida"].split(":")
                    def_out = time(int(ho), int(mi))
                except: pass

            h_out = t1.time_input("Hora OUT (Salida)", value=def_out, step=60)
            h_in = t2.time_input("Hora IN (Llegada)", value=time(14, 0), step=60)
            t3.info("💡 El Tiempo de Vuelo se calculará y guardará automáticamente al confirmar.")

            st.markdown("#### 📝 Detalles Adicionales")
            ruta = st.text_area("Ruta de Vuelo", value=st.session_state.form_data["ruta"], height=68, placeholder="Ej: SUMU3 SUMU SID KUKEN UM534... ")
            notas = st.text_area("Notas / Observaciones", height=68, placeholder="Combustible restante, METAR en ruta, incidencias...")

            st.markdown("---")
            submitted = st.form_submit_button("💾 Guardar en Bitácora")

        if submitted:
            aero_final = st.session_state["aerolinea_seleccionada"]

            if not origen or len(origen) < 3:
                st.error("❌ Ingresá un código ICAO de origen válido.")
            elif not destino or len(destino) < 3:
                st.error("❌ Ingresá un código ICAO de destino válido.")
            elif st.session_state["nueva_aerolinea_modo"] and not aero_final:
                st.error("❌ Escribí el nombre de la nueva aerolínea.")
            else:
                tiempo_hhmm = calcular_diferencia_hhmm(h_out, h_in)
                c_orig = obtener_coords(origen)
                c_dest = obtener_coords(destino)
                distancia = round(haversine_nm(c_orig[0], c_orig[1], c_dest[0], c_dest[1])) if c_orig and c_dest else 0

                row = [
                    str(fecha), origen, destino, ruta, aero_final, num, modelo,
                    h_out.strftime("%H:%M"), h_in.strftime("%H:%M"),
                    tiempo_hhmm, distancia, p_out, p_in, l_rate, notas
                ]
                with st.spinner("Registrando vuelo..."):
                    if guardar_vuelo_gs(row):
                        dist_txt = f" ({distancia} NM)" if distancia > 0 else ""
                        st.success(f"✅ Vuelo {origen}→{destino}{dist_txt} guardado. Tiempo registrado: **{tiempo_hhmm}**.")
                        st.session_state["nueva_aerolinea_modo"] = False
                    else:
                        st.error("Error al guardar en la nube.")

    # =========================================================
    # CHECKLISTS
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
    # MAPA Y EXPLORADOR DE RUTAS
    # =========================================================
    elif menu == "🗺️ Mapa":
        from folium.plugins import Terminator
        st.header("🗺️ Explorador Global de Rutas")
        df = leer_vuelos()
        
        @st.cache_data(ttl=300)
        def obtener_url_radar():
            try:
                r = requests.get("https://api.rainviewer.com/public/weather-maps.json", timeout=5)
                if r.status_code == 200:
                    path = r.json()['radar']['past'][-1]['path']
                    return f"https://tilecache.rainviewer.com{path}/256/{{z}}/{{x}}/{{y}}/2/1_1.png"
            except: pass
            return None

        if not df.empty:
            c_ctrl, c_mapa = st.columns([1, 3.5])
            with c_ctrl:
                st.subheader("🎛️ Filtros")
                aeros = ["Todas"] + sorted(df['Aerolinea'].dropna().astype(str).unique().tolist()) if 'Aerolinea' in df.columns else ["Todas"]
                filtro_aero = st.selectbox("🏢 Aerolínea", aeros)
                aviones = ["Todos"] + sorted(df['Modelo_Avion'].dropna().astype(str).unique().tolist()) if 'Modelo_Avion' in df.columns else ["Todos"]
                filtro_avion = st.selectbox("🛩️ Avión", aviones)
                
                st.divider()
                st.subheader("🎨 Capas y Clima")
                estilo_mapa = st.radio("Fondo:", ["Modo Oscuro", "Modo Claro", "Satélite"], label_visibility="collapsed")
                mostrar_iconos = st.toggle("📍 Mostrar Aeropuertos", value=True)
                mostrar_radar = st.toggle("🌧️ Radar Lluvia", value=False)
                mostrar_noche = st.toggle("🌓 Línea Día/Noche", value=False)
                
                df_mapa = df.copy()
                if filtro_aero != "Todas": df_mapa = df_mapa[df_mapa['Aerolinea'] == filtro_aero]
                if filtro_avion != "Todos": df_mapa = df_mapa[df_mapa['Modelo_Avion'] == filtro_avion]
                
                st.divider()
                dist_total = pd.to_numeric(df_mapa['Distancia_NM'], errors='coerce').fillna(0).sum() if 'Distancia_NM' in df_mapa.columns else 0
                st.metric("Vuelos en pantalla", len(df_mapa))
                st.metric("Distancia cubierta", f"{dist_total:,.0f} NM")
                
            with c_mapa:
                tiles_dict = {"Modo Oscuro": "CartoDB dark_matter", "Modo Claro": "CartoDB positron", "Satélite": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"}
                centro = [20, 0]
                if not df_mapa.empty:
                    c_ult = obtener_coords(str(df_mapa.iloc[-1].get('Origen', '')).strip())
                    if c_ult: centro = c_ult

                m = folium.Map(location=centro, zoom_start=3, tiles=tiles_dict[estilo_mapa], attr="Esri" if estilo_mapa=="Satélite" else None)

                if mostrar_noche: Terminator().add_to(m)
                if mostrar_radar and obtener_url_radar():
                    folium.TileLayer(tiles=obtener_url_radar(), attr="RainViewer", name="Radar", overlay=True, opacity=0.65).add_to(m)

                aeropuertos_dibujados = set()
                for i, r in df_mapa.iterrows():
                    orig, dest = str(r.get('Origen', '')).strip().upper(), str(r.get('Destino', '')).strip().upper()
                    c1, c2 = obtener_coords(orig), obtener_coords(dest)
                    
                    if c1 and c2:
                        color_linea = "#00f2fe" if estilo_mapa == "Modo Oscuro" else "#ff0844"
                        folium.PolyLine(get_geodesic_path(c1[0], c1[1], c2[0], c2[1]), color=color_linea, weight=2.5, opacity=0.6,
                                        tooltip=f"<div style='text-align:center;'><b>{r.get('Aerolinea','')}</b><br>{orig} ➡️ {dest}</div>").add_to(m)
                        
                        if mostrar_iconos:
                            for c_code, c_coord in [(orig, c1), (dest, c2)]:
                                if c_code not in aeropuertos_dibujados:
                                    folium.CircleMarker(location=c_coord, radius=4, color="#fff" if estilo_mapa != "Modo Claro" else "#000",
                                                        fill=True, fill_color=color_linea, fill_opacity=1, tooltip=c_code).add_to(m)
                                    aeropuertos_dibujados.add(c_code)

                st_folium(m, width="100%", height=650, returned_objects=[]) 
        else: st.info("No hay vuelos registrados en el mapa.")

    # =========================================================
    # CLIMA Y NOTAMS (RESTAURADO)
    # =========================================================
    elif menu == "☁️ Clima (METAR/TAF)":
        st.header("🌤️ Centro Meteorológico y Alertas")
        tab1, tab2, tab3, tab4 = st.tabs(["🔍 Buscar Clima", "📡 TAF Comentado", "🎓 Referencia", "⚠️ NOTAMs"])

        with tab1:
            with st.form("metar_search"):
                col_s1, col_s2 = st.columns([3, 1])
                icao_input = col_s1.text_input("Código ICAO", max_chars=4, placeholder="Ej: SCEL, EGLL, KJFK")
                buscar = col_s2.form_submit_button("Buscar Clima 🔎")

            if buscar and icao_input:
                icao_q = icao_input.strip().upper()
                datos, err = obtener_clima(icao_q)
                if not datos:
                    st.error(err)
                else:
                    metar_raw, taf_raw = datos
                    st.subheader(f"METAR — {icao_q}")
                    st.code(metar_raw, language=None)
                    
                    if metar_raw not in ("No disponible", "Error conexión"):
                        dec = decodificar_metar(metar_raw)
                        if dec.get('alerta_niebla'):
                            st.warning("⚠️ Temp y punto de rocío muy cercanos — riesgo de niebla.")
                        
                        # RESTAURADO: Diseño en grilla para las métricas del METAR
                        campos = [
                            ("📍 Estación",    dec.get('estacion',    '—')),
                            ("🕐 Fecha/Hora",  dec.get('fecha_hora',  '—')),
                            ("💨 Viento",      dec.get('viento',      '—')),
                            ("👁️ Visibilidad", dec.get('visibilidad', '—')),
                            ("🌡️ Temperatura", dec.get('temperatura', '—')),
                            ("💧 Rocío",       dec.get('rocio',       '—')),
                            ("🧭 QNH",         dec.get('qnh',         '—')),
                            ("☁️ Nubes",       dec.get('nubes', 'CAVOK' if dec.get('cavok') else '—')),
                        ]
                        if dec.get('fenomenos'):
                            campos.insert(4, ("⛈️ Fenómenos", dec['fenomenos']))
                            
                        for i in range(0, len(campos), 4):
                            row_c = st.columns(4)
                            for j, (lbl, val) in enumerate(campos[i:i+4]):
                                row_c[j].metric(lbl, val)
                                
                        if dec.get('tendencia'):
                            st.info(f"**Tendencia:** `{dec['tendencia']}`")
                            
                    st.divider()
                    
                    if taf_raw not in ("No disponible", "Error conexión"):
                        st.subheader(f"TAF — {icao_q}")
                        taf_fmt = taf_raw.strip().replace('BECMG', '\n  BECMG').replace('TEMPO', '\n  TEMPO').replace(' FM', '\n  FM').replace('PROB', '\n  PROB')
                        st.code(taf_fmt, language=None)
                    else:
                        st.info("TAF no disponible para este aeropuerto.")
                        
            elif buscar:
                st.warning("Ingresá un código ICAO primero.")

            st.divider()
            st.subheader("🔧 Decodificador manual")
            st.caption("Pegá cualquier METAR para decodificarlo sin conexión a red.")
            metar_manual = st.text_input("METAR", placeholder="Ej: SCEL 151400Z 18012KT 9999 SCT040 17/10 Q1014")
            if metar_manual.strip():
                dec = decodificar_metar(metar_manual.strip())
                if dec:
                    campos_m = [
                        ("📍 Estación",    dec.get('estacion',    '—')),
                        ("💨 Viento",      dec.get('viento',      '—')),
                        ("👁️ Visibilidad", dec.get('visibilidad', '—')),
                        ("🌡️ Temperatura", dec.get('temperatura', '—')),
                        ("☁️ Nubes",       dec.get('nubes', 'CAVOK' if dec.get('cavok') else '—')),
                        ("🧭 QNH",         dec.get('qnh',         '—')),
                    ]
                    for i in range(0, len(campos_m), 3):
                        row_c = st.columns(3)
                        for j, (lbl, val) in enumerate(campos_m[i:i+3]):
                            row_c[j].metric(lbl, val)

        # RESTAURADO: Explicación completa del TAF
        with tab2:
            st.subheader("📡 ¿Cómo leer un TAF completo?")
            st.markdown("El TAF es el pronóstico oficial del aeropuerto. Dura normalmente 24–30 horas.")
            st.code("""TAF EGLL 151700Z 1518/1624 27015KT 9999 SCT030
  BECMG 1520/1522 27008KT
  TEMPO 1600/1606 4000 RADZ BKN008
  PROB30 TEMPO 1606/1612 0800 FG BKN002
  FM161200 29012KT 9999 FEW025""", language=None)
            with st.expander("🔍 Línea por línea", expanded=True):
                st.markdown("- **BECMG**: Cambio gradual permanente.\n- **TEMPO**: Cambio temporal.\n- **FM**: Cambio rápido desde esa hora.\n- **PROB30/40**: Probabilidad.")

        # RESTAURADO: Pestaña de referencias completa
# ---- TAB 3: REFERENCIA RÁPIDA ----
        with tab3:
            st.subheader("🎓 Diccionario Aeronáutico METAR/TAF")
            st.caption("Guía completa para interpretar los reportes meteorológicos como un profesional.")
            
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                with st.expander("☁️ Nubes y Cobertura", expanded=True):
                    st.markdown("""
                    | Código | Cobertura | Significado | ¿Es Techo? |
                    |:---|:---|:---|:---|
                    | **FEW** | 1-2 octavas | Escasas | ❌ No |
                    | **SCT** | 3-4 octavas | Dispersas | ❌ No |
                    | **BKN** | 5-7 octavas | Fragmentadas | **✅ Sí** |
                    | **OVC** | 8/8 octavas | Cubierto total | **✅ Sí** |
                    | **VV** | Vis. Vertical | Cielo oscurecido (niebla/nieve) | **✅ Sí** |
                    | **NSC** | 0 octavas | Sin nubes significativas | ❌ No |
                    
                    *Nota: Para aproximaciones por instrumentos (IFR), se considera "techo de nubes" a la capa más baja reportada como BKN u OVC.*
                    """)
                    
                with st.expander("💨 Viento y Ráfagas", expanded=True):
                    st.markdown("""
                    | Formato | Ejemplo | Significado |
                    |:---|:---|:---|
                    | **dddffKT** | `27015KT` | Viento de 270° a 15 nudos |
                    | **dddffGggKT**| `18020G35KT`| Viento 180°/20 nudos, **ráfagas de 35 nudos** |
                    | **VRB** | `VRB03KT` | Dirección variable (suele ser viento débil) |
                    | **00000KT** | `00000KT` | Viento en calma absoluta |
                    | **...V...** | `28015KT 250V310`| 15 nudos, variando entre 250° y 310° |
                    """)

                with st.expander("👁️ Visibilidad y Pista (RVR)"):
                    st.markdown("""
                    | Código | Significado |
                    |:---|:---|
                    | **9999** | Visibilidad de 10 km o más (óptima) |
                    | **0800** | Visibilidad de 800 metros |
                    | **CAVOK** | Vis > 10km, sin nubes bajo 5000ft, sin clima significativo |
                    | **R36/1200** | **RVR**: Pista 36 tiene visibilidad visual de 1200m |
                    """)

            with col_g2:
                with st.expander("⛈️ Fenómenos Meteorológicos", expanded=True):
                    st.markdown("""
                    **Intensidad y Proximidad:**
                    *   `-` Ligero (Ej: `-RA` lluvia ligera)
                    *   `+` Fuerte (Ej: `+TSRA` tormenta fuerte con lluvia)
                    *   `VC` En vecindad (a unos 8km del aeropuerto)
                    *   `RE` Reciente (Ej: `RERA` lluvia reciente, ya paró)

                    **Tipos de Precipitaciones:**
                    | Código | Fenómeno | Código | Fenómeno |
                    |:---|:---|:---|:---|
                    | **RA** | Lluvia (Rain) | **SN** | Nieve (Snow) |
                    | **DZ** | Llovizna (Drizzle) | **GR** | Granizo (Hail) |
                    | **SH** | Chubasco (Shower) | **TS** | Tormenta Eléctrica |

                    **Oscurecimiento (Visibilidad):**
                    | Código | Fenómeno | Código | Fenómeno |
                    |:---|:---|:---|:---|
                    | **FG** | Niebla (< 1km) | **BR** | Neblina (1-5km) |
                    | **HZ** | Bruma seca | **FU** | Humo (Smoke) |
                    
                    **Peligros Críticos para el Vuelo:**
                    *   **FZRA / FZFG:** Lluvia o niebla **Engelante** (forma hielo en las alas de inmediato).
                    *   **FC:** Tromba marina o tornado cerca de la estación.
                    """)
                    
                with st.expander("🧭 Presión y Tendencias"):
                    st.markdown("""
                    **Presión Altimétrica (QNH):**
                    *   `Q1013` = Presión en hectopascales (hPa). Estándar = 1013.
                    *   `A2992` = Presión en pulgadas de mercurio (inHg), usado en EE.UU. Estándar = 29.92.

                    **Tendencias (Próximas 2 horas):**
                    *   **NOSIG**: Sin cambios significativos esperados (No Significant Change).
                    *   **BECMG**: Cambio gradual permanente hacia las nuevas condiciones.
                    *   **TEMPO**: Fluctuaciones temporales que duran menos de 1 hora.
                    """)

# ---- TAB 4: NOTAMS REALES ----
        with tab4:
            st.subheader("⚠️ Avisos a los Aviadores (NOTAMs)")
            st.caption("Conectado a AVWX API. Información crítica temporal sobre aeropuertos (pistas cerradas, radioayudas inoperativas, grúas, etc).")
            
            with st.form("form_notam"):
                c_n1, c_n2 = st.columns([1, 2])
                icao_notam = c_n1.text_input("Código ICAO", max_chars=4, placeholder="Ej: SCEL").upper()
                api_key_avwx = c_n2.text_input("🔑 AVWX API Token", type="password", help="Registrate gratis en avwx.rest para obtener tu Token")
                
                if st.form_submit_button("📡 Descargar NOTAMs"):
                    if not api_key_avwx or not icao_notam: 
                        st.warning("Completá el ICAO y tu Token de AVWX.")
                    else:
                        with st.spinner(f"Descargando NOTAMs oficiales para {icao_notam}..."):
                            notams, error = obtener_notams(icao_notam, api_key_avwx)
                            
                            if error: 
                                st.error(error)
                            elif not notams: 
                                st.info(f"✅ Sin avisos. No hay NOTAMs activos reportados para {icao_notam}.")
                            else:
                                st.success(f"Se encontraron {len(notams)} NOTAMs activos para {icao_notam}.")
                                
                                for idx, nt in enumerate(notams):
                                    with st.expander(f"NOTAM {idx + 1}"): 
                                        st.code(nt, language=None)
                                        # Filtro inteligente de palabras clave críticas
                                        if "CLOSED" in nt or "CLSD" in nt:
                                            st.error("🚫 Contiene aviso de CIERRE (Closed).")
                                        elif "U/S" in nt or "UNSERVICEABLE" in nt:
                                            st.warning("⚠️ Contiene aviso de equipo INOPERATIVO (Unserviceable).")

    # =========================================================
    # VUELOS ALEATORIOS 
    # =========================================================
    elif menu == "🎲 Vuelos Aleatorios":
        import random
        st.header("🎲 Centro de Rutas")
        st.caption("Tu base de datos personal de vuelos reales.")

        tab_gen, tab_add, tab_admin = st.tabs(["🎲 Generar Vuelo", "➕ Añadir a la Base", "✏️ Administrar Base"])
        df_rutas = leer_rutas_aleatorias()

        with tab_gen:
            if df_rutas.empty: st.info("Base vacía. Añadí vuelos en la pestaña siguiente.")
            else:
                c1, c2, c3 = st.columns([2, 2, 1])
                cat_sel = c1.selectbox("Categoría", ["Cualquiera"] + sorted(df_rutas["Categoria"].unique().tolist()))
                avion_sel = c2.selectbox("Avión", ["Cualquier avión"] + sorted(df_rutas["Avion"].unique().tolist()))
                if c3.button("🎲 Sortear", use_container_width=True) or "vuelo_sorteado" not in st.session_state:
                    pool = df_rutas.copy()
                    if cat_sel != "Cualquiera": pool = pool[pool["Categoria"] == cat_sel]
                    if avion_sel != "Cualquier avión": pool = pool[pool["Avion"] == avion_sel]
                    st.session_state["vuelo_sorteado"] = pool.sample(1).iloc[0].to_dict() if not pool.empty else None
                        
                v = st.session_state.get("vuelo_sorteado")
                if v:
                    st.divider()
                    v1, v2 = st.columns([3, 2])
                    with v1:
                        st.markdown(f"## 🛫 {v['Origen']}  →  🛬 {v['Destino']}")
                        st.metric(v['Aerolinea'], f"✈️ {v['Callsign']}") 
                    with v2:
                        st.metric("✈️ Avión", v['Avion'])
                        st.metric("📏 Distancia / Tiempo", f"{v['Distancia_NM']} NM | {v['Duracion_Est']}")

                    if st.button("📋 Cargar al Registro", use_container_width=True):
                        h_f = 0.0
                        if "h" in str(v['Duracion_Est']):
                            try: h_f = float(v['Duracion_Est'].split("h")[0].replace("~","")) + float(v['Duracion_Est'].split("h")[1].replace("m",""))/60
                            except: pass
                        st.session_state.form_data = {"origen": v["Origen"], "destino": v["Destino"], "ruta": "", "no_vuelo": v["Callsign"], "puerta_salida": "", "puerta_llegada": ""}
                        st.session_state["aerolinea_seleccionada"] = v["Aerolinea"]
                        st.success(f"Vuelo {v['Callsign']} enviado al Registro.")

        with tab_add:
            with st.form("add_ruta"):
                ca1, ca2 = st.columns(2)
                orig, dest = ca1.text_input("Origen (ICAO)").upper().strip(), ca2.text_input("Destino (ICAO)").upper().strip()
                ca3, ca4 = st.columns(2)
                aero, callsign = ca3.text_input("Aerolínea"), ca4.text_input("Callsign")
                ca5, ca6 = st.columns(2)
                avion = ca5.selectbox("Avión", AVIONES_DINAMICOS)
                es_esp = ca6.toggle("🌟 Ruta Especial (Ignorar auto-categoría)")

                if st.form_submit_button("💾 Guardar en Base"):
                    if len(orig) != 4 or len(dest) != 4 or not callsign: st.error("Datos inválidos.")
                    else:
                        co, cd = obtener_coords(orig), obtener_coords(dest)
                        if co and cd:
                            d_nm = round(haversine_nm(co[0], co[1], cd[0], cd[1]))
                            h_e = (d_nm / 430) + 0.6
                            d_str = f"~{int(h_e)}h {int((h_e - int(h_e)) * 60):02d}m"
                            cat = "Desafiante / Especial" if es_esp else ("Corto radio (< 2h)" if h_e < 2 else ("Medio radio (2-6h)" if h_e <= 6 else "Largo radio (> 6h)"))
                            if guardar_ruta_gs([orig, dest, aero, callsign, avion, cat, d_nm, d_str]): st.success(f"Guardado como {cat}.")
                        else: st.error("No se encontraron las coordenadas.")

        with tab_admin:
            if df_rutas.empty: st.write("Base vacía.")
            else:
                for i, row in df_rutas.iterrows():
                    with st.expander(f"✈️ {row['Aerolinea']} {row['Callsign']} | {row['Origen']} ➡️ {row['Destino']}"):
                        with st.form(f"ef_{i}"):
                            ec1, ec2, ec3 = st.columns(3)
                            n_o, n_d, n_c = ec1.text_input("Orig", row['Origen']).upper(), ec2.text_input("Dest", row['Destino']).upper(), ec3.text_input("Call", row['Callsign'])
                            ec4, ec5, ec6 = st.columns(3)
                            n_a, n_av, n_cat = ec4.text_input("Aero", row['Aerolinea']), ec5.text_input("Avión", row['Avion']), ec6.text_input("Cat", row['Categoria'])
                            b1, b2 = st.columns(2)
                            if b1.form_submit_button("💾 Guardar"):
                                d_nm, d_str = row['Distancia_NM'], row['Duracion_Est']
                                if n_o != row['Origen'] or n_d != row['Destino']:
                                    co, cd = obtener_coords(n_o), obtener_coords(n_d)
                                    if co and cd:
                                        d_nm = round(haversine_nm(co[0], co[1], cd[0], cd[1]))
                                        h_e = (d_nm / 430) + 0.6
                                        d_str = f"~{int(h_e)}h {int((h_e - int(h_e)) * 60):02d}m"
                                        if n_cat != "Desafiante / Especial": n_cat = "Corto radio (< 2h)" if h_e < 2 else ("Medio radio (2-6h)" if h_e <= 6 else "Largo radio (> 6h)")
                                actualizar_ruta_gs(i, [n_o, n_d, n_a, n_c, n_av, n_cat, d_nm, d_str])
                                st.rerun()
                            if b2.form_submit_button("🗑️ Borrar"):
                                eliminar_ruta_gs(i)
                                st.rerun()

    # =========================================================
    # HERRAMIENTAS
    # =========================================================
    elif menu == "🧰 Herramientas":
        st.header("🧰 Herramientas")
        t1, t2, t3, t4 = st.tabs(["🌬️ Viento Cruzado", "📉 Calc. Descenso", "🔄 Conversor", "⛽ Combustible"])
        with t1:
            wc1, wc2, wc3 = st.columns(3)
            wd = wc1.number_input("Dir. Viento (°)", 0, 360, 0)
            ws = wc2.number_input("Vel. Viento (kt)", 0, 100, 0)
            rwy = wc3.number_input("Rumbo Pista (°)", 0, 360, 0)
            if ws > 0:
                cw, hw = calcular_viento_cruzado(wd, ws, rwy)
                st.metric("Viento Cruzado", f"{cw:.1f} kt")
        with t2:
            c_alt, c_tgt = st.columns(2)
            alt_act = c_alt.number_input("Alt Actual (ft)", value=35000, step=1000)
            alt_tgt = c_tgt.number_input("Alt Objetivo (ft)", value=3000, step=1000)
            if alt_act > alt_tgt: st.success(f"Iniciar descenso a **{(alt_act - alt_tgt) * 3 / 1000:.0f} NM** del destino.")
        with t3:
            cc1, cc2 = st.columns(2)
            kg = cc1.number_input("Kg → Lbs", value=0.0)
            cc1.caption(f"= {kg * 2.20462:.1f} lbs")
            kt = cc2.number_input("Nudos → km/h", value=0.0)
            cc2.caption(f"= {kt * 1.852:.1f} km/h")
        with t4:
            f1, f2, f3 = st.columns(3)
            tf = f1.number_input("Trip Fuel (kg)", value=5000)
            cp = f2.slider("Contingencia (%)", 0, 10, 5)
            af = f3.number_input("Alternado (kg)", value=1500)
            block = tf + (tf*cp/100) + af + 1500 + 200
            st.metric("Block Fuel Sugerido", f"{block:.0f} kg")

    # =========================================================
    # ESTADÍSTICAS (RESTAURADAS CON GRÁFICO DE BARRAS)
    # =========================================================
    elif menu == "📊 Estadísticas":
        st.header("📊 Dashboard de Rendimiento")
        df = leer_vuelos()
        if not df.empty:
            if 'Landing_Rate_FPM' in df.columns:
                df['Landing_Rate_FPM'] = pd.to_numeric(df['Landing_Rate_FPM'], errors='coerce')
            if 'Tiempo_Vuelo_Horas' in df.columns:
                df['Tiempo_Vuelo_Horas'] = df['Tiempo_Vuelo_Horas'].astype(str)
            if 'Distancia_NM' in df.columns:
                df['Distancia_NM'] = pd.to_numeric(df['Distancia_NM'], errors='coerce').fillna(0)

            # Restauramos los 5 KPIs
            kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
            total_vuelos = len(df)
            total_horas = df['Tiempo_Vuelo_Horas'].apply(parse_tiempo_horas).sum()
            promedio_landing = df['Landing_Rate_FPM'].mean() if 'Landing_Rate_FPM' in df.columns else 0
            total_nm = df['Distancia_NM'].sum()
            avion_fav = df['Modelo_Avion'].mode()[0] if 'Modelo_Avion' in df.columns and not df['Modelo_Avion'].mode().empty else "N/A"

            kpi1.metric("📦 Vuelos", f"{total_vuelos}")
            kpi2.metric("⏱️ Horas", f"{total_horas:.1f} h")
            kpi3.metric("🌍 Distancia", f"{total_nm:,.0f} NM")
            kpi4.metric("🛬 Toque Prom.", f"{promedio_landing:.0f} fpm")
            kpi5.metric("✈️ Avión Fav.", avion_fav)

            st.markdown("---")

            # RESTAURADO: Gráfico de Flota Utilizada
            if 'Modelo_Avion' in df.columns:
                st.subheader("✈️ Flota Utilizada")
                data_aviones = df['Modelo_Avion'].value_counts().reset_index()
                data_aviones.columns = ['Modelo', 'Vuelos']
                fig_bar = px.bar(data_aviones, x='Vuelos', y='Modelo', orientation='h',
                                 text='Vuelos', color='Vuelos')
                fig_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)

            st.markdown("---")
            st.subheader("📋 Historial Completo")

            col_exp1, col_exp2 = st.columns([3, 1])
            with col_exp2:
                if st.button("📥 Exportar CSV"):
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button("Descargar CSV", csv, "vuelos.csv", "text/csv")

            with st.expander("Ver / Buscar en historial", expanded=True):
                
                f1, f2, f3 = st.columns(3)
                search_text = f1.text_input("🔍 Buscar (ICAO, Fecha...)", "")
                
                aeros = ["Todas"] + sorted(df['Aerolinea'].dropna().astype(str).unique().tolist()) if 'Aerolinea' in df.columns else ["Todas"]
                filtro_aero_hist = f2.selectbox("Aerolínea", aeros)
                
                aviones = ["Todos"] + sorted(df['Modelo_Avion'].dropna().astype(str).unique().tolist()) if 'Modelo_Avion' in df.columns else ["Todos"]
                filtro_avion_hist = f3.selectbox("Avión", aviones)
                
                st.divider()

                df_display = df.copy()
                
                if search_text:
                    search_text_lower = search_text.lower()
                    mask = df_display.astype(str).apply(lambda x: x.str.lower().str.contains(search_text_lower)).any(axis=1)
                    df_display = df_display[mask]
                
                if filtro_aero_hist != "Todas":
                    df_display = df_display[df_display['Aerolinea'] == filtro_aero_hist]
                    
                if filtro_avion_hist != "Todos":
                    df_display = df_display[df_display['Modelo_Avion'] == filtro_avion_hist]

                if df_display.empty:
                    st.info("No se encontraron vuelos que coincidan con la búsqueda.")
                else:
                    for i, row in df_display.iterrows():
                        with st.container():
                            # Ajustamos las proporciones para darle más espacio a la info combinada
                            cols = st.columns([1.5, 1.5, 2.5, 2, 2, 1])
                            
                            cols[0].write(f"**{row.get('Origen','?')} → {row.get('Destino','?')}**")
                            cols[1].write(f"{row.get('Fecha','')}")
                            
                            # Aerolínea + N° de Vuelo en negrita
                            aero = row.get('Aerolinea', '')
                            num = row.get('Num_Vuelo', '')
                            texto_vuelo = f"{aero} **{num}**" if num else aero
                            cols[2].write(texto_vuelo)
                            
                            cols[3].write(f"{row.get('Modelo_Avion','')}")
                            
                            # Tiempo + Toque de Aterrizaje (FPM)
                            tiempo = row.get('Tiempo_Vuelo_Horas', '')
                            try:
                                fpm = int(float(row.get('Landing_Rate_FPM', 0)))
                                fpm_str = f"🛬 {fpm} fpm"
                            except:
                                fpm_str = "🛬 -- fpm"
                                
                            cols[4].write(f"⏱️ {tiempo}h | {fpm_str}")
                            
                            # Botón de eliminar
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

    # =========================================================
    # CONFIGURACIÓN
    # =========================================================
    elif menu == "⚙️ Configuración":
        st.header("⚙️ Configuración Base de Datos")
        aeros_db, aviones_db = leer_configuracion()
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("✈️ Aerolíneas")
            na = st.text_input("Nueva aerolínea")
            if st.button("➕ Añadir Aerolínea") and na:
                agregar_item_config("Aerolineas", na.strip())
                st.rerun()
            ae = st.selectbox("Eliminar", ["Seleccionar..."] + aeros_db)
            if st.button("🗑️ Eliminar Aero") and ae != "Seleccionar...":
                eliminar_item_config("Aerolineas", ae)
                st.rerun()

        with c2:
            st.subheader("🛩️ Aviones")
            nav = st.text_input("Nuevo avión")
            if st.button("➕ Añadir Avión") and nav:
                agregar_item_config("Aviones", nav.strip())
                st.rerun()
            ave = st.selectbox("Eliminar Avión", ["Seleccionar..."] + aviones_db)
            if st.button("🗑️ Eliminar Avión") and ave != "Seleccionar...":
                eliminar_item_config("Aviones", ave)
                st.rerun()

if __name__ == "__main__":
    main_app()
