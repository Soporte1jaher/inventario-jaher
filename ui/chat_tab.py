import streamlit as st
import pandas as pd
import time
import datetime

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler
from modules.stock_calculator import StockCalculator


class ChatTab:
    """Tab de chat para auditoría - UI Corporativa + Logo JAHER (sin perder funcionalidad)"""

    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()
        self.stock_calc = StockCalculator()

        # ============== CONFIG UI ==============
        # Opción A: URL pública (recomendado)
        # Ejemplo: "https://raw.githubusercontent.com/Soporte1jaher/inventario-jaher/main/assets/logo_jaher.png"
        self.LOGO_URL = None

        # Opción B: logo dentro del repo (recomendado si lo subes a /assets/)
        self.LOGO_LOCAL_PATH = "assets/logo_jaher.png"

        self.APP_TITLE = "LAIA — Auditoría de Bodega TI"
        self.APP_SUBTITLE = "Corporación Jarrín Herrera (JAHER)"

        # Inicializar estado de sesión
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "draft" not in st.session_state:
            st.session_state.draft = []
        if "status" not in st.session_state:
            st.session_state.status = "NEW"
        if "missing_info" not in st.session_state:
            st.session_state.missing_info = ""

    # ---------------------------
    # UI Helpers (sin archivo CSS)
    # ---------------------------
    def _inject_micro_style(self):
        """
        Micro-estilos (opcionales) incrustados aquí.
        No necesitas crear archivo CSS.
        Si algún día no te gusta, lo borras y todo sigue funcionando.
        """
        st.markdown(
            """
            <style>
              /* Espaciado superior más pro */
              .block-container { padding-top: 1.2rem; }

              /* Chat un poquito más “corporativo” */
              [data-testid="stChatMessage"] { border-radius: 14px; }

              /* Botones un poco más firmes */
              .stButton button { border-radius: 10px; }

              /* Data editor: bordes suaves */
              [data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

              /* Quita padding feo en algunos contenedores */
              [data-testid="stVerticalBlock"] > div:has(> [data-testid="stChatInput"]) { padding-top: .2rem; }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def _render_header(self):
        """
        Encabezado corporativo con logo en esquina derecha.
        """
        with st.container(border=True):
            c1, c2 = st.columns([4, 1], vertical_alignment="center")

            with c1:
                st.markdown(f"### {self.APP_TITLE}")
                st.caption(self.APP_SUBTITLE)

                # Chip de estado
                status = st.session_state.get("status", "NEW")
                if status == "READY":
                    st.success("Estado: READY (Listo para guardar)", icon="✅")
                elif status == "QUESTION":
                    st.warning("Estado: QUESTION (Faltan datos)", icon="⚠️")
                else:
                    st.info("Estado: NEW (Sin borrador)", icon="ℹ️")

            with c2:
                # Logo: intenta URL, si no hay, intenta archivo local
                logo_rendered = False

                if self.LOGO_URL:
                    try:
                        st.image(self.LOGO_URL, use_container_width=True)
                        logo_rendered = True
                    except:
                        logo_rendered = False

                if not logo_rendered:
                    try:
                        st.image(self.LOGO_LOCAL_PATH, use_container_width=True)
                        logo_rendered = True
                    except:
                        # Si no existe, no rompemos nada
                        st.caption(" ")

    def render(self):
        # UI micro (sin archivo CSS)
        self._inject_micro_style()

        # Header corporativo
        self._render_header()

        # ============= ZONA CHAT =============
        with st.container(border=True):
            st.markdown("#### 💬 Chat Auditor")
            st.caption("Escribe en lenguaje natural lo que llegó o lo que enviaste. LAIA lo audita y arma el borrador.")

            # A. Mostrar historial de mensajes
            for m in st.session_state.messages:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])

            # B. Entrada de usuario
            if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
                self._procesar_mensaje(prompt)

        # ============= BORRADOR / TABLA =============
        if st.session_state.draft:
            self._mostrar_borrador()

    def _procesar_mensaje(self, prompt):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            with st.spinner("🧠 LAIA auditando información..."):
                lecciones = self.github.obtener_lecciones()

                resultado = self.ai_engine.procesar_input(
                    user_input=prompt,
                    lecciones=lecciones,
                    borrador_actual=st.session_state.draft,
                    historial_mensajes=st.session_state.messages
                )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": resultado["mensaje"]
                })

                with st.chat_message("assistant"):
                    st.markdown(resultado["mensaje"])

                res_json = resultado["json_response"]
                if "items" in res_json and res_json["items"]:
                    self._actualizar_borrador(res_json["items"])

                st.session_state.status = res_json.get("status", "QUESTION")
                if st.session_state.status == "READY":
                    st.success("✅ Datos auditados. Listo para guardar.", icon="✅")

        except Exception as e:
            st.error(f"Error en el motor de LAIA: {str(e)}")

    def _actualizar_borrador(self, nuevos_items):
        if not st.session_state.draft:
            st.session_state.draft = nuevos_items
        else:
            dict_actual = {(i.get('serie') or i.get('modelo') or i.get('equipo')): i for i in st.session_state.draft}
            for item in nuevos_items:
                key = item.get('serie') or item.get('modelo') or item.get('equipo')
                dict_actual[key] = item
            st.session_state.draft = list(dict_actual.values())

    def _mostrar_borrador(self):
        st.markdown("---")

        with st.container(border=True):
            top1, top2 = st.columns([3, 1], vertical_alignment="center")

            with top1:
                st.markdown("#### 📊 Borrador de Movimientos")
                st.caption("Revisa, ajusta si hace falta y guarda. (Puedes forzar si quieres saltar preguntas).")

            with top2:
                st.metric("Items en borrador", len(st.session_state.draft))

            # Sincronizar con el calculador de stock modular
            st.session_state.draft = self.stock_calc.aplicar_reglas_obsolescencia(st.session_state.draft)

            df_editor = pd.DataFrame(st.session_state.draft)
            cols_base = [
                "categoria_item", "equipo", "marca", "modelo", "serie", "cantidad", "estado",
                "tipo", "origen", "destino", "pasillo", "estante", "repisa", "guia", "fecha_llegada",
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
                key="editor_v12",
                hide_index=True
            )

            if not df_editor.equals(edited_df):
                st.session_state.draft = edited_df.to_dict("records")

            st.markdown(" ")
            self._mostrar_botones_accion()

    def _mostrar_botones_accion(self):
        c1, c2, c3 = st.columns([1.2, 3.2, 1.6], vertical_alignment="center")

        with c1:
            forzar = st.checkbox("🔓 Forzar", help="Permite guardar aunque LAIA marque QUESTION.")

        with c2:
            if st.session_state.status == "READY" or forzar:
                if st.button("🚀 GUARDAR Y ENVIAR AL ROBOT", type="primary", use_container_width=True):
                    self._guardar_borrador()
            else:
                st.button("🚀 GUARDAR (BLOQUEADO)", disabled=True, use_container_width=True)

        with c3:
            if st.button("🗑️ Descartar Todo", use_container_width=True):
                self._limpiar_sesion()

    def _guardar_borrador(self):
        # Sellar con fecha (UTC-5)
        ahora = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
        for item in st.session_state.draft:
            item["fecha_registro"] = ahora

        # Enviar al BUZÓN para el Robot
        if self.github.enviar_a_buzon(st.session_state.draft):
            st.success("✅ ¡Enviado al Robot de la PC!", icon="✅")
            self._limpiar_sesion()
            time.sleep(1)
            st.rerun()

    def _limpiar_sesion(self):
        st.session_state.draft = []
        st.session_state.messages = []
        st.session_state.status = "NEW"
        st.rerun()
