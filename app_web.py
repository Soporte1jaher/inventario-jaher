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
FILE_LECCIONES = "lecciones.json"
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
    timestamp = int(time.time())
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}?t={timestamp}"    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        
        if resp.status_code == 200:
            d = resp.json()
            contenido_decodificado = base64.b64decode(d['content']).decode('utf-8')
            
            try:
                # Intentamos leer el JSON
                return json.loads(contenido_decodificado), d['sha']
            except json.JSONDecodeError:
                # 🛑 AQUÍ ESTÁ EL CAMBIO: Si falla, devolvemos None, None.
                # Esto activa la alarma en la función de enviar.
                st.error(f"⛔ ¡PELIGRO CRÍTICO! El archivo {archivo} está CORRUPTO en GitHub. Se ha bloqueado el sistema para evitar borrar datos.")
                return None, None
                
        elif resp.status_code == 404:
            # Si no existe, devolvemos lista vacía (esto sí es seguro)
            return [], None
        else:
            st.error(f"❌ Error GitHub {resp.status_code}: {resp.text}")
            return None, None
            
    except Exception as e:
        st.error(f"❌ Error de conexión: {str(e)}")
        return None, None

def enviar_github(archivo, datos, mensaje="LAIA Update"):
    # 1. Intentamos obtener lo que ya hay
    actuales, sha = obtener_github(archivo)
    
    # --- CANDADO DE SEGURIDAD TOTAL ---
    # Si 'actuales' es None, es porque el archivo está corrupto o no se pudo leer.
    # PROHIBIMOS GUARDAR para no sobrescribir el desastre.
    if actuales is None:
        st.error(f"🛡️ SEGURIDAD ACTIVADA: No se puede guardar en {archivo} porque el archivo original está dañado. Repáralo en GitHub primero.")
        return False

    # 2. Mezclamos los datos
    if isinstance(datos, list):
        actuales.extend(datos)
    else:
        actuales.append(datos)

    # 3. Subimos a GitHub
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode()).decode()
    }
    
    if sha:
        payload["sha"] = sha
        
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    
    resp = requests.put(url, headers=HEADERS, json=payload)
    
    if resp.status_code in [200, 201]:
        return True
    else:
        st.error(f"❌ Error al subir: {resp.text}")
        return False

def aprender_leccion(error, correccion):
    lecciones, sha = obtener_github(FILE_LECCIONES)
    
    # Si lecciones es None (error de lectura), no intentamos guardar para no romper nada.
    if lecciones is None and sha is None:
         # Excepción: Si es la primera vez (404), obtener_github devuelve [], None. 
         # Si devuelve None, None es error crítico.
         return False

    if lecciones is None: lecciones = [] # Si era 404, iniciamos lista

    nueva = {
        "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "lo_que_hizo_mal": error,
        "como_debe_hacerlo": correccion
    }
    lecciones.append(nueva)
    
    if enviar_github(FILE_LECCIONES, lecciones[-15:], "LAIA: Nueva lección aprendida"):
        return True
    return False
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
## ROLE: LAIA v2.0 – Auditora de Inventario Multitarea
SYSTEM_PROMPT = """
Eres una IA auditora especializada en inventarios.
Operas mediante **Segregación de Entidades** y **Validación por Fases**.
Tu salida debe ser **EXCLUSIVAMENTE un JSON válido**.
Está estrictamente prohibido emitir texto fuera del JSON.

Tu comportamiento es crítico, analítico y secuencial.
No improvisas ni asumes datos no proporcionados por el usuario.

---

### 0. FASES OBLIGATORIAS (NO OMITIR NI SALTAR)

FASE 1: Generación de un JSON preliminar (uso interno, no visible).
FASE 2: Auditoría completa del JSON preliminar.
FASE 3:
- Si existe al menos un campo faltante → RESPONDER SOLO con `missing_info`.
- Si `missing_info` está vacío → generar JSON final y declarar `"status": "TABLA LISTA"`.

⚠️ No puedes avanzar a FASE 3 sin completar FASE 2.

---

### 1. CAMPOS OBLIGATORIOS POR ÍTEM

Los siguientes campos son obligatorios **por defecto**:

- tipo_evento (Entrada / Salida)
- guia (OBLIGATORIA solo si tipo_evento = "Recibido")
- marca
- modelo
- procesador
- ram
- almacenamiento
- cantidad

⚠️ EXCEPCIÓN:
Un campo solo puede omitirse si el **usuario lo indica explícitamente**
con frases como: “pon N/A”, “omitir”, “no aplica”.

La IA **NO puede decidir omitir campos por cuenta propia**.

---

### 2. DEFINICIÓN FORMAL DE CAMPO FALTANTE

Un campo se considera FALTANTE si ocurre cualquiera de las siguientes condiciones:

- El campo no existe en el JSON
- El valor es null
- El valor es una cadena vacía ""
- El valor es "N/A" sin autorización explícita del usuario
- El valor es 0 cuando el campo requiere un valor >= 1

---

### 3. REGLA DE BLOQUEO ABSOLUTO

Si el JSON contiene uno o más campos faltantes:

ESTÁ ESTRICTAMENTE PROHIBIDO:
- Declarar “tabla lista”
- Declarar “tabla actualizada”
- Generar filas finales
- Inferir o completar datos

La respuesta debe contener **ÚNICAMENTE** el campo `missing_info`.

---

### 4. FORMATO OBLIGATORIO DE `missing_info`

- UNA sola oración
- Campos separados por comas
- Sin repetir campos
- Sin explicaciones
- Sin palabras de cortesía

Ejemplo válido:
"missing_info": "Indica la cantidad, tipo de almacenamiento y destino del envío"

---

### 5. PROTOCOLO DE EXTRACCIÓN (CRÍTICO)

Antes de construir el JSON, debes separar la información del usuario en eventos independientes:

- **Evento A – Salidas / Envíos:** Todo lo que sale hacia agencias, sedes o destinos.
- **Evento B – Entradas / Recepciones:** Todo lo que ingresa desde proveedores o stock.

REGLA DE ORO:
Nunca mezcles atributos de un Evento A dentro de un ítem del Evento B, ni viceversa.

Cada evento genera ítems independientes.

---

### 6. LÓGICA DE NEGOCIO Y ESTADO

Estado automático por equipo:

- Si Procesador ≤ Gen 9 → 
  estado: "Dañado", destino: "DAÑADOS"

- Si Procesador ≥ Gen 10 y almacenamiento = HDD →
  estado: "Dañado", reporte: "REQUIERE CAMBIO A SSD"

- Si Procesador ≥ Gen 10 y almacenamiento = SSD →
  estado: "Bueno"

---

### 7. DESGLOSE OBLIGATORIO

Si el usuario menciona:
- “Combo”
- “Laptop con accesorios”
- “Incluye mouse, cargador, etc.”

Debes generar **una fila independiente por cada elemento**, sin agrupar.

---

### 8. PRIORIDAD DE INSTRUCCIONES DEL USUARIO

Si el usuario da una instrucción directa:
- “pon N/A”
- “añade a stock”
- “no evaluar estado”

Esa instrucción **tiene prioridad absoluta** sobre cualquier lógica automática.

---

### 9. REGLAS DE FORMATEO Y LIMPIEZA

- `missing_info` es tu **única voz** hacia el usuario.
- Corrige ortografía automáticamente.
- Estandariza marcas y nombres (HP, Dell, Lenovo).
- No inventes modelos, capacidades ni cantidades.

---

### 10. AUTOVERIFICACIÓN FINAL (OBLIGATORIA)

Antes de responder, pregúntate internamente:
“¿Puedo generar la tabla sin pedir ningún dato adicional?”

Si la respuesta es NO:
- Bloquea la salida final
- Usa exclusivamente `missing_info`
### 11. PROTOCOLO DE EXTRACCIÓN (CRÍTICO)
Antes de generar el JSON, separa la entrada del usuario en "Eventos Independientes":
- **Evento A (Salidas/Envíos):** Todo lo que va hacia agencias/destinos.
- **Evento B (Entradas/Recepciones):** Todo lo que llega de proveedores o stock.
*REGLA DE ORO:* Nunca mezcles atributos de un Evento A en un ítem del Evento B.

### 12. LÓGICA DE NEGOCIO Y ESTADO
- **Estado Automático:** - Si Proc <= Gen 9 -> estado: "Dañado", destino: "DAÑADOS".
  - Si Proc >= Gen 10 + HDD -> estado: "Dañado", reporte: "REQUIERE CAMBIO A SSD".
  - Si Proc >= Gen 10 + SSD -> estado: "Bueno".
- **Desglose Obligatorio:** Si el usuario dice "Combo" o "Laptop con X", crea una fila independiente para cada accesorio.
- **Prioridad de Datos:** Si el usuario da una instrucción directa ("ponle N/A", "añade a stock"), esa orden sobreescribe cualquier lógica automática.

### 13. REGLAS DE FORMATEO
- **Texto en JSON:** El campo `missing_info` es tu ÚNICA voz. Sé profesional y directa.
- **Limpieza:** Corrige ortografía (recivido -> Recibido) y estandariza marcas (HP, Dell, Lenovo).

### 14. ESTRUCTURA JSON OBLIGATORIA
{
  "status": "READY | QUESTION",
  "missing_info": "Mensaje de auditoría aquí",
  "items": [
    {
      "equipo": string,
      "marca": string,
      "modelo": string,
      "serie": string,
      "cantidad": number,
      "estado": "Bueno | Dañado",
      "tipo": "Enviado | Recibido",
      "origen": string,
      "destino": string,
      "guia": string,
      "fecha_llegada": "AAAA-MM-DD | N/A",
      "ram": string,
      "procesador": string,
      "disco": string,
      "reporte": string
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
    # 1. Mostrar historial
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): 
            st.markdown(m["content"])

    # 2. Entrada de chat
    if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): 
            st.markdown(prompt)

        try:
            with st.spinner("LAIA Auditando y consultando su memoria..."):
                # --- LÓGICA DE APRENDIZAJE ---
                lecciones_previas, _ = obtener_github(FILE_LECCIONES)
                texto_memoria = "\n".join([f"- ERROR: {l['lo_que_hizo_mal']} | LECCIÓN: {l['como_debe_hacerlo']}" for l in lecciones_previas])
                
                # Inyectamos el aprendizaje en el cerebro de LAIA
                prompt_con_memoria = f"{SYSTEM_PROMPT}\n\n=== MEMORIA DE ERRORES PASADOS (PROHIBIDO REPETIR) ===\n{texto_memoria}"
                
                # Memoria de la tabla actual
                contexto_tabla = json.dumps(st.session_state.draft) if st.session_state.draft else "[]"
                
                # Llamada a la IA
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": prompt_con_memoria},
                        {"role": "user", "content": f"BORRADOR ACTUAL: {contexto_tabla}\n\nMENSAJE USUARIO: {prompt}"}
                    ],
                    temperature=0
                )
                
                # Procesar respuesta (Aquí estaba el error de alineación)
                res_txt = extraer_json(response.choices[0].message.content)
                if res_txt:
                    res_json = json.loads(res_txt)
                    st.session_state.draft = res_json.get("items", [])
                    st.session_state.status = res_json.get("status", "READY")
                    st.session_state.missing_info = res_json.get("missing_info", "")

                    msg_laia = f"✅ Tabla actualizada. {st.session_state.missing_info}" if st.session_state.status=="QUESTION" else "✅ Tabla lista para enviar."
                    with st.chat_message("assistant"): 
                        st.markdown(msg_laia)
                    st.session_state.messages.append({"role": "assistant", "content": msg_laia})
                    st.rerun()

        except Exception as e:
            st.error(f"❌ Error de Auditoría: {error_msg}")

    # 3. Tabla en Vivo y Botones
    if st.session_state.draft:
        st.divider()
        st.subheader("📊 Tabla de Inventario (Edición en Vivo)")
        
        df_editor = pd.DataFrame(st.session_state.draft)
        # Forzamos el orden de las columnas para que no se desordenen
        cols_orden = ["equipo","marca","modelo","serie","cantidad","estado","tipo","origen","destino","guia","fecha_llegada","ram","procesador","disco","reporte"]
        df_editor = df_editor.reindex(columns=cols_orden).fillna("")
        
        edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True, key="auditoria_editor")
        
        if not df_editor.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

        c1, c2 = st.columns([1,4])
        with c1:
            if st.button("🚀 ENVIAR AL BUZÓN", type="primary"):
                if st.session_state.status == "QUESTION":
                    st.error(f"⛔ BLOQUEADO: {st.session_state.missing_info}")
                else:
                    with st.spinner("Sincronizando..."):
                        final_data = st.session_state.draft
                        fecha_now = (datetime.datetime.now(timezone.utc)-timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                        for d in final_data: d["fecha_registro"] = fecha_now
                        
                        if enviar_github(FILE_BUZON, final_data):
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
    st.subheader("📊 Control de Stock e Historial")
    
    # 1. Botón para forzar la sincronización (limpia el caché)
    if st.button("🔄 Sincronizar Datos de GitHub"):
        st.rerun()

    # 2. Obtenemos el histórico real
    hist, _ = obtener_github(FILE_HISTORICO)
    
    if hist:
        df_h = pd.DataFrame(hist)
        # Normalizamos columnas
        df_h.columns = df_h.columns.str.lower().str.strip()
        
        # 3. Calculamos stock (usando tu función)
        st_res, st_det = calcular_stock_web(df_h)
        
        # 4. Mostramos métricas
        k1, k2 = st.columns(2)
        k1.metric("📦 Stock Total", int(st_res['val'].sum()) if not st_res.empty else 0)
        k2.metric("🚚 Total Movimientos", len(df_h))

        # --- AQUÍ ESTÁ LA MAGIA PARA EL EXCEL ---
        import io
        buffer = io.BytesIO()
        # Creamos el Excel en la memoria del navegador con los datos de historico.json
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_h.to_excel(writer, index=False, sheet_name='Historico_Real')
            if not st_res.empty:
                st_res.to_excel(writer, index=False, sheet_name='Resumen_Stock')
        
        st.download_button(
            label="📥 DESCARGAR EXCEL SINCRONIZADO",
            data=buffer.getvalue(),
            file_name=f"Inventario_Jaher_{datetime.datetime.now().strftime('%d_%m_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary" # Lo pone en color verde/destacado
        )
        # ----------------------------------------

        # 5. Mostrar la tabla en la web para verificar
        st.write("### 📜 Últimos Movimientos en el Histórico")
        st.dataframe(df_h.tail(20), use_container_width=True) # Muestra los últimos 20
        
    else:
        st.warning("⚠️ No se encontraron datos en el histórico. Verifica que historico.json en GitHub tenga información.")
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
                st.sidebar.divider()
                st.sidebar.subheader("🎓 Entrenar a LAIA")
with st.sidebar.expander("¿LAIA cometió un error? Enséñale"):
    error_ia = st.text_area("¿Qué hizo mal LAIA?", placeholder="Ej: Me pidió fecha para un envío...")
    solucion_ia = st.text_area("¿Cómo debe actuar?", placeholder="Ej: Nunca pidas fecha si el tipo es 'Enviado'...")
    if st.button("🧠 Guardar Lección"):
        if error_ia and solucion_ia:
            if aprender_leccion(error_ia, solucion_ia):
                st.success("Lección guardada. LAIA no volverá a cometer ese error.")
                time.sleep(2)
                st.rerun()
            else:
                st.error("No se pudo guardar en GitHub.")

if st.sidebar.button("🧹 Borrar Chat"):
    st.session_state.messages = []
    st.session_state.draft = None
    st.rerun()
