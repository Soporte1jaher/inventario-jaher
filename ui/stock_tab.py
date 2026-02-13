# ui/stock_tab.py
"""
ui/stock_tab.py
Stock Real — Control & Reportes (PRO)

Mejoras clave:
- 4 vistas: Movimientos / Stock / Bodega / Dañados
- Regla JAHER:
  - si DESTINO == "bodega" -> solo se ve en BODEGA (no en MOVIMIENTOS)
  - si ORIGEN == "bodega" -> se ve normal en MOVIMIENTOS
- Métricas top + resumen por equipo
- Debug opcional
- Export Excel 4 hojas (RAW)

FIX aplicado:
✅ 1) Filtrar “comandos” (action/accion delete/borrar_*)
✅ 2) Sanear histórico: eliminar filas raras (listas/columnas 0,1,2...) que contaminan UI
✅ 3) Forzar columnas de vista (las mismas del Excel)
"""

import streamlit as st
import pandas as pd
import datetime
import io

from modules.github_handler import GitHubHandler
from modules.stock_calculator import StockCalculator


class StockTab:
    def __init__(self):
        self.github = GitHubHandler()
        self.stock_calc = StockCalculator()

        # Columnas “oficiales” (las que quieres ver igual que Excel)
        self.base_cols = [
            "fecha_registro",
            "guia",
            "tipo",
            "origen",
            "destino",
            "categoria_item",
            "equipo",
            "marca",
            "modelo",
            "serie",
            "estado",
            "procesador",
            "ram",
            "disco",
            "reporte",
            "cantidad",
        ]

    # ---------------------------------------------------------
    # ✅ FIX 1: Filtrar filas comando dentro del histórico
    # ---------------------------------------------------------
    def _filtrar_comandos(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        d = df.copy()
        d.columns = [str(c).strip().lower() for c in d.columns]

        col_acc = None
        if "action" in d.columns:
            col_acc = "action"
        elif "accion" in d.columns:
            col_acc = "accion"

        if col_acc:
            acc = d[col_acc].astype(str).str.strip().str.lower()
            comandos = acc.isin(["delete", "borrar_por_indices", "borrar_todo", "borrar"])
            return d[~comandos].copy()

        # Fallback por indices + source/instruction
        if "indices" in d.columns:
            ind = d["indices"].astype(str).str.strip()
            comandos = ind.str.startswith("[") & ind.str.endswith("]") & (ind != "[]")
            if "instruction" in d.columns or "source" in d.columns:
                return d[~comandos].copy()

        return d

    # ---------------------------------------------------------
    # ✅ FIX 2: Sanear histórico antes del cálculo/UI
    # - Si vienen listas -> mapear a schema
    # - Si vienen dicts con columnas 0,1,2... -> limpiar
    # ---------------------------------------------------------
    def _sanear_historial(self, hist) -> pd.DataFrame:
        if not hist:
            return pd.DataFrame()

        filas = []
        schema = self.base_cols[:]  # mismo orden

        for x in hist:
            if isinstance(x, dict):
                filas.append(x)
                continue

            # Si te llegó como lista/tuple => convertir a dict por orden
            if isinstance(x, (list, tuple)):
                d = {}
                for i, k in enumerate(schema):
                    d[k] = x[i] if i < len(x) else ""
                filas.append(d)

        df = pd.DataFrame(filas)
        if df.empty:
            return df

        # Normalizar nombres de columnas
        df.columns = [str(c).strip().lower() for c in df.columns]

        # ❌ eliminar columnas basura típicas que aparecen en tu web
        # (columnas numéricas 0,1,2,3... y comandos)
        cols_drop = []
        for c in df.columns:
            cs = str(c).strip().lower()
            if cs.isdigit():  # "0","1","2"...
                cols_drop.append(c)
            if cs in ["action", "accion", "source", "instruction", "count", "indices", "idx_list", "mat", "meta"]:
                cols_drop.append(c)

        if cols_drop:
            df = df.drop(columns=list(set(cols_drop)), errors="ignore")

        return df

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------
    def render(self):
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1.1, 1.1], vertical_alignment="center")

            with c1:
                st.markdown("## 📊 Stock Real — Control & Reportes")
                st.caption("Fuente: historico.json (GitHub) → cálculo modular → vistas + Excel (4 hojas)")

            with c2:
                if st.button("🔄 Refrescar", use_container_width=True, key="stk_refresh_btn"):
                    st.rerun()

            with c3:
                show_debug = st.toggle(
                    "🧪 Debug",
                    value=False,
                    help="Muestra dataframes crudos/post-cálculo (solo para revisión).",
                    key="stk_debug_toggle",
                )

        hist = self.github.obtener_historico()
        if not hist:
            st.info("Aún no hay datos en el histórico.")
            return

        self._mostrar_datos(hist, show_debug=show_debug)

    # ---------------------------------------------------------
    # Core
    # ---------------------------------------------------------
    def _mostrar_datos(self, hist, show_debug=False):
        # ✅ SANEAR primero (mata las columnas 0,1,2... y filas raras)
        df_h_raw = self._sanear_historial(hist)
        if df_h_raw.empty:
            st.info("Histórico vacío.")
            return

        # ✅ Filtrar comandos (por si quedaron dicts con action/accion)
        df_h_raw = self._filtrar_comandos(df_h_raw)

        # Cálculo modular (tu lógica)
        st_res_raw, bod_res_raw, danados_res_raw, df_h_raw_out = self.stock_calc.calcular_stock_completo(df_h_raw)

        # ✅ doble sanitización por seguridad
        if isinstance(df_h_raw_out, pd.DataFrame):
            df_h_raw_out = self._filtrar_comandos(df_h_raw_out)
            # también recortar basura si el calculador reintroduce columnas extra
            df_h_raw_out.columns = [str(c).strip().lower() for c in df_h_raw_out.columns]
            for extra in ["action", "accion", "source", "instruction", "count", "indices"]:
                if extra in df_h_raw_out.columns:
                    df_h_raw_out = df_h_raw_out.drop(columns=[extra], errors="ignore")

        # Vista normalizada (UI)
        df_h_view = self._normalize_historial(df_h_raw_out)

        # ✅ Regla JAHER: si destino=bodega => sale de Movimientos
        df_mov_view = self._movimientos_sin_destino_bodega(df_h_view)

        # Normalizar tablas para UI (y limpiar NaN)
        st_res_view = self._normalize_stock(st_res_raw, mode="stock")
        bod_res_view = self._normalize_stock(bod_res_raw, mode="bodega")
        danados_res_view = self._normalize_stock(danados_res_raw, mode="danados")

        # Métricas + resumen por equipo
        self._mostrar_metricas_top(df_h_view, df_mov_view, st_res_view, bod_res_view, danados_res_view)

        # Export (RAW) pero ya limpio
        self._crear_boton_descarga(st_res_raw, bod_res_raw, danados_res_raw, df_h_raw_out)

        # Tabs internas
        t_mov, t_stock, t_bod, t_dan = st.tabs(
            ["🧾 Movimientos", "📦 Stock (Periféricos)", "🏢 Bodega (Cómputo)", "🧯 Dañados/Chatarras"]
        )

        with t_mov:
            self._tab_movimientos(df_mov_view)

        with t_stock:
            self._tab_stock(st_res_view)

        with t_bod:
            self._tab_bodega(bod_res_view)

        with t_dan:
            self._tab_danados(danados_res_view)

        if show_debug:
            with st.expander("🧪 Debug (revisión técnica)", expanded=False):
                st.write("df_h_raw (saneado):", df_h_raw.shape)
                st.dataframe(df_h_raw.head(30), use_container_width=True)

                if isinstance(df_h_raw_out, pd.DataFrame):
                    st.write("df_h_raw_out:", df_h_raw_out.shape)
                    st.dataframe(df_h_raw_out.head(30), use_container_width=True)

                st.write("df_h_view:", df_h_view.shape)
                st.dataframe(df_h_view.head(30), use_container_width=True)

                st.write("df_mov_view:", df_mov_view.shape)
                st.dataframe(df_mov_view.head(30), use_container_width=True)

                if isinstance(st_res_raw, pd.DataFrame):
                    st.write("st_res_raw:", st_res_raw.shape)
                    st.dataframe(st_res_raw.head(30), use_container_width=True)

    # ---------------------------------------------------------
    # Métricas + resumen
    # ---------------------------------------------------------
    def _mostrar_metricas_top(self, df_h_view, df_mov_view, st_res_view, bod_res_view, danados_res_view):
        total_hist = len(df_h_view)
        total_mov = len(df_mov_view)

        total_stock = 0
        if isinstance(st_res_view, pd.DataFrame) and not st_res_view.empty:
            if "cantidad_disponible" in st_res_view.columns:
                total_stock = int(pd.to_numeric(st_res_view["cantidad_disponible"], errors="coerce").fillna(0).sum())

        total_bodega = len(bod_res_view) if isinstance(bod_res_view, pd.DataFrame) else 0
        total_danados = len(danados_res_view) if isinstance(danados_res_view, pd.DataFrame) else 0

        ultimo = ""
        if "fecha_registro" in df_h_view.columns:
            try:
                ultimo_dt = pd.to_datetime(df_h_view["fecha_registro"], errors="coerce").max()
                if pd.notna(ultimo_dt):
                    ultimo = ultimo_dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                ultimo = ""

        with st.container(border=True):
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("📜 Movimientos (vista)", total_mov, help="Movimientos visibles (EXCLUYE destino=bodega).")
            k2.metric("📦 Periféricos en Stock", total_stock, help="Total disponible en stock (suma).")
            k3.metric("🏢 Registros en Bodega", total_bodega, help="Items que caen en la vista Bodega.")
            k4.metric("🧯 Dañados/Chatarras", total_danados, help="Items marcados como dañados/obsoletos/chatarras.")

            if ultimo:
                st.caption(f"🕒 Última actividad detectada: **{ultimo}** | Histórico total: **{total_hist}**")

        if isinstance(st_res_view, pd.DataFrame) and (not st_res_view.empty):
            if "equipo" in st_res_view.columns and "cantidad_disponible" in st_res_view.columns:
                with st.container(border=True):
                    st.markdown("### 📌 Resumen rápido (por equipo)")
                    st.caption("Ej: TECLADO 11, MOUSE 3… (calculado desde la tabla de Stock)")

                    df = st_res_view.copy()
                    df["cantidad_disponible"] = pd.to_numeric(df["cantidad_disponible"], errors="coerce").fillna(0).astype(int)

                    resumen = (
                        df.groupby("equipo")["cantidad_disponible"]
                        .sum()
                        .reset_index()
                        .sort_values("cantidad_disponible", ascending=False)
                    )

                    if resumen.empty:
                        st.info("No hay datos suficientes para resumen por equipo.")
                    else:
                        top = resumen.head(10)
                        cols = st.columns(min(5, len(top)))
                        for i, (_, row) in enumerate(top.iterrows()):
                            with cols[i % len(cols)]:
                                st.metric(str(row["equipo"]).upper(), int(row["cantidad_disponible"]))

                        with st.expander("Ver detalle completo (tabla)", expanded=False):
                            st.dataframe(resumen, use_container_width=True, hide_index=True)

        st.divider()

    # ---------------------------------------------------------
    # Tabs
    # ---------------------------------------------------------
    def _tab_movimientos(self, df_view):
        with st.container(border=True):
            st.markdown("### 🧾 Movimientos (Histórico)")
            st.caption("Regla: DESTINO='bodega' NO se muestra aquí (solo en Bodega).")

            if df_view is None or df_view.empty:
                st.warning("No hay movimientos para mostrar.")
                return

            df_show = self._clean_nan_to_na(df_view.copy())
            st.dataframe(df_show.tail(250), use_container_width=True, hide_index=True, height=520)

    def _tab_stock(self, st_res):
        with st.container(border=True):
            st.markdown("### 📦 Stock (Periféricos)")
            if st_res is None or st_res.empty:
                st.info("No hay stock disponible (o no se han registrado periféricos).")
                return

            df = self._clean_nan_to_na(st_res.copy())

            if "cantidad_disponible" in df.columns:
                df["cantidad_disponible"] = pd.to_numeric(df["cantidad_disponible"], errors="coerce").fillna(0).astype(int)
                df = df.sort_values("cantidad_disponible", ascending=False)

            st.dataframe(df, use_container_width=True, hide_index=True, height=560)

    def _tab_bodega(self, bod_res):
        with st.container(border=True):
            st.markdown("### 🏢 Bodega (Cómputo)")
            st.caption("Aquí se muestran registros que caen en Bodega (incluye DESTINO='bodega').")

            if bod_res is None or bod_res.empty:
                st.info("No hay registros que caigan en Bodega.")
                return

            df = self._clean_nan_to_na(bod_res.copy())
            st.dataframe(df, use_container_width=True, hide_index=True, height=560)

    def _tab_danados(self, danados_res):
        with st.container(border=True):
            st.markdown("### 🧯 Dañados / Chatarras / Bajas")
            if danados_res is None or danados_res.empty:
                st.info("No hay registros marcados como dañados/chatarras/bajas.")
                return

            df = self._clean_nan_to_na(danados_res.copy())
            st.dataframe(df, use_container_width=True, hide_index=True, height=560)

    # ---------------------------------------------------------
    # Export
    # ---------------------------------------------------------
    def _crear_boton_descarga(self, st_res, bod_res, danados_res, df_h):
        with st.container(border=True):
            c1, c2 = st.columns([3, 1.4], vertical_alignment="center")
            with c1:
                st.markdown("### 📥 Exportación Excel")
                st.caption("Descarga el Excel con 4 hojas: MOVIMIENTOS, STOCK_SALDOS, BODEGA, DANADOS_CHATARRA.")
            with c2:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    pd.DataFrame(df_h).to_excel(writer, index=False, sheet_name="MOVIMIENTOS")

                    if isinstance(st_res, pd.DataFrame) and not st_res.empty:
                        st_res.to_excel(writer, index=False, sheet_name="STOCK_SALDOS")
                    else:
                        pd.DataFrame().to_excel(writer, index=False, sheet_name="STOCK_SALDOS")

                    if isinstance(bod_res, pd.DataFrame) and not bod_res.empty:
                        bod_res.to_excel(writer, index=False, sheet_name="BODEGA")
                    else:
                        pd.DataFrame().to_excel(writer, index=False, sheet_name="BODEGA")

                    if isinstance(danados_res, pd.DataFrame) and not danados_res.empty:
                        danados_res.to_excel(writer, index=False, sheet_name="DANADOS_CHATARRA")
                    else:
                        pd.DataFrame().to_excel(writer, index=False, sheet_name="DANADOS_CHATARRA")

                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                st.download_button(
                    label="📥 Descargar Excel (4 hojas)",
                    data=buffer.getvalue(),
                    file_name=f"Inventario_Jaher_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                    key="stk_download_excel",
                )

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _clean_nan_to_na(self, df: pd.DataFrame):
        if df is None or df.empty:
            return df
        df = df.replace({pd.NA: "", "nan": ""}).fillna("")
        df = df.replace("", "N/A")
        return df

    def _normalize_historial(self, df: pd.DataFrame):
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        # compat: si viene fecha_llegada
        if "fecha_llegada" in df.columns and "fecha_registro" not in df.columns:
            df["fecha_registro"] = df["fecha_llegada"]

        # Asegurar columnas base
        for c in self.base_cols:
            if c not in df.columns:
                df[c] = ""

        # Forzar SOLO columnas base para que nunca se cuelen extras
        df = df[self.base_cols].copy()

        df["fecha_registro_dt"] = pd.to_datetime(df["fecha_registro"], errors="coerce")
        df = df.sort_values("fecha_registro_dt", ascending=True)

        df["fecha_registro"] = df["fecha_registro_dt"].dt.strftime("%Y-%m-%d %H:%M").fillna("N/A")

        try:
            df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(1).astype(int)
        except Exception:
            df["cantidad"] = 1

        # Quitar helper dt antes de mostrar
        df = df.drop(columns=["fecha_registro_dt"], errors="ignore")
        return self._clean_nan_to_na(df)

    def _normalize_stock(self, df, mode="stock"):
        if df is None:
            return pd.DataFrame()

        if not isinstance(df, pd.DataFrame):
            try:
                df = pd.DataFrame(df)
            except Exception:
                return pd.DataFrame()

        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        if "valor_final" in df.columns and "val" not in df.columns:
            df["val"] = df["valor_final"]

        if mode == "stock":
            if "equipo_f" in df.columns and "equipo" not in df.columns:
                df["equipo"] = df["equipo_f"]
            if "marca_f" in df.columns and "marca" not in df.columns:
                df["marca"] = df["marca_f"]

            cols = [c for c in ["equipo", "marca", "val"] if c in df.columns]
            if cols:
                df = df[cols]

            if "val" in df.columns:
                df = df.rename(columns={"val": "cantidad_disponible"})

        return self._clean_nan_to_na(df)

    def _movimientos_sin_destino_bodega(self, df_view: pd.DataFrame):
        if df_view is None or df_view.empty:
            return df_view
        if "destino" not in df_view.columns:
            return df_view

        df = df_view.copy()
        dest = df["destino"].astype(str).str.strip().str.lower()
        return df[dest != "bodega"]
