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
    df_c.columns = df_c.columns.str.lower().str.strip()

    # Asegura columnas básicas
    cols = ['estado', 'estado_fisico', 'tipo', 'destino', 'equipo', 'marca', 'cantidad', 'modelo']
    for col in cols:
        if col not in df_c.columns:
            df_c[col] = "No especificado"

    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)

    # Lógica de stock
    def procesar_fila(row):
        est = str(row['estado']).lower()
        t = str(row['tipo']).lower()
        d = str(row['destino']).lower()
        eq = str(row['equipo']).lower()
        cant = row['cant_n']

        # Periféricos siempre restan/añaden stock
        perifericos = ['mouse', 'teclado', 'cable', 'hdmi', 'ponchadora', 'cargador']
        if any(p in eq for p in perifericos):
            if 'recibido' in t:
                return cant
            if 'enviado' in t:
                return -cant

        # Equipos dañados u obsoletos no afectan stock general
        if 'dañ' in est or 'obs' in est:
            return 0

        # Stock normal
        if d == 'stock' or 'recibido' in t:
            return cant
        if 'enviado' in t:
            return -cant
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)

    # Resumen stock normal
    resumen = df_c.groupby(['equipo', 'marca', 'modelo', 'estado_fisico'])['val'].sum().reset_index()

    # Filas con movimientos
    movimientos = df_c[df_c['val'] != 0]

    return resumen[resumen['val'] > 0], movimientos

# ==========================================
# 4. CEREBRO SUPREMO LAIA V91.0
# ==========================================
SYSTEM_PROMPT = """
Eres LAIA, la Auditora Senior de Inventarios de Jaher. Tu inteligencia es superior, deductiva y meticulosa.
No eres una secretaria que anota; eres una auditora que VERIFICA y ACTUALIZA datos en tiempo real.

=== MODO DE OPERACIÓN: EDICIÓN VS CREACIÓN ===
1. Si recibes un JSON llamado "INVENTARIO ACTUAL":
   - NO crees una lista nueva desde cero.
   - Tu trabajo es BUSCAR en esa lista el equipo al que se refiere el usuario y MODIFICAR sus datos (RAM, procesador, serie, corrección de cantidad).
   - Mantén intactos los items que el usuario no mencionó.
   - Devuelve la lista COMPLETA actualizada.

2. Si NO recibes inventario previo:
   - Crea la lista desde cero extrayendo los datos del mensaje.

=== REGLAS DE AUDITORÍA ===

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
- SI EL EQUIPO SE "ENVIA" O SINONIMOS DE ENVIAR, NO DEBES PEDIR FECHA DE LLEGADA. 
- Si el movimiento es "Recibido" (implica transporte), LA FECHA DE LLEGADA DE LOS EQUIPOS NO ES OBLIGATORIA PERO ES NECESARIA.
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

14. REGLA DE FORMULARIO DE RELLENO (CRÍTICA):
- Tu objetivo NO es chatear, es generar filas de Excel.
- Si faltan datos (como Series, Guías, Marcas), NO redactes una pregunta en texto.
- En su lugar, devuelve el objeto en "items" con los datos que SÍ tienes, y deja los campos faltantes como cadena vacía "" o null.
- Usa "status": "QUESTION" solo para indicar al sistema que despliegue el formulario de relleno.

15. AUTOMATIZACIÓN Y FORMULARIO MÍNIMO:
- Rellena todo lo que puedas deducir del mensaje del usuario.
- Solo deja vacíos los campos obligatorios que no se puedan inferir.
- Usa "status":"QUESTION" solo si faltan datos críticos.
- El formulario debe mostrar únicamente los campos vacíos críticos, no todos los campos.
- Respeta las respuestas "N/A", "no", "sin X", y no vuelvas a preguntar.

16. REGLA DE CONTINUIDAD (INTEGRACIÓN):
- Si el usuario te da especificaciones técnicas sueltas (ej: "es core i5"), asígnalas al equipo correspondiente del inventario actual.
- Si hay ambigüedad (ej: 2 laptops y dice "la laptop es i5"), asigna a la que tenga más sentido o pregunta, pero intenta deducirlo.

SALIDA JSON OBLIGATORIA:
{
 "status": "QUESTION",
 "missing_info": "Faltan series y guías",
 "items": [
 {
  "equipo": "Laptop",
  "marca": "Dell",
  "modelo": "",
  "serie": "",
  "cantidad": 2,
  "estado": "",
  "tipo": "Enviado",
  "origen": "Portete",
  "destino": "Latacunga",
  "guia": "",
  "fecha_llegada": "",
  "ram": "",
  "procesador": "",
  "disco": "",
  "reporte": ""
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
    # 1. MOSTRAR HISTORIAL (Arriba)
    # ------------------------------------------------
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # ------------------------------------------------
    # 2. ÁREA DE TEXTO Y BOTÓN (Dentro de un Formulario Seguro)
    # ------------------------------------------------
    # clear_on_submit=True hace el trabajo sucio de borrar el texto por ti
    with st.form(key="chat_form", clear_on_submit=True):
        
        # El input de texto
        prompt_usuario = st.text_area("📋 Habla con LAIA...", height=80)
        
        # Columnas para alinear el botón a la derecha
        c_vacia, c_btn = st.columns([5, 1])
        with c_btn:
            st.write("") # Espaciado vertical para alinear
            st.write("") 
            # El botón de envío (dentro del form)
            submitted = st.form_submit_button("📤 Enviar")

    # ------------------------------------------------
    # 3. LÓGICA DE PROCESAMIENTO (Solo si se presionó el botón)
    # ------------------------------------------------
    if submitted and prompt_usuario:
        
        # Guardamos mensaje usuario
        st.session_state.messages.append({"role": "user", "content": prompt_usuario})

        try:
            with st.spinner("LAIA está pensando..."):
                
                # Preparamos contexto
                if st.session_state.draft:
                    inventario_json = json.dumps(st.session_state.draft, indent=2)
                    prompt_completo = (
                        f"INVENTARIO ACTUAL:\n{inventario_json}\n\n"
                        f"USUARIO DICE: {prompt_usuario}\n\n"
                        "Actualiza la tabla según las reglas."
                    )
                else:
                    prompt_completo = f"USUARIO: {prompt_usuario}"

                # Llamada a OpenAI
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt_completo}
                    ],
                    temperature=0
                )

                # Procesar respuesta
                texto = response.choices[0].message.content
                json_txt = extraer_json(texto)
                
                if json_txt:
                    res_json = json.loads(json_txt)
                    
                    st.session_state.draft = res_json.get("items", [])
                    st.session_state.status = res_json.get("status", "READY")
                    st.session_state.missing_info = res_json.get("missing_info", "")
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": f"✅ {res_json.get('missing_info', 'Tabla actualizada.')}"
                    })
            
            # Recarga obligatoria para mostrar cambios
            st.rerun()
            
        except Exception as e:
            st.error(f"Error: {e}")

    # Separador visual
    st.divider()

    # ------------------------------------------------
    # 4. TABLA EN VIVO (Debajo del chat)
    # ------------------------------------------------
    if st.session_state.draft:
        st.subheader("📊 Tabla de Inventario (En Vivo)")
        
        # Alerta de datos faltantes
        if st.session_state.status == "QUESTION":
            st.warning(f"⚠️ FALTAN DATOS: {st.session_state.missing_info}")

        # Editor de tabla
        df_draft = pd.DataFrame(st.session_state.draft)
        edited_df = st.data_editor(
            df_draft,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_tabla"
        )

        # Si el usuario edita manualmente, guardamos cambios
        if not df_draft.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

        # Botones finales
        st.write("")
        col1, col2 = st.columns([1, 4])
        
        with col1:
            if st.button("🚀 ENVIAR AL BUZÓN", type="primary"):
                if st.session_state.status == "QUESTION":
                    st.error("⚠️ Faltan datos obligatorios.")
                else:
                    datos = st.session_state.draft
                    fecha = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                    for d in datos: d["fecha"] = fecha
                    
                    if enviar_github(FILE_BUZON, datos):
                        st.success("✅ ¡Enviado!")
                        time.sleep(1)
                        # Reset total
                        st.session_state.draft = None
                        st.session_state.messages = []
                        st.session_state.status = "NEW"
                        st.rerun()
                    else:
                        st.error("Error GitHub")

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
