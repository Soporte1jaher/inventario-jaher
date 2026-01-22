import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="LAIA NEURAL ENGINE", page_icon="🧠", layout="wide")

# --- CSS PERSONALIZADO (MAMADÍSIMO) ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e445b; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; border-radius: 4px 4px 0px 0px; padding: 20px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- CREDENCIALES ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Secrets no configurados.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
HEADERS = {"Authorization": f"token {}", "Cache-Control": "no-cache"}

# --- FUNCIONES NUCLEARES ---
def obtener_fecha_ecuador():
    return (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")

def obtener_github(archivo):
    url = f"https://api.github.com/repos/{}/{}/contents/{}"
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            d = resp.json()
            return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    except: pass
    return [], None

def enviar_buzon(datos):
    if not isinstance(datos, list): datos = [datos]
    actuales, sha = obtener_github(FILE_BUZON)
    actuales.extend(datos)
    payload = {
        "message": "LAIA NEURAL EXECUTION",
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    url = f"https://api.github.com/repos/{}/{}/contents/{}"
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

def extraer_json(texto):
    try:
        if "```" in texto:
            texto = texto.split("```")[1]
            if texto.startswith("json"): texto = texto[4:]
        inicio = texto.find("[")
        if inicio == -1: inicio = texto.find("{")
        fin = texto.rfind("]") + 1
        if fin == 0: fin = texto.rfind("}") + 1
        return texto[inicio:fin].strip()
    except: return ""

# --- INTERFAZ ---
st.title("🧠 LAIA: NEURAL INVENTORY ENGINE v6.0")

# Sidebar con Métricas Rápidas
with st.sidebar:
    st.header("📊 Resumen Flash")
    hist, _ = obtener_github(FILE_HISTORICO)
    if hist:
        df_side = pd.DataFrame(hist)
        st.metric("Total Registros", len(df_side))
        st.metric("Equipos en Manta", len(df_side[df_side['ubicacion'].str.contains('Manta', case=False, na=False)]))
        st.metric("Alertas Dañados", len(df_side[df_side['estado'].str.contains('Dañado', case=False, na=False)]))

t1, t2, t3, t4 = st.tabs(["🚀 Operaciones IA", "🔍 Super Buscador", "🧹 Borrado Quirúrgico", "📋 Tablero de Control"])

# --- TAB 1: OPERACIONES ---
with t1:
    col1, col2 = st.columns([2, 1])
    with col1:
        texto_input = st.text_area("Dictado Logístico:", height=200, placeholder="Ej: Recibí 20 CPUs Dell de Quito. Divide 10 para Manta y 10 para Guayaquil. Todos son usados...")
    with col2:
        st.info("💡 **LAIA Razonamiento:**\n- Detecta ciudades automáticamente.\n- Calcula repartos.\n- Clasifica Stock vs Movimiento.")
    
    if st.button("🚀 PROCESAR REGISTRO"):
        with st.spinner("Pensando lógicamente..."):
            client = genai.Client(api_key=API_KEY)
            prompt = f"""
            Eres el núcleo lógico de Jaher. Transforma este texto en JSON operativo.
            TEXTO: "{}"
            REGLAS DE INTELIGENCIA:
            1. Clasifica como 'Stock' si son periféricos (mouse, teclados, cables) o 'Movimientos' si son equipos con serie.
            2. Si el texto implica una división (ej. 'reparte'), crea múltiples JSONs.
            3. Normaliza ciudades: Quito, Guayaquil, Manta, Cuenca, Ambato.
            4. Si el estado no se menciona, asume 'Bueno'.
            5. Formato: [{{"destino": "...", "tipo": "Recibido/Enviado", "cantidad": n, "equipo": "...", "marca": "...", "serie": "...", "estado": "...", "ubicacion": "...", "reporte": "..."}}]
            """
            resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
            json_data = extraer_json(resp.text)
            if json_data:
                datos = json.loads(json_data)
                for d in datos: d["fecha"] = obtener_fecha_ecuador()
                enviar_buzon(datos)
                st.success("Orden enviada al Sincronizador.")
                st.dataframe(pd.DataFrame(datos))

# --- TAB 3: BORRADO QUIRÚRGICO (MAMADÍSIMO) ---
with t3:
    st.subheader("🧹 Eliminación por Razonamiento")
    input_borrar = st.text_input("Describe qué quieres borrar:", placeholder="Ej: Borra el cpu que vino de Ambato ayer por la tarde")
    
    if st.button("🔥 EJECUTAR BORRADO INTELIGENTE"):
        with st.spinner("Buscando el objetivo preciso..."):
            # Contexto completo para que la IA decida
            inventario, _ = obtener_github(FILE_HISTORICO)
            # Solo pasamos columnas clave para no saturar
            contexto_mini = pd.DataFrame(inventario).tail(200)[['fecha', 'equipo', 'serie', 'ubicacion', 'tipo']].to_json()
            
            client = genai.Client(api_key=API_KEY)
            prompt_b = f"""
            DATOS ACTUALES: {contexto_mini}
            PETICIÓN: "{input_borrar}"
            TAREA: Identifica EXACTAMENTE qué registro quiere borrar el usuario.
            Devuelve un JSON con la acción 'borrar_quirurgico' y los campos que lo identifican unívocamente (preferiblemente la serie).
            Si hay varios que coinciden, devuélvelos todos en una lista.
            """
            resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
            orden = extraer_json(resp.text)
            if orden:
                enviar_buzon(json.loads(orden))
                st.warning("⚠️ Orden quirúrgica enviada.")
                st.json(orden)

# --- TAB 4: TABLERO DE CONTROL (SEPARADO) ---
with t4:
    if st.button("🔄 Actualizar Tablero"):
        datos, _ = obtener_github(FILE_HISTORICO)
        if datos:
            df = pd.DataFrame(datos)
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("📦 Stock Disponible (Saldos)")
                df_s = df[df['destino'] == 'Stock'].copy()
                if not df_s.empty:
                    df_s['cant_n'] = pd.to_numeric(df_s['cantidad'], errors='coerce').fillna(0)
                    df_s['val'] = df_s.apply(lambda x: x['cant_n'] if x['tipo'] == 'Recibido' else -x['cant_n'], axis=1)
                    res = df_s.groupby(['equipo', 'marca'])['val'].sum().reset_index()
                    st.dataframe(res, use_container_width=True)
            
            with c2:
                st.subheader("🚚 Últimos Movimientos (Envíos/Llegadas)")
                df_m = df[df['destino'] != 'Stock'].tail(10)
                st.dataframe(df_m[['fecha', 'tipo', 'equipo', 'ubicacion']], use_container_width=True)
            
            st.subheader("📋 Base de Datos Completa")
            st.dataframe(df, use_container_width=True)
