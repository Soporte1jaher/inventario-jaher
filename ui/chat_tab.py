import streamlit as st
import pandas as pd
import time
import datetime
from collections import Counter

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler
from modules.stock_calculator import StockCalculator


class ChatTab:
    """
    Chat Auditor — UI Corporativa + 2 upgrades:
    ✅ (A) Vista Operativa arriba del borrador (widgets mini)
    ✅ (B) Plantillas conversacionales (botones que “escriben” al chat y disparan a LAIA)
    """

    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()
        self.stock_calc = StockCalculator()

        self.LOGO_URL = "https://raw.githubusercontent.com/Soporte1jaher/inventario-jaher/main/assets/logo_jaher.png"
        self.APP_TITLE = "LAIA — Auditoría de Bodega TI"
        self.APP_SUBTITLE = "Corporación Jarrín Herrera (JAHER)"

        # Session state base
        st.session_state.setdefault("messages", [])
        st.session_state.setdefault("draft", [])
        st.session_state.setdefault("status", "NEW")
        st.session_state.setdefault("missing_info", "")

        # ✅ Sidebar state
        st.session_state.setdefault("confirm_risky_save", False)

        # ✅ Plantillas conversacionales (valores por defecto)
        st.session_state.setdefault("tpl_tipo", "recibido")
        st.session_state.setdefault("tpl_origen", "")
        st.session_state.setdefault("tpl_destino", "")
        st.session_state.setdefault("tpl_equipo", "laptops")
        st.session_state.setdefault("tpl_marca", "")
        st.session_state.setdefault("tpl_modelo", "")
        st.session_state.setdefault("tpl_cantidad", 1)
        st.session_state.setdefault("tpl_guia", "")
        st.session_state.setdefault("tpl_series_text", "")

        # ✅ Buffer para disparar mensajes al chat
        st.session_state.setdefault("chat_prefill", "")
        st.session_state.setdefault("chat_fire", False)

    # ---------------------------
    # UI style
    # ---------------------------
    def _inject_micro_style(self):
        st.markdown(
            """
            <style>
              .block-container { padding-top: 1.1rem; padding-bottom: 1.1rem; max-width: 1250px; }

              div[data-testid="stVerticalBlockBorderWrapper"]{
                border-radius: 16px !important;
                border: 1px solid rgba(255,255,255,0.08) !important;
                background: rgba(255,255,255,0.02);
              }

              [data-testid="stChatMessage"]{ border-radius: 14px; }

              .stButton button{
                border-radius: 12px !important;
                font-weight: 800 !important;
                padding: 0.55rem 0.9rem !important;
              }

              div[data-testid="stDataEditor"]{
                border-radius: 14px;
                overflow: hidden;
                border: 1px solid rgba(255,255,255,0.08);
              }

              #jaher-logo{
                position: fixed;
                top: 14px;
                right: 18px;
                z-index: 9999;
                width: 120px;
                opacity: 0.95;
                filter: drop-shadow(0 6px 14px rgba(0,0,0,0.35));
              }

              .op-card{
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.08);
                background: rgba(255,255,255,0.02);
                padding: 14px 14px 10px 14px;
              }
              .op-title{ font-weight: 900; opacity: 0.9; margin-bottom: 6px; }
              .op-mini{ opacity: 0.85; font-size: 0.95rem; }
              .op-alert{ color: #ffb300; font-weight: 900; }
              .op-bad{ color: #ff5252; font-weight: 900; }
              .op-ok{ color: #00e676; font-weight: 900; }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def _render_floating_logo(self):
        if self.LOGO_URL:
            st.markdown(f"""<img id="jaher-logo" src="{self.LOGO_URL}" />""", unsafe_allow_html=True)

    # ---------------------------
    # Data helpers
    # ---------------------------
    def _get_sedes_sugeridas(self):
        try:
            hist = self.github.obtener_historico() or []
            df = pd.DataFrame([x for x in hist if isinstance(x, dict)])
            if df.empty:
                return []
            sedes = []
            for c in ["origen", "destino"]:
                if c in df.columns:
                    sedes += df[c].astype(str).str.strip().tolist()
            sedes = [s for s in sedes if s and s.lower() not in ["n/a", "na", "none", "nan", ""]]
            sedes = sorted(list(dict.fromkeys(sedes)))
            return sedes[:250]
        except Exception:
            return []

    def _validate_draft(self, draft_items):
        if not draft_items:
            return {"ok": 0, "warn": 0, "bad": 0}, [], pd.DataFrame()

        df = pd.DataFrame(draft_items).copy()

        for c in ["tipo", "equipo", "marca", "modelo", "serie", "origen", "destino", "guia", "cantidad", "estado"]:
            if c not in df.columns:
                df[c] = ""

        for c in ["tipo", "equipo", "marca", "modelo", "serie", "origen", "destino", "guia", "estado"]:
            df[c] = df[c].astype(str).fillna("").str.strip()

        errors = []
        status_col = []
        ok = warn = bad = 0

        for _, r in df.iterrows():
            t = str(r["tipo"]).lower()
            serie = str(r["serie"])
            guia = str(r["guia"])
            destino = str(r["destino"])
            origen = str(r["origen"])
            equipo = str(r["equipo"])

            row_issues = []

            if equipo.strip() in ["", "N/A", "n/a"]:
                row_issues.append("Falta equipo")

            if "envi" in t:
                if guia.strip() in ["", "N/A", "n/a"]:
                    row_issues.append("Enviado sin guía")
                if destino.strip() in ["", "N/A", "n/a"]:
                    row_issues.append("Enviado sin destino")

            if "recib" in t:
                if origen.strip() in ["", "N/A", "n/a"]:
                    row_issues.append("Recibido sin origen")

            if serie.strip() in ["", "N/A", "n/a"]:
                if str(r.get("modelo", "")).strip() in ["", "N/A", "n/a"]:
                    row_issues.append("Sin serie/modelo")

            if len(row_issues) == 0:
                status_col.append("OK")
                ok += 1
            elif any("Enviado sin" in x for x in row_issues):
                status_col.append("CRÍTICO")
                bad += 1
                errors += row_issues
            else:
                status_col.append("REVISAR")
                warn += 1
                errors += row_issues

        df["validacion"] = status_col
        resumen = {"ok": ok, "warn": warn, "bad": bad}
        errors = sorted(list(dict.fromkeys(errors)))
        return resumen, errors, df

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

    # =========================================================
    # ✅ (A): Vista Operativa
    # =========================================================
    def _render_vista_operativa(self, df: pd.DataFrame, resumen: dict, errores: list):
        if df is None or df.empty:
            return

        tipos = df.get("tipo", pd.Series([], dtype=str)).astype(str).str.lower().str.strip()
        recibidos = int(tipos.str.contains("recib").sum())
        enviados = int(tipos.str.contains("envi").sum())

        origenes = df.get("origen", pd.Series([], dtype=str)).astype(str).str.strip()
        destinos = df.get("destino", pd.Series([], dtype=str)).astype(str).str.strip()

        def _top_values(s: pd.Series, k=3):
            vals = [x for x in s.tolist() if x and str(x).strip() and str(x).strip().lower() not in ["n/a", "na", "none", "nan"]]
            if not vals:
                return []
            c = Counter(vals)
            return [x for x, _ in c.most_common(k)]

        top_origen = _top_values(origenes, k=2)
        top_dest = _top_values(destinos, k=4)

        guia = df.get("guia", pd.Series([], dtype=str)).astype(str).str.strip().str.lower()
        destino_l = destinos.astype(str).str.strip().str.lower()

        enviados_mask = tipos.str.contains("envi")
        sin_guia = int((enviados_mask & guia.isin(["", "n/a", "na", "none", "nan"])).sum())
        sin_destino = int((enviados_mask & destino_l.isin(["", "n/a", "na", "none", "nan"])).sum())

        with st.container(border=True):
            a, b, c = st.columns([1.2, 1.8, 1.6], vertical_alignment="center")

            with a:
                st.markdown(
                    f"""
                    <div class="op-card">
                      <div class="op-title">📌 Resumen</div>
                      <div class="op-mini">Recibidos: <span class="op-ok">{recibidos}</span></div>
                      <div class="op-mini">Enviados: <span class="op-ok">{enviados}</span></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with b:
                o_txt = ", ".join(top_origen) if top_origen else "N/A"
                d_txt = ", ".join(top_dest) if top_dest else "N/A"
                st.markdown(
                    f"""
                    <div class="op-card">
                      <div class="op-title">🏢 Sedes</div>
                      <div class="op-mini">Origen (top): <b>{o_txt}</b></div>
                      <div class="op-mini">Destinos (top): <b>{d_txt}</b></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with c:
                crit = int(resumen.get("bad", 0))
                rev = int(resumen.get("warn", 0))
                st.markdown(
                    f"""
                    <div class="op-card">
                      <div class="op-title">⚠️ Alertas</div>
                      <div class="op-mini">Enviados sin guía: <span class="{ 'op-bad' if sin_guia else 'op-ok' }">{sin_guia}</span></div>
                      <div class="op-mini">Enviados sin destino: <span class="{ 'op-bad' if sin_destino else 'op-ok' }">{sin_destino}</span></div>
                      <div class="op-mini">Críticos: <span class="{ 'op-bad' if crit else 'op-ok' }">{crit}</span> | Revisar: <span class="{ 'op-alert' if rev else 'op-ok' }">{rev}</span></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if errores:
            with st.expander("🧩 Detalles de alertas", expanded=False):
                for e in errores[:15]:
                    st.write(f"- {e}")

    # =========================================================
    # ✅ (B): Plantillas conversacionales (CORREGIDO)
    # =========================================================
    def _render_plantillas_conversacionales(self):
        sedes = self._get_sedes_sugeridas()

        with st.container(border=True):
            st.markdown("#### ⚡ Plantillas rápidas (conversación)")
            st.caption("Toca una plantilla, completa 2-3 campos y LAIA recibe el mensaje ya armado.")

            c1, c2, c3, c4 = st.columns([1.2, 1.6, 1.6, 1.2], vertical_alignment="center")
            with c1:
                st.selectbox("Tipo", ["recibido", "enviado"], key="tpl_tipo")
            with c2:
                st.selectbox("Origen", options=[""] + sedes, key="tpl_origen")
            with c3:
                st.selectbox("Destino", options=[""] + sedes, key="tpl_destino")
            with c4:
                st.number_input("Cantidad", min_value=1, value=int(st.session_state.get("tpl_cantidad", 1)), step=1, key="tpl_cantidad")

            d1, d2, d3, d4 = st.columns(4, vertical_alignment="center")
            with d1:
                st.text_input("Equipo", value=st.session_state.get("tpl_equipo", "laptops"), key="tpl_equipo")
            with d2:
                st.text_input("Marca", value=st.session_state.get("tpl_marca", ""), key="tpl_marca")
            with d3:
                st.text_input("Modelo", value=st.session_state.get("tpl_modelo", ""), key="tpl_modelo")
            with d4:
                st.text_input("Guía (si enviado)", value=st.session_state.get("tpl_guia", ""), key="tpl_guia")

            st.markdown("**Plantillas**")
            b1, b2, b3, b4 = st.columns([1.25, 1.25, 1.45, 1.05], vertical_alignment="center")

            with b1:
                if st.button("📦 Recibí laptops", use_container_width=True, key="tpl_btn_laptops"):
                    self._chat_send_template(self._tpl_build_recibi_laptops())

            with b2:
                if st.button("🚚 Envié equipos", use_container_width=True, key="tpl_btn_envie"):
                    self._chat_send_template(self._tpl_build_envie_equipos())

            with b3:
                if st.button("🧾 Lote por series", use_container_width=True, key="tpl_btn_lote_series"):
                    with st.expander("Pegar series", expanded=True):
                        st.text_area(
                            "Series (una por línea)",
                            value=st.session_state.get("tpl_series_text", ""),
                            height=130,
                            key="tpl_series_text",
                            placeholder="ABC123\nDEF456\nGHI789",
                        )
                        cta1, cta2 = st.columns([1.3, 1.7])
                        with cta1:
                            if st.button("✅ Generar mensaje", use_container_width=True, key="tpl_btn_gen_series"):
                                self._chat_send_template(self._tpl_build_lote_series())
                        with cta2:
                            st.caption("LAIA recibirá el lote en un solo mensaje.")

            with b4:
                if st.button("🧹 Limpiar", use_container_width=True, key="tpl_btn_clear"):
                    st.session_state["tpl_marca"] = ""
                    st.session_state["tpl_modelo"] = ""
                    st.session_state["tpl_guia"] = ""
                    st.session_state["tpl_series_text"] = ""
                    st.rerun()

    def _tpl_build_recibi_laptops(self) -> str:
        cant = int(st.session_state.get("tpl_cantidad", 1) or 1)
        marca = (st.session_state.get("tpl_marca") or "N/A").strip()
        modelo = (st.session_state.get("tpl_modelo") or "N/A").strip()
        origen = (st.session_state.get("tpl_origen") or "N/A").strip()
        destino = (st.session_state.get("tpl_destino") or "N/A").strip()
        return f"Recibido: {cant} laptops {marca} {modelo} desde {origen} hacia {destino}"

    def _tpl_build_envie_equipos(self) -> str:
        cant = int(st.session_state.get("tpl_cantidad", 1) or 1)
        equipo = (st.session_state.get("tpl_equipo") or "equipos").strip()
        destino = (st.session_state.get("tpl_destino") or "N/A").strip()
        guia = (st.session_state.get("tpl_guia") or "N/A").strip()
        return f"Enviado: {cant} {equipo} a {destino} guía {guia}"

    def _tpl_build_lote_series(self) -> str:
        equipo = (st.session_state.get("tpl_equipo") or "N/A").strip()
        marca = (st.session_state.get("tpl_marca") or "N/A").strip()
        modelo = (st.session_state.get("tpl_modelo") or "N/A").strip()
        origen = (st.session_state.get("tpl_origen") or "N/A").strip()
        destino = (st.session_state.get("tpl_destino") or "N/A").strip()
        guia = (st.session_state.get("tpl_guia") or "N/A").strip()

        series = [s.strip() for s in (st.session_state.get("tpl_series_text") or "").splitlines() if s.strip()]
        series_block = "\n".join(series) if series else "(sin series)"

        return (
            "Registrar lote:\n"
            f"- equipo: {equipo}\n"
            f"- marca: {marca}\n"
            f"- modelo: {modelo}\n"
            f"- tipo: {st.session_state.get('tpl_tipo', 'recibido')}\n"
            f"- origen: {origen}\n"
            f"- destino: {destino}\n"
            f"- guia: {guia}\n"
            "series:\n"
            f"{series_block}"
        )

    def _chat_send_template(self, prompt: str):
        st.session_state["chat_prefill"] = prompt
        st.session_state["chat_fire"] = True
        st.toast("Plantilla lista ✅ (enviando a LAIA…)", icon="⚡")
        st.rerun()

    # ---------------------------
    # Main render (CORREGIDO: sin FÁCIL/PRO)
    # ---------------------------
    def render(self):
        self._inject_micro_style()
        self._render_floating_logo()

        # ✅ Sidebar SOLO con el toggle
        with st.sidebar:
            st.markdown("## ⚙️ Panel")
            st.toggle(
                "🛡️ Bloquear guardado riesgoso",
                value=bool(st.session_state.get("confirm_risky_save", False)),
                help="Evita guardar si hay 'Enviado sin guía/destino' hasta que se corrija.",
                key="ui_lock_risky",
            )
        st.session_state["confirm_risky_save"] = bool(st.session_state.get("ui_lock_risky", False))

        self._render_header()

        # ✅ Plantillas SIEMPRE visibles
        self._render_plantillas_conversacionales()

        # ✅ Chat (único flujo principal)
        self._render_chat()

        if st.session_state.draft:
            self._mostrar_borrador()

    # ---------------------------
    # Chat area
    # ---------------------------
    def _render_chat(self):
        with st.container(border=True):
            st.markdown("#### 💬 Chat Auditor")
            st.caption("Escribe en lenguaje natural lo que llegó o lo que enviaste. LAIA lo audita y arma el borrador.")

            for m in st.session_state.messages:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])

            # ✅ Si viene una plantilla, dispara como si user la escribió
            if st.session_state.get("chat_fire") and st.session_state.get("chat_prefill"):
                prompt = st.session_state.get("chat_prefill", "")
                st.session_state["chat_fire"] = False
                st.session_state["chat_prefill"] = ""
                self._procesar_mensaje(prompt)
                st.rerun()

            if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
                self._procesar_mensaje(prompt)

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

                res_json = resultado.get("json_response", {}) or {}
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

    # ---------------------------
    # Draft table
    # ---------------------------
    def _mostrar_borrador(self):
        st.markdown("---")

        st.session_state.draft = self.stock_calc.aplicar_reglas_obsolescencia(st.session_state.draft)

        resumen, errores, _df_valid = self._validate_draft(st.session_state.draft)

        # Vista operativa arriba
        try:
            df_ops = pd.DataFrame(st.session_state.draft).fillna("N/A")
            self._render_vista_operativa(df_ops, resumen, errores)
        except Exception:
            pass

        with st.container(border=True):
            top1, top2, top3 = st.columns([2.2, 1, 1], vertical_alignment="center")
            with top1:
                st.markdown("#### 📊 Borrador de Movimientos")
                st.caption("Revisa, ajusta si hace falta y guarda.")
            with top2:
                st.metric("Items", len(st.session_state.draft))
            with top3:
                if resumen["bad"] > 0:
                    st.error(f"Críticos: {resumen['bad']}")
                elif resumen["warn"] > 0:
                    st.warning(f"Revisar: {resumen['warn']}")
                else:
                    st.success(f"OK: {resumen['ok']}")

        with st.container(border=True):
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
                key="editor_v13",
                hide_index=True
            )

            if not df_editor.equals(edited_df):
                st.session_state.draft = edited_df.to_dict("records")
                st.session_state.status = "QUESTION"
                st.rerun()

            self._mostrar_botones_accion(resumen)

    def _mostrar_botones_accion(self, resumen):
        c1, c2, c3 = st.columns([1.2, 3.2, 1.6], vertical_alignment="center")

        with c1:
            forzar = st.checkbox("🔓 Forzar", help="Permite guardar aunque LAIA marque QUESTION.", key="chk_forzar_v13")

        risky = (resumen.get("bad", 0) > 0)
        if st.session_state.get("confirm_risky_save", False) and risky:
            allow_save = False
        else:
            allow_save = (st.session_state.status == "READY") or forzar or (not risky)

        with c2:
            if allow_save:
                if st.button("🚀 GUARDAR Y ENVIAR AL ROBOT", type="primary", use_container_width=True, key="btn_save_v13"):
                    self._guardar_borrador()
            else:
                st.button("🚀 GUARDAR (REVISA CRÍTICOS)", disabled=True, use_container_width=True, key="btn_save_blocked_v13")

        with c3:
            if st.button("🗑️ Descartar Todo", use_container_width=True, key="btn_discard_v13"):
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
