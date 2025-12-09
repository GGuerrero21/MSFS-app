import streamlit as st
import csv
import random
import requests
import pandas as pd
from datetime import datetime
import io 

# --- 1. Configuración de Datos Base ---

AEROPUERTOS_EJEMPLO = [
    "JFK", "LAX", "LHR", "CDG", "NRT", "DXB", "PEK", "MIA", "MAD", "SCL", "GRU", "GIG", "EHAM", "EGLL", "KJFK", "KLAX"
]
AEROLINEAS_EJEMPLO = [
    "AirTech Virtual", "FlyPy Airways", "Python Airlines", "DataWings Express", "Random Flights Inc."
]
MODELOS_AVION_EJEMPLO = [
    "Airbus A320neo", "Boeing 747-8 Intercontinental", "Cessna 172 Skyhawk", 
    "Daher TBM 930", "Diamond DA62", "Boeing 787-10 Dreamliner"
]

NOMBRE_ARCHIVO = 'mis_vuelos_msfs2020.csv'
ENCABEZADOS_CSV = [
    "Fecha", "Origen", "Destino", "Ruta", "Aerolinea", "No_Vuelo", "Modelo_Avion", 
    "Tiempo_Vuelo_Horas", "Distancia_NM", "Puerta", "Clase", "Notas"
]

# Diccionario de distancias simuladas (en Millas Náuticas - NM)
DISTANCIAS_NM = {
    "JFK-LAX": 2146, "LHR-CDG": 185, "DXB-NRT": 4905, "MIA-MAD": 3816, "SCL-GRU": 1600,
    "KJFK-KLAX": 2146, "EGLL-EHAM": 201, "KJFK-EGLL": 3004, "KLAX-KJFK": 2146
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
        pass # El archivo ya existe

def calcular_distancia_estimada(origen, destino):
    """Estima la distancia en Millas Náuticas (NM)."""
    clave = f"{origen}-{destino}"
    
    if clave in DISTANCIAS_NM:
        return DISTANCIAS_NM[clave]
    
    # Simulación para rutas desconocidas (usa semilla para consistencia)
    random.seed(origen + destino) 
    return random.randint(300, 7000)

def obtener_metar(icao_code):
    """Obtiene el METAR actual para un código ICAO de 4 letras."""
    if not icao_code or len(icao_code) != 4:
        return "❌ Código ICAO no válido. Debe tener 4 letras (Ej: KJFK)."
        
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao_code.upper()}.TXT"
    
    try:
        headers = {'User-Agent': 'MSFS2020-Companion-App/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            raw_metar = lines[2].strip() if len(lines) >= 3 else "METAR no encontrado."
            fecha_obs = lines[1].strip() if len(lines) >= 2 else "Fecha desconocida"
            
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
        # Usamos pandas para un manejo más robusto de los datos en Streamlit
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
        col1, col2, col3 = st.columns(3)
        
        with col1:
            fecha = st.date_input("Fecha", value=datetime.now())
            origen = st.text_input("Código ICAO de Origen (Ej: KJFK)", "").upper()
            destino = st.text_input("Código ICAO de Destino (Ej: EGLL)", "").upper()

        with col2:
            modelo_avion = st.selectbox("Modelo de Avión", MODELOS_AVION_EJEMPLO)
            aerolinea = st.text_input("Aerolínea Virtual")
            no_vuelo = st.text_input("Número de Vuelo")
        
        with col3:
            tiempo_vuelo_horas = st.number_input("Tiempo de Vuelo Total (Horas)", min_value=0.0, step=0.1, format="%.1f")
            puerta = st.text_input("Puerta/Parking")
            clase = st.selectbox("Clase", ["Economy", "Business", "First", "N/A"])
        
        ruta = st.text_area("Ruta / Plan de Vuelo (Opcional)")
        notas = st.text_area("Notas sobre el vuelo")

        submitted = st.form_submit_button("Guardar Vuelo 💾")

        if submitted:
            if origen and destino and tiempo_vuelo_horas > 0:
                distancia_nm = calcular_distancia_estimada(origen, destino)
                
                datos_vuelo = {
                    "Fecha": fecha.strftime("%Y-%m-%d"),
                    "Origen": origen,
                    "Destino": destino,
                    "Ruta": ruta,
                    "Aerolinea": aerolinea,
                    "No_Vuelo": no_vuelo,
                    "Modelo_Avion": modelo_avion,
                    "Tiempo_Vuelo_Horas": tiempo_vuelo_horas,
                    "Distancia_NM": distancia_nm,
                    "Puerta": puerta,
                    "Clase": clase,
                    "Notas": notas
                }
                
                # Proceso de guardado en CSV
                try:
                    with open(NOMBRE_ARCHIVO, mode='a', newline='', encoding='utf-8') as archivo:
                        escritor_csv = csv.writer(archivo)
                        fila = [datos_vuelo.get(h, '') for h in ENCABEZADOS_CSV]
                        escritor_csv.writerow(fila)
                    
                    st.success(f"✅ ¡Vuelo registrado exitosamente! Ruta {origen}-{destino} ({distancia_nm} NM).")
                except Exception as e:
                    st.error(f"❌ Error al guardar el vuelo: {e}")
            else:
                st.error("Por favor, completa los campos obligatorios (Origen, Destino y Tiempo de Vuelo > 0).")

def mostrar_herramienta_metar():
    st.header("☁️ Herramienta METAR")
    st.markdown("Consulta el informe meteorológico actual para cualquier aeropuerto ICAO.")
    
    icao_code = st.text_input("Ingresa el Código ICAO (4 Letras)", max_chars=4).upper()
    
    if st.button("Buscar METAR 🔎"):
        if len(icao_code) == 4:
            with st.spinner(f"Buscando datos para {icao_code}..."):
                raw_metar = obtener_metar(icao_code) 
            
            if "❌" in raw_metar or "No se encontró" in raw_metar:
                st.error(raw_metar.replace("\n", " "))
            else:
                st.info(raw_metar)
                st.markdown(
                    f"**🔗 Enlace útil para decodificar:** [Decodificador METAR](https://www.aviationweather.gov/metar/decoder?icao={icao_code})"
                )
        else:
            st.warning("El código ICAO debe tener 4 letras.")

def mostrar_logbook():
    st.header("📖 Logbook (Registro de Vuelos)")
    df = leer_vuelos_registrados()
    
    if df.empty:
        st.info("Aún no tienes vuelos registrados. ¡Empieza a volar!")
        return
    
    # Asegurarse de que la columna de tiempo sea numérica para el cálculo
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
    
    # --- Detalle y Filtro ---
    st.subheader("Detalle de Vuelos")
    
    # Permitir al usuario filtrar y buscar en la tabla
    st.dataframe(df, use_container_width=True)
    
    # Opción de descarga del logbook
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
    
    # Menú en la barra lateral
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