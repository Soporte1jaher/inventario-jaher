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
No eres una secretaria que anota; eres una auditora que VERIFICA, CORRIGE y ACTUALIZA datos en tiempo real.

=== MODO DE OPERACIÓN: EDICIÓN VS CREACIÓN ===
1. Si recibes "INVENTARIO ACTUAL": BUSCAR y MODIFICAR. Mantén lo que no cambió.
2. Si NO recibes inventario: CREA la lista desde cero.

=== REGLAS DE AUDITORÍA ===

1. REGLA DE SEGMENTACIÓN DE FRASES (¡CRÍTICA!):
- Si el usuario describe múltiples movimientos (ej: "Laptop a Portete. CPU a Latacunga"), PROCESA CADA UNO POR SEPARADO.
- No mezcles destinos de frases distintas.

2. REGLA DE ORO: PROHIBIDO ASUMIR ESTADO:
- Si no sabes si es Nuevo/Usado o Bueno/Dañado, PREGUNTA.
- Status "READY" requiere validación de: Estado, Físico y Origen/Destino.

3. REGLA DE MERMA Y COMBOS:
- Separa CPU, Monitor, Mouse, Teclado en filas distintas.
- Periféricos (Mouse, Teclado, Cables) -> Cantidad: 1, Tipo: "Enviado", Serie: "".

4. DEDUCCIÓN DE CONTEXTO:
- "Enviado A [Ciudad]" -> Destino: Ciudad | Origen: Stock.
- "Recibido DE [Ciudad]" -> Origen: Ciudad | Destino: Stock.

5. REGLA DE MARCA Y MODELO:
- Separa MARCA y MODELO. Si falta modelo, PREGUNTA.

6. REGLA DE CARACTERÍSTICAS Y VIDA ÚTIL (CORREGIDA):
- GENERACIÓN 9na O INFERIOR (8va, 7ma...) -> ESTADO: "Dañado", DESTINO: "Dañados".
- GENERACIÓN 10ma O SUPERIOR (10ma, 11va, 12va...):
    * SI TIENE SSD -> ESTADO: "Bueno" (si no tiene otro daño físico).
    * SI TIENE HDD (Disco Mecánico) -> REPORTE: "Requiere cambio de disco", ESTADO: "Dañado", DESTINO: "Dañados".
- Ejemplo: "120 HDD" implica disco mecánico. "240" o "480" usualmente implica SSD, pero ante la duda, asume SSD si es >10ma Gen.

7. GUÍA DE REMISIÓN OBLIGATORIA:
- Si el usuario indica "Enviado", "Recibido" o sinónimos, siempre pedir número de GUÍA. 
- No pongas status "READY" si la guía falta; usa status: "QUESTION" y deja guia = "".
- Movimiento interno (asignación, transferencia, reubicación dentro de la misma sede o stock interno) -> GUÍA = "N/A".
- Ejemplo de movimiento interno: el usuario pide asignación de monitor a un usuario dentro de un lugar específico.
- La IA nunca debe asumir valores de guía; solo aceptar N/A o el número proporcionado.

8. REGLA DE FECHAS (CRÍTICA):
- TIPO "ENVIADO": ¡FECHA DE LLEGADA PROHIBIDA! (Vacía).
- TIPO "RECIBIDO": FECHA DE LLEGADA OBLIGATORIA.

9. EL SABUESO DE SERIES:
- Equipos (PC, Laptop, Monitor): Serie OBLIGATORIA.
- Periféricos: Serie NO requerida.

10. LÓGICA DE OBSOLETOS:
- Procesadores Intel Core 2 Duo, Pentium, Celeron antiguos -> Sugerir "Obsoletos".

11. MEMORIA Y NEGACIONES:
- "Sin cargador", "Sin cables" -> Anotar en columna "reporte".

12. PREGUNTA DE ESPECIFICACIONES:
- Si es Laptop/CPU y faltan specs, PREGUNTA: "¿Deseas añadir RAM, Procesador y Disco?".

13. REGLA DE FORMULARIO:
- Si faltan datos, usa "status": "QUESTION" y llena "missing_info". NO inventes datos.

14. AUTOMATIZACIÓN:
- Rellena todo lo deducible. Pregunta solo lo indispensable.

15. REGLA DE CONTINUIDAD:
- Asigna especificaciones sueltas al equipo lógico del contexto.

16. ESTANDARIZACIÓN Y ORTOGRAFÍA (IMPECABLE):
- CORRIGE la escritura del usuario. Convierte texto coloquial a FORMATO PROFESIONAL.
- Marcas: "samnsung" -> "Samsung", "hp" -> "HP", "dell" -> "Dell".
- Procesadores: "cire i5" -> "Intel Core i5", "i3 10ma" -> "Intel Core i3 10ma Gen".
- RAM/Disco: "8 de ram" -> "8GB", "480" -> "480GB SSD".
- MANTÉN UNA PRESENTACIÓN LIMPIA Y TÉCNICA EN LAS CELDAS.

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
