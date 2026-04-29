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

# Fallback manual para aeropuertos no cubiertos por airportsdata (pistas de tierra, helipuertos, etc.)
AIRPORT_COORDS_FALLBACK = {
    "NTAA": [-17.5536, -149.6070]
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
    return AIRPORT_COORDS_FALLBACK.get(codigo, None)

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

def decodificar_metar(metar_raw):
    """
    Decodifica un string METAR y retorna un dict con campos legibles.
    Cubre: estación, fecha/hora, viento, visibilidad, fenómenos, nubes, temp/dewpoint, QNH, CAVOK.
    """
    import re
    resultado = {}
    tokens = metar_raw.strip().split()
    if not tokens:
        return resultado

    idx = 0

    # Estación ICAO (4 letras)
    if re.match(r'^[A-Z]{4}$', tokens[idx]):
        resultado['estacion'] = tokens[idx]
        idx += 1

    # Fecha/Hora (DDHHMMz)
    if idx < len(tokens) and re.match(r'^\d{6}Z$', tokens[idx]):
        t = tokens[idx]
        resultado['fecha_hora'] = f"Día {t[0:2]}, {t[2:4]}:{t[4:6]} UTC"
        idx += 1

    # AUTO / COR
    if idx < len(tokens) and tokens[idx] in ('AUTO', 'COR'):
        resultado['tipo'] = tokens[idx]
        idx += 1

    # Viento: dddffKT o dddffGggKT o VRBffKT
    if idx < len(tokens):
        m = re.match(r'^(VRB|\d{3})(\d{2,3})(G(\d{2,3}))?(KT|MPS|KMH)$', tokens[idx])
        if m:
            direccion = "Variable" if m.group(1) == 'VRB' else f"{m.group(1)}°"
            velocidad = m.group(2)
            unidad = m.group(5)
            rafaga = f", ráfagas {m.group(4)} {unidad}" if m.group(4) else ""
            resultado['viento'] = f"{direccion} a {velocidad} {unidad}{rafaga}"
            idx += 1
            # Variación de viento (ej: 280V350)
            if idx < len(tokens) and re.match(r'^\d{3}V\d{3}$', tokens[idx]):
                v = tokens[idx]
                resultado['viento'] += f" (variable {v[:3]}°–{v[4:]}°)"
                idx += 1

    # CAVOK
    if idx < len(tokens) and tokens[idx] == 'CAVOK':
        resultado['visibilidad'] = "> 10 km"
        resultado['nubes'] = "Sin nubes bajo 5000 ft, sin precipitación"
        resultado['cavok'] = True
        idx += 1
    else:
        # Visibilidad (metros o millas)
        if idx < len(tokens):
            m = re.match(r'^(\d{4})$', tokens[idx])
            m_us = re.match(r'^(\d+(?:\s\d+/\d+)?SM)$', tokens[idx])
            if m:
                vis = int(m.group(1))
                resultado['visibilidad'] = "> 10 km" if vis >= 9999 else f"{vis} m"
                idx += 1
            elif m_us:
                resultado['visibilidad'] = tokens[idx]
                idx += 1

        # Fenómenos meteorológicos
        wx_codes = {
            'RA':'Lluvia', 'SN':'Nieve', 'GR':'Granizo', 'GS':'Granizo pequeño',
            'DZ':'Llovizna', 'SG':'Granos de nieve', 'IC':'Cristales de hielo',
            'FG':'Niebla', 'BR':'Neblina', 'HZ':'Bruma', 'FU':'Humo',
            'SA':'Arena', 'DU':'Polvo', 'VA':'Ceniza volcánica',
            'TS':'Tormenta', 'SQ':'Turbonada', 'FC':'Tromba',
            'SS':'Tormenta de arena', 'DS':'Tormenta de polvo',
            'PY':'Spray', 'RASN':'Lluvia y nieve mezcladas'
        }
        intensidad = {'-':'Ligero', '+':'Fuerte', 'VC':'En vecindad'}
        fenomenos = []
        while idx < len(tokens):
            tok = tokens[idx]
            desc = None
            prefijo = ''
            if tok[0] in ('-', '+'):
                prefijo = intensidad.get(tok[0], '')
                tok_body = tok[1:]
            elif tok.startswith('VC'):
                prefijo = 'En vecindad de'
                tok_body = tok[2:]
            else:
                tok_body = tok
            # Puede ser combinación: TSRA, +RASN, etc.
            for code, name in wx_codes.items():
                if tok_body == code or tok_body.startswith(code):
                    desc = f"{prefijo} {name}".strip()
                    break
            if desc:
                fenomenos.append(desc)
                idx += 1
            else:
                break
        if fenomenos:
            resultado['fenomenos'] = ", ".join(fenomenos)

        # Nubes
        nubes = []
        while idx < len(tokens):
            m = re.match(r'^(FEW|SCT|BKN|OVC|NSC|SKC|NCD|VV)(\d{3})?(?:(CB|TCU))?$', tokens[idx])
            if m:
                cobertura_map = {
                    'FEW':'Escasas (1-2/8)', 'SCT':'Dispersas (3-4/8)',
                    'BKN':'Fragmentadas/Techo (5-7/8)', 'OVC':'Cubierto/Techo (8/8)',
                    'NSC':'Sin nubes significativas', 'SKC':'Cielo despejado',
                    'NCD':'Sin nubes detectadas', 'VV':'Visibilidad vertical'
                }
                cobertura = cobertura_map.get(m.group(1), m.group(1))
                altura = f" a {int(m.group(2)) * 100} ft" if m.group(2) else ""
                tipo_nube = f" [{m.group(3)}]" if m.group(3) else ""
                nubes.append(f"{cobertura}{altura}{tipo_nube}")
                idx += 1
            else:
                break
        if nubes:
            resultado['nubes'] = " | ".join(nubes)

    # Temperatura / Punto de rocío
    if idx < len(tokens):
        m = re.match(r'^(M?\d{2})/(M?\d{2})$', tokens[idx])
        if m:
            def conv(s): return f"-{s[1:]}°C" if s.startswith('M') else f"{s}°C"
            temp = conv(m.group(1))
            dewp = conv(m.group(2))
            resultado['temperatura'] = temp
            resultado['rocio'] = dewp
            # Diferencia pequeña → riesgo de niebla
            t_val = int(m.group(1).replace('M','-'))
            d_val = int(m.group(2).replace('M','-'))
            if abs(t_val - d_val) <= 2:
                resultado['alerta_niebla'] = True
            idx += 1

    # QNH
    if idx < len(tokens):
        m = re.match(r'^(Q|A)(\d{4})$', tokens[idx])
        if m:
            if m.group(1) == 'Q':
                resultado['qnh'] = f"{m.group(2)} hPa"
            else:
                resultado['qnh'] = f"{int(m.group(2))/100:.2f} inHg"
            idx += 1

    # Tendencia / NOSIG / TEMPO
    resto = " ".join(tokens[idx:])
    if resto:
        resultado['tendencia'] = resto

    return resultado


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
        "☁️ Clima (METAR/TAF)", "🎲 Vuelos Aleatorios", "🧰 Herramientas", "📊 Estadísticas"
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
        tab1, tab2, tab3 = st.tabs(["🔍 Buscar & Decodificar", "📡 TAF Comentado", "🎓 Referencia Rápida"])

        # ---- TAB 1: BUSCAR + DECODIFICAR ----
        with tab1:
            with st.form("metar_search"):
                col_s1, col_s2 = st.columns([3, 1])
                icao_input = col_s1.text_input("Código ICAO", max_chars=4, placeholder="Ej: SCEL, EGLL, KJFK")
                buscar = col_s2.form_submit_button("Buscar 🔎")

            if buscar and icao_input:
                icao_q = icao_input.strip().upper()
                datos, err = obtener_clima(icao_q)
                if not datos:
                    st.error(err)
                else:
                    metar_raw, taf_raw = datos
                    # METAR raw
                    st.subheader(f"METAR — {icao_q}")
                    st.code(metar_raw, language=None)
                    # Decodificado
                    if metar_raw not in ("No disponible", "Error conexión"):
                        dec = decodificar_metar(metar_raw)
                        if dec.get('alerta_niebla'):
                            st.warning("⚠️ Temp y punto de rocío muy cercanos — riesgo de niebla.")
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
                    # TAF
                    if taf_raw not in ("No disponible", "Error conexión"):
                        st.subheader(f"TAF — {icao_q}")
                        taf_fmt = taf_raw.strip() \
                            .replace('BECMG', '\n  BECMG') \
                            .replace('TEMPO', '\n  TEMPO') \
                            .replace(' FM',   '\n  FM') \
                            .replace('PROB',  '\n  PROB')
                        st.code(taf_fmt, language=None)
                        kws = []
                        if 'BECMG' in taf_raw: kws.append("**BECMG** = cambio gradual permanente")
                        if 'TEMPO' in taf_raw: kws.append("**TEMPO** = cambio temporal")
                        if 'FM'    in taf_raw: kws.append("**FM** = cambio rápido desde esa hora")
                        if 'PROB'  in taf_raw: kws.append("**PROB** = probabilidad de cambio")
                        if 'TS'    in taf_raw: kws.append("**TS** = tormenta eléctrica")
                        if 'NSW'   in taf_raw: kws.append("**NSW** = fin del mal tiempo")
                        if kws:
                            with st.expander("📖 Leyenda de este TAF"):
                                for k in kws: st.markdown(f"- {k}")
                    else:
                        st.info("TAF no disponible para este aeropuerto.")
            elif buscar:
                st.warning("Ingresá un código ICAO primero.")

            # Decodificador manual
            st.divider()
            st.subheader("🔧 Decodificador manual")
            st.caption("Pegá cualquier METAR para decodificarlo sin conexión a red.")
            metar_manual = st.text_input("METAR", placeholder="Ej: SCEL 151400Z 18012KT 9999 SCT040 17/10 Q1014")
            if metar_manual.strip():
                dec = decodificar_metar(metar_manual.strip())
                if dec:
                    if dec.get('alerta_niebla'):
                        st.warning("⚠️ Diferencia Temp/Rocío ≤ 2°C — posible niebla.")
                    campos_m = [
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
                        campos_m.insert(4, ("⛈️ Fenómenos", dec['fenomenos']))
                    for i in range(0, len(campos_m), 4):
                        row_c = st.columns(4)
                        for j, (lbl, val) in enumerate(campos_m[i:i+4]):
                            row_c[j].metric(lbl, val)
                    if dec.get('tendencia'):
                        st.info(f"**Tendencia:** `{dec['tendencia']}`")

        # ---- TAB 2: TAF COMENTADO ----
        with tab2:
            st.subheader("📡 ¿Cómo leer un TAF completo?")
            st.markdown("El TAF es el pronóstico oficial del aeropuerto. Dura normalmente 24–30 horas.")
            st.code("""TAF EGLL 151700Z 1518/1624 27015KT 9999 SCT030
  BECMG 1520/1522 27008KT
  TEMPO 1600/1606 4000 RADZ BKN008
  PROB30 TEMPO 1606/1612 0800 FG BKN002
  FM161200 29012KT 9999 FEW025""", language=None)
            with st.expander("🔍 Línea por línea", expanded=True):
                st.markdown("""
| Fragmento | Significado |
|:---|:---|
| `TAF EGLL` | Pronóstico de Londres Heathrow |
| `151700Z` | Emitido el día 15 a las 17:00 UTC |
| `1518/1624` | Válido desde día 15/18:00 hasta día 16/24:00 UTC |
| `27015KT 9999 SCT030` | Base: viento 270°/15kt, vis >10km, nubes dispersas 3000ft |
| `BECMG 1520/1522 27008KT` | Entre 20:00–22:00 el viento amainará a 8kt permanentemente |
| `TEMPO 1600/1606 4000 RADZ BKN008` | Madrugada del 16: vis 4km con llovizna, techo 800ft ⚠️ |
| `PROB30 TEMPO 1606/1612` | 30% de probabilidad de niebla con techo en 200ft |
| `FM161200 29012KT 9999 FEW025` | Desde mediodía del 16: mejora general |
""")
            with st.expander("⚠️ Alertas que buscar siempre"):
                st.markdown("""
- **BKN/OVC < 010** → techo bajo 1000ft, posible aproximación por instrumentos
- **Visibilidad < 0800** → mínimos de muchos procedimientos ILS
- **TS** en cualquier parte → tormentas, planear alternado
- **PROB30/40 + TEMPO** → clima inestable, monitorear en ruta
- **FZRA / FZFG** → lluvia o niebla engelante, riesgo de hielo
""")

        # ---- TAB 3: REFERENCIA RÁPIDA ----
        with tab3:
            st.subheader("🎓 Referencia rápida METAR/TAF")
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                with st.expander("💨 Viento", expanded=True):
                    st.markdown("""
| Código | Significado |
|:---|:---|
| `27015KT` | 270° a 15 kt |
| `27015G25KT` | 270°/15kt, ráfagas 25kt |
| `VRB05KT` | Variable, 5 kt |
| `00000KT` | Calma |
""")
                with st.expander("☁️ Nubes"):
                    st.markdown("""
| Código | Cobertura | ¿Techo? |
|:---|:---|:---|
| `FEW030` | 1–2/8 a 3000ft | No |
| `SCT030` | 3–4/8 a 3000ft | No |
| `BKN030` | 5–7/8 a 3000ft | **Sí** |
| `OVC030` | 8/8 a 3000ft | **Sí** |
| `VV004` | Niebla total, vis vertical 400ft | **Sí** |
""")
                with st.expander("🧭 Presión"):
                    st.markdown("""
- `Q1013` → hPa (Europa, Latinoamérica)
- `A2992` → inHg (EE.UU.)
- **1013.25 hPa = 29.92 inHg** (ISA estándar)
""")
            with col_g2:
                with st.expander("⛈️ Fenómenos", expanded=True):
                    st.markdown("""
| Código | Significado |
|:---|:---|
| `RA / -RA / +RA` | Lluvia / ligera / fuerte |
| `SN` | Nieve |
| `DZ` | Llovizna |
| `GR` | Granizo |
| `FG` | Niebla (vis < 1km) |
| `BR` | Neblina (1–5km) |
| `HZ` | Bruma seca |
| `TS / TSRA` | Tormenta / con lluvia |
| `FZRA / FZFG` | Lluvia/niebla engelante |
| `SH` | Chubasco (ej: `SHRA`) |
| `VC` | En vecindad |
""")
                with st.expander("✅ Especiales"):
                    st.markdown("""
- **CAVOK** = Vis >10km + sin nubes <5000ft + sin precipitación
- **NSC** = No Significant Cloud
- **SKC/CLR** = Cielo despejado
- **NOSIG** = Sin cambios en 2h
- **NSW** = Cesó el mal tiempo
- **SPECI** = METAR especial por cambio brusco
""")

    # =========================================================
    # 5. VUELOS ALEATORIOS (OpenSky Network)
    # =========================================================
    elif menu == "🎲 Vuelos Aleatorios":
        import random

        # Mapa tipo ICAO → nombre legible
        ICAO_TYPE_MODELS = {
            "A319": "Airbus A319", "A320": "Airbus A320", "A20N": "Airbus A320 Neo",
            "A321": "Airbus A321", "A21N": "Airbus A321 Neo", "A332": "Airbus A330-200",
            "A333": "Airbus A330-300", "A339": "Airbus A330-900", "A346": "Airbus A340-600",
            "A359": "Airbus A350-900", "A35K": "Airbus A350-1000", "A388": "Airbus A380-800",
            "B736": "Boeing 737-600", "B737": "Boeing 737-700", "B738": "Boeing 737-800",
            "B739": "Boeing 737-900", "B38M": "Boeing 737 MAX 8", "B748": "Boeing 747-8",
            "B772": "Boeing 777-200", "B77L": "Boeing 777-200LR", "B77W": "Boeing 777-300ER",
            "B788": "Boeing 787-8", "B789": "Boeing 787-9", "B78X": "Boeing 787-10",
            "E170": "Embraer E170", "E175": "Embraer E175", "E190": "Embraer E190",
            "E195": "Embraer E195", "AT45": "ATR 42-600", "AT75": "ATR 72-600",
            "DH8D": "Dash 8 Q400", "CRJ9": "CRJ-900", "CRJ7": "CRJ-700",
            "C172": "Cessna 172", "C208": "Cessna Caravan",
        }

        @st.cache_data(ttl=30)
        def obtener_vuelo_fr24():
            """
            Usa FlightRadarAPI (SDK no oficial, educativo) para obtener
            un vuelo real en curso con origen, destino, avión y aerolínea.
            Retorna (dict, error_str).
            """
            try:
                from FlightRadar24 import FlightRadar24API
            except ImportError:
                return None, "Instalá `FlightRadarAPI` en requirements.txt"

            try:
                fr = FlightRadar24API()
                vuelos = fr.get_flights()
                if not vuelos:
                    return None, "No se obtuvieron vuelos."

                # Filtrar: en vuelo, con origen Y destino conocidos
                candidatos = [
                    v for v in vuelos
                    if getattr(v, 'origin_airport_iata', None)
                    and getattr(v, 'destination_airport_iata', None)
                    and getattr(v, 'altitude', 0) > 5000
                    and not getattr(v, 'on_ground', True)
                ]

                if not candidatos:
                    return None, "No se encontraron vuelos con ruta completa ahora mismo."

                random.shuffle(candidatos)

                # Intentar hasta 6 hasta obtener datos de detalle completos
                for vuelo_base in candidatos[:6]:
                    try:
                        det = fr.get_flight_details(vuelo_base)
                        vuelo_base.set_flight_details(det)

                        orig_iata  = getattr(vuelo_base, 'origin_airport_iata',  '') or ''
                        dest_iata  = getattr(vuelo_base, 'destination_airport_iata', '') or ''
                        callsign   = (getattr(vuelo_base, 'callsign', '') or '').strip()
                        aerolinea  = getattr(vuelo_base, 'airline_short_name', '') or \
                                     getattr(vuelo_base, 'airline_name', '') or ''
                        tipo_icao  = (getattr(vuelo_base, 'aircraft_code', '') or '').strip().upper()
                        registro   = getattr(vuelo_base, 'registration', '') or ''
                        alt_ft     = int(getattr(vuelo_base, 'altitude', 0))
                        vel_kt     = int(getattr(vuelo_base, 'ground_speed', 0))
                        heading    = int(getattr(vuelo_base, 'heading', 0))
                        lat        = float(getattr(vuelo_base, 'latitude', 0))
                        lon        = float(getattr(vuelo_base, 'longitude', 0))

                        # Convertir IATA → ICAO usando airportsdata
                        # airportsdata también tiene índice IATA
                        DB_IATA = airportsdata.load('IATA')
                        orig_icao = DB_IATA.get(orig_iata, {}).get('icao', orig_iata) if orig_iata else '????'
                        dest_icao = DB_IATA.get(dest_iata, {}).get('icao', dest_iata) if dest_iata else '????'

                        modelo = ICAO_TYPE_MODELS.get(tipo_icao, tipo_icao or 'Desconocido')

                        # ETA
                        eta_ts = getattr(vuelo_base, 'time_details', {})
                        eta_str = None
                        if isinstance(eta_ts, dict):
                            eta_real = eta_ts.get('estimated', {}).get('arrival')
                            if eta_real:
                                from datetime import datetime as _dt
                                try:
                                    eta_str = _dt.utcfromtimestamp(eta_real).strftime('%H:%M UTC')
                                except Exception:
                                    pass

                        return {
                            "callsign":    callsign or "N/A",
                            "aerolinea":   aerolinea,
                            "origen_icao": orig_icao,
                            "destino_icao":dest_icao,
                            "origen_iata": orig_iata,
                            "destino_iata":dest_iata,
                            "tipo_icao":   tipo_icao,
                            "modelo":      modelo,
                            "registro":    registro,
                            "alt_ft":      alt_ft,
                            "vel_kt":      vel_kt,
                            "heading":     heading,
                            "lat":         lat,
                            "lon":         lon,
                            "eta":         eta_str,
                        }, None

                    except Exception:
                        continue

                return None, "No se pudo obtener detalle de ningún vuelo. Intentá de nuevo."

            except Exception as e:
                return None, f"Error con FlightRadarAPI: {e}"

        # ------------------------------------------------------------------
        # UI principal
        # ------------------------------------------------------------------
        st.header("🎲 Vuelos Reales para el Simulador")

        modo_fuente = st.radio(
            "Fuente de vuelos",
            ["🛰️ En vivo (Flightradar24)", "📚 Base curada"],
            horizontal=True,
        )

        # ── MODO EN VIVO ──────────────────────────────────────────────────
        if modo_fuente == "🛰️ En vivo (Flightradar24)":
            col_btn, col_hint = st.columns([1, 3])
            with col_btn:
                generar_live = st.button("🔄 Obtener vuelo en vivo", use_container_width=True)
            with col_hint:
                st.caption("Datos reales de Flightradar24: origen, destino, aerolínea y tipo de avión en tiempo real.")

            if generar_live or "vuelo_live" not in st.session_state:
                obtener_vuelo_fr24.clear()   # forzar refresh en cada click
                with st.spinner("Conectando con Flightradar24 y buscando un vuelo con ruta completa…"):
                    v_live, err_live = obtener_vuelo_fr24()
                if not v_live:
                    st.error(f"No se pudo obtener un vuelo: {err_live}")
                    st.stop()
                st.session_state["vuelo_live"] = v_live

            v = st.session_state["vuelo_live"]

            dist = mostrar_tarjeta_vuelo(
                orig_icao  = v["origen_icao"],
                dest_icao  = v["destino_icao"],
                callsign   = v["callsign"],
                modelo     = v.get("modelo", "Desconocido"),
                aerolinea  = v.get("aerolinea"),
                num_vuelo  = v["callsign"],
                alt_ft     = v["alt_ft"],
                vel_kt     = v["vel_kt"],
                heading    = v["heading"],
                lat_actual = v["lat"],
                lon_actual = v["lon"],
                es_live    = True,
            )

            # ETA y matrícula si están disponibles
            extras = []
            if v.get("registro"):   extras.append(f"✈️ Matrícula: `{v['registro']}`")
            if v.get("eta"):        extras.append(f"🕐 ETA: **{v['eta']}**")
            if v.get("tipo_icao"):  extras.append(f"🔤 Tipo ICAO: `{v['tipo_icao']}`")
            if extras:
                st.caption("  |  ".join(extras))

            st.divider()
            if st.button("📋 Cargar en el Registro", use_container_width=True):
                horas_est = (dist / 480) if dist else 0.0
                st.session_state.form_data = {
                    "origen":       v["origen_icao"],
                    "destino":      v["destino_icao"],
                    "ruta":         "",
                    "no_vuelo":     v["callsign"],
                    "tiempo":       round(horas_est, 1),
                    "puerta_salida": "",
                    "puerta_llegada": "",
                }
                if v.get("aerolinea"):
                    st.session_state["aerolinea_seleccionada"] = v["aerolinea"]
                st.success(f"✅ Vuelo `{v['callsign']}` cargado. Andá a '📋 Registro de Vuelo'.")
        def mostrar_tarjeta_vuelo(orig_icao, dest_icao, callsign, modelo,
                                  duracion=None, aerolinea=None, num_vuelo=None,
                                  alt_ft=None, vel_kt=None, heading=None,
                                  lat_actual=None, lon_actual=None, es_live=False):

            apt_o = AIRPORTS_DB.get(orig_icao, {})
            apt_d = AIRPORTS_DB.get(dest_icao, {})
            ciudad_o = f"{apt_o.get('city','')}, {apt_o.get('country','')}" if apt_o else "—"
            ciudad_d = f"{apt_d.get('city','')}, {apt_d.get('country','')}" if apt_d else "—"
            nombre_o = apt_o.get('name', orig_icao)
            nombre_d = apt_d.get('name', dest_icao)
            elev_o = apt_o.get('elevation', 0)
            elev_d = apt_d.get('elevation', 0)

            c_orig = obtener_coords(orig_icao)
            c_dest = obtener_coords(dest_icao)
            dist_nm = round(haversine_nm(c_orig[0], c_orig[1], c_dest[0], c_dest[1])) if (c_orig and c_dest) else None
            dist_km = round(dist_nm * 1.852) if dist_nm else None

            # Tiempo estimado si no se provee (a ~480kt crucero)
            if not duracion and dist_nm:
                horas_est = dist_nm / 480
                h = int(horas_est)
                m = int((horas_est - h) * 60)
                duracion = f"~{h}h {m:02d}m"

            live_badge = '<span style="background:#e74c3c;color:#fff;font-size:11px;padding:2px 8px;border-radius:4px;font-weight:700;letter-spacing:1px;">● LIVE</span>' if es_live else ''
            aero_str = f"<span style='color:#aaa;font-size:14px;'>{aerolinea}</span>" if aerolinea else ""
            num_str = f"<code style='background:#222;padding:2px 8px;border-radius:4px;font-size:15px;'>{num_vuelo or callsign}</code>"

            st.markdown(f"""
<div style="background:linear-gradient(135deg,#0f1923 0%,#1a2535 100%);
            border:1px solid #2a3a4a;border-radius:14px;padding:24px 28px;margin-bottom:16px;">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px;flex-wrap:wrap;">
    {num_str} {aero_str} {live_badge}
  </div>
  <div style="display:grid;grid-template-columns:1fr 48px 1fr;align-items:center;gap:8px;margin-bottom:20px;">
    <div>
      <div style="font-size:32px;font-weight:800;color:#fff;letter-spacing:2px;">{orig_icao}</div>
      <div style="font-size:13px;color:#7ec8e3;font-weight:600;">{nombre_o}</div>
      <div style="font-size:12px;color:#888;">{ciudad_o}</div>
      <div style="font-size:11px;color:#555;">⛰ {elev_o} ft</div>
    </div>
    <div style="text-align:center;font-size:22px;color:#39ff14;">✈</div>
    <div style="text-align:right;">
      <div style="font-size:32px;font-weight:800;color:#fff;letter-spacing:2px;">{dest_icao}</div>
      <div style="font-size:13px;color:#7ec8e3;font-weight:600;">{nombre_d}</div>
      <div style="font-size:12px;color:#888;">{ciudad_d}</div>
      <div style="font-size:11px;color:#555;">⛰ {elev_d} ft</div>
    </div>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:12px;">
    <div style="background:#0d1f2d;border-radius:8px;padding:10px 16px;min-width:110px;">
      <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;">Avión</div>
      <div style="font-size:14px;font-weight:600;color:#fff;margin-top:2px;">{modelo}</div>
    </div>
    <div style="background:#0d1f2d;border-radius:8px;padding:10px 16px;min-width:110px;">
      <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;">Distancia</div>
      <div style="font-size:14px;font-weight:600;color:#fff;margin-top:2px;">{f'{dist_nm:,} NM' if dist_nm else '—'}</div>
    </div>
    <div style="background:#0d1f2d;border-radius:8px;padding:10px 16px;min-width:110px;">
      <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;">Duración est.</div>
      <div style="font-size:14px;font-weight:600;color:#fff;margin-top:2px;">{duracion or '—'}</div>
    </div>
    {f'''<div style="background:#0d1f2d;border-radius:8px;padding:10px 16px;min-width:110px;">
      <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;">Altitud</div>
      <div style="font-size:14px;font-weight:600;color:#39ff14;margin-top:2px;">{alt_ft:,} ft</div>
    </div>
    <div style="background:#0d1f2d;border-radius:8px;padding:10px 16px;min-width:110px;">
      <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;">Velocidad</div>
      <div style="font-size:14px;font-weight:600;color:#39ff14;margin-top:2px;">{vel_kt} kt</div>
    </div>
    <div style="background:#0d1f2d;border-radius:8px;padding:10px 16px;min-width:110px;">
      <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;">Rumbo</div>
      <div style="font-size:14px;font-weight:600;color:#39ff14;margin-top:2px;">{heading}°</div>
    </div>''' if es_live and alt_ft else ''}
  </div>
</div>
""", unsafe_allow_html=True)

            # Mapa
            if c_orig and c_dest:
                centro = [v["lat"], v["lon"]] if (es_live and lat_actual) else [(c_orig[0]+c_dest[0])/2, (c_orig[1]+c_dest[1])/2]
                zoom = 4 if es_live else 3
                m = folium.Map(location=centro, zoom_start=zoom, tiles="CartoDB dark_matter")
                ruta = get_geodesic_path(c_orig[0], c_orig[1], c_dest[0], c_dest[1])
                folium.PolyLine(ruta, color="#39ff14", weight=2,
                                opacity=0.6 if es_live else 0.85,
                                dash_array="6" if es_live else None).add_to(m)
                folium.Marker(c_orig, tooltip=f"🛫 {orig_icao}",
                              icon=folium.Icon(color="green", icon="plane", prefix="fa")).add_to(m)
                folium.Marker(c_dest, tooltip=f"🛬 {dest_icao}",
                              icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa")).add_to(m)
                if es_live and lat_actual:
                    folium.Marker(
                        [lat_actual, lon_actual],
                        tooltip=f"✈️ {callsign} — posición actual",
                        icon=folium.Icon(color="blue", icon="plane", prefix="fa"),
                        popup=f"{alt_ft:,} ft | {vel_kt} kt | {heading}°"
                    ).add_to(m)
                st_folium(m, width=900, height=400)
                if dist_nm:
                    st.caption(f"📏 Gran círculo: **{dist_nm:,} NM** ({dist_km:,} km)")

            return dist_nm  # para usar en el botón de registro

        # ── MODO EN VIVO ──────────────────────────────────────────────────
        if modo_fuente == "🛰️ En vivo (OpenSky Network)":
            col_btn, col_hint = st.columns([1, 3])
            with col_btn:
                generar_live = st.button("🔄 Obtener vuelo en vivo", use_container_width=True)
            with col_hint:
                st.caption("Conecta con OpenSky Network y elige un vuelo comercial real en curso ahora mismo.")

            aviso_ruta = None
            if generar_live or "vuelo_live" not in st.session_state:
                with st.spinner("Conectando con OpenSky…"):
                    token, err_tok = obtener_token_opensky(
                        st.secrets["opensky"]["client_id"],
                        st.secrets["opensky"]["client_secret"],
                    )
                if not token:
                    st.error(f"No se pudo autenticar: {err_tok}")
                    st.stop()
                with st.spinner("Buscando vuelo con ruta completa…"):
                    v_live, aviso_ruta = obtener_vuelo_live_completo(token)
                if not v_live:
                    st.error(aviso_ruta)
                    st.stop()
                st.session_state["vuelo_live"] = v_live
                st.session_state["aviso_live"] = aviso_ruta

            v = st.session_state["vuelo_live"]
            aviso_ruta = st.session_state.get("aviso_live")
            if aviso_ruta:
                st.warning(aviso_ruta)

            dist = mostrar_tarjeta_vuelo(
                orig_icao=v["origen_icao"],
                dest_icao=v["destino_icao"],
                callsign=v["callsign"],
                modelo=v.get("modelo","Desconocido"),
                alt_ft=v["alt_ft"],
                vel_kt=v["vel_kt"],
                heading=v["heading"],
                lat_actual=v["lat"],
                lon_actual=v["lon"],
                es_live=True,
            )

            st.divider()
            if st.button("📋 Cargar en el Registro", use_container_width=True):
                horas_est = (dist / 480) if dist else 0.0
                st.session_state.form_data = {
                    "origen": v["origen_icao"],
                    "destino": v["destino_icao"],
                    "ruta": "",
                    "no_vuelo": v["callsign"],
                    "tiempo": round(horas_est, 1),
                    "puerta_salida": "",
                    "puerta_llegada": "",
                }
                st.success(f"✅ Vuelo `{v['callsign']}` cargado. Andá a '📋 Registro de Vuelo'.")

        # ── MODO BASE CURADA ──────────────────────────────────────────────
        else:
            VUELOS_CURADOS = [
                # Largo radio
                {"origen":"EGLL","destino":"KJFK","aerolinea":"British Airways","num":"BA112","avion":"Boeing 777-200","duracion":"7h 30m","categoria":"Largo radio"},
                {"origen":"OMDB","destino":"KLAX","aerolinea":"Emirates","num":"EK215","avion":"Airbus A380-800","duracion":"16h 15m","categoria":"Largo radio"},
                {"origen":"YSSY","destino":"EGLL","aerolinea":"Qantas","num":"QF1","avion":"Boeing 787-9","duracion":"22h 00m","categoria":"Largo radio"},
                {"origen":"KJFK","destino":"NZAA","aerolinea":"Air New Zealand","num":"NZ2","avion":"Boeing 787-9","duracion":"17h 40m","categoria":"Largo radio"},
                {"origen":"LFPG","destino":"RJAA","aerolinea":"Air France","num":"AF276","avion":"Boeing 777-300ER","duracion":"12h 30m","categoria":"Largo radio"},
                {"origen":"LEMD","destino":"SAEZ","aerolinea":"Aerolíneas Argentinas","num":"AR1140","avion":"Boeing 787-9","duracion":"13h 00m","categoria":"Largo radio"},
                {"origen":"EGLL","destino":"OMDB","aerolinea":"Emirates","num":"EK3","avion":"Airbus A380-800","duracion":"7h 05m","categoria":"Largo radio"},
                {"origen":"KLAX","destino":"RJAA","aerolinea":"Japan Airlines (JAL)","num":"JL62","avion":"Boeing 777-300ER","duracion":"11h 30m","categoria":"Largo radio"},
                {"origen":"SBGR","destino":"LFPG","aerolinea":"Air France","num":"AF444","avion":"Boeing 777-300ER","duracion":"11h 20m","categoria":"Largo radio"},
                {"origen":"FAOR","destino":"EGLL","aerolinea":"South African Airways","num":"SA234","avion":"Airbus A340-600","duracion":"11h 00m","categoria":"Largo radio"},
                {"origen":"KLAX","destino":"PHNL","aerolinea":"Hawaiian Airlines","num":"HA2","avion":"Airbus A330-900","duracion":"5h 45m","categoria":"Largo radio"},
                # Medio radio
                {"origen":"SCEL","destino":"SAEZ","aerolinea":"LATAM Airlines","num":"LA400","avion":"Airbus A320","duracion":"2h 15m","categoria":"Medio radio"},
                {"origen":"LEMD","destino":"LFPG","aerolinea":"Iberia","num":"IB3166","avion":"Airbus A321","duracion":"2h 05m","categoria":"Medio radio"},
                {"origen":"KJFK","destino":"KMIA","aerolinea":"American Airlines","num":"AA1","avion":"Boeing 737-800","duracion":"3h 10m","categoria":"Medio radio"},
                {"origen":"EHAM","destino":"LEMD","aerolinea":"KLM","num":"KL1706","avion":"Boeing 737-800","duracion":"2h 40m","categoria":"Medio radio"},
                {"origen":"MMMX","destino":"KJFK","aerolinea":"Aeroméxico","num":"AM002","avion":"Boeing 787-8","duracion":"4h 30m","categoria":"Medio radio"},
                {"origen":"SKBO","destino":"MPTO","aerolinea":"Copa Airlines","num":"CM303","avion":"Boeing 737-800","duracion":"1h 40m","categoria":"Medio radio"},
                {"origen":"RJAA","destino":"RKSI","aerolinea":"All Nippon Airways (ANA)","num":"NH963","avion":"Boeing 767-300","duracion":"2h 25m","categoria":"Medio radio"},
                {"origen":"EGLL","destino":"LIRF","aerolinea":"British Airways","num":"BA548","avion":"Airbus A320 Neo","duracion":"2h 30m","categoria":"Medio radio"},
                {"origen":"SAEZ","destino":"SBGR","aerolinea":"LATAM Airlines Brasil","num":"LA8080","avion":"Airbus A320","duracion":"3h 00m","categoria":"Medio radio"},
                {"origen":"SPJC","destino":"SCEL","aerolinea":"LATAM Airlines","num":"LA2037","avion":"Airbus A319","duracion":"3h 30m","categoria":"Medio radio"},
                {"origen":"OMDB","destino":"VABB","aerolinea":"flydubai","num":"FZ551","avion":"Boeing 737 MAX 8","duracion":"3h 15m","categoria":"Medio radio"},
                # Corto radio
                {"origen":"LEMD","destino":"LEBL","aerolinea":"Vueling","num":"VY1803","avion":"Airbus A320","duracion":"1h 10m","categoria":"Corto radio"},
                {"origen":"EGLL","destino":"EGPH","aerolinea":"British Airways","num":"BA1478","avion":"Airbus A319","duracion":"1h 20m","categoria":"Corto radio"},
                {"origen":"KJFK","destino":"KBOS","aerolinea":"JetBlue","num":"B61025","avion":"Airbus A320","duracion":"1h 10m","categoria":"Corto radio"},
                {"origen":"SCEL","destino":"SCTE","aerolinea":"Sky Airline","num":"H2201","avion":"Airbus A320","duracion":"1h 30m","categoria":"Corto radio"},
                {"origen":"EHAM","destino":"EGLL","aerolinea":"KLM","num":"KL1009","avion":"Embraer E190","duracion":"1h 05m","categoria":"Corto radio"},
                {"origen":"SAEZ","destino":"SAME","aerolinea":"Aerolíneas Argentinas","num":"AR1531","avion":"Boeing 737-700","duracion":"1h 35m","categoria":"Corto radio"},
                {"origen":"RKSI","destino":"RCTP","aerolinea":"Asiana Airlines","num":"OZ711","avion":"Airbus A321","duracion":"1h 55m","categoria":"Corto radio"},
                # Desafiantes
                {"origen":"BGGH","destino":"EKCH","aerolinea":"Air Greenland","num":"GL451","avion":"Airbus A330-900","duracion":"4h 30m","categoria":"Desafiante"},
                {"origen":"NZAA","destino":"NTAA","aerolinea":"Air New Zealand","num":"NZ1","avion":"Boeing 787-9","duracion":"5h 30m","categoria":"Desafiante"},
                {"origen":"SCCI","destino":"SCEL","aerolinea":"LATAM Airlines","num":"LA336","avion":"Airbus A319","duracion":"3h 40m","categoria":"Desafiante"},
                {"origen":"LPLA","destino":"LPPT","aerolinea":"SATA Air Açores","num":"SP191","avion":"Airbus A320","duracion":"2h 10m","categoria":"Desafiante"},
                {"origen":"VIDP","destino":"VQPR","aerolinea":"Druk Air","num":"KB200","avion":"Airbus A319","duracion":"1h 50m","categoria":"Desafiante"},
                {"origen":"FACT","destino":"FHSH","aerolinea":"Airlink","num":"4Z541","avion":"Embraer E170","duracion":"2h 00m","categoria":"Desafiante"},
            ]

            col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
            cats = ["Cualquiera", "Largo radio", "Medio radio", "Corto radio", "Desafiante"]
            with col_f1:
                cat_sel = st.selectbox("Categoría", cats)
            with col_f2:
                aviones_disp = ["Cualquier avión"] + sorted(set(v["avion"] for v in VUELOS_CURADOS))
                avion_sel = st.selectbox("Avión", aviones_disp)
            with col_f3:
                st.write("")
                st.write("")
                generar_cur = st.button("🎲 Generar vuelo", use_container_width=True)

            if generar_cur or "vuelo_random" not in st.session_state:
                pool = VUELOS_CURADOS.copy()
                if cat_sel != "Cualquiera":
                    pool = [v for v in pool if v["categoria"] == cat_sel]
                if avion_sel != "Cualquier avión":
                    pool = [v for v in pool if v["avion"] == avion_sel]
                if pool:
                    st.session_state["vuelo_random"] = random.choice(pool)
                else:
                    st.warning("Sin resultados con esos filtros.")
                    st.stop()

            v = st.session_state.get("vuelo_random")
            if not v:
                st.stop()

            mostrar_tarjeta_vuelo(
                orig_icao=v["origen"],
                dest_icao=v["destino"],
                callsign=v["num"],
                modelo=v["avion"],
                duracion=v["duracion"],
                aerolinea=v["aerolinea"],
                num_vuelo=v["num"],
                es_live=False,
            )

            st.divider()
            if st.button("📋 Cargar este vuelo en el Registro", use_container_width=True):
                c_o = obtener_coords(v["origen"])
                c_d = obtener_coords(v["destino"])
                dist_h = round(haversine_nm(c_o[0],c_o[1],c_d[0],c_d[1])/480, 1) if (c_o and c_d) else 0.0
                st.session_state.form_data = {
                    "origen": v["origen"],
                    "destino": v["destino"],
                    "ruta": "",
                    "no_vuelo": v["num"],
                    "tiempo": dist_h,
                    "puerta_salida": "",
                    "puerta_llegada": "",
                }
                st.session_state["aerolinea_seleccionada"] = v["aerolinea"]
                st.success(f"✅ Vuelo {v['num']} cargado. Andá a '📋 Registro de Vuelo'.")


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
