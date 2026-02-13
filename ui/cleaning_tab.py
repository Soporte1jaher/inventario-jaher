import streamlit as st
import pandas as pd
import re
from datetime import datetime

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler


class CleaningTab:
    """
    🧹 Limpieza (Minimalista, usuario final) — v3

    ✅ Un solo flujo:
      1) Buscar (serie/guía/texto)
      2) Seleccionar (checkbox en tabla)
      3) Borrar seleccionados / Borrar todo (con confirmación)

    ✅ Incluye:
      - Buscar por SERIE / GUÍA (auto-detect) o texto general
      - Tabla simple (solo columnas clave)
      - Botón "Borrar todo" (confirmación fuerte)
      - Botón "Borrar seleccionados" (confirmación simple)
      - Refrescar
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
        st.caption("Busca, selecciona y borra. Hecho para usuario final.")

        # Orden anterior (si existe)
        if st.session_state.get("cln_last_order"):
            with st.container(border=True):
                st.success("✅ Orden enviada. Refresca cuando el robot procese historico.json.")
                c1, c2 = st.columns([1, 1.5])
                with c1:
                    if st.button("🔄 Refrescar", use_container_width=True):
                        st.session_state["cln_last_order"] = None
                        st.rerun()
                with c2:
                    if st.button("🧼 Ocultar mensaje", use_container_width=True):
                        st.session_state["cln_last_order"] = None
                        st.rerun()

        # cargar historial
        hist = self.github.obtener_historico()
        if hist is None:
            st.error("❌ No pude leer el historial (GitHub). Revisa tu token/secret.")
            return
        if len(hist) == 0:
            st.info("📭 El historial está vacío.")
            return

        df = self._normalize(self._safe_hist_to_df(hist))
        st.session_state["cln_df"] = df

        # Barra superior (minimal)
        with st.container(border=True):
            c1, c2, c3 = st.columns([3.2, 1.2, 1.2], vertical_alignment="center")

            with c1:
                q = st.text_input(
                    "Buscar (serie, guía o texto)",
                    value=st.session_state.get("cln_query", ""),
                    placeholder="Ej: 099209 | guia 9032 | HP | babahoyo | teclado | obsoleto ...",
                    key="cln_input_query_min",
                ).strip()
                st.session_state["cln_query"] = q

            with c2:
                if st.button("🔎 Buscar", type="primary", use_container_width=True):
                    view = self._apply_query(df, q)
                    st.session_state["cln_view"] = view
                    st.session_state["cln_selected_idx"] = set()
                    st.session_state["cln_editor_key"] = str(datetime.now().timestamp())
                    st.rerun()

            with c3:
                if st.button("↩️ Mostrar todo", use_container_width=True):
                    st.session_state["cln_view"] = df
                    st.session_state["cln_selected_idx"] = set()
                    st.session_state["cln_query"] = ""
                    st.session_state["cln_editor_key"] = str(datetime.now().timestamp())
                    st.rerun()

        # Vista por defecto: si no hay view aún, mostrar todo
        if st.session_state.get("cln_view") is None or st.session_state.get("cln_view", pd.DataFrame()).empty:
            # si el usuario todavía no buscó nada, mostramos TODO sin filtrar
            st.session_state["cln_view"] = df

        viewdf = st.session_state["cln_view"].copy()
        if viewdf.empty:
            st.warning("No hay resultados con esa búsqueda.")
            return

        # Tabla simple
        st.markdown("### Resultados")
        st.caption("Marca ELIMINAR solo lo que realmente quieres borrar.")

        cols_show = [c for c in [
            "idx", "fecha_registro", "tipo", "equipo", "marca", "modelo", "serie",
            "estado", "origen", "destino", "guia"
        ] if c in viewdf.columns]

        table = viewdf[cols_show].copy()
        table.insert(0, "ELIMINAR", False)

        edited = st.data_editor(
            table,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            height=520,
            key=f"cln_editor_min_{st.session_state['cln_editor_key']}",
        )

        selected_idx = set(edited.loc[edited["ELIMINAR"] == True, "idx"].astype(int).tolist())
        st.session_state["cln_selected_idx"] = selected_idx

        # Acciones
        with st.container(border=True):
            a1, a2, a3, a4 = st.columns([1.2, 1.4, 1.8, 2.2], vertical_alignment="center")
            with a1:
                st.metric("Seleccionados", len(selected_idx))
            with a2:
                if st.button("🧽 Limpiar selección", use_container_width=True):
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
            confirm = st.checkbox("✅ Confirmo borrar seleccionados", value=False, key="cln_chk_confirm_selected_min")

            if st.button("🔥 Enviar orden", type="primary", use_container_width=True, disabled=(not confirm)):
                self._send_delete_order_indices(dfall, sorted(list(selected_idx)), instruction="BORRAR_SELECCIONADOS")
                st.rerun()

    # =========================
    # UI: borrar todo (fuerte)
    # =========================
    def _ui_delete_all(self, dfall: pd.DataFrame):
        with st.popover("🔥 Borrar TODO", use_container_width=True):
            st.warning("Esto borra TODO el historico.json. Acción irreversible.")
            total = len(dfall)
            st.write(f"Total actual: **{total}** registros.")

            text = st.text_input(
                "Para confirmar, escribe EXACTAMENTE: BORRAR TODO",
                placeholder="BORRAR TODO",
                key="cln_txt_confirm_delete_all_min",
            ).strip().upper()

            disabled = text != "BORRAR TODO"
            if st.button("🔥 Enviar orden BORRAR TODO", type="primary", use_container_width=True, disabled=disabled):
                self._send_delete_order_all(dfall)
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
            "instruction": instruction,
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
            st.session_state["cln_editor_key"] = str(datetime.now().timestamp())
            st.success("✅ Orden enviada.")
        else:
            st.error("❌ No se pudo enviar la orden. Revisa formato esperado por el robot.")
            st.json(orden)

    def _send_delete_order_all(self, dfall: pd.DataFrame):
        # orden simple para que el robot entienda "borrar todo"
        orden = {
            "action": "delete",
            "source": "historico.json",
            "instruction": "BORRAR_TODO",
            "count": int(len(dfall)),
            "accion": "borrar_todo",
            "idx_list": [],
            "matches": [],
        }

        ok = self.github.enviar_orden_limpieza(orden)
        if ok:
            st.session_state["cln_last_order"] = orden
            st.session_state["cln_selected_idx"] = set()
            st.session_state["cln_view"] = pd.DataFrame()
            st.session_state["cln_query"] = ""
            st.session_state["cln_editor_key"] = str(datetime.now().timestamp())
            st.success("✅ Orden BORRAR TODO enviada.")
        else:
            st.error("❌ No se pudo enviar la orden BORRAR TODO. Revisa formato esperado por el robot.")
            st.json(orden)

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
    # CSS mínimo
    # =========================
    def _inject_css(self):
        st.markdown(
            """
            <style>
              .stApp { background-color: #0e1117; }
              [data-testid="stDataEditor"] { border-radius: 14px; overflow: hidden; }
            </style>
            """,
            unsafe_allow_html=True,
        )
