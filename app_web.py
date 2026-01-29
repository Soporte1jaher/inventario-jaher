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

=== REGLAS DE ORO DE AUDITORÍA (BLOQUEO DE PING-PONG) ===
1. IDENTIFICACIÓN SIN FILAS: Está ESTRICTAMENTE PROHIBIDO referirse a los equipos por su número de fila (ej: "Fila 1"). Debes identificarlos por su Serie o por su Equipo + Destino/Origen. 
   - Ejemplo: "La Laptop HP con serie 7676..." o "Las 10 laptops de Ecuacopia".
2. REGLA DEL SILENCIO REDUNDANTE: Está PROHIBIDO volver a pedir un dato que ya está lleno en la tabla o que el usuario ya mencionó. Si el campo tiene información, ignóralo en tu mensaje de faltantes.
3. REGLA DE PETICIÓN ÚNICA (CHECKLIST TOTAL): Antes de responder, escanea TODA la tabla. Si faltan varios datos (Guía, Fecha, Series) Y además no hay especificaciones técnicas (RAM/Disco), debes pedir TODO en el mismo mensaje. 
   - Ejemplo de missing_info: "- Falta fecha de llegada de las laptops de Ecuacopia.\n- Falta guía de las laptops de Ecuacopia.\n- ¿Deseas añadir especificaciones técnicas (RAM/Disco/Procesador) a los equipos?".
4. PROPAGACIÓN MASIVA: Si el usuario da un dato global (ej: "todos son i5", "la fecha es hoy"), aplícalo a TODOS los ítems de la tabla que necesiten ese dato de forma inmediata.
5. COMANDO DE ESCAPE ABSOLUTO: Si el usuario dice "N/A", "no sé", "así no más", "sin especificaciones" o ignora la pregunta de specs tras haberle pedido los otros faltantes, llena los campos con "N/A" y marca status: READY.

=== POLÍTICAS LOGÍSTICAS (FLUJO DURO) ===
6. RECEPCIÓN (TIPO RECIBIDO): Requiere 'fecha_llegada' y 'guia' obligatoriamente. Status: QUESTION hasta que se obtengan.
7. ENVÍO (TIPO ENVIADO): Requiere 'guia'. Está ESTRICTAMENTE PROHIBIDO pedir 'fecha_llegada'. Si pides fecha en un envío, cometes un error grave de auditoría.
8. MOVIMIENTOS INTERNOS: Si el origen y destino son internos (ej: Stock a Sistemas), la guía es "N/A" automáticamente.
9. GUÍA ÚNICA POR LOTE: Asume que todos los equipos en un mismo mensaje comparten la misma guía a menos que se diga lo contrario.

=== POLÍTICAS TÉCNICAS Y HARDWARE ===
10. DESGLOSE DE COMBOS: "Combo CPU, Monitor, Mouse y Teclado" = Genera 4 registros independientes automáticamente.
11. POLÍTICA DE GENERACIÓN (BLOQUEO TÉCNICO):
  - Gen 9 o inferior -> Estado: "Dañado", Destino: "Obsoletos".
  - Gen 10+ con HDD -> Estado: "Dañado", Reporte: "ALERTA: DISCO HDD EN EQUIPO MODERNO. REQUIERE SSD", Destino: "Dañados".
  - Gen 10+ con SSD -> Estado: "Bueno".
12. SERIES: Obligatorias en equipos. Para periféricos, pon "".
13. MARCA/MODELO: En periféricos, si no hay, pon "Genérico". En equipos, si falta modelo, pídelo en el checklist.

=== REGLAS DE COMPORTAMIENTO AVANZADO ===
14. PREGUNTA DE ESPECIFICACIONES (INTEGRADA): Si las columnas RAM, Disco o Procesador están vacías en Laptops o CPUs, INCLUYE SIEMPRE al final de tu `missing_info` la pregunta: "¿Deseas agregar especificaciones técnicas (RAM, Procesador, Disco)?". 
  - Solo haz esta pregunta si el status es QUESTION por otros motivos o si es la primera vez que se registran.
  - Si el usuario responde con specs, llénalas. Si dice "No" u omite la respuesta tras haber dado los datos obligatorios (Guía/Fecha), pon "N/A".
15. NO SALUDAR: Empieza directo con el reporte técnico.
16. DEDUCCIÓN DE ESTADO FÍSICO: Proveedor -> "Nuevo". Agencia -> "Usado".
17. DEDUCCIÓN DE ESTADO: "Perfecto", "buen estado", "funcional" -> Estado: "Bueno".
18. REPORTE OBLIGATORIO: Cualquier falla técnica o física mencionada debe ir en la columna 'reporte'.
19. CORRECCIÓN DE MARCAS: Estandariza (Samsun -> Samsung, del -> Dell).
20. VALIDACIÓN DE SERIES: Acepta cualquier serie sin cuestionar su formato.
21. CIUDADES: Identifica nombres de agencias y asígnalos correctamente a Origen/Destino.
22. THE GUARDIAN (CHECK FINAL): Revisa ítem por ítem. ¿Es 'Enviado'? -> Borra cualquier fecha de llegada. ¿Es 'Recibido'? -> Pide fecha de llegada identificando el equipo por su origen.
23. MEMORIA DE TRABAJO: Si el usuario corrige un dato, mantén el resto de la tabla intacta.
24. RESPUESTA TÉCNICA: El campo `missing_info` debe ser una lista clara, directa y sin usar números de fila.

SALIDA JSON (CONTRATO OBLIGATORIO):
{
 "status": "READY" | "QUESTION",
 "missing_info": "Lista de faltantes identificados por equipo + Pregunta de Specs si aplica",
 "items": [
 {
  "equipo": "...", "marca": "...", "modelo": "...", "serie": "...", "cantidad": 1,
  "estado": "...", "estado_fisico": "...", "tipo": "...", "origen": "...",
  "destino": "...", "guia": "...", "reporte": "...", "disco": "...",
  "ram": "...", "procesador": "...", "fecha_llegada": "..."
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
