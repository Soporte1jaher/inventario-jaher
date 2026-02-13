import streamlit as st
import html
import json
import pandas as pd

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler


class ChatTab:
    """
    LAIA — Chat + Tabla (Borrador)
    ✅ Chat bonito + respeta saltos de línea
    ✅ Tabla de borrador como antes (data_editor)
    ✅ JSON debug solo en modo técnico
    """

    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()

        self.LOGO_URL = "https://raw.githubusercontent.com/Soporte1jaher/inventario-jaher/main/assets/logo_jaher.png"

        st.session_state.setdefault("messages", [])
        st.session_state.setdefault("draft", [])
        st.session_state.setdefault("status", "NEW")

        st.session_state.setdefault("modo_tecnico", False)
        st.session_state.setdefault("last_json", {})

    # ---------------------------
    # UI style
    # ---------------------------
    def _inject_style(self):
        st.markdown(
            """
            <style>
              .block-container { padding-top: 0.9rem; padding-bottom: 1.1rem; max-width: 1100px; }

              .stApp {
                background: radial-gradient(1200px 600px at 15% 10%, rgba(46,125,50,0.12), transparent 60%),
                            radial-gradient(900px 500px at 85% 15%, rgba(0,180,255,0.10), transparent 55%),
                            #0e1117 !important;
              }

              #jaher-logo{
                position: fixed;
                top: 14px;
                right: 18px;
                z-index: 9999;
                width: 110px;
                opacity: 0.95;
                filter: drop-shadow(0 8px 18px rgba(0,0,0,0.40));
              }

              [data-testid="stChatMessage"]{
                border-radius: 16px;
                border: 1px solid rgba(255,255,255,0.06);
                background: rgba(255,255,255,0.02);
              }

              .user-pre{
                white-space: pre-wrap;
                word-wrap: break-word;
                line-height: 1.35rem;
                font-size: 0.98rem;
                opacity: 0.98;
              }

              /* Tabla/borrador */
              div[data-testid="stDataEditor"]{
                border-radius: 14px;
                overflow: hidden;
                border: 1px solid rgba(255,255,255,0.08);
                background: rgba(255,255,255,0.02);
              }

              details summary { font-weight: 800; }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def _render_logo(self):
        if self.LOGO_URL:
            st.markdown(f"""<img id="jaher-logo" src="{self.LOGO_URL}" />""", unsafe_allow_html=True)

    def _render_user_text_preserving_lines(self, text: str):
        safe = html.escape(text or "")
        st.markdown(f"<div class='user-pre'>{safe}</div>", unsafe_allow_html=True)

    def _is_saludo_o_basura(self, text: str) -> bool:
        t = (text or "").strip().lower()
        if len(t) <= 2:
            return True
        saludos = ["hola", "buenas", "buenos dias", "buen día", "buenas tardes", "buenas noches", "hey", "qe tal", "que tal", "holi", "ola"]
        if any(s == t or t.startswith(s + " ") for s in saludos):
            return True
        if t in ["ok", "dale", "aja", "sí", "si", "ya", "listo", "gracias", "xd", ":v"]:
            return True
        return False

    # ---------------------------
    # Main render
    # ---------------------------
    def render(self):
        self._inject_style()
        self._render_logo()

        # Toggle técnico arriba
        top_l, top_r = st.columns([4, 1.2], vertical_alignment="center")
        with top_r:
            st.session_state["modo_tecnico"] = st.toggle(
                "🛠️ Modo técnico",
                value=bool(st.session_state.get("modo_tecnico", False))
            )

        # CHAT
        for m in st.session_state.messages:
            role = m.get("role", "assistant")
            content = m.get("content", "")
            with st.chat_message(role):
                if role == "user":
                    self._render_user_text_preserving_lines(content)
                else:
                    st.markdown(content)

        if prompt := st.chat_input("Dime qué llegó o qué enviaste (puedes pegar varias líneas)..."):
            self._procesar_mensaje(prompt)
            st.rerun()

        # JSON debug (solo técnico)
        if st.session_state.get("modo_tecnico", False):
            last = st.session_state.get("last_json", {}) or {}
            with st.expander("🧾 JSON (debug)", expanded=False):
                st.code(json.dumps(last, ensure_ascii=False, indent=2), language="json")

        # ✅ TABLA BORRADOR (como antes)
        if st.session_state.get("draft"):
            self._render_borrador()

    # ---------------------------
    # Core
    # ---------------------------
    def _procesar_mensaje(self, prompt: str):
        prompt = (prompt or "").rstrip()
        if not prompt:
            return

        st.session_state.messages.append({"role": "user", "content": prompt})

        if self._is_saludo_o_basura(prompt):
            st.session_state.messages.append({
                "role": "assistant",
                "content": (
                    "Dime un movimiento de inventario.\n\n"
                    "Ejemplos:\n"
                    "- `Recibí 1 laptop Dell serie 099209`\n"
                    "- `Envié 1 CPU a Pedernales guía 12345`\n"
                    "- Puedes pegar varios movimientos, uno por línea."
                )
            })
            st.session_state["last_json"] = {"status": "QUESTION", "missing_info": "Falta movimiento de inventario"}
            return

        try:
            with st.spinner("🧠 LAIA auditando..."):
                lecciones = self.github.obtener_lecciones()

                resultado = self.ai_engine.procesar_input(
                    user_input=prompt,
                    lecciones=lecciones,
                    borrador_actual=st.session_state.draft,
                    historial_mensajes=st.session_state.messages
                )

                mensaje = resultado.get("mensaje", "Sin respuesta.")
                st.session_state.messages.append({"role": "assistant", "content": mensaje})

                res_json = resultado.get("json_response", {}) or {}
                st.session_state["last_json"] = res_json

                items = res_json.get("items") or []
                if items:
                    self._merge_draft(items)

                st.session_state["status"] = res_json.get("status", "QUESTION")

        except Exception as e:
            st.session_state.messages.append({"role": "assistant", "content": f"⚠️ Error en el motor de LAIA: {str(e)}"})
            st.session_state["last_json"] = {"status": "ERROR", "error": str(e)}

    def _merge_draft(self, nuevos_items):
        if not st.session_state.draft:
            st.session_state.draft = nuevos_items
            return

        actual = {(i.get("serie") or i.get("modelo") or i.get("equipo")): i for i in st.session_state.draft}
        for item in nuevos_items:
            key = item.get("serie") or item.get("modelo") or item.get("equipo")
            actual[key] = item
        st.session_state.draft = list(actual.values())

    # ---------------------------
    # Tabla de borrador
    # ---------------------------
    def _render_borrador(self):
        st.markdown("---")

        with st.container(border=True):
            left, mid, right = st.columns([2.4, 1, 1], vertical_alignment="center")
            with left:
                st.markdown("#### 📊 Borrador de Movimientos")
                st.caption("Revisa y corrige aquí. Se guarda en sesión.")
            with mid:
                st.metric("Items", len(st.session_state.draft))
            with right:
                st.caption(f"Estado: **{st.session_state.get('status', 'NEW')}**")

        # columnas base (las que tu robot espera)
        cols_base = [
            "categoria_item", "equipo", "marca", "modelo", "serie", "cantidad", "estado",
            "tipo", "origen", "destino", "pasillo", "estante", "repisa", "guia", "fecha_llegada",
            "ram", "disco", "procesador", "reporte"
        ]

        df = pd.DataFrame(st.session_state.draft).copy()
        for c in cols_base:
            if c not in df.columns:
                df[c] = ""

        df = df.reindex(columns=cols_base).fillna("N/A")

        with st.container(border=True):
            edited = st.data_editor(
                df,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key="editor_borrador_chat"
            )

        # sincronizar cambios
        if not df.equals(edited):
            st.session_state.draft = edited.to_dict("records")
            st.session_state.status = "QUESTION"
            st.rerun()

        # botones mínimos
        c1, c2 = st.columns([1.2, 2.8], vertical_alignment="center")
        with c1:
            if st.button("🗑️ Limpiar borrador", use_container_width=True):
                st.session_state.draft = []
                st.session_state.status = "NEW"
                st.rerun()
        with c2:
            st.caption("Tip: si LAIA marca faltantes, completa aquí y vuelve a enviar un 'OK' para que re-audite.")
