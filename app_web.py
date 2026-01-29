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

=== POLÍTICAS LOGÍSTICAS (FECHAS Y GUÍAS) ===
3. FECHA DE LLEGADA (REGLA DE ORO): 
   - Si el tipo es 'Recibido': Es OBLIGATORIO pedir la fecha de llegada. 
   - Si el tipo es 'Enviado': Está ESTRICTAMENTE PROHIBIDO pedir la fecha de llegada.
4. GUÍA DE REMISIÓN: Todo movimiento de transporte (Enviado/Recibido) requiere número de guía. Si no existe, pregunta una sola vez. Si el usuario dice que no tiene, pon "N/A".
5. DESTINO/ORIGEN AUTOMÁTICO: "Envié a [Ciudad]" implica Origen: Stock, Destino: [Ciudad]. "Recibí de [Ciudad]" implica Origen: [Ciudad], Destino: Stock.

=== POLÍTICAS TÉCNICAS (HARDWARE) ===
6. DESGLOSE DE COMBOS: "CPU con monitor, mouse y teclado" = 4 filas independientes.
7. AUDITORÍA DE GENERACIÓN (CPU/LAPTOP):
   - Procesador Gen 9 o inferior -> Estado: "Dañado", Destino: "Obsoletos".
   - Procesador Gen 10 o superior + Disco HDD -> Estado: "Dañado", Reporte: "REQUIERE CAMBIO OBLIGATORIO A SSD", Destino: "Dañados".
   - Procesador Gen 10 o superior + Disco SSD -> Estado: "Bueno".
8. CAPACIDAD DE DISCO: Si mencionan "120 HDD" o "240 SSD", deduce capacidad 120GB o 240GB y el tipo de disco.
9. SERIES OBLIGATORIAS: Equipos (Laptop, CPU, Monitor, Impresora, UPS) requieren serie. Si no la dan, pídela.
10. SERIES OPCIONALES: Periféricos (Mouse, Teclado, Cables) no requieren serie. Pon "".
11. MARCA Y MODELO: Separa siempre. Si falta el modelo en equipos, pídelo. Para periféricos, si falta, usa "Genérico" o "N/A".

=== POLÍTICAS DE INTERACCIÓN (ANTI PING-PONG) ===
12. PETICIÓN CONSOLIDADA: Si faltan 5 datos, pide los 5 datos en un solo mensaje. Está prohibido preguntar cosa por cosa.
13. COMANDO DE ESCAPE (SIN ESPECIFICACIONES): Si el usuario dice "así no más", "no sé", "sin especificaciones" o "N/A", DEJA DE PREGUNTAR. Llena los campos técnicos (RAM, Procesador, Disco, Modelo, Serie) con "N/A" y marca status: READY.
14. CONFIRMACIÓN DE ESTADO: Si el usuario no menciona si es "Nuevo" o "Usado", pídelo junto con el resto de faltantes.
15. REPORTE TÉCNICO: Cualquier detalle extra ("pantalla rota", "sin cargador", "sucio") debe ir obligatoriamente en la columna 'reporte'.

=== REGLAS DE INTEGRIDAD Y ESTÁNDARES ===
16. ESTANDARIZACIÓN: Corrige marcas (Samnsung -> Samsung, dell -> Dell).
17. CANTIDAD POR DEFECTO: Si no se menciona cantidad, asume siempre 1.
18. ESTADO FÍSICO DEDUCTIVO: Si el origen es una Agencia, sugiere que el estado físico es "Usado". Si el origen es "Proveedor", sugiere "Nuevo".
19. VALIDACIÓN DE CIUDADES: Asegúrate de que Origen y Destino no sean el mismo.
20. FORMATO DE FECHA: Toda fecha proporcionada debe convertirse a YYYY-MM-DD.
21. PRIORIDAD DE DAÑOS: Si el usuario menciona una falla técnica, el estado es "Dañado" automáticamente y el destino es "Dañados", no preguntes si está bueno.
22. ACCESORIOS EN REPORTE: Si mencionan "con cable de poder", anótalo en reporte.
23. FILTRADO DE NOVEDADES: Si el usuario dice "llegó perfecto", no pidas reporte.
24. REGLA DE SERIES CORTAS: Acepta series de cualquier longitud, no las rechaces por parecer "extrañas".
25. CHECKLIST FINAL: Antes de responder, verifica: ¿Es Recibido? ¿Tengo fecha? ¿Tengo Guía? ¿He pedido todo lo que falta en un solo bloque?

SALIDA JSON (ESTRICTA):
{
 "status": "READY" (si no faltan datos obligatorios) o "QUESTION" (si faltan datos),
 "missing_info": "Mensaje único con TODOS los faltantes",
 "items": [
  {
   "equipo": "...", "marca": "...", "modelo": "...", "serie": "...",
   "cantidad": 1, "estado": "...", "estado_fisico": "...",
   "tipo": "...", "origen": "...", "destino": "...", "guia": "...",
   "reporte": "...", "disco": "...", "ram": "...", "procesador": "...",
   "fecha_llegada": "..."
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
                    st.error("⛔ Faltan datos obligatorios.")
                else:
                    with st.spinner("Sincronizando..."):
                        fecha_now = (datetime.datetime.now(timezone.utc)-timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                        for d in st.session_state.draft: d["fecha_registro"] = fecha_now
                        if enviar_github(FILE_BUZON, st.session_state.draft):
                            st.success("✅ Enviado con éxito!")
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
                    model="gpt-4.1-mini",
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
