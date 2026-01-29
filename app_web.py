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
# 2. CREDENCIAL
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
        # Limpieza básica de Markdown
        texto = texto.replace("```json", "").replace("```", "").strip()
        
        # Buscamos dónde empieza el primer objeto
        inicio = texto.find("{")
        if inicio == -1: return ""
        
        # Algoritmo de "Balance de Llaves" 
        # (Cuenta cuántas abren y cierran para encontrar el final exacto)
        balance = 0
        for i in range(inicio, len(texto)):
            char = texto[i]
            if char == '{':
                balance += 1
            elif char == '}':
                balance -= 1
                # Cuando el balance llega a cero, hemos encontrado el cierre exacto
                if balance == 0:
                    json_limpio = texto[inicio:i+1]
                    return json_limpio
        
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
    if isinstance(datos, list):
        actuales.extend(datos)
    else:
        actuales.append(datos)

    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode()).decode(),
        "sha": sha
    }
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

# ==========================================
# 3. MOTOR DE STOCK
# ==========================================
def calcular_stock_web(df):
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df_c = df.copy()
    # Normalizamos columnas a minúsculas
    df_c.columns = df_c.columns.str.lower().str.strip()

    # Asegura columnas básicas
    cols = ['estado', 'estado_fisico', 'tipo', 'destino', 'equipo', 'marca', 'cantidad', 'modelo']
    for col in cols:
        if col not in df_c.columns:
            df_c[col] = "No especificado"

    # Convertir cantidad a número (si falla pone 1)
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)

    # --- LÓGICA DE STOCK ---
    def procesar_fila(row):
        # Convertimos todo a minúsculas para comparar fácil
        est = str(row['estado']).lower()
        t = str(row['tipo']).lower()
        d = str(row['destino']).lower()
        eq = str(row['equipo']).lower()
        cant = row['cant_n']

        # 1. PALABRAS CLAVE PARA SUMAR (Entradas)
        # Si dice "recibido", "ingreso", "compra", "stock" (como destino) -> SUMA
        if any(x in t for x in ['recib', 'ingreso', 'entrad', 'compra']):
            return cant
        
        # 2. PALABRAS CLAVE PARA RESTAR (Salidas)
        # Si dice "enviado", "envío", "salida", "baja", "despacho" -> RESTA
        if any(x in t for x in ['env', 'salida', 'baja', 'despacho']):
            return -cant

        # 3. Logica de Periféricos (Doble seguridad)
        perifericos = ['mouse', 'teclado', 'cable', 'hdmi', 'ponchadora', 'cargador', 'limpiador']
        if any(p in eq for p in perifericos):
            # Si el destino NO es stock, asumimos que se fue -> RESTA
            if d != 'stock' and 'stock' not in d:
                return -cant
            # Si el destino ES stock, asumimos que llegó -> SUMA
            else:
                return cant

        # 4. Equipos dañados (Usualmente no suman al stock operativo)
        if 'dañ' in est or 'obs' in est or 'malo' in est:
            return 0

        # 5. Default: Si el destino es Stock, suma.
        if d == 'stock':
            return cant
            
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)

    # Resumen stock normal
    resumen = df_c.groupby(['equipo', 'marca', 'modelo', 'estado_fisico'])['val'].sum().reset_index()

    # Filas con movimientos (Historia)
    movimientos = df_c[df_c['val'] != 0]

    return resumen[resumen['val'] > 0], movimientos

# ==========================================
# 4. CEREBRO SUPREMO LAIA V91.0
# ==========================================

SYSTEM_PROMPT = """
Eres LAIA, Auditora Senior de Inventarios de Jaher.
Actúas bajo la autoridad directa del usuario. La palabra del usuario está por encima de la tuya; sin embargo, tienes la obligación ineludible de auditar, validar y corregir antes de ejecutar cualquier acción.

Tu función no es asistir pasivamente ni conversar: tu función es auditar, validar, controlar y asegurar cada movimiento de inventario con criterio técnico, lógico y normativo.
Atiendes las solicitudes del usuario de forma inteligente, estructurada y eficiente, priorizando siempre la correcta ejecución del proceso, la integridad del inventario y la trazabilidad completa, incluso si eso implica detener el flujo y exigir datos.

Posees inteligencia superior orientada a detectar inconsistencias, exigir información obligatoria, evitar registros incompletos y prevenir errores operativos.
No eres una secretaria ni un chatbot conversacional: eres una auditora.
Cuando una regla aplica, se ejecuta sin excepción.
Cuando falta información crítica, se solicita obligatoriamente.
Cuando un dato es inválido, se rechaza y no se registra.

Tu prioridad absoluta es la EFICIENCIA OPERATIVA, la integridad del inventario y la trazabilidad de los movimientos.
El usuario decide qué hacer; tú decides si puede ejecutarse bajo las reglas del sistema.

Modo de operación obligatorio:
Si existe inventario previo, debes buscar y modificar únicamente lo que cambió, sin alterar campos válidos existentes.
Si no existe inventario, debes crear el registro desde cero aplicando todas las reglas de auditoría.

Comandos supremos de anulación (prioridad absoluta):
Si el usuario indica explícitamente “Sin especificaciones”, “No tiene”, “N/A”, “Sin datos”, “Así no más” o variantes con errores tipográficos, tu acción obligatoria es rellenar RAM, Procesador, Disco, Modelo y Serie faltantes con “N/A”, cambiar el status a READY únicamente si se cumplen guía y fecha cuando aplique, y prohibirte volver a preguntar por esos datos.

Reglas de auditoría extrema:
Cada movimiento debe procesarse en frases independientes; no mezcles orígenes, destinos ni eventos distintos en una misma interpretación.
Está prohibido asumir estado, origen, destino, guía o fecha; si falta información, pregunta una sola vez todo lo necesario y no repitas preguntas ya realizadas.
El status READY solo se permite con validación completa.

CPU, monitor, mouse y teclado siempre se registran en filas separadas.
Periféricos siempre tienen cantidad 1, tipo “Enviado” cuando corresponda y serie vacía.

Deducción automática obligatoria:
“Enviado a [Ciudad]” implica origen Stock y destino la ciudad indicada.
“Recibido de [Ciudad]” implica origen la ciudad indicada y destino Stock.

Marca y modelo:
Laptops, CPUs y monitores siempre se separan y modelo es obligatorio; si falta, se pregunta.
Periféricos no requieren marca ni modelo; si faltan, usa “Genérico” o “N/A” sin preguntar.

Vida útil y estado:
Generación menor o igual a 9 → Dañado, destino Dañados.
Generación mayor o igual a 10: SSD → Bueno; HDD → Dañado con reporte “Requiere cambio de disco”.
Si la generación es mayor a 10, deduce el tipo de disco por capacidad.

Guía obligatoria:
Todo Enviado o Recibido requiere guía.
Si el usuario insiste en no colocar guía, usar “N/A”.
Movimientos internos siempre llevan guía “N/A”.

Fechas, lógica fila por fila con máximo rigor:
Tipo ENVIADO → fecha de llegada siempre vacía y prohibido solicitarla.
Tipo RECIBIDO → fecha de llegada obligatoria; si falta, debes solicitarla antes de continuar.
Estado Dañado no lleva fecha salvo que sea un Recibido.
Una vez solicitada la fecha para un equipo o lote, no vuelvas a pedirla.

Diferencia entre fechas:
Al detectar un movimiento RECIBIDO, solicita todas las fechas necesarias de una sola vez, exclusivamente como fecha de llegada o recepción.

Detección automática del tipo:
“Recibí”, “llegaron”, “me llegaron”, “ingresaron”, “recepción” → RECIBIDO.
“Envié”, “salió”, “entregado”, “despachado” → ENVIADO.

Regla según tipo:
ENVIADO → prohibido pedir fechas.
RECIBIDO → obligatorio pedir fecha.

Frecuencia de solicitud de fecha:
La fecha se pide una sola vez por equipo o por lote homogéneo del mismo origen o proveedor y del mismo evento.
Una vez obtenida, se aplica a todo el lote.

No duplicidad:
Nunca vuelvas a pedir una fecha ya proporcionada; reutilízala siempre.

Series N/A:
Si el usuario indica que la serie es N/A, solo el campo Serie se llena con “N/A”.
Esto no elimina ni reemplaza la obligación de solicitar fecha en Recibidos.

Recepción sin guía:
La falta de guía no elimina la obligación de solicitar fecha en Recibidos.

Control de registro:
Está estrictamente prohibido guardar, confirmar o generar JSON si existe algún Recibido sin fecha.

Series:
Equipos → serie obligatoria.
Periféricos → serie opcional y vacía.

Obsoletos y envíos especiales:
Core 2 Duo, Pentium y Celeron antiguos → sugerir Obsoletos.
Excepción: si es Enviado, estado Dañado y el usuario confirma, mantener el envío.

Memoria y negaciones:
“Sin cargador”, “sin cables” deben registrarse en el reporte.

Especificaciones:
Laptop o CPU sin specs → preguntar RAM, procesador y disco.
Excepción absoluta: si aplica comando supremo, rellenar con N/A.

Formulario:
Si hay faltantes, status = QUESTION y missing_info debe listar todo lo faltante.
Prohibido inventar datos.

Automatización:
Rellena todo lo deducible automáticamente; pregunta solo lo imprescindible.

Continuidad:
Asigna especificaciones sueltas al equipo lógico correcto.

Estandarización:
Corrige ortografía, marcas y procesadores automáticamente.

Anti-ping-pong radical:
Revisa todos los campos vacíos y solicita todo de una sola vez.
Nunca preguntes dato por dato.

Captura de reportes:
Reconoce abreviaciones técnicas y códigos de informe.

Regla maestra de propagación:
Si un dato aplica a múltiples filas, propágalo automáticamente.

Regla maestra contextual:
“Me llegaron el 23 de marzo” → aplica solo a Recibidos sin fecha.
“Todos son i5” → propaga procesador a todas las CPUs/Laptops vacías.

Guardián de la puerta, checklist final obligatorio:
Antes de generar JSON verifica:
Recibidos sin fecha → QUESTION.
Enviados o Recibidos sin guía → QUESTION.
CPUs/Laptops sin specs válidas → QUESTION.
Si cualquiera falla, prohibido marcar READY, incluso si acabas de recibir otro dato.

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

# -----------------------------
# Inicialización session_state
# -----------------------------
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

t1, t2, t3 = st.tabs(["💬 Chat Auditor", "📊 Dashboard Previo", "🗑️ Limpieza"])

# ==========================================
# 6. GUARDAR EXCEL CON HOJA "DAÑADOS"
# ==========================================
def aplicar_formato_zebra(writer, df, nombre_hoja):
    if df.empty: return
    df.to_excel(writer, index=False, sheet_name=nombre_hoja)
    workbook, worksheet = writer.book, writer.sheets[nombre_hoja]
    header_fmt = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': '#1F4E78', 'font_color': 'white', 'border': 1})
    zebra_fmt = workbook.add_format({'bg_color': '#F2F2F2', 'border': 1})
    normal_fmt = workbook.add_format({'bg_color': '#FFFFFF', 'border': 1})
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_fmt)
    for row_num in range(1, len(df)+1):
        fmt = zebra_fmt if row_num % 2 == 0 else normal_fmt
        for col_num in range(len(df.columns)):
            val = df.iloc[row_num-1, col_num]
            worksheet.write(row_num, col_num, str(val) if pd.notna(val) else "", fmt)
    worksheet.freeze_panes(1,0)
    worksheet.set_column(0, len(df.columns)-1, 22)

def guardar_excel_premium(df, ruta):
    while True:
        try:
            writer = pd.ExcelWriter(ruta, engine='xlsxwriter')
            df_mov = df.copy().fillna("")

            columnas = list(df_mov.columns)
            orden = ['fecha','equipo','marca','modelo','serie','origen','destino',
                     'estado','estado_fisico','tipo','cantidad','reporte']
            columnas_finales = [c for c in orden if c in columnas] + \
                               [c for c in columnas if c not in orden]

            aplicar_formato_zebra(writer, df_mov[columnas_finales], 'Enviados y Recibidos')

            df_calc = df.copy()
            df_calc['cant_n'] = pd.to_numeric(df_calc['cantidad'], errors='coerce').fillna(1)
            df_calc['variacion'] = df_calc.apply(
                lambda row:
                    row['cant_n'] if 'recibido' in str(row.get('tipo','')).lower()
                    else (-row['cant_n'] if 'enviado' in str(row.get('tipo','')).lower() else 0),
                axis=1
            )
            res = df_calc.groupby(['equipo','marca','modelo','estado'])['variacion'].sum().reset_index()
            aplicar_formato_zebra(writer, res[res['variacion'] > 0], 'Stock (Saldos)')

            df_danados = df_mov[df_mov['estado'].str.lower() == 'dañado']
            if not df_danados.empty:
                aplicar_formato_zebra(writer, df_danados, 'Dañados')

            writer.close()
            return True

        except PermissionError:
            print("⚠️ POR FAVOR, CIERRA EL EXCEL PARA CONTINUAR...")
            time.sleep(5)
        except Exception as e:
            print("❌ Error crítico: " + str(e))
            return False

# ==========================================
# Pestaña Chat
# ==========================================
with t1:
    # ------------------------------------------------
    # 1. HISTORIAL DE CHAT
    # ------------------------------------------------
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # ------------------------------------------------
    # 2. FORMULARIO DE ENTRADA (Mantiene el chat limpio)
    # ------------------------------------------------
    with st.form(key="chat_form", clear_on_submit=True):
        prompt_usuario = st.text_area("📋 Habla con LAIA...", height=80)
        c_vacia, c_btn = st.columns([5, 1])
        with c_btn:
            st.write("") 
            st.write("") 
            submitted = st.form_submit_button("📤 Enviar")

    # ------------------------------------------------
    # 3. CEREBRO (LÓGICA DE PROCESAMIENTO)
    # ------------------------------------------------
    if submitted and prompt_usuario:
        st.session_state.messages.append({"role": "user", "content": prompt_usuario})

        try:
            with st.spinner("LAIA está auditando..."):
                
                # Contexto
                if st.session_state.draft:
                    inventario_json = json.dumps(st.session_state.draft, indent=2)
                    prompt_completo = (
                        f"INVENTARIO ACTUAL:\n{inventario_json}\n\n"
                        f"USUARIO DICE: {prompt_usuario}\n\n"
                        "Actualiza la tabla. NO BORRES NADA a menos que te lo pidan explícitamente."
                    )
                else:
                    prompt_completo = f"USUARIO: {prompt_usuario}"

                # Llamada AI
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt_completo}
                    ],
                    temperature=0
                )

                # Procesar respuesta
                texto_limpio = extraer_json(response.choices[0].message.content)
                
                if texto_limpio:
                    res_json = json.loads(texto_limpio)
                    nuevos_items = res_json.get("items", [])
                    
                    # --- SALVAVIDAS ANTI-BORRADO ---
                    # Si la IA devuelve 0 items pero antes teníamos datos y el usuario NO pidió borrar:
                    if not nuevos_items and st.session_state.draft and "borra" not in prompt_usuario.lower():
                         st.warning("⚠️ LAIA intentó borrar la tabla por error. Se han restaurado los datos anteriores.")
                         # No actualizamos el draft, mantenemos el anterior
                    else:
                         st.session_state.draft = nuevos_items
                         st.session_state.status = res_json.get("status", "READY")
                         st.session_state.missing_info = res_json.get("missing_info", "")
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": f"✅ {res_json.get('missing_info', 'Tabla actualizada.')}"
                    })
                else:
                    st.error("⚠️ La IA respondió algo incoherente. Intenta de nuevo.")

            st.rerun()
            
        except Exception as e:
            st.error(f"Error crítico: {e}")

    st.divider()

    # ------------------------------------------------
    # 4. TABLA EN VIVO (VISIBILIDAD FORZADA)
    # ------------------------------------------------
    # Cambiamos la condición: Mostramos la tabla si NO ES "None" (incluso si está vacía [])
if st.session_state.draft is not None:
        st.subheader("📊 Tabla de Inventario (En Vivo)")
        
        # Muestra la advertencia pero NO bloquea
        if st.session_state.status == "QUESTION":
            st.warning(f"⚠️ LAIA DETECTA FALTANTES: {st.session_state.missing_info}")
            st.info("💡 CONSEJO: Puedes editar las celdas manualmente antes de enviar.")

        # Editor
        df_draft = pd.DataFrame(st.session_state.draft)
        edited_df = st.data_editor(
            df_draft,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_tabla"
        )

        if not df_draft.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

        # Botones
        st.write("")
        col1, col2 = st.columns([1, 4])
        
        with col1:
            # --- CAMBIO AQUÍ: BOTÓN SIN RESTRICCIONES ---
            if st.button("🚀 ENVIAR AL BUZÓN", type="primary"):
                
                # Solo verificamos que la tabla no esté vacía (0 filas)
                if not st.session_state.draft:
                    st.error("❌ La tabla está vacía, no hay nada que enviar.")
                else:
                    # Si hay advertencias, enviamos igual pero avisamos
                    if st.session_state.status == "QUESTION":
                        st.toast("⚠️ Enviando con campos pendientes...", icon="⚠️")
                    
                    with st.spinner("Enviando datos..."):
                        datos = st.session_state.draft
                        fecha = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                        
                        # Ponemos la fecha a todos
                        for d in datos: 
                            d["fecha"] = fecha
                            # Opcional: Rellenar vacíos con "N/A" automáticamente al enviar
                            for key in d:
                                if d[key] == "" or d[key] is None:
                                    d[key] = ""
                        
                        if enviar_github(FILE_BUZON, datos):
                            st.success("✅ ¡Enviado exitosamente!")
                            time.sleep(1)
                            st.session_state.draft = None
                            st.session_state.messages = []
                            st.session_state.status = "NEW"
                            st.rerun()
                        else:
                            st.error("Error al conectar con GitHub")

        with col2:
            if st.button("🗑️ Borrar todo"):
                st.session_state.draft = None
                st.session_state.messages = []
                st.rerun()
# ==========================================
# Pestaña Dashboard
# ==========================================
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

# ==========================================
# Pestaña Limpieza
# ==========================================
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
