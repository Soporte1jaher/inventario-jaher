import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="LAIA Intelligence PRO", page_icon="🤖", layout="wide")

# --- CREDENCIALES ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Configura los Secrets (GITHUB_TOKEN y GOOGLE_API_KEY).")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

def obtener_fecha_ecuador():
    return (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")

def obtener_github(archivo):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
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
        "message": "LAIA STRATEGIC UPDATE",
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}"
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

def extraer_json(texto):
    try:
        i = texto.find("[")
        f = texto.rfind("]") + 1
        if i != -1 and f != 0: return texto[i:f]
        return ""
    except: return ""

st.title("🤖 LAIA: Inteligencia Logística Pro V5.0")
t1, t2, t3, t4 = st.tabs(["📝 Registro & Estrategia", "💬 Chat IA", "🗑️ Limpieza Inteligente", "📊 Historial"])

with t1:
    st.subheader("📝 Gestión de Movimientos y Distribución")
    st.info("LAIA procesa cientos de series o cálculos de reparto automáticamente.")
    texto_input = st.text_area("Orden logística:", height=200, placeholder="Ej: Registra estas 50 series... o 'Divide 100 mouses para 10 agencias'...")
    
    if st.button("🚀 Ejecutar Orden", type="primary"):
        if texto_input.strip():
            with st.spinner("LAIA calculando logística..."):
                client = genai.Client(api_key=API_KEY)
                prompt = f"""
                Eres una Estratega Logística Pro. Analiza: "{texto_input}"
                TAREAS:
                1. SI HAY MUCHAS SERIES: Genera un registro individual por cada serie.
                2. SI HAY REPARTO/DIVISIÓN: Calcula la cantidad por agencia y genera los registros de 'Enviado'.
                3. DESTINO: 'Movimientos' (con serie) o 'Stock' (periféricos).
                JSON: [{{ "destino": "...", "tipo": "Enviado/Recibido", "cantidad": n, "equipo": "...", "marca": "...", "serie": "...", "ubicacion": "...", "reporte": "Procesado por LAIA" }}]
                """
                resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                datos = json.loads(extraer_json(resp.text))
                fecha = obtener_fecha_ecuador()
                for d in datos: d["fecha"] = fecha
                if enviar_buzon(datos):
                    st.success(f"✅ LAIA procesó {len(datos)} registros.")
                    st.table(pd.DataFrame(datos).head(10))

with t2:
    st.subheader("💬 Consulta Semántica")
    if p_chat := st.chat_input("¿Qué deseas consultar?"):
        hist, _ = obtener_github(FILE_HISTORICO)
        contexto = f"Datos: {json.dumps(hist[-150:])}. Responde pro. Si preguntan stock, suma Recibidos y resta Enviados de 'Stock'."
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto + p_chat)
        st.markdown(resp.text)

with t3:
    st.subheader("🗑️ Motor de Limpieza Universal")
    st.info("Elimina por cualquier criterio: 'vacíos', 'por marca', 'por tipo', 'por contenido'...")
    txt_borrar = st.text_area("Orden de limpieza:", placeholder="Ej: 'borra los recibidos', 'borra lo que dice sin serie', 'borra marcas patito'...")
    
    if st.button("🗑️ EJECUTAR LIMPIEZA"):
        client = genai.Client(api_key=API_KEY)
        prompt_b = f"""
        Analiza la orden: "{txt_borrar}"
        Clasifica la acción:
        1. 'borrar_todo': Borrar todo el inventario.
        2. 'borrar_vacios': Series vacías, 'nan', 'sin serie', 'no aplica'.
        3. 'borrar_filtro': Borrar por una columna específica (ej: tipo: recibido, marca: hp).
        4. 'borrar_contiene': Borrar si cualquier celda contiene una palabra.
        
        Devuelve LISTA JSON:
        [{{"accion": "...", "columna": "nombre_columna", "valor": "valor_a_buscar"}}]
        """
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
        lista_borrar = json.loads(extraer_json(resp.text))
        if enviar_buzon(lista_borrar):
            st.warning("⚠️ Orden de limpieza enviada al sistema local.")
            st.json(lista_borrar)

with t4:
    if st.button("🔄 Cargar Historial"):
        datos, _ = obtener_github(FILE_HISTORICO)
        if datos: st.dataframe(pd.DataFrame(datos), use_container_width=True)
