import streamlit as st
import html
import json
import pandas as pd
import re
from datetime import datetime, timezone, timedelta

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler


class ChatTab:
    """
    LAIA — Chat + Tabla (Borrador) [FIX]
    ✅ Respeta saltos de línea del usuario
    ✅ Vista simple REAL (tarjeta) vs JSON crudo (code)
    ✅ Modo técnico (JSON crudo abajo)
    ✅ Tabla borrador (data_editor)
    ✅ Botón GUARDAR Y ENVIAR AL ROBOT
    ✅ Cinturón de seguridad: Intel <= 9 => CHATARRA/BAJA (si no hay override)
    ✅ NO rompe con: "Motor no devolvió json_response"
    ✅ IDLE para charla/preguntas (frío) como tu prompt v14
    """

    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()

        self.LOGO_URL = "https://raw.githubusercontent.com/Soporte1jaher/inventario-jaher/main/assets/logo_jaher.png"

        st.session_state.setdefault("messages", [])
        st.session_state.setdefault("draft", [])
        st.session_state.setdefault("status", "NEW")

        st.session_state.setdefault("modo_tecnico", False)
        st.session_state.setdefault("vista_simple", True)

        st.session_state.setdefault("last_json", {})
        st.session_state.setdefault("forzar_guardado", False)

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

              .simple-card{
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.08);
                background: rgba(255,255,255,0.02);
                padding: 12px 14px;
              }
              .simple-title{ font-weight: 900; margin-bottom: 6px; display:flex; align-items:center; gap:10px; }
              .simple-muted{ opacity: .78; font-size: .95rem; }
              .badge{
                display:inline-block;
                padding: 3px 10px;
                border-radius: 999px;
                border: 1px solid rgba(255,255,255,0.12);
                background: rgba(255,255,255,0.03);
                font-size: .85rem;
                opacity: .95;
              }
              .b-ok{ border-color: rgba(0,230,118,0.35); }
              .b-warn{ border-color: rgba(255,179,0,0.35); }
              .b-idle{ border-color: rgba(130,177,255,0.35); }
              .b-bad{ border-color: rgba(255,82,82,0.35); }

              /* para que el toggle "vista simple" se note visualmente */
              .hint-mode{
                opacity:.75;
                font-size:.85rem;
                margin-top:-6px;
              }
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

    # ---------------------------
    # Detecciones (NO secuestrar la IA)
    # ---------------------------
    def _is_force_override(self, user_text: str) -> bool:
        t = (user_text or "").lower()
        triggers = ["enviar así", "guarda eso", "no importa", "asi esta bien", "así está bien", "asi nomas", "así nomás", "forzar ready"]
        return any(x in t for x in triggers)

    def _is_smalltalk(self, text: str) -> bool:
        """Saludo / charla sin inventario: debe responder IDLE (frío) según prompt."""
        t = (text or "").strip().lower()
        if not t:
            return True
        if len(t) <= 2:
            return True
        saludos = [
            "hola", "holaa", "buenas", "buenos dias", "buen día", "buenas tardes", "buenas noches",
            "hey", "que tal", "qe tal", "holi", "ola", "como estas", "cómo estás"
        ]
        if any(s == t or t.startswith(s + " ") for s in saludos):
            return True
        if t in ["ok", "dale", "aja", "sí", "si", "ya", "listo", "gracias", "xd", ":v"]:
            return True
        return False

    def _is_about_me(self, text: str) -> bool:
        """Preguntas sobre LAIA => IDLE con respuesta fría."""
        t = (text or "").strip().lower()
        keys = [
            "quien eres", "quién eres", "que eres", "qué eres", "de que eres capaz", "de qué eres capaz",
            "que haces", "qué haces", "que puedes hacer", "qué puedes hacer", "capacidades", "funciones"
        ]
        return any(k in t for k in keys)

    def _looks_like_inventory(self, text: str) -> bool:
        """Heurística mínima: si parece inventario, NO dejamos items vacíos."""
        t = (text or "").lower()
        verbs = ["llego", "llegó", "me llego", "me llegó", "recibi", "recibí", "envié", "envie", "envio", "envió", "mandé", "mande"]
        stuff = ["laptop", "cpu", "monitor", "pantalla", "teclado", "mouse", "impresora", "servidor", "aio", "all-in-one", "tablet", "router", "switch", "ap", "aruba"]
        return any(v in t for v in verbs) and any(s in t for s in stuff)

    # ---------------------------
    # JSON extraction robusto
    # ---------------------------
    def _extract_json(self, resultado):
        """
        Soporta:
          - dict con 'json_response'
          - dict con 'response' / 'content' que trae JSON string
          - string JSON puro
        """
        if resultado is None:
            return None

        if isinstance(resultado, dict):
            if isinstance(resultado.get("json_response"), dict):
                return resultado.get("json_response")
            if isinstance(resultado.get("json_response"), str):
                return self._try_parse_json(resultado.get("json_response"))

            # otras claves comunes
            for k in ["response", "content", "message", "raw"]:
                v = resultado.get(k)
                if isinstance(v, dict):
                    # si ya es dict, asumo que es el JSON final
                    if "items" in v and "status" in v:
                        return v
                if isinstance(v, str):
                    parsed = self._try_parse_json(v)
                    if parsed and isinstance(parsed, dict) and "items" in parsed and "status" in parsed:
                        return parsed
            return None

        if isinstance(resultado, str):
            return self._try_parse_json(resultado)

        return None

    def _try_parse_json(self, s: str):
        if not s:
            return None
        try:
            return json.loads(s)
        except:
            # intenta extraer el primer bloque {...} por si viene texto con JSON incrustado
            try:
                m = re.search(r"\{.*\}", s, flags=re.DOTALL)
                if m:
                    return json.loads(m.group(0))
            except:
                return None
        return None

    # ---------------------------
    # Cinturón chatarrización
    # ---------------------------
    def _infer_intel_gen(self, proc: str):
        if not proc:
            return None
        p = str(proc).lower().strip()

        m = re.search(r'(\d{1,2})\s*(?:th)?\s*gen', p)
        if m:
            try:
                return int(m.group(1))
            except:
                pass

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
        if any(x in p for x in ["13ma", "13a", "13ª"]) or "13th" in p:
            return 13
        if any(x in p for x in ["14ma", "14a", "14ª"]) or "14th" in p:
            return 14

        m2 = re.search(r'i[3579]\s*[- ]?\s*(\d{4,5})', p)
        if m2:
            code = m2.group(1)
            try:
                if len(code) == 4:
                    return int(code[0])
                if len(code) == 5:
                    return int(code[:2])
            except:
                return None

        return None

    def _enforce_chatarrizacion_rule(self, items: list, user_text: str) -> list:
        if not items:
            return items
        if self._is_force_override(user_text):
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
    # Vista simple (tarjeta)
    # ---------------------------
    def _render_simple_assistant(self, res_json: dict):
        status = (res_json.get("status") or "QUESTION").upper()
        missing = (res_json.get("missing_info") or "").strip()
        items = res_json.get("items") or []

        if status == "READY":
            badge = "<span class='badge b-ok'>READY</span>"
            title = f"{badge} Listo para enviar"
            subtitle = f"Items: {len(items)}. Si está correcto, presiona **GUARDAR Y ENVIAR**."
        elif status == "IDLE":
            badge = "<span class='badge b-idle'>IDLE</span>"
            title = f"{badge} Sin movimiento"
            subtitle = "Reporta movimientos (recibido/enviado) con series/guías."
        else:
            badge = "<span class='badge b-warn'>QUESTION</span>"
            title = f"{badge} Faltan datos"
            subtitle = "Completa lo faltante en la tabla o escribe la corrección."

        st.markdown(
            f"""
            <div class="simple-card">
              <div class="simple-title">{title}</div>
              <div class="simple-muted">{html.escape(subtitle)}</div>
              {"<div style='margin-top:10px; white-space:pre-wrap;'>" + html.escape(missing) + "</div>" if missing else ""}
            </div>
            """,
            unsafe_allow_html=True
        )

    # ---------------------------
    # Render
    # ---------------------------
    def render(self):
        self._inject_style()
        self._render_logo()

        top_l, top_r = st.columns([4, 2.2], vertical_alignment="center")
        with top_r:
            st.session_state["vista_simple"] = st.toggle(
                "👤 Vista simple (usuarios)",
                value=bool(st.session_state.get("vista_simple", True)),
                help="ON: tarjeta resumen. OFF: JSON crudo en el chat."
            )
            st.session_state["modo_tecnico"] = st.toggle(
                "🛠️ Modo técnico",
                value=bool(st.session_state.get("modo_tecnico", False)),
                help="Muestra JSON crudo también abajo (debug)."
            )
            # micro-indicador visible
            st.markdown(
                "<div class='hint-mode'>"
                + ("Modo: <b>Tarjeta</b>" if st.session_state["vista_simple"] else "Modo: <b>JSON</b>")
                + "</div>",
                unsafe_allow_html=True
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
                    elif fmt == "simple":
                        try:
                            self._render_simple_assistant(json.loads(content))
                        except:
                            st.markdown(content)
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
    def _reply(self, res_json: dict):
        """Centraliza cómo se muestra la respuesta (simple vs json)."""
        st.session_state["last_json"] = res_json
        st.session_state["status"] = res_json.get("status", "QUESTION")

        if st.session_state.get("vista_simple", True):
            st.session_state.messages.append({
                "role": "assistant",
                "content": json.dumps(res_json, ensure_ascii=False),
                "format": "simple"
            })
        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": json.dumps(res_json, ensure_ascii=False, indent=2),
                "format": "json"
            })

    def _procesar_mensaje(self, prompt: str):
        prompt = (prompt or "").rstrip()
        if not prompt:
            return

        st.session_state.messages.append({"role": "user", "content": prompt, "format": "text"})

        # 1) Preguntas sobre LAIA / charla => IDLE frío (NO QUESTION)
        if self._is_about_me(prompt):
            res_json = {
                "status": "IDLE",
                "missing_info": "Soy LAIA v14.0. Audito hardware y registro movimientos (recibido/enviado), validando series, guías, specs y destino. Reporta los movimientos pendientes.",
                "items": st.session_state.draft or []
            }
            self._reply(res_json)
            return

        if self._is_smalltalk(prompt) and not self._looks_like_inventory(prompt):
            res_json = {
                "status": "IDLE",
                "missing_info": "Ese mensaje no es un movimiento. Reporta recepción o envío con equipo/serie/guía/destino.",
                "items": st.session_state.draft or []
            }
            self._reply(res_json)
            return

        # 2) Si el usuario fuerza override, NO bloquees; deja que el motor lo haga (y si falla, forzamos READY)
        forced = self._is_force_override(prompt)

        try:
            with st.spinner("🧠 LAIA auditando..."):
                lecciones = self.github.obtener_lecciones()

                resultado = self.ai_engine.procesar_input(
                    user_input=prompt,
                    lecciones=lecciones,
                    borrador_actual=st.session_state.draft,
                    historial_mensajes=st.session_state.messages
                )

                res_json = self._extract_json(resultado)

                # 3) Si el motor no devolvió JSON, fallback decente
                if not res_json:
                    if self._looks_like_inventory(prompt):
                        # crea 1 item genérico para que la tabla exista (tu regla NMMS: jamás items:[])
                        res_json = {
                            "status": "QUESTION" if not forced else "READY",
                            "missing_info": "Motor no devolvió JSON. Se creó borrador mínimo. Completa datos en la tabla.",
                            "items": [
                                {
                                    "categoria_item": "Computo",
                                    "tipo": "Recibido",
                                    "equipo": "N/A",
                                    "marca": "N/A",
                                    "modelo": "N/A",
                                    "serie": "N/A",
                                    "cantidad": 1,
                                    "estado": "N/A",
                                    "procesador": "N/A",
                                    "ram": "N/A",
                                    "disco": "N/A",
                                    "reporte": "",
                                    "origen": "N/A",
                                    "destino": "Bodega",
                                    "pasillo": "N/A",
                                    "estante": "N/A",
                                    "repisa": "N/A",
                                    "guia": "N/A",
                                    "fecha_llegada": "N/A"
                                }
                            ]
                        }
                    else:
                        # no parece inventario => IDLE (no molestes con QUESTION)
                        res_json = {
                            "status": "IDLE",
                            "missing_info": "Ese mensaje no contiene un movimiento inventariable. Reporta equipos/series/guías.",
                            "items": st.session_state.draft or []
                        }

                # 4) Cinturón supremo + set draft
                items = res_json.get("items") or []
                if items:
                    items = self._enforce_chatarrizacion_rule(items, prompt)
                    res_json["items"] = items
                    self._set_draft(items)

                # 5) Si el usuario force override y el motor no puso READY, nosotros lo dejamos READY (UI)
                if forced:
                    res_json["status"] = "READY"

                self._reply(res_json)

        except Exception as e:
            res_json = {
                "status": "ERROR",
                "missing_info": "Error en motor.",
                "error": str(e),
                "items": st.session_state.draft or []
            }
            self._reply(res_json)

    def _set_draft(self, items):
        st.session_state.draft = items

    # ---------------------------
    # Guardar / Enviar
    # ---------------------------
    def _guardar_y_enviar(self):
    # Hora Ecuador (UTC-5)
        ahora = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")

        payload = []
       for item in (st.session_state.draft or []):
          x = dict(item)
          x["fecha_registro"] = x.get("fecha_registro") or ahora
          payload.append(x)

         ok = self.github.enviar_a_buzon(payload)
      if ok:
        st.success("✅ Enviado al Robot de la PC", icon="✅")

        # ✅ LIMPIEZA TOTAL (chat + borrador + estado)
          st.session_state["draft"] = []
          st.session_state["status"] = "NEW"
          st.session_state["forzar_guardado"] = False
          st.session_state["last_json"] = {}

        # ✅ chat limpio para nuevo registro
          st.session_state["messages"] = []

        # ✅ opcional: “reset” del data_editor (evita que quede cacheado)
          st.session_state["editor_reset_key"] = str(datetime.now().timestamp())

          st.rerun()
      else:
          st.error("❌ No se pudo enviar al buzón. Revisa token/permiso/red.")

    # ---------------------------
    # Tabla borrador
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
                key="editor_borrador_chat_final_fix"
            )

        if not df.equals(edited):
            st.session_state.draft = edited.to_dict("records")
            st.session_state.status = "QUESTION"
            st.rerun()

        c1, c2, c3 = st.columns([1.2, 1.8, 1.8], vertical_alignment="center")

        with c1:
            st.session_state["forzar_guardado"] = st.checkbox(
                "🔓 Forzar",
                value=bool(st.session_state.get("forzar_guardado", False)),
                help="Permite enviar aunque el estado sea QUESTION (bajo tu responsabilidad).",
                key="chk_forzar_guardado"
            )

        allow_save = (st.session_state.get("status") == "READY") or bool(st.session_state.get("forzar_guardado", False))

        with c2:
            if allow_save:
                if st.button("🚀 GUARDAR Y ENVIAR AL ROBOT", type="primary", use_container_width=True, key="btn_send_robot"):
                    self._guardar_y_enviar()
            else:
                st.button("🚀 GUARDAR (FALTAN DATOS)", disabled=True, use_container_width=True, key="btn_send_robot_disabled")

        with c3:
            if st.button("🗑️ Limpiar borrador", use_container_width=True, key="btn_clear_draft"):
                st.session_state.draft = []
                st.session_state.status = "NEW"
                st.session_state.forzar_guardado = False
                st.rerun()
