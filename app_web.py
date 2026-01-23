import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd
import time

# ==========================================
# 1. CONFIGURACIÓN Y ESTILOS
# ==========================================
st.set_page_config(page_title="LAIA v24.0 - Agente Logístico Pro", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
    .stChatFloatingInputContainer { background-color: #0e1117; }
    .status-card { background-color: #161b22; border-radius: 10px; padding: 15px; border-left: 5px solid #2e7d32; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CREDENCIALES Y GITHUB
# ==========================================
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

HEADERS = {"Authorization": "token " + GITHUB_TOKEN, "Cache-Control": "no-cache"}

def obtener_github(archivo):
    url = "https://api.github.com/repos/" + GITHUB_USER + "/" + GITHUB_REPO + "/contents/" + archivo
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            d = resp.json()
            return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    except: pass
    return [], None

def enviar_github(archivo, datos, mensaje="Update"):
    actuales, sha = obtener_github(archivo)
    if isinstance(datos, list): actuales.extend(datos)
    else: actuales.append(datos)
        
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    url = "https://api.github.com/repos/" + GITHUB_USER + "/" + GITHUB_REPO + "/contents/" + archivo
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

# ==========================================
# 3. MOTOR DE STOCK (NUEVO vs USADO)
# ==========================================
def calcular_stock_web(df):
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    df_c = df.copy()
    df_c.columns = df_c.columns.str.lower().str.strip()
    df_c['cantidad'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)
    
    columnas = ['condicion', 'estado_fisico', 'tipo', 'destino', 'equipo', 'marca']
    for col in columnas:
        if col not in df_c.columns: df_c[col] = "No especificado"

    def procesar_fila(row):
        condicion = str(row.get('condicion', '')).lower()
        tipo = str(row.get('tipo', '')).lower()
        dest = str(row.get('destino', '')).lower()
        cant = row['cantidad']
        if 'dañ' in condicion or 'obs' in condicion: return 0
        if 'stock' in dest or 'recibido' in tipo: return cant
        if 'enviado' in tipo: return -cant
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)
    stock_resumen = df_c.groupby(['equipo', 'marca', 'estado_fisico'])['val'].sum().reset_index()
    stock_resumen = stock_resumen[stock_resumen['val'] > 0]
    stock_detalle = df_c[df_c['val'] > 0].copy()
    return stock_resumen, stock_detalle

# ==========================================
# 4. EL CEREBRO DE LAIA (PROMPT MAESTRO)
# ==========================================
SYSTEM_PROMPT = """
Eres LAIA, la inteligencia de control de inventarios de Jaher. No eres un chatbot común, eres una AUDITORA.

TU MISIÓN:
Registrar movimientos de bodega con precisión absoluta. El registro SOLO se completa cuando tienes TODA la información.

REGLAS DE CLASIFICACIÓN:
1. EQUIPOS (Serie Obligatoria): Laptop, CPU, Monitor, Impresora, Cámaras, Bocinas.
   - REGLA DE ORO: 1 Equipo = 1 Serie.
   - Si dicen "2 laptops", DEBES recibir 2 series distintas.
2. PERIFÉRICOS (Sin Serie): Mouse, Teclado, Cables, Cargadores. Solo importa la cantidad.

REGLAS DE CUESTIONAMIENTO (Ponte lista):
- Si falta el ORIGEN (¿De dónde viene? Proveedor, Agencia Pascuales, etc.), ¡PREGUNTA!
- Si falta la MARCA, ¡PREGUNTA!
- Si falta el ESTADO FÍSICO (¿Nuevo o Usado?), ¡PREGUNTA!
- Si falta la CONDICIÓN (¿Bueno o Dañado?), ¡PREGUNTA!
- Si mencionan daños (roto, no prende, quemado), asume CONDICIÓN="Dañado" y DESTINO="Bodega Dañados".
- Si algo está "Bueno" pero va a "Taller", pregunta por qué.
- IGNORA comentarios irrelevantes como "tiene stickers" o "está sucio", pero anótalos en el reporte si quieres.

MEMORIA:
Revisa todo el historial. Si el usuario dio las series en un mensaje y la marca en otro, únelos.

SALIDA JSON (Estricta):
Si falta algo (aunque sea un solo dato):
{ "status": "QUESTION", "missing_info": "Escribe aquí tu pregunta al usuario" }

Si todo está completo (Cantidad = Número de series para equipos):
{
  "status": "READY",
  "items": [
    {
      "equipo": "Laptop",
      "marca": "HP",
      "serie": "ABC123",
      "cantidad": 1,
      "estado_fisico": "Usado",
      "condicion": "Bueno",
      "tipo": "Recibido",
      "destino": "Stock",
      "reporte": "Viene de Agencia Pascuales"
    }
  ]
}
"""

# ==========================================
# 5. INTERFAZ Y LÓGICA DE DIÁLOGO
# ==========================================
st.title("🧠 LAIA v24.0: Super Auditora")

if "messages" not in st.session_state: st.session_state.messages = []
if "draft" not in st.session_state: st.session_state.draft = None

tab1, tab2 = st.tabs(["💬 Chat Auditor", "📊 Dashboard de Stock"])

with tab1:
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("Escribe tu orden logística aquí..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        try:
            client = genai.Client(api_key=API_KEY)
            
            # Construcción de la memoria total para la IA
            historial_completo = ""
            for msg in st.session_state.messages:
                historial_completo += msg["role"].upper() + ": " + msg["content"] + "\n"

            contexto = SYSTEM_PROMPT + "\n\n--- HISTORIAL DE AUDITORÍA ---\n" + historial_completo + "\n\n--- INSTRUCCIÓN ---\nAnaliza si con lo que ha dicho el usuario ya podemos cerrar el registro o si falta preguntar algo más."
            
            response = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto)
            
            # Limpieza del JSON
            raw_text = response.text
            if "```json" in raw_text: raw_text = raw_text.split("```json")[1].split("```")[0]
            elif "```" in raw_text: raw_text = raw_text.split("```")[1].split("```")[0]
            
            res_json = json.loads(raw_text)
            
            if res_json.get("status") == "READY":
                st.session_state.draft = res_json.get("items", [])
                resp_laia = "✅ He verificado toda la información. Los datos son coherentes. ¿Deseas que guarde esto en el inventario?"
            else:
                resp_laia = res_json.get("missing_info", "Necesito más detalles para proceder.")
                st.session_state.draft = None

            with st.chat_message("assistant"): st.markdown(resp_laia)
            st.session_state.messages.append({"role": "assistant", "content": resp_laia})

        except Exception as e:
            st.error("Error de análisis: " + str(e))

    if st.session_state.draft:
        st.write("---")
        st.markdown("### 📋 Pre-visualización del Registro")
        df_draft = pd.DataFrame(st.session_state.draft)
        st.table(df_draft)
        
        c1, c2 = st.columns(2)
        if c1.button("✅ CONFIRMAR Y SUBIR A BODEGA"):
            with st.spinner("Sincronizando con GitHub..."):
                fecha_ecu = (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                for item in st.session_state.draft: item["fecha"] = fecha_ecu
                
                if enviar_github(FILE_BUZON, st.session_state.draft):
                    st.success("¡Datos guardados! El chat se reiniciará.")
                    st.session_state.draft = None
                    st.session_state.messages = []
                    time.sleep(2)
                    st.rerun()
                else: st.error("Error de conexión.")
        
        if c2.button("❌ CANCELAR REGISTRO"):
            st.session_state.draft = None
            st.rerun()

# ==========================================
# 6. DASHBOARD (OPCIÓN B + DETALLE)
# ==========================================
with tab2:
    hist, _ = obtener_github(FILE_HISTORICO)
    if hist:
        df_hist = pd.DataFrame(hist)
        
        # --- BLINDAJE ANTI-KEYERROR ---
        # 1. Pasamos todo a minúsculas para no pelear con mayúsculas/minúsculas
        df_hist.columns = df_hist.columns.str.lower().str.strip()
        
        # 2. Lista de columnas que el sistema NUEVO necesita
        columnas_vitales = ['equipo', 'marca', 'serie', 'cantidad', 'estado_fisico', 'condicion', 'tipo', 'destino']
        
        # 3. Si una columna no existe en tu JSON viejo, la creamos con un valor por defecto
        for col in columnas_vitales:
            if col not in df_hist.columns:
                df_hist[col] = "No especificado"
        
        # 4. Forzamos que la cantidad sea número
        df_hist['cantidad'] = pd.to_numeric(df_hist['cantidad'], errors='coerce').fillna(1)
        # ------------------------------

        # Ahora sí calculamos el stock sin miedo a errores
        st_resumen, st_detalle = calcular_stock_web(df_hist)
        
        k1, k2, k3 = st.columns(3)
        total_st = int(st_resumen['val'].sum()) if not st_resumen.empty else 0
        k1.metric("📦 Stock Total", total_st)
        
        # El conteo de dañados ahora es seguro porque 'condicion' existe sí o sí
        danados = len(df_hist[df_hist['condicion'].astype(str).str.lower().str.contains('dañ', na=False)])
        k2.metric("⚠️ Dañados", danados)
        k3.metric("🚚 Movimientos", len(df_hist))

        t_res, t_det, t_dañ = st.tabs(["📦 Stock (Resumen)", "🔍 Stock (Series)", "🚨 Bodega Dañados"])
        
        with t_res:
            st.write("#### Saldo por Estado (Nuevo/Usado)")
            if not st_resumen.empty:
                try:
                    res_pivot = st_resumen.pivot_table(index=['equipo', 'marca'], 
                                                     columns='estado_fisico', 
                                                     values='val', 
                                                     aggfunc='sum').fillna(0)
                    st.dataframe(res_pivot, use_container_width=True)
                except: 
                    st.dataframe(st_resumen, use_container_width=True)
            else: 
                st.info("No hay stock disponible.")

        with t_det:
            if not st_detalle.empty:
                # Mostramos solo las columnas que nos interesan
                cols_ver = ['fecha', 'equipo', 'marca', 'serie', 'estado_fisico', 'condicion', 'destino']
                existentes = [c for c in cols_ver if c in st_detalle.columns]
                st.dataframe(st_detalle[existentes], use_container_width=True, hide_index=True)

        with t_dañ:
            df_bad = df_hist[df_hist['condicion'].astype(str).str.lower().str.contains('dañ|obs', na=False)]
            if not df_bad.empty: 
                st.error(f"Se han encontrado {len(df_bad)} registros en mal estado.")
                st.dataframe(df_bad, use_container_width=True)
            else: 
                st.success("Sin equipos dañados en el historial.")
    else: 
        st.warning("Esperando datos del histórico o archivo vacío...")
