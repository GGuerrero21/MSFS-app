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

# --- FUNCIONES PARA LA BASE DE VUELOS ALEATORIOS ---
HEADERS_RUTAS = ["Origen", "Destino", "Aerolinea", "Callsign", "Avion", "Categoria", "Distancia_NM", "Duracion_Est"]

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
    except Exception as e:
        st.error(f"Error conectando a BD de Rutas: {e}")
        return None

@st.cache_data(ttl=10)
def leer_rutas_aleatorias():
    sheet = conectar_gs_rutas()
    if sheet:
        try:
            data = sheet.get_all_records()
            return pd.DataFrame(data)
        except Exception:
            pass
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
            sheet.delete_rows(row_index + 2) # +2 por header y base 1
            leer_rutas_aleatorias.clear()
            return True
        except Exception: return False
    return False

def actualizar_ruta_gs(row_index, row_data):
    sheet = conectar_gs_rutas()
    if sheet:
        try:
            # Gspread usa base 1, fila 1 es header, así que la data empieza en row_index + 2
            cell_list = sheet.range(f"A{row_index + 2}:H{row_index + 2}")
            for i, val in enumerate(row_data):
                cell_list[i].value = str(val)
            sheet.update_cells(cell_list)
            leer_rutas_aleatorias.clear()
            return True
        except Exception as e: 
            st.error(e)
            return False
    return False
# --- FUNCIONES PARA CONFIGURACIÓN (AEROLÍNEAS Y AVIONES) ---

@st.cache_resource
def conectar_gs_config():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], SCOPE)
        client = gspread.authorize(creds)
        doc = client.open("FlightLogbook")
        try:
            sheet = doc.worksheet("Configuracion")
        except gspread.exceptions.WorksheetNotFound:
            # Si no existe, la crea y vuelca los datos base para que no pierdas nada
            sheet = doc.add_worksheet(title="Configuracion", rows="1000", cols="2")
            col_a = [["Aerolineas"]] + [[a] for a in AEROLINEAS_BASE]
            col_b = [["Aviones"]] + [[a] for a in AVIONES_DINAMICOS]
            try:
                sheet.update(f"A1:A{len(col_a)}", col_a)
                sheet.update(f"B1:B{len(col_b)}", col_b)
            except:
                pass # Por si la versión de gspread es distinta, crea la hoja igual
        return sheet
    except Exception as e:
        st.error(f"Error conectando a Configuración: {e}")
        return None

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
        except Exception:
            pass
    
    # Fallback de seguridad
    if not aero_list: aero_list = AEROLINEAS_BASE
    if not avion_list: avion_list = AVIONES_DINAMICOS
    
    # Retorna las listas limpias, ordenadas y sin vacíos
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
                fila = valores.index(valor) + 1
                sheet.update_cell(fila, col_idx, "") # Lo borramos dejándolo en blanco
                leer_configuracion.clear()
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
        # Sumamos usando la función inteligente que armamos
        horas = sum(parse_tiempo_horas(x) for x in df['Tiempo_Vuelo_Horas'].dropna())
    
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
    lista_db, _ = leer_configuracion()
    lista = set(lista_db)
    df = leer_vuelos()
    if not df.empty and 'Aerolinea' in df.columns:
        for a in df['Aerolinea'].dropna().unique():
            a_clean = a.strip()
            if a_clean:
                lista.add(a_clean)
    return sorted(list(lista))
    
def parse_tiempo_horas(val):
    """Convierte tanto formatos 'HH:MM' como '2.5' a decimal para sumar estadísticas."""
    val = str(val).strip()
    if ':' in val:
        try:
            h, m = val.split(':')
            return float(h) + float(m)/60.0
        except: return 0.0
    try: return float(val)
    except: return 0.0

def calcular_diferencia_hhmm(t_out, t_in):
    """Calcula la diferencia entre dos objetos time y devuelve 'HH:MM', soportando cruce de medianoche."""
    m_out = t_out.hour * 60 + t_out.minute
    m_in = t_in.hour * 60 + t_in.minute
    if m_in < m_out: 
        m_in += 24 * 60 # Cruzó la medianoche (ej. salió 23:00, llegó 02:00)
    diff = m_in - m_out
    return f"{diff // 60:02d}:{diff % 60:02d}"
    
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

    # --- CSS PARA OCULTAR LA BARRA DEL SIDEBAR ---
    st.markdown("""
        <style>
        /* Bloquear el scroll por completo en el menú lateral */
        [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {
            overflow-y: hidden !important;
        }
        </style>
    """, unsafe_allow_html=True)
    # ---------------------------------------------
    # ---------------------------------------------

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
        "☁️ Clima (METAR/TAF)", "🎲 Vuelos Aleatorios", "🧰 Herramientas", "📊 Estadísticas", "⚙️ Configuración"
    ])

    # Leemos la base de datos en vivo
    _, AVIONES_DINAMICOS = leer_configuracion()

    # =========================================================
    # 1. REGISTRO DE VUELO
    # =========================================================
    if menu == "📋 Registro de Vuelo":
        st.header("📋 Bitácora de Vuelo")
        st.caption("Completá los datos del despacho. El tiempo de vuelo se calculará de forma automática bloque a bloque.")

        if 'form_data' not in st.session_state:
            st.session_state.form_data = {
                "origen": "", "destino": "", "ruta": "", "no_vuelo": "",
                "puerta_salida": "", "puerta_llegada": ""
            }

        # --- SimBrief ---
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

        # --- SELECTOR DE AEROLÍNEA ---
        st.markdown("#### 🏢 Operador / Aerolínea")
        if "nueva_aerolinea_modo" not in st.session_state: st.session_state["nueva_aerolinea_modo"] = False
        if "aerolinea_seleccionada" not in st.session_state: st.session_state["aerolinea_seleccionada"] = AEROLINEAS_BASE[0] # Usa lista base si no cambiaste a AVIONES_DINAMICOS

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

        # --- FORMULARIO REDISEÑADO ---
        with st.form("vuelo", clear_on_submit=False):
            st.markdown("#### ✈️ Identificación del Vuelo")
            c1, c2, c3, c4 = st.columns(4)
            fecha = c1.date_input("📅 Fecha", value=datetime.now())
            num = c2.text_input("🔢 N° Vuelo / Callsign", value=st.session_state.form_data["no_vuelo"])
            modelo = c3.selectbox("🛩️ Equipo", MODELOS_AVION) # Si en el paso anterior usaste AVIONES_DINAMICOS, cambialo acá.
            l_rate = c4.number_input("📉 Toque (fpm)", value=0, step=10, help="Ej: -150")

            st.markdown("#### 🗺️ Ruta y Puertas")
            r1, r2, r3, r4 = st.columns(4)
            origen = r1.text_input("🛫 Origen (ICAO)", value=st.session_state.form_data["origen"]).upper()
            p_out = r2.text_input("🚪 Gate Salida", value=st.session_state.form_data["puerta_salida"])
            destino = r3.text_input("🛬 Destino (ICAO)", value=st.session_state.form_data["destino"]).upper()
            p_in = r4.text_input("🚪 Gate Llegada", value=st.session_state.form_data["puerta_llegada"])

            st.markdown("#### ⏱️ Tiempos de Calzos (ZULU)")
            t1, t2, t3 = st.columns([1, 1, 2])
            # Intentamos parsear la hora de SimBrief si existe, si no 12:00
            def_out = time(12, 0)
            if st.session_state.form_data.get("hora_salida") and ":" in st.session_state.form_data["hora_salida"]:
                try:
                    ho, mi = st.session_state.form_data["hora_salida"].split(":")
                    def_out = time(int(ho), int(mi))
                except: pass

            h_out = t1.time_input("Hora OUT (Salida)", value=def_out, step=60)
            h_in = t2.time_input("Hora IN (Llegada)", value=time(14, 0), step=60)
            t3.info("💡 El Tiempo de Vuelo (`HH:MM`) se calculará y guardará automáticamente al confirmar.")

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
                # 1. Calculamos el tiempo en formato HH:MM
                tiempo_hhmm = calcular_diferencia_hhmm(h_out, h_in)
                
                # 2. Calculamos la distancia
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
    # 5. VUELOS ALEATORIOS (BASE DE DATOS PROPIA)
    # =========================================================
    elif menu == "🎲 Vuelos Aleatorios":
        import random
        st.header("🎲 Centro de Rutas")
        st.caption("Tu base de datos personal de vuelos reales para simular.")

        tab_gen, tab_add, tab_admin = st.tabs(["🎲 Generar Vuelo", "➕ Añadir a la Base", "✏️ Administrar Base"])
        df_rutas = leer_rutas_aleatorias()

        # ── 1. PESTAÑA GENERAR ──
        with tab_gen:
            if df_rutas.empty:
                st.info("💡 Tu base de datos está vacía. Andá a la pestaña 'Añadir a la Base' para guardar tus primeros vuelos.")
            else:
                col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
                categorias = ["Cualquiera"] + sorted(df_rutas["Categoria"].unique().tolist())
                aviones = ["Cualquier avión"] + sorted(df_rutas["Avion"].unique().tolist())
                
                with col_f1: cat_sel = st.selectbox("Categoría", categorias)
                with col_f2: avion_sel = st.selectbox("Avión", aviones)
                with col_f3:
                    st.write("")
                    st.write("")
                    btn_gen = st.button("🎲 Sortear", use_container_width=True)

                if btn_gen or "vuelo_sorteado" not in st.session_state:
                    pool = df_rutas.copy()
                    if cat_sel != "Cualquiera": pool = pool[pool["Categoria"] == cat_sel]
                    if avion_sel != "Cualquier avión": pool = pool[pool["Avion"] == avion_sel]
                    
                    if not pool.empty:
                        # Selecciona una fila al azar y la convierte en diccionario
                        st.session_state["vuelo_sorteado"] = pool.sample(1).iloc[0].to_dict()
                    else:
                        st.warning("No hay vuelos guardados que coincidan con esos filtros.")
                        st.session_state["vuelo_sorteado"] = None

                v = st.session_state.get("vuelo_sorteado")
                if v:
                    st.divider()
                    c1, c2 = st.columns([3, 2])
                    with c1:
                        st.markdown(f"## 🛫 {v['Origen']}  →  🛬 {v['Destino']}")
                        
                        # Usamos st.metric para poner la Aerolínea como "etiqueta" y el Callsign gigante como "valor"
                        st.metric(v['Aerolinea'], f"✈️ {v['Callsign']}") 
                        
                        # (Eliminamos la línea de st.caption de la categoría)
                        
                    with c2:
                        st.metric("✈️ Avión", v['Avion'])
                        st.metric("📏 Distancia / Tiempo", f"{v['Distancia_NM']} NM | {v['Duracion_Est']}")

                    # Cargar al registro
                    st.divider()

                    # Cargar al registro
                    st.divider()
                    if st.button("📋 Cargar este vuelo en el Registro", use_container_width=True):
                        # Extraemos horas del texto de duracion (ej: "~3h 15m")
                        horas_float = 0.0
                        if "h" in str(v['Duracion_Est']):
                            try:
                                h_str = v['Duracion_Est'].split("h")[0].replace("~", "").strip()
                                m_str = v['Duracion_Est'].split("h")[1].replace("m", "").strip()
                                horas_float = float(h_str) + (float(m_str)/60)
                            except: pass

                        st.session_state.form_data = {
                            "origen": v["Origen"], "destino": v["Destino"], "ruta": "",
                            "no_vuelo": v["Callsign"], "tiempo": round(horas_float, 1),
                            "puerta_salida": "", "puerta_llegada": "",
                        }
                        st.session_state["aerolinea_seleccionada"] = v["Aerolinea"]
                        st.success(f"✅ Vuelo {v['Callsign']} cargado. Andá a '📋 Registro de Vuelo'.")

# ── 2. PESTAÑA AÑADIR ──
        with tab_add:
            st.subheader("➕ Guardar nuevo vuelo en la base")
            with st.form("add_ruta_form"):
                c1, c2 = st.columns(2)
                origen = c1.text_input("Origen (ICAO)").upper().strip()
                destino = c2.text_input("Destino (ICAO)").upper().strip()
                
                c3, c4 = st.columns(2)
                aerolinea = c3.text_input("Aerolínea (ej. LATAM Airlines)")
                callsign = c4.text_input("Número de Vuelo / Callsign (ej. LA400)")
                
                c5, c6 = st.columns(2)
                avion = c5.selectbox("Modelo de Avión", AVIONES_DINAMICOS)
                # Reemplazamos el selectbox por un toggle opcional
                es_desafiante = c6.toggle("🌟 Marcar como ruta Desafiante/Especial", help="Activalo solo si es una ruta escénica o peligrosa. Si no, se categorizará automáticamente por tiempo.")

                submitted_add = st.form_submit_button("💾 Guardar en Base de Datos")

                if submitted_add:
                    if len(origen) != 4 or len(destino) != 4:
                        st.error("Los códigos ICAO deben tener 4 letras.")
                    elif not callsign or not aerolinea:
                        st.error("Completá la aerolínea y el callsign.")
                    else:
                        # Cálculo automático de distancia y tiempo
                        c_o = obtener_coords(origen)
                        c_d = obtener_coords(destino)
                        dist_nm = 0
                        dur_str = "Desconocido"
                        cat_calculada = "Desconocida"

                        if c_o and c_d:
                            dist_nm = round(haversine_nm(c_o[0], c_o[1], c_d[0], c_d[1]))
                            
                            # NUEVA FÓRMULA DE TIEMPO: 430kt promedio + 36 mins (0.6h) de rodaje/maniobras
                            horas_est = (dist_nm / 430) + 0.6
                            h = int(horas_est)
                            m = int((horas_est - h) * 60)
                            dur_str = f"~{h}h {m:02d}m"
                            
                            # Lógica de Categorización Automática
                            if es_desafiante:
                                cat_calculada = "Desafiante / Especial"
                            elif horas_est < 2.0:
                                cat_calculada = "Corto radio (< 2h)"
                            elif horas_est <= 6.0:
                                cat_calculada = "Medio radio (2-6h)"
                            else:
                                cat_calculada = "Largo radio (> 6h)"
                        else:
                            st.warning("⚠️ No se encontraron las coordenadas de uno de los aeropuertos. Revisá los códigos ICAO.")
                        
                        row = [origen, destino, aerolinea, callsign, avion, cat_calculada, dist_nm, dur_str]
                        with st.spinner("Guardando ruta..."):
                            if guardar_ruta_gs(row):
                                st.success(f"✅ Ruta {origen}-{destino} guardada automáticamente como **{cat_calculada}**.")
                            else:
                                st.error("Error al guardar en Google Sheets.")

        # ── 3. PESTAÑA ADMINISTRAR ──
        with tab_admin:
            if df_rutas.empty:
                st.write("No hay rutas registradas todavía.")
            else:
                st.subheader("🛠️ Editar o Eliminar Rutas")
                for i, row in df_rutas.iterrows():
                    with st.expander(f"✈️ {row['Aerolinea']} {row['Callsign']} | {row['Origen']} ➡️ {row['Destino']}"):
                        with st.form(f"edit_form_{i}"):
                            ec1, ec2, ec3 = st.columns(3)
                            n_orig = ec1.text_input("Origen", value=row['Origen'], key=f"o_{i}").upper()
                            n_dest = ec2.text_input("Destino", value=row['Destino'], key=f"d_{i}").upper()
                            n_call = ec3.text_input("Callsign", value=row['Callsign'], key=f"c_{i}")
                            
                            ec4, ec5, ec6 = st.columns(3)
                            n_aero = ec4.text_input("Aerolínea", value=row['Aerolinea'], key=f"a_{i}")
                            n_avion = ec5.text_input("Avión", value=row['Avion'], key=f"av_{i}")
                            n_cat = ec6.text_input("Categoría", value=row['Categoria'], key=f"cat_{i}", help="Podés forzar una categoría escribiéndola aquí.")
                            
                            c_btn1, c_btn2 = st.columns(2)
                            guardar_cambios = c_btn1.form_submit_button("💾 Actualizar Ruta")
                            eliminar = c_btn2.form_submit_button("🗑️ Eliminar Ruta")

                            if guardar_cambios:
                                # Recalcular si cambiaron los aeropuertos
                                dist_nm = row['Distancia_NM']
                                dur_str = row['Duracion_Est']
                                if n_orig != row['Origen'] or n_dest != row['Destino']:
                                    co = obtener_coords(n_orig)
                                    cd = obtener_coords(n_dest)
                                    if co and cd:
                                        dist_nm = round(haversine_nm(co[0], co[1], cd[0], cd[1]))
                                        
                                        # NUEVA FÓRMULA DE TIEMPO
                                        h_est = (dist_nm / 430) + 0.6
                                        dur_str = f"~{int(h_est)}h {int((h_est - int(h_est)) * 60):02d}m"

                                        # Actualizar también la categoría auto si cambia la distancia
                                        if n_cat != "Desafiante / Especial":
                                            if h_est < 2.0: n_cat = "Corto radio (< 2h)"
                                            elif h_est <= 6.0: n_cat = "Medio radio (2-6h)"
                                            else: n_cat = "Largo radio (> 6h)"

                                new_row = [n_orig, n_dest, n_aero, n_call, n_avion, n_cat, dist_nm, dur_str]
                                if actualizar_ruta_gs(i, new_row):
                                    st.success("¡Ruta actualizada!")
                                    st.rerun()
                                else:
                                    st.error("Error al actualizar.")
                                    
                            if eliminar:
                                if eliminar_ruta_gs(i):
                                    st.success("¡Eliminado!")
                                    st.rerun()
                                else:
                                    st.error("Error al eliminar.")
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
            total_horas = df['Tiempo_Vuelo_Horas'].apply(parse_tiempo_horas).sum()
            promedio_landing = df['Landing_Rate_FPM'].mean()
            total_nm = df['Distancia_NM'].sum()
            avion_fav = df['Modelo_Avion'].mode()[0] if 'Modelo_Avion' in df.columns and not df['Modelo_Avion'].mode().empty else "N/A"

            kpi1.metric("📦 Vuelos", f"{total_vuelos}")
            kpi2.metric("⏱️ Horas", f"{total_horas:.1f} h")
            kpi3.metric("🌍 Distancia", f"{total_nm:,.0f} NM")
            kpi4.metric("🛬 Toque Prom.", f"{promedio_landing:.0f} fpm")
            kpi5.metric("✈️ Avión Fav.", avion_fav)

            st.markdown("---")

            # Mantenemos un diseño limpio solo con el histograma de flota
            if 'Modelo_Avion' in df.columns:
                st.subheader("✈️ Flota Utilizada")
                data_aviones = df['Modelo_Avion'].value_counts().reset_index()
                data_aviones.columns = ['Modelo', 'Vuelos']
                fig_bar = px.bar(data_aviones, x='Vuelos', y='Modelo', orientation='h',
                                 text='Vuelos', color='Vuelos')
                fig_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)

            # Historial con edición/eliminación y Búsqueda
            st.markdown("---")
            st.subheader("📋 Historial Completo")

            col_exp1, col_exp2 = st.columns([3, 1])
            with col_exp2:
                if st.button("📥 Exportar CSV"):
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button("Descargar CSV", csv, "vuelos.csv", "text/csv")

            # Tabla interactiva con opción de eliminar y filtrar
            with st.expander("Ver / Buscar en historial", expanded=True):
                
                # --- Buscador y Filtros ---
                f1, f2, f3 = st.columns(3)
                search_text = f1.text_input("🔍 Buscar (ICAO, Fecha...)", "")
                
                aeros = ["Todas"] + sorted(df['Aerolinea'].dropna().astype(str).unique().tolist()) if 'Aerolinea' in df.columns else ["Todas"]
                filtro_aero_hist = f2.selectbox("Aerolínea", aeros)
                
                aviones = ["Todos"] + sorted(df['Modelo_Avion'].dropna().astype(str).unique().tolist()) if 'Modelo_Avion' in df.columns else ["Todos"]
                filtro_avion_hist = f3.selectbox("Avión", aviones)
                
                st.divider()

                df_display = df.copy()
                
                # --- Lógica de filtrado ---
                if search_text:
                    search_text_lower = search_text.lower()
                    mask = df_display.astype(str).apply(lambda x: x.str.lower().str.contains(search_text_lower)).any(axis=1)
                    df_display = df_display[mask]
                
                if filtro_aero_hist != "Todas":
                    df_display = df_display[df_display['Aerolinea'] == filtro_aero_hist]
                    
                if filtro_avion_hist != "Todos":
                    df_display = df_display[df_display['Modelo_Avion'] == filtro_avion_hist]

                # --- Mostrar resultados ---
                if df_display.empty:
                    st.info("No se encontraron vuelos que coincidan con la búsqueda.")
                else:
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
# =========================================================
    # 7. CONFIGURACIÓN
    # =========================================================
    elif menu == "⚙️ Configuración":
        st.header("⚙️ Configuración de Flota y Aerolíneas")
        st.caption("Los cambios acá se guardan en tu Google Sheets y actualizan todos los menús de la app.")

        aeros_db, aviones_db = leer_configuracion()

        c1, c2 = st.columns(2)

        with c1:
            st.subheader("✈️ Aerolíneas")
            nueva_aero = st.text_input("Agregar nueva aerolínea")
            if st.button("➕ Añadir Aerolínea", use_container_width=True) and nueva_aero:
                if agregar_item_config("Aerolineas", nueva_aero.strip()):
                    st.success(f"{nueva_aero} agregada!")
                    st.rerun()

            st.divider()
            aero_eliminar = st.selectbox("Eliminar Aerolínea", ["Seleccionar..."] + aeros_db)
            if st.button("🗑️ Eliminar", key="del_aero", use_container_width=True) and aero_eliminar != "Seleccionar...":
                if eliminar_item_config("Aerolineas", aero_eliminar):
                    st.success(f"{aero_eliminar} eliminada!")
                    st.rerun()

        with c2:
            st.subheader("🛩️ Modelos de Avión")
            nuevo_avion = st.text_input("Agregar nuevo avión")
            if st.button("➕ Añadir Avión", use_container_width=True) and nuevo_avion:
                if agregar_item_config("Aviones", nuevo_avion.strip()):
                    st.success(f"{nuevo_avion} agregado!")
                    st.rerun()

            st.divider()
            avion_eliminar = st.selectbox("Eliminar Avión", ["Seleccionar..."] + aviones_db)
            if st.button("🗑️ Eliminar", key="del_avion", use_container_width=True) and avion_eliminar != "Seleccionar...":
                if eliminar_item_config("Aviones", avion_eliminar):
                    st.success(f"{avion_eliminar} eliminado!")
                    st.rerun()
if __name__ == "__main__":
    main_app()
