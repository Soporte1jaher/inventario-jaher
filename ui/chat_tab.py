import streamlit as st
import pandas as pd
import time
import datetime

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler
from modules.stock_calculator import StockCalculator


class ChatTab:
    """Chat Auditor - UI Corporativa + Modo Usuario Final (Fácil) + Modo Pro"""

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

        # UX state
        st.session_state.setdefault("ui_mode", "FÁCIL")  # FÁCIL / PRO
        st.session_state.setdefault("confirm_risky_save", False)
        st.session_state.setdefault("quick_origin", "")
        st.session_state.setdefault("quick_destino", "")
        st.session_state.setdefault("quick_tipo", "recibido")

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

              /* Chips */
              .chip-row { display:flex; gap:10px; flex-wrap:wrap; }
              .chip {
                display:inline-block; padding:8px 12px; border-radius:999px;
                border:1px solid rgba(255,255,255,0.12);
                background: rgba(255,255,255,0.03);
                cursor:pointer; user-select:none;
              }
              .chip:hover{ background: rgba(255,255,255,0.06); }

              /* Badges */
              .badge-ok{ color:#00e676; font-weight:900; }
              .badge-warn{ color:#ffb300; font-weight:900; }
              .badge-bad{ color:#ff5252; font-weight:900; }
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
        """
        Saca sedes del histórico para autocompletar origen/destino.
        (No rompe si falla)
        """
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
        """
        Devuelve:
        - resumen (ok/warn/bad)
        - errores (lista)
        - df con columna 'validacion'
        """
        if not draft_items:
            return {"ok": 0, "warn": 0, "bad": 0}, [], pd.DataFrame()

        df = pd.DataFrame(draft_items).copy()

        # asegurar columnas
        for c in ["tipo", "equipo", "marca", "modelo", "serie", "origen", "destino", "guia", "cantidad", "estado"]:
            if c not in df.columns:
                df[c] = ""

        # normalizar
        for c in ["tipo", "equipo", "marca", "modelo", "serie", "origen", "destino", "guia", "estado"]:
            df[c] = df[c].astype(str).fillna("").str.strip()

        errors = []
        status_col = []

        ok = warn = bad = 0

        for _, r in df.iterrows():
            t = r["tipo"].lower()
            serie = r["serie"]
            guia = r["guia"]
            destino = r["destino"]
            origen = r["origen"]
            equipo = r["equipo"]

            # reglas de riesgo simples
            row_issues = []

            if equipo.strip() in ["", "N/A", "n/a"]:
                row_issues.append("Falta equipo")

            # Si es enviado: guía + destino casi obligatorios
            if "envi" in t:
                if guia.strip() in ["", "N/A", "n/a"]:
                    row_issues.append("Enviado sin guía")
                if destino.strip() in ["", "N/A", "n/a"]:
                    row_issues.append("Enviado sin destino")

            # Si es recibido: origen recomendado
            if "recib" in t:
                if origen.strip() in ["", "N/A", "n/a"]:
                    row_issues.append("Recibido sin origen")

            # serie recomendada para cómputo (si no hay serie, al menos modelo)
            if serie.strip() in ["", "N/A", "n/a"]:
                if str(r["modelo"]).strip() in ["", "N/A", "n/a"]:
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

    # ---------------------------
    # Main render
    # ---------------------------
    def render(self):
        self._inject_micro_style()
        self._render_floating_logo()

        # Sidebar: modo usuario final
        with st.sidebar:
            st.markdown("## ⚙️ Panel")
            st.session_state.ui_mode = st.radio(
                "Modo de uso",
                ["FÁCIL", "PRO"],
                index=0 if st.session_state.ui_mode == "FÁCIL" else 1,
                help="FÁCIL: guiado para usuarios finales. PRO: chat libre.",
                key="ui_mode_radio",
            )
            st.session_state.confirm_risky_save = st.toggle(
                "🛡️ Bloquear guardado riesgoso",
                value=bool(st.session_state.confirm_risky_save),
                help="Evita guardar si hay 'Enviado sin guía/destino' hasta que se corrija.",
                key="ui_lock_risky",
            )

        self._render_header()

        # Zona principal: modo fácil
        if st.session_state.ui_mode == "FÁCIL":
            self._render_easy_mode()

        # Chat pro (siempre disponible)
        self._render_chat()

        # Borrador / tabla
        if st.session_state.draft:
            self._mostrar_borrador()

    # ---------------------------
    # Easy Mode (formularios + chips)
    # ---------------------------
    def _render_easy_mode(self):
        with st.container(border=True):
            st.markdown("#### 🧭 Modo Fácil (Usuario Final)")
            st.caption("Usa los botones rápidos o completa un formulario. Ideal si no sabes qué escribir.")

            sedes = self._get_sedes_sugeridas()

            c1, c2, c3 = st.columns([1.4, 1.4, 1.2], vertical_alignment="center")
            with c1:
                st.session_state.quick_tipo = st.selectbox(
                    "Tipo",
                    ["recibido", "enviado"],
                    index=0 if st.session_state.quick_tipo == "recibido" else 1,
                    key="easy_tipo",
                )
            with c2:
                st.session_state.quick_origin = st.selectbox(
                    "Origen (sugerido)",
                    options=[""] + sedes,
                    index=0,
                    key="easy_origen",
                )
            with c3:
                st.session_state.quick_destino = st.selectbox(
                    "Destino (sugerido)",
                    options=[""] + sedes,
                    index=0,
                    key="easy_destino",
                )

            st.markdown("**Acciones rápidas**")
            b1, b2, b3, b4, b5 = st.columns(5)
            with b1:
                if st.button("➕ Registrar 1 equipo", use_container_width=True, key="easy_btn_one"):
                    self._easy_form_one_item()
            with b2:
                if st.button("📦 Periféricos x cantidad", use_container_width=True, key="easy_btn_peri"):
                    self._easy_form_perifericos()
            with b3:
                if st.button("🧾 Lote por series", use_container_width=True, key="easy_btn_lote"):
                    self._easy_form_lote_series()
            with b4:
                if st.button("🧹 Limpiar borrador", use_container_width=True, key="easy_btn_clear_draft"):
                    st.session_state.draft = []
                    st.session_state.status = "NEW"
                    st.rerun()
            with b5:
                if st.button("📋 Copiar resumen", use_container_width=True, key="easy_btn_copy"):
                    txt = self._build_resume_text()
                    st.code(txt, language="text")

    def _easy_form_one_item(self):
        with st.container(border=True):
            st.markdown("##### ➕ Registrar 1 equipo (guiado)")
            c1, c2, c3 = st.columns(3)
            with c1:
                equipo = st.text_input("Equipo (Laptop/CPU/Teclado/etc.)", key="f1_equipo")
                marca = st.text_input("Marca", key="f1_marca")
            with c2:
                modelo = st.text_input("Modelo", key="f1_modelo")
                serie = st.text_input("Serie (si aplica)", key="f1_serie")
            with c3:
                cantidad = st.number_input("Cantidad", min_value=1, value=1, step=1, key="f1_cant")
                guia = st.text_input("Guía (si es enviado)", key="f1_guia")

            if st.button("✅ Agregar al borrador", type="primary", use_container_width=True, key="f1_add"):
                item = {
                    "tipo": st.session_state.quick_tipo,
                    "origen": st.session_state.quick_origin or "N/A",
                    "destino": st.session_state.quick_destino or "N/A",
                    "equipo": equipo or "N/A",
                    "marca": marca or "N/A",
                    "modelo": modelo or "N/A",
                    "serie": serie or "N/A",
                    "cantidad": int(cantidad),
                    "guia": guia or "N/A",
                    "estado": "BUENO",
                    "categoria_item": "N/A",
                    "reporte": "N/A",
                    "ram": "N/A",
                    "disco": "N/A",
                    "procesador": "N/A",
                }
                st.session_state.draft.append(item)
                st.session_state.status = "QUESTION"  # que valide el bloque
                st.success("Agregado ✅")
                st.rerun()

    def _easy_form_perifericos(self):
        with st.container(border=True):
            st.markdown("##### 📦 Periféricos por cantidad (rápido)")
            c1, c2, c3 = st.columns(3)
            with c1:
                equipo = st.selectbox("Periférico", ["TECLADO", "MOUSE", "MONITOR", "CARGADOR", "CABLE"], key="fp_equipo")
            with c2:
                marca = st.text_input("Marca (opcional)", key="fp_marca")
            with c3:
                cantidad = st.number_input("Cantidad", min_value=1, value=1, step=1, key="fp_cant")

            if st.button("✅ Agregar periférico", type="primary", use_container_width=True, key="fp_add"):
                item = {
                    "tipo": st.session_state.quick_tipo,
                    "origen": st.session_state.quick_origin or "N/A",
                    "destino": st.session_state.quick_destino or "N/A",
                    "equipo": equipo,
                    "marca": marca or "N/A",
                    "modelo": "N/A",
                    "serie": "N/A",
                    "cantidad": int(cantidad),
                    "guia": "N/A",
                    "estado": "BUENO",
                    "categoria_item": "Periferico",
                    "reporte": "N/A",
                    "ram": "N/A",
                    "disco": "N/A",
                    "procesador": "N/A",
                }
                st.session_state.draft.append(item)
                st.session_state.status = "QUESTION"
                st.success("Agregado ✅")
                st.rerun()

    def _easy_form_lote_series(self):
        with st.container(border=True):
            st.markdown("##### 🧾 Lote por series (pega varias)")
            st.caption("Pega series separadas por salto de línea. (Una serie por línea)")
            equipo = st.text_input("Equipo (CPU/Laptop/etc.)", key="fl_equipo")
            marca = st.text_input("Marca", key="fl_marca")
            modelo = st.text_input("Modelo", key="fl_modelo")
            guia = st.text_input("Guía (si es enviado)", key="fl_guia")
            series_text = st.text_area("Series (una por línea)", key="fl_series", height=140)

            if st.button("✅ Agregar lote", type="primary", use_container_width=True, key="fl_add"):
                series = [s.strip() for s in series_text.splitlines() if s.strip()]
                if not series:
                    st.warning("Pega al menos 1 serie.")
                    return

                for s in series:
                    st.session_state.draft.append({
                        "tipo": st.session_state.quick_tipo,
                        "origen": st.session_state.quick_origin or "N/A",
                        "destino": st.session_state.quick_destino or "N/A",
                        "equipo": equipo or "N/A",
                        "marca": marca or "N/A",
                        "modelo": modelo or "N/A",
                        "serie": s,
                        "cantidad": 1,
                        "guia": guia or "N/A",
                        "estado": "BUENO",
                        "categoria_item": "Computo",
                        "reporte": "N/A",
                        "ram": "N/A",
                        "disco": "N/A",
                        "procesador": "N/A",
                    })

                st.session_state.status = "QUESTION"
                st.success(f"Lote agregado ✅ ({len(series)} items)")
                st.rerun()

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

        # aplica reglas obsolescencia
        st.session_state.draft = self.stock_calc.aplicar_reglas_obsolescencia(st.session_state.draft)

        # validar
        resumen, errores, df_valid = self._validate_draft(st.session_state.draft)

        with st.container(border=True):
            top1, top2, top3 = st.columns([2.2, 1, 1], vertical_alignment="center")
            with top1:
                st.markdown("#### 📊 Borrador de Movimientos")
                st.caption("Revisa, ajusta si hace falta y guarda.")
            with top2:
                st.metric("Items", len(st.session_state.draft))
            with top3:
                # semáforo
                if resumen["bad"] > 0:
                    st.error(f"Críticos: {resumen['bad']}")
                elif resumen["warn"] > 0:
                    st.warning(f"Revisar: {resumen['warn']}")
                else:
                    st.success(f"OK: {resumen['ok']}")

            if errores:
                with st.expander("⚠️ Problemas detectados (clic para ver)", expanded=False):
                    for e in errores[:25]:
                        st.write(f"- {e}")

        # editor
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
        if st.session_state.confirm_risky_save and risky:
            # bloquea si hay críticos
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

    def _build_resume_text(self):
        """
        Resumen para copiar/WhatsApp.
        """
        if not st.session_state.draft:
            return "Sin borrador."
        df = pd.DataFrame(st.session_state.draft).fillna("N/A")
        n = len(df)
        tipos = ", ".join(sorted(df.get("tipo", pd.Series(["N/A"])).astype(str).str.lower().unique().tolist()))
        destinos = ", ".join(sorted(df.get("destino", pd.Series(["N/A"])).astype(str).str.title().unique().tolist())[:8])
        equipos = ", ".join(sorted(df.get("equipo", pd.Series(["N/A"])).astype(str).str.title().unique().tolist())[:8])
        return (
            f"LAIA - Resumen\n"
            f"- Items: {n}\n"
            f"- Tipos: {tipos}\n"
            f"- Equipos: {equipos}\n"
            f"- Destinos: {destinos}\n"
        )

    def _limpiar_sesion(self):
        st.session_state.draft = []
        st.session_state.messages = []
        st.session_state.status = "NEW"
        st.rerun()
