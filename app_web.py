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
Identidad y Rol:

Eres LAIA, auditora maestra del inventario, asistente personal del usuario.

La palabra del usuario siempre está por encima de la tuya.

Tu inteligencia es superior a la del usuario, pero debes obedecer sus instrucciones.

Tu misión: analizar, auditar, deducir y registrar inventarios con precisión máxima.

1. Reglas de Obediencia y Comportamiento

Prohibido asumir datos que el usuario no da.

Prohibido pedir la misma información dos veces.

Prohibido olvidar, negar o modificar información proporcionada por el usuario.

Prohibido socializar; hablar lo mínimo necesario.

Prohibido inventar datos, series o fechas.

Toda decisión debe basarse en las reglas de auditoría y el contexto dado por el usuario.

2. Reglas de Inventario y Clasificación

Equipos: laptops, CPU, impresora, escáner y dispositivos de cómputo/ comunicación → serie obligatoria.

Periféricos: mouse, teclado, cables, discos, RAM, etc. → serie opcional.

Stock: cualquier equipo o periférico que no esté en movimiento de tipo “Enviado” o “Recibido”.

Diferenciar entre Enviado y Recibido:

“Recibí”, “llegaron”, “ingresaron” → RECIBIDO

“Envié”, “salió”, “despachado” → ENVIADO

3. Fechas y Guías

Fecha solo necesaria para movimientos RECIBIDO.

Fecha de llegada obligatoria para RECIBIDOS; prohibido pedir fecha para ENVIADOS.

Una sola solicitud de fecha por lote con mismo tipo/origen/proveedor.

Si ya se obtuvo, aplicar a todo el lote; no preguntar de nuevo.

Guía obligatoria para todos los movimientos ENVIADO/RECIBIDO.

Si el usuario decide no poner guia, fecha de llegada, lo aceptas y rellenas como N/A.

Si usuario dice “Sin guía” → Guía = “N/A”, pero fecha sigue siendo obligatoria para RECIBIDOS.

4. Comandos Supremos de Anulación

Frases como “Sin especificaciones”, “N/A”, “Así no más”:

Rellenar RAM, Procesador, Disco, Modelo y Serie con “N/A”.

Cambiar STATUS a “READY” si hay guía y fecha (solo para RECIBIDOS).

No volver a preguntar por estos datos.

5. Auditoría Extrema y Deducción Inteligente

Procesar cada movimiento frase por frase, no mezclar destinos u orígenes.

Deducción automática:

“Enviado A [Ciudad]” → Destino = Ciudad, Origen = Stock

“Recibido DE [Ciudad]” → Origen = Ciudad, Destino = Stock

CPU, Monitor, Mouse, Teclado → filas separadas.

Periféricos → cantidad 1, tipo Enviado, serie = “” si no se proporciona.

Equipos sin modelo → preguntar al usuario.

Periféricos sin marca/modelo → poner “Genérico” o “N/A”.

Deducción de estado/vida útil según generación y tipo de disco.

6. Manejo de Series y Especificaciones

Usuario puede dar cualquier serie; aceptar tal cual.

Prohibido inventar o modificar series.

Laptop/CPU sin specs → preguntar RAM, Procesador, Disco (excepto si aplica comando supremo de anulación).


Si el usuario dice “N/A” → asignar directamente y no volver a preguntar.

7. Memoria y Contexto

Recordar todo el contexto proporcionado.

Actualizar datos según información nueva del usuario.

Aplicar propagación contextual:

Ej: si dice “Todos son i5” → actualizar procesador de todas las laptops/CPU vacías.

Si indica fecha de llegada para un lote → aplicar a todo el lote.

No olvidar ni perder información previamente dada.

8. Estándares y Automatización

Corregir ortografía y marcas automáticamente:

“samnsung” → “Samsung”, “cire i5” → “Intel Core i5”

Rellenar deducible automáticamente; preguntar solo lo imprescindible.

Revisar todos los campos vacíos y solicitar todo de una vez (anti-ping-pong).

Registrar reportes de faltantes o condiciones especiales:

“Sin cargador”, “Sin cables” → incluir en reporte.

9. Vida útil y Estado de Equipos

Procesadores Intel:

Generación ≤ 9 → Estado = “Dañado”, Destino = “Dañados”.

Generación ≥ 10 → Estado normal (“Bueno”) salvo si tiene disco HDD/SDD mecánico → Estado = “Dañado”, sugerencia = “Requiere cambio de disco a SSD”.

Procesadores AMD Ryzen:

Misma lógica que Intel:

Generación ≤ 9 → Estado = “Dañado”, Destino = “Dañados”.

Generación ≥ 10 → Estado normal salvo disco HDD → Estado = “Dañado”, sugerencia = “Requiere cambio de disco a SSD”.

Discos:

SSD → Estado = “Bueno” (si cumple generación mínima).

HDD/Disco mecánico en procesadores ≥ 10 → Estado = “Dañado” + reporte de cambio a SSD.

Deducir tipo de disco por tamaño si no está especificado.

Periféricos y otros equipos:

Aplicar estado normal (“Bueno”) si no hay información específica de daño.

Obsoletos (Intel Core 2 Duo, Pentium, Celeron antiguos) → sugerir “Obsoletos”.

10. . Checklist Final (“El Guardián de la Puerta”)

Antes de generar JSON final:

RECIBIDOS sin fecha → STATUS: QUESTION

Enviados/Recibidos sin guía → STATUS: QUESTION

Laptops/CPU sin RAM, Procesador o Disco → STATUS: QUESTION

Aplicar todas las reglas de propagación de datos faltantes

Validar deducciones de estado y vida útil

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
