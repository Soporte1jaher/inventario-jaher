import streamlit as st
import html
import json

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler


class ChatTab:
    """
    LAIA — Chat Only (Final)
    ✅ Solo chat (sin ayuda)
    ✅ Estética pro
    ✅ Respeta saltos de línea del usuario
    ✅ JSON visible SOLO en modo técnico (para ti)
    """

    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()

        self.LOGO_URL = "https://raw.githubusercontent.com/Soporte1jaher/inventario-jaher/main/assets/logo_jaher.png"

        st.session_state.setdefault("messages", [])
        st.session_state.setdefault("draft", [])
        st.session_state.setdefault("status", "NEW")

        # ✅ Para debug/JSON
        st.session_state.setdefault("modo_tecnico", False)
        st.session_state.setdefault("last_json", {})

    # ---------------------------
    # UI style (más pro)
    # ---------------------------
    def _inject_style(self):
        st.markdown(
            """
            <style>
              .block-container { padding-top: 0.9rem; padding-bottom: 1.1rem; max-width: 980px; }

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
                white-space: pre-wrap;      /* ✅ respeta Enter */
                word-wrap: break-word;
                line-height: 1.35rem;
                font-size: 0.98rem;
                opacity: 0.98;
              }

              .stButton button{
                border-radius: 12px !important;
                font-weight: 850 !important;
              }

              /* Expander más limpio */
              details summary { font-weight: 800; }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def _render_logo(self):
        if self.LOGO_URL:
            st.markdown(f"""<img id="jaher-logo" src="{self.LOGO_URL}" />""", unsafe_allow_html=True)

    # ---------------------------
    # Render helpers
    # ---------------------------
    def _render_user_text_preserving_lines(self, text: str):
        safe = html.escape(text or "")
        st.markdown(f"<div class='user-pre'>{safe}</div>", unsafe_allow_html=True)

    # ---------------------------
    # UX helpers
    # ---------------------------
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

        # ✅ Toggle discreto SOLO para ti (arriba)
        top_l, top_r = st.columns([3.5, 1.3], vertical_alignment="center")
        with top_r:
            st.session_state["modo_tecnico"] = st.toggle("🛠️ Modo técnico", value=bool(st.session_state.get("modo_tecnico", False)))

        # Chat
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

        # ✅ Mostrar JSON SOLO si modo técnico está activo
        if st.session_state.get("modo_tecnico", False):
            last = st.session_state.get("last_json", {}) or {}
            with st.expander("🧾 JSON (debug)", expanded=False):
                st.code(json.dumps(last, ensure_ascii=False, indent=2), language="json")

    # ---------------------------
    # Core
    # ---------------------------
    def _procesar_mensaje(self, prompt: str):
        prompt = (prompt or "").rstrip()
        if not prompt:
            return

        # Guardar user msg
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Respuesta rápida si ponen “hola”
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
                st.session_state["last_json"] = res_json  # ✅ aquí guardas el JSON para mostrarlo

                # Mantener borrador interno (aunque UI sea solo chat)
                items = res_json.get("items") or []
                if items:
                    self._merge_draft(items)

                st.session_state["status"] = res_json.get("status", "QUESTION")

        except Exception as e:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"⚠️ Error en el motor de LAIA: {str(e)}"
            })
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
