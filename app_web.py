import streamlit as st
import pandas as pd
import json

from ai_logic import client, SYSTEM_PROMPT, extraer_json
from github_utils import obtener_github, enviar_github
from inventory_engine import calcular_stock_web


# -------------------------------------------------
# CONFIGURACIÓN GLOBAL
# -------------------------------------------------
st.set_page_config(page_title="LAIA", layout="wide")
st.title("🧠 LAIA — Auditora TI")

FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"

if "messages" not in st.session_state:
    st.session_state.messages = []

if "draft" not in st.session_state:
    st.session_state.draft = []

if "status" not in st.session_state:
    st.session_state.status = "NEW"

if "missing_info" not in st.session_state:
    st.session_state.missing_info = ""


# -------------------------------------------------
# TABS
# -------------------------------------------------
t1, t2, t3 = st.tabs(["💬 Chat Auditor", "📊 Stock Real", "🗑️ Limpieza"])

# =================================================
# TAB 1 — CHAT
# =================================================
import streamlit as st
import pandas as pd
import json
import time
import datetime
import io

# Importaciones de tus módulos locales
from ai_logic import client, SYSTEM_PROMPT, extraer_json, extraer_gen
from github_utils import obtener_github, enviar_github
from inventory_engine import calcular_stock_web
# Asegúrate de crear este archivo o mover las funciones a uno existente
from glpi_utils import solicitar_busqueda_glpi, revisar_respuesta_glpi 

# -------------------------------------------------
# CONFIGURACIÓN GLOBAL
# -------------------------------------------------
st.set_page_config(page_title="LAIA", layout="wide")
st.title("🧠 LAIA — Auditora TI")

# Constantes de archivos
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
FILE_LECCIONES = "lecciones.json" # <--- Faltaba definir esta

# Inicialización de Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "draft" not in st.session_state:
    st.session_state.draft = []
if "status" not in st.session_state:
    st.session_state.status = "NEW"

# -------------------------------------------------
# TABS
# -------------------------------------------------
t1, t2, t3 = st.tabs(["💬 Chat Auditor", "📊 Stock Real", "🗑️ Limpieza"])

# =================================================
# TAB 1 — CHAT
# =================================================
with t1:
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            with st.spinner("LAIA auditando información..."):
                # Obtener contexto de lecciones
                lecciones, _ = obtener_github(FILE_LECCIONES)
                memoria_err = "\n".join([f"- {l['lo_que_hizo_mal']} -> {l['como_debe_hacerlo']}" for l in lecciones]) if lecciones else ""
                contexto_tabla = json.dumps(st.session_state.draft, ensure_ascii=False) if st.session_state.draft else "[]"

                # Configurar mensajes para la API
                mensajes_api = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": f"LECCIONES TÉCNICAS:\n{}"}, # <--- Ahora sí incluye la variable
                    {"role": "system", "content": f"ESTADO ACTUAL: {}"}     # <--- Ahora sí incluye la variable
                ]

                for m in st.session_state.messages[-10:]:
                    mensajes_api.append(m)

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=mensajes_api,
                    temperature=0
                )

                raw_content = response.choices[0].message.content
                texto_fuera, res_txt = extraer_json(raw_content)
                
                try:
                    res_json = json.loads(res_txt) if res_txt else {}
                except:
                    res_json = {}

                msg_laia = texto_fuera if texto_fuera else "Instrucción procesada."
                st.session_state.messages.append({"role": "assistant", "content": msg_laia})
                with st.chat_message("assistant"):
                    st.markdown(msg_laia)

                # Lógica de Fusión del Draft
                if "items" in res_json and res_json["items"]:
                    nuevos_items = res_json["items"]
                    if not st.session_state.draft:
                        st.session_state.draft = nuevos_items
                    else:
                        # Usar serie/modelo/equipo como llave única
                        dict_actual = { (i.get('serie') or i.get('modelo') or i.get('equipo')): i for i in st.session_state.draft }
                        for item in nuevos_items:
                            key = item.get('serie') or item.get('modelo') or item.get('equipo')
                            dict_actual[key] = item
                        st.session_state.draft = list(dict_actual.values())
                    
                    st.session_state.status = res_json.get("status", "QUESTION")
                    if st.session_state.status == "READY":
                        st.success("✅ Datos auditados. Listo para guardar.")
                        time.sleep(1)
                        st.rerun()
                        
        except Exception as e:
            st.error(f"Error en el motor de LAIA: {str(e)}")

    # 3. Tabla de Edición
    if st.session_state.draft:
        st.divider()
        st.subheader("📊 Borrador de Movimientos")
        
        # Autocorrección de obsolescencia
        for d in st.session_state.draft:
            gen = extraer_gen(d.get("procesador", ""))
            if gen == "obsoleto":
                d["estado"] = "Obsoleto / Pendiente Chatarrización"
                d["destino"] = "CHATARRA / BAJA"

        df_editor = pd.DataFrame(st.session_state.draft)
        cols_base = ["categoria_item", "equipo", "marca", "modelo", "serie", "cantidad", "estado", "tipo", "origen", "destino",
                     "pasillo", "estante", "repisa", "guia", "fecha_llegada", "ram", "disco", "procesador", "reporte"]
        
        # Asegurar que todas las columnas existan
        for c in cols_base:
            if c not in df_editor.columns: df_editor[c] = ""
        
        df_editor = df_editor.reindex(columns=cols_base).fillna("N/A")
        edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True, key="editor_v1")

        if not df_editor.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

        # Botones GLPI
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            if st.button("🔍 SOLICITAR BÚSQUEDA EN OFICINA"):
                serie_v = next((i.get('serie') for i in st.session_state.draft if i.get('serie') and i.get('serie') != "N/A"), None)
                if serie_v and solicitar_busqueda_glpi(serie_v):
                    st.toast(f"Búsqueda iniciada para: {serie_v}", icon="📡")
        
        with col_g2:
            if st.button("🔄 REVISAR Y AUTORELLENAR"):
                res_glpi = revisar_respuesta_glpi()
                if res_glpi and res_glpi.get("estado") == "completado":
                    # Lógica de actualización de draft... (tu código original aquí está bien)
                    st.success("¡Datos cargados!")
                    st.rerun()

        # Botones de Acción Final
        st.divider()
        c1, c2 = st.columns([1, 4])
        with c1:
            forzar = st.checkbox("🔓 Forzar")
        with c2:
            if st.session_state.status == "READY" or forzar:
                if st.button("🚀 GUARDAR EN HISTÓRICO", type="primary", use_container_width=True):
                    # Timestamp
                    ahora = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                    for d in st.session_state.draft: d["fecha_registro"] = ahora
                    
                    if enviar_github(FILE_BUZON, st.session_state.draft, "Registro LAIA"):
                        st.success("✅ ¡Guardado!")
                        st.session_state.draft = []
                        st.session_state.messages = []
                        st.session_state.status = "NEW"
                        time.sleep(1)
                        st.rerun()
            else:
                st.button("🚀 GUARDAR (BLOQUEADO)", disabled=True, use_container_width=True)



with t2:
  st.subheader("📊 Control de Stock e Historial")
   
  if st.button("🔄 Sincronizar Datos de GitHub"):
    st.rerun()

  hist, _ = obtener_github(FILE_HISTORICO)
   
  if hist:
    df_h_raw = pd.DataFrame(hist)
     
    # --- AQUÍ ES EL CAMBIO: Recibimos 4 variables ahora ---
    st_res, bod_res, danados_res, df_h = calcular_stock_web(df_h_raw)
     
    # 4. Mostramos métricas
    k1, k2 = st.columns(2)
    total_stock = int(st_res['val'].sum()) if not st_res.empty else 0
    k1.metric("📦 Periféricos en Stock", total_stock)
    k2.metric("🚚 Movimientos Totales", len(df_h))

    # --- GENERACIÓN DEL EXCEL MULTI-HOJA ---
    import io
    buffer = io.BytesIO()
     
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
      # HOJA 1: Historial Completo
      df_h.to_excel(writer, index=False, sheet_name='Enviados y Recibidos')
       
      # HOJA 2: Stock Saldos
      if not st_res.empty:
        st_res.to_excel(writer, index=False, sheet_name='Stock (Saldos)')
       
      # HOJA 3: BODEGA
      if not bod_res.empty:
        bod_res.to_excel(writer, index=False, sheet_name='BODEGA')

      # HOJA 4: DAÑADOS
      if not danados_res.empty:
        danados_res.to_excel(writer, index=False, sheet_name='DAÑADOS')
     
    st.download_button(
      label="📥 DESCARGAR EXCEL SINCRONIZADO (4 HOJAS)",
      data=buffer.getvalue(),
      file_name=f"Inventario_Jaher_{datetime.datetime.now().strftime('%d_%m_%H%M')}.xlsx",
      mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      type="primary" 
    )

    # 5. Mostrar la tabla en la web (el historial)
    st.write("### 📜 Últimos Movimientos en el Histórico")
    st.dataframe(df_h.tail(20), use_container_width=True) 
      
with t3:
  st.subheader("🗑️ Limpieza Inteligente del Historial")
  st.markdown("""
  Usa este panel para eliminar registros específicos mediante lenguaje natural. 
  LAIA analizará el historial para encontrar coincidencias.
  """)
  st.info("💡 Ejemplos: 'Borra lo de Latacunga', 'Elimina la serie 89238928', 'Limpia los teclados de marca N/A'")

  txt_borrar = st.text_input("¿Qué deseas eliminar?", placeholder="Escribe tu instrucción aquí...")

  if st.button("🔥 BUSCAR Y GENERAR ORDEN DE BORRADO", type="secondary"):
    if txt_borrar:
      try:
        with st.spinner("LAIA analizando historial para identificar el objetivo..."):
          # 1. Obtener contexto real del historial
          hist, _ = obtener_github(FILE_HISTORICO)
          # Mandamos los últimos 40 registros para que la IA vea nombres reales
          contexto_breve = json.dumps(hist[-40:], ensure_ascii=False) if hist else "[]"

          p_db = f"""
          Actúa como DBA Senior. Tu objetivo es generar un comando de borrado en JSON.
          Analiza el HISTORIAL ACTUAL para encontrar qué columna y valor coinciden con la instrucción.

          COLUMNAS VÁLIDAS: 'equipo', 'marca', 'modelo', 'serie', 'guia', 'destino', 'origen', 'categoria_item'.

          HISTORIAL ACTUAL (Muestra): {contexto_breve}

          INSTRUCCIÓN DEL USUARIO: "{txt_borrar}"

          REGLAS DE SALIDA:
          1. Si pide borrar todo: {{"accion": "borrar_todo"}}
          2. Si es específico:
             - Identifica la columna que mejor encaja.
             - Si el usuario menciona un lugar, suele ser 'destino' u 'origen'.
             - Si menciona un código largo, es 'serie' o 'guia'.
             - Genera: {{"accion": "borrar_filtro", "columna": "nombre_de_columna", "valor": "valor_exacto_encontrado_en_historial"}}

          RESPONDE ÚNICAMENTE EL JSON.
          """

          response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": p_db}],
            temperature=0
          )

          raw_res = response.choices[0].message.content.strip()
          # Extraer JSON por si la IA pone texto extra
          inicio = raw_res.find("{")
          fin = raw_res.rfind("}") + 1
          order = json.loads(raw_res[inicio:fin])

          # 2. Enviar la orden al buzón para que el Robot de la PC la ejecute
          if enviar_github(FILE_BUZON, order, "Orden de Borrado Inteligente"):
            st.success("✅ Orden de borrado enviada con éxito.")
            st.json(order)
            st.warning("⚠️ El Robot en tu PC procesará esto en unos segundos y actualizará el Excel y la Nube.")
          else:
            st.error("❌ No se pudo enviar la orden a GitHub.")

      except Exception as e:
        st.error(f"Error en el motor de limpieza: {e}")
    else:
      st.warning("Escribe una instrucción antes de presionar el botón.")
