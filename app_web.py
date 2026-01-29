import streamlit as st
from openai import OpenAI
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
st.set_page_config(page_title="LAIA v91.2 - Auditora Senior", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
    .stChatFloatingInputContainer { background-color: #0e1117; }
    .stDataFrame { background-color: #1e212b; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CREDENCIALES
# ==========================================
try:
    API_KEY = st.secrets["GPT_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Configura los Secrets (GITHUB_TOKEN y GPT_API_KEY).")
    st.stop()

client = OpenAI(api_key=API_KEY)

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
HEADERS = {"Authorization": "token " + GITHUB_TOKEN, "Cache-Control": "no-cache"}

# ==========================================
# 3. FUNCIONES AUXILIARES
# ==========================================
def extraer_json(texto):
    try:
        texto = texto.replace("```json", "").replace("```", "").strip()
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio != -1 and fin > inicio:
            return texto[inicio:fin].strip()
        return ""
    except:
        return ""

def obtener_github(archivo):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            d = resp.json()
            return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    except:
        pass
    return [], None

def enviar_github(archivo, datos, mensaje="LAIA Update"):
    actuales, sha = obtener_github(archivo)
    if isinstance(datos, list): actuales.extend(datos)
    else: actuales.append(datos)
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode()).decode(),
        "sha": sha
    }
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

# ==========================================
# 4. MOTOR DE STOCK
# ==========================================
def calcular_stock_web(df):
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    df_c = df.copy()
    df_c.columns = df_c.columns.str.lower().str.strip()
    for col in ['estado', 'estado_fisico', 'tipo', 'destino', 'equipo', 'marca', 'cantidad', 'modelo']:
        if col not in df_c.columns: df_c[col] = "No especificado"
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)

    def procesar_fila(row):
        est = str(row['estado']).lower()
        t = str(row['tipo']).lower()
        d = str(row['destino']).lower()
        eq = str(row['equipo']).lower()
        cant = row['cant_n']
        perifericos = ['mouse', 'teclado', 'cable', 'hdmi', 'ponchadora', 'cargador']
        if any(p in eq for p in perifericos):
            return cant if 'recibido' in t else -cant
        if 'dañ' in est or 'obs' in est: return 0
        if d == 'stock' or 'recibido' in t: return cant
        if 'enviado' in t: return -cant
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)
    resumen = df_c.groupby(['equipo', 'marca', 'modelo', 'estado_fisico'])['val'].sum().reset_index()
    movimientos = df_c[df_c['val'] != 0]
    return resumen[resumen['val'] > 0], movimientos

# ==========================================
# 5. PROMPT CEREBRO LAIA
# ==========================================
SYSTEM_PROMPT = """
Eres LAIA, la Auditora Senior de Inventarios de Jaher. Tu inteligencia es superior, deductiva y meticulosa. No eres una secretaria que anota; eres una auditora que VERIFICA.
1. Modo de operación obligatorio:
- Si existe inventario previo, debes buscar y modificar únicamente los campos afectados, sin alterar información válida existente.
- Si no existe inventario, debes crear el registro desde cero aplicando todas las reglas de auditoría sin omisiones.

-------------------------------------------------------------------------------

1. REGLA DE ORO: PROHIBIDO ASUMIR (CONFIRMACIÓN OBLIGATORIA)
- Aunque deduzcas que un equipo es "Usado" (porque viene de agencia), DEBES PREGUNTAR para confirmar.
- NUNCA asumas que un equipo está "Bueno" si el usuario no lo ha dicho. 
- El status "READY" solo se activa cuando el usuario ha validado: 1. Estado (Bueno/Dañado) | 2. Estado Físico (Nuevo/Usado) | 3. Origen/Destino.

2. PROTOCOLO DE PREGUNTAS INTELIGENTES (CERO PING-PONG):
- Si faltan datos, NO preguntes uno por uno. Analiza todo el mensaje y pide lo que falta en una sola respuesta amable.
- Ejemplo: "He anotado el envío a Portete y el combo a Latacunga. Para completar el registro, ¿podrías confirmarme si todos los equipos están buenos y si son nuevos o usados? Además, ¿deseas añadir especificaciones técnicas (RAM/Disco) a la laptop y al CPU?"

3. REGLA DE MERMA Y DESGLOSE DE COMBOS:
- Si el usuario dice "Envío de CPU con monitor, mouse y teclado", genera filas independientes para cada uno.
- Para periféricos (Mouse, Teclado, Cables, etc.) en envíos, usa cantidad: 1 y tipo: "Enviado". Tu script de PC restará el stock automáticamente.

4. DEDUCCIÓN AGRESIVA DE CONTEXTO:
- CIUDADES (Portete, Paute, Latacunga, etc.) -> DEDUCE que es el Destino/Origen.
- DAÑOS (Pantalla trizada, no enciende, falla) -> DEDUCE Estado: "Dañado", Destino: "Dañados". En este caso, NO preguntes si está bueno.
- SINÓNIMOS: "Portátil" = Laptop | "Fierro / Case" = CPU | "Pantalla" = Monitor.

5. REGLA DE MARCA Y MODELO:
- Debes separar la MARCA del MODELO. 
- Ejemplo: "Laptop HP Probook&0G o cualquier marca, debes preguntar al usuario si quiere añadir una marca" -> marca: "HP", modelo: "Probook".
- SIEMPRE PREGUNTA: Si el usuario no da el modelo, debes pedirlo: "¿Cuál es el modelo del equipo?".

6. REGLA DE CARACTERISTICAS:
- DEBES DIFERENCIAR QUE UN PROCESADOR MENOR A LA DECIMA GENERACION AUTOMATICAMENTE SE CATALOGA COMO "DAÑADO" Y IRIA A DAÑADOS.
- SI EL EQUIPO TIENE UN PROCESADOR MAYOR A LA DECIMA GENERACION PERO TIENE DISCO HDD O MECANICO, DEBERAS PONER OBLIGATORIAMENTE EN "reporte" QUE REQUIERE CAMBIO DE DISCO; SEGUIDO LO AÑADES A DAÑADOS Y LO AGREGAS CON EL REPORTE HASTA EL CAMBIO DE DISCO.
- Ejemplo: "CPU XTRATECH SERIE 1234 CON 120 HDD" -> DEBERAS ESPECULAR QUE SI PONE "120 HDD" QUIERE DECIR QUE EL DISCO HDD ES DE UNA CAPACIDAD DE 120GB.

7. ¡NUEVA REGLA CRÍTICA! - GUÍA DE REMISIÓN OBLIGATORIA:
- Si el movimiento es "Enviado" o "Recibido" (implica transporte), EL NÚMERO DE GUÍA ES OBLIGATORIO.
- Si el usuario no da la guía, NO PUEDES PONER "READY". Debes preguntar: "¿Cuál es el número de la guía de remisión?".
- Excepción: Si el movimiento es interno (ej: "Stock" a "Sistemas" en el mismo edificio), la guía puede ser "N/A", pero debes confirmarlo.

8. REGLA DE FECHA DE LLEGADA DE LOS EQUIPOS - GUÍA DE REMISIÓN OBLIGATORIA:
- Si el movimiento es "Enviado" o "Recibido" (implica transporte), LA FECHA DE LLEGADA DE LOS EQUIPOS NO ES OBLIGATORIA PERO ES NECESARIA.
- Si el usuario no da LA FECHA DE LLEGADA, NO PUEDES PONER "READY". Debes preguntar: "¿Cuál es LA FECHA DE LLEGADA DEL EQUIPO O DE LOS EQUIPOS?".
- FECHA DE REGISTRO "FECHA" ES DIFERENTE FECHA DE LLEGADA "FECHA LLEGADA" Y AMBAS SON IMPORTANTES

9. EL SABUESO DE SERIES:
- EQUIPOS: (Laptop, CPU, Monitor, Impresora, Regulador, UPS, Cámaras). REQUIEREN serie obligatoria. ACÉPTALA aunque sea corta o extraña (ej: "aaaaas").
- PERIFÉRICOS: (Mouse, Teclado, Cables, Ponchadora). NO requieren serie.

10. LÓGICA DE OBSOLETOS:
- Si detectas procesadores antiguos (Intel 9na Gen o inferior, Core 2 Duo, Pentium), sugiere mover a "Obsoletos".

11. MEMORIA Y NEGACIONES:
- Si dicen "sin cargador" o "sin modelo", anota "N/A" y NO preguntes más.
- Revisa el historial de la conversación actual antes de preguntar algo que ya se respondió arriba.

12. PREGUNTA DE ESPECIFICACIONES (NUEVO):
- Solo para Laptops y CPUs, una vez tengas los datos básicos, PREGUNTA: "¿Deseas añadir especificaciones técnicas (RAM, Procesador, Disco HDD/SSD)?".
- Si el usuario dice que SÍ, pon esos datos en las columnas 'procesador', 'disco', 'ram', segun corresponda.

13. REGLA REPORTES:
- SI EL USUARIO DICE ALGUN REPORTE EXTRA QUE NO SE PUEDA AÑADIR AL RESTO DE CELDAS, AÑADELO A LA CELDA "reporte".
- EJEMPLO: "LAPTOP DELL SERIE 123456 DE LA AGENCIA PORTETE LLEGA SIN CARGADOR Y LA PANTALLA ROTA" EN REPORTE IRIA: "SIN CARGADOR Y CON LA PANTALLA ROTA" O CUALQUIER PARECIDO A REPORTE. 


SALIDA JSON (CONTRATO DE DATOS OBLIGATORIO):
{
 "status": "READY" o "QUESTION",
 "missing_info": "Mensaje amable pidiendo los datos faltantes",
 "items": [
  {
   "equipo": "...", 
   "marca": "...", 
   "modelo": "...", 
   "serie": "...", 
   "cantidad": 1,
   "estado": "Bueno/Dañado/Obsoleto", 
   "estado_fisico": "Nuevo/Usado",
   "tipo": "Recibido/Enviado", 
   "origen": "...", 
   "destino": "...", 
   "guia": "...",
   "reporte": "...",
   "disco": "...",
   "ram": "...",
   "procesador": "...",
   "fecha_llegada": "...",
  }
 ]
}
"""
# ==========================================
# 6. INTERFAZ PRINCIPAL
# ==========================================
if "messages" not in st.session_state: st.session_state.messages = []
if "draft" not in st.session_state: st.session_state.draft = []
if "status" not in st.session_state: st.session_state.status = "NEW"
if "missing_info" not in st.session_state: st.session_state.missing_info = ""

t1, t2, t3 = st.tabs(["💬 Chat Auditor", "📊 Stock Real", "🗑️ Limpieza"])

with t1:
  for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

  if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.spinner("LAIA Auditando..."):
      contexto_tabla = json.dumps(st.session_state.draft) if st.session_state.draft else "[]"
      response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
          {"role": "system", "content": SYSTEM_PROMPT},
          {"role": "user", "content": f"BORRADOR ACTUAL: {contexto_tabla}\n\nMENSAJE USUARIO: {prompt}"}
        ],
        temperature=0
      )
      res_txt = extraer_json(response.choices[0].message.content)
      if res_txt:
        res_json = json.loads(res_txt)
        st.session_state.draft = res_json.get("items", [])
        st.session_state.status = res_json.get("status", "READY")
        st.session_state.missing_info = res_json.get("missing_info", "")

        msg_laia = f"✅ Tabla actualizada. {st.session_state.missing_info}" if st.session_state.status=="QUESTION" else "✅ Tabla lista para enviar."
        with st.chat_message("assistant"): st.markdown(msg_laia)
        st.session_state.messages.append({"role": "assistant", "content": msg_laia})
        st.rerun()

  if st.session_state.draft:
    st.divider()
    st.subheader("📊 Tabla de Inventario (Edición en Vivo)")
    df_editor = pd.DataFrame(st.session_state.draft)
    columnas_orden = ["equipo","marca","modelo","serie","cantidad","estado","tipo","origen","destino","guia","fecha_llegada","ram","procesador","disco","reporte"]
    df_editor = df_editor.reindex(columns=columnas_orden).fillna("")
    edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True, key="auditoria_editor")
    if not df_editor.equals(edited_df):
      st.session_state.draft = edited_df.to_dict("records")

    c1, c2 = st.columns([1,4])
    with c1:
      if st.button("🚀 ENVIAR AL BUZÓN"):
        if st.session_state.status == "QUESTION":
          st.error(f"⛔ Faltan datos: {st.session_state.missing_info}")
        else:
          with st.spinner("Sincronizando..."):
            fecha_now = (datetime.datetime.now(timezone.utc)-timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
            for d in st.session_state.draft: d["fecha_registro"] = fecha_now
            if enviar_github(FILE_BUZON, st.session_state.draft):
              st.success("✅ Enviado!")
              st.session_state.draft = []
              st.session_state.messages = []
              time.sleep(1)
              st.rerun()
    with c2:
      if st.button("🗑️ Cancelar Todo"):
        st.session_state.draft = []
        st.session_state.messages = []
        st.rerun()
# --- Pestañas Stock y Limpieza quedan igual, integrando el cálculo de stock y generación de Excel del segundo código ---
with t2:
    hist, _ = obtener_github(FILE_HISTORICO)
    if hist:
        df_h = pd.DataFrame(hist)
        df_h.columns = df_h.columns.str.lower().str.strip()
        st_res, st_det = calcular_stock_web(df_h)

        k1, k2 = st.columns(2)
        k1.metric("📦 Stock Total", int(st_res['val'].sum()) if not st_res.empty else 0)
        k2.metric("🚚 Movimientos", len(df_h))

        if not st_res.empty:
            st.dataframe(
                st_res.pivot_table(
                    index=['equipo', 'marca'],
                    columns='estado_fisico',
                    values='val',
                    aggfunc='sum'
                ).fillna(0)
            )

        st.dataframe(st_det, use_container_width=True)
    else:
        st.info("Sincronizando con GitHub...")
with t3:
    st.subheader("🗑️ Limpieza Inteligente")

    txt_borrar = st.text_input("¿Qué deseas eliminar?")

    if st.button("🔥 EJECUTAR BORRADO"):
        if txt_borrar:
            try:
                p_db = (
                    "Actúa como DBA. "
                    "COLUMNAS: [equipo, marca, serie, estado, destino]. "
                    "ORDEN: " + txt_borrar +
                    "\nRESPONDE SOLO JSON: "
                    "{\"accion\":\"borrar_todo\"} "
                    "o "
                    "{\"accion\":\"borrar_filtro\",\"columna\":\"...\",\"valor\":\"...\"}"
                )

                resp = client.responses.create(
                    model="gpt-4o-mini",
                    input=p_db
                )

                texto = resp.output_text
                order = json.loads(extraer_json(texto))

                if enviar_github(FILE_BUZON, order):
                    st.success("✅ Orden enviada.")
                    st.json(order)

            except Exception as e:
                st.error("Error: " + str(e))


if st.sidebar.button("🧹 Borrar Chat"):
    st.session_state.messages = []
    st.session_state.draft = None
    st.rerun()
