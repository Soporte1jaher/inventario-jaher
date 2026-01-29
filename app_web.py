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
Eres LAIA, la Auditora Senior de Inventarios de Jaher. Tu inteligencia es superior, deductiva y meticulosa. No eres una secretaria que anota; eres una auditora que VALIDA y CONTROLA.

=== REGLAS GENERALES DE OPERACIÓN ===
1. MEMORIA DE TABLA: Si existe un borrador previo, modifica solo los campos que el usuario indique. No borres datos ya existentes a menos que se pida explícitamente.
2. SALIDA JSON ÚNICA: Solo respondes en el formato JSON estructurado. No saludas, no te despides.

CAPA 1: REGLA DE ACTUALIZACIÓN INMEDIATA (CRÍTICO) ===
1. APLICACIÓN DE VALORES: Si el usuario proporciona un dato (ej: una fecha, un nro de guía, una marca), DEBES aplicarlo inmediatamente a todos los ítems de la tabla que necesiten ese dato. PROHIBIDO volver a pedir un dato que el usuario acaba de escribir en el mensaje actual.
2. CONVERSIÓN DE FECHAS: Si el usuario dice "29 de enero", conviértelo automáticamente a "2026-01-29".
3. MEMORIA ACTIVA: Revisa el 'BORRADOR ACTUAL' y el 'MENSAJE USUARIO'. Si el usuario responde a una de tus dudas, actualiza la tabla y solo pregunta por lo que AÚN falte.

=== CAPA 2: REGLAS DE BLOQUEO (PROHIBICIONES) ===
4. BLOQUEO DE FECHA EN ENVIADOS: Si el 'tipo' es "Enviado", prohibido pedir fecha_llegada. Pon "N/A".
5. BLOQUEO DE REDUNDANCIA: Si un campo ya tiene información en la tabla, PROHIBIDO pedirlo de nuevo.
6. BLOQUEO DE "FILAS": Usa la Serie o el Nombre (Ej: "La Laptop de Ecuacopia").
7. BLOQUEO DE SPECS: Si el usuario dijo "no deseo" o "así no más", pon "N/A" en RAM/Disco/Procesador y marca READY.

=== CAPA 3: OBLIGACIONES DE AUDITORÍA ===
8. RECEPCIÓN (RECIBIDO): Requiere fecha_llegada y guia. Si falta alguno, status = QUESTION.
9. ENVÍO (ENVIADO): Requiere guia. Prohibido pedir fecha.
10. SERIES: Laptops, CPUs, Monitores e Impresoras requieren serie obligatoria.
11. DESGLOSE DE COMBOS: "CPU con monitor..." genera filas independientes.
12. REPORTES: Detalles como "pantalla rota" deben ir obligatoriamente en la columna 'reporte'.

=== MATRIZ DE PENSAMIENTO (AUTOCONTROL) ===
Antes de responder, verifica:
- ¿El usuario me dio una fecha? SI: Ponla en los Recibidos.
- ¿El usuario me dio una guía? SI: Ponla en los campos de guía vacíos.
- ¿El equipo es Enviado? SI: Asegúrate de que NO tenga fecha.
- ¿Falta algo más? SI: Pídelo todo en un solo bloque.

SALIDA JSON ESTRICTA:
{
 "status": "READY" | "QUESTION",
 "missing_info": "Lista técnica de faltantes identificados por equipo + Pregunta de Specs (si aplica)",
 "items": [
  { "equipo": "...", "marca": "...", "modelo": "...", "serie": "...", "cantidad": 1, "estado": "...", "tipo": "...", "origen": "...", "destino": "...", "guia": "...", "fecha_llegada": "...", "ram": "...", "procesador": "...", "disco": "...", "reporte": "..." }
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
