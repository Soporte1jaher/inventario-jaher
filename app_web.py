import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA (ESTÉTICA MAMADA) ---
st.set_page_config(page_title="LAIA NEURAL SYSTEM", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
    .stTextArea>div>div>textarea { background-color: #1a1c23; color: #00ff00; font-family: 'Courier New', monospace; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
</style>
""", unsafe_allow_html=True)

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

# CORREGIDO: Se agregó la variable {GITHUB_TOKEN} dentro de las llaves
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

# --- FUNCIONES DE APOYO (ESTRUCTURA ORIGINAL EXPANDIDA) ---
def obtener_fecha_ecuador():
    return (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")

def obtener_github(archivo):
    # CORREGIDO: Se agregaron las variables a la URL
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            d = resp.json()
            return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    except Exception as e:
        pass
    return [], None

def enviar_buzon(datos):
    if not isinstance(datos, list): datos = [datos]
    actuales, sha = obtener_github(FILE_BUZON)
    actuales.extend(datos)
    payload = {
        "message": "LAIA NEURAL UPDATE",
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    # CORREGIDO: Se agregaron las variables a la URL
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}"
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
        if inicio != -1 and fin > inicio:
            return texto[inicio:fin].strip()
        return texto.strip()
    except: return ""

# --- INTERFAZ ---
st.title("🤖 LAIA NEURAL ENGINE v9.0")
t1, t2, t3, t4 = st.tabs(["📝 Registro Inteligente", "💬 Chat Consultor", "🗑️ Limpieza Quirúrgica", "📊 BI & Historial"])

# --- TAB 1: REGISTRO & ESTRATEGIA (IA MEJORADA V9.3) ---
with t1:
    st.subheader("📝 Gestión de Movimientos")
    st.info("💡 IA V9.3: Detecta Daños Críticos vs Estéticos. Si pides 'Informe Técnico', lo etiqueta automáticamente.")
    texto_input = st.text_area("Orden Logística:", height=200, placeholder="Ej: Recibí Laptop HP con pantalla rota, hacer informe técnico. O llegaron 50 mouses a stock...")
    
    if st.button("🚀 EJECUTAR ACCIÓN INTELIGENTE", type="primary"):
        if texto_input.strip():
            with st.spinner("LAIA diagnosticando estado y procesando inventario..."):
                try:
                    client = genai.Client(api_key=API_KEY)
                    
                    # --- PROMPT MAESTRO DE DIAGNÓSTICO ---
                    prompt = f"""
                    Actúa como un Auditor de Inventario y Técnico de Soporte Nivel 2.
                    TEXTO ORIGINAL: "{texto_input}"
                    
                    TU MISIÓN (SIGUE ESTOS PASOS ESTRICTAMENTE):

                    1. **CORRECCIÓN ORTOGRÁFICA**: 
                       - Corrige errores (ej: "cragador"->"Cargador", "mause"->"Mouse", "laptp"->"Laptop").

                    2. **DIAGNÓSTICO DE ESTADO (CRÍTICO)**:
                       - **DAÑADO**: Si menciona fallas funcionales (ej: "Pantalla rota", "No prende", "No da video", "Teclado no sirve", "Golpeado fuerte").
                         -> El campo 'estado' DEBE SER "Dañado".
                       - **USADO**: Si solo son defectos cosméticos (ej: "Rayones", "Despintado", "Sucio", "Gomas gastadas").
                         -> El campo 'estado' DEBE SER "Usado".

                    3. **SOLICITUD DE INFORME TÉCNICO (IT)**:
                       - Si el usuario pide "Hacer informe", "Revisar", "Diagnosticar" o "IT":
                         -> AGREGA la etiqueta "[REQUIERE IT]" al principio del campo 'reporte'.

                    4. **LÓGICA DE STOCK Y ACCESORIOS**:
                       - Si dice "a stock", "bodega" o son consumibles masivos (50 mouses) -> Destino: "Stock", Cantidad: Total.
                       - Equipos con serie (Laptop, CPU) -> Cantidad: 1 (una fila por equipo).
                       - **Accesorio Adjunto** ("Laptop con cargador") -> NO crees fila extra. Ponlo en 'reporte' de la Laptop.
                       - **Accesorio Suelto** ("50 cargadores a stock") -> SÍ crea fila.

                    FORMATO DE SALIDA (JSON ARRAY):
                    Ejemplo Dañado:
                    [{{ "destino": "Taller", "tipo": "Recibido", "cantidad": 1, "equipo": "Laptop", "marca": "Dell", "serie": "ABC", "estado": "Dañado", "ubicacion": "Mesa 1", "reporte": "[REQUIERE IT] Pantalla trizada y bisagra rota. Incluye cargador." }}]
                    """
                    
                    resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
                    json_limpio = extraer_json(resp.text)
                    
                    if json_limpio:
                        datos = json.loads(json_limpio)
                        fecha = obtener_fecha_ecuador()
                        for d in datos: d["fecha"] = fecha
                        
                        if enviar_buzon(datos):
                            st.success(f"✅ LAIA procesó {len(datos)} registros.")
                            if any(d.get('estado') == 'Dañado' for d in datos):
                                st.warning("⚠️ Se detectaron equipos DAÑADOS. Se moverán a la hoja de reportes.")
                            st.table(pd.DataFrame(datos))
                        else:
                            st.error("Error de conexión con GitHub.")
                    else:
                        st.warning("La IA no pudo interpretar la orden. Intenta ser más específico.")
                            
                except Exception as e:
                    st.error(f"Error crítico en IA: {e}")

# --- TAB 2: CHAT IA (CON CONTEXTO DE INVENTARIO) ---
with t2:
    st.subheader("💬 Consulta Inteligente")
    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p_chat := st.chat_input("¿Qué equipos tenemos en Ambato?"):
        st.session_state.messages.append({"role": "user", "content": p_chat})
        with st.chat_message("user"): st.markdown(p_chat)
        
        # Inyectamos el historial completo para que la IA responda con la verdad
        hist, _ = obtener_github(FILE_HISTORICO)
        # Convertir a string seguro para el prompt
        hist_str = json.dumps(hist[-150:]) if hist else "[]"
        contexto = f"INVENTARIO ACTUAL: {hist_str}. Responde basado solo en estos datos."
        
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto + p_chat)
        
        with st.chat_message("assistant"): st.markdown(resp.text)
        st.session_state.messages.append({"role": "assistant", "content": resp.text})

# --- TAB 3: LIMPIEZA QUIRÚRGICA (LA MAGIA QUE PEDISTE) ---
with t3:
    st.subheader("🗑️ Eliminación por Razonamiento")
    st.warning("⚠️ Aquí puedes ser descriptivo: 'Borra el CPU de Ambato' o 'Borra los mouses dañados'")
    txt_borrar = st.text_input("¿Qué quieres eliminar?")
    
    if st.button("🔥 EJECUTAR BORRADO DE PRECISIÓN"):
        if txt_borrar:
            with st.spinner("LAIA localizando el registro en el historial..."):
                # PASO 1: Obtener historial para que la IA identifique el registro
                hist, _ = obtener_github(FILE_HISTORICO)
                contexto_borrado = json.dumps(hist[-100:]) if hist else "[]"
                
                client = genai.Client(api_key=API_KEY)
                # CORREGIDO: Se insertó {txt_borrar} en el prompt
                prompt_b = f"""
                DADOS ESTOS REGISTROS: {contexto_borrado}
                ORDEN DEL USUARIO: "{txt_borrar}"
                TAREA: Identifica qué registro exacto quiere borrar. 
                Responde UNICAMENTE un JSON con este formato:
                [{{"accion": "borrar_quirurgico", "serie": "SERIE_A_BORRAR", "equipo": "NOMBRE", "motivo": "RAZON"}}]
                Si el usuario dice "borra todo", la accion es "borrar_todo".
                """
                resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
                orden_json = extraer_json(resp.text)
                
                if orden_json:
                    try:
                        data_borrado = json.loads(orden_json)
                        if enviar_buzon(data_borrado):
                            st.success("🎯 LAIA identificó el registro y envió la orden de eliminación.")
                            st.json(orden_json)
                    except Exception as e:
                        st.error(f"Error procesando respuesta de borrado: {e}")
                else:
                    st.error("LAIA no pudo identificar qué registro borrar.")

# --- TAB 4: HISTORIAL & BI (MEJORADO) ---
with t4:
    col1, col2, col3 = st.columns(3)
    datos, _ = obtener_github(FILE_HISTORICO)
    
    if datos:
        df = pd.DataFrame(datos)
        col1.metric("Total Registros", len(df))
        # Validar si existen las columnas antes de filtrar para evitar errores
        if 'destino' in df.columns:
            col2.metric("En Stock", len(df[df['destino']=='Stock']))
            col3.metric("Movimientos", len(df[df['destino']=='Movimientos']))
        
        st.subheader("📋 Base de Datos Maestra")
        st.dataframe(df, use_container_width=True)
        
        # Botón para descargar CSV
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Inventario Completo", data=csv, file_name="inventario_jaher.csv", mime="text/csv")
    else:
        st.info("El inventario está vacío.")
