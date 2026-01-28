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
Eres LAIA, la Auditora Senior de Inventarios de Jaher. Tu inteligencia es superior, deductiva y meticulosa. No eres una secretaria que anota; eres una auditora que VERIFICA.

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

if "messages" not in st.session_state:
    st.session_state.messages = []
if "draft" not in st.session_state:
    st.session_state.draft = None

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

            # Hoja Enviados y Recibidos
            aplicar_formato_zebra(
                writer, df_mov[columnas_finales], 'Enviados y Recibidos'
            )

            # Hoja Stock
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

            # ✅ Hoja Dañados (AQUÍ VA)
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
with t1:
    if "draft" not in st.session_state:
        st.session_state.draft = None
    if "status" not in st.session_state:
        st.session_state.status = "NEW"
    if "missing_info" not in st.session_state:
        st.session_state.missing_info = ""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    # 1. Mostrar historial visual
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # 2. Input del usuario
    if prompt := st.text_area("📋 Describe tu envío o movimiento de equipos"):

        # Guardar mensaje
        if not st.session_state.messages or st.session_state.messages[-1]["content"] != prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})

        with st.expander("Ver mensaje original"):
            st.markdown(prompt)

        # ⚡ SOLO llamamos a la IA si no existe draft
        if "draft" not in st.session_state or st.session_state.draft is None:
            try:
                with st.spinner("Analizando inventario..."):
                    response = client.responses.create(
                        model="gpt-4.1-mini",
                        input=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": "\nUSUARIO ACTUAL: " + prompt}
                        ]
                    )
                texto = response.output_text
                json_txt = extraer_json(texto)
                res_json = json.loads(json_txt) if json_txt else {}

                st.session_state.draft = res_json.get("items", [])
                st.session_state.status = res_json.get("status", "READY")
                st.session_state.missing_info = res_json.get("missing_info", "")
            except Exception as e:
                st.error("Error procesando solicitud: " + str(e))

        # 2a. Lógica para completar información faltante
        if st.session_state.status == "QUESTION":
            st.warning(f"⚠️ Faltan datos: {st.session_state.missing_info}")

            with st.form("completar_info"):
                st.write("### 📝 Rellena solo los campos faltantes:")
                form_respuestas = {}
                campos_clave = ["marca", "modelo", "serie", "estado", "origen", "destino", "guia", "fecha_llegada"]

                for i, item in enumerate(st.session_state.draft):
                    st.markdown(f"**Item {i+1}: {item.get('equipo', 'Equipo')}**")
                    cols = st.columns(4)
                    col_idx = 0

                    for key in campos_clave:
                        valor_actual = item.get(key, "")
                        if valor_actual in ["", None, "N/A"]:
                            with cols[col_idx % 4]:
                                form_respuestas[f"{i}_{key}"] = st.text_input(
                                    label=key.capitalize(),
                                    value=valor_actual,  # recordamos lo que haya escrito antes
                                    key=f"input_{i}_{key}"
                                )
                            col_idx += 1
                    st.divider()

                submitted = st.form_submit_button("✅ Actualizar y Generar Tabla")

            if submitted:
                # Guardamos los datos ingresados en session_state
                for key_compuesta, valor_usuario in form_respuestas.items():
                    if valor_usuario:
                        idx_str, campo = key_compuesta.split("_", 1)
                        st.session_state.draft[int(idx_str)][campo] = valor_usuario

                st.success("✅ Datos completados.")
                st.session_state.status = "READY"  # marcamos como listo
                st.experimental_rerun()  # rerun después de guardar

        elif st.session_state.status == "READY":
            st.success("✅ Todos los datos completos.")

    # 3. Mostrar Tabla Final y Botón Enviar
    if st.session_state.draft:
        st.write("### 📋 Confirmación Final")

        df_draft = pd.DataFrame(st.session_state.draft)
        edited_df = st.data_editor(df_draft, num_rows="dynamic", use_container_width=True)

        col_btn1, col_btn2 = st.columns([1, 4])

        with col_btn1:
            if st.button("🚀 ENVIAR AL BUZÓN", type="primary"):
                with st.spinner("Enviando..."):
                    fecha_ecu = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                    datos_finales = edited_df.to_dict('records')

                    for item in datos_finales:
                        item["fecha"] = fecha_ecu

                    if enviar_github(FILE_BUZON, datos_finales):
                        st.success("✅ ¡Datos enviados correctamente!")
                        st.session_state.draft = None
                        st.session_state.messages = []
                        time.sleep(2)
                        st.experimental_rerun()
                    else:
                        st.error("Falló la conexión con GitHub")

        with col_btn2:
            if st.button("🗑️ Cancelar"):
                st.session_state.draft = None
                st.experimental_rerun()


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
