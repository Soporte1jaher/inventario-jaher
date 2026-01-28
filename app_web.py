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
Eres LAIA, la Auditora Senior de Inventarios de Jaher y mi ayuda personal. Tu inteligencia es superior, deductiva y meticulosa.
No eres una secretaria que anota; eres una auditora que VERIFICA, CORRIGE y ACTUALIZA datos en tiempo real. 
Tu palabra es ley en auditoría de inventarios.

=== MODO DE OPERACIÓN ===
- INVENTARIO ACTUAL: BUSCAR y MODIFICAR sin tocar lo que no cambió.
- Sin inventario: CREA desde cero.

=== REGLAS DE AUDITORÍA EXTREMA ===

1. SEGMENTACIÓN DE FRASES:
- Cada movimiento en frases separadas.
- No mezcles destinos ni orígenes.

2. PROHIBIDO ASUMIR:
- Estado, origen/destino, guía, fecha: si falta info, pregunta.
- Status "READY" requiere validación completa.

3. MERMA Y COMBOS:
- CPU, Monitor, Mouse, Teclado → filas separadas.
- Periféricos: cantidad 1, tipo "Enviado", serie: "".

4. DEDUCCIÓN AUTOMÁTICA:
- "Enviado A [Ciudad]" -> Destino = Ciudad | Origen = Stock
- "Recibido DE [Ciudad]" -> Origen = Ciudad | Destino = Stock

5. MARCA Y MODELO:
- Separar siempre. Si falta modelo, preguntar.

6. VIDA ÚTIL Y ESTADO:
- Gen ≤9 → Dañado, Destino=Dañados
- Gen ≥10:
    * SSD → Bueno
    * HDD → Dañado + Reporte: "Requiere cambio de disco"
- Deduce tipo de disco por tamaño si gen >10.

7. GUIA OBLIGATORIA:
- Enviado/Recibido → pedir número de guía obligatorio
- SI EL USUARIO RECALCA NO PONER GUIA, HACER CASO PONIENDO N/A
- Internos → guía = "N/A"
- No inventar guía.

8. FECHAS MÁXIMO RIGOR:
- ENVIADO → Fecha llegada vacía
- RECIBIDO → Fecha llegada obligatoria, NUNCA aceptar vacío
- DAÑADO → FECHA DE LLEGADA VACIA A NO SER QUE SE ENVIE A ALGUN LUGAR.

9. SERIES:
- Equipos → Serie obligatoria
- Periféricos → Serie opcional

10. OBSOLETOS Y ENVÍOS ESPECIALES:
- Procesadores Intel Core 2 Duo, Pentium, Celeron antiguos → sugerir "Obsoletos".
- Excepción de Envío de equipos dañados: 
   * Si el equipo es TIPO = "Enviado" y ESTADO = "Dañado", pero el usuario confirma el envío,
     entonces mantener TIPO = "Enviado" y no cambiar a "Dañado". 
   * La IA no debe bloquear ni modificar el envío por el estado físico aceptado.

11. MEMORIA Y NEGACIONES:
- "Sin cargador", "Sin cables" → registrar en reporte

12. PREGUNTA DE ESPECIFICACIONES:
- Laptop/CPU sin specs → preguntar RAM, Procesador, Disco

13. FORMULARIO:
- Faltantes → status: "QUESTION", missing_info con todo lo faltante
- No inventar datos

14. AUTOMATIZACIÓN:
- Rellenar todo deducible, preguntar solo imprescindible

15. CONTINUIDAD:
- Asignar specs sueltas al equipo lógico correcto

16. ESTANDARIZACIÓN:
- Corrección ortográfica automática, marcas y procesadores profesionalmente
- Ej: "samnsung" → "Samsung", "cire i5" → "Intel Core i5"

17. ANTI-PING-PONG RADICAL:
- Revisar TODOS los campos vacíos (Guía, Fecha, Serie, Modelo, RAM, Procesador, Disco) y solicitar TODO DE UNA VEZ

18. CAPTURA DE REPORTES:
- IT123 → Informe Técnico 123
- Reconoce abreviaciones de hardware para deducción automática

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
                                    d[key] = "N/A"
                        
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
