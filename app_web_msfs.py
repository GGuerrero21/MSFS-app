import streamlit as st
import csv
import random
import requests
import pandas as pd
import plotly.express as px  # NUEVO: Librería para gráficos
from datetime import datetime, timedelta 

# --- 1. Configuración de Datos Base ---

AEROPUERTOS_EJEMPLO = [
    "JFK", "LAX", "LHR", "CDG", "NRT", "DXB", "PEK", "MIA", "MAD", "SCL", "GRU", "GIG", "EHAM", "EGLL", "KJFK", "KLAX", "SCEL", "SAEZ", "LEMD"
]

# Lista base de Aerolíneas
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

# LISTA DE MODELOS DE AVIÓN
MODELOS_AVION_EJEMPLO = [
    "ATR 42-600", "ATR 72-600", "Airbus A319", "Airbus A320", "Airbus A320 Neo",
    "Airbus A321 Neo", "Airbus A330-900", "Airbus A340-600", "Airbus A350-900",
    "Airbus A350-1000", "Airbus A380-800", "Boeing 737-600", "Boeing 737-700",
    "Boeing 737-800", "Boeing 737-900", "Boeing 747-8", "Boeing 777-200",
    "Boeing 777-200LR", "Boeing 777-300ER", "Boeing 777F", "Boeing 787-8",
    "Boeing 787-9", "Boeing 787-10", "Embraer E170", "Embraer E190", "Embraer E195"
]

NOMBRE_ARCHIVO = 'mis_vuelos_msfs2020.csv'
ENCABEZADOS_CSV = [
    "Fecha", "Origen", "Destino", "Ruta", "Aerolinea", "No_Vuelo", "Modelo_Avion", 
    "Hora_OUT_UTC", "Hora_IN_UTC", "Tiempo_Vuelo_Horas", "Distancia_NM", "Puerta", "Notas"
]

# Diccionario de distancias simuladas
DISTANCIAS_NM = {
    "JFK-LAX": 2146, "LHR-CDG": 185, "DXB-NRT": 4905, "MIA-MAD": 3816, "SCL-GRU": 1600,
    "KJFK-KLAX": 2146, "EGLL-EHAM": 201, "KJFK-EGLL": 3004, "KLAX-KJFK": 2146,
    "SCEL-SAEZ": 699, "SAEZ-SCEL": 699
}
for key, dist in list(DISTANCIAS_NM.items()):
    o, d = key.split('-')
    DISTANCIAS_NM[f"{d}-{o}"] = dist


# --- 2. Funciones de Utilidad ---

def crear_archivo_csv():
    try:
        with open(NOMBRE_ARCHIVO, mode='x', newline='', encoding='utf-8') as archivo:
            escritor_csv = csv.writer(archivo)
            escritor_csv.writerow(ENCABEZADOS_CSV)
    except FileExistsError:
        pass

def calcular_distancia_estimada(origen, destino):
    clave = f"{origen}-{destino}"
    if clave in DISTANCIAS_NM: return DISTANCIAS_NM[clave]
    random.seed(origen + destino) 
    return random.randint(300, 7000)

def obtener_metar(icao_code):
    if not icao_code or len(icao_code) != 4:
        return "❌ Código ICAO no válido. Debe tener 4 letras (Ej: KJFK)."
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao_code.upper()}.TXT"
    try:
        headers = {'User-Agent': 'MSFS2020-Companion-App/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            raw_metar = "METAR no encontrado."
            fecha_obs = "Fecha desconocida"
            for line in lines:
                line = line.strip()
                if line.startswith('20'): fecha_obs = line
                elif line.startswith(icao_code.upper()):
                    raw_metar = line
                    break 
            if raw_metar == "METAR no encontrado." and len(lines) > 2:
                 raw_metar = lines[2].strip()
            return f"--- ☁️ METAR de **{icao_code.upper()}** ---\n[Hora de Obs: {fecha_obs}]\nRaw: **{raw_metar}**"
        elif response.status_code == 404: return f"❌ No se encontró METAR para {icao_code.upper()}."
        else: return f"❌ Error al obtener datos. Código: {response.status_code}"
    except requests.exceptions.RequestException as e: return f"❌ Error de conexión: {e}"

def leer_vuelos_registrados():
    try:
        df = pd.read_csv(NOMBRE_ARCHIVO)
        return df
    except FileNotFoundError: return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al leer CSV: {e}")
        return pd.DataFrame()

def obtener_lista_aerolineas_inteligente():
    lista_completa = set(AEROLINEAS_BASE)
    df = leer_vuelos_registrados()
    if not df.empty and 'Aerolinea' in df.columns:
        historial = df['Aerolinea'].dropna().unique()
        for a in historial:
            if isinstance(a, str) and a.strip() != "":
                lista_completa.add(a.strip())
    return sorted(list(lista_completa))


# --- 3. Funciones de Interfaz (Streamlit) ---

def mostrar_registro_vuelo():
    st.header("📝 Registrar Vuelo Completado")
    with st.form("registro_vuelo_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.subheader("Ruta y Aeronave")
            fecha = st.date_input("Fecha (OUT)", value=datetime.now().date())
            origen = st.text_input("Origen (ICAO)", "").upper()
            destino = st.text_input("Destino (ICAO)", "").upper()
            modelo_avion = st.selectbox("Modelo de Avión", MODELOS_AVION_EJEMPLO)
        with col2:
            st.subheader("Tiempos UTC (Z)")
            hora_out = st.text_input("Hora OUT (HHMM)", "", max_chars=4)
            hora_in = st.text_input("Hora IN (HHMM)", "", max_chars=4)
            tiempo_manual = st.number_input("Tiempo Manual (H)", 0.0, step=0.1, format="%.1f")
        with col3:
            st.subheader("Detalles")
            lista_aero = obtener_lista_aerolineas_inteligente()
            usar_manual = st.checkbox("¿Aerolínea nueva?")
            if usar_manual: aerolinea_final = st.text_input("Nombre Aerolínea")
            else: aerolinea_final = st.selectbox("Seleccionar Aerolínea", lista_aero)
            no_vuelo = st.text_input("N° Vuelo")
            puerta = st.text_input("Puerta")
        
        ruta = st.text_area("Ruta / Plan de Vuelo")
        notas = st.text_area("Notas")
        submitted = st.form_submit_button("Guardar Vuelo 💾")

        if submitted:
            if not aerolinea_final or not origen or not destino:
                st.error("Faltan datos obligatorios (Origen, Destino, Aerolínea).")
                return

            tiempo_vuelo_horas = tiempo_manual
            try:
                if hora_out and hora_in:
                    if len(hora_out)==4 and len(hora_in)==4 and hora_out.isdigit() and hora_in.isdigit():
                        dt_out = datetime.combine(fecha, datetime.strptime(hora_out, "%H%M").time())
                        dt_in = datetime.combine(fecha, datetime.strptime(hora_in, "%H%M").time())
                        if dt_in < dt_out: dt_in += timedelta(days=1)
                        tiempo_vuelo_horas = (dt_in - dt_out).total_seconds() / 3600
                        st.success(f"✅ Tiempo calculado: **{tiempo_vuelo_horas:.2f} h**")
            except: st.warning("Error calculando tiempo. Usando manual.")

            if tiempo_vuelo_horas <= 0:
                st.error("El tiempo debe ser > 0.")
                return

            datos = {
                "Fecha": fecha.strftime("%Y-%m-%d"), "Origen": origen, "Destino": destino,
                "Ruta": ruta, "Aerolinea": aerolinea_final.strip(), "No_Vuelo": no_vuelo,
                "Modelo_Avion": modelo_avion, "Hora_OUT_UTC": hora_out, "Hora_IN_UTC": hora_in,
                "Tiempo_Vuelo_Horas": f"{tiempo_vuelo_horas:.2f}",
                "Distancia_NM": calcular_distancia_estimada(origen, destino),
                "Puerta": puerta, "Notas": notas
            }
            try:
                with open(NOMBRE_ARCHIVO, mode='a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow([datos.get(h, '') for h in ENCABEZADOS_CSV])
                st.success("✅ Vuelo registrado.")
            except Exception as e: st.error(f"Error guardando: {e}")

def mostrar_herramienta_metar():
    st.header("☁️ Herramienta METAR")
    icao = st.text_input("Código ICAO (4 letras)", max_chars=4).upper()
    if st.button("Buscar"):
        if len(icao)==4: st.info(obtener_metar(icao))
        else: st.warning("4 letras requeridas.")
    
    with st.expander("Ver Guía de Decodificación"):
        st.markdown("""
        **SCEL 092200Z 21015KT 9999 FEW030 26/12 Q1011**
        * **SCEL**: Lugar. **092200Z**: Día 09, 22:00 UTC.
        * **21015KT**: Viento 210° a 15 nudos.
        * **9999**: Visibilidad >10km.
        * **FEW030**: Pocas nubes a 3000 pies.
        * **26/12**: Temp 26°C / Rocío 12°C.
        * **Q1011**: Presión 1011 hPa.
        """)

def mostrar_logbook():
    st.header("📖 Logbook y Estadísticas")
    df = leer_vuelos_registrados()
    
    if df.empty:
        st.info("Registra tu primer vuelo para ver estadísticas.")
        return
    
    # Conversión de tipos para cálculos
    df['Tiempo_Vuelo_Horas'] = pd.to_numeric(df['Tiempo_Vuelo_Horas'], errors='coerce').fillna(0)
    df['Distancia_NM'] = pd.to_numeric(df['Distancia_NM'], errors='coerce').fillna(0)

    # --- KPIs Principales ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Vuelos Totales", len(df))
    col2.metric("Horas Totales", f"{df['Tiempo_Vuelo_Horas'].sum():.1f} h")
    col3.metric("Distancia Total", f"{df['Distancia_NM'].sum():,.0f} NM")
    
    st.markdown("---")
    
    # --- GRÁFICOS (VISUALIZACIÓN BONITA) ---
    st.subheader("📊 Análisis de Flota y Rutas")
    
    # Fila 1: Aviones y Aerolíneas
    c_graf1, c_graf2 = st.columns(2)
    
    with c_graf1:
        st.caption("🏆 Top Aeronaves Usadas")
        # Contamos cuántas veces se repite cada avión
        conteo_aviones = df['Modelo_Avion'].value_counts().reset_index()
        conteo_aviones.columns = ['Modelo', 'Vuelos']
        # Gráfico de barras horizontal
        fig_aviones = px.bar(
            conteo_aviones.head(10), 
            x='Vuelos', 
            y='Modelo', 
            orientation='h',
            color='Vuelos',
            color_continuous_scale='Viridis'
        )
        fig_aviones.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig_aviones, use_container_width=True)

    with c_graf2:
        st.caption("🌍 Top Aerolíneas")
        conteo_aero = df['Aerolinea'].value_counts().reset_index()
        conteo_aero.columns = ['Aerolinea', 'Vuelos']
        # Gráfico de dona (Pie chart con agujero)
        fig_aero = px.pie(
            conteo_aero.head(10), 
            values='Vuelos', 
            names='Aerolinea', 
            hole=0.4
        )
        fig_aero.update_layout(height=350)
        st.plotly_chart(fig_aero, use_container_width=True)

    # Fila 2: Aeropuertos (Origenes y Destinos)
    st.markdown("---")
    c_graf3, c_graf4 = st.columns(2)
    
    with c_graf3:
        st.caption("🛫 Top Aeropuertos de Salida (Origen)")
        conteo_origen = df['Origen'].value_counts().head(7).reset_index()
        conteo_origen.columns = ['ICAO', 'Salidas']
        fig_origen = px.bar(conteo_origen, x='ICAO', y='Salidas', color='Salidas', color_continuous_scale='Blues')
        st.plotly_chart(fig_origen, use_container_width=True)
        
    with c_graf4:
        st.caption("🛬 Top Aeropuertos de Llegada (Destino)")
        conteo_dest = df['Destino'].value_counts().head(7).reset_index()
        conteo_dest.columns = ['ICAO', 'Llegadas']
        fig_dest = px.bar(conteo_dest, x='ICAO', y='Llegadas', color='Llegadas', color_continuous_scale='Reds')
        st.plotly_chart(fig_dest, use_container_width=True)

    st.markdown("---")
    st.subheader("📋 Historial Detallado")
    st.dataframe(df, use_container_width=True)
    
    csv_log = df.to_csv(index=False).encode('utf-8')
    st.download_button("Descargar CSV", csv_log, "logbook.csv", "text/csv")

def main_app():
    crear_archivo_csv() 
    st.set_page_config(page_title="MSFS Logbook Pro", layout="wide", initial_sidebar_state="expanded")
    st.title("✈️ Compañía Aérea MSFS 2020 🚀")
    opcion = st.sidebar.selectbox("Herramienta:", ["Registro de Vuelo", "METAR", "Logbook y Estadísticas"])

    if opcion == "Registro de Vuelo": mostrar_registro_vuelo()
    elif opcion == "METAR": mostrar_herramienta_metar()
    elif opcion == "Logbook y Estadísticas": mostrar_logbook()

if __name__ == "__main__":
    random.seed(datetime.now().timestamp())
    main_app()