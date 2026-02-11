import streamlit as st
from openai import OpenAI
import json
import pandas as pd
import datetime
import time
import io

# Importaciones de los otros archivos
from github_utils import *
from hardware_utils import *
from ai_logic import *
from glpi_utils import *

# CONFIGURACIÓN
st.set_page_config(page_title="LAIA v91.2", page_icon="🧠", layout="wide")

# Estilos simples para evitar errores de sintaxis
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
</style>
""", unsafe_allow_html=True)

# CREDENCIALES
try:
    API_KEY = st.secrets["GPT_API_KEY"]
    client = OpenAI(api_key=API_KEY)
    FILE_BUZON, FILE_HISTORICO, FILE_LECCIONES = "buzon.json", "historico.json", "lecciones.json"
except Exception as e:
    st.error(f"❌ Error de conexión GitHub: {str(e)}")
    st.stop()

# ESTADO DE SESIÓN
if "messages" not in st.session_state: st.session_state.messages = []
if "draft" not in st.session_state: st.session_state.draft = []
if "status" not in st.session_state: st.session_state.status = "NEW"

t1, t2, t3 = st.tabs(["💬 Chat Auditor", "📊 Stock Real", "🗑️ Limpieza"])

# ==============================
# TAB 1 — REGISTRO Y BORRADOR
# ==============================

with t1:
    # A. Mostrar historial de mensajes
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # B. Entrada de usuario
    if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            with st.spinner("LAIA auditando información..."):
                lecciones, _ = obtener_github(FILE_LECCIONES)

                memoria_err = "\n".join(
                    [f"- {l['lo_que_hizo_mal']} -> {l['como_debe_hacerlo']}" for l in lecciones]
                ) if lecciones else ""

                contexto_tabla = json.dumps(
                    st.session_state.draft, ensure_ascii=False
                ) if st.session_state.draft else "[]"

                mensajes_api = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": f"LECCIONES TÉCNICAS:\n{memoria_err}"},
                    {"role": "system", "content": f"ESTADO ACTUAL: {contexto_tabla}"}
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

                voz_interna = res_json.get("missing_info", "")
                msg_laia = f"{texto_fuera}\n{voz_interna}".strip()

                if not msg_laia:
                    msg_laia = "Instrucción técnica procesada."

                st.session_state.messages.append({"role": "assistant", "content": msg_laia})
                with st.chat_message("assistant"):
                    st.markdown(msg_laia)

                # ================= FUSIÓN DE ITEMS =================
                if "items" in res_json and res_json["items"]:
                    nuevos_items = res_json["items"]

                    if not st.session_state.draft:
                        st.session_state.draft = nuevos_items
                    else:
                        dict_actual = {
                            (i.get("serie") or i.get("modelo") or i.get("equipo")): i
                            for i in st.session_state.draft
                        }

                        for item in nuevos_items:
                            key = item.get("serie") or item.get("modelo") or item.get("equipo")
                            dict_actual[key] = item

                        st.session_state.draft = list(dict_actual.values())

                st.session_state.status = res_json.get("status", "QUESTION")

                if st.session_state.status == "READY":
                    st.success("✅ Datos auditados. Listo para guardar.")
                    time.sleep(1)
                    st.rerun()

        except Exception as e:
            st.error(f"Error en el motor de LAIA: {str(e)}")

    # ================= TABLA BORRADOR =================

    if st.session_state.draft:
        st.divider()
        st.subheader("📊 Borrador de Movimientos")

        # AUTOCORRECCIÓN CPU
        for d in st.session_state.draft:
            proc = d.get("procesador", "")
            gen = extraer_gen(proc)
            if gen == "obsoleto":
                d["estado"] = "Obsoleto / Pendiente Chatarrización"
                d["destino"] = "CHATARRA / BAJA"
                d["origen"] = d.get("origen", "Bodega")

        df_editor = pd.DataFrame(st.session_state.draft)

        cols_base = [
            "categoria_item", "equipo", "marca", "modelo", "serie",
            "cantidad", "estado", "tipo", "origen", "destino",
            "pasillo", "estante", "repisa", "guia", "fecha_llegada",
            "ram", "disco", "procesador", "reporte"
        ]

        for c in cols_base:
            if c not in df_editor.columns:
                df_editor[c] = ""

        df_editor = df_editor.reindex(columns=cols_base).fillna("N/A")

        edited_df = st.data_editor(
            df_editor,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_v11"
        )

        if not df_editor.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

    # ================= BOTONES GUARDADO =================

    c1, c2 = st.columns([1, 4])

    with c1:
        forzar = st.checkbox("🔓 Forzar")

    with c2:
        if st.session_state.status == "READY" or forzar:
            if st.button("🚀 GUARDAR EN HISTÓRICO", type="primary", use_container_width=True):

                for d in st.session_state.draft:
                    if extraer_gen(d.get("procesador", "")) == "obsoleto":
                        d["estado"] = "Obsoleto / Pendiente Chatarrización"
                        d["destino"] = "CHATARRA / BAJA"
                        d["origen"] = d.get("origen", "Bodega")

                ahora = (
                    datetime.datetime.now(datetime.timezone.utc)
                    - datetime.timedelta(hours=5)
                ).strftime("%Y-%m-%d %H:%M")

                for d in st.session_state.draft:
                    d["fecha_registro"] = ahora

                if enviar_github(FILE_BUZON, st.session_state.draft, "Registro LAIA"):
                    st.success("✅ ¡Guardado con éxito!")
                    st.session_state.draft = []
                    st.session_state.messages = []
                    st.session_state.status = "NEW"
                    time.sleep(1)
                    st.rerun()
        else:
            st.button("🚀 GUARDAR (BLOQUEADO)", disabled=True, use_container_width=True)

    if st.button("🗑️ Descartar Todo"):
        st.session_state.draft = []
        st.session_state.messages = []
        st.session_state.status = "NEW"
        st.rerun()


# ==============================
# TAB 2 — HISTORIAL Y STOCK
# ==============================

with t2:
    st.subheader("📊 Control de Stock e Historial")

    if st.button("🔄 Sincronizar Datos de GitHub"):
        st.rerun()

    hist, _ = obtener_github(FILE_HISTORICO)

    if hist:
        df_h_raw = pd.DataFrame(hist)

        st_res, bod_res, danados_res, df_h = calcular_stock_web(df_h_raw)

        k1, k2 = st.columns(2)
        total_stock = int(st_res["val"].sum()) if not st_res.empty else 0
        k1.metric("📦 Periféricos en Stock", total_stock)
        k2.metric("🚚 Movimientos Totales", len(df_h))

        import io
        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df_h.to_excel(writer, index=False, sheet_name="Enviados y Recibidos")

            if not st_res.empty:
                st_res.to_excel(writer, index=False, sheet_name="Stock (Saldos)")

            if not bod_res.empty:
                bod_res.to_excel(writer, index=False, sheet_name="BODEGA")

            if not danados_res.empty:
                danados_res.to_excel(writer, index=False, sheet_name="DAÑADOS")

        st.download_button(
            label="📥 DESCARGAR EXCEL SINCRONIZADO (4 HOJAS)",
            data=buffer.getvalue(),
            file_name=f"Inventario_Jaher_{datetime.datetime.now().strftime('%d_%m_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

        st.write("### 📜 Últimos Movimientos en el Histórico")
        st.dataframe(df_h.tail(20), use_container_width=True)


# ==============================
# TAB 3 — LIMPIEZA INTELIGENTE
# ==============================

with t3:
    st.subheader("🗑️ Limpieza Inteligente del Historial")

    st.markdown("""
    Usa este panel para eliminar registros específicos mediante lenguaje natural.
    LAIA analizará el historial para encontrar coincidencias.
    """)

    st.info("💡 Ejemplos: 'Borra lo de Latacunga', 'Elimina la serie 89238928', 'Limpia los teclados N/A'")

    txt_borrar = st.text_input(
        "¿Qué deseas eliminar?",
        placeholder="Escribe tu instrucción aquí..."
    )

    if st.button("🔥 BUSCAR Y GENERAR ORDEN DE BORRADO", type="secondary"):
        if txt_borrar:
            try:
                with st.spinner("LAIA analizando historial..."):

                    hist, _ = obtener_github(FILE_HISTORICO)
                    contexto_breve = json.dumps(hist[-40:], ensure_ascii=False) if hist else "[]"

                    p_db = f"""
Actúa como DBA Senior. Genera un comando de borrado en JSON.

COLUMNAS VÁLIDAS:
'equipo', 'marca', 'modelo', 'serie', 'guia',
'destino', 'origen', 'categoria_item'.

HISTORIAL:
{contexto_breve}

INSTRUCCIÓN:
"{txt_borrar}"

Reglas:
1. Si pide borrar todo:
{{"accion": "borrar_todo"}}

2. Si es específico:
{{"accion": "borrar_filtro", "columna": "...", "valor": "..."}}

Responde SOLO el JSON.
"""

                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "system", "content": p_db}],
                        temperature=0
                    )

                    raw_res = response.choices[0].message.content.strip()

                    inicio = raw_res.find("{")
                    fin = raw_res.rfind("}") + 1
                    order = json.loads(raw_res[inicio:fin])

                    if enviar_github(FILE_BUZON, order, "Orden de Borrado Inteligente"):
                        st.success("✅ Orden enviada con éxito.")
                        st.json(order)
                        st.warning("⚠️ El robot procesará la orden en segundos.")
                    else:
                        st.error("❌ No se pudo enviar la orden.")

            except Exception as e:
                st.error(f"Error en limpieza: {e}")
        else:
            st.warning("Escribe una instrucción antes de presionar el botón.")
