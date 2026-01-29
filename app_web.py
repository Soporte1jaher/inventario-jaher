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

def extraer_json(texto):
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
                if balance == 0:
                    return texto[inicio:i+1]
        return ""
    except:
        return ""

def obtener_github(archivo):
    url = f"https://api.github.com/repos/{}/{}/contents/{}"
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
    url = f"https://api.github.com/repos/{}/{}/contents/{}"
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

# ==========================================
# 3. MOTOR DE STOCK
# ==========================================
def calcular_stock_web(df):
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    df_c = df.copy()
    df_c.columns = df_c.columns.str.lower().str.strip()
    cols = ['estado', 'estado_fisico', 'tipo', 'destino', 'equipo', 'marca', 'cantidad', 'modelo']
    for col in cols:
        if col not in df_c.columns: df_c[col] = "No especificado"
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)

    def procesar_fila(row):
        t = str(row['tipo']).lower()
        cant = row['cant_n']
        if any(x in t for x in ['recib', 'ingreso', 'entrad', 'compra']): return cant
        if any(x in t for x in ['env', 'salida', 'baja', 'despacho']): return -cant
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)
    resumen = df_c.groupby(['equipo', 'marca', 'modelo', 'estado_fisico'])['val'].sum().reset_index()
    return resumen[resumen['val'] > 0], df_c[df_c['val'] != 0]

# ==========================================
# 4. SYSTEM PROMPT (Resumido para estabilidad)
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
# 5. INTERFAZ
# ==========================================
st.title("🧠 LAIA v91.0 - Auditoría Senior")

if "messages" not in st.session_state: st.session_state.messages = []
if "draft" not in st.session_state: st.session_state.draft = None
if "status" not in st.session_state: st.session_state.status = "NEW"

t1, t2, t3 = st.tabs(["💬 Chat Auditor", "📊 Dashboard Previo", "🗑️ Limpieza"])

with t1:
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    with st.form(key="chat_form", clear_on_submit=True):
        prompt_usuario = st.text_area("📋 Habla con LAIA...", height=80)
        submitted = st.form_submit_button("📤 Enviar")

    if submitted and prompt_usuario:
        st.session_state.messages.append({"role": "user", "content": prompt_usuario})
        try:
            with st.spinner("LAIA está auditando..."):
                inventario_previo = json.dumps(st.session_state.draft) if st.session_state.draft else "Ninguno"
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"INVENTARIO ACTUAL: {inventario_previo}\n\nUSUARIO: {}"}
                    ],
                    temperature=0
                )
                
                texto = extraer_json(response.choices[0].message.content)
                if texto:
                    res_json = json.loads(texto)
                    st.session_state.draft = res_json.get("items", [])
                    st.session_state.status = res_json.get("status", "READY")
                    st.session_state.messages.append({"role": "assistant", "content": f"✅ {res_json.get('missing_info', 'Actualizado')}"})
                    st.rerun()
        except Exception as e:
            st.error(f"Error: {}")

    if st.session_state.draft:
        st.subheader("📊 Tabla en Vivo")
        df_ed = pd.DataFrame(st.session_state.draft)
        nuevo_df = st.data_editor(df_ed, num_rows="dynamic", use_container_width=True)
        st.session_state.draft = nuevo_df.to_dict("records")

        if st.button("🚀 ENVIAR AL BUZÓN"):
            if st.session_state.status == "QUESTION":
                st.error("⛔ Faltan datos obligatorios según LAIA.")
            else:
                fecha_gen = (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                for item in st.session_state.draft: item["fecha_registro"] = fecha_gen
                if enviar_github(FILE_BUZON, st.session_state.draft):
                    st.success("✅ Enviado!")
                    st.session_state.draft = None
                    st.session_state.messages = []
                    st.rerun()

with t2:
    hist, _ = obtener_github(FILE_HISTORICO)
    if hist:
        df_h = pd.DataFrame(hist)
        res, det = calcular_stock_web(df_h)
        st.metric("📦 Stock Total", int(res['val'].sum()) if not res.empty else 0)
        st.dataframe(det, use_container_width=True)

with t3:
    st.subheader("🗑️ Limpieza")
    txt_borrar = st.text_input("¿Qué borrar?")
    if st.button("🔥 EJECUTAR"):
        # CORREGIDO: Usando el método correcto de la API
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"Genera un JSON de borrado para: {txt_borrar}"}]
        )
        st.write("Comando procesado.")
