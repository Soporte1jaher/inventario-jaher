import streamlit as st
import html
import json
import pandas as pd
import re

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler


class ChatTab:
    """
    LAIA — Chat + Tabla (Borrador) [CORREGIDO]
    ✅ Respeta saltos de línea del usuario
    ✅ La respuesta del assistant se muestra como JSON (según SYSTEM_PROMPT)
    ✅ Tabla de borrador (data_editor) como antes
    ✅ Vista simple opcional (para usuarios finales)
    ✅ Cinturón de seguridad: Intel <= 9th Gen => CHATARRA/BAJA siempre
    """

    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()

        self.LOGO_URL = "https://raw.githubusercontent.com/Soporte1jaher/inventario-jaher/main/assets/logo_jaher.png"

        st.session_state.setdefault("messages", [])
        st.session_state.setdefault("draft", [])
        st.session_state.setdefault("status", "NEW")

        # UI toggles
        st.session_state.setdefault("modo_tecnico", False)     # muestra JSON debug abajo
        st.session_state.setdefault("vista_simple", True)      # usuarios finales: resumen corto (opcional)

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

    # =========================================================
    # ✅ CINTURÓN DE SEGURIDAD (PROMPT NO SIEMPRE OBEDECE)
    # =========================================================
    def _infer_intel_gen(self, proc: str):
        """
        Devuelve gen Intel como int (8, 10, etc) o None.
        Soporta:
          - 'Intel Core i5 - 10th Gen'
          - 'core i3 de octava'
          - 'i5-10210u', 'i7 8565u'
        """
        if not proc:
            return None
        p = str(proc).lower().strip()

        # "10th gen", "8th gen"
        m = re.search(r'(\d{1,2})\s*(?:th)?\s*gen', p)
        if m:
            try:
                return int(m.group(1))
            except:
                pass

        # español: "octava", "8va", "10ma"
        if any(x in p for x in ["octava", "8va", "8a", "8ª"]):
            return 8
        if any(x in p for x in ["novena", "9na", "9a", "9ª"]):
            return 9
        if any(x in p for x in ["decima", "décima", "10ma", "10a", "10ª"]):
            return 10
        if any(x in p for x in ["11ma", "11a", "11ª"]) or "11th" in p:
            return 11
        if any(x in p for x in ["12ma", "12a", "12ª"]) or "12th" in p:
            return 12

        # i5-10210u / i7-8565u
        m2 = re.search(r'i[3579]\s*[- ]?\s*(\d{4,5})', p)
        if m2:
            code = m2.group(1)
            try:
                if len(code) == 4:
                    return int(code[0])         # 8565 -> 8
                if len(code) == 5:
                    return int(code[:2])        # 10210 -> 10
            except:
                return None

        return None

    def _is_force_override(self, user_text: str) -> bool:
        """
        Regla #5 del prompt: si el usuario dice 'así está bien' etc => READY y N/A.
        Aquí solo detectamos para NO pelear la corrección si el usuario lo ordenó.
        """
        t = (user_text or "").lower()
        triggers = ["enviar así", "guarda eso", "no importa", "asi esta bien", "así está bien"]
        return any(x in t for x in triggers)

    def _enforce_chatarrizacion_rule(self, items: list, user_text: str) -> list:
        """
        Aplica regla #1: Intel <= 9 => CHATARRA/BAJA + estado obsoleto.
        Esto es post-check, no depende del modelo.
        Solo se evita si el usuario está activando OVERRIDE (#5).
        """
        if not items:
            return items

        if self._is_force_override(user_text):
            # si el usuario forzó, no tocamos nada: el prompt manda READY + N/A
            return items

        fixed = []
        for it in items:
            x = dict(it)

            equipo = str(x.get("equipo", "") or "").lower()
            categoria = str(x.get("categoria_item", "") or "").lower()
            es_computo = ("computo" in categoria) or any(k in equipo for k in ["laptop", "cpu", "servidor", "aio", "all-in-one", "tablet"])

            gen = self._infer_intel_gen(str(x.get("procesador", "") or ""))

            if es_computo and gen is not None and gen <= 9:
                x["estado"] = "Obsoleto / Pendiente Chatarrización"
                x["destino"] = "CHATARRA / BAJA"

            fixed.append(x)

        return fixed

    # ---------------------------
    # Main render
    # ---------------------------
    def render(self):
        self._inject_style()
        self._render_logo()

        top_l, top_r = st.columns([4, 2.2], vertical_alignment="center")
        with top_r:
            st.session_state["vista_simple"] = st.toggle(
                "👤 Vista simple (usuarios)",
                value=bool(st.session_state.get("vista_simple", True)),
                help="ON: muestra un resumen corto. OFF: muestra el JSON en el chat."
            )
            st.session_state["modo_tecnico"] = st.toggle(
                "🛠️ Modo técnico",
                value=bool(st.session_state.get("modo_tecnico", False)),
                help="Muestra el JSON crudo también abajo (debug)."
            )

        # CHAT
        for m in st.session_state.messages:
            role = m.get("role", "assistant")
            content = m.get("content", "")
            fmt = m.get("format", "md")

            with st.chat_message(role):
                if role == "user":
                    self._render_user_text_preserving_lines(content)
                else:
                    if fmt == "json":
                        st.code(content, language="json")
                    else:
                        st.markdown(content)

        if prompt := st.chat_input("Dime qué llegó o qué enviaste (puedes pegar varias líneas)..."):
            self._procesar_mensaje(prompt)
            st.rerun()

        if st.session_state.get("modo_tecnico", False):
            last = st.session_state.get("last_json", {}) or {}
            with st.expander("🧾 JSON (debug)", expanded=False):
                st.code(json.dumps(last, ensure_ascii=False, indent=2), language="json")

        if st.session_state.get("draft"):
            self._render_borrador()

    # ---------------------------
    # Core
    # ---------------------------
    def _procesar_mensaje(self, prompt: str):
        prompt = (prompt or "").rstrip()
        if not prompt:
            return

        st.session_state.messages.append({"role": "user", "content": prompt, "format": "text"})

        if self._is_saludo_o_basura(prompt):
            res_json = {
                "status": "QUESTION",
                "missing_info": "Falta movimiento de inventario",
                "items": st.session_state.draft or []
            }
            st.session_state["last_json"] = res_json

            if st.session_state.get("vista_simple", True):
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "Necesito un movimiento. Ej: `Recibí 1 laptop Dell serie 099209` o `Envié 1 CPU a Pedernales guía 12345`.",
                    "format": "md"
                })
            else:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": json.dumps(res_json, ensure_ascii=False, indent=2),
                    "format": "json"
                })
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

                res_json = (resultado.get("json_response") or {}) if isinstance(resultado, dict) else {}
                if not res_json:
                    res_json = {
                        "status": "QUESTION",
                        "missing_info": "Motor no devolvió json_response",
                        "items": st.session_state.draft or []
                    }

                # ✅ APLICAR REGLA SUPREMA EN CÓDIGO
                items = res_json.get("items") or []
                if items:
                    items = self._enforce_chatarrizacion_rule(items, prompt)
                    res_json["items"] = items
                    self._set_draft(items)

                st.session_state["last_json"] = res_json
                st.session_state["status"] = res_json.get("status", "QUESTION")

                if st.session_state.get("vista_simple", True):
                    missing = (res_json.get("missing_info") or "").strip()
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": missing if missing else "READY: sin faltantes.",
                        "format": "md"
                    })
                else:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": json.dumps(res_json, ensure_ascii=False, indent=2),
                        "format": "json"
                    })

        except Exception as e:
            res_json = {"status": "ERROR", "missing_info": "", "error": str(e), "items": st.session_state.draft or []}
            st.session_state["last_json"] = res_json
            st.session_state.messages.append({
                "role": "assistant",
                "content": json.dumps(res_json, ensure_ascii=False, indent=2),
                "format": "json"
            })

    def _set_draft(self, items):
        st.session_state.draft = items

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
                key="editor_borrador_chat_v2"
            )

        if not df.equals(edited):
            st.session_state.draft = edited.to_dict("records")
            st.session_state.status = "QUESTION"
            st.rerun()

        c1, c2 = st.columns([1.2, 2.8], vertical_alignment="center")
        with c1:
            if st.button("🗑️ Limpiar borrador", use_container_width=True):
                st.session_state.draft = []
                st.session_state.status = "NEW"
                st.rerun()
        with c2:
            st.caption("Completa faltantes en la tabla. Luego envía: `así está bien` para forzar READY.")
