import streamlit as st
import pandas as pd
import re
import datetime

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler


class CleaningTab:
    """
    🧹 Limpieza del Historial (FÁCIL para usuario final) — v2 UX+

    ✅ Añadido:
    - ✅ Por SERIE (lo que te faltaba)
    - Por GUÍA, MARCA, EQUIPO, MODELO (rápidos)
    - Búsqueda rápida tipo Google (arriba) -> detecta serie/guia o hace texto
    - UI más clara: chips/atajos + textos simples
    - Ordenamiento (más nuevos primero / más antiguos)
    - Resumen de riesgo (borrado masivo)
    - “Seleccionar por reglas”: todos / invert / limpiar
    - Preview más bonito + top info
    """

    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()

        self.base_cols = [
            "idx",
            "fecha_registro",
            "fecha_registro_dt",
            "tipo",
            "categoria_item",
            "equipo",
            "marca",
            "modelo",
            "serie",
            "cantidad",
            "estado",
            "origen",
            "destino",
            "guia",
            "reporte",
        ]

        # state
        st.session_state.setdefault("cln_df", pd.DataFrame())
        st.session_state.setdefault("cln_results", pd.DataFrame())
        st.session_state.setdefault("cln_selected_idx", set())
        st.session_state.setdefault("cln_last_query", "")
        st.session_state.setdefault("cln_last_order", None)

        # UX state
        st.session_state.setdefault("cln_flow_step", 1)
        st.session_state.setdefault("cln_filter_type", "Recomendado (Automático)")

        st.session_state.setdefault("cln_text_search", "")
        st.session_state.setdefault("cln_date_from", None)
        st.session_state.setdefault("cln_date_to", None)
        st.session_state.setdefault("cln_pick_field", "Cualquier campo")
        st.session_state.setdefault("cln_pick_value", "")
        st.session_state.setdefault("cln_massive_lock", True)

        st.session_state.setdefault("cln_sort", "Más nuevos primero")
        st.session_state.setdefault("cln_quick_search", "")

    # =========================================================
    # UI
    # =========================================================
    def render(self):
        self._inject_css()

        with st.container(border=True):
            st.markdown("## 🧹 Limpieza del Historial (Fácil)")
            st.caption("Hecho para usuarios finales: escribe o elige una opción, revisa y confirma.")

        # orden enviada
        if st.session_state.cln_last_order:
            with st.container(border=True):
                st.success("✅ Orden enviada. El robot debe procesarla y actualizar historico.json.")
                c1, c2 = st.columns([1.2, 3.8], vertical_alignment="center")
                with c1:
                    if st.button("🔄 Refrescar", key="cln_btn_refresh_after_send", use_container_width=True):
                        st.session_state.cln_last_order = None
                        st.rerun()
                with c2:
                    st.caption("Si el robot aún no corrió, verás lo mismo. Refresca luego de que procese.")
                with st.expander("📦 Ver orden enviada (soporte)", expanded=False):
                    st.json(st.session_state.cln_last_order)

        # cargar historial
        hist = self.github.obtener_historico()
        if hist is None:
            st.error("❌ No pude leer el historial (GitHub). Revisa tu token/secret.")
            return
        if len(hist) == 0:
            st.info("📭 El historial está vacío.")
            return

        df = self._safe_hist_to_df(hist)
        df = self._normalize(df)
        st.session_state.cln_df = df

        # Búsqueda rápida (arriba) — para usuario final
        self._quick_search_bar(df)

        # wizard
        self._render_steps_header()

        step = st.session_state.cln_flow_step
        if step == 1:
            self._step_1_choose(df)
        elif step == 2:
            self._step_2_review()
        else:
            self._step_3_confirm_and_send()

    def _inject_css(self):
        st.markdown(
            """
            <style>
              .cln-chip {
                display:inline-block;
                padding:6px 10px;
                border-radius:999px;
                border:1px solid rgba(255,255,255,.12);
                background: rgba(255,255,255,.04);
                margin-right:8px;
                margin-bottom:8px;
                font-size: 13px;
              }
              .cln-muted { opacity: .8; }
              .cln-title { font-weight: 800; letter-spacing: .2px; }
            </style>
            """,
            unsafe_allow_html=True
        )

    def _render_steps_header(self):
        with st.container(border=True):
            s1, s2, s3 = st.columns(3)
            step = st.session_state.cln_flow_step

            def pill(label, active):
                if active:
                    st.markdown(f"### ✅ {label}")
                else:
                    st.markdown(f"### {label}")

            with s1:
                pill("1) Elegir", step == 1)
            with s2:
                pill("2) Revisar", step == 2)
            with s3:
                pill("3) Confirmar", step == 3)

    # =========================================================
    # QUICK SEARCH (tipo Google)
    # =========================================================
    def _quick_search_bar(self, df: pd.DataFrame):
        with st.container(border=True):
            st.markdown("### 🔎 Búsqueda rápida")
            st.caption("Escribe una serie, guía, marca, equipo, destino… y te saco resultados al toque.")

            q = st.text_input(
                "Buscar y limpiar",
                placeholder="Ej: 5CD1234 (serie) | guia 0987 | HP | babahoyo | monitor | obsoleto ...",
                key="cln_quick_search_input",
            ).strip()

            c1, c2, c3 = st.columns([1.4, 1.4, 2.2], vertical_alignment="center")
            with c1:
                if st.button("🔎 Buscar", key="cln_btn_quick_search", use_container_width=True, type="secondary"):
                    if q:
                        field, value = self._detect_quick_intent(q)
                        res = self._search(df, field, value)
                        st.session_state.cln_last_query = f"RÁPIDO: {field}={value}"
                        st.session_state.cln_results = self._apply_sort(res)
                        st.session_state.cln_selected_idx = set()
                        if st.session_state.cln_results.empty:
                            st.warning("❌ No encontré nada con eso.")
                            return
                        st.session_state.cln_flow_step = 2
                        st.rerun()
                    else:
                        st.warning("Escribe algo para buscar.")
            with c2:
                if st.button("🧹 Limpiar", key="cln_btn_quick_clear", use_container_width=True):
                    self._reset(keep_order=True)
                    st.rerun()
            with c3:
                st.session_state.cln_sort = st.selectbox(
                    "Ordenar resultados",
                    ["Más nuevos primero", "Más antiguos primero"],
                    index=0,
                    key="cln_sel_sort",
                )

            # chips guía
            st.markdown(
                """
                <span class="cln-chip">✅ Tip: si pegas SOLO un número o código, lo tomo como <b>serie</b></span>
                <span class="cln-chip">✅ Tip: escribe <b>guia 123</b> o <b>serie 5CD...</b></span>
                <span class="cln-chip">✅ Tip: escribe <b>destino babahoyo</b> o <b>origen sid</b></span>
                """,
                unsafe_allow_html=True
            )

    def _detect_quick_intent(self, q: str):
        ql = q.lower().strip()

        # patrones directos
        m = re.search(r"\b(serie|serial)\s*[:#-]?\s*([a-z0-9\-_/]+)\b", ql)
        if m:
            return "serie", m.group(2).strip()

        m = re.search(r"\b(guia|guía)\s*[:#-]?\s*([a-z0-9\-_/]+)\b", ql)
        if m:
            return "guia", m.group(2).strip()

        for k in ["marca", "equipo", "modelo", "destino", "origen", "tipo", "estado"]:
            m = re.search(rf"\b({k})\s*[:#-]?\s*([a-z0-9\-_/]+)\b", ql)
            if m:
                return k, m.group(2).strip()

        # si parece código/serie (sin espacios, largo razonable)
        if re.fullmatch(r"[a-z0-9\-_/]{4,}", ql) and " " not in ql:
            return "serie", ql

        return "texto", ql

    # =========================================================
    # STEP 1
    # =========================================================
    def _step_1_choose(self, df: pd.DataFrame):
        with st.container(border=True):
            st.markdown("### 1) ¿Qué quieres limpiar?")

            opciones = [
                "Recomendado (Automático)",
                "Por SERIE (exacta / contiene)",
                "Por GUÍA (exacta / contiene)",
                "Por MARCA",
                "Por EQUIPO",
                "Por MODELO",
                "Registros vacíos / basura (N/A)",
                "Duplicados (repetidos)",
                "Por fecha (un día)",
                "Por rango de fechas",
                "Por sede (origen / destino)",
                "Por tipo (Recibido / Enviado)",
                "Por estado (Bueno / Dañado / Obsoleto / etc.)",
                "Por texto (buscar en todo)",
            ]

            st.session_state.cln_filter_type = st.selectbox(
                "Elige una opción",
                opciones,
                index=0,
                key="cln_sel_filter_type_user",
                help="Si no sabes, usa: Recomendado (Automático).",
            )

            st.session_state.cln_massive_lock = st.toggle(
                "🛡️ Bloquear borrados masivos (recomendado)",
                value=bool(st.session_state.cln_massive_lock),
                help="Evita borrar mucho por error. Puedes desactivarlo si sabes lo que haces.",
                key="cln_tgl_massive_lock",
            )

        ft = st.session_state.cln_filter_type

        with st.container(border=True):
            st.markdown("### Configuración")

            # atajos pro
            st.markdown(
                """
                <span class="cln-chip">🧼 Vacíos (basura)</span>
                <span class="cln-chip">🔁 Duplicados</span>
                <span class="cln-chip">📅 Por fechas</span>
                <span class="cln-chip">🏷️ Por serie / guía</span>
                """,
                unsafe_allow_html=True
            )

            if ft == "Recomendado (Automático)":
                st.caption("Detecta automáticamente: vacíos (N/A), basura común y registros raros.")
                st.session_state.cln_text_search = ""

            elif ft == "Por SERIE (exacta / contiene)":
                st.session_state.cln_pick_value = st.text_input(
                    "Escribe la serie",
                    placeholder="Ej: 5CD123ABC",
                    key="cln_txt_serie",
                ).strip()

            elif ft == "Por GUÍA (exacta / contiene)":
                st.session_state.cln_pick_value = st.text_input(
                    "Escribe la guía",
                    placeholder="Ej: 098765",
                    key="cln_txt_guia",
                ).strip()

            elif ft == "Por MARCA":
                marcas = self._unique_values(df, ["marca"], limit=200)
                st.session_state.cln_pick_value = st.selectbox("Marca", ["(Escribir)"] + marcas, key="cln_sel_marca")
                if st.session_state.cln_pick_value == "(Escribir)":
                    st.session_state.cln_pick_value = st.text_input("Escribe la marca", key="cln_txt_marca_manual").strip()

            elif ft == "Por EQUIPO":
                equipos = self._unique_values(df, ["equipo"], limit=250)
                st.session_state.cln_pick_value = st.selectbox("Equipo", ["(Escribir)"] + equipos, key="cln_sel_equipo")
                if st.session_state.cln_pick_value == "(Escribir)":
                    st.session_state.cln_pick_value = st.text_input("Escribe el equipo", key="cln_txt_equipo_manual").strip()

            elif ft == "Por MODELO":
                modelos = self._unique_values(df, ["modelo"], limit=250)
                st.session_state.cln_pick_value = st.selectbox("Modelo", ["(Escribir)"] + modelos, key="cln_sel_modelo")
                if st.session_state.cln_pick_value == "(Escribir)":
                    st.session_state.cln_pick_value = st.text_input("Escribe el modelo", key="cln_txt_modelo_manual").strip()

            elif ft == "Registros vacíos / basura (N/A)":
                st.caption("Encuentra filas que tienen casi todo N/A (filas fantasma).")

            elif ft == "Duplicados (repetidos)":
                st.caption("Detecta registros repetidos por firma (fecha+serie+guia+equipo+marca+origen+destino+tipo).")

            elif ft == "Por fecha (un día)":
                d = st.date_input("Selecciona la fecha", value=datetime.date.today(), key="cln_date_one_day")
                st.session_state.cln_date_from = d
                st.session_state.cln_date_to = d

            elif ft == "Por rango de fechas":
                c1, c2 = st.columns(2)
                with c1:
                    d1 = st.date_input("Desde", value=datetime.date.today() - datetime.timedelta(days=7), key="cln_date_from_user")
                with c2:
                    d2 = st.date_input("Hasta", value=datetime.date.today(), key="cln_date_to_user")
                st.session_state.cln_date_from = d1
                st.session_state.cln_date_to = d2

            elif ft == "Por sede (origen / destino)":
                sedes = self._unique_values(df, ["origen", "destino"], limit=250)
                st.session_state.cln_pick_field = st.radio("¿Dónde buscar?", ["Origen", "Destino"], horizontal=True, key="cln_radio_origen_destino")
                st.session_state.cln_pick_value = st.selectbox("Selecciona la sede", options=["(Escribir)"] + sedes, key="cln_sel_sede")
                if st.session_state.cln_pick_value == "(Escribir)":
                    st.session_state.cln_pick_value = st.text_input("Escribe la sede", key="cln_txt_sede_manual").strip()

            elif ft == "Por tipo (Recibido / Enviado)":
                st.session_state.cln_pick_value = st.selectbox("Tipo", ["recibido", "enviado"], key="cln_sel_tipo_user")

            elif ft == "Por estado (Bueno / Dañado / Obsoleto / etc.)":
                estados = self._unique_values(df, ["estado"], limit=120)
                st.session_state.cln_pick_value = st.selectbox("Estado", options=["(Escribir)"] + estados, key="cln_sel_estado_user")
                if st.session_state.cln_pick_value == "(Escribir)":
                    st.session_state.cln_pick_value = st.text_input("Escribe el estado", key="cln_txt_estado_manual").strip()

            elif ft == "Por texto (buscar en todo)":
                st.session_state.cln_text_search = st.text_input(
                    "Escribe lo que quieres buscar y eliminar",
                    placeholder="Ej: puyo / hp / teclado / obsoleto / sid ...",
                    key="cln_txt_search_all",
                ).strip().lower()

        with st.container(border=True):
            c1, c2 = st.columns([1.4, 2.6], vertical_alignment="center")
            with c1:
                if st.button("🔎 Buscar registros", key="cln_btn_generate_results", type="primary", use_container_width=True):
                    self._generate_results_user(df)
            with c2:
                st.caption("Luego podrás revisar la lista, seleccionar y confirmar.")

    def _generate_results_user(self, df: pd.DataFrame):
        ft = st.session_state.cln_filter_type
        q = ft

        if ft == "Recomendado (Automático)":
            results = self._recommended_cleanup(df)
            q = "AUTO: recomendación"

        elif ft == "Registros vacíos / basura (N/A)":
            results = self._search(df, "vacios", "1")
            q = "VACIOS"

        elif ft == "Duplicados (repetidos)":
            results = self._find_duplicates(df)
            q = "DUPLICADOS"

        elif ft == "Por fecha (un día)":
            d = st.session_state.cln_date_from
            q = f"FECHA: {d}"
            results = self._search_by_date_range(df, d, d)

        elif ft == "Por rango de fechas":
            d1 = st.session_state.cln_date_from
            d2 = st.session_state.cln_date_to
            q = f"RANGO: {d1} -> {d2}"
            results = self._search_by_date_range(df, d1, d2)

        elif ft == "Por sede (origen / destino)":
            sede = (st.session_state.cln_pick_value or "").strip().lower()
            campo = "origen" if st.session_state.cln_pick_field == "Origen" else "destino"
            q = f"{campo.upper()}: {sede}"
            results = self._search(df, campo, sede)

        elif ft == "Por tipo (Recibido / Enviado)":
            v = (st.session_state.cln_pick_value or "").strip().lower()
            q = f"TIPO: {v}"
            results = self._search(df, "tipo", v)

        elif ft == "Por estado (Bueno / Dañado / Obsoleto / etc.)":
            v = (st.session_state.cln_pick_value or "").strip().lower()
            q = f"ESTADO: {v}"
            results = self._search(df, "estado", v)

        elif ft == "Por SERIE (exacta / contiene)":
            v = (st.session_state.cln_pick_value or "").strip().lower()
            q = f"SERIE: {v}"
            results = self._search(df, "serie", v)

        elif ft == "Por GUÍA (exacta / contiene)":
            v = (st.session_state.cln_pick_value or "").strip().lower()
            q = f"GUIA: {v}"
            results = self._search(df, "guia", v)

        elif ft == "Por MARCA":
            v = (st.session_state.cln_pick_value or "").strip().lower()
            q = f"MARCA: {v}"
            results = self._search(df, "marca", v)

        elif ft == "Por EQUIPO":
            v = (st.session_state.cln_pick_value or "").strip().lower()
            q = f"EQUIPO: {v}"
            results = self._search(df, "equipo", v)

        elif ft == "Por MODELO":
            v = (st.session_state.cln_pick_value or "").strip().lower()
            q = f"MODELO: {v}"
            results = self._search(df, "modelo", v)

        else:  # Por texto (buscar en todo)
            v = (st.session_state.cln_text_search or "").strip().lower()
            q = f"TEXTO: {v}"
            results = self._search(df, "texto", v)

        results = self._apply_sort(results)

        st.session_state.cln_last_query = q
        st.session_state.cln_results = results
        st.session_state.cln_selected_idx = set()

        if results.empty:
            st.warning("❌ No se encontraron registros con esa selección.")
            return

        st.session_state.cln_flow_step = 2
        st.rerun()

    def _apply_sort(self, dfres: pd.DataFrame):
        if dfres is None or dfres.empty:
            return dfres
        if "fecha_registro_dt" not in dfres.columns:
            return dfres
        if st.session_state.cln_sort == "Más antiguos primero":
            return dfres.sort_values("fecha_registro_dt", ascending=True)
        return dfres.sort_values("fecha_registro_dt", ascending=False)

    # =========================================================
    # STEP 2
    # =========================================================
    def _step_2_review(self):
        dfres = st.session_state.cln_results.copy()
        q = st.session_state.cln_last_query

        with st.container(border=True):
            st.markdown("### 2) Revisa y selecciona")
            st.caption(f"Filtro aplicado: **{q}**")

        if dfres is None or dfres.empty:
            st.warning("No hay resultados.")
            st.session_state.cln_flow_step = 1
            return

        with st.container(border=True):
            total = len(dfres)
            st.metric("Registros encontrados", total)
            if total >= 200:
                st.warning("⚠️ Son muchos registros. Revisa bien antes de borrar.")

        cols_pref = [c for c in [
            "idx", "fecha_registro", "tipo", "categoria_item", "equipo", "marca", "modelo", "serie",
            "cantidad", "estado", "origen", "destino", "guia", "reporte"
        ] if c in dfres.columns]

        view = dfres[cols_pref].copy()
        view.insert(0, "ELIMINAR", False)

        edited = st.data_editor(
            view,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            height=540,
            key="cln_editor_results_user_v2",
        )

        selected_idx = set(edited.loc[edited["ELIMINAR"] == True, "idx"].astype(int).tolist())
        st.session_state.cln_selected_idx = selected_idx

        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2], vertical_alignment="center")
            with c1:
                st.metric("Seleccionados", len(selected_idx))
            with c2:
                if st.button("✅ Todo", key="cln_btn_sel_all_user_v2", use_container_width=True):
                    st.session_state.cln_selected_idx = set(dfres["idx"].astype(int).tolist())
                    st.rerun()
            with c3:
                if st.button("🔁 Invertir", key="cln_btn_sel_inv_user_v2", use_container_width=True):
                    all_idx = set(dfres["idx"].astype(int).tolist())
                    st.session_state.cln_selected_idx = all_idx - set(st.session_state.cln_selected_idx)
                    st.rerun()
            with c4:
                if st.button("🧽 Limpiar", key="cln_btn_sel_clear_user_v2", use_container_width=True):
                    st.session_state.cln_selected_idx = set()
                    st.rerun()
            with c5:
                if st.button("⬅️ Volver", key="cln_btn_back_to_step1_v2", use_container_width=True):
                    st.session_state.cln_flow_step = 1
                    st.rerun()

        with st.container(border=True):
            disabled = len(st.session_state.cln_selected_idx) == 0
            if st.button("➡️ Continuar a Confirmación", key="cln_btn_go_step3_v2", type="primary", use_container_width=True, disabled=disabled):
                st.session_state.cln_flow_step = 3
                st.rerun()

    # =========================================================
    # STEP 3
    # =========================================================
    def _step_3_confirm_and_send(self):
        dfall = st.session_state.cln_df
        selected_idx = sorted(list(st.session_state.cln_selected_idx))

        with st.container(border=True):
            st.markdown("### 3) Confirmar y enviar")
            st.caption("Aquí es donde realmente se envía la orden al robot.")

        if not selected_idx:
            st.warning("No hay registros seleccionados.")
            st.session_state.cln_flow_step = 2
            return

        sub = dfall[dfall["idx"].isin(selected_idx)].copy()

        with st.container(border=True):
            st.markdown("#### Vista previa (lo que se eliminará)")
            sub_cols = [c for c in ["idx","fecha_registro","tipo","equipo","marca","modelo","serie","estado","origen","destino","guia"] if c in sub.columns]
            st.dataframe(sub[sub_cols].head(250), use_container_width=True, hide_index=True)

        with st.container(border=True):
            total = len(selected_idx)
            st.metric("Total a eliminar", total)

            warn_massive = total >= 200
            if warn_massive:
                st.warning("⚠️ Esto es un borrado masivo. Confirma con cuidado.")

            confirm = st.checkbox("✅ Sí, quiero eliminar estos registros", key="cln_chk_confirm_user_v2", value=False)

            confirm2 = True
            if st.session_state.cln_massive_lock and warn_massive:
                confirm2 = st.text_input(
                    "Para borrar masivo, escribe EXACTAMENTE: ELIMINAR",
                    key="cln_txt_confirm_massive_v2",
                    placeholder="ELIMINAR",
                ).strip().upper() == "ELIMINAR"

            c1, c2 = st.columns(2)
            with c1:
                if st.button("⬅️ Volver", key="cln_btn_back_step2_v2", use_container_width=True):
                    st.session_state.cln_flow_step = 2
                    st.rerun()

            disabled = (not confirm) or (not confirm2)
            with c2:
                if st.button("🔥 Enviar al robot", key="cln_btn_send_user_v2", type="primary", use_container_width=True, disabled=disabled):
                    self._send_delete_order_user()

    def _send_delete_order_user(self):
        dfall = st.session_state.cln_df
        selected_idx = sorted(list(st.session_state.cln_selected_idx))
        sub = dfall[dfall["idx"].isin(selected_idx)].copy()

        firmas = []
        for _, r in sub.iterrows():
            firmas.append({
                "idx": int(r.get("idx")),
                "serie": str(r.get("serie", "N/A")).strip(),
                "guia": str(r.get("guia", "N/A")).strip(),
                "fecha_registro": str(r.get("fecha_registro", "N/A")).strip(),
                "equipo": str(r.get("equipo", "N/A")).strip(),
                "marca": str(r.get("marca", "N/A")).strip(),
                "modelo": str(r.get("modelo", "N/A")).strip(),
                "origen": str(r.get("origen", "N/A")).strip(),
                "destino": str(r.get("destino", "N/A")).strip(),
                "tipo": str(r.get("tipo", "N/A")).strip(),
                "estado": str(r.get("estado", "N/A")).strip(),
            })

        orden = {
            "action": "delete",
            "source": "historico.json",
            "instruction": st.session_state.cln_last_query,
            "count": len(firmas),
            "indices": [int(x) for x in selected_idx],
            "matches": firmas,
            "accion": "borrar_por_indices",
            "idx_list": [int(x) for x in selected_idx],
        }

        ok = self.github.enviar_orden_limpieza(orden)
        if ok:
            st.session_state.cln_last_order = orden
            st.success("✅ Orden enviada. Refresca cuando el robot procese.")
            self._reset(keep_order=True)
            st.session_state.cln_flow_step = 1
            st.rerun()
        else:
            st.error("❌ No se pudo enviar la orden. Revisa formato esperado por el robot.")
            st.json(orden)

    # =========================================================
    # Recommended / extras
    # =========================================================
    def _recommended_cleanup(self, df: pd.DataFrame):
        vacios = self._search(df, "vacios", "1")
        na_tipo = self._search(df, "tipo", "n/a")
        na_estado = self._search(df, "estado", "n/a")
        na_equipo = self._search(df, "equipo", "n/a")

        out = pd.concat([vacios, na_tipo, na_estado, na_equipo], ignore_index=True) if not df.empty else pd.DataFrame()
        if out.empty:
            return out

        out = out.drop_duplicates(subset=["idx"], keep="first").copy()
        out = out.sort_values("fecha_registro_dt", ascending=False)
        return out.head(2000)

    def _find_duplicates(self, df: pd.DataFrame):
        if df is None or df.empty:
            return pd.DataFrame()

        cols = [c for c in ["fecha_registro", "serie", "guia", "equipo", "marca", "origen", "destino", "tipo"] if c in df.columns]
        if not cols:
            return pd.DataFrame()

        tmp = df.copy()
        for c in cols:
            tmp[c] = tmp[c].astype(str).str.strip().str.lower()

        tmp["__sig__"] = tmp[cols].agg("|".join, axis=1)
        dup_mask = tmp.duplicated(subset="__sig__", keep="first")
        out = tmp[dup_mask].copy()
        out = out.drop(columns=["__sig__"], errors="ignore")
        return out.sort_values("fecha_registro_dt", ascending=False).head(2000)

    def _search_by_date_range(self, df: pd.DataFrame, d1, d2):
        if df is None or df.empty:
            return pd.DataFrame()
        if d1 is None or d2 is None:
            return pd.DataFrame()

        start = pd.to_datetime(d1)
        end = pd.to_datetime(d2)
        if pd.isna(start) or pd.isna(end):
            return pd.DataFrame()

        start = min(start, end).normalize()
        end = max(start, end).normalize() + pd.Timedelta(days=1)

        out = df[(df["fecha_registro_dt"] >= start) & (df["fecha_registro_dt"] < end)].copy()
        return out.sort_values("fecha_registro_dt", ascending=False).head(3000)

    def _unique_values(self, df: pd.DataFrame, cols, limit=200):
        vals = []
        for c in cols:
            if c in df.columns:
                v = (
                    df[c].astype(str)
                    .str.strip()
                    .replace({"": "N/A", "nan": "N/A", "None": "N/A"})
                    .fillna("N/A")
                )
                vals.extend(v.unique().tolist())
        vals = [x for x in vals if x and str(x).strip()]
        vals = sorted(list(dict.fromkeys(vals)))
        vals = [x for x in vals if str(x).strip().lower() not in ["n/a", "na", "none", "nan"]]
        return vals[:limit]

    # =========================================================
    # Core search
    # =========================================================
    def _search(self, df: pd.DataFrame, field: str, value: str):
        field = (field or "").strip().lower()
        value = (value or "").strip().lower()

        if df is None or df.empty:
            return pd.DataFrame()

        if field == "vacios":
            check_cols = [c for c in ["tipo","categoria_item","equipo","marca","modelo","serie","estado","origen","destino","guia","reporte"] if c in df.columns]
            if not check_cols:
                return pd.DataFrame()

            tmp = df[check_cols].astype(str).apply(lambda col: col.str.strip().str.lower())
            na_mask = tmp.isin(["n/a", "na", "", "none", "nan"])
            ratio = na_mask.sum(axis=1) / max(1, len(check_cols))
            out = df[ratio >= 0.8].copy()
            return out.sort_values("fecha_registro_dt", ascending=False).head(4000)

        if not value:
            return pd.DataFrame()

        if field in df.columns and field != "texto":
            s = df[field].astype(str).str.lower().str.strip()

            if field in ["serie", "guia"]:
                mask = (s == value) | s.str.contains(re.escape(value), na=False)
            elif field in ["tipo", "estado"]:
                mask = (s == value) | s.str.contains(re.escape(value), na=False)
            else:
                mask = s.str.contains(re.escape(value), na=False)

            out = df[mask].copy()
            return out.sort_values("fecha_registro_dt", ascending=False).head(4000)

        search_cols = [c for c in ["serie", "marca", "equipo", "modelo", "origen", "destino", "guia", "reporte", "tipo", "estado"] if c in df.columns]
        if not search_cols:
            search_cols = df.columns.tolist()

        mask = pd.Series(False, index=df.index)
        for c in search_cols:
            try:
                mask = mask | df[c].astype(str).str.lower().str.contains(re.escape(value), na=False)
            except Exception:
                pass

        out = df[mask].copy()
        return out.sort_values("fecha_registro_dt", ascending=False).head(4000)

    # =========================================================
    # Normalización
    # =========================================================
    def _safe_hist_to_df(self, hist):
        filas = []
        for x in hist:
            if isinstance(x, dict):
                filas.append(x)
            elif isinstance(x, (list, tuple)):
                continue
            else:
                continue
        return pd.DataFrame(filas)

    def _normalize(self, df: pd.DataFrame):
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        if "idx" not in df.columns:
            df.insert(0, "idx", range(len(df)))

        for c in [
            "fecha_registro", "tipo", "categoria_item", "equipo", "marca", "modelo", "serie",
            "cantidad", "estado", "origen", "destino", "guia", "reporte"
        ]:
            if c not in df.columns:
                df[c] = ""

        df["fecha_registro_dt"] = pd.to_datetime(df["fecha_registro"], errors="coerce")
        df["fecha_registro"] = df["fecha_registro_dt"].dt.strftime("%Y-%m-%d %H:%M")
        df["fecha_registro"] = df["fecha_registro"].fillna("N/A")

        try:
            df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(1).astype(int)
        except Exception:
            df["cantidad"] = 1

        text_cols = ["tipo", "categoria_item", "equipo", "marca", "modelo", "serie", "estado", "origen", "destino", "guia", "reporte"]
        for c in text_cols:
            df[c] = df[c].astype(str)
            df[c] = df[c].replace({"nan": "", "None": "", "NONE": "", "NaN": "", "NAN": ""})
            df[c] = df[c].fillna("").str.strip()
            df.loc[df[c] == "", c] = "N/A"

        keep = [c for c in self.base_cols if c in df.columns]
        df = df[keep].copy()
        return df

    def _reset(self, keep_order: bool = False):
        st.session_state.cln_results = pd.DataFrame()
        st.session_state.cln_selected_idx = set()
        st.session_state.cln_last_query = ""
        if not keep_order:
            st.session_state.cln_last_order = None
        st.session_state.cln_flow_step = 1
