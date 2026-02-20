import streamlit as st
import pandas as pd
import re
from datetime import datetime

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler


class CleaningTab:
    """
    🧹 Limpieza de Historial — v5 (Usuario Final + Viñetas tipo Stock Real)

    UI:
      - 3 viñetas (tabs): Buscar / Seleccionar / Acciones
      - Métricas arriba: Total / Resultados / Seleccionados
      - FIX BORRAR TODO: manda TODOS los idx al robot (borrado por índices)

    Mantiene:
      - búsqueda por serie/guía/texto
      - data_editor con checkbox
      - envío de orden al robot via github.enviar_orden_limpieza()
    """

    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()

        # state
        st.session_state.setdefault("cln_df", pd.DataFrame())
        st.session_state.setdefault("cln_view", pd.DataFrame())
        st.session_state.setdefault("cln_selected_idx", set())
        st.session_state.setdefault("cln_query", "")
        st.session_state.setdefault("cln_last_order", None)
        st.session_state.setdefault("cln_editor_key", "0")
        st.session_state.setdefault("cln_active_tab", "🔎 Buscar")  # para mantener la viñeta

    # =========================
    # UI
    # =========================
    def render(self):
        self._inject_css()

        # Header tipo Stock Real
        with st.container(border=True):
            c1, c2, c3 = st.columns([3.2, 1.1, 1.1], vertical_alignment="center")
            with c1:
                st.markdown("## 🧹 Limpieza de Historial")
                st.caption("Busca registros, selecciona y elimina (pensado para usuario final).")
            with c2:
                if st.button("🔄 Refrescar", use_container_width=True, type="primary", key="cln_refresh_btn"):
                    # reset suave visual
                    st.session_state["cln_last_order"] = None
                    st.session_state["cln_editor_key"] = str(datetime.now().timestamp())
                    st.rerun()
            with c3:
                if st.button("🧼 Reiniciar", use_container_width=True, key="cln_reset_btn"):
                    self._reset_ui(full=True)
                    st.rerun()

        # Mensaje post orden
        if st.session_state.get("cln_last_order"):
            with st.container(border=True):
                st.success("✅ Orden enviada. Cuando el robot termine, presiona **Refrescar**.")
                b1, b2 = st.columns([1, 1], vertical_alignment="center")
                with b1:
                    if st.button("🔄 Refrescar ahora", use_container_width=True, key="cln_ref_now"):
                        st.session_state["cln_last_order"] = None
                        st.rerun()
                with b2:
                    if st.button("Ocultar mensaje", use_container_width=True, key="cln_hide_msg"):
                        st.session_state["cln_last_order"] = None
                        st.rerun()

        # Cargar histórico desde GitHub
        hist = self.github.obtener_historico()
        if hist is None:
            st.error("❌ No pude leer el historial. Revisa conexión/token.")
            return
        if len(hist) == 0:
            st.info("📭 El historial está vacío.")
            return

        df_all = self._normalize(self._safe_hist_to_df(hist))
        st.session_state["cln_df"] = df_all

        # Vista por defecto (si no existe)
        if st.session_state.get("cln_view") is None or st.session_state.get("cln_view", pd.DataFrame()).empty:
            st.session_state["cln_view"] = df_all

        df_view = st.session_state["cln_view"].copy()

        # Métricas TOP (siempre visibles)
        total = int(len(df_all))
        results = int(len(df_view)) if isinstance(df_view, pd.DataFrame) else 0
        selected = int(len(st.session_state.get("cln_selected_idx", set())))

        with st.container(border=True):
            m1, m2, m3 = st.columns(3, vertical_alignment="center")
            m1.metric("📦 Total registros", total)
            m2.metric("🔎 Resultados", results)
            m3.metric("✅ Seleccionados", selected)

        # Viñetas (tabs)
        tabs = ["🔎 Buscar", "✅ Seleccionar", "🗑️ Acciones"]
        t_search, t_select, t_actions = st.tabs(tabs)

        # -------------------------
        # TAB 1: BUSCAR
        # -------------------------
        with t_search:
            with st.container(border=True):
                st.markdown("### 🔎 Buscar en el historial")
                st.caption("Puedes escribir una serie, guía o texto (marca, agencia, estado, etc.).")

                q = st.text_input(
                    "Buscar",
                    value=st.session_state.get("cln_query", ""),
                    placeholder="Ej: 5CD4098M63 | guia 031002... | HP | Ambato | teclado | obsoleto ...",
                    key="cln_input_query_v5",
                ).strip()
                st.session_state["cln_query"] = q

                c1, c2, c3 = st.columns([1.2, 1.2, 1.6], vertical_alignment="center")
                with c1:
                    if st.button("Buscar", type="primary", use_container_width=True, key="cln_btn_search_v5"):
                        view = self._apply_query(df_all, q)
                        st.session_state["cln_view"] = view
                        st.session_state["cln_selected_idx"] = set()
                        st.session_state["cln_editor_key"] = str(datetime.now().timestamp())
                        st.success("✅ Listo. Ve a la viñeta **Seleccionar**.")
                with c2:
                    if st.button("Ver todo", use_container_width=True, key="cln_btn_all_v5"):
                        st.session_state["cln_view"] = df_all
                        st.session_state["cln_selected_idx"] = set()
                        st.session_state["cln_query"] = ""
                        st.session_state["cln_editor_key"] = str(datetime.now().timestamp())
                        st.success("✅ Mostrando todo. Ve a **Seleccionar**.")
                with c3:
                    st.info("Tip: escribe `guia 0310...` o `serie 5CD...` para afinar.", icon="💡")

            # Preview pequeño (no tabla gigante)
            if isinstance(df_view, pd.DataFrame) and not df_view.empty:
                with st.expander("👀 Vista rápida (últimos 12 resultados)", expanded=False):
                    cols_preview = [c for c in ["fecha_registro", "tipo", "equipo", "marca", "modelo", "serie", "estado", "origen", "destino", "guia"] if c in df_view.columns]
                    st.dataframe(df_view[cols_preview].head(12), use_container_width=True, hide_index=True)

        # -------------------------
        # TAB 2: SELECCIONAR
        # -------------------------
        with t_select:
            with st.container(border=True):
                st.markdown("### ✅ Seleccionar registros a eliminar")
                st.caption("Marca **Eliminar** solo lo que realmente deseas borrar.")

            if df_view is None or df_view.empty:
                st.warning("No hay resultados para seleccionar. Ve a **Buscar**.")
            else:
                cols_show = [c for c in [
                    "idx", "fecha_registro", "tipo", "equipo", "marca", "modelo", "serie",
                    "estado", "origen", "destino", "guia"
                ] if c in df_view.columns]

                table = df_view[cols_show].copy()
                table.insert(0, "Eliminar", False)

                edited = st.data_editor(
                    table,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    height=560,
                    key=f"cln_editor_v5_{st.session_state['cln_editor_key']}",
                )

                selected_idx = set(edited.loc[edited["Eliminar"] == True, "idx"].astype(int).tolist())
                st.session_state["cln_selected_idx"] = selected_idx

                with st.container(border=True):
                    c1, c2 = st.columns([1.2, 2.2], vertical_alignment="center")
                    with c1:
                        st.metric("Seleccionados", len(selected_idx))
                    with c2:
                        if st.button("🧽 Limpiar selección", use_container_width=True, key="cln_clear_sel_v5"):
                            st.session_state["cln_selected_idx"] = set()
                            st.session_state["cln_editor_key"] = str(datetime.now().timestamp())
                            st.rerun()

                st.info("Cuando termines, ve a la viñeta **Acciones** para eliminar.", icon="➡️")

        # -------------------------
        # TAB 3: ACCIONES
        # -------------------------
        with t_actions:
            with st.container(border=True):
                st.markdown("### 🗑️ Acciones")
                st.caption("Elimina seleccionados o elimina todo el historial.")

            sel = st.session_state.get("cln_selected_idx", set())

            a1, a2 = st.columns([1.6, 1.6], vertical_alignment="center")

            with a1:
                self._ui_delete_selected(df_all, sel)

            with a2:
                self._ui_delete_all(df_all)

    # =========================
    # UI: borrar seleccionados
    # =========================
    def _ui_delete_selected(self, dfall: pd.DataFrame, selected_idx: set):
        disabled = len(selected_idx) == 0

        with st.container(border=True):
            st.markdown("#### 🧹 Eliminar seleccionados")
            st.caption("Solo elimina los registros que marcaste en la viñeta **Seleccionar**.")
            st.write(f"Seleccionados: **{len(selected_idx)}**")

            with st.popover("🗑️ Eliminar seleccionados", use_container_width=True, disabled=disabled):
                st.warning("Esto no se puede deshacer.")
                confirm = st.checkbox("Confirmo eliminar los seleccionados", value=False, key="cln_chk_confirm_selected_v5")

                if st.button("Eliminar ahora", type="primary", use_container_width=True, disabled=(not confirm)):
                    self._send_delete_order_indices(dfall, sorted(list(selected_idx)), instruction="BORRAR_SELECCIONADOS")
                    st.rerun()

            if disabled:
                st.info("Marca registros en **Seleccionar** para habilitar este botón.", icon="ℹ️")

    # =========================
    # UI: borrar todo (fuerte)
    # =========================
    def _ui_delete_all(self, dfall: pd.DataFrame):
        with st.container(border=True):
            st.markdown("#### 🔥 Eliminar TODO")
            st.caption("Borra el historial completo (uso restringido).")
            st.write(f"Total actual: **{len(dfall)}**")

            with st.popover("🔥 Eliminar TODO", use_container_width=True):
                st.error("Acción irreversible. Solo úsalo si estás seguro.")
                text = st.text_input(
                    "Escribe: BORRAR TODO",
                    placeholder="BORRAR TODO",
                    key="cln_txt_confirm_delete_all_v5",
                ).strip().upper()

                disabled = text != "BORRAR TODO"
                if st.button("Eliminar TODO ahora", type="primary", use_container_width=True, disabled=disabled):
                    self._send_delete_order_all(dfall)  # ✅ borrado real
                    st.rerun()

    # =========================
    # lógica de búsqueda
    # =========================
    def _apply_query(self, df: pd.DataFrame, q: str) -> pd.DataFrame:
        q = (q or "").strip()
        if not q:
            return df

        field, value = self._detect_intent(q)
        return self._search(df, field, value)

    def _detect_intent(self, q: str):
        ql = q.lower().strip()

        m = re.search(r"\b(serie|serial)\s*[:#-]?\s*([a-z0-9\-_/]+)\b", ql)
        if m:
            return "serie", m.group(2).strip()

        m = re.search(r"\b(guia|guía)\s*[:#-]?\s*([a-z0-9\-_/]+)\b", ql)
        if m:
            return "guia", m.group(2).strip()

        # si parece un código sin espacios -> serie
        if re.fullmatch(r"[a-z0-9\-_/]{4,}", ql) and " " not in ql:
            return "serie", ql

        return "texto", ql

    def _search(self, df: pd.DataFrame, field: str, value: str) -> pd.DataFrame:
        field = (field or "").strip().lower()
        value = (value or "").strip().lower()

        if df is None or df.empty:
            return pd.DataFrame()

        if not value:
            return pd.DataFrame()

        if field in df.columns and field != "texto":
            s = df[field].astype(str).str.lower().str.strip()
            if field in ["serie", "guia"]:
                mask = (s == value) | s.str.contains(re.escape(value), na=False)
            else:
                mask = s.str.contains(re.escape(value), na=False)
            out = df[mask].copy()
            return out.sort_values("fecha_registro_dt", ascending=False)

        # texto global
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
        return out.sort_values("fecha_registro_dt", ascending=False)

    # =========================
    # enviar órdenes al robot
    # =========================
    def _send_delete_order_indices(self, dfall: pd.DataFrame, idx_list: list, instruction: str):
        sub = dfall[dfall["idx"].isin(idx_list)].copy()

        matches = []
        for _, r in sub.iterrows():
            matches.append({
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
            "instruction": instruction,  # BORRAR_SELECCIONADOS o BORRAR TODO
            "count": len(idx_list),
            "accion": "borrar_por_indices",
            "idx_list": [int(x) for x in idx_list],
            "matches": matches,
        }

        ok = self.github.enviar_orden_limpieza(orden)
        if ok:
            st.session_state["cln_last_order"] = orden
            self._reset_ui(full=False)
            st.success("✅ Orden enviada. Espera al robot y luego presiona Refrescar.")
        else:
            st.error("❌ No se pudo enviar la orden. Revisa conexión/permiso.")
            st.json(orden)

    def _send_delete_order_all(self, dfall: pd.DataFrame):
        """
        FIX REAL:
        Tu robot borra POR INDICES.
        Antes mandabas idx_list vacío => eliminados 0.
        Ahora mandamos TODOS los idx para borrar todo usando el flujo existente.
        """
        if dfall is None or dfall.empty or "idx" not in dfall.columns:
            st.error("❌ No hay registros para borrar.")
            return

        all_idx = dfall["idx"].astype(int).tolist()
        self._send_delete_order_indices(
            dfall=dfall,
            idx_list=sorted(all_idx),
            instruction="BORRAR TODO"
        )

    # =========================
    # Normalización
    # =========================
    def _safe_hist_to_df(self, hist):
        filas = []
        for x in hist:
            if isinstance(x, dict):
                filas.append(x)
            elif isinstance(x, (list, tuple)):
                # Si te llega sucio tipo lista, lo ignoramos aquí (limpieza solo para dicts)
                # (Si quieres mapearlo a schema como StockTab, me dices y lo adapto)
                pass
        return pd.DataFrame(filas)

    def _normalize(self, df: pd.DataFrame):
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        if "idx" not in df.columns:
            df.insert(0, "idx", range(len(df)))

        for c in ["fecha_registro", "tipo", "equipo", "marca", "modelo", "serie", "estado", "origen", "destino", "guia", "reporte"]:
            if c not in df.columns:
                df[c] = "N/A"

        df["fecha_registro_dt"] = pd.to_datetime(df["fecha_registro"], errors="coerce")
        df = df.sort_values("fecha_registro_dt", ascending=False, na_position="last")

        # limpiar strings
        text_cols = ["tipo", "equipo", "marca", "modelo", "serie", "estado", "origen", "destino", "guia", "reporte"]
        for c in text_cols:
            df[c] = df[c].astype(str).replace({"nan": "N/A", "None": "N/A", "": "N/A"}).fillna("N/A").str.strip()
            df.loc[df[c] == "", c] = "N/A"

        # fecha visual
        df["fecha_registro"] = df["fecha_registro_dt"].dt.strftime("%Y-%m-%d %H:%M")
        df["fecha_registro"] = df["fecha_registro"].fillna("N/A")

        return df

    # =========================
    # Helpers UI
    # =========================
    def _reset_ui(self, full: bool = False):
        # reset editor + selección (no toques df)
        st.session_state["cln_selected_idx"] = set()
        st.session_state["cln_editor_key"] = str(datetime.now().timestamp())
        if full:
            st.session_state["cln_query"] = ""
            st.session_state["cln_view"] = pd.DataFrame()

    # =========================
    # CSS (más pro, menos técnico)
    # =========================
    def _inject_css(self):
        st.markdown(
            """
            <style>
              .stApp { background-color: #0e1117; }
              .block-container { max-width: 1100px; padding-top: 1rem; }
              [data-testid="stDataEditor"] { border-radius: 14px; overflow: hidden; }
              [data-testid="stMetric"] {
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 14px;
                padding: 10px 12px;
                background: rgba(255,255,255,0.02);
              }
            </style>
            """,
            unsafe_allow_html=True,
        )
