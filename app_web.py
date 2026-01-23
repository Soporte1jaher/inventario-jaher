import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd
import time

# =========================================
# 1. CONFIGURACIÓN
# ==========================================
st.set_page_config(page_title="LAIA v25.0 - Auditora Conectada", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CREDENCIALES
# ==========================================
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Configura los Secrets en Streamlit.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"

HEADERS = {"Authorization": "token " + GITHUB_TOKEN, "Cache-Control": "no-cache"}
def extraer_json(texto):
    try:
        # Limpieza de marcas de markdown
        texto = texto.replace("```json", "").replace("```", "").strip()
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio != -1 and fin > inicio:
            return texto[inicio:fin].strip()
        return texto
    except:
        return ""
def obtener_github(archivo):
    url = "https://api.github.com/repos/" + GITHUB_USER + "/" + GITHUB_REPO + "/contents/" + archivo
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            d = resp.json()
            return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    except: pass
    return [], None

def enviar_github(archivo, datos, mensaje="LAIA Input"):
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


# ==========================================
# 3. MOTOR DE STOCK (ALINEADO CON SINCRONIZADOR)
# ==========================================
def calcular_stock_web(df):
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    df_c = df.copy()
    df_c.columns = df_c.columns.str.lower().str.strip()
    
    # Asegurar columnas para el cálculo
    cols = ['estado', 'estado_fisico', 'tipo', 'destino', 'equipo', 'marca', 'cantidad']
    for col in cols:
        if col not in df_c.columns: df_c[col] = "No especificado"
    
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)

    def procesar_fila(row):
        # USAMOS 'estado' que es lo que tu script sincronizador usa
        est = str(row.get('estado', '')).lower() 
        tipo = str(row.get('tipo', '')).lower()
        dest = str(row.get('destino', '')).lower()
        cant = row['cant_n']
        
        if 'dañ' in est or 'obs' in est: return 0
        if dest == 'stock' or 'recibido' in tipo: return cant
        if 'enviado' in tipo: return -cant
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)
    resumen = df_c.groupby(['equipo', 'marca', 'estado_fisico'])['val'].sum().reset_index()
    resumen = resumen[resumen['val'] > 0]
    return resumen, df_c[df_c['val'] != 0]

# ==========================================
# 4. CEREBRO DE LAIA (CONSTRUCTOR DE JSON PARA SINCRONIZADOR)
# ==========================================
SYSTEM_PROMPT = """
Eres LAIA, la Auditora Senior de Inventarios de Jaher. Tu inteligencia es proactiva, NO eres un formulario vacío. Tu meta es procesar el registro con la MENOR cantidad de preguntas posibles.

REGLA DE ORO DE EXTRACCIÓN:
Antes de preguntar, analiza cada palabra del usuario para llenar estos campos:
1. Equipo: (Laptop, CPU, Monitor, etc.)
2. Marca: (HP, Dell, Lenovo, Forza, etc.)
3. Serie: (Cualquier cadena alfanumérica)
4. Cantidad: (Si no dice, asume 1)
5. Estado: (Bueno/Dañado/Obsoleto)
6. Estado Físico: (Nuevo/Usado)
7. Origen/Agencia: (Cualquier lugar o ciudad mencionada)
8. Tipo: (Recibido/Enviado)
9. Destino: (Stock/Dañados/Obsoletos)

LÓGICA DE DEDUCCIÓN (PROHIBIDO PREGUNTAR SI ESTO SE CUMPLE):
- Si menciona una ciudad o lugar (Tena, Pascuales, Manta, Quito, etc.) -> Eso es el ORIGEN/AGENCIA. Marca automáticamente estado_fisico: "Usado", tipo: "Recibido", destino: "Stock".
- Si menciona "Proveedor" o "Compra" -> estado_fisico: "Nuevo", tipo: "Recibido", destino: "Stock".
- Si menciona "Me llegó", "Recibí", "Ingresó" -> tipo: "Recibido", destino: "Stock".
- Si menciona "Roto", "Falla", "Trizado" -> estado: "Dañado", destino: "Dañados".
- Si menciona "Sin [algo]" (ej: sin cargador) -> Ponlo en el campo 'reporte' y NO preguntes por ello.

INSTRUCCIONES DE RESPUESTA (TRATO HUMANO):
- NUNCA respondas con una lista técnica como ['1. Equipo', '2. Marca'].
- Si te falta información, responde como una persona: "¡Hola! Recibí la info de la laptop HP de Tena. Solo me falta saber si está buena o dañada para terminar."
- Si solo te dijeron "Llegó un equipo", pregunta: "¿Qué equipo llegó (Laptop, CPU, Monitor...)?".

REGLAS DE SERIES:
- EQUIPOS: (Laptop, CPU, Monitor, Impresora, Regulador, UPS, Cámara, Bocina). REQUIEREN SERIE 1:1.
- Si el usuario dice "2 laptops" y da 2 series, ya está. Si da 1, pide la otra.

SALIDA JSON (ESTRICTA):
- status: "QUESTION" o "READY".
- missing_info: TEXTO amigable y conversacional. NUNCA UNA LISTA [].
- items: Lista de objetos con los campos: equipo, marca, serie, cantidad, estado, estado_fisico, tipo, destino, reporte.
"""
# ==========================================
# 5. INTERFAZ
# ==========================================
st.title("🧠 LAIA v25.0 - Enlace a Excel")

if "messages" not in st.session_state: st.session_state.messages = []
if "draft" not in st.session_state: st.session_state.draft = None

t1, t2, t3 = st.tabs(["💬 Chat Auditor", "📊 Dashboard Previo", "🗑️ Limpieza"])

with t1:
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("¿Qué ingresó a bodega hoy?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        try:
            client = genai.Client(api_key=API_KEY)
            hist = ""
            for m in st.session_state.messages: hist += m["role"].upper() + ": " + m["content"] + "\n"
            
            contexto = SYSTEM_PROMPT + "\n\n--- CONVERSACIÓN ---\n" + hist
            response = client.models.generate_content(model="gemini-2.0-flash-exp", contents=contexto)
            
            raw = response.text
            if "```json" in raw: raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw: raw = raw.split("```")[1].split("```")[0]
            
            res_json = json.loads(raw)
            
            # --- BLINDAJE CONTRA EL ERROR DE LISTA ---
            resp_laia = res_json.get("missing_info", "Necesito más detalles.")
            if isinstance(resp_laia, list): # Si la IA mandó una lista por error
                resp_laia = " . ".join(map(str, resp_laia))
            # -----------------------------------------

            if res_json.get("status") == "READY":
                st.session_state.draft = res_json.get("items", [])
                resp_laia = "✅ ¡Excelente! He recolectado toda la información. ¿Confirmas el envío al buzón?"
            else:
                st.session_state.draft = None

            with st.chat_message("assistant"): st.markdown(resp_laia)
            st.session_state.messages.append({"role": "assistant", "content": resp_laia})
        except Exception as e: 
            st.error("Error IA: " + str(e))
    if st.session_state.draft:
        st.table(pd.DataFrame(st.session_state.draft))
        if st.button("🚀 ENVIAR AL BUZÓN PARA SINCRONIZAR"):
            fecha = (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
            for i in st.session_state.draft: i["fecha"] = fecha
            
            if enviar_github(FILE_BUZON, st.session_state.draft):
                # Mensaje más claro para el usuario
                st.success(f"✅ ¡Datos enviados al BUZÓN! Ahora abre el Sincronizador en tu PC para verlos en el Excel.")
                st.session_state.draft = None
                st.session_state.messages = []
                time.sleep(2)
                st.rerun()

with t2:
    # El dashboard lee el histórico para mostrarte qué hay actualmente
    hist, _ = obtener_github(FILE_HISTORICO)
    if hist:
        df_h = pd.DataFrame(hist)
        # Parche de nombres de columnas para el dashboard de LAIA
        df_h.columns = df_h.columns.str.lower().str.strip()
        if 'estado' in df_h.columns and 'condicion' not in df_h.columns:
            df_h['condicion'] = df_h['estado'] # Compatibilidad visual
        
        st_res, st_det = calcular_stock_web(df_h)
        k1, k2 = st.columns(2)
        k1.metric("📦 Stock en Excel", int(st_res['val'].sum()) if not st_res.empty else 0)
        k2.metric("🚚 Total Movimientos", len(df_h))
        
        st.write("#### Resumen por Estado Físico")
        if not st_res.empty:
            st.dataframe(st_res.pivot_table(index=['equipo','marca'], columns='estado_fisico', values='val', aggfunc='sum').fillna(0))
        st.write("#### Detalle de Series")
        st.dataframe(st_det, use_container_width=True)
    else: st.info("Sincronizando con GitHub...")

if st.sidebar.button("🧹 Limpiar Chat"):
    st.session_state.messages = []
    st.session_state.draft = None
    st.rerun()

# --- TAB 3: LIMPIEZA QUIRÚRGICA ---
with t3:
    st.subheader("🗑️ Eliminación y Limpieza Inteligente")
    st.info("💡 Ahora puedes decir: 'Borra todo lo de Dell', 'Elimina los mouses de Pascuales' o 'Quita la serie 123'.")
    
    txt_borrar = st.text_input("Orden de eliminación:", placeholder="Ej: 'Borrar mouses usados de California'")
    
    if st.button("🔥 EJECUTAR ORDEN DE LIMPIEZA", type="primary"):
        if txt_borrar:
            with st.spinner("LAIA analizando intención de borrado..."):
                try:
                    # 1. Obtenemos muestra para que la IA sepa qué hay
                    hist, _ = obtener_github(FILE_HISTORICO)
                    muestra = hist[-5:] if hist else []
                    
                    client = genai.Client(api_key=API_KEY)
                    
                    # 2. Construimos el prompt usando SUMA (+) para evitar errores de llaves {}
                    prompt_b = "Actúa como un DBA experto. Convierte la orden del usuario en un comando JSON.\n\n"
                    prompt_b += "COLUMNAS DISPONIBLES: [fecha, equipo, marca, serie, cantidad, estado, estado_fisico, tipo, destino, reporte]\n"
                    prompt_b += "MUESTRA DE DATOS: " + json.dumps(muestra) + "\n"
                    prompt_b += "ORDEN DEL USUARIO: " + txt_borrar + "\n\n"
                    prompt_b += "REGLAS DE SALIDA (JSON):\n"
                    prompt_b += "1. BORRADO TOTAL -> {\"accion\": \"borrar_todo\"}\n"
                    prompt_b += "2. LIMPIEZA VACÍOS -> {\"accion\": \"borrar_vacios\"}\n"
                    prompt_b += "3. POR FILTRO (ej. marca, equipo, destino) -> {\"accion\": \"borrar_filtro\", \"columna\": \"...\", \"valor\": \"...\"}\n"
                    prompt_b += "4. POR SERIE -> {\"accion\": \"borrar\", \"serie\": \"...\"}\n"
                    prompt_b += "5. GLOBAL (contiene palabra) -> {\"accion\": \"borrar_contiene\", \"valor\": \"...\"}\n\n"
                    prompt_b += "RESPONDE SOLO EL JSON."
                    
                    # 3. Llamada a la IA
                    response = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_b)
                    
                    # 4. Extraer y procesar JSON
                    orden_json = extraer_json(response.text)
                    
                    if orden_json:
                        data_borrado = json.loads(orden_json)
                        # Enviamos la instrucción al buzón (FILE_BUZON)
                        if enviar_github(FILE_BUZON, data_borrado, mensaje="Orden de Limpieza LAIA"):
                            st.success("✅ Orden enviada correctamente al buzón.")
                            st.json(data_borrado)
                            st.info("La limpieza se reflejará en el Excel en la próxima sincronización de tu PC.")
                        else:
                            st.error("Error al conectar con GitHub.")
                    else:
                        st.warning("LAIA no pudo interpretar la orden. Intenta decir: 'Borra la serie [numero]'")
                        
                except Exception as e:
                    # CORRECCIÓN FINAL: Error sin llaves vacías
                    st.error("Error en el motor de limpieza: " + str(e))
