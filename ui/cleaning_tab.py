import streamlit as st
import pandas as pd
import re
from datetime import datetime

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler


class CleaningTab:
    """
    🧹 Limpieza de Historial — v4 (Usuario Final)

    Objetivo:
    - Que cualquiera pueda buscar, seleccionar y borrar sin ver cosas técnicas.
    - Mantiene tu funcionalidad (mismo flujo, mismas keys, mismo GitHubHandler).
    - FIX real: "BORRAR TODO" ahora borra de verdad (manda TODOS los idx al robot).

    Flujo:
      1) Buscar (serie/guía/texto)
      2) Marcar lo que se quiere borrar
      3) Borrar seleccionados / Borrar todo (confirmaciones)
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
        st.session_state.setdefault("cln_editor_key", "0")  # para reset editor

    # =========================
    # UI
    # =========================
    def render(self):
        self._inject_css()

        st.markdown("## 🧹 Limpieza de Historial")
        st.caption("Busca registros, selecciona y elimina. Diseñado para usuario final.")

        # Aviso de orden enviada
        if st.session_state.get("cln_last_order"):
            with st.container(border=True):
                st.success("✅ Orden enviada. Presiona **Refrescar** cuando el robot termine de procesar.")
                c1, c2 = st.columns([1, 1], vertical_alignment="center")
                with c1:
                    if st.button("🔄 Refrescar", use_container_width=True, type="primary"):
                        st.session_state["cln_last_order"] = None
                        st.rerun()
                with c2:
                    if st.button("Ocultar", use_container_width=True):
                        st.session_state["cln_last_order"] = None
                        st.rerun()

        # Cargar historial
        hist = self.github.obtener_historico()
        if hist is None:
            st.error("❌ No pude leer el historial. Revisa conexión/token.")
            return
        if len(hist) == 0:
            st.info("📭 El historial está vacío.")
            return

        df = self._normalize(self._safe_hist_to_df(hist))
        st.session_state["cln_df"] = df

        # Panel superior: búsqueda
        with st.container(border=True):
            st.markdown("### 🔎 Buscar")
            c1, c2, c3 = st.columns([3.2, 1.2, 1.2], vertical_alignment="center")

            with c1:
                q = st.text_input(
                    "Escribe una serie, guía o cualquier texto",
                    value=st.session_state.get("cln_query", ""),
                    placeholder="Ej: 5CD4098M63 | guia 031002... | HP | Ambato | teclado | obsoleto ...",
                    key="cln_input_query_min",
                    label_visibility="visible",
                ).strip()
                st.session_state["cln_query"] = q

            with c2:
                if st.button("Buscar", type="primary", use_container_width=True):
                    view = self._apply_query(df, q)
                    st.session_state["cln_view"] = view
                    st.session_state["cln_selected_idx"] = set()
                    st.session_state["cln_editor_key"] = str(datetime.now().timestamp())
                    st.rerun()

            with c3:
                if st.button("Ver todo", use_container_width=True):
                    st.session_state["cln_view"] = df
                    st.session_state["cln_selected_idx"] = set()
                    st.session_state["cln_query"] = ""
                    st.session_state["cln_editor_key"] = str(datetime.now().timestamp())
                    st.rerun()

        # Vista por defecto
        if st.session_state.get("cln_view") is None or st.session_state.get("cln_view", pd.DataFrame()).empty:
            st.session_state["cln_view"] = df

        viewdf = st.session_state["cln_view"].copy()
        if viewdf.empty:
            st.warning("No hay resultados con esa búsqueda.")
            return

        # Tabla
        st.markdown("### 📋 Resultados")
        st.caption("Marca **Eliminar** solo los registros que quieras borrar.")

        cols_show = [c for c in [
            "idx", "fecha_registro", "tipo", "equipo", "marca", "modelo", "serie",
            "estado", "origen", "destino", "guia"
        ] if c in viewdf.columns]

        table = viewdf[cols_show].copy()
        table.insert(0, "Eliminar", False)

        edited = st.data_editor(
            table,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            height=520,
            key=f"cln_editor_min_{st.session_state['cln_editor_key']}",
        )

        selected_idx = set(edited.loc[edited["Eliminar"] == True, "idx"].astype(int).tolist())
        st.session_state["cln_selected_idx"] = selected_idx

        # Acciones
        with st.container(border=True):
            a1, a2, a3, a4 = st.columns([1.1, 1.4, 1.8, 2.1], vertical_alignment="center")

            with a1:
                st.metric("Seleccionados", len(selected_idx))

            with a2:
                if st.button("Limpiar selección", use_container_width=True):
                    st.session_state["cln_selected_idx"] = set()
                    st.session_state["cln_editor_key"] = str(datetime.now().timestamp())
                    st.rerun()

            with a3:
                self._ui_delete_selected(df, selected_idx)

            with a4:
                self._ui_delete_all(df)

    # =========================
    # UI: borrar seleccionados
    # =========================
    def _ui_delete_selected(self, dfall: pd.DataFrame, selected_idx: set):
        disabled = len(selected_idx) == 0

        with st.popover("🗑️ Borrar seleccionados", use_container_width=True, disabled=disabled):
            st.write(f"Vas a borrar **{len(selected_idx)}** registro(s).")
            st.caption("Esto no se puede deshacer.")
            confirm = st.checkbox("Confirmo borrar los seleccionados", value=False, key="cln_chk_confirm_selected_min")

            if st.button("Eliminar ahora", type="primary", use_container_width=True, disabled=(not confirm)):
                # Se mantiene el instruction que ya usas
                self._send_delete_order_indices(dfall, sorted(list(selected_idx)), instruction="BORRAR_SELECCIONADOS")
                st.rerun()

    # =========================
    # UI: borrar todo (fuerte)
    # =========================
    def _ui_delete_all(self, dfall: pd.DataFrame):
        with st.popover("🔥 Borrar TODO", use_container_width=True):
            st.warning("Esto elimina TODO el historial. Acción irreversible.")
            total = len(dfall)
            st.write(f"Total actual: **{total}** registros.")

            text = st.text_input(
                "Para confirmar, escribe: BORRAR TODO",
                placeholder="BORRAR TODO",
                key="cln_txt_confirm_delete_all_min",
            ).strip().upper()

            disabled = text != "BORRAR TODO"
            if st.button("Eliminar TODO ahora", type="primary", use_container_width=True, disabled=disabled):
                self._send_delete_order_all(dfall)  # ✅ ahora sí borra
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
            # limpiar UI
            st.session_state["cln_selected_idx"] = set()
            st.session_state["cln_view"] = pd.DataFrame()
            st.session_state["cln_query"] = ""
            st.session_state["cln_editor_key"] = str(datetime.now().timestamp())
            st.success("✅ Listo. Orden enviada.")
        else:
            st.error("❌ No se pudo enviar la orden. Revisa conexión/permiso.")
            st.json(orden)

    def _send_delete_order_all(self, dfall: pd.DataFrame):
        """
        FIX REAL:
        Tu robot (por tus logs) borra POR INDICES.
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
            instruction="BORRAR TODO"  # ✅ mismo texto que exige el usuario
        )

    # =========================
    # Normalización
    # =========================
    def _safe_hist_to_df(self, hist):
        filas = []
        for x in hist:
            if isinstance(x, dict):
                filas.append(x)
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
    # CSS (usuario final)
    # =========================
    def _inject_css(self):
        st.markdown(
            """
            <style>
              .stApp { background-color: #0e1117; }
              [data-testid="stDataEditor"] { border-radius: 14px; overflow: hidden; }
              .block-container { max-width: 1100px; padding-top: 1rem; }
            </style>
            """,
            unsafe_allow_html=True,
        )
