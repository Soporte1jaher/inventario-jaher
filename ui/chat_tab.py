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

        # ============== CONFIG UI (LIMPIO Y FUNCIONAL) ==============
        self.LOGO_URL = "https://raw.githubusercontent.com/Soporte1jaher/inventario-jaher/main/assets/logo_jaher.png"
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
        st.markdown(
            """
            <style>
              /* Layout más pro */
              .block-container { padding-top: 1.2rem; padding-bottom: 1.2rem; max-width: 1200px; }

              /* Cards (containers con border=True) un poco más premium */
              div[data-testid="stVerticalBlockBorderWrapper"]{
                border-radius: 16px !important;
                border: 1px solid rgba(255,255,255,0.08) !important;
                background: rgba(255,255,255,0.02);
              }

              /* Chat messages más suaves */
              [data-testid="stChatMessage"]{
                border-radius: 14px;
              }

              /* Botones más corporativos */
              .stButton button{
                border-radius: 12px !important;
                font-weight: 800 !important;
                padding: 0.55rem 0.9rem !important;
              }

              /* Data editor: borde + radius */
              div[data-testid="stDataEditor"]{
                border-radius: 14px;
                overflow: hidden;
                border: 1px solid rgba(255,255,255,0.08);
              }

              /* Logo flotante */
              #jaher-logo{
                position: fixed;
                top: 14px;
                right: 18px;
                z-index: 9999;
                width: 120px;
                opacity: 0.95;
                filter: drop-shadow(0 6px 14px rgba(0,0,0,0.35));
              }

              /* Quita padding raro alrededor del chat input */
              [data-testid="stVerticalBlock"] > div:has(> [data-testid="stChatInput"]) { padding-top: .2rem; }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def _render_floating_logo(self):
        """
        Logo JAHER flotante en esquina.
        - Preferencia: URL
        - Fallback: archivo local
        - Si nada existe: no rompe nada
        """
        # 1) Intento por URL (más fácil en Streamlit Cloud)
        if self.LOGO_URL:
            st.markdown(
                f"""<img id="jaher-logo" src="{self.LOGO_URL}" />""",
                unsafe_allow_html=True
            )
            return

        # 2) Fallback local (si lo empaquetas en repo /assets/)
        try:
            st.image(self.LOGO_LOCAL_PATH, width=120)
        except:
            pass

    def _render_header(self):
        with st.container(border=True):
            st.markdown(f"### {self.APP_TITLE}")
            st.caption(self.APP_SUBTITLE)

            status = st.session_state.get("status", "NEW")
            if status == "READY":
                st.success("Estado: READY (Listo para guardar)", icon="✅")
            elif status == "QUESTION":
                st.warning("Estado: QUESTION (Faltan datos)", icon="⚠️")
            else:
                st.info("Estado: NEW (Sin borrador)", icon="ℹ️")

    def render(self):
        # UI (sin archivo CSS)
        self._inject_micro_style()
        self._render_floating_logo()
        self._render_header()

        # ============= ZONA CHAT =============
        with st.container(border=True):
            st.markdown("#### 💬 Chat Auditor")
            st.caption("Escribe en lenguaje natural lo que llegó o lo que enviaste. LAIA lo audita y arma el borrador.")

            for m in st.session_state.messages:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])

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

                st.session_state.messages.append({"role": "assistant", "content": resultado["mensaje"]})
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
        ahora = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
        for item in st.session_state.draft:
            item["fecha_registro"] = ahora

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
