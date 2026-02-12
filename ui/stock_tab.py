"""
ui/stock_tab.py
Tab de control de stock (PRO) — 4 vistas: Movimientos, Stock, Bodega, Dañados
- Filtros (fecha, tipo, equipo, marca, estado, texto libre)
- Métricas y resúmenes
- Tabs internas con tablas limpias
- Descarga Excel 4 hojas con nombres claros
"""

import streamlit as st
import pandas as pd
import datetime
import io

from modules.github_handler import GitHubHandler
from modules.stock_calculator import StockCalculator


class StockTab:
    """Tab PRO de control de stock e historial"""

    def __init__(self):
        self.github = GitHubHandler()
        self.stock_calc = StockCalculator()

    def render(self):
        st.subheader("📊 Stock Real — Control & Reportes")

        # Barra superior (acciones)
        a1, a2, a3 = st.columns([1.2, 1.2, 3.6], vertical_alignment="center")
        with a1:
            if st.button("🔄 Refrescar", use_container_width=True):
                st.rerun()
        with a2:
            show_debug = st.toggle("🧪 Debug", value=False)
        with a3:
            st.caption("Fuente: historico.json (GitHub) → cálculo modular → vistas + Excel (4 hojas)")

        # Obtener histórico
        hist = self.github.obtener_historico()

        if not hist:
            st.info("Aún no hay datos en el histórico.")
            return

        self._mostrar_datos(hist, show_debug=show_debug)

    # ---------------------------------------------------------
    # Core
    # ---------------------------------------------------------
    def _mostrar_datos(self, hist, show_debug=False):
        df_h_raw = pd.DataFrame(hist)
        if df_h_raw.empty:
            st.info("Histórico vacío.")
            return

        # Calcular stock completo (NO tocamos tu lógica)
        st_res, bod_res, danados_res, df_h = self.stock_calc.calcular_stock_completo(df_h_raw)

        # Normalizaciones suaves para UI (no cambian tu data base)
        df_h = self._normalize_historial(df_h)
        st_res = self._normalize_stock(st_res, mode="stock")
        bod_res = self._normalize_stock(bod_res, mode="bodega")
        danados_res = self._normalize_stock(danados_res, mode="danados")

        # Métricas PRO
        self._mostrar_metricas_top(df_h, st_res, bod_res, danados_res)

        # Filtros (impactan vistas, no el excel si no quieres)
        with st.expander("🎛️ Filtros de vista (no altera datos, solo lo que ves)", expanded=True):
            filtros = self._ui_filtros(df_h)

        df_view = self._apply_filters(df_h, filtros)

        # Descarga Excel (4 hojas)
        self._crear_boton_descarga(st_res, bod_res, danados_res, df_h)

        # Tabs internas (lo que pediste)
        t_mov, t_stock, t_bod, t_dan = st.tabs(
            ["🧾 Movimientos", "📦 Stock (Periféricos)", "🏢 Bodega (Cómputo)", "🧯 Dañados/Chatarras"]
        )

        with t_mov:
            self._tab_movimientos(df_view, df_h)

        with t_stock:
            self._tab_stock(st_res)

        with t_bod:
            self._tab_bodega(bod_res)

        with t_dan:
            self._tab_danados(danados_res)

        if show_debug:
            with st.expander("🧪 Debug DataFrames", expanded=False):
                st.write("df_h_raw:", df_h_raw.shape)
                st.dataframe(df_h_raw.head(25), use_container_width=True)
                st.write("df_h (normalizado):", df_h.shape)
                st.dataframe(df_h.head(25), use_container_width=True)

    # ---------------------------------------------------------
    # UI Blocks
    # ---------------------------------------------------------
    def _mostrar_metricas_top(self, df_h, st_res, bod_res, danados_res):
        # Totales
        total_mov = len(df_h)
        total_stock = int(st_res.get("val", pd.Series([0])).sum()) if not st_res.empty else 0
        total_bodega = len(bod_res) if isinstance(bod_res, pd.DataFrame) else 0
        total_danados = len(danados_res) if isinstance(danados_res, pd.DataFrame) else 0

        # “Último movimiento”
        ultimo = ""
        if "fecha_registro" in df_h.columns:
            try:
                ultimo_dt = pd.to_datetime(df_h["fecha_registro"], errors="coerce").max()
                if pd.notna(ultimo_dt):
                    ultimo = ultimo_dt.strftime("%Y-%m-%d %H:%M")
            except:
                ultimo = ""

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("📜 Movimientos", total_mov, help="Cantidad total de registros en el histórico.")
        k2.metric("📦 Periféricos en Stock", total_stock, help="Suma de cantidades disponibles (stock).")
        k3.metric("🏢 Registros en Bodega", total_bodega, help="Cantidad de items que caen en la vista Bodega.")
        k4.metric("🧯 Registros Dañados/Chatarras", total_danados, help="Items marcados como dañados/obsoletos/chatarras.")

        if ultimo:
            st.caption(f"🕒 Última actividad detectada: **{ultimo}**")

        # Top quick insights
        c1, c2 = st.columns(2)
        with c1:
            top_equipo = self._top_count(df_h, "equipo", 5)
            if not top_equipo.empty:
                st.write("**Top Equipos (Movimientos)**")
                st.dataframe(top_equipo, use_container_width=True, hide_index=True)
        with c2:
            top_marca = self._top_count(df_h, "marca", 5)
            if not top_marca.empty:
                st.write("**Top Marcas (Movimientos)**")
                st.dataframe(top_marca, use_container_width=True, hide_index=True)

        st.divider()

    def _ui_filtros(self, df_h):
        # Campos disponibles
        col_fecha = "fecha_registro" if "fecha_registro" in df_h.columns else None
        col_tipo = "tipo" if "tipo" in df_h.columns else None
        col_equipo = "equipo" if "equipo" in df_h.columns else None
        col_marca = "marca" if "marca" in df_h.columns else None
        col_estado = "estado" if "estado" in df_h.columns else None

        f1, f2, f3, f4 = st.columns([1.7, 1.2, 1.2, 1.7])
        filtros = {}

        with f1:
            filtros["q"] = st.text_input(
                "🔎 Buscar texto (serie/modelo/reporte/etc.)",
                placeholder="Ej: 8th gen / LATACUNGA / ABC123 / HP...",
            ).strip()

        with f2:
            if col_tipo:
                tipos = sorted([x for x in df_h[col_tipo].dropna().unique().tolist() if str(x).strip() != ""])
                filtros["tipo"] = st.multiselect("Tipo", tipos, default=[])
            else:
                filtros["tipo"] = []

        with f3:
            if col_estado:
                estados = sorted([x for x in df_h[col_estado].dropna().unique().tolist() if str(x).strip() != ""])
                filtros["estado"] = st.multiselect("Estado", estados, default=[])
            else:
                filtros["estado"] = []

        with f4:
            filtros["max_rows"] = st.slider("Filas a mostrar", min_value=20, max_value=1000, value=120, step=20)

        f5, f6, f7 = st.columns([1.5, 1.5, 1.0])

        with f5:
            if col_equipo:
                equipos = sorted([x for x in df_h[col_equipo].dropna().unique().tolist() if str(x).strip() != ""])
                filtros["equipo"] = st.multiselect("Equipo", equipos, default=[])
            else:
                filtros["equipo"] = []

        with f6:
            if col_marca:
                marcas = sorted([x for x in df_h[col_marca].dropna().unique().tolist() if str(x).strip() != ""])
                filtros["marca"] = st.multiselect("Marca", marcas, default=[])
            else:
                filtros["marca"] = []

        with f7:
            filtros["solo_ultimos"] = st.toggle("Solo últimos", value=True, help="Limita a los últimos N movimientos.")

        # Rango de fechas si existe
        if col_fecha:
            try:
                s = pd.to_datetime(df_h[col_fecha], errors="coerce")
                s = s.dropna()
                if not s.empty:
                    min_d = s.min().date()
                    max_d = s.max().date()
                    d1, d2 = st.date_input("📅 Rango de fechas", value=(min_d, max_d))
                    filtros["date_from"] = d1
                    filtros["date_to"] = d2
                else:
                    filtros["date_from"] = None
                    filtros["date_to"] = None
            except:
                filtros["date_from"] = None
                filtros["date_to"] = None
        else:
            filtros["date_from"] = None
            filtros["date_to"] = None

        return filtros

    def _tab_movimientos(self, df_view, df_h):
        st.markdown("### 🧾 Movimientos (Histórico)")
        if df_view.empty:
            st.warning("No hay movimientos que coincidan con los filtros.")
            return

        st.dataframe(df_view, use_container_width=True, hide_index=True)

        # Quick KPIs de la vista
        c1, c2, c3 = st.columns(3)
        c1.metric("Filas visibles", len(df_view))
        c2.metric("Total histórico", len(df_h))
        if "tipo" in df_view.columns:
            c3.metric("Tipos en vista", df_view["tipo"].nunique())
        else:
            c3.metric("Tipos en vista", 0)

    def _tab_stock(self, st_res):
        st.markdown("### 📦 Stock (Periféricos)")
        if st_res is None or st_res.empty:
            st.info("No hay stock disponible (o no se han registrado periféricos).")
            return

        # ordenado por cantidad
        df = st_res.copy()
        if "val" in df.columns:
            df = df.sort_values("val", ascending=False)

        st.dataframe(df, use_container_width=True, hide_index=True)

    def _tab_bodega(self, bod_res):
        st.markdown("### 🏢 Bodega (Cómputo)")
        if bod_res is None or bod_res.empty:
            st.info("No hay registros que caigan en Bodega.")
            return

        st.dataframe(bod_res, use_container_width=True, hide_index=True)

    def _tab_danados(self, danados_res):
        st.markdown("### 🧯 Dañados / Chatarras / Bajas")
        if danados_res is None or danados_res.empty:
            st.info("No hay registros marcados como dañados/chatarras/bajas.")
            return

        st.dataframe(danados_res, use_container_width=True, hide_index=True)

    # ---------------------------------------------------------
    # Excel export (4 hojas)
    # ---------------------------------------------------------
    def _crear_boton_descarga(self, st_res, bod_res, danados_res, df_h):
        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            # Hoja 1: Movimientos
            df_h.to_excel(writer, index=False, sheet_name="MOVIMIENTOS")

            # Hoja 2: Stock
            if st_res is not None and not st_res.empty:
                st_res.to_excel(writer, index=False, sheet_name="STOCK_SALDOS")
            else:
                pd.DataFrame(columns=["equipo", "marca", "val"]).to_excel(writer, index=False, sheet_name="STOCK_SALDOS")

            # Hoja 3: Bodega
            if bod_res is not None and not bod_res.empty:
                bod_res.to_excel(writer, index=False, sheet_name="BODEGA")
            else:
                pd.DataFrame().to_excel(writer, index=False, sheet_name="BODEGA")

            # Hoja 4: Dañados
            if danados_res is not None and not danados_res.empty:
                danados_res.to_excel(writer, index=False, sheet_name="DANADOS_CHATARRA")
            else:
                pd.DataFrame().to_excel(writer, index=False, sheet_name="DANADOS_CHATARRA")

        timestamp = datetime.datetime.now().strftime("%d_%m_%H%M")

        st.download_button(
            label="📥 Descargar Excel (Movimientos / Stock / Bodega / Dañados)",
            data=buffer.getvalue(),
            file_name=f"Inventario_Jaher_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _normalize_historial(self, df):
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        # renombres si vienen variables distintas
        # (no rompe si ya existen)
        if "fecha_llegada" in df.columns and "fecha_registro" not in df.columns:
            df["fecha_registro"] = df["fecha_llegada"]

        # ordenar por fecha si existe
        if "fecha_registro" in df.columns:
            df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce")
            df = df.sort_values("fecha_registro", ascending=True)

            # formatear de vuelta para vista (bonito)
            df["fecha_registro"] = df["fecha_registro"].dt.strftime("%Y-%m-%d %H:%M")

        # asegurar columnas típicas
        for c in ["tipo", "equipo", "marca", "modelo", "serie", "estado", "origen", "destino", "reporte", "cantidad"]:
            if c not in df.columns:
                df[c] = ""

        # cantidad como número si se puede (solo vista)
        try:
            df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(1).astype(int)
        except:
            pass

        # reemplazo de NaN visual
        df = df.fillna("")

        # Orden de columnas amigable
        cols_pref = [
            "fecha_registro", "tipo", "categoria_item", "equipo", "marca", "modelo", "serie",
            "cantidad", "estado", "procesador", "ram", "disco", "origen", "destino", "guia", "reporte"
        ]
        cols_pref = [c for c in cols_pref if c in df.columns]
        resto = [c for c in df.columns if c not in cols_pref]
        return df[cols_pref + resto]

    def _normalize_stock(self, df, mode="stock"):
        if df is None:
            return pd.DataFrame()

        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Intentar normalizar nombres comunes
        # st_res normalmente trae equipo/marca/val (según tu calculador)
        if "valor_final" in df.columns and "val" not in df.columns:
            df["val"] = df["valor_final"]

        # Para vista stock: poner nombres amigables
        if mode == "stock":
            # Si viene equipo_f / marca_f
            if "equipo_f" in df.columns and "equipo" not in df.columns:
                df["equipo"] = df["equipo_f"]
            if "marca_f" in df.columns and "marca" not in df.columns:
                df["marca"] = df["marca_f"]

            # Dejar columnas clave
            cols = [c for c in ["equipo", "marca", "val"] if c in df.columns]
            if cols:
                df = df[cols]

            # Renombrar para UI
            rename = {}
            if "val" in df.columns:
                rename["val"] = "cantidad_disponible"
            df = df.rename(columns=rename)

        # Para bodega y dañados, solo limpiamos NaN
        df = df.fillna("")
        return df

    def _apply_filters(self, df, filtros):
        dfv = df.copy()

        # Texto libre (busca en todo)
        q = filtros.get("q", "")
        if q:
            q_lower = q.lower()
            mask = pd.Series([False] * len(dfv))
            for col in dfv.columns:
                try:
                    mask = mask | dfv[col].astype(str).str.lower().str.contains(q_lower, na=False)
                except:
                    pass
            dfv = dfv[mask]

        # Tipo, estado, equipo, marca
        for key in ["tipo", "estado", "equipo", "marca"]:
            vals = filtros.get(key, [])
            if vals and key in dfv.columns:
                dfv = dfv[dfv[key].isin(vals)]

        # Fecha
        d1 = filtros.get("date_from")
        d2 = filtros.get("date_to")
        if d1 and d2 and "fecha_registro" in dfv.columns:
            # fecha_registro viene formateada como string "YYYY-MM-DD HH:MM"
            try:
                s = pd.to_datetime(dfv["fecha_registro"], errors="coerce")
                dfv = dfv[(s.dt.date >= d1) & (s.dt.date <= d2)]
            except:
                pass

        # Limitar filas
        max_rows = int(filtros.get("max_rows", 120))
        if filtros.get("solo_ultimos", True):
            dfv = dfv.tail(max_rows)
        else:
            dfv = dfv.head(max_rows)

        return dfv

    def _top_count(self, df, col, n=5):
        if col not in df.columns:
            return pd.DataFrame()
        s = df[col].astype(str).str.strip()
        s = s[s != ""]
        if s.empty:
            return pd.DataFrame()
        out = s.value_counts().head(n).reset_index()
        out.columns = [col.upper(), "TOTAL"]
        return out
