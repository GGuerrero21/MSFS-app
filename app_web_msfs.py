import streamlit as st
import csv
import random
import requests
import pandas as pd
from datetime import datetime, timedelta 
import re 

# --- 1. Configuración de Datos Base ---

AEROPUERTOS_EJEMPLO = [
    "JFK", "LAX", "LHR", "CDG", "NRT", "DXB", "PEK", "MIA", "MAD", "SCL", "GRU", "GIG", "EHAM", "EGLL", "KJFK", "KLAX", "SCEL", "SAEZ", "LEMD"
]

# Lista de aerolíneas predefinidas + la opción para buscar/agregar
AEROLINEAS_PREDEFINIDAS = [
    "--- Escribir o buscar aquí ---",
    "LATAM Airlines", "Air France", "British Airways", "Iberia", "Lufthansa", "Emirates", "Delta Air Lines", 
    "American Airlines", "Southwest Airlines", "Ryanair", "EasyJet", "Avianca", "Aerolíneas Argentinas", 
    "Qatar Airways", "KLM", "Air Canada"
]

# LISTA ACTUALIZADA DE MODELOS DE AVIÓN
MODELOS_AVION_EJEMPLO = [
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

NOMBRE_ARCHIVO = 'mis_vuelos_msfs2020.csv'
# Encabezados actualizados con las horas UTC
ENCABEZADOS_CSV = [
    "Fecha", "Origen", "Destino", "Ruta", "Aerolinea", "No_Vuelo", "Modelo_Avion", 
    "Hora_OUT_UTC", "Hora_IN_UTC", "Tiempo_Vuelo_Horas", "Distancia_NM", "Puerta", "Notas"
]

# Diccionario de distancias simuladas (en Millas Náuticas - NM)
DISTANCIAS_NM = {
    "JFK-LAX": 2146, "LHR-CDG": 185, "DXB-NRT": 4905, "MIA-MAD": 3816, "SCL-GRU": 1600,
    "KJFK-KLAX": 2146, "EGLL-EHAM": 201, "KJFK-EGLL": 3004, "KLAX-KJFK": 2146,
    "SCEL-SAEZ": 699, "SAEZ-SCEL": 699
}
# Asegura que las distancias funcionen en ambos sentidos
for key, dist in list(DISTANCIAS_NM.items()):
    o, d = key.split('-')
    DISTANCIAS_NM[f"{d}-{o}"] = dist


# --- 2. Funciones de Utilidad ---

def crear_archivo_csv():
    """Crea el archivo CSV con los encabezados si no existe."""
    try:
        with open(NOMBRE_ARCHIVO, mode='x', newline='', encoding='utf-8') as archivo:
            escritor_csv = csv.writer(archivo)
            escritor_csv.writerow(ENCABEZADOS_CSV)
    except FileExistsError:
        pass

def calcular_distancia_estimada(origen, destino):
    """Estima la distancia en Millas Náuticas (NM)."""
    clave = f"{origen}-{destino}"
    
    if clave in DISTANCIAS_NM:
        return DISTANCIAS_NM[clave]
    
    random.seed(origen + destino) 
    return random.randint(300, 7000)

def obtener_metar(icao_code):
    """Obtiene el METAR actual para un código ICAO de 4 letras y ajusta el formato."""
    if not icao_code or len(icao_code) != 4:
        return "❌ Código ICAO no válido. Debe tener 4 letras (Ej: KJFK)."
        
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao_code.upper()}.TXT"
    
    try:
        headers = {'User-Agent': 'MSFS2020-Companion-App/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            
            raw_metar = "METAR no encontrado o datos incompletos."
            fecha_obs = "Fecha desconocida"
            
            for line in lines:
                line = line.strip()
                if line.startswith('20'):
                    fecha_obs = line
                elif line.startswith(icao_code.upper()):
                    raw_metar = line
                    break 

            if raw_metar == "METAR no encontrado o datos incompletos." and len(lines) > 2:
                 raw_metar = lines[2].strip()

            resultado = (
                f"--- ☁️ METAR de **{icao_code.upper()}** ---"
                f"\n[Hora de Obs: {fecha_obs}]"
                f"\nRaw: **{raw_metar}**"
            )
            return resultado
        elif response.status_code == 404:
            return f"❌ No se encontró METAR para {icao_code.upper()}. (Código 404)"
        else:
            return f"❌ Error al obtener datos. Código de estado: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return f"❌ Error de conexión al obtener METAR: {e}"

def leer_vuelos_registrados():
    """Lee y devuelve los datos del CSV como un DataFrame de Pandas."""
    try:
        df = pd.read_csv(NOMBRE_ARCHIVO)
        return df
    except FileNotFoundError:
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al leer el archivo CSV: {e}")
        return pd.DataFrame()

# --- 3. Funciones de Interfaz (Streamlit) ---

def mostrar_registro_vuelo():
    st.header("📝 Registrar Vuelo Completado")
    
    with st.form("registro_vuelo_form"):
        # Tres columnas principales para la info básica
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("Ruta y Aeronave")
            fecha = st.date_input("Fecha (OUT)", value=datetime.now().date())
            origen = st.text_input("Código ICAO de Origen (Ej: KJFK)", "").upper()
            destino = st.text_input("Código ICAO de Destino (Ej: EGLL)", "").upper()
            modelo_avion = st.selectbox("Modelo de Avión", MODELOS_AVION_EJEMPLO)
            
        with col2:
            st.subheader("Tiempos UTC (Z) y Duración")
            hora_out = st.text_input("Hora OUT (Salida) UTC (HHMM)", value="", max_chars=4)
            hora_in = st.text_input("Hora IN (Llegada) UTC (HHMM)", value="", max_chars=4)
            
            tiempo_manual = st.number_input(
                "Tiempo de Vuelo Manual (Horas) - Solo si OUT/IN falla", 
                min_value=0.0, 
                step=0.1, 
                format="%.1f", 
                value=0.0
            )
            
        with col3:
            st.subheader("Detalles del Vuelo")
            
            # Aerolínea con Selectbox + Text Input
            aerolinea_seleccionada = st.selectbox(
                "Aerolínea", 
                AEROLINEAS_PREDEFINIDAS, 
                index=0
            )
            
            aerolinea_manual = ""
            if aerolinea_seleccionada == "--- Escribir o buscar aquí ---":
                aerolinea_manual = st.text_input("Ingresa la Aerolínea (Nueva)")
                aerolinea_final = aerolinea_manual
            else:
                aerolinea_final = aerolinea_seleccionada

            no_vuelo = st.text_input("Número de Vuelo")
            puerta = st.text_input("Puerta/Parking")
        
        ruta = st.text_area("Ruta / Plan de Vuelo (Opcional)")
        notas = st.text_area("Notas sobre el vuelo")

        submitted = st.form_submit_button("Guardar Vuelo 💾")

        if submitted:
            
            # Validación de la aerolínea
            if aerolinea_final == "" or aerolinea_final == "--- Escribir o buscar aquí ---":
                st.error("Por favor, selecciona o escribe el nombre de una Aerolínea.")
                return

            # 1. Validación de campos obligatorios
            if not (origen and destino):
                st.error("Por favor, completa los códigos ICAO de Origen y Destino.")
                return

            # Inicializar el tiempo de vuelo con el valor manual como fallback
            tiempo_vuelo_horas = tiempo_manual
            
            # 2. Cálculo de Tiempo de Vuelo (Sobrescribe el tiempo manual si es exitoso)
            try:
                if hora_out and hora_in:
                    if not (hora_out.isdigit() and len(hora_out) == 4 and hora_in.isdigit() and len(hora_in) == 4):
                        raise ValueError("Formato de hora inválido. Usa HHMM.")
                        
                    out_h = int(hora_out[:2])
                    out_m = int(hora_out[2:])
                    in_h = int(hora_in[:2])
                    in_m = int(hora_in[2:])
                    
                    base_date = fecha
                    out_dt = datetime(base_date.year, base_date.month, base_date.day, out_h, out_m)
                    in_dt = datetime(base_date.year, base_date.month, base_date.day, in_h, in_m)
                    
                    if in_dt < out_dt:
                        in_dt = in_dt + timedelta(days=1)
                        
                    flight_duration = in_dt - out_dt
                    tiempo_vuelo_horas = flight_duration.total_seconds() / 3600.0
                    st.success(f"✅ Tiempo de vuelo calculado automáticamente: **{tiempo_vuelo_horas:.2f} h**")
                
            except Exception as e:
                st.warning(f"⚠️ Error al calcular el tiempo de vuelo: {e}. Se utilizará el valor manual de **{tiempo_manual:.1f} h**.")

            # 3. Validación final del tiempo
            if tiempo_vuelo_horas <= 0:
                st.error("El tiempo de vuelo (automático o manual) debe ser mayor a 0.")
                return

            # 4. Cálculo de Distancia (Automatizado)
            distancia_nm = calcular_distancia_estimada(origen, destino)
            
            # 5. Registro de Datos
            datos_vuelo = {
                "Fecha": fecha.strftime("%Y-%m-%d"),
                "Origen": origen,
                "Destino": destino,
                "Ruta": ruta,
                "Aerolinea": aerolinea_final, # Usar la aerolínea validada
                "No_Vuelo": no_vuelo,
                "Modelo_Avion": modelo_avion,
                "Hora_OUT_UTC": hora_out,
                "Hora_IN_UTC": hora_in,
                "Tiempo_Vuelo_Horas": f"{tiempo_vuelo_horas:.2f}", 
                "Distancia_NM": distancia_nm,
                "Puerta": puerta,
                "Notas": notas
            }
            
            try:
                with open(NOMBRE_ARCHIVO, mode='a', newline='', encoding='utf-8') as archivo:
                    escritor_csv = csv.writer(archivo)
                    fila = [datos_vuelo.get(h, '') for h in ENCABEZADOS_CSV]
                    escritor_csv.writerow(fila)
                
                st.success(f"✅ ¡Vuelo registrado exitosamente! Distancia estimada: **{distancia_nm:,.0f} NM**.")
            except Exception as e:
                st.error(f"❌ Error al guardar el vuelo: {e}")

def mostrar_herramienta_metar():
    st.header("☁️ Herramienta METAR")
    st.markdown("Consulta el informe meteorológico actual para cualquier aeropuerto ICAO.")
    
    icao_code = st.text_input("Ingresa el Código ICAO (4 Letras)", max_chars=4).upper()
    
    if st.button("Buscar METAR 🔎"):
        if len(icao_code) == 4:
            with st.spinner(f"Buscando datos para {icao_code}..."):
                raw_metar = obtener_metar(icao_code) 
            
            if "❌" in raw_metar or "METAR no encontrado" in raw_metar:
                st.error(raw_metar.replace("\n", " "))
            else:
                st.info(raw_metar)
                st.markdown(
                    f"**🔗 Enlace útil para decodificar:** [Decodificador METAR Online](https://www.aviationweather.gov/metar/decoder?icao={icao_code})"
                )
        else:
            st.warning("El código ICAO debe tener 4 letras.")
            
    # Guía de Decodificación METAR (Completa)
    st.markdown("---")
    st.subheader("Guía Completa para Entender el METAR")
    st.markdown("El METAR se lee en una secuencia fija de grupos. Utiliza esta guía para descifrar cada código. **Recuerda: Si aparece CAVOK, reemplaza los grupos de Visibilidad, Fenómenos y Nubes.**")
    
    # Estructura principal
    st.table({
        "Sección": ["1. Identificador, Hora y Condición", "2. Viento", "3. Visibilidad", "4. Fenómenos", "5. Nubes y Techo", "6. Temperatura/Punto de Rocío", "7. Presión (QNH)", "8. Tendencia"],
        "Ejemplo": ["SCEL 092200Z AUTO", "21015G25KT", "9999", "-SHRA", "FEW030 BKN080", "26/12", "Q1011", "NOSIG"],
        "Significado": [
            "Aeropuerto (SCEL), Día 09, Hora 22:00 UTC (Z), Automático.",
            "De 210 grados, 15 nudos, Ráfagas (G) de 25 nudos.",
            "10 kilómetros o más (Excelente).",
            "Chubasco (SH) de Lluvia (RA) Ligero (-).",
            "Pocas nubes a 3000 ft, Rotas a 8000 ft.",
            "Temperatura 26°C / Punto de Rocío 12°C.",
            "Presión 1011 Hectopascales.",
            "No hay cambio significativo."
        ]
    })
    
    # Detalles adicionales de códigos
    with st.expander("Ver Códigos Detallados (Intensidad, Descriptores y Fenómenos)"):
        st.markdown("### Códigos Comunes de Fenómenos Meteorológicos")
        
        col_c1, col_c2, col_c3 = st.columns(3)

        with col_c1:
            st.markdown("#### Intensidad/Proximidad")
            st.code("- : Ligera\n(ninguno) : Moderada\n+ : Fuerte\nVC : Cerca (Vicinity)")
            
        with col_c2:
            st.markdown("#### Descriptores (Cómo se ve)")
            st.code("MI : Fina/Baja\nBC : Bancos\nSH : Chubasco\nTS : Tormenta\nFZ : Congelante\nBL : Alta (Blowing)")

        with col_c3:
            st.markdown("#### Fenómenos (Qué es)")
            st.code("RA : Lluvia\nSN : Nieve\nFG : Niebla (Visibilidad < 1km)\nBR : Neblina (Vis. 1-5km)\nHZ : Bruma\nFU : Humo\nGR : Granizo\nPL : Granizo")

        st.markdown("### Otros Códigos Importantes")
        st.code("VRB03KT : Viento Variable a 3 nudos.\nM05/M08 : Temperatura -5°C / Punto de Rocío -8°C.\nVV002 : Visibilidad Vertical de 200 pies (cielo oscurecido).\nNSC : No Significant Clouds (No nubes significativas).\nBECMG : Cambiando permanentemente (Tendencia).\nTEMPO : Cambio temporal (Tendencia).")


def mostrar_logbook():
    st.header("📖 Logbook (Registro de Vuelos)")
    df = leer_vuelos_registrados()
    
    if df.empty:
        st.info("Aún no tienes vuelos registrados. ¡Empieza a volar!")
        return
    
    # Asegurarse de que las columnas sean numéricas para el cálculo
    df['Tiempo_Vuelo_Horas'] = pd.to_numeric(df['Tiempo_Vuelo_Horas'], errors='coerce').fillna(0)
    df['Distancia_NM'] = pd.to_numeric(df['Distancia_NM'], errors='coerce').fillna(0)
    
    # --- Estadísticas Totales ---
    st.subheader("📊 Estadísticas Totales de Vuelo")
    
    col_t1, col_t2, col_t3 = st.columns(3)
    
    total_vuelos = len(df)
    total_horas = df['Tiempo_Vuelo_Horas'].sum()
    total_distancia = df['Distancia_NM'].sum()
    
    col_t1.metric("Total de Vuelos Hechos", total_vuelos)
    col_t2.metric("Total de Horas de Vuelo", f"{total_horas:.1f} h")
    col_t3.metric("Total de Distancia Volada", f"{total_distancia:,.0f} NM")
    
    st.markdown("---")
    
    # --- Detalle y Descarga ---
    st.subheader("Detalle de Vuelos")
    st.dataframe(df, use_container_width=True)
    
    csv_log = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Descargar Logbook (.csv)",
        data=csv_log,
        file_name='logbook_msfs.csv',
        mime='text/csv',
    )


# --- 4. Función Principal y Ejecución ---

def main_app():
    crear_archivo_csv() 

    st.set_page_config(
        page_title="MSFS Logbook & METAR",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("✈️ Compañía Aérea MSFS 2020 🚀")
    
    st.sidebar.header("Menú de Navegación")
    opcion = st.sidebar.selectbox(
        "Elige una herramienta:",
        ["Registro de Vuelo", "Herramienta METAR", "Logbook (Mis Vuelos)"]
    )

    if opcion == "Registro de Vuelo":
        mostrar_registro_vuelo()
    elif opcion == "Herramienta METAR":
        mostrar_herramienta_metar()
    elif opcion == "Logbook (Mis Vuelos)":
        mostrar_logbook()


if __name__ == "__main__":
    random.seed(datetime.now().timestamp())
    main_app()