import streamlit as st
import time
import datetime

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler


class ChatTab:
    """
    LAIA — Chat Only (UI para usuarios finales)
    ✅ Solo chat
    ✅ Estética pro + UX para usuarios no técnicos
    ✅ Manejo de "hola" / basura con guía de ejemplo
    """

    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()

        # Opcional: logo flotante
        self.LOGO_URL = "https://raw.githubusercontent.com/Soporte1jaher/inventario-jaher/main/assets/logo_jaher.png"

        # Session base
        st.session_state.setdefault("messages", [])
        st.session_state.setdefault("draft", [])
        st.session_state.setdefault("status", "NEW")

        # UX flags
        st.session_state.setdefault("show_examples", True)

    # ---------------------------
    # UI style (pro, simple)
    # ---------------------------
    def _inject_style(self):
        st.markdown(
            """
            <style>
              .block-container { padding-top: 1rem; padding-bottom: 1.2rem; max-width: 980px; }
              [data-testid="stChatMessage"] { border-radius: 14px; }
              .stButton button { border-radius: 12px !important; font-weight: 800 !important; }
              #jaher-logo{
                position: fixed;
                top: 14px;
                right: 18px;
                z-index: 9999;
                width: 110px;
                opacity: 0.95;
                filter: drop-shadow(0 6px 14px rgba(0,0,0,0.35));
              }
              .hint-card{
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.08);
                background: rgba(255,255,255,0.02);
                padding: 12px 14px;
                margin-bottom: 10px;
              }
              .hint-title{ font-weight: 900; opacity: .95; margin-bottom: 6px; }
              .hint-txt{ opacity: .85; font-size: .95rem; margin: 0; }
              .chip-row{ display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
              .chip{
                display:inline-block;
                padding: 6px 10px;
                border-radius: 999px;
                border: 1px solid rgba(255,255,255,0.12);
                background: rgba(255,255,255,0.03);
                font-size: .9rem;
                opacity: .9;
              }
              .mini{
                opacity:.7;
                font-size:.85rem;
                margin-top:6px;
              }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def _render_logo(self):
        if self.LOGO_URL:
            st.markdown(f"""<img id="jaher-logo" src="{self.LOGO_URL}" />""", unsafe_allow_html=True)

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
        # Mensajes típicos sin contenido operativo
        if t in ["ok", "dale", "aja", "sí", "si", "ya", "listo", "gracias", "xd", ":v"]:
            return True
        return False

    def _render_examples_card(self):
        if not st.session_state.get("show_examples", True):
            return

        st.markdown(
            """
            <div class="hint-card">
              <div class="hint-title">🧠 ¿Qué debo escribir?</div>
              <p class="hint-txt">
                Escribe tal como lo dirías por WhatsApp. Incluye <b>tipo</b> (recibido/enviado), <b>equipo</b>,
                y si es envío: <b>destino + guía</b>. Si tienes series, pégalas una por línea.
              </p>
              <div class="chip-row">
                <span class="chip">Recibí 2 laptops Dell 5420 desde Bodega</span>
                <span class="chip">Envié 1 laptop a Babahoyo guía 12345</span>
                <span class="chip">Registrar lote: equipo laptop, marca HP, modelo 440 G8 + series...</span>
              </div>
              <div class="mini">Tip: si solo escribes “hola”, LAIA te pedirá datos.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns([1.4, 1.0])
        with c1:
            if st.button("🙋‍♂️ Pegar ejemplo de 'ENVIADO'", use_container_width=True):
                self._prefill_and_fire("Enviado: 1 laptop a Babahoyo guía 12345")
        with c2:
            if st.button("✅ Ocultar ayuda", use_container_width=True):
                st.session_state["show_examples"] = False
                st.rerun()

    def _prefill_and_fire(self, prompt: str):
        # No existe prefill nativo en chat_input; lo disparo procesando el prompt directamente
        self._procesar_mensaje(prompt)
        st.rerun()

    # ---------------------------
    # Main render
    # ---------------------------
    def render(self):
        self._inject_style()
        self._render_logo()

        # Card de ayuda arriba (para usuarios finales)
        self._render_examples_card()

        # Chat
        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

        if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
            self._procesar_mensaje(prompt)

    # ---------------------------
    # Core
    # ---------------------------
    def _procesar_mensaje(self, prompt: str):
        prompt = (prompt or "").strip()
        if not prompt:
            return

        # Si es “hola” o mensaje vacío de negocio, responde guiando
        if self._is_saludo_o_basura(prompt):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.messages.append({
                "role": "assistant",
                "content": (
                    "Necesito datos de inventario.\n\n"
                    "**Escribe así (ejemplos):**\n"
                    "- `Recibí 2 laptops Dell 5420 desde Bodega`\n"
                    "- `Envié 1 laptop a Babahoyo guía 12345`\n"
                    "- `Registrar lote: equipo laptop, marca HP, modelo 440 G8` + pega series\n"
                )
            })
            return

        # Guardar user msg
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

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
                with st.chat_message("assistant"):
                    st.markdown(mensaje)

                res_json = resultado.get("json_response", {}) or {}

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

    def _merge_draft(self, nuevos_items):
        if not st.session_state.draft:
            st.session_state.draft = nuevos_items
            return

        # Merge por clave: serie > modelo > equipo
        actual = {(i.get("serie") or i.get("modelo") or i.get("equipo")): i for i in st.session_state.draft}
        for item in nuevos_items:
            key = item.get("serie") or item.get("modelo") or item.get("equipo")
            actual[key] = item
        st.session_state.draft = list(actual.values())
