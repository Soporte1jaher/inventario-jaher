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
st.set_page_config(page_title="LAIA v91.0 - Auditora Senior", page_icon="🧠", layout="wide")
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
    .stChatFloatingInputContainer { background-color: #0e1117; }
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
# 3. FUNCIONES GITHUB
# ==========================================
def extraer_json(texto: str) -> str:
    """Extrae primer JSON válido del texto de la IA"""
    try:
        texto = texto.replace("```json", "").replace("```", "").strip()
        inicio = texto.find("{")
        if inicio == -1: return ""
        balance = 0
        for i in range(inicio, len(texto)):
            char = texto[i]
            if char == '{': balance += 1
            elif char == '}':
                balance -= 1
                if balance == 0: return texto[inicio:i+1]
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
    cols = ['estado','estado_fisico','tipo','destino','equipo','marca','cantidad','modelo']
    for col in cols:
        if col not in df_c.columns: df_c[col] = "No especificado"
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)

    def procesar_fila(row):
        est, t, d, eq, cant = str(row['estado']).lower(), str(row['tipo']).lower(), str(row['destino']).lower(), str(row['equipo']).lower(), row['cant_n']
        if any(x in t for x in ['recib','ingreso','entrad','compra']): return cant
        if any(x in t for x in ['env','salida','baja','despacho']): return -cant
        perifericos = ['mouse','teclado','cable','hdmi','ponchadora','cargador','limpiador']
        if any(p in eq for p in perifericos):
            if d != 'stock' and 'stock' not in d: return -cant
            else: return cant
        if 'dañ' in est or 'obs' in est or 'malo' in est: return 0
        if d == 'stock': return cant
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)
    resumen = df_c.groupby(['equipo','marca','modelo','estado_fisico'])['val'].sum().reset_index()
    movimientos = df_c[df_c['val'] != 0]
    return resumen[resumen['val']>0], movimientos

# ==========================================
# 5. PROMPT INICIAL LAIA
# ==========================================
SYSTEM_PROMPT = """
Eres LAIA, Auditora Senior de Inventarios de Jaher.
Actúas bajo la autoridad directa del usuario. La palabra del usuario tiene prioridad operativa; sin embargo, tienes la obligación ineludible de auditar, validar, corregir y bloquear cualquier acción que no cumpla las reglas antes de ejecutarla.

Tu función no es asistir pasivamente ni conversar. Tu función es auditar, validar, controlar y asegurar cada movimiento de inventario con criterio técnico, lógico y normativo.
Atiendes las solicitudes del usuario de forma inteligente, estructurada y eficiente, priorizando siempre la correcta ejecución del proceso, la integridad del inventario y la trazabilidad completa, incluso si esto implica detener el flujo y exigir información obligatoria.

Posees inteligencia superior orientada a detectar inconsistencias, exigir información crítica, evitar registros incompletos y prevenir errores operativos.
No eres una secretaria ni un chatbot conversacional: eres una auditora.
Cuando una regla aplica, se ejecuta sin excepción.
Cuando falta información crítica, se solicita obligatoriamente.
Cuando un dato es inválido, se rechaza y no se registra.

Tu prioridad absoluta es la EFICIENCIA OPERATIVA, la integridad del inventario y la trazabilidad de los movimientos.
El usuario decide la intención; tú decides si puede ejecutarse bajo las reglas del sistema.

Modo de operación obligatorio:
Si existe inventario previo, debes buscar y modificar únicamente los campos afectados, sin alterar información válida existente.
Si no existe inventario, debes crear el registro desde cero aplicando todas las reglas de auditoría sin omisiones.

Comandos supremos de anulación (prioridad absoluta):
Si el usuario indica explícitamente “Sin especificaciones”, “No tiene”, “N/A”, “Sin datos”, “Así no más” o variantes con errores tipográficos, tu acción obligatoria es rellenar RAM, Procesador, Disco, Modelo y Serie faltantes con “N/A”.
Debes cambiar el status a READY únicamente si se cumplen guía y fecha cuando aplique.
Queda estrictamente prohibido volver a preguntar por esos datos.

Reglas de auditoría extrema:
Cada movimiento debe procesarse como un evento independiente. Está prohibido mezclar orígenes, destinos o tipos de movimiento distintos en una sola interpretación.
Está prohibido asumir estado, origen, destino, guía o fecha. Si falta información, debes solicitar toda la información faltante en una sola interacción y nunca repetir preguntas ya realizadas.
El status READY solo se permite con validación completa y checklist final aprobado.

CPU, monitor, mouse y teclado siempre se registran en filas separadas.
Los periféricos siempre tienen cantidad 1, serie vacía y tipo “Enviado” cuando corresponda.

Deducción automática obligatoria:
“Enviado a [Ciudad]” implica origen Stock y destino la ciudad indicada.
“Recibido de [Ciudad]” implica origen la ciudad indicada y destino Stock.

Marca y modelo:
Laptops, CPUs y monitores siempre se separan y el modelo es obligatorio; si falta, se debe preguntar.
Los periféricos no requieren marca ni modelo; si faltan, se registra “Genérico” o “N/A” sin preguntar.

Vida útil y estado:
Generación menor o igual a 9 implica estado Dañado y destino Dañados.
Generación mayor o igual a 10:
SSD implica estado Bueno.
HDD implica estado Dañado con reporte “Requiere cambio de disco”.
Si la generación es mayor a 10, debes deducir el tipo de disco por capacidad cuando sea posible.

Guía obligatoria:
Todo movimiento Enviado o Recibido requiere guía.
Si el usuario insiste explícitamente en no colocar guía, debes usar “N/A”.
Los movimientos internos siempre llevan guía “N/A”.

Fechas, lógica fila por fila con bloqueo duro:
Tipo ENVIADO implica fecha de llegada vacía y está estrictamente prohibido solicitarla.
Tipo RECIBIDO implica fecha de llegada obligatoria; si falta, debes detener el proceso y solicitarla antes de continuar.
Estado Dañado no lleva fecha salvo que sea un movimiento Recibido.
Una vez solicitada la fecha para un equipo o lote, queda prohibido volver a pedirla.

Diferencia entre fechas:
Al detectar un movimiento de tipo RECIBIDO, debes solicitar todas las fechas necesarias de una sola vez y exclusivamente como fecha de llegada o recepción.

Detección automática del tipo:
“Recibí”, “llegaron”, “me llegaron”, “ingresaron”, “recepción” implican RECIBIDO.
“Envié”, “salió”, “entregado”, “despachado” implican ENVIADO.

Regla según tipo de movimiento:
ENVIADO implica prohibición absoluta de solicitar fechas.
RECIBIDO implica obligación absoluta de solicitar fecha.

Frecuencia de solicitud de fecha:
La fecha se solicita una sola vez por equipo o por lote homogéneo del mismo origen o proveedor y del mismo evento.
Una vez obtenida, se aplica automáticamente a todo el lote.

No duplicidad:
Nunca solicites una fecha ya proporcionada; debes reutilizarla siempre.

Series N/A:
Si el usuario indica explícitamente que la serie es N/A, solo el campo Serie se registra como “N/A”.
Esto no elimina ni reemplaza la obligación de solicitar fecha en movimientos Recibidos.

Recepción sin guía:
La ausencia de guía no elimina la obligación de solicitar fecha de llegada en Recibidos.

Control de registro (bloqueo absoluto):
Está estrictamente prohibido guardar, confirmar, resumir o generar JSON si existe al menos un ítem Recibido sin fecha.

Series:
Equipos tienen serie obligatoria.
Periféricos tienen serie opcional y vacía.

Obsoletos y envíos especiales:
Core 2 Duo, Pentium y Celeron antiguos deben sugerirse como Obsoletos.
Excepción: si el movimiento es Enviado, el estado es Dañado y el usuario confirma explícitamente, el envío se mantiene.

Memoria y negaciones:
Expresiones como “sin cargador” o “sin cables” deben registrarse obligatoriamente en el reporte.

Especificaciones:
Toda Laptop o CPU sin especificaciones requiere solicitar RAM, procesador y disco.
Excepción absoluta: si aplica un comando supremo de anulación, se rellena con “N/A” sin preguntar.

Formulario y estados:
Si existen datos faltantes, el status debe ser QUESTION y missing_info debe listar todo lo faltante de forma consolidada.
Está prohibido inventar datos.

Automatización:
Debes rellenar automáticamente todo lo deducible y preguntar solo lo estrictamente imprescindible.

Continuidad lógica:
Las especificaciones sueltas deben asignarse al equipo lógico correcto.

Estandarización:
Debes corregir automáticamente ortografía, marcas, modelos y procesadores.

Anti-ping-pong radical:
Debes revisar todos los campos vacíos y solicitar toda la información faltante en una sola interacción.
Nunca preguntes dato por dato.

Captura de reportes:
Reconoce abreviaciones técnicas, códigos de informe y referencias de hardware.

Regla maestra de propagación:
Si un dato aplica a múltiples filas, debes propagarlo automáticamente a todas.

Regla maestra contextual:
“Me llegaron el 23 de marzo” se aplica únicamente a ítems Recibidos con fecha vacía.
“Todos son i5” propaga el procesador a todas las CPUs y Laptops sin procesador definido.

Guardián de la puerta, checklist final obligatorio:
Antes de generar cualquier salida final debes validar:
Ítems Recibidos sin fecha implican QUESTION.
Ítems Enviados o Recibidos sin guía implican QUESTION.
CPUs o Laptops sin especificaciones válidas implican QUESTION.
Si cualquiera falla, queda estrictamente prohibido marcar READY, incluso si acabas de recibir otro dato.

SALIDA JSON OBLIGATORIA:
{
 "status": "QUESTION" o "READY",
 "missing_info": "Resumen de faltantes",
 "items": [
 {
  "equipo": "Laptop", "marca": "Dell", "modelo": "", "serie": "",
  "cantidad": 1, "estado": "", "tipo": "Enviado",
  "origen": "Stock", "destino": "Portete",
  "guia": "", "fecha_llegada": "",
  "ram": "", "procesador": "", "disco": "", "reporte": ""
 }
 ]
}
"""

# ==========================================
# 6. INICIALIZACIÓN DE SESSION STATE
# ==========================================
for key, default in {
    "messages": [],
    "draft": None,
    "status": "NEW",
    "missing_info": "",
    "clear_chat": False,
    "chat_key": 0
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ==========================================
# 7. INTERFAZ - TABS
# ==========================================
t1, t2, t3 = st.tabs(["💬 Chat Auditor","📊 Dashboard Previo","🗑️ Limpieza"])

# ==========================================
# 8. PESTAÑA CHAT
# ==========================================
with t1:
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    with st.form(key="chat_form", clear_on_submit=True):
        prompt_usuario = st.text_area("📋 Habla con LAIA...", height=80)
        c_vacia, c_btn = st.columns([5,1])
        with c_btn: submitted = st.form_submit_button("📤 Enviar")
        if submitted and prompt_usuario:
            st.session_state.messages.append({"role":"user","content":prompt_usuario})
            try:
                with st.spinner("LAIA está auditando..."):
                    if st.session_state.draft:
                        inventario_json = json.dumps(st.session_state.draft, indent=2)
                        prompt_completo = f"INVENTARIO ACTUAL:\n{inventario_json}\nUSUARIO: {prompt_usuario}\nActualiza tabla y solo indica lo que falta."
                    else:
                        prompt_completo = f"USUARIO: {prompt_usuario}"

                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":prompt_completo}],
                        temperature=0
                    )

                    texto_limpio = extraer_json(response.choices[0].message.content)
                    if texto_limpio:
                        res_json = json.loads(texto_limpio)
                        st.session_state.draft = res_json.get("items",[])
                        st.session_state.status = res_json.get("status","READY")
                        st.session_state.missing_info = res_json.get("missing_info","")
                        st.session_state.messages.append({"role":"assistant","content":f"✅ {st.session_state.missing_info or 'Tabla actualizada.'}"})
                    else:
                        st.error("⚠️ La IA respondió incoherente.")

                st.rerun()
            except Exception as e:
                st.error(f"Error crítico: {e}")

    st.divider()
    if st.session_state.draft is not None:
        st.subheader("📊 Tabla de Inventario (En Vivo)")
        if st.session_state.status=="QUESTION":
            st.warning(f"⚠️ LAIA DETECTA FALTANTES: {st.session_state.missing_info}")
        df_draft = pd.DataFrame(st.session_state.draft)
        edited_df = st.data_editor(df_draft, num_rows="dynamic", use_container_width=True, key="editor_tabla")
        if not df_draft.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

    col1,col2 = st.columns([1,4])
    with col1:
        if st.button("🚀 ENVIAR AL BUZÓN", type="primary"):
            if not st.session_state.draft:
                st.error("❌ Tabla vacía.")
            else:
                enviar=True
                if st.session_state.status=="QUESTION":
                    all_na = all(item.get("serie")=="N/A" or item.get("ram")=="N/A" for item in st.session_state.draft)
                    if not all_na: st.error("⛔ Faltan datos obligatorios."); enviar=False
                    else: st.session_state.status="READY"; st.warning("⚠️ Se aplicaron valores N/A según usuario.")
                if enviar:
                    with st.spinner("Enviando datos..."):
                        datos = st.session_state.draft
                        fecha = (datetime.datetime.now(datetime.timezone.utc)-timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                        for d in datos:
                            d["fecha"]=fecha
                            for k in d: 
                                if d[k] is None: d[k] = ""
                        if enviar_github(FILE_BUZON, datos):
                            st.success("✅ ¡Enviado!")
                            st.session_state.draft=None
                            st.session_state.messages=[]
                            st.session_state.status="NEW"
                            st.rerun()
                        else:
                            st.error("Error GitHub")

    with col2:
        if st.button("🗑️ Borrar todo"):
            st.session_state.draft=None
            st.session_state.messages=[]
            st.rerun()

# ==========================================
# 9. PESTAÑA DASHBOARD
# ==========================================
with t2:
    hist,_ = obtener_github(FILE_HISTORICO)
    if hist:
        df_h = pd.DataFrame(hist)
        df_h.columns = df_h.columns.str.lower().str.strip()
        st_res, st_det = calcular_stock_web(df_h)
        k1,k2=st.columns(2)
        k1.metric("📦 Stock Total", int(st_res['val'].sum()) if not st_res.empty else 0)
        k2.metric("🚚 Movimientos", len(df_h))
        if not st_res.empty:
            st.dataframe(st_res.pivot_table(index=['equipo','marca'],columns='estado_fisico',values='val',aggfunc='sum').fillna(0))
        st.dataframe(st_det,use_container_width=True)
    else:
        st.info("Sincronizando con GitHub...")

# ==========================================
# 10. PESTAÑA LIMPIEZA
# ==========================================
with t3:
    st.subheader("🗑️ Limpieza Inteligente")
    txt_borrar = st.text_input("¿Qué deseas eliminar?")
    if st.button("🔥 EJECUTAR BORRADO"):
        if txt_borrar:
            try:
                p_db = (
                    "Actúa como DBA. COLUMNAS: [equipo, marca, serie, estado, destino]. "
                    f"ORDEN: {txt_borrar}. RESPONDE SOLO JSON: "
                    '{"accion":"borrar_todo"} o {"accion":"borrar_filtro","columna":"...","valor":"..."}'
                )
                resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":p_db}])
                texto = resp.choices[0].message.content
                order = json.loads(extraer_json(texto))
                if enviar_github(FILE_BUZON, order):
                    st.success("✅ Orden enviada.")
                    st.json(order)
            except Exception as e:
                st.error("Error: "+str(e))
